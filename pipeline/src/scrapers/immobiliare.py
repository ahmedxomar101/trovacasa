"""Immobiliare.it scraper using memo23/immobiliare-scraper on Apify.

Two actors available:
1. memo23/immobiliare-scraper -- primary, rich output with coords
2. azzouzana/immobiliare-it-listing-page-scraper -- fallback

Both run on Apify infrastructure with residential proxies (IP-safe).
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from apify_client import ApifyClient
from rich.console import Console

from src.config import ScraperConfig, Settings
from src.models import RawListing

console = Console()

TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
POLL_INTERVAL = 30
LOCAL_TIMEOUT = 1800
START_TIMEOUT_SECS = 1800


class ImmobiliareScraper:
    """Wraps the memo23 Apify immobiliare actor."""

    name = "immobiliare"

    async def scrape(
        self,
        config: ScraperConfig,
        *,
        settings: Settings | None = None,
    ) -> list[RawListing]:
        """Run the Apify actor and return filtered listings."""
        token = os.environ.get("APIFY_API_TOKEN")
        if not token:
            console.log("[bold red]APIFY_API_TOKEN not set.[/bold red]")
            return []

        zones = config.__pydantic_extra__.get("zones", [])
        start_urls = [{"url": z} for z in zones]

        client = ApifyClient(token)

        run_input = {
            "startUrls": start_urls,
            "maxItems": config.max_items,
            "maxConcurrency": 10,
            "minConcurrency": 1,
            "maxRequestRetries": 50,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        console.rule(
            f"[bold blue]Immobiliare.it -- {config.actor_id}[/bold blue]"
        )
        console.log(f"Start URLs: {len(zones)} zone regions")
        console.log(f"Max items: {config.max_items}")
        console.log(
            "[dim]Running on Apify (your IP is safe)...[/dim]"
        )

        try:
            run = client.actor(config.actor_id).start(
                run_input=run_input,
                timeout_secs=config.timeout_secs,
            )
            run_id = run["id"]
            console.log(f"[dim]Apify run started (id: {run_id})[/dim]")

            start_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed > LOCAL_TIMEOUT:
                    console.log(
                        f"[bold red]Apify run timed out "
                        f"after {LOCAL_TIMEOUT}s[/bold red]"
                    )
                    return []

                run = client.run(run_id).get()
                status = run.get("status", "UNKNOWN")
                stats = run.get("stats", {})
                item_count = stats.get("itemCount", "?")
                console.log(
                    f"[dim]\u23f3 Apify running... "
                    f"{int(elapsed)}s elapsed | "
                    f"status: {status} | items: {item_count}[/dim]"
                )

                if status in TERMINAL_STATUSES:
                    break

                time.sleep(POLL_INTERVAL)

            if status != "SUCCEEDED":
                console.log(
                    f"[bold red]Apify run ended with "
                    f"status: {status}[/bold red]"
                )
                return []
        except Exception as e:
            console.log(f"[bold red]Apify actor failed: {e}[/bold red]")
            return []

        console.log(f"[green]Run completed. Status: {status}[/green]")

        raw_items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )
        console.log(f"[green]Fetched {len(raw_items)} raw items[/green]")

        listings: list[RawListing] = []
        for item in raw_items:
            listing = self.normalize(item)
            if listing is None:
                continue
            listing.raw_data = item
            if settings and not _passes_budget_filter(listing, settings):
                continue
            listings.append(listing)

        console.log(
            f"[green]Normalized {len(listings)} listings "
            f"after filtering[/green]"
        )
        return listings

    def normalize(self, raw_item: dict) -> RawListing | None:
        """Normalize memo23 output to RawListing."""
        return _normalize_memo23(raw_item)


def _normalize_memo23(item: dict) -> RawListing | None:
    """Normalize memo23 output to RawListing."""
    try:
        # Skip agency data
        if item.get("dataType") == "agency":
            return None

        # Price
        price_obj = item.get("price", {})
        price = (
            price_obj.get("raw")
            if isinstance(price_obj, dict) else None
        )
        if price is None:
            analytics = item.get("analytics", {})
            price = (
                int(analytics.get("price", 0))
                if analytics.get("price") else None
            )

        # Rooms & size
        topology = item.get("topology", {})
        rooms = topology.get("rooms")
        rooms = int(rooms) if rooms else None
        size = (
            topology.get("surface", {}).get("size")
            if isinstance(topology.get("surface"), dict) else None
        )
        size = int(size) if size else None

        # Geography
        geo = item.get("geography", {})
        geoloc = geo.get("geolocation", {})
        lat = geoloc.get("latitude")
        lon = geoloc.get("longitude")
        street = geo.get("street", "")
        municipality = (
            geo.get("municipality", {}).get("name", "")
            if isinstance(geo.get("municipality"), dict) else ""
        )
        macrozone = (
            geo.get("macrozone", {}).get("name", "")
            if isinstance(geo.get("macrozone"), dict) else ""
        )
        address_parts = [p for p in [street, macrozone, municipality] if p]
        address = ", ".join(address_parts)

        # Agent
        analytics = item.get("analytics", {})
        advertiser = analytics.get("advertiser", "")
        agent = (
            "privato"
            if advertiser == "privato"
            else (analytics.get("agencyName") or "agenzia")
        )

        # Floor
        floor = topology.get("floor") or analytics.get("floor")

        # URL
        share_url = item.get("shareUrl", "")
        listing_id = item.get("id")
        if share_url:
            url = share_url.split("?")[0]
        elif listing_id:
            url = f"https://www.immobiliare.it/annunci/{listing_id}/"
        else:
            url = ""

        # Image
        media = item.get("media", {})
        images = (
            media.get("images", [])
            if isinstance(media, dict) else []
        )
        image_url = (
            images[0].get("hd", images[0].get("sd", ""))
            if images else ""
        )

        # Title
        title = item.get("title", "")
        if not title:
            title = f"{rooms or '?'}r {size or '?'}m\u00b2 - {address}"

        # --- Structured fields from topology ---
        bathrooms = topology.get("bathrooms")
        bathrooms = int(bathrooms) if bathrooms else None

        typology = topology.get("typology", {})
        property_type = (
            typology.get("name")
            if isinstance(typology, dict) else None
        )

        elevator = topology.get("lift")
        if elevator is not None:
            elevator = bool(elevator)

        balcony = topology.get("balcony")
        if balcony is not None:
            balcony = bool(balcony)

        terrace = topology.get("terrace")
        if terrace is not None:
            terrace = bool(terrace)

        # Energy class from energyClass.consumptions
        energy_class = None
        energy_obj = item.get("energyClass", {})
        if isinstance(energy_obj, dict):
            consumptions = energy_obj.get("consumptions", [])
            if (
                consumptions
                and isinstance(consumptions, list)
                and isinstance(consumptions[0], dict)
            ):
                energy_class = consumptions[0].get("value")

        # Media counts
        num_photos = len(images) if images else None

        videos = (
            media.get("videos", [])
            if isinstance(media, dict) else []
        )
        has_video = bool(videos) if isinstance(videos, list) else False

        virtual_tour = (
            media.get("virtualTour")
            if isinstance(media, dict) else None
        )
        has_3d_tour = bool(virtual_tour)

        # Timestamps (unix -> ISO date string)
        creation_ts = item.get("creationDate")
        creation_date = None
        if creation_ts and isinstance(creation_ts, (int, float)):
            creation_date = datetime.fromtimestamp(
                creation_ts, tz=timezone.utc
            ).strftime("%Y-%m-%d")

        modified_ts = item.get("lastModified")
        last_modified = None
        if modified_ts and isinstance(modified_ts, (int, float)):
            last_modified = datetime.fromtimestamp(
                modified_ts, tz=timezone.utc
            ).strftime("%Y-%m-%d")

        # Price per sqm
        price_per_sqm = (
            round(price / size, 2) if price and size else None
        )

        # Condition (Italian -> English mapping)
        _condition_map = {
            "Buono / Abitabile": "good",
            "Buono/Abitabile": "good",
            "Ristrutturato": "renovated",
            "Da ristrutturare": "needs-work",
            "Ottimo/Ristrutturato": "renovated",
            "Nuovo / In costruzione": "new",
        }
        raw_condition = analytics.get("propertyStatus", "")
        condition = _condition_map.get(
            raw_condition, raw_condition or None
        )

        # --- Condo fees from costs array ---
        condo_fees = None
        condo_included = False
        costs_list = item.get("costs", [])
        if isinstance(costs_list, list):
            for cost in costs_list:
                if (
                    isinstance(cost, dict)
                    and "condomin"
                    in (cost.get("label", "") or "").lower()
                ):
                    val_str = cost.get("value", "")
                    digits = "".join(
                        c for c in val_str if c.isdigit()
                    )
                    if digits:
                        condo_fees = int(digits)

        # --- Heating from analytics or mainData ---
        heating = analytics.get("heating")
        heating_fuel = None
        main_data = item.get("mainData", [])
        if isinstance(main_data, list):
            for section in main_data:
                if not isinstance(section, dict):
                    continue
                for row in section.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    label = (row.get("label") or "").lower()
                    value = row.get("value", "")
                    if label == "heating" and value:
                        heating = value
                        if (
                            "methane" in value.lower()
                            or "metano" in value.lower()
                        ):
                            heating_fuel = "methane"
                        elif "gas" in value.lower():
                            heating_fuel = "gas"
                        elif (
                            "electric" in value.lower()
                            or "elettric" in value.lower()
                        ):
                            heating_fuel = "electric"

        # --- Building age from mainData ---
        building_age = None
        if isinstance(main_data, list):
            for section in main_data:
                if not isinstance(section, dict):
                    continue
                for row in section.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    label = (row.get("label") or "").lower()
                    if (
                        "year of construction" in label
                        or "anno" in label
                    ):
                        building_age = row.get("value")

        # --- Furnished from mainData or otherFeatures ---
        furnished = None
        other_features = analytics.get("otherFeatures", [])
        # Check mainData first (most reliable)
        if isinstance(main_data, list):
            for section in main_data:
                if not isinstance(section, dict):
                    continue
                for row in section.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    label = (row.get("label") or "").lower()
                    value = (row.get("value") or "").lower()
                    if label == "furnished" or label == "arredato":
                        if (
                            "partial" in value
                            or "parzial" in value
                            or "semi" in value
                        ):
                            furnished = "partial"
                        elif value in (
                            "yes", "s\u00ec", "si", "arredato",
                        ):
                            furnished = "full"
                        elif value in ("no", "non arredato"):
                            furnished = "no"
        # Fallback to otherFeatures
        if furnished is None and isinstance(other_features, list):
            features_lower = [
                f.lower() for f in other_features
                if isinstance(f, str)
            ]
            if "parzialmente arredato" in features_lower:
                furnished = "partial"
            elif "arredato" in features_lower:
                furnished = "full"

        # --- Air conditioning from mainData rows ---
        air_conditioning = None
        if isinstance(main_data, list):
            for section in main_data:
                if not isinstance(section, dict):
                    continue
                for row in section.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    label = (row.get("label") or "").lower()
                    if (
                        "air conditioning" in label
                        or "aria condizionata" in label
                        or "climatizzazione" in label
                    ):
                        air_conditioning = True

        # --- Orientation from otherFeatures (esposizione) ---
        orientation = None
        if isinstance(other_features, list):
            for f in other_features:
                if isinstance(f, str) and "esposizione" in f.lower():
                    orientation = f

        # --- Contract type, availability, balcony/terrace ---
        contract_type = None
        available_from = None
        if isinstance(main_data, list):
            for section in main_data:
                if not isinstance(section, dict):
                    continue
                for row in section.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    label = (row.get("label") or "").lower()
                    value = row.get("value", "")
                    if label == "contract" and value:
                        parts = value.split(", ", 1)
                        if len(parts) > 1:
                            contract_type = parts[1]
                    elif label == "availability" and value:
                        if value.lower() in (
                            "available", "disponibile", "libero",
                        ):
                            available_from = "immediate"
                        else:
                            available_from = value
                    elif label == "balcony" and value:
                        if balcony is None:
                            balcony = value.lower() in (
                                "yes", "s\u00ec", "si",
                            )
                    elif label == "terrace" and value:
                        if terrace is None:
                            terrace = value.lower() in (
                                "yes", "s\u00ec", "si",
                            )

        # --- Deposit from costs ---
        deposit_months = None
        if isinstance(costs_list, list):
            for cost in costs_list:
                if isinstance(cost, dict):
                    dep_label = (
                        cost.get("label", "") or ""
                    ).lower()
                    if "cauzione" in dep_label or "deposit" in dep_label:
                        val = cost.get("value", "")
                        digits = "".join(
                            c for c in val if c.isdigit()
                        )
                        if digits:
                            deposit_months = int(digits)

        # --- Phone from contacts ---
        phone = None
        contacts = item.get("contacts", {})
        if isinstance(contacts, dict):
            phones_list = contacts.get("phones", [])
            if isinstance(phones_list, list) and phones_list:
                first_phone = phones_list[0]
                if isinstance(first_phone, dict):
                    phone = first_phone.get("num")

        # --- Is private ---
        is_private = (
            True if analytics.get("advertiser") == "privato"
            else False
        )

        # --- Agency fee ---
        agency_fee = None
        if isinstance(costs_list, list):
            for cost in costs_list:
                if isinstance(cost, dict):
                    fee_label = (
                        cost.get("label", "") or ""
                    ).lower()
                    if (
                        "agenc" in fee_label
                        or "provvigion" in fee_label
                        or "commissi" in fee_label
                    ):
                        agency_fee = cost.get("value")

        # Description
        desc_obj = item.get("description", {})
        description = ""
        if isinstance(desc_obj, dict):
            description = (
                desc_obj.get("content", "")
                or desc_obj.get("caption", "")
                or ""
            )

        return RawListing(
            source="immobiliare",
            url=url,
            title=title,
            price=price,
            rooms=rooms,
            size_sqm=size,
            address=address,
            floor=floor,
            description=description,
            image_url=image_url,
            agent=agent,
            phone=phone,
            published_date="",
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
            bathrooms=bathrooms,
            property_type=property_type,
            elevator=elevator,
            balcony=balcony,
            terrace=terrace,
            energy_class=energy_class,
            num_photos=num_photos,
            has_video=has_video,
            has_3d_tour=has_3d_tour,
            creation_date=creation_date,
            last_modified=last_modified,
            price_per_sqm=price_per_sqm,
            condition=condition,
            condo_fees=condo_fees,
            condo_included=condo_included,
            heating=heating,
            heating_fuel=heating_fuel,
            building_age=building_age,
            furnished=furnished,
            air_conditioning=air_conditioning,
            orientation=orientation,
            is_private=is_private,
            agency_fee=agency_fee,
            contract_type=contract_type,
            available_from=available_from,
            deposit_months=deposit_months,
        )
    except Exception as e:
        console.log(f"[red]Error normalizing memo23: {e}[/red]")
        return None


def _normalize_azzouzana(item: dict) -> RawListing | None:
    """Normalize azzouzana output to RawListing (fallback actor)."""
    try:
        # Price -- try multiple paths
        price = None
        if isinstance(item.get("price"), dict):
            price = (
                item["price"].get("raw")
                or item["price"].get("value")
            )
            if isinstance(price, str):
                price = (
                    int(
                        "".join(c for c in price if c.isdigit())
                        or "0"
                    ) or None
                )
        elif isinstance(item.get("price"), (int, float)):
            price = int(item["price"])
        elif isinstance(item.get("price"), str):
            price = (
                int(
                    "".join(c for c in item["price"] if c.isdigit())
                    or "0"
                ) or None
            )

        # Rooms & size
        rooms = item.get("rooms")
        if isinstance(rooms, str):
            rooms = (
                int(
                    "".join(c for c in rooms if c.isdigit()) or "0"
                ) or None
            )
        elif isinstance(rooms, (int, float)):
            rooms = int(rooms)

        size = (
            item.get("surface")
            or item.get("size_sqm")
            or item.get("size")
        )
        if isinstance(size, dict):
            size = size.get("size")
        if isinstance(size, str):
            size = (
                int(
                    "".join(c for c in size if c.isdigit()) or "0"
                ) or None
            )
        elif isinstance(size, (int, float)):
            size = int(size)

        # Geography
        lat = None
        lon = None
        address = ""
        geo = item.get("geography") or item.get("location") or {}
        if isinstance(geo, dict):
            geoloc = geo.get("geolocation", {})
            if isinstance(geoloc, dict):
                lat = geoloc.get("latitude")
                lon = geoloc.get("longitude")
            street = (
                geo.get("street", "")
                if isinstance(geo.get("street"), str) else ""
            )
            macrozone = ""
            if isinstance(geo.get("macrozone"), dict):
                macrozone = geo["macrozone"].get("name", "")
            municipality = ""
            if isinstance(geo.get("municipality"), dict):
                municipality = geo["municipality"].get("name", "")
            address_parts = [
                p for p in [street, macrozone, municipality] if p
            ]
            address = ", ".join(address_parts)

        if not address:
            addr = item.get("address", "") or item.get("location", "")
            address = addr if isinstance(addr, str) else ""

        # Agent
        agent = (
            item.get("advertiser")
            or item.get("agent")
            or "privato"
        )
        if isinstance(agent, dict):
            agent = agent.get("name", "agenzia")

        # Floor
        floor = item.get("floor")

        # URL
        url = item.get("url") or item.get("shareUrl") or ""
        if url and "?" in url:
            url = url.split("?")[0]

        # Image
        image_url = ""
        media = item.get("media") or item.get("images")
        if isinstance(media, dict):
            imgs = media.get("images", [])
            if imgs and isinstance(imgs[0], dict):
                image_url = imgs[0].get(
                    "hd", imgs[0].get("sd", "")
                )
        elif isinstance(media, list) and media:
            first = media[0]
            if isinstance(first, dict):
                image_url = first.get(
                    "hd",
                    first.get("sd", first.get("url", "")),
                )

        # Title
        title = item.get("title", "") or ""
        if not title:
            title = (
                f"{rooms or '?'}r {size or '?'}m\u00b2 - {address}"
            )

        return RawListing(
            source="immobiliare",
            url=url,
            title=title,
            price=price,
            rooms=rooms,
            size_sqm=size,
            address=address,
            floor=floor,
            description="",
            image_url=image_url,
            agent=agent,
            published_date="",
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
        )
    except Exception as e:
        console.log(f"[red]Error normalizing azzouzana: {e}[/red]")
        return None


def _passes_budget_filter(
    listing: RawListing,
    settings: Settings,
) -> bool:
    """Check if listing passes budget and size filters."""
    if listing.price and listing.price > settings.budget.max_rent:
        return False
    if (
        listing.size_sqm
        and listing.size_sqm < settings.apartment.min_size_sqm
    ):
        return False
    return True
