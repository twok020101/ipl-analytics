"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchTeams, fetchPlayers, fetchH2HTeams, fetchH2HPlayers } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GitCompareArrows, Loader2 } from "lucide-react";
import { cn, getTeamTextColor } from "@/lib/utils";
import type { H2HTeamResult, H2HPlayerResult } from "@/lib/types";

export default function HeadToHeadPage() {
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
  const { data: playersData } = useQuery({
    queryKey: ["all-players"],
    queryFn: () => fetchPlayers({ per_page: 500 }),
  });

  const [mode, setMode] = useState<"teams" | "players">("teams");

  // Team H2H - use short_name for API calls
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [teamResult, setTeamResult] = useState<H2HTeamResult | null>(null);

  const teamH2HMutation = useMutation({
    mutationFn: ({ t1, t2 }: { t1: string; t2: string }) => fetchH2HTeams(t1, t2),
    onSuccess: (data) => setTeamResult(data),
  });

  // Player H2H - use IDs
  const [batterId, setBatterId] = useState("");
  const [bowlerId, setBowlerId] = useState("");
  const [playerResult, setPlayerResult] = useState<H2HPlayerResult | null>(null);

  const playerH2HMutation = useMutation({
    mutationFn: ({ b, bo }: { b: string; bo: string }) => fetchH2HPlayers(b, bo),
    onSuccess: (data) => setPlayerResult(data),
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

      <Tabs defaultValue="teams" value={mode} onValueChange={(v) => setMode(v as "teams" | "players")}>
        <TabsList>
          <TabsTrigger value="teams">Team vs Team</TabsTrigger>
          <TabsTrigger value="players">Player vs Player</TabsTrigger>
        </TabsList>

        {/* Team H2H */}
        <TabsContent value="teams">
          <Card>
            <CardContent className="p-6">
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
                <CardContent className="p-8">
                  <div className="grid grid-cols-3 gap-6 text-center">
                    <div>
                      <p className={cn("text-4xl font-bold", getTeamTextColor(teamResult.team1.name))}>
                        {teamResult.team1_wins}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">{teamResult.team1.name}</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-muted-foreground">
                        {teamResult.total_matches}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">Total Matches</p>
                      {teamResult.no_result > 0 && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {teamResult.no_result} No Result
                        </p>
                      )}
                    </div>
                    <div>
                      <p className={cn("text-4xl font-bold", getTeamTextColor(teamResult.team2.name))}>
                        {teamResult.team2_wins}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">{teamResult.team2.name}</p>
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

        {/* Player H2H */}
        <TabsContent value="players">
          <Card>
            <CardContent className="p-6">
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
                        <p className={cn("text-2xl font-bold mt-1", stat.color)}>
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
      </Tabs>
    </div>
  );
}
