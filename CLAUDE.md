# cloudflare-colo-list

## What This Is
Structured data for all Cloudflare PoP (Point of Presence) locations. Updated twice daily via GitHub Actions from Cloudflare's status page, enriched with airport coordinates and LB region mappings.

## Key Files
- `generate.py` — Main script that fetches, enriches, and outputs PoP data
- `DC-Colos.json` — All PoPs keyed by IATA code (the primary lookup file)
- `global-locations.json` — All PoPs as a sorted array
- `north-america.json` / `europe.json` — Regional subsets
- `cloudflare_lb_region_pops.json` — LB region → list of IATA codes
- `regions.json` — Cloudflare LB region definitions (API fallback)
- `config/pop_overrides.json` — Manual coordinate/region overrides for PoPs missing from airportsdata
- `config/subdivision_regions.json` — Country subdivision → LB region mappings

## How generate.py Works
1. Fetches PoP list from `cloudflarestatus.com/api/v2/components.json`
2. Parses component names like "Abidjan, Ivory Coast - (ABJ)" into city/country/IATA
3. Looks up coordinates from the `airportsdata` Python package
4. Falls back to `config/pop_overrides.json` for PoPs not in airportsdata
5. Maps each PoP to a Cloudflare LB region using the Regions API (or `regions.json` fallback)
6. Outputs all JSON files sorted by display name

## Data Sources
- cloudflarestatus.com API — authoritative PoP list
- airportsdata pip package — coordinates
- Cloudflare Regions API — LB region mappings
- config/pop_overrides.json — manual overrides
- config/subdivision_regions.json — subdivision-to-region mapping

## Common Tasks

### A new PoP appears with missing coordinates
Add it to `config/pop_overrides.json` with lat, lon, cca2, and optionally cf_lb_region.

### A PoP is in the wrong LB region
Add a `cf_lb_region` key to its entry in `config/pop_overrides.json`.

### The Cloudflare Regions API is down
The script falls back to `regions.json`. If the API response has changed, update `regions.json` manually.

## GitHub Actions
- Runs on schedule (twice daily: 1am and 1pm UTC)
- Runs on push to main and on PRs
- Compares before/after PoP lists and generates a descriptive commit message
- Uses `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` secrets for the Regions API
