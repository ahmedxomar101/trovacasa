"""Extract structured data from Italian apartment listings using OpenAI structured output."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field

# Defaults — overridden by settings when called from batch_extract
LLM_MODEL = "gpt-5-mini"
LLM_MAX_RETRIES = 4

# --- Logging setup ---
_LOG_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("llm_extract")
_logger.setLevel(logging.DEBUG)

if not _logger.handlers:
    _fh = logging.FileHandler(_LOG_DIR / "llm_extract.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_fh)


# ── Pydantic schema for structured output ──

class ListingExtraction(BaseModel):
    condo_fees: int | None = Field(None, description="Monthly condominium fees in EUR (numeric only, e.g. 150). Look for 'spese condominiali', 'community costs', or amounts near 'spese'.")
    condo_included_in_rent: bool | None = Field(None, description="True if rent explicitly includes condo fees ('spese incluse', 'comprensivo di spese'). False if separate. Null if unclear.")
    available_from: str | None = Field(None, description="When the apartment is available. Use YYYY-MM-DD for exact dates. Use first of month if only month given (e.g. 'da maggio' → '2026-05-01'). Use 'immediate' for 'subito'/'immediata'/'libero subito'. Null if not mentioned.")
    furnished: str | None = Field(None, description="Furnishing status. 'full' = arredato/completamente arredato/ammobiliato/furnished. 'partial' = semi-arredato/parzialmente arredato. 'no' = non arredato/vuoto/unfurnished. Null if not mentioned.")
    contract_type: str | None = Field(None, description="Rental contract type as stated: '4+4', '3+2', 'transitorio', 'cedolare secca', 'contratto libero', '12 mesi', etc. Null if not mentioned.")
    deposit_months: int | None = Field(None, description="Security deposit in number of months (e.g. 3 for 'cauzione di 3 mesi' or '3 month deposit'). Null if not mentioned.")
    elevator: bool | None = Field(None, description="True if 'con ascensore'/'with lift'/'has elevator'. False if 'senza ascensore'/'no lift'. Null if not mentioned.")
    balcony: bool | None = Field(None, description="True if 'balcone'/'terrazzo'/'terrazzino'/'balcony'/'terrace' present. False if explicitly absent. Null if not mentioned.")
    heating: str | None = Field(None, description="Heating type. 'autonomous' = autonomo/individual. 'centralized' = centralizzato/central. Null if not mentioned.")
    heating_fuel: str | None = Field(None, description="Heating fuel/energy source: 'natural gas', 'propane/butane', 'electric', 'heat pump', 'district heating', etc. Look for 'gas naturale', 'metano', 'gas propano/butano', 'pompa di calore'. Null if not mentioned.")
    air_conditioning: bool | None = Field(None, description="True if 'aria condizionata'/'air conditioning' present. False if explicitly absent. Null if not mentioned.")
    condition: str | None = Field(None, description="Property condition. 'renovated' = ristrutturato/nuovo/refurbished. 'good' = buono stato/buone condizioni/good condition. 'needs-work' = da ristrutturare/da rinnovare. Null if not mentioned.")
    building_age: str | None = Field(None, description="Year or decade the building was constructed. Extract from 'Costruito nel XXXX' or 'Built in XXXX'. Return as string: '1900', '1960', 'anni 60', etc. Null if not mentioned.")
    energy_class: str | None = Field(None, description="Energy efficiency class as a single letter: A, B, C, D, E, F, or G. Extract from 'Classe energetica' or 'Energy class'. Null if unknown or not mentioned.")
    orientation: str | None = Field(None, description="Apartment orientation/facing direction. Extract from 'Orientamento' or 'Orientation'. Return as comma-separated directions: 'east, west', 'south', 'north, east', etc. Null if not mentioned.")
    is_private: bool | None = Field(None, description="True if the listing is from a private owner (privato), not an agency. False if from an agency/professional. Null if unclear.")
    agency_fee: str | None = Field(None, description="Agency/broker fee description if mentioned (e.g. 'provvigione 1 mese', 'no spese agenzia'). Null if not mentioned.")
    floor_level: str | None = Field(None, description="The floor level of the apartment. Use these exact values: 'basement' (seminterrato/interrato/cantina), 'ground' (piano terra/pianterreno), 'mezzanine' (ammezzato/rialzato/mezzanino), or a number ('1', '2', '3', etc.). If 'ultimo piano'/'last floor'/'top floor' is mentioned, return the floor number if given, otherwise return 'last'. Null if not mentioned.")
    is_last_floor: bool | None = Field(None, description="True if the listing explicitly mentions 'ultimo piano', 'last floor', 'top floor', 'attico', or 'penthouse'. False if there are floors above. Null if not mentioned.")
    red_flags: list[str] = Field(default_factory=list, description="List of concerning phrases found in the listing. Be STRICT. Include: discriminatory language ('no stranieri', 'solo italiani'), restrictive demands ('solo referenziati', 'solo lavoratori dipendenti', 'no animali', 'no fumatori'), suspicious patterns (price too low, money upfront, contact only via WhatsApp), vague descriptions hiding problems. Return empty list [] ONLY if genuinely no concerns.")
    additional_costs: str | None = Field(None, description="Any costs beyond rent and condo fees: utilities (utenze), TARI, electricity, water, heating supplements, garage, etc. Describe what is excluded or extra. Null if everything is included or not mentioned.")


SYSTEM_PROMPT = """\
You are an expert at extracting structured data from Italian apartment rental listings.

