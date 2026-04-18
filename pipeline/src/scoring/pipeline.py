"""Scoring pipeline — compute all scores for listings in the DB."""

from __future__ import annotations

import asyncio
import time

import asyncpg
from dotenv import load_dotenv
from rich.console import Console

from src.config import ScoringConfig
from src.models import ScoreResult
from src.scoring.registry import (
    MULTIPLIER_SCORERS,
    get_active_scorers,
)

console = Console()


def compute_hybrid_score(
    listing: dict, config: ScoringConfig
) -> dict:
    """Compute all scores for a single listing.

    Returns a dict of DB column names to values.
    """
    active = get_active_scorers(config)

    # Run weighted scorers
    weighted_sum = 0.0
    score_columns: dict = {}

    for scorer, weight in active:
        result: ScoreResult = scorer.score(listing, config)
        col_name = f"{scorer.name}_score"
        score_columns[col_name] = result.score
        weighted_sum += result.score * weight

        # Stash commute-specific details
        if scorer.name == "commute":
            score_columns["commute_minutes"] = (
                result.details.get("commute_minutes")
            )

    # Run multiplier scorers (neighborhood)
    neighborhood_factor = 1.0
    for name, scorer in MULTIPLIER_SCORERS.items():
        result = scorer.score(listing, config)
        score_columns[f"{name}_score"] = result.score

        if name == "neighborhood":
            neighborhood_factor = result.details.get(
                "factor", 1.0
            )
            score_columns["neighborhood_name"] = (
                result.details.get("zone")
            )

    # Hybrid = weighted sum * neighborhood factor
    hybrid = round(weighted_sum * neighborhood_factor, 1)
    score_columns["hybrid_score"] = hybrid

    # Budget status
    score_columns["total_monthly_cost"] = (
        _compute_total_cost(listing)
    )
    score_columns["budget_status"] = _compute_budget_status(
        score_columns["total_monthly_cost"], config
    )

    return score_columns


def _compute_total_cost(listing: dict) -> float | None:
    price = listing.get("price")
    if price is None:
        return None
    total = float(price)
    condo_fees = listing.get("condo_fees")
    if condo_fees is not None:
        condo_included = listing.get("condo_included")
        if not condo_included:
            total += float(condo_fees)
    return total


def _compute_budget_status(
    total_cost: float | None, config: ScoringConfig
) -> str:
    if total_cost is None:
        return "unknown"
    max_rent = config.budget.max_rent if config.budget else 1100
    if total_cost <= max_rent - 100:
        return "under_budget"
    if total_cost <= max_rent:
        return "at_budget"
    if total_cost <= max_rent + 100:
        return "slightly_over"
    if total_cost <= max_rent + 200:
        return "over_budget"
    return "way_over"


