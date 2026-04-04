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
import { useChartColors } from "@/hooks/useChartColors";

interface FormLineChartProps {
  data: { label: string; runs: number; balls?: number; opponent?: string }[];
  color?: string;
}

export function FormLineChart({ data, color = "#3b82f6" }: FormLineChartProps) {
  const c = useChartColors();
  const avg = data.length > 0 ? data.reduce((a, b) => a + b.runs, 0) / data.length : 0;

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis
            dataKey="label"
            tick={{ fill: c.tick, fontSize: 11 }}
            axisLine={{ stroke: c.axis }}
          />
          <YAxis
            tick={{ fill: c.tick, fontSize: 11 }}
            axisLine={{ stroke: c.axis }}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: c.tooltipBg,
              border: `1px solid ${c.tooltipBorder}`,
              borderRadius: "8px",
              color: c.tooltipText,
            }}
            formatter={(value: number) => [`${value} runs`, "Score"]}
          />
          <ReferenceLine
            y={avg}
            stroke={c.axis}
            strokeDasharray="5 5"
            label={{ value: `Avg: ${avg.toFixed(1)}`, fill: c.tick, fontSize: 11 }}
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
