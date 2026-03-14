"""Tests for all scorer classes and the hybrid scoring pipeline."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.config import (
    BudgetConfig,
    CommuteConfig,
    Coordinates,
    ScoringConfig,
)
from src.models import ScoreResult
from src.scoring.commute import CommuteScorer
from src.scoring.freshness import FreshnessScorer
from src.scoring.livability import LivabilityScorer
from src.scoring.metro import MetroScorer
from src.scoring.neighborhood import NeighborhoodScorer
from src.scoring.pipeline import compute_hybrid_score
from src.scoring.quality import QualityScorer
from src.scoring.scam import ScamScorer

_CITY_DATA = Path(__file__).parents[1] / "data" / "cities" / "milan"


def _make_config(**kwargs) -> ScoringConfig:
    defaults = {
        "weights": {
            "commute": 0.30,
            "metro": 0.20,
            "livability": 0.15,
            "freshness": 0.15,
            "scam": 0.10,
            "quality": 0.10,
        },
        "commute": CommuteConfig(
            destination=Coordinates(
                lat=45.4565, lon=9.1525, name="Tre Torri"
            ),
            preferred_line="M5",
        ),
        "city_data_path": _CITY_DATA,
        "budget": BudgetConfig(max_rent=1100),
    }
    defaults.update(kwargs)
    return ScoringConfig(**defaults)


# ---------------------------------------------------------------
# CommuteScorer
# ---------------------------------------------------------------


class TestCommuteScorer:
    scorer = CommuteScorer()
    config = _make_config()

    def test_near_destination(self):
        # Near Tre Torri (M5 line area)
        listing = {"lat": 45.4580, "lon": 9.1550}
        result = self.scorer.score(listing, self.config)
        assert isinstance(result, ScoreResult)
        assert result.score >= 80
        assert "commute_minutes" in result.details

    def test_no_coordinates(self):
        listing = {"lat": None, "lon": None}
        result = self.scorer.score(listing, self.config)
        assert result.score == 50

    def test_missing_coordinates(self):
        listing = {"address": "Via Roma 1"}
        result = self.scorer.score(listing, self.config)
        assert result.score == 50

    def test_far_location(self):
        # Sesto Primo Maggio (far north on M1)
        listing = {"lat": 45.5360, "lon": 9.2351}
        result = self.scorer.score(listing, self.config)
        assert result.score < 80


# ---------------------------------------------------------------
# MetroScorer
# ---------------------------------------------------------------


class TestMetroScorer:
    scorer = MetroScorer()
    config = _make_config()

    def test_near_preferred_line_station(self):
        # Near Zara (M3+M5 interchange)
        listing = {"lat": 45.4927, "lon": 9.1929}
        result = self.scorer.score(listing, self.config)
        assert isinstance(result, ScoreResult)
        assert result.score >= 80

    def test_no_coordinates(self):
        listing = {}
        result = self.scorer.score(listing, self.config)
        assert result.score == 0

    def test_near_non_preferred_station(self):
        # Near Corvetto (M3 only, no M5)
        listing = {"lat": 45.4404, "lon": 9.2234}
        result = self.scorer.score(listing, self.config)
        assert result.score > 0
        assert result.score < 90


# ---------------------------------------------------------------
# LivabilityScorer
# ---------------------------------------------------------------


class TestLivabilityScorer:
    scorer = LivabilityScorer()
    config = _make_config()

    def test_good_apartment(self):
        listing = {
            "elevator": True,
            "floor": "4",
            "balcony": True,
            "furnished": "full",
            "energy_class": "B",
            "condition": "renovated",
            "heating": "autonomous",
        }
        result = self.scorer.score(listing, self.config)
        assert isinstance(result, ScoreResult)
        assert 70 <= result.score <= 100
        assert "elevator" in result.details

    def test_poor_apartment(self):
        listing = {
            "elevator": False,
            "floor": "5",
            "balcony": False,
            "furnished": "no",
            "energy_class": "G",
            "condition": "needs-work",
            "heating": None,
        }
        result = self.scorer.score(listing, self.config)
        assert result.score < 50

    def test_with_overrides(self):
        config = _make_config(
            overrides={"livability": {"elevator": 100}}
        )
        listing = {"elevator": False, "floor": "5"}
        result = self.scorer.score(listing, config)
        # Elevator override to 100 means overall is higher
        assert result.details["elevator"] == 100

    def test_empty_listing(self):
        listing = {}
        result = self.scorer.score(listing, self.config)
        assert 40 <= result.score <= 70


# ---------------------------------------------------------------
# QualityScorer
# ---------------------------------------------------------------


class TestQualityScorer:
    scorer = QualityScorer()
    config = _make_config()

    def test_many_photos(self):
        listing = {
            "num_photos": 20,
            "description": "x" * 400,
            "has_video": True,
            "has_3d_tour": True,
        }
        result = self.scorer.score(listing, self.config)
        assert result.score == 100

    def test_minimal_listing(self):
        listing = {"num_photos": 2, "description": "short"}
        result = self.scorer.score(listing, self.config)
        assert result.score < 50


# ---------------------------------------------------------------
# ScamScorer
# ---------------------------------------------------------------


class TestScamScorer:
    scorer = ScamScorer()
    config = _make_config()

    def test_clean_listing(self):
        listing = {
            "num_photos": 10,
            "description": "x" * 200,
            "price": 900,
            "url": "https://example.com/listing/1",
        }
        result = self.scorer.score(listing, self.config)
        assert result.score == 100

    def test_suspicious_listing(self):
        listing = {
            "num_photos": 0,
            "description": "",
            "price": 200,
            "url": "",
            "red_flags": ["too good to be true", "wire transfer", "urgente"],
        }
        result = self.scorer.score(listing, self.config)
        assert result.score < 30

    def test_red_flags_json_string(self):
        listing = {
            "num_photos": 10,
            "description": "x" * 200,
            "price": 900,
            "url": "https://example.com",
            "red_flags": '["flag1", "flag2"]',
        }
        result = self.scorer.score(listing, self.config)
        assert result.score == 80  # 100 - 20 (2 flags)


# ---------------------------------------------------------------
# FreshnessScorer
# ---------------------------------------------------------------


class TestFreshnessScorer:
    scorer = FreshnessScorer()
    config = _make_config()

    def test_today(self):
        listing = {
            "creation_date": date.today().isoformat()
        }
        result = self.scorer.score(listing, self.config)
        assert result.score >= 90

    def test_old_listing(self):
        old = (date.today() - timedelta(days=30)).isoformat()
        listing = {"creation_date": old}
        result = self.scorer.score(listing, self.config)
        assert result.score <= 10

    def test_no_date(self):
        listing = {}
        result = self.scorer.score(listing, self.config)
        assert result.score == 50


# ---------------------------------------------------------------
# NeighborhoodScorer
# ---------------------------------------------------------------


class TestNeighborhoodScorer:
    scorer = NeighborhoodScorer()
    config = _make_config()

    def test_top_zone(self):
        listing = {"address": "Via Citta Studi 12, Milano"}
        result = self.scorer.score(listing, self.config)
        assert result.score == 100
        assert result.details["factor"] == 1.0
        assert result.details["tier"] == "top"

    def test_caution_zone(self):
        listing = {
            "address": "Via Quarto Oggiaro 5, Milano"
        }
        result = self.scorer.score(listing, self.config)
        assert result.score == 35
        assert result.details["tier"] == "caution"

    def test_unknown_zone(self):
        listing = {
            "address": "Via Sconosciuta 99, Unknown City"
        }
        result = self.scorer.score(listing, self.config)
        assert result.score == 60
        assert result.details["tier"] == "average"

    def test_macrozone_match(self):
        listing = {
            "neighborhood_name": "Isola - Garibaldi"
        }
        result = self.scorer.score(listing, self.config)
        # "isola" should match first (longest match)
        assert result.details["tier"] in ("top", "good")


# ---------------------------------------------------------------
# compute_hybrid_score integration
# ---------------------------------------------------------------


class TestHybridScore:
    config = _make_config()

    def test_full_integration(self):
        listing = {
            "lat": 45.4580,
            "lon": 9.1550,
            "address": "Via Isola 10, Milano",
            "elevator": True,
            "floor": "3",
            "balcony": True,
            "furnished": "full",
            "energy_class": "B",
            "condition": "renovated",
            "heating": "autonomous",
            "num_photos": 15,
            "description": "x" * 400,
            "has_video": True,
            "has_3d_tour": False,
            "price": 1000,
            "url": "https://example.com/listing/1",
            "creation_date": date.today().isoformat(),
        }
        scores = compute_hybrid_score(listing, self.config)

        assert "hybrid_score" in scores
        assert "commute_score" in scores
        assert "metro_score" in scores
        assert "livability_score" in scores
        assert "quality_score" in scores
        assert "scam_score" in scores
        assert "freshness_score" in scores
        assert "neighborhood_score" in scores
        assert "budget_status" in scores
        assert scores["hybrid_score"] > 0

    def test_empty_listing(self):
        listing = {"price": 800, "url": "https://x.com"}
        scores = compute_hybrid_score(listing, self.config)
        assert "hybrid_score" in scores
        assert scores["hybrid_score"] >= 0
