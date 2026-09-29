#!/usr/bin/env python3
from __future__ import annotations

import json, math, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection, MultiPoint, shape, mapping
from shapely.ops import transform, unary_union, voronoi_diagram
from shapely.strtree import STRtree

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parents[1]
SOURCE_RULES=ROOT/"data-2027-propozycja-miasta"/"source-2027-propozycja-miasta"/"okregi-wyborcze-2027-propozycja-miasta.json"
OUT=ROOT/"wariant-spojny-propozycja"
GEO=OUT/"geojson"
DATA=OUT/"data"
PDF=OUT/"pdf"
TMP=OUT/"tmp"

BOUNDARY_URL="https://gis.um.wroc.pl/portal_srv/rest/services/search/MapServer/12/query"
ADDRESS_URL="https://gis.um.wroc.pl/portal_srv/rest/services/emuia_wroclaw/MapServer/0/query"
PARCEL_URL="https://gis.um.wroc.pl/portal_srv/rest/services/Dzia%C5%82ki/MapServer/0/query"
STREETS_URL="https://gis.um.wroc.pl/portal_srv/rest/services/search/MapServer/2/query"

COLORS={1:"#D73027",2:"#4575B4",3:"#1A9850",4:"#762A83",5:"#F28E2B"}
SESSION=requests.Session()
SESSION.headers["User-Agent"]="KarlowiceRozanaka-OkregiWyborcze/variant-spojny"

PREFIX={"ul","ulica","al","aleja","pl","plac"}
TITLES={"bp","biskup","biskupa","gen","general","generala","marsz","marszalek","marszalka","ks","ksiadz","ksiedza"}

