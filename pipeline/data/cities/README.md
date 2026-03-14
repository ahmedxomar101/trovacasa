# City Data

Static data files that define metro systems and neighborhood quality tiers for each supported city.

## Directory Structure

```
cities/
  <city_name>/
    metro.json          # Metro/subway system: lines, branches, stations, coordinates
    neighborhoods.json  # Neighborhood quality tiers for scoring
```

## Schemas

### metro.json

```json
{
  "city": "string",
  "lines": [
    {
      "id": "string",
      "name": "string",
      "branches": [
        {
          "id": "string",
          "diverges_at": "string (optional, omit for the main branch)",
          "stations": ["string", "..."]
        }
      ]
    }
  ],
  "stations": [
    {
      "name": "string",
      "lat": 0.0,
      "lon": 0.0,
      "lines": ["string"],
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

**Field details:**

| Field | Description |
|-------|-------------|
| `lines[].id` | Short identifier (e.g. `M1`, `A`, `U6`) |
| `lines[].name` | Human-readable name (e.g. `Red Line`) |
| `lines[].branches[].id` | Unique branch ID (e.g. `M1-main`, `M1-bisceglie`) |
| `lines[].branches[].diverges_at` | Station where this branch splits from the main branch. Omit for the main/trunk branch. |
| `lines[].branches[].stations[]` | Ordered list of station names along this branch. Branch stations start from the divergence point. |
| `stations[].name` | Station name (original casing, must match branch references exactly) |
| `stations[].lat/lon` | GPS coordinates (WGS84) |
| `stations[].lines` | List of line IDs serving this station |
| `stations[].is_interchange` | `true` if the station connects two or more lines |
| `travel_time.minutes_per_stop` | Average travel time between consecutive stations |
| `travel_time.transfer_minutes` | Penalty added when changing lines at an interchange |
| `travel_time.walking_speed_m_per_min` | Walking speed used for walk-to-station estimates |

### neighborhoods.json

```json
{
  "city": "string",
  "tiers": {
    "top":     { "score": 100, "factor": 1.0,  "zones": ["zone1", "zone2"] },
    "good":    { "score": 85,  "factor": 0.9,  "zones": ["zone3", "zone4"] },
    "average": { "score": 60,  "factor": 0.75, "zones": ["zone5", "zone6"] },
    "caution": { "score": 35,  "factor": 0.5,  "zones": ["zone7", "zone8"] }
  },
  "default_tier": "average"
}
```

**Field details:**

| Field | Description |
|-------|-------------|
| `tiers.<name>.score` | Raw neighborhood score (0-100) |
| `tiers.<name>.factor` | Multiplier applied to the hybrid score |
| `tiers.<name>.zones[]` | Zone names, **always lowercase** |
| `default_tier` | Tier used when no zone matches the listing address |

Zone matching is case-insensitive substring search: if any zone name appears within the listing's address or macrozone string, that tier is applied.

## Adding a New City

1. Create the directory: `pipeline/data/cities/<city_name>/`
2. Create `metro.json`:
   - List every metro/subway line under `lines[]` with ordered stations per branch.
   - If a line forks, create one branch with `id: "<line>-main"` for the trunk and additional branches with `diverges_at` set to the fork station. The branch's `stations[]` must start from the fork station.
   - Add every unique station to the flat `stations[]` array with GPS coordinates and `is_interchange` flag.
   - Set `travel_time` defaults (2 min/stop, 5 min transfer, 80 m/min walk) or adjust per city.
3. Create `neighborhoods.json`:
   - Classify zones into `top`, `good`, `average`, and `caution` tiers.
   - All zone names must be **lowercase**.
   - Set `default_tier` (usually `"average"`).
4. Validate: ensure every station name referenced in `lines[].branches[].stations[]` has a matching entry in the `stations[]` array, and vice versa.
