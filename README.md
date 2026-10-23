# Centrepointe Flyer Map

A map for restaurant staff handing out flyers around 261 Centrepointe Dr, Ottawa. It highlights the apartment
buildings within 3 km that have elevators, with delivery details (floors, unit estimate, distance, building
manager, team notes), and tracks which buildings got flyers this round. English and Simplified Chinese.

- Website: https://studykeepyell.github.io/centrepointe-flyer-map/ (served from `docs/` by GitHub Pages)
- Staff share progress through a private team link (`…/#team=CODE`). The code is not in this repo.

## How it is built

| Path | What it is |
| --- | --- |
| `app/flyer-map.html` | The whole app: page, styles and script. Also published as a Claude artifact. |
| `app/buildings.json` | Apartment buildings with floors, elevator estimate, address, unit estimate. |
| `app/basemap.json` | Streets, parks, water and building outlines, drawn by the app on canvas tiles. |
| `build/fetch.py` | Downloads OpenStreetMap data around the restaurant (Overpass API). |
| `build/process.py` | Turns that download into `app/buildings.json` and `app/basemap.json`. |
| `build/site.py` | Builds the website into `docs/`, adding `backend.js` for team sync. |
| `build/site-backend.js` | Team sync on the website: Firebase Cloud Firestore under `teams/<code>/`. |
| `build/firestore.rules` | Firestore security rules (paste into the Firebase console, Firestore > Rules). |
| `build/firebase-config.json` | Firebase web config (public identifiers, not secrets). |

Refresh the map data, then rebuild and publish:

```
python build/fetch.py
python build/process.py
python build/site.py
git add -A && git commit -m "Refresh map data" && git push
```

Elevators are estimated: no public list of Ottawa elevators exists, so 5+ storeys counts as "likely",
4 storeys or unknown counts as "check at the door", and staff corrections in the app override the estimate.

Map data © OpenStreetMap contributors (ODbL). Leaflet 1.9.4 (BSD-2-Clause).
