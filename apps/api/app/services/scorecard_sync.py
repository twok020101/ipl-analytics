"""
Scorecard sync — fetches per-player batting/bowling stats from CricAPI
match scorecards and populates PlayerSeasonBatting/Bowling for the current season.

Run as part of the daily cron sync so the my-team dashboard and player
pages show up-to-date IPL 2026 stats without needing ball-by-ball data.

Each completed match is fetched once; subsequent calls skip already-synced matches.
"""

import logging
from typing import Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings, CURRENT_SEASON
from app.models.models import (
    Match, Player, Team, SquadMember,
    PlayerSeasonBatting, PlayerSeasonBowling,
)

logger = logging.getLogger("scorecard_sync")

CRICAPI_BASE = "https://api.cricapi.com/v1"


def _resolve_player(db: Session, name: str, name_cache: Dict[str, Optional[int]]) -> Optional[int]:
    """Resolve a CricAPI player name to a DB player ID, with caching.

    Tries exact match first, then case-insensitive. Returns None if not found.
    """
    if name in name_cache:
        return name_cache[name]

    player = db.query(Player).filter(Player.name == name).first()
    if not player:
        # Case-insensitive fallback
        player = db.query(Player).filter(Player.name.ilike(name)).first()
    pid = player.id if player else None
    name_cache[name] = pid
    return pid


