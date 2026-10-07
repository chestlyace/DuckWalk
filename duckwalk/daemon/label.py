"""One-key labeling of recorded windows: s = stuck, f = flow, k = skip, q = quit.

    uv run python -m duckwalk.daemon.label           # unlabeled windows, oldest first
    uv run python -m duckwalk.daemon.label --all     # also re-label labeled ones
"""

import argparse
import sys
import termios
import tty
from collections import Counter
from datetime import datetime
from pathlib import Path

from duckwalk import config
from duckwalk.daemon import store
from duckwalk.daemon.collectors.events import read_events

KEYS = {"s": 1, "f": 0}


def getkey() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def context(ts: str) -> str:
    """What happened in the window, to help remember it."""
    start = datetime.fromisoformat(ts).timestamp()
    end = start + config.WINDOW_MINUTES * 60
    files = Counter(Path(e["file"]).name for e in read_events(config.EDITOR_EVENTS, start, end) if e["type"] == "edit")
    runs = read_events(config.RUN_EVENTS, start, end)
    lines = []
    if files:
        lines.append("  edited: " + ", ".join(f"{f} ({n})" for f, n in files.most_common(3)))
    if runs:
        lines.append("  ran:    " + ", ".join(f"{r['cmd']} -> exit {r['exit']}" for r in runs[-5:]))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="include already-labeled windows")
    args = parser.parse_args()

    conn = store.connect()
    where = "" if args.all else "WHERE stuck IS NULL"
    rows = conn.execute(f"SELECT * FROM windows {where} ORDER BY ts").fetchall()
    if not rows:
        print("Nothing to label.")
        return 0
    print(f"{len(rows)} windows. Keys: s = stuck, f = flow, k = skip, q = quit\n")
    done = 0
    for row in rows:
        when = datetime.fromisoformat(row["ts"]).strftime("%a %d %b %H:%M")
        current = {1: "stuck", 0: "flow", None: "unlabeled"}[row["stuck"]]
        print(f"#{row['id']}  {when}  ({current})")
        print("  " + "  ".join(f"{f}={row[f]}" for f in store.FEATURES))
        if ctx := context(row["ts"]):
            print(ctx)
        key = getkey()
        while key not in ("s", "f", "k", "q"):
            key = getkey()
        if key == "q":
            break
        if key in KEYS:
            conn.execute("UPDATE windows SET stuck = ? WHERE id = ?", (KEYS[key], row["id"]))
            conn.commit()
            done += 1
        print(f"  -> {'stuck' if key == 's' else 'flow' if key == 'f' else 'skipped'}\n")
    counts = dict(conn.execute("SELECT stuck, COUNT(*) FROM windows WHERE stuck IS NOT NULL GROUP BY stuck").fetchall())
    print(f"Labeled {done} now. Totals: stuck {counts.get(1, 0)}, flow {counts.get(0, 0)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
