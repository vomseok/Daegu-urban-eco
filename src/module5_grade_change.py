# -*- coding: utf-8 -*-
r"""
모듈5-G — 비오톱 등급변화 탐지 (2019 최종등급 ↔ 2024 최종평가등)
================================================================
목적: 두 시점의 비오톱 평가등급이 공간적으로 어떻게 이동했는지 전이행렬로 본다.

⚠ 한계(중요): 두 조사의 등급 체계가 다르다.
   · 2019 '최종등급' = 1~5 + 평가제외 (단순 5등급)
   · 2024 '최종평가등' = '1-1','3-2','5-' 등 복합코드 → 앞자리(주등급)만 취해 정규화
   · 분포도 크게 다름(2024는 1등급이 전체의 ~60%) → 등급 기준 자체가 달라
     '등급 상승/하락'을 생태 개선/악화로 직결 해석하면 안 됨. 분포 비교·참고용.

입력:  data_clean\biotope_2019_5179.gpkg (필드 최종등급)
       data_clean\biotope_2024_5179.gpkg (필드 최종평가등)
출력:  outputs\<실행일자>\module5G_등급전이행렬.csv / _등급요약.csv / _등급히트맵.png
       catalog\module5G_report_YYYYMMDD.txt
실행:  .venv\Scripts\python.exe src\module5_grade_change.py
"""
import os, sys, io, datetime, re
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
LABEL = "등급"

REPORT = []
def log(msg=""):
    print(msg, flush=True); REPORT.append(str(msg))

