#!/usr/bin/env python3
"""Washington Information - site generator (adapted from the Oregon Information generator).

Builds every city page, every county page, the cities A-Z directory, the About /
Contact / Privacy pages, sitemap.xml and robots.txt from:
  data/cities.json    (281 incorporated cities and towns: 2020/2010 Census, area, incorporation,
                       coordinates, official website, Wikipedia summary + photo)
  data/counties.json  (39 counties)
  custom_city_content.json (optional hand-written extras, keyed like "portland")
Data refresh: WIKI_OFFLINE=1 python3 data/fetch_wa_data.py; python3 data/build_aux_data.py; python3 data/build_schools.py   |   Build: python3 generate_city_pages.py
"""

import hashlib, html, json, math, os, posixpath, re, shutil, subprocess
from datetime import date

BASE_URL     = 'https://washingtoninformation.com'
SITE_NAME    = 'Washington Information'
CONTACT_EMAIL = 'contact@washingtoninformation.com'
ANALYTICS_ID = 'G-ZKFJSK6FM1'   # GA4 measurement ID (loaded directly with gtag.js, alongside Tag Manager)
GTM_ID       = 'GTM-N26D57SS'   # Google Tag Manager container for washingtoninformation.com
GTM_HEAD     = (f'<script async src="https://www.googletagmanager.com/gtm.js?id={GTM_ID}"></script>'
                '<script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag(\'js\', new Date());</script>')
OUT          = 'public'   # everything Cloudflare publishes
TODAY        = date.today().isoformat()
DEFAULT_IMG  = f'{BASE_URL}/assets/og-image.png'
SLUG_OVERRIDES = {}

COUNTY_INFO = {   # county -> (region, main electric utilities; residents confirm by address)
 'King':('Seattle Metro','Puget Sound Energy / Seattle City Light'),'Pierce':('Seattle Metro','Puget Sound Energy / Tacoma Power'),
 'Snohomish':('Seattle Metro','Snohomish County PUD'),'Kitsap':('Seattle Metro','Puget Sound Energy'),
 'Whatcom':('North Sound','Puget Sound Energy'),'Skagit':('North Sound','Puget Sound Energy'),
 'San Juan':('North Sound','OPALCO'),'Island':('North Sound','Puget Sound Energy'),
 'Clallam':('Olympic Peninsula','Clallam County PUD'),'Jefferson':('Olympic Peninsula','Jefferson County PUD'),
 'Grays Harbor':('Olympic Peninsula','Grays Harbor PUD'),'Pacific':('Olympic Peninsula','Pacific County PUD'),
 'Mason':('Olympic Peninsula','Mason County PUD 3'),
 'Thurston':('Southwest Washington','Puget Sound Energy'),'Lewis':('Southwest Washington','Lewis County PUD'),
 'Cowlitz':('Southwest Washington','Cowlitz County PUD'),'Clark':('Southwest Washington','Clark Public Utilities'),
 'Wahkiakum':('Southwest Washington','Wahkiakum PUD'),'Skamania':('Southwest Washington','Skamania County PUD'),
 'Chelan':('Central Washington','Chelan County PUD'),'Okanogan':('Central Washington','Okanogan County PUD'),
 'Kittitas':('Central Washington','Puget Sound Energy / Kittitas PUD'),'Yakima':('Central Washington','Pacific Power'),
 'Klickitat':('Central Washington','Klickitat PUD'),'Douglas':('Central Washington','Douglas County PUD'),
 'Grant':('Central Washington','Grant County PUD'),
 'Spokane':('Eastern Washington','Avista / Inland Power & Light'),'Stevens':('Eastern Washington','Avista'),
 'Pend Oreille':('Eastern Washington','Pend Oreille County PUD'),'Ferry':('Eastern Washington','Ferry County PUD'),
 'Lincoln':('Eastern Washington','Avista'),'Whitman':('Eastern Washington','Avista'),'Adams':('Eastern Washington','Avista / Big Bend Electric Cooperative'),
 'Benton':('Southeast Washington','Benton PUD'),'Franklin':('Southeast Washington','Franklin PUD'),
 'Walla Walla':('Southeast Washington','Pacific Power'),'Columbia':('Southeast Washington','Pacific Power / Columbia REA'),
 'Garfield':('Southeast Washington','Pacific Power'),'Asotin':('Southeast Washington','Avista'),
}

COUNTY_ELECTIONS = {}   # no hand-checked list yet: voter_card() falls back to the county's official website

UTILITY_URLS = {
 'Puget Sound Energy': 'https://www.pse.com/',
 'Seattle City Light': 'https://www.seattle.gov/city-light',
 'Tacoma Power': 'https://www.mytpu.org/',
 'Snohomish County PUD': 'https://www.snopud.com/',
 'OPALCO': 'https://www.opalco.com/',
 'Clallam County PUD': 'https://www.clallampud.net/',
 'Jefferson County PUD': 'https://www.jeffpud.org/',
 'Grays Harbor PUD': 'https://www.ghpud.org/',
 'Pacific County PUD': 'https://www.pacificpud.org/',
 'Mason County PUD 3': 'https://www.masonpud3.org/',
 'Lewis County PUD': 'https://www.lcpud.org/',
 'Cowlitz County PUD': 'https://www.cowlitzpud.org/',
 'Clark Public Utilities': 'https://www.clarkpublicutilities.com/',
 'Wahkiakum PUD': '',
 'Skamania County PUD': 'https://www.skamaniapud.com/',
 'Chelan County PUD': 'https://www.chelanpud.org/',
 'Okanogan County PUD': 'https://www.okpud.org/',
 'Kittitas PUD': 'https://www.kittitaspud.com/',
 'Pacific Power': 'https://www.pacificpower.net/',
 'Klickitat PUD': 'https://www.klickpud.com/',
 'Douglas County PUD': 'https://douglaspud.org/',
 'Grant County PUD': 'https://www.grantpud.org/',
 'Avista': 'https://www.myavista.com/',
 'Inland Power & Light': 'https://www.inlandpower.com/',
 'Pend Oreille County PUD': 'https://www.popud.org/',
 'Ferry County PUD': '',
 'Big Bend Electric Cooperative': 'https://www.bbec.org/',
 'Benton PUD': 'https://www.bentonpud.org/',
 'Franklin PUD': 'https://www.franklinpud.com/',
 'Columbia REA': 'https://www.columbiarea.com/',
 'Cascade Natural Gas': 'https://www.cngc.com/',
 'NW Natural': 'https://www.nwnatural.com/',
}


def utility_links_html(electric_str):
    """'Avista / Inland Power & Light' -> linked names joined by ' / ' (plain text when no URL is known)."""
    parts = []
    for name in [p.strip() for p in (electric_str or '').split(' / ') if p.strip()]:
        url = UTILITY_URLS.get(name)
        parts.append(f'<a href="{e(url)}" target="_blank" rel="noopener">{e(name)}</a>' if url else e(name))
    return ' / '.join(parts)


STATE_LINKS = [
 ('WA.gov', 'https://wa.gov/'),
 ('Washington DOL (licensing)', 'https://dol.wa.gov/'),
 ('WorkSource Washington', 'https://www.worksourcewa.com/'),
 ('OSPI (K-12 education)', 'https://ospi.k12.wa.us/'),
 ('Apple Health (Medicaid)', 'https://www.hca.wa.gov/free-or-low-cost-health-care'),
 ('Washington Connection (food & cash benefits)', 'https://www.washingtonconnection.org/'),
 ('Northwest Harvest food banks', 'https://www.northwestharvest.org/'),
 ('Washington 211', 'https://wa211.org/'),
 ('Washington State Housing Finance Commission', 'https://www.wshfc.org/'),
 ('State of Washington Tourism', 'https://stateofwatourism.com/'),
]

# Counties map directly to the 7 public-facing regions (sub-region == region)
REGION_SLUGS = {
 'Seattle Metro':'seattle-metro','North Sound':'north-sound','Olympic Peninsula':'olympic-peninsula',
 'Southwest Washington':'southwest-washington','Central Washington':'central-washington',
 'Eastern Washington':'eastern-washington','Southeast Washington':'southeast-washington',
}
BIG_REGION_MAP = {r: r for r in REGION_SLUGS}

REGION_COUNTIES = {
 'Seattle Metro':['King','Pierce','Snohomish','Kitsap'],
 'North Sound':['Whatcom','Skagit','San Juan','Island'],
 'Olympic Peninsula':['Clallam','Jefferson','Grays Harbor','Pacific','Mason'],
 'Southwest Washington':['Thurston','Lewis','Cowlitz','Clark','Wahkiakum','Skamania'],
 'Central Washington':['Chelan','Okanogan','Kittitas','Yakima','Klickitat','Douglas','Grant'],
 'Eastern Washington':['Spokane','Stevens','Pend Oreille','Ferry','Lincoln','Whitman','Adams'],
 'Southeast Washington':['Benton','Franklin','Walla Walla','Columbia','Garfield','Asotin'],
}

REGION_CONTENT = {
 'Seattle Metro':{
  'desc':"Washington's largest metro area around Puget Sound: Seattle, Tacoma, Bellevue, Everett and dozens of suburbs. Home to Amazon, Microsoft and Boeing, with ferries, mountains and water in every direction.",
  'hero_sub':"Seattle, Tacoma, Bellevue and Everett — tech, ferries and mountain views around Puget Sound.",
  'living':"More than half of all Washingtonians live in King, Pierce, Snohomish and Kitsap counties. Seattle and the Eastside (Bellevue, Redmond, Kirkland) hold the region's big employers in technology, aerospace, health care and trade, and they also carry the state's highest housing costs. Tacoma, Everett and the south King County cities (Kent, Renton, Auburn, Federal Way) are generally more affordable. Sound Transit Link light rail, regional buses, the Sounder commuter train and Washington State Ferries connect much of the metro, and Kitsap County residents often commute to Seattle by ferry.",
  'visiting':"Pike Place Market, the Space Needle and Seattle Center, the Seattle waterfront and the Museum of Pop Culture top most first visits. Ferries to Bainbridge Island and Bremerton make easy scenic day trips, and Tacoma has its Museum District and Point Defiance Park. Mount Rainier National Park is about two hours from Seattle, and Snoqualmie Falls and the Cascade passes are under an hour east.",
  'highlights':["Seattle — Washington's largest city: Pike Place Market, Space Needle, waterfront","Tacoma — Museum of Glass, Point Defiance Park, Mount Rainier views","Bellevue & Redmond — Eastside tech hub, home of Microsoft","Everett — Boeing's widebody factory and the Future of Flight tour","Bainbridge Island — a 35-minute ferry ride from downtown Seattle","Gig Harbor & Poulsbo — waterfront towns on the Kitsap side of the Sound"],
 },
 'North Sound':{
  'desc':"The northwest corner of Washington between Seattle and Canada: Bellingham, the Skagit Valley tulip fields, Whidbey Island, the San Juan Islands and the gateway to North Cascades National Park.",
  'hero_sub':"Islands, tulip fields and the North Cascades — Washington's northwest corner up to the Canadian border.",
  'living':"Bellingham is the region's largest city, a college town (Western Washington University) with a strong outdoor culture and Mount Baker on the horizon. Mount Vernon and Burlington anchor the Skagit Valley's farm economy, Oak Harbor is home to Naval Air Station Whidbey Island, and Anacortes is the ferry port for the San Juans. Island living means planning around ferry schedules, and housing on the islands is limited and pricey; the valley towns are generally more affordable.",
  'visiting':"The Skagit Valley Tulip Festival fills the fields with color every April. Ferries from Anacortes reach the San Juan Islands for whale watching, kayaking and Friday Harbor. Chuckanut Drive is one of the state's prettiest short drives, Deception Pass State Park is among the most visited state parks, and the North Cascades Highway (State Route 20) crosses the mountains from late spring to fall.",
  'highlights':["Bellingham — Western Washington University, Fairhaven, Mount Baker skiing","Mount Vernon — Skagit Valley Tulip Festival every April","Anacortes — ferry gateway to the San Juan Islands","Friday Harbor — San Juan Island's port town, whale watching","Oak Harbor & Coupeville — Whidbey Island, Ebey's Landing","La Conner — waterfront arts town in the Skagit Valley"],
 },
 'Olympic Peninsula':{
  'desc':"Olympic National Park's rainforests, glacier peaks and wild beaches, plus the Pacific coast from Ocean Shores to Long Beach. Small towns, Victorian Port Townsend and some of the wettest and wildest country in the Lower 48.",
  'hero_sub':"Rainforests, wild Pacific beaches and Olympic National Park — Washington's far west.",
  'living':"Port Angeles, Sequim and Port Townsend on the north side draw retirees and remote workers; Sequim sits in a rain shadow and gets far less rain than the rest of the peninsula. Aberdeen and Hoquiam on Grays Harbor and Shelton on Hood Canal are working towns built on timber, fishing and shellfish. Housing is generally cheaper than the Seattle metro, but health care, shopping and airports can be an hour or more away.",
  'visiting':"Olympic National Park covers mountains, the Hoh Rain Forest and miles of wild coastline such as Rialto and Ruby beaches. Hurricane Ridge rises above Port Angeles, Port Townsend has a Victorian downtown and a lively arts scene, and Forks is a base for the coast. Southward, Ocean Shores, Westport and the Long Beach Peninsula offer razor clamming, kite flying and storm watching.",
  'highlights':["Port Angeles — gateway to Hurricane Ridge and the Victoria ferry","Port Townsend — Victorian seaport, wooden boats and festivals","Sequim — lavender farms in the Olympic rain shadow","Forks — Hoh Rain Forest and coastal beaches base camp","Ocean Shores — drivable Pacific beach and razor clamming","Long Beach — a long peninsula of sand dunes, kites and clams"],
 },
 'Southwest Washington':{
  'desc':"The state capital Olympia, fast-growing Vancouver across the Columbia from Portland, Longview, Centralia and the country around Mount St. Helens and the Columbia River Gorge.",
  'hero_sub':"Olympia, Vancouver and Mount St. Helens — the capital region and the Columbia River country.",
  'living':"Olympia, Lacey and Tumwater form the capital metro, where state government is the largest employer. Vancouver, Camas, Battle Ground and Ridgefield in Clark County are among the fastest-growing cities in the state, partly because residents can work in Portland while living in a state that does not tax wages (Oregon still taxes income earned there). Longview, Kelso and Centralia are mid-sized river and rail towns with lower housing costs.",
  'visiting':"Mount St. Helens National Volcanic Monument, with the Johnston Ridge area and Ape Cave lava tube, is the region's headline sight. The Washington side of the Columbia River Gorge has Beacon Rock and Dog Mountain, Fort Vancouver National Historic Site recalls the fur trade, and Olympia's Capitol Campus and waterfront make an easy stop on I-5.",
  'highlights':["Olympia — the state capital, Capitol Campus and farmers market","Vancouver — Fort Vancouver and a booming waterfront","Camas & Washougal — gateway to the Columbia River Gorge","Longview — planned 1920s city on the Columbia","Centralia — historic downtown midway between Seattle and Portland","Stevenson — Gorge town near Beacon Rock and the Bridge of the Gods"],
 },
 'Central Washington':{
  'desc':"Sunny, dry country east of the Cascades: the Yakima Valley's hops and wine, Wenatchee's apples, Lake Chelan, Leavenworth's Bavarian village, the Okanogan and the Columbia Basin farms around Moses Lake.",
  'hero_sub':"Apples, hops, wine and sunshine — Washington's fruit bowl east of the Cascades.",
  'living':"Central Washington trades the west side's rain for hot summers, cold winters and plenty of sun. Yakima and Wenatchee are the regional hubs for health care and shopping, Ellensburg is home to Central Washington University, and Moses Lake anchors Columbia Basin farming and a growing data-center and manufacturing sector. Housing costs are well below the Puget Sound area, and agriculture remains the backbone of the economy.",
  'visiting':"Leavenworth's Bavarian-themed village is busiest for Oktoberfest and the winter lights. Lake Chelan is a summer playground with wineries along its shores, the Yakima Valley has dozens of wineries and hop farms, and the Columbia Gorge Amphitheatre near George hosts summer concerts. The Okanogan offers the Methow Valley's trails and ski touring around Winthrop.",
  'highlights':["Yakima — hop and wine country capital of the Yakima Valley","Wenatchee — \"Apple Capital of the World\" on the Columbia","Leavenworth — Bavarian village in the Cascade foothills","Chelan — lake resort town and wine region","Ellensburg — Central Washington University and the Ellensburg Rodeo","Winthrop — Old West-style town in the Methow Valley"],
 },
 'Eastern Washington':{
  'desc':"Spokane and the Inland Northwest: the state's second-largest city, the rolling wheat fields of the Palouse, Pullman's Washington State University and the forests and lakes of the northeast corner.",
  'hero_sub':"Spokane, the Palouse and the northeast woods — the Inland Northwest's big-sky country.",
  'living':"Spokane and Spokane Valley form the region's metro, with a large medical sector, Fairchild Air Force Base, Gonzaga University and housing that costs well below Seattle's. Pullman (Washington State University) and Cheney (Eastern Washington University) are college towns, and Liberty Lake and Airway Heights are fast-growing suburbs. Farther out, the Palouse and the northeast counties are rural, with small towns built on wheat, timber and ranching.",
  'visiting':"Spokane's Riverfront Park sits around Spokane Falls, the site of the Expo '74 world's fair. The Palouse's rolling hills are famous with photographers, Palouse Falls is the official state waterfall, and the northeast has Lake Roosevelt's shoreline and Mount Spokane State Park for skiing and hiking.",
  'highlights':["Spokane — Riverfront Park, Spokane Falls and Gonzaga","Spokane Valley — the region's second-largest city","Pullman — Washington State University on the Palouse","Cheney — Eastern Washington University","Colville — northeast hub near Lake Roosevelt","Colfax — county seat in the heart of the Palouse wheat country"],
 },
 'Southeast Washington':{
  'desc':"The Tri-Cities of Kennewick, Pasco and Richland where the Snake and Yakima rivers meet the Columbia, Walla Walla's wine country, and the Blue Mountains down to Clarkston on the Idaho border.",
  'hero_sub':"The Tri-Cities and Walla Walla — rivers, wine country and the Blue Mountains.",
  'living':"Kennewick, Pasco and Richland form one of the state's fastest-growing metro areas, with jobs at the Hanford cleanup, Pacific Northwest National Laboratory, agriculture and food processing. Summers are hot and winters are short and cold. Walla Walla is a historic small city with Whitman College and a large wine industry, and Clarkston faces Lewiston, Idaho, across the Snake River. Housing is typically far cheaper than the Puget Sound region.",
  'visiting':"Walla Walla has well over a hundred wineries and tasting rooms, and the Tri-Cities add their own wine routes, river trails and boating. The Manhattan Project National Historical Park offers tours of Hanford's B Reactor, Whitman Mission National Historic Site sits near Walla Walla, and Clarkston is a starting point for jet boat trips into Hells Canyon.",
  'highlights':["Kennewick — the largest of the Tri-Cities, Columbia Park","Richland — Hanford history and Pacific Northwest National Laboratory","Pasco — farmers market and the region's main airport","Walla Walla — wine country, Whitman College, historic downtown","Prosser — Yakima Valley wineries and the Walter Clore Wine Center","Clarkston — Snake River gateway to Hells Canyon"],
 },
}

