"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useRef } from "react";
import { cn } from "@/lib/utils";

export function FilterBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  const updateParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value && value !== "all" && value !== "0" && value !== "") {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      router.push(`/listings?${params.toString()}`);
    },
    [router, searchParams]
  );

  const debouncedUpdate = useCallback(
    (key: string, value: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => updateParam(key, value), 400);
    },
    [updateParam]
  );

  const selectClass =
    "bg-zinc-800 border border-zinc-700 text-zinc-200 text-sm rounded-lg px-3 py-2.5 min-h-[44px] focus-visible:ring-2 focus-visible:ring-blue-500 outline-none touch-manipulation";
  const inputClass =
    "bg-zinc-800 border border-zinc-700 text-zinc-200 text-sm rounded-lg px-3 py-2.5 min-h-[44px] focus-visible:ring-2 focus-visible:ring-blue-500 outline-none touch-manipulation";

  const btnClass = (isActive: boolean) =>
    cn(
      "px-3 py-2 text-sm font-medium rounded-lg border transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-blue-500 outline-none touch-manipulation",
      isActive
        ? "bg-blue-600 border-blue-600 text-white"
        : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-blue-500 active:bg-zinc-700"
    );

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl px-4 py-4 space-y-3">
      {/* Row 1: Dropdowns & inputs */}
      <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-3">
        <select
          value={searchParams.get("source") || "all"}
          onChange={(e) => updateParam("source", e.target.value)}
          className={selectClass}
          aria-label="Source"
        >
          <option value="all">All Sources</option>
          <option value="idealista">Idealista</option>
          <option value="immobiliare">Immobiliare</option>
        </select>

        <select
          value={searchParams.get("sort") || "hybrid"}
          onChange={(e) => updateParam("sort", e.target.value)}
          className={selectClass}
          aria-label="Sort order"
        >
          <option value="hybrid">Best Score</option>
          <option value="price_asc">Cheapest</option>
          <option value="price_desc">Most Expensive</option>
          <option value="newest">Newest</option>
        </select>

        <input
          type="number"
          min="0"
          max="100"
          defaultValue={searchParams.get("minScore") || ""}
          placeholder="Min score…"
          onChange={(e) => debouncedUpdate("minScore", e.target.value)}
          className={cn(inputClass, "w-full sm:w-28")}
          aria-label="Minimum score"
        />

        <input
          type="number"
          min="0"
          step="50"
          defaultValue={searchParams.get("maxPrice") || ""}
          placeholder="Max price…"
          onChange={(e) => debouncedUpdate("maxPrice", e.target.value)}
          className={cn(inputClass, "w-full sm:w-28")}
          aria-label="Maximum price"
        />

        <label className="flex items-center gap-2.5 text-sm text-zinc-400 cursor-pointer select-none py-1 col-span-2 sm:col-span-1 min-h-[44px] touch-manipulation">
          <input
            type="checkbox"
            checked={searchParams.get("privato") === "1"}
            onChange={(e) =>
              updateParam("privato", e.target.checked ? "1" : "")
            }
            className="w-5 h-5 rounded accent-blue-500"
          />
          Privato only
        </label>
      </div>

      {/* Row 2: Budget pills */}
      <div className="space-y-3 sm:space-y-0 sm:flex sm:items-center sm:gap-x-6">
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none -mx-1 px-1" role="group" aria-label="Budget filter">
          <span className="text-xs text-zinc-500 uppercase tracking-wider mr-1 shrink-0">Budget</span>
          {[
            { value: "all", label: "All", bg: "" },
            { value: "tier1k", label: "≤€1k", bg: "bg-green-500" },
            { value: "tier1_1k", label: "1-1.1k", bg: "bg-lime-500" },
            { value: "tier1_2k", label: "1.1-1.2k", bg: "bg-yellow-500" },
            { value: "tier1_3k", label: "1.2-1.3k", bg: "bg-orange-500" },
            { value: "tier1_3k_plus", label: ">1.3k", bg: "bg-red-500" },
          ].map(({ value, label, bg }) => {
            const isActive = (searchParams.get("budget") || "all") === value;
            return (
              <button
                key={value}
                onClick={() => updateParam("budget", value)}
                className={cn(
                  "px-2.5 py-2 text-xs font-bold rounded-lg border transition-colors min-h-[40px] focus-visible:ring-2 focus-visible:ring-blue-500 outline-none shrink-0 touch-manipulation",
                  isActive
                    ? bg
                      ? `${bg} text-white border-transparent ring-2 ring-white/30`
                      : "bg-blue-600 text-white border-transparent ring-2 ring-white/30"
                    : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500 active:bg-zinc-700"
                )}
              >
                {bg && <span className={cn("inline-block w-2 h-2 rounded-full mr-1", bg)} />}
                {label}
              </button>
            );
          })}
        </div>

        <div className="hidden sm:block w-px h-6 bg-zinc-700 shrink-0" />

        {/* Time */}
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none -mx-1 px-1" role="group" aria-label="Time filter">
          <span className="text-xs text-zinc-500 uppercase tracking-wider mr-1 shrink-0">Time</span>
          {[
            { value: "", label: "All" },
            { value: "1", label: "1d" },
            { value: "3", label: "3d" },
            { value: "7", label: "7d" },
            { value: "14", label: "14d" },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => updateParam("days", value)}
              className={btnClass((searchParams.get("days") || "") === value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
