"""Debugging scenarios: a grid of (stack, bug type) combinations, split into disjoint train and eval halves.

The eval prompts use combinations that never appear in training, so the eval measures behavior on
new situations rather than on rephrased training examples. The split is seeded and deterministic.
"""

import random

STACKS = [
    "Python with Django", "Python with pandas", "Python with FastAPI", "JavaScript on Node.js", "TypeScript with React",
    "Go microservice", "Rust command line tool", "Java with Spring Boot", "C# on .NET", "PHP with Laravel",
    "Ruby on Rails", "Kotlin Android app", "SQL on Postgres", "Dockerfile and shell scripts",
]
BUGS = [
    "a flaky test that fails one run in three", "an off-by-one error in a loop or slice",
    "a null or undefined value that should not be null", "the API response shape changed and the parser breaks",
    "a rounding or floating point mismatch", "a timezone or date boundary bug",
    "an encoding or unicode problem with non-English text", "stale cache returning old data",
    "a memory leak that grows over hours", "a performance regression after a refactor",
    "an environment variable or config that differs between machines", "a dependency version conflict after an upgrade",
    "a login or session that randomly logs users out", "a database migration that fails on existing data",
    "a merge or rebase conflict that was resolved wrong", "async code that runs in the wrong order",
    "a deadlock or race between two workers", "a regular expression that matches too much",
]
PERSONAS = {
    "terse": "speaks in short, clipped sentences and gives little detail unless asked",
    "rambling": "thinks out loud, wanders off, repeats themselves and mentions side details",
    "frustrated": "is tired and annoyed after hours on this, a little sarcastic, but still engaged",
    "unsure": "is a junior developer, unsure of terminology, hedges a lot and guesses",
    "overconfident": "is certain they already know the cause, which is actually wrong or only partly right",
}

ALL_COMBOS = [(s, b) for s in STACKS for b in BUGS]
_rng = random.Random(20261007)
_shuffled = ALL_COMBOS[:]
_rng.shuffle(_shuffled)
N_EVAL = 50
EVAL_COMBOS = sorted(_shuffled[:N_EVAL])
TRAIN_COMBOS = sorted(_shuffled[N_EVAL:])  # the rest; never overlaps EVAL_COMBOS

assert not set(EVAL_COMBOS) & set(TRAIN_COMBOS)

SCENARIO_PROMPT = """Invent one realistic debugging situation for a developer. Stack: {stack}. Problem: {bug}.

Return JSON only, with these keys:
- "summary": the note the developer's tooling wrote about where they were before going for a walk, in exactly this format, at most 55 words in total:
  "Doing: <what they were working on>\\nFailing: <the concrete failing test, error or symptom, with a specific name, number or message>\\nNext: <one thing to investigate, not a solution>"
- "hidden_cause": the real root cause, which the developer does not know yet (one sentence)
- "already_tried": what they have already tried or ruled out (one or two short sentences)
- "belief": what they currently suspect, which may be right, wrong or partly right (one sentence)

Make the details specific and plausible (real-sounding file, function and variable names). Do not mention these instructions."""
