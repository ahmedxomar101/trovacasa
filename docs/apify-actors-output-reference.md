# Apify Actors — Output Data Reference

Last updated: 2026-03-07

Comparison of what each actor returns vs what idealista's detail page shows.

---

## Idealista Detail Page Fields (source of truth)

The idealista listing detail page shows these sections:

### "Caratteristiche specifiche" (Specific characteristics)
- Size (m² commerciali)
- Rooms (locali)
- Bathrooms (bagni)
- Condition (stato)
- Orientation (orientamento)
- Building year (costruito nel)
- Furnished status (ammobiliato / con cucina attrezzata)
- Heating type + fuel (riscaldamento autonomo/centralizzato: gas naturale/etc.)
- Energy class + kWh/m²/year
- Floor (piano)
- Elevator (con ascensore)

### "Prezzo" (Price)
- Rent (€/month)
- Price per m² (€/m²)
- Condo fees (spese condominiali €/month)

### Other
- Full description
- Photos, video, 3D tour
- Agent/contact info
- GPS coordinates
- Address
- Neighborhood/district

---

## 1. igolaizola/idealista-scraper — Output Fields

### Without fetchDetails (search results only)

```json
{
  "propertyCode": "35075374",
  "thumbnail": "https://...",
  "numPhotos": 18,
  "floor": "5",
  "price": 790,
  "priceInfo": {"price": {"amount": 790, "currencySuffix": "€/month"}},
  "propertyType": "flat",
  "operation": "rent",
  "size": 45,
  "rooms": 2,
  "bathrooms": 1,
  "address": "via Example, 2",
  "province": "Milano",
  "municipality": "Milano",
  "district": "Certosa",
  "country": "it",
  "latitude": 45.495,
  "longitude": 9.147,
  "url": "/immobile/35075374/",
  "description": "...",
  "hasVideo": false,
  "status": "good",
  "newDevelopment": false,
  "contactInfo": {
    "commercialName": "Agency Name",
    "userType": "professional"
  },
  "suggestedTexts": {"subtitle": "Zone, Milano", "title": "Flat in via..."},
  "hasPlan": false,
  "has3DTour": false,
  "has360": false
}
```

Fields available WITHOUT fetchDetails:
| Field | Key | Example |
|-------|-----|---------|
| Price | `price` | `790` |
| Size | `size` | `45` |
| Rooms | `rooms` | `2` |
| Bathrooms | `bathrooms` | `1` |
| Floor | `floor` | `"5"` |
| Condition | `status` | `"good"` |
| Address | `address` | `"via Example, 2"` |
| District | `district` | `"Certosa"` |
| GPS | `latitude`, `longitude` | `45.495, 9.147` |
| Agent | `contactInfo.commercialName` | `"Agency Name"` |
| Private/Agency | `contactInfo.userType` | `"professional"` |
| Photos count | `numPhotos` | `18` |
| Video | `hasVideo` | `false` |
| 3D tour | `has3DTour` | `false` |
| Description | `description` | full text |
| Property type | `propertyType` | `"flat"` |

Fields NOT available without fetchDetails:
- Energy class
- Furnished status
- Heating type/fuel
- Building year
- Orientation
- Condo fees
- Elevator/lift
- Air conditioning
- Balcony/terrace

### With fetchDetails=True (_details object)

Adds a `_details` object per listing. Key sections:

#### `_details.moreCharacteristics`
```json
{
  "roomNumber": 2,
  "bathNumber": 1,
  "constructedArea": 68,
  "floor": "bj",
  "status": "good",
  "lift": true,
  "garden": false,
  "boxroom": false,
  "swimmingPool": false,
  "isDuplex": false,
  "isPenthouse": false,
  "isStudio": false,
  "housingFurnitures": "unknown",
  "energyCertificationType": "g",
  "energyPerformance": 250,
  "modificationDate": 1772879428000
}
```

Note: `housingFurnitures` often returns `"unknown"` even when the listing is furnished.

#### `_details.energyCertification`
```json
{
  "title": "Energy performance certificate",
  "energyConsumption": {
    "prefix": "Consumption:",
    "suffix": "250 kwh/m² year",
    "value": 250,
    "type": "g"
  },
  "text": "Law 90 from 2013, current legislation"
}
```

#### `_details.translatedTexts.characteristicsDescriptions` (RICH DATA)

This is the most valuable section — contains human-readable phrases that match the detail page's "Caratteristiche specifiche" section. Organized by category:

