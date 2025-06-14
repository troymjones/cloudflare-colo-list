from cloudflare import Cloudflare
import requests
import json
import os
import sys
import re
import csv
import time
import unicodedata
import pandas as pd
from collections import OrderedDict

os.chdir(os.path.split(os.path.realpath(sys.argv[0]))[0])

exit_code = 0

missing_city_country = {
    "Hong Kong": "China",
    "Ramallah": "Palestine",
    "Taipei": "Taiwan",
    "Macau": "China",
    "South Dakota": "United States",
}

missing_in_regions_json = {
    "NEAS": [{
        "country_code_a2": "CN",
        "country_name": "China"
    }],
}

pop_to_cf_lb_region = {
    # Start Brazil
    "QWJ": "SSAM",
    "ARU": "SSAM",
    "BEL": "NSAM",
    "CNF": "SSAM",
    "BNU": "SSAM",
    "BSB": "SSAM",
    "CFC": "SSAM",
    "VCP": "SSAM",
    "CAW": "SSAM",
    "XAP": "SSAM",
    "CGB": "SSAM",
    "CWB": "SSAM",
    "FLN": "SSAM",
    "FOR": "NSAM",
    "GYN": "SSAM",
    "ITJ": "SSAM",
    "JOI": "SSAM",
    "JDO": "NSAM",
    "MAO": "NSAM",
    "PMW": "NSAM",
    "POA": "SSAM",
    "REC": "NSAM",
    "RAO": "SSAM",
    "GIG": "SSAM",
    "SSA": "NSAM",
    "SJP": "SSAM",
    "SJK": "SSAM",
    "GRU": "SSAM",
    "SOD": "SSAM",
    "NVT": "SSAM",
    "UDI": "SSAM",
    "VIX": "SSAM",
    # End Brazil

    # Start Canada
    "YYC": "WNAM",
    "YVR": "WNAM",
    "YWG": "ENAM",
    "YHZ": "ENAM",
    "YOW": "ENAM",
    "YYZ": "ENAM",
    "YUL": "ENAM",
    "YXE": "ENAM",
    # End Canada

    # Start Germany
    "TXL": "EEU",
    "DUS": "WEU",
    "FRA": "WEU",
    "HAM": "EEU",
    "MUC": "WEU",
    "STR": "WEU",
    # End Germany

    # Start Italy
    "MXP": "WEU",
    "PMO": "EEU",
    "FCO": "EEU",
    # End Italy

    # Start Russia
    "KJA": "SAS",
    "DME": "EEU",
    "LED": "EEU",
    "SVX": "SAS",
    # End Russia

    # Start US
    "ABQ": "WNAM",
    "ANC": "WNAM",
    "ATL": "ENAM",
    "AUS": "WNAM",
    "BNA": "ENAM",
    "BGR": "ENAM",
    "BOS": "ENAM",
    "BUF": "ENAM",
    "CLE": "ENAM",
    "CLT": "ENAM",
    "DFW": "WNAM",
    "DEN": "WNAM",
    "DTW": "ENAM",
    "CMH": "ENAM",
    "EWR": "ENAM",
    "FSD": "ENAM",
    "HNL": "WNAM",
    "IAH": "WNAM",
    "IAD": "ENAM",
    "IND": "ENAM",
    "JAX": "ENAM",
    "LAX": "WNAM",
    "LAS": "WNAM",
    "MEM": "ENAM",
    "MCI": "WNAM",
    "MFE": "WNAM",
    "MIA": "ENAM",
    "MSP": "ENAM",
    "OMA": "WNAM",
    "OKC": "WNAM",
    "ORD": "ENAM",
    "ORF": "ENAM",
    "PDX": "WNAM",
    "PHL": "ENAM",
    "PHX": "WNAM",
    "PIT": "ENAM",
    "RDU": "ENAM",
    "RIC": "ENAM",
    "SAN": "WNAM",
    "SEA": "WNAM",
    "SFO": "WNAM",
    "SJC": "WNAM",
    "SMX": "WNAM",
    "SLC": "WNAM",
    "SMF": "WNAM",
    "SAT": "WNAM",
    "STL": "ENAM",
    "TLH": "ENAM",
    "TPA": "ENAM",
    # End US
}


def get(url, retry=5):
    try:
        r = requests.get(url, timeout=5)
        return r
    except Exception:
        if retry > 0:
            time.sleep(1)
            return get(url, retry - 1)
        else:
            raise Exception('Failed to get url: {}'.format(url))


