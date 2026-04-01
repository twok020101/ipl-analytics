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

interface ManhattanChartProps {
  data: { over: number; runs: number; boundaries?: number }[];
  color?: string;
}

export function ManhattanChart({ data, color = "#3b82f6" }: ManhattanChartProps) {
  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="over"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            axisLine={{ stroke: "#374151" }}
            label={{ value: "Over", position: "insideBottom", offset: -2, fill: "#6b7280" }}
          />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            axisLine={{ stroke: "#374151" }}
            label={{ value: "Runs", angle: -90, position: "insideLeft", fill: "#6b7280" }}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#f9fafb",
            }}
            formatter={(value: number) => [`${value} runs`, "Runs"]}
          />
          <Bar dataKey="runs" radius={[3, 3, 0, 0]} animationDuration={1000}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.runs >= 12 ? "#f59e0b" : entry.runs >= 8 ? color : "#6b7280"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
