# -*- coding: utf-8 -*-
r"""
모듈4-A — 녹지 접근성 (도로망 도보시간, 인구가중)
==================================================
공식 도로망(도로명주소 도로구간)으로 각 인구격자(100m)에서 최근접 녹지까지의
실제 도보 도달시간을 계산하고, 인구가중 평균시간·N분내 도달인구비율을 산출한다.

방법:
  · 도로구간(EPSG:5181)→5179, 창(구+완충)으로 잘라 networkx 그래프 구성(엣지 walk_min=길이/도보속도).
  · 녹지(산림+조성녹지+수계·습지, 연도별) 경계 인접 도로노드를 '진입점'으로.
  · 진입점 다중출발 Dijkstra → 도로노드별 최근접녹지 도보시간.
  · 인구격자(100m, val=인구) 중심을 최근접 도로노드에 스냅 → 접근시간=노드시간+셀↔노드 도보보정.
  · 지표: 인구가중 평균 도보시간, 5/10/15분 내 녹지 도달 인구비율. 2019·2024(도로·인구 공통, 녹지만 상이).

입력:  data_clean\biotope_{2019,2024}_5179.gpkg  (녹지)
       도로: (도로명주소)도로구간 대구 shp (5181)   · 인구: 국토통계 100m 인구격자 shp(5179)
       config\crosswalk\통합비교유형_{2019,2024}.csv
출력:  outputs\<일자>\module4A_<구>_<연도>_접근시간.gpkg/.png  · module4A_<구>_접근성요약.csv
실행:  .venv\Scripts\python.exe src\module4_accessibility.py [구이름]   (기본 수성구)
"""
import os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
import networkx as nx
from scipy.spatial import cKDTree

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(PROJ, "data_clean")
CWDIR = os.path.join(PROJ, "config", "crosswalk")
OUTROOT = os.path.join(PROJ, "outputs")
ROAD_SHP = r"C:/Users/user/AppData/Local/Temp/claude/D--my-Data-GIS-Project-20260629----------/3dd1a3d4-23e4-4fa8-a518-c682997d53f4/scratchpad/roads/Z_KAIS_TL_SPRD_MANAGE_27000.shp"
POP_SHP = r"D:/my Data/GIS/Data/Source/2_public D/(B100)국토통계_인구정보-총 인구 수(전체)-(격자) 100M_대구광역시_201904/vl_blk.shp"

WALK_MPS = 4500.0/60.0        # 4.5km/h → m/분
BUFFER = 1500.0               # 구 경계 밖 완충(도로 경로 확보)
SNAP = 1.0                    # 도로 노드 스냅 정밀도(m)
GREEN = {"산림", "초지·조성녹지", "수계·습지"}
GREEN_MIN_HA = 1.0            # 목적지 녹지 최소면적
ENTRY_BUF = 60.0             # 녹지 경계에서 이 거리내 도로노드를 진입점으로
THRESHOLDS = [5, 10, 15]      # 분
DINFO = {"2019": ("SIG_KOR_NM", "biotope_2019_5179.gpkg", "U소분류", "통합비교유형_2019.csv"),
         "2024": ("조사지역", "biotope_2024_5179.gpkg", "유형중분류", "통합비교유형_2024.csv")}
BAD = {"대분류","중분류","소분류","세분류","유형","미분류"}

REPORT=[]
def log(m=""):
    print(m, flush=True); REPORT.append(str(m))
def save_report(stamp, gu, note=""):
    cat=os.path.join(PROJ,"catalog"); os.makedirs(cat,exist_ok=True)
    rp=os.path.join(cat,f"module4A_{gu}_report_{stamp}.txt")
    open(rp,"w",encoding="utf-8").write("\n".join(REPORT)+("\n"+note if note else ""))
    print("리포트:",rp,flush=True)

def _poly_only(g):
    if g is None or g.is_empty: return None
    if g.geom_type in ("Polygon","MultiPolygon"): return g
    if g.geom_type=="GeometryCollection":
        ps=[p for p in g.geoms if p.geom_type in ("Polygon","MultiPolygon")]
        return None if not ps else (ps[0] if len(ps)==1 else shapely.union_all(ps))
    return None

