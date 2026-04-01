# IPL Analytics Pro

B2B cricket analytics platform for IPL teams — win prediction, team strategy, match analysis, and live game planning.

## Features

- **Match Analyzer** — Single-click full analysis: win probability, playing XI for both teams, toss strategy, matchup matrix, over-by-over game plan
- **IPL 2026 Live** — Current season fixtures, squads, standings with accurate NRR
- **Strategy Engine** — Playing XI selection (with IPL rules: max 4 overseas, impact player), toss recommendation based on pitch, batting order, bowling plan
- **Player Intelligence** — Phase-wise stats (powerplay/middle/death), batter vs bowler matchups, form tracking
- **AI Insights** — Gemini-powered match previews, player scouting reports, live news & fitness updates via Google Search grounding
- **Venue Intelligence** — Scoring patterns, pace vs spin effectiveness, chase records

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TanStack Query
- **Backend**: Python FastAPI, SQLAlchemy, XGBoost, scikit-learn
- **AI**: Google Gemini 3 Flash with Search grounding
- **Data**: CricAPI for live IPL 2026 data
- **Monorepo**: Turborepo

## Getting Started

```bash
# Install dependencies
npm install
cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Place IPL.csv in project root (see Data section below)

# Run data ingestion
cd apps/api && .venv/bin/python -m app.ingestion.load_csv
cd apps/api && .venv/bin/python -m app.ingestion.load_ipl2026
cd apps/api && .venv/bin/python -m app.ingestion.fix_player_mapping
cd apps/api && .venv/bin/python -m app.ml.train

# Start both services
npm run dev
```

Frontend: http://localhost:3000 | API: http://localhost:8000

## Data Attribution

The historical IPL ball-by-ball dataset (2008–2025) used in this project is sourced from:

**[IPL Dataset 2008-2025](https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025)** by [chaitu20](https://www.kaggle.com/chaitu20) on Kaggle.

This dataset contains 278,000+ ball-by-ball records across 1,169 IPL matches and is used under the terms provided on Kaggle.

Live IPL 2026 data (fixtures, squads, scorecards) is fetched from [CricAPI](https://cricketdata.org).

## License

Private — All rights reserved.
