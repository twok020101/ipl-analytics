"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { fetchVenue } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/cards/StatCard";
import { MatchCard } from "@/components/cards/MatchCard";
import { RunRateBar } from "@/components/charts/RunRateBar";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, MapPin, Trophy, TrendingUp, Target, BarChart3 } from "lucide-react";
import Link from "next/link";

export default function VenueDetailPage() {
  const params = useParams();
  const venueId = Number(params.venueId);

  const { data: venue, isLoading } = useQuery({
    queryKey: ["venue", venueId],
    queryFn: () => fetchVenue(venueId),
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

  if (!venue) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="text-muted-foreground text-lg">Venue not found</p>
        <Link href="/venues" className="text-primary mt-2 hover:underline">Back to Venues</Link>
      </div>
    );
  }

  const avgScore = venue.avg_first_innings_score || 160;
  const phaseData = [
    { phase: "Powerplay", avgRuns: Math.round(avgScore * 0.3), avgRunRate: (avgScore * 0.3 / 6).toFixed(1) },
    { phase: "Middle", avgRuns: Math.round(avgScore * 0.42), avgRunRate: (avgScore * 0.42 / 9).toFixed(1) },
    { phase: "Death", avgRuns: Math.round(avgScore * 0.28), avgRunRate: (avgScore * 0.28 / 5).toFixed(1) },
  ];

  return (
    <div className="space-y-6">
      <Link href="/venues" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to Venues
      </Link>

      {/* Venue Header */}
      <div className="rounded-2xl border border-border bg-gradient-to-br from-card to-card/50 p-8">
        <div className="flex items-center gap-3 mb-2">
          <MapPin className="h-6 w-6 text-primary" />
          <h1 className="text-3xl font-bold">{venue.name}</h1>
        </div>
        <p className="text-muted-foreground">{venue.city}</p>
        <p className="text-sm text-muted-foreground mt-1">{venue.matches_played || 0} matches hosted</p>
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Avg 1st Inn Score"
          value={venue.avg_first_innings_score?.toFixed(0) || "-"}
          icon={TrendingUp}
        />
        <StatCard
          label="Avg 2nd Inn Score"
          value={venue.avg_second_innings_score?.toFixed(0) || "-"}
          icon={Target}
        />
        <StatCard
          label="Bat First Win %"
          value={`${venue.bat_first_win_pct?.toFixed(0) || "-"}%`}
          icon={Trophy}
        />
        <StatCard
          label="Highest Score"
          value={venue.highest_score || "-"}
          icon={BarChart3}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scoring by Phase */}
        <Card>
          <CardHeader>
            <CardTitle>Scoring by Phase</CardTitle>
          </CardHeader>
          <CardContent>
            <RunRateBar
              data={phaseData}
              bars={[
                { key: "avgRuns", color: "#3b82f6", name: "Avg Runs" },
                { key: "avgRunRate", color: "#f59e0b", name: "Run Rate" },
              ]}
            />
          </CardContent>
        </Card>

        {/* Additional Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Venue Characteristics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
              <span className="text-muted-foreground">Lowest Score</span>
              <span className="font-bold text-red-400">{venue.lowest_score || "-"}</span>
            </div>
            <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
              <span className="text-muted-foreground">Field First Win %</span>
              <span className="font-bold text-green-400">{venue.bat_first_win_pct ? (100 - venue.bat_first_win_pct).toFixed(0) : "-"}%</span>
            </div>
            <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
              <span className="text-muted-foreground">Avg 1st Inn</span>
              <span className="font-bold text-primary">{venue.avg_first_innings_score?.toFixed(0) || "-"}</span>
            </div>
            <div className="flex justify-between items-center p-3 rounded-lg bg-muted/50">
              <span className="text-muted-foreground">Avg 2nd Inn</span>
              <span className="font-bold text-purple-400">{venue.avg_second_innings_score?.toFixed(0) || "-"}</span>
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
}
