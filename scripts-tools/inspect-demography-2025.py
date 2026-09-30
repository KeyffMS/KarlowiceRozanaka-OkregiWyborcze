#!/usr/bin/env python3
import requests,zipfile,io,tempfile,os
import geopandas as gpd
url="https://geoportal.wroclaw.pl/www/pliki/dem-rejurb-rejstat-shp.zip"
r=requests.get(url,timeout=120); r.raise_for_status()
with tempfile.TemporaryDirectory() as td:
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(td)
    root=os.path.join(td,"dem-rejurb-rejstat-shp")
    for name in sorted(os.listdir(root)):
        if "20251231.shp" in name:
            p=os.path.join(root,name)
            g=gpd.read_file(p)
            print("FILE",name,"CRS",g.crs,"ROWS",len(g))
            print("COLUMNS",list(g.columns))
            print(g.drop(columns="geometry").head(5).to_dict("records"))
