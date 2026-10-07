"""Daemon: every 5 minutes, turn the last window of signals into a row in windows.db.

    uv run python -m duckwalk.daemon            # run forever (the systemd service runs this)
    uv run python -m duckwalk.daemon --once     # record the window that just ended, then exit
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime

from duckwalk import config
from duckwalk.daemon import store
from duckwalk.daemon.collectors import activity, build, editor, git

log = logging.getLogger("duckwalk.daemon")
WINDOW_S = config.WINDOW_MINUTES * 60


def build_window(start: float, end: float) -> dict | None:
    """Features for [start, end), or None when there was no activity at all."""
    ed = editor.collect(start, end)
    bd = build.collect(start, end)
    gt = git.collect(start, end)
    if not ed["event_times"] and not bd["event_times"] and not gt["commits"]:
        return None
    return {
        "ts": datetime.fromtimestamp(start).isoformat(timespec="seconds"),
        "repo": git.repo_for(ed["top_file"]),
        "mins_since_break": round(activity.mins_since_break(end), 1),
        "failed_builds": bd["failed_builds"],
        "same_file_edits": ed["same_file_edits"],
        "undo_ratio": round(ed["undo_ratio"], 3),
        "commits": gt["commits"],
        "hour": datetime.fromtimestamp(start).hour,
    }


def record(conn, start: float) -> None:
    window = build_window(start, start + WINDOW_S)
    if window is None:
        log.info("window %s: no activity, skipped", datetime.fromtimestamp(start).strftime("%H:%M"))
        return
    row = store.insert_window(conn, window)
    log.info("window %s recorded as #%d: %s", window["ts"], row, {f: window[f] for f in store.FEATURES})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="record the window that just ended and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not config.REPOS:
        log.warning("DUCKWALK_REPOS is empty, so commits will always be 0")

    conn = store.connect()
    if args.once:
        now = time.time()
        record(conn, now - now % WINDOW_S - WINDOW_S)
        return 0

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    log.info("started; windows of %d min -> %s", config.WINDOW_MINUTES, config.DB_PATH)
    while True:
        now = time.time()
        next_boundary = now - now % WINDOW_S + WINDOW_S
        time.sleep(next_boundary - now + 1)  # +1s so late-flushed events land in the window
        try:
            record(conn, next_boundary - WINDOW_S)
        except Exception:  # one bad window must not kill the daemon
            log.exception("failed to record window")


if __name__ == "__main__":
    sys.exit(main())
