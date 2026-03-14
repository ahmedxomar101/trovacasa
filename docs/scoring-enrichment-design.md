# Scoring & Enrichment Design

## Overview
Enrich raw listing data with computed fields, LLM-extracted info, and multi-dimensional scoring
to produce a single hybrid score that ranks apartments by overall fit for the user.

## User Context
- Commute destination configured in `config.yaml` (e.g., a metro station or office coordinates)
- Budget, room preferences, and priorities are all config-driven
- Scoring weights and thresholds are configurable per user

## Budget Logic
```
total = rent + condo_fees

Budget thresholds are relative to the user's configured max_rent:
≤ max_rent         → GREEN (comfortable)
max_rent to +10%   → YELLOW (acceptable)
+10% to +20%      → ORANGE (only if exceptional hybrid score)
> +20%             → RED (skip)

If condo_fees unknown → flag "ASK ABOUT CONDO FEES"
If total unknown → show rent only + warning
```

---

## Phase 1: Expanded Data Fields

### From actors (store in DB, currently discarded)
| Field | idealista (igolaizola) | idealista (dz_omar) | immobiliare (memo23) |
|-------|----------------------|---------------------|---------------------|
| bathrooms | yes | yes | yes (topology.bathrooms) |
| property_type | yes (propertyType) | yes (propertyType) | yes (topology.typology) |
| elevator | via description | no | yes (topology.lift) |
| balcony | via description | no | yes (topology.balcony) |
| terrace | via description | no | yes (topology.terrace) |
| energy_class | no | no | yes (energyClass) |
| num_photos | yes (multimedia) | yes (numPhotos) | yes (media.images count) |
| has_video | no | yes (hasVideo) | yes (media.videos) |
| has_3d_tour | no | yes (has3DTour) | yes (media.virtualTour) |
| creation_date | no | yes (scrapedAt) | yes (creationDate) |
| last_modified | no | no | yes (lastModified) |
| advertiser_type | yes (contactInfo) | via description | yes (analytics.advertiser) |

### Computed fields
| Field | How |
|-------|-----|
| price_per_sqm | price / size_sqm |
| total_monthly_cost | price + condo_fees (from LLM extraction) |
| commute_minutes | walking to station + metro travel + walking from destination station |
| days_since_posted | today - creation_date |
| budget_status | green/yellow/orange/red based on total_monthly_cost |

---

## Phase 2: LLM Extraction from Descriptions

### Provider
- **OpenAI API** via key in .env (OPENAI_API_KEY)
- Model: gpt-4o-mini (cheap, fast, good at structured extraction)
- Cost estimate: ~200 descriptions × ~500 tokens each = ~100K tokens ≈ $0.01-0.05

### Fields to extract
| Field | Italian keywords to look for | Example |
|-------|------------------------------|---------|
| condo_fees | spese condominiali, spese incluse/escluse | "€150/mese spese condominiali" |
| condo_included | spese incluse, comprensivo di | true/false |
| available_from | disponibile da, libero da | "disponibile da aprile 2026" |
| furnished | arredato, semi-arredato, non arredato, ammobiliato | "completamente arredato" |
| contract_type | 4+4, 3+2, transitorio, cedolare secca | "contratto transitorio 18 mesi" |
| deposit_months | cauzione, deposito, mensilità | "3 mensilità di cauzione" |
| deposit_amount | (computed: deposit_months × price) | €2700 |
| elevator | ascensore, senza ascensore | "palazzo con ascensore" |
| balcony | balcone, terrazzo, terrazzino | "ampio balcone" |
| heating_type | autonomo, centralizzato, riscaldamento | "riscaldamento autonomo" |
| condition | ristrutturato, buono stato, da ristrutturare | "recentemente ristrutturato" |
| building_age | anno di costruzione, anni '60, nuovo | "edificio anni '80" |
| is_private | privato, no agenzia, no provvigione | "affitto privato senza agenzia" |
| agency_fee | provvigione, commissione agenzia | "provvigione 1 mensilità" |
| red_flags | no stranieri, solo referenziati, solo lavoratori | array of flags found |
| total_cost_notes | any mentions of additional costs | "escluse utenze e TARI" |

