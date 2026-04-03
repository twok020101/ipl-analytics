"""
Train the live in-match win probability model (1st + 2nd innings).

Builds over-by-over snapshots from ball-by-ball delivery data, extracts
features matching live_tracker.predict_live_win_probability(), and trains
two XGBoost classifiers:
  - 1st innings: predicts batting-first team's win probability
  - 2nd innings: predicts chasing team's win probability

Features (1st innings — 9):
  runs, wickets, over, run_rate, wickets_remaining, overs_remaining,
  projected_score, venue_avg, above_par

Features (2nd innings — 8):
  runs, wickets, over, target, remaining_runs, required_rate,
  current_rate, wickets_remaining

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    .venv/bin/python -m app.ml.train_live
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.database import SessionLocal
from app.config import MODEL_DIR
from app.services.cricapi_utils import resolve_batting_order


# ---------------------------------------------------------------------------
# Feature definitions — must match live_tracker.predict_live_win_probability()
# ---------------------------------------------------------------------------

FEATURES_1ST = [
    "runs", "wickets", "over", "run_rate", "wickets_remaining",
    "overs_remaining", "projected", "venue_avg", "above_par",
]

FEATURES_2ND = [
    "runs", "wickets", "over", "target", "remaining_runs",
    "required_rate", "current_rate", "wickets_remaining",
]


def load_over_snapshots(db_session) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build over-by-over snapshots from deliveries for both innings.

    Returns (inn1_df, inn2_df) with features and labels ready for training.
    """
    engine = db_session.get_bind()

    print("  Loading deliveries...")
    df = pd.read_sql_query("""
        SELECT d.match_id, d.innings, d.over_num,
               d.team_runs, d.team_wickets,
               m.winner_id, m.team1_id, m.team2_id,
               m.toss_winner_id, m.toss_decision, m.venue_id
        FROM deliveries d
        JOIN matches m ON d.match_id = m.id
        WHERE m.winner_id IS NOT NULL AND d.valid_ball = true
        ORDER BY d.match_id, d.innings, d.over_num, d.ball_num
    """, engine)
    print(f"  Valid deliveries: {len(df):,}")

    # Venue average scores for 1st innings context
    venue_avg = pd.read_sql_query(
        "SELECT venue_id, avg_first_innings_score FROM venue_stats", engine
    )
    venue_map = dict(zip(venue_avg.venue_id, venue_avg.avg_first_innings_score))

    # Aggregate to over-level snapshots (end-of-over state)
    over_data = df.groupby(["match_id", "innings", "over_num"]).agg(
        runs=("team_runs", "max"),
        wickets=("team_wickets", "max"),
        winner_id=("winner_id", "first"),
        team1_id=("team1_id", "first"),
        team2_id=("team2_id", "first"),
        toss_winner_id=("toss_winner_id", "first"),
        toss_decision=("toss_decision", "first"),
        venue_id=("venue_id", "first"),
    ).reset_index()
    print(f"  Over snapshots: {len(over_data):,}")

    # Determine batting-first team per match
    def _bat_first(row):
        bf, _ = resolve_batting_order(
            row["toss_winner_id"], row["toss_decision"],
            row["team1_id"], row["team2_id"],
        )
        return bf

    over_data["bat_first"] = over_data.apply(_bat_first, axis=1)

    # First innings totals (needed for 2nd innings target)
    inn1_totals = (
        over_data[over_data["innings"] == 1]
        .groupby("match_id")["runs"]
        .max()
        .to_dict()
    )

    # --- 1st Innings features ---
    inn1 = over_data[over_data["innings"] == 1].copy()
    inn1["over"] = inn1["over_num"] + 1
    inn1["run_rate"] = inn1["runs"] / inn1["over"].clip(lower=0.1)
    inn1["wickets_remaining"] = 10 - inn1["wickets"]
    inn1["overs_remaining"] = 20 - inn1["over"]
    inn1["projected"] = inn1["runs"] / (inn1["over"] / 20.0).clip(lower=0.05)
    inn1["venue_avg"] = inn1["venue_id"].map(venue_map).fillna(165.0)
    inn1["above_par"] = (inn1["projected"] - inn1["venue_avg"]) / inn1["venue_avg"].clip(lower=1)
    inn1["label"] = (inn1["winner_id"] == inn1["bat_first"]).astype(int)

    # --- 2nd Innings features ---
    inn2 = over_data[over_data["innings"] == 2].copy()
    inn2["target"] = inn2["match_id"].map(inn1_totals).fillna(165) + 1
    inn2["over"] = inn2["over_num"] + 1
    inn2["remaining_runs"] = inn2["target"] - inn2["runs"]
    inn2["remaining_overs"] = (20 - inn2["over"]).clip(lower=0.1)
    inn2["required_rate"] = inn2["remaining_runs"] / inn2["remaining_overs"]
    inn2["current_rate"] = inn2["runs"] / inn2["over"].clip(lower=0.1)
    inn2["wickets_remaining"] = 10 - inn2["wickets"]

    # Chasing team wins label
    bat_first_map = (
        over_data[over_data["innings"] == 1]
        .drop_duplicates("match_id")
        .set_index("match_id")["bat_first"]
    )
    inn2["bat_first"] = inn2["match_id"].map(bat_first_map)
    inn2["label"] = (inn2["winner_id"] != inn2["bat_first"]).astype(int)

    return inn1, inn2


