# -*- coding: utf-8 -*-
r"""
모듈2 — 탄소 흡수·저장·배출(토지변화)
======================================
유형별 탄소저장(tC/ha)·연간흡수(tC/ha/yr) 계수를 통합비교유형에 결합해
전역·구군·100m격자로 탄소저장·흡수를 산정하고, 2019→2024 저장변화로
토지변화 탄소수지(손실=배출, 증가=축적)를 계산한다.

계수:  config\carbon_coefficients.csv  (원고+IPCC/이경학2006/Nowak2013, 편집가능)
녹지/유형:  2019=U소분류, 2024=유형중분류 → 통합비교유형(config\crosswalk\통합비교유형_*.csv)
격자:  기존 연결성 래스터(module4C_대구_2019_전류밀도.tif) 격자에 정합.
출력:  outputs\<일자>\module2_탄소_3단위요약.xlsx · 저장/흡수/탄소수지 지도 · tif
실행:  .venv\Scripts\python.exe src\module2_carbon.py
"""
import os, sys, io, datetime, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
from rasterio import features as rfeatures
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors as mcolors

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(PROJ, "data_clean")
CWDIR = os.path.join(PROJ, "config", "crosswalk")
OUTDIR = os.path.join(PROJ, "outputs", datetime.date.today().strftime("%Y%m%d"))
os.makedirs(OUTDIR, exist_ok=True)
DIST = os.path.join(CLEAN, "districts_5179.gpkg")
# 연결성 래스터(격자 기준)를 최근 출력폴더에서 탐색
_grids = sorted(glob.glob(os.path.join(PROJ, "outputs", "*", "module4C_대구_2019_전류밀도.tif")))
GRIDTIF = _grids[-1] if _grids else os.path.join(OUTDIR, "module4C_대구_2019_전류밀도.tif")
COEF = os.path.join(PROJ, "config", "carbon_coefficients.csv")
CO2 = 44.0/12.0
FOREST_FLAT = 115.0     # 연도비교용 산림 단일 저장계수(수종 재분류 아티팩트 제거; 2019 수종가중 평균≈114)
FOREST_UPT_FLAT = 4.6   # 연도비교용 산림 단일 흡수계수
FOREST_CLS = {"침엽수림","활엽수림","혼효림","인공림","산림기타"}
DINFO = {"2019": ("biotope_2019_5179.gpkg", "U소분류", "통합비교유형_2019.csv", "U세분류"),
         "2024": ("biotope_2024_5179.gpkg", "유형중분류", "통합비교유형_2024.csv", "유형중분류")}
BAD = {"대분류","중분류","소분류","세분류","유형","미분류"}

def forest_coef(s):
    """산림 세부유형 문자열 → 탄소유형(수종 우선)."""
    s = str(s)
    if "비식생" in s or "훼손" in s: return "산림기타"
    if "혼효" in s: return "혼효림"
    if "침엽" in s or "소나무" in s: return "침엽수림"
    if "활엽" in s or "참나무" in s: return "활엽수림"
    if "인공" in s or "복원" in s or "임업" in s: return "인공림"
    return "혼효림"   # 기타 산림 등 → 대표값
REPORT=[]
def log(m=""): print(m, flush=True); REPORT.append(str(m))
def p(f): return os.path.join(OUTDIR, f)

fp=r"C:\Windows\Fonts\malgun.ttf"
if os.path.exists(fp):
    font_manager.fontManager.addfont(fp); plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"]=False

def _poly(g):
    if g is None or g.is_empty: return None
    if g.geom_type in ("Polygon","MultiPolygon"): return g
    if g.geom_type=="GeometryCollection":
        ps=[x for x in g.geoms if x.geom_type in ("Polygon","MultiPolygon")]
        return None if not ps else (ps[0] if len(ps)==1 else shapely.union_all(ps))
    return None

