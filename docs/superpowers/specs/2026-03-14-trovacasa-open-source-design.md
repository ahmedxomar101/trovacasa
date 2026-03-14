# TrovaCasa — Open-Source Refactor Design

**Date:** 2026-03-14
**Status:** Approved
**Scope:** Refactor milan-finder into TrovaCasa, an open-source, AI-powered apartment finder for Italian cities.

---

## 1. Overview

TrovaCasa is an open-source tool that helps people find apartments in Italian cities. It scrapes listings from Italian rental platforms (idealista, immobiliare.it), enriches them with LLM extraction, scores them across 7 configurable dimensions, and delivers results via Telegram notifications and a Next.js dashboard.

The project ships ready-to-use with working scrapers, a full scoring suite, and city data for Milan and Rome. Users configure it to their needs via a YAML config file — manually, or with AI-assisted setup prompts for Claude Code / Cursor.

### Design Goals

- **Works out of the box** for Milan and Rome with minimal setup (just API keys + config)
- **Configurable** — budget, commute, scoring weights, thresholds, scrapers all user-controlled
- **Extensible** — clean protocols for adding scrapers, scorers, and cities without touching core code
- **AI-assisted setup** — prompt files that walk users through configuration via their coding assistant

### Non-Goals

- Supporting non-Italian platforms or non-apartment use cases (jobs, cars, etc.)
- Supporting LLM providers other than OpenAI (may come later)
- Dynamic plugin loading or a plugin registry CLI
- A web-based configuration UI

---

## 2. Project Structure

```
trovacasa/
├── config.example.yaml              # Fully commented template
├── config.yaml                      # User's config (gitignored)
├── .env.example                     # Required env vars template
├── .env                             # User's env vars (gitignored)
├── ai-setup/
│   ├── README.md                    # Explains the 3 setup paths
│   ├── config-builder.md            # Builds config.yaml interactively
│   ├── city-builder.md              # Builds metro.json + neighborhoods.json
│   └── scoring-builder.md           # Customizes scoring config or adds scorers
├── pipeline/
│   ├── pyproject.toml
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                  # Pipeline orchestrator
│   │   ├── config.py                # Pydantic config loader
│   │   ├── models.py                # Shared models (RawListing, ScoreResult, etc.)
│   │   ├── db.py                    # asyncpg + Supabase
│   │   ├── dedup.py                 # Address normalization + fuzzy matching
│   │   ├── run_tracker.py           # Pipeline run history
│   │   ├── report.py                # HTML report generator
│   │   ├── gallery.py               # Image gallery fetcher
│   │   ├── scrapers/
│   │   │   ├── __init__.py          # SCRAPER_REGISTRY dict
│   │   │   ├── base.py              # BaseScraper protocol
│   │   │   ├── idealista.py         # Apify idealista scraper
│   │   │   └── immobiliare.py       # Apify immobiliare scraper
│   │   ├── enrichment/
│   │   │   ├── llm_extract.py       # OpenAI structured extraction
│   │   │   └── batch_extract.py     # Parallel batch processing
│   │   ├── scoring/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # BaseScorer protocol (imports ScoreResult from models.py)
│   │   │   ├── registry.py          # Discovers & loads enabled scorers
│   │   │   ├── pipeline.py          # Iterates scorers, computes hybrid
│   │   │   ├── commute.py           # Transit commute time
│   │   │   ├── metro.py             # Metro proximity + preferred line
│   │   │   ├── livability.py        # Apartment comfort factors
│   │   │   ├── quality.py           # Listing quality signals
│   │   │   ├── scam.py              # Scam risk detection
│   │   │   ├── freshness.py         # Listing age
│   │   │   └── neighborhood.py      # Zone tier classification
│   │   └── telegram/
│   │       ├── notify.py            # Telegram alerts
│   │       └── callback_handler.py  # Button press handler
│   └── data/
│       └── cities/
│           ├── README.md            # Schema docs for adding a city
│           ├── milan/
│           │   ├── metro.json
│           │   └── neighborhoods.json
│           └── rome/
│               ├── metro.json
│               └── neighborhoods.json
├── web/                             # Next.js dashboard (unchanged structure)
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql
└── docs/
```

