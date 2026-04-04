"use client";

import { cn, getTeamTextColor } from "@/lib/utils";
import { Calendar, MapPin } from "lucide-react";

interface MatchCardProps {
  team1: string;
  team2: string;
  winner: string;
  result: string;
  date: string;
  venue: string;
  score1?: string;
  score2?: string;
  className?: string;
}

export function MatchCard({
  team1,
  team2,
  winner,
  result,
  date,
  venue,
  score1,
  score2,
  className,
}: MatchCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-4 transition-all duration-200 hover:border-border-strong",
        className
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 text-center">
          <p className={cn("font-semibold", getTeamTextColor(team1))}>{team1}</p>
          {score1 && <p className="text-sm text-muted-foreground mt-0.5">{score1}</p>}
        </div>
        <div className="px-4">
          <span className="text-xs font-bold text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
            VS
          </span>
        </div>
        <div className="flex-1 text-center">
          <p className={cn("font-semibold", getTeamTextColor(team2))}>{team2}</p>
          {score2 && <p className="text-sm text-muted-foreground mt-0.5">{score2}</p>}
        </div>
      </div>
      <div className="mt-3 pt-3 border-t border-border">
        <p className="text-xs text-center">
          <span className="text-primary font-medium">{winner}</span>
          <span className="text-muted-foreground"> {result}</span>
        </p>
        <div className="mt-2 flex items-center justify-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {date}
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {venue}
          </span>
        </div>
      </div>
    </div>
  );
}
