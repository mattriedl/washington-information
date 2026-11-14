"""Washington Information - hand-written guide pages (home, counties shell, moving, visiting).

Imported by generate_city_pages.py, which writes these pages first and then fills the data-driven blocks
(<!--home-regions-->, <!--county-table-->, <!--county-az-->, <!--county-schema-->) on every build.
Edit the text here, then run: python3 generate_city_pages.py
"""
import json
from generate_city_pages import (BASE_URL, CONTACT_EMAIL, REGION_SLUGS, REGION_CONTENT, REGION_COUNTIES, head, header, footer,
                                 ticker_html, alert_banner, state_silhouette, ld, e, n, slug)

EXT = ' target="_blank" rel="noopener"'
PAGE_CSS = ('<style>.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin:24px 0}'
            '.stat{background:var(--bg);border:1px solid #dfe7ec;border-radius:10px;padding:18px;text-align:center}'
            '.stat b{display:block;font-size:1.7rem;color:var(--g);font-family:Outfit,system-ui,sans-serif}.stat span{color:var(--mu);font-size:.88rem;font-weight:600}'
            'a.card{display:block;text-decoration:none;color:inherit}a.card p{font-size:.93rem;color:var(--tx)}a.card .go{color:var(--blue);font-weight:700;font-size:.9rem;margin-top:8px;display:block}'
            '.city-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px;margin:18px 0}'
            '.city-card{background:#fff;border:1px solid #dfe7ec;border-radius:10px;padding:16px;text-decoration:none;color:var(--tx);transition:transform .15s}'
            '.city-card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(14,42,59,.12)}.city-card h3{font-size:1.05rem;color:var(--blue)}.city-card p{font-size:.86rem;color:var(--mu);margin-top:4px}'
            '.section-title{font-size:1.45rem;color:var(--gd);margin:36px 0 10px}.section-sub{color:var(--mu);margin-bottom:16px;max-width:760px}'
            '.alpha-nav{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.alpha-nav a{background:var(--bg);border:1px solid #d3dfe6;border-radius:6px;padding:7px 12px;text-decoration:none;color:var(--blue);font-weight:600;font-size:.9rem}'
            '.alpha-nav a:hover{background:var(--g);color:#fff}.steps{counter-reset:s;list-style:none;padding:0}.steps li{position:relative;padding:12px 0 12px 46px;border-bottom:1px dashed #dfe7ec}'
            '.steps li:before{counter-increment:s;content:counter(s);position:absolute;left:0;top:12px;width:32px;height:32px;border-radius:50%;background:var(--g);color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center}'
            '.steps h3{font-size:1.02rem;color:var(--gd);margin-bottom:4px}.steps p{font-size:.94rem}'
            '.wrap .wrap{padding:0}.cards.four{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}</style>')


def faq_block(faq, title):
    html = ''.join(f'<details><summary>{e(q)}</summary><p>{a}</p></details>' for q, a in faq)
    schema = ld({'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': _strip(a)}} for q, a in faq]})
    return f'<h2 class="st">{title}</h2><section class="faq">{html}</section>', schema


def _strip(h):
    import re, html as H
    return H.unescape(re.sub(r'<[^>]+>', '', h))


def crumbs(*items):
    parts = ['<a href="/">Home</a>'] + [f'<a href="{u}">{t}</a>' if u else t for t, u in items]
    return '<nav class="crumbs" aria-label="Breadcrumb">' + ' &rsaquo; '.join(parts) + '</nav>'


def bread_ld(path, name):
    return ld({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': f'{BASE_URL}/'},
        {'@type': 'ListItem', 'position': 2, 'name': name, 'item': f'{BASE_URL}{path}'}]})


