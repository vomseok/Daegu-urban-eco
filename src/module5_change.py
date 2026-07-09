# -*- coding: utf-8 -*-
r"""
모듈5 — 변화탐지 (1차↔2차 유형 전이, 공간중첩 기반)
====================================================
설계초안 §4·§5 및 모듈3 "다음" 지침에 따름:
  · 모듈3에서 사람이 확정한 '중분류 대응표'로 두 시점을 같은 어휘로 재라벨하고,
  · 공간중첩(intersection)으로 "같은 위치에서 무엇이 무엇으로 바뀌었나"를 면적으로 집계한다.

방법:
  1. 재라벨 — 2019 'U중분류' → 확정표의 '확정_2차유형'(2차 어휘로 통일).
             2024 '유형중분류'는 이미 2차 어휘 → 그대로 사용.
             ⇒ 두 시점이 같은 유형공간에 놓여 비교 가능.
  2. 전이   — 각 시점을 재라벨 유형으로 dissolve → 2019⊗2024 교차중첩 →
             (2019유형 → 2024유형)별 전이면적(ha) 행렬.
             (모듈3와 동일: 15만 폴리곤 전체 overlay 대신 유형별 융합 후 교차 → 가볍고 정확)
  3. 요약   — 유형별 유지(대각)·전환 면적, 순변화(2024면적-2019면적), 상위 전환 경로.

입력:  data_clean\biotope_2019_5179.gpkg   (필드 U중분류)
       data_clean\biotope_2024_5179.gpkg   (필드 유형중분류)
       config\crosswalk\crosswalk_중분류_확정.csv   (확정여부=Y 행만 사용)

출력:  outputs\<실행일자>\
         module5_전이행렬.csv        (행=2019유형, 열=2024유형, 전이면적 ha)
         module5_변화요약.csv        (유형별 2019/2024면적·유지·전환·순변화)
         module5_요약.xlsx
         module5_전이히트맵.png
       catalog\module5_report_YYYYMMDD.txt

실행:  .venv\Scripts\python.exe src\module5_change.py
"""
import os, sys, io, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import geopandas as gpd
import shapely

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEANDIR = os.path.join(PROJ, "data_clean")
CATDIR = os.path.join(PROJ, "catalog")
OUTROOT = os.path.join(PROJ, "outputs")

GPKG_1 = os.path.join(CLEANDIR, "biotope_2019_5179.gpkg")
GPKG_2 = os.path.join(CLEANDIR, "biotope_2024_5179.gpkg")
CROSSWALK = os.path.join(PROJ, "config", "crosswalk", "crosswalk_중분류_확정.csv")
FIELD_1 = "U중분류"        # 1차 재라벨 대상 필드
FIELD_2 = "유형중분류"     # 2차(이미 비교어휘)
LABEL = "비교유형"         # 두 시점 공통 라벨 컬럼명

REPORT = []
def log(msg=""):
    print(msg, flush=True)
    REPORT.append(str(msg))


