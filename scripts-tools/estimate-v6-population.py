#!/usr/bin/env python3
from __future__ import annotations
import io, json, os, tempfile, zipfile
from pathlib import Path
import requests
import geopandas as gpd
from shapely import make_valid

ROOT=Path(__file__).resolve().parents[1]
CUSTOM=ROOT/"analysis-v6"/"okregi-v6.geojson"
ADDR=ROOT/"data-2027-propozycja-miasta"/"generated-2027-propozycja-miasta"/"adresy-dopasowane-2027-propozycja-miasta.geojson"
BOUND=ROOT/"geojson-2027-propozycja-miasta"/"karlowice-rozanka-granica-osiedla-rekonstrukcja-2027-propozycja-miasta.geojson"
OUT=ROOT/"analysis-v6"/"population-estimate.json"

OFFICIAL_2026_TOTAL=29252
OFFICIAL_CITY_DISTRICTS={1:5824,2:3663,3:4767,4:8110,5:6888}
URL="https://geoportal.wroclaw.pl/www/pliki/dem-rejurb-rejstat-shp.zip"

custom=gpd.read_file(CUSTOM).to_crs(2177)
addresses=gpd.read_file(ADDR).to_crs(2177)
boundary=gpd.read_file(BOUND).to_crs(2177)
nb=make_valid(boundary.geometry.iloc[0])

# Assign each official-proposal address point to custom district.
join=gpd.sjoin(addresses,custom[["district","geometry"]],predicate="within",how="left")
if join["district_right"].isna().any():
    # Covers boundary points using a tiny tolerance.
    miss=join[join["district_right"].isna()].copy()
    for idx,row in miss.iterrows():
        p=row.geometry
        hits=custom[custom.geometry.buffer(0.15).covers(p)]
        if len(hits):
            join.loc[idx,"district_right"]=int(hits.iloc[0]["district"])

# Address transfer-matrix estimate based directly on official 2026 proposed district totals.
matrix={}
addr_weight_est={d:0.0 for d in range(1,6)}
for src in range(1,6):
    rows=join[join["district_left"]==src]
    counts=rows["district_right"].value_counts().to_dict()
    denom=sum(counts.values())
    matrix[src]={d:int(counts.get(d,0)) for d in range(1,6)}
    for d in range(1,6):
        addr_weight_est[d]+=OFFICIAL_CITY_DISTRICTS[src]*(counts.get(d,0)/denom)

# Download latest official 2025 census-block demographics.
r=requests.get(URL,timeout=180)
r.raise_for_status()
with tempfile.TemporaryDirectory() as td:
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(td)
    shp=Path(td)/"dem-rejurb-rejstat-shp"/"REJSTAT_20251231.shp"
    dem=gpd.read_file(shp).to_crs(2177)

# Restrict statistical regions to the osiedle.
# Population within a region crossing the osiedle boundary is area-weighted.
raw={d:0.0 for d in range(1,6)}
region_records=[]
for _,reg in dem.iterrows():
    geom=make_valid(reg.geometry)
    inter_nb=geom.intersection(nb)
    if inter_nb.is_empty or geom.area<=0:
        continue
    pop_nb=float(reg["SUMA"])*(inter_nb.area/geom.area)
    if pop_nb<=0:
        continue

    # Distribution inside a census region:
    # - when proposal-address points are present, use their counts by custom district;
    # - otherwise fall back to intersection area.
    pts=join[join.geometry.within(geom)]
    counts=pts["district_right"].dropna().astype(int).value_counts().to_dict()
    if counts:
        denom=sum(counts.values())
        shares={d:counts.get(d,0)/denom for d in range(1,6)}
        method="address_points"
    else:
        areas={}
        for d,row in custom.set_index("district").iterrows():
            a=inter_nb.intersection(row.geometry).area
            areas[int(d)]=a
        denom=sum(areas.values())
        shares={d:(areas[d]/denom if denom else 0.0) for d in range(1,6)}
        method="area"

    for d in range(1,6):
        raw[d]+=pop_nb*shares[d]
    region_records.append({
        "rejon":str(reg["REJON"]),
        "population_2025":float(reg["SUMA"]),
        "population_inside_neighborhood_est":pop_nb,
        "method":method,
        "shares":shares,
    })

raw_total=sum(raw.values())
scale=OFFICIAL_2026_TOTAL/raw_total
scaled={d:raw[d]*scale for d in range(1,6)}

# Blend the two independent estimates:
# 70% census-region method, 30% address-transfer method.
blend={d:0.7*scaled[d]+0.3*addr_weight_est[d] for d in range(1,6)}
# Normalize exactly to official 2026 total.
bf=OFFICIAL_2026_TOTAL/sum(blend.values())
blend={d:blend[d]*bf for d in range(1,6)}

payload={
    "methodology":{
        "official_total_date":"2026-06-30",
        "official_total":OFFICIAL_2026_TOTAL,
        "official_city_proposal_district_counts":OFFICIAL_CITY_DISTRICTS,
        "demography_source":"SIP Wroclaw REJSTAT_20251231.shp, permanent registrations at 2025-12-31",
        "method_a":"2025 census blocks clipped to neighborhood; split by counts of official proposal residential address points, fallback to area; scaled to official 2026 neighborhood total",
        "method_b":"official 2026 city proposal district totals redistributed according to address-point transfer matrix into custom v6",
        "combined":"70% method_a + 30% method_b, normalized to 29252",
    },
    "address_transfer_matrix":matrix,
    "method_a_2025_scaled_to_2026":{str(d):scaled[d] for d in range(1,6)},
    "method_b_address_transfer":{str(d):addr_weight_est[d] for d in range(1,6)},
    "combined_estimate":{str(d):blend[d] for d in range(1,6)},
    "combined_rounded_100":{str(d):round(blend[d]/100)*100 for d in range(1,6)},
    "sum_combined":sum(blend.values()),
    "raw_2025_total_inside_neighborhood_est":raw_total,
    "scale_2025_to_official_2026_total":scale,
    "statistical_regions_used":len(region_records),
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
