"""FreshnessScorer — listing age scoring."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from src.config import ScoringConfig
from src.models import ScoreResult


class FreshnessScorer:
    """Score listing freshness based on publication/modification date."""

    name = "freshness"
    description = "Listing age scoring"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        creation_date = listing.get("creation_date")
        last_modified = listing.get("last_modified")

        listing_date = _parse_date(
            last_modified
        ) or _parse_date(creation_date)

        if listing_date is None:
            return ScoreResult(
                score=50, details={"reason": "no_date"}
            )

        reference = date.today()
        days_old = (reference - listing_date).days

        if days_old < 0:
            days_old = 0

        return ScoreResult(
            score=_score_days(days_old),
            details={"days_old": days_old},
        )


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse an ISO date string, returning None on failure."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(
            date_str.replace("Z", "+00:00")
        )
        return dt.date()
    except (ValueError, TypeError):
        return None


def _score_days(days: int) -> int:
    """Map listing age in days to a 0-100 score."""
    if days == 0:
        return 100
    if days <= 3:
        return 90
    if days <= 7:
        return 70
    if days <= 14:
        return 50
    if days <= 28:
        return 30
    return 10
