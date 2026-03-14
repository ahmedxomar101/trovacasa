"""Tests for shared transit utilities."""

from __future__ import annotations

import pytest

from src.scoring.transit import (
    build_metro_graph,
    find_nearest_stations,
    haversine_m,
    load_city_transit,
    shortest_path,
)


def test_haversine_known_distance():
    """Duomo to Cadorna is roughly 900-1400 m."""
    d = haversine_m(45.4641, 9.1919, 45.4669, 9.1750)
    assert 800 < d < 1500


def test_haversine_zero_distance():
    """Same point should return 0."""
    d = haversine_m(45.0, 9.0, 45.0, 9.0)
    assert d == 0.0


def test_load_city_transit():
    """Load milan metro.json and verify basic structure."""
    data = load_city_transit("milan")
    assert data["city"] == "milan"
    assert len(data["stations"]) > 100


def test_find_nearest_stations():
    """Near Duomo, should find at least one station."""
    data = load_city_transit("milan")
    stations = find_nearest_stations(
        45.4641, 9.1919, data["stations"], max_distance_m=1000
    )
    assert len(stations) > 0
    # Results should be sorted by distance
    distances = [s["distance_m"] for s in stations]
    assert distances == sorted(distances)
    # Each result has required keys
    for s in stations:
        assert "name" in s
        assert "lines" in s
        assert "distance_m" in s
        assert "walk_minutes" in s


def test_find_nearest_stations_empty():
    """No stations in the middle of nowhere."""
    data = load_city_transit("milan")
    stations = find_nearest_stations(
        0.0, 0.0, data["stations"], max_distance_m=1000
    )
    assert stations == []


def test_build_and_route_graph():
    """Build graph and route Duomo -> Tre Torri (requires transfer)."""
    data = load_city_transit("milan")
    graph = build_metro_graph(data)
    result = shortest_path(
        graph, "Duomo", "Tre Torri", data["travel_time"]
    )
    assert result is not None
    assert result["total_minutes"] > 0
    assert result["transfers"] >= 1
    assert result["route"][0] == "Duomo"
    assert result["route"][-1] == "Tre Torri"


def test_shortest_path_same_station():
    """Routing from a station to itself should be instant."""
    data = load_city_transit("milan")
    graph = build_metro_graph(data)
    result = shortest_path(
        graph, "Duomo", "Duomo", data["travel_time"]
    )
    assert result is not None
    assert result["total_minutes"] == 0
    assert result["transfers"] == 0


def test_shortest_path_same_line():
    """Two stations on the same line should need 0 transfers."""
    data = load_city_transit("milan")
    graph = build_metro_graph(data)
    # Duomo and Loreto are both on M1
    result = shortest_path(
        graph, "Duomo", "Loreto", data["travel_time"]
    )
    assert result is not None
    assert result["transfers"] == 0
    assert result["total_minutes"] > 0
