"""MetroScorer — proximity to metro and preferred line access."""

from __future__ import annotations

from src.config import ScoringConfig
from src.models import ScoreResult
from src.scoring import transit

# Default radii (meters)
_MAX_DISTANCE_M = 1000
_SCAN_RADIUS_M = 1200


class MetroScorer:
    """Score listings by metro proximity and preferred line."""

    name = "metro"
    description = "Metro proximity and preferred line access"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        lat = listing.get("lat")
        lon = listing.get("lon")

        if lat is None or lon is None:
            return ScoreResult(score=0, details={})

        preferred_line = (
            config.commute.preferred_line
            if config.commute
            else None
        )

        city = (
            config.city_data_path.name
            if config.city_data_path
            else "milan"
        )
        transit_data = transit.load_city_transit(city)
        stations = transit_data["stations"]

        # Find all stations within scan radius
        nearby: list[tuple[dict, float]] = []
        for st in stations:
            dist = transit.haversine_m(
                lat, lon, st["lat"], st["lon"]
            )
            if dist <= _SCAN_RADIUS_M:
                nearby.append((st, dist))

        nearby.sort(key=lambda x: x[1])

        if not nearby:
            return ScoreResult(
                score=0,
                details={
                    "nearest_station": None,
                    "on_preferred_line": False,
                },
            )

        nearest_st, nearest_dist = nearby[0]
        nearest_info = {
            "name": nearest_st["name"],
            "distance_m": round(nearest_dist),
            "lines": nearest_st["lines"],
        }

        # Build interchange set for preferred line
        pref_interchanges = _find_preferred_interchanges(
            stations, preferred_line
        )

        # Determine preferred-line flags
        on_pref = _has_preferred_station(
            nearby, preferred_line
        )
        has_pref_interchange = _has_preferred_interchange(
            nearby, pref_interchanges
        )

        # Find closest preferred-line station distance
        pref_dist = _closest_matching_dist(
            nearby,
            lambda st: preferred_line in st.get("lines", []),
        )
        interchange_dist = _closest_matching_dist(
            nearby,
            lambda st: st["name"] in pref_interchanges,
        )

        # Compute score using same tiers as old metro.py
        score = _compute_score(
            nearest_dist,
            pref_dist,
            interchange_dist,
        )

        # Determine transfers to preferred line
        if on_pref:
            transfers = 0
            pref_reachable = True
        elif has_pref_interchange:
            transfers = 1
            pref_reachable = True
        else:
            nearby_lines: set[str] = set()
            for st, _ in nearby:
                nearby_lines.update(st.get("lines", []))
            interchange_lines = {
                _line_of_interchange(st_name, stations)
                for st_name in pref_interchanges
            }
            interchange_lines.discard(None)
            if nearby_lines & interchange_lines:
                transfers = 1
                pref_reachable = True
            else:
                transfers = 2
                pref_reachable = False

        return ScoreResult(
            score=score,
            details={
                "nearest_station": nearest_info,
                "on_preferred_line": on_pref,
                "preferred_line_reachable": pref_reachable,
                "transfers_to_preferred": transfers,
            },
        )


def _find_preferred_interchanges(
    stations: list[dict], preferred_line: str | None
) -> set[str]:
    """Find interchange stations that connect to the preferred line."""
    if not preferred_line:
        return set()
    result: set[str] = set()
    for st in stations:
        if (
            st.get("is_interchange")
            and preferred_line in st.get("lines", [])
        ):
            result.add(st["name"])
    return result


def _has_preferred_station(
    nearby: list[tuple[dict, float]],
    preferred_line: str | None,
) -> bool:
    if not preferred_line:
        return False
    return any(
        preferred_line in st.get("lines", [])
        for st, _ in nearby
    )


def _has_preferred_interchange(
    nearby: list[tuple[dict, float]],
    interchanges: set[str],
) -> bool:
    return any(st["name"] in interchanges for st, _ in nearby)


def _closest_matching_dist(
    nearby: list[tuple[dict, float]],
    predicate,
) -> float | None:
    for st, d in nearby:
        if predicate(st):
            return d
    return None


def _line_of_interchange(
    station_name: str, stations: list[dict]
) -> str | None:
    """Return the non-preferred line of an interchange station."""
    for st in stations:
        if st["name"] == station_name:
            lines = st.get("lines", [])
            return lines[0] if lines else None
    return None


def _compute_score(
    nearest_dist: float,
    pref_dist: float | None,
    interchange_dist: float | None,
) -> int:
    """Compute metro score using tiered distance brackets."""
    if pref_dist is not None and pref_dist <= 800:
        # Preferred line within 800m: 90-100
        return 100 - round(10 * (pref_dist / 800))
    if interchange_dist is not None and interchange_dist <= 800:
        # Interchange within 800m: 75-89
        return 89 - round(14 * (interchange_dist / 800))
    if nearest_dist <= 800:
        # Any metro within 800m: 50-74
        return 74 - round(24 * (nearest_dist / 800))
    if nearest_dist <= _SCAN_RADIUS_M:
        # Station 800-1200m: reduced score
        if pref_dist is not None and pref_dist <= _SCAN_RADIUS_M:
            base = 90
        elif (
            interchange_dist is not None
            and interchange_dist <= _SCAN_RADIUS_M
        ):
            base = 75
        else:
            base = 50
        return max(0, base - 15)
    return 0
