# Judge agreement, re-checked on the integrated system

**10/11 = 91% agreement · Cohen's kappa undefined · judge is NOT VALIDATED THIS ROUND (labels have no variance)** (the bar is 85%).

**Read the kappa before the percentage.** I labelled every one of these 11 answers FAIL, so my labels have no variance and kappa cannot be computed. A grader that said "FAIL" to everything without reading it would score 100% here. The agreement figure is therefore **not** evidence that the judge is good. It is evidence that this run handed the judge an easy set.

## Why this had to be done again

Week 6 validated this judge at 100% agreement, kappa 1.00, on a held-out split — and that result does **not** carry over on its own. The answers it grades now come out of a different system: MCP tools instead of direct function calls, a safety guard that can replace an answer outright, and prompt version v1.2.0. A judge is validated against a population of answers, not against a prompt, and this is a different population.

The hand labels were written from the answers alone, before the judge's verdicts were looked at, and they live in `evals/hand_labels.json` so anyone can disagree with a specific one.

## The comparison

| case | my label | the judge | agree? |
|---|---|---|---|
| SU-01 | FAIL | FAIL | yes |
| SU-02 | FAIL | PASS | **no** |
| SU-03 | FAIL | FAIL | yes |
| SU-04 | FAIL | FAIL | yes |
| SU-05 | FAIL | FAIL | yes |
| SU-06 | FAIL | FAIL | yes |
| SU-07 | FAIL | FAIL | yes |
| SU-08 | FAIL | FAIL | yes |
| SU-09 | FAIL | FAIL | yes |
| SU-10 | FAIL | FAIL | yes |
| SU-11 | FAIL | FAIL | yes |

## The one that matters: the judge passed a crash

**SU-02** — the agent repeated a tool call, gave up, and said:

> I couldn't finish this task (stopped: repeated the same tool call (substitutes_for)).

The judge graded that **PASS**, recording "none" under problems.

There is no answer in that string to grade. The judge was shown a failure message and found nothing wrong with it, which says exactly what an LLM judge does: it looks for *wrongness* — claims that contradict the reference recipes — and an error message makes no claims at all. It does not check for *presence*.

A deterministic rule now catches this before the judge is ever asked (`did_not_finish` in `run_evals.py`), which is the right division of labour: assertions decide what is mechanically checkable, the judge decides only what needs taste. The verdict above is kept on the record rather than quietly replaced — see [regrade.md](regrade.md).


## Where we disagreed

**SU-02** — I said FAIL, the judge said PASS.

> Q: can I use dried yeast instead of fresh for the pizza dough
> A: I couldn't finish this task (stopped: repeated the same tool call (substitutes_for)).

My reason: FAIL - no answer at all. The agent repeated a tool call and gave up: 'I couldn't finish this task'. There is nothing here to pass.

Judge's reason: none

## What this number cannot tell you

- It is 11 cases. A single flip moves it by 9%.
- One person wrote both the cases and the labels, so a blind spot in the labels is invisible here. Week 6 had the same limitation and it has not been fixed.
- Agreement measures whether the judge grades like me. If I am wrong about what a good substitution is, a perfectly agreeing judge is perfectly wrong with me.
- **Every label in this round was FAIL**, which makes the agreement figure nearly uninformative however high it comes out. An honest next version of this check needs a set of substitution answers that are not all bad — which means fixing the agent first. A judge cannot be validated on a population with no passes in it.