# Unique hero taglines (key = city slug). Cities not listed get an auto-generated tagline.
CITY_TAGLINES = {
    "seattle": "The Emerald City — Washington's largest city on Puget Sound",
    "spokane": "The Lilac City — hub of the Inland Northwest on the Spokane River",
    "tacoma": "City of Destiny — museums, waterfront parks and Mount Rainier views",
    "vancouver": "Southwest Washington's largest city — on the Columbia across from Portland",
    "bellevue": "The Eastside's downtown — tech, shopping and parks across Lake Washington from Seattle",
    "kent": "Valley industrial and warehouse hub in south King County",
    "everett": "Snohomish County seat — home of Boeing's widebody jet factory",
    "renton": "Where the 737 is built — south end of Lake Washington",
    "spokane-valley": "Inland Northwest suburb along the Spokane River and Centennial Trail",
    "federal-way": "Halfway between Seattle and Tacoma — Wild Waves and the Rhododendron Garden",
    "yakima": "Heart of the Yakima Valley — hops, apples and wine country",
    "kirkland": "Lakefront Eastside city on Lake Washington",
    "bellingham": "City of Subdued Excitement — Western Washington University and Mount Baker views",
    "auburn": "Green River Valley city spanning King and Pierce counties",
    "kennewick": "Largest of the Tri-Cities — Columbia River parks and sunshine",
    "pasco": "Tri-Cities crossroads where the Snake River meets the Columbia",
    "marysville": "Fast-growing Snohomish County city north of Everett",
    "redmond": "Bicycle Capital of the Northwest — home of Microsoft",
    "sammamish": "Plateau suburb between Lake Sammamish and the Cascade foothills",
    "lakewood": "Pierce County city next to Joint Base Lewis-McChord",
    "richland": "Atomic Frontier City — Hanford history and science on the Columbia",
    "shoreline": "North Seattle neighbor on Puget Sound",
    "olympia": "Washington's capital city — at the southern tip of Puget Sound",
    "lacey": "Thurston County's growing neighbor to the state capital",
    "burien": "Puget Sound waterfront city south of Seattle",
    "bothell": "Biotech and university city on the Sammamish River",
    "lynnwood": "Snohomish County shopping and light rail hub",
    "edmonds": "Waterfront arts town with a ferry to Kingston",
    "longview": "A planned 1920s city on the Columbia River",
    "wenatchee": "Apple Capital of the World — at the confluence of the Wenatchee and Columbia",
    "mount-vernon": "Skagit Valley Tulip Festival hometown",
    "walla-walla": "The town so nice they named it twice — wine country and Whitman College",
    "pullman": "Home of Washington State University on the Palouse",
    "puyallup": "Home of the Washington State Fair in the Puyallup Valley",
    "issaquah": "Alpine-flavored town among the Issaquah Alps",
    "moses-lake": "Columbia Basin hub on its namesake lake",
    "ellensburg": "Rodeo city and home of Central Washington University",
    "port-angeles": "Gateway to Olympic National Park and the Victoria ferry",
    "port-townsend": "Victorian seaport at the entrance to Puget Sound",
    "sequim": "Lavender Capital of North America in the Olympic rain shadow",
    "anacortes": "Ferry gateway to the San Juan Islands",
    "friday-harbor": "San Juan Island's port town — orcas, kayaks and ferries",
    "oak-harbor": "Whidbey Island's largest city, home of NAS Whidbey Island",
    "coupeville": "Historic Whidbey Island town on Penn Cove",
    "la-conner": "Waterfront arts village in the Skagit Valley",
    "leavenworth": "Washington's Bavarian Village in the Cascade foothills",
    "chelan": "Sunny lake resort town and wine country",
    "winthrop": "Old West-themed town in the Methow Valley",
    "forks": "Rain forest gateway on the Olympic Peninsula",
    "aberdeen": "Grays Harbor port city — gateway to the Pacific coast",
    "hoquiam": "Historic timber port on Grays Harbor",
    "ocean-shores": "Pacific beach resort town on the North Beach peninsula",
    "long-beach": "Kite capital on the Long Beach Peninsula",
    "westport": "Charter fishing and surfing port on Grays Harbor",
    "shelton": "Christmas Town USA — timber and shellfish on Oakland Bay",
    "centralia": "Historic railroad town midway between Seattle and Portland",
    "chehalis": "Lewis County seat with a steam train and historic downtown",
    "camas": "Paper-mill town turned Gorge gateway on the Columbia",
    "battle-ground": "Fast-growing Clark County city near Lewisville Park",
    "ridgefield": "Wildlife refuge town on the Columbia River lowlands",
    "stevenson": "Columbia River Gorge town near the Bridge of the Gods",
    "goldendale": "Dark-sky town and home of the Goldendale Observatory",
    "gig-harbor": "Maritime City on a postcard-perfect harbor",
    "poulsbo": "Little Norway on Liberty Bay",
    "bainbridge-island": "Island city a ferry ride from downtown Seattle",
    "bremerton": "Navy shipyard city on Sinclair Inlet",
    "port-orchard": "Kitsap County seat on Sinclair Inlet",
    "snoqualmie": "Home of Snoqualmie Falls in the Cascade foothills",
    "north-bend": "Mountain town at the foot of Mount Si and Snoqualmie Pass",
    "enumclaw": "Gateway to Mount Rainier's Sunrise and Crystal Mountain",
    "sumner": "Rhubarb Pie Capital of the World in the Puyallup Valley",
    "steilacoom": "Washington's oldest incorporated town",
    "toppenish": "City of Murals on the Yakama Nation reservation",
    "sunnyside": "Yakima Valley farm town and wine country stop",
    "prosser": "Birthplace of Washington wine — Yakima Valley",
    "zillah": "Rattlesnake Hills wine trail town",
    "cle-elum": "Former coal-mining town gateway to the Cascades",
    "roslyn": "Historic mining town famous as TV's Cicely, Alaska",
    "grand-coulee": "Home of Grand Coulee Dam",
    "coulee-dam": "Company town built for Grand Coulee Dam",
    "omak": "Okanogan Valley hub and home of the Omak Stampede",
    "twisp": "Arts town in the Methow Valley",
    "colville": "Northeast Washington hub near Lake Roosevelt",
    "cheney": "Home of Eastern Washington University",
    "liberty-lake": "Planned lakeside city east of Spokane",
    "colfax": "Palouse county seat in the heart of wheat country",
    "palouse": "Small town on the Palouse River in the rolling wheat hills",
    "clarkston": "Snake River gateway to Hells Canyon",
    "dayton": "Victorian small town at the foot of the Blue Mountains",
    "pomeroy": "Garfield County's only incorporated town",
    "ritzville": "Historic wheat-country town on I-90",
    "republic": "Old gold-mining town in Ferry County",
    "newport": "Pend Oreille River town on the Idaho line",
    "davenport": "Lincoln County seat in the wheat country west of Spokane",
    "lynden": "Dutch heritage town near the Canadian border",
    "blaine": "Border town at the Peace Arch",
    "sedro-woolley": "Gateway to the North Cascades Highway",
    "burlington": "Skagit Valley crossroads of I-5 and the North Cascades Highway",
    "snohomish": "Antique Capital of the Northwest on the Snohomish River",
    "mukilteo": "Lighthouse town with a ferry to Whidbey Island",
    "arlington": "Stillaguamish Valley city with a historic airfield",
    "monroe": "Skykomish Valley town and Evergreen State Fair home",
    "lake-stevens": "Fast-growing lakeside city in Snohomish County",
    "mercer-island": "Island suburb in the middle of Lake Washington",
    "seatac": "Home of Seattle-Tacoma International Airport",
    "tukwila": "Southcenter shopping hub where I-5 meets I-405",
    "des-moines": "Marina town on Puget Sound south of Seattle",
    "tumwater": "Where Washington's first American settlement began, on the Deschutes River",
    "kelso": "Cowlitz County seat on the Cowlitz River",
    "east-wenatchee": "Douglas County city across the Columbia from Wenatchee",
    "ephrata": "Grant County seat in the Columbia Basin",
    "quincy": "Columbia Basin farm and data-center town near the Gorge Amphitheatre",
    "othello": "Columbia Basin farm town and sandhill crane festival host",
    "selah": "Yakima's northern neighbor and apple-packing town",
    "union-gap": "Yakima Valley city at the Ahtanum Ridge gap",
    "grandview": "Yakima Valley farm town on the lower valley wine trail",
    "college-place": "Walla Walla's college neighbor, home of Walla Walla University",
    "west-richland": "Fast-growing Tri-Cities suburb on the Yakima River",
    "benton-city": "Red Mountain wine district gateway",
    "connell": "Franklin County farm town",
}

# Per-region hero theme: gradient + short evocative line
REGION_THEME = {
    'Seattle Metro': ('#1b263b', '#415a77', 'Ferries, skylines and snowcapped peaks around the waters of Puget Sound.'),
    'North Sound': ('#0b3d4c', '#2a7f62', 'Island ferries, tulip fields and the jagged North Cascades.'),
    'Olympic Peninsula': ('#0b3b2e', '#1f7a5a', 'Mossy rainforests, glacier peaks and sea stacks on a wild Pacific shore.'),
    'Southwest Washington': ('#22313f', '#3b6e8f', 'The capital on Puget Sound, the Columbia River and the open crater of Mount St. Helens.'),
    'Central Washington': ('#5a3e1b', '#8a6d2c', 'Orchards, vineyards and sun-baked canyons east of the Cascades.'),
    'Eastern Washington': ('#4a3b1f', '#7a6a2d', 'Rolling Palouse wheat hills, pine forests and the falls of the Spokane River.'),
    'Southeast Washington': ('#5b2e2e', '#8c5a3c', 'River country, vineyards and the Blue Mountains on the Idaho line.'),
}

STATE_FACTS = [
 ('Statehood','November 11, 1889 (42nd state admitted to the Union)'),
 ('Capital','<a href="/cities/olympia/index.html">Olympia</a>'),
 ('Largest city','<a href="/cities/seattle/index.html">Seattle</a>'),
 ('Population (2020 Census)','7,705,281 (13th most populous state)'),
 ('Area','71,362 sq mi (18th largest state)'),
 ('Counties','39 (see <a href="/counties/index.html">all counties</a>)'),
 ('Incorporated cities and towns','281 (see <a href="/cities/index.html">all cities A–Z</a>)'),
 ('Geographic regions','7 (see <a href="/regions/index.html">all regions</a>)'),
 ('Nickname','The Evergreen State'),
 ('Motto','<em>Al-ki</em> (Chinook Jargon, “By and by”)'),
 ('State bird','American goldfinch (willow goldfinch)'),
 ('State flower','Coast rhododendron'),
 ('State tree','Western hemlock'),
 ('State fish','Steelhead trout'),
 ('State fruit','Apple'),
 ('State song','“Washington, My Home”'),
 ('Highest point','Mount Rainier, 14,411 ft (4,392 m)'),
 ('Longest river','Columbia River (forms most of the southern border with Oregon)'),
 ('Time zone','Pacific Time'),
 ('Abbreviation','WA (postal); Wash. (traditional)'),
 ('Income tax','None on wages and ordinary income today; taxes apply to large capital gains, and a 9.9% tax on income over $1 million is scheduled for 2028 (under court challenge)'),
]

CSS = ":root{--gd:#0e2a3b;--g:#1f6f6b;--gold:#e8835a;--blue:#1d5d8f;--bg:#f2f6f8;--tx:#1d2b33;--mu:#5b6b75}*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Source Sans 3',system-ui,sans-serif;color:var(--tx);line-height:1.6;background:#fff}h1,h2,h3{font-family:'Outfit',system-ui,sans-serif;line-height:1.25}.wrap{max-width:1000px;margin:0 auto;padding:0 24px}.hd{background:var(--gd);color:#fff;padding:14px 0;position:sticky;top:0;z-index:50}.hd nav{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:1.1rem;color:#fff;text-decoration:none}.badge{width:30px;height:30px;background:var(--gold);border-radius:50%;display:flex;align-items:center;justify-content:center}.nl{list-style:none;display:flex;gap:16px;flex-wrap:wrap}.nl a{color:#dbe7ee;text-decoration:none;font-weight:600;font-size:.9rem}.nl a:hover{color:var(--gold)}.hero{background:linear-gradient(160deg,var(--gd),var(--g));color:#fff;padding:52px 0 44px;margin-bottom:36px}.hero h1{font-size:clamp(1.6rem,4vw,2.4rem);max-width:760px}.hero p{color:#d9e9f0;margin-top:12px;max-width:640px}.crumbs{font-size:.88rem;color:var(--mu);padding:14px 0 0}.crumbs a{color:var(--blue);text-decoration:none}h2.st{font-size:1.45rem;color:var(--gd);margin:36px 0 16px;border-bottom:3px solid var(--g);padding-bottom:8px}.facts{background:var(--bg);border:1px solid #dfe7ec;border-radius:10px;padding:20px;margin:24px 0}.facts table{width:100%;border-collapse:collapse}.facts th{text-align:left;padding:9px;color:var(--gd);border-bottom:2px solid var(--g);width:35%;vertical-align:top}.facts td{padding:9px;border-bottom:1px solid #dfe7ec}.facts a,.prose a,.tbl a{color:var(--blue)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin:24px 0}.card{background:#fff;border:1px solid #dfe7ec;border-top:4px solid var(--g);border-radius:10px;padding:20px}.card h3{font-size:1rem;color:var(--gd);margin-bottom:10px}.card ul{list-style:none}.card li{padding:6px 0;border-bottom:1px dashed #dfe7ec;font-size:.92rem}.card a{color:var(--blue);text-decoration:none;font-weight:600}.faq details{background:#fff;border:1px solid #dfe7ec;border-radius:8px;margin:9px 0;padding:0 16px}.faq summary{cursor:pointer;font-weight:600;padding:13px 0;color:var(--gd)}.faq p{padding:0 0 14px;font-size:.94rem}.faq ul{padding-left:20px}.faq li{padding:3px 0}.faq a{color:var(--blue)}.back{margin-top:40px;padding-top:18px;border-top:1px solid #dfe7ec}.back a{color:var(--g);font-weight:700;text-decoration:none}.ft{background:var(--gd);color:#cfdde6;padding:30px 0;text-align:center;font-size:.84rem;margin-top:44px}.ft a{color:#fff;text-decoration:none;font-weight:600}.ft .fl{margin-bottom:10px}.ft .fl a{margin:0 9px}.dir-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin:16px 0 26px}.dir-list a{background:var(--bg);border:1px solid #d3dfe6;border-radius:6px;padding:10px 14px;text-decoration:none;color:var(--blue);font-weight:600;font-size:.9rem}.dir-list a small{display:block;color:var(--mu);font-weight:400;font-size:.78rem}.dir-list a:hover{background:var(--g);color:#fff}.dir-list a:hover small{color:#d9e9f0}.photo{margin:24px 0}.photo img{width:100%;max-height:440px;object-fit:cover;border-radius:10px;background:var(--bg)}.photo figcaption,.src{font-size:.8rem;color:var(--mu);margin-top:6px}.src a{color:var(--mu)}.prose p{margin:0 0 14px}.tbl{width:100%;border-collapse:collapse;margin:16px 0;font-size:.93rem}.tbl th{background:var(--gd);color:#fff;text-align:left;padding:9px}.tbl td{padding:9px;border-bottom:1px solid #dfe7ec}.tbl tr:nth-child(even) td{background:var(--bg)}.alpha{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 20px}.alpha a{background:var(--gd);color:#fff;text-decoration:none;font-weight:700;padding:6px 11px;border-radius:5px}.alpha a:hover{background:var(--gold)}h3.letter{font-size:1.3rem;color:var(--gd);margin-top:22px;scroll-margin-top:80px}#q{width:100%;padding:12px 14px;font-size:1rem;border:2px solid #d3dfe6;border-radius:8px}.gallery{display:grid;gap:14px;margin:20px 0 10px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}.gallery.g1{display:flex}.gallery.g1 figure{width:fit-content;max-width:min(100%,560px)}.gallery figure{background:var(--bg);border:1px solid #dfe7ec;border-radius:10px;overflow:hidden}.gallery img{width:100%;height:210px;object-fit:cover;display:block}.gallery.g1 img{width:auto;max-width:100%;height:auto;max-height:480px}.gallery figcaption{font-size:.82rem;color:var(--tx);padding:8px 10px;line-height:1.35}.gallery figcaption small{color:var(--mu);font-size:.74rem}.gallery figcaption a{color:var(--mu)}"

