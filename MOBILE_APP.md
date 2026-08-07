# 🌳 그늘로 (Geuneul) - 모바일 앱

여름 그늘길 경로 안내 애플리케이션

## 📱 앱 개요

**"더운 여름, 그늘로 가다"**

- 출발지에서 목적지까지 **가장 쾌적한 경로(그늘길)** 제공
- 시간대별 태양각도 고려한 **정확한 그늘 계산**
- 건축물과 가로수 그늘 모두 반영
- 실시간 경로 안내

## 🏗️ 프로젝트 구조

```
├── src/
│   ├── app.py                    # FastAPI 백엔드
│   ├── route_optimizer.py        # 경로 최적화 (A*)
│   ├── solar_position.py         # 태양각도 계산
│   ├── merge_shade_layers.py    # 그늘 점수 계산
│   └── ... (기타 모듈)
│
└── flutter_app/
    ├── lib/
    │   ├── main.dart                    # 앱 진입점
    │   ├── screens/
    │   │   ├── home_screen.dart         # 메인 화면 (경로 검색)
    │   │   └── route_screen.dart        # 경로 결과 (지도)
    │   ├── providers/
    │   │   ├── route_provider.dart      # 경로 상태 관리
    │   │   └── location_provider.dart   # 위치 상태 관리
    │   ├── models/
    │   │   └── route_model.dart         # 데이터 모델
    │   └── widgets/
    │       ├── shade_chart.dart         # 시간대별 그늘 차트
    │       └── route_info_card.dart     # 경로 정보 카드
    └── pubspec.yaml                     # 의존성
```

## 🚀 시작하기

### 1️⃣ 백엔드 (FastAPI) 실행

```bash
cd /home/user/Daegu-urban-eco
source .venv/bin/activate
pip install fastapi uvicorn pyproj
python src/app.py
```

서버: `http://localhost:8000`

API 문서: `http://localhost:8000/docs` (Swagger UI)

### 2️⃣ 모바일 앱 (Flutter) 준비

```bash
cd flutter_app
flutter pub get
flutter run
```

## 📡 API 엔드포인트

### 경로 계산
```http
POST /api/route
Content-Type: application/json

{
  "start": {"lat": 35.8721, "lng": 128.5953},
  "end": {"lat": 35.9000, "lng": 128.6200},
  "hour": 12
}
```

**응답:**
```json
{
  "success": true,
  "distance": 2500.5,
  "avg_shade_score": 45.3,
  "duration_min": 33.4,
  "path": [
    {"lat": 35.8721, "lng": 128.5953},
    {"lat": 35.8730, "lng": 128.5960},
    ...
  ],
  "message": "74개 도로, 2500m, 예상 33분, 그늘 점수 45.3점"
}
```

### 시간대별 그늘 정보
```http
GET /api/shade-by-hour
```

**응답:**
```json
{
  "shade_by_hour": [
    {"hour": 9, "shade_score": 0.7},
    {"hour": 12, "shade_score": 0.3},
    {"hour": 15, "shade_score": 0.7},
    {"hour": 18, "shade_score": 5.2}
  ],
  "best_time": 12,
  "worst_time": 18
}
```

## 🎨 UI 구성

### 홈 화면
- 출발지/목적지 입력
- 시간대 선택 (09:00, 12:00, 15:00, 18:00)
- 하루 그늘 예보 차트
- "쾌적한 경로 찾기" 버튼

### 경로 결과 화면
- Google Maps 지도 표시
- 경로 폴리라인 (녹색)
- 출발지/목적지 마커
- 정보 카드:
  - 거리 (km)
  - 소요 시간 (분)
  - 그늘 점수 (0~100)
- 네비게이션 시작 버튼

## 🔧 주요 기술 스택

**백엔드:**
- Python 3.11
- FastAPI
- GeoPandas (공간 분석)
- NetworkX (그래프 알고리즘)

**모바일:**
- Flutter 3.0+
- Google Maps Flutter
- Provider (상태 관리)
- GetX (네비게이션)
- Dio (HTTP 클라이언트)

## 📊 알고리즘

### 1. 태양 위치 계산
```
시간/계절 → 태양 고도각 & 방위각
```
- NOAA 태양 위치 알고리즘 기반
- 대구 좌표 (35.8721°N, 128.5953°E)
- 시간대별 그림자 길이 계산

### 2. 그늘 점수 계산
```
건물 높이 + 가로수 수관폭 + 도로 위치
→ 그늘 커버율 (0~100%)
```
- 공간 인덱싱으로 근처 객체만 조회
- 건물 그림자: 고도각 기반 다각형 계산
- 가로수 그늘: 수관폭 원형 버퍼

### 3. 경로 최적화 (A*)
```
도로 네트워크 + 그늘 가중치
→ 최단 경로 (거리-그늘 트레이드오프)
```
- 가중치: `거리 × (1 - 그늘점수/100)`
- 그늘이 많을수록 가중치 감소

## 🗺️ 지원 지역

- **대구광역시** (중구, 동구, 서구, 남구, 북구, 수성구, 달성군, 군위군)
- 데이터: 3,321개 도로, 500개 건물, 1,000개 가로수

## 🚧 향후 계획

- [ ] Google Places API 통합 (장소 자동완성)
- [ ] 실시간 위치 추적
- [ ] 대구 전역 확대
- [ ] 지역별/시즌별 데이터 업데이트
- [ ] 사용자 리뷰/그늘 정보 제보
- [ ] iOS/Android 앱 스토어 배포
- [ ] 웹 버전 (React)

## 📝 라이선스

MIT

## 📧 연락처

**개발자**: vomseok@googlemail.com

---

*"더운 여름, 그늘로 가다" 🌳☀️*
