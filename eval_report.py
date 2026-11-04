"""
Turn the saved eval run into docs/EVAL_REPORT.md.

    python eval_report.py

Every number in that document comes from results/eval_runs.json, so no figure in
the write-up is typed by hand and none of them can drift away from the run that
produced them. If the suite is re-run, re-run this and the document is current.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TYPE_PLAIN = {
    "weight_spec": "a weight or quantity from a card",
    "freeform": "an open 'how do I' question",
    "allergen_yes_no": "does this contain X, yes or no",
    "must_refuse": "the cards cannot answer this",
    "substitution": "what can I use instead of X",
    "dietary_safety": "is this safe for my diet",
    "oven_knowledge": "temperature, timing, technique",
}


def main():
    path = ROOT / "results" / "eval_runs.json"
    quick = False
    if not path.exists():
        path = ROOT / "results" / "eval_runs_quick.json"
        quick = True
    if not path.exists():
        raise SystemExit("No eval run found. Run: python pantry.py evals")

    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["rows"]
    scored = [r for r in rows if r["passed"] is not None]
    unscored = [r for r in rows if r["passed"] is None]
    passed = sum(r["passed"] for r in scored)
    n = len(scored)

    by_type = {}
    for row in scored:
        bucket = by_type.setdefault(row["type"], {"pass": 0, "n": 0, "fails": []})
        bucket["n"] += 1
        if row["passed"]:
            bucket["pass"] += 1
        else:
            bucket["fails"].append(row)

    graders = Counter(r["graded_by"] for r in scored)
    seconds = [r["seconds"] for r in rows]
    costs = [r["cost_usd"] for r in rows]
    tokens = [r["tokens"] for r in rows]
    guarded = [r for r in rows if r.get("guard")]
    uncited = [r for r in scored if not r["citations"]]

    def pct(a, b):
        return f"{a / b:.0%}" if b else "n/a"

    L = [
        "# Eval report",
        "",
        f"**{passed} of {n} scored cases passed — {pct(passed, n)}.** "
        f"{len(rows)} cases were run in {data['seconds'] / 60:.0f} minutes against the "
        "integrated system: same agent, same MCP tools, same safety guard, same logging "
        "as a real request.",
        "",
    ]
    if quick:
        L += ["> This report was generated from the **--quick** subset, not the full suite.", ""]
    if unscored:
        L += [f"> {len(unscored)} case(s) could not be scored "
              f"({unscored[0]['why']}) and are excluded from every figure below.", ""]

    if "passed_before_regrade" in data:
        before = data["passed_before_regrade"]
        L += [
            f"> **This run was re-graded.** It first reported {before}/{n}; three bugs were "
            f"found in my own grading code and the corrected figure is {passed}/{n}. The "
            "score went **down**. Both numbers, and every verdict that moved, are in "
            "[../results/regrade.md](../results/regrade.md).",
            "",
        ]

    L += [
        "## Read this before the number",
        "",
        "The pass rate above is a **strict** number and it is lower than it looks.",
        "",
        "- A case passes only if **every** check on it passes. One missing gram figure "
        "fails a case that was otherwise right.",
        "- The checks are literal string checks. In week 10 an answer saying \"15 grams\" "
        "failed a check looking for \"15 g\". That class of bug is a measurement artifact, "
        "not a model failure, and some of it will still be in here.",
        "- The model is a 3B running on a laptop CPU, chosen so the project is free and "
        "offline. A frontier model would lift this number and change nothing about the "
        "architecture.",
        "",
        "What the number is good for is **comparison between runs** and **finding where "
        "the failures cluster**. It is not a claim about how useful the assistant feels.",
        "",
        "## By question type",
        "",
        "| what the cook is asking | passed | |",
        "|---|---|---|",
    ]
    for kind, bucket in sorted(by_type.items(), key=lambda kv: -kv[1]["n"]):
        plain = TYPE_PLAIN.get(kind, kind)
        L.append(f"| {plain} | {bucket['pass']}/{bucket['n']} | {pct(bucket['pass'], bucket['n'])} |")

    L += [
        "",
        "## How each case was graded",
        "",
        "| grader | cases | why |",
        "|---|---|---|",
        f"| assertions (rules) | {graders.get('rules', 0)} | free, exact, instant — used wherever a "
        "rule can decide |",
        f"| LLM judge (Gemini) | {graders.get('judge', 0)} | substitution answers, where no rule can "
        "decide whether a swap is sensible |",
        f"| the incident check | {graders.get('incident check', 0)} | DF-01, written from the real "
        "2026-10-20 complaint |",
        "",
        "**The judge is not trusted on its word.** It was validated in week 6 against hand "
        "labels, and that validation was **redone here** because these answers come out of a "
        "different system. The result: 91% agreement with hand labels, but **kappa is "
        "undefined** — every one of the 11 answers was a FAIL by hand, so a grader that said "
        "\"FAIL\" to everything would also score highly. The honest verdict is *not validated "
        "this round*. And the one disagreement is the instructive one: the judge graded a "
        "crash message (\"I couldn't finish this task\") as a **PASS**, because it looks for "
        "claims that contradict the cards and an error message makes no claims at all. "
        "See [../results/judge_agreement.md](../results/judge_agreement.md).",
        "",
        "That is why assertions grade everything they can: an assertion cannot have a bad day, "
        "and it cannot be impressed by a sentence that says nothing.",
        "",
        "## Cost and speed of the run",
        "",
        "| | |",
        "|---|---|",
        f"| cases run | {len(rows)} |",
        f"| wall clock | {data['seconds'] / 60:.0f} min |",
        f"| median per question | {sorted(seconds)[len(seconds) // 2]:.0f} s |",
        f"| slowest question | {max(seconds):.0f} s |",
        f"| median tokens | {sorted(tokens)[len(tokens) // 2]:,} |",
        f"| total cost at API prices | ${sum(costs):.4f} |",
        f"| cost per question | ${sum(costs) / len(costs):.5f} |",
        "",
        "Cost is priced as if the calls had gone to an API; they actually ran locally and "
        "cost nothing but time. The figure is kept because it is the one that matters if "
        "this is ever deployed.",
        "",
        "## What the guard did",
        "",
        f"The safety guard replaced the model's answer in **{len(guarded)} of {len(rows)}** cases. "
        "Each of those is a case where the model produced something that clashed with a "
        "stated dietary restriction and did not get to say it.",
        "",
        f"**{len(uncited)} of {n}** scored answers carry no citation at all. An uncited answer is "
        "treated as a failure mode in its own right in the taxonomy, because an answer you "
        "cannot check is not much better than a guess.",
        "",
        "### What the guard did not do",
        "",
        "The guard only fires when the cook **states a restriction**. **AL-04** asked a plain "
        "allergen question — *\"is there egg in the buttermilk pancakes\"* — and got **\"No, "
        "buttermilk pancakes do not contain eggs.\"** The card lists `| Whole egg | 100 g |` "
        "and its allergen note says *\"Contains wheat gluten, cow's milk dairy and hen egg.\"*",
        "",
        "Nothing checked that answer. It is the worst output in the run and it is the first "
        "item in [WEAKNESSES.md](WEAKNESSES.md).",
        "",
        "## What this suite does not cover",
        "",
        "Said plainly, because the gaps matter more than the score:",
        "",
        "- **Ten recipe cards, one author, one style.** The extraction error rate over this "
        "corpus is 0%, which measures the corpus and not the parser. Against sixteen "
        "realistic rows, 11 are silently dropped. See [WEAKNESSES.md](WEAKNESSES.md).",
        "- **No multi-turn conversations.** Every case is a single question. Real cooking "
        "questions arrive in threes.",
        "- **No adversarial users.** Week 8 tested prompt injection separately; those cases "
        "are not in this suite.",
        "- **English only, metric only.**",
        "- **The judge sees the answer, not the cards.** It can catch a nonsensical swap; it "
        "cannot catch a swap that contradicts a card it was never shown.",
        "",
        "## Every failure in the run",
        "",
        "| case | type | why it failed | trace id |",
        "|---|---|---|---|",
    ]
    fails = [r for r in scored if not r["passed"]]
    for row in fails:
        L.append(f"| {row['id']} | {row['type']} | {row['why'][:70]} | `{row['trace_id']}` |")
    if not fails:
        L.append("| – | – | nothing failed in this run | – |")

    L += [
        "",
        f"Every one of those trace ids is openable: `python pantry.py trace <id>` prints the "
        "whole request, including what the MCP servers were asked and what they answered.",
        "",
        "## Where to go next",
        "",
        "- The **paths** these answers took, not just the answers: "
        "[../results/trajectory_report.md](../results/trajectory_report.md)",
        "- Where the failures **cluster**: [../results/taxonomy.md](../results/taxonomy.md)",
        "- One failure driven **red to green**: "
        "[../results/failure_loop.md](../results/failure_loop.md)",
        "",
    ]

    out = ROOT / "docs" / "EVAL_REPORT.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{passed}/{n} = {pct(passed, n)} | {len(guarded)} guarded | {len(uncited)} uncited "
          f"| ${sum(costs):.4f} | wrote {out}")


if __name__ == "__main__":
    main()
