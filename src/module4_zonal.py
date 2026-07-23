# -*- coding: utf-8 -*-
r"""
모듈4-Z — 3공간단위 집계 (전역·구군·100m격자)
==============================================
전역 연결성(tif)·접근성(gpkg)을 읽어 전역/구군/격자 3단위로 집계하고 변화(2024-2019)를 낸다.
입력:  outputs\<일자>\module4C_대구_{2019,2024}_전류밀도.tif
       outputs\<일자>\module4A_대구_{2019,2024}_접근시간.gpkg   (val=인구, time_min)
       outputs\<일자>\module4C_대구_연결성요약.csv               (R_eff)
       data_clean\districts_5179.gpkg
출력:  outputs\<일자>\module4_3단위요약.xlsx  + 전역 연결성/접근성 지도·차이맵 png
실행:  .venv\Scripts\python.exe src\module4_zonal.py
"""
import os, sys, io, datetime, platform
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features as rfeatures
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patheffects import withStroke

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = "20260705"
OUTDIR = os.path.join(PROJ, "outputs", STAMP)
DIST = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")
THRESH = [5, 10, 15]
def p(f): return os.path.join(OUTDIR, f)

# 한글 폰트 설정 (Windows/Linux 모두 지원)
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

plt.rcParams["axes.unicode_minus"] = False

def log(m=""): print(m, flush=True)

# ── 연결성: 래스터 로드 + 구별 zonal 평균 ────────────────────────────
def conn_rasters(dist):
    arrs = {}
    with rasterio.open(p("module4C_대구_2019_전류밀도.tif")) as ds:
        arrs["2019"] = ds.read(1); transform = ds.transform; shape = ds.shape
    with rasterio.open(p("module4C_대구_2024_전류밀도.tif")) as ds2:
        arrs["2024"] = ds2.read(1)
    # 구 id 래스터(동일 격자)
    dist = dist.reset_index(drop=True).copy(); dist["did"] = np.arange(1, len(dist)+1)
    did = rfeatures.rasterize(zip(dist.geometry, dist["did"]), out_shape=shape,
                              transform=transform, fill=0, dtype="int32")
    rows = []
    for _, r in dist.iterrows():
        m = (did == r["did"])
        rec = {"구군": r["구군"]}
        for y in ["2019", "2024"]:
            a = arrs[y]; mm = m & np.isfinite(a)
            rec[f"평균전류밀도_{y}"] = round(float(a[mm].mean()), 4) if mm.any() else np.nan
        rec["변화"] = round(rec["평균전류밀도_2024"] - rec["평균전류밀도_2019"], 4)
        rows.append(rec)
    return pd.DataFrame(rows), arrs, transform, shape

# ── 접근성: 인구셀 → 구별 인구가중 집계 ──────────────────────────────
def access_zonal(dist):
    g19 = gpd.read_file(p("module4A_대구_2019_접근시간.gpkg"), engine="pyogrio")
    g24 = gpd.read_file(p("module4A_대구_2024_접근시간.gpkg"), engine="pyogrio")
    g19["cx"] = g19.geometry.centroid.x.round(0); g19["cy"] = g19.geometry.centroid.y.round(0)
    g24c = g24.copy(); g24c["cx"] = g24c.geometry.centroid.x.round(0); g24c["cy"] = g24c.geometry.centroid.y.round(0)
    m = g19.merge(g24c[["cx", "cy", "time_min"]].rename(columns={"time_min": "t24"}),
                  on=["cx", "cy"], how="left").rename(columns={"time_min": "t19"})
    # 구 공간조인(셀 중심)
    cent = gpd.GeoDataFrame(m[["val", "t19", "t24"]].copy(),
                            geometry=gpd.points_from_xy(m["cx"], m["cy"]), crs=5179)
    j = gpd.sjoin(cent, dist[["구군", "geometry"]], how="left", predicate="within")
    def agg(df, tcol):
        w = df["val"].values; t = df[tcol].values; ok = np.isfinite(t) & np.isfinite(w)
        wm = float(np.average(t[ok], weights=w[ok])) if ok.any() else np.nan
        rec = {"인구가중평균_분": round(wm, 2)}
        for T in THRESH:
            rec[f"{T}분내%"] = round(float(w[ok & (t <= T)].sum()/w[ok].sum()*100), 1) if ok.any() else np.nan
        return rec
    rows = []
    for gu, df in j.groupby("구군"):
        r = {"구군": gu, "인구": int(df["val"].sum())}
        a19 = agg(df, "t19"); a24 = agg(df, "t24")
        r["평균_2019"] = a19["인구가중평균_분"]; r["평균_2024"] = a24["인구가중평균_분"]
        r["평균변화"] = round(a24["인구가중평균_분"] - a19["인구가중평균_분"], 2)
        r["10분내%_2019"] = a19["10분내%"]; r["10분내%_2024"] = a24["10분내%"]
        rows.append(r)
    return pd.DataFrame(rows).sort_values("인구", ascending=False), m

