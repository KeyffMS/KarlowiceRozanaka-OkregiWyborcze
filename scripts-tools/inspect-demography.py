#!/usr/bin/env python3
import requests,zipfile,io,os
url="https://geoportal.wroclaw.pl/www/pliki/dem-rejurb-rejstat-shp.zip"
r=requests.get(url,timeout=120)
print(r.status_code,len(r.content),r.headers.get("content-type"))
r.raise_for_status()
z=zipfile.ZipFile(io.BytesIO(r.content))
for n in z.namelist():
    print(n)
