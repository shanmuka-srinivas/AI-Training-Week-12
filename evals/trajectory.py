"""
TRAJECTORY EVALUATION: grading the path, not just the answer.

Week 7 asked one question of each run: "is the final answer right?". That misses
a whole class of problems. An agent can reach the right answer by luck:

    "How much salt for 350 g of cabbage?"  ->  the sauerkraut card is already
    written for 350 g, so an agent that never calls scale_recipe still says
    "7 g" and looks correct. Ask for 1 kg tomorrow and the same path is wrong.

So for every task we also write down the path it SHOULD take, and check the run
against it:

    must_use          tools that have to be called, with the right recipe
    expected_order    the order those tools should appear in (as a subsequence,
                      so extra steps in between are allowed)
    max_steps         a generous ceiling; more than this means it wandered
    read_only         if True, the run must not call a memory-writing tool

From those we get three numbers the outcome score can't give us:

    trajectory pass        did the run take an acceptable path?
    tool-choice accuracy   share of tool calls that were useful, i.e. not a
                           duplicate, not an error, and a tool this task needs
    outcome-vs-trajectory  right answer + wrong path = "lucky"
    gap                    wrong answer + right path = "unlucky"

"Lucky" runs are the dangerous ones: they pass today's test and will break in
production the first time the numbers change.
"""

# Recipe titles, so we can spot an answer that names a recipe the run never opened.
RECIPE_TITLES = {
    "R-001": "Rosemary Focaccia",
    "R-002": "Neapolitan Pizza Dough",
    "R-003": "Buttermilk Pancakes",
    "R-004": "Classic Hummus",
    "R-101": "Two-Kilo Country Sourdough",
    "R-102": "One Hundred Percent Wholegrain Rye Sourdough",
    "R-103": "Gluten-Free Buckwheat Sourdough",
    "R-104": "Traditional Napa Cabbage Kimchi",
    "R-105": "Vegan Napa Cabbage Kimchi",
    "R-106": "Small-Batch Caraway Sauerkraut",
}

WRITE_TOOLS = {"remember"}