CSS += (
 # cards, headings, tables, hero
 ".hero{padding:64px 0 52px}.card{transition:all .2s}.card:hover{box-shadow:0 4px 16px rgba(0,0,0,.12);transform:translateY(-2px)}"
 ".card ul li:last-child{border-bottom:none}.card li small{display:block;color:var(--mu);font-weight:400;font-size:.82rem;line-height:1.4}"
 ".dir-list a{transition:all .2s}.dir-list a:hover{background:var(--g);color:#fff;transform:translateY(-1px)}"
 "h2.st{position:relative;padding-left:14px}h2.st:before{content:'';position:absolute;left:0;top:2px;bottom:10px;width:5px;border-radius:3px;background:var(--gold)}"
 ".facts tr:nth-child(even) th,.facts tr:nth-child(even) td{background:#eaf1f4}"
 # hero variants: city / region / Washington state
 ".city-hero,.region-hero{position:relative;overflow:hidden}.city-hero .wrap,.region-hero .wrap,.or-hero .wrap{position:relative;z-index:2}"
 ".hero p.city-tagline{font-family:'Outfit',system-ui,sans-serif;font-style:italic;font-size:clamp(1.05rem,2.2vw,1.3rem);color:#ffd2bd;margin-top:10px;max-width:720px}"
 ".region-hero .hero-sub{color:#d9e9f0}"
 ".pills{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.pill{display:inline-block;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.3);color:#fff;"
 "padding:5px 13px;border-radius:999px;font-size:.84rem;font-weight:600;backdrop-filter:blur(2px)}.pill a{color:#fff}"
 ".or-sil{position:absolute;right:3%;top:50%;transform:translateY(-50%);width:340px;max-width:45%;height:auto;opacity:.5;z-index:1;pointer-events:none}"
 ".or-hero{position:relative;overflow:hidden;min-height:420px;display:flex;align-items:center;color:#fff;margin-bottom:36px;padding:72px 0 64px;"
 "background:radial-gradient(ellipse at 75% 30%,rgba(232,131,90,.35),transparent 55%),linear-gradient(135deg,#081c28 0%,#0e2a3b 40%,#1d5d8f 100%)}"
 ".or-hero .wrap{width:100%}.or-sil-lg{width:440px;max-width:42%;right:4%;opacity:.6}"
 ".or-hero h1{font-size:clamp(2rem,5.5vw,3.4rem);max-width:720px;text-shadow:0 2px 12px rgba(0,0,0,.35)}"
 ".or-eyebrow{text-transform:uppercase;letter-spacing:.18em;font-size:.8rem;font-weight:700;color:var(--gold);margin-bottom:14px}"
 ".or-sub{color:#d9e9f0;font-size:clamp(1rem,2vw,1.18rem);margin-top:16px;max-width:620px}"
 ".or-cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}"
 ".btn-cta,.btn-ghost{display:inline-block;padding:12px 24px;border-radius:8px;font-weight:700;text-decoration:none;transition:all .2s}"
 ".btn-cta{background:var(--gold);color:#0e2a3b}.btn-cta:hover{background:#f19a75;transform:translateY(-2px)}"
 ".btn-ghost{border:2px solid rgba(255,255,255,.7);color:#fff}.btn-ghost:hover{background:rgba(255,255,255,.12);border-color:#fff}"
 "@media(max-width:700px){.or-sil{opacity:.2;max-width:80%;right:-20px}.or-hero{min-height:360px}}"
 # quick facts + map
 ".qf{display:flex;gap:20px;align-items:flex-start;margin:24px 0}.qf .facts{flex:1;min-width:0;margin:0}"
 ".ormap{flex:0 0 216px;background:var(--bg);border:1px solid #dfe7ec;border-radius:10px;padding:8px;text-align:center}"
 ".ormap svg{display:block;width:200px;height:160px}.ormap figcaption{font-size:.8rem;color:var(--mu);margin-top:4px}"
 # ticker (pure CSS)
 ".ticker{background:var(--gd);border-top:1px solid #22495c;border-bottom:1px solid #071722;overflow:hidden;white-space:nowrap;font-size:.85rem}"
 ".ticker-track{display:inline-block;padding:7px 0;animation:scroll-left 1500s linear infinite;will-change:transform}"
 ".ticker-track:hover{animation-play-state:paused}.ticker-track span{color:var(--gold);padding:0 26px;border-right:1px solid #22495c}"
 "@keyframes scroll-left{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}"
 "@media(prefers-reduced-motion:reduce){.ticker-track{animation-play-state:paused}}"
 # travel alerts banner
 "#alerts-bar{background:#fff8e6;border-bottom:1px solid #e8c873}#alerts-bar summary{max-width:1000px;margin:0 auto;padding:7px 24px;cursor:pointer;font-weight:700;font-size:.88rem;color:#7a4b00;list-style-position:inside}"
 "#alerts-bar summary:hover{color:#4f3100}#alerts-bar[open]{background:#fffbf0}#alerts-bar .ab{max-width:1000px;margin:0 auto;padding:4px 24px 16px;font-size:.9rem}"
 "#alerts-bar .ab-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}#alerts-bar .ab-grid div{background:#fff;border:1px solid #f0dca6;border-left:4px solid var(--g);border-radius:6px;padding:10px 12px}"
 "#alerts-bar .abh{display:block;color:var(--gd);font-size:.92rem;margin-bottom:4px}#alerts-bar a{color:var(--blue);font-weight:600}#alerts-bar ul{list-style:none}#alerts-bar li{padding:2px 0}"
 "#ab-live{margin-top:12px}#ab-live:empty{display:none}#ab-live p{margin:4px 0}#ab-live .ab-note{font-size:.78rem;color:var(--mu)}"
 # mobile
 "@media(max-width:600px){.cards{grid-template-columns:1fr}.hero{padding:40px 0 32px}.qf{flex-direction:column}.ormap{align-self:center}"
 ".wrap{padding:0 16px}.nl{gap:10px}.facts{padding:12px}.facts th{width:auto}.facts th,.facts td{display:block;border-bottom:none;padding:4px 6px}.facts td{border-bottom:1px solid #dfe7ec;padding-bottom:9px}"
 "#alerts-bar summary,#alerts-bar .ab{padding-left:16px;padding-right:16px}}"
 # weather widget
 ".wx-card{background:#fff;border:1px solid #dfe7ec;border-top:4px solid #1d5d8f;border-radius:10px;padding:20px;margin:24px 0}"
 ".wx-card h3{font-size:1rem;color:var(--gd);margin-bottom:12px}"
 ".wx-loading{color:var(--mu);font-size:.9rem}"
 ".wx-cur{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #dfe7ec}"
 ".wx-icon{font-size:2.6rem;line-height:1}.wx-temp{font-size:2rem;font-weight:700;color:var(--gd)}"
 ".wx-cond{font-size:1rem;color:var(--tx)}.wx-wind,.wx-humid{font-size:.88rem;color:var(--mu)}"
 ".wx-forecast{display:flex;gap:8px;flex-wrap:wrap}"
 ".wx-day{background:var(--bg);border:1px solid #dfe7ec;border-radius:8px;padding:8px 10px;text-align:center;min-width:54px;flex:1}"
 ".wx-day-name{font-size:.78rem;font-weight:700;color:var(--gd)}.wx-day-icon{font-size:1.4rem;margin:4px 0}"
 ".wx-day-hi{font-size:.9rem;font-weight:700;color:var(--tx)}.wx-day-lo{font-size:.82rem;color:var(--mu)}"
 ".wx-attr{font-size:.74rem;color:var(--mu);margin-top:10px}"
 ".wx-attr a{color:var(--mu)}"
 # voter registration card
 ".vote-card{background:#fff;border:1px solid #dfe7ec;border-top:4px solid var(--gold);border-radius:10px;padding:20px}"
 ".vote-card h3{font-size:1rem;color:var(--gd);margin-bottom:10px}"
 ".vote-card ul{list-style:none}.vote-card li{padding:6px 0;border-bottom:1px dashed #dfe7ec;font-size:.92rem}"
 ".vote-card li:last-child{border-bottom:none}.vote-card a{color:var(--blue);text-decoration:none;font-weight:600}"
 # region link (city pages) + did-you-know (county pages)
 "a.pill{text-decoration:none}a.pill:hover{background:rgba(255,255,255,.25)}.region-link{margin:6px 0 0;font-size:.92rem}.region-link a{color:var(--g);font-weight:700;text-decoration:none}"
 ".did-you-know{background:var(--bg);border-left:4px solid var(--gold);border-radius:6px;padding:12px 16px;margin:18px 0 0}.did-you-know a{color:var(--blue);font-weight:600}"
 # blog (index cards + article body)
 ".post-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.post{max-width:760px;font-size:1.04rem;margin-top:20px}.post p{margin:0 0 16px}"
 ".post h2{font-size:1.45rem;color:var(--gd);margin:38px 0 14px;border-bottom:3px solid var(--g);padding-bottom:8px}"
 ".post h3{font-size:1.15rem;color:var(--gd);margin:26px 0 10px}.post ul,.post ol{padding-left:22px;margin:0 0 16px}.post li{padding:3px 0}"
 ".post a{color:var(--blue)}.post .lede{font-size:1.14rem;color:var(--tx)}.post .tbl{font-size:.92rem}@media(max-width:700px){.tbl{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}.tbl th,.tbl td{min-width:90px}}"
 ".toc{background:#fff;border:1px solid #dfe7ec;border-radius:8px;padding:14px 18px;margin:20px 0}.toc ol{margin:6px 0 0;columns:2;column-gap:28px}.toc li{padding:2px 0;font-size:.93rem;break-inside:avoid}@media(max-width:600px){.toc ol{columns:1}}.post h2[id]{scroll-margin-top:80px}"
    ".callout{background:var(--bg);border:1px solid #dfe7ec;border-left:5px solid var(--gold);border-radius:8px;padding:16px 18px;margin:22px 0}.callout p:last-child{margin:0}"
 ".town-facts{font-size:.88rem;color:var(--mu);margin:-4px 0 12px}"
 ".visit-card{background:var(--bg);border:1px solid #dfe7ec;border-left:5px solid var(--g);border-radius:8px;padding:12px 16px;margin:-4px 0 18px;font-size:.93rem;display:flex;flex-wrap:wrap;gap:4px 18px}"
 ".visit-card strong{flex-basis:100%;color:var(--gd)}.visit-card span{white-space:normal}.visit-card a{color:var(--blue);font-weight:600;text-decoration:none}.visit-card a:hover{text-decoration:underline}"
 ".cta-box{background:linear-gradient(135deg,#081c28 0%,#0e2a3b 45%,#1d5d8f 100%);color:#fff;border-radius:12px;padding:28px;margin:36px 0 10px}"
 ".cta-box h2{color:#fff;border:none;margin:0 0 10px;padding:0}.cta-box p{color:#d9e9f0}.cta-box .btn-cta{margin-top:6px}.cta-box .btn-ghost{margin:6px 0 0 8px}"
 ".post-card{display:flex;flex-direction:column;text-decoration:none;color:inherit}.post-card .pc-cat{text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:700;color:#b85c38}"
 ".post-card h3{font-size:1.15rem;margin:8px 0}.post-card p{font-size:.93rem;color:var(--tx);flex:1}.post-card .pc-date{font-size:.82rem;color:var(--mu);margin-top:12px}"
 ".post-card .pc-more{color:var(--blue);font-weight:700;font-size:.9rem;margin-top:6px}"
)

CSS += ( # ---- Washington theme (Puget Sound navy, evergreen teal, salmon/Rainier-sunrise coral, sans-serif headings)
 "h1,h2,h3{letter-spacing:-.01em;font-weight:700}body{font-size:1.02rem}"
 ".hd{background:#fff;color:var(--gd);border-bottom:3px solid var(--g);box-shadow:0 2px 12px rgba(14,42,59,.08);padding:12px 0}"
 ".logo{color:var(--gd);font-family:'Outfit',system-ui,sans-serif;font-size:1.2rem;letter-spacing:-.01em}.logo .badge{background:var(--gd);width:34px;height:34px;border-radius:9px}"
 ".nl a{color:var(--gd);font-weight:600}.nl a:hover{color:var(--gold)}"
 ".hero,.or-hero{position:relative;padding-bottom:84px}.hero:after,.or-hero:after{content:'';position:absolute;left:0;right:0;bottom:-1px;height:72px;background:url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 90' preserveAspectRatio='none'><path fill='%23ffffff' fill-opacity='.18' d='M0 70 L180 40 L300 58 L470 22 L600 50 L700 30 L760 8 L800 4 L840 10 L900 32 L1040 46 L1180 26 L1320 52 L1440 34 V90 H0Z'/><path fill='%23ffffff' d='M0 84 L140 66 L260 76 L420 52 L560 72 L700 56 L860 74 L1000 60 L1160 78 L1300 64 L1440 74 V90 H0Z'/></svg>\") bottom/100% 100% no-repeat;pointer-events:none;z-index:1}"
 ".hero{background:linear-gradient(160deg,#0e2a3b 0%,#174a5c 55%,#1f6f6b 100%);margin-bottom:24px}"
 ".or-hero{background:radial-gradient(ellipse at 80% 20%,rgba(232,131,90,.32),transparent 55%),linear-gradient(160deg,#081c28 0%,#0e2a3b 45%,#1f6f6b 100%)}"
 ".hero p.city-tagline{font-family:'Source Sans 3',system-ui,sans-serif;font-style:normal;font-weight:600}"
 ".or-eyebrow{color:#ffb596}.btn-cta,.btn-ghost{border-radius:999px}.btn-cta{color:#fff}.btn-cta:hover{color:#fff}"
 "h2.st{border-bottom:none;padding:0 0 12px;padding-left:0}h2.st:before{display:none}h2.st:after{content:'';display:block;width:64px;height:4px;border-radius:2px;background:var(--gold);margin-top:10px}"
 ".card{border:1px solid #dfe7ec;border-radius:14px;box-shadow:0 2px 10px rgba(14,42,59,.06)}.card h3{color:var(--g)}"
 ".facts{border-radius:14px}.facts th{border-bottom-color:#c7d6de}.tbl th{background:var(--g)}.pill{border-radius:8px}"
 ".dir-list a{border-radius:10px;background:#fff}.dir-list a:hover{background:var(--g)}"
 ".ticker{background:var(--g);border:none}.ticker-track span{color:#fff;border-right-color:rgba(255,255,255,.25)}"
 ".ft{background:#081c28;border-top:4px solid var(--gold)}"
)

STATE_TICKER_FACTS = [
 "Washington is the only U.S. state named after a president 🇺🇸",
 "Washington became the 42nd state on November 11, 1889 🎉",
 "Mount Rainier is the most heavily glaciated peak in the contiguous United States 🏔",
 "Washington has more glaciers than the rest of the Lower 48 states combined 🧊",
 "Washington grows more apples than any other state 🍎",
 "The Yakima Valley grows most of the hops used in American beer 🍺",
 "Washington State Ferries runs the largest ferry system in the United States ⛴",
 "Washington does not tax wages 💰",
 "Grand Coulee Dam is the largest power-producing facility in the United States ⚡",
 "The Hoh Rain Forest gets around 12 feet of rain in a typical year 🌧",
 "The first Starbucks opened at Seattle's Pike Place Market in 1971 ☕",
 "Pike Place Market has operated since 1907 🐟",
 "Boeing was founded in Seattle in 1916 ✈️",
 "Amazon was started in a Bellevue garage in 1994 📦",
 "Microsoft is headquartered in Redmond 💻",
 "The Space Needle was built for the 1962 Seattle World's Fair 🗼",
 "Mount St. Helens erupted on May 18, 1980 🌋",
 "Lake Chelan is one of the deepest lakes in the United States 🏞",
 "Washington is the nation's second-largest wine producer 🍷",
 "The first Father's Day was celebrated in Spokane in 1910 👔",
 "The SR 520 Evergreen Point bridge is the longest floating bridge in the world 🌉",
 "Cape Flattery is the northwesternmost point of the contiguous United States 🧭",
 "Washington has five major volcanoes: Baker, Glacier Peak, Rainier, St. Helens and Adams 🌋",
 "Olympic National Park is a UNESCO World Heritage Site 🌲",
 "The Walla Walla sweet onion is Washington's official state vegetable 🧅",
 "Washington's state dinosaur is Suciasaurus rex, found in the San Juan Islands 🦖",
 "Woody Guthrie's \"Roll On, Columbia, Roll On\" is Washington's state folk song 🎶",
 "Washington's flag is the only state flag that is green 💚",
 "Spokane hosted the Expo '74 world's fair 🎡",
 "Lewis and Clark reached the Pacific near Cape Disappointment in 1805 🛶",
 "Olympia has been the capital since Washington Territory was created in 1853 🏛",
 "Mount Baker Ski Area recorded 1,140 inches of snow in the 1998–99 season ❄️",
 "Palouse Falls is Washington's official state waterfall 💧",
 "Steilacoom, incorporated in 1854, is Washington's oldest incorporated town 🏘",
 "After the Great Fire of 1889, Seattle raised its downtown streets by one to two stories 🔥",
 "Skamania County passed an ordinance protecting Bigfoot in 1969 🦶",
 "Washington is home to 29 federally recognized tribes 🪶",
 "Washington's nickname is the Evergreen State 🌲",
]


TICKER_PER_PAGE = 16   # facts shown per page; the set rotates by page so every fact appears somewhere on the site


def ticker_html(seed=''):
    """Infinite horizontal fact ticker — CSS animation only; facts duplicated so translateX(-50%) loops seamlessly.
    Each page shows a different rotating window of TICKER_PER_PAGE facts (seeded by page name) instead of all
    100+ facts, so the same ~1,500 words of boilerplate are not repeated ahead of the main content on every page."""
    facts = STATE_TICKER_FACTS
    if seed:
        start = sum(ord(ch) * (i + 1) for i, ch in enumerate(seed)) % len(facts)
        facts = (facts[start:] + facts[:start])[:TICKER_PER_PAGE]
    spans = ''.join(f'<span>{e(f)}</span>' for f in facts)
    dur = max(60, round(1500 * len(facts) / len(STATE_TICKER_FACTS)))
    return (f'<div class="ticker" role="region" aria-label="Washington fun facts"><div class="ticker-track" style="animation-duration:{dur}s">'
            f'{spans}{spans}</div></div>')


def alert_banner():
    """Collapsed travel-alert bar on every page with links to official WSDOT, wildfire and emergency-alert sources."""
    ext = 'target="_blank" rel="noopener"'
    return ('<details id="alerts-bar"><summary>&#9888;&#65039; Washington Travel Alerts &mdash; Passes, Ferries &amp; Wildfire Smoke</summary><div class="ab"><div class="ab-grid">'
            f'<div><strong class="abh">&#128679; Roads &amp; Mountain Passes</strong><ul><li><a href="https://wsdot.com/travel/real-time/map" {ext}>WSDOT real-time travel map</a> &mdash; closures &amp; cameras</li><li><a href="https://wsdot.com/travel/real-time/mountainpasses" {ext}>Mountain pass reports</a> &mdash; Snoqualmie, Stevens, White &amp; more</li><li>Dial <strong>511</strong> for road info by phone</li></ul></div>'
            f'<div><strong class="abh">&#9972; Ferries</strong><ul><li><a href="https://wsdot.wa.gov/travel/washington-state-ferries" {ext}>Washington State Ferries</a> &mdash; schedules, alerts &amp; wait times</li></ul></div>'
            f'<div><strong class="abh">&#128293; Wildfire &amp; Smoke</strong><ul><li><a href="https://fire.airnow.gov/" {ext}>AirNow Fire &amp; Smoke Map</a></li><li><a href="https://wasmoke.blogspot.com/" {ext}>Washington Smoke Information</a></li></ul></div>'
            '</div></div></details>')


OR_BBOX = (45.54, 49.0, -124.85, -116.92)   # lat_min, lat_max, lon_min, lon_max (Washington)
OR_OUTLINE = [  # (lon, lat), clockwise from the Canadian border near Blaine
    (-122.76, 49.0), (-120.0, 49.0), (-117.03, 49.0), (-117.04, 47.5), (-117.04, 46.43), (-116.92, 46.0),
    (-118.98, 46.0), (-119.25, 45.93), (-119.6, 45.92), (-120.0, 45.82), (-120.5, 45.7), (-120.9, 45.65),
    (-121.2, 45.61), (-121.5, 45.72), (-121.9, 45.66), (-122.4, 45.58), (-122.77, 45.65), (-122.8, 45.86),
    (-122.9, 46.1), (-123.2, 46.17), (-123.55, 46.26), (-124.03, 46.26), (-124.06, 46.65), (-124.1, 46.9),
    (-124.17, 47.3), (-124.35, 47.7), (-124.6, 48.0), (-124.73, 48.38), (-124.6, 48.4), (-124.0, 48.3),
    (-123.5, 48.25), (-123.25, 48.28), (-123.15, 48.45), (-123.25, 48.7), (-123.02, 48.83), (-123.08, 49.0), (-122.76, 49.0)]


def _or_xy(lat, lon, w=200, h=160, pad=8):
    la0, la1, lo0, lo1 = OR_BBOX
    return (lon - lo0) / (lo1 - lo0) * (w - 2 * pad) + pad, (la1 - lat) / (la1 - la0) * (h - 2 * pad) + pad


def state_svg_map(lat, lon, label='City'):
    pts = ' '.join('%.1f,%.1f' % _or_xy(la, lo) for lo, la in OR_OUTLINE)
    x, y = _or_xy(lat, lon)
    return (f'<figure class="ormap"><svg viewBox="0 0 200 160" width="200" height="160" role="img" aria-label="Map of Washington showing the location of {e(label)}">'
            f'<polygon points="{pts}" fill="#e4eef3" stroke="#1f6f6b" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#d62828" stroke="#fff" stroke-width="1.5"><title>{e(label)}</title></circle>'
            f'</svg><figcaption>Location in Washington</figcaption></figure>')


def state_silhouette(w=500, h=400, cls='or-sil'):
    """Large decorative Washington outline (inline SVG) for hero backgrounds."""
    pts = ' '.join('%.1f,%.1f' % _or_xy(la, lo, w, h, 10) for lo, la in OR_OUTLINE)
    return (f'<svg class="{cls}" viewBox="0 0 {w} {h}" aria-hidden="true" focusable="false">'
            f'<polygon points="{pts}" fill="rgba(255,255,255,.07)" stroke="rgba(255,255,255,.6)" stroke-width="2.5" stroke-linejoin="round"/></svg>')


def city_tagline(name, county, region):
    t = CITY_TAGLINES.get(slug(name))
    if t: return t
    return f'{name} \u2014 {county} County \u00b7 ' + (region if region.endswith('Washington') else f'{region}, Washington')


def hero_style(rname):
    a, b, _ = REGION_THEME.get(rname, ('#0e2a3b', '#1f6f6b', ''))
    return f' style="background:linear-gradient(135deg,{a} 0%,{b} 100%)"'


def slug(name):
    if name in SLUG_OVERRIDES: return SLUG_OVERRIDES[name]
    s = name.lower().replace('.', '').replace("'", '').replace(' ', '-')
    while '--' in s: s = s.replace('--', '-')
    return s.strip('-')


def e(t):
    return html.escape(str(t), quote=True)


def n(v):
    try: return f'{int(float(v)):,}'
    except (TypeError, ValueError): return ''


def host(url):
    return re.sub(r'^https?://(www\.)?', '', url).rstrip('/')


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a['lat'], a['lon'], b['lat'], b['lon']))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def summary_html(text, limit=1100):
    """Clean a Wikipedia intro (drop stripped pronunciation guides) and trim to whole paragraphs/sentences."""
    text = re.sub(r' \(\s[^)]*\)', '', text or '')
    text = re.sub(r'\s+([,.])', r'\1', text)
    out, total = [], 0
    for para in [p.strip() for p in text.split('\n') if p.strip()]:
        if total + len(para) > limit and out: break
        if len(para) > limit:
            cut = para[:limit]
            para = cut[:cut.rfind('. ') + 1] if '. ' in cut else cut
        out.append(para); total += len(para)
    return ''.join(f'<p>{e(p)}</p>' for p in out)


def head(title, desc, path, og_type='website', image=None, extra='', up='', keywords=''):
    url = f'{BASE_URL}{path}'
    img = image or DEFAULT_IMG
    ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={ANALYTICS_ID}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","{ANALYTICS_ID}");</script>' if ANALYTICS_ID else '')
    ga = GTM_HEAD + ga
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{e(title)}</title>'
            f'<meta name="description" content="{e(desc)}">' + (f'<meta name="keywords" content="{e(keywords)}">' if keywords else '') + '<meta name="robots" content="index, follow">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<link rel="icon" href="{up}assets/favicon.ico"><link rel="apple-touch-icon" href="{up}assets/favicon-32.png"><link rel="canonical" href="{url}">'
            f'<meta property="og:site_name" content="{SITE_NAME}"><meta property="og:locale" content="en_US"><meta property="og:type" content="{og_type}">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">'
            f'<meta property="og:url" content="{url}"><meta property="og:image" content="{e(img)}">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(title)}">'
            f'<meta name="twitter:description" content="{e(desc)}"><meta name="twitter:image" content="{e(img)}">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">'
            f'{extra}{ga}<style>{CSS}</style></head><body>')


