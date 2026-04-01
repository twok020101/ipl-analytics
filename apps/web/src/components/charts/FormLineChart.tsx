"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface FormLineChartProps {
  data: { label: string; runs: number; balls?: number; opponent?: string }[];
  color?: string;
}

export function FormLineChart({ data, color = "#3b82f6" }: FormLineChartProps) {
  const avg = data.length > 0 ? data.reduce((a, b) => a + b.runs, 0) / data.length : 0;

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="label"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            axisLine={{ stroke: "#374151" }}
          />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            axisLine={{ stroke: "#374151" }}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#f9fafb",
            }}
            formatter={(value: number) => [`${value} runs`, "Score"]}
          />
          <ReferenceLine
            y={avg}
            stroke="#6b7280"
            strokeDasharray="5 5"
            label={{ value: `Avg: ${avg.toFixed(1)}`, fill: "#9ca3af", fontSize: 11 }}
          />
          <Line
            type="monotone"
            dataKey="runs"
            stroke={color}
            strokeWidth={2.5}
            dot={{ fill: color, r: 4, strokeWidth: 0 }}
            activeDot={{ r: 6, fill: color, stroke: "#fff", strokeWidth: 2 }}
            animationDuration={1000}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
