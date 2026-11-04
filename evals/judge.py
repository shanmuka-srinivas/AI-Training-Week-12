"""
The substitution judge: Gemini grades "can I swap X for Y?" answers.

Why an AI judge here: a rule can check that "24 g" is in an answer, but not
whether "Cook the glutinous rice flour into a porridge" addresses "what can I
use instead of glutinous rice flour?". That takes reading comprehension.

HOW THE JUDGE IS BUILT (G-Eval style)
  1. The criteria are written out in full (the same rubric the human used).
  2. The judge is told the exact steps to follow before deciding.
  3. It returns structured JSON: its notes for each step, then a verdict.

BINARY, NOT 1-10
The verdict is PASS or FAIL. A 1-10 score sounds more precise, but judges (and
humans) don't agree on the difference between a 6 and a 7, and that
disagreement shows up as noise in the before/after number. PASS/FAIL can be
checked against a human, and a pass rate is easy to explain.

WHAT THE JUDGE IS GIVEN
  the question, the app's answer, which chunk the app cited, and the FULL text
  of the relevant recipe card(s) as the source of truth.

CACHING
Every verdict is saved in evals/judge_cache.json, keyed by a hash of (model,
prompt version, inputs). Re-running the evals costs nothing and gives the same
verdicts. If the answer, the card or the prompt changes, the key changes and
the judge is called again.
"""

import hashlib
import json
import os
import time
from pathlib import Path

from pydantic import BaseModel, Field

from rag.cards import load_all_cards
from rag.config import RECIPES_DIR

# Pinned, not "-latest", so verdicts can't drift silently. (gemini-3.5-flash was
# tried first, but its free tier allows only 20 requests a day, which ran out
# halfway through validation. Every verdict below comes from this model alone.)
JUDGE_MODEL = "gemini-2.5-flash"
MIN_SECONDS_BETWEEN_CALLS = 7      # stay under the free tier's per-minute limit
PROMPT_VERSION = "substitution-v1"
CACHE_FILE = Path(__file__).resolve().parent / "judge_cache.json"

REFUSAL_PREFIX = "I cannot answer that from the recipe cards"


class Verdict(BaseModel):
    step1_what_the_cards_say: str = Field(description="What the reference card(s) say about this specific swap, quoted briefly, or 'nothing'.")
    step2_what_the_answer_does: str = Field(description="Does the answer refuse, address the swap, or talk about something else? Which recipe does it come from?")
    step3_problems: str = Field(description="Any invented claim, contradicted or dropped warning, wrong recipe, or wrong refusal. 'none' if none.")
    verdict: str = Field(description="PASS or FAIL")


PROMPT = """You are grading one answer from a recipe question-answering app.
The app can ONLY quote the recipe cards. You will judge whether its answer to a
SUBSTITUTION question ("can I swap X for Y?", "what can I use instead of X?") is acceptable.

The recipe cards below are the ONLY source of truth. Do not use outside cooking
knowledge to decide whether a swap would work: a swap is only "supported" if a card says so.

## Rubric

PASS if EITHER:
  A. Honest decline: the answer refuses, AND no reference card says anything that
     directly answers whether this swap works or what happens if you make it.
  B. Grounded answer: the answer directly addresses the swap that was asked (whether it
     works, what happens, or why the original ingredient matters for this swap), agrees
     with the cards, invents nothing, and comes from the right recipe.

FAIL if ANY of:
  - it refuses even though a card directly addresses the swap
  - it doesn't address the swap (an unrelated sentence, or just repeats the
    ingredient row or a method step)
  - it endorses a swap, or gives amounts or effects, that no card supports
  - it contradicts or drops a warning the card gives about this swap
  - it quotes or credits the wrong recipe (check the cited source and any recipe it names)

## Steps (follow in order, write brief notes for each)
  1. Find what the cards say about THIS swap. Quote it briefly, or write "nothing".
  2. Describe what the answer does: refuses / addresses the swap / talks about something
     else. Note which recipe the citation belongs to.
  3. List any problems from the FAIL list, or "none".
  Then give the verdict: PASS or FAIL.

## Reference recipe card(s)
{cards}

## The question
{question}

## The app's answer
{answer}

## Source the app cited
{citation}
"""