def asciify(s:str)->str:
    s=s.replace("ł","l").replace("Ł","L")
    s=unicodedata.normalize("NFKD",s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def norm_street(s:str|None)->str:
    if not s:return ""
    s=asciify(s).lower()
    s=re.sub(r"[^a-z0-9]+"," ",s).strip()
    toks=s.split()
    while toks and toks[0] in PREFIX:toks.pop(0)
    while toks and toks[0] in TITLES:toks.pop(0)
    return " ".join(toks)

def norm_num(s:str|None)->str:
    if s is None:return ""
    s=asciify(str(s)).upper().replace(" ","").replace("–","-").replace("—","-")
    return re.sub(r"^(\d+)-(\d+)$",r"\1/\2",s)

def lead_num(s:str|None):
    m=re.match(r"^(\d+)",norm_num(s))
    return int(m.group(1)) if m else None

def street_match(rule,actual):
    a,b=norm_street(actual),norm_street(rule)
    if a==b:return True
    at,bt=a.split(),b.split()
    return len(at)>=2 and len(bt)>=2 and (a.endswith(b) or b.endswith(a) or at[-2:]==bt[-2:])

def num_match(spec,n):
    typ=spec.get("type"); nn=lead_num(n); ns=norm_num(n)
    if typ=="all":return bool(ns)
    if typ=="exact":return ns in {norm_num(x) for x in spec.get("exact",[])}
    if typ=="range":return nn is not None and spec["min"]<=nn<=spec["max"]
    if typ=="range_parity":
        return nn is not None and spec["min"]<=nn<=spec["max"] and ((nn%2==0)==(spec["parity"]=="even"))
    if typ=="ranges_exact":
        return ns in {norm_num(x) for x in spec.get("exact",[])} or (nn is not None and any(a<=nn<=b for a,b in spec.get("ranges",[])))
    if typ=="compound":return any(num_match(c,n) for c in spec.get("clauses",[]))
    return False

def source_match(street,number,districts):
    hits=[]
    for d in districts:
        for r in d["rules"]:
            if street_match(r["street"],street) and num_match(r["numbers"],number):
                hits.append(int(d["district"]))
    u=sorted(set(hits))
    return u[0] if len(u)==1 else None

def variant_district(street,number):
    s=norm_street(street); n=lead_num(number); ns=norm_num(number)

    # split streets first
    if s.endswith("czajkowskiego") or s=="piotra czajkowskiego":
        return 3 if n==109 else 2
    if s.endswith("pola") or s=="wincentego pola":
        if n is None:return 2
        return 3 if ((n%2==0 and 50<=n<=70) or (n%2==1 and 65<=n<=77)) else 2
    if s.endswith("obornicka"):
        return 5 if (n is not None and n<=76) else 4
    if s.endswith("bezpieczna"):
        return 4 if (n is not None and n%2==1) else 5
    if "kasprowicza" in s:return 2
    if s=="rowerowa":return 2
    if "romanowskiego" in s:return 3

    d1={
      "aleksandra brucknera","brucknera","boleslawa krzywoustego","krzywoustego","bydgoska","galla anonima","galla",
      "gizycka","grudziadzka","jana dlugosza","dlugosza","juliana klaczki","klaczki","ketrzynska","laka mazurska",
      "macieja miechowity","miechowity","marcina kromera","kromera","poprzeczna","torunska",
      "zenona miriama przesmyckiego","przesmyckiego","artyleryjska","koszarowa","soltysowicka","sportowa",
      "stanislawa przybyszewskiego","przybyszewskiego"
    }
    d2={
      "adama asnyka","asnyka","adolfa dygasinskiego","dygasinskiego","artura oppmana","oppmana","bohdana zaleskiego","zaleskiego",
      "boleslawa lesmiana","lesmiana","ignacego krasickiego","krasickiego","filomatow","franciszka karpinskiego","karpinskiego",
      "jozefa wybickiego","wybickiego","gustawa danilowskiego","danilowskiego","ignacego chrzanowskiego","chrzanowskiego",
      "jana brzechwy","brzechwy","kazimierza przerwy tetmajera","przerwy tetmajera","kornela makuszynskiego","makuszynskiego",
      "kornela ujejskiego","ujejskiego","norberta bonczyka","bonczyka","leopolda staffa","staffa","ludwika nabielaka","nabielaka",
      "marii konopnickiej","konopnickiej","jozefa pilsudskiego","pilsudskiego","samuela bogumila lindego","lindego",
      "seweryna goszczynskiego","goszczynskiego","skwer obroncow helu","stanislawa grochowiaka","grochowiaka","stanislawa pietaka","pietaka",
      "tadeusza gajcego","gajcego","tadeusza boya zelenskiego","boya zelenskiego","tadeusza micinskiego","micinskiego",
      "tadeusza zelenaya","zelenaya","teofila lenartowicza","lenartowicza","waclawa berenta","berenta","waclawa gasiorowskiego","gasiorowskiego",
      "waclawa potockiego","potockiego","wladyslawa anczyca","anczyca","wladyslawa broniewskiego","broniewskiego","wladyslawa orkana","orkana",
      "wladyslawa syrokomli","syrokomli","wlodzimierza perzynskiego","perzynskiego","zawalna","zmigrodzka"
    }
    d3={
      "forteczna","henryka michala kamienskiego","kamienskiego","jutrosinska","kazimierza brodzinskiego","brodzinskiego",
      "krzysztofa kamila baczynskiego","baczynskiego","maurycego mochnackiego","mochnackiego","mieczyslawa romanowskiego","romanowskiego",
      "roberta kocha","kocha","torowa"
    }
    d4={"jarocinska","kepinska","ligocka","mlynarska","paprotna","weroniki kumko","kumko","wolowska","zaulek rogozinski"}
    d5={"balkanska","baltycka","bulgarska","chorwacka","czeska","jugoslowianska","lutycka","luzycka","macedonska","morawska",
        "na polance","obodrzycka","osobowicka","piesza","serbska","slowacka","teodora parnickiego","parnickiego"}

    for d,sett in [(1,d1),(2,d2),(3,d3),(4,d4),(5,d5)]:
        if s in sett or any(s.endswith(x) for x in sett if len(x)>6):return d
    return None

DISPLAY={
1:["Artyleryjska","Brücknera Aleksandra, al. P 10-54","Bydgoska","Długosza Jana","Galla Anonima","Giżycka","Grudziądzka","Klaczki Juliana","Koszarowa","Kromera Marcina, al.","Krzywoustego Bolesława 1-109, 111","Kętrzyńska","Łąka Mazurska","Miechowity Macieja","Poprzeczna, al. 33/35, 33A","Przesmyckiego Zenona Miriama","Przybyszewskiego Stanisława","Sołtysowicka N 1-5A, P 2-12, 15-24","Sportowa","Toruńska"],
2:["Anczyca Władysława","Asnyka Adama","Berenta Wacława","Bonczyka Norberta, ks.","Boya-Żeleńskiego Tadeusza, al.","Broniewskiego Władysława","Brzechwy Jana","Chrzanowskiego Ignacego","Daniłowskiego Gustawa, pl.","Dygasińskiego Adolfa","Filomatów","Gajcego Tadeusza","Goszczyńskiego Seweryna","Grochowiaka Stanisława","Gąsiorowskiego Wacława","Karpińskiego Franciszka","Kasprowicza Jana, al. 1-112","Konopnickiej Marii","Krasickiego Ignacego, bp.","Leśmiana Bolesława","Lenartowicza Teofila","Lindego Samuela Bogumiła","Makuszyńskiego Kornela","Micińskiego Tadeusza","Nabielaka Ludwika","Oppmana Artura","Orkana Władysława","Perzyńskiego Włodzimierza","Piłsudskiego Józefa, pl. Marsz.","Piętaka Stanisława","Pola Wincentego N 1-63, P 2-48C","Potockiego Wacława","Przerwy-Tetmajera Kazimierza","Rowerowa","Skwer Obrońców Helu","Staffa Leopolda","Syrokomli Władysława","Ujejskiego Kornela","Wybickiego Józefa, gen.","Zaleskiego Bohdana","Zawalna","Zelenaya Tadeusza","Żmigrodzka 9-145"],
3:["Baczyńskiego Krzysztofa Kamila","Brodzińskiego Kazimierza","Czajkowskiego Piotra 109","Forteczna","Jutrosińska","Kamieńskiego Henryka Michała 3-184","Kocha Roberta","Mochnackiego Maurycego","Pola Wincentego P 50-70, N 65-77A","Romanowskiego Mieczysława","Torowa"],
4:["Bezpieczna N 3-91","Jarocińska 99","Kumko Weroniki","Kępińska","Ligocka","Młynarska","Obornicka 77-217","Paprotna 2-6","Wołowska","Zaułek Rogoziński"],
5:["Bałkańska","Bałtycka","Bezpieczna P 2-52","Bułgarska","Chorwacka","Czeska","Jugosłowiańska","Lutycka","Łużycka","Macedońska","Morawska","Na Polance","Obodrzycka","Obornicka 2-76F","Osobowicka 2-63","Parnickiego Teodora","Piesza","Serbska","Słowacka"]
}

def req_json(url,params):
    r=SESSION.get(url,params=params,timeout=120); r.raise_for_status(); j=r.json()
    if j.get("error"):raise RuntimeError(j["error"])
    return j

def query_geojson(url,params,page=2000):
    feats=[]; off=0
    while True:
        q=dict(params); q.update({"f":"geojson","resultOffset":off,"resultRecordCount":page,"returnGeometry":"true","outSR":4326})
        j=req_json(url,q); p=j.get("features",[]); feats+=p
        if len(p)<page:break
        off+=len(p)
    return {"type":"FeatureCollection","features":feats}

def poly(g):
    if g.is_empty:return MultiPolygon([])
    g=make_valid(g)
    if isinstance(g,(Polygon,MultiPolygon)):return g
    if isinstance(g,GeometryCollection):
        ps=[x for x in g.geoms if isinstance(x,(Polygon,MultiPolygon))]
        return unary_union(ps) if ps else MultiPolygon([])
    return g

def write_fc(path,features):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False),encoding="utf-8")

