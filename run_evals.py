"""
The full eval suite, against the INTEGRATED system, in one command.

    python pantry.py evals            all 47 cases (~35 min on the local model)
    python pantry.py evals --quick    a 12-case subset (~9 min)

What runs:
  * the 46 cases from the Week 6 suite, unchanged
  * DF-01, the case born from the Week 11 dairy-free incident
  * assertions FIRST, because they are free and exact; the Gemini judge only for
    the 11 substitution cases, where no rule can decide

Every answer comes from the real app: same agent, same MCP tools, same logging,
same safety guard. Each case's whole path is saved, so the trajectory and
taxonomy reports score this same run instead of paying for another one.

Writes results/eval_runs.json
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("APP_ENV", "eval")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.mcp_client import MCPToolbox  # noqa: E402
from app import answer_question  # noqa: E402
from evals.case_dairy_free import CASE as DAIRY_CASE  # noqa: E402
from evals.cases import CASES  # noqa: E402
from evals.checks import rule_checks  # noqa: E402

QUICK_IDS = ["WS-01", "WS-03", "FR-02", "FR-03", "AL-01", "AL-05", "MR-01", "MR-02",
             "OK-01", "OK-05", "SU-04", "SU-09"]

# Words that mean "I am not going to answer this".
#
# NOTE what is deliberately NOT in this list: "does not contain" and "do not
# contain". The first version of this file had them, and it cost two correct
# answers. "No, buttermilk pancakes do not contain eggs" is not a refusal — it
# is the exact shape a correct negative allergen answer takes, and scoring it as
# a refusal failed AL-04 and AL-05 for being right.
REFUSAL_WORDS = ("cannot", "can not", "could not", "no information", "does not say",
                 "not available", "unable", "not provided", "no record", "do not record",
                 "no safe substitute", "not recorded", "cant", "couldnt", "dont have",
                 "do not have")


def looks_like_refusal(answer):
    flat = answer.lower().replace("'", "")
    return any(word.replace("'", "") in flat for word in REFUSAL_WORDS)


def did_not_finish(record_status):
    """
    An agent that gave up is not an agent that refused.

    Week 10 had this exact bug and it is back: the agent hits its step limit or
    repeats a tool call, says "I couldn't finish this task", and the refusal
    detector reads "couldnt" and scores it as a polite refusal — which PASSES a
    must_refuse case. Two of the five passes in the first run of this suite were
    crashes. A stop is its own outcome and it fails, whatever the case wanted.
    """
    return record_status.startswith("stopped")


def grade_with_rules(case, record):
    if did_not_finish(record["status"]):
        return False, f"did not finish ({record['status']})"
    citations = record["citations"]
    result = {"answer": record["answer"], "refused": looks_like_refusal(record["answer"]),
              "refusal_reason": "",
              "citation": citations[0]["cite"] if citations else None,
              "cited_recipe_id": next((c["recipe_id"] for c in citations if c["recipe_id"]), None),
              "context": [{"recipe_id": c["recipe_id"], "body": ""} for c in citations]}
    checks = rule_checks(case, result)
    failed = [name for name, ok, _ in checks if not ok]
    return all(ok for _, ok, _ in checks), ("; ".join(failed) or "all checks passed")


def main():
    quick = "--quick" in sys.argv
    cases = [c for c in CASES if not quick or c["id"] in QUICK_IDS]
    judged = [c for c in cases if c.get("judge") == "substitution"]
    print(f"{len(cases)} Week-6 cases + 1 incident case | {len(judged)} need the judge\n")

    rows, started = [], time.perf_counter()
    with MCPToolbox() as toolbox:
        for case in cases + [DAIRY_CASE]:
            record = answer_question(case["question"], toolbox, user_id="u-eval")
            row = {"id": case["id"], "type": case["type"], "question": case["question"],
                   "answer": record["answer"], "trace_id": record["trace_id"],
                   "citations": record["citations"], "steps": record["steps"],
                   "status": record["status"], "guard": bool(record.get("safety_guard")),
                   "seconds": record["totals"]["ms"] / 1000, "tokens": record["totals"]["tokens"],
                   "cost_usd": record["totals"]["cost_usd"], "graded_by": "rules"}
            if did_not_finish(record["status"]):
                row["passed"] = False
                row["why"] = f"did not finish ({record['status']})"
                row["graded_by"] = "no answer to grade"
            elif case["id"] == "DF-01":
                row["passed"], row["why"] = case["check"](record["answer"])
                row["graded_by"] = "incident check"
            elif case.get("judge") == "substitution":
                row["passed"], row["why"], row["graded_by"] = None, "awaiting judge", "judge"
            else:
                row["passed"], row["why"] = grade_with_rules(case, record)
            rows.append(row)
            mark = {True: "PASS", False: "FAIL", None: "  ?  "}[row["passed"]]
            print(f"  {row['id']:7} {mark}  {row['why'][:58]}")

    if judged:
        print(f"\njudging {len(judged)} substitution answers with Gemini...")
        try:
            from evals.judge import SubstitutionJudge

            judge = SubstitutionJudge()
            by_id = {c["id"]: c for c in judged}
            for row in rows:
                if row["graded_by"] != "judge":
                    continue
                case = by_id[row["id"]]
                verdict = judge.grade(case["question"], row["answer"],
                                      row["citations"][0]["cite"] if row["citations"] else None,
                                      case["reference_recipes"])
                if verdict is None:
                    row["why"] = "judge quota exhausted"
                    continue
                row["passed"] = verdict["verdict"] == "PASS"
                row["why"] = verdict["notes"]["problems"][:90]
                row["judge_notes"] = verdict["notes"]
                print(f"  {row['id']:7} {'PASS' if row['passed'] else 'FAIL'}  {row['why'][:58]}")
        except SystemExit as stop:
            print(f"  judge unavailable: {stop}")

    scored = [r for r in rows if r["passed"] is not None]
    passed = sum(r["passed"] for r in scored)
    out = {"cases": len(rows), "scored": len(scored), "passed": passed,
           "pass_rate": passed / len(scored) if scored else 0,
           "seconds": round(time.perf_counter() - started, 1), "rows": rows}
    (ROOT / "results").mkdir(exist_ok=True)
    name = "eval_runs_quick.json" if quick else "eval_runs.json"
    (ROOT / "results" / name).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSUITE: {passed}/{len(scored)} scored cases passed ({out['pass_rate']:.0%}) "
          f"in {out['seconds'] / 60:.0f} min -> results/{name}")


if __name__ == "__main__":
    main()
