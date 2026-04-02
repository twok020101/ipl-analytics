"use client";

import "./globals.css";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Providers } from "./providers";
import { AuthProvider, useAuth } from "@/lib/auth";
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
  Zap,
  CalendarDays,
  LogOut,
  Loader2,
  Radio,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/live", label: "Live", icon: Radio },
  { href: "/fixtures", label: "IPL 2026", icon: CalendarDays },
  { href: "/predict", label: "Match Analyzer", icon: Target },
  { href: "/standings", label: "Standings", icon: Trophy },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/players", label: "Players", icon: UserCircle },
  { href: "/head-to-head", label: "Head-to-Head", icon: GitCompareArrows },
  { href: "/venues", label: "Venues", icon: MapPin },
  { href: "/ai-insights", label: "AI Insights", icon: BrainCircuit },
];

function Sidebar({
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
  const { user, logout } = useAuth();

  return (
    <>
      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={cn(
          "fixed top-0 left-0 z-50 h-full bg-gray-900 border-r border-gray-800 transition-all duration-300 flex flex-col",
          // Mobile: full-width drawer, hidden by default
          "max-lg:w-72 max-lg:-translate-x-full",
          mobileOpen && "max-lg:translate-x-0",
          // Desktop: collapsible sidebar
          "lg:translate-x-0",
          collapsed ? "lg:w-16" : "lg:w-64"
        )}
      >
        <div className="flex items-center gap-3 p-4 border-b border-gray-800">
          {(!collapsed || mobileOpen) && (
            <Link href="/" className="flex items-center gap-2" onClick={onMobileClose}>
              <Zap className="h-7 w-7 text-primary" />
              <span className="text-lg font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                IPL Analytics Pro
              </span>
            </Link>
          )}
          {/* Desktop collapse toggle */}
          <button
            onClick={onToggle}
            className={cn(
              "p-1.5 rounded-lg hover:bg-gray-800 transition-colors text-muted-foreground hover:text-foreground hidden lg:block",
              collapsed && "mx-auto"
            )}
          >
            {collapsed ? <Menu className="h-5 w-5" /> : <X className="h-5 w-5" />}
          </button>
          {/* Mobile close button */}
          <button
            onClick={onMobileClose}
            className="p-1.5 rounded-lg hover:bg-gray-800 transition-colors text-muted-foreground hover:text-foreground lg:hidden ml-auto"
          >
            <X className="h-5 w-5" />
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
                onClick={onMobileClose}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-gray-800",
                  collapsed && "lg:justify-center lg:px-2"
                )}
                title={collapsed ? item.label : undefined}
              >
                <item.icon className={cn("h-5 w-5 shrink-0", isActive && "text-primary")} />
                {/* Always show label on mobile, conditionally on desktop */}
                <span className={cn(collapsed && "lg:hidden")}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gray-800">
          {((!collapsed || mobileOpen) && user) && (
            <div className="space-y-2">
              <p className="text-sm text-foreground font-medium truncate">{user.name}</p>
              <p className="text-xs text-muted-foreground truncate">{user.email}</p>
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
              IPL Analytics Platform v1.0
            </p>
          )}
        </div>
      </aside>
    </>
  );
}

function MobileHeader({ onMenuOpen }: { onMenuOpen: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-gray-800 bg-gray-900/95 backdrop-blur px-4 py-3 lg:hidden">
      <button
        onClick={onMenuOpen}
        className="p-1.5 rounded-lg hover:bg-gray-800 transition-colors text-muted-foreground"
      >
        <Menu className="h-5 w-5" />
      </button>
      <Link href="/" className="flex items-center gap-2">
        <Zap className="h-6 w-6 text-primary" />
        <span className="text-base font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
          IPL Analytics Pro
        </span>
      </Link>
    </header>
  );
}

function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const closeMobile = () => setMobileOpen(false);

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.push("/login");
    }
  }, [loading, user, pathname, router]);

  if (loading || (!user && pathname !== "/login")) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (pathname === "/login") {
    return <>{children}</>;
  }

  return (
    <>
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
        mobileOpen={mobileOpen}
        onMobileClose={closeMobile}
      />
      <MobileHeader onMenuOpen={() => setMobileOpen(true)} />
      <main
        className={cn(
          "min-h-screen transition-all duration-300",
          // No left margin on mobile; sidebar is an overlay
          "lg:ml-64",
          collapsed && "lg:ml-16"
        )}
      >
        <div className="p-4 sm:p-6 lg:p-8">{children}</div>
      </main>
    </>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
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
          <AuthProvider>
            <AuthGate>{children}</AuthGate>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
