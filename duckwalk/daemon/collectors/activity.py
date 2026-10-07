"""Break detection from editor and `dw` activity.

KDE Wayland doesn't expose session idle time, so "last input" is the latest
editor event or `dw` run. A gap of BREAK_GAP_MINUTES with neither is a break.
"""

from duckwalk import config
from duckwalk.daemon.collectors.events import read_events

LOOKBACK_HOURS = 12


def activity_times(start: float, end: float) -> list[float]:
    times = [e["ts"] for e in read_events(config.EDITOR_EVENTS, start, end)]
    for r in read_events(config.RUN_EVENTS, start, end):
        times += [r["ts"], r.get("end", r["ts"])]
    return sorted(t for t in times if start <= t < end)


def mins_since_break(end: float) -> float:
    """Minutes from the end of the last break (or the start of the lookback) to `end`."""
    start = end - LOOKBACK_HOURS * 3600
    times = activity_times(start, end)
    if not times:
        return 0.0
    gap = config.BREAK_GAP_MINUTES * 60
    resumed = times[0]
    for prev, cur in zip(times, times[1:]):
        if cur - prev >= gap:
            resumed = cur
    if end - times[-1] >= gap:  # currently on a break
        return 0.0
    return (end - resumed) / 60
