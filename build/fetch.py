"""Download OpenStreetMap data around the restaurant (Overpass API).

Run:  python build/fetch.py   (writes build/raw_*.json)
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
LAT, LON = 45.33916, -75.77170  # 261 Centrepointe Dr, Ottawa
R = 3200  # metres

QUERIES = {
    # Residential buildings + elevator nodes + address points
    "buildings": f"""
[out:json][timeout:180];
(
  way["building"~"^(apartments|residential|condominium|dormitory|yes|retirement_home|nursing_home)$"](around:{R},{LAT},{LON});
  relation["building"~"^(apartments|residential|condominium|dormitory|yes|retirement_home)$"](around:{R},{LAT},{LON});
);
out geom;
node["highway"="elevator"](around:{R},{LAT},{LON});
out;
node["addr:housenumber"](around:{R},{LAT},{LON});
out;
""",
    # Base map: roads, paths, water, parks, all other building outlines
    "basemap": f"""
[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|pedestrian|footway|path|cycleway|busway)$"](around:{R + 600},{LAT},{LON});
  way["natural"="water"](around:{R + 600},{LAT},{LON});
  relation["natural"="water"](around:{R + 600},{LAT},{LON});
  way["waterway"~"^(river|stream|canal)$"](around:{R + 600},{LAT},{LON});
  way["leisure"~"^(park|golf_course|pitch|playground|nature_reserve)$"](around:{R + 600},{LAT},{LON});
  relation["leisure"~"^(park|golf_course|nature_reserve)$"](around:{R + 600},{LAT},{LON});
  way["landuse"~"^(grass|forest|meadow|recreation_ground|cemetery)$"](around:{R + 600},{LAT},{LON});
  way["natural"="wood"](around:{R + 600},{LAT},{LON});
  way["building"](around:{R + 600},{LAT},{LON});
  way["railway"~"^(rail|light_rail)$"](around:{R + 600},{LAT},{LON});
);
out geom;
""",
}

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def run(name, q):
    body = urllib.parse.urlencode({"data": q}).encode()
    for ep in ENDPOINTS:
        try:
            req = urllib.request.Request(ep, data=body, headers={"User-Agent": "restaurant-leaflet-map/1.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                data = json.loads(r.read())
            out = HERE / f"raw_{name}.json"
            out.write_text(json.dumps(data), encoding="utf-8")
            print(name, ep, len(data.get("elements", [])), "elements")
            return
        except Exception as e:  # try the next mirror
            print(name, ep, "failed:", e, file=sys.stderr)
            time.sleep(3)
    sys.exit(f"{name}: all endpoints failed")


if __name__ == "__main__":
    for n in sys.argv[1:] or QUERIES:
        run(n, QUERIES[n])
