"""
Train advanced XGBoost win probability model.

Uses ~45 features including rolling team stats, phase-wise scoring,
head-to-head records, venue characteristics, and toss data.

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    .venv/bin/python -m app.ml.train_v2
"""

import sys
from pathlib import Path
import numpy as np

API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.database import SessionLocal
from app.ml.features_v2 import load_all_data, build_feature_matrix


def main():
    print("Loading data from database...")
    db = SessionLocal()

    try:
        data = load_all_data(db)
        print(f"  Matches: {len(data['matches'])}")
        print(f"  Innings stats: {len(data['innings_stats'])}")

        print("\nBuilding feature matrix...")
        X, y, match_ids, seasons, feature_names = build_feature_matrix(data)
        print(f"  Feature matrix: {X.shape}")
        print(f"  Features: {len(feature_names)}")
        print(f"  Positive rate: {y.mean():.3f}")

        # Handle NaN
        nan_count = np.isnan(X).sum()
        if nan_count > 0:
            print(f"  Replacing {nan_count} NaN values with 0.5")
            X = np.nan_to_num(X, nan=0.5)

        # Time-based split
        seasons_arr = np.array(seasons)
        train_mask = np.array([s not in ("2024", "2025", "2026") for s in seasons])
        val_mask = np.array([s == "2024" for s in seasons])
        test_mask = np.array([s in ("2025", "2026") for s in seasons])

        X_train, y_train = X[train_mask], y[train_mask]
        X_val, y_val = X[val_mask], y[val_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        print(f"\n  Train: {len(X_train)} samples (up to 2023)")
        print(f"  Validation: {len(X_val)} samples (2024)")
        print(f"  Test: {len(X_test)} samples (2025-2026)")

        if len(X_train) < 100:
            print("ERROR: Not enough training data")
            return

        # Train XGBoost with early stopping
        from xgboost import XGBClassifier
        from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

        print("\nTraining XGBoost...")
        model = XGBClassifier(
            n_estimators=500,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.7,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            eval_metric="logloss",
            random_state=42,
            early_stopping_rounds=50,
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        best_iter = model.best_iteration
        print(f"  Best iteration: {best_iter}")

        # Evaluate on test set
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)

        accuracy = accuracy_score(y_test, y_pred)
        logloss = log_loss(y_test, y_proba)
        auc = roc_auc_score(y_test, y_proba[:, 1])

        print(f"\n=== TEST RESULTS (2025-2026) ===")
        print(f"  Accuracy: {accuracy:.3f}")
        print(f"  Log Loss: {logloss:.3f}")
        print(f"  AUC-ROC:  {auc:.3f}")

        # Validation results too
        y_val_pred = model.predict(X_val)
        y_val_proba = model.predict_proba(X_val)
        val_acc = accuracy_score(y_val, y_val_pred)
        val_auc = roc_auc_score(y_val, y_val_proba[:, 1])
        print(f"\n=== VALIDATION RESULTS (2024) ===")
        print(f"  Accuracy: {val_acc:.3f}")
        print(f"  AUC-ROC:  {val_auc:.3f}")

        # Feature importance
        importances = model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]
        print(f"\n=== TOP 15 FEATURES ===")
        for i in sorted_idx[:15]:
            print(f"  {feature_names[i]:30} {importances[i]:.4f}")

        # Save model
        import joblib
        model_dir = Path(__file__).resolve().parents[2] / "trained_models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "win_probability_v2.joblib"
        joblib.dump({"model": model, "feature_names": feature_names}, model_path)
        print(f"\nModel saved to {model_path}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
