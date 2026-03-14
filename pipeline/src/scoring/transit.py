"""Shared transit utilities for metro routing and station lookup.

Provides haversine distance, station search, graph construction,
and Dijkstra shortest-path routing. All logic is data-driven from
metro.json — no city-specific constants are hardcoded.
"""

from __future__ import annotations

import heapq
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional


# Default walking speed in meters per minute (~4.8 km/h)
_DEFAULT_WALK_SPEED_M_PER_MIN = 80


def haversine_m(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distance in meters between two GPS coordinates."""
    R = 6_371_000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


@lru_cache(maxsize=4)
def load_city_transit(city: str) -> dict:
    """Load metro.json for a city from data/cities/{city}/."""
    data_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "cities"
        / city
        / "metro.json"
    )
    return json.loads(data_path.read_text())


def find_nearest_stations(
    lat: float,
    lon: float,
    stations: list[dict],
    max_distance_m: float = 1000,
    limit: int = 3,
    walking_speed: float = _DEFAULT_WALK_SPEED_M_PER_MIN,
) -> list[dict]:
    """Find nearest metro stations within *max_distance_m*.

    Returns list of dicts with: name, lines, distance_m, walk_minutes.
    Sorted by distance (closest first).
    """
    results: list[dict] = []

    for st in stations:
        dist = haversine_m(lat, lon, st["lat"], st["lon"])
        if dist <= max_distance_m:
            results.append(
                {
                    "name": st["name"],
                    "lines": st["lines"],
                    "distance_m": round(dist),
                    "walk_minutes": round(dist / walking_speed),
                }
            )

    results.sort(key=lambda r: r["distance_m"])
    return results[:limit]


def build_metro_graph(transit_data: dict) -> dict:
    """Build a graph for shortest-path routing from metro.json.

    The graph is built from the ``lines[].branches[].stations[]``
    structure. Adjacent stations in a branch are connected.
    Interchange stations (same name on different lines) are
    connected with transfer penalty.

    Returns
    -------
    dict
        ``{(station, line): [(neighbor_station, neighbor_line, cost), ...]}``
        where *cost* is the inter-station travel time in minutes.
    """
    travel_time = transit_data.get("travel_time", {})
    minutes_per_stop = travel_time.get("minutes_per_stop", 2)
    transfer_penalty = travel_time.get("transfer_penalty", 5)

    # Adjacency list keyed by (station_name, line_id)
    graph: dict[
        tuple[str, str],
        list[tuple[str, str, float]],
    ] = {}

    def _add_edge(
        s1: str,
        l1: str,
        s2: str,
        l2: str,
        cost: float,
    ) -> None:
        graph.setdefault((s1, l1), []).append((s2, l2, cost))
        graph.setdefault((s2, l2), []).append((s1, l1, cost))

    # Track all (station, line) pairs for interchange linking
    station_lines: dict[str, list[str]] = {}

    for line in transit_data.get("lines", []):
        line_id = line["id"]

        for branch in line.get("branches", []):
            branch_stations = branch.get("stations", [])

            for i in range(len(branch_stations) - 1):
                s1 = branch_stations[i]
                s2 = branch_stations[i + 1]
                _add_edge(s1, line_id, s2, line_id, minutes_per_stop)

            # Record which lines each station appears on
            for name in branch_stations:
                station_lines.setdefault(name, [])
                if line_id not in station_lines[name]:
                    station_lines[name].append(line_id)

    # Connect interchange stations (same name, different lines)
    for name, lines_at in station_lines.items():
        for i in range(len(lines_at)):
            for j in range(i + 1, len(lines_at)):
                _add_edge(
                    name,
                    lines_at[i],
                    name,
                    lines_at[j],
                    transfer_penalty,
                )

    return graph


def shortest_path(
    graph: dict,
    from_station: str,
    to_station: str,
    travel_time: dict,
) -> dict | None:
    """Find shortest path between two stations using Dijkstra.

    Parameters
    ----------
    graph : dict
        Output of :func:`build_metro_graph`.
    from_station, to_station : str
        Station names (must exist in the graph on at least one line).
    travel_time : dict
        The ``travel_time`` block from metro.json (provides
        ``transfer_penalty`` for counting transfers).

    Returns
    -------
    dict or None
        ``{total_minutes, transfers, route}`` where *route* is a
        list of station names. Returns ``None`` if no path exists.
    """
    if from_station == to_station:
        return {
            "total_minutes": 0,
            "transfers": 0,
            "route": [from_station],
        }

    transfer_penalty = travel_time.get("transfer_penalty", 5)

    # Collect start / end nodes (station may appear on multiple lines)
    start_nodes = [
        key for key in graph if key[0] == from_station
    ]
    end_names = {to_station}

    if not start_nodes:
        return None

    # Dijkstra over (station, line) states
    # heap items: (cost, transfers, station, line, route)
    best: dict[tuple[str, str], float] = {}
    heap: list[
        tuple[float, int, str, str, list[str]]
    ] = []

    for node in start_nodes:
        heapq.heappush(heap, (0, 0, node[0], node[1], [node[0]]))

    while heap:
        cost, transfers, station, line, route = heapq.heappop(
            heap
        )

        state = (station, line)
        if state in best:
            continue
        best[state] = cost

        if station in end_names:
            return {
                "total_minutes": cost,
                "transfers": transfers,
                "route": route,
            }

        for nb_station, nb_line, edge_cost in graph.get(
            state, []
        ):
            nb_state = (nb_station, nb_line)
            if nb_state in best:
                continue

            is_transfer = (
                nb_station == station and nb_line != line
            )
            new_transfers = (
                transfers + 1 if is_transfer else transfers
            )

            # Build route — only append if moving to a new station
            new_route = (
                route
                if nb_station == station
                else route + [nb_station]
            )

            heapq.heappush(
                heap,
                (
                    cost + edge_cost,
                    new_transfers,
                    nb_station,
                    nb_line,
                    new_route,
                ),
            )

    return None
