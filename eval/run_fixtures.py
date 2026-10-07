"""Run the summary and nudge prompts on every fixture state and write eval/fixtures/outputs.md.

    uv run python eval/run_fixtures.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import sentry_sdk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from duckwalk import config  # noqa: E402
from duckwalk.activities import breadcrumb  # noqa: E402
from duckwalk.telemetry import init_sentry  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SUMMARY_WORD_LIMIT = 60


def main() -> int:
    fixtures = json.loads((FIXTURES / "states.json").read_text())
    init_sentry()
    rows, sections = [], []
    with sentry_sdk.start_transaction(op="duckwalk.eval", name="fixtures"):
        for fx in fixtures:
            summary = breadcrumb.summarize(fx["state"])
            nudge = breadcrumb.nudge(fx["state"])
            words = len(summary.text.split())
            within = words <= SUMMARY_WORD_LIMIT
            rows.append(
                f"| {fx['id']} | {words} | {'yes' if within else '**NO**'} | {len(nudge.text.split())} "
                f"| {summary.input_tokens}+{summary.output_tokens} | {nudge.input_tokens}+{nudge.output_tokens} |"
            )
            sections.append(
                f"## {fx['id']}\n\n_{fx['description']}_\n\n"
                f"**Summary** ({words} words):\n\n```\n{summary.text}\n```\n\n"
                f"**Nudge:** {nudge.text}\n\n"
                f"**Would you act on it?** [ ] yes  [ ] no\n"
            )
            print(f"{fx['id']}: {words} words{'' if within else ' (OVER LIMIT)'}", flush=True)
    sentry_sdk.flush(timeout=10)

    out = FIXTURES / "outputs.md"
    out.write_text(
        f"# Fixture outputs\n\n"
        f"Model `{config.OLLAMA_MODEL}`, generated {datetime.now():%Y-%m-%d %H:%M} by `eval/run_fixtures.py`. "
        f"Prompts: `duckwalk/prompts/summary.txt`, `duckwalk/prompts/nudge.txt`.\n\n"
        f"| Fixture | Summary words | Within {SUMMARY_WORD_LIMIT}? | Nudge words | Summary tokens (in+out) | Nudge tokens (in+out) |\n"
        f"|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n" + "\n".join(sections)
    )
    print(f"wrote {out.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