def rasterize_coef(year, stock, upt, transform, shape):
    gpkg, field, mapcsv, finef = DINFO[year]
    mp = pd.read_csv(os.path.join(CWDIR, mapcsv), encoding="utf-8-sig")
    mapping = dict(zip(mp["원유형"].astype(str), mp["통합비교유형"].astype(str)))
    cols = list(dict.fromkeys([field, finef]))
    g = gpd.read_file(os.path.join(CLEAN, gpkg), engine="pyogrio", columns=cols)
    s=(g[field].astype("string").str.replace(r"\s+"," ",regex=True).str.strip().replace({"":pd.NA}))
    s=s.mask(s.isin(BAD|{field})); g["통합"]=s.map(mapping)
    g=g.dropna(subset=["통합"]).copy()
    # 산림은 세부유형(수종)으로 세분 → 탄소유형
    g["탄소유형"]=g["통합"]
    isf = g["통합"]=="산림"
    g.loc[isf,"탄소유형"]=g.loc[isf, finef].apply(forest_coef)
    g["geometry"]=g.geometry.apply(_poly); g=g[g.geometry.notna()]
    log(f"  [{year}] 산림 세분: "+", ".join(f"{k} {v}" for k,v in g.loc[isf,'탄소유형'].value_counts().items()))
    stock_flat={k:(FOREST_FLAT if k in FOREST_CLS else v) for k,v in stock.items()}
    upt_flat={k:(FOREST_UPT_FLAT if k in FOREST_CLS else v) for k,v in upt.items()}
    out={}
    for key, cmap in [("저장",stock),("흡수",upt),("저장평탄",stock_flat),("흡수평탄",upt_flat)]:
        g["_v"]=g["탄소유형"].map(cmap).astype(float)
        gg=g.dropna(subset=["_v"])
        out[key]=rfeatures.rasterize(zip(gg.geometry, gg["_v"]), out_shape=shape, transform=transform,
                                     fill=np.nan, dtype="float32")
    miss=set(g["탄소유형"].unique())-set(stock)
    if miss: log(f"  ⚠ 계수 없는 탄소유형: {miss}")
    # 유형별 상세(면적·저장)
    g["_ha"]=g.geometry.area/10000.0
    sp=g.groupby("탄소유형")["_ha"].sum().reset_index().rename(columns={"_ha":f"면적ha_{year}"})
    sp[f"저장tC_{year}"]=(sp["탄소유형"].map(stock)*sp[f"면적ha_{year}"]).round(0)
    return out, sp

