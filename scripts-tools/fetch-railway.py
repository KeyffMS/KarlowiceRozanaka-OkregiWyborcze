#!/usr/bin/env python3
import json, requests
from pathlib import Path

BASE="https://gis.um.wroc.pl/portal_srv/rest/services/podklad_mocny_odniesienie/MapServer"
BBOX="17.00,51.12,17.09,51.16"
OUT=Path("data-gis")
OUT.mkdir(exist_ok=True)

def fetch(layer, name):
    url=f"{BASE}/{layer}/query"
    params={
        "where":"1=1",
        "geometry":BBOX,
        "geometryType":"esriGeometryEnvelope",
        "inSR":4326,
        "spatialRel":"esriSpatialRelIntersects",
        "outFields":"*",
        "returnGeometry":"true",
        "outSR":4326,
        "f":"geojson",
        "resultRecordCount":2000
    }
    r=requests.get(url,params=params,timeout=90)
    r.raise_for_status()
    data=r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(name, len(data.get("features",[])))

fetch(12,"railway-main-lines.geojson")
fetch(13,"railway-tracks-detail.geojson")
fetch(14,"railway-tracks-overview.geojson")
