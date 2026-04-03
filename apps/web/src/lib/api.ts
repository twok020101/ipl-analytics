import type {
  Team,
  Player,
  Venue,
  VenueStats,
  H2HTeamResult,
  H2HPlayerResult,
  MatchPrediction,
  StrategyResponse,
  SeasonStanding,
  Season,
  PlayerBattingStats,
  PlayerBowlingStats,
  PlayerForm,
  AIResponse,
  DashboardStats,
  PaginatedResponse,
  Fixture,
  Squad,
  PartnershipData,
  RunDistributionData,
  WicketTypesData,
  PlayerCompareResult,
  AppUser as AdminUser,
} from "./types";

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || (
  typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000/api/v1"
    : "https://ipl-api.thetwok.in/api/v1"
);

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("ipl_token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE_URL}${endpoint}`, { cache: "no-store", headers, ...options });
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("ipl_token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Teams
export const fetchTeams = () => fetchAPI<Team[]>("/teams");
export const fetchTeam = (slug: string) => fetchAPI<Team>(`/teams/${slug}`);
export const fetchTeamPlayers = (slug: string) => fetchAPI<Player[]>(`/teams/${slug}/players`);

// Players
export const fetchPlayers = (params?: {
  search?: string;
  role?: string;
  page?: number;
  per_page?: number;
}) => {
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set("search", params.search);
  if (params?.role && params.role !== "All") searchParams.set("role", params.role);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.per_page) searchParams.set("per_page", String(params.per_page));
  const qs = searchParams.toString();
  return fetchAPI<PaginatedResponse<Player>>(`/players${qs ? `?${qs}` : ""}`);
};
export const fetchPlayer = (id: number) => fetchAPI<Player>(`/players/${id}`);
export const fetchPlayerBatting = (id: number) =>
  fetchAPI<PlayerBattingStats[]>(`/players/${id}/batting`);
export const fetchPlayerBowling = (id: number) =>
  fetchAPI<PlayerBowlingStats[]>(`/players/${id}/bowling`);
export const fetchPlayerForm = (id: number) => fetchAPI<PlayerForm>(`/players/${id}/form`);

// Venues
export const fetchVenues = () => fetchAPI<Venue[]>("/venues");
export const fetchVenue = (id: number) => fetchAPI<Venue & VenueStats>(`/venues/${id}`);

// Head to Head
export const fetchH2HTeams = (team1: string, team2: string) =>
  fetchAPI<H2HTeamResult>(`/h2h/teams?team1=${encodeURIComponent(team1)}&team2=${encodeURIComponent(team2)}`);
export const fetchH2HPlayers = (batter: string, bowler: string) =>
  fetchAPI<H2HPlayerResult>(
    `/h2h/players?batter=${encodeURIComponent(batter)}&bowler=${encodeURIComponent(bowler)}`
  );

// Predictions
export const predictMatch = (data: {
  team1_id: number;
  team2_id: number;
  venue_id?: number;
  toss_winner_id?: number;
  toss_decision?: string;
}) => fetchAPI<MatchPrediction>("/predict/match", { method: "POST", body: JSON.stringify(data) });

export const predictPlayer = (data: { player_id: number; venue_id?: number; opposition_id?: number }) =>
  fetchAPI<{ player: { id: number; name: string }; projection: Record<string, unknown>; features: Record<string, unknown> }>(
    "/predict/player",
    { method: "POST", body: JSON.stringify(data) }
  );

// Strategy
export const getStrategy = (data: {
  squad_player_ids: number[];
  opposition_bowler_ids?: number[];
  venue_id?: number;
  include_ai_explanation?: boolean;
}) =>
  fetchAPI<StrategyResponse>("/strategy/batting-order", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const getBowlingPlan = (data: {
  squad_bowler_ids: number[];
  opposition_batter_ids?: number[];
  venue_id?: number;
  include_ai_explanation?: boolean;
}) =>
  fetchAPI<StrategyResponse>("/strategy/bowling-plan", {
    method: "POST",
    body: JSON.stringify(data),
  });

// AI
export const fetchAIMatchPreview = (data: {
  team1_id: number;
  team2_id: number;
  venue_id?: number;
}) =>
  fetchAPI<AIResponse>("/ai/match-preview", { method: "POST", body: JSON.stringify(data) });

export const fetchAIPlayerReport = (data: { player_id: number }) =>
  fetchAPI<AIResponse>("/ai/player-report", { method: "POST", body: JSON.stringify(data) });

export const fetchAIChat = (question: string) =>
  fetchAPI<AIResponse>("/ai/chat", { method: "POST", body: JSON.stringify({ question }) });

// Seasons
export const fetchSeasons = () => fetchAPI<Season[]>("/seasons");
export const fetchSeasonStandings = (season: string) =>
  fetchAPI<{ season: string; standings: SeasonStanding[] }>(`/seasons/${season}/standings`);

// Dashboard
export const fetchDashboardStats = () => fetchAPI<DashboardStats>("/dashboard/stats");

// Season Predictions
export interface SeasonPrediction {
  team_id: number;
  team_name: string;
  short_name: string;
  current_played: number;
  current_won: number;
  current_lost: number;
  current_points: number;
  current_nrr: number;
  strength_rating: number;
  playoff_pct: number;
  top_2_pct: number;
  winner_pct: number;
  avg_final_points: number;
  avg_final_position: number;
}

export interface SeasonPredictionResult {
  season: string;
  simulations: number;
  predictions: SeasonPrediction[];
  remaining_matches: number;
  completed_matches: number;
}

export const fetchSeasonPredictions = (season: string) =>
  fetchAPI<SeasonPredictionResult>(`/seasons/${season}/predictions`);

// Comprehensive Match Analysis
export const fetchMatchAnalysis = (data: { team1: string; team2: string; venue_id: number }) =>
  fetchAPI<Record<string, unknown>>("/analysis/match", { method: "POST", body: JSON.stringify(data) });

// Live Match Tracking
export const fetchLiveScores = () => fetchAPI<Record<string, unknown>>("/live/scores");
export const fetchLiveMatch = (id: string) => fetchAPI<Record<string, unknown>>(`/live/match/${id}`);
export const fetchLiveGamePlan = (id: string) => fetchAPI<Record<string, unknown>>(`/live/match/${id}/gameplan`);

// Post-match analysis
export interface WinProbPoint {
  innings: number;
  over: number;
  runs: number;
  wickets: number;
  bat_first_win_prob: number;
  bat_second_win_prob: number;
  runs_in_over?: number;
  wickets_in_over?: number;
  timestamp?: string;
}

export interface TurningPoint extends WinProbPoint {
  swing: number;
  favours: string;
  type: string;
  description: string;
}

export interface PostMatchAnalysis {
  match_id: number;
  season: string;
  date: string | null;
  bat_first: { id: number; name: string; short_name: string };
  bat_second: { id: number; name: string; short_name: string };
  winner: { id: number; name: string; short_name: string };
  result: string;
  first_innings_score: number;
  curve: WinProbPoint[];
  turning_points: TurningPoint[];
  total_overs: number;
  data_source: "ball_by_ball" | "live_snapshots";
  error?: string;
}

export const fetchPostMatchAnalysis = (matchId: number) =>
  fetchAPI<PostMatchAnalysis>(`/live/analysis/${matchId}`);

// External — IPL 2026

export const fetchFixtures = () => fetchAPI<Fixture[]>("/external/fixtures");
export const fetchUpcomingFixtures = (limit = 5) =>
  fetchAPI<Fixture[]>(`/external/fixtures/upcoming?limit=${limit}`);
export const fetchSquads = () => fetchAPI<Record<string, Squad>>("/external/squads");
export const fetchSquad = (team: string) => fetchAPI<Squad>(`/external/squads/${team}`);

// Visualizations

export const fetchPartnerships = (matchId: number, innings = 1) =>
  fetchAPI<PartnershipData>(`/viz/partnerships/${matchId}?innings=${innings}`);
export const fetchPlayerPartnerships = (playerId: number, limit = 10) =>
  fetchAPI<PartnershipData>(`/viz/partnerships/player/${playerId}?limit=${limit}`);
export const fetchRunDistribution = (playerId: number, season?: string) =>
  fetchAPI<RunDistributionData>(`/viz/run-distribution/${playerId}${season ? `?season=${season}` : ""}`);
export const fetchWicketTypes = (playerId: number, mode = "batter", season?: string) => {
  const params = new URLSearchParams({ mode });
  if (season) params.set("season", season);
  return fetchAPI<WicketTypesData>(`/viz/wicket-types/${playerId}?${params}`);
};
export const fetchPlayerCompare = (player1: number, player2: number) =>
  fetchAPI<PlayerCompareResult>(`/viz/player-compare?player1=${player1}&player2=${player2}`);

// --- Admin: User Management ---

export type { AdminUser };

export const fetchUsers = () => fetchAPI<AdminUser[]>("/auth/users");

export const updateUserRole = (userId: number, role: string) =>
  fetchAPI<AdminUser>(`/auth/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });

export const updateUserActive = (userId: number, isActive: boolean) =>
  fetchAPI<AdminUser>(`/auth/users/${userId}/active`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });

export const linkOrgToTeam = (teamId: number) =>
  fetchAPI<{ organization: string; team_id: number; team_name: string; short_name: string }>(
    "/auth/org/team",
    { method: "PATCH", body: JSON.stringify({ team_id: teamId }) },
  );

// --- Team-scoped dashboard ---

export interface MyTeamDashboard {
  team: { id: number; name: string; short_name: string };
  season_record: { played: number; won: number; lost: number; points: number };
  squad: { id: number; name: string; role: string; is_captain: boolean; country: string }[];
  squad_size: number;
  upcoming_matches: { match_id: number; opponent: string; date: string | null; venue: string | null }[];
  recent_results: { match_id: number; opponent: string; result: string; margin: string | null; date: string | null }[];
  top_batters: { name: string; runs: number; strike_rate: number }[];
  top_bowlers: { name: string; wickets: number; economy: number }[];
}

export const fetchMyTeamDashboard = () =>
  fetchAPI<MyTeamDashboard>("/dashboard/my-team");