def feat(g,p):return {"type":"Feature","properties":p,"geometry":mapping(g)}

def wrap_text(text,font,size,width):
    words=text.split(); out=[]; cur=""
    for w in words:
        t=w if not cur else cur+" "+w
        if stringWidth(t,font,size)<=width:cur=t
        else:
            if cur:out.append(cur)
            cur=w
    if cur:out.append(cur)
    return out

def draw_list(c,items,x,y_top,width,bottom):
    k=3 if len(items)>24 else 2; gap=10; cw=(width-gap*(k-1))/k
    size=7.0 if len(items)>35 else 7.7; leading=size+2
    chunk=math.ceil(len(items)/k)
    for ci in range(k):
        col=items[ci*chunk:(ci+1)*chunk]; xx=x+ci*(cw+gap); yy=y_top
        for idx,item in enumerate(col):
            s=item+("," if idx<len(col)-1 else "")
            for line in wrap_text(s,"Doc",size,cw):
                if yy<bottom:break
                c.setFont("Doc",size); c.setFillColor(colors.HexColor("#1F2430")); c.drawString(xx,yy,line); yy-=leading
            yy-=1.5

def plot_map(path,boundary,districts,streets,focus=None):
    fig,ax=plt.subplots(figsize=(13,6.7),dpi=170)
    ax.set_aspect("equal"); ax.axis("off"); ax.set_facecolor("#eef1f5")
    # other districts light
    for d,g in districts.items():
        geoms=[g] if isinstance(g,Polygon) else list(g.geoms)
        for pg in geoms:
            xy=list(pg.exterior.coords)
            ax.add_patch(MplPolygon(xy,closed=True,facecolor=(COLORS[d] if focus in (None,d) else "#d9dee5"),
                                    edgecolor="white",linewidth=1.6,alpha=(0.48 if focus is None else (0.50 if d==focus else 0.40)),zorder=1))
    # official street grid - no labels
    for f in streets:
        try:g=shape(f["geometry"])
        except:continue
        klass=(f.get("properties",{}).get("KLASA") or "").lower()
        if "autostrada" in klass or "ekspres" in klass: lw=1.8
        elif "główna" in klass or "glowna" in klass: lw=1.45
        elif "zbiorcza" in klass: lw=1.15
        elif "lokalna" in klass: lw=0.82
        elif "dojazdowa" in klass: lw=0.62
        else: lw=0.72
        gs=[g] if g.geom_type=="LineString" else list(getattr(g,"geoms",[]))
        for line in gs:
            xs,ys=line.xy
            ax.plot(xs,ys,color="#68717b",linewidth=lw,alpha=0.76,zorder=3)
    bg=boundary.bounds
    if focus is None:
        minx,miny,maxx,maxy=bg
    else:
        minx,miny,maxx,maxy=districts[focus].bounds
    dx=maxx-minx; dy=maxy-miny
    pad=0.10 if focus else 0.04
    ax.set_xlim(minx-dx*pad,maxx+dx*pad); ax.set_ylim(miny-dy*pad,maxy+dy*pad)
    fig.tight_layout(pad=0)
    fig.savefig(path,bbox_inches="tight",pad_inches=0.02,facecolor="#eef1f5")
    plt.close(fig)

