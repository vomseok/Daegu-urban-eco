# -*- coding: utf-8 -*-
r"""
모듈4-G — 녹지 추가 우선지 도출 (접근성 소외 × 연결성 취약 접목)
================================================================
전역 산출물(접근성 인구셀·연결성 래스터)을 구 단위로 잘라, 두 지표를 접목해
'신규 녹지 우선 후보지'를 도출한다.
  · 접근성 소외: 거주격자 중 최근접 녹지 도보 >10분(생활권 녹지 결핍).
  · 후보 점수: 비녹지 셀 반경 350m내 '소외 인구'가 많을수록 신규 녹지 효과 큼.
  · 연결성 접목: 후보가 연결성 취약대(등급4~5)이면 가점(공급+연결 동시 효과).
입력:  outputs\*\module4A_대구_2024_접근시간.gpkg (val,time_min)
       outputs\*\module4C_대구_2024_전류밀도.tif
       data_clean\biotope_2024_5179.gpkg + 통합비교유형_2024.csv (녹지마스크)
       data_clean\districts_5179.gpkg
출력:  outputs\<일자>\module4_녹지추가_<구>_2024.png · module4_녹지추가_요약.csv
실행:  .venv\Scripts\python.exe src\module4_greenadd.py [구1 구2 ...]  (기본 수성구 중구)
"""
import os, sys, io, glob, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
from rasterio import features as rfeatures
from scipy.ndimage import uniform_filter, distance_transform_edt
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(PROJ, "outputs", datetime.date.today().strftime("%Y%m%d")); os.makedirs(OUTDIR, exist_ok=True)
def latest(pat):
    fs=sorted(glob.glob(os.path.join(PROJ,"outputs","*",pat))); return fs[-1] if fs else None
ACC = latest("module4A_대구_2024_접근시간.gpkg")
CONN = latest("module4C_대구_2024_전류밀도.tif")
DIST = os.path.join(PROJ,"data_clean","districts_5179.gpkg")
GREEN={"산림","초지·조성녹지","수계·습지"}; BAD={"대분류","중분류","소분류","세분류","유형","미분류"}
DEP_MIN=10; RADIUS_CELLS=7; CONN_BREAKS=[0.05,0.15,0.33,0.62]
def p(f): return os.path.join(OUTDIR,f)
def log(m=""): print(m,flush=True)
fp=r"C:\Windows\Fonts\malgun.ttf"
if os.path.exists(fp):
    font_manager.fontManager.addfont(fp); plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"]=False

def green_mask(shape, transform):
    g=gpd.read_file(os.path.join(PROJ,"data_clean","biotope_2024_5179.gpkg"),engine="pyogrio",columns=["유형중분류"])
    mp=pd.read_csv(os.path.join(PROJ,"config","crosswalk","통합비교유형_2024.csv"),encoding="utf-8-sig")
    mapping=dict(zip(mp["원유형"].astype(str),mp["통합비교유형"].astype(str)))
    s=(g["유형중분류"].astype("string").str.replace(r"\s+"," ",regex=True).str.strip().replace({"":pd.NA}))
    s=s.mask(s.isin(BAD|{"유형중분류"})); g["통합"]=s.map(mapping)
    grn=g[g["통합"].isin(GREEN)]
    inv=~grn.geometry.is_valid
    if inv.any(): grn.loc[inv,grn.geometry.name]=grn.loc[inv,grn.geometry.name].make_valid()
    return rfeatures.rasterize(((x,1) for x in grn.geometry),out_shape=shape,transform=transform,fill=0,dtype="uint8").astype(bool)

