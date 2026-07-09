# -*- coding: utf-8 -*-
r"""
모듈4-K — 연결성 계획도 정제 (녹지 마스크 반영) + 코리더 보전·복원 액션맵
==========================================================================
문제: 전류밀도 등급도에서 큰 산림 '내부'가 저전류→'연결단절'로 오독됨(실제는 건강한 코어).
해결:
  옵션1(정제 계획도): 녹지 멤버십을 반영해 4계열로 재분류
     A 핵심 생태코리더(grade1-2) · B 녹지 코어/내부(녹지, 저전류) · C 매트릭스 일반(비녹지 중전류) · D 매트릭스 취약·단절(비녹지 저전류)
  옵션2(액션맵): 보전=핵심 생태코리더, 복원후보=녹지 인접(≤300m) 시가지 단절지만 강조.
입력:  outputs\<일자>\module4C_대구_2024_전류밀도.tif
       data_clean\biotope_2024_5179.gpkg + config\crosswalk\통합비교유형_2024.csv (녹지마스크)
       data_clean\districts_5179.gpkg
출력:  outputs\<일자>\module4_연결성계획도_정제_2024.png · module4_코리더_보전복원_2024.png (+ 요약)
실행:  .venv\Scripts\python.exe src\module4_corridor.py
"""
import os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
from rasterio import features as rfeatures
from scipy.ndimage import distance_transform_edt
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors as mcolors
from matplotlib.patches import Patch

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(PROJ, "outputs", datetime.date.today().strftime("%Y%m%d"))
DIST = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")
def p(f): return os.path.join(OUTDIR, f)
def log(m=""): print(m, flush=True)

fp = r"C:\Windows\Fonts\malgun.ttf"
if os.path.exists(fp):
    font_manager.fontManager.addfont(fp)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"] = False

GREEN = {"산림", "초지·조성녹지", "수계·습지"}
CONN_BREAKS = [0.05, 0.15, 0.33, 0.62]     # grade 경계(가이드라인)
RESTORE_DIST_M = 300                        # 복원후보: 녹지에서 이 거리내 시가지
BAD = {"대분류","중분류","소분류","세분류","유형","미분류"}

def green_mask(shape, transform):
    g = gpd.read_file(os.path.join(PROJ,"data_clean","biotope_2024_5179.gpkg"),
                      engine="pyogrio", columns=["유형중분류"])
    mp = pd.read_csv(os.path.join(PROJ,"config","crosswalk","통합비교유형_2024.csv"), encoding="utf-8-sig")
    mapping = dict(zip(mp["원유형"].astype(str), mp["통합비교유형"].astype(str)))
    s = (g["유형중분류"].astype("string").str.replace(r"\s+"," ",regex=True).str.strip().replace({"":pd.NA}))
    s = s.mask(s.isin(BAD | {"유형중분류"}))
    g["통합"] = s.map(mapping)
    grn = g[g["통합"].isin(GREEN)]
    inv = ~grn.geometry.is_valid
    if inv.any(): grn.loc[inv, grn.geometry.name] = grn.loc[inv, grn.geometry.name].make_valid()
    m = rfeatures.rasterize(((geom,1) for geom in grn.geometry), out_shape=shape,
                            transform=transform, fill=0, dtype="uint8").astype(bool)
    return m

