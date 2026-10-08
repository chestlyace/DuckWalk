"""Run the frozen eval set against one model and grade every reply with the rubric.

    uv run python ml/tinker/run_eval.py ollama:gemma4:31b-cloud          # the duck as deployed today (baseline)
    uv run python ml/tinker/run_eval.py tinker-base:Qwen/Qwen3.5-4B      # untuned base of the fine-tuned model
    uv run python ml/tinker/run_eval.py tinker:<tinker://checkpoint-path> --name qwen-tuned

Prompts are the deployed duck system prompt (with the eval item's summary) plus the conversation so far, exactly as
the voice loop would send them. Generation is sequential so latency numbers don't contend with each other. Grading
happens afterwards. Results go to ml/tinker/results/<name>.jsonl, and make_results.py builds eval/results.md.
"""

import argparse
import json
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sentry_sdk

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import build_eval  # noqa: E402
import rubric  # noqa: E402
import teacher  # noqa: E402
from duckwalk.activities import llm  # noqa: E402
from duckwalk.telemetry import init_sentry  # noqa: E402
from duckwalk.voice.duck import build_messages, system_prompt  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def generate_ollama(model: str):
    def run(messages: list[dict]) -> dict:
        stream = llm.ChatStream(messages, stage="eval", model=model, max_tokens=150)
        t0 = time.monotonic()
        text = "".join(stream)
        return {"text": text.strip(), "first_token_s": stream.first_token_s, "total_s": time.monotonic() - t0,
                "input_tokens": stream.input_tokens, "output_tokens": stream.output_tokens}
    return run


def make_generator(spec: str):
    kind, _, model = spec.partition(":")
    if kind == "ollama":
        return generate_ollama(model)
    if kind in ("tinker", "tinker-base"):
        from tinker_sampler import TinkerSampler  # needs TINKER_API_KEY; added with the training script

        return TinkerSampler(model, base_only=(kind == "tinker-base"))
    raise SystemExit(f"unknown model spec {spec!r}: use ollama:<tag>, tinker-base:<model> or tinker:<path>")


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    per_criterion = {c: sum(r["passed"][c] for r in rows) / n for c in rubric.CRITERIA}
    firsts = [r["first_token_s"] for r in rows if r["first_token_s"] is not None]
    return {
        "n": n,
        "mean_score": sum(r["score"] for r in rows) / n,
        "all_pass_rate": sum(r["all_pass"] for r in rows) / n,
        "per_criterion": per_criterion,
        "median_total_s": statistics.median(r["total_s"] for r in rows),
        "median_first_token_s": statistics.median(firsts) if firsts else None,
        "mean_output_tokens": sum(r["output_tokens"] for r in rows) / n,
        "mean_words": sum(len(rubric.words(r["reply"])) for r in rows) / n,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model", help="ollama:<tag> | tinker-base:<model> | tinker:<checkpoint path>")
    parser.add_argument("--name", help="result name (default: derived from the model)")
    args = parser.parse_args()

    build_eval.verify_frozen()
    items = [json.loads(line) for line in build_eval.EVAL_PATH.read_text().splitlines()]
    name = args.name or re.sub(r"[^A-Za-z0-9._-]+", "-", args.model)
    generate = make_generator(args.model)

    init_sentry()
    generated = []
    with sentry_sdk.start_transaction(op="duckwalk.eval", name=f"duck-eval {name}"):
        for i, item in enumerate(items):
            messages = build_messages(system_prompt(item["summary"]), item["turns"])
            out = generate(messages)
            out["text"] = " ".join(out["text"].split()).strip('"')
            generated.append(out)
            print(f"  {i + 1}/{len(items)} {out['total_s']:.1f}s  {out['text'][:80]}", flush=True)
    sentry_sdk.flush(timeout=10)

    with ThreadPoolExecutor(4) as pool:  # grading is independent per reply, so it runs in parallel
        grades = list(pool.map(lambda p: rubric.grade(p[1]["text"], p[0]["turns"], p[0]["summary"], teacher.judge, always_judge=True),
                               zip(items, generated)))
    rows = []
    for item, out, g in zip(items, generated, grades):
        rows.append({"id": item["id"], "kind": item["kind"], "reply": out["text"], "passed": g.passed, "verdict": g.verdict,
                     "reason": g.reason, "score": g.score, "all_pass": g.all_pass, "total_s": out["total_s"],
                     "first_token_s": out["first_token_s"], "input_tokens": out["input_tokens"],
                     "output_tokens": out["output_tokens"]})
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    s = summarize(rows)
    (RESULTS / f"{name}.summary.json").write_text(json.dumps({"model": args.model, **s}, indent=2) + "\n")
    print(f"\n{name}: mean score {s['mean_score']:.3f}, all-pass {s['all_pass_rate']:.0%}, "
          f"median {s['median_total_s']:.2f}s/reply, {s['mean_output_tokens']:.0f} output tokens")
    print("  " + ", ".join(f"{c} {v:.0%}" for c, v in s["per_criterion"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
