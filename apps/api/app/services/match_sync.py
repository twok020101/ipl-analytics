"""
Match result sync — updates DB from live CricAPI data.

Call after every match completes or periodically to keep data fresh.
"""

import logging
import re
from datetime import date, timedelta

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.models import Match, Team
from app.config import settings
from app.services.cricapi_utils import parse_score, extract_team_short


async def sync_results(db: Session) -> dict:
    """Fetch latest results from cricScore and update DB.

    Returns summary of what was updated.
    """
    api_key = settings.CRICAPI_KEY
    if not api_key:
        return {"error": "No CRICAPI_KEY configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.cricapi.com/v1/cricScore",
                params={"apikey": api_key},
            )
            data = resp.json()
    except Exception as e:
        return {"error": f"API fetch failed: {e}"}

    if data.get("status") != "success":
        return {"error": data.get("reason", "API error")}

    ipl_matches = [m for m in data.get("data", [])
                   if "indian premier" in m.get("series", "").lower()]

    updated_db = []

    # Pre-load all teams once to avoid per-match queries
    all_teams = {t.short_name: t for t in db.query(Team).all()}

    for m in ipl_matches:
        if m.get("ms") != "result":
            continue

        cricapi_id = m.get("id")
        t1_short = extract_team_short(m.get("t1", ""))
        t2_short = extract_team_short(m.get("t2", ""))
        status = m.get("status", "")
        t1_score = parse_score(m.get("t1s", ""))
        t2_score = parse_score(m.get("t2s", ""))

        if not t1_short or not t2_short:
            continue

        team1 = all_teams.get(t1_short)
        team2 = all_teams.get(t2_short)
        if not team1 or not team2:
            continue

        # Find match in DB — prefer cricapi_id (unique), fall back to team pair + no winner
        db_match = None
        if cricapi_id:
            db_match = db.query(Match).filter(Match.cricapi_id == cricapi_id).first()

        if not db_match:
            # Fallback: match by team pair, but restrict to matches within
            # 2 days of today to avoid writing results onto future fixtures
            # between the same two teams.
            cutoff = date.today() + timedelta(days=2)
            db_match = db.query(Match).filter(
                Match.season == "2026",
                Match.winner_id.is_(None),
                Match.date <= cutoff,
                or_(
                    (Match.team1_id == team1.id) & (Match.team2_id == team2.id),
                    (Match.team1_id == team2.id) & (Match.team2_id == team1.id),
                ),
            ).order_by(Match.date.desc()).first()

        if not db_match:
            continue

        # Skip if already has a winner
        if db_match.winner_id:
            # Still update status fields
            db_match.match_ended = True
            db_match.match_started = True
            db_match.status_text = status
            continue

        # Backfill cricapi_id if missing
        if cricapi_id and not db_match.cricapi_id:
            db_match.cricapi_id = cricapi_id

        # Parse winner from status: "Delhi Capitals won by 6 wkts"
        margin_match = re.search(r"won by (\d+) (run|wkt)", status, re.IGNORECASE)
        margin = int(margin_match.group(1)) if margin_match else None
        win_type = None
        if margin_match:
            win_type = "wickets" if "wkt" in margin_match.group(2).lower() else "runs"

        # Determine winner
        winner = None
        for t in [team1, team2]:
            if t.name.lower() in status.lower() or t.short_name.lower() in status.lower():
                winner = t
                break

        if not winner:
            continue

        # Determine who batted first from scores
        if t2_score.get("wickets", 0) >= 10 or t2_score.get("overs", 0) >= 20:
            first_score = t2_score.get("runs")
            first_overs = t2_score.get("overs")
            second_score = t1_score.get("runs")
            second_overs = t1_score.get("overs")
            toss_winner = team1
            toss_decision = "field"
        else:
            first_score = t1_score.get("runs")
            first_overs = t1_score.get("overs")
            second_score = t2_score.get("runs")
            second_overs = t2_score.get("overs")
            toss_winner = team2
            toss_decision = "field"

        # Update DB
        db_match.winner_id = winner.id
        db_match.win_margin = margin
        db_match.win_type = win_type
        db_match.first_innings_score = first_score
        db_match.first_innings_overs = first_overs
        db_match.second_innings_score = second_score
        db_match.second_innings_overs = second_overs
        db_match.match_ended = True
        db_match.match_started = True
        db_match.status_text = status
        if not db_match.toss_winner_id:
            db_match.toss_winner_id = toss_winner.id
            db_match.toss_decision = toss_decision

        updated_db.append(f"{t1_short} vs {t2_short}: {status}")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logging.warning("Duplicate match skipped during result sync (unique constraint)")

    return {
        "db_updated": updated_db,
        "total_ipl_matches": len(ipl_matches),
        "results_found": len([m for m in ipl_matches if m.get("ms") == "result"]),
    }
