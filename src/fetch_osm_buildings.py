# -*- coding: utf-8 -*-
r"""OSM 대구 건물 데이터 다운로드 (높이 정보 포함).
출력: data_clean\osm_buildings_대구.gpkg  (EPSG:5179 투영)
"""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import osmnx as ox
import geopandas as gpd
import pandas as pd
import shapely

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "data_clean", "osm_buildings_대구.gpkg")

def main():
    t0 = time.time()

    # 대구 바운딩박스 로드
    bbox_file = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")
    if not os.path.exists(bbox_file):
        print(f"ERROR: {bbox_file} 없음", flush=True)
        return
    g = gpd.read_file(bbox_file, engine="pyogrio")
    b = g.total_bounds
    box = gpd.GeoSeries([shapely.geometry.box(*b)], crs=5179).to_crs(4326).total_bounds
    west, south, east, north = [float(x) for x in box]
    print(f"대구 bbox(4326): W{west:.4f} S{south:.4f} E{east:.4f} N{north:.4f}", flush=True)

    # OSM에서 건물 데이터 다운로드
    print("OSM 건물 데이터 다운로드 중... (Overpass)", flush=True)
    try:
        tags = {'building': True}
        buildings = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags=tags
        )
    except Exception as e:
        print(f"  오류: {e}", flush=True)
        return

    if buildings.empty:
        print("  경고: 건물 데이터 없음", flush=True)
        return

    print(f"  원본: {len(buildings)} 건물", flush=True)

    # 폴리곤만 필터링
    buildings = buildings[buildings.geometry.type == 'Polygon'].copy()
    print(f"  폴리곤 필터: {len(buildings)} 건물", flush=True)

    # 좌표계 통일
    buildings = buildings.to_crs("EPSG:5179")

    # 필요한 컬럼만 선택
    cols_to_keep = []
    if 'name' in buildings.columns:
        cols_to_keep.append('name')
    if 'height' in buildings.columns:
        cols_to_keep.append('height')
    if 'building:height' in buildings.columns:
        cols_to_keep.append('building:height')
    if 'building:levels' in buildings.columns:
        cols_to_keep.append('building:levels')
    if 'building' in buildings.columns:
        cols_to_keep.append('building')

    # 높이 정보 표준화
    if 'height' not in buildings.columns:
        buildings['height'] = None
    if 'building:height' in buildings.columns:
        buildings.loc[buildings['height'].isna(), 'height'] = buildings.loc[buildings['height'].isna(), 'building:height']

    # 높이값 숫자로 변환 (문자열 제거)
    def parse_height(h):
        if pd.isna(h):
            return None
        if isinstance(h, (int, float)):
            return float(h)
        try:
            s = str(h).split()[0]
            return float(s)
        except:
            return None

    buildings['height'] = buildings.get('height', None)
    buildings['height'] = buildings['height'].apply(parse_height)

    # 결측값 추정 (층수 × 3.5m)
    if 'building:levels' in buildings.columns:
        mask = buildings['height'].isna() & buildings['building:levels'].notna()
        buildings.loc[mask, 'height'] = buildings.loc[mask, 'building:levels'].apply(
            lambda x: float(x) * 3.5 if isinstance(x, (int, float, str)) and str(x).replace('.','',1).isdigit() else None
        )

    # 기본값 (5m) 할당
    buildings.loc[buildings['height'].isna(), 'height'] = 5.0

    # 최종 컬럼 정리
    final_cols = ['geometry', 'height']
    if 'name' in buildings.columns:
        final_cols.insert(1, 'name')
    if 'building' in buildings.columns:
        final_cols.insert(1, 'building')

    buildings = buildings[[c for c in final_cols if c in buildings.columns]]

    # 저장
    buildings.to_file(OUT, driver='GPKG', layer='buildings', index=False)
    print(f"✓ 저장: {OUT}  ({len(buildings)} 건물, {time.time()-t0:.0f}s)", flush=True)

if __name__ == "__main__":
    main()