# ── 전역 요약 ─────────────────────────────────────────────────────────
def global_summary(conn_arrs, acc_m):
    reff = pd.read_csv(p("module4C_대구_연결성요약.csv"), encoding="utf-8-sig").set_index("연도")
    rows = []
    for y in ["2019", "2024"]:
        a = conn_arrs[y]; t = acc_m[f"t{y[2:]}"].values; w = acc_m["val"].values
        ok = np.isfinite(t)
        rec = {"연도": y,
               "연결성_평균전류밀도": round(float(np.nanmean(a)), 4),
               "연결성_유효저항Reff": float(reff.loc[int(y), "평균유효저항"]),
               "접근성_인구가중평균분": round(float(np.average(t[ok], weights=w[ok])), 2)}
        for T in THRESH:
            rec[f"접근성_{T}분내%"] = round(float(w[ok & (t <= T)].sum()/w[ok].sum()*100), 1)
        rows.append(rec)
    df = pd.DataFrame(rows)
    return df

# ── 지도: 전역 + 차이맵 ───────────────────────────────────────────────
def citymap_conn(arrs, transform, shape, dist):
    b = rasterio.transform.array_bounds(shape[0], shape[1], transform)
    extent = (b[0], b[2], b[1], b[3])
    for y in ["2019", "2024"]:
        a = arrs[y]; vmax = np.nanpercentile(a, 98)
        fig, ax = plt.subplots(figsize=(9, 8)); ax.set_facecolor("#d9d9d9")
        im = ax.imshow(a, cmap="magma", extent=extent, origin="upper", vmin=0, vmax=vmax)
        dist.boundary.plot(ax=ax, color="cyan", linewidth=0.7)
        for idx, row in dist.iterrows():
            centroid = row.geometry.centroid
            t = ax.text(centroid.x, centroid.y, row["구군"],
                       fontsize=15, ha="center", va="center",
                       color="white")
            t.set_path_effects([withStroke(linewidth=3, foreground="black")])
        ax.set_title(f"대구 녹지 연결성(전류밀도) {y}"); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.6, label="전류밀도")
        fig.tight_layout(); fig.savefig(p(f"module4_대구_연결성_{y}.png"), dpi=140); plt.close(fig)
    d = arrs["2024"] - arrs["2019"]; v = np.nanpercentile(np.abs(d), 98)
    fig, ax = plt.subplots(figsize=(9, 8)); ax.set_facecolor("#d9d9d9")
    im = ax.imshow(d, cmap="RdBu", extent=extent, origin="upper", vmin=-v, vmax=v)
    dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
    for idx, row in dist.iterrows():
        centroid = row.geometry.centroid
        t = ax.text(centroid.x, centroid.y, row["구군"],
                   fontsize=15, ha="center", va="center",
                   color="white")
        t.set_path_effects([withStroke(linewidth=3, foreground="black")])
    ax.set_title("대구 연결성 변화 (2024-2019)\n파랑=증가, 빨강=감소"); ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.6, label="Δ전류밀도")
    fig.tight_layout(); fig.savefig(p("module4_대구_연결성_차이.png"), dpi=140); plt.close(fig)
    log("  ✓ 연결성 전역·차이맵")

