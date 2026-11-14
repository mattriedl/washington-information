#!/usr/bin/env python3
"""Washington Information - data gatherer.

Builds data/cities.json (281 incorporated cities and towns) and data/counties.json (39 counties) from:
  * U.S. Census Bureau 2020 Gazetteer (land area, internal point) and place-by-county file
  * U.S. Census Bureau population estimates files (2010 Census count, 2020 base, 2024 estimate)
  * Wikidata (2020 Census population, official website, incorporation date, county seat)
  * Wikipedia REST summaries (intro paragraph + lead image, CC BY-SA 4.0)
Raw downloads are cached in data/raw/. Run from the repo root:  python3 data/gather.py
"""
import csv, io, json, os, re, sys, time, urllib.parse
import requests

UA = {'User-Agent': 'WashingtonInformationBuilder/1.0 (https://washingtoninformation.com)'}
RAW = 'data/raw'
os.makedirs(RAW, exist_ok=True)
CENSUS = {
    'gaz_place.txt': 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_gaz_place_53.txt',
    'gaz_county.txt': 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_gaz_counties_53.txt',
    'place_county.txt': 'https://www2.census.gov/geo/docs/reference/codes2020/place_by_cou/st53_wa_place_by_county2020.txt',
    'est2024.csv': 'https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024_53.csv',
    'est2020.csv': 'https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/cities/SUB-EST2020_53.csv',
}


def fetch(name):
    p = f'{RAW}/{name}'
    if not os.path.exists(p):
        r = requests.get(CENSUS[name], headers=UA, timeout=60); r.raise_for_status()
        open(p, 'wb').write(r.content)
    return open(p, encoding='latin-1').read()


def sparql(q, cache):
    p = f'{RAW}/{cache}'
    if os.path.exists(p): return json.load(open(p))
    for i in range(4):
        r = requests.post('https://query.wikidata.org/sparql', data={'query': q}, timeout=180,
                          headers={**UA, 'Accept': 'application/sparql-results+json'})
        if r.ok:
            d = r.json()['results']['bindings']; json.dump(d, open(p, 'w')); return d
        time.sleep(10 * (i + 1))
    r.raise_for_status()


OFFLINE = os.environ.get('WIKI_OFFLINE') == '1'   # cached summaries only (Wikipedia rate-limits cloud IPs)


def wiki_summary(title):
    """Wikipedia REST summary (cached). Returns {} when unavailable."""
    key = re.sub(r'[^A-Za-z0-9_,.()-]', '_', title)
    p = f'{RAW}/summary/{key}.json'
    os.makedirs(f'{RAW}/summary', exist_ok=True)
    if os.path.exists(p): return json.load(open(p))
    if OFFLINE: return {}
    url = 'https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(title.replace(' ', '_'), safe=',()')
    for i in range(5):
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code == 429: time.sleep(15 * (i + 1)); continue
        d = r.json() if r.ok else {}
        json.dump(d, open(p, 'w')); time.sleep(0.4); return d
    return {}


def thumb(summary, width=960):
    """960px thumbnail of the article's lead image (same URL scheme Wikipedia uses)."""
    src = (summary.get('originalimage') or {}).get('source', '')
    m = re.match(r'https://upload\.wikimedia\.org/wikipedia/(commons|en)/(\w)/(\w\w)/([^/]+)$', src)
    if not m: return src, ''
    proj, a, ab, f = m.groups()
    ow = (summary.get('originalimage') or {}).get('width', 0)
    fname = urllib.parse.unquote(f)
    if f.lower().endswith('.svg') or ow > width:
        url = f'https://upload.wikimedia.org/wikipedia/{proj}/thumb/{a}/{ab}/{f}/{width}px-{f}' + ('.png' if f.lower().endswith('.svg') else '')
    else:
        url = src
    return url, fname


