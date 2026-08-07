# -*- coding: utf-8 -*-
r"""건물·가로수 데이터를 도로망과 통합하는 전처리 스크립트.
입력: osm_buildings_대구.gpkg, osm_trees_대구.gpkg, osm_walk_대구.graphml
출력: shade_buildings_대구.geojson, shade_trees_대구.geojson (도로 인접성 필터)
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd
import networkx as nx
from shapely.geometry import box, Point
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_road_network():
    """도로망 그래프 로드"""
    graphml_path = os.path.join(PROJ, "data_clean", "osm_walk_대구.graphml")
    if not os.path.exists(graphml_path):
        print(f"ERROR: {graphml_path} 없음", flush=True)
        return None
    G = nx.read_graphml(graphml_path)
    print(f"✓ 도로망 로드: 노드 {G.number_of_nodes():,}, 엣지 {G.number_of_edges():,}", flush=True)
    return G

def graph_to_linestrings(G):
    """네트워크 그래프 → LineString GeoDataFrame 변환"""
    lines = []
    for u, v, key, data in G.edges(keys=True, data=True):
        geom = data.get('geometry', None)
        if geom is None:
            continue
        lines.append({
            'geometry': geom,
            'u': u, 'v': v,
            'length': data.get('length', 0),
            'walk_min': data.get('walk_min', 0)
        })
    return gpd.GeoDataFrame(lines, crs='EPSG:5179')

def filter_buildings_near_road(buildings_gdf, road_gdf, buffer_m=100):
    """도로 근처 건물만 필터링 (그늘 계산이 필요한 것만)"""
    road_buffer = road_gdf.geometry.unary_union.buffer(buffer_m)
    filtered = buildings_gdf[buildings_gdf.geometry.intersects(road_buffer)].copy()
    print(f"  건물: 원본 {len(buildings_gdf)} → 도로 근처 {len(filtered)}", flush=True)
    return filtered

def filter_trees_near_road(trees_gdf, road_gdf, buffer_m=100):
    """도로 근처 가로수만 필터링"""
    road_buffer = road_gdf.geometry.unary_union.buffer(buffer_m)
    filtered = trees_gdf[trees_gdf.geometry.intersects(road_buffer)].copy()
    print(f"  가로수: 원본 {len(trees_gdf)} → 도로 근처 {len(filtered)}", flush=True)
    return filtered

def main():
    print("=" * 60)
    print("도로망과 그늘 데이터 통합 준비")
    print("=" * 60, flush=True)

    # 도로망 로드
    G = load_road_network()
    if G is None:
        return
    road_gdf = graph_to_linestrings(G)
    print(f"✓ 도로 라인: {len(road_gdf)} 세그먼트", flush=True)

    # 건물 데이터 로드
    buildings_path = os.path.join(PROJ, "data_clean", "osm_buildings_대구.gpkg")
    if os.path.exists(buildings_path):
        print("\n[건물 데이터]", flush=True)
        buildings = gpd.read_file(buildings_path, engine="pyogrio")
        filtered_buildings = filter_buildings_near_road(buildings, road_gdf, buffer_m=100)
        out_path = os.path.join(PROJ, "data_clean", "shade_buildings_대구.geojson")
        filtered_buildings.to_file(out_path, driver='GeoJSON')
        print(f"✓ 저장: {out_path}", flush=True)
    else:
        print(f"  경고: {buildings_path} 없음 (fetch_osm_buildings.py 실행 필요)", flush=True)

    # 가로수 데이터 로드
    trees_path = os.path.join(PROJ, "data_clean", "osm_trees_대구.gpkg")
    if os.path.exists(trees_path):
        print("\n[가로수 데이터]", flush=True)
        trees = gpd.read_file(trees_path, engine="pyogrio")
        filtered_trees = filter_trees_near_road(trees, road_gdf, buffer_m=100)
        out_path = os.path.join(PROJ, "data_clean", "shade_trees_대구.geojson")
        filtered_trees.to_file(out_path, driver='GeoJSON')
        print(f"✓ 저장: {out_path}", flush=True)
    else:
        print(f"  경고: {trees_path} 없음 (fetch_osm_trees.py 실행 필요)", flush=True)

    print("\n✓ 완료!", flush=True)

if __name__ == "__main__":
    main()
