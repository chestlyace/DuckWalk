"""Build/test results recorded by `dw`."""

from duckwalk import config
from duckwalk.daemon.collectors.events import read_events


def collect(start: float, end: float) -> dict:
    runs = read_events(config.RUN_EVENTS, start, end)
    return {
        "failed_builds": sum(r["exit"] != 0 for r in runs),
        "event_times": [r["ts"] for r in runs] + [r["end"] for r in runs if "end" in r],
    }
