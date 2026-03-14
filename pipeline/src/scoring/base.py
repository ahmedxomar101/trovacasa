"""BaseScorer protocol for scoring dimensions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.config import ScoringConfig
from src.models import ScoreResult


@runtime_checkable
class BaseScorer(Protocol):
    """Protocol that all scorer dimensions must satisfy."""

    name: str
    description: str

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult: ...
