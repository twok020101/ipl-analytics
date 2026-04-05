# Stumpline — Product Documentation

## Overview

Stumpline is a B2B cricket analytics SaaS platform designed for IPL team management and analysts. It provides data-driven match strategy, win prediction, team selection, and live game planning powered by machine learning and AI.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TanStack Query |
| Backend | Python FastAPI, SQLAlchemy, XGBoost, scikit-learn |
| Database | PostgreSQL (production via Railway), SQLite (local dev) |
| AI | Google Gemini 3 Flash with Search grounding |
| External Data | CricAPI (cricketdata.org) — fixtures, squads, live scores, scorecards |
| Weather | Open-Meteo API (free, no key) — dew, rain, humidity |
| Auth | Custom JWT with bcrypt (in-house, no external dependency) |
| Monorepo | Turborepo (apps/web + apps/api) |
| Deployment | Railway (backend) + Vercel (frontend) |
| Domains | ipl-api.thetwok.in (API), ipl.thetwok.in (frontend) |

## Data Sources

### Historical Data (2008-2025)
- **Source**: [IPL Dataset 2008-2025](https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025) by chaitu20 on Kaggle
- **Size**: 278,205 ball-by-ball deliveries across 1,169 matches, 18 seasons
- **Tables**: teams (15), players (966), venues (59), matches (1,239), deliveries (278K), player_season_batting (2,783), player_season_bowling (2,076), batter_vs_bowler (29,533), venue_stats (59)

### Live IPL 2026 Data
- **Source**: CricAPI (cricketdata.org) with API key
- **Data**: 70 fixtures, 10 team squads (256 players), live scores, scorecards
- **Refresh**: Auto-syncs completed match results daily at 2 AM IST + on page visit
- **API Limit**: 10,000 calls/day (paid plan)

### Weather Data
- **Source**: Open-Meteo API (free, no API key needed)
- **Coverage**: 13 IPL venue cities with coordinates
- **Data**: Temperature, humidity, dew point, precipitation, wind speed, cloud cover
- **Cricket Impact**: Dew factor analysis (heavy/moderate/minimal), rain risk, toss recommendation adjustments

## Architecture

### Backend (apps/api/)

```
app/
├── main.py                    # FastAPI app, CORS, lifespan, background sync
├── config.py                  # Settings (env vars), DATA_DIR, MODEL_DIR
├── database.py                # SQLAlchemy engine (SQLite + PostgreSQL dual support)
├── models/models.py           # ORM: Team, Player, Venue, Match, Delivery, User, Org + enums
├── api/                       # REST endpoints
│   ├── auth.py                # POST /register, /login, GET /me (JWT)
│   ├── analysis.py            # POST /analysis/match (comprehensive single-call, injury-aware)
│   ├── live.py                # GET /live/scores, /match/{id}, POST /sync, /poll, /predict
│   ├── strategy.py            # POST /playing-11, /toss-decision, /game-plan, /live-update, GET /rules
│   ├── teams.py, players.py, venues.py, headtohead.py, predictions.py
│   ├── season.py              # Standings with NRR (cricket overs notation)
│   ├── dashboard.py           # Stats overview
│   ├── external.py            # CricAPI proxy (fixtures, squads)
│   ├── visualizations.py      # Partnerships, run distribution, wicket types, player compare
│   ├── cron.py                # Railway cron endpoints (refresh squads, sync results)
│   └── ai_insights.py         # Gemini AI chat, match preview, player report
├── services/
│   ├── auth.py                # JWT creation/verification, bcrypt password hashing
│   ├── gemini.py              # Gemini 3 Flash with Google Search grounding
│   ├── weather.py             # Open-Meteo API, 13 venue coordinates, dew/rain analysis
│   ├── live_tracker.py        # CricAPI cricScore polling, ML prediction, game plan
│   ├── match_sync.py          # Auto-sync completed results to DB + fixture cache
│   ├── game_plan_live.py      # Dynamic tactical advice based on current score
│   ├── external_api.py        # CricAPI integration (series, squads, scorecards)
│   ├── cricapi_utils.py       # Shared score parsing, team name extraction
│   ├── stats.py               # Aggregate stats (team, player, venue, H2H)
│   └── form.py                # EWMA form index calculation
├── ml/
│   ├── strategy_engine.py     # Playing 11 selection (injury-aware), toss, game plan, live update (1,500+ lines)
│   ├── win_probability.py     # XGBoost pre-match model + heuristic fallback
│   ├── features.py            # 11 basic match features
│   ├── features_v2.py         # 38 advanced features (rolling stats, phase-wise, H2H)
│   ├── features_v3.py         # 62 features (V2 + 24 squad composition features)
│   ├── train.py               # Basic model training
│   ├── train_v2.py            # Advanced model training with time-based splits
│   └── train_v3.py            # V3 training with squad features + V2 comparison
├── ingestion/
│   ├── load_csv.py            # IPL.csv → normalized relational tables
│   ├── load_ipl2026.py        # CricAPI data → DB (fixtures, players, venues)
│   ├── fix_player_mapping.py  # Map CricAPI names to historical DB names
│   └── team_mappings.py       # Franchise rename mappings
├── data/
│   ├── ipl2026.json           # Cached fixtures + squads from CricAPI
│   └── team_squads_2026.json  # Team → player_ids + captain_id mapping
└── trained_models/
    ├── live_win_probability.joblib  # 1st + 2nd innings XGBoost models
    ├── win_probability_v2.joblib   # Advanced pre-match model (reference)
    └── win_probability_v3.joblib   # V3: squad composition features (62 features)
```

