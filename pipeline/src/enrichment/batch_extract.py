"""Batch LLM extraction for apartment listings."""

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import asyncpg
from dotenv import load_dotenv
from rich.console import Console

from .llm_extract import extract_from_listing, extract_from_immobiliare, extract_from_description

console = Console()

# Max parallel LLM calls — default, overridden by settings
MAX_WORKERS = 15

# All fields the LLM can produce → DB column mapping.
_LLM_FIELDS = [
    "condo_fees",
    "condo_included",
    "available_from",
    "furnished",
    "contract_type",
    "deposit_months",
    "elevator",
    "balcony",
    "heating",
    "heating_fuel",
    "air_conditioning",
    "condition",
    "building_age",
    "energy_class",
    "orientation",
    "is_private",
    "agency_fee",
    "red_flags",
    "additional_costs",
    "is_last_floor",
]

# Mapping from LLM output keys to DB column names (where they differ).
_KEY_TO_COLUMN = {
    "condo_included_in_rent": "condo_included",
}

# Fields from LLM that update existing columns only when the DB value is NULL
_LLM_COALESCE_FIELDS = {
    "floor_level": "floor",
}


def _map_result_to_db(result: dict, existing_row: dict | None = None) -> dict:
    """Map LLM extraction result keys to database column names."""
    db_values = {}
    for key, value in result.items():
        # Handle coalesce fields (only fill if DB is NULL)
        if key in _LLM_COALESCE_FIELDS:
            col = _LLM_COALESCE_FIELDS[key]
            if existing_row and existing_row.get(col) is not None:
                continue  # DB already has a value, skip
            if value is not None:
                db_values[col] = str(value)
            continue

        col = _KEY_TO_COLUMN.get(key, key)
        if col in _LLM_FIELDS:
            if isinstance(value, (list, dict)):
                db_values[col] = json.dumps(value, ensure_ascii=False)
            else:
                db_values[col] = value
    return db_values


def _extract_one(raw_data: str | None, description: str, listing_meta: dict, existing_row: dict | None = None) -> tuple[dict, dict]:
    """Run LLM extraction for a single listing (runs in thread).

    Routes to source-specific extractor:
    - idealista with _details → build_clean_context (structured API data + description)
    - immobiliare → build_immobiliare_context (costs[], mainData[], analytics + description)
    - fallback → description-only
    """
    source = listing_meta.get("source", "")

    if raw_data:
        try:
            item = json.loads(raw_data)
            item.setdefault("price", listing_meta.get("price"))
            item.setdefault("rooms", listing_meta.get("rooms"))
            item.setdefault("size", listing_meta.get("size_sqm"))
            item.setdefault("address", listing_meta.get("address"))
            item.setdefault("description", description)

            if source == "idealista" and item.get("_details"):
                result = extract_from_listing(item, listing_meta=listing_meta)
                return listing_meta, _map_result_to_db(result, existing_row)
            elif source == "immobiliare":
                result = extract_from_immobiliare(item, listing_meta=listing_meta)
                return listing_meta, _map_result_to_db(result, existing_row)
        except (json.JSONDecodeError, Exception):
            pass

    # Fallback: description-only extraction
    result = extract_from_description(description, listing_meta=listing_meta)
    return listing_meta, _map_result_to_db(result, existing_row)


