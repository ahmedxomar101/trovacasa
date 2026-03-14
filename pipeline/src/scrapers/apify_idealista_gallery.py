"""Fetch full image galleries for idealista listings via dz_omar/idealista-scraper-api.

This actor takes individual property URLs and returns full multimedia data
including HD images, floor plans, videos, and rich structured details.
Used selectively for high-score listings to keep costs low.
"""

import json
import os
import time

from apify_client import ApifyClient
from rich.console import Console

from ..config import (
    IDEALISTA_API_ACTOR_ID,
    APIFY_POLL_INTERVAL,
    APIFY_TIMEOUT_IDEALISTA_API,
)

console = Console()

TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def fetch_idealista_galleries(
    urls: list[str],
    api_token: str | None = None,
) -> dict[str, dict]:
    """Fetch full property data for a list of idealista URLs.

    Args:
        urls: List of idealista property URLs.
        api_token: Apify API token (defaults to env var).

    Returns:
        Dict mapping original URL to the full API actor response.
    """
    token = api_token or os.environ.get("APIFY_API_TOKEN", "").strip()
    if not token:
        console.print("[red]APIFY_API_TOKEN not set — skipping gallery fetch[/red]")
        return {}

    if not urls:
        return {}

    client = ApifyClient(token)

    run_input = {
        "Property_urls": [{"url": u} for u in urls],
    }

    console.print(
        f"[bold]Fetching galleries for {len(urls)} idealista listings...[/bold]"
    )

    try:
        run = client.actor(IDEALISTA_API_ACTOR_ID).start(
            run_input=run_input,
            timeout_secs=APIFY_TIMEOUT_IDEALISTA_API,
        )
        run_id = run["id"]
        console.print(f"[dim]Actor run started: {run_id}[/dim]")

        t0 = time.monotonic()
        while True:
            run = client.run(run_id).get()
            status = run.get("status", "UNKNOWN")
            elapsed = time.monotonic() - t0

            if status in TERMINAL_STATUSES:
                console.print(
                    f"[dim]Run {status} in {elapsed:.0f}s[/dim]"
                )
                break

            if elapsed > APIFY_TIMEOUT_IDEALISTA_API:
                console.print("[red]Gallery fetch timed out[/red]")
                return {}

            time.sleep(APIFY_POLL_INTERVAL)

        if status != "SUCCEEDED":
            console.print(f"[red]Gallery fetch failed: {status}[/red]")
            return {}

        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )

        result = {}
        for item in items:
            original_url = item.get("originalUrl", "")
            if original_url:
                result[original_url] = item

        console.print(
            f"[green]Fetched {len(result)} galleries successfully[/green]"
        )
        return result

    except Exception as e:
        console.print(f"[red]Gallery fetch error: {e}[/red]")
        return {}