### Frontend (apps/web/)

```
src/
├── app/
│   ├── page.tsx               # Dashboard: IPL 2026 banner, upcoming fixtures, stats, quick predict
│   ├── live/page.tsx          # Live: real-time scores, ML win prob, game plan, weather
│   ├── fixtures/page.tsx      # IPL 2026: all fixtures, squads, results
│   ├── predict/page.tsx       # Match Analyzer: comprehensive analysis (5 tabs)
│   ├── standings/page.tsx     # Points table with NRR
│   ├── teams/page.tsx         # Team listing
│   ├── teams/[teamSlug]/      # Team profile with stats
│   ├── players/page.tsx       # Player search/filter
│   ├── players/[playerId]/    # Player profile with spider chart, form, run dist, dismissals
│   ├── head-to-head/page.tsx  # Team vs team, batter vs bowler, player compare (side-by-side)
│   ├── venues/page.tsx        # Venue listing
│   ├── venues/[venueId]/      # Venue intelligence
│   ├── ai-insights/page.tsx   # Chat with Gemini AI
│   ├── login/page.tsx         # JWT auth login/register
│   └── layout.tsx             # Sidebar nav (mobile drawer + desktop), auth gate, dark theme
├── components/
│   ├── charts/                # WinProbGauge, SpiderChart, FormLineChart, RunRateBar, ManhattanChart, WagonWheel, PitchMap, PartnershipBars
│   ├── cards/                 # StatCard, PlayerCard, MatchCard
│   ├── tables/                # DataTable (sortable, filterable, paginated)
│   └── ui/                    # shadcn/ui primitives
└── lib/
    ├── api.ts                 # Typed fetch wrapper, all API functions, BASE_URL
    ├── auth.tsx               # AuthProvider context, JWT token management
    ├── types.ts               # TypeScript interfaces matching API responses
    └── utils.ts               # cn(), team colors, formatters
```

## ML Models

### In-Match Win Probability (Production)
- **1st Innings Model**: 60.3% accuracy, 0.666 AUC-ROC
  - Features: runs, wickets, over, run rate, projected score, venue avg, above par
  - Predicts batting-first team's win probability during their innings
- **2nd Innings Model**: 80.1% accuracy, 0.884 AUC-ROC
  - Features: runs, wickets, over, target, required rate, current rate, wickets remaining
  - Required run rate is the dominant feature (39.4% importance)
  - Predicts chasing team's win probability

### Pre-Match Prediction
- Pre-match T20 prediction is fundamentally ~50% (coin flip) due to high in-game variance
- Heuristic fallback used: weighted combination of win rate, form, H2H, venue, toss
- The real value is in strategy (playing 11, game plan) not pre-match prediction

## IPL 2026 Rules Enforced

