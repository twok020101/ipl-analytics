"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchTeams, fetchPlayers, fetchH2HTeams, fetchH2HPlayers, fetchPlayerCompare } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { SpiderChart } from "@/components/charts/SpiderChart";
import { GitCompareArrows, Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn, getTeamTextColor } from "@/lib/utils";
import type { H2HTeamResult, H2HPlayerResult, PlayerCompareResult, PlayerCompareStats } from "@/lib/types";

function CompareStat({
  label,
  val1,
  val2,
  format,
  higherIsBetter = true,
}: {
  label: string;
  val1: number;
  val2: number;
  format?: (v: number) => string;
  higherIsBetter?: boolean;
}) {
  const fmt = format || ((v: number) => String(v));
  const better1 = higherIsBetter ? val1 > val2 : val1 < val2;
  const better2 = higherIsBetter ? val2 > val1 : val2 < val1;
  return (
    <div className="grid grid-cols-3 gap-2 items-center py-2.5 border-b border-gray-800/50 last:border-0">
      <div className={cn("text-right font-semibold text-sm", better1 && "text-green-400")}>
        {fmt(val1)}
      </div>
      <div className="text-center text-xs text-muted-foreground">{label}</div>
      <div className={cn("text-left font-semibold text-sm", better2 && "text-green-400")}>
        {fmt(val2)}
      </div>
    </div>
  );
}

