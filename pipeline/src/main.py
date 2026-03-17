"""TrovaCasa — main orchestrator.

Stages that can run independently:
  1. scrape    — fetch from Apify actors, store raw data in DB
  2. enrich    — LLM extraction from descriptions
  3. score     — compute all scores + generate report
  4. gallery   — fetch full image galleries for high-score listings
  5. notify    — send Telegram alerts for new listings
  6. validate  — validate config.yaml and environment

Usage:
  python -m src.main scrape          # scrape only
  python -m src.main enrich          # LLM enrich only
  python -m src.main score           # score + report only
  python -m src.main gallery         # gallery fetch only
  python -m src.main notify          # Telegram notifications only
  python -m src.main validate        # validate config
  python -m src.main all             # full pipeline
"""

import asyncio
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from rich.console import Console

from .config import load_config, ConfigError
from .scrapers import SCRAPER_REGISTRY
from .scoring.transit import load_city_transit, find_nearest_stations
from .db import create_pool, save_listing, get_listings, listing_exists
from .scoring.pipeline import score_all_listings
from .enrichment.batch_extract import enrich_listings_with_llm
from .report import generate_report
from .run_tracker import RunTracker
from .gallery import fetch_galleries
from .telegram.notify import send_new_listings
from .telegram.callback_handler import run_callback_handler

# ── Logging setup: terminal + persistent log file ────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
_log_filename = f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
_log_path = os.path.join(LOG_DIR, _log_filename)
_log_file = open(_log_path, "w", encoding="utf-8")

console = Console(record=True)
_file_console = Console(file=_log_file, width=120, force_terminal=False, no_color=True)

# Monkey-patch console.log and console.print to write to both terminal and file
_orig_log = console.log
_orig_print = console.print
_orig_rule = console.rule

def _tee_log(*args, **kwargs):
    _orig_log(*args, **kwargs)
    _file_console.log(*args, **kwargs)
    _log_file.flush()

def _tee_print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    _file_console.print(*args, **kwargs)
    _log_file.flush()

def _tee_rule(*args, **kwargs):
    _orig_rule(*args, **kwargs)
    _file_console.rule(*args, **kwargs)
    _log_file.flush()

console.log = _tee_log
console.print = _tee_print
console.rule = _tee_rule


