# Re-grade: same answers, a fixed grader

**5/47 → 3/47** (11% → 6%) after fixing three bugs in my own grading code. Not one answer changed; no model was called. Only the scoring changed.

## Why this is published instead of re-run quietly

A 33-minute run finished, the number came out low, and the first thing I did was go looking for a reason it was unfairly low. That is the exact moment where an eval suite stops being a measurement, so both numbers are here, and so is every verdict that moved.

The check that keeps it honest: **the score went DOWN.** Every fix was made because the grading was wrong, not because the number was low, and the result is a worse number than the one I started with. A set of grading fixes that only ever helps is a set of fixes that was chosen to help.

And the fix I expected to *raise* the score did something more useful instead: it uncovered an answer that is dangerously wrong and had been failing for the wrong reason. See bug 2.

## The three bugs

### 1. A crash was counted as a refusal — *cost 2 passes*

When the agent hit its step limit or repeated a tool call, it answered "I couldn't finish this task". The refusal detector saw `couldnt` and called it a refusal — and on a `must_refuse` case, a refusal is a **pass**. So the agent scored points for giving up.

`2` case(s) lost their pass to this. A stop is now its own outcome (`did not finish`) and fails whatever the case wanted.

This is the second time: week 10 had the identical bug in its grading glue. Finding it twice says the lesson did not stick the first time, so it is written into `run_evals.py` as a named function with the story in its docstring rather than left as a line of code to rediscover.

### 2. "does not contain" was read as a refusal — *and was hiding an unsafe answer*

The refusal word list contained `do not contain` and `not contain`, so a direct negative answer was scored as a refusal to answer. That is wrong on its face: a clear "no" is **exactly** the shape a correct negative allergen answer takes.

I expected fixing it to recover two passes. It recovered none, and what it exposed is worth far more than two passes:

**AL-04 — "is there egg in the buttermilk pancakes?" → "No, buttermilk pancakes do not contain eggs."**

The card (`buttermilk_pancakes.md`) says `| Whole egg | 100 g | 33.3% |` and its allergen note reads *"Contains wheat gluten, cow's milk dairy and hen egg."* The answer is **flatly wrong, on an allergen, in the confident direction**. It is the single most dangerous output this system can produce, and the broken grader was hiding it: the case failed, so it never showed up as a problem, but it failed for "did not refuse" rather than for "told a cook with an egg allergy there is no egg in the pancakes".

**A failing test that fails for the wrong reason is not a safety net. It is a blindfold with a pass rate printed on it.**

Worse: the safety guard did not catch this either, and it was never going to. The guard only fires when the cook **states a restriction**. AL-04 asks a plain allergen question with no restriction attached, so nothing checked the answer against the card. That gap is now in [../docs/WEAKNESSES.md](../docs/WEAKNESSES.md).

**AL-05 — "does the vegan kimchi contain shellfish?" → "The vegan kimchi (R-105) does not contain shellfish."**

This answer is correct. It still fails, because the case wants the literal card phrase `Free from fish, shellfish` to appear in the answer. That is a measurement artifact of the same family as week 10's "15 grams" failing a check for "15 g", and the check is left exactly as it is: rewriting a test after reading the answer it failed on is not allowed, and one known-bad check is cheaper to disclose than to quietly repair.

### 3. One real refusal is still missed — *left alone on purpose*

MR-05 answered "The available recipes are for specific types of sourdough, not a general sourdough starter. Please search for a sourdough starter recipe specifically." That is a refusal in substance and the detector misses it, so MR-05 still scores as a failure.

It is left failing deliberately. Adding whatever phrase makes MR-05 pass would be tuning the grader against a case whose answer I have already read. The honest record is: **the pass rate below is at least one case too low, and the refusal detector is keyword matching that needs replacing, not widening.**

## Every verdict that moved

| case | type | before | after | the answer |
|---|---|---|---|---|
| WS-01 | wrong_sentence | FAIL (did not refuse) | **FAIL** (did not finish (stopped: step limi) | I couldn't finish this task (stopped: step limit (8) reached |
| AL-04 | allergen_yes_no | FAIL (did not refuse) | **FAIL** (cites the right recipe; contains t) | No, buttermilk pancakes do not contain eggs. |
| AL-05 | allergen_yes_no | FAIL (did not refuse) | **FAIL** (contains the fact) | The vegan kimchi (R-105) does not contain shellfish. |
| SU-02 | substitution | PASS (none) | **FAIL** (did not finish (stopped: repeated ) | I couldn't finish this task (stopped: repeated the same tool |
| MR-01 | must_refuse | PASS (all checks passed) | **FAIL** (did not finish (stopped: repeated ) | I couldn't finish this task (stopped: repeated the same tool |

## What is left after the re-grade

**3/47 = 6%.** All 47 answers were read by hand after the re-grade. Two cases (AL-05, MR-05) are known to be scored unfairly and are left that way on the record. The rest are real:

- the agent **invents recipe ids** — it calls `get_recipe_section(recipe_id="R-123")` for a card that does not exist instead of searching first, then reports its own mistake to the cook as the answer;
- it **answers questions the cards cannot support** — a wine pairing, where to buy gochugaru, and "7 grams of sodium per serving", which is invented;
- it **refuses substitution questions the cards do answer** — the judge's most common complaint, in 5 of the 11 substitution cases;
- and once, it got an **allergen flatly wrong** (AL-04).

Those are what [../docs/EVAL_REPORT.md](../docs/EVAL_REPORT.md) and [taxonomy.md](taxonomy.md) are about.