```json
{
  "characteristicsDescriptions": [
    {
      "key": "advertiserPreferences",
      "title": "The advertiser considers it appropriate for",
      "detailFeatures": [
        {"key": "maxTenantsAllowed", "phrase": "Maximum 2 person(s)"}
      ]
    },
    {
      "key": "features",
      "title": "Basic features",
      "detailFeatures": [
        {"phrase": "68 m² constructed"},
        {"phrase": "2 rooms"},
        {"phrase": "1 bathroom"},
        {"phrase": "Second hand/good condition"},
        {"phrase": "Built in 1960"},
        {"phrase": "Furnished and with equipped kitchen"},
        {"phrase": "Central heating: Gas"}
      ]
    },
    {
      "key": "layout",
      "title": "Building",
      "detailFeatures": [
        {"phrase": "Ground floor"},
        {"phrase": "With lift"}
      ]
    },
    {
      "key": "equipment",
      "title": "Equipment",
      "detailFeatures": [
        {"phrase": "Air conditioning"}
      ]
    },
    {
      "key": "costs",
      "title": "Price",
      "detailFeatures": [
        {"phrase": "900 €/month"},
        {"phrase": "13.24 €/m²"}
      ]
    }
  ]
}
```

Data extractable from `characteristicsDescriptions` phrases:
| Detail page field | Phrase example | Parsing needed |
|-------------------|---------------|----------------|
| Building year | `"Built in 1960"` | regex: `Built in (\d{4})` |
| Furnished | `"Furnished and with equipped kitchen"` | keyword match |
| Heating type + fuel | `"Central heating: Gas"` | split on `:` |
| Air conditioning | `"Air conditioning"` | presence check |
| Orientation | `"East, West facing"` | keyword match |
| Floor | `"Ground floor"` / `"5th floor"` | regex |
| Elevator | `"With lift"` | keyword match |
| Condition | `"Second hand/good condition"` | keyword match |

**IMPORTANT:** The "costs" section does NOT include condo fees, only rent and €/m².

#### `_details.comments` (multi-language descriptions)
```json
[
  {"propertyComment": "English text...", "language": "en", "autoTranslated": true},
  {"propertyComment": "Italian text...", "language": "it", "defaultLanguage": true},
  {"propertyComment": "Romanian text...", "language": "ro", "autoTranslated": true}
]
```

#### `_details.ubication` (location)
```json
{
  "title": "Via Sile no number",
  "latitude": 45.4399553,
  "longitude": 9.2214949,
  "buildingName": "corso lodi",
  "administrativeAreaLevel4": "Corvetto",
  "administrativeAreaLevel3": "Corvetto - Rogoredo",
  "administrativeAreaLevel2": "Milano",
  "administrativeAreaLevel1": "Milano",
  "locationId": "0-EU-IT-MI-01-001-135-12-002",
  "locationName": "Corvetto, Milano"
}
```

#### `_details.multimedia` (full image list)
Each image has: `url` (high-res), `tag` (livingRoom/bedroom/kitchen/bathroom/plan/corridor/atmosphere), `width`, `height`

Also: `videos[]` and `virtual3DTours[]` with URLs.

#### `_details.modificationDate`
```json
{"value": 1772879428000, "text": "Listing updated 5 hours ago"}
```

### With fetchStats=True (_stats object)

Not tested yet. Adds price history, visitor counts per property. 1 extra request per property.

---

## 2. dz_omar/idealista-scraper — Output Fields

Returns flat structure (no nested `_details`). All data in one pass, no extra requests.

```json
{
  "propertyCode": "35075374",
  "thumbnail": "https://...",
  "numPhotos": 18,
  "floor": "5",
  "price": 790,
  "priceInfo": {"price": {"amount": 790, "currencySuffix": "€/month"}},
  "propertyType": "flat",
  "operation": "rent",
  "size": 45,
  "rooms": 2,
  "bathrooms": 1,
  "address": "via Marcantonio dal Re, 2",
  "province": "Milano",
  "municipality": "Milano",
  "district": "Certosa",
  "neighborhood": "Villapizzone - Varesina",
  "locationId": "0-EU-IT-MI-01-001-135-06-003",
  "country": "it",
  "latitude": 45.4952177,
  "longitude": 9.1475355,
  "showAddress": true,
  "url": "https://www.idealista.it/immobile/35075374/",
  "description": "Full English description...",
  "hasVideo": false,
  "status": "good",
  "firstActivationDate": 1772896871000,
  "hasLift": true,
  "priceByArea": 18,
  "has3DTour": false,
  "has360": false,
  "hasPlan": false,
  "hasStaging": false,
  "multimedia": {
    "images": [{"url": "https://...", "tag": "livingRoom"}]
  },
  "contactInfo": {
    "commercialName": "Like Home",
    "contactName": "Like",
    "userType": "professional",
    "agencyLogo": "https://...",
    "phone1": {"phoneNumber": "...", "formattedPhone": "..."}
  },
  "features": {
    "hasSwimmingPool": false,
    "hasTerrace": false,
    "hasAirConditioning": false,
    "hasBoxRoom": false,
    "hasGarden": false
  },
  "detailedType": {"typology": "flat"},
  "suggestedTexts": {
    "subtitle": "Villapizzone - Varesina, Milano",
    "title": "Flat in via Marcantonio dal Re, 2"
  },
  "sourceUrl": "https://www.idealista.it/affitto-case/...",
  "scrapedAt": "2026-03-07T16:18:55.622Z"
}
```

