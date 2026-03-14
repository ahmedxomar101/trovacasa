"use client";

import { useRouter } from "next/navigation";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import {
  Star,
  Phone,
  PhoneOff,
  CalendarCheck,
  Eye,
  Clock,
  ThumbsDown,
  Ban,
  X,
  ExternalLink,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Listing } from "@/lib/supabase/types";
import { useState } from "react";

type PipelineListing = Partial<Listing> &
  Pick<Listing, "id" | "source" | "url" | "status"> & {
    notes?: string | null;
    status_updated_at?: string | null;
  };

interface StatusConfig {
  label: string;
  icon: LucideIcon;
  bg: string;
  text: string;
}

const STATUS_MAP: Record<string, StatusConfig> = {
  favorited: { label: "Saved", icon: Star, bg: "bg-yellow-500", text: "text-yellow-500" },
  contacted: { label: "Contacted", icon: Phone, bg: "bg-blue-500", text: "text-blue-500" },
  no_reply: { label: "No Reply", icon: PhoneOff, bg: "bg-orange-500", text: "text-orange-500" },
  booked: { label: "Booked", icon: CalendarCheck, bg: "bg-emerald-500", text: "text-emerald-500" },
  visited: { label: "Visited", icon: Eye, bg: "bg-purple-500", text: "text-purple-500" },
  waiting: { label: "Waiting", icon: Clock, bg: "bg-cyan-500", text: "text-cyan-500" },
  passed: { label: "Passed", icon: ThumbsDown, bg: "bg-zinc-600", text: "text-zinc-400" },
  gone: { label: "Gone", icon: Ban, bg: "bg-zinc-500", text: "text-zinc-400" },
};

interface NextAction {
  value: string;
  label: string;
  icon: LucideIcon;
  bg: string;
}

