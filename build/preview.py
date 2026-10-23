"""Wrap app/flyer-map.html in the publish skeleton for local testing -> app/_preview.html"""
from pathlib import Path
root = Path(__file__).resolve().parent.parent
SKEL = '<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
html = (root / "app/flyer-map.html").read_text(encoding="utf-8")
(root / "app/_preview.html").write_text(SKEL + html + "</body></html>", encoding="utf-8")
print("wrote app/_preview.html")
