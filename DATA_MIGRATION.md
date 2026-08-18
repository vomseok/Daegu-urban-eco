# 대구 지리 데이터 재생성 가이드

## 현재 상황

### 문제점
- `shade_score_roads_대구.geojson` 파일이 일본 지역 데이터를 포함하고 있습니다
- 대구 좌표(35.8°N, 128.6°E)로 경로 검색 시 0 값 반환
- 데이터 범위 내 좌표(29.5°N, 135.1°E - 일본 오키나와)로 검색하면 정상 작동

### 현재 데이터 범위
- **EPSG:5179**: X=1077032-1113032, Y=1734852-1779852
- **EPSG:4326 (위도/경도)**: lat=29.45-29.75°N, lng=135.06-135.55°E (일본 오키나와/와카야마 지역)

### 실제 대구 좌표 범위
- **EPSG:4326**: lat=35.80-35.95°N, lng=128.50-128.75°E (대한민국 대구광역시)
- **EPSG:5179**: X=1756412-1773310, Y=1090356-1112733

## 해결 방법

### 방법 1: 로컬 머신에서 OSM 데이터 생성 (권장)

로컬 머신(윈도우/맥/리눅스)에서 다음 명령어를 실행하세요:

```bash
# 1. 프로젝트 폴더에서
cd /path/to/Daegu-urban-eco

# 2. 대구 보행도로망 다운로드
python src/fetch_osm_walk.py

# 3. 시간이 걸리므로 기다려주세요 (5-10분)
# 출력 파일: data_clean/osm_walk_대구.graphml
```

### 방법 2: 수동으로 데이터 생성

```python
import osmnx as ox
import geopandas as gpd

# 대구 보행도로망 다운로드
G = ox.graph_from_place("Daegu, South Korea", network_type="walk")

# EPSG:5179로 투영
G = ox.project_graph(G, to_crs="EPSG:5179")

# GeoJSON으로 저장
edges_data = []
for u, v, key, data in G.edges(keys=True, data=True):
    edges_data.append({
        'geometry': data['geometry'],
        'length': data.get('length', 0),
        'u': u, 'v': v
    })

edges_gdf = gpd.GeoDataFrame(edges_data, crs='EPSG:5179')
edges_gdf.to_file('data_clean/osm_walk_daegu.geojson', driver='GeoJSON')
```

### 방법 3: 기존 OSM 파일 사용 (이미 있는 경우)

```python
import osmnx as ox

# 저장된 graphml 파일 로드
G = ox.load_graphml('data_clean/osm_walk_대구.graphml')

# EPSG:5179로 투영 및 GeoJSON 변환
G = ox.project_graph(G, to_crs="EPSG:5179")
```

## 데이터 생성 후 다음 단계

1. **건물 그늘 데이터**
   ```bash
   python src/fetch_osm_buildings.py
   ```

2. **가로수 그늘 데이터**
   ```bash
   python src/fetch_osm_trees.py
   ```

3. **시간대별 그늘 점수 계산**
   ```bash
   python src/merge_shade_layers.py
   ```

4. **경로 네트워크 구축**
   ```bash
   python src/create_sample_network.py  # 또는 OSM 데이터 사용
   ```

## 현재 테스트 상태

### 작동하는 좌표 (일본 데이터)
- 출발: lat=29.543036, lng=135.176014
- 목적: lat=29.670946, lng=135.442900
- 결과: 41km, 546분, 그늘점수 1.14점 ✅

### 테스트 예정 좌표 (대구 데이터 생성 후)
- 출발: lat=35.87°N, lng=128.59°E (대구역)
- 목적: lat=35.88°N, lng=128.60°E (동인동)

## 참고 사항

- 프론트엔드는 현재 일본 데이터로 작동하도록 설정되어 있습니다
- 대구 데이터 준비 완료 시 프론트엔드 좌표도 업데이트해야 합니다
- OSM 데이터는 2024년 기준이며 정기적으로 업데이트됩니다
