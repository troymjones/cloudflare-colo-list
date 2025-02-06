import requests
import json
import bs4
import os
import sys
import re
import time
import unicodedata
import pandas as pd

os.chdir(os.path.split(os.path.realpath(sys.argv[0]))[0])


def get(url, retry=5):
    try:
        r = requests.get(url, timeout=5)
        return r
    except:
        if retry > 0:
            time.sleep(1)
            return get(url, retry - 1)
        else:
            raise Exception('Failed to get url: {}'.format(url))


def generate():
    data = {}
    north_america = []
    europe = []
    asia = []
    africa = []
    south_america = []
    middle_east = []
    oceania = []

    # www.cloudflarestatus.com for DC list
    # Site Struct: Table --div--> continents --div--> DCs --text--> Info
    soup = bs4.BeautifulSoup(get('https://www.cloudflarestatus.com/').text, 'html.parser')
    soup = soup.find('div', {'class': 'components-container one-column'})
    continents = soup.find_all('div', recursive=False)
    continents.pop(0)
    for continent in continents:
        for div in continent.find('div', {'class': 'child-components-container'}).find_all('div', recursive=False):
            txt = div.get_text(strip=True)
            txt = unicodedata.normalize("NFKD", txt)
            regex = re.search(r'^([\s\S]+?)( +-)? +\(([A-Z]{3})\)', txt)
            name = regex.group(1)
            colo = regex.group(3)
            data[colo] = {}
            data[colo]['name'] = name

    # speed.cloudflare.com for locations
    # format: json
    speed_locations = json.loads(get('https://speed.cloudflare.com/locations').text)
    country_codes = json.load(open('country.json', 'r', encoding='utf-8'))
    for location in speed_locations:
        iata = location['iata']
        if iata in data:
            data[iata].update(location)
        else:
            print(iata, 'not found in cloudflare status')
            data[iata] = location
            data[iata]['name'] = location['city'] + ', ' + country_codes[location['cca2']]
            
        if data[iata]["region"] == "North America":
            north_america.append(data[iata])
        elif data[iata]["region"] == "Europe":
            europe.append(data[iata])
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
            print(data[iata]["region"])

    unicodedata_dict(data)
    unicodedata_dict(speed_locations)
    unicodedata_dict(north_america)
    unicodedata_dict(europe)
    unicodedata_dict(asia)
    unicodedata_dict(africa)
    unicodedata_dict(south_america)
    unicodedata_dict(middle_east)
    unicodedata_dict(oceania)

    return data, speed_locations, north_america, europe, asia, africa, south_america, middle_east, oceania

def unicodedata_dict(data):
    for k in data:
        if isinstance(k, dict):
            for i in k:
                if isinstance(k[i], str):
                    k[i] = unicodedata.normalize("NFKD", k[i]).encode("ascii", "ignore").decode("utf-8")
        else:
            for i in data[k]:
                if isinstance(data[k][i], str):
                    data[k][i] = unicodedata.normalize("NFKD", data[k][i]).encode("ascii", "ignore").decode("utf-8")
    return data

if __name__ == '__main__':
    match_data, location_data, north_america, europe, asia, africa, south_america, middle_east, oceania = generate()

    locations_json_content = json.dumps(location_data, indent=4, ensure_ascii=False, sort_keys=True)
    dc_colos_json_content = json.dumps(match_data, indent=4, ensure_ascii=False, sort_keys=True)
    north_america_json_content = json.dumps(north_america, indent=4, ensure_ascii=False, sort_keys=True)
    europe_json_content = json.dumps(europe, indent=4, ensure_ascii=False, sort_keys=True)
    asia_json_content = json.dumps(asia, indent=4, ensure_ascii=False, sort_keys=True)
    africa_json_content = json.dumps(africa, indent=4, ensure_ascii=False, sort_keys=True)
    south_america_json_content = json.dumps(south_america, indent=4, ensure_ascii=False, sort_keys=True)
    middle_east_json_content = json.dumps(middle_east, indent=4, ensure_ascii=False, sort_keys=True)
    oceania_json_content = json.dumps(oceania, indent=4, ensure_ascii=False, sort_keys=True)
    content_changed = True

    if (os.path.exists('DC-Colos.json')):
        with open('DC-Colos.json', 'r', encoding='utf-8') as f:
            if f.read() == dc_colos_json_content:
                content_changed = False

    if not content_changed:
        print('Content unchanged, exiting...')
        # sys.exit()

    # save locations to json
    with open('locations.json', 'w', encoding='utf-8') as f:
        f.write(locations_json_content)

    # save as DC-Colo matched data json
    with open('DC-Colos.json', 'w', encoding='utf-8') as f:
        f.write(dc_colos_json_content)

    # save as DC-Colo matched data json
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

    # save as csv
    dt = pd.DataFrame(match_data).T
    dt.index.name = 'colo'
    dt.to_csv('DC-Colos.csv', encoding='utf-8')

    # final check for log
    for colo in dt.index[dt.cca2.isnull()]:
        print(colo, match_data[colo], 'not found in cloudflare locations')