---

## 3. Config System

### config.yaml

Single YAML file, validated by a Pydantic `Settings` model. All pipeline behavior flows from this file.

```yaml
# --- Profile ---
city: milan                        # Maps to data/cities/{city}/
budget:
  max_rent: 1100
  currency: EUR

apartment:
  min_size_sqm: 40
  rooms: [2, 3]               # Pipeline-level filter (applied after scraping)
  bedrooms: [1, 2, 3]         # Scraper-level filter (passed to Apify actor query params)

# --- Commute ---
commute:
  destination:
    lat: 45.4565
    lon: 9.1525
    name: "Your Destination"
  preferred_line: M5              # Optional — metro scorer boosts proximity score
                                   # for stations on this line (replaces hardcoded M5 priority)

# --- Scrapers ---
scrapers:
  idealista:
    enabled: true
    actor_id: "dz_omar/idealista-scraper"
    location_id: "0-EU-IT-MI-01-001-135"
    max_items: 400
    timeout_secs: 1900
  immobiliare:
    enabled: true
    actor_id: "memo23/immobiliare-scraper"
    max_items: 400
    timeout_secs: 1200
    zones:
      - { lat: "45.510", lon: "9.190", zoom: 14, name: "North" }
      - { lat: "45.485", lon: "9.190", zoom: 14, name: "Central-North" }
      - { lat: "45.460", lon: "9.190", zoom: 14, name: "Central" }
      - { lat: "45.470", lon: "9.145", zoom: 14, name: "West" }
      - { lat: "45.470", lon: "9.230", zoom: 14, name: "East" }
      - { lat: "45.435", lon: "9.190", zoom: 14, name: "South" }

# --- Scoring ---
scoring:
  weights:
    commute: 0.30
    metro: 0.20
    livability: 0.15
    freshness: 0.15
    scam: 0.10
    quality: 0.10
  # Optional per-scorer threshold overrides
  livability:
    elevator: { "yes": 80, "no_high_floor": 30, "no_low_floor": 70 }
    furnished: { "full": 90, "partial": 70, "no": 50, "unknown": 60 }
    energy_class: { "A": 100, "B": 100, "C": 70, "D": 70, "E": 40, "F": 40, "G": 20, "unknown": 50 }
    condition: { "renovated": 100, "new": 100, "good": 70, "needs_work": 30, "unknown": 50 }
    heating: { "autonomous": 80, "centralized": 50, "unknown": 60 }
    balcony: { "yes": 80, "no": 40, "unknown": 60 }
    floor: { "basement": 20, "ground": 40, "mezzanine": 40, "low": 50, "mid": 70, "high": 80 }
    # Note: floor score interacts with elevator — high floor without elevator
    # is penalized in the scorer logic, not in these base thresholds

# --- Notifications ---
telegram:
  enabled: true
  score_thresholds:
    fresh_6h: 65
    day_old: 70
    two_day: 80

# --- LLM ---
llm:
  model: "gpt-5-mini"
  max_workers: 15
  max_retries: 4
```

### Config Loader (config.py)

Pydantic `Settings` model that:
- Reads `config.yaml` from repo root (not `pipeline/` — path resolved via `Path(__file__).parents[3]`)
- Validates all fields with types and constraints
- Validates that scoring weights sum to 1.0
- Provides typed access: `settings.budget.max_rent`, `settings.scoring.weights["commute"]`
- Falls back to sensible defaults where possible
- Raises clear errors on missing required fields (city, commute destination, at least one scraper enabled)

### Config Sub-Models

The `Settings` model contains nested Pydantic models used as typed parameters throughout the codebase:

