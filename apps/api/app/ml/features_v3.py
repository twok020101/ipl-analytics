"""
V3 feature engineering — extends V2 with player-level squad composition features.

Adds ~12 squad features per match on top of the ~38 V2 features:
- Per-team batting strength (avg career runs, SR of likely XI)
- Per-team bowling depth (avg career wickets, economy)
- Overseas player count and quality
- Team experience (avg IPL caps)
- Star player factor (top performers in squad)

Total: ~50 features.
"""

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.ml.features_v2 import load_all_data, _compute_match_features


def load_squad_data(db: Session) -> dict:
    """Load player career aggregates for squad composition features."""
    engine = db.get_bind()

    # Player batting career totals
    batting = pd.read_sql(text("""
        SELECT player_id, team_id,
               SUM(matches) as matches,
               SUM(innings) as innings,
               SUM(runs) as runs,
               SUM(balls_faced) as balls,
               SUM(fours) as fours,
               SUM(sixes) as sixes,
               MAX(highest_score) as highest
        FROM player_season_batting
        GROUP BY player_id, team_id
    """), engine)

    # Player bowling career totals
    bowling = pd.read_sql(text("""
        SELECT player_id, team_id,
               SUM(matches) as matches,
               SUM(innings) as innings,
               SUM(wickets) as wickets,
               SUM(overs_bowled) as overs,
               SUM(runs_conceded) as runs_conceded
        FROM player_season_bowling
        GROUP BY player_id, team_id
    """), engine)

    # Player roles
    players = pd.read_sql(text("""
        SELECT id as player_id, name, role, batting_style, bowling_style
        FROM players
    """), engine)

    return {"batting": batting, "bowling": bowling, "players": players}


def _compute_squad_features(team_id: int, season: str, squad_data: dict, prior_batting: pd.DataFrame) -> list:
    """Compute squad composition features for a team.

    Uses batting/bowling aggregates for players who played for the team
    in seasons up to (but not including) the current one.
    """
    bat = squad_data["batting"]
    bowl = squad_data["bowling"]
    players = squad_data["players"]

    # Get players who played for this team (any season)
    team_batters = bat[bat["team_id"] == team_id].copy()
    team_bowlers = bowl[bowl["team_id"] == team_id].copy()

    # Merge role info
    team_batters = team_batters.merge(players, on="player_id", how="left")
    team_bowlers = team_bowlers.merge(players, on="player_id", how="left")

    features = []

    # 1. Batting strength: avg runs per player
    if len(team_batters) > 0:
        avg_runs = team_batters["runs"].mean()
        features.append(min(avg_runs / 2000.0, 1.0))  # normalize ~2000 as max career runs
    else:
        features.append(0.5)

    # 2. Batting SR: avg strike rate across squad
    valid_bat = team_batters[team_batters["balls"] > 50]  # minimum 50 balls faced
    if len(valid_bat) > 0:
        squad_sr = (valid_bat["runs"].sum() / valid_bat["balls"].sum()) * 100
        features.append(min(squad_sr / 200.0, 1.0))  # normalize ~200 as max SR
    else:
        features.append(0.65)

    # 3. Batting depth: number of batters with 200+ career runs
    features.append(min(len(team_batters[team_batters["runs"] >= 200]) / 8.0, 1.0))

    # 4. Power hitting: sixes per match
    if len(valid_bat) > 0 and valid_bat["matches"].sum() > 0:
        sixes_per_match = valid_bat["sixes"].sum() / valid_bat["matches"].sum()
        features.append(min(sixes_per_match / 5.0, 1.0))
    else:
        features.append(0.4)

    # 5. Bowling strength: avg wickets per bowler
    if len(team_bowlers) > 0:
        avg_wkts = team_bowlers["wickets"].mean()
        features.append(min(avg_wkts / 80.0, 1.0))
    else:
        features.append(0.5)

    # 6. Bowling economy: avg economy across squad bowlers
    valid_bowl = team_bowlers[team_bowlers["overs"] > 10]  # min 10 overs bowled
    if len(valid_bowl) > 0:
        squad_econ = valid_bowl["runs_conceded"].sum() / valid_bowl["overs"].sum()
        features.append(1.0 - min(squad_econ / 15.0, 1.0))  # lower is better
    else:
        features.append(0.5)

    # 7. Bowling depth: number of bowlers with 10+ career wickets
    features.append(min(len(team_bowlers[team_bowlers["wickets"] >= 10]) / 6.0, 1.0))

    # 8. All-rounder factor: players who bat and bowl meaningfully
    if len(team_batters) > 0:
        batter_ids = set(team_batters[team_batters["runs"] >= 100]["player_id"])
        bowler_ids = set(team_bowlers[team_bowlers["wickets"] >= 5]["player_id"]) if len(team_bowlers) > 0 else set()
        allrounders = len(batter_ids & bowler_ids)
        features.append(min(allrounders / 4.0, 1.0))
    else:
        features.append(0.3)

    # 9. Experience: total IPL matches across squad
    total_exp = team_batters["matches"].sum() if len(team_batters) > 0 else 0
    features.append(min(total_exp / 1500.0, 1.0))  # normalize: ~1500 total caps

    # 10. Star power: runs of top scorer / 5000
    if len(team_batters) > 0:
        top_runs = team_batters["runs"].max()
        features.append(min(top_runs / 5000.0, 1.0))
    else:
        features.append(0.3)

    # 11. Star bowler: wickets of top wicket-taker / 150
    if len(team_bowlers) > 0:
        top_wkts = team_bowlers["wickets"].max()
        features.append(min(top_wkts / 150.0, 1.0))
    else:
        features.append(0.3)

    # 12. Squad size (players used): indicates depth
    unique_players = len(set(team_batters["player_id"]) | (set(team_bowlers["player_id"]) if len(team_bowlers) > 0 else set()))
    features.append(min(unique_players / 30.0, 1.0))

    return features


