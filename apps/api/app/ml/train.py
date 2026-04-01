"""
Train the win probability model.

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    python -m app.ml.train
"""

import sys
from pathlib import Path

import numpy as np

API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.database import SessionLocal
from app.models.models import Match
from app.ml.features import build_match_features
from app.ml.win_probability import WinProbabilityModel


def main():
    print("Loading matches from database ...")
    db = SessionLocal()

    try:
        matches = (
            db.query(Match)
            .filter(
                Match.winner_id.isnot(None),
                Match.team1_id.isnot(None),
                Match.team2_id.isnot(None),
            )
            .order_by(Match.date)
            .all()
        )

        print(f"Found {len(matches)} decided matches.")

        X_list = []
        y_list = []
        skipped = 0

        for i, match in enumerate(matches):
            features = build_match_features(db, match)
            if features is None:
                skipped += 1
                continue

            label = 1 if match.winner_id == match.team1_id else 0
            X_list.append(features)
            y_list.append(label)

            if (i + 1) % 200 == 0:
                print(f"  Processed {i + 1}/{len(matches)} matches ...")

        print(f"Built {len(X_list)} feature vectors (skipped {skipped}).")

        if len(X_list) < 50:
            print("Not enough data to train. Need at least 50 matches.")
            return

        X = np.array(X_list)
        y = np.array(y_list)

        # Train/test split (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        print(f"Training on {len(X_train)} samples, testing on {len(X_test)} ...")

        model = WinProbabilityModel()
        model.train(X_train, y_train)

        # Evaluate
        from sklearn.metrics import accuracy_score, log_loss

        y_pred = model.model.predict(X_test)
        y_proba = model.model.predict_proba(X_test)

        accuracy = accuracy_score(y_test, y_pred)
        logloss = log_loss(y_test, y_proba)

        print(f"\nResults:")
        print(f"  Accuracy: {accuracy:.3f}")
        print(f"  Log Loss: {logloss:.3f}")
        print(f"  Model saved to {model.save.__code__.co_filename}")
        print("Done!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