def header(up):
    return (f'<header class="hd"><div class="wrap"><nav><a class="logo" href="{up}index.html"><span class="badge"><svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 20 L9 9 L12 13 L15.5 6 L22 20Z" fill="#fff"/><path d="M13.6 9.8 L15.5 6 L17.4 9.8 L16.3 9.2 L15.5 10.2 L14.7 9.2Z" fill="#e8835a"/></svg></span> Washington Information</a>'
            f'<ul class="nl"><li><a href="{up}moving-to-washington/index.html">Moving</a></li><li><a href="{up}visit-washington/index.html">Visiting</a></li>'
            f'<li><a href="{up}regions/index.html">Regions</a></li>'
            f'<li><a href="{up}counties/index.html">Counties</a></li><li><a href="{up}cities/index.html">Cities A&ndash;Z</a></li><li><a href="{up}blog/index.html">Blog</a></li></ul></nav></div></header>')


def footer(up, note=''):
    return (f'<footer class="ft"><div class="wrap"><p class="fl"><a href="{up}about/index.html">About</a><a href="{up}contact/index.html">Contact</a>'
            f'<a href="{up}privacy/index.html">Privacy Policy</a><a href="{up}advertise/index.html">Advertise</a><a href="{up}regions/index.html">Regions</a>'
            f'<a href="{up}cities/index.html">Cities</a><a href="{up}counties/index.html">Counties</a><a href="/washington-zip-codes/">ZIP Codes</a>'
            f'<a href="/washington-area-codes/">Area Codes</a><a href="/washington/">State Facts</a><a href="{up}blog/index.html">Blog</a></p>'
            f'<p>&copy; 2026 Washington Information &mdash; independent resource, not affiliated with the State of Washington.{note}</p></div></footer></body></html>')


def ld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>'


def file_page(item):
    f = item.get('image_file', '')
    if not f: return ''
    base = 'https://en.wikipedia.org' if '/wikipedia/en/' in (item.get('image') or '') else 'https://commons.wikimedia.org'
    return f'{base}/wiki/File:{f}'


def photo(item, alt):
    if not item.get('image'): return ''
    f = item.get('image_file', '')
    credit = f'<a href="{e(file_page(item))}" target="_blank" rel="noopener">Wikimedia</a>' if f else 'Wikimedia Commons'
    fit = ' style="object-fit:contain"' if f.lower().endswith(('.svg', '.png')) else ''
    return (f'<figure class="photo"><img src="{e(item["image"])}"{fit} alt="{e(alt)}" loading="lazy">'
            f'<figcaption>Image: {credit} (see file page for author and license)</figcaption></figure>')


CITY_IMAGES = json.load(open('data/city_images.json', encoding='utf-8')) if os.path.exists('data/city_images.json') else {}
CITY_ZIPS = json.load(open('data/city_zips.json', encoding='utf-8')) if os.path.exists('data/city_zips.json') else {}   # USPS ZIPs per city (from the 'zipcodes' package)
TZ_NAMES = {'America/Los_Angeles': 'Pacific Time (PT)'}
LINK_FIXES = json.load(open('data/link_fixes.json', encoding='utf-8')) if os.path.exists('data/link_fixes.json') else {}
DEAD_LINKS = set(json.load(open('data/dead_links.json', encoding='utf-8'))) if os.path.exists('data/dead_links.json') else set()


def fix_url(u):
    return LINK_FIXES.get(u, u) if u else u


GALLERY_EXCLUDE = json.load(open('data/gallery_exclude.json', encoding='utf-8')) if os.path.exists('data/gallery_exclude.json') else {}
CITY_SCHOOLS = json.load(open('data/city_schools.json', encoding='utf-8')) if os.path.exists('data/city_schools.json') else {}


JUNK_WORDS = ('cemetery', 'greyhound', 'crucible', 'corbett hill', 'national forest historic photo', 'grave', '500px provided', 'photo by', 'odfw')


def clean_cap(s, name):
    s = re.sub(r'<[^>]+>', '', s or '').split('\n')[0]
    s = re.sub(r'\b(w|en|wikipedia):', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' .-')
    return s if 3 <= len(s) else f'{name}, Washington'


def norm_file(f):
    """Normalize a Commons filename so 'A_b%2C.jpg' and 'A b,.jpg' compare equal."""
    from urllib.parse import unquote
    f = unquote(f or '').split('/')[-1]
    f = re.sub(r'^(file|image):', '', f, flags=re.I)
    return re.sub(r'[\s_]+', ' ', f).strip().lower()


def gallery(c, name):
    imgs = [i for i in CITY_IMAGES.get(name, []) if i.get('src')
            and not any(w in (i.get('file', '') + ' ' + (i.get('caption') or '')).lower() for w in JUNK_WORDS)]
    main_file = norm_file(c.get('image_file'))
    main_ok = c.get('image') and not any(w in main_file for w in ('map', 'locator', 'area', '.svg', '.png', 'seal', 'flag', 'logo'))
    figs = []
    seen = {norm_file(x) for x in GALLERY_EXCLUDE.get(name, [])}  # hand-picked near-duplicates
    if main_ok:
        seen.add(main_file)
        m = next((i for i in imgs if norm_file(i.get('file')) == main_file), None)
        if m:  # same photo is in the gallery data: reuse its real caption and credit
            figs.append((c['image'], clean_cap(m.get('caption'), name), m.get('page') or file_page(c), m.get('artist') or 'Wikimedia Commons', m.get('license') or ''))
        else:
            figs.append((c['image'], f'{name}, Washington', file_page(c), 'Wikipedia' if '/wikipedia/en/' in c['image'] else 'Wikimedia Commons', ''))
    for i in imgs:
        key = norm_file(i.get('file')) or i['src']
        if key in seen: continue
        seen.add(key)
        figs.append((i['src'], clean_cap(i.get('caption'), name), i.get('page') or '', i.get('artist') or 'Wikimedia Commons', i.get('license') or ''))
    figs = figs[:6]
    if not figs:
        return photo(c, f'{name}, Washington')
    out = []
    for src, cap, page, artist, lic in figs:
        credit = f'{e(artist)}' + (f', {e(lic)}' if lic else '')
        link = f' &middot; <a href="{e(page)}" target="_blank" rel="noopener">source</a>' if page else ''
        alt = cap if (name.lower() in cap.lower() and not re.match(r'^[\d_ .-]{6}', cap)) else f'{cap} in {name}, Washington'
        if re.match(r'^[\d_ .-]{6}', cap): alt = f'{name}, Washington'
        out.append(f'<figure><img src="{e(src)}" alt="{e(alt)}" loading="lazy"><figcaption>{e(cap if len(cap) <= 90 else cap[:88].rsplit(" ", 1)[0].rstrip(",;:") + "…")}<br><small>Photo: {credit}{link}</small></figcaption></figure>')
    return f'<h2 class="st">{e(name)} in Pictures</h2><section class="gallery g{min(len(figs),3)}">{"".join(out)}</section>'


def data_story(c, all_cities, county):
    """Plain-language paragraph built from the city's own data, used when no Wikipedia summary is available."""
    name, out = c['name'], []
    try:
        p20, p10 = int(c['pop2020']), int(c['pop2010'] or 0)
    except (TypeError, ValueError):
        p20, p10 = 0, 0
    if p20 and p10:
        ch = (p20 - p10) / p10 * 100
        out.append(f'Its population {"grew" if ch > 0.5 else "fell" if ch < -0.5 else "held about steady"} '
                   + (f'by {abs(ch):.0f}% ' if abs(ch) > 0.5 else '') + f'between the 2010 and 2020 censuses, from {p10:,} to {p20:,}.')
    try:
        est = int(c.get('pop2024') or 0)
        if est and p20: out.append(f'The Census Bureau estimated {est:,} residents in 2024.')
    except ValueError:
        pass
    try:
        area = float(c.get('area_sqmi') or 0)
        if area: out.append(f'{name} covers about {area:g} square miles of land.')
    except ValueError:
        pass
    if c.get('seat'): out.append(f'It is the county seat of {county} County.')
    ranked = sorted(all_cities, key=lambda x: -int(x['pop2020'] or 0))
    rank = next((i for i, x in enumerate(ranked, 1) if x is c), None)
    if rank and rank <= 50: out.append(f'By population it is the {ordinal(rank)}-largest of Washington&rsquo;s {len(all_cities)} incorporated cities and towns.')
    near = sorted((miles(c, o), o) for o in all_cities if o is not c)
    if near: out.append(f'The nearest incorporated community is {e(near[0][1]["name"])}, about {near[0][0]:.0f} miles away.')
    if c.get('incorporated'): out.append(f'{name} was incorporated in {c["incorporated"]}.')
    return ' '.join(out)


def county_story(k, members):
    """Plain-language county overview from data, used when no Wikipedia summary is available."""
    name = k['name']; out = []
    if k.get('pop2020'): out.append(f'{name} County had {n(k["pop2020"])} residents at the 2020 Census' + (f' and an estimated {n(k["pop2024"])} in 2024.' if k.get('pop2024') else '.'))
    if k.get('seat'): out.append(f'The county seat is {k["seat"]}.')
    if k.get('area_sqmi'): out.append(f'It covers about {n(k["area_sqmi"])} square miles of land.')
    if k.get('est'): out.append(f'The county was established in {k["est"]}' + (f' and is named for {k["named_for"]}.' if k.get('named_for') else '.'))
    if members:
        out.append(f'It has {len(members)} incorporated {"city or town" if len(members) == 1 else "cities and towns"}; the largest is {members[0]["name"]}.')
    else:
        out.append('It has no incorporated cities or towns.')
    return f'<p>{e(" ".join(out))}</p>'


def wiki_credit(item):
    return (f'<p class="src">Source: adapted from <a href="{e(item["wiki_url"])}" target="_blank" rel="noopener">Wikipedia</a>, '
            f'available under <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a>.</p>')


def ordinal(k):
    return f"{k}{'th' if 10 <= k % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(k % 10, 'th')}"


def city_title(name, nzips=0):
    """Keep the <title> within ~60 characters so Google shows it untruncated; city name + Washington always lead.
    Population and ZIP code searches ('kent washington zip code', 'yakima washington population') are the highest-demand,
    lowest-difficulty city queries, so they lead the title."""
    z = 'ZIP Code' if nzips == 1 else 'ZIP Codes'
    opts = ((f'{name}, Washington: Population, {z}, Weather & Schools', f'{name}, Washington: Population, {z} & Weather',
             f'{name}, WA: Population, {z} & Weather', f'{name}, WA: Population & {z}') if nzips else ())
    for t in opts + (f'{name}, Washington: Population, Schools, Weather & Moving Guide',
              f'{name}, Washington: Population, Schools & Moving Guide',
              f'{name}, WA: Population, Schools & Moving Guide'):
        if len(t) <= 60:
            return t
    return t


def city_desc(name, county, pop, has_attractions, nzips=0):
    """Meta description (<=160 chars): primary facts first, then what the page offers."""
    todo = ' things to do,' if has_attractions else ''
    lead = f'{name}, Washington guide: ' + (f'population {pop} (2020 Census), ' if pop else '') + f'{county} County.'
    first = 'ZIP code, schools' if nzips == 1 else 'ZIP codes, schools' if nzips else 'Schools'
    for tail in (f' {first}, weather,{todo} nearby cities and moving tips for {name}, WA.',
                 f' {first}, weather,{todo} nearby cities and moving tips.',
                 f' Schools, weather,{todo} nearby cities and moving tips for {name}, WA.',
                 f' Schools, weather,{todo} nearby cities and moving tips.',
                 f' Schools, weather, nearby cities and moving tips.'):
        if len(lead + tail) <= 160:
            return lead + tail
    return (lead + tail)[:160]


COUNTY_SEATS = {}
COST_GUIDE = '/moving-to-washington/#cost-of-living'


def city_faq(c, all_cities, county, breg, electric, district):
    """FAQ built from the city's own data, answering the specific questions people search for
    ("what county is X in", "how far is X from Seattle", "when was X founded"). Returns (question, text, html)."""
    name = c['name']; fq = []
    pop = n(c['pop2020'])
    if pop:
        a = (f"{name} had {pop} residents at the 2020 U.S. Census (up from {n(c['pop2010'])} in 2010)." if str(c['change']).startswith('+')
             else f"{name} had {pop} residents at the 2020 U.S. Census ({n(c['pop2010'])} in 2010).")
        fq.append((f"What is the population of {name}, Washington?", a, None))
    area = c.get('area_sqmi')
    if area and float(area) > 0:
        a = f"{name} covers about {float(area):g} square miles of land"
        if pop: a += f" and had {pop} residents at the 2020 Census, a density of about {float(c['pop2020']) / float(area):,.0f} people per square mile"
        ranked = sorted(all_cities, key=lambda x: -float(x['pop2020'] or 0))
        rank = next((i for i, x in enumerate(ranked, 1) if x is c), None)
        a += '.' + (" It is the largest city in Washington by population." if rank == 1 else f" By population it is Washington's {ordinal(rank)}-largest city out of {len(all_cities)}." if rank and rank <= 60 else '')
        fq.append((f"How big is {name}, Washington?", a, None))
    others = [x for x in c['counties'][1:]]
    a = f"{name} is in {county} County" + (f" (the city also extends into {' and '.join(others)} County)" if others else '') + f", in the {breg} region of Washington."
    if c['capital']: a += f" It is Washington's state capital and the county seat of {county} County."
    elif c['seat']: a += f" It is the county seat of {county} County."
    elif COUNTY_SEATS.get(county): a += f" The county seat is {COUNTY_SEATS[county]}."
    fq.append((f"What county is {name}, Washington in?", a, None))
    hub_name = 'Olympia' if name == 'Seattle' else 'Seattle'
    hub = next((o for o in all_cities if o['name'] == hub_name), None)
    if hub and c.get('lat') is not None:
        d = miles(c, hub)
        fq.append((f"How far is {name} from {hub_name}?",
                   f"{name} is about {d:.0f} miles from {hub_name} in a straight line; the driving distance is longer and depends on your route.", None))
    near = sorted((miles(c, o), o) for o in all_cities if o is not c and o.get('lat') is not None and c.get('lat') is not None)
    if near:
        d, o = near[0]
        fq.append((f"What cities are near {name}, Washington?",
                   f"The closest incorporated city is {o['name']}, about {d:.0f} miles away. Other nearby cities include "
                   + ', '.join(x['name'] for _, x in near[1:4]) + '.', None))
    zinfo = CITY_ZIPS.get(name, {})
    zl = zinfo.get('zips') or zinfo.get('po_box_zips') or []
    if zl:
        listed = ', '.join(zl[:10]) + (f' and {len(zl) - 10} others' if len(zl) > 10 else '')
        a = (f"{name}'s ZIP code is {zl[0]}." if len(zl) == 1 else f"ZIP codes with a {name} mailing address include {listed}.")
        if zinfo.get('zips') and zinfo.get('po_box_zips'): a += f" PO boxes use {', '.join(zinfo['po_box_zips'][:5])}."
        a += " Some addresses near the city limits use a neighboring town's ZIP code, so check a specific address with USPS."
        fq.append((f"What is the ZIP code for {name}, Washington?", a, None))
    if c.get('incorporated'):
        fq.append((f"When was {name}, Washington incorporated?", f"{name} was incorporated as a {c.get('type', 'city')} in {c['incorporated']}.", None))
    a = ("Washington does not tax wages, but it has a 6.5% state sales tax plus local sales tax (combined rates of roughly 7.6% to 10.6%), "
         f"and housing is the biggest cost difference between communities. {name} is in the {breg} region.")
    fq.append((f"What is the cost of living in {name}, Washington?", a + " See the cost of living section of our Moving to Washington guide.",
               e(a) + f' See the <a href="{COST_GUIDE}">cost of living section of our Moving to Washington guide</a>.'))
    if district:
        fq.append((f"What school district serves {name}, Washington?",
                   f"{name} is served by {district}. The exact school a student attends depends on the home address, so confirm with the district before you buy or rent.", None))
    else:
        fq.append((f"Which schools serve families in {name}?",
                   f"School assignment depends on your exact address. Start with the OSPI (Office of Superintendent of Public Instruction) school directory or the local school district office.", None))
    fq.append((f"How do I set up utilities when moving to {name}?",
               f"Electricity in this area is generally provided by {electric} (confirm by address); natural gas, where available, by Puget Sound Energy, Cascade Natural Gas, Avista or NW Natural depending on the area. Water, sewer and trash are typically arranged through the City of {name}.", None))
    fq.append((f"How soon must I register my car after moving to {name}?",
               "Washington gives new residents 30 days to get a Washington driver license, and vehicles should be registered in Washington within 30 days of becoming a resident; you need the Washington license before you can register.", None))
    return fq


def faq_for(city, county, region, electric):
    k = sum(ord(c) for c in city) % 3
    q = [
     (f"What is the cost of living in {city}, Washington?", f"{city} lies in the {region} region, where costs vary mainly by housing. Washington does not tax wages but does charge sales tax."),
     (f"What utilities do I set up when moving to {city}?", f"Electricity in this area is generally provided by {electric} (confirm by address); natural gas, where available, by Puget Sound Energy, Cascade Natural Gas, Avista or NW Natural. Water, sewer, and trash are typically arranged through the City of {city}."),
     (f"How do I find a job near {city}?", "WorkSource Washington offers free job search help, career coaching and job listings."),
     (f"Which schools serve families in {city}?", f"Assignment depends on your exact address. Start with the OSPI school directory or the local school district office."),
     (f"How soon must I register my car after moving to {city}?", "Within 30 days of becoming a Washington resident for both the driver license and vehicle registration."),
     (f"Are there food banks or assistance programs near {city}?", f"Yes. Apply for food and cash benefits through Washington Connection, find a food bank through Northwest Harvest, or dial 211 for {county} County community resources."),
    ]
    if k == 1: q[0] = (f"Is {city}, Washington affordable to live in?", q[0][1]); q[2] = (f"What is the job market like around {city}?", q[2][1])
    elif k == 2: q[1] = (f"How do I connect utilities in {city}?", q[1][1]); q[4] = (f"After moving to {city}, what's the DMV deadline?", q[4][1])
    return q


def county_links(counties_str, up):
    return ', '.join(f'<a href="{up}counties/{slug(c)}/index.html">{e(c)} County</a>' for c in counties_str)


def voter_card(county, city_name):
    """Voter registration card: VoteWA online registration, the county auditor (elections) and the Secretary of State."""
    clerk_url = COUNTY_ELECTIONS.get(county) or COUNTY_SITES.get(county) or 'https://www.sos.wa.gov/elections'

    ext = ' target="_blank" rel="noopener"'
    items = [
        f'<li><strong>Washington is a vote-by-mail state</strong> &mdash; ballots are mailed automatically to all registered voters</li>',
        f'<li><a href="https://voter.votewa.gov/"{ext}>&#9989; Register, update your address or track your ballot at VoteWA</a></li>',
        f'<li><a href="{e(clerk_url)}"{ext}>&#127970; {e(county)} County Auditor &mdash; Elections</a> &mdash; drop boxes, voting centers &amp; local info</li>',
        f'<li><a href="https://www.sos.wa.gov/elections"{ext}>Washington Secretary of State &mdash; Elections</a></li>',
        f'<li><a href="https://www.vote411.org/"{ext}>Vote411 &mdash; nonpartisan voter guide for {e(city_name)} area candidates</a></li>',
    ]
    return f'<div class="vote-card"><h3>&#127963; Register to Vote in {e(city_name)}</h3><ul>{"".join(items)}</ul></div>'


WMO_ICONS = {
    0:'☀️|Clear sky', 1:'🌤|Mainly clear', 2:'⛅|Partly cloudy', 3:'☁️|Overcast',
    45:'🌫|Fog', 48:'🌫|Icy fog',
    51:'🌦|Light drizzle', 53:'🌦|Drizzle', 55:'🌧|Heavy drizzle',
    61:'🌧|Light rain', 63:'🌧|Rain', 65:'🌧|Heavy rain',
    71:'🌨|Light snow', 73:'🌨|Snow', 75:'❄️|Heavy snow', 77:'🌨|Snow grains',
    80:'🌦|Rain showers', 81:'🌧|Heavy showers', 82:'⛈|Violent showers',
    85:'🌨|Snow showers', 86:'❄️|Heavy snow showers',
    95:'⛈|Thunderstorm', 96:'⛈|T-storm + hail', 99:'⛈|Heavy T-storm + hail',
}