```python
class ScraperConfig(BaseModel):
    """Passed to BaseScraper.scrape(). Each scraper gets its own config block."""
    enabled: bool = True
    actor_id: str
    max_items: int = 400
    timeout_secs: int = 1200
    # Scraper-specific fields passed through as extra kwargs
    model_config = ConfigDict(extra="allow")

class ScoringConfig(BaseModel):
    """Passed to BaseScorer.score() and get_active_scorers()."""
    weights: dict[str, float]              # scorer_name -> weight (must sum to 1.0)
    commute: CommuteConfig | None = None   # destination, preferred_line
    overrides: dict[str, dict] = {}        # per-scorer threshold overrides
    city_data_path: Path                   # resolved path to data/cities/{city}/

class CommuteConfig(BaseModel):
    destination: Coordinates
    preferred_line: str | None = None      # boosts metro proximity for this line
```

These are defined in `config.py` alongside the root `Settings` model.

### Environment Variables (.env)

```
APIFY_API_TOKEN=
OPENAI_API_KEY=
SUPABASE_DB_URL=
TELEGRAM_BOT_TOKEN=     # Optional
TELEGRAM_CHAT_ID=       # Optional
```

---

## 4. Scraper Protocol

### BaseScraper

```python
# scrapers/base.py
from typing import Protocol, runtime_checkable
from src.models import RawListing

@runtime_checkable
class BaseScraper(Protocol):
    name: str

    async def scrape(self, config: ScraperConfig) -> list[RawListing]:
        """Run the scraper and return normalized listings."""
        ...

    def normalize(self, raw_item: dict) -> RawListing:
        """Convert a single raw API response into the standard schema."""
        ...
```

### RawListing (models.py)

```python
class RawListing(BaseModel):
    source: str
    url: str
    title: str | None
    address: str | None
    price: int | None
    rooms: int | None
    size_sqm: int | None
    floor: str | None
    description: str | None
    image_url: str | None
    lat: float | None
    lon: float | None
    agent: str | None
    phone: str | None
    bathrooms: int | None
    energy_class: str | None
    num_photos: int | None
    has_video: bool
    has_3d_tour: bool
    published_date: str | None
    raw_data: dict      # Full original response for LLM enrichment
```

### Registry

```python
# scrapers/__init__.py
from .idealista import IdealistaScraper
from .immobiliare import ImmobiliareScraper

SCRAPER_REGISTRY: dict[str, BaseScraper] = {
    "idealista": IdealistaScraper(),
    "immobiliare": ImmobiliareScraper(),
}
```

Pipeline iterates `settings.scrapers`, skips disabled ones, looks up in registry, calls `scrape()`.

### Adding a Custom Scraper

1. Create `scrapers/my_scraper.py` implementing `BaseScraper`
2. Add to `SCRAPER_REGISTRY` in `scrapers/__init__.py`
3. Add config block under `scrapers.my_scraper` in `config.yaml`

---

## 5. Scorer Protocol

### BaseScorer

`ScoreResult` is defined in `models.py` (shared across the codebase). `scoring/base.py` imports it.

```python
# models.py
class ScoreResult(BaseModel):
    score: int                      # 0-100
    details: dict[str, Any] = {}    # Scorer-specific metadata

# scoring/base.py
from typing import Protocol, runtime_checkable
from src.models import ScoreResult

@runtime_checkable
class BaseScorer(Protocol):
    name: str
    description: str

    def score(self, listing: dict, config: ScoringConfig) -> ScoreResult:
        """Score a single listing. Receives the full DB row as a dict
        (includes both scraped and LLM-enriched fields like elevator,
        furnished, red_flags, etc.)."""
        ...
```

**Note:** `score()` is synchronous because all scorers do pure computation (no I/O). If a future custom scorer needs external API calls, it should cache/precompute the data before the scoring loop, not make network calls inside `score()`.

### Registry

The `neighborhood` scorer is a **special-case multiplier** — it implements `BaseScorer` but is NOT included in the weighted sum. It runs separately and its `factor` (0.5-1.0) multiplies the weighted base score. This is why it has no weight entry in `scoring.weights`.