def main():
    for p in (GEO,DATA,PDF,TMP):p.mkdir(parents=True,exist_ok=True)
    rules=json.loads(SOURCE_RULES.read_text(encoding="utf-8"))
    source_d=rules["districts"]

    allb=query_geojson(BOUNDARY_URL,{"where":"1=1","outFields":"OBJECTID,NAZWAOSIEDLA"})
    bf=[f for f in allb["features"] if "karlowice" in norm_street(f["properties"].get("NAZWAOSIEDLA")) and "rozanka" in norm_street(f["properties"].get("NAZWAOSIEDLA"))]
    boundary=poly(shape(bf[0]["geometry"])); minx,miny,maxx,maxy=boundary.bounds
    env=f"{minx},{miny},{maxx},{maxy}"

    afc=query_geojson(ADDRESS_URL,{"where":"1=1","outFields":"OBJECTID,NAZWA_ULICY,NUMER_PORZADKOWY,KOD_POCZTOWY","geometry":env,"geometryType":"esriGeometryEnvelope","inSR":4326,"spatialRel":"esriSpatialRelIntersects"})
    source_rows=[]; current=[]
    for f in afc["features"]:
        p=shape(f["geometry"])
        if not isinstance(p,Point) or not boundary.covers(p):continue
        current.append((f,p))
        st=f["properties"].get("NAZWA_ULICY"); no=f["properties"].get("NUMER_PORZADKOWY")
        sd=source_match(st,no,source_d)
        if sd is None:continue
        vd=variant_district(st,no)
        source_rows.append({"feature":f,"point":p,"street":st,"number":no,"source_district":sd,"district":vd})

    missing=[r for r in source_rows if r["district"] is None]
    if missing:
        raise RuntimeError("Variant misses source addresses: "+repr([(r["street"],r["number"]) for r in missing[:30]]))
    assert len(source_rows)>=3600

    pfc=query_geojson(PARCEL_URL,{"where":"1=1","outFields":"OBJECTID,ID_SWDE,NUMER","geometry":env,"geometryType":"esriGeometryEnvelope","inSR":4326,"spatialRel":"esriSpatialRelIntersects"})
    parcels=[]; pgeoms=[]
    for f in pfc["features"]:
        try:g=poly(shape(f["geometry"]).intersection(boundary))
        except:continue
        if g.is_empty:continue
        parcels.append((f,g)); pgeoms.append(g)

    tree=STRtree(pgeoms); byparcel=defaultdict(list)
    for r in source_rows:
        p=r["point"]; idxs=list(tree.query(p,predicate="intersects"))
        cov=[int(i) for i in idxs if pgeoms[int(i)].covers(p)]
        idx=min(cov,key=lambda i:pgeoms[i].area) if cov else int(tree.nearest(p))
        byparcel[idx].append(r)

    to2180=Transformer.from_crs(4326,2180,always_xy=True)
    to4326=Transformer.from_crs(2180,4326,always_xy=True)
    proj=lambda g:transform(to2180.transform,g); unproj=lambda g:transform(to4326.transform,g)

    seed_pts=[proj(r["point"]) for r in source_rows]; seed_ds=[r["district"] for r in source_rows]; seedtree=STRtree(seed_pts)
    parts={d:[] for d in range(1,6)}; conflicts=[]
    for idx,(pf,pg) in enumerate(parcels):
        rows=byparcel.get(idx,[])
        if rows:
            ds=set(r["district"] for r in rows)
            if len(ds)==1:
                parts[next(iter(ds))].append(pg); continue
            conflicts.append({"parcel":pf["properties"].get("ID_SWDE"),"districts":sorted(ds)})
            pm=proj(pg)
            sites=[]
            for r in rows:
                q=proj(r["point"]); sites.append((q,r["district"]))
            uniq={}
            for q,d in sites:uniq[(round(q.x,3),round(q.y,3))]=(q,d)
            vals=list(uniq.values())
            if len(vals)==1:parts[vals[0][1]].append(pg);continue
            vd=voronoi_diagram(MultiPoint([q for q,d in vals]),envelope=pm.envelope,edges=False)
            for cell in vd.geoms:
                cl=poly(cell.intersection(pm))
                if cl.is_empty:continue
                rp=cl.representative_point(); q,d=min(vals,key=lambda z:rp.distance(z[0]))
                parts[d].append(unproj(cl))
        else:
            rp=proj(pg.representative_point()); ni=int(seedtree.nearest(rp)); parts[seed_ds[ni]].append(pg)

    # Działki nie pokrywają dróg i części terenów publicznych. Uzupełniamy te obszary
    # najbliższym adresem-kotwicą, aby pięć okręgów pokrywało całe osiedle.
    parcel_union=poly(unary_union(pgeoms))
    leftovers=poly(boundary.difference(parcel_union))
    left_geoms=[]
    if isinstance(leftovers,Polygon): left_geoms=[leftovers]
    elif isinstance(leftovers,MultiPolygon): left_geoms=list(leftovers.geoms)
    else: left_geoms=[g for g in getattr(leftovers,"geoms",[]) if isinstance(g,Polygon)]
    for comp in left_geoms:
        rp=proj(comp.representative_point()); ni=int(seedtree.nearest(rp))
        parts[seed_ds[ni]].append(comp)

    districts={d:poly(unary_union(parts[d]).intersection(boundary)) for d in range(1,6)}

    # Oficjalne odcinki osi ulic z SIP Wrocławia. Nazwy pobieramy wyłącznie
    # technicznie; w PDF nie są renderowane.
    sfc=query_geojson(STREETS_URL,{"where":"1=1","outFields":"OBJECTID,KLASA,KATEGORIA,STATUS_KOD","geometry":env,"geometryType":"esriGeometryEnvelope","inSR":4326,"spatialRel":"esriSpatialRelIntersects"},page=1000)
    streets_all=[]
    for f in sfc["features"]:
        try:g=shape(f["geometry"]).intersection(boundary)
        except:continue
        if g.is_empty:continue
        f["geometry"]=mapping(g); streets_all.append(f)
    existing=[f for f in streets_all if "istniej" in str(f.get("properties",{}).get("STATUS_KOD","")).lower()]
    streets=existing if existing else streets_all

    # write actual GIS layers
    write_fc(GEO/"granica-osiedla.geojson",[feat(boundary,{"name":"Karłowice-Różanka","source":"SIP Wrocławia"})])
    write_fc(GEO/"siatka-ulic-geoportal.geojson",streets)
    combined=[]
    for d,g in districts.items():
        ff=feat(g,{"district":d,"variant":"wariant-spojny-propozycja","crs":"EPSG:4326"})
        write_fc(GEO/f"okreg-{d}.geojson",[ff]); combined.append(ff)
    write_fc(GEO/"okregi.geojson",combined)
    write_fc(GEO/"adresy-przypisane.geojson",[feat(r["point"],{"district":r["district"],"source_district":r["source_district"],"street":r["street"],"number":r["number"]}) for r in source_rows])

    # validation
    counts=Counter(r["district"] for r in source_rows)
    wrong=[r for r in source_rows if not districts[r["district"]].covers(r["point"])]
    union=poly(unary_union(list(districts.values())))
    area=proj(boundary).area; gap=proj(boundary.difference(union)).area
    overlap=max(0,sum(proj(g).area for g in districts.values())-proj(union).area)
    validation={
      "source_residential_addresses":len(source_rows),
      "variant_assigned_addresses":len(source_rows)-len(missing),
      "unassigned_source_addresses":len(missing),
      "addresses_outside_variant_polygon":len(wrong),
      "district_address_counts":dict(sorted(counts.items())),
      "street_features_geoportal":len(streets),
      "parcels":len(parcels),
      "parcel_conflicts":len(conflicts),
      "coverage_ratio":round((area-gap)/area,9),
      "gap_area_m2":round(gap,3),
      "overlap_area_m2":round(overlap,3),
      "street_source":STREETS_URL.rsplit("/query",1)[0],
      "street_layer":"SIP Wrocławia / search / Odcinki osi ulic (2), tylko STATUS_KOD=istniejąca",
      "notes":["Wykaz adresów wejściowych ograniczony do adresów rozpoznanych przez reguły propozycji miasta 2027.","Siatka ulic pochodzi z oficjalnej warstwy osi ulic SIP Wrocławia; na mapie nie renderuje się nazw."]
    }
    (DATA/"validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")

    # map images
    plot_map(TMP/"map-all.png",boundary,districts,streets,None)
    for d in range(1,6):plot_map(TMP/f"map-{d}.png",boundary,districts,streets,d)

    # PDF landscape
    reg="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; bold="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    pdfmetrics.registerFont(TTFont("Doc",reg)); pdfmetrics.registerFont(TTFont("Doc-Bold",bold))
    W,H=landscape(A4); outpdf=PDF/"Karlowice-Rozanka_wariant-spojny-propozycja.pdf"
    c=canvas.Canvas(str(outpdf),pagesize=(W,H))
    def hdr(title):
        c.setFillColor(colors.HexColor("#1F2430"));c.setFont("Doc-Bold",18);c.drawString(28,H-27,title)
        c.setStrokeColor(colors.HexColor("#D7DBE1"));c.line(28,H-36,W-28,H-36)
    def foot(p):
        c.setStrokeColor(colors.HexColor("#D7DBE1"));c.line(28,18,W-28,18);c.setFillColor(colors.HexColor("#5B6574"));c.setFont("Doc",6.2);c.drawRightString(W-28,8,f"strona {p}/6")
    def image(path,x,y,w,h):
        from PIL import Image
        im=Image.open(path);iw,ih=im.size;s=min(w/iw,h/ih);dw,dh=iw*s,ih*s;c.drawImage(ImageReader(str(path)),x+(w-dw)/2,y+(h-dh)/2,dw,dh,mask="auto")
    hdr("Karłowice-Różanka – propozycja podziału na 5 spójnych okręgów")
    image(TMP/"map-all.png",28,42,W-56,H-88);foot(1);c.showPage()
    for page,d in enumerate(range(1,6),2):
        hdr(f"Karłowice-Różanka – Okręg {d}")
        image(TMP/f"map-{d}.png",28,205,W-56,H-245)
        c.setFillColor(colors.HexColor(COLORS[d]));c.roundRect(28,169,W-56,22,5,stroke=0,fill=1);c.setFillColor(colors.white);c.setFont("Doc-Bold",9);c.drawString(38,176,f"Wykaz ulic i adresów – Okręg {d}")
        draw_list(c,DISPLAY[d],34,158,W-68,28);foot(page);c.showPage()
    c.save()

    print(json.dumps(validation,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
