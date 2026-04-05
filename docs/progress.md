# Stumpline — Progress Log

## Session 1 (April 1, 2026)

### Phase 1: Foundation

- Initialized Turborepo monorepo with `apps/web` (Next.js) and `apps/api` (Python FastAPI)
- Ingested IPL.csv (278K ball-by-ball deliveries, 2008-2025) into normalized SQLite database
- Created ORM models: Team, Player, Venue, Match, Delivery, PlayerSeasonBatting, PlayerSeasonBowling, BatterVsBowler, VenueStats
- Team name normalization (Delhi Daredevils → Delhi Capitals, etc.)
- Pre-computed aggregate tables for fast queries
- Built all REST API endpoints (teams, players, venues, H2H, predictions, seasons, dashboard)
- Set up shadcn/ui dark theme frontend with sidebar navigation

### Phase 2: IPL 2026 Live Data

- Integrated CricAPI (cricketdata.org) for live IPL 2026 data
- Fetched 70 fixtures, 10 team squads (256 players with roles/styles/country)
- Ingested IPL 2026 data into database (matches, players, venues)
- Player name mapping: resolved CricAPI full names (Virat Kohli) to historical DB names (V Kohli) for 125+ players
- Fetched actual match scorecards for completed matches (scores, overs, toss data)

### Phase 3: Strategy Engine

- Built comprehensive strategy engine (1,500+ lines):
  - **Playing 11 selection**: Composite scoring (career stats + venue + matchups + experience), constraints (max 4 overseas, 5 bowling options, 1+ WK, captain always plays)
  - **Toss recommendation**: Venue bat-first %, team records, dew factor analysis
  - **Game plan**: Over-by-over bowling assignment, batting order with phase SR, matchup exploitation/avoidance
  - **Live updates**: Score vs par comparison, acceleration/consolidation triggers
- All IPL 2026 rules codified: 4 overs/bowler, impact player, DRS, strategic timeout, super over
- Captain constraint added for all 10 teams (correct captains verified)
- Experience-based scoring: 0 IPL innings = 0.4x penalty, 80+ innings = 1.15x bonus
- **Result**: 10/11 correct playing 11 prediction for LSG vs DC

### Phase 4: Comprehensive Match Analysis

- Single-endpoint analysis (`POST /analysis/match`) returning:
  - Win probability, H2H record, venue stats
  - Playing 11 for BOTH teams with role tags (WK/BAT/AR/BOWL)
  - Top batters with career/opposition/venue/phase stats + strengths/weaknesses
  - Top bowlers with phase economy + strengths/weaknesses
  - Matchup matrix (batter vs bowler) with threat levels
  - Toss recommendation for both teams
  - Latest player news/fitness from Gemini AI with Google Search grounding
- Frontend Match Analyzer page with 5 tabs (Overview, Team1, Team2, Matchups, Game Plan)
- Game plan shows both scenarios (Team A bats first / Team B bats first)

### Phase 5: NRR & Standings

- Accurate NRR from ball-by-ball deliveries (actual overs faced, not assumed 20)
- Cricket overs notation: 19.4 = 19 overs 4 balls = 19.667 decimal
- Toss data determines batting order for correct team attribution
- Fetched real scores from CricAPI scorecards for IPL 2026 completed matches
- Verified NRR within 0.1 tolerance of official IPL standings

### Phase 6: Auth & Deployment

- Custom JWT auth (no external dependency): Organization + User models, bcrypt, register/login/me
- PostgreSQL support (dual SQLite/PostgreSQL based on DATABASE_URL)
- Dockerfile for Railway, vercel.json for Vercel
- CORS configured for production domains
- GitHub repo: twok020101/ipl-analytics
- Railway deployment with PostgreSQL (all data seeded via psql COPY)
- Production domains: ipl-api.thetwok.in + ipl.thetwok.in

### Phase 7: Advanced ML Models (feature branch)

- **In-match XGBoost models** trained on 278K deliveries:
  - 1st innings: 60.3% accuracy, 0.666 AUC-ROC
  - 2nd innings: 80.1% accuracy, 0.884 AUC-ROC (required rate = 39.4% feature importance)