def check_env() -> dict[str, bool]:
    """Check which API keys are set and log status. Returns {"apify": bool, "openai": bool, "supabase": bool}."""
    keys = {
        "apify": ("APIFY_API_TOKEN", os.environ.get("APIFY_API_TOKEN", "").strip()),
        "openai": ("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "").strip()),
        "supabase": ("SUPABASE_DB_URL", os.environ.get("SUPABASE_DB_URL", "").strip()),
    }
    result = {}
    for name, (env_var, value) in keys.items():
        if value:
            console.log(f"[green]\u2713 {env_var} set[/green]")
            result[name] = True
        else:
            console.log(f"[red]\u2717 {env_var} not set[/red]")
            result[name] = False
    return result


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


async def enrich_with_metro(listing: dict, city: str) -> dict:
    """Add nearest station info to a listing using GPS coordinates."""
    lat = listing.get("lat")
    lon = listing.get("lon")

    if lat and lon:
        try:
            transit_data = load_city_transit(city)
            stations = find_nearest_stations(
                lat, lon, transit_data["stations"], max_distance_m=1000
            )
            if stations:
                ns = stations[0]
                listing["nearest_station"] = (
                    f"{ns['name']} ({', '.join(ns['lines'])}) - {ns['distance_m']:.0f}m"
                )
            else:
                listing["nearest_station"] = None
        except Exception as e:
            console.log(f"[red]Metro enrichment error: {e}[/red]")
            listing["nearest_station"] = None
    else:
        listing["nearest_station"] = None

    return listing


async def store_listings(pool, listings: list[dict], city: str = "milan") -> dict:
    """Store scraped listings in DB with nearest station info."""
    stats = {"total": len(listings), "new": 0, "duplicate": 0, "updated": 0, "errors": 0}
    new_prices = []
    new_sizes = []

    for i, listing in enumerate(listings, 1):
        try:
            listing = await enrich_with_metro(listing, city)
            is_new = await save_listing(pool, listing)

            if is_new:
                stats["new"] += 1
                console.log(
                    f"[green]NEW:[/green] {listing.get('title', 'N/A')[:55]} "
                    f"| \u20ac{listing.get('price', '?')}/mo "
                    f"| {listing.get('size_sqm', '?')}m\u00b2"
                )
                if listing.get("price") is not None:
                    new_prices.append(listing["price"])
                if listing.get("size_sqm") is not None:
                    new_sizes.append(listing["size_sqm"])
            else:
                stats["updated"] += 1

        except Exception as e:
            stats["errors"] += 1
            console.log(f"[red]Error storing: {e}[/red]")

        if i % 25 == 0 or i == stats["total"]:
            console.log(
                f"[dim]Progress: {i}/{stats['total']} | "
                f"{stats['new']} new, {stats['updated']} updated, "
                f"{stats['errors']} errors[/dim]"
            )

    if new_prices or new_sizes:
        price_range = f"\u20ac{min(new_prices)}-{max(new_prices)}" if new_prices else "n/a"
        size_range = f"{min(new_sizes)}-{max(new_sizes)}m\u00b2" if new_sizes else "n/a"
        console.log(
            f"[dim]New listings summary: {stats['new']} added, "
            f"price {price_range}, size {size_range}[/dim]"
        )

    return stats


# ── Stage 1: Scrape ──────────────────────────────────────────────────────────

async def run_scrape(pool, settings, source: str | None = None) -> None:
    """Scrape listings using configured scrapers and store in DB.

    Args:
        pool: asyncpg connection pool.
        settings: Validated Settings instance.
        source: Specific scraper name, or None (all enabled).
    """
    tracker = RunTracker()
    run_id = await tracker.start(pool, "scrape")

    try:
        t0 = time.monotonic()
        console.rule("[bold magenta]Stage 1: Scrape[/bold magenta]")
        console.log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        all_stats = {}

        for scraper_name, scraper_config in settings.scrapers.items():
            if not scraper_config.enabled:
                continue
            if source is not None and scraper_name != source:
                continue

            scraper = SCRAPER_REGISTRY.get(scraper_name)
            if not scraper:
                console.log(f"[yellow]Unknown scraper: {scraper_name} (not in registry)[/yellow]")
                continue

            console.rule(f"[bold]{scraper_name} (Apify)[/bold]")
            try:
                listings = await scraper.scrape(scraper_config)
                # Convert RawListing models to dicts for DB storage
                listing_dicts = []
                for raw_listing in listings:
                    d = raw_listing.model_dump()
                    d["raw_data"] = __import__("json").dumps(d.get("raw_data", {}), default=str, ensure_ascii=False)
                    listing_dicts.append(d)

                stats = await store_listings(pool, listing_dicts, city=settings.city)
                all_stats[scraper_name] = stats
                console.log(
                    f"[bold]{scraper_name}:[/bold] {stats['total']} scraped, "
                    f"{stats['new']} new, {stats['updated']} updated, {stats['errors']} errors"
                )
            except Exception as e:
                console.log(f"[bold red]{scraper_name} failed: {e}[/bold red]")
                all_stats[scraper_name] = {"error": str(e)}

        # DB summary after scrape
        elapsed = time.monotonic() - t0
        console.rule("[bold green]Scrape Complete[/bold green]")
        console.log(f"Elapsed: {elapsed:.1f}s")
        row = await pool.fetchrow("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN source = 'idealista' THEN 1 ELSE 0 END) AS idealista,
                SUM(CASE WHEN source = 'immobiliare' THEN 1 ELSE 0 END) AS immobiliare,
                SUM(CASE WHEN lat IS NOT NULL AND lon IS NOT NULL THEN 1 ELSE 0 END) AS has_gps,
                SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) AS has_desc
            FROM listings
        """)
        console.log(
            f"DB totals: [bold]{row['total']}[/bold] listings "
            f"([cyan]{row['idealista']}[/cyan] idealista, [cyan]{row['immobiliare']}[/cyan] immobiliare)"
        )
        console.log(f"  GPS coords: {row['has_gps']}/{row['total']} | Descriptions: {row['has_desc']}/{row['total']}")

        # Gone detection: mark active listings not seen for 3+ days
        gone_result = await pool.execute("""
            UPDATE listings SET status = 'gone', status_updated_at = NOW()
            WHERE status = 'active'
              AND scraped_at < (NOW() - INTERVAL '3 days')::text
        """)
        gone_count = int(gone_result.split()[-1]) if gone_result else 0
        if gone_count and gone_count > 0:
            console.log(f"[yellow]Marked {gone_count} listings as gone (not seen in 3+ days)[/yellow]")
            all_stats["gone"] = gone_count

        await tracker.complete(pool, run_id, all_stats)
    except Exception as e:
        await tracker.fail(pool, run_id, str(e))
        raise


# ── Stage 2: Enrich ──────────────────────────────────────────────────────────

async def run_enrich(pool, force: bool = False) -> None:
    """Run LLM extraction on descriptions. Reads from DB, writes back to DB."""
    tracker = RunTracker()
    run_id = await tracker.start(pool, "enrich")

    try:
        t0 = time.monotonic()
        console.rule("[bold magenta]Stage 2: LLM Enrichment[/bold magenta]")
        console.log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Pre-enrichment stats
        row = await pool.fetchrow("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) AS has_desc,
                SUM(CASE WHEN raw_data LIKE '%_details%' THEN 1 ELSE 0 END) AS has_details,
                SUM(CASE WHEN condo_fees IS NOT NULL THEN 1 ELSE 0 END) AS has_condo,
                SUM(CASE WHEN elevator IS NOT NULL THEN 1 ELSE 0 END) AS has_elevator,
                SUM(CASE WHEN furnished IS NOT NULL THEN 1 ELSE 0 END) AS has_furnished,
                SUM(CASE WHEN contract_type IS NOT NULL THEN 1 ELSE 0 END) AS has_contract,
                SUM(CASE WHEN heating IS NOT NULL THEN 1 ELSE 0 END) AS has_heating,
                SUM(CASE WHEN deposit_months IS NOT NULL THEN 1 ELSE 0 END) AS has_deposit
            FROM listings
        """)
        console.log(
            f"[bold]Pre-enrichment:[/bold] {row['total']} listings, "
            f"{row['has_desc']} with description, {row['has_details']} with raw_data _details"
        )
        console.log(
            f"  Populated \u2014 condo_fees: {row['has_condo']}, elevator: {row['has_elevator']}, "
            f"furnished: {row['has_furnished']}, contract_type: {row['has_contract']}, "
            f"heating: {row['has_heating']}, deposit: {row['has_deposit']}"
        )

        await enrich_listings_with_llm(pool, force=force)

        # Post-enrichment stats
        post = await pool.fetchrow("""
            SELECT
                SUM(CASE WHEN condo_fees IS NOT NULL THEN 1 ELSE 0 END) AS condo,
                SUM(CASE WHEN elevator IS NOT NULL THEN 1 ELSE 0 END) AS elevator,
                SUM(CASE WHEN furnished IS NOT NULL THEN 1 ELSE 0 END) AS furnished,
                SUM(CASE WHEN contract_type IS NOT NULL THEN 1 ELSE 0 END) AS contract,
                SUM(CASE WHEN heating IS NOT NULL THEN 1 ELSE 0 END) AS heating,
                SUM(CASE WHEN deposit_months IS NOT NULL THEN 1 ELSE 0 END) AS deposit,
                SUM(CASE WHEN red_flags IS NOT NULL THEN 1 ELSE 0 END) AS flags,
                SUM(CASE WHEN condition IS NOT NULL THEN 1 ELSE 0 END) AS condition
            FROM listings
        """)
        elapsed = time.monotonic() - t0
        console.rule("[bold green]Enrichment Complete[/bold green]")
        console.log(f"Elapsed: {elapsed:.1f}s")
        console.log(
            f"[bold]Post-enrichment:[/bold] "
            f"condo_fees: {row['has_condo']}->{post['condo']}, "
            f"elevator: {row['has_elevator']}->{post['elevator']}, "
            f"furnished: {row['has_furnished']}->{post['furnished']}, "
            f"contract: {row['has_contract']}->{post['contract']}, "
            f"heating: {row['has_heating']}->{post['heating']}, "
            f"deposit: {row['has_deposit']}->{post['deposit']}, "
            f"red_flags: {post['flags']}, "
            f"condition: {post['condition']}"
        )

        await tracker.complete(pool, run_id, {"elapsed": f"{elapsed:.1f}s"})
    except Exception as e:
        await tracker.fail(pool, run_id, str(e))
        raise