def weather_widget(city_name, lat, lon):
    """Live weather card powered by Open-Meteo (free, no API key required)."""
    if lat is None or lon is None:
        return ''
    city_id = re.sub(r'[^a-z0-9]', '', city_name.lower())
    icons_js = '{' + ','.join(f'{k}:["{v.split("|")[0]}","{v.split("|")[1]}"]' for k, v in WMO_ICONS.items()) + '}'
    js = f"""<script>(function(){{
var lat={lat:.5f},lon={lon:.5f},WI={icons_js};
var days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
fetch('https://api.open-meteo.com/v1/forecast?latitude='+lat+'&longitude='+lon
 +'&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m'
 +'&daily=temperature_2m_max,temperature_2m_min,weather_code'
 +'&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FLos_Angeles&forecast_days=7')
.then(function(r){{return r.json();}})
.then(function(d){{
 var c=d.current,dl=d.daily,wi=WI[c.weather_code]||['🌡','Unknown'];
 var h='<div class="wx-cur"><span class="wx-icon">'+wi[0]+'</span>'
  +'<span class="wx-temp">'+Math.round(c.temperature_2m)+'&deg;F</span>'
  +'<span class="wx-cond">'+wi[1]+'</span>'
  +'<span class="wx-wind">&#128168; '+Math.round(c.wind_speed_10m)+' mph</span>'
  +'<span class="wx-humid">&#128167; '+Math.round(c.relative_humidity_2m)+'% humidity</span></div>';
 h+='<div class="wx-forecast">';
 for(var i=1;i<Math.min(7,dl.time.length);i++){{
  var dt=new Date(dl.time[i]+'T12:00:00'),fi=WI[dl.weather_code[i]]||['🌡',''];
  h+='<div class="wx-day"><div class="wx-day-name">'+days[dt.getDay()]+'</div>'
   +'<div class="wx-day-icon">'+fi[0]+'</div>'
   +'<div class="wx-day-hi">'+Math.round(dl.temperature_2m_max[i])+'&deg;</div>'
   +'<div class="wx-day-lo">'+Math.round(dl.temperature_2m_min[i])+'&deg;</div></div>';
 }}
 h+='</div><p class="wx-attr">Source: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> (real-time, NWS/NOAA data). Updated on page load.</p>';
 var el=document.getElementById('wx-{city_id}');if(el)el.innerHTML=h;
}})
.catch(function(){{
 var el=document.getElementById('wx-{city_id}');
 if(el)el.innerHTML='<p class="wx-loading">Weather data unavailable &mdash; visit <a href="https://forecast.weather.gov/" target="_blank" rel="noopener">weather.gov</a> for current conditions.</p>';
}});
}})();</script>"""
    return (f'<div class="wx-card"><h3>&#127782; Current Weather in {e(city_name)}, Washington</h3>'
            f'<div id="wx-{city_id}" class="wx-loading">Loading weather&hellip;</div></div>'
            + js)


def city_page(c, all_cities, custom):
    name = c['name']; counties = c['counties']; county = counties[0]
    region, electric = COUNTY_INFO.get(county, ('Washington', 'Local utility'))
    x = custom.get(name.lower().replace(' ', '_'), {})
    employers = x.get('major_employers') or f'Employers in and around {name} and {county} County'
    if isinstance(employers, list): employers = ', '.join(employers)
    or_map = state_svg_map(c['lat'], c['lon'], f'{name}, Washington') if c.get('lat') is not None else ''
    ext = ' target="_blank" rel="noopener"'
    district, district_url = x.get('school_district'), fix_url(x.get('school_district_url'))
    ccd = CITY_SCHOOLS.get(name, [])
    schools = []
    for s in (x.get('schools') or []):
        if not s.get('name'): continue
        url = fix_url(s.get('url'))
        if url in DEAD_LINKS:
            key = re.sub(r'[^a-z]', '', s['name'].lower().replace('high school', 'hs'))
            m = next((r for r in ccd if re.sub(r'[^a-z]', '', r['name'].lower().replace('high school', 'hs')) == key), None)
            url = m['url'] if m else None
        schools.append({'name': s['name'], 'url': url})
    if not schools and ccd:
        schools = [{'name': s['name'] + (f" ({s['level']}, grades {s['grades']})" if s.get('grades') else (f" ({s['level']})" if s.get('level') else '')), 'url': s['url']} for s in ccd]
        if not district:
            ds = sorted({s['district'] for s in ccd if s.get('district') and not s.get('charter')})
            district = ', '.join(ds[:2]) if ds else None
    if schools or district:
        items = []
        if district:
            dn = f'<a href="{e(district_url)}"{ext}>{e(district)}</a>' if district_url else e(district)
            items.append(f'<li><strong>District:</strong> {dn}</li>')
        for s in schools[:8]:
            items.append(f'<li><a href="{e(s["url"])}"{ext}>{e(s["name"])}</a></li>' if s.get('url') else f'<li>{e(s["name"])}</li>')
        if len(schools) > 8:
            more = district_url or 'https://ospi.k12.wa.us/'
            items.append(f'<li><a href="{e(more)}"{ext}>See all schools &rarr;</a></li>')
        schools_card = f'<div class="card"><h3>&#127891; Schools</h3><ul>{"".join(items)}</ul></div>'
    else:
        schools_card = f'<div class="card"><h3>&#127891; Schools</h3><ul><li>No public schools are located inside {e(name)} city limits &mdash; students attend schools in the surrounding {e(county)} County district</li><li><a href="https://nces.ed.gov/ccd/schoolsearch/"{ext}>Find the schools serving an address (NCES)</a></li><li><a href="https://ospi.k12.wa.us/"{ext}>OSPI &mdash; Washington K-12 education</a></li></ul></div>'
    attr = [a for a in (x.get('top_attractions') or []) if a.get('name')][:5]
    attractions_card = ''
    if attr:
        ai = ''.join((f'<li><a href="{e(a["url"])}"{ext}>{e(a["name"])}</a>' if a.get('url') else f'<li><strong>{e(a["name"])}</strong>')
                     + (f'<br><small>{e(a["desc"])}</small>' if a.get('desc') else '') + '</li>' for a in attr)
        attractions_card = f'<div class="card"><h3>&#127956; Top Attractions</h3><ul>{ai}</ul></div>'
    pop = n(c['pop2020'])
    area = c.get('area_sqmi')
    density = f'{float(c["pop2020"]) / float(area):,.0f} people per sq mi' if area and float(area) > 0 else ''
    status = f"Incorporated {c.get('type', 'city')}"
    if c['capital']: status += ' &mdash; Washington state capital and county seat'
    elif c['seat']: status += f' &mdash; county seat of {e(county)} County'
    rows = [('County' if len(counties) == 1 else 'Counties', county_links(counties, '../../')), ('Region', e(region)),
            ('Population (2020 Census)', pop or 'n/a'), ('Population (2010 Census)', n(c['pop2010']) or 'n/a'),
            ('Change 2010&ndash;2020', e(c['change']) or 'n/a')]
    if area: rows.append(('Land area', f'{float(area):g} sq mi'))
    if density: rows.append(('Population density', density))
    if c.get('incorporated'): rows.append(('Incorporated', e(c['incorporated'])))
    rows.append(('Status', status))
    if c.get('website'): rows.append(('Official city website', f'<a href="{e(c["website"])}" target="_blank" rel="noopener">{e(host(c["website"]))}</a>'))
    zinfo = CITY_ZIPS.get(name, {})
    if zinfo.get('zips') or zinfo.get('po_box_zips'):
        zl = zinfo.get('zips') or zinfo.get('po_box_zips')
        rows.append(('ZIP code' if len(zl) == 1 else 'ZIP codes', ', '.join(zl[:12]) + (f' and {len(zl) - 12} more' if len(zl) > 12 else '')
                     + (f' (PO boxes: {", ".join(zinfo["po_box_zips"][:6])})' if zinfo.get('zips') and zinfo.get('po_box_zips') else '')))
    rows.append(('Area codes', ' / '.join(area_codes_for(county, name)) + ' (<a href="/washington-area-codes/">Washington area codes</a>)'))
    if zinfo.get('timezones'):
        rows.append(('Time zone', ' / '.join(TZ_NAMES.get(t, t) for t in zinfo['timezones'])))
    if c.get('lat') is not None: rows.append(('Coordinates', f'{c["lat"]:.4f}&deg; N, {abs(c["lon"]):.4f}&deg; W'))
    for k, label in (('nearest_hospital', 'Nearest major hospital'), ('transit', 'Public transit')):
        if x.get(k): rows.append((label, e(x[k])))
    facts = ''.join(f'<tr><th>{a}</th><td>{b}</td></tr>' for a, b in rows)
    near = sorted((miles(c, o), o) for o in all_cities if o is not c and o.get('lat') is not None and c.get('lat') is not None)[:6]
    near_html = ''.join(f'<a href="../{slug(o["name"])}/index.html">{e(o["name"])}<small>{d:.0f} mi &middot; pop. {n(o["pop2020"])}</small></a>' for d, o in near)
    path = f'/cities/{slug(name)}/'
    breg = big_region(c)
    reg_phrase = breg if breg.endswith('Washington') else f'{breg} Washington'
    fq = city_faq(c, all_cities, county, breg, electric, district)
    faq_details = '\n'.join(f'<details><summary>{e(q)}</summary><p>{h or e(a)}</p></details>' for q, a, h in fq)
    desc = city_desc(name, county, pop, bool(attr), len(CITY_ZIPS.get(name, {}).get('zips') or CITY_ZIPS.get(name, {}).get('po_box_zips') or []))
    posts = CITY_POSTS.get(slug(name), [])[:4]
    posts_html = ''
    if posts:
        posts_html = (f'<h2 class="st">{e(name)} in Our Washington Guides</h2><nav class="dir-list">'
                      + ''.join(f'<a href="/blog/{a["slug"]}/">{e(a["title"])}<small>{e(a.get("category", "Washington"))}</small></a>' for a in posts)
                      + '</nav>')
    keywords = (f'{name}, {name} Washington, {name} WA, {county} County Washington, {reg_phrase}, moving to {name}, '
                f'{name} schools, {name} utilities, Washington cities')
    tagline = city_tagline(name, county, breg)
    badges = ''.join(f'<span class="pill">{b}</span>' for b in (
        [f'&#128101; Pop. {pop}'] if pop else []) + [f'&#127963; {e(county)} County']
        + (['&#11088; State capital'] if c['capital'] else ['&#127963; County seat'] if c['seat'] else []))
    rslug = REGION_SLUGS.get(breg)
    badges += (f'<a href="../../regions/{rslug}/index.html" class="pill">&#128205; {e(breg)} Region</a>' if rslug
               else f'<span class="pill">&#128205; {e(breg)}</span>')
    city_ld = {'@context': 'https://schema.org', '@type': 'City', 'name': f'{name}, Washington', 'url': f'{BASE_URL}{path}',
               'containedInPlace': {'@type': 'AdministrativeArea', 'name': f'{county} County, Washington'}}
    if c.get('lat') is not None: city_ld['geo'] = {'@type': 'GeoCoordinates', 'latitude': c['lat'], 'longitude': c['lon']}
    same = [u for u in (c.get('wiki_url'), c.get('website')) if u]
    if same: city_ld['sameAs'] = same
    if c.get('image'): city_ld['image'] = c['image']
    bread = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': f'{BASE_URL}/'},
        {'@type': 'ListItem', 'position': 2, 'name': 'Washington Cities', 'item': f'{BASE_URL}/cities/'},
        {'@type': 'ListItem', 'position': 3, 'name': f'{county} County', 'item': f'{BASE_URL}/counties/{slug(county)}/'},
        {'@type': 'ListItem', 'position': 4, 'name': name, 'item': f'{BASE_URL}{path}'}]}
    faq_ld = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a, _ in fq]}
    sl = '\n'.join(f'<li><a href="{u}" target="_blank" rel="noopener">{t}</a></li>' for t, u in STATE_LINKS)
    local = []
    if c.get('website'): local.append(f'<li><a href="{e(c["website"])}" target="_blank" rel="noopener">City of {e(name)} official website</a></li>')
    for cn in counties:
        cw = COUNTY_SITES.get(cn)
        if cw: local.append(f'<li><a href="{e(cw)}" target="_blank" rel="noopener">{e(cn)} County official website</a></li>')
    local.append(f'<li><a href="../../counties/{slug(county)}/index.html">{e(county)} County guide on Washington Information</a></li>')
    if c.get('wiki_url'): local.append(f'<li><a href="{e(c["wiki_url"])}" target="_blank" rel="noopener">{e(name)} on Wikipedia</a></li>')
    reg_txt = f'the {e(region)} region' if region.endswith('Washington') else f'Washington&rsquo;s {e(region)} region'
    lead = f'{e(name)} is an incorporated {c.get("type", "city")} in {county_links(counties, "../../")}, in {reg_txt}' + (f', with a 2020 Census population of {pop}.' if pop else '.')
    if not (c.get('summary') or '').strip():
        lead += ' ' + data_story(c, all_cities, county)
    wx = weather_widget(name, c.get('lat'), c.get('lon'))
    vote = voter_card(county, name)
    return (head(city_title(name, len(CITY_ZIPS.get(name, {}).get('zips') or CITY_ZIPS.get(name, {}).get('po_box_zips') or [])), desc, path, 'article', c.get('image'), ld(city_ld) + ld(bread) + ld(faq_ld), '../../', keywords)
            + header('../../') + ticker_html(name) + alert_banner()
            + f'<div class="hero city-hero"{hero_style(breg)}><div class="wrap"><h1>{e(name)}, Washington</h1><p class="city-tagline">{e(tagline)}</p>'
            + f'<div class="pills">{badges}</div>'
            + f'<p class="hero-sub">{e(name)}, WA guide: population, schools, utilities, weather, attractions, nearby cities and a moving checklist for {e(county)} County, {e(reg_phrase)}.</p></div></div>'
            + f'<main><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="../../index.html">Home</a> &rsaquo; <a href="../index.html">Washington Cities</a> &rsaquo; <a href="../../counties/{slug(county)}/index.html">{e(county)} County</a> &rsaquo; {e(name)}</nav>'
            + (f'<p class="region-link"><a href="../../regions/{rslug}/index.html">Explore the {e(breg)} region &rarr;</a></p>' if rslug else '')
            + f'<h2 class="st">Quick Facts</h2><div class="qf"><section class="facts"><table>{facts}</table></section>{or_map}</div>'
            + wx
            + f'<h2 class="st">About {e(name)}</h2><section class="prose"><p>{lead}</p>{summary_html(c["summary"])}{wiki_credit(c) if c.get("wiki_url") and c.get("summary") else ""}</section>'
            + gallery(c, name)
            + f'<h2 class="st">Moving to {e(name)}</h2><div class="cards"><div class="card"><h3>&#9889; Utilities Checklist</h3><ul><li><strong>Electricity:</strong> {utility_links_html(electric)} (confirm by address)</li><li><strong>Natural gas:</strong> Puget Sound Energy, Cascade Natural Gas, Avista or NW Natural (where available)</li><li><strong>Water &amp; sewer:</strong> City of {e(name)}</li><li><strong>Trash:</strong> Franchised hauler &mdash; verify by service address</li><li><strong>Internet:</strong> Compare providers at the <a href="https://broadbandmap.fcc.gov/" target="_blank" rel="noopener">FCC broadband map</a></li></ul></div>'
            + f'<div class="card"><h3>&#128188; Jobs &amp; Economy</h3><ul><li><strong>Notable employers:</strong> {e(employers)}</li><li><a href="https://www.worksourcewa.com/" target="_blank" rel="noopener">WorkSource Washington (free)</a></li><li><a href="https://esd.wa.gov/" target="_blank" rel="noopener">Employment Security Department</a></li></ul></div>'
            + '<div class="card"><h3>&#127968; Housing</h3><ul><li><a href="https://www.zillow.com/wa/" target="_blank" rel="noopener">Zillow Washington</a></li><li><a href="https://www.apartments.com/washington/" target="_blank" rel="noopener">Apartments.com</a></li><li><a href="https://www.wshfc.org/" target="_blank" rel="noopener">WSHFC home-buyer programs</a></li></ul></div>'
            + '<div class="card"><h3>&#128663; DMV Steps</h3><ul><li>Washington driver license &amp; vehicle registration within <strong>30 days</strong> of becoming a resident</li><li><a href="https://dol.wa.gov/" target="_blank" rel="noopener">Department of Licensing (DOL)</a></li><li><a href="https://dol.wa.gov/" target="_blank" rel="noopener">Find a licensing office</a></li></ul></div>'
            + schools_card + attractions_card
            + vote
            + '<div class="card"><h3>&#127973; Healthcare &amp; Assistance</h3><ul><li><a href="https://www.washingtonconnection.org/" target="_blank" rel="noopener">Washington Connection (food, cash &amp; medical)</a></li><li><a href="https://www.wahealthplanfinder.org/" target="_blank" rel="noopener">Washington Healthplanfinder</a></li><li><a href="https://www.northwestharvest.org/" target="_blank" rel="noopener">Northwest Harvest food banks</a></li><li><a href="https://wa211.org/" target="_blank" rel="noopener">Dial 211 for local help</a></li></ul></div></div>'
            + posts_html
            + (f'<h2 class="st">Cities Near {e(name)}</h2><nav class="dir-list">{near_html}</nav>' if near_html else '')
            + f'<h2 class="st">{e(name)}, Washington: Frequently Asked Questions</h2><section class="faq">{faq_details}</section>'
            + f'<h2 class="st">Local &amp; Official Links</h2><section class="faq"><ul>{"".join(local)}{sl}</ul></section>'
            + '<p class="back"><a href="../index.html">&larr; All Washington Cities</a></p></div></main>'
            + footer('../../', '<br>Population: U.S. Census Bureau (2010, 2020). Background text: Wikipedia (CC BY-SA 4.0).'))


COUNTY_GEO = json.load(open('data/washington_counties_geo.json', encoding='utf-8'))['counties'] if os.path.exists('data/washington_counties_geo.json') else []


