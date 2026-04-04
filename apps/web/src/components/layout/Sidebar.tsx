"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  UserCircle,
  Target,
  GitCompareArrows,
  MapPin,
  BrainCircuit,
  Trophy,
  Menu,
  X,
  CalendarDays,
  LogOut,
  Radio,
  Activity,
  Shield,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { StumplineIcon } from "@/components/brand/StumplineIcon";

const navItems: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  minRole: "viewer" | "analyst" | "admin";
}[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, minRole: "viewer" },
  { href: "/my-team", label: "My Team", icon: Shield, minRole: "viewer" },
  { href: "/live", label: "Live", icon: Radio, minRole: "viewer" },
  { href: "/fixtures", label: "IPL 2026", icon: CalendarDays, minRole: "viewer" },
  { href: "/predict", label: "Match Analyzer", icon: Target, minRole: "analyst" },
  { href: "/standings", label: "Standings", icon: Trophy, minRole: "viewer" },
  { href: "/teams", label: "Teams", icon: Users, minRole: "viewer" },
  { href: "/players", label: "Players", icon: UserCircle, minRole: "viewer" },
  { href: "/head-to-head", label: "Head-to-Head", icon: GitCompareArrows, minRole: "viewer" },
  { href: "/venues", label: "Venues", icon: MapPin, minRole: "viewer" },
  { href: "/match-analysis", label: "Match Analysis", icon: Activity, minRole: "viewer" },
  { href: "/ai-insights", label: "AI Insights", icon: BrainCircuit, minRole: "analyst" },
  { href: "/admin/users", label: "User Management", icon: UserCircle, minRole: "admin" },
];

const roleBadgeColor: Record<string, string> = {
  admin: "bg-red-500/20 text-red-400 border-red-500/30",
  analyst: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  viewer: "bg-muted text-muted-foreground border-border",
};

export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onMobileClose,
}: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  const pathname = usePathname();
  const { user, logout, hasRole } = useAuth();

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={cn(
          "fixed top-0 left-0 z-50 h-full bg-card border-r border-border transition-all duration-300 flex flex-col",
          "max-lg:w-72 max-lg:-translate-x-full",
          mobileOpen && "max-lg:translate-x-0",
          "lg:translate-x-0",
          collapsed ? "lg:w-16" : "lg:w-64"
        )}
      >
        <div className="flex items-center gap-3 p-4 border-b border-border">
          {(!collapsed || mobileOpen) && (
            <Link href="/" className="flex items-center gap-2" onClick={onMobileClose}>
              <StumplineIcon className="h-7 w-7 text-primary" />
              <span className="text-lg font-black bg-gradient-to-r from-primary to-blue-300 bg-clip-text text-transparent">
                Stumpline
              </span>
            </Link>
          )}
          {collapsed && !mobileOpen && (
            <Link href="/" className="mx-auto">
              <StumplineIcon className="h-7 w-7 text-primary" />
            </Link>
          )}
          <button
            onClick={onToggle}
            className={cn(
              "p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground hidden lg:block",
              collapsed && "mx-auto"
            )}
          >
            {collapsed ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
          </button>
          <button
            onClick={onMobileClose}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground lg:hidden ml-auto"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
          {navItems
            .filter((item) => hasRole(item.minRole))
            .map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onMobileClose}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                    isActive
                      ? cn(
                          "bg-primary/10 text-primary",
                          !collapsed && "border-l-2 border-primary pl-[calc(0.75rem-2px)]",
                        )
                      : "text-muted-foreground hover:text-foreground hover:bg-muted",
                    collapsed && "lg:justify-center lg:px-2"
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  <item.icon className={cn("h-5 w-5 shrink-0", isActive && "text-primary")} />
                  <span className={cn(collapsed && "lg:hidden")}>{item.label}</span>
                </Link>
              );
            })}
        </nav>

        <div className="p-4 border-t border-border">
          <div className={cn("mb-3", collapsed && !mobileOpen && "flex justify-center")}>
            <ThemeToggle collapsed={collapsed && !mobileOpen} />
          </div>
          {((!collapsed || mobileOpen) && user) && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <p className="text-sm text-foreground font-medium truncate flex-1">{user.name}</p>
                <span className={cn(
                  "text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border shrink-0",
                  roleBadgeColor[user.role] || roleBadgeColor.viewer,
                )}>
                  {user.role}
                </span>
              </div>
              <p className="text-xs text-muted-foreground truncate">{user.email}</p>
              {user.organization_name && (
                <p className="text-xs text-muted-foreground/70 truncate">{user.organization_name}</p>
              )}
              <button
                onClick={logout}
                className="flex items-center gap-2 text-xs text-muted-foreground hover:text-red-400 transition-colors w-full mt-1"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          )}
          {collapsed && !mobileOpen && user && (
            <button
              onClick={logout}
              className="mx-auto block text-muted-foreground hover:text-red-400 transition-colors"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
          {!collapsed && !user && (
            <p className="text-xs text-muted-foreground text-center">
              Stumpline v2.0
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
