import { createServerClient } from "@/lib/supabase/server";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface TopListing {
  id: string;
  price: number | null;
  address: string | null;
  hybrid_score: number | null;
  nearest_station: string | null;
  image_url: string | null;
  rooms: number | null;
  size_sqm: number | null;
  commute_minutes: number | null;
}

function TopSection({ title, listings }: { title: string; listings: TopListing[] | null }) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-zinc-200 mb-4">{title}</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
        {listings && listings.length > 0 ? (
          listings.map((listing, i) => (
            <Link
              key={listing.id}
              href={`/listings/${listing.id}`}
              className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden hover:border-zinc-600 transition-colors group"
            >
              <div className="relative h-36 bg-zinc-800">
                {listing.image_url ? (
                  <img
                    src={listing.image_url}
                    alt=""
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-600 text-sm">
                    No Image
                  </div>
                )}
                <div className="absolute top-2 left-2 w-8 h-8 rounded-full bg-black/70 flex items-center justify-center text-white text-sm font-bold">
                  #{i + 1}
                </div>
                {listing.hybrid_score != null && (
                  <div
                    className={cn(
                      "absolute top-2 right-2 w-10 h-10 rounded-full flex items-center justify-center text-white font-extrabold text-sm",
                      listing.hybrid_score >= 70
                        ? "bg-green-500"
                        : listing.hybrid_score >= 40
                          ? "bg-orange-500"
                          : "bg-red-500"
                    )}
                  >
                    {Math.round(listing.hybrid_score)}
                  </div>
                )}
              </div>
              <div className="p-3.5 space-y-1.5">
                <div className="text-lg font-bold text-blue-400">
                  {listing.price
                    ? `€${listing.price.toLocaleString()}/mo`
                    : "N/A"}
                </div>
                <p className="text-sm text-zinc-400 truncate">
                  {listing.address || "Address N/A"}
                </p>
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  {listing.rooms && <span>{listing.rooms}r</span>}
                  {listing.size_sqm && <span>{listing.size_sqm}m²</span>}
                  {listing.commute_minutes != null && (
                    <span>{listing.commute_minutes}min</span>
                  )}
                </div>
                {listing.nearest_station && (
                  <p className="text-xs text-zinc-500 truncate">
                    {listing.nearest_station}
                  </p>
                )}
              </div>
            </Link>
          ))
        ) : (
          <p className="text-sm text-zinc-500 col-span-full">
            No scored listings in this period.
          </p>
        )}
      </div>
    </div>
  );
}

export default async function DashboardPage() {
  const supabase = await createServerClient();

  // Stats
  const { count: totalActive } = await supabase
    .from("listings")
    .select("id", { count: "exact", head: true })
    .eq("status", "active");

  const { count: totalFavorited } = await supabase
    .from("listings")
    .select("id", { count: "exact", head: true })
    .in("status", ["favorited", "contacted", "no_reply", "booked", "visited", "waiting"]);

  // Compute stats from listings
  const { data: scores } = await supabase
    .from("listings")
    .select("hybrid_score, price, creation_date")
    .eq("status", "active");

  let avgScore = 0;
  let avgPrice = 0;
  let newThisWeek = 0;

  if (scores && scores.length > 0) {
    const validScores = scores.filter((s) => s.hybrid_score != null);
    avgScore = validScores.length
      ? validScores.reduce((a, b) => a + (b.hybrid_score || 0), 0) /
        validScores.length
      : 0;
    const validPrices = scores.filter((s) => s.price != null);
    avgPrice = validPrices.length
      ? validPrices.reduce((a, b) => a + (b.price || 0), 0) /
        validPrices.length
      : 0;
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    newThisWeek = scores.filter(
      (s) => s.creation_date && new Date(s.creation_date) >= weekAgo
    ).length;
  }

  const selectCols =
    "id, price, address, hybrid_score, nearest_station, image_url, rooms, size_sqm, commute_minutes";

  // Top 5 last 7 days
  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const { data: top5_7d } = await supabase
    .from("listings")
    .select(selectCols)
    .eq("status", "active")
    .not("hybrid_score", "is", null)
    .gte("creation_date", sevenDaysAgo.toISOString())
    .order("hybrid_score", { ascending: false })
    .limit(5);

  // Top 3 last 3 days
  const threeDaysAgo = new Date();
  threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
  const { data: top3_3d } = await supabase
    .from("listings")
    .select(selectCols)
    .eq("status", "active")
    .not("hybrid_score", "is", null)
    .gte("creation_date", threeDaysAgo.toISOString())
    .order("hybrid_score", { ascending: false })
    .limit(3);

  // Recent pipeline runs
  const { data: recentRuns } = await supabase
    .from("pipeline_runs")
    .select("id, started_at, completed_at, stage, status, stats")
    .order("started_at", { ascending: false })
    .limit(5);

  return (
    <div className="space-y-8 max-w-[1400px]">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-zinc-500 mt-1">Overview of your apartment search</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 sm:gap-4">
        {[
          { label: "Active", value: totalActive || 0 },
          { label: "New This Week", value: newThisWeek },
          { label: "Avg Score", value: Math.round(avgScore) },
          {
            label: "Avg Price",
            value: `€${Math.round(avgPrice).toLocaleString()}`,
          },
          { label: "Shortlisted", value: totalFavorited || 0 },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 sm:p-5"
          >
            <div className="text-2xl sm:text-3xl font-bold text-zinc-100" style={{ fontVariantNumeric: "tabular-nums" }}>{value}</div>
            <div className="text-[10px] sm:text-xs text-zinc-500 uppercase tracking-wider mt-1">
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* Top 3 — Last 3 Days */}
      <TopSection title="Top 3 — Last 3 Days" listings={top3_3d} />

      {/* Top 5 — Last 7 Days */}
      <TopSection title="Top 5 — Last 7 Days" listings={top5_7d} />

      {/* Recent pipeline runs */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
        <h2 className="text-lg font-semibold text-zinc-200 mb-4">
          Recent Pipeline Runs
        </h2>
        {recentRuns && recentRuns.length > 0 ? (
          <div className="space-y-2">
            {recentRuns.map((run) => {
              const started = new Date(run.started_at);
              const duration = run.completed_at
                ? Math.round(
                    (new Date(run.completed_at).getTime() -
                      started.getTime()) /
                      1000
                  )
                : null;
              return (
                <div
                  key={run.id}
                  className="flex items-center gap-3 text-sm p-3 rounded-xl bg-zinc-800/30"
                >
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      run.status === "completed"
                        ? "bg-green-500"
                        : run.status === "running"
                          ? "bg-yellow-500"
                          : "bg-red-500"
                    }`}
                  />
                  <span className="text-zinc-300 capitalize font-medium">
                    {run.stage}
                  </span>
                  <span className="text-zinc-500">
                    {started.toLocaleDateString()}{" "}
                    {started.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  {duration != null && (
                    <span className="text-zinc-600">{duration}s</span>
                  )}
                  <span
                    className={`ml-auto text-xs font-semibold ${
                      run.status === "completed"
                        ? "text-green-400"
                        : run.status === "running"
                          ? "text-yellow-400"
                          : "text-red-400"
                    }`}
                  >
                    {run.status}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-zinc-500">
            No pipeline runs recorded yet.
          </p>
        )}
      </div>
    </div>
  );
}
