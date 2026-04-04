"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { fetchTeam, fetchTeamPlayers } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { StatCard } from "@/components/cards/StatCard";
import { RunRateBar } from "@/components/charts/RunRateBar";
import { DataTable } from "@/components/tables/DataTable";
import { Trophy, Target, TrendingUp, Percent, ArrowLeft } from "lucide-react";
import { cn, getTeamTextColor, getTeamBg, formatPercentage } from "@/lib/utils";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import type { ColumnDef } from "@tanstack/react-table";
import type { Player } from "@/lib/types";

export default function TeamDetailPage() {
  const params = useParams();
  const slug = params.teamSlug as string;

  const { data: team, isLoading } = useQuery({
    queryKey: ["team", slug],
    queryFn: () => fetchTeam(slug),
  });

  const { data: players } = useQuery({
    queryKey: ["team-players", slug],
    queryFn: () => fetchTeamPlayers(slug),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!team) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground text-lg">Team not found</p>
        <Link href="/teams" className="text-primary mt-2 hover:underline">Back to Teams</Link>
      </div>
    );
  }

  const shortName = team.short_name || slug.toUpperCase();

  // Mock data for charts (will be replaced by API data)
  const battingData = (players || [])
    .filter((p) => (p.runs || 0) > 0)
    .sort((a, b) => (b.runs || 0) - (a.runs || 0))
    .slice(0, 8)
    .map((p) => ({ name: p.name.split(" ").pop(), runs: p.runs || 0 }));

  const bowlingData: { name: string | undefined; wickets: number }[] = [];

  const phaseData = [
    { phase: "Powerplay", runRate: 8.2, avgRate: 7.8 },
    { phase: "Middle", runRate: 7.5, avgRate: 7.3 },
    { phase: "Death", runRate: 9.8, avgRate: 9.4 },
  ];

  const playerColumns: ColumnDef<Player, unknown>[] = [
    { accessorKey: "name", header: "Player", cell: ({ row }) => (
      <Link href={`/players/${row.original.id}`} className="text-primary hover:underline font-medium">
        {row.original.name}
      </Link>
    )},
    { accessorKey: "role", header: "Role", cell: ({ row }) => row.original.role || "Player" },
    { accessorKey: "latest_season", header: "Last Season" },
    { accessorKey: "matches", header: "Matches" },
    { accessorKey: "runs", header: "Runs" },
    { accessorKey: "strike_rate", header: "SR", cell: ({ row }) => (row.original.strike_rate || 0).toFixed(1) },
  ];

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href="/teams" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to Teams
      </Link>

      {/* Team Header */}
      <div className={cn("rounded-2xl border border-border p-8", getTeamBg(shortName))}>
        <div className="flex items-center gap-4 mb-6">
          <Badge variant="outline" className={cn("text-lg px-3 py-1", getTeamTextColor(shortName))}>
            {shortName}
          </Badge>
          <h1 className="text-3xl font-bold">{team.name}</h1>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Matches Played" value={team.stats?.matches || 0} icon={Target} />
          <StatCard label="Wins" value={team.stats?.wins || 0} icon={Trophy} />
          <StatCard label="Losses" value={team.stats?.losses || 0} icon={TrendingUp} />
          <StatCard label="Win %" value={formatPercentage(team.stats?.win_pct || 0)} icon={Percent} />
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="batting">Batting</TabsTrigger>
          <TabsTrigger value="bowling">Bowling</TabsTrigger>
          <TabsTrigger value="squad">Squad</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Run Rate by Phase</CardTitle>
              </CardHeader>
              <CardContent>
                <RunRateBar
                  data={phaseData}
                  bars={[
                    { key: "runRate", color: "#3b82f6", name: team.short_name },
                    { key: "avgRate", color: "#6b7280", name: "League Avg" },
                  ]}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Quick Stats</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                  <span className="text-muted-foreground">Win Percentage</span>
                  <span className="font-bold text-green-400">{formatPercentage(team.stats?.win_pct || 0)}</span>
                </div>
                <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                  <span className="text-muted-foreground">Matches Won</span>
                  <span className="font-bold">{team.stats?.wins || 0}</span>
                </div>
                <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                  <span className="text-muted-foreground">Matches Lost</span>
                  <span className="font-bold text-red-400">{team.stats?.losses || 0}</span>
                </div>
                <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                  <span className="text-muted-foreground">Toss Wins</span>
                  <span className="font-bold">{team.stats?.toss_wins || 0}</span>
                </div>
                <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
                  <span className="text-muted-foreground">Seasons Played</span>
                  <span className="font-bold text-amber-400">{team.seasons?.length || 0}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="batting">
          <Card>
            <CardHeader>
              <CardTitle>Top Run Scorers</CardTitle>
            </CardHeader>
            <CardContent>
              {battingData.length > 0 ? (
                <div className="h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={battingData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                      <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: "#1f2937",
                          border: "1px solid #374151",
                          borderRadius: "8px",
                          color: "#f9fafb",
                        }}
                      />
                      <Bar dataKey="runs" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-8">No batting data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="bowling">
          <Card>
            <CardHeader>
              <CardTitle>Top Wicket Takers</CardTitle>
            </CardHeader>
            <CardContent>
              {bowlingData.length > 0 ? (
                <div className="h-[350px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={bowlingData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                      <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: "#1f2937",
                          border: "1px solid #374151",
                          borderRadius: "8px",
                          color: "#f9fafb",
                        }}
                      />
                      <Bar dataKey="wickets" fill="#22c55e" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-8">No bowling data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="squad">
          <Card>
            <CardHeader>
              <CardTitle>Squad</CardTitle>
            </CardHeader>
            <CardContent>
              {players && players.length > 0 ? (
                <DataTable columns={playerColumns} data={players} searchKey="name" searchPlaceholder="Search players..." />
              ) : (
                <p className="text-muted-foreground text-center py-8">No squad data available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