def main():
    log(f"### 모듈2 탄소 흡수·저장·배출(토지변화)  {datetime.date.today()}\n")
    cf=pd.read_csv(COEF, encoding="utf-8-sig")
    stock=dict(zip(cf["탄소유형"], cf["탄소저장_tC_ha"].astype(float)))
    upt=dict(zip(cf["탄소유형"], cf["연간흡수_tC_ha_yr"].astype(float)))
    log(f"계수: 활엽수림 {stock['활엽수림']}/{upt['활엽수림']} · 침엽수림 {stock['침엽수림']}/{upt['침엽수림']} · 혼효림 {stock['혼효림']}/{upt['혼효림']} tC/ha …\n")
    with rasterio.open(GRIDTIF) as ds:
        transform=ds.transform; shape=ds.shape
    dist=gpd.read_file(DIST, engine="pyogrio").reset_index(drop=True); dist["did"]=np.arange(1,len(dist)+1)
    didr=rfeatures.rasterize(zip(dist.geometry,dist["did"]), out_shape=shape, transform=transform, fill=0, dtype="int32")

    R={}; SP={}
    for y in ["2019","2024"]:
        R[y], SP[y] = rasterize_coef(y, stock, upt, transform, shape)
    # 변화·배출은 산림 평탄값(수종 재분류 아티팩트 제거)로 비교가능하게
    dstock = R["2024"]["저장평탄"] - R["2019"]["저장평탄"]   # +축적 / −배출

    # ── 구별·전역 집계 ──
    rows=[]
    for _,d in dist.iterrows():
        m=(didr==d["did"]); rec={"구군":d["구군"]}
        for y in ["2019","2024"]:
            rec[f"저장_tC_{y}"]=int(np.nansum(np.where(m,R[y]["저장평탄"],np.nan)))
            rec[f"흡수_tCyr_{y}"]=int(np.nansum(np.where(m,R[y]["흡수평탄"],np.nan)))
        dd=np.where(m,dstock,np.nan)
        rec["순저장변화_tC"]=int(np.nansum(dd))
        rec["배출_tC"]=int(-np.nansum(dd[dd<0])) if np.isfinite(dd).any() else 0
        rec["축적_tC"]=int(np.nansum(dd[dd>0])) if np.isfinite(dd).any() else 0
        rows.append(rec)
    gu_df=pd.DataFrame(rows).sort_values("저장_tC_2024", ascending=False)
    log("[구군 탄소 요약]\n"+gu_df.to_string(index=False)+"\n")

    u19=np.nansum(R['2019']['흡수평탄']); u24=np.nansum(R['2024']['흡수평탄'])
    glob=pd.DataFrame([{
        "지표":"탄소저장 tC","2019":int(np.nansum(R['2019']['저장평탄'])),"2024":int(np.nansum(R['2024']['저장평탄'])),
        "변화":int(np.nansum(R['2024']['저장평탄'])-np.nansum(R['2019']['저장평탄']))},
        {"지표":"연간흡수 tC/yr","2019":int(u19),"2024":int(u24),"변화":int(u24-u19)},
        {"지표":"연간흡수 tCO2/yr(환산)","2019":int(u19*CO2),"2024":int(u24*CO2),"변화":int((u24-u19)*CO2)},
    ])
    emit=-np.nansum(dstock[dstock<0]); gain=np.nansum(dstock[dstock>0])
    log("[전역 탄소 요약]\n"+glob.to_string(index=False))
    log(f"  토지변화 배출 {emit:,.0f} tC (={emit*CO2:,.0f} tCO2), 축적 {gain:,.0f} tC, 순 {np.nansum(dstock):,.0f} tC\n")

    # ── 지도 ──
    b=rasterio.transform.array_bounds(shape[0],shape[1],transform); ext=(b[0],b[2],b[1],b[3])
    def savemap(arr,title,fname,cmap,vmin,vmax,label,diverge=False):
        fig,ax=plt.subplots(figsize=(9,8)); ax.set_facecolor("#d9d9d9")
        im=ax.imshow(arr,cmap=cmap,extent=ext,origin="upper",vmin=vmin,vmax=vmax)
        dist.boundary.plot(ax=ax,color="black",linewidth=0.7)
        ax.set_title(title); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im,ax=ax,shrink=0.6,label=label); fig.tight_layout()
        fig.savefig(p(fname),dpi=140); plt.close(fig)
    savemap(R["2024"]["저장"],"대구 탄소저장량 2024 (tC/ha)","module2_탄소저장_2024.png","YlGn",0,np.nanpercentile(R["2024"]["저장"],98),"tC/ha")
    savemap(R["2024"]["흡수"],"대구 연간 탄소흡수 2024 (tC/ha/yr)","module2_탄소흡수_2024.png","YlGn",0,5,"tC/ha/yr")
    v=np.nanpercentile(np.abs(dstock[np.isfinite(dstock)]),98) or 1
    savemap(dstock,"대구 토지변화 탄소수지 (2024-2019)\n빨강=배출(손실), 파랑=축적","module2_탄소수지_차이.png","RdBu",-v,v,"Δ tC/ha")
    log("✓ 지도 3종")

    # ── 엑셀 ──
    xlsx=p("module2_탄소_3단위요약.xlsx")
    sp=SP["2019"].merge(SP["2024"], on="탄소유형", how="outer").fillna(0).sort_values("저장tC_2024", ascending=False)
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        glob.to_excel(xw, sheet_name="전역", index=False)
        gu_df.to_excel(xw, sheet_name="구군", index=False)
        sp.to_excel(xw, sheet_name="유형별상세", index=False)
        cf.to_excel(xw, sheet_name="계수표", index=False)
    log(f"✓ 엑셀: {xlsx}")

    # 리포트
    cat=os.path.join(PROJ,"catalog"); os.makedirs(cat,exist_ok=True)
    open(os.path.join(cat,f"module2_report_{datetime.date.today().strftime('%Y%m%d')}.txt"),"w",encoding="utf-8").write("\n".join(REPORT))
    log("모듈2 완료")

if __name__=="__main__":
    try: main()
    except Exception:
        import traceback; log("\n!!! 예외:\n"+traceback.format_exc()); raise
