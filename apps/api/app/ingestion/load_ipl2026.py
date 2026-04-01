"""Ingest IPL 2026 data from CricAPI cache into the database.

Adds:
- New players with role/batting_style/bowling_style from squad data
- Enriches existing players with missing role/style info
- Adds new venues from fixture data
- Adds IPL 2026 fixtures as Match records (season='2026')
- Creates a team_squad mapping table for current squad membership

Run: python -m app.ingestion.load_ipl2026
"""

import json
import re
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, SessionLocal
from app.models.models import Team, Player, Venue, Match, VenueStats
from app.ingestion.team_mappings import TEAM_NAME_MAP, TEAM_SHORT_NAMES


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "ipl2026.json"


def _normalize_team(name: str) -> str:
    """Map CricAPI team names to our canonical names."""
    return TEAM_NAME_MAP.get(name, name)


def _find_or_create_team(db: Session, short_name: str, full_name: str) -> Team:
    """Find team by short_name or create."""
    team = db.query(Team).filter(Team.short_name == short_name).first()
    if team:
        return team
    # Try by name
    canonical = _normalize_team(full_name)
    team = db.query(Team).filter(Team.name == canonical).first()
    if team:
        if not team.short_name:
            team.short_name = short_name
        return team
    # Create new
    team = Team(name=canonical, short_name=short_name, is_active=True)
    db.add(team)
    db.flush()
    return team


def _find_or_create_venue(db: Session, venue_str: str) -> Venue:
    """Find venue by name or create. Handles slight name variations."""
    if not venue_str:
        return None

    # Try exact match first
    venue = db.query(Venue).filter(Venue.name == venue_str).first()
    if venue:
        return venue

    # Extract city from "Stadium Name, City" format
    parts = venue_str.rsplit(", ", 1)
    city = parts[-1] if len(parts) > 1 else None

    # Try fuzzy match by checking if existing venue name is contained
    all_venues = db.query(Venue).all()
    for v in all_venues:
        # Match by key words
        v_lower = v.name.lower()
        new_lower = venue_str.lower()
        if v_lower in new_lower or new_lower in v_lower:
            return v
        # Match by stadium name stem (e.g. "Chinnaswamy")
        v_words = set(re.findall(r'\b\w{5,}\b', v_lower))
        new_words = set(re.findall(r'\b\w{5,}\b', new_lower))
        if v_words & new_words and len(v_words & new_words) >= 1:
            return v

    # Create new venue
    venue = Venue(name=venue_str, city=city)
    db.add(venue)
    db.flush()
    return venue


def _find_or_create_player(db: Session, player_data: dict) -> Player:
    """Find player by name or create with CricAPI metadata."""
    name = player_data["name"]
    player = db.query(Player).filter(Player.name == name).first()

    role = player_data.get("role")
    batting_style = player_data.get("battingStyle")
    bowling_style = player_data.get("bowlingStyle")

    if player:
        # Enrich existing player with missing info
        updated = False
        if not player.role and role:
            player.role = role
            updated = True
        if not player.batting_style and batting_style:
            player.batting_style = batting_style
            updated = True
        if not player.bowling_style and bowling_style:
            player.bowling_style = bowling_style
            updated = True
        if updated:
            db.flush()
        return player

    # Create new player
    player = Player(
        name=name,
        role=role,
        batting_style=batting_style,
        bowling_style=bowling_style,
    )
    db.add(player)
    db.flush()
    return player


def _parse_result(status: str):
    """Parse match result from status string like 'CSK won by 6 wkts'."""
    if not status:
        return None, None, None

    # "Team Name won by X runs/wkts"
    match = re.match(r"(.+?) won by (\d+) (run|wkt|wicket)", status, re.IGNORECASE)
    if match:
        winner_name = match.group(1).strip()
        margin = int(match.group(2))
        win_type = "wickets" if "wkt" in match.group(3).lower() or "wicket" in match.group(3).lower() else "runs"
        return winner_name, margin, win_type

    return None, None, None


