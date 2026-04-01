"""Dynamic game plan recalculation based on live match state."""

import numpy as np
from typing import Optional


def recalculate_game_plan(
    innings: int,
    runs: int,
    wickets: int,
    overs: float,
    target: int = 0,
    venue_avg: float = 165.0,
    weather: dict = None,
    win_prob: dict = None,
) -> dict:
    """Generate updated game plan based on current match situation.

    Returns tactical advice for BOTH teams -- batting team and bowling team.
    """
    if win_prob is None:
        # Lazy import to avoid circular dependency with live_tracker
        from app.services.live_tracker import predict_live_win_probability
        win_prob = predict_live_win_probability(innings, runs, wickets, overs, target, venue_avg)

    over_num = int(overs)
    balls_bowled = int(over_num * 6 + round((overs - over_num) * 10))
    balls_remaining = 120 - balls_bowled
    overs_remaining = balls_remaining / 6.0
    wickets_in_hand = 10 - wickets
    current_rr = runs / max(overs, 0.1)

    # Determine phase
    if over_num < 6:
        phase = "powerplay"
    elif over_num < 15:
        phase = "middle"
    else:
        phase = "death"

    # Dew factor from weather
    dew = weather.get("dew_factor", "minimal") if weather else "minimal"

    if innings == 1:
        return _first_innings_plan(runs, wickets, overs, over_num, overs_remaining,
                                    wickets_in_hand, current_rr, venue_avg, phase, dew, win_prob)
    else:
        return _second_innings_plan(runs, wickets, overs, over_num, overs_remaining,
                                     wickets_in_hand, current_rr, target, phase, dew, win_prob)


def _first_innings_plan(runs, wickets, overs, over_num, overs_rem, wkts_hand,
                         curr_rr, venue_avg, phase, dew, win_prob):
    projected = runs + (curr_rr * overs_rem)
    par_at_stage = venue_avg * (overs / 20.0)
    delta = runs - par_at_stage

    # Batting advice
    if phase == "powerplay":
        if delta > 10:
            bat_advice = "Excellent start. Continue aggressive approach, target 50+ in PP."
            bat_approach = "aggressive"
        elif delta > -5:
            bat_advice = "Solid start. Push for boundaries but don't take unnecessary risks."
            bat_approach = "positive"
        else:
            bat_advice = "Slow start. Need to accelerate -- look for bad balls to punish."
            bat_approach = "rebuild_then_attack"
    elif phase == "middle":
        if wkts_hand >= 8 and delta > 0:
            bat_advice = f"Strong position at {runs}/{wickets}. Accelerate towards {int(venue_avg + 20)}+. Set up for a big death overs push."
            bat_approach = "accelerate"
        elif wkts_hand >= 6:
            bat_advice = f"Need to build platform. Target par score of {int(venue_avg)}. Keep wickets for death overs assault."
            bat_approach = "controlled_aggression"
        else:
            bat_advice = f"Wickets falling. Consolidate and aim for {int(venue_avg - 10)}. Protect remaining batters."
            bat_approach = "consolidate"
    else:  # death
        if wkts_hand >= 5:
            bat_advice = f"Wickets in hand! Go all out. Target {int(projected + 15)}+. Every ball is a scoring opportunity."
            bat_approach = "all_out_attack"
        elif wkts_hand >= 3:
            bat_advice = f"Calculated hitting. Target {int(projected + 5)}-{int(projected + 10)}. Pick the right bowlers to attack."
            bat_approach = "calculated_aggression"
        else:
            bat_advice = f"Tail exposed. Maximize every ball. Even {int(projected)} could be competitive on this pitch."
            bat_approach = "survival_plus"

    # Bowling advice (for the team bowling)
    if phase == "powerplay":
        bowl_advice = "Use new ball well. Target early wickets to put pressure. Swing/seam conditions are best now."
        if dew != "minimal":
            bowl_advice += " Ball is dry -- take advantage before dew sets in."
    elif phase == "middle":
        if wickets >= 3:
            bowl_advice = f"Batters under pressure at {runs}/{wickets}. Keep building dot ball pressure. Spinners should dominate."
        else:
            bowl_advice = "Need breakthrough. Mix up pace and spin. Use variations -- slower balls, wide yorkers."
        if dew == "heavy":
            bowl_advice += " DEW WARNING: Grip getting difficult. Prefer pace over spin."
    else:
        if wickets >= 7:
            bowl_advice = "Almost done. Keep it tight, no freebies. Tail-enders -- target the stumps."
        else:
            bowl_advice = f"Critical phase! {10 - wickets} batters still in. Yorkers and slower balls. No width outside off."
            if dew == "heavy":
                bowl_advice += " Heavy dew -- execute yorkers, avoid spin, pace variations only."

    return {
        "win_probability": win_prob,
        "situation": "above_par" if delta > 5 else "par" if delta > -5 else "below_par",
        "projected_score": round(projected),
        "par_score": round(venue_avg),
        "phase": phase,
        "batting_plan": {
            "approach": bat_approach,
            "advice": bat_advice,
            "target_score": round(max(projected, venue_avg)),
            "current_rr": round(curr_rr, 2),
            "required_rr_for_par": round((venue_avg - runs) / max(overs_rem, 0.1), 2),
        },
        "bowling_plan": {
            "advice": bowl_advice,
            "dot_ball_target": "60%+" if phase == "middle" else "40%+",
            "priority": "wickets" if wickets < 3 else "containment",
        },
        "weather_impact": f"Dew: {dew}" + (". Ball grip reducing." if dew != "minimal" else ""),
    }


