# -*- coding: utf-8 -*-
r"""OSM 대구 가로수/나무 데이터 다운로드 (수종, 높이 정보 포함).
출력: data_clean\osm_trees_대구.gpkg  (EPSG:5179 투영)
"""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import osmnx as ox
import geopandas as gpd
import pandas as pd
import shapely

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "data_clean", "osm_trees_대구.gpkg")

# 수종별 수관폭(직경, m) — 그늘 버퍼 계산용
SPECIES_CROWN_WIDTH = {
    '느티나무': 18,
    '은행나무': 15,
    '플라타너스': 20,
    '벚나무': 10,
    '소나무': 12,
    '잣나무': 8,
    '자작나무': 10,
    '참나무': 16,
    'ginkgo': 15,
    'platanus': 20,
    'zelkova': 18,
}

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

    # OSM에서 나무 데이터 다운로드
    print("OSM 나무/가로수 데이터 다운로드 중... (Overpass)", flush=True)
    try:
        tags = {'natural': 'tree'}
        trees = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags=tags
        )
    except Exception as e:
        print(f"  오류: {e}", flush=True)
        return

    if trees.empty:
        print("  경고: 나무 데이터 없음", flush=True)
        return

    print(f"  원본: {len(trees)} 포인트/폴리곤", flush=True)

    # 포인트 또는 폴리곤 중심점으로 변환
    if trees.geometry.type.eq('Polygon').any():
        trees['geometry'] = trees.geometry.apply(lambda g: g.centroid if g.type == 'Polygon' else g)

    # 포인트만 필터링
    trees = trees[trees.geometry.type == 'Point'].copy()
    print(f"  포인트 필터: {len(trees)} 나무", flush=True)

    # 좌표계 통일
    trees = trees.to_crs("EPSG:5179")

    # 데이터 정제
    trees = trees.reset_index(drop=True)

    # 필요한 정보 추출
    if 'name' not in trees.columns:
        trees['name'] = None
    if 'species' not in trees.columns:
        trees['species'] = None
    if 'height' not in trees.columns:
        trees['height'] = None

    # 높이값 정제 (문자열 제거)
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

    trees['height'] = trees['height'].apply(parse_height)

    # 기본 높이 할당 (8m 기본값)
    trees.loc[trees['height'].isna(), 'height'] = 8.0

    # 수관폭 추정
    trees['crown_width'] = trees['species'].apply(
        lambda x: SPECIES_CROWN_WIDTH.get(x, 12) if pd.notna(x) else 12
    )

    # 최종 컬럼
    final_cols = ['geometry', 'height', 'crown_width']
    if 'name' in trees.columns:
        final_cols.insert(1, 'name')
    if 'species' in trees.columns:
        final_cols.insert(1, 'species')

    trees = trees[[c for c in final_cols if c in trees.columns]]

    # 저장
    trees.to_file(OUT, driver='GPKG', layer='trees', index=False)
    print(f"✓ 저장: {OUT}  ({len(trees)} 나무, {time.time()-t0:.0f}s)", flush=True)

if __name__ == "__main__":
    main()
