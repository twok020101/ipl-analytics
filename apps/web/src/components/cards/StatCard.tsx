"use client";

import { memo, useEffect, useRef } from "react";
import { motion, animate } from "framer-motion";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  delay?: number;
  className?: string;
}

function AnimatedNumber({ value }: { value: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const prevValue = useRef(0);
  useEffect(() => {
    const from = prevValue.current;
    prevValue.current = value;
    const controls = animate(from, value, {
      duration: from === 0 ? 1.2 : 0.6,
      ease: "easeOut",
      onUpdate: (v) => {
        if (ref.current) ref.current.textContent = Math.round(v).toLocaleString();
      },
    });
    return () => controls.stop();
  }, [value]);
  return <span ref={ref}>{Math.round(value).toLocaleString()}</span>;
}

export const StatCard = memo(function StatCard({ label, value, icon: Icon, trend, delay = 0, className }: StatCardProps) {
  const isNumeric = typeof value === "number";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut", delay }}
      className={cn(
        "group relative overflow-hidden rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:border-border-strong hover:shadow-lg hover:shadow-primary/5",
        className
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight">
            {isNumeric ? <AnimatedNumber value={value} /> : value}
          </p>
          {trend && (
            <div className="mt-2 flex items-center gap-1">
              <span
                className={cn(
                  "text-xs font-medium",
                  trend.value >= 0 ? "text-green-400" : "text-red-400"
                )}
              >
                {trend.value >= 0 ? "+" : ""}
                {trend.value}%
              </span>
              <span className="text-xs text-muted-foreground">{trend.label}</span>
            </div>
          )}
        </div>
        <div className="rounded-lg bg-primary/10 p-2.5">
          <Icon className="h-5 w-5 text-primary" />
        </div>
      </div>
    </motion.div>
  );
});
