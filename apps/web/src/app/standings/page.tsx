"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSeasons, fetchSeasonStandings } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Trophy } from "lucide-react";
import { cn, getTeamTextColor } from "@/lib/utils";

export default function StandingsPage() {
  const [season, setSeason] = useState("2024");

  const { data: seasons } = useQuery({
    queryKey: ["seasons"],
    queryFn: fetchSeasons,
  });

  const { data: standingsData, isLoading, isError } = useQuery({
    queryKey: ["standings", season],
    queryFn: () => fetchSeasonStandings(season),
    enabled: !!season,
  });

  const standings = standingsData?.standings || standingsData || [];

  const seasonOptions = (seasons || [
    { season: "2024" }, { season: "2023" }, { season: "2022" }, { season: "2021" }, { season: "2020" },
    { season: "2019" }, { season: "2018" }, { season: "2017" }, { season: "2016" }, { season: "2015" },
    { season: "2014" }, { season: "2013" }, { season: "2012" }, { season: "2011" }, { season: "2010" },
    { season: "2009" }, { season: "2008" },
  ] as { season: string }[]).map((s) => ({ value: s.season, label: `IPL ${s.season}` }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-amber-400" />
            Standings
          </h1>
          <p className="text-muted-foreground mt-1">Points table for each IPL season</p>
        </div>
        <div className="w-48">
          <Select
            options={seasonOptions}
            value={season}
            onChange={(e) => setSeason(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>IPL {season} Points Table</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(10)].map((_, i) => <Skeleton key={i} className="h-12" />)}
            </div>
          ) : isError ? (
            <p className="text-muted-foreground text-center py-8">
              Failed to load standings. Ensure the API is running.
            </p>
          ) : (
            <div className="rounded-lg border border-gray-800 overflow-x-auto">
              <table className="w-full text-sm min-w-[480px]">
                <thead>
                  <tr className="bg-gray-800/50 border-b border-gray-800">
                    <th className="px-3 sm:px-4 py-3 text-left font-medium text-muted-foreground w-10">#</th>
                    <th className="px-3 sm:px-4 py-3 text-left font-medium text-muted-foreground">Team</th>
                    <th className="px-2 sm:px-4 py-3 text-center font-medium text-muted-foreground">P</th>
                    <th className="px-2 sm:px-4 py-3 text-center font-medium text-muted-foreground">W</th>
                    <th className="px-2 sm:px-4 py-3 text-center font-medium text-muted-foreground">L</th>
                    <th className="px-2 sm:px-4 py-3 text-center font-medium text-muted-foreground">NR</th>
                    <th className="px-2 sm:px-4 py-3 text-center font-medium text-muted-foreground">Pts</th>
                    <th className="px-2 sm:px-4 py-3 text-center font-medium text-muted-foreground">NRR</th>
                  </tr>
                </thead>
                <tbody>
                  {(Array.isArray(standings) ? standings : []).map((row, i) => (
                    <tr
                      key={row.team_name || row.team_id || i}
                      className={cn(
                        "border-b border-gray-800/50 transition-colors",
                        i % 2 === 0 ? "bg-transparent" : "bg-gray-900/30",
                        i < 4 && "bg-green-500/5 border-l-2 border-l-green-500"
                      )}
                    >
                      <td className="px-4 py-3 font-bold text-muted-foreground">{row.position}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={cn("font-semibold", getTeamTextColor(row.short_name || row.team_name))}>
                            {row.team_name}
                          </span>
                          {i < 4 && (
                            <Badge className="text-[10px] px-1.5 py-0 bg-green-500/10 text-green-400">Q</Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">{row.played}</td>
                      <td className="px-4 py-3 text-center font-medium text-green-400">{row.won}</td>
                      <td className="px-4 py-3 text-center font-medium text-red-400">{row.lost}</td>
                      <td className="px-4 py-3 text-center text-muted-foreground">{row.no_result}</td>
                      <td className="px-4 py-3 text-center font-bold text-primary">{row.points}</td>
                      <td className={cn(
                        "px-4 py-3 text-center font-medium",
                        row.nrr >= 0 ? "text-green-400" : "text-red-400"
                      )}>
                        {row.nrr >= 0 ? "+" : ""}{row.nrr.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
