"""Prediction API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.models import Team, Venue, Player
from app.ml.features import build_match_features_from_params, build_player_features
from app.ml.win_probability import WinProbabilityModel
from typing import Optional

router = APIRouter(prefix="/predict", tags=["predictions"])


class MatchPredictionRequest(BaseModel):
    team1_id: int
    team2_id: int
    venue_id: Optional[int] = None
    toss_winner_id: Optional[int] = None
    toss_decision: Optional[str] = None  # "bat" or "field"


class PlayerProjectionRequest(BaseModel):
    player_id: int
    venue_id: Optional[int] = None
    opposition_id: Optional[int] = None


@router.post("/match")
def predict_match(req: MatchPredictionRequest, db: Session = Depends(get_db)):
    """Predict match win probability."""
    team1 = db.query(Team).get(req.team1_id)
    team2 = db.query(Team).get(req.team2_id)
    if not team1 or not team2:
        raise HTTPException(status_code=404, detail="Team not found")

    features = build_match_features_from_params(
        db,
        req.team1_id,
        req.team2_id,
        req.venue_id,
        req.toss_winner_id,
        req.toss_decision,
    )

    model = WinProbabilityModel()
    prediction = model.predict(features)

    venue = db.query(Venue).get(req.venue_id) if req.venue_id else None

    return {
        "team1": {"id": team1.id, "name": team1.name, "short_name": team1.short_name},
        "team2": {"id": team2.id, "name": team2.name, "short_name": team2.short_name},
        "venue": venue.name if venue else None,
        "prediction": prediction,
        "model_trained": model.is_trained(),
    }


@router.post("/player")
def predict_player(req: PlayerProjectionRequest, db: Session = Depends(get_db)):
    """Project player performance."""
    player = db.query(Player).get(req.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    features = build_player_features(db, req.player_id, req.venue_id, req.opposition_id)

    batting = features.get("batting", {})
    bowling = features.get("bowling", {})

    # Project performance based on historical averages + venue factor
    venue_mult = 1.0
    if "venue_factor" in features:
        venue_mult = features["venue_factor"]["avg_first_innings"] / 160.0

    projected_runs = round(batting.get("avg_runs", 0) * venue_mult, 1)
    projected_sr = round(batting.get("avg_sr", 0), 1)
    projected_wickets = round(bowling.get("avg_wickets", 0), 2)
    projected_economy = round(bowling.get("avg_economy", 0), 2)

    return {
        "player": {"id": player.id, "name": player.name},
        "projection": {
            "batting": {
                "projected_runs": projected_runs,
                "projected_sr": projected_sr,
                "confidence": "high" if batting.get("total_matches", 0) >= 30 else "medium",
            },
            "bowling": {
                "projected_wickets": projected_wickets,
                "projected_economy": projected_economy,
                "confidence": "high" if bowling.get("total_matches", 0) >= 20 else "medium",
            },
        },
        "features": features,
    }
