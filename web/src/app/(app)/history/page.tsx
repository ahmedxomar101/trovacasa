import { createServerClient } from "@/lib/supabase/server";

export default async function HistoryPage() {
  const supabase = await createServerClient();

  const { data: runs } = await supabase
    .from("pipeline_runs")
    .select("id, started_at, completed_at, stage, status, stats, error_message")
    .order("started_at", { ascending: false })
    .limit(50);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Pipeline History</h1>

      {runs && runs.length > 0 ? (
        <div className="space-y-3">
          {runs.map((run) => {
            const started = new Date(run.started_at);
            const duration = run.completed_at
              ? Math.round(
                  (new Date(run.completed_at).getTime() - started.getTime()) /
                    1000
                )
              : null;

            const stats = run.stats as Record<string, unknown> | null;

            return (
              <div
                key={run.id}
                className="bg-zinc-900 border border-zinc-800 rounded-xl p-4"
              >
                <div className="flex items-center gap-3 mb-2">
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      run.status === "completed"
                        ? "bg-green-500"
                        : run.status === "running"
                          ? "bg-yellow-500 animate-pulse"
                          : "bg-red-500"
                    }`}
                  />
                  <span className="font-semibold text-zinc-200 capitalize">
                    {run.stage}
                  </span>
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      run.status === "completed"
                        ? "bg-green-900/50 text-green-400"
                        : run.status === "running"
                          ? "bg-yellow-900/50 text-yellow-400"
                          : "bg-red-900/50 text-red-400"
                    }`}
                  >
                    {run.status}
                  </span>
                  <span className="text-sm text-zinc-500 ml-auto">
                    {started.toLocaleDateString()}{" "}
                    {started.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </span>
                </div>

                <div className="flex flex-wrap gap-4 text-sm text-zinc-400">
                  {duration != null && (
                    <span>Duration: {duration}s</span>
                  )}
                  {stats &&
                    Object.entries(stats).map(([key, value]) => (
                      <span key={key}>
                        {key}:{" "}
                        <span className="text-zinc-300">
                          {typeof value === "object"
                            ? JSON.stringify(value)
                            : String(value)}
                        </span>
                      </span>
                    ))}
                </div>

                {run.error_message && (
                  <div className="mt-2 text-sm text-red-400 bg-red-950/30 rounded-lg p-2">
                    {run.error_message}
                  </div>
                )}

                <div className="mt-2 text-[10px] text-zinc-600 font-mono">
                  {run.id}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center text-zinc-500 py-20">
          No pipeline runs recorded yet.
        </div>
      )}
    </div>
  );
}
