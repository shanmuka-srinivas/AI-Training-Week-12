"""
PANTRY-TO-PLATE ASSISTANT — the single entry point.

Everything from the twelve weeks lives behind this one command.

    python pantry.py ask "I have 1 kg of cabbage. How much salt for the sauerkraut?"
    python pantry.py ask --dietary "dairy-free" "What can I use instead of buttermilk?"

    python pantry.py doctor          is everything wired up? (no model needed, ~10s)
    python pantry.py tools           what the agent discovered over MCP, right now
    python pantry.py trace <id>      one request, every span, cost and citations
    python pantry.py logs --flag diet_conflict      search every past answer
    python pantry.py evals           the full suite against the integrated system
    python pantry.py trajectory      score the PATHS taken, not just the answers
    python pantry.py taxonomy        re-score the error taxonomy from real traces
    python pantry.py cost            cost per request by stage, and the 10x plan
    python pantry.py loop            the failure->test loop, live: RED then GREEN
    python pantry.py demo            the four-part demo, in order

WHERE THE MODEL RUNS: here, in this process, and nowhere else. The MCP servers
are separate processes that read recipe cards and do arithmetic; they never call
a model, and they never receive the cook's own words.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _python(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT).returncode


# ---------------------------------------------------------------------------
# ask: one question, end to end
# ---------------------------------------------------------------------------

def cmd_ask(args):
    from agent.mcp_client import MCPToolbox
    from app import answer_question

    question = " ".join(args.question)
    if args.dietary:
        question = f"I'm {args.dietary}. {question}"

    with MCPToolbox() as toolbox:
        print(f"tools discovered over MCP: {', '.join(sorted(toolbox.tools))}\n")
        record = answer_question(question, toolbox, user_id=args.user, verbose=not args.quiet,
                                 guard_enabled=not args.no_guard)

    print(f"\nQ: {record['question']}")
    print(f"A: {record['answer']}\n")
    if record.get("citations"):
        print("sources:")
        for citation in record["citations"]:
            print(f"   {citation['cite']}")
    else:
        print("sources: NONE — treat this answer as unsupported")
    if record.get("safety_guard"):
        print(f"\nsafety guard fired: {record['safety_guard']['conflicts']}")
        print(f"   suppressed: {record['safety_guard']['suppressed_answer'][:120]}")
    if record.get("blocked_tool_calls"):
        print(f"\nprivacy guard blocked {len(record['blocked_tool_calls'])} tool call(s) "
              f"from leaving this process")
    totals = record["totals"]
    print(f"\ntrace_id {record['trace_id']} · prompt {record['prompt_version']} · "
          f"{totals['ms'] / 1000:.0f}s · {totals['tokens']} tokens · ${totals['cost_usd']:.6f}")
    print(f"follow it: python pantry.py trace {record['trace_id']}")


# ---------------------------------------------------------------------------
# doctor: can a stranger tell whether this thing is actually wired up?
# ---------------------------------------------------------------------------

def cmd_doctor(args):
    ok = True
    print("Pantry-to-Plate: checking the seams\n")

    cards = sorted((ROOT / "data" / "recipes").glob("*.md"))
    print(f"  [{'ok' if cards else 'XX'}] recipe cards: {len(cards)} found")
    ok &= bool(cards)

    try:
        import mcp  # noqa: F401
        print("  [ok] mcp SDK importable")
    except ImportError:
        print("  [XX] mcp SDK missing — pip install -r requirements.txt")
        ok = False

    try:
        from agent.mcp_client import MCPToolbox
        with MCPToolbox() as toolbox:
            print(f"  [ok] MCP servers reachable: {', '.join(toolbox.server_info)}")
            print(f"  [ok] tools discovered at runtime: {len(toolbox.tools)} "
                  f"({', '.join(sorted(toolbox.tools))})")
            result = toolbox.call("get_recipe_section", {"recipe_id": "R-106", "section": "ingredients"},
                                  trace_id="doctor-check")
            served = "error" not in result
            print(f"  [{'ok' if served else 'XX'}] a live tool call returns real card text")
            ok &= served
            blocked = toolbox.call("search_recipes",
                                   {"query": "I am dairy free and allergic to peanuts and I would like "
                                             "to know what to use instead of buttermilk please"},
                                   trace_id="doctor-check", user_text="x")
            held = "refused" in json.dumps(blocked)
            print(f"  [{'ok' if held else 'XX'}] privacy line holds (free text refused at the boundary)")
            ok &= held
    except Exception as error:
        print(f"  [XX] MCP layer failed: {error}")
        ok = False

    audit = ROOT / "logs" / "mcp_server.jsonl"
    if audit.exists():
        ids = {json.loads(line)["trace_id"] for line in audit.read_text(encoding="utf-8").splitlines() if line.strip()}
        print(f"  [ok] server-side audit log present, {len(ids)} distinct trace ids")
    else:
        print("  [--] no server audit log yet (ask a question and it appears)")

    try:
        from llama_cpp import Llama  # noqa: F401
        print("  [ok] local model library present")
    except ImportError:
        print("  [XX] llama-cpp-python missing — see README, the model is needed for `ask` and `evals`")
        ok = False

    print(f"\n{'READY' if ok else 'NOT READY — fix the XX lines above'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# small commands that wrap the parts
# ---------------------------------------------------------------------------

def cmd_tools(args):
    from agent.mcp_client import MCPToolbox
    with MCPToolbox() as toolbox:
        for name, info in toolbox.server_info.items():
            print(f"\n{name}  (v{info['version']}, MCP {info['protocol']})")
            for tool in info["tool_names"]:
                print(f"    - {tool}")
        print(f"\n{len(toolbox.tools)} tools discovered at runtime, none hardcoded in the agent.")


def cmd_trace(args):
    from obs.trace_log import read_log
    found = [r for r in read_log() if r["trace_id"] == args.trace_id]
    if not found:
        print(f"no request with trace id {args.trace_id}")
        return 1
    record = found[0]
    print(json.dumps(record, indent=2, ensure_ascii=False))

    audit = ROOT / "logs" / "mcp_server.jsonl"
    if audit.exists():
        hops = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()
                if line.strip() and json.loads(line)["trace_id"] == args.trace_id]
        print(f"\n--- the same trace id on the OTHER side of the MCP hop ({len(hops)} tool calls) ---")
        for hop in hops:
            print(f"  {hop['ts']}  {hop['server']:<14} {hop['tool']:<20} {json.dumps(hop['args'])}")
    return 0


def cmd_logs(args):
    return _python("logsearch.py", *args.rest)


def cmd_evals(args):
    code = _python("run_evals.py", *(["--quick"] if args.quick else []))
    if code == 0:
        # Regenerate the write-up straight away, so no number in docs/ can drift
        # away from the run that produced it.
        _python("eval_report.py")
    return code


def cmd_judge(args):
    return _python("judge_agreement.py", *(["--show"] if args.show else []))


def cmd_trajectory(args):
    return _python("trajectory_report.py")


def cmd_taxonomy(args):
    return _python("taxonomy_report.py")


def cmd_cost(args):
    return _python("cost_report.py")


def cmd_loop(args):
    return _python("failure_loop.py", "--trials", str(args.trials))


def cmd_demo(args):
    extra = ["--part", str(args.part)] if args.part else []
    return _python("demo.py", *extra)


def main():
    parser = argparse.ArgumentParser(description="Pantry-to-Plate Assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="ask the assistant one question")
    ask.add_argument("question", nargs="+")
    ask.add_argument("--dietary", help="a restriction to state, e.g. 'dairy-free'")
    ask.add_argument("--user", default="u-0001")
    ask.add_argument("--quiet", action="store_true")
    ask.add_argument("--no-guard", action="store_true", help="disable the safety guard (for the demo)")
    ask.set_defaults(func=cmd_ask)

    sub.add_parser("doctor", help="check every seam without needing the model").set_defaults(func=cmd_doctor)
    sub.add_parser("tools", help="what is discovered over MCP right now").set_defaults(func=cmd_tools)

    trace = sub.add_parser("trace", help="one request, both sides of the MCP hop")
    trace.add_argument("trace_id")
    trace.set_defaults(func=cmd_trace)

    logs = sub.add_parser("logs", help="search past answers (passes flags to logsearch.py)")
    logs.add_argument("rest", nargs=argparse.REMAINDER)
    logs.set_defaults(func=cmd_logs)

    evals = sub.add_parser("evals", help="the full suite against the integrated system")
    evals.add_argument("--quick", action="store_true", help="a 12-case subset")
    evals.set_defaults(func=cmd_evals)

    judge = sub.add_parser("judge", help="re-check the LLM judge against hand labels")
    judge.add_argument("--show", action="store_true", help="print the answers to label")
    judge.set_defaults(func=cmd_judge)

    sub.add_parser("trajectory", help="score the paths taken").set_defaults(func=cmd_trajectory)
    sub.add_parser("taxonomy", help="re-score the error taxonomy").set_defaults(func=cmd_taxonomy)
    sub.add_parser("cost", help="cost per stage and the 10x plan").set_defaults(func=cmd_cost)
    loop = sub.add_parser("loop", help="the failure->test loop, measured over repeats")
    loop.add_argument("--trials", type=int, default=5, help="runs per condition (default 5)")
    loop.set_defaults(func=cmd_loop)
    demo = sub.add_parser("demo", help="the four-part demo")
    demo.add_argument("--part", type=int, choices=[1, 2, 3, 4], help="run just one part")
    demo.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    raise SystemExit(args.func(args) or 0)


if __name__ == "__main__":
    main()
