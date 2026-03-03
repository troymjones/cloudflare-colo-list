#!/usr/bin/env python3
"""Generate Cloudflare PoP location data.

Data sources:
1. cloudflarestatus.com/api/v2/components.json - authoritative PoP list
2. airportsdata pip package - coordinates and subdivision data
3. Cloudflare Regions API (with regions.json fallback) - region mappings
4. config/subdivision_regions.json - supplementary subdivision-to-region mapping
5. config/pop_overrides.json - overrides for PoPs missing from airportsdata
"""

import json
import os
import re
import unicodedata

import airportsdata
import requests
from cloudflare import Cloudflare

# Countries missing from the Regions API that need to be added
EXTRA_REGION_COUNTRIES = {
    "NEAS": [{"country_code_a2": "CN", "country_name": "China"}],
    "WEU": [{"country_code_a2": "MT", "country_name": "Malta"}],
    "NAF": [{"country_code_a2": "ET", "country_name": "Ethiopia"}],
    "SAF": [{"country_code_a2": "MW", "country_name": "Malawi"}],
    "SAS": [{"country_code_a2": "KG", "country_name": "Kyrgyzstan"}],
}


def normalize_str(s):
    """Remove Unicode accents, converting to ASCII equivalents."""
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode("utf-8")
    )


def load_regions():
    """Load Cloudflare LB regions from API or fallback to local file."""
    try:
        cf = Cloudflare(api_token=os.environ.get("CLOUDFLARE_API_TOKEN"))
        regions = cf.load_balancers.regions.list(
            account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        )["regions"]
    except Exception as e:
        print(f"Warning: Falling back to local regions.json: {e}")
        with open("regions.json", "r", encoding="utf-8") as f:
            regions = json.load(f)["regions"]

    # Supplement with countries missing from the API
    for region in regions:
        rc = region["region_code"]
        if rc in EXTRA_REGION_COUNTRIES:
            region["countries"].extend(EXTRA_REGION_COUNTRIES[rc])

    return regions


def build_region_mappings(regions, subdivision_regions_config):
    """Build country-to-region and subdivision-to-region mappings.

    Returns:
        country_to_regions: cca2 -> region_code (str) or [region_codes] (list)
        subdivision_to_region: (cca2, subdivision_name) -> region_code
        country_names: cca2 -> country_name (ASCII-normalized)
    """
    country_to_regions = {}
    subdivision_to_region = {}
    country_names = {}

    for region in regions:
        rc = region["region_code"]
        for country in region["countries"]:
            cc = country["country_code_a2"]
            country_names[cc] = normalize_str(country["country_name"])

            if cc in country_to_regions:
                existing = country_to_regions[cc]
                if isinstance(existing, list):
                    existing.append(rc)
                else:
                    country_to_regions[cc] = [existing, rc]
            else:
                country_to_regions[cc] = rc

            # Map subdivisions from Regions API (covers US, CA, BR-Tocantins)
            for sub in country.get("country_subdivisions", []):
                subdivision_to_region[(cc, sub["subdivision_name"])] = rc

    # Add supplementary subdivision mappings from config (BR, DE, IT, RU)
    for cc, region_map in subdivision_regions_config.items():
        for region_code, subdivisions in region_map.items():
            for subd_name in subdivisions:
                subdivision_to_region[(cc, subd_name)] = region_code

    return country_to_regions, subdivision_to_region, country_names


def parse_status_page():
    """Parse Cloudflare status page to get PoP list.

    Returns list of dicts: {iata, city, parsed_country, region, name}
    """
    url = "https://www.cloudflarestatus.com/api/v2/components.json"
    resp = requests.get(url, timeout=10)
    components = resp.json()["components"]

    # Group components by parent group
    groups = {}
    for item in components:
        if item["group_id"]:
            gid = item["group_id"]
            groups.setdefault(gid, {"child": {}})
            groups[gid]["child"][item["id"]] = item["name"]
        else:
            mid = item["id"]
            groups.setdefault(mid, {"child": {}})
            groups[mid]["name"] = item["name"]

    # Filter to geographic region groups (remove "Cloudflare ..." entries)
    groups = {
        k: v
        for k, v in groups.items()
        if "Cloudflare" not in v.get("name", "")
    }

    pops = []
    for region_data in groups.values():
        region_name = region_data["name"]
        for child_name in region_data["child"].values():
            name = normalize_str(child_name.strip())
            match = re.search(r"^([\s\S]+?)( +-)? +\(([A-Z]{3})\)", name)
            if not match:
                continue

            display_name = match.group(1)
            iata = match.group(3)

            # Parse city and country from "City, Country" or
            # "City, State, Country"
            city_match = re.search(r"^([\s\S]+), ([\s\S]+)", display_name)
            if city_match:
                city = city_match.group(1)
                parsed_country = city_match.group(2)
            else:
                city = display_name
                parsed_country = display_name

            pops.append(
                {
                    "iata": iata,
                    "city": city,
                    "parsed_country": parsed_country,
                    "region": region_name,
                    "name": display_name,
                }
            )

    return pops


