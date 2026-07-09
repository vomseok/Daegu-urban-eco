# -*- coding: utf-8 -*-
r"""행정구역(구·군) 경계 레이어 생성 — 비오톱을 SIG_KOR_NM으로 융합.
출력: data_clean\districts_5179.gpkg  (8개 구·군 폴리곤)  ※ 지도 오버레이·전역 집계 재사용
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")

g = gpd.read_file(os.path.join(PROJ, "data_clean", "biotope_2019_5179.gpkg"),
                  engine="pyogrio", columns=["SIG_KOR_NM"])
g = g[g["SIG_KOR_NM"].notna()].copy()
print("융합 중...", flush=True)
d = g.dissolve(by="SIG_KOR_NM", as_index=False)
inv = ~d.geometry.is_valid
if inv.any():
    d.loc[inv, d.geometry.name] = d.loc[inv, d.geometry.name].make_valid()
d["area_ha"] = d.geometry.area / 10000.0
d = d.rename(columns={"SIG_KOR_NM": "구군"})
d[["구군", "area_ha", d.geometry.name]].to_file(OUT, driver="GPKG")
print(d[["구군", "area_ha"]].sort_values("area_ha", ascending=False).to_string(index=False))
print("✓ 저장:", OUT, flush=True)
