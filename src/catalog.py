# -*- coding: utf-8 -*-
"""
단계0 — 자동 탐색·진단 (카탈로그 생성기)
=========================================
config/data_sources.yaml 의 scan_roots 폴더를 훑어
모든 공간자료(벡터 .shp / 래스터 .tif·.img)의
좌표계·도형형식·도형수·필드목록·용량을 표로 정리한다.

실행:  .venv/Scripts/python.exe src/catalog.py
결과:  catalog/catalog_YYYYMMDD.csv  (+ .json)
"""
import os, sys, io, csv, json, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import yaml
import pyogrio
from pyproj import CRS

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(PROJ, "config", "data_sources.yaml")
CATDIR = os.path.join(PROJ, "catalog")

VECTOR_EXT = (".shp", ".gpkg", ".geojson")
RASTER_EXT = (".tif", ".tiff", ".img")


def to_epsg(crs_str):
    """CRS 문자열 → EPSG 코드(가능하면). 실패 시 None."""
    if not crs_str:
        return None
    try:
        return CRS.from_user_input(crs_str).to_epsg()
    except Exception:
        return None


def scan_vector(path):
    info = pyogrio.read_info(path)
    fields = list(info.get("fields", []))
    return {
        "kind": "vector",
        "epsg": to_epsg(info.get("crs")),
        "crs_raw": str(info.get("crs"))[:60],
        "geom_type": info.get("geometry_type"),
        "features": int(info.get("features", 0)),
        "n_fields": len(fields),
        "fields": fields,
        "encoding": info.get("encoding"),
    }


def scan_raster(path):
    import rasterio
    with rasterio.open(path) as r:
        return {
            "kind": "raster",
            "epsg": r.crs.to_epsg() if r.crs else None,
            "crs_raw": str(r.crs)[:60],
            "geom_type": f"{r.width}x{r.height}",
            "features": r.count,                 # 밴드 수
            "n_fields": 0,
            "fields": [f"res={r.res[0]:.2f}"],
            "encoding": str(r.dtypes[0]),
        }


def main():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    roots = cfg.get("scan_roots", [])
    target = cfg.get("target_crs")

    rows = []
    for root in roots:
        if not os.path.isdir(root):
            print(f"  ! 폴더 없음: {root}")
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                full = os.path.join(dirpath, fn)
                try:
                    if ext in VECTOR_EXT:
                        rec = scan_vector(full)
                    elif ext in RASTER_EXT:
                        rec = scan_raster(full)
                    else:
                        continue
                except Exception as e:
                    rec = {"kind": "ERROR", "epsg": None, "crs_raw": str(e)[:60],
                           "geom_type": None, "features": 0, "n_fields": 0,
                           "fields": [], "encoding": None}
                rec["file"] = fn
                rec["size_mb"] = round(os.path.getsize(full) / 1e6, 1)
                rec["needs_reproject"] = (rec["epsg"] != target) if rec["epsg"] else "확인필요"
                rec["path"] = full
                rows.append(rec)

    rows.sort(key=lambda r: (r["kind"], -r["size_mb"]))
    os.makedirs(CATDIR, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    csv_path = os.path.join(CATDIR, f"catalog_{stamp}.csv")
    json_path = os.path.join(CATDIR, f"catalog_{stamp}.json")

    cols = ["kind", "file", "epsg", "needs_reproject", "geom_type",
            "features", "n_fields", "size_mb", "encoding", "path"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    # 요약 출력
    vec = [r for r in rows if r["kind"] == "vector"]
    ras = [r for r in rows if r["kind"] == "raster"]
    err = [r for r in rows if r["kind"] == "ERROR"]
    print(f"=== 카탈로그 생성 완료 ===  (기준좌표계 EPSG:{target})")
    print(f"  벡터 {len(vec)} · 래스터 {len(ras)} · 오류 {len(err)}")
    epsgs = {}
    for r in vec + ras:
        epsgs[r["epsg"]] = epsgs.get(r["epsg"], 0) + 1
    print("  좌표계 분포:", {f"EPSG:{k}": v for k, v in epsgs.items()})
    need = [r for r in vec + ras if r["needs_reproject"] is True]
    print(f"  변환 필요(≠{target}): {len(need)}개")
    print(f"  저장: {csv_path}")
    print(f"        {json_path}")


if __name__ == "__main__":
    main()
