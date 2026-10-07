"""CLI: capture a breadcrumb for a repo and print the summary and nudge.

    uv run python -m duckwalk.breadcrumb --repo . [--log path/to/terminal.log]
"""

import argparse
import sys

import sentry_sdk

from duckwalk import config
from duckwalk.activities import breadcrumb
from duckwalk.activities.llm import OllamaError
from duckwalk.telemetry import init_sentry


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a breadcrumb summary and walk nudge for a repo.")
    parser.add_argument("--repo", default=".", help="git repository to snapshot (default: .)")
    parser.add_argument("--log", help="terminal log to tail (overrides DUCKWALK_TERMINAL_LOG)")
    parser.add_argument("--show-state", action="store_true", help="also print the raw captured state")
    args = parser.parse_args()

    init_sentry()
    with sentry_sdk.start_transaction(op="duckwalk.cli", name="breadcrumb"):
        state = breadcrumb.capture_breadcrumb(args.repo, terminal_log=args.log)
        if args.show_state:
            print(breadcrumb.format_state(state), end="\n\n")
        try:
            summary = breadcrumb.summarize(state)
            nudge = breadcrumb.nudge(state)
        except OllamaError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    sentry_sdk.flush(timeout=10)

    print(f"Summary ({len(summary.text.split())} words):\n{summary.text}\n")
    print(f"Nudge:\n{nudge.text}\n")
    print(f"[{config.OLLAMA_MODEL}] summary {summary.duration_s:.1f}s, nudge {nudge.duration_s:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
