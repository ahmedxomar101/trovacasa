# TrovaCasa

AI-powered apartment finder for Italian cities. Scrapes rental listings from idealista.it and immobiliare.it, enriches with LLM extraction, scores across configurable dimensions, and delivers results via Telegram and a web dashboard.

## IMPORTANT: Maintain This File
This CLAUDE.md is the project's living documentation. **Always update it** when you discover new learnings, fix bugs, change architecture, add/remove actors, update configs, or make any significant decision.

## Open Source

This is a **public open-source project** (MIT license). All code, commits, and PRs are visible to anyone. Keep this in mind:
- **Never commit secrets** (API keys, DB credentials, personal data) — use `.env` files (gitignored)
- **Write clean commit messages** — they're public-facing
- **No personal references** — use config-driven values, not hardcoded names/locations
- **PR descriptions matter** — external contributors may read them

## Git Workflow

### Repository
- **Remote:** https://github.com/ahmedxomar101/trovacasa
- **Default branch:** `main`

### Branch Strategy
- **Never commit directly to master** — always use feature branches
- **Branch naming:** `feat/<step-name>` for new work, `fix/<description>` for bug fixes
- **Merge to master** only when verified working
- **Delete branches** after merging

## Architecture

```
trovacasa/
  config.example.yaml        # Config template (copy to config.yaml)
  config.yaml                # User config (gitignored)
  ai-setup/                  # AI-assisted setup prompts
  pipeline/                  # Python pipeline
    src/
      config.py              # Pydantic config loader (reads config.yaml)
      models.py              # Shared models (RawListing, ScoreResult)
      main.py                # Pipeline orchestrator
      db.py                  # Postgres via asyncpg
      dedup.py               # Address normalization + fuzzy dedup
      report.py              # Interactive HTML report
      run_tracker.py         # Pipeline execution history
      gallery.py             # Image gallery fetcher
      scrapers/
        base.py              # BaseScraper protocol
        idealista.py          # Apify idealista scraper
        immobiliare.py        # Apify immobiliare scraper
      enrichment/
        llm_extract.py        # OpenAI structured extraction
        batch_extract.py      # Parallel batch LLM processing
      scoring/
        base.py              # BaseScorer protocol
        registry.py          # Scorer registry (WEIGHTED + MULTIPLIER)
        pipeline.py          # Batch scoring orchestrator
        transit.py           # Shared transit utilities (haversine, graph, Dijkstra)
        commute.py           # CommuteSorer — transit time to destination
        metro.py             # MetroScorer — proximity to preferred line
        livability.py        # LivabilityScorer — apartment comfort
        quality.py           # QualityScorer — listing quality
        scam.py              # ScamScorer — scam risk
        freshness.py         # FreshnessScorer — listing age
        neighborhood.py      # NeighborhoodScorer — zone tier multiplier
      telegram/
        notify.py            # Telegram alerts
        callback_handler.py  # Button press handler
    data/
      cities/
        milan/               # Milan metro + neighborhoods
        rome/                # Rome metro + neighborhoods
        README.md            # Schema docs for adding a city
    tests/                   # Pipeline tests
  web/                       # Next.js 16 dashboard
  supabase/                  # DB migrations
  docs/                      # Specs, plans, reference docs
```

**Data flow:** Pipeline (Python, local Mac) → Supabase Postgres ← Web app (Next.js, Vercel)

## Configuration

All pipeline settings are in `config.yaml` (copy from `config.example.yaml`).

### Key Concepts
- **City data** — `pipeline/data/cities/{city}/` contains `metro.json` and `neighborhoods.json`
- **Scraper protocol** — Add new scrapers by implementing `BaseScraper` in `scrapers/`
- **Scorer protocol** — Add new scoring dimensions by implementing `BaseScorer` in `scoring/`
- **Config-driven** — All search criteria, weights, thresholds configurable via YAML
- **AI setup** — `ai-setup/` contains prompts for AI-assisted configuration

### Environment Variables (pipeline/.env)
- `APIFY_API_TOKEN` — Apify API token
- `OPENAI_API_KEY` — OpenAI API key
- `SUPABASE_DB_URL` — Session pooler Postgres connection string
- `TELEGRAM_BOT_TOKEN` — Telegram bot token (optional)
- `TELEGRAM_CHAT_ID` — Telegram chat ID (optional)

## How to Run

### Pipeline
```bash
cd pipeline
uv run python -m src.main validate         # validate config
uv run python -m src.main scrape           # scrape only
uv run python -m src.main enrich           # LLM enrich only
uv run python -m src.main enrich --force   # re-process all
uv run python -m src.main score            # score + report
uv run python -m src.main gallery          # fetch image galleries
uv run python -m src.main notify           # send Telegram alerts
uv run python -m src.main bot              # run callback handler
uv run python -m src.main all              # full pipeline
```

### Tests
```bash
cd pipeline && uv run pytest tests/ -v
```

### Web App
```bash
cd web
npm run dev      # local dev server
npm run build    # production build
```

## Scoring System
- **6 weighted scorers** (0-100): commute, metro, livability, scam, freshness, quality
- **1 multiplier scorer**: neighborhood (factor 0.5-1.0)
- **Hybrid score** = `(sum of weighted scores) * neighborhood_factor`
- Weights and thresholds configurable in `config.yaml`

## Supported Cities
- **Milan** — 125 metro stations (M1-M5), 45+ neighborhood zones
- **Rome** — Lines A, B, B1, C, zone tiers
- Add your own: see `pipeline/data/cities/README.md`

## Apify Actors
| Actor | Price | Notes |
|-------|-------|-------|
| `dz_omar/idealista-scraper` | $4.99/mo | URL-based, rich features |
| `memo23/immobiliare-scraper` | $0.70/1K | 100 items/run cap |

## Listing States
`active` → `favorited` → `contacted` → `no_reply` → `booked` → `visited` → `waiting` (or `passed` / `gone` / `dismissed` at any point)

## Design Spec
`docs/superpowers/specs/2026-03-14-trovacasa-open-source-design.md`
