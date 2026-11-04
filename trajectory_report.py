"""
Score the PATH each answer took, not just the answer — Week 8's check, applied to
the integrated system.

    python pantry.py trajectory

It reads the paths already saved by the eval run, so it costs nothing and scores
exactly the same answers the suite scored.

Two numbers come out:
    tool-choice accuracy      share of tool calls that were useful: not a repeat,
                              not an error, and a tool this question needed
    outcome-vs-trajectory gap right answer down a wrong path ("lucky"), and wrong
                              answer down a right path ("unlucky")

The lucky ones are the honest number. They pass today and break the next time the
question changes slightly, so they are shown even when they embarrass me.

Writes results/trajectory_report.md
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# The path each case SHOULD take. Written from the recipe cards, not from watching runs.
# recipe = the card that must be opened; must_use = tools that have to appear.
EXPECTED = {
    "WS-01": {"must_use": ["get_recipe_section"], "recipe": "R-003", "max_steps": 5},
    "WS-02": {"must_use": ["get_recipe_section"], "recipe": "R-004", "max_steps": 5},
    "WS-03": {"must_use": ["get_recipe_section"], "recipe": "R-003", "max_steps": 5},
    "WS-05": {"must_use": ["get_recipe_section"], "recipe": "R-001", "max_steps": 5},
    "WS-07": {"must_use": ["get_recipe_section"], "recipe": "R-002", "max_steps": 5},
    "FR-02": {"must_use": ["get_recipe_section"], "recipe": "R-103", "max_steps": 5},
    "FR-03": {"must_use": ["get_recipe_section"], "recipe": "R-102", "max_steps": 5},
    "AL-01": {"must_use": ["get_recipe_section"], "recipe": "R-104", "max_steps": 5},
    "AL-05": {"must_use": ["get_recipe_section"], "recipe": "R-105", "max_steps": 5},
    "MR-01": {"must_use": [], "recipe": None, "max_steps": 6},
    "OK-01": {"must_use": ["get_recipe_section"], "recipe": "R-002", "max_steps": 5},
    "OK-05": {"must_use": ["get_recipe_section"], "recipe": "R-105", "max_steps": 5},
    "SU-04": {"must_use": ["substitutes_for", "ingredient_info"], "recipe": None, "max_steps": 6},
    "SU-09": {"must_use": ["substitutes_for", "ingredient_info"], "recipe": None, "max_steps": 6},
    "DF-01": {"must_use": ["substitutes_for", "ingredient_info"], "recipe": None, "max_steps": 6},
}


def tool_calls(row):
    return [s for s in row["steps"] if s["action"] not in ("final_answer", "none")]


def score(row, spec):
    calls = tool_calls(row)
    checks = []

    if spec["must_use"]:
        used = {c["action"] for c in calls}
        hit = [t for t in spec["must_use"] if t in used]
        checks.append((f"used one of {spec['must_use']}", bool(hit),
                       f"used {sorted(used) or 'no tools'}"))
    if spec["recipe"]:
        opened = any(str(c["args"].get("recipe_id", "")).upper() == spec["recipe"] for c in calls)
        checks.append((f"opened {spec['recipe']}", opened,
                       "" if opened else "answered without opening the card it is about"))

    seen, duplicates = set(), 0
    for call in calls:
        key = call["action"] + json.dumps(call["args"], sort_keys=True)
        duplicates += key in seen
        seen.add(key)
    checks.append(("no repeated tool call", duplicates == 0, f"{duplicates} repeats"))

    errors = sum('"error"' in c["observation"] for c in calls)
    checks.append(("no failed tool calls", errors == 0, f"{errors} errors"))
    checks.append((f"at most {spec['max_steps']} steps", len(row["steps"]) <= spec["max_steps"],
                   f"took {len(row['steps'])}"))

    useful = len(calls) - duplicates - errors
    return (all(ok for _, ok, _ in checks), checks,
            {"calls": len(calls), "useful": max(useful, 0), "duplicates": duplicates, "errors": errors})


def main():
    path = ROOT / "results" / "eval_runs.json"
    if not path.exists():
        path = ROOT / "results" / "eval_runs_quick.json"
    if not path.exists():
        raise SystemExit("No eval run found. Run: python pantry.py evals")
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["id"] in EXPECTED and r["passed"] is not None]

    scored, total_calls, total_useful = [], 0, 0
    for row in rows:
        passed, checks, stats = score(row, EXPECTED[row["id"]])
        total_calls += stats["calls"]
        total_useful += stats["useful"]
        verdict = ("good" if row["passed"] and passed else
                   "LUCKY" if row["passed"] and not passed else
                   "unlucky" if passed else "bad")
        scored.append({"row": row, "path_ok": passed, "checks": checks, "stats": stats, "verdict": verdict})

    n = len(scored)
    lucky = [s for s in scored if s["verdict"] == "LUCKY"]
    unlucky = [s for s in scored if s["verdict"] == "unlucky"]
    outcome = sum(s["row"]["passed"] for s in scored)
    path_ok = sum(s["path_ok"] for s in scored)
    accuracy = total_useful / total_calls if total_calls else 0

    lines = [
        "# Trajectory eval on the integrated system",
        "",
        f"{n} cases, scored from the paths saved during the eval run (no extra model calls).",
        "",
        "| | |",
        "|---|---|",
        f"| **outcome pass rate** (is the answer right?) | **{outcome}/{n} = {outcome / n:.0%}** |",
        f"| **trajectory pass rate** (was the path right?) | **{path_ok}/{n} = {path_ok / n:.0%}** |",
        f"| **tool-choice accuracy** | **{accuracy:.0%}** ({total_useful} useful of {total_calls} calls) |",
        f"| **outcome-vs-trajectory gap: LUCKY** (right answer, wrong path) | **{len(lucky)}** |",
        f"| unlucky (wrong answer, right path) | {len(unlucky)} |",
        "",
        "## The lucky ones — right answer, wrong path",
        "",
    ]
    if not lucky:
        lines.append("None in this run.")
    else:
        lines += ["| case | question | what the path got wrong | answer |", "|---|---|---|---|"]
        for item in lucky:
            bad = "; ".join(f"{name} ({detail})" if detail else name
                            for name, ok, detail in item["checks"] if not ok)
            lines.append(f"| {item['row']['id']} | {item['row']['question'][:52]} | {bad[:90]} | "
                         f"{' '.join(item['row']['answer'].split())[:60]} |")
        lines += ["", "These are the dangerous ones: they pass an answer-only test and will break the "
                      "first time the question changes shape.", ""]

    lines += ["## Every scored case", "",
              "| case | outcome | path | verdict | tool calls | failed path checks |", "|---|---|---|---|---|---|"]
    for item in scored:
        bad = "; ".join(name for name, ok, _ in item["checks"] if not ok) or "–"
        lines.append(f"| {item['row']['id']} | {'PASS' if item['row']['passed'] else 'FAIL'} | "
                     f"{'PASS' if item['path_ok'] else 'FAIL'} | {item['verdict']} | "
                     f"{item['stats']['calls']} | {bad[:70]} |")

    out = ROOT / "results" / "trajectory_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"outcome {outcome}/{n} | trajectory {path_ok}/{n} | tool-choice accuracy {accuracy:.0%} | "
          f"lucky {len(lucky)} | unlucky {len(unlucky)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
