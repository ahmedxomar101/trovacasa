"""Telegram notification module — send alerts for new high-score listings."""

import asyncio
import json
import os
from datetime import datetime, timezone
from html import escape

import asyncpg
import httpx
from rich.console import Console

console = Console()

# Telegram API base
_API = "https://api.telegram.org/bot{token}/{method}"

# Notification thresholds
NOTIFY_MAX_PRICE = 1100
NOTIFY_MAX_PER_RUN = 20

# Sliding score threshold by listing age
# Newer listings get in easier, older need higher scores
NOTIFY_AGE_TIERS = [
    (6, 65),    # < 6 hours old → score >= 65
    (24, 70),   # 6-24 hours old → score >= 70
    (48, 80),   # 24-48 hours old → score >= 80
]
NOTIFY_MAX_AGE_HOURS = 48  # Hard cutoff — no notifications beyond this


def _get_token() -> str:
    """Get Telegram bot token from env."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in environment")
    return token


def _format_caption(listing: dict) -> str:
    """Format a listing as HTML caption for Telegram."""
    title = escape(listing.get("title") or listing.get("address") or "Listing")
    address = escape(listing.get("address") or "")

    # Price — show total if available, with condo breakdown
    price = listing.get("price")
    total_cost = listing.get("total_monthly_cost")
    condo = listing.get("condo_fees")
    if total_cost and condo and total_cost != price:
        price_str = f"\u20ac{int(total_cost):,}/mo (incl. \u20ac{int(condo)} condo)"
    elif total_cost:
        price_str = f"\u20ac{int(total_cost):,}/mo"
    elif price:
        price_str = f"\u20ac{price:,}/mo"
    else:
        price_str = "N/A"
    rooms = listing.get("rooms")
    size = listing.get("size_sqm")
    price_sqm = listing.get("price_per_sqm")

    size_parts = []
    if size:
        size_parts.append(f"{size} sqm")
    if rooms:
        size_parts.append(f"{rooms} room{'s' if rooms > 1 else ''}")
    floor = listing.get("floor")
    if floor:
        size_parts.append(f"Floor {escape(str(floor))}")
    size_str = " \u00b7 ".join(size_parts)

    # Metro
    station = listing.get("nearest_station") or ""
    commute = listing.get("commute_minutes")
    commute_str = f" \u00b7 {commute} min to office" if commute else ""

    # Price per sqm
    sqm_str = f" \u00b7 \u20ac{price_sqm:.0f}/m\u00b2" if price_sqm else ""

    # Energy class
    energy = listing.get("energy_class")
    energy_str = f"\n\u26a1 Energy class: {escape(str(energy))}" if energy else ""

    # Listing age with freshness tag
    creation = listing.get("creation_date") or listing.get("published_date")
    age_str = ""
    age_tag = ""
    if creation:
        try:
            created = datetime.fromisoformat(str(creation).replace("Z", "+00:00"))
            hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            if hours < 6:
                age_str = "Less than 6 hours ago"
                age_tag = "NEW"
            elif hours < 24:
                age_str = "Today"
                age_tag = "Today"
            elif hours < 48:
                age_str = "Yesterday"
                age_tag = "Yesterday"
            else:
                days = int(hours // 24)
                age_str = f"{days} days ago"
        except (ValueError, TypeError):
            pass

    # Agent
    agent = listing.get("agent") or ""
    is_privato = "privato" in agent.lower()
    agent_line = ""
    if is_privato:
        agent_line = "\n\U0001f464 <b>PRIVATO</b> (no agency fee)"
    elif agent:
        agent_line = f"\n\U0001f464 {escape(agent)}"

    # Hybrid score
    hybrid = listing.get("hybrid_score")
    score_str = f"{int(hybrid)}/100" if hybrid is not None else ""

    tag_prefix = f"[{age_tag}] " if age_tag else ""
    lines = [
        f"\U0001f3e0 <b>{tag_prefix}{title}</b>",
        "",
        f"\U0001f4b0 {price_str}",
        f"\U0001f4ca {price_sqm:.0f}/m\u00b2" if price_sqm else "",
        f"\U0001f4d0 {size_str}" if size_str else "",
        f"\U0001f687 {escape(station)}" if station else "",
        f"\U0001f6b6 Commute: {commute} min" if commute else "",
        energy_str.lstrip("\n") if energy_str else "",
        f"\U0001f4c5 Listed: {age_str}" if age_str else "",
        agent_line.lstrip("\n") if agent_line else "",
        "",
        f"\u2b50 <b>Score: {score_str}</b>" if score_str else "",
    ]

    return "\n".join(line for line in lines if line is not None)


def _build_keyboard(listing_id: str, url: str) -> dict:
    """Build inline keyboard with Save/Dismiss/View buttons."""
    return {
        "inline_keyboard": [[
            {"text": "\U0001f4be Save", "callback_data": f"fav:{listing_id[:12]}"},
            {"text": "\u2715 Dismiss", "callback_data": f"dis:{listing_id[:12]}"},
            {"text": "🔗 View", "url": url},
        ]]
    }


async def _send_to_chat(
    client: httpx.AsyncClient,
    token: str,
    chat_id: int,
    caption: str,
    keyboard: dict,
    image_url: str | None,
) -> bool:
    """Send a single listing notification to one chat. Returns True on success."""
    try:
        if image_url:
            resp = await client.post(
                _API.format(token=token, method="sendPhoto"),
                json={
                    "chat_id": chat_id,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                },
            )
            if resp.status_code != 200 or not resp.json().get("ok"):
                resp = await client.post(
                    _API.format(token=token, method="sendMessage"),
                    json={
                        "chat_id": chat_id,
                        "text": caption,
                        "parse_mode": "HTML",
                        "reply_markup": keyboard,
                    },
                )
        else:
            resp = await client.post(
                _API.format(token=token, method="sendMessage"),
                json={
                    "chat_id": chat_id,
                    "text": caption,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                },
            )
        return resp.json().get("ok", False)
    except Exception:
        return False


def _get_min_score_for_age(hours: float) -> int | None:
    """Return the minimum score threshold for a listing's age.

    Returns None if the listing is too old to notify.
    """
    if hours > NOTIFY_MAX_AGE_HOURS:
        return None
    for max_hours, min_score in NOTIFY_AGE_TIERS:
        if hours <= max_hours:
            return min_score
    return None


async def send_new_listings(
    pool: asyncpg.Pool,
    max_price: int = NOTIFY_MAX_PRICE,
    max_per_run: int = NOTIFY_MAX_PER_RUN,
) -> dict:
    """Send Telegram notifications for new high-score listings to all subscribers.

    Uses a sliding score threshold based on listing age:
    - < 6h old: score >= 65 (fresh listings get in easier)
    - 6-24h old: score >= 70
    - 24-48h old: score >= 80 (older listings need to be excellent)
    - 48h+: not notified

    Returns stats dict with counts.
    """
    token = _get_token()
    stats = {"sent": 0, "errors": 0, "skipped": 0, "subscribers": 0}

    # Get active subscribers
    subscribers = await pool.fetch(
        "SELECT chat_id, first_name FROM telegram_subscribers WHERE active = TRUE"
    )
    if not subscribers:
        console.print("[yellow]No active Telegram subscribers. Users need to /start the bot.[/]")
        return stats

    stats["subscribers"] = len(subscribers)
    console.print(f"[bold]Active subscribers: {len(subscribers)}[/]")

    # Get the lowest possible score threshold (for the broadest initial query)
    lowest_score = min(score for _, score in NOTIFY_AGE_TIERS)

    # Get candidate listings: unnotified, active, within max age, above lowest threshold
    rows = await pool.fetch(
        """SELECT id, source, url, title, address, price, rooms, size_sqm,
                  floor, image_url, metro_score, nearest_station, agent,
                  hybrid_score, commute_score, commute_minutes,
                  quality_score, scam_score, livability_score,
                  freshness_score, neighborhood_score,
                  condo_fees, condo_included, furnished, is_private,
                  total_monthly_cost, price_per_sqm, energy_class,
                  creation_date, published_date
           FROM listings
           WHERE notified_at IS NULL
             AND status = 'active'
             AND hybrid_score >= $1
             AND price <= $2
             AND creation_date IS NOT NULL
             AND creation_date::timestamptz >= NOW() - INTERVAL '%s hours'
           ORDER BY hybrid_score DESC
           LIMIT $3""" % NOTIFY_MAX_AGE_HOURS,
        float(lowest_score), max_price, max_per_run * 2,  # fetch extra, filter below
    )

    # Apply sliding threshold: filter by age-based score
    now = datetime.now(timezone.utc)
    qualified = []
    for row in rows:
        listing = dict(row)
        creation = listing.get("creation_date") or listing.get("published_date")
        if not creation:
            continue
        try:
            created = datetime.fromisoformat(str(creation).replace("Z", "+00:00"))
            hours = (now - created).total_seconds() / 3600
        except (ValueError, TypeError):
            continue

        min_score = _get_min_score_for_age(hours)
        if min_score is None:
            continue
        if listing["hybrid_score"] >= min_score:
            qualified.append(listing)

    # Sort by score DESC (best first)
    qualified.sort(key=lambda x: x["hybrid_score"], reverse=True)
    qualified = qualified[:max_per_run]

    if not qualified:
        console.print("[green]No new listings to notify about.[/]")
        return stats

    # Log tier breakdown
    tier_counts = {"<6h": 0, "6-24h": 0, "24-48h": 0}
    for listing in qualified:
        creation = listing.get("creation_date") or listing.get("published_date")
        try:
            created = datetime.fromisoformat(str(creation).replace("Z", "+00:00"))
            hours = (now - created).total_seconds() / 3600
            if hours < 6:
                tier_counts["<6h"] += 1
            elif hours < 24:
                tier_counts["6-24h"] += 1
            else:
                tier_counts["24-48h"] += 1
        except (ValueError, TypeError):
            pass
    console.print(
        f"[dim]Notification tiers: {tier_counts['<6h']} new (<6h), "
        f"{tier_counts['6-24h']} today (6-24h), {tier_counts['24-48h']} yesterday (24-48h)[/]"
    )

    console.print(f"[bold]Sending {len(qualified)} listings to {len(subscribers)} subscriber(s)...[/]")

    async with httpx.AsyncClient(timeout=30) as client:
        for listing in qualified:
            listing_id = listing["id"]
            caption = _format_caption(listing)
            keyboard = _build_keyboard(listing_id, listing.get("url", ""))
            image_url = listing.get("image_url")

            # Send to all subscribers
            all_ok = True
            for sub in subscribers:
                ok = await _send_to_chat(client, token, sub["chat_id"], caption, keyboard, image_url)
                if not ok:
                    all_ok = False
                    console.print(f"  [red]\u2717[/] Failed for chat_id={sub['chat_id']} ({sub['first_name']})")
                # Rate limit between subscribers
                await asyncio.sleep(0.3)

            if all_ok:
                await pool.execute(
                    "UPDATE listings SET notified_at = NOW() WHERE id = $1",
                    listing_id,
                )
                stats["sent"] += 1
                price_tag = f"\u20ac{listing.get('price', '?')}/mo"
                console.print(f"  [green]\u2713[/] {price_tag} {(listing.get('address') or '')[:35]}")
            else:
                stats["errors"] += 1

            # Rate limit between listings
            await asyncio.sleep(1)

    # Send digest summary to all subscribers
    total_active = await pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE status = 'active'"
    )
    top = qualified[0] if qualified else None  # first = highest score (DESC order)
    digest_lines = [
        f"<b>Pipeline notification summary</b>",
        f"Sent: {stats['sent']} alerts",
        f"Active listings: {total_active}",
    ]
    if top:
        digest_lines.append(
            f"Top pick: \u20ac{top.get('price', '?')}/mo | "
            f"{escape(top.get('address', '?')[:25])} | Score {int(top.get('hybrid_score', 0))}"
        )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for sub in subscribers:
                await client.post(
                    _API.format(token=token, method="sendMessage"),
                    json={
                        "chat_id": sub["chat_id"],
                        "text": "\n".join(digest_lines),
                        "parse_mode": "HTML",
                    },
                )
                await asyncio.sleep(0.3)
    except Exception:
        pass  # digest is best-effort

    console.print(f"\n[bold]Notification summary:[/] {stats['sent']} sent to {stats['subscribers']} subscribers, {stats['errors']} errors")
    return stats
