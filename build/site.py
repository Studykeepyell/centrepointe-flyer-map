"""Build the standalone website (served by GitHub Pages) into docs/.

Run:  python build/site.py
It wraps app/flyer-map.html in a full HTML document and copies the data files next to it.
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
app, site = root / "app", root / "docs"
site.mkdir(exist_ok=True)

ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Crect width='32' height='32' rx='7' fill='%2318201C'/%3E"
        "%3Crect x='7' y='8' width='18' height='17' rx='3' fill='%23FFE04A'/%3E"
        "%3Ctext x='16' y='21.5' font-family='Arial' font-weight='700' font-size='11' text-anchor='middle' fill='%2318201C'%3E14%3C/text%3E%3C/svg%3E")

HEAD = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="Apartment buildings with elevators near 261 Centrepointe Dr, Ottawa, for flyer delivery.">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#181E1A" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Flyer Map">
<link rel="icon" href="{ICON}">
<script src="backend.js"></script>
<style>:root{{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}
body{{margin:0}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
</head>
<body>
"""

html = (app / "flyer-map.html").read_text(encoding="utf-8")
(site / "index.html").write_text(HEAD + html + "\n</body>\n</html>\n", encoding="utf-8")
for f in ("leaflet.css", "buildings.json", "basemap.json"):
    shutil.copy2(app / f, site / f)

# team sync: inject the Firebase web config (public identifiers, not secrets) if it exists
import json
backend = (root / "build/site-backend.js").read_text(encoding="utf-8")
cfg_file = root / "build/firebase-config.json"
if cfg_file.exists():
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    backend = backend.replace("const FIREBASE_CONFIG = null; /* @config */",
                              "const FIREBASE_CONFIG = " + json.dumps(cfg) + ";")
    print("team sync: on, project", cfg.get("projectId"))
else:
    print("team sync: off (no build/firebase-config.json)")
(site / "backend.js").write_text(backend, encoding="utf-8")
shutil.copy2(root / "build/firestore.rules", site / "firestore.rules")
(site / ".nojekyll").write_text("", encoding="utf-8")
print("docs/ ready:", sorted(p.name for p in site.iterdir()))