You will receive ALL available data for a listing: structured fields from the platform API AND the free-text description written by the advertiser.

Your task: extract every field in the output schema as completely and accurately as possible, using ALL sources.

General rules:
- Use null ONLY when a field is genuinely not mentioned anywhere in the data.
- Do NOT skip fields that are clearly present — check both structured data AND description.
- When structured data and description conflict, prefer structured data (it comes from the platform).
- When the description adds detail not in structured data, use it (e.g. contract type, availability date).
- Be conservative on ambiguous fields but aggressive on red flags.

Each output field has a detailed description in the schema — follow those instructions precisely for format and allowed values.
"""

MODEL = LLM_MODEL


def _strip_bloat(data: dict, strip_keys: set[str] | None = None) -> dict:
    """Deep-copy a dict, removing large useless keys (images, tracking, etc.)."""
    if strip_keys is None:
        strip_keys = {
            "multimedia", "comments", "savedAd", "ribbons", "labels",
            "tracking", "detailWebLink", "link", "media",
            "allowsCounterOffers", "allowsMortgageSimulator",
            "allowsProfileQualification", "allowsRecommendation",
            "allowsRemoteVisit", "showSuggestedPrice",
            "preferenceHighlight", "topHighlight", "topNewDevelopment",
            "topPlus", "urgentVisualHighlight", "visualHighlight",
            "newDevelopmentHighlight", "isOnlineBookingActive",
            "mortgage", "aiSettings", "badge",
        }
    result = {}
    for k, v in data.items():
        if k in strip_keys:
            continue
        if isinstance(v, dict):
            result[k] = _strip_bloat(v, strip_keys)
        else:
            result[k] = v
    return result


def build_clean_context(item: dict) -> str:
    """Build full context from all available listing data for the LLM.

    Sends the complete raw API data (minus image URLs and tracking bloat)
    so the LLM has maximum information to extract from.
    """
    cleaned = _strip_bloat(item)
    description = item.get("description") or item.get("_details", {}).get("propertyComment", "")

    parts = []
    parts.append("=== FULL API DATA ===")
    parts.append(json.dumps(cleaned, indent=2, ensure_ascii=False, default=str))

    if description:
        parts.append(f"\n=== DESCRIPTION ===\n{description}")

    return "\n".join(parts)


def build_immobiliare_context(item: dict) -> str:
    """Build full context from immobiliare.it (memo23) raw data for the LLM.

    Sends the complete raw API data (minus image URLs and tracking bloat)
    so the LLM has maximum information to extract from.
    """
    cleaned = _strip_bloat(item)

    # Extract description text
    desc_obj = item.get("description", {})
    description = ""
    if isinstance(desc_obj, dict):
        description = desc_obj.get("content", "") or desc_obj.get("caption", "") or ""
    elif isinstance(desc_obj, str):
        description = desc_obj

    parts = []
    parts.append("=== FULL API DATA ===")
    parts.append(json.dumps(cleaned, indent=2, ensure_ascii=False, default=str))

    if description:
        parts.append(f"\n=== DESCRIPTION ===\n{description}")

    return "\n".join(parts)


def build_description_only_context(description: str, listing_meta: dict | None = None) -> str:
    """Build context from description + basic metadata only (no _details).

    Fallback for listings without fetchDetails data.
    """
    parts = []
    if listing_meta:
        lines = []
        for k, v in listing_meta.items():
            if v is not None and k != "id":
                lines.append(f"- {k}: {v}")
        if lines:
            parts.append("Listing info:\n" + "\n".join(lines))
    parts.append(f"Description:\n{description}")
    return "\n\n".join(parts)


def _call_openai(client: OpenAI, user_msg: str, listing_meta: dict | None = None) -> dict:
    """Make a single OpenAI API call with structured output and log the result."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format=ListingExtraction,
    )

    result = completion.choices[0].message.parsed
    usage = completion.usage

    # Build listing context for log
    meta_str = ""
    if listing_meta:
        meta_str = "\n>>> LISTING CONTEXT >>>\n" + "\n".join(
            f"  {k}: {v}" for k, v in listing_meta.items() if v is not None
        ) + "\n"

    # Log full request/response
    result_dict = result.model_dump() if result else {}
    _logger.debug(
        "\n%s\n%s\n%s"
        ">>> SYSTEM PROMPT >>>\n%s\n\n"
        ">>> USER MESSAGE >>>\n%s\n\n"
        ">>> LLM OUTPUT >>>\n%s\n\n"
        ">>> TOKENS: input=%s output=%s total=%s\n",
        "=" * 60, ts, meta_str,
        SYSTEM_PROMPT, user_msg,
        json.dumps(result_dict, indent=2, ensure_ascii=False),
        usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
    )

    return result_dict


