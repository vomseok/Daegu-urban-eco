# -*- coding: utf-8 -*-
"""툴체인 검증: 실제 비오톱 파일을 읽고 좌표계 인식·변환·한글속성을 확인."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd

SRC = r"D:\my Data\GIS\Data\Source\2_public D"
f1 = SRC + r"\대구시 비오톱 자료\05_비오톱평가 결과\비오톱 등급 평가 결과.shp"
f2 = SRC + r"\대구시 도시생태현황도 2차\01_최종비오톱 GIS파일\제2차 대구광역시 도시생태현황지도 성과품 보완\250225_제2차_대구광역시_최종비오톱평가도_보완_제출용.shp"

for tag, path, fld in [("1차(2019)", f1, "U소분류"), ("2차(2024~25)", f2, "유형소분류")]:
    g = gpd.read_file(path, rows=5, engine="pyogrio")
    print(f"=== {tag} ===")
    print("  좌표계(CRS):", g.crs)
    print("  EPSG:", g.crs.to_epsg() if g.crs else None)
    print("  도형형식:", g.geom_type.iloc[0], "| 컬럼수:", len(g.columns))
    # 한글 속성 표본
    if fld in g.columns:
        print(f"  {fld} 표본:", list(g[fld].head(3)))
    # 좌표변환 시험 → EPSG:5179 (UTM-K)
    g5179 = g.to_crs(5179)
    print("  →5179 변환 후 좌표(첫 도형 중심):",
          tuple(round(v,1) for v in g5179.geometry.iloc[0].centroid.coords[0]))
    print()
print("SMOKETEST OK")
