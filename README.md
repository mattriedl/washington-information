# washington-information

Static site for **washingtoninformation.com** — a guide to all 281 incorporated cities and towns, 39 counties and 7 regions of Washington State, modeled on oregoninformation.com.

## Build
```
python3 generate_city_pages.py      # writes every page, sitemap.xml and robots.txt
python3 tools/check_links.py         # internal link check (last line: "Problems: N")
```
Hand-written guide pages (home, counties shell, moving, visiting) live in `static_pages.py`; Washington-specific constants (regions, utilities, taglines, facts) are at the top of `generate_city_pages.py`.

## Data refresh
```
WIKI_OFFLINE=1 python3 data/fetch_wa_data.py   # Census Gazetteer + estimates, Wikidata (cached in data/raw/)
python3 data/fetch_summaries.py                # slow Wikipedia intro fetch (cloud IPs get rate-limited)
python3 data/build_aux_data.py                 # ZIP codes + county shapes
python3 data/build_schools.py                  # NCES public schools by city
```

## Preview / deploy
Cloudflare Pages: connect this repo, framework preset **None**, build command empty, output directory `/`.

## Before launch
- Set `ANALYTICS_ID` in `generate_city_pages.py` to the site's GA4 ID.
- Fill Wikipedia summaries (`data/fetch_summaries.py`), then rebuild.
- Blog tooling (`build_blog_index.py`, `tools/blog_seo_check.py`) is ready but no articles exist yet, so the Blog link is hidden.