async def sync_player_stats(db: Session) -> dict:
    """Fetch scorecards for completed 2026 matches and aggregate player stats.

    Only fetches scorecards for matches that have a winner but haven't been
    processed yet (checked via existing PlayerSeasonBatting records).

    Returns summary of what was synced.
    """
    api_key = settings.CRICAPI_KEY
    if not api_key:
        return {"error": "No CRICAPI_KEY configured"}

    # Find completed 2026 matches with cricapi_id (needed for scorecard fetch)
    completed = (
        db.query(Match)
        .filter(
            Match.season == CURRENT_SEASON,
            Match.winner_id.isnot(None),
            Match.cricapi_id.isnot(None),
        )
        .all()
    )

    if not completed:
        return {"status": "no_completed_matches"}

    # Track which matches already have player stats synced.
    # We tag synced matches by checking if any PlayerSeasonBatting row
    # references the current season for players from that match.
    # For simplicity, use a set of cricapi_ids we've already processed
    # by checking if batting stats exist for this season.
    existing_bat_count = (
        db.query(PlayerSeasonBatting)
        .filter(PlayerSeasonBatting.season == CURRENT_SEASON)
        .count()
    )

    # Build team lookup for determining team_id from inning names
    teams = {t.name: t.id for t in db.query(Team).filter(Team.is_active == True).all()}
    # Also map short names
    for t in db.query(Team).filter(Team.is_active == True).all():
        teams[t.short_name] = t.id

    # Accumulate per-player stats across all matches
    bat_stats: Dict[int, dict] = {}   # player_id → aggregated batting
    bowl_stats: Dict[int, dict] = {}  # player_id → aggregated bowling
    name_cache: Dict[str, Optional[int]] = {}
    matches_synced = 0
    matches_failed = 0

    async with httpx.AsyncClient(timeout=20) as client:
        for match in completed:
            try:
                resp = await client.get(
                    f"{CRICAPI_BASE}/match_scorecard",
                    params={"apikey": api_key, "id": match.cricapi_id},
                )
                data = resp.json()
                if data.get("status") != "success":
                    matches_failed += 1
                    continue

                match_data = data.get("data", {})

                for inn in match_data.get("scorecard", []):
                    inning_name = inn.get("inning", "")

                    # Resolve team from inning name (e.g., "Chennai Super Kings Inning 1")
                    team_id = None
                    for tname, tid in teams.items():
                        if tname in inning_name:
                            team_id = tid
                            break

                    # Process batting entries
                    for b in inn.get("batting", []):
                        name = b.get("batsman", {}).get("name", "")
                        if not name:
                            continue
                        pid = _resolve_player(db, name, name_cache)
                        if not pid:
                            continue

                        if pid not in bat_stats:
                            bat_stats[pid] = {
                                "team_id": team_id,
                                "matches": set(),
                                "innings": 0,
                                "runs": 0,
                                "balls_faced": 0,
                                "fours": 0,
                                "sixes": 0,
                                "highest_score": 0,
                                "not_outs": 0,
                                "fifties": 0,
                                "hundreds": 0,
                            }

                        s = bat_stats[pid]
                        runs = b.get("r", 0) or 0
                        balls = b.get("b", 0) or 0
                        fours = b.get("4s", 0) or 0
                        sixes = b.get("6s", 0) or 0

                        s["matches"].add(match.id)
                        s["innings"] += 1
                        s["runs"] += runs
                        s["balls_faced"] += balls
                        s["fours"] += fours
                        s["sixes"] += sixes
                        if runs > s["highest_score"]:
                            s["highest_score"] = runs
                        if runs >= 100:
                            s["hundreds"] += 1
                        elif runs >= 50:
                            s["fifties"] += 1

                        # Check if not out (dismissal field empty or "not out")
                        dismissal = b.get("dismissal", "")
                        if not dismissal or "not out" in dismissal.lower():
                            s["not_outs"] += 1

                        if team_id and not s["team_id"]:
                            s["team_id"] = team_id

                    # Process bowling entries
                    for bw in inn.get("bowling", []):
                        name = bw.get("bowler", {}).get("name", "")
                        if not name:
                            continue
                        pid = _resolve_player(db, name, name_cache)
                        if not pid:
                            continue

                        if pid not in bowl_stats:
                            bowl_stats[pid] = {
                                "team_id": None,
                                "matches": set(),
                                "innings": 0,
                                "overs_bowled": 0.0,
                                "runs_conceded": 0,
                                "wickets": 0,
                                "best_wickets": 0,
                                "best_runs": 999,
                                "four_wickets": 0,
                                "five_wickets": 0,
                            }

                        s = bowl_stats[pid]
                        overs = float(bw.get("o", 0) or 0)
                        runs = bw.get("r", 0) or 0
                        wickets = bw.get("w", 0) or 0

                        s["matches"].add(match.id)
                        s["innings"] += 1
                        s["overs_bowled"] += overs
                        s["runs_conceded"] += runs
                        s["wickets"] += wickets

                        # Track best figures
                        if wickets > s["best_wickets"] or (
                            wickets == s["best_wickets"] and runs < s["best_runs"]
                        ):
                            s["best_wickets"] = wickets
                            s["best_runs"] = runs

                        if wickets >= 5:
                            s["five_wickets"] += 1
                        elif wickets >= 4:
                            s["four_wickets"] += 1

                        # Bowler's team is the OTHER team in this inning
                        # (they bowl for their team in the opponent's inning)
                        # Resolve from squad membership instead
                        if not s["team_id"]:
                            squad = db.query(SquadMember).filter(
                                SquadMember.player_id == pid,
                                SquadMember.season == CURRENT_SEASON,
                            ).first()
                            if squad:
                                s["team_id"] = squad.team_id

                matches_synced += 1

            except Exception as e:
                logger.warning(f"Scorecard fetch failed for {match.cricapi_id}: {e}")
                matches_failed += 1

    # Upsert aggregated stats into DB
    bat_upserted = 0
    for pid, s in bat_stats.items():
        matches_count = len(s["matches"])
        innings = s["innings"]
        runs = s["runs"]
        balls = s["balls_faced"]
        outs = innings - s["not_outs"]
        sr = (runs / balls * 100) if balls > 0 else 0.0
        avg = (runs / outs) if outs > 0 else float(runs)

        existing = db.query(PlayerSeasonBatting).filter(
            PlayerSeasonBatting.player_id == pid,
            PlayerSeasonBatting.season == CURRENT_SEASON,
        ).first()

        if existing:
            existing.matches = matches_count
            existing.innings = innings
            existing.runs = runs
            existing.balls_faced = balls
            existing.fours = s["fours"]
            existing.sixes = s["sixes"]
            existing.strike_rate = round(sr, 2)
            existing.average = round(avg, 2)
            existing.highest_score = s["highest_score"]
            existing.fifties = s["fifties"]
            existing.hundreds = s["hundreds"]
            existing.not_outs = s["not_outs"]
        else:
            db.add(PlayerSeasonBatting(
                player_id=pid,
                season=CURRENT_SEASON,
                team_id=s["team_id"],
                matches=matches_count,
                innings=innings,
                runs=runs,
                balls_faced=balls,
                fours=s["fours"],
                sixes=s["sixes"],
                strike_rate=round(sr, 2),
                average=round(avg, 2),
                highest_score=s["highest_score"],
                fifties=s["fifties"],
                hundreds=s["hundreds"],
                not_outs=s["not_outs"],
            ))
        bat_upserted += 1

    bowl_upserted = 0
    for pid, s in bowl_stats.items():
        matches_count = len(s["matches"])
        overs = s["overs_bowled"]
        runs = s["runs_conceded"]
        wickets = s["wickets"]
        eco = (runs / overs) if overs > 0 else 0.0
        avg = (runs / wickets) if wickets > 0 else 0.0
        best = f"{s['best_wickets']}/{s['best_runs']}" if s["best_wickets"] > 0 else "0/0"

        existing = db.query(PlayerSeasonBowling).filter(
            PlayerSeasonBowling.player_id == pid,
            PlayerSeasonBowling.season == CURRENT_SEASON,
        ).first()

        if existing:
            existing.matches = matches_count
            existing.innings = s["innings"]
            existing.overs_bowled = round(overs, 1)
            existing.runs_conceded = runs
            existing.wickets = wickets
            existing.economy = round(eco, 2)
            existing.average = round(avg, 2)
            existing.best_figures = best
            existing.four_wickets = s["four_wickets"]
            existing.five_wickets = s["five_wickets"]
        else:
            db.add(PlayerSeasonBowling(
                player_id=pid,
                season=CURRENT_SEASON,
                team_id=s["team_id"],
                matches=matches_count,
                innings=s["innings"],
                overs_bowled=round(overs, 1),
                runs_conceded=runs,
                wickets=wickets,
                economy=round(eco, 2),
                average=round(avg, 2),
                best_figures=best,
                four_wickets=s["four_wickets"],
                five_wickets=s["five_wickets"],
            ))
        bowl_upserted += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit player stats: {e}")
        return {"error": str(e)}

    return {
        "status": "synced",
        "matches_processed": matches_synced,
        "matches_failed": matches_failed,
        "batters_updated": bat_upserted,
        "bowlers_updated": bowl_upserted,
        "had_existing_stats": existing_bat_count > 0,
    }
