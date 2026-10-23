"""Make a printable page: a map with the N nearest elevator buildings numbered,
and a numbered address list (English + Simplified Chinese headings).

    python build/nearest_pdf.py [count] [out.html]

Writes an HTML page; build/html_to_pdf.js turns it into a PDF.
"""
import html
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "nearest.html"

data = json.loads((ROOT / "app/buildings.json").read_text())
base = json.loads((ROOT / "app/basemap.json").read_text())
rest = data["restaurant"]
picks = sorted((b for b in data["buildings"] if b["elev"] == "likely"), key=lambda b: b["dist"])[:N]

# ---- projection: Web Mercator, fitted to the picks + restaurant ----
MW, MH = 760, 510  # map size in CSS px


def merc(lat, lon):
    s = math.sin(math.radians(lat))
    return lon / 360 + 0.5, 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)


pts = [merc(*b["c"]) for b in picks] + [merc(rest["lat"], rest["lon"])]
x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
scale = min(MW / ((x1 - x0) or 1e-6), MH / ((y1 - y0) or 1e-6)) * 0.82


def px(lat, lon):
    x, y = merc(lat, lon)
    return (x - cx) * scale + MW / 2, (y - cy) * scale + MH / 2


lat0, lon0 = base["origin"]
SC = base["scale"]


def decode(a):
    out, x, y = [], 0, 0
    for i in range(0, len(a), 2):
        x += a[i]
        y += a[i + 1]
        out.append(px(lat0 + y / SC, lon0 + x / SC))
    return out


def visible(ring):
    return any(-60 < x < MW + 60 and -60 < y < MH + 60 for x, y in ring)


def d_attr(ring, close):
    s = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in ring)
    return s + ("Z" if close else "")


svg = []
FILL = {"grass": "#dfeccf", "park": "#d3e7c0", "wood": "#c7dfb3", "pitch": "#c9e3b9", "water": "#b7d5ea", "building": "#e3ddd2"}
for k in ["grass", "park", "wood", "pitch", "water", "building"]:
    ds = []
    for g in base["layers"].get(k, []):
        rings = [decode(r) for r in g]
        if any(visible(r) for r in rings):
            ds.append(" ".join(d_attr(r, True) for r in rings))
    if ds:
        edge = ' stroke="#d2cabc" stroke-width="0.5"' if k == "building" else ""
        svg.append(f'<path d="{" ".join(ds)}" fill="{FILL[k]}" fill-rule="evenodd"{edge}/>')

for k, col, w, dash in [("stream", "#b7d5ea", 1.5, ""), ("rail", "#9a948a", 1.4, "5 4")]:
    ds = [d_attr(r, False) for r in (decode(g) for g in base["layers"].get(k, [])) if visible(r)]
    if ds:
        svg.append(f'<path d="{" ".join(ds)}" fill="none" stroke="{col}" stroke-width="{w}" stroke-dasharray="{dash}"/>')

ROAD_W = {"motorway": 7, "primary": 6, "secondary": 5.6, "tertiary": 5, "residential": 3.6, "busway": 2.4, "service": 2, "path": 0.9}
MAJOR = {"motorway", "primary", "secondary", "tertiary"}
ORDER = ["path", "service", "busway", "residential", "tertiary", "secondary", "primary", "motorway"]
roads = {cls: [r for r in (decode(g) for g in base["roads"].get(cls, [])) if visible(r)] for cls in ORDER}
casing, fill = [], []
for cls in ORDER:
    if not roads[cls]:
        continue
    d = " ".join(d_attr(r, False) for r in roads[cls])
    if cls == "path":
        fill.append(f'<path d="{d}" fill="none" stroke="#b1a897" stroke-width="0.9" stroke-dasharray="3 3"/>')
        continue
    casing.append(f'<path d="{d}" fill="none" stroke="{"#d4a94c" if cls in MAJOR else "#cfc7b8"}" stroke-width="{ROAD_W[cls] + 1.6}"/>')
    fill.append(f'<path d="{d}" fill="none" stroke="{"#f8d98a" if cls in MAJOR else "#ffffff"}" stroke-width="{ROAD_W[cls]}"/>')
