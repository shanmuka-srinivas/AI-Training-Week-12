# The seam list

What broke, bent or quietly stopped working when twelve weeks of separate
exercises were bolted into one app. **This list is unedited.** Nothing was
removed because it was embarrassing, and every entry is marked honestly:

- **fixed** — it works now, and something in the repo proves it
- **accepted** — a deliberate decision to live with it, with the reason
- **ran out of time** — known, not done, and on the next-steps list

Each part worked on its own. That was never the question. The question was what
happens at the joins, and the answer was: nine things, five of which I would not
have found without going looking.

---

## 1. The trace id stopped at the process boundary — **fixed**

Week 11 logged a trace id for every request. Week 9 ran the tools in separate
processes. Joined together, the trace id described everything *except* the part
most likely to go wrong. A complaint could be narrowed to "the agent called
`scale_recipe` with something", with no record of what came back.

**Fix:** every MCP tool now takes an optional `trace_id` and writes a line to
`logs/mcp_server.jsonl` before it does anything. The client injects it
automatically when the tool's schema accepts it, so the agent never has to
remember.

**Proof:** `python pantry.py trace <id>` prints the app-side record and then the
server-side audit lines for the same id.

---

## 2. The cook's own words were crossing into the tool servers — **fixed**

This is the one that genuinely surprised me. Nothing in weeks 7–9 said the agent
couldn't put the user's sentence into a tool argument, and sometimes it did —
`search_recipes(query="I'm dairy-free and allergic to peanuts, what bread…")`.
Harmless with local servers on one laptop. Not harmless as soon as one of those
servers belongs to somebody else, which is the whole point of MCP.

**Fix:** a rule in code at the boundary. Any argument longer than **8 words** is
refused before it leaves the process, because eight words is a sentence, not an
identifier. The refusal is returned to the agent as a normal recoverable tool
error, so it recovers and tries a proper identifier instead of dying.

**Proof:** `python pantry.py doctor` attempts a 17-word argument and reports
whether the line held.

**What's wrong with the fix:** a word count is a crude proxy for "this is
personal". It would pass `peanut-allergy-death-risk` and block a legitimate
seven-word recipe title. It is the right *shape* of control in the wrong units.

---

## 3. Week 6's RAGAS metrics do not survive the MCP hop — **accepted**

`evals/checks.py` can compute faithfulness, context recall and context precision
— but all three read the **body text** of the retrieved chunks. Across MCP, the
app gets back an answer and a citation, not the chunks. So those three metrics
are computed over empty strings, which is worse than not computing them.

**Decision:** they are not computed at all in week 12, rather than reported as
meaningless zeroes. The pass/fail grading is unaffected (`rule_checks` never
reads the bodies), so the headline number is honest; the retrieval-quality
numbers are simply absent.

**The real fix**, not done: have the tool return the text it answered from, and
score that. That is a change to the tool contract, not to the evals.

---

## 4. The safety guard fires on answers that are correct — **accepted**

The guard looks for an allergen word near a stated restriction. An answer that
*correctly* warns "this contains dairy, so it is not suitable for you" trips the
same rule as one that recommends dairy to a dairy-free cook.

**Decision:** keep it, loudly. A false positive costs a cook one unhelpful
answer. A false negative costs them an allergic reaction. The asymmetry is not
close, so the guard stays wide and the cost is recorded rather than hidden:
`guard blocked a safe answer` is its own named mode in the taxonomy with its own
frequency, because its cure is a better rule, not a better model.

---

## 5. The ingredient parser only understands one person's handwriting — **ran out of time**

Our ten cards all say `20 g`. The tools accept exactly that and silently skip
anything else. Measured against sixteen rows of the kind any real card carries —
`900g`, `1/2 cup`, `1 kg`, `750-800 g`, `20 grams`, `7 g*` — **11 of 16 are
dropped without a word**, and the cook gets a scaled recipe with ingredients
missing and no warning.

This is not strictly an integration bug; integration is what made it visible,
because `scale_recipe` became a thing an agent reaches for on its own.

**What's needed:** accept more units, and make an unparsable row an explicit
warning in the tool result instead of silence. The second half matters more than
the first.

---

## 6. Week 10's multi-agent squad was deliberately left out — **accepted**

It works. It is also strictly worse here: an orchestrator plus workers multiplies
the model calls, and model calls are 100% of the measured cost and 98% of the
latency. Ten recipe cards do not need parallel research.

