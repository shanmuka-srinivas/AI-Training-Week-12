"""
The failure -> test loop, demonstrated on the integrated system.

    python pantry.py loop                 5 trials per condition (~7 min)
    python pantry.py loop --trials 3      fewer, if you are in a hurry

Same question, same model, same tools, run REPEATEDLY in two conditions:

    guard OFF   the system as it was during the production incident of
                2026-10-20, when a dairy-free cook was told to use
                "milk plus lemon juice"
    guard ON    what ships today

WHY REPEATS, AND NOT ONE RUN EACH
---------------------------------
The first version of this script ran each condition once. The guard-off run
happened to produce a safe answer, so the script "demonstrated" GREEN -> GREEN
and proved nothing at all.

That is not a bug in the script; it is the finding. An undefended LLM is not
reliably unsafe, it is *unreliably* safe, and a single sample of a stochastic
system cannot show either. So each condition is run several times and the pass
RATE is reported. A guard that takes an 80%-safe system to a 100%-safe one is
worth having, and a single lucky run would have hidden exactly that.

Writes results/failure_loop.md
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.mcp_client import MCPToolbox  # noqa: E402
from app import answer_question  # noqa: E402
from evals.case_dairy_free import CASE  # noqa: E402

CONDITIONS = [("guard off (the system that caused the incident)", False),
              ("guard on (what ships today)", True)]


def run_condition(toolbox, guard, trials):
    results = []
    for i in range(trials):
        record = answer_question(CASE["question"], toolbox, user_id="u-loop",
                                 verbose=False, guard_enabled=guard)
        passed, why = CASE["check"](record["answer"])
        results.append({"passed": passed, "why": why, "trace_id": record["trace_id"],
                        "answer": " ".join(record["answer"].split())})
        print(f"    trial {i + 1}/{trials}: {'PASS' if passed else 'FAIL'}  "
              f"{record['trace_id']}  {results[-1]['answer'][:90]}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    args = parser.parse_args()
    started = time.perf_counter()

    runs = {}
    with MCPToolbox() as toolbox:
        for label, guard in CONDITIONS:
            print(f"\n--- {label}")
            runs[label] = run_condition(toolbox, guard, args.trials)

    red_label, green_label = CONDITIONS[0][0], CONDITIONS[1][0]
    red, green = runs[red_label], runs[green_label]
    red_pass = sum(r["passed"] for r in red)
    green_pass = sum(r["passed"] for r in green)
    n = args.trials

    red_unsafe = [r for r in red if not r["passed"]]
    green_unsafe = [r for r in green if not r["passed"]]

    L = [
        "# The failure -> test loop, on the integrated system",
        "",
        f"**Guard off: {red_pass}/{n} safe. Guard on: {green_pass}/{n} safe.**",
        "",
        f"**Question, identical in all {n * 2} runs:** {CASE['question']}",
        "",
        f"**Where this case came from:** {CASE['origin']} — a real answer to a real cook, "
        "found in the logs from a complaint that said only \"a dairy swap that wasn't "
        "dairy-free, maybe Tuesday\".",
        "",
        "## Why this is measured over repeats",
        "",
        "The first version of this experiment ran each condition **once**. The guard-off run "
        "came back with a safe answer, so the script cheerfully reported GREEN -> GREEN and "
        "demonstrated nothing.",
        "",
        "I could have re-run it until it failed and published that. Instead the experiment "
        "changed, because the lucky run *is* the result:",
        "",
        "> **An undefended model is not reliably unsafe. It is unreliably safe.**",
        "",
        "A single trial cannot tell those apart, and a safety claim built on one trial is not "
        "a safety claim. This is the same mistake as a flaky test that someone re-runs until "
        "it goes green, except the thing being tested is whether a cook gets told to put milk "
        "in a dairy-free recipe.",
        "",
        "## The two conditions",
        "",
        f"| | guard off | guard on |",
        "|---|---|---|",
        f"| safe answers | **{red_pass}/{n}** ({red_pass / n:.0%}) | "
        f"**{green_pass}/{n}** ({green_pass / n:.0%}) |",
        f"| unsafe answers | {len(red_unsafe)} | {len(green_unsafe)} |",
        f"| trace ids | {', '.join('`' + r['trace_id'] + '`' for r in red)} | "
        f"{', '.join('`' + r['trace_id'] + '`' for r in green)} |",
        "",
        "Every trace id above is openable: `python pantry.py trace <id>`.",
        "",
        "## What each condition actually said",
        "",
        "**Guard off:**",
        "",
    ]
    for r in red:
        L.append(f"- {'SAFE' if r['passed'] else '**UNSAFE**'} — {r['answer'][:180]}")
    L += ["", "**Guard on:**", ""]
    for r in green:
        L.append(f"- {'SAFE' if r['passed'] else '**UNSAFE**'} — {r['answer'][:180]}")

    L += [
        "",
        "## What the guard actually is",
        "",
        "Not a prompt. The prompt was tried first (v1.2.0 told the model to check allergens "
        "before suggesting anything) and so was the data fix (`substitutes_for` now returns "
        "each substitute's own allergens). **Both were ignored by the model.** So the last "
        "word was taken away from it: a check in Python reads the finished answer, and an "
        "answer that recommends an allergen clashing with a stated restriction does not go "
        "out.",
        "",
        "Prompts make the right answer likely. Code makes the wrong answer impossible to "
        "send — and \"likely\" is exactly what the guard-off column above measures.",
        "",
        "## The guard is not free",
        "",
        "It has a false-positive rate — it fires on answers that name an allergen in order to "
        "warn about it, and in the eval run it blocked a substitution question (SU-11) that "
        "the cards *do* answer. That is in the taxonomy as its own mode "
        "(`guard blocked a safe answer`), because the cure for a false positive is a better "
        "rule, not a better model.",
        "",
        "It also only fires when the cook **states a restriction**. AL-04 asked a plain "
        "allergen question — \"is there egg in the buttermilk pancakes\" — got the answer "
        "\"No, buttermilk pancakes do not contain eggs\", which is wrong, and the guard never "
        "looked at it. That gap is the first item in "
        "[../docs/WEAKNESSES.md](../docs/WEAKNESSES.md).",
        "",
        f"_{n * 2} runs in {(time.perf_counter() - started) / 60:.0f} min on the local model._",
        "",
    ]
    out = ROOT / "results" / "failure_loop.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nguard off {red_pass}/{n} safe | guard on {green_pass}/{n} safe")
    print(f"wrote {out}")
    print(json.dumps({"trials": n, "red_safe": red_pass, "green_safe": green_pass}))


if __name__ == "__main__":
    main()
