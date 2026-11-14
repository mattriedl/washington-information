#!/usr/bin/env python3
"""Builds data/city_schools.json: public schools in each Washington city from the NCES Common Core of Data
(EDGE public school administrative data, 2023-24), keyed by the city's name in data/cities.json."""
import json, re, requests
URL = 'https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_ADMINDATA_PUBLICSCH_2324/MapServer/1/query'
F = 'NCESSCH,LEA_NAME,SCH_NAME,LCITY,LSTATE,CHARTER_TEXT,VIRTUAL,GSLO,GSHI,SCHOOL_LEVEL,SY_STATUS_TEXT,SCHOOL_TYPE_TEXT,MEMBER'
rows, off = [], 0
while True:
    d = requests.get(URL, params={'where': "LSTATE='WA'", 'outFields': F, 'returnGeometry': 'true', 'outSR': 4326,
                                  'resultOffset': off, 'resultRecordCount': 2000, 'f': 'json'}, timeout=120).json()
    feats = d.get('features', []); rows += feats; off += len(feats)
    if not feats or not d.get('exceededTransferLimit'): break
print('schools fetched:', len(rows))
G = {'PK': 'Pre-K', 'KG': 'K'}
def grade(g): g = (g or '').strip(); return G.get(g, g.lstrip('0') or g)
LEVEL = {'High': 0, 'Secondary': 0, 'Middle': 1, 'Elementary': 2, 'Primary': 2}
cities = {c['name'].lower(): c['name'] for c in json.load(open('data/cities.json'))}
out = {c: [] for c in cities.values()}
for f in rows:
    a = f['attributes']
    if a['SY_STATUS_TEXT'] not in ('Currently operational', 'New school', 'Reopened'): continue
    if a['SCHOOL_TYPE_TEXT'] != 'Regular School' or (a.get('VIRTUAL') or '').startswith(('Full', 'Exclusively')): continue
    city = cities.get((a['LCITY'] or '').strip().lower())
    if not city: continue
    lo, hi = grade(a['GSLO']), grade(a['GSHI'])
    out[city].append({'name': re.sub(r'\s+', ' ', a['SCH_NAME']).strip(), 'grades': f'{lo}–{hi}' if lo and hi and lo != hi else lo,
                      'level': a['SCHOOL_LEVEL'] if a['SCHOOL_LEVEL'] not in ('Not reported', 'Not applicable', 'Other') else '',
                      'district': a['LEA_NAME'], 'charter': a['CHARTER_TEXT'] == 'Yes',
                      'url': f'https://nces.ed.gov/ccd/schoolsearch/school_detail.asp?ID={a["NCESSCH"]}',
                      'lat': round(f['geometry']['y'], 6), 'lon': round(f['geometry']['x'], 6), '_n': a.get('MEMBER') or 0})
for k, v in out.items():
    v.sort(key=lambda s: (LEVEL.get(s['level'], 3), -(s['_n'] if isinstance(s['_n'], (int, float)) and s['_n'] > 0 else 0)))
    for s in v: s.pop('_n')
json.dump(out, open('data/city_schools.json', 'w'), indent=1, ensure_ascii=False)
print('cities with schools:', sum(1 for v in out.values() if v), 'schools kept:', sum(len(v) for v in out.values()))
