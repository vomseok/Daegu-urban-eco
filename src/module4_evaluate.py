# -*- coding: utf-8 -*-
r"""
모듈4-E — 계획지표 재평가 (가이드라인 등급·지수·용어 적용)
============================================================
config\02_계획지표_가이드라인.md 의 기준을 기존 산출물에 적용해 전역·구군·격자로 재평가.
  · 접근성 4등급(≤5/≤10/≤15/>15분) → 우수/양호/보통/취약(녹지소외)
  · 연결성 5등급(전류밀도 임계 0.62/0.33/0.15/0.05) → 핵심연결축~연결단절 + 연결성지수(0~100)
  · 통합 우선순위(접근성×연결성 2×2) 구별 처방
입력:  outputs\<일자>\module4C_대구_{2019,2024}_전류밀도.tif
       outputs\<일자>\module4A_대구_{2019,2024}_접근시간.gpkg  (val,time_min)
       data_clean\districts_5179.gpkg
출력:  outputs\<일자>\module4_계획지표재평가.xlsx  + 등급지도 png
실행:  .venv\Scripts\python.exe src\module4_evaluate.py
"""
import os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features as rfeatures
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

# ── 기준(가이드라인) ─────────────────────────────────────────────────
ACC_BREAKS = [5, 10, 15]                       # 분
ACC_LABEL = {1:"Ⅰ우수(≤5분)", 2:"Ⅱ양호(≤10분)", 3:"Ⅲ보통(≤15분)", 4:"Ⅳ취약(>15분·소외)"}
CONN_BREAKS = [0.05, 0.15, 0.33, 0.62]         # 전류밀도(대구 백분위)
CONN_LABEL = {1:"1핵심연결축", 2:"2주요연결", 3:"3일반연결", 4:"4연결취약", 5:"5연결단절"}

def acc_grade(t):
    g = np.full(t.shape, np.nan)
    g[t <= ACC_BREAKS[2]] = 3; g[t <= ACC_BREAKS[1]] = 2; g[t <= ACC_BREAKS[0]] = 1
    g[t > ACC_BREAKS[2]] = 4
    return g

def conn_grade(a):
    g = np.full(a.shape, np.nan); v = np.isfinite(a)
    g[v & (a < CONN_BREAKS[0])] = 5
    g[v & (a >= CONN_BREAKS[0]) & (a < CONN_BREAKS[1])] = 4
    g[v & (a >= CONN_BREAKS[1]) & (a < CONN_BREAKS[2])] = 3
    g[v & (a >= CONN_BREAKS[2]) & (a < CONN_BREAKS[3])] = 2
    g[v & (a >= CONN_BREAKS[3])] = 1
    return g

def conn_index(a, ref_sorted):
    """연결성지수 0~100 = 2024 분포 대비 백분위."""
    out = np.full(a.shape, np.nan); v = np.isfinite(a)
    out[v] = np.searchsorted(ref_sorted, a[v]) / len(ref_sorted) * 100
    return out

