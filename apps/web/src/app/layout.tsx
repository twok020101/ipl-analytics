"use client";

import "./globals.css";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Providers } from "./providers";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  UserCircle,
  Target,
  Swords,
  GitCompareArrows,
  MapPin,
  BrainCircuit,
  Trophy,
  Menu,
  X,
  Zap,
  CalendarDays,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/fixtures", label: "IPL 2026", icon: CalendarDays },
  { href: "/predict", label: "Match Analyzer", icon: Target },
  { href: "/standings", label: "Standings", icon: Trophy },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/players", label: "Players", icon: UserCircle },
  { href: "/head-to-head", label: "Head-to-Head", icon: GitCompareArrows },
  { href: "/venues", label: "Venues", icon: MapPin },
  { href: "/ai-insights", label: "AI Insights", icon: BrainCircuit },
];

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed top-0 left-0 z-40 h-full bg-gray-900 border-r border-gray-800 transition-all duration-300 flex flex-col",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex items-center gap-3 p-4 border-b border-gray-800">
        {!collapsed && (
          <Link href="/" className="flex items-center gap-2">
            <Zap className="h-7 w-7 text-primary" />
            <span className="text-lg font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              IPL Analytics Pro
            </span>
          </Link>
        )}
        <button
          onClick={onToggle}
          className={cn(
            "p-1.5 rounded-lg hover:bg-gray-800 transition-colors text-muted-foreground hover:text-foreground",
            collapsed && "mx-auto"
          )}
        >
          {collapsed ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
        </button>
      </div>

      <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-gray-800",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className={cn("h-5 w-5 shrink-0", isActive && "text-primary")} />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-gray-800">
        {!collapsed && (
          <p className="text-xs text-muted-foreground text-center">
            IPL Analytics Platform v1.0
          </p>
        )}
      </div>
    </aside>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <html lang="en" className="dark">
      <head>
        <title>IPL Analytics Pro</title>
        <meta name="description" content="Professional IPL Cricket Analytics Platform" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased" style={{ fontFamily: "'Inter', sans-serif" }}>
        <Providers>
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
          <main
            className={cn(
              "min-h-screen transition-all duration-300",
              collapsed ? "ml-16" : "ml-64"
            )}
          >
            <div className="p-6 lg:p-8">{children}</div>
          </main>
        </Providers>
      </body>
    </html>
  );
}
