#!/usr/bin/env python3
from pathlib import Path
import json,math
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely import make_valid
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
GEO=ROOT/"analysis-v6"/"okregi-v6.geojson"
STREETS=ROOT/"wariant-spojny-propozycja"/"geojson"/"siatka-ulic-geoportal.geojson"
OUTDIR=ROOT/"pdf-final-propozycja"
OUTDIR.mkdir(exist_ok=True)
TMP=ROOT/".tmp-final";TMP.mkdir(exist_ok=True)
OUT=OUTDIR/"Karlowice-Rozanka_ostateczna-propozycja-wariant-spojny-v6.pdf"

gdf=gpd.read_file(GEO)
streets=gpd.read_file(STREETS)
COL=["#D73027","#4575B4","#1A9850","#762A83","#F28E2B"]
ADDR={
1:["Brücknera Aleksandra, al. P 10-54","Bydgoska","Długosza Jana","Galla Anonima","Giżycka","Grudziądzka","Krzywoustego Bolesława 1-109, 111","Kromera Marcina, al.","Kętrzyńska","Łąka Mazurska","Miechowity Macieja","Poprzeczna, al. 33/35, 33A","Toruńska"],
2:["Anczyca Władysława","Asnyka Adama","Artyleryjska","Berenta Wacława","Bonczyka Norberta, ks.","Boya-Żeleńskiego Tadeusza, al.","Brzechwy Jana","Chrzanowskiego Ignacego","Daniłowskiego Gustawa, pl.","Dygasińskiego Adolfa","Filomatów","Gajcego Tadeusza","Goszczyńskiego Seweryna","Grochowiaka Stanisława","Gąsiorowskiego Wacława","Karpińskiego Franciszka","Kasprowicza Jana, al. 1-112","Konopnickiej Marii","Koszarowa","Krasickiego Ignacego, bp.","Leśmiana Bolesława","Lenartowicza Teofila","Lindego Samuela Bogumiła","Makuszyńskiego Kornela","Micińskiego Tadeusza","Nabielaka Ludwika","Oppmana Artura","Orkana Władysława","Perzyńskiego Włodzimierza","Piłsudskiego Józefa, pl. Marsz.","Piętaka Stanisława","Potockiego Wacława","Przerwy-Tetmajera Kazimierza","Przybyszewskiego Stanisława","Rowerowa","Skwer Obrońców Helu","Sołtysowicka N 1-5A, P 2-12, 15-24","Sportowa","Staffa Leopolda","Syrokomli Władysława","Ujejskiego Kornela","Wybickiego Józefa, gen.","Zaleskiego Bohdana","Zawalna","Zelenaya Tadeusza","Żmigrodzka - strona okręgu 2"],
3:["Baczyńskiego Krzysztofa Kamila","Brodzińskiego Kazimierza","Czajkowskiego Piotra 109","Forteczna","Jutrosińska","Kamieńskiego Henryka Michała 3-184","Kocha Roberta","Mochnackiego Maurycego","Pola Wincentego - końcówka przy Kamieńskiego","Romanowskiego Mieczysława","Torowa"],
4:["Bałtycka","Broniewskiego Władysława","Ligocka","Macedońska","Młynarska","Na Polance","Obornicka N 21-217, P 2-54","Paprotna 2-6","Parnickiego Teodora","Piesza","Wołowska","Zaułek Rogoziński","Żmigrodzka P 22-58, P 104-116"],
5:["Bałkańska","Bezpieczna","Bułgarska","Chorwacka","Czeska","Jarocińska 99","Jugosłowiańska","Kumko Weroniki","Lutycka","Łużycka","Morawska","Obodrzycka","Obornicka P 56-160","Osobowicka 2-63","Serbska","Słowacka"]
}
POP={1:3850,2:8020,3:4300,4:6290,5:6790}
MAND={1:3,2:6,3:3,4:4,5:5}

def render(high=None,path=None):
    fig,ax=plt.subplots(figsize=(13,6.4),dpi=160)
    for _,r in gdf.iterrows():
        n=int(r.district); color=COL[n-1] if high in (None,n) else "#DFE4EA"; alpha=.57 if high in (None,n) else .43
        gpd.GeoSeries([make_valid(r.geometry)],crs=4326).plot(ax=ax,color=color,edgecolor="white",linewidth=1.5,alpha=alpha)
    streets.plot(ax=ax,color="#59636D",linewidth=.5,alpha=.9)
    targets=range(1,6) if high is None else [high]
    for n in targets:
        p=make_valid(gdf[gdf.district==n].geometry.iloc[0]).representative_point()
        ax.text(p.x,p.y,str(n),ha="center",va="center",fontsize=11,bbox=dict(boxstyle="circle,pad=.35",fc="white",ec="#20242A",lw=1))
    bounds=gdf.total_bounds if high is None else gdf[gdf.district==high].total_bounds
    x0,y0,x1,y1=bounds;dx=x1-x0;dy=y1-y0
    ax.set_xlim(x0-dx*.08,x1+dx*.08);ax.set_ylim(y0-dy*.12,y1+dy*.12);ax.set_axis_off();fig.tight_layout(pad=0)
    fig.savefig(path,bbox_inches="tight",pad_inches=.02,facecolor="#eef1f5");plt.close(fig)

