"use client";

import Link from "next/link";
import { Menu } from "lucide-react";
import { StumplineIcon } from "@/components/brand/StumplineIcon";

export function MobileHeader({ onMenuOpen }: { onMenuOpen: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-card/95 backdrop-blur px-4 py-3 lg:hidden">
      <button
        onClick={onMenuOpen}
        className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground"
      >
        <Menu className="h-5 w-5" />
      </button>
      <Link href="/" className="flex items-center gap-2">
        <StumplineIcon className="h-6 w-6 text-primary" />
        <span className="text-base font-black bg-gradient-to-r from-primary to-blue-300 bg-clip-text text-transparent">
          Stumpline
        </span>
      </Link>
    </header>
  );
}
