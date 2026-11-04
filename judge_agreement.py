"""
Re-check the LLM judge against hand labels — on the INTEGRATED system's answers.

    python judge_agreement.py --show      print the 11 substitution answers to label
    python judge_agreement.py             score my labels against the judge

Week 6 validated this judge on answers from the Week 6 app and got 100% agreement
(kappa 1.00) on a held-out split. That validation does not automatically carry
over: the answers it grades now come through MCP tools, a safety guard and a
different prompt version, so they are a different population. A judge is
validated against a population, not against a prompt.

The bar is 85% agreement. Below that the judge's verdicts are reported as
untrusted rather than quietly used.

Labels live in evals/hand_labels.json so they are version-controlled and can be
argued with: {"SU-01": "PASS", ...}

Writes results/judge_agreement.md
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

LABELS = ROOT / "evals" / "hand_labels.json"
BAR = 0.85


def load_run():
    """
    Read the judge's OWN verdicts, from before the re-grade overrode any of them.

    This matters for SU-02. The judge graded a crash message ("I couldn't finish
    this task") as a PASS; the re-grade later overrode that verdict with a
    did-not-finish rule, which would quietly remove the judge's worst mistake
    from its own scorecard. So the raw file is the source here, and the override
    is reported rather than allowed to hide the error.
    """
    raw = ROOT / "results" / "eval_runs.raw.json"
    path = raw if raw.exists() else ROOT / "results" / "eval_runs.json"
    if not path.exists():
        raise SystemExit("No eval run found. Run: python pantry.py evals")
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["graded_by"] == "judge"]

    live = ROOT / "results" / "eval_runs.json"
    if live.exists() and live.resolve() != path.resolve():
        after = {r["id"]: r for r in json.loads(live.read_text(encoding="utf-8"))["rows"]}
        for row in rows:
            row["_overridden"] = after.get(row["id"], {}).get("graded_by") == "no answer to grade"
    return rows


def show(rows):
    print(f"\n{len(rows)} substitution answers to label by hand.")
    print("Grade each one PASS or FAIL on its own merits, WITHOUT looking at the")
    print("judge's verdict, then write them into evals/hand_labels.json.\n")
    for row in rows:
        print("=" * 76)
        print(f"{row['id']}  Q: {row['question']}")
        print(f"\nA: {' '.join(row['answer'].split())}")
        cites = ", ".join(c["cite"] for c in row["citations"]) or "(none)"
        print(f"\nsources: {cites}")
        print(f"trace:   {row['trace_id']}")
    print("=" * 76)
    print("\nTemplate for evals/hand_labels.json:")
    print(json.dumps({row["id"]: "PASS" for row in rows}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="print the answers to label")
    args = parser.parse_args()

    rows = load_run()
    if args.show:
        return show(rows)

    if not LABELS.exists():
        raise SystemExit(f"No hand labels yet. Run with --show, then write {LABELS}")
    raw_labels = json.loads(LABELS.read_text(encoding="utf-8"))
    reasons = raw_labels.get("_why", {})
    labels = {k: v for k, v in raw_labels.items() if not k.startswith("_")}

    compared, agree = [], 0
    for row in rows:
        if row["id"] not in labels or row["passed"] is None:
            continue
        human = labels[row["id"]].upper() == "PASS"
        judge = bool(row["passed"])
        agree += human == judge
        compared.append({"id": row["id"], "human": human, "judge": judge, "row": row})

    n = len(compared)
    if not n:
        raise SystemExit("Nothing to compare: no labelled case was graded by the judge.")
    rate = agree / n

    # Cohen's kappa over two binary raters.
    both_pass = sum(c["human"] and c["judge"] for c in compared)
    both_fail = sum(not c["human"] and not c["judge"] for c in compared)
    human_pass = sum(c["human"] for c in compared)
    judge_pass = sum(c["judge"] for c in compared)
    po = (both_pass + both_fail) / n
    pe = (human_pass * judge_pass + (n - human_pass) * (n - judge_pass)) / (n * n)
    # Kappa is UNDEFINED when a rater used only one label: there is no variance to
    # correct for and pe collapses to 1. Printing 1.00 there would be a lie dressed
    # up as a statistic, so it is reported as undefined and explained in the text.
    degenerate = human_pass in (0, n) or judge_pass in (0, n)
    kappa = None if (degenerate or pe >= 1) else (po - pe) / (1 - pe)
    kappa_text = "undefined" if kappa is None else f"{kappa:.2f}"

    disagreements = [c for c in compared if c["human"] != c["judge"]]
    # A high agreement rate over a label set with no variance is not validation.
    # If every label is the same, a constant grader scores just as well, so the
    # only honest verdict is "this round could not validate the judge".
    if kappa is None:
        verdict = "NOT VALIDATED THIS ROUND (labels have no variance)"
    elif rate >= BAR:
        verdict = "TRUSTED"
    else:
        verdict = "NOT TRUSTED"

    L = [
        "# Judge agreement, re-checked on the integrated system",
        "",
        f"**{agree}/{n} = {rate:.0%} agreement · Cohen's kappa {kappa_text} · judge is "
        f"{verdict}** (the bar is {BAR:.0%}).",
        "",
        "**Read the kappa before the percentage.** I labelled every one of these "
        f"{n} answers FAIL, so my labels have no variance and kappa cannot be computed. A "
        "grader that said \"FAIL\" to everything without reading it would score "
        f"{max(human_pass, n - human_pass) / n:.0%} here. The agreement figure is therefore "
        "**not** evidence that the judge is good. It is evidence that this run handed the "
        "judge an easy set.",
        "",
        "## Why this had to be done again",
        "",
        "Week 6 validated this judge at 100% agreement, kappa 1.00, on a held-out split — and "
        "that result does **not** carry over on its own. The answers it grades now come out of "
        "a different system: MCP tools instead of direct function calls, a safety guard that "
        "can replace an answer outright, and prompt version v1.2.0. A judge is validated "
        "against a population of answers, not against a prompt, and this is a different "
        "population.",
        "",
        "The hand labels were written from the answers alone, before the judge's verdicts were "
        "looked at, and they live in `evals/hand_labels.json` so anyone can disagree with a "
        "specific one.",
        "",
        "## The comparison",
        "",
        "| case | my label | the judge | agree? |",
        "|---|---|---|---|",
    ]
    for c in compared:
        L.append(f"| {c['id']} | {'PASS' if c['human'] else 'FAIL'} | "
                 f"{'PASS' if c['judge'] else 'FAIL'} | {'yes' if c['human'] == c['judge'] else '**no**'} |")

    overridden = [c for c in compared if c["row"].get("_overridden")]
    if overridden:
        L += ["", "## The one that matters: the judge passed a crash", ""]
        for c in overridden:
            row = c["row"]
            L += [
                f"**{row['id']}** — the agent repeated a tool call, gave up, and said:",
                "",
                f"> {' '.join(row['answer'].split())}",
                "",
                f"The judge graded that **{'PASS' if c['judge'] else 'FAIL'}**, recording "
                f"\"{row.get('why', '(no reason)')[:80]}\" under problems.",
                "",
                "There is no answer in that string to grade. The judge was shown a failure "
                "message and found nothing wrong with it, which says exactly what an LLM "
                "judge does: it looks for *wrongness* — claims that contradict the reference "
                "recipes — and an error message makes no claims at all. It does not check "
                "for *presence*.",
                "",
                "A deterministic rule now catches this before the judge is ever asked "
                "(`did_not_finish` in `run_evals.py`), which is the right division of "
                "labour: assertions decide what is mechanically checkable, the judge decides "
                "only what needs taste. The verdict above is kept on the record rather than "
                "quietly replaced — see [regrade.md](regrade.md).",
                "",
            ]

    L += ["", "## Where we disagreed", ""]
    if not disagreements:
        L.append("Nowhere. Which is a smaller result than it sounds: with "
                 f"{n} cases, perfect agreement is what you get when the cases are easy, not "
                 "necessarily when the judge is good.")
    else:
        for c in disagreements:
            row = c["row"]
            L += [
                f"**{row['id']}** — I said {'PASS' if c['human'] else 'FAIL'}, "
                f"the judge said {'PASS' if c['judge'] else 'FAIL'}.",
                "",
                f"> Q: {row['question']}",
                f"> A: {' '.join(row['answer'].split())[:300]}",
                "",
                f"My reason: {reasons.get(row['id'], '(not recorded)')}",
                "",
                f"Judge's reason: {row.get('why', '(none recorded)')[:200]}",
                "",
            ]

    L += [
        "## What this number cannot tell you",
        "",
        f"- It is {n} cases. A single flip moves it by {1 / n:.0%}.",
        "- One person wrote both the cases and the labels, so a blind spot in the labels is "
        "invisible here. Week 6 had the same limitation and it has not been fixed.",
        "- Agreement measures whether the judge grades like me. If I am wrong about what a "
        "good substitution is, a perfectly agreeing judge is perfectly wrong with me.",
        "- **Every label in this round was FAIL**, which makes the agreement figure nearly "
        "uninformative however high it comes out. An honest next version of this check needs "
        "a set of substitution answers that are not all bad — which means fixing the agent "
        "first. A judge cannot be validated on a population with no passes in it.",
        "",
    ]

    out = ROOT / "results" / "judge_agreement.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{agree}/{n} = {rate:.0%} agreement | kappa {kappa_text} | {verdict}")
    for c in disagreements:
        print(f"   disagreed on {c['id']}: me {'PASS' if c['human'] else 'FAIL'}, "
              f"judge {'PASS' if c['judge'] else 'FAIL'}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