render(None,TMP/"all.png")
for n in range(1,6):render(n,TMP/f"{n}.png")

REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pdfmetrics.registerFont(TTFont("Doc",REG));pdfmetrics.registerFont(TTFont("Doc-Bold",BOLD))
W,H=landscape(A4);DARK=colors.HexColor("#1F2430");LINE=colors.HexColor("#D7DBE1");MUTED=colors.HexColor("#5B6574")

def wrap(t,font,size,w):
    out=[];cur=""
    for word in t.split():
        q=word if not cur else cur+" "+word
        if stringWidth(q,font,size)<=w:cur=q
        else:
            if cur:out.append(cur)
            cur=word
    if cur:out.append(cur)
    return out
def fit(p,mw,mh):
    im=Image.open(p);w,h=im.size;s=min(mw/w,mh/h);return w*s,h*s
def hdr(c,t):
    c.setFillColor(DARK);c.setFont("Doc-Bold",18);c.drawString(28,H-28,t);c.setStrokeColor(LINE);c.line(28,H-36,W-28,H-36)
def ftr(c,p):
    c.setStrokeColor(LINE);c.line(28,18,W-28,18);c.setFillColor(MUTED);c.setFont("Doc",6);c.drawRightString(W-28,8,f"strona {p}/6")
def cols(c,items,x,yt,w):
    nc=3 if len(items)>22 else 2;gap=10;cw=(w-gap*(nc-1))/nc;chunk=math.ceil(len(items)/nc)
    size=7 if len(items)>35 else 7.6
    for ci,col in enumerate([items[i*chunk:(i+1)*chunk] for i in range(nc)]):
        xx=x+ci*(cw+gap);yy=yt
        for k,item in enumerate(col):
            for ln in wrap(item+("," if k<len(col)-1 else ""),"Doc",size,cw):
                c.setFont("Doc",size);c.setFillColor(DARK);c.drawString(xx,yy,ln);yy-=size+2
            yy-=1

c=canvas.Canvas(str(OUT),pagesize=(W,H));c.setTitle("Karłowice-Różanka - ostateczna propozycja")
hdr(c,"Karłowice-Różanka - ostateczna propozycja podziału na 5 okręgów")
mx,my,mw,mh=28,82,W-56,H-126;c.setFillColor(colors.white);c.setStrokeColor(LINE);c.roundRect(mx,my,mw,mh,8,fill=1,stroke=1)
dw,dh=fit(TMP/"all.png",mw-8,mh-8);c.drawImage(ImageReader(str(TMP/"all.png")),mx+(mw-dw)/2,my+(mh-dh)/2,dw,dh,mask="auto")
# population table
c.setFont("Doc-Bold",8);c.setFillColor(DARK);x=34;y=58
for n in range(1,6):c.drawString(x+(n-1)*145,y,f"O{n}: ~{POP[n]:,}".replace(","," ")+" mieszk. / "+str(MAND[n])+" mand.")
ftr(c,1);c.showPage()
for page,n in enumerate(range(1,6),start=2):
    hdr(c,f"Karłowice-Różanka - Okręg {n} | ~{POP[n]:,} mieszkańców | {MAND[n]} mandatów".replace(","," "))
    mx,my,mw,mh=28,202,W-56,H-242;c.setFillColor(colors.white);c.setStrokeColor(LINE);c.roundRect(mx,my,mw,mh,8,fill=1,stroke=1)
    p=TMP/f"{n}.png";dw,dh=fit(p,mw-8,mh-8);c.drawImage(ImageReader(str(p)),mx+(mw-dw)/2,my+(mh-dh)/2,dw,dh,mask="auto")
    c.setFillColor(colors.HexColor(COL[n-1]));c.roundRect(28,169,W-56,21,5,fill=1,stroke=0);c.setFillColor(colors.white);c.setFont("Doc-Bold",9);c.drawString(38,176,f"Wykaz ulic i adresów - Okręg {n}")
    cols(c,ADDR[n],34,157,W-68);ftr(c,page);c.showPage()
c.save();print(OUT)
