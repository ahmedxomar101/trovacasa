# TrovaCasa City Builder

You are helping a user add support for a new city to TrovaCasa. Your job is to create two JSON data files: `metro.json` (transit system) and `neighborhoods.json` (zone quality tiers).

## Project Context

TrovaCasa uses city-specific data to score apartment listings:
- **metro.json** — Metro/transit stations with GPS coordinates, used for commute time calculation and metro proximity scoring
- **neighborhoods.json** — Zone quality tiers, used as a multiplier on the overall listing score

### Existing Examples

Look at the existing city data for reference:
- `pipeline/data/cities/milan/metro.json`
- `pipeline/data/cities/milan/neighborhoods.json`

### Schema Reference

Read `pipeline/data/cities/README.md` for the full JSON schema documentation.

## Instructions

### Step 1: Ask about the city

Ask: "Which city and country do you want to add? (e.g., Naples, Italy)"

### Step 2: Research the metro/transit system

Search the web for the city's metro or rapid transit system. You need:
- All metro lines with their IDs and names
- All stations on each line, in order
- GPS coordinates for each station
- Which stations are interchanges (serve multiple lines)
- Any line branches (where a line splits into two routes)

If the city has no metro, look for tram lines, commuter rail, or other rapid transit that serves as the primary public transport backbone.

### Step 3: Build metro.json

Create `pipeline/data/cities/{city}/metro.json` following this schema:

```json
{
  "city": "cityname",
  "lines": [
    {
      "id": "L1",
      "name": "Line Name",
      "branches": [
        {
          "id": "L1-main",
          "stations": ["Station A", "Station B", "Station C"]
        }
      ]
    }
  ],
  "stations": [
    {
      "name": "Station A",
      "lat": 40.1234,
      "lon": 14.5678,
      "lines": ["L1"],
      "is_interchange": false
    }
  ],
  "travel_time": {
    "minutes_per_stop": 2,
    "transfer_minutes": 5,
    "walking_speed_m_per_min": 80
  }
}
```

Rules:
- Station names in `lines[].branches[].stations[]` must exactly match `stations[].name`
- Stations on multiple lines must have `is_interchange: true`
- Branch stations must be listed in order along the route
- If a line branches, use `diverges_at` to indicate where:
  ```json
  {
    "id": "L1-branch",
    "diverges_at": "Station X",
    "stations": ["Station X", "Station Y", "Station Z"]
  }
  ```

### Step 4: Ask about neighborhoods

Ask the user: "Which neighborhoods or zones in {city} would you consider:"
1. **Top tier** (most desirable — trendy, central, well-connected)
2. **Good tier** (solid choice — convenient, decent area)
3. **Average tier** (functional but not exciting)
4. **Caution tier** (areas to be cautious about — safety, isolation, etc.)

"If you're not sure, I can suggest defaults based on general knowledge."

### Step 5: Build neighborhoods.json

Create `pipeline/data/cities/{city}/neighborhoods.json`:

```json
{
  "city": "cityname",
  "tiers": {
    "top": {
      "score": 100,
      "factor": 1.0,
      "zones": ["zone name 1", "zone name 2"]
    },
    "good": {
      "score": 85,
      "factor": 0.9,
      "zones": ["zone name 3"]
    },
    "average": {
      "score": 60,
      "factor": 0.75,
      "zones": ["zone name 4"]
    },
    "caution": {
      "score": 35,
      "factor": 0.5,
      "zones": ["zone name 5"]
    }
  },
  "default_tier": "average"
}
```

Rules:
- All zone names must be **lowercase** (the scorer does case-insensitive matching)
- Include common variations (e.g., both "centro storico" and "centro")
- The `default_tier` is used when no zone matches the listing address

### Step 6: Validate

Run a quick validation:
```bash
cd pipeline && uv run python -c "
import json
from pathlib import Path

city = 'CITY_NAME'
base = Path('data/cities') / city

metro = json.loads((base / 'metro.json').read_text())
hoods = json.loads((base / 'neighborhoods.json').read_text())

# Check metro
station_names = {s['name'] for s in metro['stations']}
for line in metro['lines']:
    for branch in line['branches']:
        for s in branch['stations']:
            assert s in station_names, f'Station {s} in branch but not in stations list'
print(f'Metro: {len(metro[\"stations\"])} stations, {len(metro[\"lines\"])} lines - OK')

# Check neighborhoods
total_zones = sum(len(t['zones']) for t in hoods['tiers'].values())
print(f'Neighborhoods: {total_zones} zones across {len(hoods[\"tiers\"])} tiers - OK')
"
```

### Step 7: Tell user next steps

"City data created! Now run the config-builder prompt to generate your config.yaml, or manually set `city: {city}` in your config.yaml."

## Important Rules

- Ask questions one at a time
- Use web search to find accurate station data (names, coordinates)
- Double-check that station names are consistent between `lines` and `stations` arrays
- GPS coordinates should be accurate to 4 decimal places
- If unsure about neighborhood tiers, err on the side of "average" — the user can always adjust later
