# -*- coding: utf-8 -*-
r"""모듈4 지도 재렌더 — 행정구역 경계 오버레이 + 흰 공백 범례.
기존 산출물(접근성 gpkg, 연결성 tif)을 읽어 다시 그린다(분석 재실행 없음).
실행: .venv\Scripts\python.exe src\render_module4_maps.py [구이름]  (기본 수성구)
"""
import os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import geopandas as gpd
import rasterio
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(PROJ, "outputs", datetime.date.today().strftime("%Y%m%d"))
DIST = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")

fp = r"C:\Windows\Fonts\malgun.ttf"
if os.path.exists(fp):
    font_manager.fontManager.addfont(fp)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"] = False

def setup_ax(ax, dpoly_all, gu, pad=800):
    dpoly_all.boundary.plot(ax=ax, color="black", linewidth=0.8, zorder=5)
    row = dpoly_all[dpoly_all["구군"] == gu]
    row.boundary.plot(ax=ax, color="black", linewidth=1.8, zorder=6)
    minx, miny, maxx, maxy = row.total_bounds
    ax.set_xlim(minx-pad, maxx+pad); ax.set_ylim(miny-pad, maxy+pad)
    # 구 이름 라벨
    for _, r in dpoly_all.iterrows():
        c = r.geometry.representative_point()
        if minx-pad < c.x < maxx+pad and miny-pad < c.y < maxy+pad:
            ax.annotate(r["구군"], (c.x, c.y), ha="center", fontsize=8,
                        color="black", zorder=7,
                        path_effects=None)
    ax.set_xticks([]); ax.set_yticks([])

def render_access(gu, dist):
    for year in ["2019", "2024"]:
        g = os.path.join(OUTDIR, f"module4A_{gu}_{year}_접근시간.gpkg")
        if not os.path.exists(g):
            print("없음:", g); continue
        cells = gpd.read_file(g, engine="pyogrio")
        cells["t"] = np.clip(cells["time_min"], 0, 30)
        fig, ax = plt.subplots(figsize=(8, 8))
        cells.plot(column="t", cmap="RdYlGn_r", ax=ax, vmin=0, vmax=30, zorder=2,
                   legend=True, legend_kwds={"label": "최근접 녹지까지 도보시간(분)",
                                             "shrink": 0.55, "extend": "max"})
        setup_ax(ax, dist, gu)
        ax.set_title(f"{gu} 녹지 접근성(도보) {year}\n(색칠=거주 100m격자, 검은선=행정구역)")
        # 흰 공백 범례
        leg = ax.legend(handles=[Patch(facecolor="white", edgecolor="gray",
                        label="흰 공백 = 인구 없음\n(산림·하천·농경·공업 등 비거주지)")],
                        loc="lower left", fontsize=9, framealpha=0.9)
        leg.set_zorder(10)
        out = os.path.join(OUTDIR, f"module4A_{gu}_{year}_접근시간_경계.png")
        fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
        print("✓", out)

def render_conn(gu, dist):
    for year in ["2019", "2024"]:
        t = os.path.join(OUTDIR, f"module4C_{gu}_{year}_전류밀도.tif")
        if not os.path.exists(t):
            print("없음:", t); continue
        with rasterio.open(t) as ds:
            arr = ds.read(1); b = ds.bounds
        extent = (b.left, b.right, b.bottom, b.top)
        vmax = np.nanpercentile(arr, 98) if np.isfinite(arr).any() else 1
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.set_facecolor("#d9d9d9")           # NoData 배경(연회색)
        im = ax.imshow(arr, cmap="magma", extent=extent, origin="upper",
                       vmin=0, vmax=vmax, zorder=2)
        setup_ax(ax, dist, gu)
        ax.set_title(f"{gu} 녹지 연결성(회로이론 전류밀도) {year}\n(밝을수록 코리더/핀치포인트)")
        cb = fig.colorbar(im, ax=ax, shrink=0.55, label="전류밀도(연결성)")
        leg = ax.legend(handles=[Patch(facecolor="#d9d9d9", edgecolor="gray",
                        label="회색 = 대구 데이터 밖(NoData)")],
                        loc="lower left", fontsize=9, framealpha=0.9)
        leg.set_zorder(10)
        out = os.path.join(OUTDIR, f"module4C_{gu}_{year}_전류밀도_경계.png")
        fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
        print("✓", out)

if __name__ == "__main__":
    gu = sys.argv[1] if len(sys.argv) > 1 else "수성구"
    dist = gpd.read_file(DIST, engine="pyogrio")
    render_access(gu, dist)
    render_conn(gu, dist)
    print("완료")
