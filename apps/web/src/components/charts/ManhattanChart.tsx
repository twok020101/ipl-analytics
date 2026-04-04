"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useChartColors } from "@/hooks/useChartColors";

interface ManhattanChartProps {
  data: { over: number; runs: number; boundaries?: number }[];
  color?: string;
}

export function ManhattanChart({ data, color = "#3b82f6" }: ManhattanChartProps) {
  const c = useChartColors();

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis
            dataKey="over"
            tick={{ fill: c.tick, fontSize: 11 }}
            axisLine={{ stroke: c.axis }}
            label={{ value: "Over", position: "insideBottom", offset: -2, fill: c.tick }}
          />
          <YAxis
            tick={{ fill: c.tick, fontSize: 11 }}
            axisLine={{ stroke: c.axis }}
            label={{ value: "Runs", angle: -90, position: "insideLeft", fill: c.tick }}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: c.tooltipBg,
              border: `1px solid ${c.tooltipBorder}`,
              borderRadius: "8px",
              color: c.tooltipText,
            }}
            formatter={(value: number) => [`${value} runs`, "Runs"]}
          />
          <Bar dataKey="runs" radius={[3, 3, 0, 0]} animationDuration={1000}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.runs >= 12 ? "#f59e0b" : entry.runs >= 8 ? color : c.axis}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
