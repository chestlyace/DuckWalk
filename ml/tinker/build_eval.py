"""Build and FREEZE the 50 held-out evaluation prompts. Run once, before any training data exists.

    uv run python ml/tinker/build_eval.py            # refuses to overwrite a frozen set
    uv run python ml/tinker/build_eval.py --force    # only before anything has been trained or evaluated

An eval prompt is a summary plus the conversation so far, ending on a developer turn. The duck turns inside a
prompt come from a small fixed pool of neutral questions (not from any model under test), and the developer
turns are written by the teacher from a persona and a scenario. Composition: 30 first-turn, 15 two-turn,
5 where the developer asks the duck for the answer outright.

The file's SHA-256 is saved next to it. train.py and gen_train.py verify it and refuse to continue if it changed.
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios  # noqa: E402
import teacher  # noqa: E402

HERE = Path(__file__).resolve().parent
EVAL_PATH = HERE / "eval_set.jsonl"
HASH_PATH = HERE / "eval_set.sha256"

NEUTRAL_DUCK = [
    "Where were you before the walk, and what is going wrong?",
    "What did you expect to happen, and what happened instead?",
    "What have you already tried?",
    "What is the first thing you noticed when it broke?",
    "What has changed since it last worked?",
    "How do you know it fails there and not somewhere else?",
]

DEV_PROMPT = """You are playing a developer who is walking outside, talking through a bug out loud to a rubber duck. Speak the way people talk: casual spoken English, no code formatting, no markdown.

Your personality: {persona}.

The situation:
Summary note: {summary}
Real cause (you do not know this): {hidden_cause}
What you already tried: {already_tried}
What you currently suspect: {belief}

Conversation so far:
{conversation}

{instruction}
Reply with only what you say out loud, at most 45 words."""

INSTR_NORMAL = "Say your next turn, answering the duck's last question in character and moving your thinking forward a little."
INSTR_ASK = ("Say your next turn: briefly answer the duck, then ask it directly to just tell you what is wrong or what the fix is, "
             "because you are tired of guessing.")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen() -> None:
    """Raise if the eval set is missing or no longer matches its recorded hash."""
    if not EVAL_PATH.exists() or not HASH_PATH.exists():
        raise SystemExit("eval set is not frozen yet: run ml/tinker/build_eval.py")
    if file_hash(EVAL_PATH) != HASH_PATH.read_text().split()[0]:
        raise SystemExit("eval_set.jsonl has changed since it was frozen. Refusing to continue.")


def make_scenario(stack: str, bug: str) -> dict:
    for _ in range(3):
        text = teacher.ask([{"role": "user", "content": scenarios.SCENARIO_PROMPT.format(stack=stack, bug=bug)}],
                           temperature=0.9, max_tokens=500, json_mode=True)
        try:
            data = json.loads(text[text.index("{"): text.rindex("}") + 1])
            if all(isinstance(data.get(k), str) and data[k] for k in ("summary", "hidden_cause", "already_tried", "belief")):
                return data
        except ValueError:
            pass
    raise RuntimeError(f"could not generate a scenario for {stack} / {bug}")


def dev_turn(scenario: dict, persona: str, turns: list[dict], instruction: str) -> str:
    from rubric import format_conversation

    prompt = DEV_PROMPT.format(persona=scenarios.PERSONAS[persona], conversation=format_conversation(turns),
                               instruction=instruction, **scenario)
    return teacher.ask([{"role": "user", "content": prompt}], temperature=0.9, max_tokens=120).strip().strip('"')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if EVAL_PATH.exists() and not args.force:
        print(f"{EVAL_PATH.name} is already frozen. Use --force only if nothing has been trained or evaluated.", file=sys.stderr)
        return 1

    rng = random.Random(7)
    kinds = ["first"] * 30 + ["second"] * 15 + ["ask"] * 5
    rng.shuffle(kinds)
    personas = list(scenarios.PERSONAS)
    items = []
    for i, ((stack, bug), kind) in enumerate(zip(scenarios.EVAL_COMBOS, kinds)):
        persona = personas[i % len(personas)]
        scenario = make_scenario(stack, bug)
        turns = [{"role": "duck", "text": rng.choice(NEUTRAL_DUCK)}]
        turns.append({"role": "you", "text": dev_turn(scenario, persona, turns, INSTR_NORMAL)})
        if kind in ("second", "ask"):
            turns.append({"role": "duck", "text": rng.choice([q for q in NEUTRAL_DUCK if q != turns[0]["text"]])})
            turns.append({"role": "you", "text": dev_turn(scenario, persona, turns, INSTR_ASK if kind == "ask" else INSTR_NORMAL)})
        items.append({"id": f"eval-{i:02d}", "kind": kind, "stack": stack, "bug": bug, "persona": persona,
                      "summary": scenario["summary"], "turns": turns})
        print(f"{items[-1]['id']} {kind:<6} {persona:<13} {stack} / {bug[:40]}", flush=True)

    EVAL_PATH.write_text("".join(json.dumps(it) + "\n" for it in items))
    HASH_PATH.write_text(f"{file_hash(EVAL_PATH)}  {EVAL_PATH.name}\n")
    print(f"\nFroze {len(items)} prompts. sha256 {file_hash(EVAL_PATH)[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
