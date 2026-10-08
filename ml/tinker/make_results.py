"""Build eval/results.md from ml/tinker/results/*.summary.json. Every number in the table comes from those files.

    uv run python ml/tinker/make_results.py [--order name1 name2 ...]
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "eval" / "results.md"
LABELS = {
    "gemma4-31b-cloud": ("gemma4:31b-cloud, deployed prompt", "the duck as it runs today (Ollama cloud)"),
    "qwen35-4b-base": ("Qwen3.5-4B, untuned", "same model as the tuned one, before training (Tinker)"),
    "qwen35-4b-duck-v1": ("Qwen3.5-4B, fine-tuned", "after supervised fine-tuning on the filtered dialogues (Tinker)"),
}
CRITERIA = ["asks_question", "one_question", "concise", "plain_speech", "no_fix_phrasing",
            "refers_to_problem", "no_direct_fix", "not_leading"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", nargs="*", default=list(LABELS))
    args = parser.parse_args()
    runs = {n: json.loads((HERE / "results" / f"{n}.summary.json").read_text())
            for n in args.order if (HERE / "results" / f"{n}.summary.json").exists()}
    if not runs:
        print("no results yet", file=sys.stderr)
        return 1
    for n, r in runs.items():
        r["name"] = n
    names = list(runs)
    head = "| Metric | " + " | ".join(LABELS.get(n, (n, ""))[0] for n in names) + " |"
    sep = "|---|" + "---|" * len(names)

    def row(label, fn):
        return f"| {label} | " + " | ".join(fn(runs[n]) for n in names) + " |"

    def independent(r):
        f = HERE / "results" / f"{r['name']}.judge2.json"
        if not f.exists():
            return "-"
        j = json.loads(f.read_text())
        return f"{j['verdicts'].get('asks_only', 0)}/{j['n']}"

    pct = lambda v: f"{v:.0%}"  # noqa: E731
    lines = [
        "# Duck evaluation: baseline vs. fine-tuned", "",
        f"Frozen eval set: {runs[names[0]]['n']} held-out prompts (`ml/tinker/eval_set.jsonl`, hash in `eval_set.sha256`), never used for training.",
        "Each reply is graded on 8 pass/fail criteria (`ml/tinker/rubric.py`): 6 deterministic checks and 2 from an LLM judge.", "",
        head, sep,
        row("**All 8 criteria pass**", lambda r: f"**{pct(r['all_pass_rate'])}**"),
        row("Mean rubric score (of 1.0)", lambda r: f"{r['mean_score']:.3f}"),
        *[row(f"&nbsp;&nbsp;{c}", lambda r, c=c: pct(r["per_criterion"][c])) for c in CRITERIA],
        row("Pure question, independent judge (gpt-oss:120b)", independent),
        row("Median time per reply", lambda r: f"{r['median_total_s']:.2f} s"),
        row("Mean output tokens", lambda r: f"{r['mean_output_tokens']:.0f}"),
        row("Mean words per reply", lambda r: f"{r['mean_words']:.1f}"), "",
        "## Models", "",
        *[f"- **{LABELS.get(n, (n, ''))[0]}**: {LABELS.get(n, (n, ''))[1]}" for n in names], "",
        "## Read this before quoting the numbers", "",
        "- Reply time is not like-for-like: the baseline streams from Ollama's cloud and the Qwen runs sample from Tinker's servers.",
        "- The main judge (gemma4:31b-cloud) is the same family as the teacher that wrote the training data, so it may favor that style. "
        "A judge from another family (gpt-oss:120b, the row above) is the check. On it the fine-tuned model is level with the deployed "
        "Gemma duck within noise, not ahead. Its verdicts also vary slightly between runs.",
        "- So the gains that hold up are: the one-question rule (a code check, no judge involved), and a large improvement over the untuned "
        "model of the same size. Against the much larger Gemma duck, the honest claim is equal quality from a 4B model, not better quality.",
        "- One rubric change was made after seeing the baseline, before any tuned model existed: the judge now always runs, so one flaw "
        "isn't counted three times. The baseline was re-run under the final rubric.",
        "- 50 prompts is a small sample. A difference of a few points is within noise.",
    ]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
