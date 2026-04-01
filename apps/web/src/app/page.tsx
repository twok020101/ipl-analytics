"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import {
  fetchDashboardStats,
  fetchTeams,
  fetchUpcomingFixtures,
  fetchFixtures,
  predictMatch,
} from "@/lib/api";
import { StatCard } from "@/components/cards/StatCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { WinProbGauge } from "@/components/charts/WinProbGauge";
import {
  Users,
  MapPin,
  Calendar,
  Trophy,
  TrendingUp,
  Target,
  CalendarDays,
  Clock,
  ArrowRight,
} from "lucide-react";
import { useState } from "react";
import Link from "next/link";
import { cn, getTeamTextColor } from "@/lib/utils";
import type { MatchPrediction } from "@/lib/types";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  });

  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: fetchTeams,
  });

  const { data: upcomingFixtures } = useQuery({
    queryKey: ["upcoming-fixtures"],
    queryFn: () => fetchUpcomingFixtures(6),
  });

  const { data: allFixtures } = useQuery({
    queryKey: ["fixtures"],
    queryFn: fetchFixtures,
  });

  const [team1, setTeam1] = useState("");
  const [team2, setTeam2] = useState("");
  const [prediction, setPrediction] = useState<MatchPrediction | null>(null);

  const predictMutation = useMutation({
    mutationFn: predictMatch,
    onSuccess: (data) => setPrediction(data),
  });

  const teamOptions = (teams || [])
    .filter((t) => t.is_active)
    .map((t) => ({ value: t.id.toString(), label: t.name }));

  const completed = (allFixtures || []).filter((f) => f.matchEnded);
  const totalMatches = (allFixtures || []).length;
  const today = new Date().toISOString().split("T")[0];
  const todayMatches = (allFixtures || []).filter((f) => f.date === today);

  return (
    <div className="space-y-8">
      {/* IPL 2026 Live Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-orange-600/20 via-red-600/10 to-yellow-600/20 border border-gray-800 p-8 lg:p-10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-amber-500/5 via-transparent to-transparent" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-3">
            <Trophy className="h-8 w-8 text-amber-400" />
            <h1 className="text-3xl lg:text-4xl font-extrabold bg-gradient-to-r from-amber-400 via-orange-400 to-red-400 bg-clip-text text-transparent">
              IPL 2026 is Live
            </h1>
            {todayMatches.length > 0 && (
              <Badge className="bg-green-500 text-white animate-pulse ml-2">
                {todayMatches.length} match{todayMatches.length > 1 ? "es" : ""} today
              </Badge>
            )}
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl">
            {completed.length} of {totalMatches} matches played · 10 teams battling for the trophy
          </p>
          {totalMatches > 0 && (
            <div className="mt-4 max-w-md">
              <div className="flex justify-between text-xs text-muted-foreground mb-1">
                <span>Season Progress</span>
                <span>{Math.round((completed.length / totalMatches) * 100)}%</span>
              </div>
              <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all duration-700"
                  style={{ width: `${(completed.length / totalMatches) * 100}%` }}
                />
              </div>
            </div>
          )}
          <Link href="/fixtures" className="inline-flex items-center gap-1.5 mt-4 text-sm font-medium text-primary hover:underline">
            View all fixtures & squads <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      {/* Today & Upcoming Matches */}
      {upcomingFixtures && upcomingFixtures.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-primary" />
            {todayMatches.length > 0 ? "Today & Upcoming" : "Upcoming Matches"}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {upcomingFixtures.map((fix) => {
              const isToday = fix.date === today;
              const matchDate = new Date(fix.dateTimeGMT + "Z");
              const timeStr = matchDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
              const dateStr = matchDate.toLocaleDateString([], { month: "short", day: "numeric" });
              return (
                <Card
                  key={fix.id}
                  className={cn(
                    "transition-all hover:border-gray-700",
                    isToday && "border-amber-500/40 bg-amber-500/5"
                  )}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <CalendarDays className="h-3 w-3" />
                        {dateStr}
                        <Clock className="h-3 w-3 ml-1" />
                        {timeStr}
                      </div>
                      {isToday ? (
                        <Badge className="bg-amber-500/20 text-amber-400 text-xs">Today</Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs">Upcoming</Badge>
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {fix.team1_img && (
                          <img src={fix.team1_img} alt="" className="w-8 h-8 rounded object-contain bg-gray-800 p-0.5" />
                        )}
                        <span className={cn("font-bold", getTeamTextColor(fix.team1))}>{fix.team1}</span>
                      </div>
                      <span className="text-xs text-muted-foreground font-bold">vs</span>
                      <div className="flex items-center gap-2">
                        <span className={cn("font-bold", getTeamTextColor(fix.team2))}>{fix.team2}</span>
                        {fix.team2_img && (
                          <img src={fix.team2_img} alt="" className="w-8 h-8 rounded object-contain bg-gray-800 p-0.5" />
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1 truncate">
                      <MapPin className="h-3 w-3 shrink-0" />
                      {fix.venue}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Stats */}
      {statsLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Matches" value={stats?.total_matches?.toLocaleString() || "0"} icon={Trophy} />
          <StatCard label="Total Players" value={stats?.total_players?.toLocaleString() || "0"} icon={Users} />
          <StatCard label="Venues" value={stats?.total_venues?.toLocaleString() || "0"} icon={MapPin} />
          <StatCard label="Seasons" value={stats?.total_seasons?.toLocaleString() || "0"} icon={Calendar} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Predict */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5 text-primary" />
              Quick Predict
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select options={teamOptions} placeholder="Select Team 1" value={team1} onChange={(e) => setTeam1(e.target.value)} />
            <div className="flex items-center justify-center">
              <span className="text-xs font-bold text-muted-foreground bg-gray-800 px-3 py-1 rounded-full">VS</span>
            </div>
            <Select options={teamOptions.filter((t) => t.value !== team1)} placeholder="Select Team 2" value={team2} onChange={(e) => setTeam2(e.target.value)} />
            <Button className="w-full" size="lg" disabled={!team1 || !team2 || predictMutation.isPending} onClick={() => predictMutation.mutate({ team1_id: Number(team1), team2_id: Number(team2) })}>
              {predictMutation.isPending ? "Predicting..." : "Predict Winner"}
            </Button>
            {prediction && (
              <div className="mt-4">
                <WinProbGauge team1={prediction.team1.short_name} team2={prediction.team2.short_name} team1Prob={prediction.prediction.team1_prob} team2Prob={prediction.prediction.team2_prob} />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Run Scorers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-amber-400" />
              All-Time Top Run Scorers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(stats?.top_run_scorers || []).map((player, i) => (
                <div key={player.name} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-800/50 transition-colors">
                  <span className="flex items-center justify-center h-7 w-7 rounded-full bg-amber-500/10 text-amber-400 text-xs font-bold">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{player.name}</p>
                    <p className="text-xs text-muted-foreground">{player.matches} matches</p>
                  </div>
                  <span className="text-sm font-bold text-amber-400">{player.runs.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Wicket Takers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5 text-green-400" />
              All-Time Top Wicket Takers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(stats?.top_wicket_takers || []).map((player, i) => (
                <div key={player.name} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-800/50 transition-colors">
                  <span className="flex items-center justify-center h-7 w-7 rounded-full bg-green-500/10 text-green-400 text-xs font-bold">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{player.name}</p>
                    <p className="text-xs text-muted-foreground">{player.matches} matches</p>
                  </div>
                  <span className="text-sm font-bold text-green-400">{player.wickets}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Results */}
      {completed.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="h-5 w-5 text-amber-400" />
              Recent IPL 2026 Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {completed.slice(-4).reverse().map((fix) => (
                <div key={fix.id} className="flex items-center justify-between p-4 rounded-lg bg-gray-800/50">
                  <div className="flex items-center gap-3">
                    {fix.team1_img && <img src={fix.team1_img} alt="" className="w-8 h-8 rounded object-contain bg-gray-800 p-0.5" />}
                    <span className={cn("font-bold", getTeamTextColor(fix.team1))}>{fix.team1}</span>
                    <span className="text-xs text-muted-foreground">vs</span>
                    <span className={cn("font-bold", getTeamTextColor(fix.team2))}>{fix.team2}</span>
                    {fix.team2_img && <img src={fix.team2_img} alt="" className="w-8 h-8 rounded object-contain bg-gray-800 p-0.5" />}
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-medium text-amber-400">{fix.status}</p>
                    <p className="text-xs text-muted-foreground">{fix.date}</p>
                  </div>
                </div>
              ))}
            </div>
            <Link href="/fixtures" className="inline-flex items-center gap-1.5 mt-4 text-sm font-medium text-primary hover:underline">
              View all fixtures <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