# ── Stage 3: Score + Report ──────────────────────────────────────────────────

async def run_score(pool, settings=None, force: bool = True) -> None:
    """Compute all scores and generate report. Reads from DB, writes back to DB."""
    tracker = RunTracker()
    run_id = await tracker.start(pool, "score")

    if settings is None:
        settings = load_config()

    try:
        console.log("[dim]Score stage \u2014 no external API keys needed.[/dim]")

        t0 = time.monotonic()
        console.rule("[bold magenta]Stage 3: Scoring + Report[/bold magenta]")
        console.log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        await score_all_listings(pool, config=settings.scoring, force=force)

        # Generate HTML report
        await generate_report(pool)

        # Export CSV
        all_listings = await get_listings(pool, min_score=0, sort_by="hybrid_score")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUTPUT_DIR, f"listings_{timestamp}.csv")
        export_csv(all_listings, csv_path)

        elapsed = time.monotonic() - t0
        console.rule("[bold green]Done[/bold green]")
        console.log(f"Elapsed: {elapsed:.1f}s")
        console.log(f"Total: {len(all_listings)} listings")
        console.log(f"CSV: {csv_path}")
        console.log(f"Report: output/report.html")

        await tracker.complete(pool, run_id, {"listings": len(all_listings), "elapsed": f"{elapsed:.1f}s"})
    except Exception as e:
        await tracker.fail(pool, run_id, str(e))
        raise