### LLM Prompt Structure
```
Extract the following from this Italian apartment listing description.
Return JSON only. Use null for fields not mentioned.

{
  "condo_fees": <number or null>,
  "condo_included_in_rent": <true/false/null>,
  "available_from": "<date string or null>",
  "furnished": "<full/partial/no/null>",
  "contract_type": "<4+4/3+2/transitorio/other string/null>",
  "deposit_months": <number or null>,
  "elevator": <true/false/null>,
  "balcony": <true/false/null>,
  "heating": "<autonomous/centralized/null>",
  "condition": "<renovated/good/needs-work/null>",
  "building_age": "<year or decade or null>",
  "is_private": <true/false/null>,
  "agency_fee": "<description or null>",
  "red_flags": ["list of concerning phrases"],
  "additional_costs": "<what's excluded from rent>"
}

Description:
{description_text}
```

---

## Phase 3: Scoring System

### Individual Scores (all 0-100)

#### 1. Metro Score (existing, weight: 0.20)
How close to ANY metro station — affects daily life beyond work.
- M5 within 800m: 90-100
- M5 interchange within 800m: 75-89
- Other metro within 800m: 50-74
- 800-1200m: score reduced by 15
- >1200m: 0

#### 2. Commute Score (weight: 0.30)
Estimated total door-to-door commute to configured destination (set in config.yaml).
- Walking to nearest station: distance_m / 80m per minute
- Metro travel: count stops to destination station (or count transfers)
  - Same line: ~2 min per stop
  - One transfer: +5 min
  - Two transfers: +10 min
- Walking from destination station to final location: configurable
- Scoring: <20min = 100, 20-30min = 80, 30-40min = 60, 40-50min = 40, >50min = 20

#### 3. Livability Score (weight: 0.15)
Measures apartment comfort/modernity — NOT size.
User prefers small modern over big old.
- Elevator: yes = 80, no & floor > 2 = 30, no & floor ≤ 2 = 70
- Balcony/terrace: yes = 80, no = 40
- Furnished: full = 90, partial = 70, no = 50
- Energy class: A/B = 100, C/D = 70, E/F = 40, G = 20 (proxy for modern building)
- Condition: renovated = 100, good = 70, needs work = 30
- Building age: 2010+ = 100, 2000s = 80, 1980-99 = 60, 1960-79 = 40, pre-1960 = 30
- Heating: autonomous = 80, centralized = 50 (you control your costs)
- Score = average of available factors (skip unknowns)

NOTE: Size and room count are NOT scored — they're informational.
A 40m² renovated apartment scores the same livability as a 40m² old one doesn't.

#### 4. Freshness Score (weight: 0.10)
How new/recently updated is the listing.
- Posted today: 100
- 1-3 days ago: 90
- 4-7 days ago: 70
- 1-2 weeks ago: 50
- 2-4 weeks ago: 30
- >1 month: 10

#### 5. Quality Score (weight: 0.10)
Listing trustworthiness and effort signals.
- num_photos: 0-5 = 20, 6-15 = 60, 16+ = 100
- has_video: +10
- has_3d_tour: +10
- description_length: <100 chars = 20, 100-300 = 60, 300+ = 80

#### 6. Scam Risk Score (weight: 0.15)
Higher = safer. Start at 100, subtract red flags.
- Price suspiciously low for area: -30
- 0 photos: -40
- Very short/no description: -20
- No agent and no address details: -20
- Discriminatory language ("no stranieri"): -10
- LLM-detected red flags: -10 each
- Duplicate listing (same address, different price): -20

---

## Phase 4: Hybrid Score

### Formula
```
base_score = (
    commute      × 0.30
  + metro        × 0.20
  + livability   × 0.15
  + scam_risk    × 0.15
  + freshness    × 0.10
  + quality      × 0.10
)
# Weights sum to 1.0

hybrid_score = base_score × neighborhood_factor
```

### Neighborhood Factor (multiplier)
Bad neighborhood fundamentally caps the score — can't be compensated by other factors.

