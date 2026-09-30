#!/usr/bin/env python3
import io,json,tempfile,zipfile
from pathlib import Path
import requests, geopandas as gpd
from shapely import make_valid

ROOT=Path(__file__).resolve().parents[1]
CUSTOM=ROOT/"analysis-v6"/"okregi-v6.geojson"
ADDR=ROOT/"data-2027-propozycja-miasta"/"generated-2027-propozycja-miasta"/"adresy-dopasowane-2027-propozycja-miasta.geojson"
BOUND=ROOT/"geojson-2027-propozycja-miasta"/"karlowice-rozanka-granica-osiedla-rekonstrukcja-2027-propozycja-miasta.geojson"
OUT=ROOT/"analysis-v6"/"o1-kromera-dlugosza-audit.json"
URL="https://geoportal.wroclaw.pl/www/pliki/dem-rejurb-rejstat-shp.zip"
TOTAL=29252

custom=gpd.read_file(CUSTOM).to_crs(2177)
addr=gpd.read_file(ADDR).to_crs(2177)
bound=gpd.read_file(BOUND).to_crs(2177)
nb=make_valid(bound.geometry.iloc[0])
o1=make_valid(custom[custom.district==1].geometry.iloc[0])

r=requests.get(URL,timeout=180); r.raise_for_status()
with tempfile.TemporaryDirectory() as td:
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(td)
    dem=gpd.read_file(Path(td)/"dem-rejurb-rejstat-shp"/"REJSTAT_20251231.shp").to_crs(2177)

# spatial join addresses to census regions
aj=gpd.sjoin(addr,dem[["REJON","SUMA","geometry"]],predicate="within",how="left")
target=aj[aj["street"].isin(["Marcina Kromera","Jana Długosza"])]

regions=[]
for rid in sorted(target.REJON.dropna().unique()):
    reg=dem[dem.REJON==rid].iloc[0]
    rg=make_valid(reg.geometry)
    nbpart=rg.intersection(nb)
    if nbpart.is_empty: continue
    o1part=rg.intersection(o1)
    pop=float(reg.SUMA)
    area_share_o1=(o1part.area/rg.area) if rg.area else 0
    area_share_nb=(nbpart.area/rg.area) if rg.area else 0
    ta=target[target.REJON==rid]
    all_a=aj[aj.REJON==rid]
    # custom district counts by point
    counts={}
    for d,row in custom.set_index("district").iterrows():
        counts[int(d)]=int(all_a.geometry.within(row.geometry).sum())
    regions.append({
        "REJON":str(rid),
        "SUMA_2025":pop,
        "area_share_in_neighborhood":area_share_nb,
        "area_share_in_O1":area_share_o1,
        "area_weight_population_O1":pop*area_share_o1,
        "kromera_dlugosza_points":int(len(ta)),
        "all_proposal_address_points":int(len(all_a)),
        "custom_address_counts":counts,
        "target_addresses":ta[["street","number"]].astype(str).to_dict("records"),
    })

# all-region estimates for all custom districts
area_raw={d:0.0 for d in range(1,6)}
majority_raw={d:0.0 for d in range(1,6)}
for _,reg in dem.iterrows():
    rg=make_valid(reg.geometry)
    nbpart=rg.intersection(nb)
    if nbpart.is_empty or rg.area<=0: continue
    pop=float(reg.SUMA)*(nbpart.area/rg.area)
    overlaps={}
    for d,row in custom.set_index("district").iterrows():
        overlaps[int(d)]=nbpart.intersection(row.geometry).area
        area_raw[int(d)] += float(reg.SUMA)*(nbpart.intersection(row.geometry).area/rg.area)
    best=max(overlaps,key=overlaps.get)
    majority_raw[best]+=pop

def scale(vals):
    f=TOTAL/sum(vals.values())
    return {d:vals[d]*f for d in vals}

payload={
 "target_address_counts":{
   "Marcina Kromera":int((target.street=="Marcina Kromera").sum()),
   "Jana Długosza":int((target.street=="Jana Długosza").sum()),
 },
 "target_regions":regions,
 "area_proportional_scaled_to_2026_total":scale(area_raw),
 "majority_region_scaled_to_2026_total":scale(majority_raw),
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(payload,ensure_ascii=False,indent=2))