# ── Full pipeline ────────────────────────────────────────────────────────────

async def run_notify(pool) -> None:
    """Send Telegram notifications for new high-score listings."""
    console.rule("[bold magenta]Stage 4: Telegram Notifications[/bold magenta]")
    console.log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await send_new_listings(pool)


async def run_bot(pool) -> None:
    """Run the Telegram callback handler (long-running poll)."""
    console.rule("[bold magenta]Telegram Bot (callback handler)[/bold magenta]")
    await run_callback_handler(pool)


async def run_gallery(pool) -> None:
    """Fetch full image galleries for high-score idealista listings."""
    tracker = RunTracker()
    run_id = await tracker.start(pool, "gallery")

    try:
        t0 = time.monotonic()
        console.rule("[bold magenta]Stage 4: Gallery Fetch[/bold magenta]")
        console.log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        stats = await fetch_galleries(pool)

        elapsed = time.monotonic() - t0
        console.rule("[bold green]Gallery Fetch Complete[/bold green]")
        console.log(f"Elapsed: {elapsed:.1f}s | {stats}")

        await tracker.complete(pool, run_id, stats)
    except Exception as e:
        await tracker.fail(pool, run_id, str(e))
        raise


async def run_all(pool, settings, source: str | None = None, skip_notify: bool = False) -> None:
    """Full pipeline: scrape → enrich → score → gallery → notify."""
    await run_scrape(pool, settings, source=source)
    await run_enrich(pool)
    await run_score(pool, settings=settings)
    # Fetch galleries for high-score listings
    if os.environ.get("APIFY_API_TOKEN"):
        await run_gallery(pool)
    # Notify only if Telegram is configured (and not skipped)
    if not skip_notify and settings.telegram.enabled and os.environ.get("TELEGRAM_BOT_TOKEN"):
        await run_notify(pool)


async def run_validate(settings) -> bool:
    """Validate config.yaml and environment."""
    checks = []

    # 1. Config loaded successfully
    checks.append(("Config YAML", True, "Parsed and validated"))

    # 2. Weights sum
    total = sum(settings.scoring.weights.values())
    checks.append(("Scoring weights sum", abs(total - 1.0) < 0.001, f"Sum: {total:.3f}"))

    # 3. City data
    city_path = settings.scoring.city_data_path
    metro_exists = (city_path / "metro.json").exists()
    neighborhoods_exists = (city_path / "neighborhoods.json").exists()
    checks.append(("City data (metro.json)", metro_exists, str(city_path / "metro.json")))
    checks.append(("City data (neighborhoods.json)", neighborhoods_exists, str(city_path / "neighborhoods.json")))

    # 4. Metro graph integrity
    if metro_exists:
        try:
            from .scoring.transit import load_city_transit, build_metro_graph
            data = load_city_transit(settings.city)
            graph = build_metro_graph(data)
            station_count = len(data["stations"])
            checks.append(("Metro graph", station_count > 0, f"{station_count} stations loaded"))
        except Exception as e:
            checks.append(("Metro graph", False, str(e)))

    # 5. Env vars
    for var in ["APIFY_API_TOKEN", "OPENAI_API_KEY", "SUPABASE_DB_URL"]:
        val = os.environ.get(var, "").strip()
        checks.append((f"Env: {var}", bool(val), "Set" if val else "Missing"))

    # 6. Scraper registry
    for name in settings.scrapers:
        cfg = settings.scrapers[name]
        if cfg.enabled:
            in_registry = name in SCRAPER_REGISTRY
            checks.append((f"Scraper: {name}", in_registry, "Registered" if in_registry else "Not in registry"))

    # Print results
    all_passed = all(ok for _, ok, _ in checks)
    for name, ok, detail in checks:
        status = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"  {status} {name}: {detail}")

    if all_passed:
        console.print("\n[bold green]All checks passed.[/bold green]")
    else:
        console.print("\n[bold red]Some checks failed. Fix the issues above.[/bold red]")

    return all_passed


