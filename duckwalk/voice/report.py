"""Latency table and reply checks for saved walk conversations.

    uv run python -m duckwalk.voice.report DIR [--out latency.md]

Reads every *.json transcript in DIR. Numbers come straight from the saved per-turn metrics.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

from duckwalk.voice.duck import GOODBYE, RESUMED, STILL_HERE


def _fmt(v, digits=2):
    return "-" if v is None else f"{v:.{digits}f}"


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def build(directory: Path) -> str:
    files = sorted(directory.glob("*.json"))
    rows, replies, all_metrics = [], [], []
    for f in files:
        data = json.loads(f.read_text())
        engine = f"{data['model']} / {data['tts']}"
        for m in data["metrics"]:
            if m["turn"] == 0:
                continue  # the opening question has no end of speech to measure from
            perceived = None if m["reply_latency_s"] is None else m["hangover_s"] + m["reply_latency_s"]
            all_metrics.append({**m, "perceived": perceived})
            rows.append(f"| {f.stem} | {m['turn']} | {_fmt(m['speech_s'], 1)} | {_fmt(m['stt_s'])} "
                        f"| {_fmt(m['llm_first_token_s'])} | {_fmt(m['tts_first_synth_s'])} "
                        f"| {_fmt(m['reply_latency_s'])} | {_fmt(perceived)} |")
        canned = (GOODBYE, STILL_HERE, RESUMED)
        replies += [t["text"] for t in data["turns"]
                    if t["role"] == "duck" and t["text"] not in canned and "Let's wrap up here" not in t["text"]]

    med = lambda key: _fmt(_median([m[key] for m in all_metrics]))  # noqa: E731
    questions = sum("?" in r for r in replies)
    flagged = [r for r in replies if "`" in r or len(r.split()) > 40]
    out = [
        "# Voice loop latency", "",
        f"{len(files)} conversations, {len(all_metrics)} measured turns. All times in seconds.", "",
        "- **reply latency**: VAD decides you finished, to the first audio reaching the speaker (STT + LLM first sentence + TTS).",
        "- **perceived**: reply latency plus the 0.7 s of silence the VAD waits for before deciding. This is what you actually wait.", "",
        "| Conversation | Turn | Speech | STT | LLM first token | TTS first audio | Reply latency | Perceived |",
        "|---|---|---|---|---|---|---|---|", *rows,
        f"| **median** | | {med('speech_s')} | {med('stt_s')} | {med('llm_first_token_s')} | {med('tts_first_synth_s')} "
        f"| **{med('reply_latency_s')}** | **{_fmt(_median([m['perceived'] for m in all_metrics]))}** |", "",
        "## Reply checks (the duck's LLM replies, not its fixed goodbye lines)", "",
        f"- Replies containing a question: {questions} of {len(replies)}",
        f"- Replies with code ticks or over 40 words: {len(flagged)} of {len(replies)}",
        "- Whether a reply hands out a solution is a judgement call: read the transcripts.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not list(args.directory.glob("*.json")):
        print(f"no transcripts in {args.directory}", file=sys.stderr)
        return 1
    text = build(args.directory)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
