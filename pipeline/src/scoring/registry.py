"""Scorer registry — maps scorer names to instances."""

from __future__ import annotations

from src.config import ScoringConfig
from src.scoring.base import BaseScorer
from src.scoring.commute import CommuteScorer
from src.scoring.freshness import FreshnessScorer
from src.scoring.livability import LivabilityScorer
from src.scoring.metro import MetroScorer
from src.scoring.neighborhood import NeighborhoodScorer
from src.scoring.quality import QualityScorer
from src.scoring.scam import ScamScorer

WEIGHTED_SCORERS: dict[str, BaseScorer] = {
    "commute": CommuteScorer(),
    "metro": MetroScorer(),
    "livability": LivabilityScorer(),
    "quality": QualityScorer(),
    "scam": ScamScorer(),
    "freshness": FreshnessScorer(),
}

MULTIPLIER_SCORERS: dict[str, BaseScorer] = {
    "neighborhood": NeighborhoodScorer(),
}


def get_active_scorers(
    config: ScoringConfig,
) -> list[tuple[BaseScorer, float]]:
    """Return weighted scorers with non-zero weight."""
    active: list[tuple[BaseScorer, float]] = []
    for name, weight in config.weights.items():
        if weight > 0 and name in WEIGHTED_SCORERS:
            active.append((WEIGHTED_SCORERS[name], weight))
    return active
