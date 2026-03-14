"""ScamScorer — scam risk detection (higher = safer)."""

from __future__ import annotations

import json

from src.config import ScoringConfig
from src.models import ScoreResult


class ScamScorer:
    """Score scam risk for a listing. Higher = safer."""

    name = "scam"
    description = "Scam risk detection (higher = safer)"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        num_photos = listing.get("num_photos")
        desc = listing.get("description") or ""
        desc_len = len(desc)
        price = listing.get("price")
        url = listing.get("url")
        red_flags = _parse_red_flags(
            listing.get("red_flags")
        )

        result = 100
        deductions: dict[str, int] = {}

        if num_photos is None or num_photos == 0:
            result -= 40
            deductions["no_photos"] = -40

        if desc_len < 50:
            result -= 20
            deductions["short_description"] = -20

        if price is not None and price < 400:
            result -= 30
            deductions["suspicious_price"] = -30

        if not url:
            result -= 20
            deductions["no_url"] = -20

        if red_flags:
            penalty = min(len(red_flags) * 10, 30)
            result -= penalty
            deductions["red_flags"] = -penalty

        return ScoreResult(
            score=max(result, 0),
            details={
                "deductions": deductions,
                "red_flags": red_flags,
            },
        )


def _parse_red_flags(raw) -> list[str]:
    """Parse red flags from various formats."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []
