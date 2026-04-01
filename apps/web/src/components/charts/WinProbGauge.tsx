"use client";

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { getTeamColor } from "@/lib/utils";

interface WinProbGaugeProps {
  team1: string;
  team2: string;
  team1Prob: number;
  team2Prob: number;
}

export function WinProbGauge({ team1, team2, team1Prob, team2Prob }: WinProbGaugeProps) {
  const data = [
    { name: team1, value: team1Prob },
    { name: team2, value: team2Prob },
  ];

  const color1 = getTeamColor(team1);
  const color2 = getTeamColor(team2);

  return (
    <div className="flex flex-col items-center">
      <div className="w-full h-[250px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="65%"
              startAngle={180}
              endAngle={0}
              innerRadius="60%"
              outerRadius="90%"
              paddingAngle={2}
              dataKey="value"
              animationBegin={0}
              animationDuration={1200}
            >
              <Cell fill={color1} stroke="none" />
              <Cell fill={color2} stroke="none" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center pt-8">
          <div className="text-center">
            <p className="text-3xl font-bold text-foreground">
              {Math.round(Math.max(team1Prob, team2Prob))}%
            </p>
            <p className="text-sm text-muted-foreground">
              {team1Prob > team2Prob ? team1 : team2}
            </p>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center gap-8 mt-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color1 }} />
          <span className="text-sm font-medium">{team1}</span>
          <span className="text-sm text-muted-foreground">{team1Prob.toFixed(1)}%</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color2 }} />
          <span className="text-sm font-medium">{team2}</span>
          <span className="text-sm text-muted-foreground">{team2Prob.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}