function getNextActions(status: string): NextAction[] {
  switch (status) {
    case "favorited":
      return [
        { value: "contacted", label: "Contact", icon: Phone, bg: "bg-blue-600 hover:bg-blue-500 active:bg-blue-700" },
        { value: "dismissed", label: "Dismiss", icon: X, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
        { value: "gone", label: "Gone", icon: Ban, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
      ];
    case "contacted":
      return [
        { value: "no_reply", label: "No Reply", icon: PhoneOff, bg: "bg-orange-600 hover:bg-orange-500 active:bg-orange-700" },
        { value: "booked", label: "Book Visit", icon: CalendarCheck, bg: "bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700" },
        { value: "gone", label: "Gone", icon: Ban, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
      ];
    case "no_reply":
      return [
        { value: "contacted", label: "Retry Call", icon: Phone, bg: "bg-blue-600 hover:bg-blue-500 active:bg-blue-700" },
        { value: "booked", label: "Book Visit", icon: CalendarCheck, bg: "bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700" },
        { value: "gone", label: "Give Up", icon: Ban, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
      ];
    case "booked":
      return [
        { value: "visited", label: "Visited", icon: Eye, bg: "bg-purple-600 hover:bg-purple-500 active:bg-purple-700" },
        { value: "gone", label: "Gone", icon: Ban, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
      ];
    case "visited":
      return [
        { value: "waiting", label: "I Like It", icon: Clock, bg: "bg-cyan-600 hover:bg-cyan-500 active:bg-cyan-700" },
        { value: "passed", label: "Pass", icon: ThumbsDown, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
      ];
    case "waiting":
      return [
        { value: "gone", label: "Didn't Get It", icon: Ban, bg: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500" },
      ];
    case "passed":
    case "gone":
      return [
        { value: "favorited", label: "Reopen", icon: Star, bg: "bg-yellow-600 hover:bg-yellow-500 active:bg-yellow-700" },
      ];
    default:
      return [];
  }
}

function PipelineCard({ listing }: { listing: PipelineListing }) {
  const router = useRouter();
  const supabase = createBrowserSupabaseClient();
  const [updating, setUpdating] = useState(false);
  const [imageOpen, setImageOpen] = useState(false);

  const config = STATUS_MAP[listing.status] || STATUS_MAP.favorited;
  const StatusIcon = config.icon;
  const nextActions = getNextActions(listing.status);

  const handleAction = async (newStatus: string) => {
    setUpdating(true);
    const updates: Record<string, unknown> = {
      status: newStatus,
      status_updated_at: new Date().toISOString(),
    };
    if (newStatus === "favorited") updates.favorited_at = new Date().toISOString();
    if (newStatus === "dismissed") updates.dismissed_at = new Date().toISOString();

    await supabase.from("listings").update(updates).eq("id", listing.id);
    router.refresh();
  };

  const updatedAt = listing.status_updated_at
    ? new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(listing.status_updated_at))
    : null;

  const isTerminal = listing.status === "passed" || listing.status === "gone";

  const navigateToDetail = () => {
    router.push(`/listings/${listing.id}`);
  };

  return (
    <div
      onClick={navigateToDetail}
      className={cn(
        "bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden cursor-pointer hover:border-zinc-600 transition-colors",
        "flex flex-col sm:flex-row",
        isTerminal && "opacity-60"
      )}
    >
      {/* Image */}
      <div
        className="shrink-0 cursor-zoom-in touch-manipulation"
        onClick={(e) => {
          if (listing.image_url) {
            e.stopPropagation();
            setImageOpen(true);
          }
        }}
      >
        {listing.image_url ? (
          <img
            src={listing.image_url}
            alt=""
            className="w-full h-40 sm:w-32 sm:h-full object-cover"
          />
        ) : (
          <div className="w-full h-28 sm:w-32 sm:h-full bg-zinc-800 flex items-center justify-center text-zinc-600 text-xs cursor-default">
            No img
          </div>
        )}
      </div>

      {/* Fullscreen image */}
      {imageOpen && listing.image_url && (
        <div
          className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center touch-manipulation"
          onClick={() => setImageOpen(false)}
        >
          <button
            onClick={() => setImageOpen(false)}
            aria-label="Close image"
            className="absolute top-4 right-4 w-12 h-12 rounded-full bg-white/10 active:bg-white/25 flex items-center justify-center text-white focus-visible:ring-2 focus-visible:ring-blue-500 outline-none"
          >
            <X size={24} />
          </button>
          <img
            src={listing.image_url}
            alt=""
            className="max-w-[95vw] max-h-[85vh] object-contain rounded-lg"
          />
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0 p-4 flex flex-col gap-2.5">
        {/* Top row: price + meta */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-lg font-bold text-blue-400">
            {listing.price != null ? `€${listing.price.toLocaleString()}/mo` : "N/A"}
          </span>

          {listing.hybrid_score != null && (
            <span
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center text-white font-bold text-sm",
                listing.hybrid_score >= 70
                  ? "bg-green-500"
                  : listing.hybrid_score >= 40
                    ? "bg-orange-500"
                    : "bg-red-500"
              )}
            >
              {Math.round(listing.hybrid_score)}
            </span>
          )}

          {updatedAt && (
            <span className="text-xs text-zinc-500 ml-auto">{updatedAt}</span>
          )}
        </div>

        {/* Address + details */}
        <div className="flex items-center gap-3 flex-wrap">
          <p className="text-sm text-zinc-300 truncate">
            {listing.address || "Address N/A"}
          </p>
          {listing.rooms && (
            <span className="text-xs text-zinc-500">{listing.rooms}r</span>
          )}
          {listing.size_sqm && (
            <span className="text-xs text-zinc-500">{listing.size_sqm}m²</span>
          )}
          {listing.nearest_station && (
            <span className="text-xs text-zinc-500 truncate">{listing.nearest_station}</span>
          )}
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="View original listing"
            className="text-zinc-500 hover:text-white transition-colors ml-auto min-w-[44px] min-h-[44px] flex items-center justify-center -mr-2 touch-manipulation"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink size={16} />
          </a>
        </div>

        {/* Notes preview */}
        {listing.notes && listing.notes !== "[]" && (
          <p className="text-xs text-zinc-500 italic truncate">
            {listing.notes}
          </p>
        )}

        {/* Next actions */}
        <div className="flex items-center gap-2 pt-1 overflow-x-auto scrollbar-none -mx-1 px-1">
          <span className="text-xs text-zinc-600 mr-0.5 shrink-0">Next:</span>
          {nextActions.map(({ value, label, icon: ActionIcon, bg }) => (
            <button
              key={value}
              onClick={(e) => { e.stopPropagation(); handleAction(value); }}
              disabled={updating}
              className={cn(
                "inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium text-white transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-blue-500 outline-none disabled:opacity-50 min-h-[40px] shrink-0 touch-manipulation",
                bg
              )}
            >
              <ActionIcon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

const STATUS_ORDER = [
  "favorited",
  "contacted",
  "no_reply",
  "booked",
  "visited",
  "waiting",
  "passed",
  "gone",
];

interface PipelineListProps {
  listings: PipelineListing[];
}

export function PipelineList({ listings: initialListings }: PipelineListProps) {
  const groups = STATUS_ORDER.map((status) => ({
    status,
    config: STATUS_MAP[status],
    listings: initialListings.filter((l) => l.status === status),
  })).filter((g) => g.listings.length > 0);

  const isTerminal = (status: string) => ["passed", "gone"].includes(status);

  return (
    <div className="space-y-8">
      {groups.map(({ status, config, listings }) => {
        const Icon = config.icon;
        const terminal = isTerminal(status);

        return (
          <div key={status} className="space-y-3">
            <div className={cn("flex items-center gap-3", terminal && "opacity-60")}>
              <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center text-white", config.bg)}>
                <Icon size={16} />
              </div>
              <h2 className="text-lg font-semibold text-zinc-200">
                {config.label}
              </h2>
              <span className="text-sm font-bold text-zinc-500">
                {listings.length}
              </span>
            </div>

            {listings.map((listing) => (
              <PipelineCard key={listing.id} listing={listing} />
            ))}
          </div>
        );
      })}
    </div>
  );
}
