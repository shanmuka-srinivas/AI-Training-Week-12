# Architecture, on one page

Boxes, arrows, where the model runs, and where the money goes.

```
                            ┌───────────────┐
                            │   the cook    │
                            └───────┬───────┘
                                    │  a question in plain English
                                    ▼
╔════════════════════════ pantry.py (ONE process) ════════════════════════════╗
║                                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ obs/trace_log.py — a trace id is minted HERE, before anything else      │  ║
║  │ every span below is timed, costed and written under that one id         │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                    │                                         ║
║                                    ▼                                         ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ agent/agent.py — think → act → observe, max 6 steps                     │  ║
║  │                                                                         │  ║
║  │    ╔═══════════════════════════════════════════════════════╗            │  ║
║  │    ║  $$  agent/llm_local.py — Qwen2.5-3B on llama.cpp     ║  ◄── ALL   │  ║
║  │    ║      THE ONLY PLACE A MODEL RUNS IN THE WHOLE APP     ║     money  │  ║
║  │    ║      ~30 s per call · 1–4 calls per question          ║     and    │  ║
║  │    ╚═══════════════════════════════════════════════════════╝     time   │  ║
║  │                                                                         │  ║
║  │  the scratchpad is re-sent as REAL CHAT TURNS each step, which is why    │  ║
║  │  cost grows faster than step count (week 7's expensive lesson)           │  ║
║  └──────────────────────────────┬─────────────────────────────────────────┘  ║
║                                 │                                            ║
║  ┌──────────────────────────────▼─────────────────────────────────────────┐  ║
║  │ agent/mcp_client.py — THE PRIVACY LINE                                  │  ║
║  │   · injects the trace id into every call                                │  ║
║  │   · refuses any argument longer than 8 words                            │  ║
║  │     (8 words is a sentence, not an identifier — the cook's own words     │  ║
║  │      must not leave this process)                                       │  ║
║  └──────────────────────────────┬─────────────────────────────────────────┘  ║
╚═════════════════════════════════╪════════════════════════════════════════════╝
                                  │  MCP · JSON-RPC over stdio
                                  │  initialize → tools/list → tools/call
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
┌──────────────────────────────┐      ┌──────────────────────────────────────┐
│ mcp_servers/recipe_server.py │      │ mcp_servers/ingredient_server.py     │
│   search_recipes             │      │   ingredient_info                    │
│   get_recipe_section         │      │   substitutes_for                    │
│   scale_recipe   ← the maths │      │   grams_to_cups                      │
│                              │      │                                      │
│  NO MODEL. NO NETWORK.       │      │  NO MODEL. NO NETWORK.               │
│  Writes logs/mcp_server.jsonl with the SAME trace id → both sides of the    │
│  hop can be read as one story.                                             │
└──────────────┬───────────────┘      └────────────────┬─────────────────────┘
               │                                       │
               └───────────────────┬───────────────────┘
                                   │  plain JSON back
                                   ▼
╔════════════════════════ back in pantry.py ══════════════════════════════════╗
║  obs/flags.py — THE SAFETY GUARD                                             ║
║     code, not a prompt. Reads the finished answer. If the cook stated a       ║
║     restriction and the answer recommends something that clashes, the         ║
║     answer is REPLACED. The model does not get the last word.                 ║
║                                   │                                          ║
║  app.py build_citations() — recipe id · section · file                        ║
║                                   │                                          ║
║  logs/requests.jsonl — one line per request: spans, tokens, cost, flags        ║
╚═══════════════════════════════════╪══════════════════════════════════════════╝
                                    ▼
                    answer + sources + trace id
```

## Where the money goes

Measured by `cost_report.py` over the real request log, not estimated:

| stage | share of time | share of cost | why |
|---|---|---|---|
| model calls in the agent loop | **98%** | **100%** | 1–4 calls at ~30 s each; the scratchpad is re-sent every step |
| search / embedding | 2% | 0% | ten cards, embedded once at startup |
| MCP tool calls | 0% | 0% | process spawn + file read; no model, no network |
| the guard, citations, logging | 0% | 0% | string work on one answer |

Per request: **$0.000318** at API prices, **p50 41 s / p99 61 s** on this laptop.

One consequence worth stating plainly: **every optimisation that matters is a
reduction in model calls.** Caching tool results, a tighter prompt, or stopping
the loop one step earlier are all worth more than anything done to the servers.

## Where each week ended up

| week | what it contributed | file |
|---|---|---|
| 3–4 | chunking, embeddings, BM25, hybrid fusion | `rag/` |
| 5 | error taxonomy, open coding | `taxonomy_report.py` |
| 6 | 46 eval cases, rule checks, validated judge | `evals/` |
| 7 | the hand-written agent loop | `agent/agent.py` |
| 8 | trajectory evals, injection defences | `trajectory_report.py` |
| 9 | MCP servers and client | `mcp_servers/`, `agent/mcp_client.py` |
| 10 | multi-agent lessons (**deliberately not shipped** — see SEAMS.md) | – |
| 11 | tracing, flags, the safety guard, cost reporting | `obs/`, `cost_report.py` |
| 12 | the single entry point that makes it one app | `pantry.py` |
