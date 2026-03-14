"""Gallery fetch pipeline step — enrich idealista listings with full image galleries.

After scoring, this step fetches full property data (images, floor plans, videos,
structured features) for high-score idealista listings that don't have galleries yet.
"""

import json

import asyncpg
from rich.console import Console

# Defaults — can be overridden by settings
GALLERY_MIN_SCORE = 70
GALLERY_BATCH_SIZE = 20
from .scrapers.apify_idealista_gallery import fetch_idealista_galleries

console = Console()


async def fetch_galleries(pool: asyncpg.Pool) -> dict:
    """Fetch full galleries for high-score idealista listings.

    Returns stats dict with counts.
    """
    stats = {"candidates": 0, "fetched": 0, "updated": 0, "errors": 0}

    rows = await pool.fetch(
        """SELECT id, url, raw_data
           FROM listings
           WHERE source = 'idealista'
             AND status = 'active'
             AND hybrid_score >= $1
             AND gallery_fetched_at IS NULL
           ORDER BY hybrid_score DESC
           LIMIT $2""",
        float(GALLERY_MIN_SCORE),
        GALLERY_BATCH_SIZE,
    )

    stats["candidates"] = len(rows)
    if not rows:
        console.print("[green]No idealista listings need gallery fetch.[/green]")
        return stats

    urls = [r["url"] for r in rows]
    console.print(
        f"[bold]Gallery candidates: {len(urls)} idealista listings "
        f"(score >= {GALLERY_MIN_SCORE})[/bold]"
    )

    gallery_data = fetch_idealista_galleries(urls)
    stats["fetched"] = len(gallery_data)

    # Mark listings not returned by the actor (removed from idealista)
    # so we don't retry them every run
    for row in rows:
        if row["url"] not in gallery_data:
            await pool.execute(
                "UPDATE listings SET gallery_fetched_at = NOW() WHERE id = $1",
                row["id"],
            )
            stats["skipped"] = stats.get("skipped", 0) + 1

    if not gallery_data:
        console.print("[yellow]No gallery data returned from API actor.[/yellow]")
        return stats

    for row in rows:
        listing_url = row["url"]
        api_response = gallery_data.get(listing_url)
        if not api_response:
            continue

        try:
            new_raw = json.dumps(api_response, default=str, ensure_ascii=False)
            images = api_response.get("multimedia", {}).get("images", [])
            image_count = len(images)

            # Extract extra structured data from API response
            energy = _extract_energy(api_response)
            phone = _extract_phone(api_response)

            await pool.execute(
                """UPDATE listings
                   SET raw_data = $1,
                       num_photos = $2,
                       gallery_fetched_at = NOW(),
                       energy_class = COALESCE(energy_class, $3),
                       phone = COALESCE(phone, $4)
                   WHERE id = $5""",
                new_raw,
                image_count,
                energy,
                phone,
                row["id"],
            )
            stats["updated"] += 1
            console.print(
                f"  [green]\u2713[/green] {listing_url[-20:]} — "
                f"{image_count} images"
            )
        except Exception as e:
            stats["errors"] += 1
            console.print(f"  [red]\u2717 {listing_url[-20:]}: {e}[/red]")

    console.print(
        f"[bold]Gallery fetch done:[/bold] "
        f"{stats['updated']} updated, {stats['errors']} errors"
    )
    return stats


def _extract_energy(data: dict) -> str | None:
    """Extract energy class from API actor response."""
    cert = data.get("energyCertification", {})
    consumption = cert.get("energyConsumption", {})
    energy_type = consumption.get("type")
    if energy_type:
        return energy_type.upper()

    chars = data.get("moreCharacteristics", {})
    cert_type = chars.get("energyCertificationType")
    if cert_type:
        return cert_type.upper()

    return None


def _extract_phone(data: dict) -> str | None:
    """Extract phone number from API actor response."""
    contact = data.get("contactInfo", {})
    phone1 = contact.get("phone1", {})
    return phone1.get("formattedPhone")
