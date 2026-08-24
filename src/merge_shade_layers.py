# -*- coding: utf-8 -*-
r"""건물·가로수 그늘을 도로망과 통합하여 경로 계산용 그늘 가중치 생성.
출력: shade_score_roads_대구.geojson (시간대별 그늘 점수)
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import pandas as pd
from solar_position import solar_position_simple, shadow_length, DAEGU_LAT, DAEGU_LON

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_data():
    """모든 그늘 데이터 로드 (OSM + 도시생태현황도)"""
    print("[데이터 로드]", flush=True)

    import osmnx as ox

    osm_walk_path = os.path.join(PROJ, "data_clean", "osm_walk_대구.graphml")
    if os.path.exists(osm_walk_path):
        print(f"  OSM 보행도로 로드 중...", flush=True)
        try:
            G = ox.load_graphml(osm_walk_path)
            G = ox.project_graph(G, to_crs="EPSG:5179")
        except:
            # graphml이 이미 EPSG:5179로 저장되어 있을 수 있음
            G = ox.load_graphml(osm_walk_path)

        edges_data = []
        for u, v, key, data in G.edges(keys=True, data=True):
            geom = data.get('geometry')
            if geom is None:
                # geometry가 없으면 노드로부터 생성
                from shapely.geometry import LineString
                u_node = G.nodes[u]
                v_node = G.nodes[v]
                geom = LineString([(u_node['x'], u_node['y']), (v_node['x'], v_node['y'])])
            edges_data.append({
                'geometry': geom,
                'length': data.get('length', 0),
                'u': u, 'v': v
            })
        roads = gpd.GeoDataFrame(edges_data, crs='EPSG:5179')
    else:
        raise FileNotFoundError(f"{osm_walk_path} 없음")

    # 2. OSM 건물
    buildings_path = os.path.join(PROJ, "data_clean", "osm_buildings_대구.gpkg")
    buildings = gpd.read_file(buildings_path)
    buildings['height'] = buildings.get('height', 10).fillna(10)

    # 3. OSM 가로수 + 도시생태현황도 띠녹지 병합
    osm_trees_path = os.path.join(PROJ, "data_clean", "osm_trees_대구.gpkg")
    ribbon_path = os.path.join(PROJ, "data_clean", "ribbon_green_대구.gpkg")

    osm_trees = gpd.read_file(osm_trees_path)
    osm_trees['crown_width'] = osm_trees.get('crown:diameter', 15).fillna(15)
    print(f"  OSM 가로수: {len(osm_trees)}개", flush=True)

    trees_data = []
    # OSM 가로수 추가
    for idx, tree in osm_trees.iterrows():
        trees_data.append({'geometry': tree.geometry, 'crown_width': tree.get('crown_width', 15)})

    # 도시생태현황도 띠녹지 추가 (폴리곤 중심점으로 포인트화)
    if os.path.exists(ribbon_path):
        ribbon = gpd.read_file(ribbon_path)
        for idx, row in ribbon.iterrows():
            centroid = row.geometry.centroid
            trees_data.append({'geometry': centroid, 'crown_width': 20})
        print(f"  도시생태현황도 띠녹지: {len(ribbon)}개", flush=True)

    trees = gpd.GeoDataFrame(trees_data, crs='EPSG:5179')

    print(f"  도로: {len(roads)}, 건물: {len(buildings)}, 녹지: {len(trees)}", flush=True)
    return roads, buildings, trees

def building_shade_on_road(road_geom, building_geom, building_height, hour):
    """건물이 도로에 드리우는 그늘 계산.

    건물의 그림자 영역이 도로와 교차하는 비율을 반환.
    """
    from datetime import datetime
    import pytz

    # 태양 위치 계산 (간단히 평면 가정)
    dt = datetime(2024, 6, 21, hour=hour, tzinfo=pytz.timezone('Asia/Seoul'))
    dt_utc = dt.astimezone(pytz.UTC)
    altitude, azimuth = solar_position_simple(DAEGU_LAT, DAEGU_LON, dt_utc)

    if altitude <= 0:
        return 0.0  # 해가 지면 그늘 없음

    # 그림자 길이
    shadow_len = shadow_length(building_height, altitude)
    if shadow_len >= 1000:  # 너무 길면 무시
        return 0.0

    # 간단한 접근: 건물 주변 버퍼가 도로와 겹치는 비율
    building_buffer = building_geom.buffer(shadow_len)
    if not building_buffer.intersects(road_geom):
        return 0.0

    intersection = building_buffer.intersection(road_geom)
    road_coverage = intersection.length / road_geom.length
    return min(1.0, road_coverage)

def tree_shade_on_road(road_geom, tree_point, crown_width, hour):
    """가로수가 도로에 드리우는 그늘 계산.

    수관 폭의 원형 버퍼를 도로와 교차시켜 비율 반환.
    """
    # 나무 수관을 원형 버퍼로 모델링 (시간에 무관)
    tree_buffer = tree_point.buffer(crown_width / 2)
    if not tree_buffer.intersects(road_geom):
        return 0.0

    intersection = tree_buffer.intersection(road_geom)
    road_coverage = intersection.length / road_geom.length
    return min(1.0, road_coverage)

def calculate_shade_scores(roads, buildings, trees, hour_list=None):
    """모든 도로에 대한 시간대별 그늘 점수 계산 (공간 인덱싱 사용).

    Returns
    -------
    pd.DataFrame
        각 도로의 시간대별 그늘 점수 (0~100)
    """
    if hour_list is None:
        hour_list = [9, 12, 15]  # 테스트: 오전, 정오, 오후

    print(f"\n[그늘 점수 계산] 시간대: {hour_list}", flush=True)

    shade_data = []

    # 공간 인덱싱 생성
    spatial_index_bldg = buildings.sindex
    spatial_index_tree = trees.sindex

    for idx, road in roads.iterrows():
        if idx % 500 == 0:
            print(f"  진행: {idx}/{len(roads)}", flush=True)

        road_geom = road.geometry
        road_scores = {'road_id': idx, 'geometry': road_geom}

        # 도로 주변 건물/가로수만 조회 (버퍼 300m)
        buffer_geom = road_geom.buffer(300)
        bldg_indices = list(spatial_index_bldg.intersection(buffer_geom.bounds))
        tree_indices = list(spatial_index_tree.intersection(buffer_geom.bounds))

        for hour in hour_list:
            # 건물 그늘 (근처 건물만)
            building_shade = 0
            for i in bldg_indices:
                try:
                    bldg = buildings.iloc[i]
                    shade = building_shade_on_road(road_geom, bldg.geometry, bldg['height'], hour)
                    building_shade = max(building_shade, shade)
                except:
                    pass

            # 가로수 그늘 (근처 가로수만)
            tree_shade = 0
            for i in tree_indices:
                try:
                    tree = trees.iloc[i]
                    shade = tree_shade_on_road(road_geom, tree.geometry, tree['crown_width'], hour)
                    tree_shade = max(tree_shade, shade)
                except:
                    pass

            # 통합 그늘 점수 (0~100)
            combined_shade = max(building_shade, tree_shade)
            road_scores[f'shade_{hour}h'] = int(combined_shade * 100)

        shade_data.append(road_scores)

    return gpd.GeoDataFrame(shade_data, crs='EPSG:5179')

def main():
    print("=" * 60)
    print("도로별 그늘 점수 계산 통합")
    print("=" * 60, flush=True)

    # 데이터 로드
    roads, buildings, trees = load_data()

    # 그늘 점수 계산
    shade_scores = calculate_shade_scores(roads, buildings, trees, hour_list=[9, 12, 15, 18])

    # 저장
    out_path = os.path.join(PROJ, "data_clean", "shade_score_roads_대구.geojson")
    shade_scores.to_file(out_path, driver='GeoJSON')
    print(f"\n✓ 저장: {out_path}", flush=True)

    # 통계
    print("\n[그늘 점수 통계]")
    for col in shade_scores.columns:
        if col.startswith('shade_'):
            print(f"  {col}: 평균 {shade_scores[col].mean():.1f}, "
                  f"최대 {shade_scores[col].max()}, 최소 {shade_scores[col].min()}")

    print("\n✓ 완료! 다음 단계: route_optimizer.py", flush=True)

if __name__ == "__main__":
    main()