def district_poly(gu):
    d=gpd.read_file(os.path.join(CLEAN,"districts_5179.gpkg"),engine="pyogrio")
    if gu in ("대구","전역","all"):
        return d.geometry.union_all()
    row=d[d["구군"]==gu]
    if row.empty: log(f"  ! '{gu}' 없음"); sys.exit(1)
    return row.geometry.union_all()

def green_union(year, win):
    gufield,gpkg,field,mapcsv=DINFO[year]
    mp=pd.read_csv(os.path.join(CWDIR,mapcsv),encoding="utf-8-sig")
    mapping=dict(zip(mp["원유형"].astype(str),mp["통합비교유형"].astype(str)))
    g=gpd.read_file(os.path.join(CLEAN,gpkg),engine="pyogrio",columns=[field])
    s=(g[field].astype("string").str.replace(r"\s+"," ",regex=True).str.strip().replace({"":pd.NA}))
    s=s.mask(s.isin(BAD|{field})); g["통합"]=s.map(mapping)
    grn=g[g["통합"].isin(GREEN)].copy()
    grn=grn[grn.geometry.intersects(win)].copy()
    inv=~grn.geometry.is_valid
    if inv.any(): grn.loc[inv,grn.geometry.name]=grn.loc[inv,grn.geometry.name].make_valid()
    grn[grn.geometry.name]=grn.geometry.apply(_poly_only)
    grn=grn[grn.geometry.notna()& ~grn.geometry.is_empty]
    # 패치 면적필터
    uni=grn.geometry.union_all()
    parts=[p for p in (uni.geoms if uni.geom_type=="MultiPolygon" else [uni]) if p.area/10000.0>=GREEN_MIN_HA]
    gu2=shapely.union_all(parts) if parts else uni
    log(f"  [{year}] 녹지패치 {len(parts)}개(≥{GREEN_MIN_HA}ha), 녹지면적 {gu2.area/1e4:,.0f} ha")
    return gu2

def build_graph(win):
    r=gpd.read_file(ROAD_SHP,engine="pyogrio",columns=["ROAD_LT"]).to_crs(5179)
    r=r[r.geometry.intersects(win)].copy()
    # 도로구간은 교차점에서 분할돼 있지 않음 → unary_union으로 노딩(교차점 분할)해야 라우팅 가능
    log(f"  창내 도로구간 {len(r):,}개, 노딩(unary_union) 중...")
    noded=shapely.unary_union(r.geometry.values)
    lines=list(noded.geoms) if noded.geom_type.startswith("Multi") else [noded]
    G=nx.Graph()
    def key(x,y): return (round(x/SNAP)*SNAP, round(y/SNAP)*SNAP)
    n_e=0
    for ln in lines:
        if ln.geom_type!="LineString": continue
        c=list(ln.coords)
        if len(c)<2: continue
        a=key(*c[0][:2]); b=key(*c[-1][:2])
        if a==b: continue
        w=ln.length/WALK_MPS
        if G.has_edge(a,b):
            if w<G[a][b]["w"]: G[a][b]["w"]=w
        else:
            G.add_edge(a,b,w=w); n_e+=1
    comps=list(nx.connected_components(G))
    giant=max(comps,key=len)
    frac=len(giant)/G.number_of_nodes()
    log(f"  도로그래프 노드 {G.number_of_nodes():,} 엣지 {n_e:,}, 연결성분 {len(comps)}개, 최대성분 {frac*100:.1f}%")
    H=G.subgraph(giant).copy()
    nodes=np.array(list(H.nodes()))
    return H, nodes

def accessibility(H, nodes, tree, green_geom):
    """녹지 진입 도로노드 다중출발 → 노드별 최근접녹지 도보시간(분)."""
    gb=green_geom.buffer(ENTRY_BUF)
    from shapely.prepared import prep
    pg=prep(gb)
    src=[tuple(nodes[i]) for i in range(len(nodes)) if pg.contains(shapely.Point(nodes[i]))]
    log(f"    녹지 진입노드 {len(src):,}개")
    if not src: return None
    dist=nx.multi_source_dijkstra_path_length(H, src, weight="w")
    tmin=np.array([dist.get(tuple(n), np.inf) for n in nodes])
    return tmin