async def score_all_listings(
    pool: asyncpg.Pool,
    config: ScoringConfig,
    force: bool = False,
):
    """Compute all scores for every listing in the database.

    Args:
        pool: asyncpg connection pool.
        config: Scoring configuration.
        force: If True, re-score all listings even if scored.
    """
    _SCORING_COLS = (
        "id, price, rooms, size_sqm, address, floor, "
        "description, lat, lon, metro_score, nearest_station, "
        "condo_fees, condo_included, elevator, balcony, "
        "terrace, furnished, energy_class, condition, "
        "heating, heating_fuel, air_conditioning, orientation, "
        "is_private, num_photos, has_video, has_3d_tour, "
        "creation_date, last_modified, price_per_sqm, "
        "red_flags, url, agent, neighborhood_name, "
        "commute_score, quality_score, scam_score, "
        "livability_score, freshness_score, "
        "neighborhood_score, hybrid_score, "
        "total_monthly_cost, budget_status, commute_minutes"
    )
    if force:
        rows = await pool.fetch(
            f"SELECT {_SCORING_COLS} FROM listings"
        )
    else:
        rows = await pool.fetch(
            f"SELECT {_SCORING_COLS} FROM listings "
            "WHERE hybrid_score IS NULL"
        )

    total = len(rows)

    if total == 0:
        console.print(
            "[green]All listings already scored.[/] "
            "Use --force to re-score."
        )
        return

    console.print(f"[bold]Scoring {total} listings...[/]")

    scored = 0
    skipped = 0
    errors = 0
    start_time = time.time()

    for row in rows:
        row = dict(row)
        listing_id = row["id"]

        try:
            scores = compute_hybrid_score(row, config)

            changed = any(
                row.get(col) != scores[col]
                for col in scores
            )
            if not changed:
                skipped += 1
                continue

            set_parts = []
            values = []
            for i, (col, val) in enumerate(
                scores.items(), 1
            ):
                set_parts.append(f"{col} = ${i}")
                values.append(val)
            values.append(listing_id)
            param_idx = len(scores) + 1

            await pool.execute(
                f"UPDATE listings SET {', '.join(set_parts)} "
                f"WHERE id = ${param_idx}",
                *values,
            )

            scored += 1
            done = scored + skipped + errors
            if done % 10 == 0:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                eta = (
                    (total - done) / rate if rate > 0 else 0
                )
                console.print(
                    f"  [dim]Progress: {done}/{total} "
                    f"| {rate:.1f} listings/s "
                    f"| elapsed {elapsed:.0f}s "
                    f"| ETA {eta:.0f}s[/]"
                )

        except Exception as e:
            errors += 1
            console.print(
                f"  [red]Error scoring {listing_id}: {e}[/]"
            )

    total_time = time.time() - start_time
    rate = total / total_time if total_time > 0 else 0

    console.print()
    console.print("[bold green]Scoring complete![/]")
    console.print(f"  Updated: {scored}")
    console.print(f"  Skipped: {skipped} (unchanged)")
    console.print(f"  Errors:  {errors}")
    console.print(f"  Total:   {total}")
    console.print(
        f"  Time:    {total_time:.1f}s "
        f"({rate:.1f} listings/s, "
        f"{total_time / max(total, 1) * 1000:.1f}ms "
        f"avg per listing)"
    )

    _print_distribution(pool)


async def _print_distribution(pool: asyncpg.Pool):
    """Print score distribution summary."""
    console.print()

    buckets = [
        ("80-100 (excellent)", 80, 100),
        ("60-79  (good)", 60, 79),
        ("40-59  (average)", 40, 59),
        ("20-39  (poor)", 20, 39),
        ("0-19   (bad)", 0, 19),
    ]
    console.print("[bold]Score distribution:[/]")
    for label, lo, hi in buckets:
        count = await pool.fetchval(
            "SELECT COUNT(*) FROM listings "
            "WHERE hybrid_score IS NOT NULL "
            "AND hybrid_score >= $1 "
            "AND hybrid_score <= $2",
            float(lo),
            float(hi + 0.999),
        )
        console.print(f"    {label}: {count} listings")

    console.print()
    console.print("[bold]Top 5:[/]")
    top5 = await pool.fetch(
        "SELECT price, address, hybrid_score FROM listings "
        "WHERE hybrid_score IS NOT NULL "
        "ORDER BY hybrid_score DESC LIMIT 5"
    )
    for i, row in enumerate(top5, 1):
        price_str = (
            f"\u20ac{int(row['price'])}/mo"
            if row["price"]
            else "\u20ac?/mo"
        )
        addr = (row["address"] or "Unknown")[:30].ljust(30)
        if row["address"] and len(row["address"]) > 30:
            addr = addr[:27] + "..."
        console.print(
            f"    {i}. {price_str} {addr} "
            f"\u2192 {row['hybrid_score']:.1f}"
        )

    console.print()
    avg = await pool.fetchrow(
        "SELECT AVG(hybrid_score) AS hybrid, "
        "AVG(commute_score) AS commute, "
        "AVG(livability_score) AS livability, "
        "AVG(scam_score) AS scam "
        "FROM listings WHERE hybrid_score IS NOT NULL"
    )
    console.print(
        f"  [bold]Averages:[/] hybrid={avg['hybrid']:.1f} "
        f"commute={avg['commute']:.1f} "
        f"livability={avg['livability']:.1f} "
        f"scam={avg['scam']:.1f}"
    )


async def main():
    """CLI entry point for batch scoring."""
    import argparse

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Score all apartment listings"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-score all listings",
    )
    args = parser.parse_args()

    from src.config import load_config
    from src.db import create_pool

    settings = load_config()
    pool = await create_pool()
    try:
        await score_all_listings(
            pool, settings.scoring, force=args.force
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
