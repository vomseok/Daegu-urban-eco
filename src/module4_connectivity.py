# -*- coding: utf-8 -*-
r"""
모듈4-C — 녹지 연결성 (회로이론, Circuitscape 방식)
====================================================
녹지 코어(산림+조성녹지+수계·습지) 사이의 '전류 흐름'으로 연결성을 평가한다.
저항면(유형별 저항)을 100m 격자로 만들고, 주요 녹지코어 쌍마다 1A를 흘려
누적 전류밀도(=코리더/핀치포인트)와 코어간 유효저항(=연결성 지수)을 계산한다.

방법(회로이론):
  · 각 격자셀=노드, 인접(rook)셀간 컨덕턴스 g=2/(R_i+R_j).
  · 라플라시안 L 구성. 코어쌍(S,T): S에 +1A 주입, T를 접지(v=0) → L v = I 희소해.
  · 셀 전류밀도 = 0.5·Σ|인접 전류|. 코어쌍 누적 → 연결성 코리더맵.
  · 유효저항 R_eff = 평균(V_S) (낮을수록 두 코어가 잘 연결됨).

입력:  data_clean\biotope_{2019,2024}_5179.gpkg
       config\crosswalk\통합비교유형_{2019,2024}.csv  (원유형→통합)
       config\connectivity_resistance.csv               (통합유형→저항, 편집가능)
출력:  outputs\<일자>\module4C_<구>_<연도>_전류밀도.tif / .png
       outputs\<일자>\module4C_<구>_연결성요약.csv
실행:  .venv\Scripts\python.exe src\module4_connectivity.py [구이름]  (기본 수성구)
"""
import os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.sparse.csgraph import connected_components
from scipy.ndimage import label as cc_label
import rasterio
from rasterio import features as rfeatures

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(PROJ, "data_clean")
CWDIR = os.path.join(PROJ, "config", "crosswalk")
OUTROOT = os.path.join(PROJ, "outputs")
RES_CSV = os.path.join(PROJ, "config", "connectivity_resistance.csv")

CELL = 100.0                 # 격자 100m
BUFFER = 1000.0              # 구 경계 밖 완충(가장자리 효과 완화)
GREEN = {"산림", "초지·조성녹지", "수계·습지"}
MIN_CORE_HA = 10             # 코어로 볼 최소 녹지패치 면적(ha=셀수)
TOP_K = 6                    # 연결성 계산에 쓸 상위 코어 수
DISTRICTS = {"2019": ("SIG_KOR_NM", "biotope_2019_5179.gpkg", "U소분류", "통합비교유형_2019.csv"),
             "2024": ("조사지역", "biotope_2024_5179.gpkg", "유형중분류", "통합비교유형_2024.csv")}
BAD = {"대분류","중분류","소분류","세분류","유형","미분류"}

REPORT = []
def log(m=""):
    print(m, flush=True); REPORT.append(str(m))