async def enrich_listings_with_llm(pool: asyncpg.Pool, force: bool = False):
    """Run LLM extraction on all listings, with parallel calls.

    Args:
        pool: asyncpg connection pool
        force: If True, re-process all listings even if already extracted
    """
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[bold red]Error:[/] OPENAI_API_KEY not set in environment.")
        return

    _META_FIELDS = "id, title, price, rooms, size_sqm, address, floor, agent, source, url, description, raw_data"

    if force:
        rows = await pool.fetch(
            f"SELECT {_META_FIELDS} FROM listings WHERE description IS NOT NULL AND description != ''"
        )
    else:
        rows = await pool.fetch(
            f"""SELECT {_META_FIELDS} FROM listings
               WHERE description IS NOT NULL
                 AND description != ''
                 AND condo_fees IS NULL
                 AND (red_flags IS NULL OR red_flags = '')"""
        )

    total = len(rows)

    if total == 0:
        console.print("[green]No listings to process.[/] All listings already enriched (use --force to re-process).")
        return

    # Count how many have _details
    has_details = 0
    for row in rows:
        rd = row["raw_data"]
        if rd:
            try:
                if "_details" in json.loads(rd):
                    has_details += 1
            except Exception:
                pass

    console.print(f"[bold]Processing {total} listings with LLM extraction ({MAX_WORKERS} parallel)...[/]")
    console.print(f"  [dim]{has_details}/{total} have fetchDetails data (full context), rest use description-only[/]")

    processed = 0
    skipped = 0
    errors = 0
    start_time = time.time()

    # Prepare tasks
    tasks = []
    for row in rows:
        row = dict(row)
        description = row["description"]
        if not description or not description.strip():
            skipped += 1
            continue
        listing_meta = {
            k: row.get(k) for k in
            ["id", "title", "price", "rooms", "size_sqm", "address", "floor", "agent", "source", "url"]
        }
        existing_row = {k: row.get(k) for k in _LLM_COALESCE_FIELDS.values()}
        tasks.append((row.get("raw_data"), description, listing_meta, existing_row))

    # Run in thread pool
    loop = asyncio.get_event_loop()
    semaphore = asyncio.Semaphore(MAX_WORKERS)

    abort = False

    async def process_one(raw_data, desc, meta, existing):
        nonlocal processed, errors, abort
        if abort:
            return
        async with semaphore:
            if abort:
                return
            try:
                listing_meta, db_values = await loop.run_in_executor(
                    executor, _extract_one, raw_data, desc, meta, existing
                )

                if not db_values:
                    price_tag = f"\u20ac{listing_meta.get('price', '?')}/mo"
                    addr_short = (listing_meta.get("address") or listing_meta.get("title") or "?")[:30]
                    console.print(f"  [yellow]\u26a0 {price_tag} {addr_short} | LLM returned empty result[/]")
                    return

                listing_id = listing_meta["id"]

                # Build parameterized UPDATE
                set_parts = []
                values = []
                for i, (col, val) in enumerate(db_values.items(), 1):
                    set_parts.append(f"{col} = ${i}")
                    values.append(val)
                values.append(listing_id)
                param_idx = len(db_values) + 1

                await pool.execute(
                    f"UPDATE listings SET {', '.join(set_parts)} WHERE id = ${param_idx}",
                    *values,
                )

                processed += 1

                # Per-listing extraction summary
                price_tag = f"\u20ac{listing_meta.get('price', '?')}/mo"
                addr_short = (listing_meta.get("address") or listing_meta.get("title") or "?")[:30]
                condo = db_values.get("condo_fees", "?")
                furnish = db_values.get("furnished", "?")
                contract = db_values.get("contract_type", "?")
                heating = db_values.get("heating", "?")
                flags = db_values.get("red_flags")
                flag_count = len(json.loads(flags)) if flags and flags.startswith("[") else (0 if not flags else 1)
                console.print(
                    f"  [dim]\u2713 {price_tag} {addr_short} | "
                    f"condo:{condo} furnish:{furnish} contract:{contract} "
                    f"heating:{heating} flags:{flag_count}[/]"
                )

                if processed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed
                    eta = (total - processed) / rate if rate > 0 else 0
                    console.print(
                        f"  [dim]Progress: {processed}/{total} "
                        f"| {rate:.1f} listings/s "
                        f"| elapsed {elapsed:.0f}s "
                        f"| ETA {eta:.0f}s[/]"
                    )

                    # Error rate monitoring
                    total_attempts = processed + errors
                    if total_attempts > 0:
                        error_rate = errors / total_attempts
                        if error_rate > 0.5 and total_attempts >= 20:
                            console.print(
                                f"  [bold red]\u2717 Error rate too high: {errors}/{total_attempts} "
                                f"({error_rate:.0%}) \u2014 aborting LLM extraction[/bold red]"
                            )
                            abort = True
                            return
                        elif error_rate > 0.3:
                            console.print(
                                f"  [bold yellow]\u26a0 High error rate: {errors}/{total_attempts} "
                                f"({error_rate:.0%}) \u2014 check OPENAI_API_KEY and model availability[/bold yellow]"
                            )

            except Exception as e:
                errors += 1
                console.print(f"  [red]Error: {e}[/]")

                # Error rate monitoring
                total_attempts = processed + errors
                if total_attempts > 0:
                    error_rate = errors / total_attempts
                    if error_rate > 0.5 and total_attempts >= 20:
                        console.print(
                            f"  [bold red]\u2717 Error rate too high: {errors}/{total_attempts} "
                            f"({error_rate:.0%}) \u2014 aborting LLM extraction[/bold red]"
                        )
                        abort = True
                        return
                    elif error_rate > 0.3:
                        console.print(
                            f"  [bold yellow]\u26a0 High error rate: {errors}/{total_attempts} "
                            f"({error_rate:.0%}) \u2014 check OPENAI_API_KEY and model availability[/bold yellow]"
                        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        await asyncio.gather(*[process_one(rd, desc, meta, existing) for rd, desc, meta, existing in tasks])

    total_time = time.time() - start_time
    final_rate = processed / total_time if total_time > 0 else 0

    console.print()
    console.print("[bold green]LLM extraction complete![/]")
    console.print(f"  Processed: {processed}")
    console.print(f"  Skipped:   {skipped}")
    console.print(f"  Errors:    {errors}")
    console.print(f"  Total:     {total}")
    console.print(f"  Time:      {total_time:.1f}s ({final_rate:.2f} listings/s, {total_time/max(processed,1):.1f}s avg per listing)")


async def main():
    """CLI entry point for batch LLM extraction."""
    import argparse

    load_dotenv()

    parser = argparse.ArgumentParser(description="Run LLM extraction on apartment listings")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process all listings, even those already extracted",
    )
    args = parser.parse_args()

    from ..db import create_pool
    pool = await create_pool()
    try:
        await enrich_listings_with_llm(pool, force=args.force)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
