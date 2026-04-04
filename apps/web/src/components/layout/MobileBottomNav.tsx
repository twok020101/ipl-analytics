"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Radio,
  Trophy,
  UserCircle,
  Target,
} from "lucide-react";

const bottomTabs = [
  { href: "/", label: "Home", icon: LayoutDashboard },
  { href: "/live", label: "Live", icon: Radio },
  { href: "/standings", label: "Standings", icon: Trophy },
  { href: "/players", label: "Players", icon: UserCircle },
  { href: "/predict", label: "Analyze", icon: Target },
];

export function MobileBottomNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-card/95 backdrop-blur lg:hidden safe-area-bottom">
      <div className="flex items-center justify-around py-1.5">
        {bottomTabs.map((tab) => {
          const isActive = pathname === tab.href || (tab.href !== "/" && pathname.startsWith(tab.href));
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-lg transition-colors min-w-[56px]",
                isActive
                  ? "text-primary shadow-[inset_0_2px_0_0_var(--color-primary)]"
                  : "text-muted-foreground",
              )}
            >
              <tab.icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
