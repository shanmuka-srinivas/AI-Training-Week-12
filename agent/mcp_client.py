"""
The MCP CLIENT side: connect to whatever servers the config lists, ask each one
what it can do, and offer those tools to the agent.

THE THREE ROLES, in our project:

    HOST    our agent process. It runs the model and decides what to call.
    CLIENT  this file. One connection per server, speaking MCP.
    SERVER  mcp_servers/*.py, and anyone else's server we add to the config.

Nothing here knows the name of a single tool. The tool list comes from the
server's own tools/list reply at start-up, which is what makes adding a second
server a config change rather than a code change.

MCP is asynchronous and our agent loop is plain synchronous Python, so the
connections live on a background thread with their own event loop, and this
class is the ordinary blocking front door to them.
"""

import asyncio
import json
import re
import threading
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "mcp_servers.json"


class MCPToolbox:
    """Every tool discovered from every configured server."""

    def __init__(self, config_path=DEFAULT_CONFIG):
        self.config_path = Path(config_path)
        self.servers = json.loads(self.config_path.read_text(encoding="utf-8"))["mcpServers"]
        self.tools = {}          # tool name -> {"server", "description", "schema"}
        self.server_info = {}    # server name -> {"version", "tool_names"}
        self.call_log = []
        self.blocked_calls = []
        self._loop = None
        self._thread = None
        self._ready = threading.Event()
        self._stop = None

    # ---- lifecycle ---------------------------------------------------------

    def __enter__(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._error:
            raise self._error
        return self

    def __exit__(self, *exc):
        if self._loop:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread:
            self._thread.join(timeout=20)

    _error = None

    def _run_loop(self):
        asyncio.run(self._main())

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        self._sessions = {}
        try:
            async with self._connect_all():
                self._ready.set()
                await self._stop.wait()
        except Exception as error:   # surfaced on the calling thread
            self._error = error
            self._ready.set()

    def _connect_all(self):
        """Open every configured server and keep them all open together."""
        from contextlib import AsyncExitStack, asynccontextmanager

        @asynccontextmanager
        async def opened():
            async with AsyncExitStack() as stack:
                for name, spec in self.servers.items():
                    params = StdioServerParameters(
                        command=spec["command"], args=spec.get("args", []), env=spec.get("env"),
                    )
                    read, write = await stack.enter_async_context(stdio_client(params))
                    session = await stack.enter_async_context(ClientSession(read, write))
                    initialised = await session.initialize()

                    listing = await session.list_tools()          # <- DISCOVERY
                    self._sessions[name] = session
                    self.server_info[name] = {
                        "server_name": initialised.server_info.name,
                        "version": initialised.server_info.version,
                        "protocol": initialised.protocol_version,
                        "tool_names": [t.name for t in listing.tools],
                    }
                    for tool in listing.tools:
                        key = tool.name if tool.name not in self.tools else f"{name}.{tool.name}"
                        self.tools[key] = {
                            "server": name,
                            "real_name": tool.name,
                            "description": (tool.description or "").strip(),
                            "schema": tool.input_schema or {},
                        }
                yield

        return opened()

    # ---- what the agent uses ----------------------------------------------

    # Parameters that exist for the plumbing and must never be shown to the model.
    #
    # trace_id is ours, not the model's. While it WAS visible, the model dutifully
    # filled it in with "trace1", so the app-side span recorded `trace_id: trace1`
    # while the client's injection quietly sent the real id to the server. Nothing
    # broke on the wire, but the log said one thing and the server's log said
    # another, which is the worst kind of logging bug: it is wrong only where you
    # go to look when something else is wrong. A field the caller always overrides
    # has no business being in the caller's prompt.
    HIDDEN_ARGS = ("trace_id",)

    def descriptions(self):
        """
        The tool list, written out for the model, straight from tools/list.

        Plumbing parameters are filtered out: the model chooses tools and real
        arguments, never transport details.
        """
        blocks = []
        for name, tool in self.tools.items():
            schema = {k: v for k, v in (tool["schema"].get("properties", {}) or {}).items()
                      if k not in self.HIDDEN_ARGS}
            required = set(tool["schema"].get("required", []) or [])
            args = ", ".join(
                f"{arg}: {spec.get('type', 'any')}" + ("" if arg in required else " (optional)")
                for arg, spec in schema.items()
            )
            blocks.append(f"{name}({args})\n    {tool['description']}")
        return "\n\n".join(blocks)

    # The longest thing we will ever send a server as an argument. A recipe id or an
    # ingredient name is short; anything longer is the cook's own sentence, which is
    # where a dietary restriction or a health detail lives. See block_long_text below.
    MAX_ARG_WORDS = 8

    def call(self, name, args, trace_id=None, user_text=None):
        """
        Run a discovered tool and hand back plain data.

        trace_id   stamped onto the call so the server can log the same id we do, and
                   one request can be followed across the hop. Injected here, by the
                   client, so the model never has to be trusted to pass it.
        user_text  the cook's original question, supplied ONLY so we can check it is
                   not being forwarded. It is never sent.
        """
        tool = self.tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool '{name}'. Available: {', '.join(self.tools)}."}

        # Anything the model invented for a plumbing parameter is dropped before it
        # is looked at, let alone sent. The model no longer sees these fields, but
        # "it cannot see it" is not a control; discarding it is.
        args = {k: v for k, v in (args or {}).items() if k not in self.HIDDEN_ARGS}

        # ---- the privacy line, enforced in code ---------------------------------
        blocked = self._leaking_arguments(args, user_text)
        if blocked:
            self.blocked_calls.append({"tool": name, "args": args, "reason": blocked})
            return {"error": f"refused to send that to the {tool['server']} server: {blocked}",
                    "next_step": "Call this tool with just the recipe id or the ingredient name."}

        if trace_id and "trace_id" in (tool["schema"].get("properties") or {}):
            args = {**args, "trace_id": trace_id}
        future = asyncio.run_coroutine_threadsafe(self._call(tool, args or {}), self._loop)
        result = future.result(timeout=60)
        self.call_log.append({"tool": name, "server": tool["server"], "args": args})
        return result

    async def _call(self, tool, args):
        session = self._sessions[tool["server"]]
        try:
            result = await session.call_tool(tool["real_name"], dict(args))
        except Exception as error:
            # A broken call must come back as data the model can read and retry from,
            # never as a crash that ends the run.
            return {"error": f"the tool call failed: {error}"}
        if getattr(result, "structured_content", None):
            inner = result.structured_content
            return inner.get("result", inner) if isinstance(inner, dict) else inner
        texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        joined = "\n".join(texts)
        try:
            return json.loads(joined)
        except (json.JSONDecodeError, TypeError):
            return {"text": joined}

    def _leaking_arguments(self, args, user_text):
        """
        Would this call send the cook's own words to a server?

        The tools need a recipe id, a section name, an ingredient and a number. None of
        those is a sentence. So a long free-text argument, or one that repeats the
        question, is a leak and is stopped here rather than politely discouraged in a
        prompt.
        """
        question_words = set(re.findall(r"[a-z0-9-]+", (user_text or "").lower()))
        for key, value in (args or {}).items():
            if not isinstance(value, str):
                continue
            words = value.split()
            if len(words) > self.MAX_ARG_WORDS:
                return f"the '{key}' argument is {len(words)} words long, which is free text, not an identifier"
            value_words = set(re.findall(r"[a-z0-9-]+", value.lower()))
            if user_text and len(words) >= 4 and len(value_words & question_words) >= 4:
                return f"the '{key}' argument repeats the cook's own question"
        return None

    def which_server(self, tool_name):
        tool = self.tools.get(tool_name)
        return tool["server"] if tool else "unknown"
