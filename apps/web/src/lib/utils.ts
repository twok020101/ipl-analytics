import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toLocaleString();
}

export function formatPercentage(num: number, decimals = 1): string {
  return num.toFixed(decimals) + "%";
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export const teamColors: Record<string, { primary: string; secondary: string; bg: string; text: string }> = {
  CSK: { primary: "#FFC107", secondary: "#F57F17", bg: "bg-yellow-500/10", text: "text-yellow-400" },
  "Chennai Super Kings": { primary: "#FFC107", secondary: "#F57F17", bg: "bg-yellow-500/10", text: "text-yellow-400" },
  MI: { primary: "#004BA0", secondary: "#1565C0", bg: "bg-blue-500/10", text: "text-blue-400" },
  "Mumbai Indians": { primary: "#004BA0", secondary: "#1565C0", bg: "bg-blue-500/10", text: "text-blue-400" },
  RCB: { primary: "#D32F2F", secondary: "#B71C1C", bg: "bg-red-500/10", text: "text-red-400" },
  "Royal Challengers Bengaluru": { primary: "#D32F2F", secondary: "#B71C1C", bg: "bg-red-500/10", text: "text-red-400" },
  "Royal Challengers Bangalore": { primary: "#D32F2F", secondary: "#B71C1C", bg: "bg-red-500/10", text: "text-red-400" },
  DC: { primary: "#1976D2", secondary: "#0D47A1", bg: "bg-blue-600/10", text: "text-blue-300" },
  "Delhi Capitals": { primary: "#1976D2", secondary: "#0D47A1", bg: "bg-blue-600/10", text: "text-blue-300" },
  KKR: { primary: "#7B1FA2", secondary: "#4A148C", bg: "bg-purple-500/10", text: "text-purple-400" },
  "Kolkata Knight Riders": { primary: "#7B1FA2", secondary: "#4A148C", bg: "bg-purple-500/10", text: "text-purple-400" },
  SRH: { primary: "#FF6F00", secondary: "#E65100", bg: "bg-orange-500/10", text: "text-orange-400" },
  "Sunrisers Hyderabad": { primary: "#FF6F00", secondary: "#E65100", bg: "bg-orange-500/10", text: "text-orange-400" },
  RR: { primary: "#E91E63", secondary: "#AD1457", bg: "bg-pink-500/10", text: "text-pink-400" },
  "Rajasthan Royals": { primary: "#E91E63", secondary: "#AD1457", bg: "bg-pink-500/10", text: "text-pink-400" },
  PBKS: { primary: "#E53935", secondary: "#C62828", bg: "bg-red-600/10", text: "text-red-300" },
  "Punjab Kings": { primary: "#E53935", secondary: "#C62828", bg: "bg-red-600/10", text: "text-red-300" },
  GT: { primary: "#1A237E", secondary: "#0D1B4A", bg: "bg-indigo-500/10", text: "text-indigo-400" },
  "Gujarat Titans": { primary: "#1A237E", secondary: "#0D1B4A", bg: "bg-indigo-500/10", text: "text-indigo-400" },
  LSG: { primary: "#00BCD4", secondary: "#006064", bg: "bg-cyan-500/10", text: "text-cyan-400" },
  "Lucknow Super Giants": { primary: "#00BCD4", secondary: "#006064", bg: "bg-cyan-500/10", text: "text-cyan-400" },
};

export function getTeamColor(team: string): string {
  return teamColors[team]?.primary || "#6B7280";
}

export function getTeamBg(team: string): string {
  return teamColors[team]?.bg || "bg-gray-500/10";
}

export function getTeamTextColor(team: string): string {
  return teamColors[team]?.text || "text-gray-400";
}
