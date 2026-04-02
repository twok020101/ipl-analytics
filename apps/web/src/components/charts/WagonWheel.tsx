"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import type { RunDistributionZone } from "@/lib/types";

interface WagonWheelProps {
  distribution: RunDistributionZone[];
  playerName?: string;
}

const ZONE_COLORS: Record<number, string> = {
  0: "#6b7280", // dots - gray
  1: "#3b82f6", // singles - blue
  2: "#10b981", // doubles - green
  3: "#8b5cf6", // triples - purple
  4: "#f59e0b", // fours - amber
  6: "#ef4444", // sixes - red
};

export function WagonWheel({ distribution, playerName }: WagonWheelProps) {
  const data = distribution
    .filter((d) => d.value > 0)
    .map((d) => ({
      name: d.label,
      value: d.value,
      pct: d.pct,
      runs: d.runs,
    }));

  return (
    <div className="w-full h-[300px] sm:h-[350px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius="40%"
            outerRadius="75%"
            paddingAngle={2}
            dataKey="value"
            animationBegin={0}
            animationDuration={1000}
            label={({ name, pct }) => `${name} ${pct}%`}
            labelLine={{ stroke: "#6b7280" }}
          >
            {data.map((entry) => (
              <Cell
                key={entry.name}
                fill={ZONE_COLORS[entry.runs] || "#6b7280"}
                stroke="none"
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
            }}
            formatter={(value: number, name: string) => [
              `${value} balls`,
              name,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