def main():
    gu=sys.argv[1] if len(sys.argv)>1 else "수성구"
    stamp=datetime.date.today().strftime("%Y%m%d")
    outdir=os.path.join(OUTROOT,stamp); os.makedirs(outdir,exist_ok=True)
    log(f"### 모듈4-A 녹지 접근성(도로망 도보,인구가중)  {datetime.date.today()}  구={gu}\n")
    dpoly=district_poly(gu); win=dpoly.buffer(BUFFER)

    log("[도로 그래프]")
    H,nodes=build_graph(win)
    tree=cKDTree(nodes)

    log("[인구격자]")
    pop=gpd.read_file(POP_SHP,engine="pyogrio",columns=["val"])
    pop=pop[pop.geometry.intersects(dpoly)].copy()
    pop["val"]=pd.to_numeric(pop["val"],errors="coerce")
    pop=pop[pop["val"]>0].copy()
    cen=pop.geometry.centroid
    pc=np.c_[cen.x.values, cen.y.values]
    nd,ni=tree.query(pc, k=1)           # 최근접 도로노드
    offset=nd/WALK_MPS                  # 셀↔노드 도보보정(분)
    log(f"  구내 인구셀 {len(pop):,}개, 총인구 {int(pop['val'].sum()):,}명")

    rows=[]; pop_time={}
    for year in ["2019","2024"]:
        log(f"[{year}] 녹지·접근성")
        gg=green_union(year,win)
        tmin=accessibility(H,nodes,tree,gg)
        if tmin is None:
            rows.append({"연도":year}); continue
        t_cell=tmin[ni]+offset          # 인구셀별 접근시간(분)
        w=pop["val"].values; valid=np.isfinite(t_cell)
        wmean=float(np.average(t_cell[valid],weights=w[valid]))
        row={"연도":year,"인구가중평균_분":round(wmean,2)}
        for T in THRESHOLDS:
            within=float(w[valid & (t_cell<=T)].sum()/w[valid].sum()*100)
            row[f"{T}분내_인구%"]=round(within,1)
        row["도달불가_인구%"]=round(float(w[~valid].sum()/w.sum()*100),1)
        rows.append(row); pop_time[year]=t_cell
        # gpkg 저장(셀별 시간)
        out=pop.copy(); out[f"time_min"]=t_cell
        gpath=os.path.join(outdir,f"module4A_{gu}_{year}_접근시간.gpkg")
        out[[out.geometry.name,"val","time_min"]].to_file(gpath,driver="GPKG")
        log(f"  ✓ {gpath}  (가중평균 {wmean:.1f}분)")
    # 지도(2019 기준)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from matplotlib import font_manager
        fp=r"C:\Windows\Fonts\malgun.ttf"
        if os.path.exists(fp):
            font_manager.fontManager.addfont(fp)
            plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp).get_name()
        plt.rcParams["axes.unicode_minus"]=False
        for year in ["2019","2024"]:
            if year not in pop_time: continue
            fig,ax=plt.subplots(figsize=(7,7))
            pp=pop.copy(); pp["t"]=np.clip(pop_time[year],0,30)
            pp.plot(column="t",cmap="RdYlGn_r",legend=True,ax=ax,markersize=2,
                    legend_kwds={"label":"녹지까지 도보(분)","shrink":0.6})
            ax.set_title(f"{gu} 녹지 접근성(도보시간) {year}"); ax.axis("off")
            fig.tight_layout(); fig.savefig(os.path.join(outdir,f"module4A_{gu}_{year}_접근시간.png"),dpi=140)
            plt.close(fig)
        log("  ✓ 접근성 지도 png")
    except Exception as e:
        log(f"  (지도 생략:{e})")

    summ=pd.DataFrame(rows)
    scsv=os.path.join(outdir,f"module4A_{gu}_접근성요약.csv")
    summ.to_csv(scsv,index=False,encoding="utf-8-sig")
    log("\n접근성 요약:\n"+summ.to_string(index=False))
    log(f"✓ {scsv}")
    log("="*60); log(f"모듈4-A 완료 → {outdir}")
    save_report(stamp,gu,note="[상태: 정상완료]")

if __name__=="__main__":
    gu=sys.argv[1] if len(sys.argv)>1 else "수성구"
    stamp=datetime.date.today().strftime("%Y%m%d")
    try: main()
    except SystemExit: raise
    except Exception:
        import traceback; log("\n!!! 예외 중단:\n"+traceback.format_exc())
        save_report(stamp,gu,note="[상태: 실패/중단]"); raise