# ---------------------------------------------------------------- home
def home_page(cities, counties):
    big = sorted(cities, key=lambda c: -int(c['pop2020'] or 0))
    labels = {'Seattle': 'Largest city', 'Olympia': 'State capital', 'Spokane': 'Inland Northwest hub', 'Tacoma': 'City of Destiny',
              'Vancouver': 'Columbia River city', 'Bellevue': 'Eastside tech hub', 'Kent': 'Green River Valley', 'Everett': 'Snohomish County seat',
              'Renton': 'South Lake Washington', 'Spokane Valley': 'Spokane suburb', 'Yakima': 'Wine & hop country', 'Bellingham': 'North Sound college town',
              'Kennewick': 'Tri-Cities', 'Redmond': 'Home of Microsoft'}
    show = [c for c in big if c['name'] in labels][:12]
    if not any(c['name'] == 'Olympia' for c in show):
        show = show[:11] + [c for c in cities if c['name'] == 'Olympia']
    cards = ''.join(f'<a class="city-card" href="/cities/{slug(c["name"])}/"><h3>{e(c["name"])}</h3>'
                    f'<p>{labels[c["name"]]} &bull; {e(c["counties"][0])} County &bull; Pop. {n(c["pop2020"])}</p></a>' for c in show)
    faq = [('What is the capital of Washington?', 'Olympia is the capital of Washington. Seattle is the largest city.'),
           ('How many cities and counties are in Washington?', 'Washington has 281 incorporated municipalities (211 cities and 70 towns) and 39 counties. This site groups them into seven regions: Seattle Metro, the North Sound, the Olympic Peninsula, Southwest Washington, Central Washington, Eastern Washington and Southeast Washington.'),
           ('What is the population of Washington?', 'Washington had 7,705,281 residents at the 2020 Census, making it the 13th most populous state. About 2.27 million people live in King County alone.'),
           ('Does Washington have a state income tax?', 'No. Washington has no personal state income tax. It relies on a 6.5% state sales tax plus local sales taxes, property taxes and a business and occupation (B&amp;O) tax, and it taxes large long-term capital gains. See our <a href="/moving-to-washington/#cost-of-living">moving guide</a> for details.'),
           ('What is Washington known for?', 'Washington is known as the Evergreen State for its forests. It is home to Mount Rainier and three national parks, Puget Sound and its ferries, the apple and hop harvests east of the Cascades, a large wine industry and companies such as Microsoft, Amazon, Boeing and Starbucks.'),
           ('What time zone is Washington in?', 'All of Washington is in the Pacific Time Zone and observes daylight saving time.')]
    faq_html, faq_ld = faq_block(faq, 'Washington Quick Facts: Frequently Asked Questions')
    site_ld = ld({'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'Washington Information', 'url': f'{BASE_URL}/',
                  'description': 'Free guide to the State of Washington: all 281 cities and towns, 39 counties and 7 regions, plus moving and travel guides.'})
    org_ld = ld({'@context': 'https://schema.org', '@type': 'Organization', '@id': f'{BASE_URL}/#organization', 'name': 'Washington Information',
                 'url': f'{BASE_URL}/', 'logo': f'{BASE_URL}/assets/og-image.png', 'email': CONTACT_EMAIL, 'areaServed': {'@type': 'State', 'name': 'Washington'}})
    title = 'Washington Information: Guide to Every Washington City & County'
    desc = 'Free guide to Washington State: all 281 cities and towns, 39 counties and 7 regions with population, schools, weather and official links, plus moving and travel guides.'
    return (head(title, desc, '/', extra=site_ld + org_ld + faq_ld + PAGE_CSS, up='/') + header('/') + ticker_html('home') + alert_banner()
            + f'<div class="or-hero">{state_silhouette(cls="or-sil or-sil-lg")}<div class="wrap">'
            + '<p class="or-eyebrow">&#10022; The Evergreen State &middot; Est. 1889 &#10022;</p>'
            + '<h1>Washington Information: Your Guide to Every Washington City, County &amp; Region</h1>'
            + '<p class="or-sub">Facts, figures and official links for the State of Washington and all 281 cities and towns, 39 counties and 7 regions &mdash; one website for residents, visitors and everyone moving to Washington.</p>'
            + '<p class="or-cta"><a class="btn-cta" href="/cities/">Explore Washington Cities &rarr;</a><a class="btn-ghost" href="/regions/">Browse the 7 regions</a></p></div></div>'
            + '<main><div class="wrap">'
            + '<h2 class="st">Washington Information for Residents, Visitors and Newcomers</h2><section class="prose">'
            + '<p>Washington Information is a free, independent guide to the State of Washington. Every one of Washington&rsquo;s 281 incorporated cities and towns has its own page with 2020 Census population, county, local public schools, utilities, live weather, ZIP and area codes and links to official city websites. You can also browse all 39 counties and the state&rsquo;s seven regions, from Puget Sound and the Olympic Peninsula to the orchards of Central Washington and the wheat fields of the Palouse.</p>'
            + '<p>Thinking about relocating? Our <a href="/moving-to-washington/">moving to Washington guide</a> covers taxes, housing, utilities, licensing deadlines and schools. Planning a trip? The <a href="/visit-washington/">Visit Washington guide</a> covers national parks, islands, wine country and scenic drives. Looking up an address? See every <a href="/washington-zip-codes/">Washington ZIP code</a> and <a href="/washington-area-codes/">area code</a>.</p></section>'
            + '<h2 class="st">Washington at a Glance</h2><div class="stat-row">'
            + '<div class="stat"><b>7.7M</b><span>Population (2020 Census)</span></div><div class="stat"><b>71,362</b><span>Square miles</span></div>'
            + '<div class="stat"><b>Olympia</b><span>Capital</span></div><div class="stat"><b>$0</b><span>State income tax</span></div></div>'
            + '<h2 class="st">Explore by Topic</h2><div class="cards four">'
            + '<a class="card" href="/moving-to-washington/"><h3>&#127968; Moving to Washington?</h3><p>Taxes and cost of living, housing, utilities, the 30-day licensing deadline, schools, voting and health coverage.</p><span class="go">Getting started &rarr;</span></a>'
            + '<a class="card" href="/visit-washington/"><h3>&#127794; Visiting Washington?</h3><p>Three national parks, the San Juan Islands, ferries, wine country, scenic byways and the best time to go.</p><span class="go">Plan your trip &rarr;</span></a>'
            + '<a class="card" href="/counties/"><h3>&#128506;&#65039; Browse by County</h3><p>All 39 counties with an interactive map, county seats, population, cities and official links.</p><span class="go">County directory &rarr;</span></a>'
            + '<a class="card" href="/cities/"><h3>&#127961;&#65039; Every Washington City</h3><p>All 281 incorporated cities and towns, each with population, schools, utilities, weather and nearby cities.</p><span class="go">City directory &rarr;</span></a></div>'
            + f'<h2 class="st">Major Cities</h2><div class="city-grid">{cards}</div><p><a href="/cities/">View all 281 Washington cities and towns A&ndash;Z &rarr;</a></p>'
            + '<!--home-regions--><!--/home-regions-->'
            + faq_html + '<p class="src">More state facts, symbols and history are on our <a href="/washington/">Washington state guide</a>.</p>'
            + '</div></main>' + footer('/'))


