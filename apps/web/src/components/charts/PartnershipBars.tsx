"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { Partnership } from "@/lib/types";

interface PartnershipBarsProps {
  partnerships: Partnership[];
  color?: string;
}

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#6366f1",
];

export function PartnershipBars({ partnerships, color }: PartnershipBarsProps) {
  const data = partnerships.map((p, i) => ({
    name: `${p.batter1.name.split(" ").pop()} & ${p.batter2.name.split(" ").pop()}`,
    runs: p.runs,
    balls: p.balls,
    sr: p.balls > 0 ? ((p.runs / p.balls) * 100).toFixed(1) : "0.0",
    idx: i,
  }));

  return (
    <div className="w-full h-[300px] sm:h-[350px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
          <XAxis type="number" tick={{ fill: "#9ca3af", fontSize: 11 }} axisLine={{ stroke: "#374151" }} />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: "#9ca3af", fontSize: 10 }}
            width={100}
            axisLine={{ stroke: "#374151" }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "8px" }}
            labelStyle={{ color: "#f9fafb" }}
            formatter={(value: number, _name: string, props) => {
              const balls = props?.payload?.balls ?? 0;
              const sr = props?.payload?.sr ?? "0.0";
              return [`${value} runs (${balls} balls, SR: ${sr})`, "Partnership"];
            }}
          />
          <Bar dataKey="runs" radius={[0, 4, 4, 0]} animationDuration={1000}>
            {data.map((entry) => (
              <Cell key={entry.idx} fill={color || COLORS[entry.idx % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
