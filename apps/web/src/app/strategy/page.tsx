"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchTeams, fetchTeamPlayers, fetchVenues, getStrategy, getBowlingPlan } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Swords, BrainCircuit, Loader2, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StrategyResponse } from "@/lib/types";

export default function StrategyPage() {
  const { data: teams } = useQuery({ queryKey: ["teams"], queryFn: fetchTeams });
  const { data: venues } = useQuery({ queryKey: ["venues"], queryFn: fetchVenues });

  const [myTeamId, setMyTeamId] = useState("");
  const [oppositionId, setOppositionId] = useState("");
  const [venueId, setVenueId] = useState("");
  const [selectedPlayerIds, setSelectedPlayerIds] = useState<number[]>([]);
  const [strategy, setStrategy] = useState<StrategyResponse | null>(null);

  const myTeamSlug = (teams || []).find((t) => t.id.toString() === myTeamId)?.slug || "";

  const { data: teamPlayers } = useQuery({
    queryKey: ["team-players", myTeamSlug],
    queryFn: () => fetchTeamPlayers(myTeamSlug),
    enabled: !!myTeamSlug,
  });

  const battingMutation = useMutation({
    mutationFn: getStrategy,
    onSuccess: (data) => setStrategy((prev) => ({ ...prev, batting_order: data.batting_order })),
  });

  const bowlingMutation = useMutation({
    mutationFn: getBowlingPlan,
    onSuccess: (data) => setStrategy((prev) => ({ ...prev, bowling_plan: data.bowling_plan })),
  });

  const teamOptions = (teams || []).map((t) => ({ value: t.id.toString(), label: t.name }));
  const venueOptions = (venues || []).map((v) => ({ value: v.id.toString(), label: `${v.name}${v.city ? `, ${v.city}` : ""}` }));

  const togglePlayer = (id: number) => {
    setSelectedPlayerIds((prev) =>
      prev.includes(id)
        ? prev.filter((p) => p !== id)
        : prev.length < 11
        ? [...prev, id]
        : prev
    );
  };

  const handleGenerate = () => {
    if (!myTeamId || !oppositionId || selectedPlayerIds.length !== 11) return;
    setStrategy(null);
    battingMutation.mutate({
      squad_player_ids: selectedPlayerIds,
      venue_id: venueId ? Number(venueId) : undefined,
      include_ai_explanation: true,
    });
    bowlingMutation.mutate({
      squad_bowler_ids: selectedPlayerIds,
      venue_id: venueId ? Number(venueId) : undefined,
      include_ai_explanation: false,
    });
  };

  const isPending = battingMutation.isPending || bowlingMutation.isPending;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Swords className="h-6 w-6 text-primary" />
          Strategy Engine
        </h1>
        <p className="text-muted-foreground mt-1">
          AI-powered batting order and bowling plan optimization
        </p>
      </div>

      {/* Configuration */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground">Your Team</label>
          <Select
            options={teamOptions}
            placeholder="Select Your Team"
            value={myTeamId}
            onChange={(e) => { setMyTeamId(e.target.value); setSelectedPlayerIds([]); }}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground">Opposition</label>
          <Select
            options={teamOptions.filter((t) => t.value !== myTeamId)}
            placeholder="Select Opposition"
            value={oppositionId}
            onChange={(e) => setOppositionId(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-muted-foreground">Venue (Optional)</label>
          <Select
            options={venueOptions}
            placeholder="Select Venue"
            value={venueId}
            onChange={(e) => setVenueId(e.target.value)}
          />
        </div>
      </div>

      {/* Squad Selector */}
      {teamPlayers && teamPlayers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Select Playing XI ({selectedPlayerIds.length}/11)</span>
              {selectedPlayerIds.length === 11 && (
                <Badge className="bg-green-500/10 text-green-400 border-green-500/20">Squad Complete</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {teamPlayers.map((player) => {
                const isSelected = selectedPlayerIds.includes(player.id);
                return (
                  <button
                    key={player.id}
                    onClick={() => togglePlayer(player.id)}
                    className={cn(
                      "flex items-center gap-2 p-3 rounded-lg border text-left text-sm transition-all",
                      isSelected
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border bg-card text-muted-foreground hover:border-border-strong hover:bg-muted",
                      !isSelected && selectedPlayerIds.length >= 11 && "opacity-40 cursor-not-allowed"
                    )}
                    disabled={!isSelected && selectedPlayerIds.length >= 11}
                  >
                    <div className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded border",
                      isSelected ? "bg-primary border-primary" : "border-border-strong"
                    )}>
                      {isSelected && <Check className="h-3 w-3 text-white" />}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{player.name}</p>
                      <p className="text-xs text-muted-foreground">{player.role || "Player"}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Generate Button */}
      <div className="flex justify-center">
        <Button
          size="lg"
          className="px-12"
          disabled={!myTeamId || !oppositionId || selectedPlayerIds.length !== 11 || isPending}
          onClick={handleGenerate}
        >
          {isPending ? (
            <><Loader2 className="h-5 w-5 animate-spin mr-2" /> Generating Strategy...</>
          ) : (
            <><BrainCircuit className="h-5 w-5 mr-2" /> Generate Strategy</>
          )}
        </Button>
      </div>

      {(battingMutation.isError || bowlingMutation.isError) && (
        <Card className="border-red-900/50">
          <CardContent className="p-8 text-center">
            <p className="text-red-400">Strategy engine unavailable. Please ensure the API is running.</p>
          </CardContent>
        </Card>
      )}

      {/* Strategy Results */}
      {strategy && (strategy.batting_order || strategy.bowling_plan) && (
        <div className="space-y-6">
          <Tabs defaultValue="batting">
            <TabsList>
              <TabsTrigger value="batting">Batting Order</TabsTrigger>
              <TabsTrigger value="bowling">Bowling Plan</TabsTrigger>
            </TabsList>

            <TabsContent value="batting">
              <Card>
                <CardHeader>
                  <CardTitle>Recommended Batting Order</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {(strategy.batting_order || []).map((entry) => (
                      <div
                        key={entry.position}
                        className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                      >
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-sm">
                          {entry.position}
                        </span>
                        <div className="flex-1">
                          <p className="font-medium">{entry.player_name}</p>
                          <p className="text-xs text-muted-foreground">{entry.role}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-semibold text-amber-400">
                            {entry.projected_runs} runs
                          </p>
                          <p className="text-xs text-muted-foreground">
                            SR: {entry.projected_sr?.toFixed(1)}
                          </p>
                        </div>
                        <Badge
                          className={cn(
                            "text-xs",
                            entry.confidence === "high" ? "bg-green-500/10 text-green-400" :
                            entry.confidence === "medium" ? "bg-amber-500/10 text-amber-400" :
                            "bg-red-500/10 text-red-400"
                          )}
                        >
                          {entry.confidence}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="bowling">
              <Card>
                <CardHeader>
                  <CardTitle>Bowling Plan by Phase</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-6">
                    {(strategy.bowling_plan || []).map((phase) => (
                      <div key={phase.phase}>
                        <div className="flex items-center gap-3 mb-3">
                          <h3 className="text-lg font-semibold">{phase.phase}</h3>
                          <Badge variant="outline">{phase.overs_range}</Badge>
                        </div>
                        <div className="rounded-lg border border-border overflow-hidden">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="bg-muted/50 border-b border-border">
                                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Bowler</th>
                                <th className="px-4 py-2 text-center font-medium text-muted-foreground">Overs</th>
                                <th className="px-4 py-2 text-center font-medium text-muted-foreground">Proj. Economy</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(phase.bowlers || []).map((bowler) => (
                                <tr key={bowler.player_id} className="border-b border-border/50">
                                  <td className="px-4 py-2 font-medium">{bowler.player_name}</td>
                                  <td className="px-4 py-2 text-center">{bowler.overs}</td>
                                  <td className="px-4 py-2 text-center text-green-400">
                                    {typeof bowler.expected_economy === "number" ? bowler.expected_economy.toFixed(1) : "-"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {strategy.ai_explanation && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BrainCircuit className="h-5 w-5 text-purple-400" />
                  AI Strategy Analysis
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{strategy.ai_explanation}</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
