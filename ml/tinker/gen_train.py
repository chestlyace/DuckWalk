"""Generate ~500 synthetic duck dialogues with the teacher and filter them with the rubric.

    uv run python ml/tinker/gen_train.py [--dialogues 510] [--workers 5]    # resumable; re-run to continue
    uv run python ml/tinker/gen_train.py --build-only                       # rebuild train.jsonl from dialogues.jsonl

For each (stack, bug) combination from the TRAIN half of the grid, the teacher invents a scenario, then plays both
sides: a developer (several personas, sometimes demanding the answer) and the duck. Every duck reply is graded with the
rubric and resampled until it passes (up to MAX_ATTEMPTS). A dialogue stops early if no candidate passes, so only
rubric-passing replies reach the training set. The teacher sees the deployed duck prompt plus a short addendum;
the training examples use the deployed prompt alone, so the student learns to behave that way unprompted.

Eval prompts are never used here: the eval combinations are disjoint, and train.jsonl is checked against the frozen eval set.
"""

import argparse
import json
import random
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import build_eval  # noqa: E402
import rubric  # noqa: E402
import scenarios  # noqa: E402
import teacher  # noqa: E402
from duckwalk.voice.duck import build_messages, system_prompt  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
MAX_ATTEMPTS = 4
ADDENDUM = """

Extra rules for this conversation:
- Every question must be open: ask what they saw, expected, ruled out, or how they could test one of THEIR OWN ideas.
- Never introduce a cause or idea of your own, not even as a question. Never ask "what if you tried X" or "could it be Y" unless they said Y.
- If they ask you to tell them the answer, say plainly that you won't, in a few words, then ask one question."""

_lock = threading.Lock()


def clean(text: str) -> str:
    return " ".join(text.strip().strip('"').split())


def duck_reply(summary: str, turns: list[dict], opener: bool, stats: Counter) -> str | None:
    """A duck reply that passes every rubric criterion, or None if MAX_ATTEMPTS candidates all fail."""
    system = system_prompt(summary) + ADDENDUM
    for attempt in range(MAX_ATTEMPTS):
        reply = clean(teacher.ask(build_messages(system, turns, opener), temperature=0.9, max_tokens=80))
        g = rubric.grade(reply, turns, summary, teacher.judge)
        with _lock:
            stats["candidates"] += 1
            stats[f"verdict_{g.verdict}"] += 1
            for name, ok in g.passed.items():
                stats[f"fail_{name}"] += not ok
            if attempt == 0:
                stats["first_try"] += 1
                stats["first_try_pass"] += g.all_pass
        if g.all_pass:
            return reply
    return None


def make_dialogue(dialogue_id: str, scenario: dict, persona: str, rng: random.Random, stats: Counter) -> dict:
    summary = scenario["summary"]
    turns: list[dict] = []
    reply = duck_reply(summary, turns, True, stats)
    if reply is None:
        return {"id": dialogue_id, "persona": persona, "summary": summary, "turns": turns, "stopped": "opener"}
    turns.append({"role": "duck", "text": reply})
    n_user = rng.choice([2, 3, 3, 4])
    ask_at = rng.randrange(1, n_user) if rng.random() < 0.3 else -1
    stopped = "complete"
    for k in range(n_user):
        text = build_eval.dev_turn(scenario, persona, turns, build_eval.INSTR_ASK if k == ask_at else build_eval.INSTR_NORMAL)
        turns.append({"role": "you", "text": text})
        reply = duck_reply(summary, turns, False, stats)
        if reply is None:
            turns.pop()  # drop the developer turn the duck couldn't answer well
            stopped = f"no_pass_at_turn_{k + 1}"
            break
        turns.append({"role": "duck", "text": reply})
    return {"id": dialogue_id, "persona": persona, "summary": summary, "turns": turns, "stopped": stopped,
            "asked_for_answer": ask_at >= 0}