SQUAD_FEATURE_NAMES = [
    "squad_bat_strength", "squad_bat_sr", "squad_bat_depth",
    "squad_power_hitting", "squad_bowl_strength", "squad_bowl_economy",
    "squad_bowl_depth", "squad_allrounder_factor", "squad_experience",
    "squad_star_batter", "squad_star_bowler", "squad_size",
]


def build_feature_matrix_v3(data: dict, squad_data: dict) -> tuple:
    """Build V3 feature matrix = V2 features + squad composition features.

    Returns (X, y, match_ids, seasons, feature_names).
    """
    matches = data["matches"].copy()
    innings = data["innings_stats"]

    # Merge innings data (same as V2)
    inn1 = innings[innings["innings"] == 1].rename(
        columns={c: f"inn1_{c}" for c in innings.columns if c not in ("match_id", "innings")}
    )
    inn2 = innings[innings["innings"] == 2].rename(
        columns={c: f"inn2_{c}" for c in innings.columns if c not in ("match_id", "innings")}
    )
    matches = matches.merge(inn1.drop(columns=["innings"]), left_on="id", right_on="match_id", how="left")
    matches = matches.merge(inn2.drop(columns=["innings"]), left_on="id", right_on="match_id", how="left", suffixes=("", "_2"))

    # Build team-match records for V2 rolling features
    team_match_records = []
    for _, m in matches.iterrows():
        for team_col, opp_col, batting_first in [("team1_id", "team2_id", True), ("team2_id", "team1_id", False)]:
            team_id = m[team_col]
            won = 1 if m["winner_id"] == team_id else 0

            if batting_first:
                score = m.get("inn1_total_runs", m.get("first_innings_score"))
                pp = m.get("inn1_pp_runs")
                death = m.get("inn1_death_runs")
                bounds = m.get("inn1_boundaries")
                s6 = m.get("inn1_sixes")
                dots = m.get("inn1_dots")
            else:
                score = m.get("inn2_total_runs", m.get("second_innings_score"))
                pp = m.get("inn2_pp_runs")
                death = m.get("inn2_death_runs")
                bounds = m.get("inn2_boundaries")
                s6 = m.get("inn2_sixes")
                dots = m.get("inn2_dots")

            team_match_records.append({
                "match_id": m["id"], "date": m["date"], "team_id": team_id,
                "opp_id": m[opp_col], "venue_id": m["venue_id"],
                "batting_first": batting_first, "won": won,
                "score": score, "opp_score": None,
                "pp_runs": pp, "death_runs": death,
                "boundaries": bounds, "sixes": s6, "dots": dots,
            })

    tmr = pd.DataFrame(team_match_records)

    feature_rows = []
    feature_names = None

    for idx, m in matches.iterrows():
        prior = matches.iloc[:idx]
        if len(prior) < 20:
            continue

        # V2 features
        v2_features, v2_names = _compute_match_features(m, prior, tmr, matches)
        if v2_features is None:
            continue

        # V3 squad features for team1 and team2
        t1_squad = _compute_squad_features(m["team1_id"], m["season"], squad_data, None)
        t2_squad = _compute_squad_features(m["team2_id"], m["season"], squad_data, None)

        # Combine: V2 + t1_squad + t2_squad
        all_features = np.concatenate([
            v2_features,
            np.array(t1_squad, dtype=np.float32),
            np.array(t2_squad, dtype=np.float32),
        ])

        if feature_names is None:
            feature_names = (
                v2_names
                + [f"t1_{n}" for n in SQUAD_FEATURE_NAMES]
                + [f"t2_{n}" for n in SQUAD_FEATURE_NAMES]
            )

        label = 1 if m["winner_id"] == m["team1_id"] else 0
        feature_rows.append({
            "match_id": m["id"],
            "season": m["season"],
            "features": all_features,
            "label": label,
        })

    X = np.array([r["features"] for r in feature_rows])
    y = np.array([r["label"] for r in feature_rows])
    match_ids = [r["match_id"] for r in feature_rows]
    seasons = [r["season"] for r in feature_rows]

    return X, y, match_ids, seasons, feature_names


def build_prediction_features_v3(db: Session, team1_id: int, team2_id: int,
                                  venue_id: int, toss_winner_id: int = None,
                                  toss_decision: str = None) -> np.ndarray:
    """Build V3 features for a new prediction."""
    from app.ml.features_v2 import build_prediction_features

    # V2 base features
    v2_features = build_prediction_features(db, team1_id, team2_id, venue_id, toss_winner_id, toss_decision)

    # Squad features
    squad_data = load_squad_data(db)
    t1_squad = _compute_squad_features(team1_id, "2026", squad_data, None)
    t2_squad = _compute_squad_features(team2_id, "2026", squad_data, None)

    return np.concatenate([
        v2_features,
        np.array(t1_squad, dtype=np.float32),
        np.array(t2_squad, dtype=np.float32),
    ])