```python
# scoring/registry.py
WEIGHTED_SCORERS: dict[str, BaseScorer] = {
    "commute": CommuteScorer(),
    "metro": MetroScorer(),
    "livability": LivabilityScorer(),
    "quality": QualityScorer(),
    "scam": ScamScorer(),
    "freshness": FreshnessScorer(),
}

MULTIPLIER_SCORERS: dict[str, BaseScorer] = {
    "neighborhood": NeighborhoodScorer(),
}

def get_active_scorers(config: ScoringConfig) -> list[tuple[BaseScorer, float]]:
    """Return (scorer, weight) pairs for enabled weighted scorers."""
    active = []
    for name, weight in config.weights.items():
        if weight > 0 and name in WEIGHTED_SCORERS:
            active.append((WEIGHTED_SCORERS[name], weight))
    return active
```

### Hybrid Computation

```python
# scoring/pipeline.py
def compute_hybrid_score(listing: dict, config: ScoringConfig) -> dict:
    scorers = get_active_scorers(config)
    results = {}
    weighted_sum = 0.0

    # Weighted scorers (additive)
    for scorer, weight in scorers:
        result = scorer.score(listing, config)
        results[scorer.name] = result
        weighted_sum += result.score * weight

    # Multiplier scorers (neighborhood factor)
    for name, scorer in MULTIPLIER_SCORERS.items():
        result = scorer.score(listing, config)
        results[name] = result

    neighborhood_factor = results.get("neighborhood", ScoreResult(score=60)).details.get("factor", 0.75)
    hybrid = weighted_sum * neighborhood_factor

    # Budget status (relative to user's max_rent)
    max_rent = config.budget.max_rent
    price = listing.get("price", 0) or 0
    condo = listing.get("condo_fees", 0) or 0
    total_monthly = price + condo
    if total_monthly <= max_rent:
        budget_status = "within"
    elif total_monthly <= max_rent * 1.1:
        budget_status = "slightly_over"
    elif total_monthly <= max_rent * 1.2:
        budget_status = "over"
    else:
        budget_status = "well_over"

    return {
        "hybrid_score": round(hybrid, 1),
        "total_monthly_cost": total_monthly,
        "budget_status": budget_status,
        "scores": {name: r.score for name, r in results.items()},
        "details": {name: r.details for name, r in results.items()},
    }
```

### Customization Levels

- **Weights**: Set in `scoring.weights` — any scorer with weight 0 is disabled
- **Thresholds**: Optional overrides under `scoring.{scorer_name}` — each scorer reads these and falls back to hardcoded defaults
- **Custom scorers**: Add module implementing `BaseScorer`, register in `registry.py`, add weight in config

---

## 6. City Data

### Directory Structure

```
data/cities/
├── README.md
├── milan/
│   ├── metro.json
│   └── neighborhoods.json
└── rome/
    ├── metro.json
    └── neighborhoods.json
```

### metro.json Schema

```json
{
  "city": "milan",
  "lines": [
    {
      "id": "M1",
      "name": "Red Line",
      "branches": [
        {
          "id": "M1-main",
          "stations": ["Sesto FS", "Marelli", "Pagano", "Rho Fiera"]
        },
        {
          "id": "M1-branch",
          "diverges_at": "Pagano",
          "stations": ["Pagano", "De Angeli", "Bisceglie"]
        }
      ]
    }
  ],
  "stations": [
    {
      "name": "Duomo",
      "lat": 45.4641,
      "lon": 9.1919,
      "lines": ["M1", "M3"],
      "is_interchange": true
    }
  ],
  "travel_time": {
    "minutes_per_stop": 2,
    "transfer_minutes": 5,
    "walking_speed_m_per_min": 80
  }
}
```

### neighborhoods.json Schema

```json
{
  "city": "milan",
  "tiers": {
    "top": { "score": 100, "factor": 1.0, "zones": ["Citta Studi", "Isola", "Navigli"] },
    "good": { "score": 85, "factor": 0.9, "zones": ["Bicocca", "Porta Romana"] },
    "average": { "score": 60, "factor": 0.75, "zones": ["Corvetto", "Niguarda"] },
    "caution": { "score": 35, "factor": 0.5, "zones": ["Quarto Oggiaro"] }
  },
  "default_tier": "average"
}
```

