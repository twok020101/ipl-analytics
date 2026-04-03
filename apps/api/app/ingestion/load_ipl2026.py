"""Ingest IPL 2026 data from CricAPI cache into the database.

Adds:
- New players with role/batting_style/bowling_style/country from squad data
- Enriches existing players with missing role/style/country info
- Adds new venues from fixture data
- Adds IPL 2026 fixtures as Match records (season='2026')
- Creates squad_members records for team squad membership

Run: python -m app.ingestion.load_ipl2026
"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import engine, Base, SessionLocal
from app.models.models import Team, Player, Venue, Match, VenueStats, SquadMember
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
    canonical = _normalize_team(full_name)
    team = db.query(Team).filter(Team.name == canonical).first()
    if team:
        if not team.short_name:
            team.short_name = short_name
        return team
    team = Team(name=canonical, short_name=short_name, is_active=True)
    db.add(team)
    db.flush()
    return team


def _find_or_create_venue(db: Session, venue_str: str) -> Venue:
    """Find venue by name or create. Handles slight name variations."""
    if not venue_str:
        return None
    venue = db.query(Venue).filter(Venue.name == venue_str).first()
    if venue:
        return venue
    parts = venue_str.rsplit(", ", 1)
    city = parts[-1] if len(parts) > 1 else None
    all_venues = db.query(Venue).all()
    for v in all_venues:
        v_lower = v.name.lower()
        new_lower = venue_str.lower()
        if v_lower in new_lower or new_lower in v_lower:
            return v
        v_words = set(re.findall(r'\b\w{5,}\b', v_lower))
        new_words = set(re.findall(r'\b\w{5,}\b', new_lower))
        if v_words & new_words and len(v_words & new_words) >= 1:
            return v
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
    country = player_data.get("country")
    player_img = player_data.get("playerImg")

    if player:
        if not player.role and role:
            player.role = role
        if not player.batting_style and batting_style:
            player.batting_style = batting_style
        if not player.bowling_style and bowling_style:
            player.bowling_style = bowling_style
        if not player.country and country:
            player.country = country
        if not player.player_img and player_img:
            player.player_img = player_img
        return player

    player = Player(
        name=name,
        role=role,
        batting_style=batting_style,
        bowling_style=bowling_style,
        country=country,
        player_img=player_img,
    )
    db.add(player)
    db.flush()
    return player


def _parse_result(status: str):
    """Parse match result from status string like 'CSK won by 6 wkts'."""
    if not status:
        return None, None, None
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

        # 1. Process squads — add/enrich players + create squad memberships
        players_added = 0
        players_enriched = 0
        squad_members_added = 0

        for short_name, squad in squads.items():
            team = _find_or_create_team(db, short_name, squad["name"])
            team.is_active = True
            if squad.get("img") and not team.img:
                team.img = squad["img"]

            for p_data in squad.get("players", []):
                existing = db.query(Player).filter(Player.name == p_data["name"]).first()
                was_new = existing is None
                player = _find_or_create_player(db, p_data)
                if was_new:
                    players_added += 1
                elif existing and (not existing.role or not existing.batting_style):
                    players_enriched += 1

                # Upsert squad membership
                existing_sm = db.query(SquadMember).filter(
                    SquadMember.team_id == team.id,
                    SquadMember.player_id == player.id,
                    SquadMember.season == "2026",
                ).first()
                if not existing_sm:
                    db.add(SquadMember(
                        team_id=team.id,
                        player_id=player.id,
                        season="2026",
                        is_captain=False,
                    ))
                    squad_members_added += 1

            print(f"  {short_name}: {squad['name']} — {len(squad.get('players', []))} players")

        db.commit()
        print(f"  Players added: {players_added}, enriched: {players_enriched}")
        print(f"  Squad memberships added: {squad_members_added}")

        # 2. Process fixtures — add as Match records
        matches_added = 0
        matches_updated = 0

        for fix in fixtures:
            cricapi_uuid = fix["id"]

            # Look up by cricapi_id first (reliable)
            existing = db.query(Match).filter(Match.cricapi_id == cricapi_uuid).first()
            if not existing:
                source_id = int(hashlib.sha256(cricapi_uuid.encode()).hexdigest()[:7], 16) + 2000000
                existing = db.query(Match).filter(Match.source_match_id == source_id).first()
            else:
                source_id = existing.source_match_id

            team1 = db.query(Team).filter(Team.short_name == fix.get("team1")).first() if fix.get("team1") else None
            team2 = db.query(Team).filter(Team.short_name == fix.get("team2")).first() if fix.get("team2") else None
            venue = _find_or_create_venue(db, fix.get("venue"))

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
                if not existing.cricapi_id:
                    existing.cricapi_id = cricapi_uuid
                existing.datetime_gmt = fix.get("dateTimeGMT")
                existing.match_started = fix.get("matchStarted", False)
                existing.match_ended = fix.get("matchEnded", False)
                existing.status_text = fix.get("status", "")
                if fix.get("matchEnded") and winner and not existing.winner_id:
                    existing.winner_id = winner.id
                    existing.win_margin = win_margin
                    existing.win_type = win_type
                    matches_updated += 1
            else:
                source_id = int(hashlib.sha256(cricapi_uuid.encode()).hexdigest()[:7], 16) + 2000000
                m = Match(
                    source_match_id=source_id,
                    cricapi_id=cricapi_uuid,
                    date=match_date,
                    datetime_gmt=fix.get("dateTimeGMT"),
                    season="2026",
                    stage="League",
                    venue_id=venue.id if venue else None,
                    team1_id=team1.id if team1 else None,
                    team2_id=team2.id if team2 else None,
                    winner_id=winner.id if winner else None,
                    win_margin=win_margin,
                    win_type=win_type,
                    match_started=fix.get("matchStarted", False),
                    match_ended=fix.get("matchEnded", False),
                    status_text=fix.get("status", ""),
                )
                db.add(m)
                matches_added += 1

        db.commit()
        print(f"\n  Fixtures added: {matches_added}, updated: {matches_updated}")

        # 3. Update venue stats for new venues
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
        total_squad = db.query(SquadMember).filter(SquadMember.season == "2026").count()
        ipl2026_matches = db.query(Match).filter(Match.season == "2026").count()
        print(f"\n=== Database Summary ===")
        print(f"  Total matches: {total_matches} (IPL 2026: {ipl2026_matches})")
        print(f"  Total players: {total_players}")
        print(f"  Total venues: {total_venues}")
        print(f"  Squad members (2026): {total_squad}")

    except Exception as e:
        db.rollback()
        print(f"Error during ingestion: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_ingestion()
