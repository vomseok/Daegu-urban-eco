# -*- coding: utf-8 -*-
r"""
모듈3 — 유형체계 표준화 (공간중첩 기반 1차↔2차 대응표)
========================================================
설계초안 §4 원칙에 따름:
  · 환경부 표준유형표에 맞추지 않는다(사용자 확인).
  · 목표는 국가표준 준수가 아니라 "1차↔2차를 서로 비교 가능하게" 만드는 것.
  · 방법: (1순위) 공간중첩 — 같은 위치에서 1차 유형이 2차 어떤 유형과 겹치는지
          면적 기준 교차표를 만들고, '지배적 대응'을 대응관계로 본다.
          (보조) 지배대응이 약한(애매한) 것만 라벨 문자유사도로 후보를 추천.
          (확정) 자동 대응표는 '초안' — 도메인 전문가가 검토·확정.

비교 레벨: 대/중/소 중 데이터가 안정적으로 대응되는 레벨을 본다.
          설계초안은 '중분류 유력'. 본 스크립트는 대·중분류를 모두 산출하되
          중분류를 주(主) 대응표로 삼는다(소분류는 시점 간 흔들림이 커 통계비교 부적합).

입력:  data_clean\biotope_2019_5179.gpkg   (1차, 필드 U대분류/U중분류/U소분류)
       data_clean\biotope_2024_5179.gpkg   (2차, 필드 유형대분류/유형중분류/유형소분류)
       ※ 없으면 먼저 src\preprocess.py 를 실행할 것.

출력:  outputs\<실행일자>\
         module3_교차표_중분류.csv        (면적 매트릭스: 1차행 × 2차열, ha)
         module3_대응표초안_중분류.csv     (1차→2차 지배대응 + 신뢰도 + 후보)
         module3_교차표_대분류.csv
         module3_대응표초안_대분류.csv
         module3_요약.xlsx                (위 표들을 시트로 묶음, openpyxl 있을 때)
         module3_히트맵_중분류.png          (교차표 시각화, 한글폰트 있을 때)
       catalog\module3_report_YYYYMMDD.txt (실행 로그)

실행:  .venv\Scripts\python.exe src\module3_crosswalk.py
"""
import os, sys, io, re, datetime, difflib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import geopandas as gpd
import shapely

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEANDIR = os.path.join(PROJ, "data_clean")
CATDIR = os.path.join(PROJ, "catalog")
OUTROOT = os.path.join(PROJ, "outputs")

# 1차/2차 정제본 경로 + 유형 필드(레벨별)
GPKG_1 = os.path.join(CLEANDIR, "biotope_2019_5179.gpkg")
GPKG_2 = os.path.join(CLEANDIR, "biotope_2024_5179.gpkg")
LEVELS = {                       # 레벨명: (1차 필드, 2차 필드)
    "대분류": ("U대분류", "유형대분류"),
    "중분류": ("U중분류", "유형중분류"),
}
MAIN_LEVEL = "중분류"            # 주 대응표로 삼을 레벨

REPORT = []
def log(msg=""):
    print(msg, flush=True)          # 단계별 즉시 출력(중단돼도 콘솔에 남게)
    REPORT.append(str(msg))


