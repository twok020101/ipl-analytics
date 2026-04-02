"use client";

import type { WicketType } from "@/lib/types";

interface PitchMapProps {
  wicketTypes: WicketType[];
  mode: "batter" | "bowler";
}

const WICKET_COLORS: Record<string, string> = {
  caught: "#ef4444",
  bowled: "#f59e0b",
  lbw: "#8b5cf6",
  "run out": "#06b6d4",
  stumped: "#ec4899",
  "caught and bowled": "#f97316",
  "hit wicket": "#14b8a6",
  "retired hurt": "#6b7280",
  "retired out": "#6b7280",
  "obstructing the field": "#6b7280",
};

function formatWicketType(type: string): string {
  return type
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function PitchMap({ wicketTypes, mode }: PitchMapProps) {
  const maxCount = Math.max(...wicketTypes.map((w) => w.count), 1);

  return (
    <div className="space-y-3">
      {wicketTypes.map((w) => {
        const color = WICKET_COLORS[w.type] || "#6b7280";
        const widthPct = (w.count / maxCount) * 100;
        return (
          <div key={w.type} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{formatWicketType(w.type)}</span>
              <span className="font-medium">
                {w.count}{" "}
                <span className="text-muted-foreground text-xs">({w.pct}%)</span>
              </span>
            </div>
            <div className="h-5 rounded-full bg-gray-800 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${widthPct}%`, backgroundColor: color }}
              />
            </div>
          </div>
        );
      })}
      {wicketTypes.length === 0 && (
        <p className="text-sm text-muted-foreground text-center py-4">
          No {mode === "batter" ? "dismissal" : "wicket"} data available
        </p>
      )}
    </div>
  );
}