def derive_cf_lb_region(
    iata, cca2, subd, country_to_regions, subdivision_to_region, pop_overrides
):
    """Derive the Cloudflare load balancer region for a PoP.

    For single-region countries, returns that region directly.
    For multi-region countries, uses subdivision mapping to determine region.
    Falls back to pop_overrides, then warns and uses first region.
    """
    if cca2 not in country_to_regions:
        print(f"  Warning: country {cca2} not in region mappings for {iata}")
        return None

    mapping = country_to_regions[cca2]

    # Single-region country
    if isinstance(mapping, str):
        return mapping

    # Multi-region country: try subdivision lookup
    if subd and (cca2, subd) in subdivision_to_region:
        return subdivision_to_region[(cca2, subd)]

    # Check pop_overrides for explicit region
    if iata in pop_overrides and "cf_lb_region" in pop_overrides[iata]:
        return pop_overrides[iata]["cf_lb_region"]

    # Unresolved: warn and use first region (don't crash)
    print(
        f"  Warning: {iata} in {cca2} (subd={subd}) has multiple regions "
        f"{mapping} but no subdivision mapping. Using {mapping[0]}"
    )
    return mapping[0]


def generate():
    """Main generation logic."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Load config files
    with open("config/subdivision_regions.json", "r", encoding="utf-8") as f:
        subdivision_regions_config = json.load(f)
    with open("config/pop_overrides.json", "r", encoding="utf-8") as f:
        pop_overrides = json.load(f)

    # Load airport data
    airports = airportsdata.load("IATA")

    # Load and process region data
    regions = load_regions()
    country_to_regions, subdivision_to_region, country_names = (
        build_region_mappings(regions, subdivision_regions_config)
    )

    # Parse status page
    status_pops = parse_status_page()

    # Initialize region-to-pops reverse index
    all_region_codes = [
        "EEU", "ENAM", "ME", "NAF", "NEAS", "NSAM",
        "OC", "SAF", "SAS", "SEAS", "SSAM", "WEU", "WNAM",
    ]
    cf_region_to_pops = {rc: [] for rc in all_region_codes}

    # Process each PoP
    all_pops = {}
    for pop in status_pops:
        iata = pop["iata"]
        entry = {
            "iata": iata,
            "region": pop["region"],
        }

        # Get coordinates, country code, and subdivision
        subd = None
        if iata in airports:
            ap = airports[iata]
            entry["lat"] = ap["lat"]
            entry["lon"] = ap["lon"]
            entry["cca2"] = ap["country"]
            subd = ap.get("subd", "")
        elif iata in pop_overrides:
            ov = pop_overrides[iata]
            entry["lat"] = ov["lat"]
            entry["lon"] = ov["lon"]
            entry["cca2"] = ov["cca2"]
        else:
            print(f"  Warning: {iata} not in airportsdata or pop_overrides")
            entry["cca2"] = None

        # Set country name from region mapping (normalized)
        cca2 = entry.get("cca2")
        if cca2 and cca2 in country_names:
            entry["country"] = country_names[cca2]
        else:
            entry["country"] = pop["parsed_country"]

        # City from status page parsing
        entry["city"] = pop["city"]

        # Display name from status page
        entry["name"] = pop["name"]

        # Derive CF LB region
        if iata in pop_overrides and "cf_lb_region" in pop_overrides[iata]:
            entry["cf_lb_region"] = pop_overrides[iata]["cf_lb_region"]
        elif cca2:
            cf_region = derive_cf_lb_region(
                iata,
                cca2,
                subd,
                country_to_regions,
                subdivision_to_region,
                pop_overrides,
            )
            if cf_region:
                entry["cf_lb_region"] = cf_region

        # Track region-to-pops mapping
        cf_region = entry.get("cf_lb_region")
        if cf_region and cf_region in cf_region_to_pops:
            cf_region_to_pops[cf_region].append(iata)

        all_pops[iata] = entry

    # Build output lists sorted by display name
    global_locations = []
    north_america = []
    europe = []

    for pop in sorted(all_pops.values(), key=lambda p: p.get("name", "")):
        global_locations.append(pop)
        region = pop.get("region", "")
        if region == "North America":
            north_america.append(pop)
        elif region == "Europe":
            europe.append(pop)

    # Sort region-to-pops lists
    for rc in cf_region_to_pops:
        cf_region_to_pops[rc].sort()

    return all_pops, global_locations, north_america, europe, cf_region_to_pops


if __name__ == "__main__":
    data, global_locations, north_america, europe, region_pops = generate()

    json_args = {"indent": 4, "ensure_ascii": False, "sort_keys": True}

    outputs = {
        "global-locations.json": global_locations,
        "north-america.json": north_america,
        "europe.json": europe,
        "DC-Colos.json": data,
        "cloudflare_lb_region_pops.json": region_pops,
    }

    for filename, content in outputs.items():
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(content, f, **json_args)

    print(f"Generated {len(global_locations)} PoP locations")
    print(f"  North America: {len(north_america)}")
    print(f"  Europe: {len(europe)}")