def save_report(stamp, gu, note=""):
    cat = os.path.join(PROJ, "catalog")
    os.makedirs(cat, exist_ok=True)
    rp = os.path.join(cat, f"module4C_{gu}_report_{stamp}.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
        if note: f.write("\n"+note)
    print("리포트:", rp, flush=True)

def _poly_only(geom):
    if geom is None or geom.is_empty: return None
    if geom.geom_type in ("Polygon","MultiPolygon"): return geom
    if geom.geom_type == "GeometryCollection":
        ps=[p for p in geom.geoms if p.geom_type in ("Polygon","MultiPolygon")]
        return None if not ps else (ps[0] if len(ps)==1 else shapely.union_all(ps))
    return None

def load_window(year, gu):
    """해당 연도 비오톱을 통합유형으로 재라벨하고, 구 경계+완충 창으로 자른다."""
    gufield, gpkg, field, mapcsv = DISTRICTS[year]
    mp = pd.read_csv(os.path.join(CWDIR, mapcsv), encoding="utf-8-sig")
    mapping = dict(zip(mp["원유형"].astype(str), mp["통합비교유형"].astype(str)))
    g = gpd.read_file(os.path.join(CLEAN, gpkg), engine="pyogrio", columns=[field, gufield])
    s = (g[field].astype("string").str.replace(r"\s+"," ",regex=True).str.strip().replace({"":pd.NA}))
    s = s.mask(s.isin(BAD | {field}))
    g["통합"] = s.map(mapping)
    g = g.dropna(subset=["통합"]).copy()
    if gu in ("대구", "전역", "all"):
        # 전역: 구 필터 없이 대구 전체
        gu_poly = None
        sub = g.copy()
    else:
        gu_poly = g[g[gufield]==gu].geometry.union_all()
        if gu_poly.is_empty:
            log(f"  ! '{gu}' 구를 찾지 못함"); sys.exit(1)
        win = gu_poly.buffer(BUFFER)
        sub = g[g.geometry.intersects(win)].copy()
    inv = ~sub.geometry.is_valid
    if inv.any(): sub.loc[inv, sub.geometry.name] = sub.loc[inv, sub.geometry.name].make_valid()
    sub[sub.geometry.name] = sub.geometry.apply(_poly_only)
    sub = sub[sub.geometry.notna() & ~sub.geometry.is_empty].copy()
    log(f"  [{year}] 창 내 {len(sub):,}도형, 구={gu}")
    return sub, gu_poly

def rasterize_resistance(sub, res_map, bounds):
    minx,miny,maxx,maxy = bounds
    minx=np.floor(minx/CELL)*CELL; miny=np.floor(miny/CELL)*CELL
    maxx=np.ceil(maxx/CELL)*CELL;  maxy=np.ceil(maxy/CELL)*CELL
    ncol=int(round((maxx-minx)/CELL)); nrow=int(round((maxy-miny)/CELL))
    transform = rasterio.transform.from_origin(minx, maxy, CELL, CELL)
    sub = sub.copy()
    sub["_R"] = sub["통합"].map(res_map).astype(float)
    sub = sub.dropna(subset=["_R"])
    shapes = ((geom, val) for geom, val in zip(sub.geometry, sub["_R"]))
    R = rfeatures.rasterize(shapes, out_shape=(nrow,ncol), transform=transform,
                            fill=np.nan, all_touched=False, dtype="float32")
    # 녹지 마스크 래스터(코어 탐지용)
    grn = sub[sub["통합"].isin(GREEN)]
    gmask = rfeatures.rasterize(((g,1) for g in grn.geometry), out_shape=(nrow,ncol),
                                transform=transform, fill=0, dtype="uint8").astype(bool)
    log(f"  래스터 {nrow}×{ncol} (셀 {CELL:.0f}m), 유효 {int(np.isfinite(R).sum()):,}셀, 녹지 {int(gmask.sum()):,}셀")
    return R, gmask, transform

def solve_connectivity(R, gmask):
    """회로이론: 상위 코어쌍 전류 누적 → 전류밀도맵 + 평균 유효저항."""
    nrow, ncol = R.shape
    valid = np.isfinite(R)
    idx = -np.ones((nrow,ncol), dtype=np.int64)
    vy, vx = np.where(valid)
    N = len(vy); idx[vy,vx]=np.arange(N)
    Rf = R[vy,vx]
    log(f"  유효노드 {N:,}개, 그래프 구성...")
    # rook 인접 엣지
    rows=[]; cols=[]; cond=[]
    for dy,dx in [(0,1),(1,0)]:
        y2=vy+dy; x2=vx+dx
        ok=(y2<nrow)&(x2<ncol)
        j = np.where(ok, idx[np.clip(y2,0,nrow-1), np.clip(x2,0,ncol-1)], -1)
        m = ok & (j>=0)
        i_=np.arange(N)[m]; j_=j[m]
        g = 2.0/(Rf[i_]+Rf[j_])
        rows.append(i_); cols.append(j_); cond.append(g)
    I=np.concatenate(rows); J=np.concatenate(cols); G=np.concatenate(cond)
    # 대칭 라플라시안
    A = sparse.coo_matrix((G,(I,J)), shape=(N,N)).tocsr()
    A = A + A.T
    deg = np.asarray(A.sum(axis=1)).ravel()
    L = sparse.diags(deg) - A
    # 녹지 코어(연결요소)
    lab, nlab = cc_label(gmask)
    sizes = np.bincount(lab.ravel()); sizes[0]=0
    cores = [c for c in np.argsort(sizes)[::-1] if sizes[c]>=MIN_CORE_HA][:TOP_K]
    log(f"  녹지패치 {nlab}개 중 코어 {len(cores)}개 사용(≥{MIN_CORE_HA}ha), 크기 {[int(sizes[c]) for c in cores]}")
    if len(cores)<2:
        log("  ! 코어가 2개 미만 — 연결성 계산 불가"); return None,None,idx,cores
    # 코어별 노드 인덱스
    core_nodes={}
    for c in cores:
        yy,xx=np.where(lab==c)
        core_nodes[c]=idx[yy,xx]
    # 그래프 연결성분(떨어진 섬 성분 제외 위해)
    ncomp, comp = connected_components(A, directed=False)
    log(f"  그래프 연결성분 {ncomp}개")
    cur = np.zeros(N)
    reffs=[]; n_skip=0
    pairs=[(a,b) for ii,a in enumerate(cores) for b in cores[ii+1:]]
    log(f"  코어쌍 {len(pairs)}개 회로해 계산...")
    for a,b in pairs:
        # 소스·싱크가 같은 연결성분에 있을 때만(아니면 연결 안됨→기여 0)
        ca=np.bincount(comp[core_nodes[a]]).argmax()
        cb=np.bincount(comp[core_nodes[b]]).argmax()
        if ca!=cb:
            n_skip+=1; continue
        comp_nodes=np.where(comp==ca)[0]
        in_comp=np.zeros(N,bool); in_comp[comp_nodes]=True
        sink=core_nodes[b][in_comp[core_nodes[b]]]
        free=in_comp.copy(); free[sink]=False       # 성분 내 노드 - 싱크
        fidx=np.where(free)[0]
        remap=-np.ones(N,np.int64); remap[fidx]=np.arange(len(fidx))
        Lf=L[fidx][:,fidx]
        rhs=np.zeros(len(fidx))
        src=core_nodes[a][in_comp[core_nodes[a]]]
        rhs[remap[src]] += 1.0/len(src)             # 총 1A 주입
        v=spsolve(Lf.tocsc(), rhs)
        vfull=np.zeros(N); vfull[fidx]=v             # sink=0
        reffs.append(float(vfull[src].mean()))
        ecur=G*np.abs(vfull[I]-vfull[J])
        np.add.at(cur, I, ecur*0.5); np.add.at(cur, J, ecur*0.5)
    curmap=np.full((nrow,ncol), np.nan, dtype=np.float32)
    curmap[vy,vx]=cur
    reff_mean=float(np.mean(reffs)) if reffs else float("nan")
    log(f"  유효 코어쌍 {len(reffs)}개(미연결 {n_skip}개 제외), 평균 유효저항 R_eff={reff_mean:.3f} (낮을수록 양호)")
    return curmap, reff_mean, idx, cores

def save_raster_png(arr, transform, base, title, gu=None):
    prof=dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
              dtype="float32", crs="EPSG:5179", transform=transform, nodata=np.nan)
    with rasterio.open(base+".tif","w",**prof) as dst: dst.write(arr,1)
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        fp=r"C:\Windows\Fonts\malgun.ttf"
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp).get_name()
        plt.rcParams["axes.unicode_minus"]=False
        a=arr.copy()
        vmax=np.nanpercentile(a,98) if np.isfinite(a).any() else 1
        fig,ax=plt.subplots(figsize=(10,10))
        im=ax.imshow(a, cmap="magma", vmin=0, vmax=vmax)

        # 구군 경계 오버레이
        if gu:
            try:
                d=gpd.read_file(os.path.join(CLEAN,"districts_5179.gpkg"),engine="pyogrio")
                # 래스터 범위 내 구군만 필터링
                bounds=rasterio.transform.array_bounds(arr.shape[0], arr.shape[1], transform)
                window_geom=shapely.box(*bounds)
                d_sub=d[d.geometry.intersects(window_geom)]
                d_sub.plot(ax=ax, facecolor="none", edgecolor="white", linewidth=1.5, alpha=0.9)
                # 구군 명 라벨
                for idx,row in d_sub.iterrows():
                    centroid=row.geometry.centroid
                    ax.text(centroid.x, centroid.y, row["구군"],
                           fontsize=9, ha="center", va="center", color="white",
                           bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.6, edgecolor="white"))
            except:
                pass

        ax.set_title(title, fontsize=12, fontweight="bold"); ax.axis("off")
        fig.colorbar(im,ax=ax,shrink=0.7,label="전류밀도(연결성)")
        fig.tight_layout(); fig.savefig(base+".png",dpi=140); plt.close(fig)
    except Exception as e:
        log(f"  (png 생략:{e})")

