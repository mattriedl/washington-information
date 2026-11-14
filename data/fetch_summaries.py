#!/usr/bin/env python3
"""Slowly fill data/raw/summary/ with Wikipedia REST summaries for every city and county.
Wikipedia rate-limits cloud IPs, so this waits politely and backs off on HTTP 429.
Re-run data/fetch_wa_data.py afterwards (WIKI_OFFLINE=1) to merge the cached summaries."""
import json, os, re, sys, time, urllib.parse
import requests
UA = {'User-Agent': 'WashingtonInformationBuilder/1.0 (https://washingtoninformation.com)'}
titles = [urllib.parse.unquote(x['wiki_url'].rsplit('/', 1)[-1]).replace('_', ' ')
          for f in ('data/counties.json', 'data/cities.json') for x in json.load(open(f))]
os.makedirs('data/raw/summary', exist_ok=True)
for i, t in enumerate(titles):
    p = 'data/raw/summary/' + re.sub(r'[^A-Za-z0-9_,.()-]', '_', t) + '.json'
    if os.path.exists(p): continue
    url = 'https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(t.replace(' ', '_'), safe=',()')
    wait = 120
    while True:
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 429: break
        print(f'429 at {i} {t}; sleeping {wait}s', flush=True); time.sleep(wait); wait = min(wait * 2, 900)
    json.dump(r.json() if r.ok else {}, open(p, 'w'))
    print(i, t, r.status_code, flush=True)
    time.sleep(3)
print('done', flush=True)
