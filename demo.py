"""
The four-part demo, in order.

    python pantry.py demo              all four parts (~4 min on the local model)
    python pantry.py demo --part 2     just one part

The four parts the capstone asks for:

    1  IT WORKS        a real question, answered from the cards, with sources
    2  IT FAILS, AND I KNOW          the same question with the guard off and on,
                                     plus the trace that proves which one shipped
    3  HOW I KNOW IT WORKS           the numbers, read from the saved eval run
    4  WHAT IT COSTS TO RUN          per-stage cost, p50/p99, and the 10x plan

Nothing here is staged. Parts 1 and 2 make live model calls; parts 3 and 4 read
results that are already in the repo, so a demo never depends on a 35-minute run
finishing on time.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

LINE = "=" * 78

# Our print() calls are block-buffered as soon as this output is piped to a file
# or a pager, but the subprocess.run() children below write STRAIGHT to the same
# pipe. Unbuffered, that means every child report lands ABOVE the banner that is
# supposed to introduce it, and part 4's banner gets nothing under it at all.
# On a bare terminal it looks fine, which is why it survived until someone
# captured the output -- which is the first thing a reviewer does.
try:
    sys.stdout.reconfigure(line_buffering=True)
except (AttributeError, OSError):
    pass


def banner(number, title, promise):
    print(f"\n{LINE}\n  PART {number} — {title}\n  {promise}\n{LINE}\n")


def show(record, indent="  "):
    print(f"{indent}Q: {record['question']}")
    print(f"{indent}A: {' '.join(record['answer'].split())}")
    if record.get("citations"):
        print(f"{indent}sources:")
        for cite in record["citations"]:
            print(f"{indent}  - {cite['cite']}")
    else:
        print(f"{indent}sources: (none — this answer cites nothing)")
    totals = record["totals"]
    print(f"{indent}trace: {record['trace_id']}   "
          f"{totals['ms'] / 1000:.0f}s  {totals['tokens']} tokens  ${totals['cost_usd']:.5f}")


# ---------------------------------------------------------------------------

def part1(toolbox):
    banner(1, "IT WORKS",
           "a real question, answered from the cards, with the card and section named")
    from app import answer_question

    print("  The cook has a kilo of cabbage and the card is written for 2 kg.")
    print("  The model must not do this arithmetic itself — a tool does it.\n")
    record = answer_question(
        "I have 1 kg of white cabbage. How much salt do I need for the sauerkraut?",
        toolbox, user_id="u-demo", verbose=False)
    show(record)
    print("\n  Note what is NOT here: no invented gram figure, and a source you can open.")
    return record


def part2(toolbox):
    banner(2, "IT FAILS, AND I KNOW ABOUT IT",
           "the incident, reproduced, then the fix, then the proof of which one shipped")
    from app import answer_question
    from evals.case_dairy_free import CASE

    print("  2026-10-20: a dairy-free cook asked for a buttermilk substitute and was told")
    print("  to use milk plus lemon juice. The complaint said only 'maybe Tuesday'.\n")

    print("  The guard-off condition runs THREE times, not once. The first version of this")
    print("  demo ran it once, happened to get a safe answer, and proved nothing. That is")
    print("  the finding: an undefended model is not reliably unsafe, it is UNRELIABLY SAFE,")
    print("  and one sample cannot tell those apart.\n")

    print("  --- the same question with the guard OFF (this is the incident), 3 trials")
    safe = 0
    for i in range(3):
        red = answer_question(CASE["question"], toolbox, user_id="u-demo", verbose=False,
                              guard_enabled=False)
        passed, why = CASE["check"](red["answer"])
        safe += passed
        print(f"      trial {i + 1}/3  {'SAFE' if passed else 'UNSAFE'}  {red['trace_id']}")
        print(f"               {' '.join(red['answer'].split())[:108]}")
    print(f"\n      guard off: {safe}/3 safe here. Over 5 trials in "
          "results/failure_loop.md: 1/5.")

    print("\n  --- the same question with the guard ON (this is what ships)")
    green = answer_question(CASE["question"], toolbox, user_id="u-demo", verbose=False)
    show(green, indent="      ")
    green_pass, green_why = CASE["check"](green["answer"])
    print(f"      eval DF-01: {'PASS (GREEN)' if green_pass else 'FAIL'} — {green_why[:70]}")
    print("      guard on: 5/5 safe over 5 trials.")

    print("\n  The guard is Python, not a prompt. The prompt was tried first and the model")
    print("  ignored it. Code it cannot ignore was the only thing that worked.\n")

    print(f"  --- and here is how I would find this from a complaint: trace {green['trace_id']}")
    sys.stdout.flush()
    subprocess.run([sys.executable, "pantry.py", "trace", green["trace_id"]], cwd=ROOT)
    print("\n  Same trace id in our log AND in the MCP servers' own log. One question,")
    print("  followed all the way out of this process and back.")
    return green


def part3():
    banner(3, "HOW I KNOW IT WORKS",
           "the numbers, and what they do not cover")
    path = ROOT / "results" / "eval_runs.json"
    if not path.exists():
        path = ROOT / "results" / "eval_runs_quick.json"
    if not path.exists():
        print("  No saved eval run. Run: python pantry.py evals")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"  {data['scored']} scored cases, {data['passed']} passed "
          f"= {data['pass_rate']:.0%}, in {data['seconds'] / 60:.0f} minutes.\n")

    by_type = {}
    for row in data["rows"]:
        if row["passed"] is None:
            continue
        bucket = by_type.setdefault(row["type"], [0, 0])
        bucket[0] += bool(row["passed"])
        bucket[1] += 1
    print("  | question type | passed |")
    print("  |---|---|")
    for kind, (ok, total) in sorted(by_type.items(), key=lambda kv: -kv[1][1]):
        print(f"  | {kind:22} | {ok}/{total} |")

    print("\n  --- the path, not just the answer")
    sys.stdout.flush()
    subprocess.run([sys.executable, "trajectory_report.py"], cwd=ROOT)
    print("\n  --- and where the failures cluster")
    sys.stdout.flush()
    subprocess.run([sys.executable, "taxonomy_report.py"], cwd=ROOT)
    print("\n  What these numbers do NOT cover: ten cards in one person's handwriting.")
    print("  The parser drops 11 of 16 realistic rows from an eleventh card, silently.")


def part4():
    banner(4, "WHAT IT COSTS TO RUN",
           "per stage, not one lump — plus what 10x traffic would break first")
    sys.stdout.flush()
    subprocess.run([sys.executable, "cost_report.py"], cwd=ROOT)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="the four-part demo")
    parser.add_argument("--part", type=int, choices=[1, 2, 3, 4])
    args = parser.parse_args()
    parts = [args.part] if args.part else [1, 2, 3, 4]
    started = time.perf_counter()

    if any(p in parts for p in (1, 2)):
        from agent.mcp_client import MCPToolbox
        with MCPToolbox() as toolbox:
            print(f"\ntools discovered over MCP at startup: {', '.join(sorted(toolbox.tools))}")
            if 1 in parts:
                part1(toolbox)
            if 2 in parts:
                part2(toolbox)
    if 3 in parts:
        part3()
    if 4 in parts:
        part4()

    print(f"\n{LINE}\n  demo finished in {time.perf_counter() - started:.0f} s\n{LINE}")


if __name__ == "__main__":
    main()
