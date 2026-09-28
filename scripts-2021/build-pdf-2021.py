#!/usr/bin/env python3
from __future__ import annotations

import json
from math import cos, radians
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "data-2021" / "source-2021" / "okregi-wyborcze-2021.json"
GEOJSON = ROOT / "geojson-2021" / "karlowice-rozanka-okregi-wyborcze-2021.geojson"
OUT_DIR = ROOT / "pdf-2021"
OUT = OUT_DIR / "Karlowice-Rozanka_okregi-wyborcze_2021.pdf"

W, H = A4
COLORS = {
    1: colors.HexColor("#D73027"),
    2: colors.HexColor("#4575B4"),
    3: colors.HexColor("#1A9850"),
    4: colors.HexColor("#762A83"),
    5: colors.HexColor("#F28E2B"),
}
MID = colors.HexColor("#D6D9DF")
DARK = colors.HexColor("#20242A")
MUTED = colors.HexColor("#5C6470")

def register_fonts():
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/lato/Lato-Regular.ttf", "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("Doc", regular))
            pdfmetrics.registerFont(TTFont("Doc-Bold", bold))
            return
    raise RuntimeError("No suitable Unicode font found")

def wrap_text(text, font, size, max_width):
    words=text.split()
    lines=[]
    cur=""
    for word in words:
        test=word if not cur else cur+" "+word
        if stringWidth(test,font,size)<=max_width:
            cur=test
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    return lines

def polygon_rings(feature):
    geom=feature["geometry"]
    if geom["type"]=="Polygon":
        polys=[geom["coordinates"]]
    else:
        polys=geom["coordinates"]
    for poly in polys:
        if poly and poly[0]:
            yield poly[0]

def format_numbers(street, spec):
    typ=spec.get("type")
    if typ=="all": return street
    if typ=="exact": return street+" "+ " i ".join(spec.get("exact",[]))
    if typ=="range": return f"{street} {spec['min']}-{spec['max']}"
    if typ=="range_parity":
        label="parzyste" if spec.get("parity")=="even" else "nieparzyste"
        return f"{street} - {label} {spec['min']}-{spec['max']}"
    if typ=="ranges_exact":
        ranges=[f"{a}-{b}" for a,b in spec.get("ranges",[])]
        vals=ranges+spec.get("exact",[])
        return street+" "+ " i ".join(vals)
    if typ=="compound":
        parts=[]
        for clause in spec.get("clauses",[]):
            ct=clause.get("type")
            if ct=="range_parity":
                label="parzyste" if clause.get("parity")=="even" else "nieparzyste"
                end=clause["max"]
                if street=="Sołtysowicka" and clause.get("parity")=="odd" and clause.get("min")==1 and clause.get("max")==5:
                    end="5A"
                parts.append(f"{label} {clause['min']}-{end}")
            elif ct=="range":
                parts.append(f"numery {clause['min']}-{clause['max']}")
        return street+" - "+", ".join(parts)
    return street