def main():
    gus=sys.argv[1:] or ["수성구","중구"]
    with rasterio.open(CONN) as ds: conn=ds.read(1); transform=ds.transform; shape=ds.shape
    grn=green_mask(shape,transform)
    # 연결성 등급(1고~5저)
    cg=np.full(shape,np.nan); v=np.isfinite(conn)
    cg[v&(conn<CONN_BREAKS[0])]=5; cg[v&(conn>=CONN_BREAKS[0])&(conn<CONN_BREAKS[1])]=4
    cg[v&(conn>=CONN_BREAKS[1])&(conn<CONN_BREAKS[2])]=3; cg[v&(conn>=CONN_BREAKS[2])&(conn<CONN_BREAKS[3])]=2
    cg[v&(conn>=CONN_BREAKS[3])]=1
    dist=gpd.read_file(DIST,engine="pyogrio")
    acc=gpd.read_file(ACC,engine="pyogrio")   # 100m 인구셀 (val,time_min)
    acc["cx"]=acc.geometry.centroid.x; acc["cy"]=acc.geometry.centroid.y

    rows=[]
    for gu in gus:
        poly=dist[dist["구군"]==gu].geometry.union_all()
        if poly.is_empty: log(f"! {gu} 없음"); continue
        # 소외 인구 래스터화(구내, time>10)
        sub=acc[acc.geometry.centroid.within(poly)].copy()
        dep=sub[sub["time_min"]>DEP_MIN]
        dep_pop=int(dep["val"].sum()); tot_pop=int(sub["val"].sum())
        dep_rast=rfeatures.rasterize(zip(dep.geometry,dep["val"]),out_shape=shape,transform=transform,fill=0.0,dtype="float32")
        # 반경 내 소외인구 합
        near_dep=uniform_filter(dep_rast,size=RADIUS_CELLS)*RADIUS_CELLS**2
        # 구 마스크
        gm=rfeatures.rasterize(((poly,1),),out_shape=shape,transform=transform,fill=0,dtype="uint8").astype(bool)
        # 후보: 구내·비녹지·유효, 점수=근접소외인구×연결취약가점
        weak=np.isin(cg,[4,5]); bonus=np.where(weak,1.3,1.0)
        score=np.where(gm&~grn&v, near_dep*bonus, 0.0)
        # 상위 후보(점수>0 중 상위 5%) → 우선지
        pos=score[score>0]
        thr=np.percentile(pos,90) if pos.size else 0
        cand=score>=max(thr,1e-6)
        cand_ha=int(cand.sum())
        rows.append({"구군":gu,"총인구":tot_pop,"소외인구(>10분)":dep_pop,
                     "소외비율%":round(dep_pop/tot_pop*100,1) if tot_pop else 0,
                     "녹지추가_우선격자_ha":cand_ha,
                     "우선지_연결취약중첩%":round(float((cand&weak).sum()/cand.sum()*100),1) if cand.sum() else 0})
        # 지도
        b=dist[dist["구군"]==gu].total_bounds; pad=600
        ext=rasterio.transform.array_bounds(shape[0],shape[1],transform); extent=(ext[0],ext[2],ext[1],ext[3])
        fig,ax=plt.subplots(figsize=(9,8)); ax.set_facecolor("white")
        # 배경: 기존 녹지(연녹), 연결취약(연회)
        base=np.full(shape,np.nan); base[gm&grn]=0; base[gm&~grn]=1
        from matplotlib.colors import ListedColormap
        ax.imshow(np.where(gm,base,np.nan),cmap=ListedColormap(["#bfe3b0","#f2f2f2"]),extent=extent,origin="upper",vmin=0,vmax=1)
        # 소외 거주지(주황) — 셀 중심 산점
        if len(dep): ax.scatter(dep["cx"],dep["cy"],s=4,c="#fdae61",label="접근성 소외 거주지(>10분)")
        # 녹지추가 우선지(빨강)
        cand_disp=np.where(cand,1.0,np.nan)
        ax.imshow(cand_disp,cmap=ListedColormap(["#d73027"]),extent=extent,origin="upper",vmin=0,vmax=1)
        dist[dist["구군"]==gu].boundary.plot(ax=ax,color="black",linewidth=1.5)
        ax.set_xlim(b[0]-pad,b[2]+pad); ax.set_ylim(b[1]-pad,b[3]+pad)
        ax.set_title(f"{gu} 녹지 추가 우선지 도출 (접근성 소외 × 연결성 취약)"); ax.set_xticks([]); ax.set_yticks([])
        ax.legend(handles=[Patch(color="#bfe3b0",label="기존 녹지"),
                           Patch(color="#fdae61",label="접근성 소외 거주지(>10분)"),
                           Patch(color="#d73027",label="녹지 추가 우선지")],loc="lower left",fontsize=9)
        fig.tight_layout(); fig.savefig(p(f"module4_녹지추가_{gu}_2024.png"),dpi=150); plt.close(fig)
        log(f"✓ {gu}: 소외인구 {dep_pop:,}명({rows[-1]['소외비율%']}%), 우선지 {cand_ha}ha")
    summ=pd.DataFrame(rows); summ.to_csv(p("module4_녹지추가_요약.csv"),index=False,encoding="utf-8-sig")
    log("\n"+summ.to_string(index=False))

if __name__=="__main__":
    main()