# ---------------------------------------------------------------- counties shell
def counties_shell(counties):
    largest = max(counties, key=lambda k: int(k['pop2020']))
    by_region = ''
    for r, ks in REGION_COUNTIES.items():
        items = ''.join(f'<a href="/counties/{slug(k)}/">{e(k)} County<small>seat: {e(next(c["seat"] for c in counties if c["name"] == k))} &middot; pop. {n(next(c["pop2020"] for c in counties if c["name"] == k))}</small></a>'
                        for k in sorted(ks, key=lambda k: -int(next(c['pop2020'] for c in counties if c['name'] == k))))
        by_region += f'<h3 class="letter"><a href="/regions/{REGION_SLUGS[r]}/" style="color:inherit">{e(r)}</a></h3><nav class="dir-list">{items}</nav>'
    title = 'Washington Counties Map & List: All 39 Counties and Seats'
    desc = 'Map and list of all 39 Washington counties with county seats, 2020 Census population and number of cities. Click any county for its cities, history and guide.'
    return (head(title, desc, '/counties/', extra='<!--county-schema--><!--/county-schema-->' + bread_ld('/counties/', 'Washington Counties') + PAGE_CSS, up='/')
            + header('/') + ticker_html('counties') + alert_banner()
            + '<div class="hero"><div class="wrap"><h1>Washington Counties: Map &amp; List of All 39 Counties</h1>'
            + '<p>Browse all 39 Washington counties, each with its county seat, population, incorporated cities and towns, and official links.</p></div></div>'
            + '<main><div class="wrap">' + crumbs(('Washington Counties', None))
            + '<div class="stat-row"><div class="stat"><b>39</b><span>Counties</span></div><div class="stat"><b>281</b><span>Cities &amp; towns</span></div>'
            + f'<div class="stat"><b>{e(largest["name"])}</b><span>Most populous county</span></div><div class="stat"><b>7</b><span>Regions</span></div></div>'
            + '</div><section class="wide"><div class="wrap"><!--county-table--><!--/county-table--></div></section><div class="wrap">'
            + '<h2 class="section-title">Washington Counties A&ndash;Z</h2><!--county-az--><!--/county-az-->'
            + '<h2 class="section-title">Counties by Region</h2><p class="section-sub">Washington&rsquo;s counties grouped into the seven regions used on this site, largest county first.</p>'
            + by_region + '</div></main>' + footer('/', '<br>Population: U.S. Census Bureau 2020.'))