svg.append('<g stroke-linecap="round" stroke-linejoin="round">' + "".join(casing + fill) + "</g>")

# highlighted buildings
for b in picks:
    d = " ".join(d_attr([px(lat, lon) for lat, lon in r], True) for r in b["poly"])
    svg.append(f'<path d="{d}" fill="#f2b632" stroke="#8a5a00" stroke-width="1.2" fill-rule="evenodd"/>')

# street names
labels = []
for x, y, a, ni, z in base["labels"]:
    if z > 15:
        continue
    lx, ly = px(lat0 + y / SC, lon0 + x / SC)
    if 30 < lx < MW - 30 and 14 < ly < MH - 14:
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" transform="rotate({a} {lx:.1f} {ly:.1f})" class="rl">{html.escape(base["names"][ni])}</text>')
svg.append("".join(labels))

# restaurant
rx, ry = px(rest["lat"], rest["lon"])
star = " ".join(
    f"{rx + (12 if i % 2 == 0 else 5) * math.sin(i * math.pi / 5):.1f},{ry - (12 if i % 2 == 0 else 5) * math.cos(i * math.pi / 5):.1f}"
    for i in range(10)
)
svg.append(f'<polygon points="{star}" fill="#c0262d" stroke="#fff" stroke-width="2" paint-order="stroke"/>')
svg.append(f'<text x="{rx + 15:.1f}" y="{ry + 4:.1f}" class="rest">Restaurant 餐厅</text>')

# numbered pins, nudged apart so none overlap
R = 11
anchors = [px(*b["c"]) for b in picks]
pos = [list(p) for p in anchors]
for _ in range(400):
    moved = False
    for i in range(len(pos)):
        for j in range(i + 1, len(pos)):
            dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
            dist = math.hypot(dx, dy)
            if dist < 2 * R + 6:
                if dist < 1e-3:
                    dx, dy, dist = 1, 0, 1
                push = (2 * R + 6 - dist) / 2 + 0.3
                pos[i][0] -= dx / dist * push
                pos[i][1] -= dy / dist * push
                pos[j][0] += dx / dist * push
                pos[j][1] += dy / dist * push
                moved = True
        # keep clear of the restaurant star
        dx, dy = pos[i][0] - rx, pos[i][1] - ry
        dist = math.hypot(dx, dy) or 1
        if dist < R + 16:
            pos[i][0] += dx / dist * (R + 16 - dist)
            pos[i][1] += dy / dist * (R + 16 - dist)
            moved = True
    if not moved:
        break
for n, ((ax, ay), (x, y)) in enumerate(zip(anchors, pos), 1):
    if math.hypot(x - ax, y - ay) > 2:
        svg.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#1d2a44" stroke-width="1.4"/>')
for n, (x, y) in enumerate(pos, 1):
    svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{R}" fill="#1d2a44" stroke="#fff" stroke-width="2"/>'
               f'<text x="{x:.1f}" y="{y + 4.3:.1f}" class="pin">{n}</text>')

# scale bar (500 m)
m_per_px = 40075016.686 * math.cos(math.radians(rest["lat"])) / scale
bar = 500 / m_per_px
svg.append(f'<g transform="translate(16 {MH - 22})"><rect x="-6" y="-14" width="{bar + 56:.0f}" height="26" rx="4" fill="#fff" opacity=".85"/>'
           f'<path d="M0,0 H{bar:.1f}" stroke="#333" stroke-width="3"/><path d="M0,-5 V5 M{bar:.1f},-5 V5" stroke="#333" stroke-width="1.5"/>'
           f'<text x="{bar + 6:.1f}" y="4" class="sb">500 m</text></g>')
# north arrow
svg.append(f'<g transform="translate({MW - 28} 34)"><circle r="16" fill="#fff" opacity=".85"/><path d="M0,-11 L6,6 L0,2 L-6,6Z" fill="#333"/><text y="-17" class="sb" text-anchor="middle">N</text></g>')

