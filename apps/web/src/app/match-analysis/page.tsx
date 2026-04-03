"use client";

/**
 * Post-Match Analysis page — interactive win probability curve with turning points.
 *
 * Users select a completed match, then see:
 *  - Win probability curve (over-by-over or ball-by-ball)
 *  - Turning points annotated on the chart
 *  - Summary of key moments that decided the match
 *
 * Works for both historical matches (2008-2025) and IPL 2026 (from live snapshots).
 */

import { useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchPostMatchAnalysis,
  type PostMatchAnalysis,
  type WinProbPoint,
  type TurningPoint,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn, getTeamTextColor, getTeamColor } from "@/lib/utils";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  Zap,
  Target,
  TrendingUp,
  TrendingDown,
  Loader2,
  Search,
} from "lucide-react";

/** Season options for the selector */
const seasonOptions = [
  { value: "2026", label: "IPL 2026" },
  { value: "2025", label: "IPL 2025" },
  { value: "2024", label: "IPL 2024" },
  { value: "2023", label: "IPL 2023" },
  { value: "2022", label: "IPL 2022" },
  { value: "2021", label: "IPL 2021" },
  { value: "2020", label: "IPL 2020" },
  { value: "2019", label: "IPL 2019" },
  { value: "2018", label: "IPL 2018" },
];

/** Icon for turning point type */
function TurningPointIcon({ type }: { type: string }) {
  switch (type) {
    case "big_over":
      return <Zap className="h-4 w-4 text-amber-400" />;
    case "wicket_cluster":
    case "key_dismissal":
      return <Target className="h-4 w-4 text-red-400" />;
    default:
      return <Activity className="h-4 w-4 text-blue-400" />;
  }
}

/** Chart data point — WinProbPoint with added label for the x-axis */
interface ChartDataPoint extends WinProbPoint {
  index: number;
  label: string;
}

/** Recharts tooltip payload entry */
interface TooltipPayloadEntry {
  payload: ChartDataPoint;
}

/** Custom tooltip for the win probability chart */
function ChartTooltip({ active, payload, analysis }: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  analysis: PostMatchAnalysis | undefined;
}) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="font-medium mb-1">
        {data.innings === 1 ? "1st" : "2nd"} Innings — Over {data.over}
      </p>
      <p>
        Score: {data.runs}/{data.wickets}
      </p>
      <div className="flex items-center gap-3 mt-1">
        <span className={cn("font-bold", getTeamTextColor(analysis?.bat_first?.short_name || ""))}>
          {analysis?.bat_first?.short_name}: {data.bat_first_win_prob}%
        </span>
        <span className={cn("font-bold", getTeamTextColor(analysis?.bat_second?.short_name || ""))}>
          {analysis?.bat_second?.short_name}: {data.bat_second_win_prob}%
        </span>
      </div>
      {data.runs_in_over !== undefined && (
        <p className="text-muted-foreground mt-1">
          Over: {data.runs_in_over} runs, {data.wickets_in_over} wkt
        </p>
      )}
    </div>
  );
}