# ---------------------------------------------------------------- moving guide
def moving_page(cities):
    def link(name): return f'<a href="/cities/{slug(name)}/">{e(name)}</a>'
    faq = [('Does Washington have a state income tax?', 'No. Washington does not tax wages or other personal income. It does tax long-term capital gains above a large annual threshold, and it collects sales tax, property tax and a business and occupation (B&amp;O) tax on businesses.'),
           ('What is the sales tax in Washington?', 'The state sales tax is 6.5%. Cities, counties and transit districts add local sales tax, so the combined rate is roughly 7.6% to 10.6% depending on where you shop. Check any address with the <a href="https://dor.wa.gov/"' + EXT + '>Department of Revenue</a>.'),
           ('How long do I have to get a Washington driver license after moving?', 'New residents have 30 days to get a Washington driver license, and vehicles must be registered in Washington within 30 days of becoming a resident. You need your Washington license before you can register a vehicle.'),
           ('How do I register to vote in Washington?', 'Register online at <a href="https://voter.votewa.gov/"' + EXT + '>VoteWA</a> with a Washington driver license or ID. Washington votes by mail: every registered voter is mailed a ballot for each election.'),
           ('Where do I sign up for health insurance in Washington?', 'Use <a href="https://www.wahealthplanfinder.org/"' + EXT + '>Washington Healthplanfinder</a>, the state marketplace, for private plans and Apple Health (Medicaid).'),
           ('What are the most affordable places to live in Washington?', 'Housing costs are generally highest in King County and around Puget Sound and lowest east of the Cascades. Spokane, Yakima, the Tri-Cities and many smaller towns in Central and Eastern Washington cost far less than Seattle. Compare cities on our <a href="/regions/">regions</a> pages.')]
    faq_html, faq_ld = faq_block(faq, 'Moving to Washington: Frequently Asked Questions')
    steps = [('Pick a region and a city', f'Washington&rsquo;s two halves feel like different states. The west side ({link("Seattle")}, {link("Tacoma")}, {link("Olympia")}, {link("Vancouver")}) is mild, wet and pricier; the east side ({link("Spokane")}, {link("Yakima")}, {link("Kennewick")}, {link("Wenatchee")}) is sunnier and drier, with hot summers, cold winters and lower housing costs. Start with the <a href="/regions/">seven regions</a> and open any city for population, schools and utilities.'),
             ('Line up housing', 'Compare listings for the specific neighborhood you want, and remember that commute times around Puget Sound can vary sharply with bridges, ferries and traffic. First-time buyers can check down-payment help through the <a href="https://www.wshfc.org/"' + EXT + '>Washington State Housing Finance Commission</a>.'),
             ('Find work', 'Search jobs and get free help through <a href="https://www.worksourcewa.com/"' + EXT + '>WorkSource Washington</a>. The state&rsquo;s Employment Security Department (<a href="https://esd.wa.gov/"' + EXT + '>ESD</a>) runs unemployment insurance and Paid Family and Medical Leave.'),
             ('Set up utilities', 'Electricity comes from an investor-owned utility, a public utility district (PUD) or a city utility depending on your address &mdash; see the utility list below. Water, sewer and garbage are usually handled by your city.'),
             ('Get your license and register your vehicles', 'Within 30 days of moving, get a Washington driver license from the <a href="https://dol.wa.gov/"' + EXT + '>Department of Licensing</a> and register your vehicles. Bring your out-of-state license and proof of identity and residence.'),
             ('Register to vote', 'Register at <a href="https://voter.votewa.gov/"' + EXT + '>VoteWA</a>. Ballots arrive by mail and can be returned by mail or at a county drop box.'),
             ('Enroll children in school', 'Contact the school district for your address; district and school lists are on each city page and through <a href="https://ospi.k12.wa.us/"' + EXT + '>OSPI</a>, the state education agency.')]
    steps_html = '<ol class="steps">' + ''.join(f'<li><h3>{t}</h3><p>{d}</p></li>' for t, d in steps) + '</ol>'
    util = [('Puget Sound Energy', 'https://www.pse.com/', 'electricity and natural gas across much of western Washington, plus Kittitas County'),
            ('Seattle City Light', 'https://www.seattle.gov/city-light', 'Seattle and some neighboring cities'),
            ('Tacoma Power', 'https://www.mytpu.org/', 'Tacoma and nearby Pierce County communities'),
            ('Snohomish County PUD', 'https://www.snopud.com/', 'Snohomish County and Camano Island'),
            ('Clark Public Utilities', 'https://www.clarkpublicutilities.com/', 'Clark County (Vancouver area)'),
            ('Avista', 'https://www.myavista.com/', 'electricity and gas in Spokane and much of Eastern Washington'),
            ('Pacific Power', 'https://www.pacificpower.net/', 'Yakima and Walla Walla areas'),
            ('County PUDs', '', 'Chelan, Douglas, Grant, Benton, Franklin, Cowlitz, Lewis, Grays Harbor, Mason, Clallam and other counties have public utility districts'),
            ('Cascade Natural Gas', 'https://www.cngc.com/', 'natural gas in many smaller cities statewide'),
            ('NW Natural', 'https://www.nwnatural.com/', 'natural gas in Clark County')]
    util_html = '<ul style="padding-left:20px">' + ''.join(
        f'<li style="padding:4px 0"><strong>' + (f'<a href="{u}"{EXT}>{e(nm)}</a>' if u else e(nm)) + f'</strong> &mdash; {e(d)}</li>' for nm, u, d in util) + '</ul>'
    title = 'Moving to Washington: Taxes, Costs, Licensing & Best Cities'
    desc = 'Moving to Washington State? No income tax, sales tax rates, housing, utilities, the 30-day license deadline, schools and a step-by-step moving checklist.'
    path = '/moving-to-washington/'
    guide_ld = ld({'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'description': desc, 'url': f'{BASE_URL}{path}',
                   'publisher': {'@id': f'{BASE_URL}/#organization'}})
    return (head(title, desc, path, 'article', extra=guide_ld + faq_ld + bread_ld(path, 'Moving to Washington') + PAGE_CSS, up='/')
            + header('/') + ticker_html('moving') + alert_banner()
            + f'<div class="hero region-hero">{state_silhouette()}<div class="wrap"><h1>Moving to Washington</h1>'
            + '<p>Taxes, housing, utilities, licensing deadlines, schools and a step-by-step checklist for your move to the Evergreen State.</p></div></div>'
            + '<main><div class="wrap">' + crumbs(('Moving to Washington', None))
            + '<nav class="toc" aria-label="On this page"><strong>On this page</strong><ol><li><a href="#checklist">Moving checklist</a></li><li><a href="#cost-of-living">Taxes &amp; cost of living</a></li>'
            + '<li><a href="#where">Where to live</a></li><li><a href="#utilities">Utilities</a></li><li><a href="#licensing">Driver license &amp; vehicles</a></li><li><a href="#resources">Official resources</a></li><li><a href="#faq">FAQ</a></li></ol></nav>'
            + f'<h2 class="st" id="checklist">Moving Checklist</h2>{steps_html}'
            + '<h2 class="st" id="cost-of-living">Taxes and Cost of Living</h2><section class="prose">'
            + '<p><strong>No income tax.</strong> Washington is one of a handful of states with no personal income tax on wages. That is the biggest financial difference for most people moving here, especially from Oregon, California or Idaho.</p>'
            + '<p><strong>Sales tax.</strong> The state rate is 6.5%, and local sales taxes push the combined rate to roughly 7.6% to 10.6%. Groceries and prescription drugs are exempt. Vehicle purchases also carry sales tax plus registration fees.</p>'
            + '<p><strong>Other taxes.</strong> Property taxes are set locally and vary by county and levy. Washington taxes long-term capital gains above a high annual threshold and has a state estate tax. Businesses pay the business and occupation (B&amp;O) tax on gross receipts.</p>'
            + '<p><strong>Housing.</strong> Housing is the largest cost difference between communities. Prices and rents are highest in King County and the Eastside, somewhat lower in Pierce, Snohomish, Thurston and Clark counties, and generally much lower east of the Cascades. Check current listings and the <a href="https://www.wshfc.org/"' + EXT + '>WSHFC</a> buyer programs before you commit.</p></section>'
            + '<h2 class="st" id="where">Where to Live: Washington by Region</h2><div class="cards">'
            + ''.join(f'<a class="card" href="/regions/{REGION_SLUGS[r]}/"><h3>{e(r)}</h3><p>{e(REGION_CONTENT[r]["living"][:200].rsplit(" ", 1)[0])}&hellip;</p><span class="go">{e(r)} guide &rarr;</span></a>' for r in REGION_SLUGS)
            + '</div>'
            + f'<h2 class="st" id="utilities">Utilities</h2><section class="prose"><p>Washington has a mix of investor-owned utilities, public utility districts (PUDs) and city-owned utilities, and the provider depends on your exact address. Each <a href="/cities/">city page</a> lists the main electric utility for that area.</p>{util_html}'
            + '<p>For internet service, compare providers for your address on the <a href="https://broadbandmap.fcc.gov/"' + EXT + '>FCC National Broadband Map</a>.</p></section>'
            + '<h2 class="st" id="licensing">Driver License and Vehicles</h2><section class="prose">'
            + '<p>Washington gives new residents <strong>30 days</strong> to get a Washington driver license, and vehicles must be registered here within 30 days of becoming a resident. Get your license first: you need it before you can register a vehicle. Both are handled by the <a href="https://dol.wa.gov/"' + EXT + '>Department of Licensing (DOL)</a>, and vehicle registration is also offered by county auditors and vehicle licensing offices.</p>'
            + '<p>Drivers in the Seattle area should know about tolls on SR 520, SR 99 and the I-405 and SR 167 express lanes, which use the <a href="https://wsdot.wa.gov/travel/roads-bridges/toll-roads-bridges-tunnels/good-go"' + EXT + '>Good To Go!</a> pass. In winter, mountain passes can require traction tires or chains; check <a href="https://wsdot.com/travel/real-time/mountainpasses"' + EXT + '>WSDOT pass reports</a>.</p></section>'
            + '<h2 class="st" id="resources">Official Resources for New Residents</h2><div class="cards">'
            + '<div class="card"><h3>&#128188; Jobs</h3><ul><li><a href="https://www.worksourcewa.com/"' + EXT + '>WorkSource Washington</a></li><li><a href="https://esd.wa.gov/"' + EXT + '>Employment Security Department</a></li></ul></div>'
            + '<div class="card"><h3>&#127973; Health &amp; Assistance</h3><ul><li><a href="https://www.wahealthplanfinder.org/"' + EXT + '>Washington Healthplanfinder</a></li><li><a href="https://www.washingtonconnection.org/"' + EXT + '>Washington Connection (food &amp; cash)</a></li><li><a href="https://wa211.org/"' + EXT + '>Washington 211</a></li></ul></div>'
            + '<div class="card"><h3>&#127891; Schools</h3><ul><li><a href="https://ospi.k12.wa.us/"' + EXT + '>OSPI (K-12)</a></li><li>School lists on every <a href="/cities/">city page</a></li></ul></div>'
            + '<div class="card"><h3>&#127963; Government</h3><ul><li><a href="https://wa.gov/"' + EXT + '>WA.gov</a></li><li><a href="https://dor.wa.gov/"' + EXT + '>Department of Revenue</a></li><li><a href="https://voter.votewa.gov/"' + EXT + '>VoteWA</a></li></ul></div></div>'
            + '<div id="faq"></div>' + faq_html
            + '<p class="back"><a href="/">&larr; Home</a> &middot; <a href="/visit-washington/">Visiting Washington &rarr;</a></p></div></main>' + footer('/'))


