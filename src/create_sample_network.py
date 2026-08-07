# -*- coding: utf-8 -*-
r"""테스트용 모의 도로망 생성 (OSM 불가능한 경우용).
행정경계 내에 격자 도로망 생성.
출력: data_clean/sample_walk_network.graphml
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString
import numpy as np

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def create_grid_network(bounds, grid_spacing=500):
    """바운딩박스 내에 격자 도로망 생성"""
    minx, miny, maxx, maxy = bounds

    # 격자점 생성
    xs = np.arange(minx, maxx, grid_spacing)
    ys = np.arange(miny, maxy, grid_spacing)

    # 그래프 생성
    G = nx.Graph()

    # 노드 추가
    node_id = 0
    node_positions = {}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            G.add_node(node_id, y=y, x=x)
            node_positions[(i, j)] = node_id
            node_id += 1

    # 엣지 추가 (격자 연결)
    for i in range(len(xs)):
        for j in range(len(ys)):
            u = node_positions[(i, j)]

            # 오른쪽으로
            if i + 1 < len(xs):
                v = node_positions[(i + 1, j)]
                x1, y1 = xs[i], ys[j]
                x2, y2 = xs[i + 1], ys[j]
                dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                G.add_edge(
                    u, v,
                    geometry=LineString([(x1, y1), (x2, y2)]),
                    length=dist,
                    walk_min=dist / 75  # 4.5 km/h = 75 m/min
                )

            # 아래로
            if j + 1 < len(ys):
                v = node_positions[(i, j + 1)]
                x1, y1 = xs[i], ys[j]
                x2, y2 = xs[i], ys[j + 1]
                dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                G.add_edge(
                    u, v,
                    geometry=LineString([(x1, y1), (x2, y2)]),
                    length=dist,
                    walk_min=dist / 75
                )

    return G

def main():
    print("=" * 60)
    print("모의 도로망 생성")
    print("=" * 60, flush=True)

    # 대구 경계 로드
    districts_path = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")
    if not os.path.exists(districts_path):
        print(f"ERROR: {districts_path} 없음", flush=True)
        return

    gdf = gpd.read_file(districts_path, engine="pyogrio")
    print(f"✓ 행정경계 로드: {len(gdf)} 구/군", flush=True)

    bounds = gdf.total_bounds
    print(f"  바운딩박스: {bounds}", flush=True)

    # 격자 도로망 생성
    G = create_grid_network(bounds, grid_spacing=1000)
    print(f"✓ 격자 도로망 생성: 노드 {G.number_of_nodes()}, 엣지 {G.number_of_edges()}", flush=True)

    # 저장 (GeoJSON으로 엣지 저장)
    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            'geometry': data['geometry'],
            'u': u, 'v': v,
            'length': data['length'],
            'walk_min': data['walk_min']
        })
    edges_gdf = gpd.GeoDataFrame(edges, crs='EPSG:5179')
    out_path = os.path.join(PROJ, "data_clean", "sample_walk_network.geojson")
    edges_gdf.to_file(out_path, driver='GeoJSON')
    print(f"✓ 저장: {out_path}", flush=True)

if __name__ == "__main__":
    main()
