"""Idealista scraper using dz_omar/idealista-scraper on Apify.

IP-safe: runs entirely on Apify infrastructure with residential proxies.
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


class IdealistaScraper:
    """Wraps the dz_omar Apify idealista actor."""

    name = "idealista"

    async def scrape(
        self,
        config: ScraperConfig,
        *,
        settings: Settings | None = None,
    ) -> list[RawListing]:
        """Run the Apify actor and return filtered listings."""
        token = os.environ.get("APIFY_API_TOKEN")
        if not token:
            console.log(
                "[bold red]APIFY_API_TOKEN not set.[/bold red]\n"
                "Get one at https://console.apify.com/account/integrations"
            )
            return []

        search_url = config.__pydantic_extra__.get("search_url", "")
        client = ApifyClient(token)

        run_input = {
            "Url": [search_url],
            "desiredResults": config.max_items,
            "proxyConfig": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        console.rule(
            "[bold blue]Idealista.it -- Apify Scraper (dz_omar)[/bold blue]"
        )
        console.log(f"Actor: {config.actor_id}")
        console.log(f"URL: {search_url}")
        console.log(
            f"Filters: rent, max {config.max_items} items"
        )
        console.log(
            "[dim]Running on Apify infrastructure "
            "(your IP is safe)...[/dim]"
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
        console.log(f"[green]Fetched {len(raw_items)} raw listings[/green]")

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
            f"after client-side filtering[/green]"
        )
        return listings

    def normalize(self, raw_item: dict) -> RawListing | None:
        """Normalize a dz_omar idealista result to RawListing."""
        try:
            price = raw_item.get("price")
            if isinstance(price, dict):
                price = price.get("amount")
            price = int(price) if price else None

            rooms = raw_item.get("rooms")
            rooms = int(rooms) if rooms else None

            size = raw_item.get("size")
            size = int(size) if size else None

            # Address
            address_parts = [
                p for p in [
                    raw_item.get("address"),
                    raw_item.get("district"),
                    raw_item.get("municipality"),
                ] if p
            ]
            address = ", ".join(address_parts)

            # Agent info + phone
            agent = "privato"
            phone = None
            contact = raw_item.get("contactInfo")
            if contact and isinstance(contact, dict):
                agent = (
                    contact.get("commercialName")
                    or contact.get("contactName")
                    or "agenzia"
                )
                phone1 = contact.get("phone1", {})
                if isinstance(phone1, dict):
                    phone = (
                        phone1.get("phoneNumberForMobileDialing")
                        or phone1.get("formattedPhone")
                    )

            # Coordinates
            lat = raw_item.get("latitude")
            lon = raw_item.get("longitude")

            # URL
            url = raw_item.get("url", "")
            if url and not url.startswith("http"):
                url = f"https://www.idealista.it{url}"

            # Images
            image_url = raw_item.get("thumbnail", "")
            multimedia = raw_item.get("multimedia", {})
            if (
                not image_url
                and isinstance(multimedia, dict)
                and multimedia.get("images")
            ):
                image_url = multimedia["images"][0].get("url", "")

            bathrooms = raw_item.get("bathrooms")
            bathrooms = int(bathrooms) if bathrooms else None

            suggested = raw_item.get("suggestedTexts", {})
            property_type = raw_item.get("propertyType") or (
                suggested.get("subtitle")
                if isinstance(suggested, dict) else None
            )

            images_list = (
                multimedia.get("images", [])
                if isinstance(multimedia, dict) else []
            )
            num_photos = raw_item.get("numPhotos") or (
                len(images_list) if images_list else None
            )

            price_per_sqm = raw_item.get("priceByArea")
            if not price_per_sqm and price and size:
                price_per_sqm = round(price / size, 2)

            # Features dict (dz_omar structured booleans)
            features = raw_item.get("features", {}) or {}

            air_conditioning = features.get("hasAirConditioning")
            terrace = features.get("hasTerrace")

            # Elevator from hasLift (top-level)
            elevator = raw_item.get("hasLift")
            if elevator is not None:
                elevator = bool(elevator)

            # Condition from status field
            _status_map = {
                "good": "good",
                "renew": "renovated",
                "newdevelopment": "new",
            }
            raw_status = raw_item.get("status")
            condition = _status_map.get(raw_status, raw_status or None)

            # Is private
            is_private = False
            if contact and isinstance(contact, dict):
                is_private = contact.get("userType") == "private"
            if not is_private:
                is_private = agent.lower() == "privato"

            # Dates (epoch ms -> ISO string)
            creation_date = None
            first_act = raw_item.get("firstActivationDate")
            if first_act and isinstance(first_act, (int, float)):
                creation_date = datetime.fromtimestamp(
                    first_act / 1000, tz=timezone.utc
                ).isoformat()

            title = (
                (
                    suggested.get("title")
                    if isinstance(suggested, dict) else ""
                )
                or f"{rooms or '?'}r {size or '?'}m\u00b2 - {address}"
            )

            return RawListing(
                source="idealista",
                url=url,
                title=title,
                price=price,
                rooms=rooms,
                size_sqm=size,
                address=address,
                floor=raw_item.get("floor"),
                description=raw_item.get("description") or "",
                image_url=image_url,
                agent=agent,
                phone=phone,
                published_date="",
                creation_date=creation_date,
                lat=float(lat) if lat else None,
                lon=float(lon) if lon else None,
                bathrooms=bathrooms,
                property_type=property_type,
                num_photos=num_photos,
                price_per_sqm=price_per_sqm,
                elevator=elevator,
                condition=condition,
                air_conditioning=air_conditioning,
                terrace=terrace,
                is_private=is_private,
                has_video=(
                    bool(raw_item.get("hasVideo"))
                    if raw_item.get("hasVideo") is not None
                    else False
                ),
                has_3d_tour=(
                    bool(raw_item.get("has3DTour"))
                    if raw_item.get("has3DTour") is not None
                    else False
                ),
            )
        except Exception as e:
            console.log(f"[red]Error normalizing: {e}[/red]")
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
