import { createServerClient } from "@/lib/supabase/server";
import { LISTING_LIST_COLUMNS } from "@/lib/supabase/types";
import { PipelineList } from "@/components/pipeline/PipelineList";

export const metadata = { title: "Shortlist" };

const ACTIVE_STATUSES = [
  "favorited",
  "contacted",
  "no_reply",
  "booked",
  "visited",
  "waiting",
  "passed",
  "gone",
];

export default async function PipelinePage() {
  const supabase = await createServerClient();

  const { data: listings } = await supabase
    .from("listings")
    .select(LISTING_LIST_COLUMNS + ", notes, status_updated_at")
    .in("status", ACTIVE_STATUSES)
    .order("status_updated_at", { ascending: false });

  return (
    <div className="space-y-6 max-w-[1200px]">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Shortlist</h1>
        <p className="text-zinc-500 mt-1">
          Manage your listings through the rental process
        </p>
      </div>

      {!listings || listings.length === 0 ? (
        <div className="text-center text-zinc-500 py-24 text-lg">
          No listings in your pipeline yet. Save listings from the feed to get started.
        </div>
      ) : (
        <PipelineList listings={listings as any} />
      )}
    </div>
  );
}
