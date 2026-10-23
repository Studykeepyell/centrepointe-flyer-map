"""Turn the raw OpenStreetMap downloads into the two data files the app loads.

Run after fetch.py:   python build/process.py
Writes:  app/buildings.json  (apartment buildings + elevator estimate)
         app/basemap.json    (roads, parks, water, building outlines, street labels)
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "app"
OUT.mkdir(exist_ok=True)

LAT, LON = 45.33916, -75.77170  # restaurant, 261 Centrepointe Dr
MAX_DIST = 3000                  # metres from the restaurant
KX = 111320 * math.cos(math.radians(LAT))  # metres per degree of longitude here
KY = 111132                                 # metres per degree of latitude


def xy(lat, lon):
    """Local metres east/north of the restaurant."""
    return (lon - LON) * KX, (lat - LAT) * KY


def dist_m(lat, lon):
    x, y = xy(lat, lon)
    return math.hypot(x, y)


def ring_area(r):
    s = 0.0
    for (a_lat, a_lon), (b_lat, b_lon) in zip(r, r[1:] + r[:1]):
        ax, ay = xy(a_lat, a_lon)
        bx, by = xy(b_lat, b_lon)
        s += ax * by - bx * ay
    return abs(s) / 2


def centroid(r):
    # area-weighted centroid in local metres, falls back to vertex mean
    a = cx = cy = 0.0
    pts = [xy(*p) for p in r]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if abs(a) < 1e-6:
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
    else:
        mx, my = cx / (3 * a), cy / (3 * a)
    return LAT + my / KY, LON + mx / KX


def point_in_ring(lat, lon, r):
    inside = False
    j = len(r) - 1
    for i in range(len(r)):
        yi, xi = r[i]
        yj, xj = r[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
            inside = not inside
        j = i
    return inside


def join_rings(segments):
    """Assemble closed rings from multipolygon member ways."""
    segs = [s[:] for s in segments if len(s) >= 2]
    rings = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while cur[0] != cur[-1] and changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == cur[-1]:
                    cur += s[1:]
                elif s[-1] == cur[-1]:
                    cur += s[::-1][1:]
                elif s[-1] == cur[0]:
                    cur = s[:-1] + cur
                elif s[0] == cur[0]:
                    cur = s[::-1][:-1] + cur
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if len(cur) >= 4:
            rings.append(cur)
    return rings


def geom_rings(e):
    """Return (outer_rings, inner_rings) as lists of (lat, lon) lists."""
    if e["type"] == "way":
        g = [(p["lat"], p["lon"]) for p in e.get("geometry", [])]
        return ([g] if len(g) >= 4 else []), []
    outer, inner = [], []
    for m in e.get("members", []):
        if m.get("type") != "way" or not m.get("geometry"):
            continue
        g = [(p["lat"], p["lon"]) for p in m["geometry"] if p]
        (inner if m.get("role") == "inner" else outer).append(g)
    return join_rings(outer), join_rings(inner)


def num(v):
    try:
        return float(str(v).split(";")[0].strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- buildings
raw = json.loads((HERE / "raw_buildings.json").read_text(encoding="utf-8"))["elements"]
addr_nodes = [e for e in raw if e["type"] == "node" and "addr:housenumber" in e.get("tags", {})]

RES = {"apartments", "residential", "condominium", "dormitory", "retirement_home", "nursing_home"}
SENIOR = {"group_home", "assisted_living"}

buildings = []
for e in raw:
    if e["type"] not in ("way", "relation"):
        continue
    t = e.get("tags", {})
    if t.get("building") not in RES:
        continue
    # long-term care homes are not apartments; leave them off the flyer map
    if t.get("social_facility") == "nursing_home" or t.get("building") == "nursing_home":
        continue
    outer, inner = geom_rings(e)
    if not outer:
        continue
    main = max(outer, key=ring_area)
    area = sum(ring_area(r) for r in outer) - sum(ring_area(r) for r in inner)
    if area < 40:  # sheds, condo offices
        continue
    clat, clon = centroid(main)
    d = dist_m(clat, clon)
    if d > MAX_DIST:
        continue

    # address: tags first, else address points inside the footprint
    numbers, street, postcode = [], t.get("addr:street"), t.get("addr:postcode")
    if t.get("addr:housenumber"):
        numbers = [t["addr:housenumber"]]
    inside = [n for n in addr_nodes if point_in_ring(n["lat"], n["lon"], main)]
    for n in inside:
        nt = n["tags"]
        street = street or nt.get("addr:street")
        postcode = postcode or nt.get("addr:postcode")
        if not t.get("addr:housenumber") and nt.get("addr:street") == street:
            numbers.append(nt["addr:housenumber"])
    numbers = sorted(set(numbers), key=lambda s: (len(s), s))

    floors = num(t.get("building:levels"))
    if floors is not None:
        floors = int(round(floors))
    kind = "apartment"
    if t.get("social_facility") in SENIOR or t.get("building") in ("retirement_home", "nursing_home"):
        kind = "seniors"
    elif t.get("building") == "dormitory":
        kind = "student"

    # Elevator estimate. No building here carries an OSM elevator tag, so this
    # is a rule of thumb that staff confirm or correct in the app.
    if kind == "seniors" and floors is not None and floors >= 2:
        elev, why = "likely", f"Seniors' residence, {floors} storeys. These nearly always have elevators."
    elif floors is not None and floors >= 5:
        elev, why = "likely", f"{floors} storeys. Buildings this tall almost always have an elevator."
    elif floors == 4 and area >= 350:
        elev, why = "unsure", "4 storeys. Some 4-storey buildings are walk-ups, so check at the door."
    elif floors is None and area >= 350:
        elev, why = "unsure", "Floor count is not on the map. Check at the door."
    elif floors is None:
        elev, why = "no", "Small building, most likely a walk-up or townhouse block."
    else:
        elev, why = "no", f"{floors} storeys, a walk-up or townhouse block."

    units = None
    if floors and elev != "no":
        units = max(10, int(round(area * floors * 0.8 / 70 / 10.0)) * 10)

    bid = ("w" if e["type"] == "way" else "r") + str(e["id"])
    buildings.append({
        "id": bid,
        "name": t.get("name") or t.get("addr:housename") or "",
        "num": numbers,
        "street": street or "",
        "postcode": postcode or "",
        "floors": floors,
        "kind": kind,
        "elev": elev,
        "why": why,
        "units": units,
        "area": round(area),
        "dist": round(d),
        "c": [round(clat, 6), round(clon, 6)],
        "poly": [[[round(a, 6), round(b, 6)] for a, b in r] for r in outer],
        "holes": [[[round(a, 6), round(b, 6)] for a, b in r] for r in inner],
        "manager": t.get("operator") or "",
        "phone": t.get("phone") or t.get("contact:phone") or "",
        "web": t.get("website") or t.get("contact:website") or "",
        "osm": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
    })

buildings.sort(key=lambda b: b["dist"])
(OUT / "buildings.json").write_text(
    json.dumps({"restaurant": {"lat": LAT, "lon": LON, "address": "261 Centrepointe Dr, Ottawa, ON K2G 6E8"},
                "built": "2026-10-23", "source": "OpenStreetMap contributors (ODbL)",
                "buildings": buildings}, separators=(",", ":"), ensure_ascii=False),
    encoding="utf-8")

from collections import Counter
print("buildings:", len(buildings), Counter(b["elev"] for b in buildings))
print("  likely within 1/2/3 km:", [sum(1 for b in buildings if b["elev"] == "likely" and b["dist"] <= k) for k in (1000, 2000, 3000)])

# ---------------------------------------------------------------- base map
base = json.loads((HERE / "raw_basemap.json").read_text(encoding="utf-8"))["elements"]
S = 100000  # 1e-5 degree units (~1 m)


def enc(coords):
    """Delta-encode [(lat, lon), ...] into a flat int list [x0, y0, dx, dy, ...]."""
    out, px, py = [], 0, 0
    for lat, lon in coords:
        x, y = round((lon - LON) * S), round((lat - LAT) * S)
        if out and x == px and y == py:
            continue
        out += [x - px, y - py]
        px, py = x, y
    return out


ROAD = {
    "motorway": "motorway", "motorway_link": "motorway", "trunk": "motorway", "trunk_link": "motorway",
    "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary",
    "tertiary": "tertiary", "tertiary_link": "tertiary",
    "residential": "residential", "unclassified": "residential", "living_street": "residential",
    "service": "service", "busway": "busway",
    "pedestrian": "path", "footway": "path", "path": "path", "cycleway": "path",
}
AREA = {
    ("natural", "water"): "water",
    ("leisure", "park"): "park", ("leisure", "nature_reserve"): "park", ("leisure", "golf_course"): "park",
    ("landuse", "recreation_ground"): "park",
    ("landuse", "grass"): "grass", ("landuse", "meadow"): "grass", ("landuse", "cemetery"): "grass",
    ("natural", "wood"): "wood", ("landuse", "forest"): "wood",
    ("leisure", "pitch"): "pitch", ("leisure", "playground"): "pitch",
}

layers = {k: [] for k in ["water", "park", "grass", "wood", "pitch", "building", "stream", "rail"]}
roads = {k: [] for k in ["path", "service", "busway", "residential", "tertiary", "secondary", "primary", "motorway"]}
named = []  # (class, name, coords) for street labels

for e in base:
    t = e.get("tags", {})
    if "building" in t:
        o, i = geom_rings(e)
        for r in o:
            layers["building"].append([enc(r)])
        continue
    if "highway" in t:
        cls = ROAD.get(t["highway"])
        if not cls or t.get("footway") in ("sidewalk", "crossing") or t.get("area") == "yes":
            continue
        g = [(p["lat"], p["lon"]) for p in e.get("geometry", [])]
        if len(g) < 2:
            continue
        roads[cls].append(enc(g))
        if t.get("name") and cls in ("motorway", "primary", "secondary", "tertiary", "residential"):
            named.append((cls, t["name"], g))
        continue
    if "waterway" in t:
        g = [(p["lat"], p["lon"]) for p in e.get("geometry", [])]
        if len(g) >= 2:
            layers["stream"].append(enc(g))
        continue
    if "railway" in t:
        g = [(p["lat"], p["lon"]) for p in e.get("geometry", [])]
        if len(g) >= 2:
            layers["rail"].append(enc(g))
        continue
    key = next((AREA[(k, t[k])] for k in ("natural", "leisure", "landuse") if (k, t.get(k)) in AREA), None)
    if key:
        o, i = geom_rings(e)
        if o:
            layers[key].append([enc(r) for r in o + i])

# ---- street labels: pick label spots along named roads, thinned per zoom
RANK = {"motorway": 0, "primary": 1, "secondary": 2, "tertiary": 3, "residential": 4}
MINZ = {"motorway": 13, "primary": 13, "secondary": 14, "tertiary": 14, "residential": 15}
SAME = {13: 2600, 14: 1500, 15: 800, 16: 420, 17: 220}   # metres between labels of one street
ANY = {13: 700, 14: 380, 15: 190, 16: 95, 17: 50}         # metres between any two labels

cands = []
for cls, name, g in named:
    pts = [xy(*p) for p in g]
    seglen = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    L = sum(seglen)
    if L < 70:
        continue
    marks = [L / 2] if L < 500 else [s for s in range(150, int(L) - 100, 250)]
    for m in marks:
        acc = 0.0
        for (a, b), sl in zip(zip(pts, pts[1:]), seglen):
            if acc + sl >= m and sl > 0:
                f = (m - acc) / sl
                px, py = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
                ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                if ang > 90:
                    ang -= 180
                if ang < -90:
                    ang += 180
                cands.append((RANK[cls], -L, px, py, ang, name, cls))
                break
            acc += sl
cands.sort()

names, name_idx, labels, placed = [], {}, [], []  # placed: (x, y, name, minzoom)
for z in (13, 14, 15, 16, 17):
    for c in cands:
        rank, negL, px, py, ang, name, cls = c
        if MINZ[cls] > z or c in [p[4] for p in placed]:
            continue
        ok = True
        for (qx, qy, qn, qz, _c) in placed:
            dd = math.hypot(px - qx, py - qy)
            if dd < ANY[z] or (qn == name and dd < SAME[z]):
                ok = False
                break
        if ok:
            placed.append((px, py, name, z, c))
for px, py, name, z, c in placed:
    if name not in name_idx:
        name_idx[name] = len(names)
        names.append(name)
    lat, lon = LAT + py / KY, LON + px / KX
    labels.append([round((lon - LON) * S), round((lat - LAT) * S), round(-c[4]), name_idx[name], z])

basemap = {"origin": [LAT, LON], "scale": S, "layers": layers, "roads": roads,
           "labels": labels, "names": names}
(OUT / "basemap.json").write_text(json.dumps(basemap, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print("basemap:", {k: len(v) for k, v in layers.items()}, {k: len(v) for k, v in roads.items()}, "labels", len(labels))
print("sizes:", {p.name: p.stat().st_size for p in OUT.glob("*.json")})