- Pre-match prediction confirmed as ~50% (inherent T20 variance) — heuristic fallback retained
- **Live match tracker**: Polls CricAPI cricScore (1 API call for ALL matches), runs ML models
- **Weather service**: Open-Meteo API, 13 venue coordinates, dew/rain impact on strategy
- **Dynamic game plan**: Phase-aware advice for both teams, weather-adjusted
- **Match auto-sync**: Completed results sync to DB + fixture cache (daily 2 AM IST + on visit)
- **Frontend live dashboard**: Auto-refreshing scores, win probability bars, game plan panels, weather cards
- **Code review cleanup**: Extracted shared utilities, cached ML models, bounded memory, centralized config

### Verified Against Real Match (DC vs LSG, April 1 2026)

- DC won toss, chose to bowl → Our model predicted: **FIELD** (correct)
- LSG 141 all out, DC chased 145/4 in 17.1 overs
- Live prediction during chase: DC 75.5% at 84/4 after 11 overs (correct — DC won)
- Playing 11 accuracy: 10/11 correct for LSG
- NRR: DC +0.893, matching official standings

---

## Session 2 (April 2, 2026)

### Phase 8: Frontend Polish & Mobile Responsiveness

- **Mobile sidebar**: Converted fixed sidebar to overlay drawer on mobile (lg breakpoint); added sticky mobile header with hamburger menu
- **Responsive grids**: All pages now use mobile-first grids (1 col → 2 → 3/4 cols)
- **Chart sizing**: Charts adapt to screen size (smaller heights on mobile)
- **Standings table**: Added horizontal scroll on mobile with min-width constraint
- **Dashboard**: Responsive banner, team logos, and fixture cards
- **Player profile**: Career stats always visible (was hidden on non-lg screens), responsive header layout
- **Bug fix**: Fixed duplicate "Matches" stat in venues page

### Phase 9: New Chart Visualizations

- **Scoring Distribution (Wagon Wheel)**: Donut chart showing balls faced by run type (dots, 1s, 2s, 3s, 4s, 6s) — stylized since no spatial data exists
- **Dismissal Types (Pitch Map)**: Horizontal bar chart showing how a batter gets out (caught, bowled, lbw, etc.) with color coding
- **Partnership Bars**: Horizontal bar chart showing batting partnerships with runs, balls, and strike rate per pair
- **Backend**: New `/viz` API endpoints — `/viz/run-distribution/{id}`, `/viz/wicket-types/{id}`, `/viz/partnerships/{match_id}`
- All charts integrated into player profile page

### Phase 10: Player Comparison Tool

- Added **"Compare Players"** tab to Head-to-Head page
- Side-by-side comparison with:
  - Spider charts for both players (Power, Consistency, SR, Form, Versatility, Experience)
  - Batting stats comparison with green highlighting for the better stat
  - Bowling stats comparison (if applicable)
  - Form index and trend indicators
- **Backend**: New `/viz/player-compare?player1=X&player2=Y` endpoint with full career aggregation

### Phase 11: Cron Endpoints for CricAPI Refresh

- Added `/cron/refresh-squads` — refreshes squad + fixture data from CricAPI (for Railway cron)
- Added `/cron/sync-results` — syncs completed match results to database
- Optionally secured via `X-Cron-Secret` header matching `JWT_SECRET`
- Railway cron can call these on any schedule (e.g., daily at 2 AM IST)

### Phase 12: V3 ML Model with Squad Composition Features

- Created `features_v3.py` with 12 squad composition features per team (24 total):
  - Batting: strength, SR, depth, power hitting
  - Bowling: strength, economy, depth
  - All-rounder factor, experience, star power (batter + bowler), squad size