def extract_from_listing(item: dict, listing_meta: dict | None = None) -> dict:
    """Extract structured data from a listing with full context (description + _details).

    This is the primary extraction method for listings scraped with fetchDetails=True.
    """
    user_msg = build_clean_context(item)
    return _extract_with_retry(user_msg, listing_meta)


def extract_from_immobiliare(item: dict, listing_meta: dict | None = None) -> dict:
    """Extract structured data from an immobiliare.it listing (memo23 raw data).

    Uses the immobiliare-specific context builder that reads costs[], mainData[],
    analytics, etc.
    """
    user_msg = build_immobiliare_context(item)
    return _extract_with_retry(user_msg, listing_meta)


def extract_from_description(description: str, listing_meta: dict | None = None) -> dict:
    """Extract structured data from description + basic metadata only.

    Fallback for listings without fetchDetails data (e.g. immobiliare).
    """
    if not description or not description.strip():
        return ListingExtraction().model_dump()

    user_msg = build_description_only_context(description, listing_meta)
    return _extract_with_retry(user_msg, listing_meta)


def _extract_with_retry(user_msg: str, listing_meta: dict | None = None) -> dict:
    """Run extraction with exponential backoff retry."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    max_retries = LLM_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            return _call_openai(client, user_msg, listing_meta)
        except Exception as e:
            _logger.debug(
                "\n%s\n>>> ERROR (attempt %d/%d) >>>\n%s\n",
                "=" * 60, attempt + 1, max_retries, str(e),
            )
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                is_rate_limit = "rate_limit" in str(e).lower() or "429" in str(e)
                if is_rate_limit:
                    wait = max(wait, 5)
                _logger.debug("  Retrying in %ds...", wait)
                time.sleep(wait)

    _logger.debug("\n>>> FAILED after %d attempts\n", max_retries)
    return ListingExtraction().model_dump()
