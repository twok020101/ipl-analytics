"""Win probability prediction model using XGBoost."""

import os
from pathlib import Path

import numpy as np
import joblib
from typing import List

from app.config import MODEL_DIR

MODEL_PATH = MODEL_DIR / "win_probability_model.joblib"

# Feature names for interpretability
FEATURE_NAMES = [
    "team1_win_pct",
    "team2_win_pct",
    "team1_recent_form",
    "team2_recent_form",
    "h2h_team1_win_pct",
    "venue_bat_first_win_pct",
    "venue_avg_score_norm",
    "toss_winner_is_team1",
    "toss_chose_bat",
    "team1_avg_score_norm",
    "team2_avg_score_norm",
]


class WinProbabilityModel:
    def __init__(self):
        self.model = None
        self._load()

    def _load(self):
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)

    def is_trained(self) -> bool:
        return self.model is not None

    def train(self, X: np.ndarray, y: np.ndarray):
        """Train the XGBoost model."""
        from xgboost import XGBClassifier

        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            eval_metric="logloss",
            random_state=42,
            use_label_encoder=False,
        )
        self.model.fit(X, y)
        self.save()

    def save(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)

    def predict(self, features: np.ndarray) -> dict:
        """
        Predict win probability.
        Returns dict with team1_prob, team2_prob, key_factors.
        """
        if not self.is_trained():
            # Fallback to simple heuristic if no model trained
            return self._heuristic_predict(features)

        features_2d = features.reshape(1, -1)
        proba = self.model.predict_proba(features_2d)[0]

        # Determine which class is which
        # Class 1 = team1 wins
        team1_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
        team2_prob = 1.0 - team1_prob

        # Key factors from feature importance
        key_factors = self._get_key_factors(features)

        return {
            "team1_prob": round(team1_prob * 100, 1),
            "team2_prob": round(team2_prob * 100, 1),
            "key_factors": key_factors,
        }

    def _heuristic_predict(self, features: np.ndarray) -> dict:
        """Simple heuristic when no trained model available."""
        t1_strength = (
            features[0] * 0.3  # overall win pct
            + features[2] * 0.25  # recent form
            + features[4] * 0.15  # h2h
            + features[7] * 0.1  # toss
            + features[9] * 0.2  # avg score
        )
        t2_strength = (
            features[1] * 0.3
            + features[3] * 0.25
            + (1 - features[4]) * 0.15
            + (1 - features[7]) * 0.1
            + features[10] * 0.2
        )

        total = t1_strength + t2_strength
        if total == 0:
            team1_prob = 50.0
        else:
            team1_prob = round(t1_strength / total * 100, 1)

        return {
            "team1_prob": team1_prob,
            "team2_prob": round(100 - team1_prob, 1),
            "key_factors": [
                {"factor": "Overall Win Rate", "impact": "high"},
                {"factor": "Recent Form", "impact": "high"},
                {"factor": "Head-to-Head Record", "impact": "medium"},
            ],
        }

    def _get_key_factors(self, features: np.ndarray) -> List[dict]:
        """Extract top contributing factors."""
        if not self.is_trained() or not hasattr(self.model, "feature_importances_"):
            return []

        importances = self.model.feature_importances_
        # Get top 5 factors
        indices = np.argsort(importances)[::-1][:5]

        factors = []
        for i in indices:
            if i < len(FEATURE_NAMES):
                impact = "high" if importances[i] > 0.15 else "medium" if importances[i] > 0.08 else "low"
                factors.append(
                    {
                        "factor": FEATURE_NAMES[i].replace("_", " ").title(),
                        "importance": round(float(importances[i]), 3),
                        "value": round(float(features[i]), 3),
                        "impact": impact,
                    }
                )

        return factors
