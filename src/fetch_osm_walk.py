# -*- coding: utf-8 -*-
r"""OSM 대구 보행도로망 다운로드·캐시 (1회 실행).
출력: data_clean\osm_walk_대구.graphml  (EPSG:5179 투영, 엣지 walk_min 포함)
"""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import osmnx as ox
import geopandas as gpd
import shapely

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "data_clean", "osm_walk_대구.graphml")
WALK_MPS = 4500.0 / 60.0     # 4.5 km/h → m/분

def main():
    t0 = time.time()
    # 대구 좌표 (위경도)
    west, south, east, north = 128.3505, 35.6032, 128.7647, 36.0191
    print(f"대구 bbox(4326): W{west:.4f} S{south:.4f} E{east:.4f} N{north:.4f}", flush=True)
    print("OSM walk network 다운로드 중... (Overpass)", flush=True)
    try:
        G = ox.graph_from_bbox((west, south, east, north), network_type="walk")
    except TypeError:
        # 구버전 시그니처 폴백
        G = ox.graph_from_bbox(north=north, south=south, east=east, west=west, network_type="walk")
    print(f"  원본: 노드 {G.number_of_nodes():,}, 엣지 {G.number_of_edges():,}", flush=True)
    G = ox.project_graph(G, to_crs="EPSG:5179")
    # 엣지 보행시간(분) 부여
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0.0)
        data["walk_min"] = length / WALK_MPS
    ox.save_graphml(G, OUT)
    print(f"✓ 저장: {OUT}  ({time.time()-t0:.0f}s)", flush=True)

if __name__ == "__main__":
    main()
