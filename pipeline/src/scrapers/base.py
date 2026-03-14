"""BaseScraper protocol for TrovaCasa scrapers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import ScraperConfig
from src.models import RawListing


@runtime_checkable
class BaseScraper(Protocol):
    """Every scraper must implement scrape() and normalize()."""

    name: str

    async def scrape(self, config: ScraperConfig) -> list[RawListing]:
        """Run the scraper and return normalized listings."""
        ...

    def normalize(self, raw_item: dict) -> RawListing | None:
        """Convert a single raw API response to a RawListing."""
        ...
