"use client";

import { useSyncExternalStore } from "react";

export interface ChartColors {
  grid: string;
  axis: string;
  tick: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipText: string;
}

const DEFAULTS: ChartColors = {
  grid: "#1f2937",
  axis: "#374151",
  tick: "#9ca3af",
  tooltipBg: "#1f2937",
  tooltipBorder: "#374151",
  tooltipText: "#f9fafb",
};

function readColors(): ChartColors {
  const s = getComputedStyle(document.documentElement);
  const get = (v: string) => s.getPropertyValue(v).trim();
  return {
    grid: get("--color-border") || DEFAULTS.grid,
    axis: get("--color-border-strong") || DEFAULTS.axis,
    tick: get("--color-muted-foreground") || DEFAULTS.tick,
    tooltipBg: get("--color-card") || DEFAULTS.tooltipBg,
    tooltipBorder: get("--color-border-strong") || DEFAULTS.tooltipBorder,
    tooltipText: get("--color-foreground") || DEFAULTS.tooltipText,
  };
}

function colorsEqual(a: ChartColors, b: ChartColors): boolean {
  return a.grid === b.grid && a.axis === b.axis && a.tick === b.tick
    && a.tooltipBg === b.tooltipBg && a.tooltipBorder === b.tooltipBorder
    && a.tooltipText === b.tooltipText;
}

// Singleton: one observer, one state, shared by all consumers
let current: ChartColors = DEFAULTS;
const listeners = new Set<() => void>();
let observerStarted = false;

function startObserver() {
  if (observerStarted || typeof window === "undefined") return;
  observerStarted = true;
  current = readColors();

  const observer = new MutationObserver(() => {
    const next = readColors();
    if (!colorsEqual(current, next)) {
      current = next;
      listeners.forEach((fn) => fn());
    }
  });
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
}

function subscribe(callback: () => void) {
  startObserver();
  listeners.add(callback);
  return () => { listeners.delete(callback); };
}

function getSnapshot() {
  if (typeof window !== "undefined" && !observerStarted) startObserver();
  return current;
}

function getServerSnapshot() {
  return DEFAULTS;
}

export function useChartColors(): ChartColors {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