---

## 3. Comparison Table — All Three Sources

| Field | Detail page | igolaizola (no details) | igolaizola (fetchDetails) | dz_omar |
|-------|-------------|------------------------|--------------------------|---------|
| **Price** | 790 €/month | `price` | `price` | `price` |
| **Size** | 45 m² | `size` | `size` + `constructedArea` | `size` |
| **Rooms** | 2 locali | `rooms` | `rooms` | `rooms` |
| **Bathrooms** | 1 bagno | `bathrooms` | `bathrooms` | `bathrooms` |
| **Condition** | Buono stato | `status` | `status` | `status` |
| **Floor** | 5° piano | `floor` | `floor` | `floor` |
| **Elevator** | Con ascensore | - | `lift` + phrases | `hasLift` |
| **Address** | Full | `address` | `address` + `ubication` | `address` |
| **GPS** | On map | `lat/lon` | `lat/lon` | `lat/lon` |
| **District** | Certosa | `district` | `ubication.adminLevel4` | `district` |
| **Neighborhood** | Villapizzone | - | `ubication.adminLevel3` | `neighborhood` |
| **Agent** | Agency name | `contactInfo` | `contactInfo` (extended) | `contactInfo` |
| **Private/Agency** | - | `userType` | `userType` | `userType` |
| **Photos** | 18 | `numPhotos` | `numPhotos` + full URLs | `numPhotos` |
| **Video** | - | `hasVideo` | `hasVideo` + URLs | `hasVideo` |
| **3D Tour** | - | `has3DTour` | `has3DTour` + URLs | `has3DTour` |
| **Description** | Italian | Italian text | Italian + EN + RO | English (translated) |
| **Property type** | flat | `propertyType` | `propertyType` | `propertyType` |
| **Orientation** | Est, Ovest | - | phrases (if listed) | - |
| **Building year** | 1930 | - | phrases: `"Built in 1930"` | - |
| **Furnished** | Ammobiliato | - | `housingFurnitures` (often "unknown") + phrases | - |
| **Heating** | Autonomo: Gas | - | phrases: `"Central heating: Gas"` | - |
| **Energy class** | G (172.84 kWh) | - | `energyCertificationType` + `energyPerformance` | - |
| **Air conditioning** | - | - | phrases + `moreCharacteristics` | `features.hasAirConditioning` |
| **Terrace** | - | - | - | `features.hasTerrace` |
| **Garden** | - | - | `moreCharacteristics.garden` | `features.hasGarden` |
| **Pool** | - | - | `moreCharacteristics.swimmingPool` | `features.hasSwimmingPool` |
| **Condo fees** | 140 €/month | - | - | - |
| **Price/m²** | 17.56 €/m² | - | phrases: `"13.24 €/m²"` | `priceByArea` |
| **Creation date** | - | - | - | `firstActivationDate` (unix) |
| **Modification date** | - | - | `modificationDate` (unix + text) | - |
| **Location ID** | - | - | `ubication.locationId` | `locationId` |
| **Max tenants** | - | - | phrases: `"Maximum 2 person(s)"` | - |

### Legend
- **Present and structured** = field name shown
- **-** = not available from this source
- **phrases** = available in `translatedTexts.characteristicsDescriptions` as human-readable text, needs parsing

---

## Key Findings

### Condo fees (spese condominiali)
Neither actor returns condo fees as a structured field. The detail page shows it in the price section, but idealista's internal API does not expose it. Our LLM enrichment extracts it from description text when agents mention it.

### igolaizola fetchDetails — untapped gold
The `translatedTexts.characteristicsDescriptions` section contains structured phrases for: building year, furnished status, heating type+fuel, AC, orientation, max tenants. These are already in English. **We are not currently parsing these phrases** — we rely on LLM extraction instead. Adding phrase parsing would give us this data for free without LLM calls.

### dz_omar advantages
- Faster (all data in one pass, no fetchDetails needed)
- Cheaper ($4.99 vs $19/mo)
- Pre-parsed fields: `hasLift`, `features.*`, `neighborhood`, `firstActivationDate`, `priceByArea`
- Description already in English
- URL-based = can get all listings the website shows (~798 vs ~115)

### dz_omar disadvantages vs igolaizola+fetchDetails
- No energy class
- No building year
- No heating type/fuel
- No furnished status (structured)
- No orientation
- No multi-language descriptions
- No full-res image URLs (only thumbnails)

### Best strategy
Use dz_omar for volume (all ~798 listings) + use LLM enrichment to extract missing fields from the English descriptions it provides. Alternatively, if igolaizola could return all listings, it would give richer per-listing data via fetchDetails — but it's capped at ~115.
