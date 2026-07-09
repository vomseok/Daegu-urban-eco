# -*- coding: utf-8 -*-
r"""
모듈5-R — 변화탐지 (세분화 통합비교유형 기반)
================================================
모듈5의 개선판. 모듈3 중분류 대응표는 2019 '녹지 및 오픈스페이스'를 1종으로 눌러
자연계열 변화가 왜곡됐다(자생침엽수림 -36,861ha 등 재분류 아티팩트).

개선: 2019는 세밀한 'U소분류', 2024는 '유형중분류'를 각각 '통합비교유형'(14종)으로
      재라벨해 같은 해상도로 비교한다. 매핑은 config\crosswalk\통합비교유형_*.csv (편집 가능).

입력:  data_clean\biotope_2019_5179.gpkg   (필드 U소분류)
       data_clean\biotope_2024_5179.gpkg   (필드 유형중분류)
       config\crosswalk\통합비교유형_2019.csv  (원유형→통합비교유형)
       config\crosswalk\통합비교유형_2024.csv

출력:  outputs\<실행일자>\
         module5R_전이행렬.csv / module5R_변화요약.csv / module5R_요약.xlsx
         module5R_전이히트맵.png
       catalog\module5R_report_YYYYMMDD.txt

실행:  .venv\Scripts\python.exe src\module5_change_refined.py
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
CWDIR = os.path.join(PROJ, "config", "crosswalk")

GPKG_1 = os.path.join(CLEANDIR, "biotope_2019_5179.gpkg")
GPKG_2 = os.path.join(CLEANDIR, "biotope_2024_5179.gpkg")
MAP_1 = os.path.join(CWDIR, "통합비교유형_2019.csv")
MAP_2 = os.path.join(CWDIR, "통합비교유형_2024.csv")
FIELD_1 = "U소분류"
FIELD_2 = "유형중분류"
LABEL = "통합비교유형"
BAD_TOKENS = {"대분류", "중분류", "소분류", "세분류", "유형", "미분류"}

REPORT = []
def log(msg=""):
    print(msg, flush=True)
    REPORT.append(str(msg))


def save_report(stamp, note=""):
    os.makedirs(CATDIR, exist_ok=True)
    rp = os.path.join(CATDIR, f"module5R_report_{stamp}.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
        if note:
            f.write("\n" + note)
    print(f"\n리포트 저장: {rp}", flush=True)
    return rp


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


def sanitize_geom(gdf, tag):
    g = gdf.copy(); gname = g.geometry.name; n0 = len(g)
    m = g.geometry.notna() & ~g.geometry.is_empty
    if (~m).any():
        log(f"  [{tag}] 빈/결측 도형 제거: {int((~m).sum())}건"); g = g[m].copy()
    inv = ~g.geometry.is_valid
    if int(inv.sum()):
        g.loc[inv, gname] = g.loc[inv, gname].make_valid()
        log(f"  [{tag}] 비유효 도형 유효화: {int(inv.sum())}건")
    non_poly = ~g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    if non_poly.any():
        g.loc[non_poly, gname] = g.loc[non_poly, gname].apply(_polygonal_only)
        keep = g.geometry.notna() & ~g.geometry.is_empty
        if int((~keep).sum()):
            log(f"  [{tag}] 폴리곤 성분 없는 도형 제거: {int((~keep).sum())}건")
        g = g[keep].copy()
    log(f"  [{tag}] 지오메트리 정리: {n0:,} → {len(g):,} 도형")
    return g


def load_relabel(gpkg, field, mapping, tag):
    if not os.path.exists(gpkg):
        log(f"  ! 정제본 없음: {gpkg}"); sys.exit(1)
    g = gpd.read_file(gpkg, engine="pyogrio", columns=[field])
    if field not in g.columns:
        log(f"  ! [{tag}] 필드 없음: {field}"); sys.exit(1)
    s = (g[field].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
         .replace({"": pd.NA}))
    s = s.mask(s.isin(BAD_TOKENS | {field}))
    g[LABEL] = s.map(mapping)
    n_un = int(g[LABEL].isna().sum())
    g = g.dropna(subset=[LABEL]).copy()
    log(f"  [{tag}] {len(g):,} 도형 재라벨(→통합 {g[LABEL].nunique()}종), 미매핑/결측 제외 {n_un:,}건")
    return g[[LABEL, g.geometry.name]]


def dissolve_by_label(gdf, tag):
    sub = sanitize_geom(gdf, tag)
    log(f"  [{tag}] '{LABEL}' 융합 중... (유형 {sub[LABEL].nunique()}종, 도형 {len(sub):,}개)")
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
    rows = []
    a19 = tbl.groupby("유형_2019")["area_ha"].sum()
    a24 = tbl.groupby("유형_2024")["area_ha"].sum()
    for t in sorted(set(a19.index) | set(a24.index)):
        s19 = float(a19.get(t, 0.0)); s24 = float(a24.get(t, 0.0))
        kept = float(tbl[(tbl["유형_2019"] == t) & (tbl["유형_2024"] == t)]["area_ha"].sum())
        outs = tbl[(tbl["유형_2019"] == t) & (tbl["유형_2024"] != t)].sort_values(
            "area_ha", ascending=False)
        top_to = f"{outs.iloc[0]['유형_2024']}({outs.iloc[0]['area_ha']:.0f}ha)" if len(outs) else ""
        rows.append({
            "통합비교유형": t, "2019면적_ha": round(s19, 1), "2024면적_ha": round(s24, 1),
            "순변화_ha": round(s24 - s19, 1), "유지_ha": round(kept, 1),
            "유지율%": round(kept / s19 * 100, 1) if s19 else "",
            "전출_ha": round(s19 - kept, 1), "최대전출경로": top_to,
        })
    return pd.DataFrame(rows).sort_values("2019면적_ha", ascending=False)


def save_heatmap(mat, outdir):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        fp = r"C:\Windows\Fonts\malgun.ttf"
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        else:
            plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(max(6, 0.6 * mat.shape[1] + 3),
                                        max(4, 0.5 * mat.shape[0] + 2)))
        im = ax.imshow(mat.values, aspect="auto", cmap="OrRd")
        ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(mat.columns, rotation=90, fontsize=8)
        ax.set_yticks(range(mat.shape[0])); ax.set_yticklabels(mat.index, fontsize=8)
        ax.set_xlabel("2024 통합비교유형"); ax.set_ylabel("2019 통합비교유형")
        ax.set_title("통합비교유형 전이면적(ha)  2019 → 2024")
        fig.colorbar(im, ax=ax, shrink=0.7, label="전이면적(ha)")
        fig.tight_layout()
        png = os.path.join(outdir, "module5R_전이히트맵.png")
        fig.savefig(png, dpi=140); plt.close(fig)
        log(f"  ✓ 히트맵: {png}")
    except Exception as e:
        log(f"  (히트맵 생략: {e})")


def load_map(path, tag):
    if not os.path.exists(path):
        log(f"  ! 매핑표 없음: {path}"); sys.exit(1)
    m = pd.read_csv(path, encoding="utf-8-sig")
    mapping = dict(zip(m["원유형"].astype(str), m["통합비교유형"].astype(str)))
    log(f"  [{tag}] 매핑 {len(mapping)}종 → 통합 {m['통합비교유형'].nunique()}종")
    return mapping


def main():
    stamp = datetime.date.today().strftime("%Y%m%d")
    outdir = os.path.join(OUTROOT, stamp)
    os.makedirs(outdir, exist_ok=True)
    log(f"### 모듈5-R 변화탐지(세분화 통합비교유형)  {datetime.date.today()}")
    log(f"    출력 폴더: {outdir}\n")

    log("[매핑표 로드]")
    map1 = load_map(MAP_1, "2019")
    map2 = load_map(MAP_2, "2024")
    log("")

    log("[재라벨·로드]")
    g1 = load_relabel(GPKG_1, FIELD_1, map1, "1차2019")
    g2 = load_relabel(GPKG_2, FIELD_2, map2, "2차2024")
    log("")

    log("[융합]")
    dis1 = dissolve_by_label(g1, "1차2019")
    dis2 = dissolve_by_label(g2, "2차2024")
    log("")

    log("[전이 계산]")
    tbl = transition_table(dis1, dis2)
    mat = tbl.pivot_table(index="유형_2019", columns="유형_2024",
                          values="area_ha", aggfunc="sum", fill_value=0.0).round(1)
    mat_csv = os.path.join(outdir, "module5R_전이행렬.csv")
    mat.to_csv(mat_csv, encoding="utf-8-sig"); log(f"  ✓ 전이행렬: {mat_csv}")

    summ = build_summary(tbl)
    summ_csv = os.path.join(outdir, "module5R_변화요약.csv")
    summ.to_csv(summ_csv, index=False, encoding="utf-8-sig"); log(f"  ✓ 변화요약: {summ_csv}")

    total = tbl["area_ha"].sum()
    kept = float(tbl[tbl["유형_2019"] == tbl["유형_2024"]]["area_ha"].sum())
    log(f"  전체 겹침 {total:,.1f} ha 중 동일유형 유지 {kept:,.1f} ha ({kept/total*100:.1f}%), "
        f"유형전환 {total-kept:,.1f} ha ({(total-kept)/total*100:.1f}%)")
    save_heatmap(mat, outdir)
    log("")

    try:
        xlsx = os.path.join(outdir, "module5R_요약.xlsx")
        with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
            summ.to_excel(xw, sheet_name="변화요약", index=False)
            mat.reset_index().to_excel(xw, sheet_name="전이행렬", index=False)
            tbl.to_excel(xw, sheet_name="전이목록", index=False)
        log(f"✓ 엑셀 요약: {xlsx}")
    except Exception as e:
        log(f"(엑셀 요약 생략: {e})")

    log("=" * 72)
    log(f"모듈5-R 완료 → {outdir}")
    save_report(stamp, note="[상태: 정상완료]")


if __name__ == "__main__":
    stamp = datetime.date.today().strftime("%Y%m%d")
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        log("\n!!! 예외 발생으로 중단 — traceback:")
        log(traceback.format_exc())
        save_report(stamp, note="[상태: 실패/중단]")
        raise