# ---- address list ----
rows = []
for n, b in enumerate(picks, 1):
    addr = f'{"/".join(b["num"])} {b["street"]}'.strip()
    rows.append(
        f"<tr><td class='n'><span>{n}</span></td><td class='a'>{html.escape(addr)}</td>"
        f"<td>{html.escape(b['name'] or '—')}</td><td class='r'>{b['floors'] or '?'}</td>"
        f"<td class='r'>~{b['units']}</td><td class='r'>{b['dist'] / 1000:.1f} km</td></tr>"
    )

page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Nearest {N} elevator buildings</title>
<style>
@page {{ size: letter; margin: 0.45in 0.5in; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "DejaVu Sans", "WenQuanYi Zen Hei", sans-serif; color: #1d2230; font-size: 10.5pt; }}
h1 {{ font-size: 14pt; margin: 0 0 2px; }}
.sub {{ color: #5b6170; font-size: 9pt; margin-bottom: 8px; }}
.map {{ border: 1px solid #c9c2b4; border-radius: 6px; overflow: hidden; width: 100%; }}
svg {{ display: block; width: 100%; height: auto; background: #f4f1ea; }}
.rl {{ font-size: 8.5px; font-weight: 600; fill: #555; stroke: #fff; stroke-width: 2.6px; paint-order: stroke; text-anchor: middle; dominant-baseline: middle; }}
.rest {{ font-size: 11px; font-weight: 700; fill: #c0262d; stroke: #fff; stroke-width: 3px; paint-order: stroke; }}
.pin {{ font-size: 12px; font-weight: 700; fill: #fff; text-anchor: middle; }}
.sb {{ font-size: 10px; fill: #333; }}
.legend {{ display: flex; gap: 16px; font-size: 8.5pt; color: #444; margin: 5px 2px 10px; flex-wrap: wrap; }}
.legend i {{ display: inline-block; width: 12px; height: 12px; vertical-align: -2px; margin-right: 4px; border-radius: 2px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
th {{ text-align: left; font-size: 8.5pt; color: #5b6170; font-weight: 700; border-bottom: 1.5px solid #1d2a44; padding: 4px 6px; }}
td {{ padding: 3.5px 6px; border-bottom: 1px solid #e3ded4; }}
tr {{ break-inside: avoid; }}
td.n span {{ display: inline-block; width: 20px; height: 20px; border-radius: 50%; background: #1d2a44; color: #fff; text-align: center; line-height: 20px; font-weight: 700; font-size: 9pt; }}
td.a {{ font-weight: 700; }}
.r {{ text-align: right; white-space: nowrap; }}
.foot {{ font-size: 8pt; color: #6a6f7c; margin-top: 8px; }}
</style></head><body>
<h1>Nearest {N} apartment buildings with elevators · 最近的{N}栋有电梯公寓</h1>
<div class="sub">From 261 Centrepointe Dr, Ottawa · 从餐厅出发 · {date.today():%Y-%m-%d}</div>
<div class="map"><svg viewBox="0 0 {MW} {MH}" xmlns="http://www.w3.org/2000/svg">{"".join(svg)}</svg></div>
<div class="legend"><span><i style="background:#c0262d;clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)"></i>Restaurant 餐厅</span>
<span><i style="background:#1d2a44;border-radius:50%"></i>Building number 楼号</span>
<span><i style="background:#f2b632;border:1px solid #8a5a00"></i>Target building 目标楼</span></div>
<table><thead><tr><th>#</th><th>Address 地址</th><th>Building name 楼名</th><th class="r">Floors 楼层</th><th class="r">Units 户数</th><th class="r">Distance 距离</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<div class="foot">Elevators are estimated from building height in OpenStreetMap; check at the door. Distance is a straight line from the restaurant; unit counts are rough estimates.<br>
电梯根据楼层高度估算，请到门口确认。距离为到餐厅的直线距离；户数为大约估计。</div>
</body></html>"""
OUT.write_text(page)
print("wrote", OUT, len(picks), "buildings")
