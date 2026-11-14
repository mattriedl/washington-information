#!/usr/bin/env python3
"""Resolve <!--IMG File name.jpg|alt|caption--> markers in data/blog_content/*.html into credited <figure> blocks.

Looks up each file on Wikimedia Commons (960px thumbnail, author, license) and caches the answers in
data/commons_images.json. If Commons is rate-limiting, it waits and retries; files it still cannot look up
are left as markers so a later run can finish them. Run: python3 tools/resolve_blog_images.py [--wait-minutes N]"""
import glob, html, json, os, re, sys, time, urllib.parse
import requests
UA = {'User-Agent': 'WashingtonInformationBuilder/1.0 (https://washingtoninformation.com)'}
CACHE = 'data/commons_images.json'
MARK = re.compile(r'<!--IMG ([^|]+)\|([^|]+)\|(.*?)-->')
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
wait_min = float(sys.argv[sys.argv.index('--wait-minutes') + 1]) if '--wait-minutes' in sys.argv else 10


def clean(m, k):
    v = m.get(k, {}).get('value', '')
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', v))).strip()


def lookup(files):
    deadline = time.time() + wait_min * 60
    todo = [f for f in files if f not in cache]
    while todo and time.time() < deadline:
        r = requests.get('https://commons.wikimedia.org/w/api.php', headers=UA, timeout=60, params={
            'action': 'query', 'format': 'json', 'prop': 'imageinfo', 'iiprop': 'url|extmetadata|size', 'iiurlwidth': 960,
            'titles': '|'.join('File:' + f for f in todo[:40])})
        if r.status_code == 429 or not r.text.startswith('{'):
            print('Commons rate limit; retrying in 60s', flush=True); time.sleep(60); continue
        q = r.json()['query']
        norm = {n['to']: n['from'] for n in q.get('normalized', [])}
        for p in q['pages'].values():
            name = norm.get(p['title'], p['title'])[5:]
            if 'imageinfo' not in p:
                cache[name] = {'missing': True}; continue
            ii = p['imageinfo'][0]; m = ii.get('extmetadata', {})
            cache[name] = {'src': ii.get('thumburl'), 'w': ii.get('thumbwidth'), 'h': ii.get('thumbheight'), 'page': ii.get('descriptionurl'),
                           'artist': clean(m, 'Artist')[:70] or 'Unknown author', 'license': clean(m, 'LicenseShortName') or 'see file page'}
        json.dump(cache, open(CACHE, 'w'), indent=1, ensure_ascii=False)
        todo = [f for f in todo if f not in cache]
        time.sleep(2)
    return todo


def figure(f, alt, cap):
    c = cache[f]
    return (f'<figure class="photo"><img src="{html.escape(c["src"])}" alt="{alt}" width="{c["w"]}" height="{c["h"]}" loading="lazy" decoding="async">'
            f'<figcaption>{cap} <small>Photo: <a href="{html.escape(c["page"])}" target="_blank" rel="noopener">{html.escape(c["artist"])} / {html.escape(c["license"])}</a> via Wikimedia Commons</small></figcaption></figure>')


files = sorted({m.group(1).strip() for p in glob.glob('data/blog_content/*.html') for m in MARK.finditer(open(p).read())})
extra = [a['image_file'] for a in json.load(open('data/blog_articles.json')) if a.get('image_file')]
left = lookup(sorted(set(files + extra)))
for p in glob.glob('data/blog_content/*.html'):
    s = open(p).read()
    s2 = MARK.sub(lambda m: figure(m.group(1).strip(), m.group(2), m.group(3)) if cache.get(m.group(1).strip(), {}).get('src') else m.group(0), s)
    if s2 != s: open(p, 'w').write(s2)
arts = json.load(open('data/blog_articles.json'))
for a in arts:
    c = cache.get(a.get('image_file', ''), {})
    if c.get('src'):
        a.update(image=c['src'], image_page=c['page'], image_credit=f'{c["artist"]} / {c["license"]}')
json.dump(arts, open('data/blog_articles.json', 'w'), indent=2, ensure_ascii=False)
print('unresolved:', left or 'none')
