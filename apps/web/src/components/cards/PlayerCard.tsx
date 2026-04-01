"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { User } from "lucide-react";
import { cn } from "@/lib/utils";

interface PlayerCardProps {
  id: number;
  name: string;
  role?: string;
  keyStatLabel?: string;
  keyStatValue?: string | number;
  className?: string;
}

const roleBadgeColor = (role: string) => {
  const r = role.toLowerCase();
  if (r.includes("batter") || r.includes("batsman")) return "bg-blue-500/10 text-blue-400 border-blue-500/20";
  if (r.includes("bowler")) return "bg-red-500/10 text-red-400 border-red-500/20";
  if (r.includes("all")) return "bg-purple-500/10 text-purple-400 border-purple-500/20";
  if (r.includes("keeper") || r.includes("wk")) return "bg-green-500/10 text-green-400 border-green-500/20";
  return "bg-gray-500/10 text-gray-400 border-gray-500/20";
};

export function PlayerCard({
  id,
  name,
  role = "Player",
  keyStatLabel,
  keyStatValue,
  className,
}: PlayerCardProps) {
  return (
    <Link href={`/players/${id}`}>
      <div
        className={cn(
          "group rounded-xl border border-gray-800 bg-gray-900 p-5 transition-all duration-300 hover:border-gray-700 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5 cursor-pointer",
          className
        )}
      >
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gray-800 group-hover:bg-primary/10 transition-colors">
            <User className="h-6 w-6 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold truncate group-hover:text-primary transition-colors">
              {name}
            </h3>
            <div className="mt-1.5">
              <Badge className={roleBadgeColor(role)}>{role}</Badge>
            </div>
          </div>
        </div>
        {keyStatLabel && keyStatValue !== undefined && (
          <div className="mt-4 flex items-center gap-2 pt-3 border-t border-gray-800">
            <span className="text-sm text-muted-foreground">{keyStatLabel}:</span>
            <span className="text-sm font-semibold">{keyStatValue}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
