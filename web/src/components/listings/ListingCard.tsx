"use client";

import Link from "next/link";
import { Star, X, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScoreBar } from "./ScoreBar";
import { BudgetChip } from "./BudgetChip";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useState, useCallback, useEffect } from "react";
import type { Listing } from "@/lib/supabase/types";

type ListingCardData = Partial<Listing> &
  Pick<Listing, "id" | "source" | "url" | "status">;

interface ListingCardProps {
  listing: ListingCardData;
}

export function ListingCard({ listing }: ListingCardProps) {
  const router = useRouter();
  const supabase = createBrowserSupabaseClient();
  const [actionFeedback, setActionFeedback] = useState<
    "saved" | "dismissed" | null
  >(null);
  const [galleryUrls, setGalleryUrls] = useState<string[] | null>(null);
  const [imgIndex, setImgIndex] = useState(0);
  const [loadingGallery, setLoadingGallery] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    if (!fullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
      if (e.key === "ArrowRight" && galleryUrls && galleryUrls.length > 1) {
        setImgIndex((prev) => (prev + 1) % galleryUrls.length);
      }
      if (e.key === "ArrowLeft" && galleryUrls && galleryUrls.length > 1) {
        setImgIndex((prev) => (prev - 1 + galleryUrls.length) % galleryUrls.length);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen, galleryUrls]);

  const updateStatus = async (status: string) => {
    const feedback = status === "favorited" ? "saved" : "dismissed";
    setActionFeedback(feedback as "saved" | "dismissed");
    const timestampCol =
      status === "favorited" ? "favorited_at" : "dismissed_at";
    await supabase
      .from("listings")
      .update({
        status,
        status_updated_at: new Date().toISOString(),
        [timestampCol]: new Date().toISOString(),
      })
      .eq("id", listing.id);
    setTimeout(() => {
      router.refresh();
    }, 400);
  };

  const loadGallery = useCallback(async () => {
    if (galleryUrls || loadingGallery) return galleryUrls;
    setLoadingGallery(true);
    try {
      const res = await fetch(`/api/gallery?id=${listing.id}`);
      const data = await res.json();
      const urls = data.urls as string[];
      setGalleryUrls(urls);
      setLoadingGallery(false);
      return urls;
    } catch {
      setLoadingGallery(false);
      return null;
    }
  }, [listing.id, galleryUrls, loadingGallery]);

  const navigate = async (dir: "prev" | "next", e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const urls = galleryUrls || (await loadGallery());
    if (!urls || urls.length <= 1) return;
    setImgIndex((prev) =>
      dir === "next"
        ? (prev + 1) % urls.length
        : (prev - 1 + urls.length) % urls.length
    );
  };

  const currentImage =
    galleryUrls && galleryUrls.length > 0
      ? galleryUrls[imgIndex]
      : listing.image_url;

  const totalImages =
    galleryUrls?.length || listing.num_photos || (listing.image_url ? 1 : 0);

  const hybridScore = listing.hybrid_score;
  const scoreClass =
    hybridScore != null
      ? hybridScore >= 70
        ? "bg-green-500"
        : hybridScore >= 40
          ? "bg-orange-500"
          : "bg-red-500"
      : "";

  const isPrivato =
    listing.agent?.toLowerCase().includes("privato") ?? false;

  const floor = listing.floor;
  let floorIcon = "";
  if (floor) {
    const fl = floor.trim().toLowerCase();
    if (["bj", "ss", "sb", "b"].includes(fl)) floorIcon = "B";
    else if (["en", "g", "0"].includes(fl)) floorIcon = "G";
    else if (fl === "m") floorIcon = "M";
    else {
      const nums = fl.match(/\d+/);
      floorIcon = nums ? nums[0] : fl.slice(0, 2).toUpperCase();
    }
  }

  return (
    <>
      {/* Fullscreen image viewer */}
      {fullscreen && currentImage && (
        <div
          className="fixed inset-0 z-50 bg-black/95 backdrop-blur flex items-center justify-center overscroll-contain touch-manipulation"
          onClick={() => setFullscreen(false)}
        >
          <button
            onClick={() => setFullscreen(false)}
            aria-label="Close fullscreen"
            className="absolute top-4 right-4 w-12 h-12 rounded-full bg-white/10 active:bg-white/25 flex items-center justify-center text-white transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 z-10"
          >
            <X size={24} />
          </button>
          {galleryUrls && galleryUrls.length > 1 && (
            <>
              <button
                onClick={(e) => navigate("prev", e)}
                aria-label="Previous image"
                className="absolute left-3 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 active:bg-white/20 flex items-center justify-center text-white transition-colors focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <ChevronLeft size={28} />
              </button>
              <button
                onClick={(e) => navigate("next", e)}
                aria-label="Next image"
                className="absolute right-3 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-white/10 active:bg-white/20 flex items-center justify-center text-white transition-colors focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <ChevronRight size={28} />
              </button>
            </>
          )}
          <img
            src={currentImage}
            alt="Full size"
            className="max-w-[95vw] max-h-[85vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
          {galleryUrls && galleryUrls.length > 1 && (
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-black/60 text-white text-sm px-4 py-2 rounded-full">
              {imgIndex + 1} / {galleryUrls.length}
            </div>
          )}
        </div>
      )}

      <div
        className={cn(
          "bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden hover:border-zinc-600 transition-colors group cursor-pointer relative",
          actionFeedback === "dismissed" && "opacity-50 scale-[0.98]"
        )}
      >
        {/* Action feedback overlay */}
        {actionFeedback && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div
              className={cn(
                "flex flex-col items-center gap-2",
                actionFeedback === "saved"
                  ? "text-yellow-400"
                  : "text-zinc-400"
              )}
            >
              {actionFeedback === "saved" ? (
                <Star size={36} fill="currentColor" />
              ) : (
                <X size={36} />
              )}
              <span className="text-lg font-semibold text-white">
                {actionFeedback === "saved" ? "Saved!" : "Dismissed"}
              </span>
            </div>
          </div>
        )}

        {/* Image */}
        <div
          className="relative h-52 sm:h-56 bg-zinc-800 cursor-pointer touch-manipulation"
          onClick={(e) => {
            if (currentImage) {
              e.preventDefault();
              e.stopPropagation();
              loadGallery();
              setFullscreen(true);
            }
          }}
        >
          {currentImage ? (
            <img
              src={currentImage}
              alt={listing.title || "Listing"}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-zinc-600 text-base">
              No Image
            </div>
          )}

          {/* Image navigation arrows — always visible on mobile */}
          {(totalImages > 1 || listing.num_photos) && (
            <>
              <button
                onClick={(e) => navigate("prev", e)}
                aria-label="Previous image"
                className="absolute left-2 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-black/50 active:bg-black/70 flex items-center justify-center text-white opacity-70 md:opacity-0 md:group-hover:opacity-100 transition-opacity touch-manipulation"
              >
                <ChevronLeft size={22} />
              </button>
              <button
                onClick={(e) => navigate("next", e)}
                aria-label="Next image"
                className="absolute right-2 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-black/50 active:bg-black/70 flex items-center justify-center text-white opacity-70 md:opacity-0 md:group-hover:opacity-100 transition-opacity touch-manipulation"
              >
                <ChevronRight size={22} />
              </button>
            </>
          )}

          {/* Image counter */}
          {galleryUrls && galleryUrls.length > 1 && (
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/60 text-white text-xs px-3 py-1 rounded-full">
              {imgIndex + 1} / {galleryUrls.length}
            </div>
          )}

          {/* Hybrid score badge */}
          {hybridScore != null && (
            <div
              className={cn(
                "absolute top-3 left-3 w-12 h-12 rounded-full flex items-center justify-center text-white font-extrabold text-base shadow-lg",
                scoreClass
              )}
            >
              {Math.round(hybridScore)}
            </div>
          )}

          {/* Floor badge */}
          {floorIcon && (
            <div className="absolute top-3 right-3 px-3 h-9 rounded-lg bg-black/65 backdrop-blur flex items-center justify-center text-white text-sm font-bold">
              F{floorIcon}
            </div>
          )}

          {/* Quick actions — always visible on mobile */}
          <div className="absolute bottom-2 right-2 flex gap-2 opacity-80 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                updateStatus(listing.status === "favorited" ? "active" : "favorited");
              }}
              aria-label={listing.status === "favorited" ? "Unsave listing" : "Save listing"}
              className="w-11 h-11 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-yellow-400 active:bg-black/80 transition-colors touch-manipulation focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <Star size={20} fill={listing.status === "favorited" ? "currentColor" : "none"} />
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                updateStatus("dismissed");
              }}
              aria-label="Dismiss listing"
              className="w-11 h-11 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-zinc-400 active:bg-black/80 transition-colors touch-manipulation focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Body */}
        <Link href={`/listings/${listing.id}`}>
          <div className="p-4 sm:p-5 space-y-2.5">
            {/* Price + budget */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xl font-bold text-blue-400">
                {listing.price != null
                  ? `€${listing.price.toLocaleString()}/mo`
                  : "N/A"}
              </span>
              <BudgetChip
                status={listing.budget_status ?? null}
                totalCost={listing.total_monthly_cost ?? null}
                price={listing.price ?? null}
              />
            </div>

            {/* Meta pills */}
            <div className="flex flex-wrap gap-1.5">
              {listing.rooms && (
                <span className="text-sm text-zinc-300 bg-zinc-800 px-2.5 py-1 rounded-lg">
                  {listing.rooms} rooms
                </span>
              )}
              {listing.size_sqm && (
                <span className="text-sm text-zinc-300 bg-zinc-800 px-2.5 py-1 rounded-lg">
                  {listing.size_sqm} sqm
                </span>
              )}
              {listing.condo_fees != null && (
                <span className="text-sm text-zinc-300 bg-zinc-800 px-2.5 py-1 rounded-lg">
                  Condo: €{Math.round(listing.condo_fees)}{" "}
                  {listing.condo_included ? "(incl.)" : "(extra)"}
                </span>
              )}
            </div>

            {/* Address */}
            <p className="text-[15px] text-zinc-300 truncate">
              {listing.address || "Address not available"}
            </p>

            {/* Metro + Commute */}
            <div className="flex flex-wrap gap-1.5">
              {listing.nearest_station && (
                <span className="text-sm text-zinc-400 bg-zinc-800/60 px-2.5 py-1 rounded-lg">
                  Metro: {listing.nearest_station}
                </span>
              )}
              {listing.commute_minutes != null && (
                <span className="text-sm text-zinc-400 bg-zinc-800/60 px-2.5 py-1 rounded-lg">
                  Commute: {listing.commute_minutes} min
                </span>
              )}
            </div>

            {/* Source + Agent */}
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "text-sm font-semibold px-3 py-1 rounded-full capitalize",
                  listing.source === "idealista"
                    ? "bg-yellow-400 text-zinc-900"
                    : "bg-red-600 text-white"
                )}
              >
                {listing.source}
              </span>
              {isPrivato ? (
                <span className="text-sm font-semibold text-green-400">
                  {listing.agent}
                </span>
              ) : listing.agent ? (
                <span className="text-sm text-zinc-500 truncate">{listing.agent}</span>
              ) : null}
            </div>

            {/* Extras */}
            {(listing.furnished || listing.energy_class) && (
              <div className="text-sm text-zinc-500">
                {[
                  listing.furnished && `Furnished: ${listing.furnished}`,
                  listing.energy_class && `Energy: ${listing.energy_class}`,
                  listing.condition && `Condition: ${listing.condition}`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            )}

            {/* Score bars */}
            {hybridScore != null && (
              <div className="space-y-1.5 pt-2">
                <ScoreBar score={listing.commute_score} label="Commute" />
                <ScoreBar score={listing.metro_score} label="Metro" />
                <ScoreBar score={listing.livability_score} label="Livability" />
                <ScoreBar score={listing.scam_score} label="Safety" />
                <ScoreBar score={listing.freshness_score} label="Fresh" />
                <ScoreBar score={listing.quality_score} label="Quality" />
                <ScoreBar score={listing.neighborhood_score} label="Neighborhood" />
              </div>
            )}
          </div>
        </Link>
      </div>
    </>
  );
}
