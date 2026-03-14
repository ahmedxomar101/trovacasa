"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  List,
  GitBranchPlus,
  Bell,
  History,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/listings", label: "Listings", icon: List },
  { href: "/pipeline", label: "Shortlist", icon: GitBranchPlus },
  { href: "/notifications", label: "Alerts", icon: Bell },
  { href: "/history", label: "History", icon: History },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed top-0 left-0 z-40 h-full w-64 bg-zinc-950 border-r border-zinc-800 flex-col hidden md:flex">
        <div className="px-7 py-6 border-b border-zinc-800">
          <h1 className="text-xl font-bold text-white tracking-tight">TrovaCasa</h1>
          <p className="text-sm text-zinc-500 mt-1">Apartment Finder</p>
        </div>

        <nav className="flex-1 p-5 space-y-1.5">
          {navItems.map(({ href, label, icon: Icon }) => {
            const isActive =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3.5 px-4 py-3 rounded-xl text-[15px] font-medium transition-colors",
                  isActive
                    ? "bg-zinc-800 text-white border-l-2 border-blue-500"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-900 border-l-2 border-transparent"
                )}
              >
                <Icon size={20} />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 md:hidden bg-zinc-950/95 backdrop-blur-lg border-t border-zinc-800 safe-area-bottom">
        <div className="flex items-stretch justify-around px-1" style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}>
          {navItems.map(({ href, label, icon: Icon }) => {
            const isActive =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 py-2 min-w-[48px] min-h-[48px] flex-1 transition-colors touch-manipulation",
                  isActive
                    ? "text-blue-400"
                    : "text-zinc-500 active:text-zinc-300"
                )}
              >
                <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
                <span className="text-[10px] font-medium leading-none">{label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
