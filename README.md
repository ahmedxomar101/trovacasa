# TrovaCasa

AI-powered apartment finder for Italian cities. Scrapes rental listings from [idealista.it](https://idealista.it) and [immobiliare.it](https://immobiliare.it), enriches them with LLM extraction, scores them across configurable dimensions, and delivers results via Telegram notifications and a web dashboard.

## Features

- **Multi-platform scraping** — Pulls listings from idealista and immobiliare via [Apify](https://apify.com) (your IP is never exposed)
- **LLM enrichment** — Extracts structured data from Italian descriptions using OpenAI (condo fees, contract type, red flags, etc.)
- **7 scoring dimensions** — Commute time, metro proximity, livability, quality, scam risk, freshness, neighborhood
- **Config-driven** — All search criteria, scoring weights, and thresholds in a single YAML file
- **Pluggable architecture** — Add custom scrapers or scoring dimensions via Python protocols
- **City support** — Ships with Milan and Rome. Add your own city with metro + neighborhood data
- **AI-assisted setup** — Prompt files for Claude Code / Cursor to generate your config interactively
- **Web dashboard** — Next.js app for browsing, filtering, and tracking listings
- **Telegram alerts** — Notifications for new high-scoring listings with inline actions

## Quick Start

### Prerequisites

- [Python 3.13+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/) package manager
- [Node.js 18+](https://nodejs.org/) (for the web dashboard)
- API keys: [Apify](https://console.apify.com/account/integrations), [OpenAI](https://platform.openai.com/api-keys)
- A [Supabase](https://supabase.com) project (free tier works)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/trovacasa.git
cd trovacasa/pipeline
uv sync
```

### 2. Configure

**Option A: Manual**
```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your city, budget, commute destination, etc.
```

**Option B: AI-assisted**
```bash
# Paste the contents of ai-setup/config-builder.md into Claude Code or Cursor
# The AI will walk you through setup interactively
```

### 3. Set up environment

```bash
cp pipeline/.env.example pipeline/.env
# Fill in your API keys
```

### 4. Set up the database

Create a Supabase project and run the migration:
```sql
-- Copy contents of supabase/migrations/001_initial_schema.sql
-- into your Supabase SQL editor
```

### 5. Validate and run

```bash
cd pipeline
uv run python -m src.main validate    # Check your config
uv run python -m src.main all         # Run the full pipeline
```

## Configuration

All settings live in `config.yaml`. See `config.example.yaml` for a fully commented template.

```yaml
city: milan                    # Must match a directory in pipeline/data/cities/
budget:
  max_rent: 1100
apartment:
  min_size_sqm: 40
  rooms: [2, 3]
commute:
  destination:
    lat: 45.4565
    lon: 9.1525
    name: "My Workplace"
  preferred_line: M5           # Boosts metro proximity for this line
scoring:
  weights:
    commute: 0.30
    metro: 0.20
    livability: 0.15
    freshness: 0.15
    scam: 0.10
    quality: 0.10
```

## Pipeline Stages

```bash
uv run python -m src.main scrape    # Fetch listings from Apify
uv run python -m src.main enrich    # LLM extraction from descriptions
uv run python -m src.main score     # Compute scores + generate report
uv run python -m src.main gallery   # Fetch full image galleries
uv run python -m src.main notify    # Send Telegram alerts
uv run python -m src.main all       # Run everything
```

## Scoring System

| Dimension | Default Weight | What It Measures |
|-----------|---------------|-----------------|
| Commute | 0.30 | Transit time to your workplace via metro graph |
| Metro | 0.20 | Walking distance to nearest station |
| Livability | 0.15 | Elevator, floor, energy class, condition, heating |
| Freshness | 0.15 | How recently the listing was posted |
| Scam | 0.10 | Missing photos, suspicious price, red flags |
| Quality | 0.10 | Photo count, description quality, video/3D tour |

**Neighborhood** acts as a multiplier (0.5x-1.0x) on the weighted sum, not a weighted dimension.

**Hybrid score** = `(weighted sum) * neighborhood_factor`

All weights and internal thresholds are configurable in `config.yaml`.

## Extending TrovaCasa

### Add a new city

1. Create `pipeline/data/cities/your-city/metro.json` and `neighborhoods.json`
2. Set `city: your-city` in `config.yaml`
3. See `pipeline/data/cities/README.md` for the JSON schema

Or use the AI city-builder: paste `ai-setup/city-builder.md` into your AI assistant.

### Add a custom scraper

Implement the `BaseScraper` protocol:

```python
# pipeline/src/scrapers/my_scraper.py
from src.scrapers.base import BaseScraper
from src.config import ScraperConfig
from src.models import RawListing

class MyScraper:
    name = "my_scraper"

    async def scrape(self, config: ScraperConfig) -> list[RawListing]:
        # Your scraping logic here
        ...

    def normalize(self, raw_item: dict) -> RawListing | None:
        # Convert raw data to RawListing
        ...
```

Register it in `pipeline/src/scrapers/__init__.py` and add config under `scrapers.my_scraper` in `config.yaml`.

### Add a custom scorer

Implement the `BaseScorer` protocol:

```python
# pipeline/src/scoring/my_scorer.py
from src.models import ScoreResult
from src.config import ScoringConfig

class MyScorer:
    name = "my_scorer"
    description = "What this scores"

    def score(self, listing: dict, config: ScoringConfig) -> ScoreResult:
        # Your scoring logic (0-100)
        return ScoreResult(score=75, details={"reason": "..."})
```

Register it in `pipeline/src/scoring/registry.py` and add a weight in `config.yaml`.

## Project Structure

```
trovacasa/
  config.example.yaml          # Config template
  ai-setup/                    # AI-assisted setup prompts
  pipeline/
    src/
      config.py                # Pydantic config loader
      models.py                # Shared models (RawListing, ScoreResult)
      main.py                  # Pipeline orchestrator
      scrapers/                # BaseScraper protocol + implementations
      scoring/                 # BaseScorer protocol + 7 scorers + transit utils
      enrichment/              # OpenAI LLM extraction
      telegram/                # Notifications
    data/cities/               # Metro + neighborhood data per city
    tests/                     # Pipeline tests
  web/                         # Next.js dashboard
  supabase/                    # Database migrations
```

## Web Dashboard

The Next.js app provides:
- Dashboard with overview stats
- Filterable listings view with scoring breakdowns
- Listing detail pages with image galleries
- Status tracking (favorited, contacted, visited, etc.)
- Notification history

```bash
cd web
cp .env.example .env.local
# Fill in Supabase URL and anon key
npm install && npm run dev
```

## Cost Estimate

Per full pipeline run (~400 listings):

| Service | Cost |
|---------|------|
| Apify (idealista + immobiliare) | ~$0.60-1.00 |
| OpenAI (gpt-5-mini, 400 extractions) | ~$0.10-0.20 |
| **Total** | **~$0.70-1.20 per run** |

## Supported Cities

| City | Metro Stations | Neighborhood Zones |
|------|---------------|-------------------|
| Milan | 125 (M1-M5) | 45+ zones, 4 tiers |
| Rome | 73 (A, B, B1, C) | 32 zones, 4 tiers |

## License

[MIT](LICENSE)
