"""Shared Pydantic models used across the TrovaCasa pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RawListing(BaseModel):
    """Standard schema that every scraper must output.

    All fields except source, url, and raw_data are optional
    to accommodate different scraper capabilities.
    """

    source: str
    url: str
    title: str | None = None
    address: str | None = None
    price: int | None = None
    rooms: int | None = None
    size_sqm: int | None = None
    floor: str | None = None
    description: str | None = None
    image_url: str | None = None
    lat: float | None = None
    lon: float | None = None
    agent: str | None = None
    phone: str | None = None
    bathrooms: int | None = None
    energy_class: str | None = None
    num_photos: int | None = None
    has_video: bool = False
    has_3d_tour: bool = False
    published_date: str | None = None
    creation_date: str | None = None
    last_modified: str | None = None
    price_per_sqm: float | None = None
    property_type: str | None = None
    elevator: bool | None = None
    balcony: bool | None = None
    terrace: bool | None = None
    condition: str | None = None
    air_conditioning: bool | None = None
    is_private: bool | None = None
    condo_fees: int | None = None
    condo_included: bool | None = None
    heating: str | None = None
    heating_fuel: str | None = None
    building_age: str | None = None
    furnished: str | None = None
    orientation: str | None = None
    agency_fee: str | None = None
    contract_type: str | None = None
    available_from: str | None = None
    deposit_months: int | None = None
    raw_data: dict = {}


class ScoreResult(BaseModel):
    """Result from a single scorer dimension."""

    score: int  # 0-100
    details: dict[str, Any] = {}
