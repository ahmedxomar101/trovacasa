"""Pydantic-based configuration loader for TrovaCasa.

Reads config.yaml from the repo root, validates all fields,
and provides typed access throughout the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


class ConfigError(Exception):
    """Raised when config.yaml is invalid or missing."""


class Coordinates(BaseModel):
    lat: float
    lon: float
    name: str


class CommuteConfig(BaseModel):
    destination: Coordinates
    preferred_line: str | None = None


class BudgetConfig(BaseModel):
    max_rent: int
    currency: str = "EUR"


class ApartmentConfig(BaseModel):
    min_size_sqm: int = 40
    rooms: list[int] = [2, 3]
    bedrooms: list[int | str] = [1, 2, 3]


class ScraperConfig(BaseModel):
    """Config block for a single scraper.

    Uses extra="allow" so scraper-specific fields
    (location_id, zones, etc.) pass through.
    """

    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    actor_id: str
    max_items: int = 400
    timeout_secs: int = 1200


class ScoreThresholds(BaseModel):
    fresh_6h: int = 65
    day_old: int = 70
    two_day: int = 80


class TelegramConfig(BaseModel):
    enabled: bool = False
    score_thresholds: ScoreThresholds = ScoreThresholds()


class LLMConfig(BaseModel):
    model: str = "gpt-5-mini"
    max_workers: int = 15
    max_retries: int = 4


class GalleryConfig(BaseModel):
    min_score: int = 70
    batch_size: int = 20


class ScoringConfig(BaseModel):
    """Scoring configuration passed to scorers and the pipeline."""

    weights: dict[str, float]
    overrides: dict[str, dict[str, Any]] = {}
    city_data_path: Path = Path()
    budget: BudgetConfig | None = None
    commute: CommuteConfig | None = None


class Settings(BaseModel):
    """Root configuration model. Validated from config.yaml."""

    city: str
    budget: BudgetConfig
    apartment: ApartmentConfig = ApartmentConfig()
    commute: CommuteConfig
    scrapers: dict[str, ScraperConfig]
    scoring: ScoringConfig
    telegram: TelegramConfig = TelegramConfig()
    llm: LLMConfig = LLMConfig()
    gallery: GalleryConfig = GalleryConfig()

    @model_validator(mode="after")
    def _validate_settings(self) -> Settings:
        total = sum(self.scoring.weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total:.3f}"
            )

        enabled = [
            name
            for name, cfg in self.scrapers.items()
            if cfg.enabled
        ]
        if not enabled:
            raise ValueError(
                "At least one scraper must be enabled"
            )

        return self


def _resolve_city_data_path(city: str) -> Path:
    """Resolve the path to city data files."""
    data_dir = Path(__file__).parent.parent / "data" / "cities" / city
    return data_dir


def _parse_scoring_section(raw: dict) -> dict:
    """Parse the scoring section, separating weights from overrides."""
    result: dict[str, Any] = {}
    overrides: dict[str, dict] = {}

    for key, value in raw.items():
        if key == "weights":
            result["weights"] = value
        else:
            overrides[key] = value

    result["overrides"] = overrides
    return result


def load_config(path: Path | None = None) -> Settings:
    """Load and validate config.yaml.

    Args:
        path: Path to config.yaml. Defaults to repo root.

    Returns:
        Validated Settings instance.

    Raises:
        ConfigError: If config is invalid or missing.
    """
    if path is None:
        path = Path(__file__).parents[2] / "config.yaml"

    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\n"
            f"Copy config.example.yaml to config.yaml and customize it."
        )

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(raw)}")

    if "city" not in raw:
        raise ConfigError("Missing required field: city")

    if "commute" not in raw:
        raise ConfigError("Missing required field: commute")

    if "scoring" in raw:
        raw["scoring"] = _parse_scoring_section(raw["scoring"])

    city = raw["city"]
    city_data_path = _resolve_city_data_path(city)

    if "scoring" in raw:
        raw["scoring"]["city_data_path"] = city_data_path
        if "budget" in raw:
            raw["scoring"]["budget"] = raw["budget"]
        if "commute" in raw:
            raw["scoring"]["commute"] = raw["commute"]

    try:
        return Settings(**raw)
    except Exception as e:
        raise ConfigError(f"Config validation failed: {e}") from e
