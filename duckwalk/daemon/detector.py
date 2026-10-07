"""TabPFN stuck detector: P(stuck) for a window, fitted on the hand-labeled windows.

    uv run python -m duckwalk.daemon.detector --synthetic stuck   # check a synthetic window
    uv run python -m duckwalk.daemon.detector --synthetic flow
"""

import argparse
import sys

import pandas as pd

from duckwalk import config
from duckwalk.daemon import store

# Clear-cut synthetic windows for checking the detector end to end. Not training data.
SYNTHETIC = {
    "stuck": {"mins_since_break": 110, "failed_builds": 6, "same_file_edits": 140, "undo_ratio": 0.35, "commits": 0, "hour": 22},
    "flow": {"mins_since_break": 25, "failed_builds": 0, "same_file_edits": 40, "undo_ratio": 0.02, "commits": 1, "hour": 10},
}


class NotEnoughLabels(Exception):
    pass


def fit(rows: list | None = None):
    """Fit TabPFN on labeled windows. Needs both classes."""
    from tabpfn import TabPFNClassifier  # slow import; keep it out of the daemon's startup

    if rows is None:
        with store.connect() as conn:
            rows = store.labeled(conn)
    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty or df["stuck"].nunique() < 2:
        raise NotEnoughLabels(f"{len(df)} labeled windows; need both stuck and flow examples")
    clf = TabPFNClassifier(device="cpu")
    clf.fit(df[store.FEATURES], df["stuck"].astype(int))
    return clf


def p_stuck(window: dict, clf=None) -> float:
    clf = clf or fit()
    X = pd.DataFrame([{f: window[f] for f in store.FEATURES}])
    proba = clf.predict_proba(X)[0]
    return float(proba[list(clf.classes_).index(1)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a synthetic window with the stuck detector.")
    parser.add_argument("--synthetic", choices=SYNTHETIC, default="stuck")
    args = parser.parse_args()
    try:
        p = p_stuck(SYNTHETIC[args.synthetic])
    except NotEnoughLabels as e:
        print(f"error: {e}. Label windows first: uv run python -m duckwalk.daemon.label", file=sys.stderr)
        return 1
    verdict = "STUCK (would nudge)" if p > config.STUCK_THRESHOLD else "not stuck"
    print(f"{args.synthetic} window: P(stuck) = {p:.2f}, threshold {config.STUCK_THRESHOLD} -> {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
