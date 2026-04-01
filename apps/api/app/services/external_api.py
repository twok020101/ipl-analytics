"""CricAPI integration for fetching live IPL data."""
import json
import httpx
from pathlib import Path
from typing import Optional
from app.config import settings

CRICAPI_BASE = "https://api.cricapi.com/v1"
IPL_2026_SERIES_ID = "87c62aac-bc3c-4738-ab93-19da0690488f"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CACHE_FILE = DATA_DIR / "ipl2026.json"

def _get_api_key():
    return settings.CRICAPI_KEY or "4e5433ae-caa5-423b-88fe-c5c159ebe9c8"

def _load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return None

def _save_cache(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

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

async def refresh_ipl2026_data():
    """Refresh all IPL 2026 data — series, fixtures, squads."""
    series = await fetch_series_info()
    if not series:
        return {"error": "Failed to fetch series info"}

    matches = series.get("matchList", [])
    info = series.get("info", {})

    # Fetch squads — need minimum matches to cover all teams
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
                    'players': team.get('players', [])
                }

    # Build fixtures
    fixtures = []
    for m in matches:
        ti = m.get('teamInfo', [])
        t1 = ti[0]['shortname'] if len(ti) > 0 else None
        t2 = ti[1]['shortname'] if len(ti) > 1 else None
        if t1 == 'RCBW': t1 = 'RCB'
        if t2 == 'RCBW': t2 = 'RCB'
        fixtures.append({
            'id': m['id'],
            'name': m.get('name', ''),
            'date': m.get('date'),
            'dateTimeGMT': m.get('dateTimeGMT'),
            'venue': m.get('venue'),
            'team1': t1,
            'team2': t2,
            'team1_img': ti[0].get('img') if len(ti) > 0 else None,
            'team2_img': ti[1].get('img') if len(ti) > 1 else None,
            'status': m.get('status', ''),
            'matchStarted': m.get('matchStarted', False),
            'matchEnded': m.get('matchEnded', False),
        })

    output = {
        'series': {
            'id': IPL_2026_SERIES_ID,
            'name': info.get('name', 'Indian Premier League 2026'),
            'startDate': info.get('startdate', '2026-03-28'),
            'endDate': info.get('enddate', '2026-05-31'),
            'totalMatches': len(matches),
        },
        'squads': all_squads,
        'fixtures': sorted(fixtures, key=lambda x: x['date'] or ''),
    }

    _save_cache(output)
    return output

def get_cached_data():
    """Get cached IPL 2026 data."""
    return _load_cache()

def get_fixtures():
    """Get IPL 2026 fixtures from cache."""
    data = _load_cache()
    if not data:
        return []
    return data.get('fixtures', [])

def get_squads():
    """Get all team squads from cache."""
    data = _load_cache()
    if not data:
        return {}
    return data.get('squads', {})

def get_team_squad(short_name: str):
    """Get a specific team's squad."""
    squads = get_squads()
    return squads.get(short_name.upper(), None)

def get_upcoming_fixtures(limit=5):
    """Get upcoming (not started) fixtures."""
    from datetime import date
    today = str(date.today())
    fixtures = get_fixtures()
    upcoming = [f for f in fixtures if f.get('date', '') >= today and not f.get('matchEnded')]
    return upcoming[:limit]
