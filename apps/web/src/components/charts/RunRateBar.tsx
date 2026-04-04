"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { useChartColors } from "@/hooks/useChartColors";

interface RunRateBarProps {
  data: { phase: string; [key: string]: string | number }[];
  bars: { key: string; color: string; name: string }[];
}

export function RunRateBar({ data, bars }: RunRateBarProps) {
  const c = useChartColors();

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis
            dataKey="phase"
            tick={{ fill: c.tick, fontSize: 12 }}
            axisLine={{ stroke: c.axis }}
          />
          <YAxis
            tick={{ fill: c.tick, fontSize: 12 }}
            axisLine={{ stroke: c.axis }}
          />
          <RechartsTooltip
            contentStyle={{
              backgroundColor: c.tooltipBg,
              border: `1px solid ${c.tooltipBorder}`,
              borderRadius: "8px",
              color: c.tooltipText,
            }}
          />
          <Legend wrapperStyle={{ color: c.tick }} />
          {bars.map((bar) => (
            <Bar
              key={bar.key}
              dataKey={bar.key}
              fill={bar.color}
              name={bar.name}
              radius={[4, 4, 0, 0]}
              animationDuration={1000}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
