#!/usr/bin/env python3
from pathlib import Path
import math
import fitz
from PIL import Image, ImageOps, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT=Path(__file__).resolve().parents[1]
P21=ROOT/"pdf-2021"/"Karlowice-Rozanka_okregi-wyborcze_2021.pdf"
P27=ROOT/"pdf-2027-propozycja-miasta"/"Karlowice-Rozanka_okregi-wyborcze_2027-propozycja-miasta.pdf"
OUTDIR=ROOT/"pdf-porownanie-2021-vs-2027-propozycja-miasta"
OUTDIR.mkdir(exist_ok=True)
OUT=OUTDIR/"Karlowice-Rozanka_roznice_2021_vs_2027-propozycja-miasta.pdf"
TMP=ROOT/".tmp-compare"
TMP.mkdir(exist_ok=True)

REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pdfmetrics.registerFont(TTFont("Doc",REG)); pdfmetrics.registerFont(TTFont("Doc-Bold",BOLD))
DARK=colors.HexColor("#1F2430"); MUTED=colors.HexColor("#5B6574"); LINE=colors.HexColor("#D7DBE1")
ACC=colors.HexColor("#3568B8"); GREEN=colors.HexColor("#2E8B57"); ORANGE=colors.HexColor("#D9822B"); BG=colors.HexColor("#F7F8FA")

DATA={
1:("84","85","4","4","Brak zmian adresowych; zmienia się tylko numer obwodu 84 → 85."),
2:("85","86","3","3","Dodano ulicę Artyleryjska; numer obwodu 85 → 86."),
3:("86","87","3","3","Brak zmian adresowych; zmienia się tylko numer obwodu 86 → 87."),
4:("87","88","6","6","Obornicka: 2–235 → 2–217; numer obwodu 87 → 88."),
5:("88","89","5","5","Brak zmian adresowych; zmienia się tylko numer obwodu 88 → 89."),
}

def render(pdf,pathprefix):
    doc=fitz.open(pdf)
    paths=[]
    for i,p in enumerate(doc):
        pix=p.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False)
        out=TMP/f"{pathprefix}-{i+1}.png"; pix.save(out); paths.append(out)
    return paths

pages21=render(P21,"2021"); pages27=render(P27,"2027")

def crop_map(src,page_no,label):
    im=Image.open(src).convert("RGB")
    iw,ih=im.size; pw,ph=A4
    if page_no==1: x,y,w,h=36,250,pw-72,500
    else: x,y,w,h=36,455,pw-72,290
    box=(int(x/pw*iw),int((ph-(y+h))/ph*ih),int((x+w)/pw*iw),int((ph-y)/ph*ih))
    crop=ImageOps.expand(im.crop(box),border=2,fill="white")
    out=TMP/f"{src.stem}-crop.png"; crop.save(out); return out

maps={}
for i in range(1,7):
    maps[("21",i)]=crop_map(pages21[i-1],i,"2021")
    maps[("27",i)]=crop_map(pages27[i-1],i,"2027")

def wrap(text,font,size,width):
    out=[];cur=""
    for word in text.split():
        t=word if not cur else cur+" "+word
        if stringWidth(t,font,size)<=width: cur=t
        else:
            if cur: out.append(cur)
            cur=word
    if cur: out.append(cur)
    return out

def hdr(c,W,H,title,sub,badge):
    c.setFillColor(DARK);c.setFont("Doc-Bold",20);c.drawString(36,H-42,title)
    c.setFillColor(ACC);c.setFont("Doc-Bold",9);c.drawRightString(W-36,H-40,badge)
    c.setFillColor(MUTED);c.setFont("Doc",8.5);c.drawString(36,H-58,sub)
    c.setStrokeColor(LINE);c.line(36,H-68,W-36,H-68)

def ftr(c,W,page,total):
    c.setStrokeColor(LINE);c.line(36,28,W-36,28)
    c.setFillColor(MUTED);c.setFont("Doc",6.5)
    c.drawString(36,17,"Karłowice-Różanka | porównanie 2021 vs 2027 - propozycja miasta")
    c.drawRightString(W-36,17,f"strona {page}/{total}")