def state_county_map(highlight=None, labels=True, width=800):
    """Inline SVG map of Washington's 39 counties; each county links to its page. highlight = county name to emphasize."""
    if not COUNTY_GEO: return ''
    kx = math.cos(math.radians(47.3))
    rings = []
    for f in COUNTY_GEO:
        polys = f['coordinates'] if f['type'] == 'MultiPolygon' else [f['coordinates']]
        rings.append((f['name'], [p[0] for p in polys]))
    xs = [pt[0] * kx for _, rs in rings for r in rs for pt in r]; ys = [pt[1] for _, rs in rings for r in rs for pt in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = (width - 20) / (x1 - x0); height = round((y1 - y0) * sc + 20)
    P = lambda pt: ((pt[0] * kx - x0) * sc + 10, (y1 - pt[1]) * sc + 10)
    paths, texts = [], []
    for name, rs in rings:
        d = ' '.join('M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in map(P, r)) + 'Z' for r in rs)
        big = max(rs, key=len); pts = list(map(P, big))
        a2 = cx = cy = 0.0
        for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
            cr = xa * yb - xb * ya; a2 += cr; cx += (xa + xb) * cr; cy += (ya + yb) * cr
        cx, cy = (cx / (3 * a2), cy / (3 * a2)) if a2 else pts[0]
        on = name == highlight
        fill = '#e8835a' if on else '#e4eef3'
        paths.append(f'<a href="/counties/{slug(name)}/" aria-label="{e(name)} County"><path d="{d}" fill="{fill}" stroke="#1f6f6b" stroke-width="1.2">'
                     f'<title>{e(name)} County</title></path></a>')
        if labels:
            fs = 8 if name in ('San Juan', 'Island', 'Wahkiakum', 'Garfield', 'Columbia', 'Asotin', 'Kitsap', 'Pacific', 'Skamania', 'Cowlitz', 'Mason', 'Thurston') else 11
            texts.append(f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="{fs}" text-anchor="middle" dominant-baseline="middle" fill="#0e2a3b" '
                         f'font-family="system-ui,sans-serif" font-weight="{700 if on else 600}" pointer-events="none">{e(name)}</text>')
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Map of Washington counties" style="width:100%;height:auto;display:block">'
            f'<style>svg a path:hover{{fill:#e8835a}}</style>{"".join(paths)}{"".join(texts)}</svg>')


COUNTY_SITES = {}
CITY_POSTS = {}
CITY_SLUGS = set()


CENSUS_2020_OVERRIDES = {'Linn': '128610'}   # summary text only quotes a 2023 estimate


def county_census_2020(k):
    """data/counties.json 'pop2020' holds a later estimate; pages label the figure '2020 Census', so use the
    official 2020 count quoted in the county's Wikipedia summary (falls back to the stored value)."""
    if k['name'] in CENSUS_2020_OVERRIDES: return CENSUS_2020_OVERRIDES[k['name']]
    t = k.get('summary') or ''
    for pat in (r'2020 census,? (?:the |its |the county\'s )?population was ([\d,]+)', r'population was ([\d,]+) at the 2020 census',
                r'2020 census recorded the population as ([\d,]+)', r'2020 population of ([\d,]+)'):
        m = re.search(pat, t, re.I)
        if m: return m.group(1).replace(',', '').rstrip(',')
    return k['pop2020']


def load_city_posts():
    """Map city slug -> blog articles that link to that city page (for 'in our guides' links back from the city)."""
    if not os.path.exists('data/blog_articles.json'): return
    arts = sorted(json.load(open('data/blog_articles.json', encoding='utf-8')), key=lambda a: a.get('date', ''), reverse=True)
    for a in arts:
        f = f'data/blog_content/{a["slug"]}.html'
        if not os.path.exists(f): continue
        found = re.findall(r'cities/([a-z0-9-]+)/', open(f, encoding='utf-8').read())
        found += [sl for sl in CITY_SLUGS if f'-{sl}-' in f'-{a["slug"]}-'] * 3   # article is about this city
        for sl in dict.fromkeys(found):
            CITY_POSTS.setdefault(sl, []).append((sl in a['slug'], found.count(sl), a))
    for sl, lst in CITY_POSTS.items():   # posts about the city first, then by how often they link to it
        CITY_POSTS[sl] = [a for _, _, a in sorted(lst, key=lambda t: (not t[0], -t[1]))]


def replace_block(path, name, html_block):
    """Replace <!--name-->...<!--/name--> in a hand-maintained page; returns True if the markers were found."""
    if not os.path.exists(path): return False
    s = open(path, encoding='utf-8').read()
    pat = re.compile(r'<!--' + name + r'-->.*?<!--/' + name + r'-->', re.S)
    if not pat.search(s): return False
    s = pat.sub(lambda m: f'<!--{name}-->{html_block}<!--/{name}-->', s)
    with open(path, 'w', encoding='utf-8') as f: f.write(s)
    return True


def update_counties_index(counties, cities):
    """Fill the generated county table and ItemList schema inside the hand-designed counties/index.html."""
    rows = []
    for i, k in enumerate(sorted(counties, key=lambda k: -float(k['pop2020'] or 0)), 1):
        members = [c for c in cities if k['name'] in c['counties']]
        seat = next((c for c in cities if c['name'] == k['seat']), None)
        seat_html = f'<a href="/cities/{slug(seat["name"])}/">{e(seat["name"])}</a>' if seat else e(k['seat'])
        rows.append(f'<tr><td>{i}</td><td><a href="/counties/{slug(k["name"])}/">{e(k["name"])} County</a></td><td>{seat_html}</td>'
                    f'<td>{n(k["pop2020"])}</td><td>{len(members)}</td><td>{e(k.get("est", ""))}</td></tr>')
    table = ('<section><div class="wrap"><h2 class="section-title">Washington Counties Map</h2>'
             '<p class="section-sub">Washington&rsquo;s 39 counties, from San Juan, the smallest by land area, to Okanogan, the largest. Select any county on the map to open its guide.</p>'
             f'<figure style="max-width:900px;margin:0 auto">{state_county_map()}<figcaption style="font-size:.8rem;color:#5b6b75;margin-top:6px">'
             'Boundaries: U.S. Census Bureau. Click a county for its seat, population, cities and history.</figcaption></figure></div></section>'
             '<section><div class="wrap"><h2 class="section-title">List of Washington Counties by Population</h2>'
             '<p class="section-sub">All 39 Washington counties ranked by 2020 Census population, with each county seat, the number of incorporated cities and the year the county was established.</p>'
             '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.93rem" class="county-table">'
             '<thead><tr style="background:#0e2a3b;color:#fff;text-align:left"><th style="padding:9px">#</th><th style="padding:9px">County</th><th style="padding:9px">County seat</th>'
             '<th style="padding:9px">Population (2020)</th><th style="padding:9px">Cities</th><th style="padding:9px">Established</th></tr></thead><tbody>'
             + ''.join(rows) + '</tbody></table></div>'
             '<style>.county-table td{padding:9px;border-bottom:1px solid #dfe7ec}.county-table tr:nth-child(even) td{background:#f2f6f8}.county-table a{color:#1d5d8f}</style>'
             '<p style="font-size:.8rem;color:#5b6b75;margin-top:6px">Source: U.S. Census Bureau, 2020 Census.</p></div></section>')
    replace_block(f'{OUT}/counties/index.html', 'county-table', table)
    az = ('<div class="alpha-nav">' + ''.join(f'<a href="/counties/{slug(k["name"])}/">{e(k["name"])}</a>'
                                              for k in sorted(counties, key=lambda k: k['name'])) + '</div>')
    replace_block(f'{OUT}/counties/index.html', 'county-az', az)
    items = [{'@type': 'ListItem', 'position': i, 'name': f'{k["name"]} County, Washington', 'url': f'{BASE_URL}/counties/{slug(k["name"])}/'}
             for i, k in enumerate(sorted(counties, key=lambda k: k['name']), 1)]
    schema = json.dumps({'@context': 'https://schema.org', '@type': 'ItemList', 'name': 'Washington Counties', 'numberOfItems': len(items),
                         'itemListElement': items}, ensure_ascii=False)
    replace_block(f'{OUT}/counties/index.html', 'county-schema', f'<script type="application/ld+json">{schema}</script>')


def county_region_note(name, sub_region, members):
    """'Did you know?' line linking a county page to its 7-region page and its largest cities."""
    breg = BIG_REGION_MAP.get(sub_region, '')
    rslug = REGION_SLUGS.get(breg)
    if not rslug: return ''
    top = members[:3]
    cities = ''
    if top:
        links = [f'<a href="../../cities/{slug(c["name"])}/index.html">{e(c["name"])}</a>' for c in top]
        joined = links[0] if len(links) == 1 else ', '.join(links[:-1]) + ' and ' + links[-1]
        cities = f' Its largest {"city is" if len(top) == 1 else "cities are"} {joined}.'
    return (f'<p class="did-you-know"><strong>Did you know?</strong> {e(name)} County is part of the '
            f'<a href="../../regions/{rslug}/index.html">{e(breg)} region</a> of Washington.{cities}</p>')


def county_page(k, cities):
    name = k['name']; region, electric = COUNTY_INFO.get(name, ('Washington', 'Local utility'))
    members = sorted([c for c in cities if name in c['counties']], key=lambda c: -float(c['pop2020'] or 0))
    pop = n(k['pop2020']); area = k.get('area_sqmi')
    density = f'{float(k["pop2020"]) / float(area):,.1f} people per sq mi' if area and float(area) > 0 else ''
    seat = next((c for c in cities if c['name'] == k['seat']), None)
    seat_html = f'<a href="../../cities/{slug(seat["name"])}/index.html">{e(seat["name"])}</a>' if seat else e(k['seat'])
    rows = [('County seat', seat_html), ('Region', e(region)), ('Population (2020 Census)', pop), ('Land area', f'{n(area)} sq mi' if area else 'n/a')]
    if density: rows.append(('Population density', density))
    rows += [('Established', e(k['est']) or 'n/a')] + ([('Named for', e(k['named_for']))] if k.get('named_for') else []) + [
             ('Incorporated cities and towns', str(len(members))), ('Main electric utilities', utility_links_html(electric)), ('FIPS code', f'53{e(k["fips"])}')]
    if k.get('website'): rows.append(('Official county website', f'<a href="{e(k["website"])}" target="_blank" rel="noopener">{e(host(k["website"]))}</a>'))
    facts = ''.join(f'<tr><th>{a}</th><td>{b}</td></tr>' for a, b in rows)
    trs = ''.join(f'<tr><td><a href="../../cities/{slug(c["name"])}/index.html">{e(c["name"])}</a>{" &#9733;" if c["name"] == k["seat"] else ""}</td><td>{n(c["pop2020"])}</td><td>{e(c.get("incorporated", ""))}</td></tr>' for c in members)
    path = f'/counties/{slug(name)}/'
    desc = f'{name} County, Washington: county seat {k["seat"]}, population {pop} (2020 Census), {len(members)} incorporated cities and towns, map, history and official links.'
    ld_obj = {'@context': 'https://schema.org', '@type': 'AdministrativeArea', 'name': f'{name} County, Washington', 'url': f'{BASE_URL}{path}',
              'containedInPlace': {'@type': 'State', 'name': 'Washington'}}
    if k.get('lat') is not None: ld_obj['geo'] = {'@type': 'GeoCoordinates', 'latitude': k['lat'], 'longitude': k['lon']}
    same = [u for u in (k.get('wiki_url'), k.get('website')) if u]
    if same: ld_obj['sameAs'] = same
    bread = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': f'{BASE_URL}/'},
        {'@type': 'ListItem', 'position': 2, 'name': 'Washington Counties', 'item': f'{BASE_URL}/counties/'},
        {'@type': 'ListItem', 'position': 3, 'name': f'{name} County', 'item': f'{BASE_URL}{path}'}]}
    links = []
    if k.get('website'): links.append(f'<li><a href="{e(k["website"])}" target="_blank" rel="noopener">{e(name)} County official website</a></li>')
    links += ['<li><a href="https://wa211.org/" target="_blank" rel="noopener">Washington 211 &mdash; local assistance</a></li>',
              '<li><a href="https://dol.wa.gov/" target="_blank" rel="noopener">Department of Licensing &mdash; driver and vehicle services</a></li>',
              '<li><a href="https://www.worksourcewa.com/" target="_blank" rel="noopener">WorkSource Washington</a></li>',
              '<li><a href="https://voter.votewa.gov/" target="_blank" rel="noopener">VoteWA &mdash; voter registration</a></li>',
              '<li><a href="https://wsac.org/" target="_blank" rel="noopener">Washington State Association of Counties</a></li>']
    if k.get('wiki_url'): links.append(f'<li><a href="{e(k["wiki_url"])}" target="_blank" rel="noopener">{e(name)} County on Wikipedia</a></li>')
    names = [c['name'] for c in members]
    cfq = [(f'What is the county seat of {name} County, Washington?', f'{k["seat"]} is the county seat of {name} County.')]
    if names:
        listed = ', '.join(names[:12]) + (f' and {len(names) - 12} more' if len(names) > 12 else '')
        cfq.append((f'What cities are in {name} County, Washington?',
                    f'{name} County has {len(names)} incorporated {"city or town" if len(names) == 1 else "cities and towns"}: {listed}.'))
    if pop: cfq.append((f'What is the population of {name} County, Washington?', f'{name} County had {pop} residents at the 2020 U.S. Census.'
                        + (f' The largest city is {names[0]}.' if names else '')))
    if k.get('est'): cfq.append((f'When was {name} County established?', f'{name} County was established in {k["est"]}.'))
    if k.get('named_for'): cfq.append((f'How did {name} County get its name?', f'{name} County is named for {k["named_for"]}.'))
    cfaq_ld = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in cfq]}
    cfaq_html = ''.join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in cfq)
    return (head(f'{name} County, Washington: Cities, Population & Living Guide', desc, path, 'article', k.get('image'), ld(ld_obj) + ld(bread) + ld(cfaq_ld), '../../')
            + header('../../') + ticker_html(name + ' County') + alert_banner()
            + f'<div class="hero"><div class="wrap"><h1>{e(name)} County, Washington</h1><p>County seat: {e(k["seat"])} &middot; {e(region)} region &middot; {len(members)} incorporated cities and towns</p></div></div>'
            + f'<main><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="../../index.html">Home</a> &rsaquo; <a href="../index.html">Washington Counties</a> &rsaquo; {e(name)} County</nav>'
            + county_region_note(name, region, members)
            + f'<h2 class="st">Quick Facts</h2><section class="facts"><table>{facts}</table></section>'
            + (f'<h2 class="st">{e(name)} County Map</h2><figure style="max-width:640px">{state_county_map(name, labels=False, width=640)}'
               f'<figcaption class="src">{e(name)} County (highlighted) among Washington&rsquo;s 39 counties. Select another county to explore it. '
               'Boundaries: U.S. Census Bureau.</figcaption></figure>' if COUNTY_GEO else '')
            + f'<h2 class="st">About {e(name)} County</h2><section class="prose">{summary_html(k["summary"], 1400) or county_story(k, members)}{wiki_credit(k) if k.get("wiki_url") and k.get("summary") else ""}</section>'
            + photo(k, f'{name} County, Washington')
            + f'<h2 class="st">Cities in {e(name)} County</h2><table class="tbl"><tr><th>City</th><th>Population (2020)</th><th>Incorporated</th></tr>{trs}</table><p class="src">&#9733; county seat. Cities that span more than one county are listed in each.</p>'
            + f'<h2 class="st">{e(name)} County: Frequently Asked Questions</h2><section class="faq">{cfaq_html}</section>'
            + f'<h2 class="st">Official &amp; Helpful Links</h2><section class="faq"><ul>{"".join(links)}</ul></section>'
            + '<p class="back"><a href="../index.html">&larr; All Washington Counties</a></p></div></main>'
            + footer('../../', '<br>Population: U.S. Census Bureau 2020. Background text: Wikipedia (CC BY-SA 4.0).'))


def cities_index(cities):
    groups = {}
    for c in sorted(cities, key=lambda x: x['name'].lower()):
        groups.setdefault(c['name'][0].upper(), []).append(c)
    alpha = ''.join(f'<a href="#letter-{L.lower()}">{L}</a>' for L in groups)
    body = ''.join(f'<h3 class="letter" id="letter-{L.lower()}">{L}</h3><nav class="dir-list">' + ''.join(
        f'<a href="{slug(c["name"])}/index.html" data-n="{e(c["name"].lower())} {e(" ".join(c["counties"]).lower())}">{e(c["name"])}<small>{e(", ".join(c["counties"]))} Co. &middot; pop. {n(c["pop2020"])}</small></a>' for c in cs) + '</nav>' for L, cs in groups.items())
    js = "<script>document.getElementById('q').addEventListener('input',function(){var v=this.value.toLowerCase();document.querySelectorAll('.dir-list a').forEach(function(a){a.style.display=a.dataset.n.indexOf(v)>-1?'':'none'});});</script>"
    N = len(cities)
    desc = f'Complete list of all {N} incorporated cities and towns in Washington, A to Z, with county and 2020 Census population, plus the largest cities ranked.'
    ranked = sorted(cities, key=lambda c: -float(c['pop2020'] or 0))
    top = ranked[:20]
    top_rows = ''.join(f'<tr><td>{i}</td><td><a href="/cities/{slug(c["name"])}/">{e(c["name"])}</a></td><td>{e(", ".join(c["counties"]))}</td><td>{n(c["pop2020"])}</td></tr>'
                       for i, c in enumerate(top, 1))
    smallest = ranked[-1]
    total = sum(float(c['pop2020'] or 0) for c in cities)
    cities_ld = ld({'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': f'List of Cities in Washington', 'description': desc,
                    'url': f'{BASE_URL}/cities/', 'mainEntity': {'@type': 'ItemList', 'numberOfItems': N, 'itemListElement': [
                        {'@type': 'ListItem', 'position': i, 'name': f'{c["name"]}, Washington', 'url': f'{BASE_URL}/cities/{slug(c["name"])}/'}
                        for i, c in enumerate(sorted(cities, key=lambda x: x['name'].lower()), 1)]}})
    bread = ld({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': f'{BASE_URL}/'},
        {'@type': 'ListItem', 'position': 2, 'name': 'Washington Cities', 'item': f'{BASE_URL}/cities/'}]})
    ntown = sum(1 for c in cities if c.get('type') == 'town')
    intro = (f'<section class="prose" style="margin-top:18px"><p>Washington has <strong>{N} incorporated municipalities</strong> &mdash; {N - ntown} cities and {ntown} towns &mdash; spread across its 39 counties. '
             f'Together they are home to about {total / 1e6:.1f} million people &mdash; about {round(total / 7705281 * 100)}% of the state&rsquo;s 7.71 million residents (2020 Census); the rest live in unincorporated areas. '
             f'<a href="/cities/seattle/">Seattle</a> is the largest city, <a href="/cities/olympia/">Olympia</a> is the state capital, and '
             f'<a href="/cities/{slug(smallest["name"])}/">{e(smallest["name"])}</a> is the smallest, with {n(smallest["pop2020"])} residents at the 2020 Census. '
             'Every city below links to its own guide with population history, schools, utilities, weather, nearby cities and official links. '
             'You can also browse cities <a href="/counties/">by county</a> or <a href="/regions/">by region</a>.</p></section>')
    top_html = (f'<h2 class="st">Largest Cities in Washington by Population</h2><table class="tbl"><tr><th>Rank</th><th>City</th><th>County</th><th>Population (2020)</th></tr>{top_rows}</table>'
                '<p class="src">Source: U.S. Census Bureau, 2020 Census.</p>')
    return (head(f'List of Cities in Washington: All {N} Cities A–Z by County', desc, '/cities/', extra=cities_ld + bread, up='../') + header('../') + ticker_html('cities') + alert_banner()
            + f'<div class="hero"><div class="wrap"><h1>List of Cities in Washington (A&ndash;Z)</h1><p>All {N} incorporated cities and towns in Washington, with county and 2020 Census population.</p></div></div>'
            + f'<main><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Home</a> &rsaquo; Washington Cities</nav>' + intro + top_html
            + f'<h2 class="st">All {N} Washington Cities A&ndash;Z</h2><p style="margin:18px 0 8px"><input id="q" type="search" placeholder="Filter by city or county name..." aria-label="Filter cities"></p>'
            + f'<nav class="alpha">{alpha}</nav>{body}</div></main>' + js + footer('../', '<br>Population: U.S. Census Bureau 2020.'))


EAST_COUNTIES = {'Adams', 'Asotin', 'Benton', 'Chelan', 'Columbia', 'Douglas', 'Ferry', 'Franklin', 'Garfield', 'Grant', 'Kittitas', 'Klickitat',
                 'Lincoln', 'Okanogan', 'Pend Oreille', 'Spokane', 'Stevens', 'Walla Walla', 'Whitman', 'Yakima'}
COUNTY_AREA_CODES = {'King': ('206', '253', '425', '360'), 'Pierce': ('253', '360'), 'Snohomish': ('425', '360')}
CITY_AREA_CODES = {'Seattle': ('206', '564')}   # USPS ZIP records list stray codes for Seattle
OVERLAY = {'360': '564', '206': '564'}   # 564 overlays 360 (2017) and 206 (2025)


def area_codes_for(county, city=None):
    """Area codes for a city (from its USPS ZIP records) or, failing that, its county; 564 overlay added where it applies."""
    if city in CITY_AREA_CODES: return CITY_AREA_CODES[city]
    allowed = list(COUNTY_AREA_CODES.get(county) or (('509',) if county in EAST_COUNTIES else ('360',)))
    codes = [x for x in (CITY_ZIPS.get(city, {}) if city else {}).get('area_codes') or [] if x in allowed] or allowed
    for x in list(codes):
        if x in OVERLAY and OVERLAY[x] not in codes: codes.append(OVERLAY[x])
    return tuple(sorted(codes, key=lambda x: (x == '564', x)))


def guide_page(path, title, desc, h1, sub, body, faq, crumb, page_type='WebPage'):
    """Standalone reference page (ZIP codes, area codes) with breadcrumb + FAQ schema and a visible FAQ."""
    page_ld = {'@context': 'https://schema.org', '@type': page_type, 'name': title, 'description': desc, 'url': f'{BASE_URL}{path}',
               'isPartOf': {'@type': 'WebSite', 'name': SITE_NAME, 'url': f'{BASE_URL}/'}, 'dateModified': TODAY}
    bread = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': f'{BASE_URL}/'},
        {'@type': 'ListItem', 'position': 2, 'name': crumb, 'item': f'{BASE_URL}{path}'}]}
    faq_ld = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': re.sub(r'<[^>]+>', '', a)}} for q, a in faq]}
    faq_html = ''.join(f'<details><summary>{e(q)}</summary><p>{a}</p></details>' for q, a in faq)
    return (head(title, desc, path, extra=ld(page_ld) + ld(bread) + ld(faq_ld), up='../') + header('../') + ticker_html(path) + alert_banner()
            + f'<div class="hero"><div class="wrap"><h1>{h1}</h1><p>{sub}</p></div></div>'
            + f'<main><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> &rsaquo; {e(crumb)}</nav>{body}'
            + f'<h2 class="st">Frequently Asked Questions</h2><section class="faq">{faq_html}</section></div></main>' + footer('../'))