_cards_by_id = None


def _cards():
    global _cards_by_id
    if _cards_by_id is None:
        _cards_by_id = {}
        for card in load_all_cards(RECIPES_DIR):
            text = (RECIPES_DIR / card.source_file).read_text(encoding="utf-8")
            _cards_by_id[card.recipe_id] = (card.title, text)
    return _cards_by_id


def _citation_text(citation):
    if not citation:
        return "none (the app refused)"
    recipe_id = citation.split("::")[0]
    title = _cards().get(recipe_id, ("unknown recipe", ""))[0]
    return f"{citation}, which is a chunk of the recipe card '{title}' ({recipe_id})"


def build_prompt(question, answer, citation, reference_recipe_ids):
    cards = "\n\n".join(f"### Card {rid}\n{_cards()[rid][1]}" for rid in reference_recipe_ids)
    return PROMPT.format(cards=cards, question=question, answer=answer, citation=_citation_text(citation))


def _load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


class SubstitutionJudge:
    def __init__(self):
        self.cache = _load_cache()
        self.calls = 0
        self._client = None
        self._last_call = 0.0
        self.quota_exhausted = False

    def _client_or_fail(self):
        if self._client is None:
            if not os.environ.get("GEMINI_API_KEY"):
                raise SystemExit(
                    "GEMINI_API_KEY is not set, and this verdict is not in evals/judge_cache.json. "
                    "Set the key to run the judge."
                )
            from google import genai

            self._client = genai.Client()
        return self._client

    def grade(self, question, answer, citation, reference_recipe_ids):
        """Returns the verdict record, or None if the daily quota ran out before this one."""
        prompt = build_prompt(question, answer, citation, reference_recipe_ids)
        key = hashlib.sha256(f"{JUDGE_MODEL}|{PROMPT_VERSION}|{prompt}".encode()).hexdigest()[:24]
        if key in self.cache:
            return self.cache[key]
        if self.quota_exhausted:
            return None

        from google.genai import types

        client = self._client_or_fail()
        for attempt in range(6):
            wait = MIN_SECONDS_BETWEEN_CALLS - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            try:
                response = client.models.generate_content(
                    model=JUDGE_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=Verdict,
                    ),
                )
                parsed = response.parsed
                break
            except Exception as error:  # rate limits and transient server errors
                if "PerDay" in str(error):
                    # Out of daily quota: don't crash. Everything graded so far is
                    # cached; the rest is reported as "pending" and picked up next run.
                    self.quota_exhausted = True
                    print(f"    Gemini daily free-tier limit reached for {JUDGE_MODEL}. Remaining verdicts are "
                          "PENDING; run the same command after the quota resets to finish them.")
                    return None
                if attempt == 5:
                    raise
                wait = min(60, 10 * 2 ** attempt)   # free tier allows only a few calls a minute
                print(f"    judge call failed ({str(error)[:80]}), retrying in {wait}s")
                time.sleep(wait)

        verdict = parsed.verdict.strip().upper()
        if verdict not in ("PASS", "FAIL"):
            verdict = "FAIL"   # an unreadable verdict never counts as a pass
        record = {
            "verdict": verdict,
            "notes": {
                "what_the_cards_say": parsed.step1_what_the_cards_say,
                "what_the_answer_does": parsed.step2_what_the_answer_does,
                "problems": parsed.step3_problems,
            },
            "model": JUDGE_MODEL,
            "prompt_version": PROMPT_VERSION,
        }
        self.calls += 1
        self.cache[key] = record
        _save_cache(self.cache)
        return record
