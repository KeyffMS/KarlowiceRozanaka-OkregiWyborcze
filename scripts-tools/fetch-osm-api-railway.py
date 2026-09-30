#!/usr/bin/env python3
import requests, json, xml.etree.ElementTree as ET
from pathlib import Path

bbox="17.052,51.137,17.086,51.145"
url=f"https://api.openstreetmap.org/api/0.6/map?bbox={bbox}"
r=requests.get(url,timeout=120,headers={"User-Agent":"KarlowiceRozanaka-OkregiWyborcze/1.0"})
r.raise_for_status()
root=ET.fromstring(r.content)
nodes={}
for n in root.findall("node"):
    nodes[int(n.attrib["id"])]=(float(n.attrib["lon"]),float(n.attrib["lat"]))
features=[]
for w in root.findall("way"):
    tags={t.attrib["k"]:t.attrib["v"] for t in w.findall("tag")}
    if tags.get("railway")!="rail":
        continue
    coords=[]
    for nd in w.findall("nd"):
        ref=int(nd.attrib["ref"])
        if ref in nodes:
            coords.append(list(nodes[ref]))
    if len(coords)>=2:
        features.append({
            "type":"Feature",
            "properties":{"osm_id":int(w.attrib["id"]),**tags},
            "geometry":{"type":"LineString","coordinates":coords}
        })
out=Path("data-gis")
out.mkdir(exist_ok=True)
(out/"osm-api-railway-tracks.geojson").write_text(
    json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False,indent=2)+"\n",
    encoding="utf-8"
)
print("features",len(features))
