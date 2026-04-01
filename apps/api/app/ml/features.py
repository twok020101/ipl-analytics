"""Feature engineering for ML models."""

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from typing import Optional

from app.models.models import Match, Delivery, Team, VenueStats, PlayerSeasonBatting, PlayerSeasonBowling


def build_match_features(db: Session, match: Match) -> Optional[np.ndarray]:
    """
    Build a feature vector for win prediction from a Match object.
    Returns a numpy array of features or None if insufficient data.

    Features:
    0: team1_win_pct (overall)
    1: team2_win_pct (overall)
    2: team1_recent_form (last 5 win rate)
    3: team2_recent_form (last 5 win rate)
    4: h2h_team1_win_pct
    5: venue_bat_first_win_pct
    6: venue_avg_first_innings_score
    7: toss_winner_is_team1 (1/0)
    8: toss_chose_bat (1/0)
    9: team1_avg_score
    10: team2_avg_score
    """
    if not match.team1_id or not match.team2_id:
        return None

    features = np.zeros(11)

    # Team overall win percentages (from matches before this one)
    for idx, tid in enumerate([match.team1_id, match.team2_id]):
        prev_matches = (
            db.query(Match)
            .filter(
                or_(Match.team1_id == tid, Match.team2_id == tid),
                Match.date < match.date if match.date else Match.id < match.id,
            )
            .all()
        )
        total = len(prev_matches)
        wins = sum(1 for m in prev_matches if m.winner_id == tid)
        features[idx] = wins / total if total > 0 else 0.5

    # Recent form (last 5)
    for idx, tid in enumerate([match.team1_id, match.team2_id]):
        recent = (
            db.query(Match)
            .filter(
                or_(Match.team1_id == tid, Match.team2_id == tid),
                Match.date < match.date if match.date else Match.id < match.id,
            )
            .order_by(Match.date.desc())
            .limit(5)
            .all()
        )
        if recent:
            features[2 + idx] = sum(1 for m in recent if m.winner_id == tid) / len(recent)
        else:
            features[2 + idx] = 0.5

    # Head to head
    h2h = (
        db.query(Match)
        .filter(
            or_(
                and_(Match.team1_id == match.team1_id, Match.team2_id == match.team2_id),
                and_(Match.team1_id == match.team2_id, Match.team2_id == match.team1_id),
            ),
            Match.date < match.date if match.date else Match.id < match.id,
        )
        .all()
    )
    if h2h:
        features[4] = sum(1 for m in h2h if m.winner_id == match.team1_id) / len(h2h)
    else:
        features[4] = 0.5

    # Venue stats
    if match.venue_id:
        vs = db.query(VenueStats).filter(VenueStats.venue_id == match.venue_id).first()
        if vs:
            features[5] = vs.bat_first_win_pct / 100.0
            features[6] = vs.avg_first_innings_score / 200.0  # normalized
        else:
            features[5] = 0.5
            features[6] = 0.75
    else:
        features[5] = 0.5
        features[6] = 0.75

    # Toss
    features[7] = 1.0 if match.toss_winner_id == match.team1_id else 0.0
    features[8] = 1.0 if match.toss_decision == "bat" else 0.0

    # Average scores
    for idx, tid in enumerate([match.team1_id, match.team2_id]):
        scores = (
            db.query(Match.first_innings_score)
            .filter(
                Match.team1_id == tid,
                Match.first_innings_score.isnot(None),
                Match.date < match.date if match.date else Match.id < match.id,
            )
            .order_by(Match.date.desc())
            .limit(10)
            .all()
        )
        if scores:
            features[9 + idx] = np.mean([s[0] for s in scores]) / 200.0
        else:
            features[9 + idx] = 0.75

    return features


def build_match_features_from_params(
    db: Session,
    team1_id: int,
    team2_id: int,
    venue_id: Optional[int],
    toss_winner_id: Optional[int],
    toss_decision: Optional[str],
) -> np.ndarray:
    """Build feature vector from parameters (for prediction)."""
    features = np.zeros(11)

    for idx, tid in enumerate([team1_id, team2_id]):
        all_matches = (
            db.query(Match)
            .filter(or_(Match.team1_id == tid, Match.team2_id == tid))
            .all()
        )
        total = len(all_matches)
        wins = sum(1 for m in all_matches if m.winner_id == tid)
        features[idx] = wins / total if total > 0 else 0.5

        recent = sorted(all_matches, key=lambda m: m.date or m.id, reverse=True)[:5]
        features[2 + idx] = sum(1 for m in recent if m.winner_id == tid) / len(recent) if recent else 0.5

    # H2H
    h2h = (
        db.query(Match)
        .filter(
            or_(
                and_(Match.team1_id == team1_id, Match.team2_id == team2_id),
                and_(Match.team1_id == team2_id, Match.team2_id == team1_id),
            )
        )
        .all()
    )
    features[4] = sum(1 for m in h2h if m.winner_id == team1_id) / len(h2h) if h2h else 0.5

    if venue_id:
        vs = db.query(VenueStats).filter(VenueStats.venue_id == venue_id).first()
        if vs:
            features[5] = vs.bat_first_win_pct / 100.0
            features[6] = vs.avg_first_innings_score / 200.0
        else:
            features[5] = 0.5
            features[6] = 0.75
    else:
        features[5] = 0.5
        features[6] = 0.75

    features[7] = 1.0 if toss_winner_id == team1_id else 0.0
    features[8] = 1.0 if toss_decision == "bat" else 0.0

    for idx, tid in enumerate([team1_id, team2_id]):
        scores = (
            db.query(Match.first_innings_score)
            .filter(Match.team1_id == tid, Match.first_innings_score.isnot(None))
            .order_by(Match.date.desc())
            .limit(10)
            .all()
        )
        features[9 + idx] = np.mean([s[0] for s in scores]) / 200.0 if scores else 0.75

    return features


def build_player_features(
    db: Session, player_id: int, venue_id: Optional[int] = None, opposition_id: Optional[int] = None
) -> dict:
    """Build player feature set for projection."""
    batting = (
        db.query(PlayerSeasonBatting)
        .filter(PlayerSeasonBatting.player_id == player_id)
        .order_by(PlayerSeasonBatting.season.desc())
        .limit(3)
        .all()
    )

    bowling = (
        db.query(PlayerSeasonBowling)
        .filter(PlayerSeasonBowling.player_id == player_id)
        .order_by(PlayerSeasonBowling.season.desc())
        .limit(3)
        .all()
    )

    result = {
        "batting": {
            "avg_runs": np.mean([b.runs / max(b.innings, 1) for b in batting]) if batting else 0,
            "avg_sr": np.mean([b.strike_rate for b in batting]) if batting else 0,
            "avg_average": np.mean([b.average for b in batting]) if batting else 0,
            "total_matches": sum(b.matches for b in batting) if batting else 0,
        },
        "bowling": {
            "avg_wickets": np.mean([b.wickets / max(b.matches, 1) for b in bowling]) if bowling else 0,
            "avg_economy": np.mean([b.economy for b in bowling]) if bowling else 0,
            "avg_average": np.mean([b.average for b in bowling]) if bowling else 0,
            "total_matches": sum(b.matches for b in bowling) if bowling else 0,
        },
    }

    # Venue adjustment
    if venue_id:
        vs = db.query(VenueStats).filter(VenueStats.venue_id == venue_id).first()
        if vs:
            result["venue_factor"] = {
                "avg_first_innings": vs.avg_first_innings_score,
                "bat_first_win_pct": vs.bat_first_win_pct,
            }

    return result
