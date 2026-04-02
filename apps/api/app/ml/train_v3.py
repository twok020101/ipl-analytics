"""
Train V3 XGBoost win probability model with squad composition features.

Extends V2's ~38 features with 24 squad features (12 per team) for ~62 total.

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    .venv/bin/python -m app.ml.train_v3
"""

import sys
from pathlib import Path
import numpy as np

API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.database import SessionLocal
from app.ml.features_v2 import load_all_data
from app.ml.features_v3 import load_squad_data, build_feature_matrix_v3


def main():
    print("=" * 60)
    print("IPL Win Probability Model V3 — Squad Composition Features")
    print("=" * 60)

    print("\nLoading data from database...")
    db = SessionLocal()

    try:
        data = load_all_data(db)
        print(f"  Matches: {len(data['matches'])}")
        print(f"  Innings stats: {len(data['innings_stats'])}")

        print("\nLoading squad composition data...")
        squad_data = load_squad_data(db)
        print(f"  Batting records: {len(squad_data['batting'])}")
        print(f"  Bowling records: {len(squad_data['bowling'])}")
        print(f"  Players: {len(squad_data['players'])}")

        print("\nBuilding V3 feature matrix...")
        X, y, match_ids, seasons, feature_names = build_feature_matrix_v3(data, squad_data)
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

        print("\nTraining XGBoost V3...")
        model = XGBClassifier(
            n_estimators=600,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.65,
            min_child_weight=5,
            reg_alpha=0.15,
            reg_lambda=1.5,
            eval_metric="logloss",
            random_state=42,
            early_stopping_rounds=60,
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

        print(f"\n{'='*40}")
        print(f"  TEST RESULTS (2025-2026)")
        print(f"{'='*40}")
        print(f"  Accuracy: {accuracy:.3f}")
        print(f"  Log Loss: {logloss:.3f}")
        print(f"  AUC-ROC:  {auc:.3f}")

        # Validation results
        y_val_pred = model.predict(X_val)
        y_val_proba = model.predict_proba(X_val)
        val_acc = accuracy_score(y_val, y_val_pred)
        val_auc = roc_auc_score(y_val, y_val_proba[:, 1])
        print(f"\n{'='*40}")
        print(f"  VALIDATION RESULTS (2024)")
        print(f"{'='*40}")
        print(f"  Accuracy: {val_acc:.3f}")
        print(f"  AUC-ROC:  {val_auc:.3f}")

        # Feature importance
        importances = model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]
        print(f"\n{'='*40}")
        print(f"  TOP 20 FEATURES")
        print(f"{'='*40}")
        for i in sorted_idx[:20]:
            marker = " *" if "squad" in feature_names[i] else ""
            print(f"  {feature_names[i]:35} {importances[i]:.4f}{marker}")

        # Count squad feature contribution
        squad_importance = sum(
            importances[i] for i, n in enumerate(feature_names) if "squad" in n
        )
        print(f"\n  Squad features total importance: {squad_importance:.4f} "
              f"({squad_importance / importances.sum() * 100:.1f}%)")

        # Save model
        import joblib
        from app.config import MODEL_DIR
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        model_path = MODEL_DIR / "win_probability_v3.joblib"
        joblib.dump({
            "model": model,
            "feature_names": feature_names,
            "version": "v3",
            "metrics": {
                "test_accuracy": accuracy,
                "test_auc": auc,
                "test_logloss": logloss,
                "val_accuracy": val_acc,
                "val_auc": val_auc,
            },
        }, model_path)
        print(f"\nModel saved to {model_path}")

        # Compare with V2 if available
        v2_path = MODEL_DIR / "win_probability_v2.joblib"
        if v2_path.exists():
            v2_data = joblib.load(v2_path)
            if isinstance(v2_data, dict) and "model" in v2_data:
                v2_model = v2_data["model"]
                v2_names = v2_data.get("feature_names", [])
                # Predict with V2 on test set using only V2 features
                n_v2 = len(v2_names)
                if n_v2 > 0 and X_test.shape[1] >= n_v2:
                    X_test_v2 = X_test[:, :n_v2]
                    v2_pred = v2_model.predict(X_test_v2)
                    v2_proba = v2_model.predict_proba(X_test_v2)
                    v2_acc = accuracy_score(y_test, v2_pred)
                    v2_auc = roc_auc_score(y_test, v2_proba[:, 1])
                    print(f"\n{'='*40}")
                    print(f"  V2 vs V3 COMPARISON (test set)")
                    print(f"{'='*40}")
                    print(f"  V2 Accuracy: {v2_acc:.3f}  |  V3 Accuracy: {accuracy:.3f}  |  Delta: {accuracy - v2_acc:+.3f}")
                    print(f"  V2 AUC-ROC:  {v2_auc:.3f}  |  V3 AUC-ROC:  {auc:.3f}  |  Delta: {auc - v2_auc:+.3f}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
