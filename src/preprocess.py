# -*- coding: utf-8 -*-
"""
단계1 — 가공(전처리): 좌표계 통일 + 속성 정제
=================================================
config/data_sources.yaml 의 datasets 를 읽어 각 자료를:
  1) 기준좌표계(target_crs, 기본 5179)로 변환
  2) 깨진 도형(self-intersection 등) 복구, 빈/결측 도형 제거
  3) 문자열 앞뒤 공백 제거, 빈문자열('') → 결측
  4) 면적 재계산 (area_m2, area_ha) — 5179 기준
  5) 특수문자 컬럼명 정리(예: '1/연결성' → '1_연결성')  * 원본 필드는 이름만 정리, 값 보존
정제 사본은 data_clean\<key>_<epsg>.gpkg 로 저장.
원본은 절대 수정하지 않음.

실행:  .venv/Scripts/python.exe src/preprocess.py
결과:  data_clean/*.gpkg  +  catalog/cleaning_report_YYYYMMDD.txt
"""
import os, sys, io, re, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import yaml
import pandas as pd
import geopandas as gpd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(PROJ, "config", "data_sources.yaml")
CLEANDIR = os.path.join(PROJ, "data_clean")
CATDIR = os.path.join(PROJ, "catalog")

REPORT = []
def log(msg=""):
    print(msg)
    REPORT.append(str(msg))


def sanitize_columns(gdf):
    """특수문자 컬럼명 정리. {원래: 정리후} 반환."""
    ren = {}
    for c in gdf.columns:
        if c == gdf.geometry.name:
            continue
        new = re.sub(r"[\/\\\n\r\t]+", "_", str(c)).strip("_ ")
        if new != c:
            ren[c] = new
    if ren:
        gdf = gdf.rename(columns=ren)
    return gdf, ren


def clean_strings(gdf, type_fields):
    """문자열 공백 제거·빈칸→결측. 이상값(값==필드명) 카운트."""
    anomalies = {}
    obj_cols = [c for c in gdf.columns
                if c != gdf.geometry.name and gdf[c].dtype == object]
    for c in obj_cols:
        s = gdf[c].astype("string").str.strip()
        s = s.replace({"": pd.NA})
        gdf[c] = s
    # 유형 필드에서 "값이 필드명과 같은" 오입력 탐지 (예: U중분류=='중분류')
    for f in type_fields:
        if f in gdf.columns:
            # 필드명에서 접두(U/B/C 등) 제거한 핵심어와 일치하는지
            core = re.sub(r"^[A-Z]", "", f)  # 'U중분류'->'중분류'
            bad = (gdf[f] == core) | (gdf[f] == f)
            n = int(bad.sum())
            if n:
                anomalies[f] = (core, n)
    return gdf, anomalies


def process(key, ds, target_crs):
    label = ds.get("label", key)
    path = ds["path"]
    type_fields = ds.get("type_fields", [])
    log("=" * 78)
    log(f"[{key}] {label}")
    log(f"  원본: {path}")
    if not os.path.exists(path):
        log("  ! 파일 없음 — 건너뜀"); return None

    gdf = gpd.read_file(path, engine="pyogrio")
    n0 = len(gdf)
    src_epsg = gdf.crs.to_epsg() if gdf.crs else None
    log(f"  읽기: {n0:,} 도형, 원본 EPSG:{src_epsg}, 컬럼 {len(gdf.columns)}")

    # 1) 좌표계 통일
    if src_epsg != target_crs:
        gdf = gdf.to_crs(target_crs)
        log(f"  좌표계 변환: {src_epsg} → {target_crs}")
    else:
        log(f"  좌표계: 이미 {target_crs}")

    # 2) 도형 복구·정리
    empty = gdf.geometry.is_empty | gdf.geometry.isna()
    if empty.any():
        log(f"  빈 도형 제거: {int(empty.sum())}개")
        gdf = gdf[~empty].copy()
    invalid = ~gdf.geometry.is_valid
    n_inv = int(invalid.sum())
    if n_inv:
        gdf.loc[invalid, gdf.geometry.name] = gdf.loc[invalid, gdf.geometry.name].make_valid()
        still = int((~gdf.geometry.is_valid).sum())
        log(f"  깨진 도형 복구: {n_inv}개 (복구 후 잔여 {still}개)")
    else:
        log("  도형 유효성: 이상 없음")

    # 3) 문자열 정제 + 이상값 리포트
    gdf, anomalies = clean_strings(gdf, type_fields)
    if anomalies:
        for f, (core, n) in anomalies.items():
            log(f"  ⚠ 이상값(오입력 추정): '{f}' 필드에 '{core}' 값 {n}개 → 모듈3에서 처리")
    else:
        log("  유형필드 이상값: 없음")

    # 4) 면적 재계산 (5179, m 단위)
    gdf["area_m2"] = gdf.geometry.area
    gdf["area_ha"] = gdf["area_m2"] / 10000.0
    log(f"  면적 재계산 완료 (총 {gdf['area_ha'].sum():,.1f} ha)")

    # 5) 컬럼명 정리
    gdf, ren = sanitize_columns(gdf)
    if ren:
        log(f"  컬럼명 정리: {ren}")

    # 저장
    os.makedirs(CLEANDIR, exist_ok=True)
    out = os.path.join(CLEANDIR, f"{key}_{target_crs}.gpkg")
    gdf.to_file(out, layer=key, driver="GPKG")
    log(f"  ✓ 저장: {out}  ({len(gdf):,} 도형)")
    return out


def main():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    target = int(cfg.get("target_crs", 5179))
    datasets = cfg.get("datasets", {})
    log(f"### 단계1 전처리 시작  (기준좌표계 EPSG:{target})  {datetime.date.today()}")
    log("")
    outs = []
    for key, ds in datasets.items():
        o = process(key, ds, target)
        if o: outs.append(o)
        log("")
    log("=" * 78)
    log(f"완료: {len(outs)}개 자료 정제·저장 → {CLEANDIR}")

    os.makedirs(CATDIR, exist_ok=True)
    rp = os.path.join(CATDIR, f"cleaning_report_{datetime.date.today():%Y%m%d}.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    print(f"\n리포트 저장: {rp}")


if __name__ == "__main__":
    main()
