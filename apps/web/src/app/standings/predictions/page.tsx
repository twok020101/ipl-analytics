"use client";

/**
 * Season Predictions page — Monte Carlo playoff qualification probabilities.
 *
 * Shows each team's likelihood of qualifying for playoffs, finishing top-2,
 * and winning the title, based on 10,000 simulated season outcomes.
 * Strength ratings are derived from current win rate, NRR, recent form,
 * and head-to-head records.
 */

import { useQuery } from "@tanstack/react-query";
import { fetchSeasonPredictions, type SeasonPrediction } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn, getTeamTextColor, getTeamBg } from "@/lib/utils";
import {
  TrendingUp,
  Trophy,
  Target,
  BarChart3,
  ArrowLeft,
  Flame,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";

/** Horizontal bar used in the prediction cards */
function ProbBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
      <div
        className={cn("h-full rounded-full transition-all duration-700", color)}
        style={{ width: `${Math.max(value, 1)}%` }}
      />
    </div>
  );
}

/** Strength indicator dots (1-5 scale) */
function StrengthDots({ rating }: { rating: number }) {
  const filled = Math.round(rating * 5);
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            i <= filled ? "bg-primary" : "bg-muted-strong",
          )}
        />
      ))}
    </div>
  );
}

export default function PredictionsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["season-predictions", "2026"],
    queryFn: () => fetchSeasonPredictions("2026"),
    staleTime: 5 * 60 * 1000, // Cache for 5 min (simulation is CPU-intensive)
  });

  return (
    <div className="space-y-6">
      {/* Header with back link */}
      <div>
        <Link
          href="/standings"
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-3 transition-colors"
        >
          <ArrowLeft className="h-3 w-3" /> Back to Standings
        </Link>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-primary" />
          Playoff Predictions
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Monte Carlo simulation — {data?.simulations?.toLocaleString() || "10,000"} season
          outcomes based on team strength, form, and H2H
        </p>
      </div>

      {/* Summary stats */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card className="bg-card/50">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-xs text-muted-foreground">Completed</p>
              <p className="text-xl font-bold mt-1">{data.completed_matches}</p>
            </CardContent>
          </Card>
          <Card className="bg-card/50">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-xs text-muted-foreground">Remaining</p>
              <p className="text-xl font-bold mt-1">{data.remaining_matches}</p>
            </CardContent>
          </Card>
          <Card className="bg-card/50">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-xs text-muted-foreground">Simulations</p>
              <p className="text-xl font-bold mt-1">{data.simulations.toLocaleString()}</p>
            </CardContent>
          </Card>
          <Card className="bg-card/50">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-xs text-muted-foreground">Playoff Spots</p>
              <p className="text-xl font-bold mt-1">4</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-4">
          {[...Array(10)].map((_, i) => (
            <Skeleton key={i} className="h-32 w-full rounded-xl" />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <AlertTriangle className="h-10 w-10 text-yellow-500" />
          <p className="text-muted-foreground">Failed to load predictions</p>
        </div>
      )}

      {/* Team prediction cards — mobile-first card layout */}
      {data?.predictions && (
        <div className="space-y-3">
          {data.predictions.map((team: SeasonPrediction, idx: number) => {
            const isQualifying = team.playoff_pct >= 50;
            const isBorderline = team.playoff_pct >= 25 && team.playoff_pct < 50;

            return (
              <Card
                key={team.team_id}
                className={cn(
                  "overflow-hidden transition-all",
                  isQualifying && "border-green-500/30",
                  isBorderline && "border-yellow-500/20",
                )}
              >
                <CardContent className="p-4">
                  {/* Team header row */}
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-lg font-bold text-muted-foreground w-6 shrink-0">
                        {idx + 1}
                      </span>
                      <div className="min-w-0">
                        <span className={cn("font-bold text-sm sm:text-base", getTeamTextColor(team.short_name))}>
                          {team.team_name}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground">
                            {team.current_won}W-{team.current_lost}L
                            ({team.current_points}pts)
                          </span>
                          <StrengthDots rating={team.strength_rating} />
                        </div>
                      </div>
                    </div>
                    {/* Main probability badge */}
                    <div className={cn(
                      "text-center px-3 py-1.5 rounded-lg shrink-0",
                      isQualifying ? "bg-green-500/10" : isBorderline ? "bg-yellow-500/10" : "bg-muted",
                    )}>
                      <p className={cn(
                        "text-xl font-bold",
                        isQualifying ? "text-green-400" : isBorderline ? "text-yellow-400" : "text-muted-foreground",
                      )}>
                        {team.playoff_pct}%
                      </p>
                      <p className="text-[10px] text-muted-foreground uppercase">Playoff</p>
                    </div>
                  </div>

                  {/* Probability bars */}
                  <div className="space-y-2.5">
                    {/* Playoff qualification */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Target className="h-3 w-3" /> Top 4 (Qualify)
                        </span>
                        <span className="font-medium">{team.playoff_pct}%</span>
                      </div>
                      <ProbBar value={team.playoff_pct} color="bg-green-500" />
                    </div>

                    {/* Top 2 */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Flame className="h-3 w-3" /> Top 2 (Home advantage)
                        </span>
                        <span className="font-medium">{team.top_2_pct}%</span>
                      </div>
                      <ProbBar value={team.top_2_pct} color="bg-blue-500" />
                    </div>

                    {/* Winner */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Trophy className="h-3 w-3" /> Champion
                        </span>
                        <span className="font-medium">{team.winner_pct}%</span>
                      </div>
                      <ProbBar value={team.winner_pct} color="bg-amber-500" />
                    </div>
                  </div>

                  {/* Footer stats */}
                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
                    <span>
                      NRR: <span className={team.current_nrr >= 0 ? "text-green-400" : "text-red-400"}>
                        {team.current_nrr >= 0 ? "+" : ""}{team.current_nrr.toFixed(3)}
                      </span>
                    </span>
                    <span>Avg finish: #{team.avg_final_position.toFixed(1)}</span>
                    <span>Avg pts: {team.avg_final_points.toFixed(1)}</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
