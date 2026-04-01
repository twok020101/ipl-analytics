// Types matching actual backend API responses

export interface Team {
  id: number;
  name: string;
  short_name: string;
  is_active: boolean;
  slug: string;
  // Extended fields from /teams/{slug}
  seasons?: string[];
  stats?: TeamStats;
}

export interface TeamStats {
  team_id: number;
  team_name: string;
  matches: number;
  wins: number;
  losses: number;
  win_pct: number;
  toss_wins: number;
  avg_bat_first_score: number;
  avg_bat_second_score: number;
  recent_form: string[];
}

export interface Player {
  id: number;
  name: string;
  role: string | null;
  batting_style?: string | null;
  bowling_style?: string | null;
  teams?: { name: string; short_name: string }[];
  career_batting?: {
    matches: number;
    runs: number;
    balls_faced: number;
    strike_rate: number;
    seasons: number;
  };
  career_bowling?: {
    matches: number;
    wickets: number;
    seasons: number;
  };
  // Fields from team players list
  latest_season?: string;
  runs?: number;
  matches?: number;
  strike_rate?: number;
}

export interface PlayerBattingStats {
  season: string;
  matches: number;
  innings: number;
  runs: number;
  balls_faced: number;
  fours: number;
  sixes: number;
  strike_rate: number;
  average: number;
  highest_score: number;
  fifties: number;
  hundreds: number;
  not_outs: number;
}

export interface PlayerBowlingStats {
  season: string;
  matches: number;
  innings: number;
  overs_bowled: number;
  runs_conceded: number;
  wickets: number;
  economy: number;
  average: number;
  best_figures: string;
  four_wickets: number;
  five_wickets: number;
}

export interface PlayerForm {
  player_id: number;
  form_index: number;
  recent_innings: {
    runs: number;
    balls: number;
    strike_rate: number;
    weight: number;
  }[];
  trend: string;
}

export interface Venue {
  id: number;
  name: string;
  city: string;
  matches_played?: number;
}

export interface VenueStats {
  venue_id: number;
  venue_name: string;
  city: string;
  matches_played: number;
  avg_first_innings_score: number;
  avg_second_innings_score: number;
  bat_first_win_pct: number;
  highest_score: number;
  lowest_score: number;
}

export interface H2HTeamResult {
  team1: { id: number; name: string };
  team2: { id: number; name: string };
  total_matches: number;
  team1_wins: number;
  team2_wins: number;
  no_result: number;
  recent_matches: {
    date: string;
    season: string;
    winner: string;
    margin: string | null;
  }[];
}

export interface H2HPlayerResult {
  batter: { id: number; name: string };
  bowler: { id: number; name: string };
  balls: number;
  runs: number;
  dismissals: number;
  dots: number;
  fours: number;
  sixes: number;
  strike_rate: number;
  average: number | null;
}

export interface MatchPrediction {
  team1: { id: number; name: string; short_name: string };
  team2: { id: number; name: string; short_name: string };
  venue: string | null;
  prediction: {
    team1_prob: number;
    team2_prob: number;
    key_factors: { factor: string; impact: string }[];
  };
  model_trained: boolean;
}

export interface BattingOrderEntry {
  position: number;
  player_id: number;
  player_name: string;
  role: string;
  projected_runs: number;
  projected_sr: number;
  confidence: string;
}

export interface BowlingPhaseEntry {
  phase: string;
  overs_range: string;
  bowlers: {
    player_id: number;
    player_name: string;
    overs: number;
    expected_economy: number;
  }[];
}

export interface StrategyResponse {
  batting_order?: BattingOrderEntry[];
  bowling_plan?: BowlingPhaseEntry[];
  ai_explanation?: string;
}

export interface SeasonStanding {
  position: number;
  team_id: number;
  team_name: string;
  short_name: string;
  played: number;
  won: number;
  lost: number;
  no_result: number;
  points: number;
  nrr: number;
}

export interface Season {
  season: string;
  matches: number;
  start_date: string;
  end_date: string;
}

export interface AIResponse {
  // Match preview
  preview?: string;
  // Player report
  report?: string;
  // Chat
  question?: string;
  answer?: string;
  // Generic
  data?: Record<string, unknown>;
}

export interface DashboardStats {
  total_matches: number;
  total_players: number;
  total_venues: number;
  total_seasons: number;
  top_run_scorers: { name: string; runs: number; matches: number }[];
  top_wicket_takers: { name: string; wickets: number; matches: number }[];
}

export interface PaginatedResponse<T> {
  total: number;
  offset: number;
  limit: number;
  players: T[];
}

// IPL 2026 External Data
export interface Fixture {
  id: string;
  name: string;
  date: string;
  dateTimeGMT: string;
  venue: string;
  team1: string;
  team2: string;
  team1_name: string;
  team2_name: string;
  team1_img: string;
  team2_img: string;
  status: string;
  matchStarted: boolean;
  matchEnded: boolean;
}

export interface SquadPlayer {
  id: string;
  name: string;
  role: string;
  battingStyle?: string;
  bowlingStyle?: string;
  country: string;
  playerImg: string;
}

export interface Squad {
  name: string;
  short_name: string;
  img: string;
  players: SquadPlayer[];
}