def save_report(stamp, note=""):
    os.makedirs(CATDIR, exist_ok=True)
    rp = os.path.join(CATDIR, f"module5_report_{stamp}.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
        if note:
            f.write("\n" + note)
    print(f"\n리포트 저장: {rp}", flush=True)
    return rp


# ── 지오메트리 유효화 (모듈3와 동일 기법) ─────────────────────────────
def sanitize_geom(gdf, tag):
    g = gdf.copy()
    gname = g.geometry.name
    n0 = len(g)
    m = g.geometry.notna() & ~g.geometry.is_empty
    if (~m).any():
        log(f"  [{tag}] 빈/결측 도형 제거: {int((~m).sum())}건")
        g = g[m].copy()
    inv = ~g.geometry.is_valid
    if int(inv.sum()):
        g.loc[inv, gname] = g.loc[inv, gname].make_valid()
        log(f"  [{tag}] 비유효 도형 유효화: {int(inv.sum())}건")
    gt = g.geometry.geom_type
    non_poly = ~gt.isin(["Polygon", "MultiPolygon"])
    if non_poly.any():
        g.loc[non_poly, gname] = g.loc[non_poly, gname].apply(_polygonal_only)
        keep = g.geometry.notna() & ~g.geometry.is_empty
        if int((~keep).sum()):
            log(f"  [{tag}] 폴리곤 성분 없는 도형 제거: {int((~keep).sum())}건")
        g = g[keep].copy()
    log(f"  [{tag}] 지오메트리 정리: {n0:,} → {len(g):,} 도형")
    return g


def _polygonal_only(geom):
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [p for p in geom.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        if not polys:
            return None
        return polys[0] if len(polys) == 1 else shapely.union_all(polys)
    return None


BAD_TOKENS = {"대분류", "중분류", "소분류", "세분류", "유형", "미분류"}

def _clean_label(s, field):
    """라벨 정리 + 오입력(머리글/필드명) 결측 처리."""
    s = s.astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    s = s.replace({"": pd.NA})
    s = s.mask(s.isin(BAD_TOKENS | {field}))
    return s


def load_relabel_2019(crosswalk):
    """2019 정제본 로드 → U중분류를 확정_2차유형으로 재라벨 → LABEL 컬럼 생성."""
    if not os.path.exists(GPKG_1):
        log(f"  ! 정제본 없음: {GPKG_1}"); sys.exit(1)
    g = gpd.read_file(GPKG_1, engine="pyogrio")
    if FIELD_1 not in g.columns:
        log(f"  ! [1차] 필드 없음: {FIELD_1}"); sys.exit(1)
    g = g[[FIELD_1, g.geometry.name]].copy()
    g[FIELD_1] = _clean_label(g[FIELD_1], FIELD_1)
    g[LABEL] = g[FIELD_1].map(crosswalk)          # 대응표에 있는 유형만 매핑
    n_unmapped = int(g[LABEL].isna().sum())
    g = g.dropna(subset=[LABEL]).copy()
    log(f"  [1차2019] {len(g):,} 도형 재라벨(대응표 {len(crosswalk)}종), 미매핑 제외 {n_unmapped:,}건")
    return g[[LABEL, g.geometry.name]]


def load_2024():
    """2024 정제본 로드 → 유형중분류를 그대로 LABEL 로."""
    if not os.path.exists(GPKG_2):
        log(f"  ! 정제본 없음: {GPKG_2}"); sys.exit(1)
    g = gpd.read_file(GPKG_2, engine="pyogrio")
    if FIELD_2 not in g.columns:
        log(f"  ! [2차] 필드 없음: {FIELD_2}"); sys.exit(1)
    g = g[[FIELD_2, g.geometry.name]].copy()
    g[LABEL] = _clean_label(g[FIELD_2], FIELD_2)
    n_na = int(g[LABEL].isna().sum())
    g = g.dropna(subset=[LABEL]).copy()
    log(f"  [2차2024] {len(g):,} 도형(라벨 {g[LABEL].nunique()}종), 결측 제외 {n_na:,}건")
    return g[[LABEL, g.geometry.name]]


def dissolve_by_label(gdf, tag):
    sub = sanitize_geom(gdf, tag)
    n_types = sub[LABEL].nunique()
    log(f"  [{tag}] '{LABEL}' 융합 중... (유형 {n_types}종, 도형 {len(sub):,}개)")
    dis = sub.dissolve(by=LABEL, as_index=False)
    dis = dis[~dis.geometry.is_empty & dis.geometry.notna()].copy()
    inv = ~dis.geometry.is_valid
    if inv.any():
        dis.loc[inv, dis.geometry.name] = dis.loc[inv, dis.geometry.name].make_valid()
    dis["_area_ha"] = dis.geometry.area / 10000.0
    log(f"  [{tag}] 융합 완료: {len(dis)}종, 총 {dis['_area_ha'].sum():,.1f} ha")
    return dis


def transition_table(dis1, dis2):
    a = dis1[[LABEL, dis1.geometry.name]].rename(columns={LABEL: "유형_2019"})
    b = dis2[[LABEL, dis2.geometry.name]].rename(columns={LABEL: "유형_2024"})
    log("  교차중첩(intersection) 계산 중... (2019 ⊗ 2024)")
    inter = gpd.overlay(a, b, how="intersection", keep_geom_type=True)
    inter["area_ha"] = inter.geometry.area / 10000.0
    tbl = (inter.groupby(["유형_2019", "유형_2024"])["area_ha"].sum()
                .reset_index().sort_values("area_ha", ascending=False))
    log(f"  전이 조합: {len(tbl)}개, 총 겹침 {tbl['area_ha'].sum():,.1f} ha")
    return tbl


def build_summary(tbl):
    """유형별 유지/전환/순변화 요약."""
    rows = []
    area2019 = tbl.groupby("유형_2019")["area_ha"].sum()
    area2024 = tbl.groupby("유형_2024")["area_ha"].sum()
    all_types = sorted(set(area2019.index) | set(area2024.index))
    for t in all_types:
        a19 = float(area2019.get(t, 0.0))
        a24 = float(area2024.get(t, 0.0))
        # 유지 = 같은 위치에서 유형이 그대로(대각)
        kept = float(tbl[(tbl["유형_2019"] == t) & (tbl["유형_2024"] == t)]["area_ha"].sum())
        changed_out = a19 - kept        # 2019에 이 유형이었다가 다른 유형으로
        # 최대 전출 경로
        outs = tbl[(tbl["유형_2019"] == t) & (tbl["유형_2024"] != t)].sort_values(
            "area_ha", ascending=False)
        top_to = (f"{outs.iloc[0]['유형_2024']}({outs.iloc[0]['area_ha']:.0f}ha)"
                  if len(outs) else "")
        rows.append({
            "비교유형": t,
            "2019면적_ha": round(a19, 1),
            "2024면적_ha": round(a24, 1),
            "순변화_ha": round(a24 - a19, 1),
            "유지_ha": round(kept, 1),
            "유지율%": round(kept / a19 * 100, 1) if a19 else "",
            "전출_ha": round(changed_out, 1),
            "최대전출경로": top_to,
        })
    return pd.DataFrame(rows).sort_values("2019면적_ha", ascending=False)


def save_heatmap(mat, outdir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        fp = r"C:\Windows\Fonts\malgun.ttf"
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        else:
            plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(max(6, 0.5 * mat.shape[1] + 3),
                                        max(4, 0.4 * mat.shape[0] + 2)))
        im = ax.imshow(mat.values, aspect="auto", cmap="OrRd")
        ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(mat.columns, rotation=90, fontsize=7)
        ax.set_yticks(range(mat.shape[0])); ax.set_yticklabels(mat.index, fontsize=7)
        ax.set_xlabel("2024 유형"); ax.set_ylabel("2019 유형(재라벨)")
        ax.set_title("유형 전이면적(ha)  2019 → 2024")
        fig.colorbar(im, ax=ax, shrink=0.7, label="전이면적(ha)")
        fig.tight_layout()
        png = os.path.join(outdir, "module5_전이히트맵.png")
        fig.savefig(png, dpi=140); plt.close(fig)
        log(f"  ✓ 히트맵: {png}")
    except Exception as e:
        log(f"  (히트맵 생략: {e})")


def load_crosswalk():
    if not os.path.exists(CROSSWALK):
        log(f"  ! 확정 대응표 없음: {CROSSWALK}")
        log("    → 모듈3 실행 후 config\\crosswalk\\crosswalk_중분류_확정.csv 를 확정하세요.")
        sys.exit(1)
    cw = pd.read_csv(CROSSWALK, encoding="utf-8-sig")
    ok = cw[cw["확정여부(Y/N)"].astype("string").str.upper() == "Y"].copy()
    ok = ok.dropna(subset=["확정_2차유형"])
    mapping = dict(zip(ok["1차유형"].astype(str), ok["확정_2차유형"].astype(str)))
    n_wait = len(cw) - len(ok)
    log(f"  [대응표] 확정 {len(mapping)}종 로드 (미확정 {n_wait}행 제외)")
    if n_wait:
        log(f"    ※ 미확정 행이 있어 해당 1차유형은 재라벨에서 빠집니다.")
    return mapping


def main():
    stamp = datetime.date.today().strftime("%Y%m%d")
    outdir = os.path.join(OUTROOT, stamp)
    os.makedirs(outdir, exist_ok=True)
    log(f"### 모듈5 변화탐지(유형 전이)  {datetime.date.today()}")
    log(f"    출력 폴더: {outdir}")
    log("")

    log("[대응표 로드]")
    cw = load_crosswalk()
    log("")

    log("[재라벨·로드]")
    g1 = load_relabel_2019(cw)
    g2 = load_2024()
    log("")

    log("[융합]")
    dis1 = dissolve_by_label(g1, "1차2019")
    dis2 = dissolve_by_label(g2, "2차2024")
    log("")

    log("[전이 계산]")
    tbl = transition_table(dis1, dis2)

    mat = tbl.pivot_table(index="유형_2019", columns="유형_2024",
                          values="area_ha", aggfunc="sum", fill_value=0.0).round(1)
    mat_csv = os.path.join(outdir, "module5_전이행렬.csv")
    mat.to_csv(mat_csv, encoding="utf-8-sig")
    log(f"  ✓ 전이행렬: {mat_csv}")

    summ = build_summary(tbl)
    summ_csv = os.path.join(outdir, "module5_변화요약.csv")
    summ.to_csv(summ_csv, index=False, encoding="utf-8-sig")
    log(f"  ✓ 변화요약: {summ_csv}")

    # 전체 유지/전환 개관
    total = tbl["area_ha"].sum()
    kept_total = float(tbl[tbl["유형_2019"] == tbl["유형_2024"]]["area_ha"].sum())
    log(f"  전체 겹침 {total:,.1f} ha 중 동일유형 유지 {kept_total:,.1f} ha "
        f"({kept_total/total*100:.1f}%), 유형전환 {total-kept_total:,.1f} ha "
        f"({(total-kept_total)/total*100:.1f}%)")
    save_heatmap(mat, outdir)
    log("")

    try:
        xlsx = os.path.join(outdir, "module5_요약.xlsx")
        with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
            summ.to_excel(xw, sheet_name="변화요약", index=False)
            mat.reset_index().to_excel(xw, sheet_name="전이행렬", index=False)
            tbl.to_excel(xw, sheet_name="전이목록", index=False)
        log(f"✓ 엑셀 요약: {xlsx}")
    except Exception as e:
        log(f"(엑셀 요약 생략: {e})")

    log("=" * 72)
    log(f"모듈5 완료 → {outdir}")
    save_report(stamp, note="[상태: 정상완료]")


if __name__ == "__main__":
    stamp = datetime.date.today().strftime("%Y%m%d")
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        log("")
        log("!!! 예외 발생으로 중단 — traceback:")
        log(traceback.format_exc())
        save_report(stamp, note="[상태: 실패/중단]")
        raise