def main():
    log(f"### 모듈4-K 연결성 계획도 정제·액션맵  {datetime.date.today()}\n")
    with rasterio.open(p("module4C_대구_2024_전류밀도.tif")) as ds:
        a = ds.read(1); transform = ds.transform; shape = ds.shape
    valid = np.isfinite(a)
    grn = green_mask(shape, transform)
    log(f"녹지 셀 {int(grn.sum()):,} / 유효 {int(valid.sum()):,}")

    # grade (1=고전류 핵심 … 5=저전류)
    g = np.full(shape, np.nan)
    g[valid & (a < CONN_BREAKS[0])] = 5
    g[valid & (a >= CONN_BREAKS[0]) & (a < CONN_BREAKS[1])] = 4
    g[valid & (a >= CONN_BREAKS[1]) & (a < CONN_BREAKS[2])] = 3
    g[valid & (a >= CONN_BREAKS[2]) & (a < CONN_BREAKS[3])] = 2
    g[valid & (a >= CONN_BREAKS[3])] = 1

    # ── 옵션1: 정제 4계열 (A핵심축 B녹지코어 C매트릭스일반 D매트릭스취약단절) ──
    cls = np.full(shape, np.nan)
    core = valid & np.isin(g, [1,2])
    cls[valid & grn] = 2                       # 기본 녹지=코어/내부
    cls[valid & ~grn] = 3                       # 기본 비녹지=매트릭스 일반
    cls[valid & ~grn & np.isin(g,[4,5])] = 4    # 비녹지 저전류=매트릭스 취약·단절
    cls[core] = 1                               # 핵심 생태코리더(녹지·비녹지 무관 최우선)
    dist = gpd.read_file(DIST, engine="pyogrio")

    b = rasterio.transform.array_bounds(shape[0], shape[1], transform); extent=(b[0],b[2],b[1],b[3])
    cmap1 = mcolors.ListedColormap(["#006837","#a1d99b","#ffffcc","#d73027"])
    fig, ax = plt.subplots(figsize=(9,8)); ax.set_facecolor("#e8e8e8")
    ax.imshow(cls, cmap=cmap1, vmin=1, vmax=4, extent=extent, origin="upper")
    dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
    ax.set_title("대구 녹지 연결성 계획도(정제) 2024\n녹지 멤버십 반영 — 숲 내부=녹지코어"); ax.set_xticks([]); ax.set_yticks([])
    labs=["A 핵심 생태코리더(보전)","B 녹지 코어/내부(양호)","C 매트릭스 일반","D 매트릭스 취약·단절(복원 관심)"]
    ax.legend(handles=[Patch(color=c,label=l) for c,l in zip(cmap1.colors,labs)], loc="lower left", fontsize=8)
    fig.tight_layout(); fig.savefig(p("module4_연결성계획도_정제_2024.png"), dpi=140); plt.close(fig)

    # ── 옵션2: 액션맵 (흐름 기반 표적화) ──
    dgreen = distance_transform_edt(~grn) * 100.0     # 각 셀→최근접 녹지 거리(m)
    green_cor = core & grn                             # 보전: 녹지 코리더
    urban_pinch = core & ~grn                          # 최우선 복원: 고전류가 시가지 관통(병목)
    weak_link = valid & ~grn & (g == 3) & (dgreen <= RESTORE_DIST_M) & (dgreen > 0)  # 강화: 취약 연결
    act = np.full(shape, np.nan)
    act[valid] = 0
    act[weak_link] = 3
    act[green_cor] = 1
    act[urban_pinch] = 2                                # 병목이 가장 위에 보이도록
    cmap2 = mcolors.ListedColormap(["#eeeeee","#006837","#d73027","#fdae61"])
    fig, ax = plt.subplots(figsize=(9,8)); ax.set_facecolor("#ffffff")
    ax.imshow(act, cmap=cmap2, vmin=0, vmax=3, extent=extent, origin="upper")
    dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
    ax.set_title("대구 녹지 코리더 보전·복원 액션맵 2024"); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(handles=[Patch(color="#006837",label="보전: 녹지 핵심 코리더"),
                       Patch(color="#d73027",label="★최우선 복원: 도시 병목(핀치포인트)"),
                       Patch(color="#fdae61",label="강화 후보: 취약 연결(녹지 300m내)")],
              loc="lower left", fontsize=9)
    fig.tight_layout(); fig.savefig(p("module4_코리더_보전복원_2024.png"), dpi=140); plt.close(fig)

    # 면적 요약(1셀=1ha)
    summ = pd.DataFrame([
        {"구분":"[정제도] A 핵심 생태코리더","면적_ha":int(np.nansum(cls==1))},
        {"구분":"[정제도] B 녹지 코어/내부","면적_ha":int(np.nansum(cls==2))},
        {"구분":"[정제도] C 매트릭스 일반","면적_ha":int(np.nansum(cls==3))},
        {"구분":"[정제도] D 매트릭스 취약·단절","면적_ha":int(np.nansum(cls==4))},
        {"구분":"[액션] 보전: 녹지 코리더","면적_ha":int(green_cor.sum())},
        {"구분":"[액션] ★최우선 복원: 도시 병목","면적_ha":int(urban_pinch.sum())},
        {"구분":"[액션] 강화 후보: 취약 연결","면적_ha":int(weak_link.sum())},
    ])
    log(summ.to_string(index=False))
    summ.to_csv(p("module4_코리더_면적요약.csv"), index=False, encoding="utf-8-sig")
    log("✓ 정제 계획도 + 액션맵 + 면적요약")
    log("모듈4-K 완료")

if __name__ == "__main__":
    main()
