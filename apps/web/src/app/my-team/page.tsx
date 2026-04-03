"use client";

/**
 * My Team dashboard — scoped view for the user's org-linked IPL team.
 *
 * Shows team record, squad, upcoming matches, recent results, and top
 * performers. Only visible when the org is linked to a team (admin sets
 * this via /admin/users or the /auth/org/team API).
 *
 * If no team is linked, shows a prompt for the admin to link one.
 */

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { fetchMyTeamDashboard, type MyTeamDashboard } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, getTeamTextColor, getTeamBg } from "@/lib/utils";
import {
  Shield,
  Users,
  Trophy,
  Calendar,
  Loader2,
  AlertTriangle,
  Swords,
  Target,
  Crown,
  Globe,
} from "lucide-react";
import Link from "next/link";

/** Compact stat card used across the dashboard */
function StatBox({ label, value, sub, color }: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-gray-800/50 rounded-lg p-3 text-center">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-2xl font-bold mt-0.5", color)}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

export default function MyTeamPage() {
  const { user } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ["my-team-dashboard"],
    queryFn: fetchMyTeamDashboard,
    enabled: !!user,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  // No team linked — show setup prompt
  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Shield className="h-16 w-16 text-muted-foreground/30" />
        <h2 className="text-xl font-bold">No Team Linked</h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Your organization isn&apos;t linked to an IPL team yet. Ask your admin to link
          a team in the User Management page to unlock your team-specific dashboard.
        </p>
        {user?.role === "admin" && (
          <Link
            href="/admin/users"
            className="mt-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            Go to User Management
          </Link>
        )}
      </div>
    );
  }

  const team = data.team;
  const record = data.season_record;

  return (
    <div className="space-y-6">
      {/* Team header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className={cn("text-2xl font-bold flex items-center gap-2", getTeamTextColor(team.short_name))}>
            <Shield className="h-6 w-6" />
            {team.name}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            IPL 2026 — Your team&apos;s command center
          </p>
        </div>
        <Badge className={cn("text-sm px-3 py-1", getTeamBg(team.short_name), getTeamTextColor(team.short_name))}>
          {team.short_name}
        </Badge>
      </div>

      {/* Season record stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatBox label="Played" value={record.played} />
        <StatBox label="Won" value={record.won} color="text-green-400" />
        <StatBox label="Lost" value={record.lost} color="text-red-400" />
        <StatBox label="Points" value={record.points} color="text-primary" />
      </div>

      {/* Two-column layout: upcoming + recent */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Upcoming matches */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Calendar className="h-4 w-4 text-blue-400" />
              Upcoming Matches
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.upcoming_matches.length > 0 ? (
              data.upcoming_matches.map((m) => (
                <div key={m.match_id} className="flex items-center justify-between p-2.5 bg-gray-800/30 rounded-lg">
                  <div>
                    <p className="text-sm font-medium">
                      vs <span className={getTeamTextColor(m.opponent)}>{m.opponent}</span>
                    </p>
                    {m.venue && <p className="text-xs text-muted-foreground">{m.venue}</p>}
                  </div>
                  {m.date && <span className="text-xs text-muted-foreground">{m.date}</span>}
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">No upcoming matches</p>
            )}
          </CardContent>
        </Card>

        {/* Recent results */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-400" />
              Recent Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.recent_results.length > 0 ? (
              data.recent_results.map((m) => (
                <div key={m.match_id} className="flex items-center justify-between p-2.5 bg-gray-800/30 rounded-lg">
                  <div>
                    <p className="text-sm font-medium">
                      vs <span className={getTeamTextColor(m.opponent)}>{m.opponent}</span>
                    </p>
                    {m.margin && <p className="text-xs text-muted-foreground">{m.margin}</p>}
                  </div>
                  <Badge className={cn(
                    "text-xs",
                    m.result === "Won" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400",
                  )}>
                    {m.result}
                  </Badge>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">No results yet</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Top performers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top batters */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Swords className="h-4 w-4 text-green-400" />
              Top Batters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.top_batters.map((b, i) => (
                <div key={i} className="flex items-center justify-between py-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-4">{i + 1}</span>
                    <span className="text-sm font-medium">{b.name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-foreground font-medium">{b.runs} runs</span>
                    <span className="text-muted-foreground">SR {b.strike_rate}</span>
                  </div>
                </div>
              ))}
              {data.top_batters.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">No batting data</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Top bowlers */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Target className="h-4 w-4 text-red-400" />
              Top Bowlers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.top_bowlers.map((b, i) => (
                <div key={i} className="flex items-center justify-between py-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-4">{i + 1}</span>
                    <span className="text-sm font-medium">{b.name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-foreground font-medium">{b.wickets} wkts</span>
                    <span className="text-muted-foreground">Eco {b.economy}</span>
                  </div>
                </div>
              ))}
              {data.top_bowlers.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-4">No bowling data</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Squad */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" />
            Squad ({data.squad_size} players)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {data.squad.map((p) => (
              <Link
                key={p.id}
                href={`/players/${p.id}`}
                className="flex items-center gap-2 p-2.5 bg-gray-800/30 rounded-lg hover:bg-gray-800/60 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate">{p.name}</span>
                    {p.is_captain && <Crown className="h-3 w-3 text-amber-400 shrink-0" />}
                  </div>
                  <span className="text-xs text-muted-foreground">{p.role || "Player"}</span>
                </div>
                {p.country && p.country !== "India" && (
                  <Globe className="h-3 w-3 text-blue-400 shrink-0" />
                )}
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