def save_report(stamp, note=""):
    os.makedirs(CATDIR, exist_ok=True)
    rp = os.path.join(CATDIR, f"module5G_report_{stamp}.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
        if note: f.write("\n" + note)
    print(f"\n리포트 저장: {rp}", flush=True); return rp

def _polygonal_only(geom):
    if geom is None or geom.is_empty: return None
    if geom.geom_type in ("Polygon", "MultiPolygon"): return geom
    if geom.geom_type == "GeometryCollection":
        polys = [p for p in geom.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        return None if not polys else (polys[0] if len(polys) == 1 else shapely.union_all(polys))
    return None

def sanitize_geom(gdf, tag):
    g = gdf.copy(); gname = g.geometry.name; n0 = len(g)
    m = g.geometry.notna() & ~g.geometry.is_empty
    if (~m).any(): g = g[m].copy()
    inv = ~g.geometry.is_valid
    if int(inv.sum()): g.loc[inv, gname] = g.loc[inv, gname].make_valid()
    non_poly = ~g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    if non_poly.any():
        g.loc[non_poly, gname] = g.loc[non_poly, gname].apply(_polygonal_only)
        g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    log(f"  [{tag}] 지오메트리 정리: {n0:,} → {len(g):,}")
    return g

def norm_grade(s):
    """등급 정규화: 앞자리 숫자(1~5)만. 평가제외/미평가는 '평가제외'."""
    s = s.astype("string").str.strip()
    def f(v):
        if v is pd.NA or v is None or str(v) in ("", "nan"): return pd.NA
        v = str(v)
        if "평가제외" in v: return "평가제외"
        m = re.match(r"\s*([1-5])", v)      # '3-2'→3, '5-'→5, '3'→3
        return m.group(1) if m else "평가제외"   # '-','-2' 등 → 평가제외
    return s.map(f)

def load_grade(gpkg, field, tag):
    g = gpd.read_file(gpkg, engine="pyogrio", columns=[field])
    g[LABEL] = norm_grade(g[field])
    n_na = int(g[LABEL].isna().sum())
    g = g.dropna(subset=[LABEL]).copy()
    log(f"  [{tag}] {len(g):,} 도형, 등급 {sorted(g[LABEL].unique())}, 결측 제외 {n_na:,}")
    return g[[LABEL, g.geometry.name]]

def dissolve_by(gdf, tag):
    sub = sanitize_geom(gdf, tag)
    dis = sub.dissolve(by=LABEL, as_index=False)
    dis = dis[~dis.geometry.is_empty & dis.geometry.notna()].copy()
    inv = ~dis.geometry.is_valid
    if inv.any(): dis.loc[inv, dis.geometry.name] = dis.loc[inv, dis.geometry.name].make_valid()
    dis["_ha"] = dis.geometry.area / 10000.0
    log(f"  [{tag}] 융합: {len(dis)}등급, 총 {dis['_ha'].sum():,.1f} ha")
    return dis

def save_heatmap(mat, outdir):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        fp = r"C:\Windows\Fonts\malgun.ttf"
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(max(5, 0.7*mat.shape[1]+2), max(4, 0.6*mat.shape[0]+2)))
        im = ax.imshow(mat.values, aspect="auto", cmap="PuBuGn")
        ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(mat.columns, fontsize=9)
        ax.set_yticks(range(mat.shape[0])); ax.set_yticklabels(mat.index, fontsize=9)
        ax.set_xlabel("2024 등급"); ax.set_ylabel("2019 등급")
        ax.set_title("비오톱 등급 전이면적(ha)  2019 → 2024")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                ax.text(j, i, f"{mat.values[i,j]:.0f}", ha="center", va="center", fontsize=7)
        fig.colorbar(im, ax=ax, shrink=0.7, label="ha")
        fig.tight_layout()
        png = os.path.join(outdir, "module5G_등급히트맵.png")
        fig.savefig(png, dpi=140); plt.close(fig)
        log(f"  ✓ 히트맵: {png}")
    except Exception as e:
        log(f"  (히트맵 생략: {e})")

def main():
    stamp = datetime.date.today().strftime("%Y%m%d")
    outdir = os.path.join(OUTROOT, stamp); os.makedirs(outdir, exist_ok=True)
    log(f"### 모듈5-G 등급변화 탐지  {datetime.date.today()}")
    log(f"    출력 폴더: {outdir}")
    log("    ⚠ 두 조사의 등급체계가 달라 '등급 상승/하락'의 생태적 직접 해석은 삼갈 것(참고용).\n")

    log("[로드·정규화]")
    g1 = load_grade(GPKG_1, "최종등급", "1차2019")
    g2 = load_grade(GPKG_2, "최종평가등", "2차2024")
    log("")

    log("[융합]")
    d1 = dissolve_by(g1, "1차2019"); d2 = dissolve_by(g2, "2차2024")
    log("")

    log("[전이 계산]")
    a = d1[[LABEL, d1.geometry.name]].rename(columns={LABEL: "등급_2019"})
    b = d2[[LABEL, d2.geometry.name]].rename(columns={LABEL: "등급_2024"})
    inter = gpd.overlay(a, b, how="intersection", keep_geom_type=True)
    inter["area_ha"] = inter.geometry.area / 10000.0
    tbl = (inter.groupby(["등급_2019", "등급_2024"])["area_ha"].sum()
                .reset_index().sort_values("area_ha", ascending=False))
    log(f"  전이 조합 {len(tbl)}개, 총 겹침 {tbl['area_ha'].sum():,.1f} ha")

    mat = tbl.pivot_table(index="등급_2019", columns="등급_2024", values="area_ha",
                          aggfunc="sum", fill_value=0.0).round(1)
    mat_csv = os.path.join(outdir, "module5G_등급전이행렬.csv")
    mat.to_csv(mat_csv, encoding="utf-8-sig"); log(f"  ✓ 등급전이행렬: {mat_csv}")

    # 등급별 분포·유지 요약
    a19 = tbl.groupby("등급_2019")["area_ha"].sum()
    a24 = tbl.groupby("등급_2024")["area_ha"].sum()
    rows = []
    for t in sorted(set(a19.index) | set(a24.index)):
        s19 = float(a19.get(t, 0)); s24 = float(a24.get(t, 0))
        kept = float(tbl[(tbl["등급_2019"] == t) & (tbl["등급_2024"] == t)]["area_ha"].sum())
        rows.append({"등급": t, "2019면적_ha": round(s19,1), "2024면적_ha": round(s24,1),
                     "순변화_ha": round(s24-s19,1), "유지_ha": round(kept,1),
                     "유지율%": round(kept/s19*100,1) if s19 else ""})
    summ = pd.DataFrame(rows)
    summ_csv = os.path.join(outdir, "module5G_등급요약.csv")
    summ.to_csv(summ_csv, index=False, encoding="utf-8-sig"); log(f"  ✓ 등급요약: {summ_csv}")

    total = tbl["area_ha"].sum()
    kept = float(tbl[tbl["등급_2019"] == tbl["등급_2024"]]["area_ha"].sum())
    log(f"  동일등급 유지 {kept:,.0f} ha ({kept/total*100:.1f}%), 등급변동 {total-kept:,.0f} ha ({(total-kept)/total*100:.1f}%)")
    save_heatmap(mat, outdir)

    try:
        xlsx = os.path.join(outdir, "module5G_등급요약.xlsx")
        with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
            summ.to_excel(xw, sheet_name="등급요약", index=False)
            mat.reset_index().to_excel(xw, sheet_name="등급전이행렬", index=False)
        log(f"✓ 엑셀: {xlsx}")
    except Exception as e:
        log(f"(엑셀 생략: {e})")

    log("=" * 72); log(f"모듈5-G 완료 → {outdir}")
    save_report(stamp, note="[상태: 정상완료]")

if __name__ == "__main__":
    stamp = datetime.date.today().strftime("%Y%m%d")
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        log("\n!!! 예외 발생으로 중단 — traceback:"); log(traceback.format_exc())
        save_report(stamp, note="[상태: 실패/중단]"); raise
