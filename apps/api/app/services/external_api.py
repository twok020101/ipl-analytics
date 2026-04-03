"""CricAPI integration for fetching live IPL data — writes to DB, not JSON."""

import logging

import httpx
from datetime import date
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from app.config import settings
from app.models.models import Team, Player, Match, Venue, SquadMember
from app.services.db_helpers import (
    find_or_create_team, find_or_create_player, find_or_create_venue, stable_source_id,
)

CRICAPI_BASE = "https://api.cricapi.com/v1"
IPL_2026_SERIES_ID = "87c62aac-bc3c-4738-ab93-19da0690488f"


def _get_api_key():
    return settings.CRICAPI_KEY or "4e5433ae-caa5-423b-88fe-c5c159ebe9c8"


# ---- CricAPI Fetch Functions ----

async def fetch_series_info():
    """Fetch IPL 2026 series info with all matches."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{CRICAPI_BASE}/series_info", params={
                "apikey": _get_api_key(),
                "id": IPL_2026_SERIES_ID,
            })
            data = resp.json()
            if data.get("status") == "success":
                return data["data"]
    except Exception as e:
        print(f"CricAPI error: {e}")
    return None


async def fetch_squad(match_id: str):
    """Fetch squad for a specific match."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{CRICAPI_BASE}/match_squad", params={
                "apikey": _get_api_key(),
                "id": match_id,
            })
            data = resp.json()
            if data.get("status") == "success":
                return data.get("data", [])
    except Exception as e:
        print(f"CricAPI squad error: {e}")
    return []


