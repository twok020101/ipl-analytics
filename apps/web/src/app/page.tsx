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
  Radio,
  BrainCircuit,
  Activity,
  Zap,
} from "lucide-react";
import { useState } from "react";
import Link from "next/link";
import { cn, getTeamTextColor, getTeamColor } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import type { MatchPrediction } from "@/lib/types";

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function getCountdown(dateTimeGMT: string) {
  const diff = new Date(dateTimeGMT + "Z").getTime() - Date.now();
  if (diff <= 0) return null;
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${mins}m`;
}

export default function DashboardPage() {
  const { user } = useAuth();
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

  const today = new Date().toISOString().split("T")[0];
  const todayMatches = (allFixtures || []).filter((f) => f.date === today && !f.matchEnded);
  const nextMatch = (upcomingFixtures || [])[0];
  const completed = (allFixtures || []).filter((f) => f.matchEnded);
  const totalMatches = (allFixtures || []).length;

  return (
    <div className="space-y-8">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            {getGreeting()}, {user?.name?.split(" ")[0] || "Analyst"}
          </h1>
          <p className="text-muted-foreground mt-1">
            {new Date().toLocaleDateString([], { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
            {totalMatches > 0 && (
              <span className="ml-2 text-foreground font-medium">
                · {completed.length}/{totalMatches} matches played
              </span>
            )}
          </p>
        </div>
        {todayMatches.length > 0 && (
          <Link href="/live">
            <Badge className="bg-green-500/15 text-green-400 border border-green-500/30 gap-1.5 px-3 py-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              {todayMatches.length} match{todayMatches.length > 1 ? "es" : ""} today
            </Badge>
          </Link>
        )}
      </div>

      {/* Stat Cards */}
      {statsLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Matches" value={stats?.total_matches ?? 0} icon={Trophy} delay={0} />
          <StatCard label="Total Players" value={stats?.total_players ?? 0} icon={Users} delay={0.05} />
          <StatCard label="Venues" value={stats?.total_venues ?? 0} icon={MapPin} delay={0.1} />
          <StatCard label="Seasons" value={stats?.total_seasons ?? 0} icon={Calendar} delay={0.15} />
        </div>
      )}

      {/* Today's Spotlight OR Next Match */}
      {todayMatches.length > 0 ? (
        <div>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-400" />
            Today&apos;s Matches
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {todayMatches.map((fix) => {
              const matchDate = new Date(fix.dateTimeGMT + "Z");
              const timeStr = matchDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
              const t1Color = getTeamColor(fix.team1);
              const t2Color = getTeamColor(fix.team2);
              return (
                <Card key={fix.id} className="border-amber-500/30 overflow-hidden">
                  <div className="h-1 w-full" style={{ background: `linear-gradient(to right, ${t1Color}, ${t2Color})` }} />
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-4">
                      <Badge className="bg-amber-500/15 text-amber-400 border border-amber-500/30">
                        <Clock className="h-3 w-3 mr-1" />
                        {timeStr} IST
                      </Badge>
                      {fix.matchStarted && (
                        <Badge className="bg-green-500 text-white animate-pulse">LIVE</Badge>
                      )}
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 flex-1">
                        {fix.team1_img && (
                          <img src={fix.team1_img} alt="" className="w-10 h-10 rounded-lg object-contain bg-muted p-1" />
                        )}
                        <span className={cn("font-bold text-lg", getTeamTextColor(fix.team1))}>{fix.team1}</span>
                      </div>
                      <span className="text-sm font-bold text-muted-foreground px-3">vs</span>
                      <div className="flex items-center gap-3 flex-1 justify-end">
                        <span className={cn("font-bold text-lg", getTeamTextColor(fix.team2))}>{fix.team2}</span>
                        {fix.team2_img && (
                          <img src={fix.team2_img} alt="" className="w-10 h-10 rounded-lg object-contain bg-muted p-1" />
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-3 flex items-center gap-1">
                      <MapPin className="h-3 w-3" /> {fix.venue}
                    </p>
                    <div className="flex gap-2 mt-4">
                      {fix.matchStarted ? (
                        <Link href="/live" className="flex-1">
                          <Button className="w-full" size="sm">
                            <Radio className="h-3.5 w-3.5 mr-1.5" /> Watch Live
                          </Button>
                        </Link>
                      ) : (
                        <Link href={`/predict?team1=${fix.team1}&team2=${fix.team2}&venue=${encodeURIComponent(fix.venue || "")}&auto=true`} className="flex-1">
                          <Button variant="outline" className="w-full" size="sm">
                            <Target className="h-3.5 w-3.5 mr-1.5" /> Analyze
                          </Button>
                        </Link>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ) : nextMatch ? (
        <Card className="border-primary/20">
          <CardContent className="p-5 sm:p-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Next Match</p>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    {nextMatch.team1_img && <img src={nextMatch.team1_img} alt="" className="w-8 h-8 rounded object-contain bg-muted p-0.5" />}
                    <span className={cn("font-bold text-lg", getTeamTextColor(nextMatch.team1))}>{nextMatch.team1}</span>
                  </div>
                  <span className="text-muted-foreground font-bold">vs</span>
                  <div className="flex items-center gap-2">
                    <span className={cn("font-bold text-lg", getTeamTextColor(nextMatch.team2))}>{nextMatch.team2}</span>
                    {nextMatch.team2_img && <img src={nextMatch.team2_img} alt="" className="w-8 h-8 rounded object-contain bg-muted p-0.5" />}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                  <MapPin className="h-3 w-3" /> {nextMatch.venue}
                </p>
              </div>
              <div className="flex flex-col items-center sm:items-end gap-1">
                {(() => {
                  const cd = getCountdown(nextMatch.dateTimeGMT);
                  return cd ? (
                    <>
                      <span className="text-2xl font-bold text-primary tabular-nums">{cd}</span>
                      <span className="text-xs text-muted-foreground">until start</span>
                    </>
                  ) : (
                    <Badge className="bg-amber-500/15 text-amber-400">Starting soon</Badge>
                  );
                })()}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Quick Actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { href: "/live", icon: Radio, label: "Live Scores", color: "text-green-400", bg: "bg-green-500/10" },
          { href: "/standings", icon: Trophy, label: "Standings", color: "text-amber-400", bg: "bg-amber-500/10" },
          { href: "/predict", icon: Target, label: "Match Analyzer", color: "text-blue-400", bg: "bg-blue-500/10" },
          { href: "/ai-insights", icon: BrainCircuit, label: "AI Insights", color: "text-purple-400", bg: "bg-purple-500/10" },
        ].map((action) => (
          <Link key={action.href} href={action.href}>
            <Card className="hover:border-border-strong transition-all group cursor-pointer">
              <CardContent className="p-4 flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", action.bg)}>
                  <action.icon className={cn("h-4 w-4", action.color)} />
                </div>
                <span className="text-sm font-medium group-hover:text-foreground transition-colors">{action.label}</span>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Quick Predict + Leaderboards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
              <span className="text-xs font-bold text-muted-foreground bg-muted px-3 py-1 rounded-full">VS</span>
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
                <div key={player.name} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/50 transition-colors">
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

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-green-400" />
              All-Time Top Wicket Takers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(stats?.top_wicket_takers || []).map((player, i) => (
                <div key={player.name} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/50 transition-colors">
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
    </div>
  );
}
