"""Read JSONL event logs (editor extension, `dw`) by time range."""

import json
from pathlib import Path


def read_events(path: Path, start: float = 0.0, end: float = float("inf")) -> list[dict]:
    """Events with start <= ts < end. Malformed lines are skipped."""
    if not path.exists():
        return []
    events = []
    with open(path) as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if start <= e.get("ts", -1) < end:
                events.append(e)
    return events