# The expected path for every task. Written by hand from the recipe cards,
# before looking at what the agent actually did.
EXPECTED = {
    # ---- Week 7 tasks ----
    "T01": {"must_use": [("scale_recipe", "R-106"), ("get_recipe", "R-106")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 6, "read_only": True},
    "T02": {"must_use": [("scale_recipe", "R-002")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 5, "read_only": True},
    "T03": {"must_use": [("scale_recipe", "R-001"), ("get_recipe", "R-001")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 6, "read_only": True},
    "T04": {"must_use": [("get_recipe", "R-004")],
            "expected_order": ["search_recipes", "get_recipe"], "max_steps": 5, "read_only": True},
    "T05": {"must_use": [("scale_recipe", "R-103")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 5, "read_only": True},
    "T06": {"must_use": [("scale_recipe", "R-105")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 6, "read_only": True},
    "T07": {"must_use": [("scale_recipe", "R-105")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 7, "read_only": True},
    "T08": {"must_use": [("get_recipe", "R-102"), ("get_recipe", "R-103")],
            "expected_order": ["search_recipes", "get_recipe", "get_recipe"], "max_steps": 7, "read_only": True},
    "T09": {"must_use": [("get_recipe", "R-103")],
            "expected_order": ["search_recipes", "get_recipe"], "max_steps": 5, "read_only": True},
    "T10": {"must_use": [("get_recipe", None)],
            "expected_order": ["search_recipes", "get_recipe"], "max_steps": 6, "read_only": True},
    "T11": {"must_use": [("get_recipe", "R-102")],
            "expected_order": ["search_recipes", "get_recipe"], "max_steps": 5, "read_only": True},
    "T12": {"must_use": [("recall", None), ("get_recipe", "R-105")],
            "expected_order": ["recall", "search_recipes"], "max_steps": 6, "read_only": True},

    # ---- Week 8 "lucky path" tasks: the right answer is reachable the wrong way ----
    "L01": {"must_use": [("scale_recipe", "R-106")],
            "expected_order": ["search_recipes", "scale_recipe"], "max_steps": 5, "read_only": True},
    "L02": {"must_use": [("search_recipes", None)], "requires_tag_check": True,
            "expected_order": ["search_recipes"], "max_steps": 5, "read_only": True},
    "L03": {"must_use": [("get_recipe", "R-104")],
            "expected_order": ["search_recipes", "get_recipe"], "max_steps": 5, "read_only": True},
    "L04": {"must_use": [("get_recipe", "R-106")], "required_sections": {"R-106": "method"},
            "expected_order": ["search_recipes", "get_recipe"], "max_steps": 5, "read_only": True},
}


def _tool_calls(run):
    """The real tool calls of a run: not final_answer, not an unreadable reply."""
    return [s for s in run["steps"] if s["action"] not in ("final_answer", "none")]


def _touched_recipes(calls):
    """
    Which recipes the run actually has evidence about.

    That means a recipe it opened with get_recipe/scale_recipe, AND any recipe
    a search returned to it, because a search result carries the id, the title
    and the dietary tags. (This second half was added after reading the first
    batch: without it, an agent that correctly filtered a search by
    dietary_tag was being marked down for "not opening" a card whose tags the
    search had already handed it. Both batches were re-scored with the
    corrected rule, from the saved steps, with no new model calls.)
    """
    found = set()
    for call in calls:
        value = str(call["args"].get("recipe_id", "")).upper()
        if value in RECIPE_TITLES:
            found.add(value)
        if call["action"] == "search_recipes":
            for recipe_id in RECIPE_TITLES:
                if recipe_id in call["observation"]:
                    found.add(recipe_id)
    return found


def _matches(call, tool, recipe_id):
    if call["action"] != tool:
        return False
    if recipe_id is None:
        return True
    return str(call["args"].get("recipe_id", "")).upper() == recipe_id


def _is_subsequence(expected, actual):
    it = iter(actual)
    return all(any(step == a for a in it) for step in expected)


def check_trajectory(run):
    """Returns (passed, [(check name, ok, detail)], stats)."""
    spec = EXPECTED.get(run["task_id"])
    calls = _tool_calls(run)
    names = [c["action"] for c in calls]
    checks = []

    if spec is None:
        return True, [("no expected path defined", True, "")], {}

    # 1. the tools that must appear, with the right recipe
    for tool, recipe_id in spec["must_use"]:
        ok = any(_matches(c, tool, recipe_id) for c in calls)
        label = f"used {tool}" + (f" on {recipe_id}" if recipe_id else "")
        checks.append((label, ok, "" if ok else f"never called {tool}{' for ' + recipe_id if recipe_id else ''}"))

    # 2. the right order (extra steps in between are fine)
    ok = _is_subsequence(spec["expected_order"], names)
    checks.append(("followed the expected order", ok, "" if ok else f"{' -> '.join(spec['expected_order'])} vs actual {' -> '.join(names) or 'no tool calls'}"))

    # 3. no repeated identical call
    seen, duplicates = set(), 0
    for call in calls:
        key = call["action"] + str(sorted(call["args"].items()))
        duplicates += key in seen
        seen.add(key)
    checks.append(("no repeated tool call", duplicates == 0, f"{duplicates} repeats" if duplicates else ""))

    # 4. didn't wander
    ok = len(run["steps"]) <= spec["max_steps"]
    checks.append((f"took at most {spec['max_steps']} steps", ok, f"took {len(run['steps'])}"))

    # 5. no tool errors left behind
    errors = sum('"error"' in c["observation"] for c in calls)
    checks.append(("no failed tool calls", errors == 0, f"{errors} calls returned an error" if errors else ""))

    # 6. every recipe named in the answer was actually opened
    touched = _touched_recipes(calls)
    named_but_unopened = [
        rid for rid, title in RECIPE_TITLES.items()
        if title.lower() in run["answer"].lower() and rid not in touched
    ]
    checks.append(("only talks about recipes it opened", not named_but_unopened,
                   f"named {named_but_unopened} without opening them" if named_but_unopened else ""))

    # 7. a read-only task must not write to memory
    if spec.get("read_only"):
        writes = [c["action"] for c in calls if c["action"] in WRITE_TOOLS]
        checks.append(("made no memory writes", not writes, f"called {writes}" if writes else ""))

    # 8. task-specific extras
    if spec.get("requires_tag_check"):
        ok = any(c["action"] == "search_recipes" and c["args"].get("dietary_tag") for c in calls) or \
             any(c["action"] == "get_recipe" and c["args"].get("section") == "overview" for c in calls)
        checks.append(("actually checked the dietary tags", ok,
                       "" if ok else "guessed from the recipe title instead of checking tags"))
    for recipe_id, section in (spec.get("required_sections") or {}).items():
        ok = any(c["action"] == "get_recipe" and str(c["args"].get("recipe_id", "")).upper() == recipe_id
                 and c["args"].get("section") == section for c in calls)
        checks.append((f"read the {section} of {recipe_id}", ok, "" if ok else f"never read the {section}"))

    useful = sum(
        1 for i, c in enumerate(calls)
        if '"error"' not in c["observation"]
        and (c["action"] + str(sorted(c["args"].items()))) not in
            [calls[j]["action"] + str(sorted(calls[j]["args"].items())) for j in range(i)]
    )
    stats = {
        "tool_calls": len(calls),
        "useful_tool_calls": useful,
        "tool_choice_accuracy": useful / len(calls) if calls else 0.0,
        "duplicate_calls": duplicates,
        "error_calls": errors,
    }
    return all(ok for _, ok, _ in checks), checks, stats


def classify(outcome_pass, trajectory_pass):
    if outcome_pass and trajectory_pass:
        return "good: right answer, right path"
    if outcome_pass and not trajectory_pass:
        return "LUCKY: right answer, wrong path"
    if not outcome_pass and trajectory_pass:
        return "unlucky: wrong answer, right path"
    return "bad: wrong answer, wrong path"
