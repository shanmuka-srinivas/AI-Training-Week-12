# Pantry-to-Plate Assistant

*Week 12 Capstone · Module 6 · Track B: Recipes & food*

Ask a cooking question in plain English and get an answer taken from real recipe cards,
with the card and section it came from — and a refusal rather than a guess when the cards
don't say.

> **The hard part isn't looking things up. It's not poisoning anyone.** A cook who says
> "I'm dairy-free" and asks for a buttermilk substitute will be told, by the ingredient
> database, to use *milk plus lemon juice*. That really happened in week 11, and most of
> this app exists to make sure it can't happen again quietly.

---

## Get it running (5 minutes, no API key, no account)

```bash
cd AI-Training-Week-12
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt   # includes the prebuilt wheel index, so nothing compiles

python pantry.py doctor           # checks every seam, ~10 seconds, no model needed
```

`doctor` should end with **READY**. If it doesn't, the line marked `XX` tells you what's
missing.

Then ask it something:

```bash
python pantry.py ask "I have 1 kg of white cabbage. How much salt for the sauerkraut?"
```

The first question downloads the local model (~2 GB, once) and takes a few minutes. After
that, about 40 seconds per question on a laptop CPU. **No API key is needed and nothing
leaves your machine.**

---

## What is this project for?

Twelve weeks of pieces — a document search, an agent, tools over MCP, an eval suite,
error analysis, logging — assembled into one app you can actually run and defend.

The job it does: **answer questions about ten recipe cards, safely and with receipts.**

| What it must do | Why it's hard |
|---|---|
| Quote the right weight from the right card | Easy. This part was done in week 3. |
| Scale a recipe to what the cook actually has | Arithmetic the model must not do itself |
| Resolve a dietary restriction **before** suggesting anything | The ingredient database's own substitutes are not diet-aware |
| Say "the cards don't say" instead of guessing | A confident invented answer about an allergen is the worst output this app can produce |
| Be auditable afterwards | A complaint arrives as "it was wrong, maybe Tuesday" |

---

## Input

| What goes in | Details |
|---|---|
| **10 recipe cards** | [data/recipes/](data/recipes/) — breads, kimchi, sauerkraut, hummus, pizza dough, pancakes, focaccia. Each has an ingredients table, a method, storage notes and an allergen note. |
| **A question in plain English** | Optionally with a restriction: `--dietary "dairy-free"` |
| **Nothing else** | No account, no API key, no internet after the model downloads |

## Output

| What comes out | Example |
|---|---|
| **An answer** | "For 1 kg of white cabbage, you need 20 g of fine sea salt." |
| **Sources** | `R-106 · ingredients · caraway_sauerkraut.md` |
| **A trace id** | `t-20261104-a1b2c3` — follow it with `python pantry.py trace <id>` |
| **Cost and time** | per step, not one lump |
| **A refusal** | when the cards don't hold the answer, or when an answer would break a stated diet |

---

## What happens between input and output

```
  your question
       │
       ▼
  ┌─────────────────────────── the app (one process) ────────────────────────────┐
  │                                                                              │
  │   1. a trace id is minted, and everything below is logged under it            │
  │                                                                              │
  │   2. THE AGENT LOOP  ── think ─► act ─► look at the result ─► repeat          │
  │          the model decides WHICH tool to call. It runs only here.             │
  │                              │                                                │
  │                              │  tools discovered at startup, not hardcoded     │
  │   3. PRIVACY LINE ───────────┤  your words never cross this line: only a       │
  │                              │  recipe id, an ingredient name or a number      │
  └──────────────────────────────┼───────────────────────────────────────────────┘
                                 │  MCP (JSON-RPC over stdio)
             ┌───────────────────┴────────────────────┐
             ▼                                        ▼
    recipe-cards server                      ingredient-db server
    search / read / scale                    allergens / cups / substitutes
    (no AI in here, ever)                    (no AI in here, ever)
             │                                        │
             └───────────────────┬────────────────────┘
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │   4. SAFETY GUARD — code, not a prompt. An answer that recommends an          │
  │      allergen clashing with a stated restriction never leaves.                │
  │   5. CITATIONS attached: recipe id · section · file                           │
  │   6. The whole request written to logs/requests.jsonl, with per-step cost     │
  └──────────────────────────────────────────────────────────────────────────────┘
                                 ▼
                     answer + sources + trace id
```

**Step by step:**

1. **Log first.** Every request gets a trace id before anything else happens. That id
   appears in our log *and* in the MCP servers' own log, so one question can be followed
   all the way out and back.
2. **The agent decides.** It sees a list of tools it discovered at startup — nothing is
   hardcoded — and picks one at a time: search the cards, read a section, scale a recipe,
   look up an ingredient's allergens.
3. **The privacy line.** The tools get `R-106` and `cabbage`, never *"I'm dairy-free and
   allergic to peanuts, what can I…"*. This is enforced in code at the boundary: an
   argument longer than 8 words is refused, because that's a sentence, not an identifier.