async def fetch_player_info(player_id: str):
    """Fetch detailed player info."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{CRICAPI_BASE}/players_info", params={
                "apikey": _get_api_key(),
                "id": player_id,
            })
            data = resp.json()
            if data.get("status") == "success":
                return data.get("data", {})
    except Exception as e:
        print(f"CricAPI player error: {e}")
    return None




# ---- Main Refresh Function ----

async def refresh_ipl2026_data(db: Session) -> dict:
    """Refresh all IPL 2026 data from CricAPI into the database."""
    series = await fetch_series_info()
    if not series:
        return {"error": "Failed to fetch series info"}

    matches = series.get("matchList", [])
    info = series.get("info", {})

    # Fetch squads
    teams_covered = set()
    match_ids_for_squads = []
    for m in matches:
        team_shorts = set(t.get('shortname', '') for t in m.get('teamInfo', []))
        new_teams = team_shorts - teams_covered
        if new_teams and m.get('hasSquad'):
            match_ids_for_squads.append(m['id'])
            teams_covered.update(team_shorts)
            if len(teams_covered) >= 10:
                break

    all_squads = {}
    for mid in match_ids_for_squads:
        squad_data = await fetch_squad(mid)
        for team in squad_data:
            short = team.get('shortname', '')
            if short == 'RCBW':
                short = 'RCB'
            if short and short not in all_squads:
                all_squads[short] = {
                    'name': team.get('teamName', ''),
                    'short_name': short,
                    'img': team.get('img', ''),
                    'players': team.get('players', []),
                }

    # 1. Upsert teams and players, create squad memberships
    for short_name, squad in all_squads.items():
        team = find_or_create_team(db, short_name, squad['name'])
        if squad.get('img'):
            team.img = squad['img']

        for p_data in squad.get('players', []):
            player = find_or_create_player(
                db,
                p_data['name'],
                role=p_data.get('role'),
                batting_style=p_data.get('battingStyle'),
                bowling_style=p_data.get('bowlingStyle'),
                country=p_data.get('country'),
                player_img=p_data.get('playerImg'),
            )

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

    db.flush()

    # 2. Upsert fixtures as Match records
    fixtures_out = []
    for m in matches:
        ti = m.get('teamInfo', [])
        t1_short = ti[0]['shortname'] if len(ti) > 0 else None
        t2_short = ti[1]['shortname'] if len(ti) > 1 else None
        if t1_short == 'RCBW':
            t1_short = 'RCB'
        if t2_short == 'RCBW':
            t2_short = 'RCB'

        cricapi_uuid = m['id']

        # Look up existing match
        db_match = db.query(Match).filter(Match.cricapi_id == cricapi_uuid).first()

        team1 = db.query(Team).filter(Team.short_name == t1_short).first() if t1_short else None
        team2 = db.query(Team).filter(Team.short_name == t2_short).first() if t2_short else None
        venue = find_or_create_venue(db, m.get('venue'))

        # Parse date
        match_date = None
        if m.get('date'):
            try:
                parts = m['date'].split('-')
                match_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                pass

        if db_match:
            # Update mutable fields
            db_match.datetime_gmt = m.get('dateTimeGMT')
            db_match.match_started = m.get('matchStarted', False)
            db_match.match_ended = m.get('matchEnded', False)
            db_match.status_text = m.get('status', '')
            if venue:
                db_match.venue_id = venue.id
        else:
            source_id = stable_source_id(cricapi_uuid)
            # Check for source_match_id collision
            existing_by_source = db.query(Match).filter(Match.source_match_id == source_id).first()
            if existing_by_source:
                # Backfill cricapi_id on the existing row
                existing_by_source.cricapi_id = cricapi_uuid
                existing_by_source.datetime_gmt = m.get('dateTimeGMT')
                existing_by_source.match_started = m.get('matchStarted', False)
                existing_by_source.match_ended = m.get('matchEnded', False)
                existing_by_source.status_text = m.get('status', '')
            else:
                db.add(Match(
                    source_match_id=source_id,
                    cricapi_id=cricapi_uuid,
                    date=match_date,
                    datetime_gmt=m.get('dateTimeGMT'),
                    season="2026",
                    stage="League",
                    venue_id=venue.id if venue else None,
                    team1_id=team1.id if team1 else None,
                    team2_id=team2.id if team2 else None,
                    match_started=m.get('matchStarted', False),
                    match_ended=m.get('matchEnded', False),
                    status_text=m.get('status', ''),
                ))

        fixtures_out.append({
            'id': cricapi_uuid,
            'name': m.get('name', ''),
            'date': m.get('date'),
            'dateTimeGMT': m.get('dateTimeGMT'),
            'venue': m.get('venue'),
            'team1': t1_short,
            'team2': t2_short,
            'team1_img': ti[0].get('img') if len(ti) > 0 else None,
            'team2_img': ti[1].get('img') if len(ti) > 1 else None,
            'status': m.get('status', ''),
            'matchStarted': m.get('matchStarted', False),
            'matchEnded': m.get('matchEnded', False),
        })

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate match skipped during fixture sync (unique constraint)")

    return {
        'series': {
            'id': IPL_2026_SERIES_ID,
            'name': info.get('name', 'Indian Premier League 2026'),
            'startDate': info.get('startdate', '2026-03-28'),
            'endDate': info.get('enddate', '2026-05-31'),
            'totalMatches': len(matches),
        },
        'squads': all_squads,
        'fixtures': sorted(fixtures_out, key=lambda x: x['date'] or ''),
    }


# ---- Read Functions (DB-first, no JSON fallback) ----

def _match_to_fixture_dict(m: Match) -> dict:
    """Convert a Match ORM object (with eager-loaded relationships) to fixture dict."""
    t1 = m.team1
    t2 = m.team2
    return {
        'id': m.cricapi_id or str(m.source_match_id),
        'name': f"{t1.short_name if t1 else '?'} vs {t2.short_name if t2 else '?'}",
        'date': str(m.date) if m.date else None,
        'dateTimeGMT': m.datetime_gmt,
        'venue': m.venue.name if m.venue else None,
        'team1': t1.short_name if t1 else None,
        'team2': t2.short_name if t2 else None,
        'team1_img': t1.img if t1 else None,
        'team2_img': t2.img if t2 else None,
        'status': m.status_text or '',
        'matchStarted': m.match_started or False,
        'matchEnded': m.match_ended or False,
    }


def get_fixtures(db: Session) -> list:
    """Get IPL 2026 fixtures from DB."""
    matches = (
        db.query(Match)
        .filter(Match.season == "2026")
        .options(joinedload(Match.team1), joinedload(Match.team2), joinedload(Match.venue))
        .order_by(Match.date)
        .all()
    )
    return [_match_to_fixture_dict(m) for m in matches]


def get_squads(db: Session) -> dict:
    """Get all team squads from DB."""
    members = (
        db.query(SquadMember)
        .filter(SquadMember.season == "2026")
        .join(SquadMember.team)
        .join(SquadMember.player)
        .all()
    )
    if not members:
        return {}

    result = {}
    for m in members:
        key = m.team.short_name
        if key not in result:
            result[key] = {
                'name': m.team.name,
                'short_name': key,
                'img': m.team.img or '',
                'players': [],
            }
        result[key]['players'].append({
            'id': str(m.player_id),
            'name': m.player.name,
            'role': m.player.role or '',
            'battingStyle': m.player.batting_style or '',
            'bowlingStyle': m.player.bowling_style or '',
            'country': m.player.country or 'India',
            'playerImg': m.player.player_img or '',
        })
    return result


def get_team_squad(db: Session, short_name: str) -> Optional[dict]:
    """Get a specific team's squad from DB."""
    squads = get_squads(db)
    return squads.get(short_name.upper())


def get_upcoming_fixtures(db: Session, limit: int = 5) -> list:
    """Get upcoming fixtures from DB. Excludes completed matches even if match_ended flag is stale."""
    today = date.today()
    matches = (
        db.query(Match)
        .filter(
            Match.season == "2026",
            Match.date >= today,
            Match.match_ended == False,
            Match.winner_id.is_(None),
        )
        .options(joinedload(Match.team1), joinedload(Match.team2), joinedload(Match.venue))
        .order_by(Match.date)
        .limit(limit)
        .all()
    )
    return [_match_to_fixture_dict(m) for m in matches]


def get_cached_data(db: Session) -> Optional[dict]:
    """Assemble full IPL 2026 data from DB."""
    fixtures = get_fixtures(db)
    squads = get_squads(db)
    if not fixtures and not squads:
        return None
    return {
        'series': {
            'id': IPL_2026_SERIES_ID,
            'name': 'Indian Premier League 2026',
        },
        'squads': squads,
        'fixtures': fixtures,
    }