- **Total features**: 62 (38 V2 + 24 squad)
- **V3 Test Accuracy**: 53.3% (up from V2's 48.0%, +5.3pp)
- Squad features contribute **34.0%** of total feature importance
- Top squad features: experience, batting SR, power hitting, star batter
- Trained with XGBoost (600 estimators, early stopping @ 60 rounds)
- Model saved as `win_probability_v3.joblib`

---

## Session 3 (April 3, 2026)

### Phase 13: Role-Based Access Control (RBAC)

- **Role hierarchy**: admin > analyst > viewer with dependency-injection guards
- **Protected endpoints**: strategy, analysis, AI (analyst+); user management (admin only)
- **Admin user management**: list org users, change roles, enable/disable accounts
- **Frontend**: nav items filtered by role, role badges in sidebar, admin user management page
- **Self-protection**: admins cannot demote or deactivate themselves

### Phase 14: Season Prediction (Monte Carlo)

- **Monte Carlo simulation**: 10,000 season outcomes per request
- **Team strength model**: weighted combination of win rate (50%), NRR (20%), recent form (30%)
- **Bradley-Terry match probability** with H2H adjustment for teams with 3+ historical meetings
- **Outputs per team**: playoff %, top-2 %, champion %, avg final points, avg final position
- **Endpoint**: `GET /seasons/{season}/predictions`
- **Frontend**: dedicated predictions page with probability bars, strength dots, color-coded cards
- Accessible via "Playoff Predictions" button on Standings page

### Phase 15: Post-Match Analysis with Turning Points

- **LiveSnapshot DB model**: persists over-by-over match state from live polling for post-match replay
- **Historical match analysis** (2008-2025): ball-by-ball replay through XGBoost, delivery-level turning points
- **IPL 2026 analysis**: reconstructed from LiveSnapshot records (over-by-over granularity)
- **Turning point detection**: flags overs where win probability swings >= 10%, classified as:
  - Wicket cluster (2+ wickets in an over)
  - Key dismissal (set batter with 25+ runs out)
  - Big over (15+ runs scored)
  - Momentum shift (general probability swing)
- **Endpoint**: `GET /live/analysis/{match_id}`
- **Frontend**: interactive Recharts area chart with turning point annotations, summary cards
- **Live tracker updated**: `record_snapshot()` now persists to LiveSnapshot table for future replay

### Phase 16: WebSocket for Live Scores

- **FastAPI WebSocket**: `/ws/live` endpoint with connection manager broadcasting to all clients
- **Background poll loop**: polls CricAPI every 30s during match windows, broadcasts to connected WS clients
- **Connection manager**: tracks connected clients, auto-removes dead connections, caches latest state
- **Frontend `useLiveScores` hook**: WebSocket-first with auto-reconnect (exponential backoff), HTTP polling fallback after 3 WS failures
- **Connection status indicator**: shows "Live" (WS), "Polling" (fallback), "Reconnecting..." states
- **Heartbeat**: client sends ping every 15s, server responds with pong

### Phase 17: Multi-Team Dashboard

- **Organization-team linking**: `Organization.team_id` FK to teams table; admin sets via `PATCH /auth/org/team`
- **Scoped dashboard**: `GET /dashboard/my-team` returns team-specific data:
  - Season record (W/L/Pts), squad list, upcoming matches, recent results
  - Top batters and bowlers from the team's squad
- **Frontend My Team page**: team command center with record stats, upcoming/results cards, squad grid with captain badge and overseas indicator
- **Auth context extended**: user object includes `team_id` and `team_name` from org
- **Nav item**: "My Team" appears for all logged-in users (shows setup prompt if no team linked)

### Phase 18: Mobile UI/UX Overhaul

- **Bottom tab navigation**: fixed bottom bar with 5 key items (Home, Live, Standings, Players, Analyze) — 44px touch targets
- **Safe area support**: `env(safe-area-inset-bottom)` padding for notched devices (iPhone)
- **Touch target enforcement**: CSS rule ensures minimum 44px height for all interactive elements on coarse pointer devices
- **Bottom padding**: main content gets extra `pb-20` on mobile to avoid overlap with bottom nav
- All new pages built mobile-first: card layouts, responsive grids, proper truncation

---

## What's Next (Planned)

### Short-term

- [x] Frontend polish: improve charts, mobile responsiveness
- [x] Add more graphical representations (wagon wheel, pitch map, partnership bars)
- [x] Player comparison tool (side-by-side stats)
- [x] Cron job for refreshing CricAPI squad data on new matches
- [x] Train ML model with player-level squad composition features

### Medium-term

- [x] Real-time score websocket (instead of 30s polling)
- [x] Post-match analysis with turning point identification
- [x] Season prediction (playoff qualifiers based on current standings)
- [x] Role-based access control (admin vs analyst vs viewer)
- [x] Multi-team dashboard (each team sees only their analysis)

### Long-term

- [ ] Historical match replay with win probability curve
- [ ] Player auction valuation model
- [ ] Fantasy team recommendation engine
- [ ] Integration with team video analysis tools
