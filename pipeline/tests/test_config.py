import yaml
import pytest
from pathlib import Path

from src.config import load_config, ConfigError


MINIMAL_CONFIG = {
    "city": "milan",
    "budget": {"max_rent": 1100, "currency": "EUR"},
    "apartment": {
        "min_size_sqm": 40,
        "rooms": [2, 3],
        "bedrooms": [1, 2, 3],
    },
    "commute": {
        "destination": {
            "lat": 45.4565,
            "lon": 9.1525,
            "name": "Tre Torri",
        },
    },
    "scrapers": {
        "idealista": {
            "enabled": True,
            "actor_id": "dz_omar/idealista-scraper",
            "location_id": "0-EU-IT-MI-01-001-135",
        },
    },
    "scoring": {
        "weights": {
            "commute": 0.30,
            "metro": 0.20,
            "livability": 0.15,
            "freshness": 0.15,
            "scam": 0.10,
            "quality": 0.10,
        },
    },
    "llm": {"model": "gpt-5-mini"},
}


def _write_config(tmp_path: Path, data: dict) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(data))
    return config_path


def test_load_minimal_config(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_config(path)
    assert settings.city == "milan"
    assert settings.budget.max_rent == 1100
    assert settings.commute.destination.lat == 45.4565
    assert settings.scoring.weights["commute"] == 0.30


def test_weights_must_sum_to_one(tmp_path):
    bad = {**MINIMAL_CONFIG}
    bad["scoring"] = {
        "weights": {"commute": 0.50, "metro": 0.60},
    }
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigError, match="sum to 1.0"):
        load_config(path)


def test_missing_city_raises(tmp_path):
    bad = {k: v for k, v in MINIMAL_CONFIG.items() if k != "city"}
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigError):
        load_config(path)


def test_no_scrapers_enabled_raises(tmp_path):
    bad = {**MINIMAL_CONFIG}
    bad["scrapers"] = {
        "idealista": {"enabled": False, "actor_id": "x"},
    }
    path = _write_config(tmp_path, bad)
    with pytest.raises(ConfigError, match="scraper"):
        load_config(path)


def test_scraper_config_extra_fields(tmp_path):
    config = {**MINIMAL_CONFIG}
    config["scrapers"] = {
        "idealista": {
            "enabled": True,
            "actor_id": "dz_omar/idealista-scraper",
            "location_id": "0-EU-IT-MI-01-001-135",
            "custom_field": "hello",
        },
    }
    path = _write_config(tmp_path, config)
    settings = load_config(path)
    scraper_cfg = settings.scrapers["idealista"]
    assert scraper_cfg.custom_field == "hello"


def test_scoring_overrides(tmp_path):
    config = {**MINIMAL_CONFIG}
    config["scoring"] = {
        **MINIMAL_CONFIG["scoring"],
        "livability": {
            "elevator": {"yes": 90, "no_high_floor": 10},
        },
    }
    path = _write_config(tmp_path, config)
    settings = load_config(path)
    assert settings.scoring.overrides["livability"]["elevator"]["yes"] == 90


def test_optional_telegram_defaults_disabled(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_config(path)
    assert settings.telegram.enabled is False


def test_preferred_line_optional(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_config(path)
    assert settings.commute.preferred_line is None


def test_preferred_line_set(tmp_path):
    config = {**MINIMAL_CONFIG}
    config["commute"] = {
        **MINIMAL_CONFIG["commute"],
        "preferred_line": "M5",
    }
    path = _write_config(tmp_path, config)
    settings = load_config(path)
    assert settings.commute.preferred_line == "M5"


def test_missing_config_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config(Path("/nonexistent/config.yaml"))


def test_city_data_path_resolved(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_config(path)
    assert settings.scoring.city_data_path.name == "milan"
    assert "cities" in str(settings.scoring.city_data_path)


def test_budget_forwarded_to_scoring(tmp_path):
    path = _write_config(tmp_path, MINIMAL_CONFIG)
    settings = load_config(path)
    assert settings.scoring.budget is not None
    assert settings.scoring.budget.max_rent == 1100
