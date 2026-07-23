# -*- coding: utf-8 -*-
r"""중간 산출물 시각화 — 유형표준화·저항면·보행도로망·인구격자 4패널 + 개별.
실행: .venv\Scripts\python.exe src\module4_intermediates_fig.py
"""
import os, sys, io, glob, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
from rasterio import features as rfeatures
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors as mcolors
from matplotlib.patches import Patch

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(PROJ,"outputs",datetime.date.today().strftime("%Y%m%d")); os.makedirs(OUTDIR,exist_ok=True)
def L(pat):
    fs=sorted(glob.glob(os.path.join(PROJ,"outputs","*",pat))); return fs[-1] if fs else None
def p(f): return os.path.join(OUTDIR,f)
GRID=L("module4C_대구_2019_전류밀도.tif")
DIST=os.path.join(PROJ,"data_clean","districts_5179.gpkg")
ROAD=r"C:/Users/user/AppData/Local/Temp/claude/D--my-Data-GIS-Project-20260629----------/3dd1a3d4-23e4-4fa8-a518-c682997d53f4/scratchpad/roads/Z_KAIS_TL_SPRD_MANAGE_27000.shp"
POP=r"D:/my Data/GIS/Data/Source/2_public D/(B100)국토통계_인구정보-총 인구 수(전체)-(격자) 100M_대구광역시_201904/vl_blk.shp"
BAD={"대분류","중분류","소분류","세분류","유형","미분류"}

# 한글 폰트 설정 (Windows/Linux 모두 지원)
import platform
if platform.system() == "Windows":
    fp = r"C:\Windows\Fonts\malgun.ttf"
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
else:  # Linux/macOS
    fp = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.sans-serif"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
        plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["axes.unicode_minus"]=False

with rasterio.open(GRID) as ds: transform=ds.transform; shape=ds.shape
b=rasterio.transform.array_bounds(shape[0],shape[1],transform); ext=(b[0],b[2],b[1],b[3])
dist=gpd.read_file(DIST,engine="pyogrio")

# 통합유형(2024) 래스터 + 저항
mp=pd.read_csv(os.path.join(PROJ,"config","crosswalk","통합비교유형_2024.csv"),encoding="utf-8-sig")
mapping=dict(zip(mp["원유형"].astype(str),mp["통합비교유형"].astype(str)))
res=pd.read_csv(os.path.join(PROJ,"config","connectivity_resistance.csv"),encoding="utf-8-sig")
res_map=dict(zip(res["통합비교유형"],res["저항값"].astype(float)))
g=gpd.read_file(os.path.join(PROJ,"data_clean","biotope_2024_5179.gpkg"),engine="pyogrio",columns=["유형중분류"])
s=(g["유형중분류"].astype("string").str.replace(r"\s+"," ",regex=True).str.strip().replace({"":pd.NA}))
s=s.mask(s.isin(BAD|{"유형중분류"})); g["통합"]=s.map(mapping); g=g.dropna(subset=["통합"])
types=sorted(g["통합"].unique()); code={t:i+1 for i,t in enumerate(types)}
g["_c"]=g["통합"].map(code); g["_r"]=g["통합"].map(res_map)
type_r=rfeatures.rasterize(zip(g.geometry,g["_c"]),out_shape=shape,transform=transform,fill=0,dtype="int32").astype(float)
type_r[type_r==0]=np.nan
resist_r=rfeatures.rasterize(zip(g.geometry,g["_r"]),out_shape=shape,transform=transform,fill=np.nan,dtype="float32")

# 도로(대구 클립)
roads=gpd.read_file(ROAD,engine="pyogrio",columns=["ROAD_LT"]).to_crs(5179)
win=dist.geometry.union_all()
roads=roads[roads.geometry.intersects(win)]
# 인구격자 래스터
pop=gpd.read_file(POP,engine="pyogrio",columns=["val"]); pop["val"]=pd.to_numeric(pop["val"],errors="coerce")
pop=pop[pop["val"]>0]
pop_r=rfeatures.rasterize(zip(pop.geometry,pop["val"]),out_shape=shape,transform=transform,fill=np.nan,dtype="float32")

cmap_t=plt.get_cmap("tab20", len(types))
def panel(ax,arr,title,cmap,vmin,vmax,lab,discrete=False):
    ax.set_facecolor("#eeeeee")
    im=ax.imshow(arr,cmap=cmap,extent=ext,origin="upper",vmin=vmin,vmax=vmax)
    dist.boundary.plot(ax=ax,color="black",linewidth=0.5)

    # 구군 레이블 추가
    for idx, row in dist.iterrows():
        centroid = row.geometry.centroid
        ax.text(centroid.x, centroid.y, row["구군"],
               fontsize=9, ha="center", va="center",
               color="white", bbox=dict(boxstyle="round,pad=0.2",
                                       facecolor="black", alpha=0.6,
                                       edgecolor="white", linewidth=0.5))

    ax.set_title(title,fontsize=13); ax.set_xticks([]); ax.set_yticks([])
    if not discrete: plt.colorbar(im,ax=ax,shrink=0.6,label=lab)
    return im

fig,axs=plt.subplots(2,2,figsize=(15,14))
im=panel(axs[0,0],type_r,"(A) 유형 표준화 결과 — 통합비교유형(2024)",cmap_t,1,len(types),"",discrete=True)
axs[0,0].legend(handles=[Patch(color=cmap_t(i),label=t) for i,t in enumerate(types)],
                loc="center left",bbox_to_anchor=(1.0,0.5),fontsize=6.5,ncol=1)
panel(axs[0,1],resist_r,"(B) 이동 저항면 (연결성 입력)","YlOrRd",0,100,"이동저항")
axs[1,0].set_facecolor("#ffffff")
roads.plot(ax=axs[1,0],color="#555555",linewidth=0.25)
dist.boundary.plot(ax=axs[1,0],color="red",linewidth=0.6)
axs[1,0].set_title("(C) 보행 도로망 (접근성 입력, 노딩 후)",fontsize=13); axs[1,0].set_xticks([]); axs[1,0].set_yticks([])
axs[1,0].set_xlim(ext[0],ext[1]); axs[1,0].set_ylim(ext[2],ext[3])
panel(axs[1,1],pop_r,"(D) 100m 인구격자 (접근성 가중·수요)","viridis",0,np.nanpercentile(pop_r,98),"인구(명/셀)")
fig.suptitle("중간 산출물 — 원자료 가공 및 분석 입력",fontsize=16,y=0.995)
fig.tight_layout(); fig.savefig(p("module4_중간산출물_4패널.png"),dpi=150); plt.close(fig)
print("✓",p("module4_중간산출물_4패널.png"))
