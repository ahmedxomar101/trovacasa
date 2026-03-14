# TrovaCasa Scoring Builder

You are helping a user customize how TrovaCasa ranks apartment listings. You'll adjust scoring weights, internal thresholds, or help them create a custom scorer.

## Project Context

TrovaCasa scores listings across 6 weighted dimensions plus a neighborhood multiplier:

| Scorer | Default Weight | What It Measures |
|--------|---------------|-----------------|
| `commute` | 0.30 | Transit commute time to workplace |
| `metro` | 0.20 | Proximity to nearest metro station |
| `livability` | 0.15 | Apartment comfort (elevator, floor, energy, condition, heating, balcony, furnished) |
| `freshness` | 0.15 | How recently the listing was posted |
| `scam` | 0.10 | Scam risk signals (missing photos, suspicious price, red flags) |
| `quality` | 0.10 | Listing quality (photo count, description length, video, 3D tour) |

The `neighborhood` scorer is a **multiplier** (0.5x to 1.0x) applied after the weighted sum — it's not in the weights.

**Hybrid formula:** `(sum of weighted scores) * neighborhood_factor`

## Instructions

### Step 1: Read current config

Read the user's `config.yaml` scoring section (or `config.example.yaml` if they haven't set up yet).

### Step 2: Understand priorities

Ask: "What matters most to you when choosing an apartment? Pick your top 2-3 priorities:"
- **Short commute** — I need to get to work/school quickly
- **Metro access** — Being near the metro is essential
- **Apartment comfort** — Elevator, good condition, energy efficiency matter
- **Fresh listings** — I want to see new listings before others
- **Safety** — I want to avoid scam/suspicious listings
- **Listing quality** — Good photos and detailed descriptions matter

### Step 3: Suggest weights

Based on their priorities, suggest a weight distribution. Some profiles:

**Commuter (default):**
```yaml
commute: 0.30, metro: 0.20, livability: 0.15, freshness: 0.15, scam: 0.10, quality: 0.10
```

**Remote worker:**
```yaml
commute: 0.00, metro: 0.10, livability: 0.35, freshness: 0.20, scam: 0.15, quality: 0.20
```

**Speed hunter (wants first-mover advantage):**
```yaml
commute: 0.20, metro: 0.15, livability: 0.10, freshness: 0.35, scam: 0.10, quality: 0.10
```

**Comfort first:**
```yaml
commute: 0.15, metro: 0.10, livability: 0.35, freshness: 0.15, scam: 0.10, quality: 0.15
```

Tell the user: "Weights must sum to 1.0. Set any scorer to 0 to disable it entirely."

### Step 4: Ask about threshold overrides

Ask: "Do you have specific preferences for any of these? (skip if defaults are fine)"

- **Elevator:** "How important is an elevator? (e.g., essential, nice-to-have, don't care)"
- **Furnished:** "Do you need it furnished? (fully, partially, or you'll furnish yourself)"
- **Energy class:** "Do you care about energy efficiency? (high priority, moderate, don't care)"
- **Floor preference:** "Any floor preference? (high floors, middle floors, ground, no preference)"

For each strong preference, adjust the livability override thresholds:

```yaml
scoring:
  livability:
    elevator: { "yes": 95, "no_high_floor": 5, "no_low_floor": 60 }   # elevator essential
    furnished: { "full": 95, "partial": 50, "no": 10, "unknown": 30 }  # must be furnished
```

### Step 5: Update config.yaml

Update only the `scoring` section of the user's `config.yaml` with the new weights and any threshold overrides.

### Step 6: Custom scorer (advanced, only if asked)

If the user wants a custom scoring dimension:

1. Create a new file following this template:

```python
# pipeline/src/scoring/my_scorer.py
from src.models import ScoreResult
from src.config import ScoringConfig


class MyScorer:
    name = "my_scorer"
    description = "Description of what this scores"

    def score(self, listing: dict, config: ScoringConfig) -> ScoreResult:
        """Score a listing on this dimension.

        Args:
            listing: Full DB row as dict. Available fields include:
                - price, rooms, size_sqm, floor, address
                - elevator, balcony, terrace, furnished, condition
                - energy_class, heating, air_conditioning
                - num_photos, has_video, has_3d_tour
                - description, red_flags
                - lat, lon, agent, is_private
                - creation_date, last_modified
                - condo_fees, contract_type, deposit_months
            config: ScoringConfig with weights, overrides, city_data_path

        Returns:
            ScoreResult with score (0-100) and optional details dict
        """
        # Read overrides from config
        overrides = config.overrides.get(self.name, {})

        # Your scoring logic here
        score = 50  # placeholder

        return ScoreResult(score=score, details={})
```

2. Register it in `pipeline/src/scoring/registry.py`:
```python
from src.scoring.my_scorer import MyScorer
WEIGHTED_SCORERS["my_scorer"] = MyScorer()
```

3. Add weight in `config.yaml`:
```yaml
scoring:
  weights:
    my_scorer: 0.10
    # ... adjust other weights to still sum to 1.0
```

### Step 7: Validate

```bash
cd pipeline && uv run python -m src.main validate
```

Check that weights sum to 1.0 and all referenced scorers exist in the registry.

## Important Rules

- Weights must always sum to exactly 1.0
- Ask questions one at a time
- Start with weight adjustments (simple) before offering threshold overrides (advanced)
- Only suggest custom scorers if the user explicitly asks for functionality not covered by the 6 built-in scorers
- The neighborhood scorer is NOT configurable via weights — it's always active as a multiplier. Users can customize it by editing their city's `neighborhoods.json`
