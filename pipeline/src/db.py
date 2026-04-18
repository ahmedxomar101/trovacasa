"""Postgres database module for Milan apartment finder (via asyncpg + Supabase)."""

import os
from datetime import datetime, timezone

import asyncpg

from .dedup import generate_listing_id, normalize_address


async def create_pool() -> asyncpg.Pool:
    """Create a connection pool to Supabase Postgres."""
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        raise RuntimeError("SUPABASE_DB_URL not set in environment")
    return await asyncpg.create_pool(dsn, min_size=2, max_size=10)


async def listing_exists(pool: asyncpg.Pool, url: str) -> bool:
    """Check if a listing URL already exists in the database."""
    row = await pool.fetchval(
        "SELECT 1 FROM listings WHERE url = $1 LIMIT 1", url
    )
    return row is not None


# Columns in INSERT order (excluding id and seen_count which are handled specially)
_INSERT_COLUMNS = [
    "source", "url", "title", "address", "price", "rooms", "size_sqm",
    "floor", "description", "image_url", "lat", "lon", "metro_score",
    "nearest_station", "agent", "published_date", "scraped_at",
    "bathrooms", "property_type", "elevator", "balcony", "terrace",
    "energy_class", "num_photos", "has_video", "has_3d_tour",
    "creation_date", "last_modified", "price_per_sqm", "condo_fees",
    "condo_included", "available_from", "furnished", "contract_type",
    "deposit_months", "deposit_amount", "heating", "condition",
    "building_age", "agency_fee", "red_flags", "additional_costs",
    "heating_fuel", "air_conditioning", "orientation", "is_private",
    "commute_score", "quality_score", "scam_score", "livability_score",
    "freshness_score", "neighborhood_score", "neighborhood_name",
    "hybrid_score", "total_monthly_cost", "budget_status",
    "commute_minutes", "raw_data", "phone",
]

# Fields that only fill NULLs (don't overwrite existing data)
_ENRICHABLE_COALESCE = [
    "bathrooms", "property_type", "elevator", "balcony", "terrace",
    "energy_class", "num_photos", "has_video", "has_3d_tour",
    "creation_date", "last_modified", "price_per_sqm", "condition",
    "condo_fees", "heating", "heating_fuel", "building_age",
    "furnished", "air_conditioning", "orientation", "is_private",
    "agency_fee", "contract_type", "available_from", "deposit_months",
]

# Fields that always take the longer/newer value
_ENRICHABLE_OVERWRITE = ["raw_data", "description"]


async def save_listing(pool: asyncpg.Pool, listing: dict) -> bool:
    """Insert or update a listing. Returns True if new, False if already existed.

    Uses INSERT ... ON CONFLICT for atomic upsert with COALESCE semantics.
    """
    listing_id = generate_listing_id(
        listing.get("address", ""),
        listing.get("price", 0),
        listing.get("size_sqm", 0),
    )

    scraped_at = datetime.now(timezone.utc).isoformat()

    # Build the ON CONFLICT SET clauses
    conflict_sets = [
        "seen_count = listings.seen_count + 1",
        "scraped_at = EXCLUDED.scraped_at",
    ]
    for col in _ENRICHABLE_COALESCE:
        conflict_sets.append(f"{col} = COALESCE(listings.{col}, EXCLUDED.{col})")
    for col in _ENRICHABLE_OVERWRITE:
        conflict_sets.append(
            f"{col} = CASE WHEN LENGTH(COALESCE(listings.{col}, '')) < LENGTH(COALESCE(EXCLUDED.{col}, '')) "
            f"THEN EXCLUDED.{col} ELSE listings.{col} END"
        )

    # All columns including id
    all_cols = ["id"] + _INSERT_COLUMNS
    placeholders = ", ".join(f"${i+1}" for i in range(len(all_cols)))
    col_names = ", ".join(all_cols)
    on_conflict = ", ".join(conflict_sets)

    query = f"""
        INSERT INTO listings ({col_names}, seen_count)
        VALUES ({placeholders}, 1)
        ON CONFLICT (id) DO UPDATE SET {on_conflict}
        RETURNING (xmax = 0) AS is_new
    """

    values = [listing_id]
    for col in _INSERT_COLUMNS:
        val = listing.get(col)
        if col == "scraped_at":
            val = scraped_at
        values.append(val)

    row = await pool.fetchrow(query, *values)
    return row["is_new"]


async def get_listings(
    pool: asyncpg.Pool,
    min_score: int = 0,
    sort_by: str = "metro_score",
) -> list[dict]:
    """Retrieve listings with optional filters, sorted as requested."""
    allowed_sort_columns = {
        "metro_score", "price", "size_sqm", "published_date", "scraped_at",
        "rooms", "hybrid_score", "quality_score", "commute_score",
        "livability_score", "freshness_score", "neighborhood_score",
        "scam_score", "total_monthly_cost", "price_per_sqm",
    }
    if sort_by not in allowed_sort_columns:
        sort_by = "metro_score"

    _LIST_COLS = (
        "id, source, url, title, address, price, rooms, "
        "size_sqm, floor, image_url, lat, lon, metro_score, "
        "nearest_station, agent, published_date, scraped_at, "
        "bathrooms, property_type, elevator, balcony, terrace, "
        "energy_class, num_photos, condo_fees, condo_included, "
        "furnished, contract_type, hybrid_score, commute_score, "
        "quality_score, scam_score, livability_score, "
        "freshness_score, neighborhood_score, neighborhood_name, "
        "total_monthly_cost, budget_status, commute_minutes, "
        "phone, status, description"
    )
    query = f"""
        SELECT {_LIST_COLS} FROM listings
        WHERE COALESCE(metro_score, 0) >= $1
        ORDER BY {sort_by} DESC NULLS LAST
    """
    rows = await pool.fetch(query, min_score)
    return [dict(row) for row in rows]