def citymap_access(m, dist):
    gdf = gpd.GeoDataFrame(m.copy(), geometry=gpd.points_from_xy(m["cx"], m["cy"]), crs=5179)
    for y, col in [("2019", "t19"), ("2024", "t24")]:
        fig, ax = plt.subplots(figsize=(9, 8))
        gdf.assign(t=np.clip(gdf[col], 0, 30)).plot(column="t", cmap="RdYlGn_r", ax=ax,
              markersize=1, vmin=0, vmax=30, legend=True,
              legend_kwds={"label": "녹지까지 도보(분)", "shrink": 0.6, "extend": "max"})
        dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
        for idx, row in dist.iterrows():
            centroid = row.geometry.centroid
            t = ax.text(centroid.x, centroid.y, row["구군"],
                       fontsize=15, ha="center", va="center",
                       color="white")
            t.set_path_effects([withStroke(linewidth=3, foreground="black")])
        ax.set_title(f"대구 녹지 접근성(도보, 거주격자) {y}"); ax.set_xticks([]); ax.set_yticks([])
        fig.tight_layout(); fig.savefig(p(f"module4_대구_접근성_{y}.png"), dpi=140); plt.close(fig)
    gdf["dt"] = gdf["t24"] - gdf["t19"]; v = float(np.nanpercentile(np.abs(gdf["dt"].dropna()), 98)) or 1
    fig, ax = plt.subplots(figsize=(9, 8))
    gdf.plot(column="dt", cmap="RdBu_r", ax=ax, markersize=1, vmin=-v, vmax=v, legend=True,
             legend_kwds={"label": "Δ도보(분) 2024-2019", "shrink": 0.6})
    dist.boundary.plot(ax=ax, color="black", linewidth=0.7)
    for idx, row in dist.iterrows():
        centroid = row.geometry.centroid
        t = ax.text(centroid.x, centroid.y, row["구군"],
                   fontsize=15, ha="center", va="center",
                   color="white")
        t.set_path_effects([withStroke(linewidth=3, foreground="black")])
    ax.set_title("대구 접근성 변화 (2024-2019)\n파랑=개선(단축), 빨강=악화(증가)"); ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(p("module4_대구_접근성_차이.png"), dpi=140); plt.close(fig)
    log("  ✓ 접근성 전역·차이맵")

def main():
    log(f"### 모듈4-Z 3공간단위 집계  {datetime.date.today()}\n")
    dist = gpd.read_file(DIST, engine="pyogrio")
    log("[연결성 구별 집계]")
    conn_df, arrs, transform, shape = conn_rasters(dist)
    log(conn_df.to_string(index=False))
    log("\n[접근성 구별 집계]")
    acc_df, acc_m = access_zonal(dist)
    log(acc_df.to_string(index=False))
    log("\n[전역 요약]")
    glob = global_summary(arrs, acc_m)
    log(glob.to_string(index=False))
    log("\n[지도 생성]")
    citymap_conn(arrs, transform, shape, dist)
    citymap_access(acc_m, dist)
    # 엑셀
    xlsx = p("module4_3단위요약.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        glob.to_excel(xw, sheet_name="전역", index=False)
        conn_df.to_excel(xw, sheet_name="구군_연결성", index=False)
        acc_df.to_excel(xw, sheet_name="구군_접근성", index=False)
    log(f"\n✓ 엑셀: {xlsx}")
    log("모듈4-Z 완료")

if __name__ == "__main__":
    main()
