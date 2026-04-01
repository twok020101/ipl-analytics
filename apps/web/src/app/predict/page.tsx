"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import {
  fetchTeams,
  fetchVenues,
  fetchUpcomingFixtures,
  fetchMatchAnalysis,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { WinProbGauge } from "@/components/charts/WinProbGauge";
import { cn, getTeamTextColor } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  Target,
  Zap,
  MapPin,
  Coins,
  Loader2,
  CalendarDays,
  Users,
  Swords,
  Shield,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  Activity,
  Newspaper,
} from "lucide-react";
import type { Fixture } from "@/lib/types";

/* ──────────────────────────── Types ──────────────────────────── */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://ipl-api.thetwok.in/api/v1";

async function fetchStrategy(endpoint: string, body: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/strategy/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

interface P11Player {
  player_id: number;
  name: string;
  role: string;
  batting_style: string;
  bowling_style: string;
  country: string;
  score: number;
  reasoning: string;
}

interface SquadComposition {
  wk: number;
  batters: number;
  allrounders: number;
  bowlers: number;
  overseas: number;
}

interface BatterCareer {
  matches: number;
  runs: number;
  avg: number;
  sr: number;
  "50s": number;
  "100s": number;
}

interface BatterVsOpp {
  matches: number;
  runs: number;
  avg: number;
  sr: number;
  dismissals_by: { bowler: string; times: number }[];
}

interface TopBatter {
  name: string;
  player_id: number;
  role: string;
  career: BatterCareer;
  vs_opposition: BatterVsOpp;
  at_venue: { matches: number; runs: number; avg: number; sr: number };
  phase_sr: { powerplay: number | null; middle: number | null; death: number | null };
  recent_form: { last_5_scores: number[]; form_index: number };
  strengths: string[];
  weaknesses: string[];
}

interface TopBowler {
  name: string;
  player_id: number;
  role: string;
  bowling_style: string;
  career: { matches: number; wickets: number; economy: number; avg: number; sr: number };
  vs_opposition: { wickets: number; economy: number };
  at_venue: { wickets: number; economy: number };
  phase_economy: { powerplay: number | null; middle: number | null; death: number | null };
  strengths: string[];
  weaknesses: string[];
}

interface TeamAnalysis {
  playing_11: P11Player[];
  impact_player_batting: P11Player | null;
  impact_player_bowling: P11Player | null;
  squad_composition: SquadComposition;
  top_batters: TopBatter[];
  top_bowlers: TopBowler[];
}

interface MatchupEntry {
  batter: string;
  batter_id: number;
  bowler: string;
  bowler_id: number;
  balls: number;
  runs: number;
  sr: number;
  dismissals: number;
  dots: number;
  boundaries: number;
  threat_level: string;
}

interface TossTeamRec {
  decision: string;
  confidence: number;
  reasoning: string[];
}

interface VenueStats {
  avg_first_innings: number;
  avg_second_innings: number;
  bat_first_win_pct: number;
  pace_wickets_pct: number;
  spin_wickets_pct: number;
  phase_averages: {
    powerplay: { avg_runs: number; avg_wickets: number; avg_rr: number };
    middle: { avg_runs: number; avg_wickets: number; avg_rr: number };
    death: { avg_runs: number; avg_wickets: number; avg_rr: number };
  };
  toss_bat_first_pct: number;
  highest_score: number;
  lowest_score: number;
}

interface AnalysisResponse {
  team1: { name: string; short_name: string };
  team2: { name: string; short_name: string };
  venue: { name: string; city: string; stats: VenueStats };
  head_to_head: { total_matches: number; team1_wins: number; team2_wins: number; recent_5: string[] };
  team1_news?: Record<string, unknown>;
  team2_news?: Record<string, unknown>;
  team1_analysis: TeamAnalysis;
  team2_analysis: TeamAnalysis;
  matchup_matrix: {
    team1_batters_vs_team2_bowlers: MatchupEntry[];
    team2_batters_vs_team1_bowlers: MatchupEntry[];
  };
  venue_analysis: VenueStats;
  toss_recommendation: { team1: TossTeamRec; team2: TossTeamRec };
  prediction: { team1_prob: number; team2_prob: number; key_factors: string[] };
}

// Game plan types
interface BattingEntry {
  position: number;
  name: string;
  role: string;
  phase_strengths: { pp_sr?: number | null; middle_sr?: number | null; death_sr?: number | null };
}
interface BowlingOver {
  over: number;
  bowler_name: string;
  phase: string;
  projected_economy: number;
  reason: string;
  danger_batters: { batter: string; sr: number }[];
}
interface GamePlanData {
  batting_order: BattingEntry[];
  bowling_plan: BowlingOver[];
  phase_targets: Record<string, { target_runs: number; target_wickets_max: number }>;
  key_matchups_exploit: { batter: string; bowler: string; sr: number; balls: number }[];
  key_matchups_avoid: { batter: string; bowler: string; sr: number; balls: number }[];
  bowling_phase_summary: Record<string, { bowlers: { name: string; economy: number | null }[]; strategy: string }>;
}

/* ──────────────────────── Helpers ──────────────────────── */

const roleOrder: Record<string, number> = {
  "WK-Batsman": 1, Batsman: 2, "Batting Allrounder": 3,
  "Bowling Allrounder": 4, Bowler: 5,
};

function roleTag(role: string) {
  if (role.includes("WK")) return { label: "WK", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" };
  if (role === "Batsman") return { label: "BAT", color: "bg-blue-500/15 text-blue-400 border-blue-500/20" };
  if (role === "Batting Allrounder") return { label: "BAT AR", color: "bg-purple-500/15 text-purple-400 border-purple-500/20" };
  if (role === "Bowling Allrounder") return { label: "BOWL AR", color: "bg-orange-500/15 text-orange-400 border-orange-500/20" };
  if (role === "Bowler") return { label: "BOWL", color: "bg-red-500/15 text-red-400 border-red-500/20" };
  return { label: role.substring(0, 6).toUpperCase(), color: "bg-gray-500/15 text-gray-400 border-gray-500/20" };
}

const PHASE_COLORS = { powerplay: "#4ade80", middle: "#60a5fa", death: "#f87171" };

function PhaseBarChart({ data, label }: { data: { phase: string; value: number | null }[]; label: string }) {
  const filtered = data.filter((d) => d.value != null && d.value > 0);
  if (filtered.length === 0) return null;
  return (
    <div className="w-full">
      <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
      <div className="h-[60px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={filtered} layout="vertical" margin={{ left: 2, right: 4, top: 0, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="phase" width={40} tick={{ fontSize: 9, fill: "#9ca3af" }} />
            <Tooltip
              contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8, fontSize: 11 }}
              formatter={(v: number) => [v.toFixed(1), label]}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={12}>
              {filtered.map((entry) => (
                <Cell key={entry.phase} fill={PHASE_COLORS[entry.phase as keyof typeof PHASE_COLORS] || "#9ca3af"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function threatBadge(level: string) {
  if (level === "high") return "bg-red-500/15 text-red-400 border-red-500/20";
  if (level === "medium") return "bg-amber-500/15 text-amber-400 border-amber-500/20";
  return "bg-green-500/15 text-green-400 border-green-500/20";
}

/* ──────────────────────── Main ──────────────────────── */

export default function PredictPageWrapper() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-muted-foreground">Loading...</div>}>
      <PredictPage />
    </Suspense>
  );
}

function PredictPage() {
  const searchParams = useSearchParams();
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
  const { data: venues } = useQuery({ queryKey: ["venues"], queryFn: fetchVenues });
  const { data: upcomingFixtures } = useQuery({
    queryKey: ["upcoming-fixtures-predict"],
    queryFn: () => fetchUpcomingFixtures(10),
  });

  const [team1, setTeam1] = useState("");
  const [team2, setTeam2] = useState("");
  const [venue, setVenue] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const autoRunDone = useRef(false);

  // Results
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [gpTeam1Bats, setGpTeam1Bats] = useState<GamePlanData | null>(null);
  const [gpTeam2Bats, setGpTeam2Bats] = useState<GamePlanData | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<"t1bats" | "t2bats">("t1bats");

  const activeTeams = (teams || []).filter((t) => t.is_active);
  const teamOptions = activeTeams.map((t) => ({ value: t.id.toString(), label: t.name }));
  const venueOptions = (venues || []).map((v) => ({
    value: v.id.toString(),
    label: `${v.name}${v.city ? `, ${v.city}` : ""}`,
  }));

  const selectedTeam1 = activeTeams.find((t) => t.id.toString() === team1);
  const selectedTeam2 = activeTeams.find((t) => t.id.toString() === team2);
  const today = new Date().toISOString().split("T")[0];

  // Auto-fill from query params (from fixtures page) and run analysis
  useEffect(() => {
    if (autoRunDone.current || !teams?.length || !venues?.length) return;
    const qTeam1 = searchParams.get("team1");
    const qTeam2 = searchParams.get("team2");
    const qVenue = searchParams.get("venue");
    const qAuto = searchParams.get("auto");

    if (qTeam1 && qTeam2) {
      const t1 = activeTeams.find((t) => t.short_name === qTeam1);
      const t2 = activeTeams.find((t) => t.short_name === qTeam2);
      if (t1) setTeam1(t1.id.toString());
      if (t2) setTeam2(t2.id.toString());

      if (qVenue) {
        const v = (venues || []).find(
          (v) => v.name === qVenue || qVenue.includes(v.name) || v.name.includes(qVenue.split(",")[0])
        );
        if (v) setVenue(v.id.toString());
      }

      if (qAuto === "true") {
        autoRunDone.current = true;
        setTimeout(() => {
          const btn = document.getElementById("analyze-btn");
          if (btn) btn.click();
        }, 300);
      }
    }
  }, [teams, venues, searchParams, activeTeams]);

  const selectFixture = (fix: Fixture) => {
    const t1 = activeTeams.find((t) => t.short_name === fix.team1);
    const t2 = activeTeams.find((t) => t.short_name === fix.team2);
    if (t1) setTeam1(t1.id.toString());
    if (t2) setTeam2(t2.id.toString());
    const v = (venues || []).find(
      (v) => fix.venue && (v.name === fix.venue || fix.venue.includes(v.name) || v.name.includes(fix.venue.split(",")[0]))
    );
    if (v) setVenue(v.id.toString());
    clearResults();
  };

  const clearResults = () => {
    setAnalysis(null);
    setGpTeam1Bats(null);
    setGpTeam2Bats(null);
  };

  const handleAnalyze = async () => {
    if (!selectedTeam1 || !selectedTeam2 || !venue) return;
    clearResults();
    setAnalyzing(true);

    const vid = Number(venue);
    const t1Short = selectedTeam1.short_name;
    const t2Short = selectedTeam2.short_name;

    try {
      // Single comprehensive API call
      const result = await fetchMatchAnalysis({ team1: t1Short, team2: t2Short, venue_id: vid }) as unknown as AnalysisResponse;
      setAnalysis(result);

      // Fetch game plans using player IDs from analysis
      if (result.team1_analysis?.playing_11 && result.team2_analysis?.playing_11) {
        const t1Ids = result.team1_analysis.playing_11.map((p) => p.player_id);
        const t2Ids = result.team2_analysis.playing_11.map((p) => p.player_id);

        const [gp1, gp2] = await Promise.allSettled([
          fetchStrategy("game-plan", {
            team: t1Short, playing_11: t1Ids,
            opposition: t2Short, opposition_11: t2Ids,
            venue_id: vid, batting_first: true,
          }),
          fetchStrategy("game-plan", {
            team: t2Short, playing_11: t2Ids,
            opposition: t1Short, opposition_11: t1Ids,
            venue_id: vid, batting_first: true,
          }),
        ]);

        if (gp1.status === "fulfilled") setGpTeam1Bats(gp1.value);
        if (gp2.status === "fulfilled") setGpTeam2Bats(gp2.value);
      }
    } catch (err) {
      console.error("Analysis failed:", err);
    }

    setAnalyzing(false);
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Target className="h-6 w-6 text-primary" />
          Match Analyzer
        </h1>
        <p className="text-muted-foreground mt-1">
          Select a match -- get comprehensive analysis, matchup matrix, and full game plan
        </p>
      </div>

      {/* IPL 2026 Fixture Picker */}
      {upcomingFixtures && upcomingFixtures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-4 w-4 text-primary" />
              IPL 2026 -- Pick a Match
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {upcomingFixtures.map((fix) => {
                const isToday = fix.date === today;
                return (
                  <button
                    key={fix.id}
                    onClick={() => selectFixture(fix)}
                    className={cn(
                      "shrink-0 rounded-lg border p-3 text-left transition-all hover:border-primary/50 hover:bg-primary/5 min-w-[180px]",
                      isToday ? "border-amber-500/40 bg-amber-500/5" : "border-gray-800 bg-gray-900"
                    )}
                  >
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
                      <CalendarDays className="h-3 w-3" />
                      {new Date(fix.dateTimeGMT + "Z").toLocaleDateString([], { month: "short", day: "numeric" })}
                      {isToday && <Badge className="bg-amber-500/20 text-amber-400 text-[10px] ml-1">Today</Badge>}
                    </div>
                    <div className="flex items-center gap-2">
                      {fix.team1_img && <img src={fix.team1_img} alt="" className="w-6 h-6 rounded" />}
                      <span className={cn("font-bold text-sm", getTeamTextColor(fix.team1))}>{fix.team1}</span>
                      <span className="text-xs text-muted-foreground">vs</span>
                      <span className={cn("font-bold text-sm", getTeamTextColor(fix.team2))}>{fix.team2}</span>
                      {fix.team2_img && <img src={fix.team2_img} alt="" className="w-6 h-6 rounded" />}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1 truncate">{fix.venue}</p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Team + Venue Selection */}
      <Card>
        <CardContent className="p-8">
          <div className="grid grid-cols-1 lg:grid-cols-7 gap-6 items-end">
            <div className="lg:col-span-2 space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Team 1</label>
              <Select options={teamOptions} placeholder="Select Team 1" value={team1} onChange={(e) => { setTeam1(e.target.value); clearResults(); }} />
            </div>
            <div className="flex items-center justify-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-cyan-500/20 border border-gray-700">
                <span className="text-base font-extrabold text-primary">VS</span>
              </div>
            </div>
            <div className="lg:col-span-2 space-y-2">
              <label className="text-sm font-medium text-muted-foreground">Team 2</label>
              <Select options={teamOptions.filter((t) => t.value !== team1)} placeholder="Select Team 2" value={team2} onChange={(e) => { setTeam2(e.target.value); clearResults(); }} />
            </div>
            <div className="lg:col-span-2 space-y-2">
              <label className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5" /> Venue
              </label>
              <Select options={venueOptions} placeholder="Select Venue" value={venue} onChange={(e) => { setVenue(e.target.value); clearResults(); }} />
            </div>
          </div>

          <div className="mt-8 flex justify-center">
            <Button
              id="analyze-btn"
              size="lg"
              className="px-12 text-base"
              disabled={!team1 || !team2 || !venue || analyzing}
              onClick={handleAnalyze}
            >
              {analyzing ? (
                <><Loader2 className="h-5 w-5 animate-spin mr-2" /> Analyzing Match...</>
              ) : (
                <><Zap className="h-5 w-5 mr-2" /> Analyze Match</>
              )}
            </Button>
          </div>
          {(!venue && team1 && team2) && (
            <p className="text-center text-xs text-amber-400 mt-2 flex items-center justify-center gap-1">
              <AlertTriangle className="h-3 w-3" /> Select a venue for full analysis
            </p>
          )}
        </CardContent>
      </Card>

      {/* Loading Skeleton */}
      {analyzing && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
          </div>
          <Skeleton className="h-64" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton className="h-40" />
            <Skeleton className="h-40" />
          </div>
        </div>
      )}

      {/* Results */}
      {analysis && !analyzing && (
        <Tabs defaultValue="overview">
          <TabsList className="flex-wrap">
            <TabsTrigger value="overview"><Activity className="h-4 w-4 mr-1.5" /> Overview</TabsTrigger>
            <TabsTrigger value="team1"><Shield className="h-4 w-4 mr-1.5" /> {analysis.team1.short_name}</TabsTrigger>
            <TabsTrigger value="team2"><Shield className="h-4 w-4 mr-1.5" /> {analysis.team2.short_name}</TabsTrigger>
            <TabsTrigger value="matchups"><Swords className="h-4 w-4 mr-1.5" /> Matchup Matrix</TabsTrigger>
            {(gpTeam1Bats || gpTeam2Bats) && (
              <TabsTrigger value="gameplan"><TrendingUp className="h-4 w-4 mr-1.5" /> Game Plan</TabsTrigger>
            )}
          </TabsList>

          {/* ═══════════════ TAB 1: OVERVIEW ═══════════════ */}
          <TabsContent value="overview">
            <div className="space-y-6">
              {/* Win Probability */}
              <Card className="overflow-hidden">
                <div className="bg-gradient-to-r from-primary/5 via-transparent to-cyan-500/5 p-8">
                  <h2 className="text-xl font-bold text-center mb-2">Win Probability</h2>
                  <WinProbGauge
                    team1={analysis.team1.short_name}
                    team2={analysis.team2.short_name}
                    team1Prob={analysis.prediction.team1_prob}
                    team2Prob={analysis.prediction.team2_prob}
                  />
                  <div className="mt-4 text-center">
                    <p className="text-sm text-muted-foreground">Predicted Winner</p>
                    <p className={cn("text-2xl font-bold", getTeamTextColor(
                      analysis.prediction.team1_prob >= analysis.prediction.team2_prob
                        ? analysis.team1.short_name
                        : analysis.team2.short_name
                    ))}>
                      {analysis.prediction.team1_prob >= analysis.prediction.team2_prob
                        ? analysis.team1.name
                        : analysis.team2.name}
                    </p>
                  </div>
                  <div className="mt-4 flex flex-wrap justify-center gap-2">
                    {(analysis.prediction.key_factors || []).map((kf, i) => (
                      <div key={i} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-800/50 text-xs">
                        <CheckCircle className="h-3 w-3 text-green-400" />
                        {kf}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>

              {/* H2H + Venue + Toss */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Head to Head */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Swords className="h-4 w-4 text-primary" /> Head to Head
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-center space-y-3">
                      <div className="flex items-center justify-center gap-4">
                        <div className="text-center">
                          <p className={cn("text-3xl font-bold", getTeamTextColor(analysis.team1.short_name))}>
                            {analysis.head_to_head.team1_wins}
                          </p>
                          <p className="text-xs text-muted-foreground">{analysis.team1.short_name}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm text-muted-foreground">in</p>
                          <p className="text-lg font-bold">{analysis.head_to_head.total_matches}</p>
                          <p className="text-xs text-muted-foreground">matches</p>
                        </div>
                        <div className="text-center">
                          <p className={cn("text-3xl font-bold", getTeamTextColor(analysis.team2.short_name))}>
                            {analysis.head_to_head.team2_wins}
                          </p>
                          <p className="text-xs text-muted-foreground">{analysis.team2.short_name}</p>
                        </div>
                      </div>
                      {/* Recent 5 dots */}
                      <div>
                        <p className="text-[10px] text-muted-foreground mb-1">Recent 5 (from {analysis.team1.short_name} perspective)</p>
                        <div className="flex justify-center gap-1.5">
                          {analysis.head_to_head.recent_5.map((r, i) => (
                            <span
                              key={i}
                              className={cn(
                                "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold",
                                r === "team1" ? "bg-green-500/20 text-green-400"
                                  : r === "team2" ? "bg-red-500/20 text-red-400"
                                  : "bg-gray-700 text-gray-400"
                              )}
                            >
                              {r === "team1" ? "W" : r === "team2" ? "L" : "-"}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Venue Summary */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-primary" /> {analysis.venue.name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Avg 1st Innings</span>
                        <span className="font-bold">{analysis.venue.stats.avg_first_innings.toFixed(0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Avg 2nd Innings</span>
                        <span className="font-bold">{analysis.venue.stats.avg_second_innings.toFixed(0)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Bat First Win %</span>
                        <span className="font-bold">{analysis.venue.stats.bat_first_win_pct.toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Highest / Lowest</span>
                        <span className="font-bold">{analysis.venue.stats.highest_score} / {analysis.venue.stats.lowest_score}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Pace / Spin</span>
                        <span className="font-bold text-xs">{analysis.venue.stats.pace_wickets_pct.toFixed(0)}% / {analysis.venue.stats.spin_wickets_pct.toFixed(0)}%</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Latest News & Player Fitness */}
                {(analysis.team1_news || analysis.team2_news) && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                      <Newspaper className="h-5 w-5 text-primary" />
                      Latest News & Player Fitness
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {[
                        { news: analysis.team1_news, team: analysis.team1.short_name },
                        { news: analysis.team2_news, team: analysis.team2.short_name },
                      ].map(({ news, team }) => {
                        if (!news) return null;
                        const updates = (news as Record<string, unknown>).player_updates as Array<{ name: string; status: string; news: string }> | undefined;
                        const teamNews = (news as Record<string, unknown>).team_news as string | undefined;
                        const conditions = (news as Record<string, unknown>).conditions as string | undefined;
                        const summary = (news as Record<string, unknown>).summary as string | undefined;
                        return (
                          <Card key={team}>
                            <CardHeader className="pb-3">
                              <CardTitle className="text-base">{team} — News & Updates</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                              {summary && (
                                <p className="text-sm text-muted-foreground italic">{summary}</p>
                              )}
                              {updates && updates.length > 0 && updates.map((u, i) => (
                                <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-gray-800/50">
                                  <div className={cn(
                                    "w-2 h-2 rounded-full shrink-0",
                                    u.status === "fit" ? "bg-green-500" :
                                    u.status === "doubtful" ? "bg-amber-500" :
                                    "bg-red-500"
                                  )} />
                                  <div className="flex-1 min-w-0">
                                    <span className="text-sm font-medium">{u.name}</span>
                                    <span className={cn(
                                      "text-xs ml-2 px-1.5 py-0.5 rounded",
                                      u.status === "fit" ? "bg-green-500/10 text-green-400" :
                                      u.status === "doubtful" ? "bg-amber-500/10 text-amber-400" :
                                      "bg-red-500/10 text-red-400"
                                    )}>{u.status}</span>
                                  </div>
                                  <p className="text-xs text-muted-foreground truncate max-w-[200px]">{u.news}</p>
                                </div>
                              ))}
                              {conditions && (
                                <div className="p-2 rounded-lg bg-blue-500/5 border border-blue-500/10">
                                  <p className="text-xs text-blue-400">Conditions: {conditions}</p>
                                </div>
                              )}
                              {teamNews && !updates?.length && (
                                <p className="text-xs text-muted-foreground">{typeof teamNews === 'string' ? teamNews.substring(0, 300) : ''}</p>
                              )}
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Toss Recommendations */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Coins className="h-4 w-4 text-amber-400" /> Toss Strategy
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {[
                        { team: analysis.team1, rec: analysis.toss_recommendation.team1 },
                        { team: analysis.team2, rec: analysis.toss_recommendation.team2 },
                      ].map(({ team, rec }) => (
                        <div key={team.short_name} className="p-3 rounded-lg bg-gradient-to-br from-amber-500/5 to-orange-500/5 border border-amber-500/10">
                          <div className="flex items-center justify-between">
                            <span className={cn("text-sm font-bold", getTeamTextColor(team.short_name))}>{team.short_name}</span>
                            <span className="text-amber-400 font-bold text-sm">{rec.decision.toUpperCase()} FIRST</span>
                          </div>
                          <span className="text-[10px] text-muted-foreground">{rec.confidence}% confidence</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Toss Reasoning */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[
                  { team: analysis.team1, rec: analysis.toss_recommendation.team1 },
                  { team: analysis.team2, rec: analysis.toss_recommendation.team2 },
                ].map(({ team, rec }) => (
                  <Card key={team.short_name}>
                    <CardContent className="p-4">
                      <p className="text-xs text-muted-foreground mb-2">
                        If <span className={cn("font-semibold", getTeamTextColor(team.short_name))}>{team.name}</span> wins the toss
                      </p>
                      <div className="space-y-1">
                        {rec.reasoning.map((r, i) => (
                          <div key={i} className="flex items-start gap-2 p-1.5 rounded bg-gray-800/50 text-xs">
                            <CheckCircle className="h-3 w-3 text-green-400 mt-0.5 shrink-0" />
                            <span>{r}</span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </TabsContent>

          {/* ═══════════════ TAB 2: TEAM 1 ANALYSIS ═══════════════ */}
          <TabsContent value="team1">
            <TeamAnalysisTab
              analysis={analysis.team1_analysis}
              teamName={analysis.team1.name}
              teamShort={analysis.team1.short_name}
            />
          </TabsContent>

          {/* ═══════════════ TAB 3: TEAM 2 ANALYSIS ═══════════════ */}
          <TabsContent value="team2">
            <TeamAnalysisTab
              analysis={analysis.team2_analysis}
              teamName={analysis.team2.name}
              teamShort={analysis.team2.short_name}
            />
          </TabsContent>

          {/* ═══════════════ TAB 4: MATCHUP MATRIX ═══════════════ */}
          <TabsContent value="matchups">
            <div className="space-y-8">
              <MatchupTable
                title={`${analysis.team1.short_name} Batters vs ${analysis.team2.short_name} Bowlers`}
                matchups={analysis.matchup_matrix.team1_batters_vs_team2_bowlers}
              />
              <MatchupTable
                title={`${analysis.team2.short_name} Batters vs ${analysis.team1.short_name} Bowlers`}
                matchups={analysis.matchup_matrix.team2_batters_vs_team1_bowlers}
              />

              {/* Key exploits and dangers */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                  <CardHeader><CardTitle className="text-green-400 text-sm">Key Exploits (SR &gt; 150)</CardTitle></CardHeader>
                  <CardContent className="space-y-1.5">
                    {[
                      ...analysis.matchup_matrix.team1_batters_vs_team2_bowlers,
                      ...analysis.matchup_matrix.team2_batters_vs_team1_bowlers,
                    ].filter((m) => m.sr > 150 && m.balls >= 6).sort((a, b) => b.sr - a.sr).slice(0, 8).map((m, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-green-500/5 border border-green-500/10 text-xs">
                        <span>{m.batter} vs {m.bowler}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">{m.balls}b, {m.runs}r</span>
                          <Badge className="bg-green-500/10 text-green-400 text-[10px]">SR {m.sr.toFixed(1)}</Badge>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader><CardTitle className="text-red-400 text-sm">Key Dangers (SR &lt; 100)</CardTitle></CardHeader>
                  <CardContent className="space-y-1.5">
                    {[
                      ...analysis.matchup_matrix.team1_batters_vs_team2_bowlers,
                      ...analysis.matchup_matrix.team2_batters_vs_team1_bowlers,
                    ].filter((m) => m.sr < 100 && m.balls >= 6).sort((a, b) => a.sr - b.sr).slice(0, 8).map((m, i) => (
                      <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-red-500/5 border border-red-500/10 text-xs">
                        <span>{m.batter} vs {m.bowler}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-muted-foreground">{m.balls}b, {m.dismissals}w</span>
                          <Badge className="bg-red-500/10 text-red-400 text-[10px]">SR {m.sr.toFixed(1)}</Badge>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* ═══════════════ TAB 5: GAME PLAN ═══════════════ */}
          {(gpTeam1Bats || gpTeam2Bats) && (
            <TabsContent value="gameplan">
              <div className="space-y-6">
                {/* Scenario Selector */}
                <div className="flex gap-2">
                  <Button
                    variant={selectedScenario === "t1bats" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedScenario("t1bats")}
                  >
                    {analysis.team1.short_name} Bats First
                  </Button>
                  <Button
                    variant={selectedScenario === "t2bats" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSelectedScenario("t2bats")}
                  >
                    {analysis.team2.short_name} Bats First
                  </Button>
                </div>

                {(() => {
                  const gp = selectedScenario === "t1bats" ? gpTeam1Bats : gpTeam2Bats;
                  const battingTeam = selectedScenario === "t1bats" ? analysis.team1 : analysis.team2;
                  const bowlingTeam = selectedScenario === "t1bats" ? analysis.team2 : analysis.team1;
                  if (!gp) return <Card><CardContent className="p-8 text-center text-muted-foreground">Game plan unavailable for this scenario</CardContent></Card>;

                  return (<>
                    {/* 1st Innings Header */}
                    <div className="flex items-center gap-2 px-1">
                      <div className="h-1 flex-1 bg-gradient-to-r from-amber-500/50 to-transparent rounded" />
                      <span className="text-sm font-bold text-amber-400">1st Innings -- {battingTeam.short_name} Batting</span>
                      <div className="h-1 flex-1 bg-gradient-to-l from-amber-500/50 to-transparent rounded" />
                    </div>

                    {/* Phase Targets */}
                    {gp.phase_targets && (
                      <Card>
                        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Target className="h-4 w-4 text-primary" />{battingTeam.short_name} Batting Targets</CardTitle></CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-3 gap-4">
                            {Object.entries(gp.phase_targets).map(([phase, targets]) => (
                              <div key={phase} className="text-center p-3 rounded-xl bg-gray-800/50">
                                <p className="text-xs font-medium capitalize text-muted-foreground">{phase}</p>
                                <p className="text-xl font-bold text-primary mt-1">{targets.target_runs}</p>
                                <p className="text-[10px] text-muted-foreground">max {targets.target_wickets_max} wkts</p>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Batting Order */}
                    <Card>
                      <CardHeader><CardTitle className="text-base"><Shield className="h-4 w-4 text-amber-400 inline mr-2" />{battingTeam.short_name} Batting Order</CardTitle></CardHeader>
                      <CardContent>
                        <div className="space-y-1.5">
                          {(gp.batting_order || []).map((b) => (
                            <div key={b.position} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-800/50">
                              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500/10 text-amber-400 text-xs font-bold">{b.position}</span>
                              <div className="flex-1">
                                <p className="font-medium text-sm">{b.name}</p>
                              </div>
                              <div className="flex gap-2 text-[10px]">
                                <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">PP {b.phase_strengths?.pp_sr != null ? Math.round(b.phase_strengths.pp_sr) : "-"}</span>
                                <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">Mid {b.phase_strengths?.middle_sr != null ? Math.round(b.phase_strengths.middle_sr) : "-"}</span>
                                <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">Death {b.phase_strengths?.death_sr != null ? Math.round(b.phase_strengths.death_sr) : "-"}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    {/* 2nd part: Bowling plan */}
                    <div className="flex items-center gap-2 px-1">
                      <div className="h-1 flex-1 bg-gradient-to-r from-green-500/50 to-transparent rounded" />
                      <span className="text-sm font-bold text-green-400">1st Innings -- {bowlingTeam.short_name} Bowling Plan</span>
                      <div className="h-1 flex-1 bg-gradient-to-l from-green-500/50 to-transparent rounded" />
                    </div>

                    {/* Bowling Phase Summary */}
                    {gp.bowling_phase_summary && (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {Object.entries(gp.bowling_phase_summary).map(([phase, info]) => (
                          <Card key={phase}>
                            <CardContent className="p-3">
                              <p className="text-sm font-medium capitalize mb-1">{phase}</p>
                              <p className="text-xs text-primary">{info.bowlers.map((b: { name: string } | string) => typeof b === "string" ? b : b.name).join(", ")}</p>
                              <p className="text-[10px] text-muted-foreground mt-1">{info.strategy}</p>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    )}

                    {/* Over-by-over bowling */}
                    <Card>
                      <CardHeader><CardTitle className="text-base"><Zap className="h-4 w-4 text-green-400 inline mr-2" />{bowlingTeam.short_name} Over-by-Over Bowling</CardTitle></CardHeader>
                      <CardContent>
                        <div className="rounded-lg border border-gray-800 overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-gray-800/50 border-b border-gray-800">
                                <th className="px-3 py-2 text-left text-xs text-muted-foreground">Over</th>
                                <th className="px-3 py-2 text-left text-xs text-muted-foreground">Bowler</th>
                                <th className="px-3 py-2 text-center text-xs text-muted-foreground">Phase</th>
                                <th className="px-3 py-2 text-center text-xs text-muted-foreground">Proj. Econ</th>
                                <th className="px-3 py-2 text-left text-xs text-muted-foreground">Danger Batters</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(gp.bowling_plan || []).map((o) => (
                                <tr key={o.over} className={cn("border-b border-gray-800/50", o.over <= 6 ? "bg-blue-500/5" : o.over >= 16 ? "bg-red-500/5" : "")}>
                                  <td className="px-3 py-2 font-bold">{o.over}</td>
                                  <td className="px-3 py-2 font-medium">{o.bowler_name}</td>
                                  <td className="px-3 py-2 text-center"><Badge variant="outline" className="text-xs capitalize">{o.phase}</Badge></td>
                                  <td className="px-3 py-2 text-center text-green-400">{o.projected_economy.toFixed(1)}</td>
                                  <td className="px-3 py-2 text-xs text-red-400">
                                    {o.danger_batters.length > 0 ? o.danger_batters.map((d) => `${d.batter} (SR ${d.sr})`).join(", ") : "-"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Key Matchups */}
                    {((gp.key_matchups_exploit || []).length > 0 || (gp.key_matchups_avoid || []).length > 0) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Card>
                          <CardHeader><CardTitle className="text-green-400 text-sm">Matchups to Exploit</CardTitle></CardHeader>
                          <CardContent className="space-y-1.5">
                            {(gp.key_matchups_exploit || []).slice(0, 5).map((m, i) => (
                              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-green-500/5 border border-green-500/10 text-xs">
                                <span>{m.batter} vs {m.bowler}</span>
                                <Badge className="bg-green-500/10 text-green-400 text-[10px]">SR {m.sr} ({m.balls}b)</Badge>
                              </div>
                            ))}
                            {(gp.key_matchups_exploit || []).length === 0 && <p className="text-xs text-muted-foreground">No significant matchup advantages found</p>}
                          </CardContent>
                        </Card>
                        <Card>
                          <CardHeader><CardTitle className="text-red-400 text-sm">Matchups to Avoid</CardTitle></CardHeader>
                          <CardContent className="space-y-1.5">
                            {(gp.key_matchups_avoid || []).slice(0, 5).map((m, i) => (
                              <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-red-500/5 border border-red-500/10 text-xs">
                                <span>{m.batter} vs {m.bowler}</span>
                                <Badge className="bg-red-500/10 text-red-400 text-[10px]">SR {m.sr} ({m.balls}b)</Badge>
                              </div>
                            ))}
                            {(gp.key_matchups_avoid || []).length === 0 && <p className="text-xs text-muted-foreground">No critical matchup risks identified</p>}
                          </CardContent>
                        </Card>
                      </div>
                    )}
                  </>);
                })()}
              </div>
            </TabsContent>
          )}
        </Tabs>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   TEAM ANALYSIS TAB — Used for both Team 1 and Team 2
   ═══════════════════════════════════════════════════════════════ */

function TeamAnalysisTab({ analysis, teamName, teamShort }: {
  analysis: TeamAnalysis;
  teamName: string;
  teamShort: string;
}) {
  const sorted = [...(analysis.playing_11 || [])].sort(
    (a, b) => (roleOrder[a.role] || 9) - (roleOrder[b.role] || 9)
  );
  const comp = analysis.squad_composition;

  return (
    <div className="space-y-8">
      {/* Playing XI */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            {teamName} -- Recommended Playing XI
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Composition bar */}
          <div className="flex gap-3 mb-4 text-xs flex-wrap">
            <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400">WK: {comp.wk}</span>
            <span className="px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400">Batters: {comp.batters}</span>
            <span className="px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-400">Allrounders: {comp.allrounders}</span>
            <span className="px-2.5 py-1 rounded-full bg-red-500/10 text-red-400">Bowlers: {comp.bowlers}</span>
            <span className="px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-400">Overseas: {comp.overseas}/4</span>
          </div>

          <div className="space-y-1.5">
            {sorted.map((p, i) => {
              const tag = roleTag(p.role);
              return (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 transition-colors">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-700 text-xs font-bold text-gray-300">{i + 1}</span>
                  <Badge className={cn("text-[10px] font-bold px-2 py-0.5 border shrink-0 w-16 justify-center", tag.color)}>{tag.label}</Badge>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm">{p.name}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{p.reasoning}</p>
                  </div>
                  {p.country !== "India" && (
                    <span className="text-[10px] text-cyan-400 bg-cyan-500/10 px-1.5 py-0.5 rounded shrink-0">{p.country}</span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Impact Players */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 p-4 rounded-lg bg-gray-800/30 border border-gray-800">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Impact Player (Bat First)</p>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{analysis.impact_player_batting?.name || "N/A"}</p>
                {analysis.impact_player_batting?.role && (
                  <Badge className={cn("text-[10px]", roleTag(analysis.impact_player_batting.role).color)}>
                    {roleTag(analysis.impact_player_batting.role).label}
                  </Badge>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Impact Player (Bowl First)</p>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{analysis.impact_player_bowling?.name || "N/A"}</p>
                {analysis.impact_player_bowling?.role && (
                  <Badge className={cn("text-[10px]", roleTag(analysis.impact_player_bowling.role).color)}>
                    {roleTag(analysis.impact_player_bowling.role).label}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Top Batters */}
      {analysis.top_batters.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="h-4 w-4 text-amber-400" /> Top Batters
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {analysis.top_batters.map((b) => (
              <BatterCard key={b.player_id} batter={b} />
            ))}
          </CardContent>
        </Card>
      )}

      {/* Top Bowlers */}
      {analysis.top_bowlers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-4 w-4 text-green-400" /> Top Bowlers
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {analysis.top_bowlers.map((b) => (
              <BowlerCard key={b.player_id} bowler={b} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ──────────────── Batter Card ──────────────── */

function BatterCard({ batter }: { batter: TopBatter }) {
  const tag = roleTag(batter.role);
  const phaseSRData = [
    { phase: "PP", value: batter.phase_sr.powerplay },
    { phase: "Mid", value: batter.phase_sr.middle },
    { phase: "Death", value: batter.phase_sr.death },
  ];

  return (
    <div className="p-4 rounded-xl bg-gray-800/40 border border-gray-800 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Badge className={cn("text-[10px] font-bold px-2 py-0.5 border", tag.color)}>{tag.label}</Badge>
        <p className="font-semibold text-sm">{batter.name}</p>
        <span className="text-[10px] text-muted-foreground ml-auto">Form: {batter.recent_form.form_index.toFixed(1)}</span>
      </div>

      {/* Career stats row */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
        {[
          { label: "Mat", val: batter.career.matches },
          { label: "Runs", val: batter.career.runs },
          { label: "Avg", val: batter.career.avg.toFixed(1) },
          { label: "SR", val: batter.career.sr.toFixed(1) },
          { label: "50s", val: batter.career["50s"] },
          { label: "100s", val: batter.career["100s"] },
        ].map((s) => (
          <div key={s.label} className="p-1.5 rounded bg-gray-700/50">
            <p className="text-[10px] text-muted-foreground">{s.label}</p>
            <p className="text-xs font-bold">{s.val}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Phase SR chart */}
        <PhaseBarChart data={phaseSRData} label="Strike Rate by Phase" />

        {/* vs Opposition */}
        {batter.vs_opposition.matches > 0 && (
          <div>
            <p className="text-[10px] text-muted-foreground mb-1">vs Opposition</p>
            <div className="grid grid-cols-2 gap-1.5 text-center">
              {[
                { label: "Mat", val: batter.vs_opposition.matches },
                { label: "Runs", val: batter.vs_opposition.runs },
                { label: "Avg", val: batter.vs_opposition.avg.toFixed(1) },
                { label: "SR", val: batter.vs_opposition.sr.toFixed(1) },
              ].map((s) => (
                <div key={s.label} className="p-1 rounded bg-gray-700/30 text-[10px]">
                  <span className="text-muted-foreground">{s.label}: </span>
                  <span className="font-bold">{s.val}</span>
                </div>
              ))}
            </div>
            {batter.vs_opposition.dismissals_by.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {batter.vs_opposition.dismissals_by.map((d) => (
                  <span key={d.bowler} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                    {d.bowler} x{d.times}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Recent form scores */}
      {batter.recent_form.last_5_scores.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">Last 5:</span>
          <div className="flex gap-1">
            {batter.recent_form.last_5_scores.map((s, i) => (
              <span key={i} className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-bold",
                s >= 50 ? "bg-green-500/20 text-green-400" : s >= 30 ? "bg-blue-500/20 text-blue-400" : "bg-gray-700 text-gray-300"
              )}>{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Strengths & Weaknesses */}
      {(batter.strengths.length > 0 || batter.weaknesses.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {batter.strengths.map((s, i) => (
            <Badge key={`s-${i}`} className="text-[10px] bg-green-500/10 text-green-400 border-green-500/20">{s}</Badge>
          ))}
          {batter.weaknesses.map((w, i) => (
            <Badge key={`w-${i}`} className="text-[10px] bg-red-500/10 text-red-400 border-red-500/20">{w}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}

/* ──────────────── Bowler Card ──────────────── */

function BowlerCard({ bowler }: { bowler: TopBowler }) {
  const tag = roleTag(bowler.role);
  const phaseEconData = [
    { phase: "PP", value: bowler.phase_economy.powerplay },
    { phase: "Mid", value: bowler.phase_economy.middle },
    { phase: "Death", value: bowler.phase_economy.death },
  ];

  return (
    <div className="p-4 rounded-xl bg-gray-800/40 border border-gray-800 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Badge className={cn("text-[10px] font-bold px-2 py-0.5 border", tag.color)}>{tag.label}</Badge>
        <p className="font-semibold text-sm">{bowler.name}</p>
        <span className="text-[10px] text-muted-foreground ml-auto">{bowler.bowling_style}</span>
      </div>

      {/* Career stats row */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 text-center">
        {[
          { label: "Mat", val: bowler.career.matches },
          { label: "Wkts", val: bowler.career.wickets },
          { label: "Econ", val: bowler.career.economy.toFixed(2) },
          { label: "Avg", val: bowler.career.avg.toFixed(1) },
          { label: "SR", val: bowler.career.sr.toFixed(1) },
        ].map((s) => (
          <div key={s.label} className="p-1.5 rounded bg-gray-700/50">
            <p className="text-[10px] text-muted-foreground">{s.label}</p>
            <p className="text-xs font-bold">{s.val}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Phase Economy chart */}
        <PhaseBarChart data={phaseEconData} label="Economy by Phase" />

        {/* vs Opposition + at Venue */}
        <div className="space-y-2">
          {bowler.vs_opposition.wickets > 0 && (
            <div>
              <p className="text-[10px] text-muted-foreground mb-1">vs Opposition</p>
              <div className="flex gap-2 text-[10px]">
                <span className="px-1.5 py-0.5 rounded bg-gray-700/30"><span className="text-muted-foreground">W:</span> <span className="font-bold">{bowler.vs_opposition.wickets}</span></span>
                <span className="px-1.5 py-0.5 rounded bg-gray-700/30"><span className="text-muted-foreground">Econ:</span> <span className="font-bold">{bowler.vs_opposition.economy.toFixed(2)}</span></span>
              </div>
            </div>
          )}
          {bowler.at_venue.wickets > 0 && (
            <div>
              <p className="text-[10px] text-muted-foreground mb-1">At Venue</p>
              <div className="flex gap-2 text-[10px]">
                <span className="px-1.5 py-0.5 rounded bg-gray-700/30"><span className="text-muted-foreground">W:</span> <span className="font-bold">{bowler.at_venue.wickets}</span></span>
                <span className="px-1.5 py-0.5 rounded bg-gray-700/30"><span className="text-muted-foreground">Econ:</span> <span className="font-bold">{bowler.at_venue.economy.toFixed(2)}</span></span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Strengths & Weaknesses */}
      {(bowler.strengths.length > 0 || bowler.weaknesses.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {bowler.strengths.map((s, i) => (
            <Badge key={`s-${i}`} className="text-[10px] bg-green-500/10 text-green-400 border-green-500/20">{s}</Badge>
          ))}
          {bowler.weaknesses.map((w, i) => (
            <Badge key={`w-${i}`} className="text-[10px] bg-red-500/10 text-red-400 border-red-500/20">{w}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}

/* ──────────────── Matchup Table ──────────────── */

function MatchupTable({ title, matchups }: { title: string; matchups: MatchupEntry[] }) {
  if (!matchups || matchups.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
        <CardContent><p className="text-sm text-muted-foreground">No matchup data available</p></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent>
        <div className="rounded-lg border border-gray-800 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800/50 border-b border-gray-800">
                <th className="px-3 py-2 text-left text-xs text-muted-foreground">Batter</th>
                <th className="px-3 py-2 text-left text-xs text-muted-foreground">Bowler</th>
                <th className="px-3 py-2 text-center text-xs text-muted-foreground">Balls</th>
                <th className="px-3 py-2 text-center text-xs text-muted-foreground">Runs</th>
                <th className="px-3 py-2 text-center text-xs text-muted-foreground">SR</th>
                <th className="px-3 py-2 text-center text-xs text-muted-foreground">Dismissals</th>
                <th className="px-3 py-2 text-center text-xs text-muted-foreground">Threat</th>
              </tr>
            </thead>
            <tbody>
              {matchups.map((m, i) => {
                const srBg = m.sr > 150
                  ? "bg-green-500/10"
                  : m.sr < 100
                    ? "bg-red-500/10"
                    : "";
                return (
                  <tr key={i} className={cn("border-b border-gray-800/50", srBg)}>
                    <td className="px-3 py-2 font-medium">{m.batter}</td>
                    <td className="px-3 py-2">{m.bowler}</td>
                    <td className="px-3 py-2 text-center">{m.balls}</td>
                    <td className="px-3 py-2 text-center">{m.runs}</td>
                    <td className="px-3 py-2 text-center font-bold">{m.sr.toFixed(1)}</td>
                    <td className="px-3 py-2 text-center">{m.dismissals}</td>
                    <td className="px-3 py-2 text-center">
                      <Badge className={cn("text-[10px] border", threatBadge(m.threat_level))}>{m.threat_level}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
