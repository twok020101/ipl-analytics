"""
Match result sync — updates DB and fixture cache from live CricAPI data.

Call after every match completes or periodically to keep data fresh.
"""

import json
import logging
from pathlib import Path
from datetime import date
import re

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.models import Match, Team
from app.config import settings, DATA_DIR
from app.services.cricapi_utils import parse_score, extract_team_short


async def sync_results(db: Session) -> dict:
    """Fetch latest results from cricScore and update DB + fixtures cache.

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
    updated_cache = []

    # Pre-load all teams once to avoid per-match queries
    all_teams = {t.short_name: t for t in db.query(Team).all()}

    for m in ipl_matches:
        if m.get("ms") != "result":
            continue

        t1_short = extract_team_short(m.get("t1", ""))
        t2_short = extract_team_short(m.get("t2", ""))
        status = m.get("status", "")
        t1_score = parse_score(m.get("t1s", ""))
        t2_score = parse_score(m.get("t2s", ""))

        if not t1_short or not t2_short:
            continue

        # Find match in DB
        team1 = all_teams.get(t1_short)
        team2 = all_teams.get(t2_short)
        if not team1 or not team2:
            continue

        db_match = db.query(Match).filter(
            Match.season == "2026",
            or_(
                (Match.team1_id == team1.id) & (Match.team2_id == team2.id),
                (Match.team1_id == team2.id) & (Match.team2_id == team1.id),
            ),
        ).first()

        if not db_match:
            continue

        # Skip if already has a winner
        if db_match.winner_id:
            continue

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
        # The team with completed innings (10 wkts or 20 overs) batted first,
        # OR if both completed, the one with more overs batted first
        if t2_score.get("wickets", 0) >= 10 or t2_score.get("overs", 0) >= 20:
            # t2 (LSG) batted first
            first_score = t2_score.get("runs")
            first_overs = t2_score.get("overs")
            second_score = t1_score.get("runs")
            second_overs = t1_score.get("overs")
            # Toss: the team that batted second chose to field
            toss_winner = team1  # DC batted second = DC won toss and fielded
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
        if not db_match.toss_winner_id:
            db_match.toss_winner_id = toss_winner.id
            db_match.toss_decision = toss_decision

        updated_db.append(f"{t1_short} vs {t2_short}: {status}")

    db.commit()

    # Update fixtures cache
    cache_path = DATA_DIR / "ipl2026.json"
    if cache_path.exists():
        with open(cache_path) as f:
            cache = json.load(f)

        for m in ipl_matches:
            for fix in cache.get("fixtures", []):
                if fix["id"] == m["id"]:
                    old_status = fix.get("status", "")
                    fix["status"] = m.get("status", "")
                    fix["matchStarted"] = m.get("ms") in ("live", "result")
                    fix["matchEnded"] = m.get("ms") == "result"
                    if old_status != fix["status"]:
                        updated_cache.append(f"{fix.get('team1')} vs {fix.get('team2')}: {fix['status']}")
                    break

        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)

    return {
        "db_updated": updated_db,
        "cache_updated": updated_cache,
        "total_ipl_matches": len(ipl_matches),
        "results_found": len([m for m in ipl_matches if m.get("ms") == "result"]),
    }
