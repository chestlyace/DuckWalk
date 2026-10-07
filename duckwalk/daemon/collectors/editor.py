"""Editor signals from the Cursor/VS Code extension (editor/vscode)."""

from collections import Counter

from duckwalk import config
from duckwalk.daemon.collectors.events import read_events


def collect(start: float, end: float) -> dict:
    events = read_events(config.EDITOR_EVENTS, start, end)
    edits = Counter(e["file"] for e in events if e["type"] == "edit")
    undos = sum(e["type"] == "undo" for e in events)
    total = sum(edits.values()) + undos
    top_file, same_file_edits = edits.most_common(1)[0] if edits else (None, 0)
    return {
        "same_file_edits": same_file_edits,
        "undo_ratio": undos / total if total else 0.0,
        "top_file": top_file,
        "event_times": [e["ts"] for e in events],
    }


def open_files(since: float, limit: int = 5) -> list[str]:
    """Most recently focused files since `since`, newest first."""
    seen: list[str] = []
    for e in reversed(read_events(config.EDITOR_EVENTS, since)):
        if e["type"] in ("focus", "edit", "save") and e["file"] not in seen:
            seen.append(e["file"])
            if len(seen) == limit:
                break
    return seen
