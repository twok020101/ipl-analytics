"""Player form index using Exponentially Weighted Moving Average."""

from sqlalchemy import desc, cast, Integer
from sqlalchemy.orm import Session

from app.models.models import Delivery, Match, Player


def calculate_form_index(db: Session, player_id: int, role: str = "batter") -> dict:
    """
    Calculate a form index (0-100) for a player based on their last 10 innings
    using EWMA with lambda=0.85.

    role: 'batter' or 'bowler'
    """
    player = db.query(Player).get(player_id)
    if not player:
        return {"player_id": player_id, "form_index": 0, "innings": [], "trend": "unknown"}

    if role == "batter":
        return _batter_form(db, player_id, player.name)
    else:
        return _bowler_form(db, player_id, player.name)


def _batter_form(db: Session, player_id: int, player_name: str) -> dict:
    """Compute batter form from last 10 innings."""
    # Get last 10 match innings for this batter
    from sqlalchemy import func

    innings_data = (
        db.query(
            Delivery.match_id,
            Match.date,
            func.sum(Delivery.runs_batter).label("runs"),
            func.sum(cast(Delivery.valid_ball, Integer)).label("balls"),
        )
        .join(Match, Match.id == Delivery.match_id)
        .filter(Delivery.batter_id == player_id)
        .group_by(Delivery.match_id, Match.date)
        .order_by(desc(Match.date))
        .limit(10)
        .all()
    )

    if not innings_data:
        return {
            "player_id": player_id,
            "player_name": player_name,
            "role": "batter",
            "form_index": 0.0,
            "innings": [],
            "trend": "unknown",
        }

    # Reverse to chronological order for EWMA
    innings_data = list(reversed(innings_data))

    scores = []
    for row in innings_data:
        runs = row.runs or 0
        balls = row.balls or 1
        sr = runs / balls * 100 if balls > 0 else 0
        # Composite score: weighted runs + SR bonus
        composite = min(runs * 1.0 + sr * 0.2, 100)
        scores.append(
            {
                "match_id": row.match_id,
                "date": str(row.date) if row.date else None,
                "runs": int(runs),
                "balls": int(balls),
                "strike_rate": round(sr, 1),
                "composite": round(composite, 1),
            }
        )

    # EWMA calculation
    lam = 0.85
    ewma = scores[0]["composite"]
    for s in scores[1:]:
        ewma = lam * s["composite"] + (1 - lam) * ewma

    form_index = round(min(max(ewma, 0), 100), 1)

    # Trend: compare last 3 vs previous
    if len(scores) >= 6:
        recent_avg = sum(s["composite"] for s in scores[-3:]) / 3
        older_avg = sum(s["composite"] for s in scores[-6:-3]) / 3
        if recent_avg > older_avg * 1.1:
            trend = "improving"
        elif recent_avg < older_avg * 0.9:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {
        "player_id": player_id,
        "player_name": player_name,
        "role": "batter",
        "form_index": form_index,
        "trend": trend,
        "innings": scores,
    }


def _bowler_form(db: Session, player_id: int, player_name: str) -> dict:
    """Compute bowler form from last 10 innings."""
    from sqlalchemy import func

    innings_data = (
        db.query(
            Delivery.match_id,
            Match.date,
            func.sum(Delivery.runs_total).label("runs_conceded"),
            func.sum(cast(Delivery.valid_ball, Integer)).label("balls"),
            func.count(Delivery.wicket_kind).label("wickets_raw"),
        )
        .join(Match, Match.id == Delivery.match_id)
        .filter(
            Delivery.bowler_id == player_id,
            Delivery.wicket_kind.notin_(["run out", "retired hurt", "retired out", "obstructing the field"]),
        )
        .group_by(Delivery.match_id, Match.date)
        .order_by(desc(Match.date))
        .limit(10)
        .all()
    )

    # Also need to count all deliveries (including those without wickets)
    all_innings = (
        db.query(
            Delivery.match_id,
            Match.date,
            func.sum(Delivery.runs_total).label("runs_conceded"),
            func.sum(cast(Delivery.valid_ball, Integer)).label("balls"),
        )
        .join(Match, Match.id == Delivery.match_id)
        .filter(Delivery.bowler_id == player_id)
        .group_by(Delivery.match_id, Match.date)
        .order_by(desc(Match.date))
        .limit(10)
        .all()
    )

    if not all_innings:
        return {
            "player_id": player_id,
            "player_name": player_name,
            "role": "bowler",
            "form_index": 0.0,
            "innings": [],
            "trend": "unknown",
        }

    # Count wickets separately per match
    from sqlalchemy import and_

    wicket_counts = {}
    for row in innings_data:
        # wickets_raw counts non-null wicket_kind entries already filtered
        wicket_counts[row.match_id] = row.wickets_raw or 0

    all_innings = list(reversed(all_innings))
    scores = []
    for row in all_innings:
        runs = row.runs_conceded or 0
        balls = row.balls or 1
        economy = runs / (balls / 6) if balls > 0 else 12
        wickets = wicket_counts.get(row.match_id, 0)

        # Composite: reward wickets, penalize high economy
        # Scale: 3 wickets + economy of 6 = ~80
        composite = min(wickets * 20 + max(0, (12 - economy) * 5), 100)
        composite = max(composite, 0)

        scores.append(
            {
                "match_id": row.match_id,
                "date": str(row.date) if row.date else None,
                "runs_conceded": int(runs),
                "balls": int(balls),
                "wickets": int(wickets),
                "economy": round(economy, 2),
                "composite": round(composite, 1),
            }
        )

    lam = 0.85
    ewma = scores[0]["composite"]
    for s in scores[1:]:
        ewma = lam * s["composite"] + (1 - lam) * ewma

    form_index = round(min(max(ewma, 0), 100), 1)

    if len(scores) >= 6:
        recent_avg = sum(s["composite"] for s in scores[-3:]) / 3
        older_avg = sum(s["composite"] for s in scores[-6:-3]) / 3
        if recent_avg > older_avg * 1.1:
            trend = "improving"
        elif recent_avg < older_avg * 0.9:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {
        "player_id": player_id,
        "player_name": player_name,
        "role": "bowler",
        "form_index": form_index,
        "trend": trend,
        "innings": scores,
    }