def commons_thumb(filepath_url, width=960):
    """Wikidata P18 (Special:FilePath URL) -> a 960px Special:FilePath URL, which redirects to the right-sized
    thumbnail (or the original when it is smaller), plus the file name for the credit link."""
    if not filepath_url: return '', ''
    f = urllib.parse.unquote(filepath_url.rsplit('/', 1)[-1]).replace(' ', '_')
    return f'https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(f)}?width={width}', f.replace('_', ' ')


def year(v):
    return v[:4] if v and re.match(r'^\d{4}', v) and not v.startswith('0') else ''


def tsv(text):
    return [r for r in csv.reader(io.StringIO(text), delimiter='\t')][1:]


PRIMARY_COUNTY = {'Coulee Dam': 'Okanogan', 'Woodland': 'Cowlitz', 'Milton': 'Pierce'}   # county holding most residents listed first


def cities():
    gaz = [[x.strip() for x in r] for r in tsv(fetch('gaz_place.txt')) if r[4].strip() != '57']
    pc = {}
    for r in csv.reader(io.StringIO(fetch('place_county.txt')), delimiter='|'):
        if r[0] == 'STATE': continue
        pc.setdefault(r[4], []).append(r[3].replace(' County', ''))
    e24 = {r['PLACE']: r for r in csv.DictReader(io.StringIO(fetch('est2024.csv'))) if r['SUMLEV'] == '162'}
    e20 = {r['PLACE']: r for r in csv.DictReader(io.StringIO(fetch('est2020.csv'))) if r['SUMLEV'] == '162'}
    vals = ' '.join(f'"{int(r[2])}"' for r in gaz)
    wd = sparql(f'''SELECT ?gnis ?item ?article ?website ?inception ?p18 ?pop ?popdate WHERE {{
 VALUES ?gnis {{ {vals} }} ?item wdt:P590 ?gnis.
 OPTIONAL {{ ?item wdt:P856 ?website }} OPTIONAL {{ ?item wdt:P571 ?inception }} OPTIONAL {{ ?item wdt:P18 ?p18 }}
 OPTIONAL {{ ?item p:P1082 ?ps. ?ps ps:P1082 ?pop. ?ps pq:P585 ?popdate. FILTER(YEAR(?popdate) = 2020) }}
 OPTIONAL {{ ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/> }} }}''', 'wd_places.json')
    W = {}
    for b in wd:
        w = W.setdefault(str(int(b['gnis']['value'])), {})
        for k in ('article', 'website', 'inception', 'p18', 'pop'):
            if k in b and k not in w: w[k] = b[k]['value']
        if 'website' in b and b['website']['value'].startswith('https'): w['website'] = b['website']['value']
    out = []
    for r in gaz:
        geoid, ansi, full = r[1], str(int(r[2])), r[3]
        place = geoid[2:]
        name = re.sub(r' \(.*\)', '', re.sub(r' (city|town)$', '', full))   # 'Krupp (Marlin) town' -> 'Krupp'
        kind = 'town' if full.endswith(' town') else 'city'
        w = W.get(ansi, {})
        title = urllib.parse.unquote(w.get('article', '').rsplit('/', 1)[-1]).replace('_', ' ') or f'{name}, Washington'
        s = wiki_summary(title)
        ext = s.get('extract', '')
        p20 = w.get('pop')
        if not p20:
            m = re.search(r'population was ([\d,]+) at the 2020 census', ext)
            p20 = m.group(1).replace(',', '') if m else (e24.get(place) or {}).get('ESTIMATESBASE2020', '')
        p10 = (e20.get(place) or {}).get('CENSUS2010POP', '')
        if p10 in ('', 'A', 'X', '0'): p10 = ''
        p20 = str(int(float(p20))) if p20 else ''
        chg = f'{(int(p20) - int(p10)) / int(p10) * 100:+.2f}%' if p20 and p10 else ''
        img, imgf = thumb(s)
        if not img: img, imgf = commons_thumb(w.get('p18'))
        counties = pc.get(place, [])
        if name in PRIMARY_COUNTY: counties = [PRIMARY_COUNTY[name]] + [x for x in counties if x != PRIMARY_COUNTY[name]]
        out.append({'name': name, 'title': f'{name}, Washington', 'type': kind, 'geoid': geoid,
                    'county': ', '.join(counties), 'pop2020': p20, 'pop2010': p10, 'change': chg,
                    'pop2024': (e24.get(place) or {}).get('POPESTIMATE2024', ''),
                    'area_sqmi': f'{float(r[8]):.2f}' if float(r[8]) < 10 else f'{float(r[8]):.1f}', 'incorporated': year(w.get('inception', '')), 'seat': False, 'capital': name == 'Olympia',
                    'summary': ext, 'lat': float(r[10]), 'lon': float(r[11]),
                    'wiki_url': 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'), safe=',()'),
                    'image': img, 'image_file': imgf, 'website': w.get('website', '')})
        print(f'{len(out):3} {name}: pop {p20} county {out[-1]["county"]}', file=sys.stderr)
    return out