def main():
    log(f"### 모듈4-E 계획지표 재평가  {datetime.date.today()}\n")
    dist = gpd.read_file(DIST, engine="pyogrio").reset_index(drop=True)
    dist["did"] = np.arange(1, len(dist)+1)

    # ── 연결성 래스터 로드·등급 ──
    with rasterio.open(p("module4C_대구_2019_전류밀도.tif")) as ds:
        c19 = ds.read(1); transform = ds.transform; shape = ds.shape
    with rasterio.open(p("module4C_대구_2024_전류밀도.tif")) as ds:
        c24 = ds.read(1)
    ref = np.sort(c24[np.isfinite(c24)])
    didr = rfeatures.rasterize(zip(dist.geometry, dist["did"]), out_shape=shape,
                               transform=transform, fill=0, dtype="int32")
    cg = {"2019": conn_grade(c19), "2024": conn_grade(c24)}
    cidx = {"2019": conn_index(c19, ref), "2024": conn_index(c24, ref)}

    # ── 접근성 셀 로드·등급 + 구 조인 ──
    acc = {}
    for y in ["2019", "2024"]:
        g = gpd.read_file(p(f"module4A_대구_{y}_접근시간.gpkg"), engine="pyogrio")
        g["cx"] = g.geometry.centroid.x.round(0); g["cy"] = g.geometry.centroid.y.round(0)
        acc[y] = g
    base = acc["2019"][["cx","cy","val","geometry"]].copy()
    base = base.merge(acc["2019"][["cx","cy","time_min"]].rename(columns={"time_min":"t19"}), on=["cx","cy"])
    base = base.merge(acc["2024"][["cx","cy","time_min"]].rename(columns={"time_min":"t24"}), on=["cx","cy"], how="left")
    cent = gpd.GeoDataFrame(base[["val","t19","t24"]].copy(),
                            geometry=gpd.points_from_xy(base["cx"], base["cy"]), crs=5179)
    cent = gpd.sjoin(cent, dist[["구군","geometry"]], how="left", predicate="within")
    for y, tc in [("2019","t19"),("2024","t24")]:
        cent[f"ag{y}"] = acc_grade(cent[tc].values)

    # ── 전역 요약 ──
    grows = []
    for y in ["2019","2024"]:
        w = cent["val"].values; t = cent[f"t{y[2:]}"].values; ok = np.isfinite(t)
        rec = {"연도": y, "10분도달인구%": round(w[ok&(t<=10)].sum()/w[ok].sum()*100,1),
               "녹지소외인구%(>15분)": round(w[ok&(t>15)].sum()/w[ok].sum()*100,1),
               "평균도보분": round(float(np.average(t[ok],weights=w[ok])),2)}
        vg = cg[y][np.isfinite(cg[y])]
        rec["핵심+주요연결축_면적ha"] = int((vg<=2).sum())
        rec["연결단절_면적ha"] = int((vg==5).sum())
        rec["평균연결성지수"] = round(float(np.nanmean(cidx[y])),1)
        grows.append(rec)
    glob = pd.DataFrame(grows)
    log("[전역 재평가]\n"+glob.to_string(index=False)+"\n")

    # ── 구군 접근성 등급분포 + 연결성 ──
    arows = []
    for gu, df in cent.groupby("구군"):
        w = df["val"].values; r = {"구군": gu, "인구": int(w.sum())}
        for y in ["2019","2024"]:
            t = df[f"t{y[2:]}"].values; ok=np.isfinite(t)
            r[f"10분도달%_{y}"] = round(w[ok&(t<=10)].sum()/w[ok].sum()*100,1)
            r[f"소외%_{y}"] = round(w[ok&(t>15)].sum()/w[ok].sum()*100,1)
        arows.append(r)
    acc_df = pd.DataFrame(arows).sort_values("10분도달%_2024")
    log("[구군 접근성 재평가]\n"+acc_df.to_string(index=False)+"\n")

    crows = []
    for _, d in dist.iterrows():
        m = (didr == d["did"])
        r = {"구군": d["구군"]}
        for y in ["2019","2024"]:
            g = cg[y]; mm = m & np.isfinite(g); tot = mm.sum()
            r[f"핵심+주요축%_{y}"] = round(float((mm & (g<=2)).sum()/tot*100),1) if tot else np.nan
            r[f"평균지수_{y}"] = round(float(np.nanmean(np.where(m, cidx[y], np.nan))),1)
        crows.append(r)
    conn_df = pd.DataFrame(crows).sort_values("평균지수_2024", ascending=False)
    log("[구군 연결성 재평가]\n"+conn_df.to_string(index=False)+"\n")

    # ── 통합 우선순위(2024, 구군 2×2) ──
    acc_kpi = acc_df.set_index("구군")["10분도달%_2024"]
    conn_kpi = conn_df.set_index("구군")["평균지수_2024"]
    amed = acc_kpi.median(); cmed = conn_kpi.median()
    prio = []
    for gu in acc_kpi.index:
        lowA = acc_kpi[gu] < amed; lowC = conn_kpi[gu] < cmed
        label = ("★최우선(공급+연결)" if lowA and lowC else
                 "공급 확충" if lowA and not lowC else
                 "연결 복원" if not lowA and lowC else "유지·관리")
        prio.append({"구군": gu, "10분도달%": acc_kpi[gu], "연결성지수": conn_kpi[gu], "처방": label})
    prio_df = pd.DataFrame(prio).sort_values("처방")
    log(f"[구군 우선순위 처방]  (기준: 접근성중앙값 {amed:.1f}%, 연결성중앙값 {cmed:.1f})\n"
        +prio_df.to_string(index=False)+"\n")

    # ── 엑셀 ──
    xlsx = p("module4_계획지표재평가.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        glob.to_excel(xw, sheet_name="전역", index=False)
        acc_df.to_excel(xw, sheet_name="구군_접근성등급", index=False)
        conn_df.to_excel(xw, sheet_name="구군_연결성등급", index=False)
        prio_df.to_excel(xw, sheet_name="구군_우선순위", index=False)
    log(f"✓ 엑셀: {xlsx}")

    # ── 지도: 접근성 4등급, 연결성 5등급(2024) ──
    b = rasterio.transform.array_bounds(shape[0], shape[1], transform)
    extent = (b[0], b[2], b[1], b[3])
    # 연결성 5등급
    cmap5 = mcolors.ListedColormap(["#006837","#66bd63","#fee08b","#f46d43","#a50026"])
    fig, ax = plt.subplots(figsize=(9,8)); ax.set_facecolor("#d9d9d9")
    ax.imshow(cg["2024"], cmap=cmap5, vmin=1, vmax=5, extent=extent, origin="upper")
    dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
    ax.set_title("대구 녹지 연결성 등급 (2024)"); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(handles=[Patch(color=c,label=CONN_LABEL[i+1]) for i,c in enumerate(cmap5.colors)],
              loc="lower left", fontsize=8, title="연결성 등급")
    fig.tight_layout(); fig.savefig(p("module4_연결성등급_2024.png"), dpi=140); plt.close(fig)
    # 접근성 4등급(거주격자)
    cmap4 = mcolors.ListedColormap(["#1a9850","#a6d96a","#fdae61","#d73027"])
    gdf = gpd.GeoDataFrame(base.copy(), geometry="geometry", crs=5179)
    gdf["ag"] = acc_grade(base["t24"].values)
    fig, ax = plt.subplots(figsize=(9,8))
    gdf.plot(column="ag", cmap=cmap4, vmin=1, vmax=4, ax=ax, markersize=2)
    dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
    ax.set_title("대구 녹지 접근성 등급 (2024, 거주격자)"); ax.set_xticks([]); ax.set_yticks([])
    ax.legend(handles=[Patch(color=c,label=ACC_LABEL[i+1]) for i,c in enumerate(cmap4.colors)],
              loc="lower left", fontsize=8, title="접근성 등급")
    fig.tight_layout(); fig.savefig(p("module4_접근성등급_2024.png"), dpi=140); plt.close(fig)
    log("✓ 등급지도 2종")
    log("모듈4-E 완료")

if __name__ == "__main__":
    main()