export default function MatchAnalysisPage() {
  const [season, setSeason] = useState("2024");
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch analysis for selected match
  const {
    data: analysis,
    isLoading: analysisLoading,
    error: analysisError,
  } = useQuery({
    queryKey: ["post-match-analysis", selectedMatchId],
    queryFn: () => fetchPostMatchAnalysis(selectedMatchId!),
    enabled: !!selectedMatchId,
  });

  // Build chart data — add an index for x-axis
  const chartData: ChartDataPoint[] = analysis?.curve?.map((point: WinProbPoint, idx: number) => ({
    ...point,
    index: idx,
    label: `${point.innings === 1 ? "1st" : "2nd"} Inn - Ov ${point.over}`,
  })) || [];

  // Find the over index where 2nd innings starts (for reference line)
  const inningsBreak = chartData.findIndex((d) => d.innings === 2);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="h-6 w-6 text-primary" />
          Post-Match Analysis
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Win probability curves and turning point identification
        </p>
      </div>

      {/* Match selector — mobile-friendly row */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="w-full sm:w-40">
          <Select
            options={seasonOptions}
            value={season}
            onChange={(e) => {
              setSeason(e.target.value);
              setSelectedMatchId(null);
            }}
          />
        </div>
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <input
              ref={inputRef}
              type="number"
              placeholder="Enter Match ID (e.g., 1, 50, 100)"
              className="w-full pl-9 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const val = parseInt(inputRef.current?.value || "");
                  if (!isNaN(val)) setSelectedMatchId(val);
                }
              }}
            />
          </div>
        </div>
        <button
          onClick={() => {
            const val = parseInt(inputRef.current?.value || "");
            if (!isNaN(val)) setSelectedMatchId(val);
          }}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          Analyze
        </button>
      </div>

      {/* Loading state */}
      {analysisLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Replaying match through ML model...</p>
          </div>
        </div>
      )}

      {/* Error / no data state */}
      {analysisError && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
            <AlertTriangle className="h-8 w-8 text-yellow-500" />
            <p className="text-muted-foreground text-sm">
              No analysis data available for this match
            </p>
          </CardContent>
        </Card>
      )}

      {/* Analysis content */}
      {analysis && !analysis.error && (
        <>
          {/* Match summary header */}
          <Card>
            <CardContent className="p-4">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={cn("font-bold text-lg", getTeamTextColor(analysis.bat_first.short_name))}>
                      {analysis.bat_first.short_name}
                    </span>
                    <span className="text-muted-foreground">vs</span>
                    <span className={cn("font-bold text-lg", getTeamTextColor(analysis.bat_second.short_name))}>
                      {analysis.bat_second.short_name}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">{analysis.result}</p>
                  {analysis.date && (
                    <p className="text-xs text-muted-foreground">{analysis.date} — Season {analysis.season}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={cn(
                    "text-xs",
                    analysis.data_source === "ball_by_ball"
                      ? "bg-green-500/10 text-green-400"
                      : "bg-blue-500/10 text-blue-400",
                  )}>
                    {analysis.data_source === "ball_by_ball" ? "Ball-by-ball" : "Over-by-over"}
                  </Badge>
                  <Badge className="bg-primary/10 text-primary text-xs">
                    {analysis.total_overs} data points
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Win Probability Curve */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Win Probability Curve</CardTitle>
            </CardHeader>
            <CardContent className="p-2 sm:p-4">
              <div className="h-[250px] sm:h-[350px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gradBatFirst" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={getTeamColor(analysis.bat_first.short_name)} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={getTeamColor(analysis.bat_first.short_name)} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 10, fill: "#9CA3AF" }}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 10, fill: "#9CA3AF" }}
                      tickFormatter={(v) => `${v}%`}
                    />
                    <Tooltip content={<ChartTooltip analysis={analysis} />} />
                    <ReferenceLine y={50} stroke="#6B7280" strokeDasharray="5 5" />
                    {inningsBreak > 0 && (
                      <ReferenceLine
                        x={chartData[inningsBreak]?.label}
                        stroke="#F59E0B"
                        strokeDasharray="3 3"
                        label={{ value: "Innings Break", fill: "#F59E0B", fontSize: 10 }}
                      />
                    )}
                    <Area
                      type="monotone"
                      dataKey="bat_first_win_prob"
                      stroke={getTeamColor(analysis.bat_first.short_name)}
                      fill="url(#gradBatFirst)"
                      strokeWidth={2}
                      name={analysis.bat_first.short_name}
                    />
                    {/* Turning point dots */}
                    {analysis.turning_points.map((tp: TurningPoint, i: number) => {
                      const idx = chartData.findIndex(
                        (d) => d.innings === tp.innings && d.over === tp.over
                      );
                      if (idx === -1) return null;
                      return (
                        <ReferenceDot
                          key={i}
                          x={chartData[idx].label}
                          y={tp.bat_first_win_prob}
                          r={5}
                          fill="#EF4444"
                          stroke="#fff"
                          strokeWidth={2}
                        />
                      );
                    })}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {/* Legend */}
              <div className="flex items-center justify-center gap-6 mt-2 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <div className="h-2 w-4 rounded" style={{ background: getTeamColor(analysis.bat_first.short_name) }} />
                  {analysis.bat_first.short_name} win %
                </span>
                <span className="flex items-center gap-1">
                  <div className="h-2.5 w-2.5 rounded-full bg-red-500 border border-white" />
                  Turning point
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Turning Points list */}
          {analysis.turning_points.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Zap className="h-4 w-4 text-amber-400" />
                  Turning Points ({analysis.turning_points.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3">
                {analysis.turning_points.map((tp: TurningPoint, i: number) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/50 border border-gray-700/50"
                  >
                    <TurningPointIcon type={tp.type} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium">
                          {tp.innings === 1 ? "1st" : "2nd"} Innings — Over {tp.over}
                        </p>
                        <div className="flex items-center gap-1 shrink-0">
                          {tp.swing > 0 ? (
                            <TrendingUp className="h-3 w-3 text-green-400" />
                          ) : (
                            <TrendingDown className="h-3 w-3 text-red-400" />
                          )}
                          <span className={cn(
                            "text-xs font-bold",
                            tp.swing > 0 ? "text-green-400" : "text-red-400",
                          )}>
                            {tp.swing > 0 ? "+" : ""}{tp.swing}%
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{tp.description}</p>
                      <div className="flex items-center gap-3 mt-1 text-xs">
                        <span className="text-muted-foreground">
                          Score: {tp.runs}/{tp.wickets}
                        </span>
                        <span className={cn("font-medium", getTeamTextColor(tp.favours))}>
                          Favours {tp.favours}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* No turning points */}
          {analysis.turning_points.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                <p>No significant turning points detected (threshold: {">"}10% swing)</p>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Empty state */}
      {!selectedMatchId && !analysisLoading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
            <Activity className="h-12 w-12 text-muted-foreground/30" />
            <p className="text-muted-foreground">Enter a match ID to see the win probability curve</p>
            <p className="text-xs text-muted-foreground/70">
              Works best with historical matches (2008-2025) that have ball-by-ball data
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