def generate():
    data = {}
    global_locations = []
    north_america = []
    europe = []
    asia = []
    africa = []
    south_america = []
    middle_east = []
    oceania = []

    iata_lat_long_backup = {}
    with open('iata-icao.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            iata_lat_long_backup[row["iata"]] = {
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
            }

    country_codes = json.load(open('country.json', 'r', encoding='utf-8'))
    country_codes_inv = {
        normalize_str(v): normalize_str(k)
        for k, v in country_codes.items()
    }

    try:
        cf = Cloudflare(
            api_token=os.environ.get("CLOUDFLARE_API_TOKEN"),
        )
        regions = cf.load_balancers.regions.list(
            account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        )["regions"]
    except Exception as e:
        print(e)
        global exit_code
        exit_code = 1
        with open('regions.json', 'r', encoding='utf-8') as f:
            regions = json.load(f)["regions"]

    country_to_cloudflare_region = {}
    cf_region_to_pops = {
        "EEU": [],
        "ENAM": [],
        "ME": [],
        "NAF": [],
        "NEAS": [],
        "NSAM": [],
        "OC": [],
        "SAF": [],
        "SAS": [],
        "SEAS": [],
        "SSAM": [],
        "WEU": [],
        "WNAM": [],
    }

    for region in regions:
        region_code = region["region_code"]
        if region_code in missing_in_regions_json:
            region["countries"].extend(missing_in_regions_json[region_code])
        for country in region["countries"]:
            cc = country["country_code_a2"]
            if cc in country_to_cloudflare_region:
                if isinstance(country_to_cloudflare_region[cc], list):
                    country_to_cloudflare_region[cc].append(region_code)
                else:
                    country_to_cloudflare_region[cc] = [
                        country_to_cloudflare_region[cc],
                        region_code
                    ]
                continue
            country_to_cloudflare_region[cc] = region_code

    # https://www.cloudflarestatus.com/api/v2/components.json for DC list
    components_url = 'https://www.cloudflarestatus.com/api/v2/components.json'
    components_json = json.loads(requests.get(components_url).text)

    grouped_list = {}

    for item in components_json['components']:
        if item['group_id']:
            group_id = item['group_id']
            if group_id not in grouped_list:
                grouped_list[group_id] = dict({'child': {}})
            my_id = item['id']
            my_name = item['name']
            grouped_list[group_id]['child'][my_id] = my_name
        else:
            my_id = item['id']
            my_name = item['name']
            if my_id not in grouped_list:
                grouped_list[my_id] = dict({'child': {}})
            grouped_list[my_id]['name'] = my_name

    to_be_deleted_keys = set()

    for key in grouped_list.keys():
        if grouped_list[key]['name'].find('Cloudflare') != -1:
            to_be_deleted_keys.add(key)

    for key in to_be_deleted_keys:
        del grouped_list[key]

    for region in grouped_list.values():
        region_name = region['name']
        for v in region['child'].values():
            v = v.strip()
            v = normalize_str(v)
            regex = re.search(r'^([\s\S]+?)( +-)? +\(([A-Z]{3})\)', v)
            name = regex.group(1)
            colo = regex.group(3)
            data[colo] = {
                'name': name,
                'region': region_name
            }
            regex2 = re.search(r'^([\s\S]+), ([\s\S]+)', name)
            city = name
            country_name = name
            if regex2:
                city = regex2.group(1)
                country_name = regex2.group(2)
            if country_name in missing_city_country:
                city = name
                country_name = missing_city_country[country_name]

            data[colo].update({
                'city': city,
                'country': country_name,
            })
            if country_name in country_codes_inv:
                cca2 = country_codes_inv[country_name]
                data[colo]['cca2'] = cca2
                if isinstance(country_to_cloudflare_region[cca2], list):
                    if colo in pop_to_cf_lb_region:
                        data[colo]["cf_lb_region"] = pop_to_cf_lb_region[colo]
                        cf_region = pop_to_cf_lb_region[colo]
                        cf_region_to_pops[cf_region].append(colo)
                    else:
                        msg = (f"Error\n{data[colo]}\n {colo} has multiple "
                               f"cf_lb_regions: "
                               f"{country_to_cloudflare_region[cca2]}")
                        print(msg)
                        sys.exit(1)
                else:
                    cf_region = country_to_cloudflare_region[cca2]
                    data[colo]["cf_lb_region"] = cf_region
                    cf_region_to_pops[cf_region].append(colo)
            else:
                print("Did not find country: {}".format(country_name))
            data[colo]["iata"] = colo
                
    # speed.cloudflare.com for locations
    # format: json
    speed_url = 'https://speed.cloudflare.com/locations'
    speed_locations = json.loads(get(speed_url).text)
    for location in speed_locations:
        iata = location['iata']
        if iata in data:
            data[iata].update(location)
            cf_lb_region = data[iata].pop("cf_lb_region")
            data[iata]["cf_lb_region"] = cf_lb_region
        else:
            print(iata, 'not found in cloudflare status')
            data[iata] = location[iata]
            city = location['city']
            country = country_codes[location['cca2']]
            data[iata]['name'] = f"{city}, {country}"

    for iata in data:
        global_locations.append(data[iata])
        if data[iata]["region"] == "North America":
            north_america.append(data[iata])
        elif data[iata]["region"] == "Europe":
            europe.append(data[iata])
        elif data[iata]["region"] == "Asia":
            asia.append(data[iata])
        elif data[iata]["region"] == "Asia Pacific":
            asia.append(data[iata])
        elif data[iata]["region"] == "Africa":
            africa.append(data[iata])
        elif data[iata]["region"] == "South America":
            south_america.append(data[iata])
        elif data[iata]["region"] == "Middle East":
            middle_east.append(data[iata])
        elif data[iata]["region"] == "Oceania":
            oceania.append(data[iata])
        else:
            region = data[iata]["region"]
            name = data[iata]["name"]
            print(f"Did not find region {region} for {iata}: {name}")

    for iata in data:
        if 'lat' not in data[iata]:
            if iata in iata_lat_long_backup:
                data[iata].update(iata_lat_long_backup[iata])
            else:
                print('No lat/long data for', iata)

    normalize_dict(data)
    normalize_dict(speed_locations)
    normalize_dict(global_locations)
    normalize_dict(north_america)
    normalize_dict(europe)
    normalize_dict(asia)
    normalize_dict(africa)
    normalize_dict(south_america)
    normalize_dict(middle_east)
    normalize_dict(oceania)

    return (data, speed_locations, global_locations, north_america, europe,
            asia, africa, south_america, middle_east, oceania,
            cf_region_to_pops)


