"""HTML report generator for Milan apartment listings."""

import asyncio
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .db import get_listings

OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "report.html"


def _esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _truncate(text: str | None, length: int = 200) -> tuple[str, bool]:
    if not text:
        return "", False
    text = text.strip()
    if len(text) <= length:
        return text, False
    return text[:length].rsplit(" ", 1)[0] + "...", True


def _budget_color(status: str | None) -> str:
    return {
        "tier1k": "#34c759",
        "tier1_1k": "#8ac926",
        "tier1_2k": "#f0c000",
        "tier1_3k": "#ff9500",
        "tier1_3k_plus": "#ff3b30",
    }.get(status or "", "#98989d")


def _score_bar(score: int | None, label: str) -> str:
    if score is None:
        return ""
    color = "#34c759" if score >= 70 else ("#ff9500" if score >= 40 else "#ff3b30")
    return f'<div class="score-row"><span class="score-label">{label}</span><div class="score-track"><div class="score-fill" style="width:{score}%;background:{color}"></div></div><span class="score-val">{score}</span></div>'


def _build_html(listings: list[dict]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total = len(listings)
    by_source: dict[str, int] = {}
    prices = []
    privato_count = 0
    scored_count = 0
    hybrid_scores = []
    budget_counts = {"tier1k": 0, "tier1_1k": 0, "tier1_2k": 0, "tier1_3k": 0, "tier1_3k_plus": 0, "unknown": 0}

    for li in listings:
        src = li.get("source") or "unknown"
        by_source[src] = by_source.get(src, 0) + 1
        if li.get("price"):
            prices.append(li["price"])
        agent = (li.get("agent") or "").lower()
        if "privato" in agent:
            privato_count += 1
        hs = li.get("hybrid_score")
        if hs is not None:
            scored_count += 1
            hybrid_scores.append(hs)
        bs = li.get("budget_status") or "unknown"
        budget_counts[bs] = budget_counts.get(bs, 0) + 1

    avg_price = int(sum(prices) / len(prices)) if prices else 0
    avg_hybrid = round(sum(hybrid_scores) / len(hybrid_scores), 1) if hybrid_scores else 0

    source_chips = " ".join(
        f'<span class="chip">{_esc(s)}: {c}</span>' for s, c in sorted(by_source.items())
    )

    _budget_meta = [
        ("tier1k", "#34c759", "\u22641k"),
        ("tier1_1k", "#8ac926", "1-1.1k"),
        ("tier1_2k", "#f0c000", "1.1-1.2k"),
        ("tier1_3k", "#ff9500", "1.2-1.3k"),
        ("tier1_3k_plus", "#ff3b30", ">1.3k"),
    ]
    budget_chips = ""
    for status, color, label in _budget_meta:
        cnt = budget_counts.get(status, 0)
        if cnt:
            budget_chips += f'<span class="chip budget-chip" style="background:{color};color:#fff;cursor:pointer" onclick="setBudgetFilter(\'{status}\')">{label}: {cnt}</span> '

    # --- Build listing cards ---
    cards_html = []
    for idx, li in enumerate(listings):
        image_url = li.get("image_url") or ""

        # Extract image gallery from raw_data
        gallery_urls = []
        raw_data = li.get("raw_data")
        if raw_data:
            try:
                rd = json.loads(raw_data)
                source = li.get("source", "")
                if source == "idealista":
                    mm = rd.get("multimedia", {})
                    if isinstance(mm, dict):
                        for img in mm.get("images", []):
                            if isinstance(img, dict) and img.get("url"):
                                gallery_urls.append(img["url"])
                elif source == "immobiliare":
                    media = rd.get("media", {})
                    if isinstance(media, dict):
                        for img in media.get("images", []):
                            if isinstance(img, dict):
                                gallery_urls.append(img.get("hd") or img.get("sd") or "")
                        for fp in media.get("floorPlans", []):
                            if isinstance(fp, dict):
                                gallery_urls.append(fp.get("hd") or fp.get("sd") or "")
                gallery_urls = [u for u in gallery_urls if u]
            except (json.JSONDecodeError, Exception):
                pass

        # Use first gallery image as main, or fall back to image_url
        main_image = gallery_urls[0] if gallery_urls else image_url
        has_gallery = len(gallery_urls) > 1

        if main_image:
            img_tag = f'<img src="{_esc(main_image)}" alt="Listing photo" loading="lazy" onerror="this.onerror=null;this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';">'
            placeholder_style = "display:none;"
        else:
            img_tag = ""
            placeholder_style = "display:flex;"

        # Encode gallery as JSON data attribute (only if has multiple images)
        gallery_attr = ""
        if has_gallery:
            gallery_json = json.dumps(gallery_urls, ensure_ascii=False)
            gallery_attr = f' data-gallery="{_esc(gallery_json)}"'

        price = li.get("price")
        price_str = f"&euro;{price:,}/mo" if price else "N/A"

        rooms = li.get("rooms")
        rooms_label = f"{rooms} rooms" if rooms else "?"
        size = li.get("size_sqm")
        size_label = f"{size} sqm" if size else "?"

        address = _esc(li.get("address") or "Address not available")

        # Hybrid score badge
        hybrid_score = li.get("hybrid_score")
        hybrid_display = ""
        if hybrid_score is not None:
            hs_int = int(round(hybrid_score))
            if hs_int >= 70:
                hs_class = "score-high"
            elif hs_int >= 40:
                hs_class = "score-mid"
            else:
                hs_class = "score-low"
            hybrid_display = f'<div class="hybrid-badge {hs_class}">{hs_int}</div>'

        # Budget status
        budget_status = li.get("budget_status")
        total_cost = li.get("total_monthly_cost")
        budget_html = ""
        if budget_status and budget_status != "unknown":
            bc = _budget_color(budget_status)
            cost_str = f"&euro;{int(total_cost):,}" if total_cost else "?"
            budget_html = f'<span class="budget-tag" style="background:{bc}">{cost_str}/mo</span>'
        elif price:
            budget_html = f'<span class="budget-tag" style="background:#98989d">&euro;{price:,} + ?</span>'

        # Condo fees
        condo_fees = li.get("condo_fees")
        condo_html = ""
        if condo_fees is not None:
            condo_included = li.get("condo_included")
            label = "incl." if condo_included else "extra"
            condo_html = f'<span class="detail-item">Condo: &euro;{int(condo_fees)} ({label})</span>'

        # Metro info
        metro_score = li.get("metro_score")
        station = _esc(li.get("nearest_station") or "")
        metro_html = ""
        if metro_score is not None:
            metro_html = f'<span class="detail-item">Metro: {metro_score} — {station}</span>'

        # Commute
        commute_min = li.get("commute_minutes")
        commute_html = ""
        if commute_min is not None:
            commute_html = f'<span class="detail-item">Commute: {commute_min} min</span>'

        # Neighborhood
        hood_name = li.get("neighborhood_name")
        hood_tier = ""
        hood_score = li.get("neighborhood_score")
        if hood_name:
            hood_tier = f'<span class="detail-item">Zone: {_esc(hood_name.title())}</span>'

        source = _esc(li.get("source") or "unknown")
        agent_raw = li.get("agent") or ""
        is_privato = "privato" in agent_raw.lower()
        if is_privato:
            agent_html = f'<span class="privato">{_esc(agent_raw)}</span>'
        else:
            agent_html = _esc(agent_raw) if agent_raw else "N/A"

        # Extra info line
        extras = []
        furnished = li.get("furnished")
        if furnished:
            extras.append(f"Furnished: {_esc(furnished)}")
        contract = li.get("contract_type")
        if contract:
            extras.append(f"Contract: {_esc(contract)}")
        deposit = li.get("deposit_months")
        if deposit:
            extras.append(f"Deposit: {deposit}mo")
        heating = li.get("heating")
        if heating:
            extras.append(f"Heating: {_esc(heating)}")
        energy = li.get("energy_class")
        if energy:
            extras.append(f"Energy: {_esc(energy)}")
        avail = li.get("available_from")
        if avail:
            extras.append(f"Available: {_esc(avail)}")
        extras_html = ""
        if extras:
            extras_html = '<div class="card-extras">' + " &middot; ".join(extras) + '</div>'

        # Score breakdown bars
        score_bars = ""
        cs = li.get("commute_score")
        ms = li.get("metro_score")
        ls = li.get("livability_score")
        ss = li.get("scam_score")
        fs = li.get("freshness_score")
        qs = li.get("quality_score")
        if hybrid_score is not None:
            score_bars = f'''<div class="score-breakdown">
                {_score_bar(cs, "Commute")}
                {_score_bar(ms, "Metro")}
                {_score_bar(ls, "Livability")}
                {_score_bar(ss, "Safety")}
                {_score_bar(fs, "Freshness")}
                {_score_bar(qs, "Quality")}
                {_score_bar(hood_score, "Hood")}
            </div>'''

        # Red flags
        red_flags_raw = li.get("red_flags")
        flags_html = ""
        if red_flags_raw:
            flags = red_flags_raw if isinstance(red_flags_raw, list) else []
            if isinstance(red_flags_raw, str):
                try:
                    flags = json.loads(red_flags_raw)
                except (json.JSONDecodeError, TypeError):
                    flags = []
            if flags:
                flags_html = '<div class="red-flags">Flags: ' + ", ".join(_esc(f) for f in flags) + '</div>'

        desc_full = li.get("description") or ""
        desc_short, was_truncated = _truncate(desc_full, 200)

        url = li.get("url") or "#"

        expand_block = ""
        if was_truncated:
            expand_block = f"""
            <div class="desc-full" id="desc-{idx}" style="display:none;">{_esc(desc_full)}</div>
            <button class="expand-btn" onclick="toggleDesc({idx})">Show more</button>
            """

        floor_raw = li.get("floor") or ""
        floor_str = _esc(floor_raw)
        floor_html = f'<span class="detail-item">Floor: {floor_str}</span>' if floor_str else ""

        # Floor badge on image
        floor_badge = ""
        if floor_raw:
            fl = floor_raw.strip().lower()
            if fl in ("bj", "ss", "sb", "b", "sb, 2"):
                floor_icon = "B"
                floor_tip = "Basement"
            elif fl in ("en", "g", "0"):
                floor_icon = "G"
                floor_tip = "Ground floor"
            elif fl == "m":
                floor_icon = "M"
                floor_tip = "Mezzanine"
            else:
                # Extract first number
                nums = [c for c in fl.split(",")[0].strip() if c.isdigit()]
                nums = ["".join(nums)] if nums else []
                if nums:
                    n = int(nums[0])
                    if n >= 8:
                        floor_icon = str(n)
                        floor_tip = f"Floor {n} (high)"
                    else:
                        floor_icon = str(n)
                        floor_tip = f"Floor {n}"
                else:
                    floor_icon = fl[:2].upper()
                    floor_tip = f"Floor: {floor_raw}"
            floor_badge = f'<div class="floor-badge" title="{_esc(floor_tip)}">{_esc(floor_icon)}</div>'

        listing_id = _esc(li.get("id") or "")

        card = f"""
        <div class="card"
             data-source="{source.lower()}"
             data-metro="{metro_score or 0}"
             data-price="{price or 999999}"
             data-privato="{1 if is_privato else 0}"
             data-hybrid="{hybrid_score or 0}"
             data-budget="{budget_status or 'unknown'}"
             data-scraped="{_esc(li.get('scraped_at') or '')}"
             data-created="{_esc(li.get('creation_date') or '')}"
             data-id="{listing_id}">
            <div class="card-header">
                {hybrid_display}
                {floor_badge}
                <div class="card-img"{gallery_attr} data-idx="0">
                    {img_tag}
                    <div class="placeholder" style="{placeholder_style}">No Image</div>
                    {'<button class="img-nav img-prev" onclick="navImg(this,-1)">&lsaquo;</button><button class="img-nav img-next" onclick="navImg(this,1)">&rsaquo;</button><div class="img-counter"></div>' if has_gallery else ''}
                </div>
            </div>
            <div class="card-body">
                <div class="card-top-row">
                    <div class="card-price">{price_str}</div>
                    {budget_html}
                </div>
                <div class="card-meta">
                    <span class="detail-item">{rooms_label}</span>
                    <span class="detail-item">{size_label}</span>
                    {floor_html}
                    {condo_html}
                </div>
                <div class="card-address">{address}</div>
                <div class="card-meta">
                    {metro_html}
                    {commute_html}
                    {hood_tier}
                </div>
                <div class="card-details">
                    <span class="source-badge source-{source.lower()}">{source}</span>
                    <span class="agent">{agent_html}</span>
                </div>
                {extras_html}
                {flags_html}
                {score_bars}
                <div class="card-desc">
                    <p class="desc-short">{_esc(desc_short)}</p>
                    {expand_block}
                </div>
                <a href="{_esc(url)}" target="_blank" rel="noopener" class="card-link">View listing &rarr;</a>
                <div class="card-id-row">
                    <span class="card-id-text">{listing_id}</span>
                    <button class="copy-id-btn" onclick="copyId('{listing_id}', this)" title="Copy listing ID">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                </div>
            </div>
        </div>
        """
        cards_html.append(card)

    all_cards = "\n".join(cards_html)

    source_options = "".join(
        f'<option value="{_esc(s.lower())}">{_esc(s)}</option>' for s in sorted(by_source.keys())
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Milan Apartment Finder</title>
<style>
:root {{
    --bg: #f5f5f7;
    --card-bg: #ffffff;
    --text: #1d1d1f;
    --text-secondary: #6e6e73;
    --border: #d2d2d7;
    --accent: #0071e3;
    --green: #34c759;
    --red: #ff3b30;
    --orange: #ff9500;
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-hover: 0 4px 12px rgba(0,0,0,0.12);
    --radius: 12px;
}}
@media (prefers-color-scheme: dark) {{
    :root {{
        --bg: #1c1c1e;
        --card-bg: #2c2c2e;
        --text: #f5f5f7;
        --text-secondary: #98989d;
        --border: #48484a;
        --shadow: 0 1px 3px rgba(0,0,0,0.3);
        --shadow-hover: 0 4px 12px rgba(0,0,0,0.4);
    }}
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    padding: 20px;
    max-width: 1400px;
    margin: 0 auto;
}}
h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 4px; }}
.subtitle {{ color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 20px; }}
.summary {{
    display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px;
}}
.stat-box {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 14px 20px;
    box-shadow: var(--shadow); min-width: 140px;
}}
.stat-box .stat-value {{ font-size: 1.5rem; font-weight: 700; }}
.stat-box .stat-label {{
    font-size: 0.8rem; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.5px;
}}
.chip {{
    display: inline-block; background: var(--accent); color: #fff;
    padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; margin-right: 4px;
}}
.filters {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: var(--radius) var(--radius) 0 0; padding: 16px 20px;
    border-bottom: none;
    box-shadow: none; display: flex; flex-wrap: wrap; gap: 16px; align-items: end;
}}
.filters-row2 {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 0 0 var(--radius) var(--radius); padding: 12px 20px; margin-bottom: 24px;
    box-shadow: var(--shadow); display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
}}
.filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
.filter-group label {{
    font-size: 0.75rem; font-weight: 600; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.5px;
}}
.filter-group select, .filter-group input[type="number"] {{
    padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--bg); color: var(--text); font-size: 0.9rem; min-width: 120px;
}}
.filter-group input[type="checkbox"] {{ width: 18px; height: 18px; margin-bottom: 4px; }}
.filter-group .toggle-row {{ display: flex; align-items: center; gap: 6px; height: 36px; }}
.visible-count {{ font-size: 0.85rem; color: var(--text-secondary); margin-left: auto; align-self: center; }}
.grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 20px;
}}
@media (max-width: 400px) {{ .grid {{ grid-template-columns: 1fr; }} }}
.card {{
    background: var(--card-bg); border: 1px solid var(--border);
    border-radius: var(--radius); overflow: hidden;
    box-shadow: var(--shadow); transition: box-shadow 0.2s, transform 0.2s;
    display: flex; flex-direction: column;
}}
.card:hover {{ box-shadow: var(--shadow-hover); transform: translateY(-2px); }}
.card.hidden {{ display: none; }}
.card-header {{ position: relative; }}
.hybrid-badge {{
    position: absolute; top: 10px; left: 10px; z-index: 2;
    width: 42px; height: 42px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1rem; color: #fff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}}
.floor-badge {{
    position: absolute; top: 10px; right: 10px; z-index: 2;
    min-width: 32px; height: 32px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 0.85rem; color: #fff;
    background: rgba(0,0,0,0.65); backdrop-filter: blur(4px);
    padding: 0 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    letter-spacing: 0.5px;
}}
.card-img {{
    width: 100%; height: 200px; overflow: hidden;
    background: var(--border); position: relative;
}}
.card-img img {{ width: 100%; height: 100%; object-fit: cover; transition: opacity 0.2s; }}
.img-nav {{
    position: absolute; top: 50%; transform: translateY(-50%);
    width: 32px; height: 32px; border-radius: 50%;
    background: rgba(0,0,0,0.5); color: #fff; border: none;
    font-size: 1.2rem; cursor: pointer; display: flex;
    align-items: center; justify-content: center; z-index: 3;
    opacity: 0; transition: opacity 0.2s;
    backdrop-filter: blur(4px);
}}
.card-img:hover .img-nav {{ opacity: 1; }}
.img-prev {{ left: 8px; }}
.img-next {{ right: 8px; }}
.img-nav:hover {{ background: rgba(0,0,0,0.75); }}
.img-counter {{
    position: absolute; bottom: 8px; right: 8px; z-index: 3;
    background: rgba(0,0,0,0.6); color: #fff; font-size: 0.7rem;
    padding: 2px 8px; border-radius: 10px;
    font-weight: 600; backdrop-filter: blur(4px);
}}
.card-img .placeholder {{
    width: 100%; height: 100%; display: flex; align-items: center;
    justify-content: center; color: var(--text-secondary);
    font-size: 0.9rem; background: var(--bg);
}}
.card-body {{
    padding: 16px; display: flex; flex-direction: column; gap: 8px; flex: 1;
}}
.card-top-row {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
.card-price {{ font-size: 1.3rem; font-weight: 700; color: var(--accent); }}
.budget-tag {{
    font-size: 0.75rem; font-weight: 700; color: #fff;
    padding: 2px 10px; border-radius: 20px;
}}
.card-meta {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.detail-item {{
    font-size: 0.82rem; color: var(--text-secondary);
    background: var(--bg); padding: 2px 8px; border-radius: 6px;
}}
.card-address {{ font-size: 0.9rem; color: var(--text); }}
.score-high {{ background: var(--green); }}
.score-mid {{ background: var(--orange); }}
.score-low {{ background: var(--red); }}
.card-details {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.source-badge {{
    font-size: 0.75rem; font-weight: 600; padding: 2px 10px;
    border-radius: 20px; text-transform: capitalize;
}}
.source-idealista {{ background: #ffe600; color: #1a1a1a; }}
.source-immobiliare {{ background: #e4002b; color: #fff; }}
.agent {{ font-size: 0.85rem; color: var(--text-secondary); }}
.privato {{ color: var(--green); font-weight: 600; }}
.card-extras {{
    font-size: 0.8rem; color: var(--text-secondary); line-height: 1.6;
}}
.red-flags {{
    font-size: 0.8rem; color: var(--red); font-weight: 500;
    padding: 4px 0;
}}
.score-breakdown {{
    display: flex; flex-direction: column; gap: 4px;
    padding: 8px 0;
}}
.score-row {{ display: flex; align-items: center; gap: 6px; }}
.score-label {{ font-size: 0.75rem; color: var(--text-secondary); width: 80px; text-align: right; }}
.score-track {{
    flex: 1; height: 8px; background: var(--bg);
    border-radius: 4px; overflow: hidden;
}}
.score-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
.score-val {{ font-size: 0.75rem; font-weight: 600; width: 24px; }}
.card-desc {{
    font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;
}}
.desc-full {{ margin-top: 4px; }}
.expand-btn {{
    background: none; border: none; color: var(--accent);
    font-size: 0.8rem; cursor: pointer; padding: 2px 0; font-weight: 500;
}}
.expand-btn:hover {{ text-decoration: underline; }}
.card-link {{
    display: inline-block; margin-top: auto; padding-top: 8px;
    color: var(--accent); text-decoration: none; font-weight: 500; font-size: 0.9rem;
}}
.card-link:hover {{ text-decoration: underline; }}
.time-btns {{ display: flex; gap: 4px; }}
.time-btn {{
    padding: 6px 12px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--bg); color: var(--text); font-size: 0.85rem;
    cursor: pointer; font-weight: 500; transition: all 0.15s;
}}
.time-btn:hover {{ border-color: var(--accent); }}
.time-btn.active {{
    background: var(--accent); color: #fff; border-color: var(--accent);
}}
.card-id-row {{
    display: flex; align-items: center; gap: 6px;
    padding-top: 8px; border-top: 1px solid var(--border); margin-top: 8px;
}}
.card-id-text {{
    font-size: 0.72rem; color: var(--text-secondary); font-family: monospace;
    letter-spacing: 0.5px; opacity: 0.6;
}}
.copy-id-btn {{
    display: inline-flex; align-items: center;
    background: none; border: 1px solid var(--border); border-radius: 5px;
    color: var(--text-secondary); padding: 2px 5px;
    cursor: pointer; transition: all 0.15s;
}}
.copy-id-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
.copy-id-btn.copied {{ border-color: var(--green); color: var(--green); }}
.no-results {{
    text-align: center; padding: 60px 20px;
    color: var(--text-secondary); font-size: 1.1rem; display: none;
}}
</style>
</head>
<body>

<h1>Milan Apartment Finder</h1>
<p class="subtitle">Report generated {generated_at} &mdash; sorted by hybrid score</p>

<div class="summary">
    <div class="stat-box">
        <div class="stat-value">{total}</div>
        <div class="stat-label">Total Listings</div>
    </div>
    <div class="stat-box">
        <div class="stat-value">&euro;{avg_price:,}</div>
        <div class="stat-label">Avg Price/mo</div>
    </div>
    <div class="stat-box">
        <div class="stat-value">{avg_hybrid}</div>
        <div class="stat-label">Avg Hybrid Score</div>
    </div>
    <div class="stat-box">
        <div class="stat-value">{privato_count}</div>
        <div class="stat-label">Privato</div>
    </div>
    <div class="stat-box">
        <div class="stat-label">By Source</div>
        <div style="margin-top:4px;">{source_chips}</div>
    </div>
    <div class="stat-box">
        <div class="stat-label">Budget</div>
        <div style="margin-top:4px;">{budget_chips}</div>
    </div>
</div>

<div class="filters">
    <div class="filter-group">
        <label>Source</label>
        <select id="f-source" onchange="applyFilters()">
            <option value="all">All</option>
            {source_options}
        </select>
    </div>
    <div class="filter-group">
        <label>Min Hybrid Score</label>
        <input type="number" id="f-hybrid" min="0" max="100" value="0" onchange="applyFilters()" oninput="applyFilters()">
    </div>
    <div class="filter-group">
        <label>Max Price (&euro;/mo)</label>
        <input type="number" id="f-price" min="0" step="50" value="" placeholder="Any" onchange="applyFilters()" oninput="applyFilters()">
    </div>
    <div class="filter-group">
        <label>Budget</label>
        <select id="f-budget" onchange="applyFilters()">
            <option value="all">All</option>
            <option value="tier1k">&le;1,000/mo</option>
            <option value="tier1_1k">1,000-1,100/mo</option>
            <option value="tier1_2k">1,100-1,200/mo</option>
            <option value="tier1_3k">1,200-1,300/mo</option>
            <option value="tier1_3k_plus">&gt;1,300/mo</option>
        </select>
    </div>
    <div class="filter-group">
        <label>Privato Only</label>
        <div class="toggle-row">
            <input type="checkbox" id="f-privato" onchange="applyFilters()">
        </div>
    </div>
    <span class="visible-count" id="visible-count"></span>
</div>

<div class="filters-row2">
    <div class="filter-group">
        <label>Listed Within</label>
        <div class="time-btns">
            <button class="time-btn active" onclick="setTimeFilter(0, this)">All</button>
            <button class="time-btn" onclick="setTimeFilter(1, this)">1d</button>
            <button class="time-btn" onclick="setTimeFilter(3, this)">3d</button>
            <button class="time-btn" onclick="setTimeFilter(7, this)">7d</button>
            <button class="time-btn" onclick="setTimeFilter(14, this)">14d</button>
        </div>
    </div>
    <div class="filter-group">
        <label>Sort By</label>
        <select id="f-sort" onchange="sortCards()">
            <option value="hybrid">Hybrid Score</option>
            <option value="price-asc">Price (low)</option>
            <option value="price-desc">Price (high)</option>
            <option value="commute">Commute</option>
        </select>
    </div>
</div>

<div class="no-results" id="no-results">No listings match the current filters.</div>

<div class="grid" id="grid">
{all_cards}
</div>

<script>
function toggleDesc(idx) {{
    var full = document.getElementById('desc-' + idx);
    if (!full) return;
    var short = full.parentElement.querySelector('.desc-short');
    var btn = full.nextElementSibling;
    if (full.style.display === 'none') {{
        full.style.display = 'block';
        if (short) short.style.display = 'none';
        if (btn) btn.textContent = 'Show less';
    }} else {{
        full.style.display = 'none';
        if (short) short.style.display = '';
        if (btn) btn.textContent = 'Show more';
    }}
}}

function toggleScores(idx) {{
    var el = document.getElementById('scores-' + idx);
    if (!el) return;
    var btn = el.nextElementSibling;
    if (el.style.display === 'none') {{
        el.style.display = 'flex';
        if (btn) btn.textContent = 'Hide scores';
    }} else {{
        el.style.display = 'none';
        if (btn) btn.textContent = 'Show scores';
    }}
}}

var currentTimeDays = 0;

function setTimeFilter(days, btn) {{
    currentTimeDays = days;
    document.querySelectorAll('.time-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    applyFilters();
}}

function isWithinDays(dateStr, days) {{
    if (!days || !dateStr) return true;
    try {{
        var d = new Date(dateStr);
        if (isNaN(d.getTime())) return true;
        var cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        return d >= cutoff;
    }} catch(e) {{ return true; }}
}}

function applyFilters() {{
    var source = document.getElementById('f-source').value;
    var minHybrid = parseFloat(document.getElementById('f-hybrid').value) || 0;
    var maxPriceVal = document.getElementById('f-price').value;
    var maxPrice = maxPriceVal ? parseInt(maxPriceVal) : Infinity;
    var privatoOnly = document.getElementById('f-privato').checked;
    var budgetFilter = document.getElementById('f-budget').value;

    var cards = document.querySelectorAll('.card');
    var visible = 0;
    cards.forEach(function(card) {{
        var show = true;
        if (source !== 'all' && card.dataset.source !== source) show = false;
        if (parseFloat(card.dataset.hybrid) < minHybrid) show = false;
        if (parseInt(card.dataset.price) > maxPrice) show = false;
        if (privatoOnly && card.dataset.privato !== '1') show = false;
        if (budgetFilter !== 'all' && card.dataset.budget !== budgetFilter) show = false;
        if (currentTimeDays > 0) {{
            var dateStr = card.dataset.created || card.dataset.scraped;
            if (!isWithinDays(dateStr, currentTimeDays)) show = false;
        }}

        if (show) {{ card.classList.remove('hidden'); visible++; }}
        else {{ card.classList.add('hidden'); }}
    }});

    document.getElementById('visible-count').textContent = visible + ' of ' + cards.length + ' shown';
    document.getElementById('no-results').style.display = visible === 0 ? 'block' : 'none';
}}

function sortCards() {{
    var grid = document.getElementById('grid');
    var cards = Array.from(grid.querySelectorAll('.card'));
    var sortBy = document.getElementById('f-sort').value;

    cards.sort(function(a, b) {{
        if (sortBy === 'hybrid') return parseFloat(b.dataset.hybrid) - parseFloat(a.dataset.hybrid);
        if (sortBy === 'price-asc') return parseInt(a.dataset.price) - parseInt(b.dataset.price);
        if (sortBy === 'price-desc') return parseInt(b.dataset.price) - parseInt(a.dataset.price);
        if (sortBy === 'commute') return parseFloat(b.dataset.hybrid) - parseFloat(a.dataset.hybrid);
        return 0;
    }});

    cards.forEach(function(card) {{ grid.appendChild(card); }});
    applyFilters();
}}

function setBudgetFilter(status) {{
    var sel = document.getElementById('f-budget');
    sel.value = (sel.value === status) ? 'all' : status;
    applyFilters();
}}

function preloadAhead(gallery, idx, count) {{
    for (var i = 1; i <= count; i++) {{
        var next = (idx + i) % gallery.length;
        var img = new Image();
        img.src = gallery[next];
    }}
}}
function navImg(btn, dir) {{
    var container = btn.closest('.card-img');
    var galleryStr = container.dataset.gallery;
    if (!galleryStr) return;
    var gallery = JSON.parse(galleryStr);
    var idx = parseInt(container.dataset.idx) || 0;
    idx = (idx + dir + gallery.length) % gallery.length;
    container.dataset.idx = idx;
    var img = container.querySelector('img');
    if (img) {{
        img.style.opacity = '0.5';
        var newImg = new Image();
        newImg.onload = function() {{ img.src = gallery[idx]; img.style.opacity = '1'; }};
        newImg.onerror = function() {{ img.style.opacity = '1'; }};
        newImg.src = gallery[idx];
    }}
    var counter = container.querySelector('.img-counter');
    if (counter) counter.textContent = (idx + 1) + ' / ' + gallery.length;
    preloadAhead(gallery, idx, 2);
}}
// Init counters for galleries
document.querySelectorAll('.card-img[data-gallery]').forEach(function(el) {{
    var gallery = JSON.parse(el.dataset.gallery);
    var counter = el.querySelector('.img-counter');
    if (counter) counter.textContent = '1 / ' + gallery.length;
}});

function copyId(id, btn) {{
    navigator.clipboard.writeText(id).then(function() {{
        btn.classList.add('copied');
        var idText = btn.parentElement.querySelector('.card-id-text');
        if (idText) {{ var orig = idText.textContent; idText.textContent = 'Copied!'; idText.style.opacity = '1';
            setTimeout(function() {{ btn.classList.remove('copied'); idText.textContent = orig; idText.style.opacity = ''; }}, 1500);
        }}
    }});
}}

applyFilters();
</script>
</body>
</html>"""


async def generate_report(pool) -> Path:
    """Generate the HTML report and write it to disk."""
    listings = await get_listings(pool, min_score=0, sort_by="hybrid_score")
    html_content = _build_html(listings)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html_content, encoding="utf-8")

    print(f"Report generated: {OUTPUT_FILE.resolve()}")
    print(f"  {len(listings)} listings included")
    return OUTPUT_FILE


def main() -> None:
    async def _run():
        from .db import create_pool
        pool = await create_pool()
        try:
            await generate_report(pool)
        finally:
            await pool.close()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