### Adding a New City

1. Create `data/cities/{city_name}/`
2. Build `metro.json` following the schema (all stations with coordinates, lines with branches, interchange flags)
3. Build `neighborhoods.json` with local zone tiers
4. Set `city: {city_name}` in `config.yaml`
5. Transit graph builder and neighborhood scorer load it automatically

The AI city-builder prompt can assist with this process.

---

## 7. AI-Assisted Setup

Three markdown prompt files that users paste into Claude Code, Cursor, or any AI coding assistant.

### ai-setup/config-builder.md

Instructs the AI to:
1. Ask: what city, max budget, apartment size, room count
2. Ask: commute destination (address or coordinates), preferred transit line
3. Ask: which scrapers to enable
4. Ask: Telegram notifications yes/no
5. Read `config.example.yaml` as template
6. Check if `data/cities/{city}/` exists — if not, suggest running city-builder
7. Generate `config.yaml`
8. Validate with `uv run python -m src.main validate`

### ai-setup/city-builder.md

Instructs the AI to:
1. Ask: what city and country
2. Research the city's transit system (lines, stations, coordinates)
3. Build `metro.json` following `data/cities/README.md` schema
4. Ask user about neighborhood preferences (desirable, average, avoid)
5. Build `neighborhoods.json`
6. Save to `data/cities/{city}/`
7. Run validation script

### ai-setup/scoring-builder.md

Instructs the AI to:
1. Read current `config.yaml` scoring section
2. Ask: what matters most — commute, comfort, price, safety, freshness?
3. Suggest weight distributions based on priorities
4. Ask: any specific threshold overrides (elevator preference, energy class, etc.)
5. Update scoring section in `config.yaml`
6. If user wants a custom scorer: scaffold module from template, add to registry, add weight

Each prompt file:
- Starts with project context (structure, file locations, schemas)
- Ends with a validation step
- Is AI-assistant-agnostic (works with Claude Code, Cursor, Copilot)

---

## 8. What Ships vs What Users Create

### Committed to Repo

| Component | Purpose |
|-----------|---------|
| `config.example.yaml` | Fully commented template |
| `data/cities/milan/` | Metro + neighborhoods |
| `data/cities/rome/` | Metro + neighborhoods |
| `data/cities/README.md` | Schema docs for new cities |
| `scrapers/base.py` | BaseScraper protocol |
| `scrapers/idealista.py` | Working Apify scraper |
| `scrapers/immobiliare.py` | Working Apify scraper |
| `scoring/base.py` | BaseScorer protocol (ScoreResult in models.py) |
| `scoring/*.py` (7 scorers) | Full scoring suite |
| `scoring/registry.py` | Scorer discovery |
| `enrichment/` | OpenAI LLM extraction |
| `ai-setup/` | 3 AI setup prompt files |
| `web/` | Next.js dashboard |
| `supabase/migrations/` | DB schema |
| `.env.example` | Env var template |

### User-Generated (Gitignored)

| Component | Created By |
|-----------|-----------|
| `config.yaml` | Manual edit or AI config-builder |
| `.env` | User fills in API keys |
| `data/cities/{new_city}/` | Manual or AI city-builder |
| `scoring/custom_*.py` | Manual or AI scoring-builder |
| `scrapers/custom_*.py` | Manual, following protocol |
| `logs/`, `output/` | Pipeline runtime |

---

## 9. Migration From Current Codebase

### What Changes