def run_ingestion():
    """Main ingestion function for IPL 2026 data."""
    if not DATA_FILE.exists():
        print(f"IPL 2026 data file not found at {DATA_FILE}")
        print("Run POST /api/v1/external/refresh to fetch data first.")
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    squads = data.get("squads", {})
    fixtures = data.get("fixtures", [])
    series_info = data.get("series", {})

    if not squads and not fixtures:
        print("No squad or fixture data found in cache.")
        return

    db = SessionLocal()
    try:
        print(f"\n=== Ingesting IPL 2026 Data ===")
        print(f"  Series: {series_info.get('name', 'IPL 2026')}")
        print(f"  Squads: {len(squads)} teams")
        print(f"  Fixtures: {len(fixtures)} matches")

        # 1. Process squads — add/enrich players
        team_squad_map = {}  # short_name -> [player_ids]
        players_added = 0
        players_enriched = 0

        for short_name, squad in squads.items():
            team = _find_or_create_team(db, short_name, squad["name"])
            team.is_active = True
            player_ids = []

            for p_data in squad.get("players", []):
                existing = db.query(Player).filter(Player.name == p_data["name"]).first()
                was_new = existing is None
                player = _find_or_create_player(db, p_data)
                player_ids.append(player.id)
                if was_new:
                    players_added += 1
                elif existing and (not existing.role or not existing.batting_style):
                    players_enriched += 1

            team_squad_map[short_name] = player_ids
            print(f"  {short_name}: {squad['name']} — {len(player_ids)} players")

        db.commit()
        print(f"  Players added: {players_added}, enriched: {players_enriched}")

        # 2. Process fixtures — add as Match records
        # Use hash of UUID as integer source_match_id to avoid column type change
        matches_added = 0
        matches_updated = 0

        for fix in fixtures:
            # Generate a stable integer ID from the UUID
            source_id = abs(hash(fix["id"])) % (10**9) + 2000000  # offset to avoid collision with CSV IDs

            existing = db.query(Match).filter(Match.source_match_id == source_id).first()

            # Find teams
            team1 = db.query(Team).filter(Team.short_name == fix.get("team1")).first() if fix.get("team1") else None
            team2 = db.query(Team).filter(Team.short_name == fix.get("team2")).first() if fix.get("team2") else None

            # Find venue
            venue = _find_or_create_venue(db, fix.get("venue"))

            # Parse result
            winner_name, win_margin, win_type = _parse_result(fix.get("status", ""))
            winner = None
            if winner_name:
                winner = db.query(Team).filter(Team.name.ilike(f"%{winner_name}%")).first()
                if not winner and team1 and winner_name in (team1.name, fix.get("team1_name", "")):
                    winner = team1
                elif not winner and team2 and winner_name in (team2.name, fix.get("team2_name", "")):
                    winner = team2

            match_date = None
            if fix.get("date"):
                try:
                    parts = fix["date"].split("-")
                    match_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                except (ValueError, IndexError):
                    pass

            if existing:
                # Update with result if match has ended
                if fix.get("matchEnded") and winner and not existing.winner_id:
                    existing.winner_id = winner.id
                    existing.win_margin = win_margin
                    existing.win_type = win_type
                    matches_updated += 1
            else:
                m = Match(
                    source_match_id=source_id,
                    date=match_date,
                    season="2026",
                    stage="League",
                    venue_id=venue.id if venue else None,
                    team1_id=team1.id if team1 else None,
                    team2_id=team2.id if team2 else None,
                    winner_id=winner.id if winner else None,
                    win_margin=win_margin,
                    win_type=win_type,
                    toss_winner_id=None,
                    toss_decision=None,
                    player_of_match_id=None,
                    method=None,
                    first_innings_score=None,
                    second_innings_score=None,
                )
                db.add(m)
                matches_added += 1

        db.commit()
        print(f"\n  Fixtures added: {matches_added}, updated: {matches_updated}")

        # 3. Store team squad membership in a simple JSON file for quick access
        squad_db_map = {}
        for short, pids in team_squad_map.items():
            team = db.query(Team).filter(Team.short_name == short).first()
            if team:
                squad_db_map[short] = {
                    "team_id": team.id,
                    "team_name": team.name,
                    "player_ids": pids,
                }

        squad_file = DATA_FILE.parent / "team_squads_2026.json"
        with open(squad_file, "w") as f:
            json.dump(squad_db_map, f, indent=2)
        print(f"  Squad mapping saved to {squad_file}")

        # 4. Update venue stats for new venues
        new_venues = db.query(Venue).filter(~Venue.id.in_(
            db.query(VenueStats.venue_id)
        )).all()
        for v in new_venues:
            vs = VenueStats(
                venue_id=v.id,
                matches_played=0,
                avg_first_innings_score=160.0,
                avg_second_innings_score=145.0,
                bat_first_win_pct=50.0,
                highest_score=0,
                lowest_score=0,
            )
            db.add(vs)
        db.commit()
        if new_venues:
            print(f"  Added default venue stats for {len(new_venues)} new venues")

        # Summary
        total_matches = db.query(Match).count()
        total_players = db.query(Player).count()
        total_venues = db.query(Venue).count()
        ipl2026_matches = db.query(Match).filter(Match.season == "2026").count()
        print(f"\n=== Database Summary ===")
        print(f"  Total matches: {total_matches} (IPL 2026: {ipl2026_matches})")
        print(f"  Total players: {total_players}")
        print(f"  Total venues: {total_venues}")

    except Exception as e:
        db.rollback()
        print(f"Error during ingestion: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_ingestion()
