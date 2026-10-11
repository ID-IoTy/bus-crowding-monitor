"""Train the crowdedness ML model on historical correlated events.

Produces ml/model.joblib, a GradientBoostingRegressor that predicts how many
people will board at a stop given context features.

Requires the optional ML stack (requirements-ml.txt). If scikit-learn is not
installed, this script exits with a clear message and the server simply keeps
using the rule-based predictor.

Run with:
    python -m ml.train
"""
from __future__ import annotations

import sys

from app.config import MODEL_PATH
from app.db.database import SessionLocal
import app.models  # noqa: F401
from app.models.events import CorrelatedEvent


def _load_training_frame(db):
    rows = db.query(CorrelatedEvent).all()
    data = []
    for r in rows:
        # Feature: occupancy fraction on arrival, stop seq (from id suffix),
        # hour, weekday, people waiting -> target: people boarded.
        try:
            seq = int(r.stop_id.split("S")[-1])
        except (ValueError, IndexError):
            seq = 0
        occ_arrival_frac = max(0.0, r.occupancy_before - r.people_alighted) / 75.0
        data.append({
            "occ_arrival_frac": occ_arrival_frac,
            "sequence": seq,
            "hour": r.timestamp.hour,
            "weekday": r.timestamp.weekday(),
            "avg_board_proxy": r.waiting_before,
            "waiting": r.waiting_before,
            "target_boarded": r.people_boarded,
        })
    return data


def main() -> int:
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError:
        print(
            "scikit-learn not installed. Skipping ML training; the server will "
            "use the rule-based predictor.\n"
            "Install the optional stack with: pip install -r requirements-ml.txt"
        )
        return 0

    db = SessionLocal()
    try:
        data = _load_training_frame(db)
    finally:
        db.close()

    if len(data) < 50:
        print(
            f"Only {len(data)} correlated events found. Run the simulator first:\n"
            "    python -m simulator.simulate_day"
        )
        return 1

    feature_cols = ["occ_arrival_frac", "sequence", "hour", "weekday", "avg_board_proxy", "waiting"]
    X = np.array([[row[c] for c in feature_cols] for row in data], dtype=float)
    y = np.array([row["target_boarded"] for row in data], dtype=float)

    model = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.08)
    model.fit(X, y)

    score = model.score(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Trained on {len(data)} samples. R^2={score:.3f}. Saved to {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
