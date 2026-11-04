# Eval report

**3 of 47 scored cases passed — 6%.** 47 cases were run in 33 minutes against the integrated system: same agent, same MCP tools, same safety guard, same logging as a real request.

> **This run was re-graded.** It first reported 5/47; three bugs were found in my own grading code and the corrected figure is 3/47. The score went **down**. Both numbers, and every verdict that moved, are in [../results/regrade.md](../results/regrade.md).

## Read this before the number

The pass rate above is a **strict** number and it is lower than it looks.

- A case passes only if **every** check on it passes. One missing gram figure fails a case that was otherwise right.
- The checks are literal string checks. In week 10 an answer saying "15 grams" failed a check looking for "15 g". That class of bug is a measurement artifact, not a model failure, and some of it will still be in here.
- The model is a 3B running on a laptop CPU, chosen so the project is free and offline. A frontier model would lift this number and change nothing about the architecture.

What the number is good for is **comparison between runs** and **finding where the failures cluster**. It is not a claim about how useful the assistant feels.

## By question type

| what the cook is asking | passed | |
|---|---|---|
| what can I use instead of X | 0/11 | 0% |
| wrong_sentence | 0/10 | 0% |
| false_refusal | 0/7 | 0% |
| the cards cannot answer this | 0/6 | 0% |
| already_working | 1/6 | 17% |
| does this contain X, yes or no | 1/5 | 20% |
| indirect | 0/1 | 0% |
| is this safe for my diet | 1/1 | 100% |

## How each case was graded

| grader | cases | why |
|---|---|---|
| assertions (rules) | 33 | free, exact, instant — used wherever a rule can decide |
| LLM judge (Gemini) | 10 | substitution answers, where no rule can decide whether a swap is sensible |
| the incident check | 1 | DF-01, written from the real 2026-10-20 complaint |

**The judge is not trusted on its word.** It was validated in week 6 against hand labels, and that validation was **redone here** because these answers come out of a different system. The result: 91% agreement with hand labels, but **kappa is undefined** — every one of the 11 answers was a FAIL by hand, so a grader that said "FAIL" to everything would also score highly. The honest verdict is *not validated this round*. And the one disagreement is the instructive one: the judge graded a crash message ("I couldn't finish this task") as a **PASS**, because it looks for claims that contradict the cards and an error message makes no claims at all. See [../results/judge_agreement.md](../results/judge_agreement.md).

That is why assertions grade everything they can: an assertion cannot have a bad day, and it cannot be impressed by a sentence that says nothing.

## Cost and speed of the run

| | |
|---|---|
| cases run | 47 |
| wall clock | 33 min |
| median per question | 27 s |
| slowest question | 156 s |
| median tokens | 2,110 |
| total cost at API prices | $0.0164 |
| cost per question | $0.00035 |

Cost is priced as if the calls had gone to an API; they actually ran locally and cost nothing but time. The figure is kept because it is the one that matters if this is ever deployed.

## What the guard did

The safety guard replaced the model's answer in **3 of 47** cases. Each of those is a case where the model produced something that clashed with a stated dietary restriction and did not get to say it.

**15 of 47** scored answers carry no citation at all. An uncited answer is treated as a failure mode in its own right in the taxonomy, because an answer you cannot check is not much better than a guess.

### What the guard did not do

The guard only fires when the cook **states a restriction**. **AL-04** asked a plain allergen question — *"is there egg in the buttermilk pancakes"* — and got **"No, buttermilk pancakes do not contain eggs."** The card lists `| Whole egg | 100 g |` and its allergen note says *"Contains wheat gluten, cow's milk dairy and hen egg."*

Nothing checked that answer. It is the worst output in the run and it is the first item in [WEAKNESSES.md](WEAKNESSES.md).

## What this suite does not cover

Said plainly, because the gaps matter more than the score:

- **Ten recipe cards, one author, one style.** The extraction error rate over this corpus is 0%, which measures the corpus and not the parser. Against sixteen realistic rows, 11 are silently dropped. See [WEAKNESSES.md](WEAKNESSES.md).
- **No multi-turn conversations.** Every case is a single question. Real cooking questions arrive in threes.
- **No adversarial users.** Week 8 tested prompt injection separately; those cases are not in this suite.
- **English only, metric only.**
- **The judge sees the answer, not the cards.** It can catch a nonsensical swap; it cannot catch a swap that contradicts a card it was never shown.

## Every failure in the run

