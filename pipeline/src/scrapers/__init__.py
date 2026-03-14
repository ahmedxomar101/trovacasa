"""Scraper registry for TrovaCasa."""

from src.scrapers.base import BaseScraper
from src.scrapers.idealista import IdealistaScraper
from src.scrapers.immobiliare import ImmobiliareScraper

SCRAPER_REGISTRY: dict[str, BaseScraper] = {
    "idealista": IdealistaScraper(),
    "immobiliare": ImmobiliareScraper(),
}

__all__ = [
    "BaseScraper",
    "IdealistaScraper",
    "ImmobiliareScraper",
    "SCRAPER_REGISTRY",
]
