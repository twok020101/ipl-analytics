"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { fetchPlayer, fetchPlayerBatting, fetchPlayerBowling, fetchPlayerForm } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { SpiderChart } from "@/components/charts/SpiderChart";
import { FormLineChart } from "@/components/charts/FormLineChart";
import { DataTable } from "@/components/tables/DataTable";
import { ArrowLeft, User, Award, TrendingUp } from "lucide-react";
import Link from "next/link";
import type { ColumnDef } from "@tanstack/react-table";
import type { PlayerBattingStats, PlayerBowlingStats } from "@/lib/types";

export default function PlayerDetailPage() {
  const params = useParams();
  const playerId = Number(params.playerId);

  const { data: player, isLoading } = useQuery({
    queryKey: ["player", playerId],
    queryFn: () => fetchPlayer(playerId),
  });

  const { data: battingData } = useQuery({
    queryKey: ["player-batting", playerId],
    queryFn: () => fetchPlayerBatting(playerId),
    enabled: !!player,
  });

  const { data: bowlingData } = useQuery({
    queryKey: ["player-bowling", playerId],
    queryFn: () => fetchPlayerBowling(playerId),
    enabled: !!player,
  });

  const { data: formData } = useQuery({
    queryKey: ["player-form", playerId],
    queryFn: () => fetchPlayerForm(playerId),
    enabled: !!player,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-48" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!player) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground text-lg">Player not found</p>
        <Link href="/players" className="text-primary mt-2 hover:underline">Back to Players</Link>
      </div>
    );
  }

  // Extract career stats from nested structure
  const careerBat = player.career_batting;
  const careerBowl = player.career_bowling;
  const sr = careerBat?.strike_rate || 0;
  const runs = careerBat?.runs || 0;
  const wickets = careerBowl?.wickets || 0;
  const matches = careerBat?.matches || 0;

  // Batting stats come wrapped: { player_id, player_name, batting: [...] }
  const battingStats: PlayerBattingStats[] = (battingData as unknown as { batting?: PlayerBattingStats[] })?.batting || (Array.isArray(battingData) ? battingData : []);
  const bowlingStats: PlayerBowlingStats[] = (bowlingData as unknown as { bowling?: PlayerBowlingStats[] })?.bowling || (Array.isArray(bowlingData) ? bowlingData : []);

  // Spider chart data
  const formIndex = formData?.form_index || 50;
  const spiderData = [
    { axis: "Power", value: Math.min(100, sr / 2) },
    { axis: "Consistency", value: Math.min(100, (runs / Math.max(matches, 1)) * 3) },
    { axis: "Strike Rate", value: Math.min(100, (sr - 80) * 2) },
    { axis: "Form", value: Math.min(100, formIndex) },
    { axis: "Versatility", value: wickets > 20 && runs > 500 ? 80 : wickets > 5 ? 55 : 35 },
    { axis: "Experience", value: Math.min(100, matches / 2.5) },
  ];

  // Form chart data
  const formChartData = (formData?.recent_innings || []).map((inn: { runs: number; balls: number; strike_rate: number }, i: number) => ({
    label: `#${i + 1}`,
    runs: inn.runs,
    balls: inn.balls,
  }));

  const battingColumns: ColumnDef<PlayerBattingStats, unknown>[] = [
    { accessorKey: "season", header: "Season" },
    { accessorKey: "matches", header: "M" },
    { accessorKey: "innings", header: "Inn" },
    { accessorKey: "runs", header: "Runs" },
    { accessorKey: "average", header: "Avg", cell: ({ row }) => row.original.average?.toFixed(2) || "-" },
    { accessorKey: "strike_rate", header: "SR", cell: ({ row }) => row.original.strike_rate?.toFixed(2) || "-" },
    { accessorKey: "fifties", header: "50s" },
    { accessorKey: "hundreds", header: "100s" },
    { accessorKey: "fours", header: "4s" },
    { accessorKey: "sixes", header: "6s" },
    { accessorKey: "highest_score", header: "HS" },
  ];

  const bowlingColumns: ColumnDef<PlayerBowlingStats, unknown>[] = [
    { accessorKey: "season", header: "Season" },
    { accessorKey: "matches", header: "M" },
    { accessorKey: "wickets", header: "Wkts" },
    { accessorKey: "economy", header: "Econ", cell: ({ row }) => row.original.economy?.toFixed(2) || "-" },
    { accessorKey: "average", header: "Avg", cell: ({ row }) => row.original.average?.toFixed(2) || "-" },
    { accessorKey: "best_figures", header: "Best" },
  ];

  const teamsStr = player.teams?.map((t) => typeof t === "string" ? t : t.short_name).join(", ") || "";
  const showBowling = bowlingStats.length > 0;

  return (
    <div className="space-y-6">
      <Link href="/players" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to Players
      </Link>

      {/* Player Header */}
      <div className="rounded-2xl border border-gray-800 bg-gradient-to-br from-gray-900 to-gray-900/50 p-8">
        <div className="flex items-start gap-6">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10">
            <User className="h-10 w-10 text-primary" />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl font-bold">{player.name}</h1>
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              {player.role && <Badge>{player.role}</Badge>}
              {player.batting_style && <Badge variant="outline">{player.batting_style}</Badge>}
              {player.bowling_style && <Badge variant="outline">{player.bowling_style}</Badge>}
            </div>
            {teamsStr && <p className="text-sm text-muted-foreground mt-2">{teamsStr}</p>}
          </div>
          <div className="hidden lg:grid grid-cols-4 gap-4">
            <div className="text-center p-3 rounded-xl bg-gray-800/50">
              <p className="text-xs text-muted-foreground">Matches</p>
              <p className="text-xl font-bold">{matches}</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-gray-800/50">
              <p className="text-xs text-muted-foreground">Runs</p>
              <p className="text-xl font-bold text-amber-400">{runs.toLocaleString()}</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-gray-800/50">
              <p className="text-xs text-muted-foreground">Wickets</p>
              <p className="text-xl font-bold text-green-400">{wickets}</p>
            </div>
            <div className="text-center p-3 rounded-xl bg-gray-800/50">
              <p className="text-xs text-muted-foreground">SR</p>
              <p className="text-xl font-bold text-primary">{sr.toFixed(1)}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Spider Chart */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="h-5 w-5 text-primary" />
              Player Profile
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SpiderChart data={spiderData} color="#3b82f6" name={player.name} />
          </CardContent>
        </Card>

        {/* Form Chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Recent Form
              {formData?.trend && (
                <Badge className={
                  formData.trend === "improving" ? "bg-green-500/10 text-green-400" :
                  formData.trend === "declining" ? "bg-red-500/10 text-red-400" :
                  "bg-gray-500/10 text-gray-400"
                }>
                  {formData.trend}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {formChartData.length > 0 ? (
              <FormLineChart data={formChartData} color="#3b82f6" />
            ) : (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                No recent form data available
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Stats Tables */}
      <Tabs defaultValue="batting">
        <TabsList>
          <TabsTrigger value="batting">Batting Stats</TabsTrigger>
          {showBowling && <TabsTrigger value="bowling">Bowling Stats</TabsTrigger>}
        </TabsList>

        <TabsContent value="batting">
          <Card>
            <CardHeader><CardTitle>Season-by-Season Batting</CardTitle></CardHeader>
            <CardContent>
              {battingStats.length > 0 ? (
                <DataTable columns={battingColumns} data={battingStats} pageSize={20} />
              ) : (
                <p className="text-muted-foreground text-center py-8">No batting stats available</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {showBowling && (
          <TabsContent value="bowling">
            <Card>
              <CardHeader><CardTitle>Season-by-Season Bowling</CardTitle></CardHeader>
              <CardContent>
                <DataTable columns={bowlingColumns} data={bowlingStats} pageSize={20} />
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
