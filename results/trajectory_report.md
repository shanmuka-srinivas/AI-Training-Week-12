# Trajectory eval on the integrated system

15 cases, scored from the paths saved during the eval run (no extra model calls).

| | |
|---|---|
| **outcome pass rate** (is the answer right?) | **1/15 = 7%** |
| **trajectory pass rate** (was the path right?) | **5/15 = 33%** |
| **tool-choice accuracy** | **77%** (23 useful of 30 calls) |
| **outcome-vs-trajectory gap: LUCKY** (right answer, wrong path) | **0** |
| unlucky (wrong answer, right path) | 4 |

## The lucky ones — right answer, wrong path

None in this run.
## Every scored case

| case | outcome | path | verdict | tool calls | failed path checks |
|---|---|---|---|---|---|
| WS-01 | FAIL | FAIL | bad | 8 | used one of ['get_recipe_section']; opened R-003; at most 5 steps |
| WS-02 | FAIL | FAIL | bad | 1 | used one of ['get_recipe_section']; opened R-004; no failed tool calls |
| WS-03 | FAIL | PASS | unlucky | 2 | – |
| WS-05 | FAIL | PASS | unlucky | 3 | – |
| WS-07 | FAIL | FAIL | bad | 3 | opened R-002; no failed tool calls |
| FR-02 | FAIL | FAIL | bad | 1 | used one of ['get_recipe_section']; opened R-103 |
| FR-03 | FAIL | FAIL | bad | 1 | opened R-102 |
| AL-01 | FAIL | FAIL | bad | 1 | used one of ['get_recipe_section']; opened R-104; no failed tool calls |
| AL-05 | FAIL | FAIL | bad | 1 | used one of ['get_recipe_section']; opened R-105 |
| SU-04 | FAIL | FAIL | bad | 1 | no failed tool calls |
| SU-09 | FAIL | FAIL | bad | 3 | no failed tool calls |
| MR-01 | FAIL | PASS | unlucky | 1 | – |
| OK-01 | FAIL | FAIL | bad | 1 | opened R-002; no failed tool calls |
| OK-05 | FAIL | PASS | unlucky | 2 | – |
| DF-01 | PASS | PASS | good | 1 | – |