**Decision:** not shipped, on purpose, with the reason written down. Week 10's
actual lesson — that a per-worker step budget set too low silently starves most
of the squad — is in the eval design here instead: the step budget is 6, and a
case that hits it is marked `ran out of steps or looped` rather than scored as a
wrong answer.

---

## 7. Two prompt versions, and the old one was still reachable — **fixed**

Week 11 introduced `v1.2.0` (check allergens before suggesting anything) beside
`v1.1.0`. After integration, which one ran depended on which entry script you
started from. That is the exact setup where a fix "stops working" months later
and nobody can say when.

**Fix:** one `CURRENT_VERSION` constant, the version id written into every trace,
and a single entry point so there is nowhere else to start from.

---

## 8. Judge capacity, not judge quality, decides how often the suite can run — **accepted**

The validated LLM judge runs on Gemini's free tier: 20 calls per model per day.
The suite needs 11. So the full suite can run honestly about **once a day**, and
`--quick` exists for the rest of the time.

**Decision:** assertions do as much grading as possible (36 of 47 cases need no
judge at all), the judge handles only the 11 substitution cases where no rule can
decide, and its verdicts are cached. This is a budget constraint being managed,
not solved.

---

## 9. The two logs disagreed about the trace id — **fixed**

Found on the last day, by actually opening an end-to-end trace instead of
trusting that seam 1 worked.

The MCP tool schemas exposed `trace_id` as an optional parameter, so the model
could see it — and being helpful, it filled it in: `trace_id: "trace1"`. The
client overrode that with the real id before sending, so the *server's* log was
correct. But the app-side span recorded what the model had proposed. Two logs,
same request, different trace ids.

Nothing broke on the wire. That is what makes it nasty: it was wrong **only in
the place you go to look when something else is wrong.** Seam 1 exists so a
complaint can be followed across the process boundary, and this quietly undid
half of it.

**Fix:** three changes, because "the model cannot see it" is not a control.

1. Plumbing parameters are filtered out of the tool list the model is shown
   (`HIDDEN_ARGS` in `agent/mcp_client.py`). A field the caller always overrides
   has no business being in the caller's prompt.
2. Any value the model supplies for one is **discarded** before the call, not
   merely overwritten.
3. The app-side span records the arguments actually **sent**, not the ones the
   model proposed.

### The first fix was incomplete, and the proof is why I did not notice

Changes 1 and 2 went in, I verified them, and I wrote this entry as closed. It
was not. Running `python pantry.py demo` end to end for the first time printed a
trace with `"args": {"name": "buttermilk", "trace_id": "trace1"}` still in it.

`MCPToolbox.descriptions()` was fixed. But `tool_descriptions()` in `app.py` —
**the loop that actually ships** — rebuilt the tool list itself straight off
`tool["schema"]["properties"]`, so `HIDDEN_ARGS` never applied there. The same
logic existed in two places and I fixed the one `agent/agent.py` calls, which is
the week-7 standalone loop that week 12 does not use.

The proof I wrote was the real failure. It asserted `trace_id not in
descriptions()` — true, and irrelevant, because the shipping prompt is not built
by that function. **A test aimed at the copy nobody runs reads exactly like a
passing test.** That is a more dangerous object than the bug it was hiding: the
bug was one wrong field in a log, and the test was a standing claim that the
field was right.

Two copies of a decision is the root cause, not the missed edit, so `app.py` now
imports `MCPToolbox.HIDDEN_ARGS` instead of restating it. One place decides what
the model may see.

**Proof, rewritten to cover what ships:** `trace_id` appears nowhere in the
rendered system prompt (`PROMPTS[CURRENT_VERSION].format(tools=...)`), not merely
nowhere in `descriptions()`. And on live request `t-20261104-14963f` the app
span reads `{'name': 'buttermilk'}` while `logs/mcp_server.jsonl` reads
`trace_id=t-20261104-14963f` — same request, same id, both sides, no `trace1`
anywhere in the record.

**The lesson that generalises:** exposing an internal field in a tool schema is
an invitation. The model will accept it.

---

## The pattern in all nine

Six of the nine are not bugs in anybody's code. They are **contracts nobody
wrote down**: what may cross a process boundary, what a tool owes its caller,
which version is in force, who pays for the judge, which fields are the
caller's business. Each part was individually correct and individually silent
about the thing the next part assumed.

The ones that were easy to find are the ones that crashed. The ones worth finding
— the cook's sentence leaving the process, the retrieval metrics quietly scoring
empty strings, two logs disagreeing about which request they describe — did not
crash anything. They just went on being wrong.