def trigrams(text: str) -> set:
    w = rubric.words(text)
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def build_train() -> None:
    """Turn dialogues.jsonl into train.jsonl: one example per duck turn, in exactly the voice loop's message format."""
    build_eval.verify_frozen()
    dialogues = [json.loads(line) for line in (DATA / "dialogues.jsonl").read_text().splitlines()]
    eval_items = [json.loads(line) for line in build_eval.EVAL_PATH.read_text().splitlines()]
    eval_tri = [trigrams(e["summary"] + " " + " ".join(t["text"] for t in e["turns"])) for e in eval_items]
    examples, dropped_overlap = [], 0
    for d in dialogues:
        for i, turn in enumerate(d["turns"]):
            if turn["role"] != "duck":
                continue
            prefix = d["turns"][:i]
            tri = trigrams(d["summary"] + " " + " ".join(t["text"] for t in prefix))
            if any(tri and len(tri & e) / len(tri | e) > 0.5 for e in eval_tri):
                dropped_overlap += 1
                continue
            messages = build_messages(system_prompt(d["summary"]), prefix, opener=(i == 0))
            examples.append({"dialogue": d["id"], "messages": messages + [{"role": "assistant", "content": turn["text"]}]})
    (DATA / "train.jsonl").write_text("".join(json.dumps(e) + "\n" for e in examples))
    stopped = Counter(d["stopped"].split("_at_")[0] for d in dialogues)
    print(f"{len(dialogues)} dialogues -> {len(examples)} training examples "
          f"({dropped_overlap} dropped for overlap with eval). Dialogue endings: {dict(stopped)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dialogues", type=int, default=510)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    build_eval.verify_frozen()  # the eval set must exist and be frozen before any training data is made
    DATA.mkdir(exist_ok=True)
    if args.build_only:
        build_train()
        return 0

    rng = random.Random(11)
    combos = rng.sample(scenarios.TRAIN_COMBOS, k=min(len(scenarios.TRAIN_COMBOS), -(-args.dialogues // 3)))
    persona_names = list(scenarios.PERSONAS)
    jobs = []
    for ci, (stack, bug) in enumerate(combos):
        for pj, persona in enumerate(rng.sample(persona_names, 3)):
            jobs.append((f"train-{ci:03d}-{pj}", (stack, bug), persona))
    jobs = jobs[: args.dialogues]

    done_path, scen_path, stats_path = DATA / "dialogues.jsonl", DATA / "scenarios.jsonl", DATA / "gen_stats.json"
    done = {json.loads(l)["id"] for l in done_path.read_text().splitlines()} if done_path.exists() else set()
    scen_cache = {json.loads(l)["combo"]: json.loads(l)["scenario"] for l in scen_path.read_text().splitlines()} if scen_path.exists() else {}
    stats = Counter(json.loads(stats_path.read_text())) if stats_path.exists() else Counter()
    todo = [j for j in jobs if j[0] not in done]
    print(f"{len(done)} dialogues done, {len(todo)} to go ({args.workers} workers)", flush=True)

    def work(job):
        did, (stack, bug), persona = job
        key = f"{stack} | {bug}"
        with _lock:
            scenario = scen_cache.get(key)
        if scenario is None:
            scenario = build_eval.make_scenario(stack, bug)
            with _lock:
                scen_cache[key] = scenario
                with open(scen_path, "a") as f:
                    f.write(json.dumps({"combo": key, "scenario": scenario}) + "\n")
        return make_dialogue(did, scenario, persona, random.Random(did), stats) | {"stack": stack, "bug": bug}

    with ThreadPoolExecutor(args.workers) as pool, open(done_path, "a") as out:
        futures = [pool.submit(work, j) for j in todo]
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                d = fut.result()
            except Exception as e:  # one failed dialogue (e.g. cloud outage) must not lose the others
                print(f"  dialogue failed: {e}", flush=True)
                continue
            with _lock:
                out.write(json.dumps(d) + "\n")
                out.flush()
                stats_path.write_text(json.dumps(stats))
            if n % 10 == 0:
                print(f"  {len(done) + n}/{len(jobs)} dialogues; candidates so far {stats['candidates']}, "
                      f"first-try pass {stats['first_try_pass']}/{stats['first_try']}", flush=True)
    build_train()
    return 0


if __name__ == "__main__":
    sys.exit(main())
