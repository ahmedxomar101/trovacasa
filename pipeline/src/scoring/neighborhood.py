"""NeighborhoodScorer — zone tier multiplier from city data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.config import ScoringConfig
from src.models import ScoreResult


class NeighborhoodScorer:
    """Score neighborhood quality and provide a multiplier factor."""

    name = "neighborhood"
    description = "Neighborhood zone tier multiplier"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        neighborhoods = _load_neighborhoods(
            config.city_data_path
        )
        tiers = neighborhoods.get("tiers", {})
        default_tier = neighborhoods.get(
            "default_tier", "average"
        )

        # Build zone -> tier lookup
        zone_map = _build_zone_map(tiers)

        address = listing.get("address")
        macrozone = listing.get("neighborhood_name")

        matched_zone, tier = _match_zone(
            address, macrozone, zone_map, default_tier
        )

        tier_data = tiers.get(tier, {})
        tier_score = tier_data.get("score", 60)
        factor = tier_data.get("factor", 0.75)

        return ScoreResult(
            score=tier_score,
            details={
                "factor": factor,
                "zone": matched_zone,
                "tier": tier,
            },
        )


@lru_cache(maxsize=4)
def _load_neighborhoods(city_data_path: Path) -> dict:
    """Load neighborhoods.json from city data directory."""
    path = city_data_path / "neighborhoods.json"
    if not path.exists():
        return {"tiers": {}, "default_tier": "average"}
    return json.loads(path.read_text())


def _build_zone_map(tiers: dict) -> dict[str, str]:
    """Build a flat zone_name -> tier_name mapping."""
    zone_map: dict[str, str] = {}
    for tier_name, tier_data in tiers.items():
        for zone in tier_data.get("zones", []):
            zone_map[zone.lower()] = tier_name
    return zone_map


def _match_zone(
    address: str | None,
    macrozone: str | None,
    zone_map: dict[str, str],
    default_tier: str,
) -> tuple[str | None, str]:
    """Find the best matching zone via substring matching.

    Prefers longer zone names (more specific matches).
    Returns (matched_zone_name, tier).
    """
    search_text = ""
    if address:
        search_text += " " + address.lower()
    if macrozone:
        search_text += " " + macrozone.lower()

    if not search_text.strip():
        return None, default_tier

    # Sort by length descending for most-specific match
    sorted_zones = sorted(
        zone_map.keys(), key=len, reverse=True
    )

    for zone in sorted_zones:
        if zone in search_text:
            return zone, zone_map[zone]

    return None, default_tier
