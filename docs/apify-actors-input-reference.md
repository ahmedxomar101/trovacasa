# Apify Actors — Input Parameter Reference

Last updated: 2026-03-07

---

## 1. igolaizola/idealista-scraper ($19/mo)

Actor page: https://apify.com/igolaizola/idealista-scraper

### Core Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation` | string | Yes | `"sale"` | `sale`, `rent` |
| `propertyType` | string | Yes | `"homes"` | `homes`, `newDevelopments`, `offices`, `premises`, `garages`, `lands`, `storageRooms`, `buildings`, `bedrooms` |
| `country` | string | Yes | `"es"` | `es` (Spain), `pt` (Portugal), `it` (Italy) |
| `location` | string | Yes | — | City name (e.g. `"Milano"`) or Idealista Location ID (e.g. `"0-EU-ES-28-07-001-079"`) |
| `maxItems` | integer | No | `50` | Max items to scrape. 0 = unlimited. Above 2500, location auto-splits into sub-locations (affects ordering). |
| `propertyCodes` | array | No | `[]` | Direct property codes to fetch. When set, location and all filters are ignored. |

### Sorting & Pagination

| Parameter | Type | Required | Default | Options |
|-----------|------|----------|---------|---------|
| `sortBy` | string | No | `"mostRecent"` | `relevance`, `closest`, `lowestPrice`, `highestPrice`, `mostRecent`, `leastRecent`, `highestPriceReduction`, `lowestPriceM2`, `highestPriceM2`, `biggest`, `smallest`, `highestFloors`, `lowestFloors` |

### Detail Fetching

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fetchDetails` | boolean | `false` | Adds `_details` field per property. 1 extra request per property, ~50x slower. Beta. |
| `fetchStats` | boolean | `false` | Adds `_stats` field per property (price history, visitor counts). 1 extra request per property, ~50x slower. Beta. |

### Price Filters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `minPrice` | string | `"0"` | `"0"` = any |
| `maxPrice` | string | `"0"` | `"0"` = any |

Valid price values (rent): `0`, `500`, `550`, `600`, `650`, `700`, `750`, `800`, `850`, `900`, `950`, `1000`, `1100`, `1200`, `1300`, `1400`, `1500`, `1600`, `1700`, `1800`, `1900`, `2000`, `2100`, `2400`, `2700`, `3000`

Valid price values (sale): extends up to `4000000`

### Size Filters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `minSize` | string | `"0"` | `"0"` = any |
| `maxSize` | string | `"0"` | `"0"` = any |

Valid size values: `0`, `60`, `80`, `100`, `120`, `140`, `160`, `180`, `200`, `220`, `240`, `260`, `280`, `300`

Note: No 40 sqm option. Use `"0"` and filter client-side.

### Date Filter

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `publicationDate` | string | `""` (any) | `T` (today), `W` (week), `M` (month), `Y` (year) |

### Rental Filter

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rentalTypes` | string[] | `[]` (any) | `longTerm`, `seasonal`. Leave empty for any. Only applies when operation=rent. |

### Bedroom / Bathroom Filters

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `bedrooms` | string[] | `[]` (any) | `studio`, `1`, `2`, `3`, `4` |
| `bathrooms` | string[] | `[]` (any) | `1`, `2`, `3` |

### Home Type Filter

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `homeType` | string[] | `[]` (any) | Leave empty for all types. Only applies when propertyType=homes. |

Valid values: `flat`, `penthouse`, `duplex`, `detachedHouse`, `semiDetachedHouse`, `terracedHouse`, `countryHouse`, `apartment`, `villa`, `loft`

### Condition Filter

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `condition` | string[] | `[]` (any) | `newDevelopment`, `good`, `renew` |

### Property Status

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `propertyStatus` | string[] | `[]` (any) | `bareOwnership`, `tenanted`, `illegallyOccupied`, `free` |

### Floor Filter

| Parameter | Type | Default | Options |
|-----------|------|---------|---------|
| `floor` | string[] | `[]` (any) | `topFloor`, `intermediateFloor`, `groundFloor` |

### Boolean Feature Filters

All default to `false`. Set to `true` to filter for properties with that feature.

| Parameter | Description |
|-----------|-------------|
| `airConditioning` | Has air conditioning |
| `fittedWardrobes` | Has fitted wardrobes |
| `lift` | Has elevator/lift |
| `balcony` | Has balcony |
| `terrace` | Has terrace |
| `exterior` | Is exterior-facing |
| `garage` | Has garage or parking |
| `garden` | Has garden |
| `swimmingPool` | Has swimming pool |
| `storageRoom` | Has storage room |
| `accessible` | Accessible property |
| `seaViews` | Has sea views |
| `luxury` | Luxury property |
| `plan` | Has floor plan |
| `virtualTour` | Has virtual tour |

### Agency Filter

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agency` | string | `""` | Agency slug from URL, e.g. `"engel-volkers"` from `idealista.com/pro/engel-volkers/` |

### Proxy

| Parameter | Type | Description |
|-----------|------|-------------|
| `proxyConfiguration` | object | `{"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}` |

---

## 2. memo23/immobiliare-scraper ($0.70/1K)

Actor page: https://apify.com/memo23/immobiliare-scraper

### Input

| Parameter | Type | Description |
|-----------|------|-------------|
| `startUrls` | string[] | Search URL(s) from immobiliare.it with filters baked in |
| `maxItems` | integer | Max items to scrape (capped at ~100 per URL in practice) |
| `maxConcurrency` | integer | Max parallel requests |
| `minConcurrency` | integer | Min parallel requests |
| `maxRequestRetries` | integer | Retry count per request |
| `proxy` | object | `{"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}` |

Note: Filters are set via the URL itself (build on immobiliare.it browser, copy URL).

Known limitation: Returns max ~100 items per search URL regardless of maxItems setting.

---

## 3. dz_omar/idealista-scraper ($4.99/mo) — NOT YET ACTIVE

Actor page: https://apify.com/dz_omar/idealista-scraper

### Input

| Parameter | Type | Description |
|-----------|------|-------------|
| `Url` | string[] | Search URL(s) from idealista.it with filters baked in |
| `desiredResults` | integer | Target number of results (minimum 10) |
| `proxyConfig` | object | `{"useApifyProxy": true, "apifyProxyGroups": ["RESIDENTIAL"]}` |

URL-based filtering: build filtered search on idealista.it browser, copy URL, pass to actor.

Example URL: `https://www.idealista.it/affitto-case/milano-milano/con-prezzo_1000,dimensione_40,monolocali-1,bilocali-2,trilocali-3,pubblicato_ultima-settimana/?ordine=pubblicazione-desc`

Returns multiple data tiers per item — rich tier includes: lat/lon, description, priceByArea, bathrooms, numPhotos, hasVideo, has3DTour, has360, status, propertyCode, hasLift, features.

---

## Our Current Config (igolaizola)

```python
{
    "country": "it",
    "location": "Milano",
    "operation": "rent",
    "propertyType": "homes",
    "maxItems": 400,
    "sortBy": "mostRecent",
    "maxPrice": "1000",
    "minPrice": "0",
    "minSize": "0",          # no 40 option, filter client-side
    "maxSize": "0",
    "publicationDate": "M",  # last month
    "bedrooms": ["1", "2", "3"],
    "homeType": ["flat", "penthouse", "duplex", "apartment"],
    "rentalTypes": ["longTerm"],
    "fetchDetails": True,
    "fetchStats": False,
    "proxyConfiguration": {
        "useApifyProxy": True,
        "apifyProxyGroups": ["RESIDENTIAL"],
    },
}
```