| Rule | Implementation |
|------|---------------|
| Max 4 overseas in XI | Enforced in select_playing_11 |
| Max 4 overs per bowler | Enforced in bowling plan + constants |
| Captain always plays | Step 0 in selection algorithm |
| 5 bowling options minimum | Constraint + swap logic |
| 1-2 wicket-keepers | Ensured in selection |
| Impact player (12th man) | Separate bat-first/bowl-first recommendations |
| No consecutive overs by same bowler | Alternating bowler logic |
| DRS, strategic timeout, super over | Documented in GET /strategy/rules |

## Strategy Engine

### Playing 11 Selection
1. Captain always selected first
2. Minimum 1 WK ensured
3. Minimum 5 bowling options (5 x 4 overs = 20)
4. Maximum 4 overseas enforced
5. Scoring: career stats + venue performance + opposition matchups + recent form
6. Experience multiplier: 0 IPL innings = 0.4x, 80+ innings = 1.15x
7. Impact player options for both bat-first and bowl-first scenarios
8. **Injury-aware**: Gemini AI fetches real-time player fitness; injured/ruled-out players are automatically excluded from selection
9. **Accuracy**: 10/11 correct against actual LSG playing 11 (DC vs LSG, Apr 1 2026)

### Toss Recommendation
- Venue bat-first win %, avg 1st vs 2nd innings scores
- Team-specific batting-first vs chasing records
- Dew factor from weather (heavy dew = bat first)
- Per-team confidence percentage

### Game Plan
- Over-by-over bowling assignment (pace in PP, spin in middle, death specialists)
- Batting order with phase-wise strike rates (PP/middle/death)
- Key matchups to exploit (SR > 150) and avoid (SR < 100) from 29K batter-vs-bowler records
- Both innings scenarios: Team A bats first AND Team B bats first

### Live Game Plan Updates
- Weather-adjusted (dew affects spin bowling recommendations)
- Phase-aware tactical advice for both teams
- Score vs par comparison with acceleration/consolidation triggers

## Authentication

- Custom JWT (no external auth provider)
- Organizations + Users (multi-tenant B2B)
- Roles: admin, analyst, viewer
- bcrypt password hashing
- 24-hour token expiry
- Frontend: AuthProvider context, protected routes, auto-redirect to /login

## NRR Calculation

Accurate Net Run Rate computation:
1. **Primary**: Ball-by-ball deliveries (actual runs and overs from 278K records)
2. **Secondary**: Stored innings scores with cricket overs notation (19.4 = 19 overs 4 balls = 19.667 decimal)
3. **Fallback**: Estimated from result margin for matches without full score data
4. Toss data determines batting order for correct team attribution
5. Verified against official IPL standings (within 0.1 tolerance)

## Environment Variables

### Backend (Railway)
```
DATABASE_URL=postgresql://...     # Railway auto-injects
GEMINI_API_KEY=...                # Google Gemini 3 Flash
CRICAPI_KEY=...                   # CricAPI (10K daily calls)
JWT_SECRET=...                    # JWT signing secret
FRONTEND_URL=https://ipl.thetwok.in
```

### Frontend (Vercel)
```
NEXT_PUBLIC_API_URL=https://ipl-api.thetwok.in/api/v1
```

## API Endpoint Summary

| Category | Endpoints |
|----------|-----------|
| Auth | POST /register, /login, GET /me |
| Analysis | POST /analysis/match (comprehensive single-call) |
| Live | GET /scores, /match/{id}, /match/{id}/gameplan, POST /predict, /sync, /poll |
| Strategy | POST /playing-11, /toss-decision, /game-plan, /live-update, GET /rules |
| Teams | GET /teams, /teams/{slug}, /teams/{slug}/players |
| Players | GET /players, /players/{id}, /batting, /bowling, /form |
| H2H | GET /h2h/teams, /h2h/players |
| Venues | GET /venues, /venues/{id} |
| Seasons | GET /seasons, /seasons/{season}/standings |
| External | GET /fixtures, /fixtures/upcoming, /squads, /squads/{team}, POST /refresh |
| AI | POST /ai/match-preview, /ai/player-report, /ai/chat |
| Viz | GET /viz/partnerships/{match_id}, /viz/run-distribution/{id}, /viz/wicket-types/{id}, /viz/player-compare |
| Cron | POST /cron/refresh-squads, /cron/sync-results |
| Dashboard | GET /dashboard/stats |
