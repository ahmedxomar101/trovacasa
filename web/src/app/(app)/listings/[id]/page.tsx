import { createServerClient } from "@/lib/supabase/server";
import { extractGalleryUrls } from "@/lib/utils/gallery";
import { ScoreBar } from "@/components/listings/ScoreBar";
import { BudgetChip } from "@/components/listings/BudgetChip";
import { ActionButtons } from "@/components/detail/ActionButtons";
import { ImageGallery } from "@/components/detail/ImageGallery";
import { NotesEditor } from "@/components/detail/NotesEditor";
import { ExternalLink, ChevronLeft, Phone as PhoneIcon } from "lucide-react";
import { notFound } from "next/navigation";
import Link from "next/link";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ListingDetailPage({ params }: PageProps) {
  const { id } = await params;
  const supabase = await createServerClient();

  const { data: listing, error } = await supabase
    .from("listings")
    .select("*")
    .eq("id", id)
    .single();

  if (error || !listing) {
    notFound();
  }

  const galleryUrls = extractGalleryUrls(listing.raw_data, listing.source);
  const allImages = galleryUrls.length > 0 ? galleryUrls : listing.image_url ? [listing.image_url] : [];

  const isPrivato = listing.agent?.toLowerCase().includes("privato") ?? false;

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Sticky back nav */}
      <div className="sticky top-0 z-20 bg-zinc-950/90 backdrop-blur-sm -mx-4 px-4 py-3 sm:static sm:mx-0 sm:px-0 sm:py-0 sm:bg-transparent sm:backdrop-blur-none">
        <Link href="/listings" className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline min-h-[44px] touch-manipulation">
          <ChevronLeft size={18} />
          Back to listings
        </Link>
      </div>

      {/* Image gallery */}
      {allImages.length > 0 && (
        <ImageGallery images={allImages} />
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl sm:text-2xl font-bold">
            {listing.address || "Address not available"}
          </h1>
          <p className="text-xl font-bold text-blue-400 mt-1">
            {listing.price != null
              ? `€${listing.price.toLocaleString()}/mo`
              : "Price N/A"}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {listing.hybrid_score != null && (
            <div
              className={`w-14 h-14 rounded-full flex items-center justify-center text-white font-extrabold text-xl shadow-lg ${
                listing.hybrid_score >= 70
                  ? "bg-green-500"
                  : listing.hybrid_score >= 40
                    ? "bg-orange-500"
                    : "bg-red-500"
              }`}
            >
              {Math.round(listing.hybrid_score)}
            </div>
          )}
          <BudgetChip
            status={listing.budget_status}
            totalCost={listing.total_monthly_cost}
            price={listing.price}
          />
        </div>
      </div>

      {/* Phone CTA — prominent on mobile */}
      {listing.phone && (
        <a
          href={`tel:${listing.phone}`}
          className="flex items-center justify-center gap-3 w-full py-3.5 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold rounded-xl text-base transition-colors min-h-[52px] touch-manipulation sm:w-auto sm:inline-flex sm:px-6"
        >
          <PhoneIcon size={20} />
          Call {listing.phone}
        </a>
      )}

      {/* Actions */}
      <ActionButtons listing={listing} />

      {/* Notes */}
      <NotesEditor listingId={listing.id} initialNotes={listing.notes} />

      {/* Details grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 sm:gap-3">
        {[
          { label: "Rooms", value: listing.rooms },
          { label: "Size", value: listing.size_sqm ? `${listing.size_sqm} sqm` : null },
          { label: "Floor", value: listing.floor },
          { label: "Bathrooms", value: listing.bathrooms },
          { label: "Source", value: listing.source },
          { label: "Condo Fees", value: listing.condo_fees != null ? `\u20ac${Math.round(listing.condo_fees)}${listing.condo_included ? " (incl.)" : " (extra)"}` : null },
          { label: "Furnished", value: listing.furnished },
          { label: "Contract", value: listing.contract_type },
          { label: "Deposit", value: listing.deposit_months ? `${listing.deposit_months} months` : null },
          { label: "Heating", value: listing.heating },
          { label: "Heating Fuel", value: listing.heating_fuel },
          { label: "AC", value: listing.air_conditioning != null ? (listing.air_conditioning ? "Yes" : "No") : null },
          { label: "Elevator", value: listing.elevator != null ? (listing.elevator ? "Yes" : "No") : null },
          { label: "Balcony", value: listing.balcony != null ? (listing.balcony ? "Yes" : "No") : null },
          { label: "Energy Class", value: listing.energy_class },
          { label: "Condition", value: listing.condition },
          { label: "Orientation", value: listing.orientation },
          { label: "Available From", value: listing.available_from },
          { label: "Building Age", value: listing.building_age },
          { label: "Photos", value: listing.num_photos },
        ]
          .filter((item) => item.value != null)
          .map(({ label, value }) => (
            <div key={label} className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
              <div className="text-[11px] text-zinc-500 uppercase tracking-wider">{label}</div>
              <div className="text-sm font-medium mt-0.5 text-zinc-200">
                {String(value)}
              </div>
            </div>
          ))}
      </div>

      {/* Contact */}
      {(listing.agent || listing.phone) && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2">
          <h2 className="font-semibold text-zinc-300">Contact</h2>
          <div className="space-y-1.5">
            {listing.agent && (
              <p className={`text-sm font-medium ${isPrivato ? "text-emerald-400" : "text-zinc-200"}`}>
                {isPrivato ? "Privato (no agency)" : listing.agent}
              </p>
            )}
            {listing.phone && (
              <a
                href={`tel:${listing.phone}`}
                className="inline-flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 transition-colors min-h-[44px] touch-manipulation"
              >
                <PhoneIcon size={16} />
                {listing.phone}
              </a>
            )}
          </div>
        </div>
      )}

      {/* Metro & Commute */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2">
        <h2 className="font-semibold text-zinc-300">Metro & Commute</h2>
        {listing.nearest_station && (
          <p className="text-sm text-zinc-400">
            Nearest: <span className="text-zinc-200">{listing.nearest_station}</span>
          </p>
        )}
        {listing.commute_minutes != null && (
          <p className="text-sm text-zinc-400">
            Commute to Tre Torri: <span className="text-zinc-200">{listing.commute_minutes} min</span>
          </p>
        )}
        {listing.neighborhood_name && (
          <p className="text-sm text-zinc-400">
            Zone: <span className="text-zinc-200 capitalize">{listing.neighborhood_name}</span>
          </p>
        )}
      </div>

      {/* Score breakdown */}
      {listing.hybrid_score != null && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-2">
          <h2 className="font-semibold text-zinc-300">Score Breakdown</h2>
          <div className="space-y-1.5">
            <ScoreBar score={listing.commute_score} label="Commute" />
            <ScoreBar score={listing.metro_score} label="Metro" />
            <ScoreBar score={listing.livability_score} label="Livability" />
            <ScoreBar score={listing.scam_score} label="Safety" />
            <ScoreBar score={listing.freshness_score} label="Freshness" />
            <ScoreBar score={listing.quality_score} label="Quality" />
            <ScoreBar score={listing.neighborhood_score} label="Neighborhood" />
          </div>
        </div>
      )}

      {/* Red flags */}
      {listing.red_flags && listing.red_flags !== "[]" && listing.red_flags.length > 0 && (() => {
        let flags: string[] = [];
        try { flags = JSON.parse(listing.red_flags); } catch { flags = [listing.red_flags]; }
        if (!flags.length) return null;
        return (
          <div className="bg-red-950/30 border border-red-900 rounded-xl p-4">
            <h2 className="font-semibold text-red-400 mb-2">Red Flags</h2>
            <ul className="space-y-1.5">
              {flags.map((flag, i) => (
                <li key={i} className="text-sm text-red-300 flex gap-2">
                  <span className="shrink-0 mt-0.5">•</span>
                  <span>{flag}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      })()}

      {/* Description */}
      {listing.description && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <h2 className="font-semibold text-zinc-300 mb-2">Description</h2>
          <p className="text-sm text-zinc-400 whitespace-pre-wrap leading-relaxed">
            {listing.description}
          </p>
        </div>
      )}

      {/* External link */}
      <a
        href={listing.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 text-blue-400 hover:underline font-medium min-h-[44px] touch-manipulation"
      >
        View original listing <ExternalLink size={16} />
      </a>

      {/* ID */}
      <div className="text-xs text-zinc-600 font-mono pb-8 sm:pb-4">
        ID: {listing.id}
      </div>
    </div>
  );
}
