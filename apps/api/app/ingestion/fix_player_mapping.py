"""
Fix player ID mapping between CricAPI 2026 squad data and historical IPL database.

Problem: ipl2026.json uses full names (e.g., "Rohit Sharma") while historical DB
uses initials (e.g., "RG Sharma"). The team_squads_2026.json points to newly
created player IDs with NO historical data.

This script:
1. Matches CricAPI players to their historical counterparts
2. Updates historical player records with CricAPI metadata (role, styles)
3. Rewrites team_squads_2026.json to use historical player IDs

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    .venv/bin/python -m app.ingestion.fix_player_mapping
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = Path(__file__).resolve().parents[2] / "ipl_analytics.db"

# -----------------------------------------------------------------------
# Verified explicit mappings: CricAPI full_name -> historical DB player_id
# These override any algorithmic matching.
# -----------------------------------------------------------------------
EXPLICIT_MAPPING = {
    # Tricky last names / unusual DB name formats
    "Venkatesh Iyer": 730,       # VR Iyer
    "Krunal Pandya": 316,        # KH Pandya (NOT HH Pandya = Hardik)
    "Varun Chakaravarthy": 153,  # CV Varun
    "Rinku Singh": 552,          # RK Singh
    "Sarfaraz Khan": 632,        # SN Khan
    "Sai Sudharsan": 106,        # B Sai Sudharsan
    "Wanindu Hasaranga": 508,    # PWH de Silva
    "Dushmantha Chameera": 505,  # PVD Chameera
    "Rasikh Salam Dar": 576,     # Rasikh Salam
    "Kamindu Mendis": 493,       # PHKD Mendis
    "Dasun Shanaka": 392,        # MD Shanaka
    "Finn Allen": 208,           # FA Allen
    "Prasidh Krishna": 375,      # M Prasidh Krishna
    "Nitish Kumar Reddy": 467,   # Nithish Kumar Reddy (spelling variant)
    "Musheer Khan": 443,         # Musheer Khan (keep own ID - has some data)
}

# Players that must NOT be matched algorithmically because the algorithm
# produces false positives for them. They either have no IPL history or
# their CricAPI ID is already correct.
DO_NOT_REMAP = {
    # New players with no history in DB (would wrongly match other players)
    "Raghu Sharma",          # NOT RG Sharma (Rohit)
    "Himmat Singh",          # NOT Harbhajan Singh
    "Kuldeep Sen",           # NOT KP Pietersen
    "Abhinandan Singh",      # NOT Arshdeep Singh
    "Ashok Sharma",          # NOT Abhishek Sharma (different person at GT)
    "Nishant Sindhu",        # No historical match
    "Vicky Ostwal",          # No historical match
    "Jordan Cox",            # No historical match
    "Atharva Ankolekar",     # No historical match
    "AM Ghazanfar",          # No historical match
    "Brydon Carse",          # No historical match
    "Ben Duckett",           # No historical match
    "Pathum Nissanka",       # No historical match
    "Ajay Jadav Mandal",     # No historical match
    "Sushant Mishra",        # No historical match
    "Eshan Malinga",         # No historical match (not Lasith Malinga)
    # New players likely without IPL history
    "Madhav Tiwari", "Auqib Nabi Dar", "Sahil Parakh", "Tripurana Vijay",
    "Vipraj Nigam", "Praful Hinge", "Sakib Hussain",
    "Smaran Ravichandran", "Jack Edwards", "Krains Fuletra", "Shivang Kumar",
    "David Payne", "Onkar Tarmale", "Amit Kumar", "Salil Arora",
    "Mohammed Salahuddin Izhar", "Danish Malewar", "Mayank Rawat",
    "Digvesh Singh Rathi", "Manimaran Siddharth", "Akash Maharaj Singh",
    "Mukul Choudhary", "Akshat Raghuwanshi", "Arshin Kulkarni",
    "Naman Tiwari", "Mayank Prabhu Yadav", "Matthew Breetzke",
    "Yash Raj Punja", "Vaibhav Sooryavanshi", "Shubham Dubey",
    "Aman Rao Perala", "Brijesh Sharma", "Ravi Singh",
    "Lhuan-dre Pretorius", "Donovan Ferreira", "Kwena Maphaka",
    "Yudhvir Singh Charak", "Vignesh Puthur",
    "Vihaan Malhotra", "Satvik Deswal", "Jacob Duffy",
    "Kanishk Chouhan",
    "Blessing Muzarabani", "Tejasvi Dahiya", "Angkrish Raghuvanshi",
    "Sarthak Ranjan", "Daksh Kamra",
    "Cooper Connolly", "Xavier Bartlett", "Mitchell Owen",
    "Ben Dwarshuis", "Harnoor Singh", "Pyla Avinash",
    "Vishal Nishad",
    "Kulwant Khejroliya", "Prithvi Raj Yarra",
    "Aman Khan", "Zakary Foulkes", "Gurjapneet Singh",
    "Prashant Veer", "Ayush Mhatre", "Kartik Sharma",
    "Ramakrishna Ghosh",
}


def get_connection():
    return sqlite3.connect(str(DB_PATH))


def load_ipl2026():
    with open(DATA_DIR / "ipl2026.json") as f:
        return json.load(f)


def load_squads():
    with open(DATA_DIR / "team_squads_2026.json") as f:
        return json.load(f)


def save_squads(data):
    with open(DATA_DIR / "team_squads_2026.json", "w") as f:
        json.dump(data, f, indent=2)


def get_delivery_count(conn, player_id: int) -> int:
    """Count deliveries where this player appears as batter or bowler."""
    r = conn.execute(
        "SELECT COUNT(*) FROM deliveries WHERE batter_id=? OR bowler_id=?",
        (player_id, player_id),
    ).fetchone()
    return r[0] if r else 0


def find_historical_player(
    conn, full_name: str, role: str = "", batting_style: str = "", bowling_style: str = ""
) -> Optional[Tuple[int, str, int]]:
    """
    Find the historical player ID matching a CricAPI full name.
    Returns (player_id, db_name, delivery_count) or None.
    """
    # ------------------------------------------------------------------
    # Step 0: Check explicit mapping first
    # ------------------------------------------------------------------
    if full_name in EXPLICIT_MAPPING:
        pid = EXPLICIT_MAPPING[full_name]
        row = conn.execute("SELECT id, name FROM players WHERE id=?", (pid,)).fetchone()
        if row:
            dc = get_delivery_count(conn, pid)
            return (row[0], row[1], dc)

    # ------------------------------------------------------------------
    # Step 1: Check if the full name already exists exactly in the DB
    # ------------------------------------------------------------------
    row = conn.execute(
        "SELECT id, name FROM players WHERE name = ?", (full_name,)
    ).fetchone()
    if row:
        dc = get_delivery_count(conn, row[0])
        if dc > 50:
            return (row[0], row[1], dc)

    # ------------------------------------------------------------------
    # Step 2: General matching - last name + first initial
    # ------------------------------------------------------------------
    parts = full_name.strip().split()
    if len(parts) < 2:
        return None

    first_name = parts[0]
    last_name = parts[-1]
    first_initial = first_name[0].upper()

    # Search for last name match
    candidates = conn.execute(
        "SELECT id, name, role FROM players WHERE name LIKE ? AND name != ?",
        (f"%{last_name}", full_name),
    ).fetchall()

    # Also search with multi-word last name (for names like "de Kock", "Salam Dar")
    if not candidates and len(parts) > 2:
        search_term = " ".join(parts[1:])
        candidates = conn.execute(
            "SELECT id, name, role FROM players WHERE name LIKE ? AND name != ?",
            (f"%{search_term}", full_name),
        ).fetchall()

    best = None
    best_dc = 0

    for cid, cname, crole in candidates:
        dc = get_delivery_count(conn, cid)
        if dc < 10:
            continue

        # Check first initial match
        cname_parts = cname.strip().split()
        cname_first = cname_parts[0] if cname_parts else ""

        initial_match = False
        # Handle initials like "RG" for "Rohit" -> R matches
        if len(cname_first) <= 4 and cname_first[0].upper() == first_initial:
            initial_match = True
        # Handle full first name starting with same letter
        elif cname_first.upper().startswith(first_initial):
            initial_match = True

        if not initial_match:
            continue

        # Avoid common false positives: if candidate name has very different length, skip
        # e.g., "Raghu Sharma" should not match "RG Sharma" (Rohit) just by initial
        # Only allow if the candidate has initials (len <= 4 for first part)
        if len(cname_first) > 4 and cname_first.lower() != first_name.lower():
            # Full first names that don't match -> skip
            continue

        if dc > best_dc:
            best = (cid, cname, dc)
            best_dc = dc

    if best and best[2] > 10:
        return best

    # ------------------------------------------------------------------
    # Step 3: Try the exact name match even with low delivery count
    # ------------------------------------------------------------------
    if row:
        dc = get_delivery_count(conn, row[0])
        if dc > 0:
            return (row[0], row[1], dc)

    return None


def run():
    conn = get_connection()
    ipl2026 = load_ipl2026()
    squads = load_squads()

    # Track results
    mapped = []
    not_found = []
    already_ok = []
    updated_metadata = []

    # New squads dict to write back
    new_squads = {}

    for team_code, team_data in ipl2026.get("squads", {}).items():
        players = team_data.get("players", [])
        squad_info = squads.get(team_code, {})
        old_ids = squad_info.get("player_ids", [])
        new_ids = []

        print(f"\n{'='*60}")
        print(f"  {team_code} - {team_data.get('name', '')}")
        print(f"{'='*60}")

        for i, player in enumerate(players):
            cricapi_id = old_ids[i] if i < len(old_ids) else None
            name = player["name"]
            role = player.get("role", "")
            batting_style = player.get("battingStyle", "")
            bowling_style = player.get("bowlingStyle", "")

            # Check if this ID already has historical data (>50 deliveries)
            if cricapi_id is not None:
                dc = get_delivery_count(conn, cricapi_id)
                if dc > 50:
                    # Already pointing to a player with data - keep it
                    new_ids.append(cricapi_id)
                    db_name = conn.execute(
                        "SELECT name FROM players WHERE id=?", (cricapi_id,)
                    ).fetchone()
                    already_ok.append((name, cricapi_id, db_name[0] if db_name else "??", dc))
                    print(f"  OK  {name:30s} -> id={cricapi_id:4d} ({dc} deliveries)")
                    continue

            # Skip players that should not be remapped
            if name in DO_NOT_REMAP:
                new_ids.append(cricapi_id)
                not_found.append((name, team_code, "skip"))
                print(f"  SKIP {name:30s} -> id={cricapi_id:4d} (no remap)")
                continue

            # Try to find historical match
            result = find_historical_player(conn, name, role, batting_style, bowling_style)

            if result:
                hist_id, hist_name, dc = result
                new_ids.append(hist_id)
                mapped.append((name, cricapi_id, hist_id, hist_name, dc))
                print(f"  MAP {name:30s} -> id={hist_id:4d} ({hist_name}, {dc} deliveries)")

                # Update historical player record with CricAPI metadata
                existing = conn.execute(
                    "SELECT role, batting_style, bowling_style FROM players WHERE id=?",
                    (hist_id,),
                ).fetchone()
                updates = []
                params = []
                if existing:
                    if not existing[0] and role:
                        updates.append("role=?")
                        params.append(role)
                    if not existing[1] and batting_style:
                        updates.append("batting_style=?")
                        params.append(batting_style)
                    if not existing[2] and bowling_style:
                        updates.append("bowling_style=?")
                        params.append(bowling_style)

                    if updates:
                        params.append(hist_id)
                        conn.execute(
                            f"UPDATE players SET {', '.join(updates)} WHERE id=?",
                            params,
                        )
                        updated_metadata.append((hist_name, hist_id, updates))
            else:
                new_ids.append(cricapi_id)
                not_found.append((name, team_code, "no_match"))
                print(f"  ??? {name:30s} -> id={cricapi_id:4d} (no historical match found)")

        new_squads[team_code] = {
            "team_id": squad_info.get("team_id"),
            "team_name": squad_info.get("team_name", team_data.get("name", "")),
            "player_ids": new_ids,
        }

    conn.commit()

    # Save updated squads
    save_squads(new_squads)

    # Print report
    print(f"\n{'='*60}")
    print(f"  MAPPING REPORT")
    print(f"{'='*60}")
    print(f"\n  Already correct:     {len(already_ok)}")
    print(f"  Successfully mapped: {len(mapped)}")
    print(f"  Not found/skipped:   {len(not_found)}")
    print(f"  Metadata updated:    {len(updated_metadata)}")

    if mapped:
        print(f"\n  --- Successfully Mapped ---")
        for name, old_id, new_id, hist_name, dc in mapped:
            print(f"    {name:30s}  old_id={old_id:4d} -> new_id={new_id:4d} ({hist_name}, {dc} del)")

    if not_found:
        print(f"\n  --- Not Found / Skipped ---")
        for name, team, reason in not_found:
            print(f"    {name:30s}  [{team}] ({reason})")

    if updated_metadata:
        print(f"\n  --- Metadata Updated ---")
        for hist_name, hist_id, updates in updated_metadata:
            print(f"    {hist_name:30s}  id={hist_id:4d}  fields={updates}")

    conn.close()
    print(f"\n  Done. team_squads_2026.json has been updated.")


if __name__ == "__main__":
    run()
