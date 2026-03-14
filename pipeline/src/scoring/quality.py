"""QualityScorer — listing media and description richness."""

from __future__ import annotations

from src.config import ScoringConfig
from src.models import ScoreResult


class QualityScorer:
    """Score listing quality based on photos, video, and description."""

    name = "quality"
    description = "Listing media and description richness"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        num_photos = listing.get("num_photos") or 0
        has_video = listing.get("has_video") or False
        has_3d_tour = listing.get("has_3d_tour") or False
        desc = listing.get("description") or ""
        desc_len = len(desc)

        photo_score = _score_photos(num_photos)
        desc_score = _score_description(desc_len)
        bonus = (10 if has_video else 0) + (
            10 if has_3d_tour else 0
        )

        combined = round((photo_score + desc_score) / 2) + bonus
        final = min(combined, 100)

        return ScoreResult(
            score=final,
            details={
                "photo_score": photo_score,
                "desc_score": desc_score,
                "bonus": bonus,
                "num_photos": num_photos,
            },
        )


def _score_photos(num_photos: int) -> int:
    if num_photos >= 16:
        return 100
    if num_photos >= 6:
        return 60
    return 20


def _score_description(desc_len: int) -> int:
    if desc_len >= 300:
        return 80
    if desc_len >= 100:
        return 60
    return 20