def main():
    gu = sys.argv[1] if len(sys.argv)>1 else "수성구"
    stamp=datetime.date.today().strftime("%Y%m%d")
    outdir=os.path.join(OUTROOT,stamp); os.makedirs(outdir,exist_ok=True)
    log(f"### 모듈4-C 녹지 연결성(회로이론)  {datetime.date.today()}  구={gu}\n")
    res=pd.read_csv(RES_CSV, encoding="utf-8-sig")
    res_map=dict(zip(res["통합비교유형"].astype(str), res["저항값"].astype(float)))
    log(f"저항표: {res_map}\n")

    global TOP_K, MIN_CORE_HA
    citywide = gu in ("대구", "전역", "all")
    if citywide:
        TOP_K = 10; MIN_CORE_HA = 50      # 전역: 주요 대형 녹지코어 위주
        log(f"[전역모드] TOP_K={TOP_K}, MIN_CORE_HA={MIN_CORE_HA}\n")

    # 공통 창 bounds (두 시점 동일 격자 위해 2019 기준)
    rows=[]
    for year in ["2019","2024"]:
        log(f"[{year}] 로드·창추출")
        sub, gu_poly = load_window(year, gu)
        if year=="2019":
            b = tuple(sub.total_bounds) if gu_poly is None else gu_poly.buffer(BUFFER).bounds
        log(f"[{year}] 저항 래스터화")
        R,gmask,transform=rasterize_resistance(sub, res_map, b)
        log(f"[{year}] 회로 연결성 해")
        curmap,reff,idx,cores=solve_connectivity(R,gmask)
        if curmap is None:
            rows.append({"연도":year,"평균유효저항":None,"평균전류밀도":None,"코어수":len(cores)})
            continue
        base=os.path.join(outdir,f"module4C_{gu}_{year}_전류밀도")
        save_raster_png(curmap,transform,base,f"{gu} 녹지연결성(전류밀도) {year}", gu=gu)
        log(f"  ✓ {base}.tif/.png (구군 경계·명 포함)")
        rows.append({"연도":year,"평균유효저항":round(reff,3),
                     "평균전류밀도":round(float(np.nanmean(curmap)),4),
                     "최대전류밀도":round(float(np.nanmax(curmap)),3),"코어수":len(cores)})
        log("")
    summ=pd.DataFrame(rows)
    scsv=os.path.join(outdir,f"module4C_{gu}_연결성요약.csv")
    summ.to_csv(scsv,index=False,encoding="utf-8-sig")
    log("연결성 요약:\n"+summ.to_string(index=False))
    log(f"✓ {scsv}")
    log("="*60); log(f"모듈4-C 완료 → {outdir}")
    save_report(stamp,gu,note="[상태: 정상완료]")

if __name__=="__main__":
    gu = sys.argv[1] if len(sys.argv)>1 else "수성구"
    stamp=datetime.date.today().strftime("%Y%m%d")
    try:
        main()
    except SystemExit: raise
    except Exception:
        import traceback
        log("\n!!! 예외 중단:\n"+traceback.format_exc())
        save_report(stamp,gu,note="[상태: 실패/중단]"); raise
