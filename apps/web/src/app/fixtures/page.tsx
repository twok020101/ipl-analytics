"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { fetchFixtures, fetchSquads, fetchTeams } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CalendarDays,
  MapPin,
  Clock,
  Trophy,
  ChevronDown,
  ChevronUp,
  Users,
  Target,
} from "lucide-react";
import { cn, getTeamColor, getTeamTextColor } from "@/lib/utils";
import type { Fixture, Squad } from "@/lib/types";

function FixtureCard({
  fixture,
  teams,
  onAnalyze,
}: {
  fixture: Fixture;
  teams: { id: number; short_name: string }[];
  onAnalyze: (f: Fixture) => void;
}) {
  const isCompleted = fixture.matchEnded;
  const isLive = fixture.matchStarted && !fixture.matchEnded;
  const today = new Date().toISOString().split("T")[0];
  const isToday = fixture.date === today;

  const matchDate = new Date(fixture.dateTimeGMT + "Z");
  const timeStr = matchDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const dateStr = matchDate.toLocaleDateString([], { month: "short", day: "numeric" });

  return (
    <Card
      className={cn(
        "transition-all hover:border-border-strong",
        isLive && "border-green-500/50 bg-green-500/5",
        isToday && !isLive && !isCompleted && "border-primary/50 bg-primary/5"
      )}
    >
      <CardContent className="p-5">
        {/* Status bar */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">{dateStr}</span>
            <Clock className="h-3.5 w-3.5 text-muted-foreground ml-1" />
            <span className="text-xs text-muted-foreground">{timeStr} IST</span>
          </div>
          {isLive && (
            <Badge className="bg-green-500 text-white animate-pulse text-xs">LIVE</Badge>
          )}
          {isCompleted && (
            <Badge className="bg-muted-strong text-muted-foreground text-xs">Completed</Badge>
          )}
          {isToday && !isLive && !isCompleted && (
            <Badge className="bg-primary/20 text-primary text-xs">Today</Badge>
          )}
          {!isToday && !isLive && !isCompleted && (
            <Badge variant="outline" className="text-xs">Upcoming</Badge>
          )}
        </div>

        {/* Teams */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            {fixture.team1_img && (
              <img src={fixture.team1_img} alt={fixture.team1} className="w-10 h-10 rounded-lg object-contain bg-muted p-1" />
            )}
            <div>
              <p className={cn("font-bold text-lg", getTeamTextColor(fixture.team1))}>
                {fixture.team1}
              </p>
              <p className="text-xs text-muted-foreground">{fixture.team1_name}</p>
            </div>
          </div>

          <div className="flex flex-col items-center px-4">
            <span className="text-xs font-bold text-muted-foreground bg-muted px-3 py-1 rounded-full">
              VS
            </span>
          </div>

          <div className="flex items-center gap-3 flex-1 justify-end text-right">
            <div>
              <p className={cn("font-bold text-lg", getTeamTextColor(fixture.team2))}>
                {fixture.team2}
              </p>
              <p className="text-xs text-muted-foreground">{fixture.team2_name}</p>
            </div>
            {fixture.team2_img && (
              <img src={fixture.team2_img} alt={fixture.team2} className="w-10 h-10 rounded-lg object-contain bg-muted p-1" />
            )}
          </div>
        </div>

        {/* Venue */}
        <div className="flex items-center gap-1.5 mt-4 text-xs text-muted-foreground">
          <MapPin className="h-3 w-3" />
          <span className="truncate">{fixture.venue}</span>
        </div>

        {/* Result or Predict */}
        {isCompleted ? (
          <div className="mt-3 p-2.5 rounded-lg bg-muted/50 text-center">
            <p className="text-sm font-medium text-amber-400">{fixture.status}</p>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="w-full mt-3"
            onClick={() => onAnalyze(fixture)}
          >
            <Target className="h-3.5 w-3.5 mr-1.5" /> Analyze Match
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function SquadCard({ squad }: { squad: Squad }) {
  const [expanded, setExpanded] = useState(false);
  const roleCounts = squad.players.reduce((acc, p) => {
    const r = p.role || "Unknown";
    acc[r] = (acc[r] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {squad.img && (
              <img src={squad.img} alt={squad.short_name} className="w-10 h-10 rounded-lg object-contain bg-muted p-1" />
            )}
            <div>
              <p className={cn("font-bold text-lg", getTeamTextColor(squad.short_name))}>
                {squad.name}
              </p>
              <p className="text-xs text-muted-foreground">{squad.players.length} players</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>

        <div className="flex flex-wrap gap-1.5 mt-3">
          {Object.entries(roleCounts).map(([role, count]) => (
            <Badge key={role} variant="outline" className="text-xs">
              {role}: {count}
            </Badge>
          ))}
        </div>

        {expanded && (
          <div className="mt-4 space-y-1.5 max-h-80 overflow-y-auto">
            {squad.players.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <img
                  src={p.playerImg}
                  alt={p.name}
                  className="w-8 h-8 rounded-full object-cover bg-muted"
                  onError={(e) => { (e.target as HTMLImageElement).src = "https://h.cricapi.com/img/icon512.png"; }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{p.name}</p>
                  <p className="text-xs text-muted-foreground">{p.role} · {p.country}</p>
                </div>
                {p.battingStyle && (
                  <span className="text-xs text-muted-foreground hidden sm:block">{p.battingStyle}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function FixturesPage() {
  const { data: fixtures, isLoading } = useQuery({
    queryKey: ["fixtures"],
    queryFn: fetchFixtures,
  });
  const { data: squads } = useQuery({
    queryKey: ["squads"],
    queryFn: fetchSquads,
  });
  const { data: teams } = useQuery({
    queryKey: ["teams"],
    queryFn: fetchTeams,
  });

  const router = useRouter();

  const today = new Date().toISOString().split("T")[0];
  const completed = (fixtures || []).filter((f) => f.matchEnded);
  const upcoming = (fixtures || []).filter((f) => !f.matchEnded);
  const todayMatches = (fixtures || []).filter((f) => f.date === today);

  const handleAnalyze = (f: Fixture) => {
    const params = new URLSearchParams();
    params.set("team1", f.team1);
    params.set("team2", f.team2);
    if (f.venue) params.set("venue", f.venue);
    params.set("auto", "true");
    router.push(`/predict?${params.toString()}`);
  };

  const teamsList = (teams || []).map((t) => ({ id: t.id, short_name: t.short_name }));

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-orange-600/20 via-red-600/10 to-yellow-600/20 border border-border p-8">
        <div className="relative">
          <div className="flex items-center gap-3 mb-2">
            <Trophy className="h-8 w-8 text-amber-400" />
            <h1 className="text-3xl font-extrabold bg-gradient-to-r from-amber-400 via-orange-400 to-red-400 bg-clip-text text-transparent">
              Indian Premier League 2026
            </h1>
          </div>
          <p className="text-muted-foreground">
            Season starts March 28 · 70 matches · 10 teams
          </p>
          <div className="flex items-center gap-6 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
              <span className="text-muted-foreground">{completed.length} completed</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-primary" />
              <span className="text-muted-foreground">{upcoming.length} upcoming</span>
            </div>
            {todayMatches.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="text-amber-400 font-medium">{todayMatches.length} today</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="upcoming">
        <TabsList>
          <TabsTrigger value="upcoming">Upcoming ({upcoming.length})</TabsTrigger>
          <TabsTrigger value="completed">Results ({completed.length})</TabsTrigger>
          <TabsTrigger value="squads">Squads ({Object.keys(squads || {}).length})</TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming">
          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-52" />)}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {upcoming.map((f) => (
                <FixtureCard key={f.id} fixture={f} teams={teamsList} onAnalyze={handleAnalyze} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="completed">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {completed.map((f) => (
              <FixtureCard key={f.id} fixture={f} teams={teamsList} onAnalyze={handleAnalyze} />
            ))}
          </div>
          {completed.length === 0 && (
            <Card>
              <CardContent className="p-12 text-center text-muted-foreground">
                No completed matches yet.
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="squads">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.values(squads || {}).sort((a, b) => a.name.localeCompare(b.name)).map((squad) => (
              <SquadCard key={squad.short_name} squad={squad} />
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