def counties():
    gaz = [[x.strip() for x in r] for r in tsv(fetch('gaz_county.txt'))]
    vals = ' '.join(f'"{r[1][2:]}"' for r in gaz)
    wd = sparql(f'''SELECT ?fips ?item ?article ?website ?inception ?p18 ?seatLabel ?namedLabel ?pop WHERE {{
 VALUES ?fips {{ {vals} }} ?item wdt:P882 ?f. BIND(SUBSTR(?f, 3) AS ?fips) FILTER(STRSTARTS(?f, "53"))
 OPTIONAL {{ ?item wdt:P856 ?website }} OPTIONAL {{ ?item wdt:P571 ?inception }} OPTIONAL {{ ?item wdt:P18 ?p18 }}
 OPTIONAL {{ ?item wdt:P36 ?seat }} OPTIONAL {{ ?item wdt:P138 ?named }}
 OPTIONAL {{ ?item p:P1082 ?ps. ?ps ps:P1082 ?pop. ?ps pq:P585 ?pd. FILTER(YEAR(?pd) = 2020) }}
 OPTIONAL {{ ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/> }}
 SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}''', 'wd_counties.json')
    W = {}
    for b in wd:
        w = W.setdefault(b['fips']['value'], {})
        for k in ('article', 'website', 'inception', 'p18', 'seatLabel', 'namedLabel', 'pop'):
            if k in b and k not in w: w[k] = b[k]['value']
    e24 = {r['COUNTY']: r for r in csv.DictReader(io.StringIO(fetch('est2024.csv'))) if r['SUMLEV'] == '050'}
    out = []
    for r in gaz:
        fips = r[1][2:]; name = r[3].replace(' County', '')
        w = W.get(fips, {})
        title = urllib.parse.unquote(w.get('article', '').rsplit('/', 1)[-1]).replace('_', ' ') or f'{name} County, Washington'
        s = wiki_summary(title)
        img, imgf = thumb(s)
        if not img: img, imgf = commons_thumb(w.get('p18'))
        out.append({'name': name, 'title': f'{name} County, Washington', 'fips': fips, 'seat': w.get('seatLabel', ''),
                    'est': year(w.get('inception', '')), 'named_for': w.get('namedLabel', ''),
                    'pop2020': str(int(float(w['pop']))) if w.get('pop') else (e24.get(fips) or {}).get('ESTIMATESBASE2020', ''),
                    'pop2024': (e24.get(fips) or {}).get('POPESTIMATE2024', ''),
                    'area_sqmi': str(round(float(r[6]))), 'summary': s.get('extract', ''), 'lat': float(r[8]), 'lon': float(r[9]),
                    'wiki_url': 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'), safe=',()'),
                    'image': img, 'image_file': imgf, 'website': w.get('website', '')})
        print(f'county {name}: seat {out[-1]["seat"]}', file=sys.stderr)
    return out


if __name__ == '__main__':
    ks = counties()
    cs = cities()
    seats = {k['seat'] for k in ks}
    for c in cs: c['seat'] = c['name'] in seats
    json.dump(cs, open('data/cities.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(ks, open('data/counties.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(cs)} cities, {len(ks)} counties')
