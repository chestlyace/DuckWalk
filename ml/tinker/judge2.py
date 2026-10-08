"""Re-grade saved eval replies with an independent judge from another model family (gpt-oss:120b-cloud).

    uv run python ml/tinker/judge2.py gemma4-31b-cloud qwen35-4b-base qwen35-4b-duck-v1

The main judge is gemma4:31b-cloud, the same family as the teacher that wrote the training data, so it may be lenient
toward that style. This second opinion checks that. Writes ml/tinker/results/<name>.judge2.json (verdict counts).
"""

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_eval  # noqa: E402
import rubric  # noqa: E402
import teacher  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
JUDGE2 = "gpt-oss:120b-cloud"


def verdict(item: dict, reply: str) -> str:
    prompt = rubric.JUDGE_PROMPT.format(summary=item["summary"], conversation=rubric.format_conversation(item["turns"]), reply=reply)
    for _ in range(3):
        try:
            text = teacher.llm.chat([{"role": "user", "content": prompt}], stage="judge2", model=JUDGE2,
                                    temperature=0, max_tokens=400, json_mode=True).text
        except teacher.llm.OllamaError:
            continue
        v, why = rubric.parse_verdict(text)
        if "could not be parsed" not in why:
            return v
    return "unparsed"


def main() -> int:
    build_eval.verify_frozen()
    items = {json.loads(l)["id"]: json.loads(l) for l in build_eval.EVAL_PATH.read_text().splitlines()}
    for name in sys.argv[1:]:
        rows = [json.loads(l) for l in (RESULTS / f"{name}.jsonl").read_text().splitlines()]
        with ThreadPoolExecutor(4) as pool:
            verdicts = list(pool.map(lambda r: verdict(items[r["id"]], r["reply"]), rows))
        counts = Counter(verdicts)
        (RESULTS / f"{name}.judge2.json").write_text(json.dumps({"judge": JUDGE2, "n": len(rows), "verdicts": dict(counts)}, indent=2) + "\n")
        print(f"{name:<20} {dict(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
