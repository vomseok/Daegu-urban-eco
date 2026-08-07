# -*- coding: utf-8 -*-
r"""그늘을 고려한 경로 최적화 (A* 알고리즘).
도로 네트워크에 그늘 가중치를 적용하여 최적 경로 탐색.
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import geopandas as gpd
import networkx as nx
import numpy as np
from heapq import heappush, heappop
from math import sqrt

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_shade_network():
    """그늘 점수가 포함된 도로 네트워크 로드"""
    shade_path = os.path.join(PROJ, "data_clean", "shade_score_roads_대구.geojson")
    if not os.path.exists(shade_path):
        print(f"ERROR: {shade_path} 없음", flush=True)
        return None

    gdf = gpd.read_file(shade_path)
    print(f"✓ 도로 네트워크 로드: {len(gdf)} 세그먼트", flush=True)
    return gdf

def build_graph_with_shade(roads_gdf, target_hour=12):
    """GeoDataFrame을 NetworkX 그래프로 변환, 그늘 가중치 추가.

    Parameters
    ----------
    roads_gdf : GeoDataFrame
        도로 세그먼트 (shade_{hour}h 컬럼 포함)
    target_hour : int
        사용할 시간대 (기본: 정오 12시)

    Returns
    -------
    nx.Graph
        각 엣지에 'weight', 'length', 'shade' 속성 포함
    """
    G = nx.Graph()

    shade_col = f'shade_{target_hour}h'
    if shade_col not in roads_gdf.columns:
        print(f"  경고: {shade_col} 컬럼 없음, 그늘 무시", flush=True)
        shade_col = None

    for idx, road in roads_gdf.iterrows():
        geom = road.geometry
        coords = list(geom.coords)

        if len(coords) < 2:
            continue

        # 도로 시작/끝점을 노드로 사용
        u = (round(coords[0][0], 1), round(coords[0][1], 1))
        v = (round(coords[-1][0], 1), round(coords[-1][1], 1))

        length = geom.length
        shade_score = 0
        if shade_col and shade_col in road:
            shade_score = road[shade_col]

        # 가중치 = 거리 - 그늘 보정
        # 그늘 점수가 높을수록(쾌적할수록) 가중치 감소
        weight = length * (1 - shade_score / 100)

        G.add_edge(u, v,
                   weight=weight,
                   length=length,
                   shade=shade_score,
                   geometry=geom)

    print(f"✓ 그래프 생성: 노드 {G.number_of_nodes()}, 엣지 {G.number_of_edges()}", flush=True)
    return G

def heuristic(u, v):
    """A* 휴리스틱: 직선거리"""
    return sqrt((u[0] - v[0])**2 + (u[1] - v[1])**2)

def astar_path_shade(G, start, end, weight='weight'):
    """A* 알고리즘으로 그늘을 고려한 경로 탐색.

    Parameters
    ----------
    G : nx.Graph
        가중치 그래프
    start : tuple
        시작 노드 좌표
    end : tuple
        목적지 노드 좌표
    weight : str
        엣지 가중치 속성명

    Returns
    -------
    list
        경로 (노드 리스트) 또는 None (경로 없음)
    """
    # 가장 가까운 노드 찾기
    def find_nearest_node(pos):
        min_dist = float('inf')
        nearest = None
        for node in G.nodes():
            dist = heuristic(pos, node)
            if dist < min_dist:
                min_dist = dist
                nearest = node
        return nearest

    start_node = find_nearest_node(start)
    end_node = find_nearest_node(end)

    if start_node is None or end_node is None:
        return None

    # A* 구현
    open_set = [(0, start_node)]
    came_from = {}
    g_score = {start_node: 0}
    f_score = {start_node: heuristic(start_node, end_node)}

    while open_set:
        _, current = heappop(open_set)

        if current == end_node:
            # 경로 복원
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]

        for neighbor in G.neighbors(current):
            edge_weight = G[current][neighbor][weight]
            tentative_g = g_score[current] + edge_weight

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, end_node)
                heappush(open_set, (f_score[neighbor], neighbor))

    return None  # 경로 없음

def path_to_geojson(G, path):
    """경로를 GeoJSON 피처로 변환"""
    if path is None:
        return None

    total_length = 0
    total_shade = 0
    segments = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = G[u][v]
        geom = edge_data.get('geometry')
        if geom:
            segments.append(geom)
            total_length += edge_data['length']
            total_shade += edge_data.get('shade', 0)

    from shapely.geometry import LineString, MultiLineString
    if segments:
        if len(segments) == 1:
            line = segments[0]
        else:
            line = MultiLineString(segments)

        avg_shade = total_shade / len(segments) if segments else 0
        return {
            'type': 'Feature',
            'geometry': line.__geo_interface__,
            'properties': {
                'length': total_length,
                'avg_shade_score': avg_shade,
                'n_segments': len(segments)
            }
        }

    return None

def test_routing():
    """경로 최적화 테스트"""
    print("=" * 60)
    print("경로 최적화 테스트 (그늘 가중치 적용)")
    print("=" * 60, flush=True)

    roads = load_shade_network()
    if roads is None:
        return

    print("\n[정오(12시) 기준 경로 계산]", flush=True)
    G = build_graph_with_shade(roads, target_hour=12)

    # 테스트 출발지/목적지 (도로 범위 내 랜덤)
    bounds = roads.total_bounds
    start_pos = (bounds[0] + 2000, bounds[1] + 2000)
    end_pos = (bounds[2] - 2000, bounds[3] - 2000)

    print(f"  출발지: {start_pos}")
    print(f"  목적지: {end_pos}")

    path = astar_path_shade(G, start_pos, end_pos)

    if path:
        print(f"✓ 경로 찾음: {len(path)} 노드", flush=True)
        for i, node in enumerate(path[:5]):
            print(f"    [{i}] {node}")
        if len(path) > 5:
            print(f"    ... ({len(path)-5} more)")
    else:
        print("  경로 없음", flush=True)

if __name__ == "__main__":
    test_routing()