def train_model(X_train, y_train, X_val, y_val, label: str):
    """Train an XGBoost classifier with hyperparameter search.

    Tries multiple configurations and returns the best by AUC on validation set.
    """
    from xgboost import XGBClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score

    configs = [
        {"learning_rate": 0.05, "max_depth": 6, "n_estimators": 300},
        {"learning_rate": 0.03, "max_depth": 5, "n_estimators": 500},
        {"learning_rate": 0.02, "max_depth": 4, "n_estimators": 800},
        {"learning_rate": 0.01, "max_depth": 4, "n_estimators": 1200},
    ]

    best_model = None
    best_auc = 0.0
    best_cfg = None

    for cfg in configs:
        model = XGBClassifier(
            **cfg,
            subsample=0.85,
            colsample_bytree=0.7,
            min_child_weight=3,
            eval_metric="logloss",
            random_state=42,
            early_stopping_rounds=50,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        proba = model.predict_proba(X_val)
        acc = accuracy_score(y_val, model.predict(X_val))
        auc = roc_auc_score(y_val, proba[:, 1])
        lr = cfg["learning_rate"]
        depth = cfg["max_depth"]
        print(f"    lr={lr}, depth={depth}: iter={model.best_iteration}, Acc={acc:.3f}, AUC={auc:.3f}")

        if auc > best_auc:
            best_auc = auc
            best_model = model
            best_cfg = cfg

    print(f"  Best {label}: AUC={best_auc:.3f} (lr={best_cfg['learning_rate']}, depth={best_cfg['max_depth']})")
    return best_model, best_auc


def main():
    from xgboost import XGBClassifier
    from sklearn.metrics import accuracy_score, roc_auc_score
    import joblib

    print("=" * 60)
    print("Live In-Match Win Probability — Training")
    print("=" * 60)

    db = SessionLocal()
    try:
        inn1, inn2 = load_over_snapshots(db)
    finally:
        db.close()

    # Prepare feature matrices
    X1 = np.nan_to_num(inn1[FEATURES_1ST].values.astype(np.float32), nan=0, posinf=20, neginf=-20)
    y1 = inn1["label"].values
    X2 = np.nan_to_num(inn2[FEATURES_2ND].values.astype(np.float32), nan=0, posinf=20, neginf=-20)
    y2 = inn2["label"].values

    print(f"\n  1st innings: {len(X1):,} samples, positive rate: {y1.mean():.3f}")
    print(f"  2nd innings: {len(X2):,} samples, positive rate: {y2.mean():.3f}")

    # Time-ordered split: train 80%, last 15% of train as val, final 20% as test
    def _split(X, y):
        n = len(X)
        test_start = int(n * 0.8)
        X_all_tr, X_te = X[:test_start], X[test_start:]
        y_all_tr, y_te = y[:test_start], y[test_start:]
        val_start = int(len(X_all_tr) * 0.85)
        X_tr, X_v = X_all_tr[:val_start], X_all_tr[val_start:]
        y_tr, y_v = y_all_tr[:val_start], y_all_tr[val_start:]
        return X_tr, y_tr, X_v, y_v, X_te, y_te

    # --- 1st Innings ---
    print(f"\n{'='*60}")
    print("  TRAINING 1st INNINGS MODEL")
    print(f"{'='*60}")
    X1_tr, y1_tr, X1_v, y1_v, X1_te, y1_te = _split(X1, y1)
    print(f"  Train: {len(X1_tr):,}, Val: {len(X1_v):,}, Test: {len(X1_te):,}")
    best_m1, best_auc1 = train_model(X1_tr, y1_tr, X1_v, y1_v, "1st innings")

    # Test set evaluation
    proba1 = best_m1.predict_proba(X1_te)
    acc1 = accuracy_score(y1_te, best_m1.predict(X1_te))
    auc1 = roc_auc_score(y1_te, proba1[:, 1])
    print(f"  TEST: Acc={acc1:.3f}, AUC={auc1:.3f}")

    # --- 2nd Innings ---
    print(f"\n{'='*60}")
    print("  TRAINING 2nd INNINGS MODEL")
    print(f"{'='*60}")
    X2_tr, y2_tr, X2_v, y2_v, X2_te, y2_te = _split(X2, y2)
    print(f"  Train: {len(X2_tr):,}, Val: {len(X2_v):,}, Test: {len(X2_te):,}")
    best_m2, best_auc2 = train_model(X2_tr, y2_tr, X2_v, y2_v, "2nd innings")

    # Test set evaluation
    proba2 = best_m2.predict_proba(X2_te)
    acc2 = accuracy_score(y2_te, best_m2.predict(X2_te))
    auc2 = roc_auc_score(y2_te, proba2[:, 1])
    print(f"  TEST: Acc={acc2:.3f}, AUC={auc2:.3f}")

    # --- Compare with existing ---
    model_path = MODEL_DIR / "live_win_probability.joblib"
    if model_path.exists():
        old = joblib.load(model_path)
        old_m1, old_m2 = old["model_1st_innings"], old["model_2nd_innings"]
        old_auc1 = roc_auc_score(y1_te, old_m1.predict_proba(X1_te)[:, 1])
        old_auc2 = roc_auc_score(y2_te, old_m2.predict_proba(X2_te)[:, 1])

        print(f"\n{'='*60}")
        print("  OLD vs NEW COMPARISON (test set)")
        print(f"{'='*60}")
        print(f"  1st Inn — Old AUC: {old_auc1:.3f} → New AUC: {auc1:.3f} ({auc1-old_auc1:+.3f})")
        print(f"  2nd Inn — Old AUC: {old_auc2:.3f} → New AUC: {auc2:.3f} ({auc2-old_auc2:+.3f})")

        improved = auc1 > old_auc1 or auc2 > old_auc2
    else:
        improved = True

    # --- Save ---
    if improved:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model_1st_innings": best_m1,
            "features_1st_innings": FEATURES_1ST,
            "model_2nd_innings": best_m2,
            "features_2nd_innings": FEATURES_2ND,
        }, model_path)
        print(f"\n  Model saved to {model_path}")
    else:
        print("\n  No improvement — existing model kept.")

    print("\nDone.")


if __name__ == "__main__":
    main()
