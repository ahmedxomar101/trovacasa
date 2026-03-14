import { createServerClient } from "@/lib/supabase/server";
import Link from "next/link";
import { cn } from "@/lib/utils";

export const metadata = { title: "Notifications" };

const STATUS_COLORS: Record<string, string> = {
  favorited: "bg-yellow-500",
  contacted: "bg-blue-500",
  no_reply: "bg-orange-500",
  booked: "bg-emerald-500",
  visited: "bg-purple-500",
  waiting: "bg-cyan-500",
  passed: "bg-zinc-600",
  gone: "bg-zinc-500",
  dismissed: "bg-zinc-700",
};

interface NotifListing {
  id: string;
  address: string | null;
  price: number | null;
  hybrid_score: number | null;
  image_url: string | null;
  rooms: number | null;
  size_sqm: number | null;
  nearest_station: string | null;
  commute_minutes: number | null;
  status: string;
  notified_at: string;
  total_monthly_cost: number | null;
  condo_fees: number | null;
  is_private: boolean | null;
  energy_class: string | null;
}

/** Group listings into batches — items notified within 30 min of each other = same batch */
function groupIntoBatches(listings: NotifListing[]) {
  const batches: { timestamp: Date; listings: NotifListing[] }[] = [];
  const GAP_MS = 30 * 60 * 1000; // 30 minutes

  // Listings come sorted by notified_at DESC from DB
  for (const l of listings) {
    const ts = new Date(l.notified_at);
    const last = batches[batches.length - 1];

    if (last && last.timestamp.getTime() - ts.getTime() < GAP_MS) {
      last.listings.push(l);
    } else {
      batches.push({ timestamp: ts, listings: [l] });
    }
  }

  // Sort within each batch: lowest score first, highest last (bottom)
  for (const batch of batches) {
    batch.listings.sort(
      (a, b) => (a.hybrid_score ?? 0) - (b.hybrid_score ?? 0)
    );
  }

  return batches;
}

export default async function NotificationsPage() {
  const supabase = await createServerClient();

  const { data: listings } = await supabase
    .from("listings")
    .select(
      "id, address, price, hybrid_score, image_url, rooms, size_sqm, nearest_station, commute_minutes, status, notified_at, total_monthly_cost, condo_fees, is_private, energy_class"
    )
    .not("notified_at", "is", null)
    .order("notified_at", { ascending: false })
    .limit(200);

  const dateFmt = new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  const batches = listings ? groupIntoBatches(listings as NotifListing[]) : [];

  return (
    <div className="space-y-6 max-w-[1000px]">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Notifications</h1>
        <p className="text-zinc-500 mt-1">
          Listings sent via Telegram (score &ge; 70)
        </p>
      </div>

      {batches.length === 0 ? (
        <div className="text-center text-zinc-500 py-24 text-lg">
          No notifications sent yet.
        </div>
      ) : (
        <div className="space-y-8">
          {batches.map((batch, i) => (
            <div key={i} className="space-y-3">
              {/* Batch header */}
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <h2 className="text-sm font-semibold text-zinc-400">
                  {dateFmt.format(batch.timestamp)}
                </h2>
                <span className="text-xs text-zinc-600">
                  {batch.listings.length} listing{batch.listings.length !== 1 ? "s" : ""}
                </span>
                <div className="flex-1 h-px bg-zinc-800" />
              </div>

              {/* Cards */}
              {batch.listings.map((l) => {
                const isDismissed = l.status === "dismissed";

                return (
                  <Link
                    key={l.id}
                    href={`/listings/${l.id}`}
                    className={cn(
                      "bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden flex flex-col sm:flex-row hover:border-zinc-600 transition-colors min-h-[44px] touch-manipulation",
                      isDismissed && "opacity-40"
                    )}
                  >
                    {/* Image */}
                    <div className="shrink-0">
                      {l.image_url ? (
                        <img
                          src={l.image_url}
                          alt=""
                          className="w-full h-36 sm:w-28 sm:h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-24 sm:w-28 sm:h-full bg-zinc-800 flex items-center justify-center text-zinc-600 text-xs">
                          No img
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0 p-3.5 sm:p-4 flex flex-col gap-2">
                      {/* Top row */}
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="text-lg font-bold text-blue-400" style={{ fontVariantNumeric: "tabular-nums" }}>
                          {l.price != null
                            ? `€${l.price.toLocaleString()}/mo`
                            : "N/A"}
                        </span>

                        {l.total_monthly_cost != null &&
                          l.condo_fees != null &&
                          l.condo_fees > 0 && (
                            <span className="text-xs text-zinc-500">
                              (€{Math.round(l.total_monthly_cost)} total)
                            </span>
                          )}

                        {l.hybrid_score != null && (
                          <span
                            className={cn(
                              "w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-xs shrink-0",
                              l.hybrid_score >= 70
                                ? "bg-green-500"
                                : l.hybrid_score >= 40
                                  ? "bg-orange-500"
                                  : "bg-red-500"
                            )}
                          >
                            {Math.round(l.hybrid_score)}
                          </span>
                        )}

                        {l.status !== "active" && (
                          <span
                            className={cn(
                              "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full text-white shrink-0",
                              STATUS_COLORS[l.status] || "bg-zinc-700"
                            )}
                          >
                            {l.status.replace("_", " ")}
                          </span>
                        )}
                      </div>

                      {/* Details */}
                      <div className="flex items-center gap-2 flex-wrap text-sm">
                        <p className="text-zinc-300 truncate w-full sm:w-auto">
                          {l.address || "Address N/A"}
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                          {l.rooms && (
                            <span className="text-xs text-zinc-500">{l.rooms}r</span>
                          )}
                          {l.size_sqm && (
                            <span className="text-xs text-zinc-500">
                              {l.size_sqm}m²
                            </span>
                          )}
                          {l.nearest_station && (
                            <span className="text-xs text-zinc-500 truncate">
                              {l.nearest_station}
                            </span>
                          )}
                          {l.commute_minutes != null && (
                            <span className="text-xs text-zinc-500">
                              {l.commute_minutes}min
                            </span>
                          )}
                          {l.is_private && (
                            <span className="text-[10px] font-bold text-emerald-400 uppercase">
                              Privato
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
