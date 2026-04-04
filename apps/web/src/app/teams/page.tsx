"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchTeams } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Users, Trophy, TrendingUp } from "lucide-react";
import { cn, getTeamBg, getTeamTextColor, formatPercentage } from "@/lib/utils";
import Link from "next/link";
import { useState } from "react";

export default function TeamsPage() {
  const { data: teams, isLoading, isError } = useQuery({
    queryKey: ["teams"],
    queryFn: fetchTeams,
  });

  const [filter, setFilter] = useState<"all" | "active">("active");

  const filteredTeams = (teams || []).filter(
    (t) => filter === "all" || t.is_active
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Teams</h1>
          <p className="text-muted-foreground mt-1">All IPL franchises and their statistics</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={filter === "active" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("active")}
          >
            Active
          </Button>
          <Button
            variant={filter === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("all")}
          >
            All Teams
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(10)].map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : isError ? (
        <Card>
          <CardContent className="p-12 text-center">
            <p className="text-muted-foreground">Failed to load teams. Make sure the API is running.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTeams.map((team) => (
            <Link key={team.id} href={`/teams/${team.slug}`}>
              <Card className="h-full transition-all duration-300 hover:border-border-strong hover:shadow-lg hover:-translate-y-0.5 cursor-pointer group">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-bold group-hover:text-primary transition-colors">
                        {team.name}
                      </h3>
                      <Badge variant="outline" className={cn("mt-1", getTeamTextColor(team.short_name))}>
                        {team.short_name}
                      </Badge>
                    </div>
                    <div
                      className={cn(
                        "flex h-12 w-12 items-center justify-center rounded-xl",
                        getTeamBg(team.short_name)
                      )}
                    >
                      <Users className={cn("h-6 w-6", getTeamTextColor(team.short_name))} />
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between p-2 rounded-lg bg-muted/50">
                    <span className="text-xs text-muted-foreground">
                      {team.is_active ? "Active" : "Defunct"}
                    </span>
                    <Badge className={team.is_active ? "bg-green-500/10 text-green-400" : "bg-muted text-muted-foreground"}>
                      {team.short_name}
                    </Badge>
                  </div>

                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