# ---------------------------------------------------------------- visiting guide
def visit_page(cities):
    def link(name): return f'<a href="/cities/{slug(name)}/">{e(name)}</a>'
    tops = [('&#127956;&#65039; Mount Rainier National Park', 'https://www.nps.gov/mora/', 'Wildflower meadows at Paradise and Sunrise, old-growth forest and glacier views on the state&rsquo;s highest peak.'),
            ('&#127794; Olympic National Park', 'https://www.nps.gov/olym/', 'Glacier-capped mountains, the Hoh Rain Forest and wild Pacific beaches, all in one park.'),
            ('&#9968;&#65039; North Cascades National Park', 'https://www.nps.gov/noca/', 'Jagged peaks and turquoise Diablo Lake along the North Cascades Highway (State Route 20), open roughly late spring to fall.'),
            ('&#127755; Mount St. Helens', 'https://www.fs.usda.gov/giffordpinchot', 'The 1980 eruption&rsquo;s blast zone, the Ape Cave lava tube and Johnston Ridge views, managed as a national volcanic monument.'),
            ('&#9972; Puget Sound &amp; the San Juan Islands', 'https://wsdot.wa.gov/travel/washington-state-ferries', 'Ride Washington State Ferries to Bainbridge Island, Whidbey Island or the San Juans for orca watching, kayaking and island towns.'),
            ('&#127863; Wine &amp; orchard country', 'https://www.washingtonwine.org/', 'Walla Walla, the Yakima Valley, Red Mountain and Lake Chelan anchor the nation&rsquo;s second-largest wine industry.')]
    tops_html = ''.join(f'<a class="card" href="{u}"{EXT}><h3>{t}</h3><p>{d}</p><span class="go">Official site &rarr;</span></a>' for t, u, d in tops)
    seasons = [('Summer (July&ndash;September)', 'The driest, sunniest stretch on the west side and the best time for Mount Rainier&rsquo;s meadows, the North Cascades Highway and the islands. Book ferries, campsites and park lodging early.'),
               ('Fall (October&ndash;November)', 'Harvest season east of the Cascades: apples, wine-country crush events and Leavenworth&rsquo;s Oktoberfest. Rain returns to the west side, and mountain roads such as SR 20 close for winter.'),
               ('Winter (December&ndash;March)', 'Skiing at Crystal Mountain, Stevens Pass, Snoqualmie, Mount Baker and Mission Ridge, storm watching on the coast and holiday lights in Leavenworth. Check pass conditions before driving the Cascades.'),
               ('Spring (April&ndash;June)', 'The Skagit Valley Tulip Festival in April, waterfalls at full flow and wildflowers in the Columbia Gorge and on the dry east side. Higher park roads open gradually through June.')]
    seasons_html = ''.join(f'<div class="card"><h3>{t}</h3><p style="font-size:.93rem">{d}</p></div>' for t, d in seasons)
    drives = [('Cascade Loop', 'A roughly 440-mile loop over the North Cascades Highway and Stevens Pass through ' + link('Leavenworth') + ', ' + link('Chelan') + ', ' + link('Winthrop') + ' and Whidbey Island.'),
              ('Olympic Peninsula Loop (US 101)', 'Circles Olympic National Park via ' + link('Port Angeles') + ', ' + link('Forks') + ' and the coast, with rainforest and beach side trips.'),
              ('Chuckanut Drive (SR 11)', 'A short cliffside drive above Samish Bay between Burlington and ' + link('Bellingham') + '.'),
              ('Mountains to Sound (I-90)', 'From Seattle&rsquo;s waterfront over Snoqualmie Pass to ' + link('Ellensburg') + ', past Snoqualmie Falls and the Cascade foothills.'),
              ('Columbia River Gorge (SR 14)', 'The Washington side of the Gorge, from ' + link('Camas') + ' past Beacon Rock to ' + link('Stevenson') + ' and ' + link('Goldendale') + '.')]
    drives_html = '<ul style="padding-left:20px">' + ''.join(f'<li style="padding:5px 0"><strong>{t}</strong> &mdash; {d}</li>' for t, d in drives) + '</ul>'
    faq = [('Do I need a pass to visit Washington state parks?', 'Yes. A Discover Pass is required for vehicle access to Washington State Parks and to recreation lands managed by the Department of Natural Resources and the Department of Fish and Wildlife. The annual pass costs $45 (since October 2025), and one-day passes are also sold. National parks charge their own entrance fees.'),
           ('How many national parks are in Washington?', 'Three: Mount Rainier, Olympic and North Cascades. Washington also has national monuments and historic sites, including Mount St. Helens and the Manhattan Project site at Hanford.'),
           ('Do I need a reservation for Washington State Ferries?', 'Reservations are available and recommended on some routes, including the San Juan Islands and Port Townsend&ndash;Coupeville. Most other routes are first-come, first-served. Check schedules and wait times with <a href="https://wsdot.wa.gov/travel/washington-state-ferries"' + EXT + '>Washington State Ferries</a>.'),
           ('When is the best time to visit Washington?', 'July through September brings the most reliable sunshine on the west side and full access to mountain roads and trails. Spring and fall are quieter, and winter is ski season.'),
           ('Is the North Cascades Highway open all year?', 'No. State Route 20 through the North Cascades closes for the winter, usually from around November until spring, because of avalanche danger. Check <a href="https://wsdot.com/travel/real-time/mountainpasses"' + EXT + '>WSDOT</a> for current status.')]
    faq_html, faq_ld = faq_block(faq, 'Visiting Washington: Frequently Asked Questions')
    title = 'Visit Washington: National Parks, Islands, Road Trips & Travel Tips'
    desc = 'Plan a Washington State trip: Mount Rainier, Olympic and North Cascades national parks, the San Juan Islands, wine country, scenic drives and when to go.'
    path = '/visit-washington/'
    guide_ld = ld({'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'description': desc, 'url': f'{BASE_URL}{path}',
                   'publisher': {'@id': f'{BASE_URL}/#organization'}})
    regions_html = ''.join(f'<a class="card" href="/regions/{REGION_SLUGS[r]}/"><h3>{e(r)}</h3><p>{e(REGION_CONTENT[r]["visiting"][:190].rsplit(" ", 1)[0])}&hellip;</p><span class="go">{e(r)} guide &rarr;</span></a>' for r in REGION_SLUGS)
    return (head(title, desc, path, 'article', extra=guide_ld + faq_ld + bread_ld(path, 'Visit Washington') + PAGE_CSS, up='/')
            + header('/') + ticker_html('visit') + alert_banner()
            + f'<div class="hero region-hero">{state_silhouette()}<div class="wrap"><h1>Visit Washington</h1>'
            + '<p>Volcanoes, rainforests, island ferries and wine country &mdash; plan a trip across the Evergreen State.</p></div></div>'
            + '<main><div class="wrap">' + crumbs(('Visit Washington', None))
            + f'<h2 class="st">Top Washington Experiences</h2><div class="cards">{tops_html}</div>'
            + f'<h2 class="st">Seattle and the Cities</h2><section class="prose"><p>{link("Seattle")} is the usual starting point: Pike Place Market, the Space Needle and Seattle Center, the waterfront and a ferry ride across Elliott Bay. {link("Tacoma")} has its Museum District and Point Defiance Park, {link("Spokane")} has Riverfront Park around Spokane Falls, and {link("Walla Walla")}, {link("Leavenworth")}, {link("Port Townsend")} and {link("Friday Harbor")} make memorable small-town bases.</p></section>'
            + f'<h2 class="st">Best Time to Visit</h2><div class="cards">{seasons_html}</div>'
            + f'<h2 class="st">Scenic Drives</h2><section class="prose">{drives_html}<p>Before crossing the Cascades between November and April, check <a href="https://wsdot.com/travel/real-time/mountainpasses"{EXT}>WSDOT mountain pass reports</a> for traction tire and chain requirements.</p></section>'
            + f'<h2 class="st">Washington by Region</h2><div class="cards">{regions_html}</div>'
            + '<h2 class="st">Plan Ahead</h2><div class="cards">'
            + '<div class="card"><h3>&#127967;&#65039; Parks &amp; passes</h3><ul><li><a href="https://parks.wa.gov/"' + EXT + '>Washington State Parks</a></li><li><a href="https://www.nps.gov/state/wa/index.htm"' + EXT + '>National parks in Washington</a></li></ul></div>'
            + '<div class="card"><h3>&#128652; Getting around</h3><ul><li><a href="https://wsdot.wa.gov/travel/washington-state-ferries"' + EXT + '>Washington State Ferries</a></li><li><a href="https://wsdot.com/travel/real-time/map"' + EXT + '>WSDOT travel map</a></li><li><a href="https://www.soundtransit.org/"' + EXT + '>Sound Transit light rail</a></li></ul></div>'
            + '<div class="card"><h3>&#128506;&#65039; Trip ideas</h3><ul><li><a href="https://stateofwatourism.com/"' + EXT + '>State of Washington Tourism</a></li><li><a href="https://visitseattle.org/"' + EXT + '>Visit Seattle</a></li></ul></div></div>'
            + faq_html
            + '<p class="back"><a href="/">&larr; Home</a> &middot; <a href="/moving-to-washington/">Moving to Washington &rarr;</a></p></div></main>' + footer('/'))