def save_report(stamp, note=""):
    r"""REPORT를 catalog\module3_report_*.txt 로 저장. 성공/실패 어느 쪽에서도 호출."""
    os.makedirs(CATDIR, exist_ok=True)
    rp = os.path.join(CATDIR, f"module3_report_{stamp}.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
        if note:
            f.write("\n" + note)
    print(f"\n리포트 저장: {rp}", flush=True)
    return rp


def sanitize_geom(gdf, tag):
    """dissolve/overlay 전 지오메트리 사전 정리.
    2차 레이어는 geometry_type이 'Unknown'(혼합·비유효 도형 포함)이라,
    유효화하지 않고 dissolve(unary_union)에 넣으면 GEOS 토폴로지 예외로 죽는다.
    → (1) 빈/결측 제거 (2) make_valid로 유효화 (3) 폴리곤 성분만 추출."""
    g = gdf.copy()
    gname = g.geometry.name
    n0 = len(g)
    # (1) 빈/결측 도형 제거
    m = g.geometry.notna() & ~g.geometry.is_empty
    if (~m).any():
        log(f"  [{tag}] 빈/결측 도형 제거: {int((~m).sum())}건")
        g = g[m].copy()
    # (2) 비유효 도형 유효화
    inv = ~g.geometry.is_valid
    n_inv = int(inv.sum())
    if n_inv:
        g.loc[inv, gname] = g.loc[inv, gname].make_valid()
        log(f"  [{tag}] 비유효 도형 유효화(make_valid): {n_inv}건")
    # (3) make_valid는 GeometryCollection/라인/포인트를 만들 수 있음 → 폴리곤 성분만 남김
    gt = g.geometry.geom_type
    non_poly = ~gt.isin(["Polygon", "MultiPolygon"])
    if non_poly.any():
        g.loc[non_poly, gname] = g.loc[non_poly, gname].apply(_polygonal_only)
        # 폴리곤 성분이 하나도 없어 None 이 된 행 제거
        keep = g.geometry.notna() & ~g.geometry.is_empty
        dropped = int((~keep).sum())
        if dropped:
            log(f"  [{tag}] 폴리곤 성분 없는 도형 제거: {dropped}건")
        g = g[keep].copy()
    log(f"  [{tag}] 지오메트리 정리 완료: {n0:,} → {len(g):,} 도형")
    return g


def _polygonal_only(geom):
    """혼합/컬렉션 도형에서 폴리곤 성분만 뽑아 (Multi)Polygon 으로. 없으면 None."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [p for p in geom.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        if not polys:
            return None
        return polys[0] if len(polys) == 1 else shapely.union_all(polys)
    return None   # Line/Point 등은 면적 비교 대상 아님


def load_layer(path, fields, tag):
    """정제본을 읽어 [유형필드들 + geometry]만 남긴다."""
    if not os.path.exists(path):
        log(f"  ! 정제본 없음: {path}")
        log("    → 먼저 'src\\preprocess.py' 를 실행하세요.")
        sys.exit(1)
    gdf = gpd.read_file(path, engine="pyogrio")
    keep = [f for f in fields if f in gdf.columns]
    miss = [f for f in fields if f not in gdf.columns]
    if miss:
        log(f"  ! [{tag}] 필드 없음: {miss} (있는 컬럼: {list(gdf.columns)[:12]}...)")
    gdf = gdf[keep + [gdf.geometry.name]].copy()
    # 유형 라벨 정리(공백/개행 제거, 빈칸→결측)
    # + 오입력 방어: 값이 필드명이거나 '대/중/소분류' 같은 머리글 그 자체면 결측 처리
    #   (preprocess 로그의 'U중분류=중분류' 1467건 등 — 가짜 유형으로 튀지 않게)
    bad_tokens = {"대분류", "중분류", "소분류", "세분류", "유형", "미분류"}
    n_bad_total = 0
    for f in keep:
        gdf[f] = gdf[f].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
        gdf[f] = gdf[f].replace({"": pd.NA})
        bad = gdf[f].isin(bad_tokens | {f})
        nb = int(bad.sum())
        if nb:
            gdf.loc[bad, f] = pd.NA
            n_bad_total += nb
    if n_bad_total:
        log(f"  [{tag}] 오입력 라벨 결측처리: {n_bad_total}건")
    log(f"  [{tag}] {len(gdf):,} 도형, EPSG:{gdf.crs.to_epsg()}, 필드 {keep}")
    return gdf


def dissolve_level(gdf, field, tag):
    """해당 레벨 유형으로 융합(dissolve) → 유형당 1개 (멀티)폴리곤.
    폴리곤 수가 수만→수십으로 줄어 교차중첩이 가벼워지고 결과도 레벨 교차표에 정확히 부합."""
    sub = gdf[[field, gdf.geometry.name]].dropna(subset=[field]).copy()
    # ② dissolve(unary_union) 전에 지오메트리 유효화 — 토폴로지 예외 예방
    sub = sanitize_geom(sub, tag)
    n_types = sub[field].nunique()
    log(f"  [{tag}] '{field}' 융합 중... (유형 {n_types}종, 도형 {len(sub):,}개)")
    dis = sub.dissolve(by=field, as_index=False)
    dis = dis[~dis.geometry.is_empty & dis.geometry.notna()].copy()
    # 융합 후 도형 유효성 보정
    inv = ~dis.geometry.is_valid
    if inv.any():
        dis.loc[inv, dis.geometry.name] = dis.loc[inv, dis.geometry.name].make_valid()
    dis["_area_self_ha"] = dis.geometry.area / 10000.0
    log(f"  [{tag}] 융합 완료: {len(dis)}종, 총 {dis['_area_self_ha'].sum():,.1f} ha")
    return dis


def intersect_area_table(dis1, f1, dis2, f2):
    """두 레벨 융합레이어를 교차중첩 → (1차유형, 2차유형)별 겹침면적(ha) 표."""
    a = dis1[[f1, dis1.geometry.name]].copy()
    b = dis2[[f2, dis2.geometry.name]].copy()
    log("  교차중첩(intersection) 계산 중...")
    inter = gpd.overlay(a, b, how="intersection", keep_geom_type=True)
    inter["area_ha"] = inter.geometry.area / 10000.0
    tbl = (inter.groupby([f1, f2])["area_ha"].sum()
                .reset_index().sort_values("area_ha", ascending=False))
    log(f"  교차 조합: {len(tbl)}개, 총 겹침 {tbl['area_ha'].sum():,.1f} ha")
    return tbl


def build_crosswalk(tbl, f1, f2):
    """교차면적표 → 1차→2차 지배대응 대응표 초안(신뢰도·후보 포함)."""
    types2 = sorted(tbl[f2].dropna().unique())
    rows = []
    for t1, g in tbl.groupby(f1):
        total = g["area_ha"].sum()
        g = g.sort_values("area_ha", ascending=False)
        best = g.iloc[0]
        ratio = float(best["area_ha"] / total) if total else 0.0
        second = g.iloc[1] if len(g) > 1 else None
        # 신뢰도: 지배대응 면적비율 기준
        conf = "상(자동확정 후보)" if ratio >= 0.70 else \
               "중(검토 권장)"     if ratio >= 0.45 else \
               "하(사람 확정 필요)"
        # 애매(하)한 경우 라벨 문자유사도로 보조 후보 추천
        label_hint = ""
        if ratio < 0.45:
            cand = difflib.get_close_matches(str(t1), [str(x) for x in types2], n=1, cutoff=0.4)
            if cand:
                label_hint = f"라벨유사:{cand[0]}"
        rows.append({
            "1차유형": t1,
            "→ 2차 대응(지배)": best[f2],
            "대응비율%": round(ratio * 100, 1),
            "겹침면적_ha": round(best["area_ha"], 1),
            "1차총면적_ha": round(total, 1),
            "신뢰도": conf,
            "2순위 후보": (f"{second[f2]}({second['area_ha']/total*100:.0f}%)"
                          if second is not None else ""),
            "보조힌트": label_hint,
        })
    cw = pd.DataFrame(rows).sort_values(["신뢰도", "1차총면적_ha"],
                                        ascending=[True, False])
    return cw


def save_heatmap(matrix, level, outdir):
    """교차표 히트맵 PNG (한글폰트 있을 때만)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        # 한글 폰트: 프로젝트 상위 font 폴더 → 시스템 맑은고딕 순
        for fp in [os.path.join(PROJ, "..", "..", "..", "font"), r"C:\Windows\Fonts\malgun.ttf"]:
            try:
                if fp.endswith(".ttf") and os.path.exists(fp):
                    font_manager.fontManager.addfont(fp)
                    plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
                    break
            except Exception:
                pass
        else:
            plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False

        m = matrix.copy()
        fig, ax = plt.subplots(figsize=(max(6, 0.5 * m.shape[1] + 3),
                                        max(4, 0.4 * m.shape[0] + 2)))
        im = ax.imshow(m.values, aspect="auto", cmap="YlGn")
        ax.set_xticks(range(m.shape[1])); ax.set_xticklabels(m.columns, rotation=90, fontsize=7)
        ax.set_yticks(range(m.shape[0])); ax.set_yticklabels(m.index, fontsize=7)
        ax.set_xlabel("2차(2024~25) 유형"); ax.set_ylabel("1차(2019) 유형")
        ax.set_title(f"1차↔2차 {level} 공간중첩 면적(ha)")
        fig.colorbar(im, ax=ax, shrink=0.7, label="겹침면적(ha)")
        fig.tight_layout()
        png = os.path.join(outdir, f"module3_히트맵_{level}.png")
        fig.savefig(png, dpi=140); plt.close(fig)
        log(f"  ✓ 히트맵: {png}")
    except Exception as e:
        log(f"  (히트맵 생략: {e})")


def main():
    stamp = datetime.date.today().strftime("%Y%m%d")
    outdir = os.path.join(OUTROOT, stamp)
    os.makedirs(outdir, exist_ok=True)
    log(f"### 모듈3 유형 표준화(공간중첩)  {datetime.date.today()}")
    log(f"    출력 폴더: {outdir}")
    log("")

    # 1) 정제본 로드 (필요한 유형 필드 전부)
    f1_all = [v[0] for v in LEVELS.values()]
    f2_all = [v[1] for v in LEVELS.values()]
    log("[로드]")
    g1 = load_layer(GPKG_1, f1_all, "1차2019")
    g2 = load_layer(GPKG_2, f2_all, "2차2024")
    log("")

    sheets = {}   # 엑셀용
    for level, (f1, f2) in LEVELS.items():
        log("=" * 72)
        log(f"[{level}]  1차 '{f1}'  ↔  2차 '{f2}'")
        dis1 = dissolve_level(g1, f1, "1차")
        dis2 = dissolve_level(g2, f2, "2차")
        tbl = intersect_area_table(dis1, f1, dis2, f2)

        # 교차표(매트릭스) 저장
        mat = tbl.pivot_table(index=f1, columns=f2, values="area_ha",
                              aggfunc="sum", fill_value=0.0).round(1)
        cross_csv = os.path.join(outdir, f"module3_교차표_{level}.csv")
        mat.to_csv(cross_csv, encoding="utf-8-sig")
        log(f"  ✓ 교차표: {cross_csv}")

        # 대응표 초안 저장
        cw = build_crosswalk(tbl, f1, f2)
        cw_csv = os.path.join(outdir, f"module3_대응표초안_{level}.csv")
        cw.to_csv(cw_csv, index=False, encoding="utf-8-sig")
        log(f"  ✓ 대응표 초안: {cw_csv}")

        # 신뢰도 분포 요약
        dist = cw["신뢰도"].value_counts().to_dict()
        log(f"  신뢰도 분포: {dist}")
        sheets[f"교차표_{level}"] = mat.reset_index()
        sheets[f"대응표_{level}"] = cw

        if level == MAIN_LEVEL:
            save_heatmap(mat, level, outdir)
        log("")

    # 엑셀로 묶기(있으면)
    try:
        xlsx = os.path.join(outdir, "module3_요약.xlsx")
        with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
            for name, df in sheets.items():
                df.to_excel(xw, sheet_name=name[:31], index=False)
        log(f"✓ 엑셀 요약: {xlsx}")
    except Exception as e:
        log(f"(엑셀 요약 생략: {e})")

    log("=" * 72)
    log(f"모듈3 완료 → {outdir}")
    log("다음: 대응표 초안을 사람이 검토·확정 후 config\\crosswalk\\ 에 확정본 저장,")
    log("      확정 대응코드로 두 시점을 재라벨 → 모듈5(변화탐지)로 진행.")

    save_report(stamp, note="[상태: 정상완료]")


if __name__ == "__main__":
    stamp = datetime.date.today().strftime("%Y%m%d")
    try:
        main()
    except SystemExit:
        raise                       # 정제본 없음 등 의도된 종료는 그대로
    except Exception:
        import traceback
        log("")
        log("!!! 예외 발생으로 중단 — traceback:")
        log(traceback.format_exc())
        save_report(stamp, note="[상태: 실패/중단]")
        raise