def table(c,x,yt,widths,headers,rows,rh=36,fs=8):
    tw=sum(widths); c.setFillColor(ACC);c.rect(x,yt-rh,tw,rh,fill=1,stroke=0)
    xx=x;c.setFillColor(colors.white);c.setFont("Doc-Bold",fs)
    for w,h in zip(widths,headers):c.drawString(xx+4,yt-rh+12,h);xx+=w
    y=yt-rh;c.setFont("Doc",fs)
    for ri,row in enumerate(rows):
        y-=rh;c.setFillColor(BG if ri%2==0 else colors.white);c.setStrokeColor(LINE);c.rect(x,y,tw,rh,fill=1,stroke=1)
        xx=x
        for w,val in zip(widths,row):
            c.setFillColor(DARK);ty=y+rh-11
            for ln in wrap(str(val),"Doc",fs,w-8)[:3]: c.drawString(xx+4,ty,ln);ty-=9
            xx+=w

def fit(path,mw,mh):
    im=Image.open(path); w,h=im.size;s=min(mw/w,mh/h);return w*s,h*s

TOTAL=9
c=canvas.Canvas(str(OUT),pagesize=A4)
W,H=A4
hdr(c,W,H,"Karłowice-Różanka - raport różnic","Podział 2021 vs propozycja miasta na 2027 r.","PORÓWNANIE")
rows=[
["Liczba okręgów","5","5","bez zmian"],["Mandaty ogółem","21","21","bez zmian"],
["Numery obwodów","84–88","85–89","+1 dla każdego okręgu"],
["Reguły adresowe","2021","propozycja 2027","zmiany w O2 i O4"],
["Geometria rekonstrukcji","2021","2027","bez różnic geometrycznych"],
]
table(c,36,H-105,[145,90,115,173],["Zakres","2021","2027","Różnica"],rows,42,8.2)
c.setFillColor(DARK);c.setFont("Doc-Bold",11);c.drawString(36,280,"Najważniejsze różnice")
for i,t in enumerate(["O2: dodano ulicę Artyleryjska.","O4: Obornicka 2–235 → 2–217.","Pozostałe różnice dotyczą numeracji obwodów."]):
    c.setFont("Doc",9);c.drawString(50,255-i*22,"• "+t)
ftr(c,W,1,TOTAL);c.showPage()

hdr(c,W,H,"Porównanie okręg po okręgu","Tylko różnice pomiędzy wariantami","TABELA")
rows=[]
for d,(a,b,m1,m2,chg) in DATA.items(): rows.append([f"Okręg {d}",a,b,f"{m1}/{m2}",chg])
table(c,24,H-95,[65,70,70,85,275],["Okręg","Obwód 21","Obwód 27","Mandaty","Różnica"],rows,70,8)
ftr(c,W,2,TOTAL);c.showPage()

hdr(c,W,H,"Różnice źródłowe","Zmiany w wykazie adresowym i numeracji","SZCZEGÓŁY")
y=H-100
for d,(a,b,m1,m2,chg) in DATA.items():
    c.setFillColor(BG);c.setStrokeColor(LINE);c.roundRect(36,y-92,W-72,78,8,fill=1,stroke=1)
    c.setFillColor(DARK);c.setFont("Doc-Bold",10);c.drawString(48,y-32,f"Okręg {d}")
    c.setFont("Doc",8.5);c.drawString(130,y-32,f"obwód {a} → {b}; mandaty {m1} → {m2}")
    yy=y-50
    for ln in wrap(chg,"Doc",8.5,W-120):c.drawString(48,yy,ln);yy-=11
    y-=98
ftr(c,W,3,TOTAL);c.showPage()

# Maps, overall + 5 districts
for outpage, sourcepage, title in [(4,1,"Całe osiedle")]+[(i+4,i+1,f"Okręg {i}") for i in range(1,6)]:
    W,H=landscape(A4);c.setPageSize((W,H))
    hdr(c,W,H,f"Mapa porównawcza - {title}","Po lewej 2021, po prawej propozycja miasta 2027","MAPY")
    mh=H-145;mw=(W-94)/2;y=55
    for key,x,cap in [("21",36,"2021"),("27",58+mw,"2027 - propozycja miasta")]:
        c.setFillColor(colors.white);c.setStrokeColor(LINE);c.roundRect(x,y,mw,mh,8,fill=1,stroke=1)
        p=maps[(key,sourcepage)];dw,dh=fit(p,mw-10,mh-32)
        c.drawImage(ImageReader(str(p)),x+(mw-dw)/2,y+5,dw,dh,mask="auto")
        c.setFillColor(DARK);c.setFont("Doc-Bold",9);c.drawString(x+10,y+mh-18,cap)
    ftr(c,W,outpage,TOTAL);c.showPage()
c.save()
print(OUT)
