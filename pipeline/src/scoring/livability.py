"""LivabilityScorer — apartment comfort and modernity."""

from __future__ import annotations

from typing import Optional

from src.config import ScoringConfig
from src.models import ScoreResult

# Basement/underground floor codes (Italian)
_BASEMENT_CODES = {"bj", "ss", "sb", "b", "s", "s1", "s2", "-1", "-2"}
_GROUND_CODES = {"en", "g", "0", "t", "pt"}
_MEZZANINE_CODES = {"m", "mz"}


class LivabilityScorer:
    """Score apartment livability based on comfort factors."""

    name = "livability"
    description = "Apartment comfort and modernity"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        overrides = config.overrides.get("livability", {})

        floor_raw = listing.get("floor")
        floor_int = _parse_floor_int(floor_raw)

        factors: list[int] = []
        factor_details: dict[str, int] = {}

        elevator_score = _score_elevator(
            listing.get("elevator"), floor_int, overrides
        )
        factors.append(elevator_score)
        factor_details["elevator"] = elevator_score

        floor_score = _score_floor(
            floor_raw,
            listing.get("is_last_floor"),
            overrides,
        )
        factors.append(floor_score)
        factor_details["floor"] = floor_score

        balcony_val = listing.get("balcony") or listing.get(
            "terrace"
        )
        balcony_score = _score_balcony(balcony_val, overrides)
        factors.append(balcony_score)
        factor_details["balcony"] = balcony_score

        furnished_score = _score_furnished(
            listing.get("furnished"), overrides
        )
        factors.append(furnished_score)
        factor_details["furnished"] = furnished_score

        energy_score = _score_energy_class(
            listing.get("energy_class"), overrides
        )
        factors.append(energy_score)
        factor_details["energy_class"] = energy_score

        condition_score = _score_condition(
            listing.get("condition"), overrides
        )
        factors.append(condition_score)
        factor_details["condition"] = condition_score

        heating_score = _score_heating(
            listing.get("heating"), overrides
        )
        factors.append(heating_score)
        factor_details["heating"] = heating_score

        total = round(sum(factors) / len(factors))
        return ScoreResult(
            score=total, details=factor_details
        )


def _parse_floor_int(floor_raw) -> Optional[int]:
    if floor_raw is None:
        return None
    try:
        return int(str(floor_raw).strip())
    except (ValueError, TypeError):
        return None


def _parse_floor(
    floor_raw: Optional[str],
) -> tuple[Optional[str], Optional[int]]:
    """Parse floor string into (category, numeric_value)."""
    if floor_raw is None:
        return None, None

    fl = str(floor_raw).strip().lower()
    if "," in fl:
        fl = fl.split(",")[0].strip()

    if fl in _BASEMENT_CODES:
        return "basement", None
    if fl in _GROUND_CODES:
        return "ground", None
    if fl in _MEZZANINE_CODES:
        return "mezzanine", None

    try:
        return "numeric", int(fl)
    except (ValueError, TypeError):
        return None, None


def _score_elevator(
    elevator: Optional[bool],
    floor: Optional[int],
    overrides: dict,
) -> int:
    if "elevator" in overrides:
        return overrides["elevator"]
    if elevator is None:
        return 50
    if elevator:
        return 80
    if floor is not None and floor > 2:
        return 30
    return 70


def _score_floor(
    floor_raw: Optional[str],
    is_last_floor: Optional[bool],
    overrides: dict,
) -> int:
    if "floor" in overrides:
        return overrides["floor"]
    category, numeric = _parse_floor(floor_raw)

    if category is None:
        if is_last_floor:
            return 45
        return 50

    if category == "basement":
        return 20
    if category == "ground":
        return 40
    if category == "mezzanine":
        return 40

    if numeric is not None:
        if numeric <= 0:
            return 20
        if is_last_floor:
            return 45
        if numeric <= 2:
            return 50
        if numeric <= 6:
            return 70
        return 45

    return 50


def _score_balcony(
    balcony: Optional[bool], overrides: dict
) -> int:
    if "balcony" in overrides:
        return overrides["balcony"]
    if balcony is None:
        return 60
    return 80 if balcony else 40


def _score_furnished(
    furnished: Optional[str], overrides: dict
) -> int:
    if "furnished" in overrides:
        return overrides["furnished"]
    if furnished is None:
        return 60
    normalized = furnished.strip().lower()
    if normalized == "full":
        return 90
    if normalized == "partial":
        return 70
    if normalized == "no":
        return 50
    return 60


def _score_energy_class(
    energy_class: Optional[str], overrides: dict
) -> int:
    if "energy_class" in overrides:
        return overrides["energy_class"]
    if energy_class is None:
        return 50
    cls = energy_class.strip().upper()
    if cls.startswith("A") or cls.startswith("B"):
        return 100
    if cls.startswith("C") or cls.startswith("D"):
        return 70
    if cls.startswith("E") or cls.startswith("F"):
        return 40
    if cls.startswith("G"):
        return 20
    return 50


def _score_condition(
    condition: Optional[str], overrides: dict
) -> int:
    if "condition" in overrides:
        return overrides["condition"]
    if condition is None:
        return 50
    normalized = condition.strip().lower()
    if normalized in ("renovated", "ristrutturato", "nuovo"):
        return 100
    if normalized in ("good", "buono", "buono stato"):
        return 70
    if normalized in (
        "needs-work",
        "needs work",
        "da ristrutturare",
    ):
        return 30
    return 50


def _score_heating(
    heating: Optional[str], overrides: dict
) -> int:
    if "heating" in overrides:
        return overrides["heating"]
    if heating is None:
        return 60
    normalized = heating.strip().lower()
    if normalized in ("autonomous", "autonomo"):
        return 80
    if normalized in ("centralized", "centralizzato"):
        return 50
    return 60