def _second_innings_plan(runs, wickets, overs, over_num, overs_rem, wkts_hand,
                          curr_rr, target, phase, dew, win_prob):
    remaining_runs = target - runs
    req_rr = remaining_runs / max(overs_rem, 0.1)
    rr_diff = curr_rr - req_rr

    chase_prob = win_prob.get("batting_team_win_prob", 50)

    # Batting (chasing team) advice
    if chase_prob > 75:
        bat_advice = f"In control! Need {remaining_runs} from {int(overs_rem * 6)} balls at {req_rr:.1f} RR. Don't panic, rotate strike."
        bat_approach = "controlled"
    elif chase_prob > 55:
        if wkts_hand >= 7:
            bat_advice = f"Slight edge. {remaining_runs} needed at {req_rr:.1f}. Wickets in hand -- pick your moments to attack."
            bat_approach = "positive"
        else:
            bat_advice = f"Tight chase. {remaining_runs} off {int(overs_rem * 6)} balls. Be smart -- singles and rotate, boundaries on bad balls."
            bat_approach = "calculated"
    elif chase_prob > 35:
        bat_advice = f"Under pressure! Need {remaining_runs} at {req_rr:.1f} -- above current rate of {curr_rr:.1f}. Must accelerate NOW."
        bat_approach = "aggressive"
    else:
        bat_advice = f"Deep trouble. {remaining_runs} needed at {req_rr:.1f} with {wkts_hand} wickets. Need boundaries every over to survive."
        bat_approach = "all_out"

    if dew == "heavy":
        bat_advice += " Dew helps you -- ball coming on nicely, use it."

    # Bowling (defending team) advice
    defend_prob = 100 - chase_prob
    if defend_prob > 70:
        bowl_advice = f"Dominant position. Keep building pressure. {remaining_runs} is too many at this rate."
        bowl_priority = "containment"
    elif defend_prob > 45:
        bowl_advice = f"One wicket changes everything. Attack the stumps. {wkts_hand} wickets left -- target the middle order."
        bowl_priority = "wickets"
    else:
        bowl_advice = f"Losing grip! Need wickets urgently. Aggressive field, bouncers, yorkers. Make every ball count."
        bowl_priority = "desperation_attack"

    if dew == "heavy":
        bowl_advice += " DEW is your enemy. Stick to pace, avoid spin. Yorkers are key."

    return {
        "win_probability": win_prob,
        "chase_status": "ahead" if rr_diff > 0.5 else "on_track" if rr_diff > -0.5 else "behind",
        "runs_needed": remaining_runs,
        "balls_remaining": int(overs_rem * 6),
        "required_rate": round(req_rr, 2),
        "current_rate": round(curr_rr, 2),
        "phase": phase,
        "batting_plan": {
            "approach": bat_approach,
            "advice": bat_advice,
        },
        "bowling_plan": {
            "advice": bowl_advice,
            "priority": bowl_priority,
        },
        "weather_impact": f"Dew: {dew}" + (". Batting advantage." if dew == "heavy" else ""),
    }