function PlayerCompareView({ data }: { data: PlayerCompareResult }) {
  const { player1: p1, player2: p2 } = data;

  const buildSpider = (p: PlayerCompareStats) => {
    const sr = p.batting.strike_rate || 0;
    const runs = p.batting.runs || 0;
    const matches = p.batting.matches || 1;
    const wickets = p.bowling.wickets || 0;
    return [
      { axis: "Power", value: Math.min(100, sr / 2) },
      { axis: "Consistency", value: Math.min(100, (runs / matches) * 3) },
      { axis: "Strike Rate", value: Math.min(100, Math.max(0, (sr - 80) * 2)) },
      { axis: "Form", value: Math.min(100, p.form_index) },
      { axis: "Versatility", value: wickets > 20 && runs > 500 ? 80 : wickets > 5 ? 55 : 35 },
      { axis: "Experience", value: Math.min(100, matches / 2.5) },
    ];
  };

  const trendIcon = (trend: string) => {
    if (trend === "improving") return <TrendingUp className="h-3.5 w-3.5 text-green-400" />;
    if (trend === "declining") return <TrendingDown className="h-3.5 w-3.5 text-red-400" />;
    return <Minus className="h-3.5 w-3.5 text-muted-foreground" />;
  };

  const fmtDec = (v: number) => v.toFixed(2);
  const fmtInt = (v: number) => String(v);

  return (
    <div className="space-y-6 mt-6">
      {/* Player headers */}
      <Card>
        <CardContent className="p-6">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-lg sm:text-xl font-bold text-primary">{p1.name}</p>
              <div className="flex items-center justify-center gap-2 mt-1">
                {p1.role && <Badge variant="outline" className="text-xs">{p1.role}</Badge>}
                <div className="flex items-center gap-1" title={`Form: ${p1.form_trend}`}>
                  {trendIcon(p1.form_trend)}
                  <span className="text-xs text-muted-foreground">{p1.form_index.toFixed(0)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {p1.teams.map((t) => t.short_name).join(", ")}
              </p>
            </div>
            <div className="flex items-center justify-center">
              <span className="text-sm font-bold text-muted-foreground">VS</span>
            </div>
            <div>
              <p className="text-lg sm:text-xl font-bold text-red-400">{p2.name}</p>
              <div className="flex items-center justify-center gap-2 mt-1">
                {p2.role && <Badge variant="outline" className="text-xs">{p2.role}</Badge>}
                <div className="flex items-center gap-1" title={`Form: ${p2.form_trend}`}>
                  {trendIcon(p2.form_trend)}
                  <span className="text-xs text-muted-foreground">{p2.form_index.toFixed(0)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {p2.teams.map((t) => t.short_name).join(", ")}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Spider Charts Side-by-Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle className="text-base">{p1.name}</CardTitle></CardHeader>
          <CardContent>
            <SpiderChart data={buildSpider(p1)} color="#3b82f6" name={p1.name} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">{p2.name}</CardTitle></CardHeader>
          <CardContent>
            <SpiderChart data={buildSpider(p2)} color="#ef4444" name={p2.name} />
          </CardContent>
        </Card>
      </div>

      {/* Batting Comparison */}
      <Card>
        <CardHeader><CardTitle className="text-base">Batting Comparison</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-2 items-center pb-2 border-b border-gray-700 mb-1">
            <div className="text-right text-xs font-medium text-primary">{p1.name.split(" ").pop()}</div>
            <div className="text-center text-xs font-medium text-muted-foreground">Stat</div>
            <div className="text-left text-xs font-medium text-red-400">{p2.name.split(" ").pop()}</div>
          </div>
          <CompareStat label="Matches" val1={p1.batting.matches} val2={p2.batting.matches} format={fmtInt} />
          <CompareStat label="Innings" val1={p1.batting.innings} val2={p2.batting.innings} format={fmtInt} />
          <CompareStat label="Runs" val1={p1.batting.runs} val2={p2.batting.runs} format={fmtInt} />
          <CompareStat label="Average" val1={p1.batting.average} val2={p2.batting.average} format={fmtDec} />
          <CompareStat label="Strike Rate" val1={p1.batting.strike_rate} val2={p2.batting.strike_rate} format={fmtDec} />
          <CompareStat label="Highest" val1={p1.batting.highest_score} val2={p2.batting.highest_score} format={fmtInt} />
          <CompareStat label="50s" val1={p1.batting.fifties} val2={p2.batting.fifties} format={fmtInt} />
          <CompareStat label="100s" val1={p1.batting.hundreds} val2={p2.batting.hundreds} format={fmtInt} />
          <CompareStat label="4s" val1={p1.batting.fours} val2={p2.batting.fours} format={fmtInt} />
          <CompareStat label="6s" val1={p1.batting.sixes} val2={p2.batting.sixes} format={fmtInt} />
        </CardContent>
      </Card>

      {/* Bowling Comparison (if both have wickets) */}
      {(p1.bowling.wickets > 0 || p2.bowling.wickets > 0) && (
        <Card>
          <CardHeader><CardTitle className="text-base">Bowling Comparison</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2 items-center pb-2 border-b border-gray-700 mb-1">
              <div className="text-right text-xs font-medium text-primary">{p1.name.split(" ").pop()}</div>
              <div className="text-center text-xs font-medium text-muted-foreground">Stat</div>
              <div className="text-left text-xs font-medium text-red-400">{p2.name.split(" ").pop()}</div>
            </div>
            <CompareStat label="Wickets" val1={p1.bowling.wickets} val2={p2.bowling.wickets} format={fmtInt} />
            <CompareStat label="Economy" val1={p1.bowling.economy} val2={p2.bowling.economy} format={fmtDec} higherIsBetter={false} />
            <CompareStat label="Average" val1={p1.bowling.average} val2={p2.bowling.average} format={fmtDec} higherIsBetter={false} />
            <CompareStat label="4W Hauls" val1={p1.bowling.four_wickets} val2={p2.bowling.four_wickets} format={fmtInt} />
            <CompareStat label="5W Hauls" val1={p1.bowling.five_wickets} val2={p2.bowling.five_wickets} format={fmtInt} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function HeadToHeadPage() {
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
  const { data: playersData } = useQuery({
    queryKey: ["all-players"],
    queryFn: () => fetchPlayers({ per_page: 500 }),
  });

  const [mode, setMode] = useState<"teams" | "players" | "compare">("teams");

  // Team H2H
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [teamResult, setTeamResult] = useState<H2HTeamResult | null>(null);

  const teamH2HMutation = useMutation({
    mutationFn: ({ t1, t2 }: { t1: string; t2: string }) => fetchH2HTeams(t1, t2),
    onSuccess: (data) => setTeamResult(data),
  });

  // Player H2H
  const [batterId, setBatterId] = useState("");
  const [bowlerId, setBowlerId] = useState("");
  const [playerResult, setPlayerResult] = useState<H2HPlayerResult | null>(null);

  const playerH2HMutation = useMutation({
    mutationFn: ({ b, bo }: { b: string; bo: string }) => fetchH2HPlayers(b, bo),
    onSuccess: (data) => setPlayerResult(data),
  });

  // Player Compare
  const [compareP1, setCompareP1] = useState("");
  const [compareP2, setCompareP2] = useState("");
  const [compareResult, setCompareResult] = useState<PlayerCompareResult | null>(null);

  const compareMutation = useMutation({
    mutationFn: ({ p1, p2 }: { p1: number; p2: number }) => fetchPlayerCompare(p1, p2),
    onSuccess: (data) => setCompareResult(data),
  });

  const teamOptions = (teams || []).map((t) => ({ value: t.short_name, label: t.name }));
  const playerOptions = (playersData?.players || []).map((p) => ({
    value: p.id.toString(),
    label: p.name,
  }));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <GitCompareArrows className="h-6 w-6 text-primary" />
          Head-to-Head
        </h1>
        <p className="text-muted-foreground mt-1">
          Compare teams and players across all IPL encounters
        </p>
      </div>

      <Tabs defaultValue="teams" value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
        <TabsList>
          <TabsTrigger value="teams">Team vs Team</TabsTrigger>
          <TabsTrigger value="players">Batter vs Bowler</TabsTrigger>
          <TabsTrigger value="compare">Compare Players</TabsTrigger>
        </TabsList>

        {/* Team H2H */}
        <TabsContent value="teams">
          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                <div className="md:col-span-2 space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Team 1</label>
                  <Select
                    options={teamOptions}
                    placeholder="Select Team 1"
                    value={teamA}
                    onChange={(e) => setTeamA(e.target.value)}
                  />
                </div>
                <div className="flex items-center justify-center">
                  <span className="text-sm font-bold text-muted-foreground">VS</span>
                </div>
                <div className="md:col-span-2 space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Team 2</label>
                  <Select
                    options={teamOptions.filter((t) => t.value !== teamA)}
                    placeholder="Select Team 2"
                    value={teamB}
                    onChange={(e) => setTeamB(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-center mt-6">
                <Button
                  onClick={() => teamH2HMutation.mutate({ t1: teamA, t2: teamB })}
                  disabled={!teamA || !teamB || teamH2HMutation.isPending}
                >
                  {teamH2HMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Compare
                </Button>
              </div>
            </CardContent>
          </Card>

          {teamH2HMutation.isError && (
            <Card className="border-red-900/50 mt-4">
              <CardContent className="p-6 text-center text-red-400">
                Failed to load head-to-head data.
              </CardContent>
            </Card>
          )}

          {teamResult && (
            <div className="space-y-6 mt-6">
              <Card>
                <CardContent className="p-6 sm:p-8">
                  <div className="grid grid-cols-3 gap-4 sm:gap-6 text-center">
                    <div>
                      <p className={cn("text-3xl sm:text-4xl font-bold", getTeamTextColor(teamResult.team1.name))}>
                        {teamResult.team1_wins}
                      </p>
                      <p className="text-xs sm:text-sm text-muted-foreground mt-1">{teamResult.team1.name}</p>
                    </div>
                    <div>
                      <p className="text-xl sm:text-2xl font-bold text-muted-foreground">
                        {teamResult.total_matches}
                      </p>
                      <p className="text-xs sm:text-sm text-muted-foreground mt-1">Total Matches</p>
                      {teamResult.no_result > 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {teamResult.no_result} No Result
                        </p>
                      )}
                    </div>
                    <div>
                      <p className={cn("text-3xl sm:text-4xl font-bold", getTeamTextColor(teamResult.team2.name))}>
                        {teamResult.team2_wins}
                      </p>
                      <p className="text-xs sm:text-sm text-muted-foreground mt-1">{teamResult.team2.name}</p>
                    </div>
                  </div>
                  <div className="mt-6 h-3 rounded-full bg-gray-800 overflow-hidden flex">
                    {teamResult.total_matches > 0 && (
                      <>
                        <div
                          className="h-full rounded-l-full transition-all duration-700"
                          style={{
                            width: `${(teamResult.team1_wins / teamResult.total_matches) * 100}%`,
                            backgroundColor: "#3b82f6",
                          }}
                        />
                        <div
                          className="h-full rounded-r-full transition-all duration-700"
                          style={{
                            width: `${(teamResult.team2_wins / teamResult.total_matches) * 100}%`,
                            backgroundColor: "#ef4444",
                          }}
                        />
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>

              {teamResult.recent_matches && teamResult.recent_matches.length > 0 && (
                <Card>
                  <CardHeader><CardTitle>Recent Encounters</CardTitle></CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {teamResult.recent_matches.map((m, i) => (
                        <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50">
                          <div>
                            <p className="text-sm font-medium">{m.winner}</p>
                            <p className="text-xs text-muted-foreground">{m.season}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">{m.date}</p>
                            {m.margin && <p className="text-xs text-primary">{m.margin}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        {/* Player H2H (Batter vs Bowler) */}
        <TabsContent value="players">
          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                <div className="md:col-span-2 space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Batter</label>
                  <Select
                    options={playerOptions}
                    placeholder="Select Batter"
                    value={batterId}
                    onChange={(e) => setBatterId(e.target.value)}
                  />
                </div>
                <div className="flex items-center justify-center">
                  <span className="text-sm font-bold text-muted-foreground">VS</span>
                </div>
                <div className="md:col-span-2 space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Bowler</label>
                  <Select
                    options={playerOptions}
                    placeholder="Select Bowler"
                    value={bowlerId}
                    onChange={(e) => setBowlerId(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-center mt-6">
                <Button
                  onClick={() => playerH2HMutation.mutate({ b: batterId, bo: bowlerId })}
                  disabled={!batterId || !bowlerId || playerH2HMutation.isPending}
                >
                  {playerH2HMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Compare
                </Button>
              </div>
            </CardContent>
          </Card>

          {playerH2HMutation.isError && (
            <Card className="border-red-900/50 mt-4">
              <CardContent className="p-6 text-center text-red-400">
                Failed to load matchup data.
              </CardContent>
            </Card>
          )}

          {playerResult && (
            <div className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle>
                    {playerResult.batter.name} vs {playerResult.bowler.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                    {[
                      { label: "Balls", value: playerResult.balls },
                      { label: "Runs", value: playerResult.runs, color: "text-amber-400" },
                      { label: "Strike Rate", value: playerResult.strike_rate?.toFixed(1), color: "text-primary" },
                      { label: "Dismissals", value: playerResult.dismissals, color: "text-red-400" },
                      { label: "Average", value: playerResult.average?.toFixed(1) || "N/A", color: "text-green-400" },
                      { label: "Dots", value: playerResult.dots },
                    ].map((stat) => (
                      <div key={stat.label} className="text-center p-4 rounded-xl bg-gray-800/50">
                        <p className="text-xs text-muted-foreground">{stat.label}</p>
                        <p className={cn("text-xl sm:text-2xl font-bold mt-1", stat.color)}>
                          {stat.value}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="text-center p-4 rounded-xl bg-gray-800/50">
                      <p className="text-xs text-muted-foreground">Fours</p>
                      <p className="text-xl font-bold text-cyan-400">{playerResult.fours}</p>
                    </div>
                    <div className="text-center p-4 rounded-xl bg-gray-800/50">
                      <p className="text-xs text-muted-foreground">Sixes</p>
                      <p className="text-xl font-bold text-purple-400">{playerResult.sixes}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        {/* Player Compare (side-by-side) */}
        <TabsContent value="compare">
          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
                <div className="md:col-span-2 space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Player 1</label>
                  <Select
                    options={playerOptions}
                    placeholder="Select Player 1"
                    value={compareP1}
                    onChange={(e) => setCompareP1(e.target.value)}
                  />
                </div>
                <div className="flex items-center justify-center">
                  <span className="text-sm font-bold text-muted-foreground">VS</span>
                </div>
                <div className="md:col-span-2 space-y-2">
                  <label className="text-sm font-medium text-muted-foreground">Player 2</label>
                  <Select
                    options={playerOptions.filter((p) => p.value !== compareP1)}
                    placeholder="Select Player 2"
                    value={compareP2}
                    onChange={(e) => setCompareP2(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex justify-center mt-6">
                <Button
                  onClick={() =>
                    compareMutation.mutate({
                      p1: Number(compareP1),
                      p2: Number(compareP2),
                    })
                  }
                  disabled={!compareP1 || !compareP2 || compareMutation.isPending}
                >
                  {compareMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Compare Players
                </Button>
              </div>
            </CardContent>
          </Card>

          {compareMutation.isError && (
            <Card className="border-red-900/50 mt-4">
              <CardContent className="p-6 text-center text-red-400">
                Failed to load comparison data.
              </CardContent>
            </Card>
          )}

          {compareResult && <PlayerCompareView data={compareResult} />}
        </TabsContent>
      </Tabs>
    </div>
  );
}