| Current | Becomes |
|---------|---------|
| `config.py` (hardcoded constants) | Pydantic config loader reading `config.yaml` |
| `metro_stations.json` (flat file) | `data/cities/milan/metro.json` (structured schema) |
| Hardcoded neighborhood tiers in `neighborhood.py` | `data/cities/milan/neighborhoods.json` |
| Hardcoded metro graph logic in `commute.py` | Generic graph builder reading `metro.json` |
| Hardcoded M5/Tre Torri priority in `metro.py` | Config-driven `preferred_line` + `commute.destination` |
| `apify_idealista.py` (function-based) | `idealista.py` class implementing `BaseScraper` |
| `apify_immobiliare.py` (function-based) | `immobiliare.py` class implementing `BaseScraper` |
| `_normalize()` returns dict | Returns `RawListing` Pydantic model |
| Scoring functions called directly | Scorers implement `BaseScorer`, loaded via registry |
| Hardcoded scoring weights in `hybrid.py` | Weights from `config.yaml` |
| Hardcoded thresholds in each scorer | Thresholds from config, fallback to defaults |
| `main.py` imports scrapers directly | Iterates `SCRAPER_REGISTRY` based on config |
| Repo name `milan-finder` | `trovacasa` |

### What Stays the Same

- `db.py` — schema and upsert logic unchanged
- `dedup.py` — address normalization unchanged
- `run_tracker.py` — pipeline run logging unchanged
- `report.py` — HTML report generation unchanged
- `gallery.py` — image gallery fetching unchanged
- `telegram/` — notification logic unchanged
- `enrichment/` — LLM extraction logic unchanged (OpenAI, gpt-5-mini)
- `web/` — Next.js dashboard unchanged (no city-specific code)
- Database schema — all columns already generic

---

## 10. CLI Commands

Unchanged from current:

```
uv run python -m src.main scrape [--source=idealista|immobiliare] [--max-items=N]
uv run python -m src.main enrich [--force]
uv run python -m src.main score [--force]
uv run python -m src.main gallery
uv run python -m src.main notify
uv run python -m src.main bot
uv run python -m src.main all [--max-items=N]
```

New:

```
uv run python -m src.main validate    # Validate config.yaml
```

### `validate` Command

Runs the following checks in order:
1. **YAML syntax** — can `config.yaml` be parsed?
2. **Pydantic validation** — do all fields pass type and constraint checks? Do weights sum to 1.0?
3. **City data exists** — does `data/cities/{config.city}/` exist with `metro.json` and `neighborhoods.json`?
4. **Metro graph integrity** — is the transit graph connected? Are all interchange stations reachable?
5. **Env vars** — are required `.env` keys set (`APIFY_API_TOKEN`, `OPENAI_API_KEY`, `SUPABASE_DB_URL`)?
6. **DB connectivity** — can we connect to Supabase? (optional, skipped with `--skip-db`)

Outputs a clear pass/fail summary with actionable error messages for each check.

---

## 11. Migration Notes

### metro_stations.json Schema Transformation

The current `pipeline/metro_stations.json` is a flat array:
```json
{"stations": [{"name": "...", "lines": ["M1"], "lat": 45.0, "lon": 9.0, "interchange": false}]}
```

This must be restructured into the new `metro.json` schema (Section 6):
- Group stations by line, then by branch (e.g., M1 splits at Pagano, M2 at Cascina Gobba)
- Add `lines[]` with `branches[]` structure — the hardcoded branch logic currently in `commute.py` becomes data
- Rename `interchange` to `is_interchange`
- Add `travel_time` config block (currently hardcoded: 2 min/stop, 5 min transfer, 80 m/min walk)
- The Dijkstra graph builder in `commute.py` is rewritten to read this generic schema instead of having Milan-specific branch handling in code

### metro.py Consolidation

Currently two files load metro data independently:
- `metro.py` (root-level) — haversine proximity + M5 priority scoring
- `scoring/commute.py` — graph builder + Dijkstra routing

After refactor, both `scoring/metro.py` and `scoring/commute.py` share a common city data loader that reads `data/cities/{city}/metro.json` once and provides station lookup, haversine, and graph routing. The `preferred_line` config replaces hardcoded M5 priority — the metro scorer boosts proximity score for stations on the user's preferred line and its interchanges.

### File Paths

All paths in this spec are relative to repo root (`trovacasa/`). The Python pipeline runs from `pipeline/` but config and data paths are resolved relative to repo root:
- `config.yaml` → `trovacasa/config.yaml`
- `data/cities/` → `trovacasa/pipeline/data/cities/`
- AI setup prompts reference paths from repo root for clarity
