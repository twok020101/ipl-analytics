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

// Visualization types
export interface Partnership {
  batter1: { id: number; name: string };
  batter2: { id: number; name: string };
  runs: number;
  balls: number;
  innings?: number;
}

export interface PartnershipData {
  match_id?: number;
  innings?: number;
  player_id?: number;
  player_name?: string;
  partnerships: Partnership[];
}

export interface RunDistributionZone {
  label: string;
  value: number;
  runs: number;
  pct: number;
}

export interface RunDistributionData {
  player_id: number;
  player_name: string;
  total_balls: number;
  distribution: RunDistributionZone[];
}

export interface WicketType {
  type: string;
  count: number;
  pct: number;
}

export interface WicketTypesData {
  player_id: number;
  player_name: string;
  mode: string;
  total: number;
  wicket_types: WicketType[];
}

export interface PlayerCompareStats {
  id: number;
  name: string;
  role: string | null;
  batting_style: string | null;
  bowling_style: string | null;
  teams: { name: string; short_name: string }[];
  batting: {
    matches: number;
    innings: number;
    runs: number;
    balls_faced: number;
    strike_rate: number;
    average: number;
    fours: number;
    sixes: number;
    fifties: number;
    hundreds: number;
    highest_score: number;
  };
  bowling: {
    innings: number;
    wickets: number;
    overs: number;
    runs_conceded: number;
    economy: number;
    average: number;
    four_wickets: number;
    five_wickets: number;
  };
  form_index: number;
  form_trend: string;
}

export interface PlayerCompareResult {
  player1: PlayerCompareStats;
  player2: PlayerCompareStats;
}

// --- App user (shared between auth context and admin API) ---

export type UserRole = "admin" | "analyst" | "viewer";

export interface AppUser {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  organization_id: number | null;
  organization_name: string | null;
  is_active: boolean;
  team_id: number | null;
  team_name: string | null;
}

// --- Live match types (shared between hook and live page) ---

export interface LiveScoreData {
  runs: number;
  wickets: number;
  overs: number;
}

export interface LiveWinProbability {
  [team: string]: number;
}

export interface LiveGamePlan {
  win_probability?: Record<string, unknown>;
  situation?: string;
  projected_score?: number;
  par_score?: number;
  phase?: string;
  chase_status?: string;
  runs_needed?: number;
  balls_remaining?: number;
  required_rate?: number;
  current_rate?: number;
  batting_plan?: {
    approach?: string;
    advice?: string;
    target_score?: number;
    current_rr?: number;
    required_rr_for_par?: number;
  };
  bowling_plan?: {
    advice?: string;
    dot_ball_target?: string;
    priority?: string;
  };
  weather_impact?: string;
}

export interface LiveWeatherData {
  available: boolean;
  city?: string;
  temperature?: number;
  humidity?: number;
  dew_point?: number;
  dew_factor?: string;
  precipitation_mm?: number;
  rain_risk?: string;
  wind_speed_kmh?: number;
  cloud_cover_pct?: number;
  impact?: string[];
  toss_recommendation_adjustment?: string | null;
}

export interface LiveHistorySnapshot {
  timestamp: string;
  win_probability?: LiveWinProbability;
  current_score?: LiveScoreData;
  innings?: number;
}

export interface LiveMatch {
  match_id: string;
  team1: string;
  team2: string;
  status: string;
  state: string;
  innings?: number;
  batting_team?: string;
  bowling_team?: string;
  current_score?: LiveScoreData;
  target?: number;
  first_innings_score?: LiveScoreData;
  win_probability?: LiveWinProbability;
  prediction_details?: Record<string, unknown>;
  game_plan?: LiveGamePlan;
  weather?: LiveWeatherData;
  history?: LiveHistorySnapshot[];
}

export interface LiveUpcomingMatch {
  match_id: string;
  team1: string;
  team2: string;
  datetime_gmt: string;
  status: string;
}

export interface LiveRecentResult {
  match_id: string;
  team1: string;
  team2: string;
  team1_score: LiveScoreData;
  team2_score: LiveScoreData;
  status: string;
}
