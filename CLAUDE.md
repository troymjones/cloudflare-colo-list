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
- `pending-changes.json` — PoP additions/removals held until they persist 72 hours
- `config/pop_overrides.json` — Manual coordinate/region overrides for PoPs missing from airportsdata
- `config/subdivision_regions.json` — Country subdivision → LB region mappings
- `test_generate.py` — unittest coverage for the hold and truncation guard

## How generate.py Works
1. Fetches PoP list from `cloudflarestatus.com/api/v2/components.json` with an identifiable User-Agent (the status API rate-limits clients without one)
2. Parses component names like "Abidjan, Ivory Coast - (ABJ)" into city/country/IATA
3. Looks up coordinates from the `airportsdata` Python package
4. Falls back to `config/pop_overrides.json` for PoPs not in airportsdata
5. Maps each PoP to a Cloudflare LB region using the Regions API (or `regions.json` fallback)
6. Fails if the PoP count drops under 90% of the published `DC-Colos.json`
7. Holds new and removed PoPs in `pending-changes.json` for 72 hours; a change that reverts in that window never publishes
8. Outputs all JSON files sorted by display name

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

### A new or removed PoP is not showing up
It is in `pending-changes.json` and publishes 72 hours after `first_seen`, as long as it does not revert first.

## GitHub Actions
- Runs on schedule (twice daily: 1am and 1pm UTC) and on push to main, on Python 3.13
- PR runs execute tests and generation only and never commit
- Compares before/after PoP lists and generates a descriptive commit message, including pending PoPs
- Uses `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` secrets for the Regions API
- `airportsdata` is pinned in `requirements.txt` because new releases shift coordinates; Dependabot opens a monthly PR to bump it
