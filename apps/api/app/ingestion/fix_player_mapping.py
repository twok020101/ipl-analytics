"""
Fix player ID mapping between CricAPI 2026 squad data and historical IPL database.

Problem: ipl2026.json uses full names (e.g., "Rohit Sharma") while historical DB
uses initials (e.g., "RG Sharma"). The squad_members table may point to newly
created player IDs with NO historical data.

This script:
1. Matches CricAPI players to their historical counterparts
2. Updates historical player records with CricAPI metadata (role, styles)
3. Updates squad_members to use historical player IDs

Usage:
    cd /Users/twok/Projects/dataset/apps/api
    .venv/bin/python -m app.ingestion.fix_player_mapping
"""

import json
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import Player, SquadMember, Team
from app.config import DATA_DIR

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


def load_ipl2026():
    with open(DATA_DIR / "ipl2026.json") as f:
        return json.load(f)


def get_delivery_count(db: Session, player_id: int) -> int:
    """Count deliveries where this player appears as batter or bowler."""
    r = db.execute(
        text("SELECT COUNT(*) FROM deliveries WHERE batter_id=:pid OR bowler_id=:pid"),
        {"pid": player_id},
    ).fetchone()
    return r[0] if r else 0


def find_historical_player(
    db: Session, full_name: str, role: str = "", batting_style: str = "", bowling_style: str = ""
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
        row = db.execute(text("SELECT id, name FROM players WHERE id=:pid"), {"pid": pid}).fetchone()
        if row:
            dc = get_delivery_count(db, pid)
            return (row[0], row[1], dc)

    # ------------------------------------------------------------------
    # Step 1: Check if the full name already exists exactly in the DB
    # ------------------------------------------------------------------
    row = db.execute(
        text("SELECT id, name FROM players WHERE name = :name"), {"name": full_name}
    ).fetchone()
    if row:
        dc = get_delivery_count(db, row[0])
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
    candidates = db.execute(
        text("SELECT id, name, role FROM players WHERE name LIKE :pattern AND name != :name"),
        {"pattern": f"%{last_name}", "name": full_name},
    ).fetchall()

    # Also search with multi-word last name (for names like "de Kock", "Salam Dar")
    if not candidates and len(parts) > 2:
        search_term = " ".join(parts[1:])
        candidates = db.execute(
            text("SELECT id, name, role FROM players WHERE name LIKE :pattern AND name != :name"),
            {"pattern": f"%{search_term}", "name": full_name},
        ).fetchall()

    best = None
    best_dc = 0

    for cid, cname, crole in candidates:
        dc = get_delivery_count(db, cid)
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
        dc = get_delivery_count(db, row[0])
        if dc > 0:
            return (row[0], row[1], dc)

    return None


def run():
    db = SessionLocal()
    ipl2026 = load_ipl2026()

    # Track results
    mapped = []
    not_found = []
    already_ok = []
    updated_metadata = []

    for team_code, team_data in ipl2026.get("squads", {}).items():
        players = team_data.get("players", [])

        # Get team
        team = db.query(Team).filter(Team.short_name == team_code).first()
        if not team:
            print(f"  Team {team_code} not found in DB, skipping")
            continue

        # Get current squad member IDs for this team
        current_members = (
            db.query(SquadMember)
            .filter(SquadMember.team_id == team.id, SquadMember.season == "2026")
            .all()
        )
        member_by_player_id = {m.player_id: m for m in current_members}

        print(f"\n{'='*60}")
        print(f"  {team_code} - {team_data.get('name', '')}")
        print(f"{'='*60}")

        for player_data in players:
            name = player_data["name"]
            role = player_data.get("role", "")
            batting_style = player_data.get("battingStyle", "")
            bowling_style = player_data.get("bowlingStyle", "")

            # Find the current player record for this name
            current_player = db.query(Player).filter(Player.name == name).first()
            if not current_player:
                not_found.append((name, team_code, "not_in_db"))
                print(f"  ??? {name:30s} (not in DB)")
                continue

            cricapi_id = current_player.id

            # Check if this ID already has historical data (>50 deliveries)
            dc = get_delivery_count(db, cricapi_id)
            if dc > 50:
                already_ok.append((name, cricapi_id, name, dc))
                print(f"  OK  {name:30s} -> id={cricapi_id:4d} ({dc} deliveries)")
                continue

            # Skip players that should not be remapped
            if name in DO_NOT_REMAP:
                not_found.append((name, team_code, "skip"))
                print(f"  SKIP {name:30s} -> id={cricapi_id:4d} (no remap)")
                continue

            # Try to find historical match
            result = find_historical_player(db, name, role, batting_style, bowling_style)

            if result:
                hist_id, hist_name, dc = result
                mapped.append((name, cricapi_id, hist_id, hist_name, dc))
                print(f"  MAP {name:30s} -> id={hist_id:4d} ({hist_name}, {dc} deliveries)")

                # Update historical player record with CricAPI metadata
                hist_player = db.query(Player).get(hist_id)
                if hist_player:
                    if not hist_player.role and role:
                        hist_player.role = role
                    if not hist_player.batting_style and batting_style:
                        hist_player.batting_style = batting_style
                    if not hist_player.bowling_style and bowling_style:
                        hist_player.bowling_style = bowling_style
                    if not hist_player.country and player_data.get("country"):
                        hist_player.country = player_data["country"]
                    updated_metadata.append((hist_name, hist_id))

                # Update squad_members to point to historical player
                sm = member_by_player_id.get(cricapi_id)
                if sm and hist_id != cricapi_id:
                    # Check if hist_id already has a squad membership
                    existing_hist_sm = db.query(SquadMember).filter(
                        SquadMember.team_id == team.id,
                        SquadMember.player_id == hist_id,
                        SquadMember.season == "2026",
                    ).first()
                    if existing_hist_sm:
                        # Already exists, delete the duplicate
                        db.delete(sm)
                    else:
                        sm.player_id = hist_id
            else:
                not_found.append((name, team_code, "no_match"))
                print(f"  ??? {name:30s} -> id={cricapi_id:4d} (no historical match found)")

    db.commit()

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

    db.close()
    print(f"\n  Done. squad_members table has been updated.")


if __name__ == "__main__":
    run()
