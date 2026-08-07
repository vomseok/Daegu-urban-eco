# -*- coding: utf-8 -*-
r"""그늘길 경로 안내 앱 - FastAPI 백엔드.
모바일 앱에 제공할 REST API 엔드포인트.
"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import geopandas as gpd
import json

# 모듈 임포트
from route_optimizer import load_shade_network, build_graph_with_shade, astar_path_shade
from solar_position import DAEGU_LAT, DAEGU_LON, shade_coverage_summer

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJ, "data_clean")

# FastAPI 앱 생성
app = FastAPI(
    title="그늘로 API",
    description="여름 그늘길 경로 안내 앱 백엔드",
    version="0.1.0"
)

# CORS 설정 (모바일 앱 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 데이터 모델
# ============================================================================

class Location(BaseModel):
    """위치 (경위도)"""
    lat: float
    lng: float

class RouteRequest(BaseModel):
    """경로 요청"""
    start: Location
    end: Location
    hour: int = 12  # 시간대 (기본값: 정오)
    date: Optional[str] = None  # 날짜 (선택사항)

class RouteResponse(BaseModel):
    """경로 응답"""
    success: bool
    distance: float  # 경로 거리 (m)
    avg_shade_score: float  # 평균 그늘 점수 (0~100)
    duration_min: float  # 예상 소요시간 (분)
    path: List[Location]  # 경로 포인트
    message: str

class ShadeInfo(BaseModel):
    """시간대별 그늘 정보"""
    hour: int
    shade_score: float  # 0~100

class DayShadeResponse(BaseModel):
    """하루 그늘 정보"""
    shade_by_hour: List[ShadeInfo]
    best_time: int  # 가장 쾌적한 시간
    worst_time: int  # 가장 뜨거운 시간

# ============================================================================
# 글로벌 변수 (캐시)
# ============================================================================

roads_gdf = None
G_network = None

def load_network():
    """네트워크 로드 (최초 1회만)"""
    global roads_gdf, G_network

    if roads_gdf is None:
        shade_path = os.path.join(DATA_DIR, "shade_score_roads_대구.geojson")
        if not os.path.exists(shade_path):
            raise FileNotFoundError(f"{shade_path} 없음")
        roads_gdf = gpd.read_file(shade_path)
        print(f"✓ 도로 네트워크 로드: {len(roads_gdf)} 세그먼트", flush=True)

    if G_network is None:
        G_network = build_graph_with_shade(roads_gdf, target_hour=12)

    return roads_gdf, G_network

# ============================================================================
# 헬스 체크
# ============================================================================

@app.get("/")
def read_root():
    """헬스 체크"""
    return {"status": "healthy", "service": "그늘로 API v0.1"}

@app.get("/health")
def health_check():
    """상세 헬스 체크"""
    try:
        roads_gdf, _ = load_network()
        return {
            "status": "ok",
            "data_loaded": True,
            "roads_count": len(roads_gdf),
            "service_location": "대구광역시"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# ============================================================================
# 경로 API
# ============================================================================

@app.post("/api/route", response_model=RouteResponse)
def get_route(req: RouteRequest):
    """
    경로 계산 API

    매개변수:
    - start: 출발지 {lat, lng}
    - end: 목적지 {lat, lng}
    - hour: 시간대 (9, 12, 15, 18 등)

    반환:
    - success: 성공 여부
    - path: 경로 포인트 배열
    - distance: 거리
    - avg_shade_score: 평균 그늘 점수
    - duration_min: 예상 소요시간
    """
    try:
        roads_gdf, G_network = load_network()

        # EPSG:4326 (위경도) → EPSG:5179 (대구 투영좌표)
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:5179")
        start_x, start_y = transformer.transform(req.start.lat, req.start.lng)
        end_x, end_y = transformer.transform(req.end.lat, req.end.lng)

        start_pos = (start_x, start_y)
        end_pos = (end_x, end_y)

        # 경로 계산
        path_nodes = astar_path_shade(G_network, start_pos, end_pos)

        if path_nodes is None:
            return RouteResponse(
                success=False,
                distance=0,
                avg_shade_score=0,
                duration_min=0,
                path=[],
                message="경로를 찾을 수 없습니다"
            )

        # 경로를 위경도로 변환
        transformer_inv = Transformer.from_crs("EPSG:5179", "EPSG:4326")
        path_locations = []
        total_distance = 0
        total_shade = 0
        edge_count = 0

        for i, node in enumerate(path_nodes):
            lat, lng = transformer_inv.transform(node[0], node[1])
            path_locations.append(Location(lat=lat, lng=lng))

            # 엣지 정보 수집
            if i < len(path_nodes) - 1:
                next_node = path_nodes[i + 1]
                try:
                    edge_data = G_network[node][next_node]
                    total_distance += edge_data['length']
                    total_shade += edge_data.get('shade', 0)
                    edge_count += 1
                except:
                    pass

        avg_shade = (total_shade / edge_count) if edge_count > 0 else 0
        duration = total_distance / 75  # 4.5 km/h = 75 m/min

        return RouteResponse(
            success=True,
            distance=total_distance,
            avg_shade_score=avg_shade,
            duration_min=duration,
            path=path_locations,
            message=f"{len(path_nodes)} 개 도로, {total_distance:.0f}m, "
                   f"예상 {duration:.0f}분, 그늘 점수 {avg_shade:.1f}점"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# 그늘 정보 API
# ============================================================================

@app.get("/api/shade-by-hour", response_model=DayShadeResponse)
def get_shade_by_hour():
    """
    하루 그늘 변화 정보

    반환:
    - shade_by_hour: 시간대별 그늘 점수
    - best_time: 가장 쾌적한 시간
    - worst_time: 가장 뜨거운 시간
    """
    try:
        # 태양 위치 기반 그늘 점수
        shade_map = shade_coverage_summer(
            DAEGU_LAT, DAEGU_LON,
            hour_list=list(range(6, 20))
        )

        shade_info = [
            ShadeInfo(
                hour=hour,
                shade_score=score * 100  # 0~1 → 0~100
            )
            for hour, score in sorted(shade_map.items())
        ]

        # 최고/최저 시간 찾기
        best_time = min(shade_info, key=lambda x: x.shade_score).hour
        worst_time = max(shade_info, key=lambda x: x.shade_score).hour

        return DayShadeResponse(
            shade_by_hour=shade_info,
            best_time=best_time,
            worst_time=worst_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# 통계 API
# ============================================================================

@app.get("/api/stats")
def get_stats():
    """
    서비스 통계
    """
    try:
        roads_gdf, _ = load_network()

        stats = {
            "service": "그늘로 - 여름 그늘길 경로 안내",
            "region": "대구광역시",
            "coverage": {
                "roads": len(roads_gdf),
                "buildings": 500,  # 모의 데이터
                "trees": 1000  # 모의 데이터
            },
            "best_time": "정오 (12:00)",
            "hottest_time": "저녁 (18:00)",
            "contact": "vomseok@googlemail.com"
        }
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# 시작
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("그늘로 API 서버 시작...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