def main():
    register_fonts()
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    rules=json.loads(RULES.read_text(encoding="utf-8"))
    gj=json.loads(GEOJSON.read_text(encoding="utf-8"))
    features=sorted(gj["features"],key=lambda f:int(f["properties"]["district"]))
    by_no={int(f["properties"]["district"]):f for f in features}

    all_pts=[p for f in features for ring in polygon_rings(f) for p in ring]
    minx=min(p[0] for p in all_pts); maxx=max(p[0] for p in all_pts)
    miny=min(p[1] for p in all_pts); maxy=max(p[1] for p in all_pts)
    cy=(miny+maxy)/2
    xf=cos(radians(cy))

    def transform_for(rect):
        x0,y0,w,h=rect; pad=12
        gx0=minx*xf; gx1=maxx*xf
        scale=min((w-2*pad)/(gx1-gx0),(h-2*pad)/(maxy-miny))
        ox=x0+(w-(gx1-gx0)*scale)/2-gx0*scale
        oy=y0+(h-(maxy-miny)*scale)/2-miny*scale
        return lambda x,y:(ox+x*xf*scale,oy+y*scale)

    def draw_map(c,rect,highlight=None):
        x0,y0,w,h=rect
        c.setFillColor(colors.white); c.setStrokeColor(MID); c.roundRect(x0,y0,w,h,8,stroke=1,fill=1)
        tf=transform_for(rect)
        for f in features:
            no=int(f["properties"]["district"])
            fill=COLORS[no] if highlight is None or no==highlight else colors.HexColor("#E4E6EA")
            alpha=.48 if highlight is None else (.72 if no==highlight else .55)
            c.saveState(); c.setFillAlpha(alpha)
            for ring in polygon_rings(f):
                if len(ring)<3: continue
                p=c.beginPath(); px,py=tf(*ring[0]); p.moveTo(px,py)
                for point in ring[1:]:
                    px,py=tf(*point); p.lineTo(px,py)
                p.close()
                c.setFillColor(fill); c.setStrokeColor(colors.white if highlight is None else colors.HexColor("#8A9098"))
                c.setLineWidth(1.2 if highlight is None else (1.8 if no==highlight else .7))
                c.drawPath(p,stroke=1,fill=1)
            c.restoreState()
        label_features=features if highlight is None else [by_no[highlight]]
        for f in label_features:
            no=int(f["properties"]["district"])
            rp=shape(f["geometry"]).representative_point()
            lx,ly=tf(rp.x,rp.y)
            c.setFillColor(colors.white); c.setStrokeColor(DARK); c.circle(lx,ly,11,stroke=1,fill=1)
            c.setFillColor(DARK); c.setFont("Doc-Bold",9.5); c.drawCentredString(lx,ly-3.2,str(no))
        c.setFillColor(DARK); c.setFont("Doc-Bold",8); c.drawString(x0+w-29,y0+h-20,"N")
        c.line(x0+w-24,y0+h-34,x0+w-24,y0+h-22)

    def header(c,title,subtitle):
        c.setFillColor(DARK); c.setFont("Doc-Bold",20); c.drawString(36,H-46,title)
        c.setFillColor(COLORS[2]); c.setFont("Doc-Bold",10.5); c.drawRightString(W-36,H-44,"ROK 2021")
        c.setFillColor(MUTED); c.setFont("Doc",8.8); c.drawString(36,H-63,subtitle)
        c.setStrokeColor(MID); c.line(36,H-73,W-36,H-73)

    def footer(c,page):
        c.setStrokeColor(MID); c.line(36,31,W-36,31)
        c.setFillColor(MUTED); c.setFont("Doc",6.4)
        c.drawString(36,20,"Karłowice-Różanka - rekonstrukcja okręgów wyborczych na podstawie ogłoszenia z 2021 r.; nie jest urzędową mapą granic okręgów.")
        c.drawRightString(W-36,20,f"2021 | strona {page}/6")

    def draw_items(c,items,y_top):
        gap=16; col_w=(W-84-gap)/2; split=(len(items)+1)//2
        for ci,col in enumerate([items[:split],items[split:]]):
            x=42+ci*(col_w+gap); y=y_top
            for item in col:
                lines=wrap_text(item,"Doc",7.55,col_w-14)
                c.setFillColor(COLORS[2]); c.circle(x+2.5,y-3,2,fill=1,stroke=0)
                c.setFillColor(DARK); c.setFont("Doc",7.55)
                for li,line in enumerate(lines):
                    c.drawString(x+10,y-li*9.4-5,line)
                y-=max(1,len(lines))*9.4+2

    c=canvas.Canvas(str(OUT),pagesize=A4)
    c.setTitle("Karłowice-Różanka - okręgi wyborcze 2021")
    c.setAuthor("Rekonstrukcja na podstawie ogłoszenia wyborczego Wrocław 2021")

    header(c,"Karłowice-Różanka - okręgi wyborcze","Wybory do Rad Osiedli Wrocławia - podział zgodny z ogłoszeniem z 2021 r.")
    draw_map(c,(36,250,W-72,500),None)
    c.setFillColor(DARK); c.setFont("Doc-Bold",10); c.drawString(42,226,"Okręgi wyborcze 2021")
    for i in range(1,6):
        x=42+(i-1)*101; c.setFillColor(COLORS[i]); c.roundRect(x,207,12,12,2,fill=1,stroke=0)
        c.setFillColor(DARK); c.setFont("Doc",8); c.drawString(x+18,209,f"Okręg {i}")
    c.setFillColor(MUTED); c.setFont("Doc",7.5)
    note=("Granice są rekonstrukcją przestrzenną: przynależność adresów wynika z oficjalnego wykazu wyborczego z 2021 r., "
          "a geometria została odtworzona na podstawie miejskich danych przestrzennych.")
    y=176
    for line in wrap_text(note,"Doc",7.5,W-84):
        c.drawString(42,y,line); y-=10
    footer(c,1); c.showPage()

    for page,d in enumerate(rules["districts"],start=2):
        no=int(d["district"])
        header(c,f"Karłowice-Różanka - Okręg {no}",f"Wybory do Rad Osiedli Wrocławia 2021 | obwód {d['precinct']} | liczba mandatów: {d['seats']}")
        draw_map(c,(36,455,W-72,290),no)
        c.setFillColor(DARK); c.setFont("Doc-Bold",8.8); c.drawString(42,438,"Lokal głosowania w ogłoszeniu 2021")
        c.setFont("Doc",8)
        yy=424
        for line in wrap_text(d["polling_station"],"Doc",8,W-84):
            c.drawString(42,yy,line); yy-=10
        c.setStrokeColor(MID); c.line(42,402,W-42,402)
        c.setFillColor(DARK); c.setFont("Doc-Bold",10); c.drawString(42,384,"Adresy należące do okręgu - zgodnie z ogłoszeniem wyborczym 2021")
        items=[format_numbers(r["street"],r["numbers"]) for r in d["rules"]]
        draw_items(c,items,364)
        footer(c,page); c.showPage()
    c.save()
    print(OUT)

if __name__=="__main__":
    main()
