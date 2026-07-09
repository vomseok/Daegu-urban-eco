# 도시생태 반복형 공간분석 시스템 (대구광역시)

대구광역시 도시생태현황도(비오톱) 1차(2019)·2차(2024)를 기반으로, 도시 녹지네트워크의
**유형 변화·연결성·접근성·탄소계정**을 반복 재현 가능한 형태로 분석하는 GIS 파이프라인입니다.

> 기준좌표계 EPSG:5179(UTM-K) · Python(geopandas·shapely·scipy·rasterio·networkx) · 100m 격자

---

## 분석 모듈

| 모듈 | 스크립트 | 내용 |
|---|---|---|
| 단계0 카탈로그 | `src/catalog.py` | 원본 폴더 스캔·자료 목록화 |
| 단계1 전처리 | `src/preprocess.py` | 좌표통일·도형복구·속성정제 |
| 모듈3 유형표준화 | `src/module3_crosswalk.py` | 1차↔2차 유형 공간중첩 대응표 |
| 모듈5 변화탐지 | `src/module5_change*.py`, `module5_grade_change.py` | 유형·등급 변화(통합비교유형) |
| 모듈4 연결성 | `src/module4_connectivity.py` | 회로이론(전류밀도·유효저항) |
| 모듈4 접근성 | `src/module4_accessibility.py` | 도로망 도보시간(인구가중) |
| 모듈4 집계·평가 | `src/module4_zonal.py`, `module4_evaluate.py`, `module4_corridor.py`, `module4_greenadd.py` | 3공간단위 집계·계획지표 등급·코리더·녹지추가 우선지 |
| 모듈2 탄소 | `src/module2_carbon*.py` | 탄소저장·흡수·토지변화 배출(수종 세분) |
| 보고서 | `src/report_*.py` | 변화탐지·연결성접근성·탄소 Word 보고서 |

## 폴더 구조
```
├─ src/               분석 코드(모듈별)
├─ config/            설정·대응표·계수표·설계문서
│  ├─ 01_설계초안.md, 02_계획지표_가이드라인.md
│  ├─ crosswalk/      유형 대응표(통합비교유형·확정 대응표)
│  ├─ connectivity_resistance.csv   연결성 이동저항
│  └─ carbon_coefficients.csv       탄소 계수(수종 세분)
├─ catalog/           카탈로그·전처리/모듈 실행 리포트
├─ data_clean/        정제 데이터 (대용량 gpkg는 미포함 → 재생성)
└─ outputs/<실행일자>/ 지도·엑셀·보고서·래스터
```

## 실행 방법
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python src/preprocess.py          # 원본 → 정제본(gpkg)
.venv/Scripts/python src/module3_crosswalk.py   # 유형 대응표
.venv/Scripts/python src/module5_change_refined.py
.venv/Scripts/python src/module4_connectivity.py 대구
.venv/Scripts/python src/module4_accessibility.py 대구
.venv/Scripts/python src/module2_carbon.py
```

## 데이터 출처 (원본 미포함)
대용량·공공 원본자료는 저장소에 포함하지 않으며, 출처는 `config/data_sources.yaml`에 등록되어 있다.
`src/preprocess.py`·`fetch_osm_walk.py`로 재생성한다.

| 자료 | 출처 |
|---|---|
| 도시생태현황도(비오톱) 1·2차 | 대구광역시 |
| 도로명주소 도로구간 | 행정안전부 주소기반산업지원서비스 |
| 100m 인구격자 | 통계청 통계지리정보서비스(SGIS) |
| 보행 도로망(보조) | OpenStreetMap |
| 탄소 계수 | 국립산림과학원(2022)·IPCC(2006)·Nowak(2013)·이경학(2006) 등 |

> ⚠ 공공데이터는 각 제공기관의 이용약관을 따른다. 원본 재배포 시 라이선스를 확인할 것.

## 주요 산출물 (`outputs/`)
- 유형 변화·등급 변화 요약·히트맵, 연결성·접근성 3단위 요약·등급도·차이맵,
  녹지 코리더/추가 우선지, 탄소계정 지도, 종합 보고서(Word)

## 라이선스
코드: MIT(또는 기관 정책). 데이터: 각 제공기관 약관 준수.
