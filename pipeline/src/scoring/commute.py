"""CommuteScorer — transit commute time to workplace."""

from __future__ import annotations

from src.config import ScoringConfig
from src.models import ScoreResult
from src.scoring import transit


class CommuteScorer:
    """Score listings by metro commute time to a destination.

    Supports two modes:
    - Intracity: routes through metro graph (Milan, Rome)
    - Intercity: fixed_transit_minutes set, scores on walk-to-station
    """

    name = "commute"
    description = "Transit commute time to workplace"

    def score(
        self, listing: dict, config: ScoringConfig
    ) -> ScoreResult:
        lat = listing.get("lat")
        lon = listing.get("lon")

        if lat is None or lon is None or config.commute is None:
            return ScoreResult(score=50, details={})

        city = config.city_data_path.name if config.city_data_path else "milan"
        transit_data = transit.load_city_transit(city)
        stations = transit_data["stations"]
        travel_time_cfg = transit_data.get("travel_time", {})
        walk_speed = travel_time_cfg.get(
            "walking_speed_m_per_min", 80
        )

        # Find nearest station
        best_dist = float("inf")
        best_station: dict | None = None
        for st in stations:
            d = transit.haversine_m(lat, lon, st["lat"], st["lon"])
            if d < best_dist:
                best_dist = d
                best_station = st

        if best_station is None:
            return ScoreResult(
                score=20,
                details={"reason": "no_stations"},
            )

        walk_to_min = best_dist / walk_speed

        # Intercity mode: score on walk-to-station only
        if config.commute.fixed_transit_minutes is not None:
            score = _score_walk_to_station(walk_to_min)
            total = round(
                walk_to_min + config.commute.fixed_transit_minutes
            )
            return ScoreResult(
                score=score,
                details={
                    "commute_minutes": total,
                    "walk_to_station_min": round(walk_to_min, 1),
                    "nearest_station": best_station["name"],
                    "fixed_transit_minutes": config.commute.fixed_transit_minutes,
                    "mode": "intercity",
                },
            )

        # Intracity mode: route through metro graph
        dest = config.commute.destination
        dest_dist = float("inf")
        dest_station: dict | None = None
        for st in stations:
            d = transit.haversine_m(
                dest.lat, dest.lon, st["lat"], st["lon"]
            )
            if d < dest_dist:
                dest_dist = d
                dest_station = st

        if dest_station is None:
            return ScoreResult(
                score=20,
                details={"reason": "no_dest_station"},
            )

        walk_from_dest = dest_dist / walk_speed
        walk_from_dest = max(walk_from_dest, 3.0)

        graph = transit.build_metro_graph(transit_data)
        path = transit.shortest_path(
            graph,
            best_station["name"],
            dest_station["name"],
            travel_time_cfg,
        )

        if path is None:
            return ScoreResult(
                score=20,
                details={
                    "nearest_station": best_station["name"],
                    "walk_minutes": round(walk_to_min, 1),
                    "reason": "no_route",
                },
            )

        total = walk_to_min + path["total_minutes"] + walk_from_dest
        commute_minutes = round(total)
        score = _score_commute_minutes(commute_minutes)

        return ScoreResult(
            score=score,
            details={
                "commute_minutes": commute_minutes,
                "nearest_station": best_station["name"],
                "walk_minutes": round(walk_to_min, 1),
                "metro_minutes": path["total_minutes"],
                "transfers": path["transfers"],
            },
        )


def _score_walk_to_station(walk_minutes: float) -> int:
    """Score intercity commute by walk-to-station time."""
    if walk_minutes < 5:
        return 100
    if walk_minutes <= 8:
        return 90
    if walk_minutes <= 12:
        return 80
    if walk_minutes <= 15:
        return 70
    if walk_minutes <= 20:
        return 55
    if walk_minutes <= 25:
        return 40
    return 20


def _score_commute_minutes(minutes: int) -> int:
    """Map commute minutes to a 0-100 score."""
    if minutes < 20:
        return 100
    if minutes <= 25:
        return 90
    if minutes <= 30:
        return 80
    if minutes <= 35:
        return 70
    if minutes <= 40:
        return 60
    if minutes <= 45:
        return 50
    if minutes <= 50:
        return 40
    return 20
