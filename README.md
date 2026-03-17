# cloudflare-colo-list

Structured data for all Cloudflare PoP (Point of Presence) locations worldwide, including IATA codes, coordinates, countries, Cloudflare regions, and load balancer region mappings.

**Updated automatically twice daily** via GitHub Actions.

> Originally forked from [Netrvin/cloudflare-colo-list](https://github.com/Netrvin/cloudflare-colo-list). This fork adds Cloudflare Load Balancer region mappings, airport coordinate enrichment, and automated daily generation.

## Data Files

| File | Description | Format |
|------|-------------|--------|
| `global-locations.json` | All PoPs worldwide | Array of PoP objects |
| `north-america.json` | North American PoPs only | Array of PoP objects |
| `europe.json` | European PoPs only | Array of PoP objects |
| `DC-Colos.json` | All PoPs keyed by IATA code | Object `{ IATA: PoP }` |
| `cloudflare_lb_region_pops.json` | Load Balancer region to IATA code mapping | Object `{ region: [IATA] }` |
| `regions.json` | Cloudflare LB region definitions with country lists | Fallback for API |

## PoP Object Schema

```json
{
  "iata": "SFO",
  "name": "San Francisco, CA, United States",
  "city": "San Francisco, CA",
  "cca2": "US",
  "country": "United States",
  "region": "North America",
  "cf_lb_region": "WNAM",
  "lat": 37.619002,
  "lon": -122.374843
}
```

| Field | Type | Description |
|-------|------|-------------|
| `iata` | string | IATA airport code (unique identifier for the PoP) |
| `name` | string | Display name (city, country) |
| `city` | string | City name |
| `cca2` | string | ISO 3166-1 alpha-2 country code |
| `country` | string | Country name |
| `region` | string | Geographic region (North America, Europe, Asia, etc.) |
| `cf_lb_region` | string | Cloudflare Load Balancer region code |
| `lat` | float | Latitude |
| `lon` | float | Longitude |

## Cloudflare Load Balancer Regions

| Code | Region |
|------|--------|
| `WNAM` | Western North America |
| `ENAM` | Eastern North America |
| `WEU` | Western Europe |
| `EEU` | Eastern Europe |
| `ME` | Middle East |
| `NAF` | Northern Africa |
| `SAF` | Southern Africa |
| `SAS` | Southern Asia |
| `SEAS` | Southeast Asia |
| `NEAS` | Northeast Asia |
| `OC` | Oceania |
| `NSAM` | Northern South America |
| `SSAM` | Southern South America |

## Usage

### Raw URLs (recommended)

```
https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/global-locations.json
https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/north-america.json
https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/europe.json
https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/DC-Colos.json
https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/cloudflare_lb_region_pops.json
```

### Python

```python
import requests

pops = requests.get(
    "https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/global-locations.json"
).json()

for pop in pops:
    print(f"{pop['iata']}: {pop['name']} ({pop['cf_lb_region']})")
```

### Terraform

```hcl
data "http" "cloudflare_pops" {
  url = "https://raw.githubusercontent.com/troymjones/cloudflare-colo-list/main/DC-Colos.json"
}

locals {
  pops = jsondecode(data.http.cloudflare_pops.response_body)
}
```

## Data Sources

1. **[cloudflarestatus.com](https://www.cloudflarestatus.com/api/v2/components.json)** — Authoritative list of all Cloudflare PoPs
2. **[airportsdata](https://pypi.org/project/airportsdata/)** — IATA airport coordinates and subdivision data
3. **Cloudflare Regions API** — Load Balancer region-to-country mappings (with `regions.json` as fallback)
4. **`config/pop_overrides.json`** — Manual overrides for PoPs not in airportsdata
5. **`config/subdivision_regions.json`** — Supplementary subdivision-to-region mappings

## How It Works

The `generate.py` script runs twice daily via GitHub Actions:

1. Fetches the current PoP list from Cloudflare's status page
2. Enriches each PoP with coordinates from airportsdata
3. Maps each PoP to a Cloudflare Load Balancer region using the Regions API
4. Outputs structured JSON files
5. Commits any changes with a descriptive message listing new/removed PoPs

## Configuration

### Adding a missing PoP

If a new Cloudflare PoP isn't in the airportsdata package, add it to `config/pop_overrides.json`:

```json
{
  "XYZ": {
    "lat": 12.345,
    "lon": 67.890,
    "cca2": "US",
    "cf_lb_region": "WNAM"
  }
}
```

### Fixing a region mapping

If a PoP is mapped to the wrong LB region, add a `cf_lb_region` override to `config/pop_overrides.json`.

If a country's subdivision should map to a different region than its country default, add it to `config/subdivision_regions.json`.

## License

MIT License — Originally Copyright (c) 2022 [Netrvin](https://github.com/Netrvin/cloudflare-colo-list)
