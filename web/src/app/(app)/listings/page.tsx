import { createServerClient } from "@/lib/supabase/server";
import { LISTING_LIST_COLUMNS } from "@/lib/supabase/types";
import { ListingCard } from "@/components/listings/ListingCard";
import { FilterBar } from "@/components/listings/FilterBar";
import { Suspense } from "react";

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

async function ListingsGrid({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const supabase = await createServerClient();

  let query = supabase
    .from("listings")
    .select(LISTING_LIST_COLUMNS)
    .neq("status", "dismissed");

  // Source filter
  const source = searchParams.source as string | undefined;
  if (source && source !== "all") {
    query = query.eq("source", source);
  }

  // Min score
  const minScore = searchParams.minScore as string | undefined;
  if (minScore) {
    query = query.gte("hybrid_score", parseFloat(minScore));
  }

  // Max price
  const maxPrice = searchParams.maxPrice as string | undefined;
  if (maxPrice) {
    query = query.lte("price", parseInt(maxPrice));
  }

  // Budget
  const budget = searchParams.budget as string | undefined;
  if (budget && budget !== "all") {
    query = query.eq("budget_status", budget);
  }

  // Privato
  const privato = searchParams.privato as string | undefined;
  if (privato === "1") {
    query = query.eq("is_private", true);
  }

  // Days filter
  const days = searchParams.days as string | undefined;
  if (days) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - parseInt(days));
    query = query.gte("creation_date", cutoff.toISOString().split("T")[0]);
  }

  // Sort
  const sort = (searchParams.sort as string) || "hybrid";
  switch (sort) {
    case "price_asc":
      query = query.order("price", { ascending: true, nullsFirst: false });
      break;
    case "price_desc":
      query = query.order("price", { ascending: false, nullsFirst: false });
      break;
    case "newest":
      query = query.order("creation_date", {
        ascending: false,
        nullsFirst: false,
      });
      break;
    default:
      query = query.order("hybrid_score", {
        ascending: false,
        nullsFirst: false,
      });
  }

  query = query.limit(200);

  const { data: listings, error } = await query;

  if (error) {
    return (
      <div className="text-red-400 p-6 text-lg">
        Error loading listings: {error.message}
      </div>
    );
  }

  if (!listings || listings.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-24 text-lg">
        No listings match the current filters.
      </div>
    );
  }

  return (
    <>
      <p className="text-sm text-zinc-500 mb-5">
        {listings.length} listings shown
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-6">
        {listings.map((listing) => (
          <ListingCard key={listing.id} listing={listing} />
        ))}
      </div>
    </>
  );
}

export default async function ListingsPage({ searchParams }: PageProps) {
  const params = await searchParams;

  return (
    <div className="space-y-6 max-w-[1800px]">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Listings</h1>
        <p className="text-zinc-500 mt-1">Browse and filter available apartments</p>
      </div>
      <Suspense fallback={<div className="text-zinc-500">Loading filters...</div>}>
        <FilterBar />
      </Suspense>
      <Suspense
        fallback={
          <div className="text-zinc-500 py-12 text-center text-lg">
            Loading listings...
          </div>
        }
      >
        <ListingsGrid searchParams={params} />
      </Suspense>
    </div>
  );
}
