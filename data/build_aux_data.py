#!/usr/bin/env python3
"""Builds data/city_zips.json, data/washington_zips.json and data/washington_counties_geo.json.
ZIPs: USPS data via the 'zipcodes' Python package. Counties: U.S. Census cartographic boundaries (via plotly/datasets)."""
import json, os, re, requests, zipcodes
cities = json.load(open('data/cities.json'))
Z = [z for z in zipcodes.filter_by(state='WA') if z['active']]
norm = lambda s: re.sub(r'[^a-z]', '', s.lower().replace('mount', 'mt').replace('saint', 'st'))
by = {}
for z in Z: by.setdefault(norm(z['city']), []).append(z)
out, miss = {}, []
for c in cities:
    zs = by.get(norm(c['name']), []) or [z for z in Z if norm(c['name']) in {norm(a) for a in z['acceptable_cities']}]
    if not zs: miss.append(c['name'])
    out[c['name']] = {'area_codes': sorted({a for z in zs for a in z['area_codes']}),
                      'po_box_zips': sorted(z['zip_code'] for z in zs if z['zip_code_type'] == 'PO BOX'),
                      'timezones': sorted({z['timezone'] for z in zs}),
                      'zips': sorted(z['zip_code'] for z in zs if z['zip_code_type'] == 'STANDARD')}
json.dump(out, open('data/city_zips.json', 'w'), indent=1)
json.dump({'source': 'USPS ZIP code data via the zipcodes Python package',
           'zips': [{'zip': z['zip_code'], 'city': z['city'], 'county': z['county'].replace(' County', ''), 'type': z['zip_code_type'], 'tz': z['timezone']}
                    for z in sorted(Z, key=lambda z: z['zip_code'])]}, open('data/washington_zips.json', 'w'))
print('cities without a ZIP of their own:', len(miss), miss)
if not os.path.exists('data/washington_counties_geo.json'):
    g = requests.get('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json', timeout=60).json()
    names = {k['fips']: k['name'] for k in json.load(open('data/counties.json'))}
    def rnd(x): return [rnd(i) for i in x] if isinstance(x[0], list) else [round(x[0], 3), round(x[1], 3)]
    cs = [{'name': names[f['id'][2:]], 'fips': f['id'], 'type': f['geometry']['type'], 'coordinates': rnd(f['geometry']['coordinates'])}
          for f in g['features'] if f['id'].startswith('53')]
    json.dump({'source': 'U.S. Census Bureau cartographic boundary file (public domain), via plotly/datasets', 'counties': cs},
              open('data/washington_counties_geo.json', 'w'), separators=(',', ':'))
    print('county shapes:', len(cs))
