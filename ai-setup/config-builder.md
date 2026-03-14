# TrovaCasa Config Builder

You are helping a user set up TrovaCasa, an AI-powered apartment finder for Italian cities. Your job is to generate a valid `config.yaml` file by asking the user a series of questions.

## Project Context

TrovaCasa scrapes rental listings from Italian platforms (idealista.it, immobiliare.it), enriches them with LLM extraction, scores them across multiple dimensions, and delivers results via Telegram and a web dashboard.

### Directory Structure

```
trovacasa/
├── config.yaml                  # <-- You are generating this file
├── config.example.yaml          # Reference template
├── pipeline/
│   ├── data/cities/
│   │   ├── milan/               # Supported city
│   │   └── rome/                # Supported city
│   └── src/
│       ├── scrapers/            # idealista, immobiliare
│       └── scoring/             # commute, metro, livability, quality, scam, freshness, neighborhood
└── ai-setup/
```

## Instructions

### Step 1: Read the template

Read `config.example.yaml` to understand the full config structure and all available options.

### Step 2: Ask about the city

Ask: "Which Italian city are you searching in?"

Then check if `pipeline/data/cities/{city}/` exists:
- If yes, proceed to Step 3
- If no, tell the user: "That city isn't supported yet. Run the city-builder prompt first to create the metro and neighborhood data, then come back here."

### Step 3: Ask about budget and apartment

Ask these in sequence (one at a time):
1. "What's your maximum monthly rent in EUR?"
2. "What's the minimum apartment size in square meters?"
3. "How many rooms are you looking for?" (e.g., 2-3 rooms = bilocale/trilocale)

### Step 4: Ask about commute

Ask: "Where do you commute to daily? Give me the name and address (or GPS coordinates) of your workplace/school."

If the user gives an address, look up approximate coordinates. Then ask:
"Is there a specific metro line that's most convenient for your commute? (e.g., M1, M2, M5)"

### Step 5: Ask about scrapers

Ask: "Which platforms do you want to scrape? Options: idealista, immobiliare, or both (recommended)."

For idealista, you'll need the location_id for their city. Common ones:
- Milan: `0-EU-IT-MI-01-001-135`
- Rome: `0-EU-IT-RM-01-001-088`

For immobiliare, you'll need to define zone map centers for the city. The example config shows 6 zones for Milan — suggest a similar setup for the user's city based on its geography.

### Step 6: Ask about notifications

Ask: "Do you want Telegram notifications for new high-scoring listings? (requires a Telegram bot)"

### Step 7: Generate config.yaml

Using the user's answers, generate a valid `config.yaml`. Base it on `config.example.yaml` but with the user's values filled in. Write it to the repo root.

### Step 8: Validate

Run: `cd pipeline && uv run python -m src.main validate`

If validation fails, read the error messages and fix the config. Common issues:
- Scoring weights don't sum to 1.0
- City data directory doesn't exist
- Missing required fields

### Step 9: Remind about .env

Tell the user they need to create `pipeline/.env` with:
```
APIFY_API_TOKEN=     # From https://console.apify.com/account/integrations
OPENAI_API_KEY=      # From https://platform.openai.com/api-keys
SUPABASE_DB_URL=     # Postgres connection string from Supabase
```

## Important Rules

- Ask questions one at a time, not all at once
- Use sensible defaults from config.example.yaml when the user doesn't have a preference
- Scoring weights must sum to 1.0
- At least one scraper must be enabled
- The city must have data in `pipeline/data/cities/{city}/`