def normalize_str(s):
    return (unicodedata.normalize('NFKD', s)
            .encode('ascii', 'ignore')
            .decode('utf-8'))


def normalize_dict(data):
    for k in data:
        if isinstance(k, dict):
            for i in k:
                if isinstance(k[i], str):
                    k[i] = normalize_str(k[i])
        else:
            for i in data[k]:
                if isinstance(data[k][i], str):
                    data[k][i] = normalize_str(data[k][i])
    return data


if __name__ == '__main__':
    (match_data, location_data, global_locations, north_america, europe, asia,
     africa, south_america, middle_east, oceania, region_pops) = generate()

    json_dump_args = {
        'indent': 4,
        'ensure_ascii': False,
        'sort_keys': True
    }

    locations_json_content = json.dumps(location_data, **json_dump_args)
    dc_colos_json_content = json.dumps(match_data, **json_dump_args)
    global_locations_json = json.dumps(global_locations, **json_dump_args)
    north_america_json_content = json.dumps(north_america, **json_dump_args)
    europe_json_content = json.dumps(europe, **json_dump_args)
    asia_json_content = json.dumps(asia, **json_dump_args)
    africa_json_content = json.dumps(africa, **json_dump_args)
    south_america_json_content = json.dumps(south_america, **json_dump_args)
    middle_east_json_content = json.dumps(middle_east, **json_dump_args)
    oceania_json_content = json.dumps(oceania, **json_dump_args)
    cf_region_pops_json_content = json.dumps(region_pops, **json_dump_args)
    content_changed = True

    if (os.path.exists('DC-Colos.json')):
        with open('DC-Colos.json', 'r', encoding='utf-8') as f:
            if f.read() == dc_colos_json_content:
                content_changed = False

    if not content_changed:
        print('Content unchanged...')

    # save locations to json
    with open('locations.json', 'w', encoding='utf-8') as f:
        f.write(locations_json_content)

    # save as DC-Colo matched data json
    with open('DC-Colos.json', 'w', encoding='utf-8') as f:
        f.write(dc_colos_json_content)

    with open('global-locations.json', 'w', encoding='utf-8') as f:
        f.write(global_locations_json)

    with open('north-america.json', 'w', encoding='utf-8') as f:
        f.write(north_america_json_content)

    with open('europe.json', 'w', encoding='utf-8') as f:
        f.write(europe_json_content)

    with open('asia.json', 'w', encoding='utf-8') as f:
        f.write(asia_json_content)

    with open('africa.json', 'w', encoding='utf-8') as f:
        f.write(africa_json_content)

    with open('south-america.json', 'w', encoding='utf-8') as f:
        f.write(south_america_json_content)

    with open('middle-east.json', 'w', encoding='utf-8') as f:
        f.write(middle_east_json_content)

    with open('oceania.json', 'w', encoding='utf-8') as f:
        f.write(oceania_json_content)
    
    with open('cloudflare_lb_region_pops.json', 'w', encoding='utf-8') as f:
        f.write(cf_region_pops_json_content)

    # save as csv
    dt = pd.DataFrame(match_data).T
    dt.index.name = 'colo'
    dt.to_csv('DC-Colos.csv', encoding='utf-8')

    # final check for log
    for colo in dt.index[dt.cca2.isnull()]:
        print(colo, match_data[colo], 'not found in cloudflare locations')

    sys.exit(exit_code)