4. **The guard.** Before the answer goes out, code checks it: if the cook stated a
   restriction and the answer recommends something that clashes, the answer is replaced.
   The model is not asked nicely — it is overruled.
5. **Citations.** Every answer carries the card and section it came from, so it can be
   checked.
6. **The log.** Time, tokens and cost per step, plus which sections were read.

---

## Everything you can run

```bash
python pantry.py doctor        # are all the seams connected? (10s, no model)
python pantry.py tools         # what it discovered over MCP, right now
python pantry.py ask "..."     # one question, end to end
python pantry.py trace <id>    # one request, both sides of the MCP hop
python pantry.py logs --flag diet_conflict    # search every past answer
python pantry.py evals         # the full 47-case suite (~35 min)
python pantry.py evals --quick # a 12-case subset (~9 min)
python pantry.py judge         # re-check the LLM judge against hand labels (instant)
python pantry.py trajectory    # score the paths taken, not just the answers (instant)
python pantry.py taxonomy      # the error taxonomy, re-scored (instant)
python pantry.py cost          # cost per stage, and the 10x plan (instant)
python pantry.py loop          # guard off vs guard on, 5 trials each (~7 min)
python pantry.py demo          # the four-part demo
```

The `instant` ones read results that are already in the repo, so you can look at the
numbers before spending half an hour reproducing them.

---

## Honest limits, before you ask

- **It passes 3 of 47 eval cases — 6%.** That is the real number and it is bad. The
  retrieval pipeline this was built on scored 19/46 on the same questions; putting an agent
  in front of it made things *worse*, not better. Full breakdown and every failing case in
  [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md).
- **The agent invents recipe ids.** It will call for card `R-123`, which does not exist,
  instead of searching first — then tell you it couldn't find `R-123`.
- **It got an allergen flatly wrong once.** Asked "is there egg in the buttermilk
  pancakes", it said no. The card says 100 g of whole egg. The safety guard did not catch
  it, because the guard only fires when you *state* a restriction. This is weakness #1.
- **The model is small** (Qwen2.5-3B on CPU) because the project runs offline and free. A
  bigger model would lift the numbers and change none of the architecture.
- **Ten recipe cards.** Not a cookbook.
- **The parser is brittle.** 11 of 16 realistic ingredient rows (`1/2 cup`, `750-800 g`,
  `20 grams`) are silently dropped. Our own cards are clean, which is why that number comes
  from a stress test and not from the corpus.
- **The safety guard has false positives.** It blocked a kimchi question the cards answer
  directly. With the guard off, the same dairy-free question is safe only **1 time in 5**;
  with it on, 5/5. That is what the guard buys and what it costs.

Two things that went *right*, for balance: **zero lucky passes** (nothing passed down a
wrong path) and **not one failure traced to the MCP layer**.

The top three weaknesses, written down before anyone asked, are in
[docs/WEAKNESSES.md](docs/WEAKNESSES.md). The three bugs I found in my own *grader* — two
of which were inflating the score — are in [results/regrade.md](results/regrade.md).

---

## Tech stack

| Part | What | Why |
|---|---|---|
| Language | **Python 3.13** | |
| Search | **MiniLM embeddings + BM25**, fused (weeks 3–4) | Meaning and exact terms; recipe codes need both |
| Agent | **Hand-written think→act→observe loop** (week 7) | ~100 lines, no framework, so nothing is magic |
| Tools | **MCP** (`mcp` SDK v2), two servers over stdio (week 9) | Discovered at runtime; our server is callable by anyone's agent |
| Model | **Qwen2.5-3B-Instruct Q4_K_M** via llama.cpp | Free, offline, no key. Runs in the host only |
| Evals | **Assertions first, Gemini judge** only where a rule can't decide (week 6) | Rules are free and exact; the judge is validated against hand labels |
| Error analysis | Trajectory checks + taxonomy (weeks 5, 8) | The path matters, not just the answer |
| Logging | **JSONL traces with spans** (week 11) | Per-step time and cost; one trace id across the MCP hop |
| Safety | A **Python guard**, not a prompt rule | The model ignored the prompt version; code it cannot ignore |

---

## Where to look next

| If you want… | Read |
|---|---|
| The numbers and what they don't cover | [docs/EVAL_REPORT.md](docs/EVAL_REPORT.md) |
| The grading bugs I found, and both scores | [results/regrade.md](results/regrade.md) |
| Whether the LLM judge can be trusted here | [results/judge_agreement.md](results/judge_agreement.md) |
| What I know is weak | [docs/WEAKNESSES.md](docs/WEAKNESSES.md) |
| What broke when the parts were joined | [docs/SEAMS.md](docs/SEAMS.md) |
| How the pieces fit, in one page | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| The 10-minute demo | [docs/DEMO.md](docs/DEMO.md) |
| Whether a stranger could actually run this | [docs/FRESH_EYES.md](docs/FRESH_EYES.md) |
| The full write-up | [RESULTS.md](RESULTS.md) |
