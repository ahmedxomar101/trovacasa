"use client";

import { useRouter } from "next/navigation";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { Star, Phone, PhoneOff, CalendarCheck, Eye, Clock, ThumbsDown, Ban, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Listing } from "@/lib/supabase/types";

const STATUSES = [
  { value: "favorited", activeLabel: "Saved", inactiveLabel: "Save", icon: Star, bg: "bg-yellow-500", hoverBg: "hover:bg-yellow-600" },
  { value: "contacted", activeLabel: "Contacted", inactiveLabel: "Contact", icon: Phone, bg: "bg-blue-500", hoverBg: "hover:bg-blue-600" },
  { value: "no_reply", activeLabel: "No Reply", inactiveLabel: "No Reply", icon: PhoneOff, bg: "bg-orange-500", hoverBg: "hover:bg-orange-600" },
  { value: "booked", activeLabel: "Booked", inactiveLabel: "Book", icon: CalendarCheck, bg: "bg-emerald-500", hoverBg: "hover:bg-emerald-600" },
  { value: "visited", activeLabel: "Visited", inactiveLabel: "Visit", icon: Eye, bg: "bg-purple-500", hoverBg: "hover:bg-purple-600" },
  { value: "waiting", activeLabel: "Waiting", inactiveLabel: "Wait", icon: Clock, bg: "bg-cyan-500", hoverBg: "hover:bg-cyan-600" },
  { value: "passed", activeLabel: "Passed", inactiveLabel: "Pass", icon: ThumbsDown, bg: "bg-zinc-600", hoverBg: "hover:bg-zinc-500" },
  { value: "gone", activeLabel: "Gone", inactiveLabel: "Gone", icon: Ban, bg: "bg-zinc-500", hoverBg: "hover:bg-zinc-600" },
  { value: "dismissed", activeLabel: "Dismissed", inactiveLabel: "Dismiss", icon: X, bg: "bg-zinc-700", hoverBg: "hover:bg-zinc-600" },
] as const;

interface ActionButtonsProps {
  listing: Pick<Listing, "id" | "status">;
}

export function ActionButtons({ listing }: ActionButtonsProps) {
  const router = useRouter();
  const supabase = createBrowserSupabaseClient();

  const handleStatusChange = async (newStatus: string) => {
    const updates: Record<string, unknown> = {
      status: newStatus,
      status_updated_at: new Date().toISOString(),
    };

    if (newStatus === "favorited") {
      updates.favorited_at = new Date().toISOString();
    } else if (newStatus === "dismissed") {
      updates.dismissed_at = new Date().toISOString();
    }

    await supabase.from("listings").update(updates).eq("id", listing.id);
    router.refresh();
  };

  return (
    <div className="flex gap-2 overflow-x-auto scrollbar-none -mx-4 px-4 sm:mx-0 sm:px-0 sm:flex-wrap">
      {STATUSES.map(({ value, activeLabel, inactiveLabel, icon: Icon, bg, hoverBg }) => {
        const isActive = listing.status === value;
        return (
          <button
            key={value}
            onClick={() => handleStatusChange(isActive ? "active" : value)}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-500 outline-none min-h-[44px] shrink-0 touch-manipulation",
              isActive
                ? `${bg} text-white ring-2 ring-white/40 shadow-lg scale-105`
                : `bg-zinc-800 border border-zinc-700 text-zinc-400 ${hoverBg} hover:text-white active:bg-zinc-700`
            )}
          >
            <Icon
              size={18}
              fill={isActive && value === "favorited" ? "currentColor" : "none"}
            />
            {isActive ? activeLabel : inactiveLabel}
          </button>
        );
      })}
    </div>
  );
}
