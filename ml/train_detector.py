"""Evaluate the TabPFN stuck detector on hand-labeled windows.

Holds out a stratified test split, then fits on growing training subsets
(10, 20, 30, 50 windows, capped by what exists) and records precision and
recall at the configured threshold. Each size is averaged over several random
subsets, because single draws on tiny data are noise.

    uv run python ml/train_detector.py
Writes ml/data/detector_metrics.json and ml/data/learning_curve.png.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import precision_score, recall_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from duckwalk import config  # noqa: E402
from duckwalk.daemon import detector, store  # noqa: E402

OUT = Path(__file__).resolve().parent / "data"
SIZES = [10, 20, 30, 50]
REPEATS = 10
TEST_FRACTION = 0.3
SEED = 0


def subsample(train: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame | None:
    """A random training subset of size n that contains both classes, or None."""
    for _ in range(50):
        sub = train.sample(n=n, random_state=int(rng.integers(1 << 31)))
        if sub["stuck"].nunique() == 2:
            return sub
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, help="windows.db to read (default: config DB_PATH)")
    parser.add_argument("--out", type=Path, default=OUT, help="output directory")
    args = parser.parse_args()

    with store.connect(args.db) as conn:
        df = pd.DataFrame([dict(r) for r in store.labeled(conn)])
    if df.empty or df["stuck"].value_counts().min() < 2:
        print(f"error: need at least 2 stuck and 2 flow labeled windows, have {len(df)} total", file=sys.stderr)
        return 1
    df["stuck"] = df["stuck"].astype(int)

    train, test = train_test_split(df, test_size=TEST_FRACTION, stratify=df["stuck"], random_state=SEED)
    sizes = sorted({min(n, len(train)) for n in SIZES})
    rng = np.random.default_rng(SEED)
    results = []
    for n in sizes:
        precisions, recalls = [], []
        for _ in range(REPEATS if n < len(train) else 1):
            sub = subsample(train, n, rng)
            if sub is None:
                continue
            clf = detector.fit(sub.to_dict("records"))
            proba = clf.predict_proba(test[store.FEATURES])[:, list(clf.classes_).index(1)]
            pred = (proba > config.STUCK_THRESHOLD).astype(int)
            precisions.append(precision_score(test["stuck"], pred, zero_division=0))
            recalls.append(recall_score(test["stuck"], pred, zero_division=0))
        if precisions:
            results.append({
                "train_size": n, "draws": len(precisions),
                "precision_mean": float(np.mean(precisions)), "precision_std": float(np.std(precisions)),
                "recall_mean": float(np.mean(recalls)), "recall_std": float(np.std(recalls)),
            })
            r = results[-1]
            print(f"n={n:>3}  precision {r['precision_mean']:.2f}±{r['precision_std']:.2f}  "
                  f"recall {r['recall_mean']:.2f}±{r['recall_std']:.2f}  ({r['draws']} draws)")

    args.out.mkdir(parents=True, exist_ok=True)
    metrics = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "labeled_windows": len(df), "stuck": int(df["stuck"].sum()), "flow": int((1 - df["stuck"]).sum()),
        "test_windows": len(test), "threshold": config.STUCK_THRESHOLD, "results": results,
        "note": "Small held-out set; treat these numbers as indicative, not conclusive.",
    }
    (args.out / "detector_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    fig, ax = plt.subplots(figsize=(6, 4))
    xs = [r["train_size"] for r in results]
    for key, label in (("precision", "Precision"), ("recall", "Recall")):
        ax.errorbar(xs, [r[f"{key}_mean"] for r in results], yerr=[r[f"{key}_std"] for r in results],
                    marker="o", capsize=3, label=label)
    ax.set(xlabel="Labeled training windows", ylabel=f"Held-out score (threshold {config.STUCK_THRESHOLD})",
           ylim=(0, 1.05), xticks=xs,
           title=f"Stuck detector learning curve (test n={len(test)})")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out / "learning_curve.png", dpi=150)
    print(f"wrote {args.out / 'detector_metrics.json'} and {args.out / 'learning_curve.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