| case | type | why it failed | trace id |
|---|---|---|---|
| WS-01 | wrong_sentence | did not finish (stopped: step limit (8) reached) | `t-20261104-450f95` |
| WS-02 | wrong_sentence | did not refuse | `t-20261104-0693e3` |
| WS-03 | wrong_sentence | contains the fact | `t-20261104-6e8bdb` |
| WS-04 | wrong_sentence | cites the right recipe; contains the fact | `t-20261104-d13ffc` |
| WS-05 | wrong_sentence | contains the fact | `t-20261104-58633a` |
| WS-06 | wrong_sentence | source present; cites the right recipe; contains the fact | `t-20261104-50eea1` |
| WS-07 | wrong_sentence | cites the right recipe; contains the fact | `t-20261104-49b271` |
| WS-08 | wrong_sentence | did not refuse | `t-20261104-799c8c` |
| WS-09 | wrong_sentence | contains the fact | `t-20261104-bd1fe5` |
| WS-10 | wrong_sentence | source present; cites the right recipe; contains the fact | `t-20261104-9d11a8` |
| FR-01 | false_refusal | source present; names at least 2 | `t-20261104-f55323` |
| FR-02 | false_refusal | did not refuse | `t-20261104-664d30` |
| FR-03 | false_refusal | cites the right recipe; contains the fact | `t-20261104-96d28f` |
| FR-04 | false_refusal | cites the right recipe; contains the fact | `t-20261104-e3dec2` |
| FR-05 | false_refusal | contains every fact | `t-20261104-682194` |
| FR-06 | false_refusal | contains the fact | `t-20261104-e39772` |
| FR-07 | false_refusal | source present; cites the right recipe; contains the fact | `t-20261104-c75ba4` |
| AL-01 | allergen_yes_no | did not refuse | `t-20261104-bfcc67` |
| AL-03 | allergen_yes_no | did not refuse | `t-20261104-f2cac5` |
| AL-04 | allergen_yes_no | cites the right recipe; contains the fact | `t-20261104-f10c26` |
| AL-05 | allergen_yes_no | contains the fact | `t-20261104-706ca9` |
| IN-01 | indirect | source present; cites the right recipe; contains the fact | `t-20261104-e49266` |
| SU-01 | substitution | Invented claim: The card states tahini contains sesame, but does not s | `t-20261104-a3b1f4` |
| SU-02 | substitution | did not finish (stopped: repeated the same tool call (substitutes_for) | `t-20261104-ecc89e` |
| SU-03 | substitution | The answer makes an invented claim that 'there is no glutinous rice fl | `t-20261104-e64b19` |
| SU-04 | substitution | The answer refuses even though the card directly addresses the swap, e | `t-20261104-694073` |
| SU-05 | substitution | The answer contradicts itself within the first sentence. It endorses a | `t-20261104-762b41` |
| SU-06 | substitution | Invented claim: The answer states 'plain flour is gluten-free', which  | `t-20261104-52bd93` |
| SU-07 | substitution | 1. Invented claim/Wrong refusal reason: The reason given for refusal i | `t-20261104-ded4d5` |
| SU-08 | substitution | The answer endorses a swap that no card supports. The answer quotes or | `t-20261104-94f2d5` |
| SU-09 | substitution | The answer refuses even though card R-105 directly addresses the swap  | `t-20261104-dd6d73` |
| SU-10 | substitution | The answer refuses even though the card provides relevant information  | `t-20261104-0606f1` |
| SU-11 | substitution | The answer refuses the swap even though the cards directly address it  | `t-20261104-0cfd16` |
| MR-01 | must_refuse | did not finish (stopped: repeated the same tool call (search_recipes)) | `t-20261104-569edf` |
| MR-02 | must_refuse | refused when it should | `t-20261104-b1b3f9` |
| MR-03 | must_refuse | refused when it should | `t-20261104-da488b` |
| MR-04 | must_refuse | refused when it should | `t-20261104-6e7589` |
| MR-05 | must_refuse | refused when it should | `t-20261104-d63009` |
| MR-06 | must_refuse | refused when it should | `t-20261104-f97b8a` |
| OK-01 | already_working | did not refuse | `t-20261104-4f2913` |
| OK-02 | already_working | did not refuse | `t-20261104-f20717` |
| OK-03 | already_working | contains the fact | `t-20261104-512a0e` |
| OK-04 | already_working | did not refuse | `t-20261104-16114c` |
| OK-05 | already_working | contains the fact | `t-20261104-24c271` |

Every one of those trace ids is openable: `python pantry.py trace <id>` prints the whole request, including what the MCP servers were asked and what they answered.

## Where to go next

- The **paths** these answers took, not just the answers: [../results/trajectory_report.md](../results/trajectory_report.md)
- Where the failures **cluster**: [../results/taxonomy.md](../results/taxonomy.md)
- One failure driven **red to green**: [../results/failure_loop.md](../results/failure_loop.md)

