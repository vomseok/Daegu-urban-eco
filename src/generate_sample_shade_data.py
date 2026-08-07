# -*- coding: utf-8 -*-
r"""테스트용 모의 건물·가로수 데이터 생성 (실제 OSM 불가능한 환경용).
도로망 주변에 랜덤 배치된 건물과 가로수 생성.
출력: shade_buildings_대구.geojson, shade_trees_대구.geojson
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import Point, Polygon, LineString
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_road_network():
    """도로망 GeoJSON 로드"""
    geojson_path = os.path.join(PROJ, "data_clean", "sample_walk_network.geojson")
    if not os.path.exists(geojson_path):
        print(f"ERROR: {geojson_path} 없음", flush=True)
        return None

    road_gdf = gpd.read_file(geojson_path)
    print(f"✓ 도로망 로드: {len(road_gdf)} 세그먼트", flush=True)
    return road_gdf

def generate_buildings(road_gdf, num_buildings=500):
    """도로 근처에 랜덤 건물 배치"""
    np.random.seed(42)

    buildings = []
    buffer_distance = 50  # 도로로부터 50m 이내

    for idx in range(num_buildings):
        # 랜덤 도로 세그먼트 선택
        road_idx = np.random.randint(0, len(road_gdf))
        line = road_gdf.iloc[road_idx].geometry

        # 라인 위의 랜덤 포인트
        distance = np.random.uniform(0, line.length)
        point = line.interpolate(distance)

        # 옆으로 오프셋 (왼쪽/오른쪽)
        offset = np.random.choice([-1, 1]) * np.random.uniform(10, buffer_distance)

        # 수직 오프셋 적용
        x, y = point.x, point.y
        # 간단한 회전 (실제로는 라인 방향을 고려해야 함)
        angle = np.random.uniform(0, 2*np.pi)
        x_offset = offset * np.cos(angle)
        y_offset = offset * np.sin(angle)

        building_point = Point(x + x_offset, y + y_offset)

        # 건물 크기 (5~30m)
        width = np.random.uniform(5, 30)
        height = np.random.uniform(5, 40)

        # 정사각형 건물
        building_poly = Polygon([
            (building_point.x - width/2, building_point.y - width/2),
            (building_point.x + width/2, building_point.y - width/2),
            (building_point.x + width/2, building_point.y + width/2),
            (building_point.x - width/2, building_point.y + width/2),
        ])

        buildings.append({
            'geometry': building_poly,
            'height': height,
            'building': f'type_{np.random.randint(1, 5)}'
        })

    return gpd.GeoDataFrame(buildings, crs='EPSG:5179')

def generate_trees(road_gdf, num_trees=1000):
    """도로변에 랜덤 가로수 배치"""
    np.random.seed(123)

    species_list = ['느티나무', '은행나무', '플라타너스', '벚나무', '소나무', '자작나무']
    crown_widths = {
        '느티나무': 18,
        '은행나무': 15,
        '플라타너스': 20,
        '벚나무': 10,
        '소나무': 12,
        '자작나무': 10,
    }

    trees = []
    buffer_distance = 40

    for idx in range(num_trees):
        # 랜덤 도로 세그먼트
        road_idx = np.random.randint(0, len(road_gdf))
        line = road_gdf.iloc[road_idx].geometry

        # 라인 위의 랜덤 포인트
        distance = np.random.uniform(0, line.length)
        point = line.interpolate(distance)

        # 옆으로 오프셋 (도로변)
        offset = np.random.choice([-1, 1]) * np.random.uniform(3, buffer_distance)

        angle = np.random.uniform(0, 2*np.pi)
        x_offset = offset * np.cos(angle)
        y_offset = offset * np.sin(angle)

        tree_point = Point(point.x + x_offset, point.y + y_offset)

        # 수종 및 높이
        species = np.random.choice(species_list)
        height = np.random.uniform(6, 20)
        crown_width = crown_widths.get(species, 12)

        trees.append({
            'geometry': tree_point,
            'species': species,
            'height': height,
            'crown_width': crown_width
        })

    return gpd.GeoDataFrame(trees, crs='EPSG:5179')

def main():
    print("=" * 60)
    print("모의 그늘 데이터 생성 (테스트용)")
    print("=" * 60, flush=True)

    # 도로망 로드
    road_gdf = load_road_network()
    if road_gdf is None:
        return

    # 건물 생성
    print("\n[건물 생성]", flush=True)
    buildings = generate_buildings(road_gdf, num_buildings=500)
    buildings_path = os.path.join(PROJ, "data_clean", "shade_buildings_대구.geojson")
    buildings.to_file(buildings_path, driver='GeoJSON')
    print(f"✓ 저장: {buildings_path}  ({len(buildings)} 건물)", flush=True)

    # 가로수 생성
    print("\n[가로수 생성]", flush=True)
    trees = generate_trees(road_gdf, num_trees=1000)
    trees_path = os.path.join(PROJ, "data_clean", "shade_trees_대구.geojson")
    trees.to_file(trees_path, driver='GeoJSON')
    print(f"✓ 저장: {trees_path}  ({len(trees)} 나무)", flush=True)

    print("\n✓ 완료! 다음 단계: solar_position.py → merge_shade_layers.py", flush=True)

if __name__ == "__main__":
    main()