def zip_page(cities):
    data = json.load(open('data/washington_zips.json', encoding='utf-8'))['zips']
    norm = lambda t: re.sub(r'[^a-z]', '', t.lower().replace('saint ', 'st ').replace('mount ', 'mt '))
    city_by = {norm(c['name']): c for c in cities}
    N = len(data); std = sum(1 for z in data if z['type'] == 'STANDARD')
    rows = []
    for z in data:
        c = city_by.get(norm(z['city']))
        cname = f'<a href="/cities/{slug(c["name"])}/">{e(c["name"])}</a>' if c else e(z['city'].title())
        typ = {'STANDARD': 'Standard', 'PO BOX': 'PO Box', 'UNIQUE': 'Unique (single organization)'}.get(z['type'], z['type'].title())
        rows.append(f'<tr data-n="{z["zip"]} {e(z["city"].lower())} {e(z["county"].lower())}"><td>{z["zip"]}</td><td>{cname}</td>'
                    + (f'<td><a href="/counties/{slug(z["county"])}/">{e(z["county"])}</a></td>' if os.path.exists(f'{OUT}/counties/{slug(z["county"])}/index.html')
                       else f'<td>{e(z["county"])} (CA)</td>' if z['county'] == 'Modoc' else f'<td>{e(z["county"])}</td>') + f'<td>{typ}</td></tr>')
    top = sorted(cities, key=lambda c: -float(c['pop2020'] or 0))[:12]
    top_rows = ''.join(f'<tr><td><a href="/cities/{slug(c["name"])}/">{e(c["name"])}</a></td><td>{", ".join((CITY_ZIPS.get(c["name"], {}).get("zips") or ["—"])[:14])}'
                       f'{" &hellip;" if len(CITY_ZIPS.get(c["name"], {}).get("zips") or []) > 14 else ""}</td></tr>' for c in top)
    js = ("<script>document.getElementById('zq').addEventListener('input',function(){var v=this.value.toLowerCase().trim();"
          "document.querySelectorAll('#ziptbl tbody tr').forEach(function(r){r.style.display=r.dataset.n.indexOf(v)>-1?'':'none'});});</script>")
    zl = lambda nm, k=8: ', '.join((CITY_ZIPS.get(nm, {}).get('zips') or [])[:k])
    body = (f'<section class="prose" style="margin-top:18px"><p>Washington has <strong>{N} active ZIP codes</strong>, and every one of them begins with <strong>98</strong> or <strong>99</strong>. '
            f'{std} are standard delivery ZIP codes, and the rest are PO box or single-organization ZIP codes. The first three digits point to a region: 980&ndash;981 cover Seattle and King County; '
            '982 covers Everett, Snohomish County and the North Sound; 983&ndash;984 cover Tacoma, Pierce County and the Kitsap Peninsula; 985 covers Olympia and the coast; 986 covers Vancouver and Clark County; '
            '988 covers Wenatchee and north-central Washington; 989 covers Yakima; 990&ndash;992 cover Spokane and the rest of Eastern Washington; 993 covers the Tri-Cities; and 994 covers Clarkston. '
            'Search the full list below by ZIP code, city or county, or open any city for its population, schools and moving guide.</p>'
            '<p>Looking for phone numbers instead? See <a href="/washington-area-codes/">Washington area codes</a>.</p></section>'
            f'<h2 class="st">ZIP Codes for Washington&rsquo;s Largest Cities</h2><table class="tbl"><tr><th>City</th><th>Standard ZIP codes</th></tr>{top_rows}</table>'
            f'<h2 class="st">All {N} Washington ZIP Codes</h2><p style="margin:12px 0 8px"><input id="zq" style="width:100%;padding:12px 14px;font-size:1rem;border:2px solid #d3dfe6;border-radius:8px" type="search" placeholder="Search by ZIP code, city or county..." aria-label="Search Washington ZIP codes"></p>'
            f'<div style="overflow-x:auto"><table class="tbl" id="ziptbl"><thead><tr><th>ZIP code</th><th>City</th><th>County</th><th>Type</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<p class="src">Source: USPS ZIP code data. ZIP codes follow postal routes, not city limits, so an address can carry a city name in its mailing address without being inside that city.</p>' + js)
    first, last = data[0], data[-1]
    faq = [('How many ZIP codes are in Washington?', f'Washington has {N} active ZIP codes: {std} standard delivery ZIP codes plus PO box and single-organization ZIP codes.'),
           ('What do Washington ZIP codes start with?', f'Every Washington ZIP code starts with 98 or 99, running from {first["zip"]} ({first["city"].title()}) to {last["zip"]} ({last["city"].title()}).'),
           ('What is the ZIP code for Seattle, Washington?', f'Seattle has dozens of ZIP codes, all starting with 981, including {zl("Seattle")}. Downtown Seattle is mainly 98101, 98104 and 98121.'),
           ('What is the ZIP code for Spokane, Washington?', 'Spokane ZIP codes include ' + zl('Spokane') + '.'),
           ('What is the ZIP code for Tacoma, Washington?', 'Tacoma ZIP codes include ' + zl('Tacoma') + '.'),
           ('What is the ZIP code for Olympia, Washington?', 'Olympia ZIP codes include ' + zl('Olympia') + '.'),
           ('Does a ZIP code tell me which city I live in?', 'Not always. ZIP codes are drawn for mail delivery, so many homes outside city limits use a nearby city&rsquo;s name and ZIP code. Check your county&rsquo;s property records to confirm which city, if any, you are in.')]
    return guide_page('/washington-zip-codes/', f'Washington ZIP Codes: All {N} ZIP Codes by City & County', f'Complete list of all {N} Washington ZIP codes with city, county and type. Search any ZIP code and find ZIP codes for Seattle, Spokane, Tacoma and every Washington city.',
                      'Washington ZIP Codes', f'All {N} Washington ZIP codes, searchable by ZIP code, city or county.', body, faq, 'Washington ZIP Codes', 'CollectionPage')


def area_code_page(cities):
    def city_links(names):
        return ', '.join(f'<a href="/cities/{slug(n)}/">{e(n)}</a>' for n in names if any(c['name'] == n for c in cities))
    def county_links_(names):
        return ', '.join(f'<a href="/counties/{slug(c)}/">{c}</a>' for c in sorted(names))
    west = sorted({k for c in cities for k in c['counties']} - EAST_COUNTIES - {'King', 'Pierce', 'Snohomish'})
    body = ('<section class="prose" style="margin-top:18px"><p>Washington has <strong>six area codes</strong>. Four of them split up western Washington: <strong>206</strong> covers Seattle and a few close-in suburbs, '
            '<strong>253</strong> covers Tacoma and the south end of the Puget Sound metro, <strong>425</strong> covers the Eastside and southern Snohomish County, and <strong>360</strong> covers the rest of western Washington. '
            '<strong>564</strong> is an overlay that adds new numbers in the 360 area (since 2017) and in Seattle&rsquo;s 206 area (since 2025). East of the Cascades, the whole region uses <strong>509</strong>. '
            'Ten-digit dialing (area code plus number) is required for local calls throughout Washington.</p></section>'
            '<h2 class="st">Washington Area Codes at a Glance</h2><table class="tbl"><tr><th>Area code</th><th>Region</th><th>In service</th></tr>'
            '<tr><td><strong>206</strong></td><td>Seattle, plus nearby communities such as Burien, Shoreline and Mercer Island</td><td>1947 (originally all of western Washington)</td></tr>'
            '<tr><td><strong>253</strong></td><td>Tacoma, Pierce County and south King County (Kent, Auburn, Federal Way)</td><td>1997 (split from 206)</td></tr>'
            '<tr><td><strong>425</strong></td><td>The Eastside and southern Snohomish County: Bellevue, Redmond, Kirkland, Renton, Everett, Lynnwood</td><td>1997 (split from 206)</td></tr>'
            '<tr><td><strong>360</strong></td><td>The rest of western Washington: Olympia, Vancouver, Bellingham, the Olympic Peninsula and the coast</td><td>1995 (split from 206)</td></tr>'
            '<tr><td><strong>564</strong></td><td>Overlay for the 360 area (2017) and the 206 area (2025)</td><td>2017</td></tr>'
            '<tr><td><strong>509</strong></td><td>All of eastern Washington: Spokane, Yakima, the Tri-Cities, Wenatchee, Walla Walla</td><td>1957</td></tr></table>'
            f'<h2 class="st">Area Code 206</h2><p><strong>Major cities:</strong> {city_links(["Seattle", "Shoreline", "Burien", "Mercer Island", "Lake Forest Park", "Tukwila", "SeaTac", "Normandy Park"])}.</p>'
            f'<h2 class="st">Area Code 253</h2><p><strong>Major cities:</strong> {city_links(["Tacoma", "Kent", "Federal Way", "Auburn", "Lakewood", "Puyallup", "University Place", "Bonney Lake", "Gig Harbor", "Sumner", "Fife", "Milton"])}.</p>'
            f'<h2 class="st">Area Code 425</h2><p><strong>Major cities:</strong> {city_links(["Bellevue", "Everett", "Renton", "Kirkland", "Redmond", "Sammamish", "Lynnwood", "Bothell", "Edmonds", "Issaquah", "Mukilteo", "Mill Creek", "Woodinville"])}.</p>'
            f'<h2 class="st">Area Codes 360 and 564</h2><p><strong>Counties:</strong> {county_links_(west)}, plus northern Snohomish County and parts of Pierce County.</p>'
            f'<p><strong>Major cities:</strong> {city_links(["Vancouver", "Olympia", "Bellingham", "Marysville", "Lacey", "Bremerton", "Longview", "Mount Vernon", "Port Angeles", "Aberdeen", "Oak Harbor", "Camas", "Centralia"])}.</p>'
            f'<h2 class="st">Area Code 509</h2><p><strong>Counties:</strong> {county_links_(EAST_COUNTIES)}.</p>'
            f'<p><strong>Major cities:</strong> {city_links(["Spokane", "Spokane Valley", "Yakima", "Kennewick", "Pasco", "Richland", "Wenatchee", "Walla Walla", "Pullman", "Moses Lake", "Ellensburg", "Clarkston"])}.</p>'
            '<p class="src">Area code boundaries follow telephone exchanges, not county lines, so communities near the edges can be exceptions. Cell phone numbers keep the area code where they were issued.</p>'
            '<p>Looking for mailing addresses instead? See all <a href="/washington-zip-codes/">Washington ZIP codes</a>.</p>')
    faq = [('What are the area codes in Washington?', 'Washington has six area codes: 206 (Seattle), 253 (Tacoma and south King County), 425 (the Eastside and southern Snohomish County), 360 and its overlay 564 (the rest of western Washington), and 509 (eastern Washington).'),
           ('What area code is Seattle, Washington?', 'Seattle uses area code 206. Since 2025, some new Seattle numbers are issued in the 564 overlay.'),
           ('What area code is Spokane, Washington?', 'Spokane uses area code 509, like the rest of eastern Washington.'),
           ('What area code is Tacoma, Washington?', 'Tacoma uses area code 253.'),
           ('What area code is Bellevue, Washington?', 'Bellevue and most of the Eastside use area code 425.'),
           ('What area code is Vancouver, Washington?', 'Vancouver uses area code 360, with new numbers also issued in the 564 overlay.'),
           ('Do I need to dial the area code for local calls in Washington?', 'Yes. Ten-digit dialing is required for local calls throughout Washington, because of the 564 overlay in western Washington and the 988 crisis line change in the 509 area.')]
    return guide_page('/washington-area-codes/', 'Washington Area Codes: 206, 253, 360, 425, 509 & 564', 'All six Washington area codes explained: 206 for Seattle, 253 for Tacoma, 425 for the Eastside, 360 and 564 for the rest of western Washington and 509 for eastern Washington.',
                      'Washington Area Codes', 'Which area code covers which part of Washington: 206, 253, 360, 425, 509 and 564.', body, faq, 'Washington Area Codes')


def simple_page(path, title, desc, h1, sub, body, page_type='WebPage'):
    page_ld = ld({'@context': 'https://schema.org', '@type': page_type, 'name': title, 'description': desc, 'url': f'{BASE_URL}{path}',
                  'isPartOf': {'@type': 'WebSite', 'name': 'Washington Information', 'url': f'{BASE_URL}/'}})
    return (head(title, desc, path, extra=page_ld, up='../') + header('../') + ticker_html(path) + alert_banner()
            + f'<div class="hero"><div class="wrap"><h1>{h1}</h1><p>{sub}</p></div></div>'
            + f'<main><div class="wrap prose"><nav class="crumbs"><a href="../index.html">Home</a> &rsaquo; {h1}</nav>{body}</div></main>' + footer('../'))


ABOUT = f'''<h2 class="st">What Washington Information is</h2>
<p>Washington Information is an independent, free guide to the State of Washington. It brings together practical facts about all 281 incorporated cities and towns and all 39 counties &mdash; population, history, location, official websites &mdash; along with step-by-step guides for people <a href="../moving-to-washington/index.html">moving to Washington</a> and people <a href="../visit-washington/index.html">visiting</a>.</p>
<h2 class="st">Who it is for</h2>
<p>Newcomers comparing places to live, visitors planning a trip, and Washingtonians who want a quick, plain-language starting point before contacting a city, county or state office.</p>
<h2 class="st">Where the information comes from</h2>
<ul style="padding-left:20px">
<li>Population figures: U.S. Census Bureau (2010 and 2020 decennial census).</li>
<li>City and county background, incorporation dates, coordinates and photos: Wikipedia, Wikidata and Wikimedia Commons, used under their Creative Commons licenses with attribution on each page.</li>
<li>Government services and programs: official State of Washington websites, linked directly.</li>
</ul>
<p>We check sources carefully, but details such as utility providers, school assignments and office hours change. Always confirm with the official agency before making decisions.</p>
<h2 class="st">Independence</h2>
<p>Washington Information is not affiliated with, endorsed by, or operated by the State of Washington or any city or county government.</p>
<h2 class="st">Corrections and suggestions</h2>
<p>Spotted something out of date? Please <a href="../contact/index.html">contact us</a> &mdash; corrections are welcome and appreciated.</p>'''

CONTACT = f'''<h2 class="st">Get in touch</h2>
<p>Questions, corrections, or suggestions for a city or county page? Email us at <!--email_off--><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a><!--/email_off-->. We read every message and aim to reply within a few business days.</p>
<h2 class="st">Reporting a correction</h2>
<p>To help us fix things quickly, please include the page address (URL), what is wrong, and a link to an official source if you have one.</p>
<h2 class="st">Need government help?</h2>
<p>Washington Information is an independent website and cannot process applications or access government records. For official help:</p>
<ul style="padding-left:20px">
<li><a href="https://wa.gov/" target="_blank" rel="noopener">WA.gov</a> &mdash; state agencies</li>
<li><a href="https://dol.wa.gov/" target="_blank" rel="noopener">Washington Department of Licensing</a> &mdash; driver licenses and vehicles</li>
<li><a href="https://www.washingtonconnection.org/" target="_blank" rel="noopener">Washington Connection</a> &mdash; food, cash and medical assistance</li>
<li><a href="https://wa211.org/" target="_blank" rel="noopener">Washington 211</a> &mdash; dial 2-1-1 for local resources</li>
</ul>'''

ADVERTISE = f'''<h2 class="st">Reach people planning their Washington move or trip</h2>
<p>Washington Information is an independent guide used by people who are moving to, visiting, or exploring Washington. Our pages cover all 281 incorporated cities and towns, 39 counties and 7 regions, plus moving and visiting guides. Visitors arrive with clear intent: choosing a town, planning a trip, or looking for local services.</p>
<h2 class="st">Placement options</h2>
<ul><li>Sitewide or section banners (city, county, region or guide pages)</li><li>Sponsored placement on a specific city, county or region page</li><li>Standard IAB sizes such as 728x90, 300x250, 336x280, 300x600 and 320x50, static or animated</li></ul>
<h2 class="st">Get started</h2>
<p>Email <!--email_off--><a href="mailto:{CONTACT_EMAIL}?subject=Advertising%20on%20Washington%20Information">{CONTACT_EMAIL}</a><!--/email_off--> with your business, the pages or regions you want to reach, preferred sizes and dates. We reply within a few business days with availability and rates.</p>
'''

PRIVACY_UPDATED = 'November 6, 2026'   # change only when the policy text changes
PRIVACY = f'''<p><em>Last updated: {PRIVACY_UPDATED}</em></p>
<h2 class="st">Summary</h2>
<p>Washington Information is a read-only informational website. We do not require accounts, we do not sell personal information, and we do not run advertising trackers.</p>
<h2 class="st">Information collected automatically</h2>
<p>Like nearly all websites, our hosting provider and content-delivery/security service (Cloudflare) automatically record standard technical data when you visit &mdash; such as your IP address, browser type, the page requested, and the date and time. This data is used to deliver the site, keep it secure, and understand overall traffic. Cloudflare may set strictly necessary security cookies.</p>
<h2 class="st">Information you send us</h2>
<p>If you email us, we receive your email address and whatever you include in your message. We use it only to reply and to improve the site, and we do not share it.</p>
<h2 class="st">Analytics</h2>
<p>We use Google Tag Manager and Google Analytics 4, web analytics services provided by Google LLC, to understand how visitors use the site (for example, which pages are viewed, how long visits last, approximate location at the city/region level, device and browser type, and how visitors arrived). Google Analytics uses cookies and similar technologies, and the information it collects is processed by Google under its own privacy policy. We use this data only in aggregate to improve the site; we do not use it to identify individual visitors, and we do not use Google Analytics advertising features.</p>
<p>You can learn how Google uses this data at <a href="https://policies.google.com/technologies/partner-sites" rel="noopener">policies.google.com/technologies/partner-sites</a>, and you can opt out of Google Analytics on all websites by installing the <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener">Google Analytics Opt-out Browser Add-on</a>. You can also block or delete cookies in your browser settings.</p>
<h2 class="st">Third-party links and images</h2>
<p>Pages link to government agencies and other external websites, and some photos are loaded from Wikimedia Commons. Those sites have their own privacy policies, which we do not control.</p>
<h2 class="st">Children</h2>
<p>This site is intended for a general audience and does not knowingly collect information from children under 13.</p>
<h2 class="st">Changes and contact</h2>
<p>We may update this policy; the date above shows the latest revision. Questions? Email <!--email_off--><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a><!--/email_off-->.</p>'''


def big_region(city):
    """Return the 7-region name for a city dict."""
    county = city['counties'][0]
    sub = COUNTY_INFO.get(county, ('Unknown',))[0]
    return BIG_REGION_MAP.get(sub, 'Washington')


