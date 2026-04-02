"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLiveScores } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Radio,
  Cloud,
  Droplets,
  Wind,
  Thermometer,
  TrendingUp,
  TrendingDown,
  Target,
  Shield,
  Swords,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { cn, getTeamColor, getTeamTextColor, getTeamBg } from "@/lib/utils";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useState, useEffect, useRef } from "react";

// ---- Types ----

interface ScoreData {
  runs: number;
  wickets: number;
  overs: number;
}

interface WinProbability {
  [team: string]: number;
}

interface GamePlan {
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

interface WeatherData {
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

interface LiveMatch {
  match_id: string;
  team1: string;
  team2: string;
  status: string;
  state: string;
  innings?: number;
  batting_team?: string;
  bowling_team?: string;
  current_score?: ScoreData;
  target?: number;
  first_innings_score?: ScoreData;
  win_probability?: WinProbability;
  prediction_details?: Record<string, unknown>;
  game_plan?: GamePlan;
  weather?: WeatherData;
  history?: HistorySnapshot[];
}

interface HistorySnapshot {
  timestamp: string;
  win_probability?: WinProbability;
  current_score?: ScoreData;
  innings?: number;
}

interface LiveScoresResponse {
  live: LiveMatch[];
  upcoming: { match_id: string; team1: string; team2: string; datetime_gmt: string; status: string }[];
  recent_results: { match_id: string; team1: string; team2: string; team1_score: ScoreData; team2_score: ScoreData; status: string }[];
  fetched_at: string;
}

// ---- Helpers ----

function getPhaseLabel(phase?: string) {
  switch (phase) {
    case "powerplay": return "Powerplay";
    case "middle": return "Middle Overs";
    case "death": return "Death Overs";
    default: return phase || "N/A";
  }
}

function getPhaseColor(phase?: string) {
  switch (phase) {
    case "powerplay": return "text-green-400 bg-green-500/10 border-green-500/30";
    case "middle": return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    case "death": return "text-red-400 bg-red-500/10 border-red-500/30";
    default: return "text-gray-400 bg-gray-500/10 border-gray-500/30";
  }
}

function timeAgo(isoString: string) {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ---- Components ----

function WinProbabilityBar({ team1, team2, winProb }: { team1: string; team2: string; winProb: WinProbability }) {
  const t1Prob = winProb[team1] ?? 50;
  const t2Prob = winProb[team2] ?? 50;
  const t1Color = getTeamColor(team1);
  const t2Color = getTeamColor(team2);

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm font-medium">
        <span className={getTeamTextColor(team1)}>{team1} {t1Prob.toFixed(1)}%</span>
        <span className={getTeamTextColor(team2)}>{t2Prob.toFixed(1)}% {team2}</span>
      </div>
      <div className="h-3 rounded-full overflow-hidden flex bg-gray-800">
        <div
          className="h-full transition-all duration-1000 ease-in-out rounded-l-full"
          style={{ width: `${t1Prob}%`, backgroundColor: t1Color }}
        />
        <div
          className="h-full transition-all duration-1000 ease-in-out rounded-r-full"
          style={{ width: `${t2Prob}%`, backgroundColor: t2Color }}
        />
      </div>
    </div>
  );
}

function LiveMatchCard({ match }: { match: LiveMatch }) {
  const score = match.current_score;
  const gp = match.game_plan;
  const phase = gp?.phase;

  return (
    <Card className="border-gray-700/50">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
            </span>
            <CardTitle className="text-base">
              <span className={getTeamTextColor(match.team1)}>{match.team1}</span>
              {" vs "}
              <span className={getTeamTextColor(match.team2)}>{match.team2}</span>
            </CardTitle>
          </div>
          {phase && (
            <span className={cn("text-xs font-medium px-2.5 py-1 rounded-full border", getPhaseColor(phase))}>
              {getPhaseLabel(phase)}
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">{match.status}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Score display */}
        <div className="grid grid-cols-2 gap-4">
          <div className={cn("rounded-lg p-3", getTeamBg(match.team1))}>
            <p className={cn("text-sm font-medium", getTeamTextColor(match.team1))}>{match.team1}</p>
            {match.innings === 1 && match.batting_team === match.team1 && score ? (
              <p className="text-2xl font-bold">{score.runs}/{score.wickets} <span className="text-sm text-muted-foreground">({score.overs})</span></p>
            ) : match.first_innings_score && match.bowling_team === match.team1 ? (
              <p className="text-2xl font-bold">{match.first_innings_score.runs}/{match.first_innings_score.wickets} <span className="text-sm text-muted-foreground">({match.first_innings_score.overs})</span></p>
            ) : match.innings === 2 && match.batting_team === match.team1 && score ? (
              <p className="text-2xl font-bold">{score.runs}/{score.wickets} <span className="text-sm text-muted-foreground">({score.overs})</span></p>
            ) : (
              <p className="text-lg text-muted-foreground">Yet to bat</p>
            )}
          </div>
          <div className={cn("rounded-lg p-3", getTeamBg(match.team2))}>
            <p className={cn("text-sm font-medium", getTeamTextColor(match.team2))}>{match.team2}</p>
            {match.innings === 1 && match.batting_team === match.team2 && score ? (
              <p className="text-2xl font-bold">{score.runs}/{score.wickets} <span className="text-sm text-muted-foreground">({score.overs})</span></p>
            ) : match.first_innings_score && match.bowling_team === match.team2 ? (
              <p className="text-2xl font-bold">{match.first_innings_score.runs}/{match.first_innings_score.wickets} <span className="text-sm text-muted-foreground">({match.first_innings_score.overs})</span></p>
            ) : match.innings === 2 && match.batting_team === match.team2 && score ? (
              <p className="text-2xl font-bold">{score.runs}/{score.wickets} <span className="text-sm text-muted-foreground">({score.overs})</span></p>
            ) : (
              <p className="text-lg text-muted-foreground">Yet to bat</p>
            )}
          </div>
        </div>

        {/* Win probability bar */}
        {match.win_probability && (
          <WinProbabilityBar team1={match.team1} team2={match.team2} winProb={match.win_probability} />
        )}

        {/* Chase info for 2nd innings */}
        {match.innings === 2 && gp && (
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-gray-800/50 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Need</p>
              <p className="text-lg font-bold text-foreground">{gp.runs_needed}</p>
              <p className="text-xs text-muted-foreground">from {gp.balls_remaining}b</p>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Req. RR</p>
              <p className={cn("text-lg font-bold", (gp.required_rate ?? 0) > 10 ? "text-red-400" : (gp.required_rate ?? 0) > 8 ? "text-amber-400" : "text-green-400")}>
                {gp.required_rate?.toFixed(2)}
              </p>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Curr. RR</p>
              <p className="text-lg font-bold text-foreground">{gp.current_rate?.toFixed(2)}</p>
            </div>
          </div>
        )}

        {/* 1st innings projected */}
        {match.innings === 1 && gp && (
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-gray-800/50 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Projected</p>
              <p className="text-lg font-bold text-foreground">{gp.projected_score}</p>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Par</p>
              <p className="text-lg font-bold text-muted-foreground">{gp.par_score}</p>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Situation</p>
              <p className={cn("text-sm font-bold capitalize", gp.situation === "above_par" ? "text-green-400" : gp.situation === "below_par" ? "text-red-400" : "text-amber-400")}>
                {gp.situation?.replace("_", " ")}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GamePlanPanel({ match }: { match: LiveMatch }) {
  const gp = match.game_plan;
  if (!gp) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Batting Plan */}
      <Card className="border-green-500/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-green-400">
            <Swords className="h-4 w-4" />
            Batting Plan {match.batting_team && <Badge variant="outline" className="text-xs">{match.batting_team}</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {gp.batting_plan?.approach && (
            <Badge className="mb-2 capitalize" variant={
              gp.batting_plan.approach === "all_out_attack" || gp.batting_plan.approach === "all_out" || gp.batting_plan.approach === "aggressive"
                ? "destructive"
                : gp.batting_plan.approach === "controlled" || gp.batting_plan.approach === "consolidate"
                ? "success"
                : "warning"
            }>
              {gp.batting_plan.approach.replace(/_/g, " ")}
            </Badge>
          )}
          <p className="text-sm text-muted-foreground leading-relaxed">{gp.batting_plan?.advice}</p>
          {gp.batting_plan?.target_score && (
            <div className="mt-3 flex items-center gap-2 text-xs">
              <Target className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">Target: <span className="text-foreground font-medium">{gp.batting_plan.target_score}</span></span>
              {gp.batting_plan.current_rr && (
                <>
                  <span className="text-muted-foreground ml-2">RR: <span className="text-foreground font-medium">{gp.batting_plan.current_rr}</span></span>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Bowling Plan */}
      <Card className="border-blue-500/20">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-blue-400">
            <Shield className="h-4 w-4" />
            Bowling Plan {match.bowling_team && <Badge variant="outline" className="text-xs">{match.bowling_team}</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {gp.bowling_plan?.priority && (
            <Badge className="mb-2 capitalize" variant={
              gp.bowling_plan.priority === "desperation_attack" ? "destructive"
                : gp.bowling_plan.priority === "wickets" ? "warning"
                : "success"
            }>
              {gp.bowling_plan.priority.replace(/_/g, " ")}
            </Badge>
          )}
          <p className="text-sm text-muted-foreground leading-relaxed">{gp.bowling_plan?.advice}</p>
          {gp.bowling_plan?.dot_ball_target && (
            <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <span>Dot ball target: <span className="text-foreground font-medium">{gp.bowling_plan.dot_ball_target}</span></span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function WeatherPanel({ weather }: { weather: WeatherData }) {
  if (!weather?.available) return null;

  return (
    <Card className="border-cyan-500/20">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2 text-cyan-400">
          <Cloud className="h-4 w-4" />
          Weather at {weather.city}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="flex items-center gap-2">
            <Thermometer className="h-4 w-4 text-orange-400" />
            <div>
              <p className="text-xs text-muted-foreground">Temp</p>
              <p className="text-sm font-medium">{weather.temperature}°C</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Droplets className="h-4 w-4 text-blue-400" />
            <div>
              <p className="text-xs text-muted-foreground">Humidity</p>
              <p className="text-sm font-medium">{weather.humidity}%</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Wind className="h-4 w-4 text-gray-400" />
            <div>
              <p className="text-xs text-muted-foreground">Wind</p>
              <p className="text-sm font-medium">{weather.wind_speed_kmh} km/h</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Cloud className="h-4 w-4 text-gray-500" />
            <div>
              <p className="text-xs text-muted-foreground">Cloud</p>
              <p className="text-sm font-medium">{weather.cloud_cover_pct}%</p>
            </div>
          </div>
        </div>

        {/* Impact badges */}
        <div className="flex flex-wrap gap-2 mt-3">
          <Badge variant={weather.dew_factor === "heavy" ? "destructive" : weather.dew_factor === "moderate" ? "warning" : "success"}>
            Dew: {weather.dew_factor}
          </Badge>
          <Badge variant={weather.rain_risk === "high" ? "destructive" : weather.rain_risk === "moderate" ? "warning" : "success"}>
            Rain: {weather.rain_risk}
          </Badge>
          {weather.toss_recommendation_adjustment && (
            <Badge variant="warning">
              Toss adjust: {weather.toss_recommendation_adjustment.replace("_", " ")}
            </Badge>
          )}
        </div>

        {/* Impact statements */}
        {weather.impact && weather.impact.length > 0 && (
          <div className="mt-3 space-y-1">
            {weather.impact.map((imp, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-muted-foreground">
                <AlertTriangle className="h-3 w-3 text-amber-400 mt-0.5 shrink-0" />
                <span>{imp}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function WinProbChart({ match, history }: { match: LiveMatch; history: HistorySnapshot[] }) {
  const t1 = match.team1;
  const t2 = match.team2;
  const t1Color = getTeamColor(t1);
  const t2Color = getTeamColor(t2);

  // Build chart data from history + current
  const chartData: { over: number; [key: string]: number }[] = [];

  for (const snap of history) {
    if (snap.win_probability && snap.current_score) {
      chartData.push({
        over: snap.current_score.overs,
        [t1]: snap.win_probability[t1] ?? 50,
        [t2]: snap.win_probability[t2] ?? 50,
      });
    }
  }

  // Add current state
  if (match.win_probability && match.current_score) {
    const currentOver = match.current_score.overs;
    const alreadyHas = chartData.some((d) => d.over === currentOver);
    if (!alreadyHas) {
      chartData.push({
        over: currentOver,
        [t1]: match.win_probability[t1] ?? 50,
        [t2]: match.win_probability[t2] ?? 50,
      });
    }
  }

  if (chartData.length < 2) {
    // Add start point if we only have one
    if (chartData.length === 1) {
      chartData.unshift({ over: 0, [t1]: 50, [t2]: 50 });
    } else {
      return null;
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-primary" />
          Win Probability Over Time
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="over"
                stroke="#6B7280"
                tick={{ fontSize: 12 }}
                label={{ value: "Overs", position: "insideBottom", offset: -2, style: { fill: "#6B7280", fontSize: 11 } }}
              />
              <YAxis
                domain={[0, 100]}
                stroke="#6B7280"
                tick={{ fontSize: 12 }}
                label={{ value: "Win %", angle: -90, position: "insideLeft", style: { fill: "#6B7280", fontSize: 11 } }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151", borderRadius: "8px" }}
                labelStyle={{ color: "#9CA3AF" }}
                labelFormatter={(v) => `Over ${v}`}
              />
              <ReferenceLine y={50} stroke="#4B5563" strokeDasharray="3 3" />
              <Line type="monotone" dataKey={t1} stroke={t1Color} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey={t2} stroke={t2Color} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function UpcomingMatchCard({ match }: { match: { team1: string; team2: string; datetime_gmt: string; status: string } }) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-800/30 rounded-lg">
      <div>
        <p className="text-sm font-medium">
          <span className={getTeamTextColor(match.team1)}>{match.team1}</span>
          {" vs "}
          <span className={getTeamTextColor(match.team2)}>{match.team2}</span>
        </p>
        <p className="text-xs text-muted-foreground">{match.status}</p>
      </div>
      <Clock className="h-4 w-4 text-muted-foreground" />
    </div>
  );
}

function ResultCard({ match }: { match: { team1: string; team2: string; team1_score: ScoreData; team2_score: ScoreData; status: string } }) {
  return (
    <div className="p-3 bg-gray-800/30 rounded-lg">
      <div className="flex justify-between items-center">
        <div>
          <span className={cn("text-sm font-medium", getTeamTextColor(match.team1))}>{match.team1}</span>
          <span className="text-sm text-muted-foreground ml-2">{match.team1_score.runs}/{match.team1_score.wickets}</span>
        </div>
        <div>
          <span className={cn("text-sm font-medium", getTeamTextColor(match.team2))}>{match.team2}</span>
          <span className="text-sm text-muted-foreground ml-2">{match.team2_score.runs}/{match.team2_score.wickets}</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-1">{match.status}</p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-6">
        <Skeleton className="h-64 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    </div>
  );
}

// ---- Main Page ----

export default function LivePage() {
  const { data, isLoading, isError, dataUpdatedAt } = useQuery({
    queryKey: ["live-scores"],
    queryFn: fetchLiveScores,
    refetchInterval: 30000,
    refetchIntervalInBackground: true,
  });

  const scores = data as LiveScoresResponse | undefined;
  const liveMatches = scores?.live ?? [];
  const upcoming = scores?.upcoming ?? [];
  const results = scores?.recent_results ?? [];
  const hasLive = liveMatches.length > 0;

  // Accumulate win probability history client-side across polls
  const historyRef = useRef<Record<string, HistorySnapshot[]>>({});
  const seededRef = useRef<Record<string, boolean>>({});

  useEffect(() => {
    for (const match of liveMatches) {
      if (!match.win_probability || !match.current_score) continue;
      const id = match.match_id;
      if (!historyRef.current[id]) historyRef.current[id] = [];

      // Seed from server-side history on first load
      const serverHistory = match.history;
      if (serverHistory?.length && !seededRef.current[id]) {
        seededRef.current[id] = true;
        for (const snap of serverHistory) {
          if (snap.win_probability && snap.current_score) {
            const alreadyHas = historyRef.current[id].some(
              (s) => s.current_score?.overs === snap.current_score?.overs
            );
            if (!alreadyHas) historyRef.current[id].push(snap);
          }
        }
      }

      const snapshots = historyRef.current[id];
      const currentOver = match.current_score.overs;
      const last = snapshots[snapshots.length - 1];
      if (!last || (last.current_score && last.current_score.overs !== currentOver)) {
        snapshots.push({
          timestamp: new Date().toISOString(),
          win_probability: match.win_probability,
          current_score: match.current_score,
          innings: match.innings,
        });
        // Cap at 60 snapshots to match server-side deque limit
        if (snapshots.length > 60) snapshots.splice(0, snapshots.length - 60);
      }
    }
  }, [liveMatches]);

  if (isLoading) return <LoadingSkeleton />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Radio className="h-6 w-6 text-green-400" />
            Live Matches
            {hasLive && (
              <span className="relative flex h-2.5 w-2.5 ml-1">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
              </span>
            )}
          </h1>
          <p className="text-muted-foreground mt-1">
            Real-time scores, ML win probability, and tactical game plans
          </p>
        </div>
        {dataUpdatedAt > 0 && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            Updated {timeAgo(new Date(dataUpdatedAt).toISOString())}
            <span className="text-muted-foreground/50">| Auto-refresh 30s</span>
          </div>
        )}
      </div>

      {isError && (
        <Card className="border-red-500/30">
          <CardContent className="p-4">
            <p className="text-sm text-red-400">Failed to fetch live scores. Will retry automatically.</p>
          </CardContent>
        </Card>
      )}

      {/* Live matches */}
      {hasLive ? (
        <div className="space-y-8">
          {liveMatches.map((match) => (
            <div key={match.match_id} className="space-y-4">
              <LiveMatchCard match={match} />
              <GamePlanPanel match={match} />
              {match.weather && <WeatherPanel weather={match.weather} />}
              <WinProbChart match={match} history={historyRef.current[match.match_id] ?? []} />
            </div>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-8 text-center">
            <Radio className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-lg font-medium text-muted-foreground">No live matches right now</p>
            <p className="text-sm text-muted-foreground/70 mt-1">
              Live match tracking with ML predictions will appear here during IPL matches
            </p>
          </CardContent>
        </Card>
      )}

      {/* Upcoming and Recent Results */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {upcoming.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                <Clock className="h-4 w-4" />
                Upcoming
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {upcoming.map((m) => (
                <UpcomingMatchCard key={m.match_id} match={m} />
              ))}
            </CardContent>
          </Card>
        )}

        {results.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground">
                <TrendingDown className="h-4 w-4" />
                Recent Results
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {results.map((m) => (
                <ResultCard key={m.match_id} match={m} />
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