# ── CSV export ───────────────────────────────────────────────────────────────

def export_csv(listings: list[dict], filepath: str) -> None:
    """Export listings to CSV."""
    if not listings:
        return

    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "source", "price", "rooms", "size_sqm", "agent", "title",
        "address", "floor", "metro_score", "nearest_station",
        "published_date", "url",
        "hybrid_score", "commute_score", "commute_minutes",
        "livability_score", "quality_score", "scam_score",
        "freshness_score", "neighborhood_score", "neighborhood_name",
        "budget_status", "total_monthly_cost",
        "condo_fees", "furnished", "contract_type", "deposit_months",
        "heating", "heating_fuel", "air_conditioning", "energy_class",
        "condition", "elevator", "balcony", "orientation",
        "available_from", "is_private", "red_flags", "additional_costs",
        "lat", "lon",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(listings)

    console.log(f"[green]CSV exported to {filepath}[/green]")


# ── CLI ──────────────────────────────────────────────────────────────────────

async def _run(cmd: str, force: bool = False, source: str | None = None, skip_db: bool = False, skip_notify: bool = False) -> None:
    """Load config, create pool, and run the requested stage."""

    # Load config
    try:
        settings = load_config()
    except ConfigError as e:
        console.log(f"[bold red]Config error: {e}[/bold red]")
        return

    # Validate-only path (no DB needed)
    if cmd == "validate":
        await run_validate(settings)
        return

    env = check_env()

    if not env["supabase"]:
        console.log("[bold red]SUPABASE_DB_URL is required \u2014 aborting.[/bold red]")
        return

    if cmd == "scrape" and not env["apify"]:
        console.log("[bold red]APIFY_API_TOKEN is required for scrape stage \u2014 aborting.[/bold red]")
        return

    if cmd == "enrich" and not env["openai"]:
        console.log("[bold red]OPENAI_API_KEY is required for enrich stage \u2014 aborting.[/bold red]")
        return

    if cmd == "all":
        if not env["apify"]:
            console.log("[bold red]APIFY_API_TOKEN is required for full pipeline \u2014 aborting.[/bold red]")
            return
        if not env["openai"]:
            console.log("[bold red]OPENAI_API_KEY is required for full pipeline \u2014 aborting.[/bold red]")
            return

    pool = await create_pool()
    try:
        if cmd == "scrape":
            await run_scrape(pool, settings, source=source)
        elif cmd == "enrich":
            await run_enrich(pool, force=force)
        elif cmd == "score":
            await run_score(pool, settings=settings, force=force)
        elif cmd == "notify":
            await run_notify(pool)
        elif cmd == "gallery":
            await run_gallery(pool)
        elif cmd == "bot":
            await run_bot(pool)
        elif cmd == "all":
            await run_all(pool, settings, source=source, skip_notify=skip_notify)
    finally:
        await pool.close()


def _parse_args() -> tuple[str, bool, str | None, bool, bool]:
    """Parse CLI arguments. Returns (cmd, force, source, skip_db, skip_notify)."""
    cmd = "all"
    force = False
    source = None
    skip_db = False
    skip_notify = False

    args = sys.argv[1:]
    for arg in args:
        if arg == "--force":
            force = True
        elif arg == "--skip-db":
            skip_db = True
        elif arg == "--skip-notify":
            skip_notify = True
        elif arg.startswith("--source="):
            source = arg.split("=", 1)[1]
        elif not arg.startswith("--"):
            cmd = arg

    return cmd, force, source, skip_db, skip_notify


if __name__ == "__main__":
    cmd, force, source, skip_db, skip_notify = _parse_args()

    console.log(f"[bold]Pipeline log:[/bold] {_log_path}")

    try:
        asyncio.run(_run(cmd, force=force, source=source, skip_db=skip_db, skip_notify=skip_notify))
    except Exception as e:
        console.log(f"[bold red]Pipeline failed: {e}[/bold red]")
        raise
    finally:
        console.log(f"[bold]Full log saved to:[/bold] {_log_path}")
        _log_file.close()