def region_page(rname, rcities):
    rc = REGION_CONTENT[rname]
    rslug = REGION_SLUGS[rname]
    path = f'/regions/{rslug}/'
    desc = rc['desc']
    meta_desc = (f"{rname} guide: {len(rcities)} cities across {len(REGION_COUNTIES[rname])} counties. "
                 f"Population, living, visiting and travel information for every {rname} city.")
    counties_list = REGION_COUNTIES[rname]
    evoke = REGION_THEME.get(rname, ('', '', ''))[2]
    total_pop = sum(int(float(c['pop2020'] or 0)) for c in rcities)
    r_kw = f"{rname if rname.endswith('Washington') else rname + ' Washington'}, {rname} cities, living in {rname}, visiting {rname}, " + ', '.join(f'{cn} County Washington' for cn in REGION_COUNTIES[rname]) + ', Washington regions'
    counties_html = ', '.join(f'<a href="../../counties/{slug(cn)}/index.html">{e(cn)} County</a>' for cn in counties_list)
    sorted_cities = sorted(rcities, key=lambda c: -float(c['pop2020'] or 0))
    top = sorted_cities[:18]
    cities_grid = ''.join(
        f'<a href="../../cities/{slug(c["name"])}/index.html">{e(c["name"])}'
        f'<small>{e(c["counties"][0])} Co. &middot; pop. {n(c["pop2020"])}</small></a>' for c in top)
    all_rows = ''.join(
        f'<tr><td><a href="../../cities/{slug(c["name"])}/index.html">{e(c["name"])}</a></td>'
        f'<td>{e(", ".join(c["counties"]))}</td><td>{n(c["pop2020"])}</td></tr>' for c in sorted_cities)
    highlights_html = ''.join(f'<li style="padding:4px 0">{e(h)}</li>' for h in rc['highlights'])
    ld_obj = {'@context':'https://schema.org','@type':'Place','name':f'{rname}, Washington','url':f'{BASE_URL}{path}',
              'containedInPlace':{'@type':'State','name':'Washington'}}
    bread = {'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[
        {'@type':'ListItem','position':1,'name':'Home','item':f'{BASE_URL}/'},
        {'@type':'ListItem','position':2,'name':'Washington Regions','item':f'{BASE_URL}/regions/'},
        {'@type':'ListItem','position':3,'name':rname,'item':f'{BASE_URL}{path}'}]}
    return (head(f'{rname}: {len(rcities)} Cities, Living & Travel Guide', meta_desc, path, 'article', None, ld(ld_obj)+ld(bread), '../../', r_kw)
            + header('../../') + ticker_html(rname) + alert_banner()
            + f'<div class="hero region-hero"{hero_style(rname)}>{state_silhouette()}<div class="wrap"><h1>{e(rname)}, Washington</h1>'
            + f'<p class="city-tagline">{e(evoke)}</p><p class="hero-sub">{e(rc["hero_sub"])}</p>'
            + f'<div class="pills"><span class="pill">&#127961; {len(rcities)} cities</span><span class="pill">&#127963; {len(counties_list)} counties</span>'
            + f'<span class="pill">&#128101; {total_pop:,} residents (2020)</span></div></div></div>'
            + f'<main><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="../../index.html">Home</a> &rsaquo; <a href="../index.html">Washington Regions</a> &rsaquo; {e(rname)}</nav>'
            + f'<h2 class="st">About the {e(rname)} Region</h2><section class="prose"><p>{e(desc)}</p></section>'
            + f'<h2 class="st">Counties</h2><p class="prose" style="margin:8px 0 24px">{counties_html}</p>'
            + f'<h2 class="st">Highlights</h2><ul style="padding-left:20px;margin:0 0 24px">{highlights_html}</ul>'
            + f'<h2 class="st">Living in {e(rname)}</h2><section class="prose"><p>{e(rc["living"])}</p></section>'
            + f'<h2 class="st">Visiting {e(rname)}</h2><section class="prose"><p>{e(rc["visiting"])}</p></section>'
            + f'<h2 class="st">Top Cities in {e(rname)}</h2><nav class="dir-list">{cities_grid}</nav>'
            + f'<h2 class="st">All Cities in {e(rname)} ({len(sorted_cities)} total)</h2>'
            + f'<table class="tbl"><tr><th>City</th><th>County</th><th>Population (2020)</th></tr>{all_rows}</table>'
            + '<p class="back"><a href="../index.html">&larr; All Washington Regions</a></p></div></main>'
            + footer('../../'))


def regions_index(all_cities):
    path = '/regions/'
    desc = ("Explore Washington's 7 regions: Seattle Metro, the North Sound, the Olympic Peninsula, Southwest, Central, Eastern and "
            "Southeast Washington, with city and travel guides.")
    region_cards = ''
    for rname, rslug2 in REGION_SLUGS.items():
        rc = REGION_CONTENT[rname]
        city_count = sum(1 for c in all_cities if big_region(c) == rname)
        ra, rb, _ = REGION_THEME[rname]
        region_cards += (f'<a href="{rslug2}/index.html" style="display:block;text-decoration:none;color:inherit;border-top-color:{rb}" class="card">'
                         f'<h3>{e(rname)}</h3>'
                         f'<p style="font-size:.92rem;color:var(--tx);margin:6px 0">{e(rc["desc"][:150])}&hellip;</p>'
                         f'<p style="font-size:.84rem;color:var(--mu);margin-top:6px">{city_count} cities &middot; {len(REGION_COUNTIES[rname])} counties</p>'
                         f'</a>')
    ld_obj = {'@context':'https://schema.org','@type':'ItemList','name':'Washington Regions',
              'url':f'{BASE_URL}{path}','numberOfItems':7}
    return (head("Washington's 7 Regions: Puget Sound, Peninsula, East & More", desc, path, 'website', None, ld(ld_obj), '../',
                 'Washington regions, Seattle Metro, Puget Sound, North Sound, Olympic Peninsula, Southwest Washington, Central Washington, Eastern Washington, Southeast Washington, Washington cities by region')
            + header('../') + ticker_html('regions') + alert_banner()
            + f'<div class="hero region-hero">{state_silhouette()}<div class="wrap"><h1>Washington&rsquo;s Seven Regions</h1>'
            + '<p>Explore Washington by region &mdash; cities, counties, living guides, and things to do in each part of the state.</p></div></div>'
            + f'<main><div class="wrap"><nav class="crumbs"><a href="../index.html">Home</a> &rsaquo; Washington Regions</nav>'
            + '<h2 class="st">Explore Washington by Region</h2>'
            + f'<div class="cards" style="margin-top:24px">{region_cards}</div>'
            + '</div></main>' + footer('../'))


def state_page():
    path = '/washington/'
    title = 'Washington State Guide: Facts, Population, Cities & Counties'
    desc = ('Guide to the State of Washington: population, capital, state symbols, geography, history and economy, '
            'plus all 281 cities and towns, 39 counties and 7 regions.')
    kw = ('Washington, State of Washington, Washington facts, Washington population, Washington cities, Washington counties, Washington regions, '
          'moving to Washington, visiting Washington, Washington state symbols, Washington history')
    facts_rows = ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in STATE_FACTS)
    ld_obj = {'@context':'https://schema.org','@type':'State','name':'Washington','url':f'{BASE_URL}{path}'}
    bread = {'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[
        {'@type':'ListItem','position':1,'name':'Home','item':f'{BASE_URL}/'},
        {'@type':'ListItem','position':2,'name':'Washington State Facts','item':f'{BASE_URL}{path}'}]}
    region_links = ''.join(
        f'<a href="/regions/{REGION_SLUGS[r]}/index.html" style="display:block;text-decoration:none;color:inherit" class="card">'
        f'<h3>{e(r)}</h3><p style="font-size:.92rem;color:var(--tx);margin:4px 0">{e(REGION_CONTENT[r]["desc"][:120])}&hellip;</p></a>'
        for r in REGION_SLUGS)
    return (head(title, desc, path, 'article', None, ld(ld_obj)+ld(bread), '../', kw)
            + header('../') + ticker_html('washington') + alert_banner()
            + f'<div class="or-hero">{state_silhouette(cls="or-sil or-sil-lg")}<div class="wrap">'
            + '<p class="or-eyebrow">&#10022; The Evergreen State &middot; Est. 1889 &#10022;</p>'
            + '<h1>Washington State Guide: Facts, Population &amp; Geography</h1>'
            + '<p class="or-sub">Explore 281 cities and towns, 39 counties and 7 regions &mdash; population data, schools, utilities, attractions &amp; more</p>'
            + '<p class="or-cta"><a class="btn-cta" href="/cities/">Explore Washington &rarr;</a><a class="btn-ghost" href="/regions/">Browse the 7 regions</a></p>'
            + '</div></div>'
            + f'<main><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Home</a> &rsaquo; Washington State Facts</nav>'
            + f'<h2 class="st">Quick Facts</h2><section class="facts"><table>{facts_rows}</table></section>'
            + '''<h2 class="st">About Washington</h2><section class="prose">
<p>Washington is a U.S. state in the Pacific Northwest, bordered by the Canadian province of British Columbia to the north, Idaho to the east, Oregon to the south and the Pacific Ocean to the west. It is the only state named after a U.S. president, and it became the 42nd state on November&nbsp;11, 1889.</p>
<p>The Cascade Range divides the state in two. West of the mountains, a mild, wet marine climate supports dense evergreen forests, Puget Sound&rsquo;s inland sea and the rainforests of the <a href="/regions/olympic-peninsula/index.html">Olympic Peninsula</a>. East of the Cascades, the land is drier and sunnier, with orchards, vineyards, the wheat fields of the Palouse and the scablands carved by Ice Age floods. Five major volcanoes &mdash; Mount Baker, Glacier Peak, Mount Rainier, Mount St.&nbsp;Helens and Mount Adams &mdash; rise along the Cascade crest, and the Columbia River crosses the state before forming most of the border with Oregon.</p>
<p>Most Washingtonians live in the <a href="/regions/seattle-metro/index.html">Seattle Metro</a> area around Puget Sound. Seattle is the largest city, followed by Spokane, Tacoma, Vancouver and Bellevue; Olympia, at the southern tip of Puget Sound, is the capital.</p>
</section>'''
            + '''<h2 class="st">Economy</h2><section class="prose">
<p>Washington&rsquo;s economy spans technology, aerospace, trade, agriculture and tourism. Microsoft and Amazon are headquartered in the Seattle area, Boeing builds commercial jets at plants in Everett and Renton, and the ports of Seattle and Tacoma handle a large share of the nation&rsquo;s trade with Asia. Health care, research (including Pacific Northwest National Laboratory in Richland) and the military, with Joint Base Lewis-McChord and naval bases around Puget Sound, are also major employers.</p>
<p>East of the Cascades, agriculture leads: Washington grows more apples than any other state, along with most of the nation&rsquo;s hops and large crops of cherries, pears, potatoes and wheat, and it is the country&rsquo;s second-largest wine producer. Hydroelectric dams on the Columbia, including Grand Coulee, supply much of the state&rsquo;s electricity.</p>
<p>Washington has <strong>no income tax on wages</strong>, although a 9.9% tax on personal income above $1 million, signed in 2026, is scheduled to start in 2028 and is being challenged in court. The state relies heavily on sales tax (6.5% statewide, plus local sales taxes) and the business and occupation (B&amp;O) tax, and it taxes large long-term capital gains.</p>
</section>'''
            + '''<h2 class="st">History</h2><section class="prose">
<p>People have lived in what is now Washington for thousands of years, and today 29 federally recognized tribes are based in the state, including the Yakama, Colville, Puyallup, Tulalip, Muckleshoot, Spokane and Makah. Spanish and British navigators explored the coast in the late 1700s, and Lewis and Clark followed the Columbia River to the Pacific in 1805.</p>
<p>The fur trade, centered on the Hudson&rsquo;s Bay Company post at Fort Vancouver, brought the first permanent non-Native settlements. Washington Territory was created in 1853 with Olympia as its capital, and statehood followed in 1889. Railroads, timber, mining and the Klondike Gold Rush fueled growth; in the 20th century, Columbia River dams, Boeing, wartime shipyards and the Hanford site, and later the technology industry, shaped the modern state.</p>
</section>'''
            + f'<h2 class="st">Explore Washington by Region</h2><div class="cards">{region_links}</div>'
            + '<h2 class="st">Explore by County or City</h2><div class="cards">'
            + '<a href="/counties/index.html" class="card" style="display:block;text-decoration:none;color:inherit"><h3>All 39 Counties</h3><p style="font-size:.92rem;color:var(--tx)">Population, history, and cities for every Washington county.</p></a>'
            + '<a href="/cities/index.html" class="card" style="display:block;text-decoration:none;color:inherit"><h3>All 281 Cities &amp; Towns A&ndash;Z</h3><p style="font-size:.92rem;color:var(--tx)">Directory of every incorporated city and town in Washington with facts and moving guides.</p></a>'
            + '</div>'
            + '<p class="back"><a href="../index.html">&larr; Home</a></p></div></main>'
            + footer('../'))


_SCHEME = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//|#|\?)', re.I)


def clean_links(content, page_file):
    """Rewrite relative internal href/src values to root-relative canonical URLs.
    '../../cities/bend/index.html' on /cities/sisters/ becomes '/cities/bend/' (the URL used in the canonical tag
    and sitemap), so internal links never point at the duplicate .../index.html address."""
    rel = os.path.relpath(os.path.dirname(os.path.abspath(page_file)), os.path.abspath(OUT)).replace(os.sep, '/')
    base = posixpath.normpath('/' + ('' if rel == '.' else rel))

    def fix(m):
        attr, url = m.group(1), m.group(2)
        if not url or _SCHEME.match(url):
            return m.group(0)
        frag = ''
        for sep in ('#', '?'):
            if sep in url:
                url, rest = url.split(sep, 1); frag = sep + rest + frag; break
        trailing = url.endswith('/')
        path = url if url.startswith('/') else posixpath.normpath(posixpath.join(base.rstrip('/') + '/', url))
        path = '/' + path.lstrip('/')   # never emit '//x' (a protocol-relative URL pointing at another host)
        if path.endswith('/index.html'):
            path = path[:-len('index.html')]
        elif path == 'index.html':
            path = '/'
        elif trailing and not path.endswith('/'):
            path += '/'
        return f'{attr}="{path}{frag}"'
    return re.sub(r'\b(href|src)="([^"]*)"', fix, content)


LASTMOD_JSON = 'data/lastmod.json'


def page_lastmod(urls):
    """Real <lastmod> per URL: the date a page's HTML last changed (content hash tracked in data/lastmod.json),
    not the build date. Search engines ignore lastmod when every URL claims to change on every build."""
    store = json.load(open(LASTMOD_JSON, encoding='utf-8')) if os.path.exists(LASTMOD_JSON) else {}
    out = {}
    for u in urls:
        f = f'{OUT}{u}index.html'
        if not os.path.exists(f):
            out[u] = store.get(u, [None, TODAY])[1]; continue
        h = hashlib.sha1(open(f, 'rb').read()).hexdigest()
        old = store.get(u)
        if old and old[0] == h:
            out[u] = old[1]
        else:
            if old is None:   # first run: seed from git history so unchanged pages keep their real date
                try:
                    d = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', f], capture_output=True, text=True).stdout.strip()
                    status = subprocess.run(['git', 'status', '--porcelain', '--', f], capture_output=True, text=True).stdout.strip()
                except Exception:
                    d, status = '', 'x'
                out[u] = d if d and not status else TODAY
            else:
                out[u] = TODAY
            store[u] = [h, out[u]]
    with open(LASTMOD_JSON, 'w', encoding='utf-8') as fh:
        json.dump(store, fh, indent=0, sort_keys=True)
    return out


def write(path, content):
    for bad, good in LINK_FIXES.items():
        content = content.replace(f'href="{bad}"', f'href="{good}"').replace(f'href="{e(bad)}"', f'href="{e(good)}"')
    if path.endswith('.html'):
        content = clean_links(content, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: f.write(content)


def main():
    cities = json.load(open('data/cities.json', encoding='utf-8'))
    counties = json.load(open('data/counties.json', encoding='utf-8'))
    custom = json.load(open('custom_city_content.json', encoding='utf-8')) if os.path.exists('custom_city_content.json') else {}
    for c in cities: c['counties'] = [x.strip() for x in c['county'].split(',')]
    for c in cities + counties:
        if c.get('website'): c['website'] = fix_url(c['website'])
    for k in counties:
        k['pop2020'] = county_census_2020(k)
        if k.get('seat') == 'Saint Helens': k['seat'] = 'St. Helens'   # match the city's name in cities.json
    for k in counties: COUNTY_SITES[k['name']] = k.get('website', ''); COUNTY_SEATS[k['name']] = k.get('seat', '')
    CITY_SLUGS.update(slug(c['name']) for c in cities)
    load_city_posts()
    import static_pages as sp   # hand-written guide pages; data blocks inside them are filled below
    write(f'{OUT}/index.html', sp.home_page(cities, counties))
    write(f'{OUT}/counties/index.html', sp.counties_shell(counties))
    write(f'{OUT}/moving-to-washington/index.html', sp.moving_page(cities))
    write(f'{OUT}/visit-washington/index.html', sp.visit_page(cities))
    for c in cities:
        write(f'{OUT}/cities/{slug(c["name"])}/index.html', city_page(c, cities, custom))
    for k in counties:
        write(f'{OUT}/counties/{slug(k["name"])}/index.html', county_page(k, cities))
    write(f'{OUT}/cities/index.html', cities_index(cities))
    update_counties_index(counties, cities)
    write(f'{OUT}/washington-zip-codes/index.html', zip_page(cities))
    write(f'{OUT}/washington-area-codes/index.html', area_code_page(cities))
    write(f'{OUT}/about/index.html', simple_page('/about/', 'About Washington Information | Independent Washington Guide', 'About Washington Information: an independent, free guide to every Washington city and county, with moving and visiting guides.', 'About Washington Information', 'An independent, plain-language guide to the State of Washington.', ABOUT, 'AboutPage'))
    write(f'{OUT}/contact/index.html', simple_page('/contact/', 'Contact Washington Information', 'Contact Washington Information with questions, corrections or suggestions about any Washington city, county, region or blog guide. We read every message we receive.', 'Contact Us', 'Questions, corrections and suggestions are always welcome.', CONTACT, 'ContactPage'))
    write(f'{OUT}/privacy/index.html', simple_page('/privacy/', 'Privacy Policy | Washington Information', 'Privacy policy for washingtoninformation.com: what information we collect, how cookies and analytics are used, and your choices.', 'Privacy Policy', 'How washingtoninformation.com handles information.', PRIVACY))
    write(f'{OUT}/advertise/index.html', simple_page('/advertise/', 'Advertise on Washington Information | Banner Ads & Sponsorships', 'Advertise on Washington Information and reach people moving to or visiting Washington. Banner sizes, placement options and how to get started.', 'Advertise with Us', 'Reach people planning their Washington move or trip.', ADVERTISE))
    # Build 7 region pages + regions index
    for c in cities: c['counties'] = [x.strip() for x in c['county'].split(',')]  # ensure counties set (idempotent)
    by_region = {}
    for c in cities:
        r = big_region(c)
        by_region.setdefault(r, []).append(c)
    for rname in REGION_SLUGS:
        rslug2 = REGION_SLUGS[rname]
        write(f'{OUT}/regions/{rslug2}/index.html', region_page(rname, by_region.get(rname, [])))
    write(f'{OUT}/regions/index.html', regions_index(cities))
    home_regions = ('<section class="alt"><div class="wrap"><h2 class="section-title">Explore Washington&rsquo;s 7 Regions</h2>'
                    '<p class="section-sub">From Puget Sound and the Pacific coast to the Palouse, every region has its own guide with cities, travel ideas and living information.</p><div class="city-grid">'
                    + ''.join(f'<a class="city-card" href="/regions/{REGION_SLUGS[r]}/"><h3>{e(r)}</h3><p>{len(by_region.get(r, []))} cities &bull; '
                              f'{e(REGION_CONTENT[r]["desc"][:110].rsplit(" ", 1)[0].rstrip(",;:"))}&hellip;</p></a>' for r in REGION_SLUGS)
                    + '</div></div></section>')
    replace_block(f'{OUT}/index.html', 'home-regions', home_regions)
    # Washington state facts page
    write(f'{OUT}/washington/index.html', state_page())
    # Sitemap
    urls = ['/', '/washington/', '/regions/', '/cities/', '/counties/', '/washington-zip-codes/', '/washington-area-codes/', '/moving-to-washington/', '/visit-washington/', '/about/', '/contact/', '/privacy/', '/advertise/']
    urls += [f'/regions/{REGION_SLUGS[r]}/' for r in REGION_SLUGS]
    urls += [f'/counties/{slug(k["name"])}/' for k in counties] + [f'/cities/{slug(c["name"])}/' for c in cities]
    if os.path.exists('data/blog_articles.json'):   # statewide blog (built by build_blog_index.py)
        urls += ['/blog/'] + [f'/blog/{a["slug"]}/' for a in json.load(open('data/blog_articles.json', encoding='utf-8'))]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    lastmod = page_lastmod(urls)
    sm += '\n'.join(f'  <url><loc>{BASE_URL}{u}</loc><lastmod>{lastmod[u]}</lastmod></url>' for u in urls) + '\n</urlset>\n'
    write(f'{OUT}/sitemap.xml', sm)
    write(f'{OUT}/robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n')
    print(f'Built {len(cities)} city pages, {len(counties)} county pages, {len(REGION_SLUGS)} region pages + index, Washington page, cities index, about/contact/privacy, sitemap ({len(urls)} URLs).')


if __name__ == '__main__':
    main()
