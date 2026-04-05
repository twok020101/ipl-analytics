"""Gemini AI integration for generating cricket insights."""

import json
from datetime import date
from google import genai
from google.genai import types

from app.config import settings
from typing import Optional, List

MODEL = "gemini-3-flash-preview"
_client = None


def _get_client():
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            return None
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _generate(prompt: str) -> str:
    client = _get_client()
    if client is None:
        return "Gemini API key not configured. Please set GEMINI_API_KEY in your .env file."
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error generating AI response: {str(e)}"


def _generate_with_search(prompt: str) -> str:
    """Generate content with Google Search grounding for live information."""
    client = _get_client()
    if client is None:
        return "Gemini API key not configured."
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"


def fetch_player_news(team_name: str, player_names: List[str]) -> dict:
    """Fetch latest news about player fitness, injuries, form for a team.

    Uses Gemini with Google Search grounding to get real-time information.
    Returns: { "team": str, "player_updates": [...], "conditions": str, "summary": str }
    """
    players_str = ", ".join(player_names[:15])  # top 15 players
    prompt = f"""You are an IPL cricket analyst. Search for the LATEST news (last 7 days) about these {team_name} players for IPL 2026:

Players: {players_str}

For each player where you find relevant news, report:
1. Fitness status (fit / doubtful / injured / ruled out)
2. Recent form or any notable performance
3. Any team selection hints from captain or coach

Also report:
- Current pitch/weather conditions if a match is today or tomorrow
- Any team news, squad changes, or tactical hints from press conferences

Respond in this EXACT JSON format (no markdown, just raw JSON):
{{
  "player_updates": [
    {{"name": "Player Name", "status": "fit/doubtful/injured/ruled_out", "news": "brief summary", "source": "source name"}},
  ],
  "team_news": "any team-level news about selection, strategy",
  "conditions": "pitch/weather conditions if available",
  "summary": "2-3 sentence overall summary for team selection impact"
}}

If no recent news found for a player, omit them. Only include players with actual news."""

    raw = _generate_with_search(prompt)

    # Parse JSON from response
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]
        result = json.loads(text.strip())
        result["team"] = team_name
        return result
    except (json.JSONDecodeError, Exception):
        return {
            "team": team_name,
            "player_updates": [],
            "team_news": raw[:500] if raw else "No news available",
            "conditions": "",
            "summary": "Could not parse structured news. Raw response available in team_news.",
        }


def generate_match_preview(
    team1_stats: dict,
    team2_stats: dict,
    venue_stats: Optional[dict],
    h2h_stats: dict,
) -> str:
    """Generate a narrative match preview using Gemini."""
    prompt = f"""You are an expert IPL cricket analyst. Generate a detailed, engaging match preview
based on the following data. Include win prediction reasoning, key matchups to watch,
and tactical insights.

Team 1 Stats:
{json.dumps(team1_stats, indent=2, default=str)}

Team 2 Stats:
{json.dumps(team2_stats, indent=2, default=str)}

Venue Stats:
{json.dumps(venue_stats, indent=2, default=str) if venue_stats else "Not available"}

Head-to-Head:
{json.dumps(h2h_stats, indent=2, default=str)}

Write a 300-400 word match preview with sections:
1. Overview
2. Key Stats Comparison
3. Venue Factor
4. Head-to-Head Edge
5. Prediction with reasoning
"""
    return _generate(prompt)


def generate_player_report(
    player_stats: dict, matchup_data: Optional[dict] = None
) -> str:
    """Generate a scouting report for a player."""
    prompt = f"""You are an expert IPL cricket scout. Generate a detailed scouting report
for the following player based on their stats.

Player Stats:
{json.dumps(player_stats, indent=2, default=str)}

Matchup Data:
{json.dumps(matchup_data, indent=2, default=str) if matchup_data else "Not available"}

Write a 200-300 word scouting report covering:
1. Strengths
2. Weaknesses
3. Best matchups
4. Tactical recommendation
5. Form assessment
"""
    return _generate(prompt)


def generate_strategy_explanation(
    batting_order: Optional[list],
    bowling_plan: Optional[list],
    context: Optional[dict] = None,
) -> str:
    """Generate explanation for a recommended strategy."""
    prompt = f"""You are an IPL cricket strategist. Explain the following recommended strategy
and why these choices make sense given the context.

Batting Order:
{json.dumps(batting_order, indent=2, default=str) if batting_order else "Not provided"}

Bowling Plan:
{json.dumps(bowling_plan, indent=2, default=str) if bowling_plan else "Not provided"}

Context:
{json.dumps(context, indent=2, default=str) if context else "Not provided"}

Write a 200-300 word strategy explanation covering:
1. Rationale for the order/plan
2. Key tactical advantages
3. Risk factors to watch
4. Phase-wise breakdown
"""
    return _generate(prompt)


def chat_analytics(question: str, context_data: Optional[dict] = None) -> str:
    """Answer a cricket analytics question using Gemini."""
    prompt = f"""You are an expert IPL cricket data analyst assistant. Answer the following question
using the provided data context. Be precise, use numbers when available, and provide
actionable insights.

IMPORTANT CONTEXT: Today's date is {date.today().strftime('%B %d, %Y')}. We are currently in the IPL {date.today().year} season.
Always reference IPL {date.today().year - 1} and {date.today().year} statistics, form, and news as your primary source.
Do NOT reference {date.today().year - 2} or earlier seasons as "recent" or "current" — those are historical.

Question: {question}

Data Context:
{json.dumps(context_data, indent=2, default=str) if context_data else "No specific match data provided - answer using IPL 2025-2026 knowledge and statistics"}

Provide a clear, data-driven answer in 100-200 words.
"""
    return _generate(prompt)
