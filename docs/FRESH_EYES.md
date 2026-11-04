# Did a stranger actually run this?

**No. A human stranger did not run this, and I am not going to imply otherwise.**

The brief asks for someone unfamiliar to follow the setup and report where they
got stuck. This project was built solo, on a deadline, on one laptop. So what
follows is a **proxy**, clearly labelled as one, plus an honest list of what a
proxy cannot catch.

---

## What was done instead

### 1. A clean-machine check, mechanically

`python pantry.py doctor` is the stand-in for a confused first-timer. It does
not test the happy path — it tests every assumption the README makes, and it
says which one is false:

| it checks | because a stranger would otherwise see |
|---|---|
| the ten recipe cards are present and parse | an empty, cheerful "no results" |
| the MCP SDK is installed and importable | `ModuleNotFoundError: mcp`, three frames deep |
| both servers start and answer `tools/list` | a hang with no output |
| a real tool call returns real data | a plausible, empty answer |
| the privacy line refuses a 17-word argument | nothing at all — this fails silently |
| the audit log exists and has trace ids | nothing at all — this fails silently |
| the local model library is importable | a 2 GB download, then a crash |

It runs in about ten seconds, needs no model and no key, and ends in **READY**
or a line marked `XX`. Two of those seven checks cover failures that produce no
error message whatsoever, which is precisely where a stranger gives up without
being able to say why.

### 2. The install path was broken, found, and fixed — on a real machine

This part is not a proxy. The original `requirements.txt` listed
`llama-cpp-python`, and on this Windows machine pip tried to **compile it from
source**, hit the long-path limit, and aborted *the entire install* — so `mcp`
was never installed either, and the first error the user saw was about MCP,
which had nothing to do with the real problem.

`requirements.txt` now pins the prebuilt CPU wheel index, so nothing compiles.
That bug was found by a person hitting it, which is exactly the point of the
exercise, and it is the single most valuable thing in this document.

### 3. The README was written to the five-minute test

Copy-pasteable blocks, both Windows and Unix activation on the same line, the
model download called out *before* it happens with its size and duration, and
the honest limits above the fold rather than buried at the bottom.

---

## What this proxy cannot catch, and I know it

- **Vocabulary.** I cannot tell which words in the README are jargon, because I
  chose them. "Trace id", "the privacy line", "MCP hop" are all opaque to
  someone who has not read the other twelve weeks.
- **The order of confusion.** `doctor` reports problems in my mental order, not
  in the order a stranger meets them.
- **The decision to stop.** The most important data point — the moment someone
  closes the terminal and does something else — is invisible to a self-test.
  Nothing in this repo measures it.
- **Different machines.** macOS, Linux, Python 3.11, a machine with no AVX2: all
  untested. The wheel index that fixed Windows may be wrong elsewhere.

---

## What I would ask a real first-timer to do

Ten minutes, no help from me, three questions afterwards:

1. Where did you first have to guess at something?
2. What did you expect `doctor` to tell you that it didn't?
3. At what point did you believe the answers were coming from the cards rather
   than being made up?

Question 3 is the real one. Everything in this project — the citations, the
traces, the refusals, the guard — exists to make the answer to it "immediately",
and there is no evidence yet that it does.
