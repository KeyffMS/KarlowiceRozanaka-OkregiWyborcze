#!/usr/bin/env python3
import requests, json
from pathlib import Path

bbox="51.12,17.00,51.16,17.09"
q=f'''[out:json][timeout:60];
way["railway"="rail"]({bbox});
out geom;'''
urls=[
  "https://overpass-api.de/api/interpreter",
  "https://overpass.kumi.systems/api/interpreter",
]
data=None
for url in urls:
    try:
        r=requests.post(url,data={"data":q},timeout=90)
        r.raise_for_status()
        data=r.json()
        break
    except Exception as e:
        print("failed",url,e)
if data is None:
    raise RuntimeError("Overpass unavailable")
features=[]
for el in data.get("elements",[]):
    geom=el.get("geometry")
    if not geom: continue
    coords=[[p["lon"],p["lat"]] for p in geom]
    features.append({
      "type":"Feature",
      "properties":{"osm_type":"way","osm_id":el["id"],**el.get("tags",{})},
      "geometry":{"type":"LineString","coordinates":coords}
    })
out=Path("data-gis")
out.mkdir(exist_ok=True)
(out/"osm-railway-tracks.geojson").write_text(
    json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False,indent=2)+"\n",
    encoding="utf-8"
)
print("features",len(features))