```
neighborhood_factor:
  top_tier  = 1.00  (keeps full score)
  good      = 0.90
  average   = 0.75
  caution   = 0.50  (halves the score)
```

### Neighborhood Classification

**Top tier (factor: 1.00):**
Città Studi, Isola, Porta Venezia, Navigli, Brera, Garibaldi, CityLife, Porta Nuova,
Arco della Pace, Sempione, Indipendenza

**Good (factor: 0.90):**
Bicocca, Bovisa, Porta Romana, Lambrate, NoLo, Maggiolina,
Dergano, Cenisio, Sarpi/Chinatown, Loreto area,
Maciachini, Precotto, Turro, Washington, Fiera

**Average (factor: 0.75):**
Corvetto (improving), Niguarda, Affori, Baggio, Barona, Gratosoglio,
Gallaratese, Quinto Romano, Famagosta, Chiesa Rossa, Stadera,
Vigentino, Ripamonti (far), Gorla, Adriano, Crescenzago

**Caution (factor: 0.50):**
Quarto Oggiaro, Rogoredo (parts), San Siro (near stadium),
Comasina, Ponte Lambro, Molise-Calvairate (parts),
Via Padova (parts — rapidly improving though)

Mapping approach:
1. Use immobiliare's macrozone/microzone or idealista's district field
2. Fallback: reverse-geocode lat/lon to neighborhood
3. Future: enrich with external data (crime stats, green space, transport density)

---

## Phase 5: Cost Transparency

### Total Monthly Cost Display
```
Rent:              €850
Condo fees:        €150 (extracted from description)
                   ────
Estimated total:   €1,000/mo   → GREEN

Missing info:      utilities (gas, electricity), TARI
Deposit:           3 months (€2,550)
Agency fee:        none (privato)
```

### Budget bands
```
Budget bands are relative to the user's configured max_rent:
≤ max_rent         → GREEN (comfortable)
max_rent to +10%   → YELLOW (acceptable)
+10% to +20%      → ORANGE (only if hybrid score is exceptional)
> +20%             → RED (skip — filter out)
```

---

## Technical Implementation

### DB Schema Changes
New columns to add to listings table:
```sql
-- From actors (Phase 1)
bathrooms INTEGER,
property_type TEXT,
elevator BOOLEAN,
balcony BOOLEAN,
terrace BOOLEAN,
energy_class TEXT,
num_photos INTEGER,
has_video BOOLEAN,
has_3d_tour BOOLEAN,
creation_date TEXT,
last_modified TEXT,
price_per_sqm REAL,

-- LLM extracted (Phase 2)
condo_fees REAL,
condo_included BOOLEAN,
available_from TEXT,
furnished TEXT,
contract_type TEXT,
deposit_months INTEGER,
deposit_amount REAL,
heating TEXT,
condition TEXT,
building_age TEXT,
agency_fee TEXT,
red_flags TEXT,         -- JSON array
additional_costs TEXT,

-- Scores (Phase 3-4)
commute_score INTEGER,
quality_score INTEGER,
scam_score INTEGER,
livability_score INTEGER,
freshness_score INTEGER,
neighborhood_score INTEGER,
neighborhood_name TEXT,
hybrid_score REAL,
total_monthly_cost REAL,
budget_status TEXT,     -- green/yellow/orange/red
commute_minutes INTEGER
```

### File Structure (new)
```
src/
  scoring/
    __init__.py
    commute.py         # commute time estimation via metro graph
    quality.py         # listing quality signals
    scam.py            # scam risk detection
    livability.py      # apartment comfort/modernity
    freshness.py       # listing age
    neighborhood.py    # neighborhood classification + mapping
    hybrid.py          # combined score with weights + neighborhood multiplier
  enrichment/
    __init__.py
    llm_extract.py     # OpenAI-based description parsing
    fields.py          # extract additional fields from raw actor data
  report.py            # HTML report generator (exists)
```

### Environment
- OPENAI_API_KEY in .env (for LLM extraction)
- Model: gpt-4o-mini (cheapest, sufficient for structured extraction)
