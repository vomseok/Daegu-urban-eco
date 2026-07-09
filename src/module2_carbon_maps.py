# -*- coding: utf-8 -*-
r"""대구 탄소계정 공간표현 (정밀화 반영) — 저장·흡수 분포 + 토지변화 수지 + 구별 계정.
module2_carbon 의 래스터화 함수를 재사용해 폴리시된 지도 세트를 생성.
실행: .venv\Scripts\python.exe src\module2_carbon_maps.py
"""
import os, sys, io, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features as rfeatures
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import module2_carbon as M

OUTDIR = M.OUTDIR
def p(f): return os.path.join(OUTDIR, f)
fp=r"C:\Windows\Fonts\malgun.ttf"
if os.path.exists(fp):
    font_manager.fontManager.addfont(fp); plt.rcParams["font.family"]=font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"]=False
CO2=44.0/12.0

def main():
    cf=pd.read_csv(M.COEF, encoding="utf-8-sig")
    stock=dict(zip(cf["탄소유형"],cf["탄소저장_tC_ha"].astype(float)))
    upt=dict(zip(cf["탄소유형"],cf["연간흡수_tC_ha_yr"].astype(float)))
    with rasterio.open(M.GRIDTIF) as ds: transform=ds.transform; shape=ds.shape
    dist=gpd.read_file(M.DIST, engine="pyogrio").reset_index(drop=True); dist["did"]=np.arange(1,len(dist)+1)
    didr=rfeatures.rasterize(zip(dist.geometry,dist["did"]),out_shape=shape,transform=transform,fill=0,dtype="int32")
    R24,_=M.rasterize_coef("2024",stock,upt,transform,shape)
    R19,_=M.rasterize_coef("2019",stock,upt,transform,shape)
    dstock=R24["저장평탄"]-R19["저장평탄"]
    b=rasterio.transform.array_bounds(shape[0],shape[1],transform); ext=(b[0],b[2],b[1],b[3])

    # 구별 계정(총저장 tC, 순배출 tC, 평균밀도 tC/ha)
    rows=[]
    for _,d in dist.iterrows():
        m=(didr==d["did"]); sto=np.where(m,R24["저장"],np.nan); dd=np.where(m,dstock,np.nan)
        rows.append({"구군":d["구군"],"총저장_tC":np.nansum(sto),"평균밀도_tCha":np.nanmean(sto),
                     "순배출_tC":-np.nansum(dd)})
    gu=pd.DataFrame(rows); dist=dist.merge(gu,on="구군")

    # ── 4패널 종합도 ──
    fig,axs=plt.subplots(2,2,figsize=(15,14))
    def rast(ax,arr,title,cmap,vmin,vmax,lab):
        ax.set_facecolor("#d9d9d9")
        im=ax.imshow(arr,cmap=cmap,extent=ext,origin="upper",vmin=vmin,vmax=vmax)
        dist.boundary.plot(ax=ax,color="black",linewidth=0.6)
        ax.set_title(title,fontsize=13); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im,ax=ax,shrink=0.7,label=lab)
    rast(axs[0,0],R24["저장"],"(A) 탄소저장 밀도 2024 (수종 세분)","YlGn",0,np.nanpercentile(R24["저장"],98),"tC/ha")
    rast(axs[0,1],R24["흡수"],"(B) 연간 탄소흡수 2024","YlGn",0,5,"tC/ha/yr")
    v=np.nanpercentile(np.abs(dstock[np.isfinite(dstock)]),98) or 1
    rast(axs[1,0],dstock,"(C) 토지변화 탄소수지 (2019→2024)\n빨강=배출, 파랑=축적","RdBu",-v,v,"Δ tC/ha")
    # (D) 구별 순배출 choropleth
    ax=axs[1,1]
    dist.plot(column="순배출_tC",cmap="OrRd",ax=ax,legend=True,edgecolor="black",linewidth=0.6,
              legend_kwds={"label":"구별 순배출 (tC)","shrink":0.7})
    for _,r in dist.iterrows():
        c=r.geometry.representative_point()
        ax.annotate(f"{r['구군']}\n{r['순배출_tC']/1000:.0f}k",(c.x,c.y),ha="center",fontsize=8)
    ax.set_title("(D) 구·군 순배출 탄소계정 (2019→2024)",fontsize=13); ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("대구광역시 탄소계정 공간표현 (정밀화·수종 세분 반영)",fontsize=16,y=0.995)
    fig.tight_layout(); fig.savefig(p("module2_탄소계정_종합도.png"),dpi=150); plt.close(fig)
    print("✓",p("module2_탄소계정_종합도.png"))

    # 개별 고해상: 저장 분포도
    fig,ax=plt.subplots(figsize=(10,9)); ax.set_facecolor("#d9d9d9")
    im=ax.imshow(R24["저장"],cmap="YlGn",extent=ext,origin="upper",vmin=0,vmax=np.nanpercentile(R24["저장"],98))
    dist.boundary.plot(ax=ax,color="black",linewidth=0.7)
    ax.set_title("대구광역시 탄소저장 밀도 2024 (tC/ha, 수종 세분)"); ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im,ax=ax,shrink=0.6,label="탄소저장 tC/ha")
    fig.tight_layout(); fig.savefig(p("module2_탄소저장분포_2024.png"),dpi=150); plt.close(fig)
    print("✓",p("module2_탄소저장분포_2024.png"))

    # tif 저장(재사용)
    for name,arr in [("탄소저장_2024",R24["저장"]),("탄소흡수_2024",R24["흡수"]),("탄소수지_2019_2024",dstock)]:
        prof=dict(driver="GTiff",height=shape[0],width=shape[1],count=1,dtype="float32",
                  crs="EPSG:5179",transform=transform,nodata=np.nan)
        with rasterio.open(p(f"module2_{name}.tif"),"w",**prof) as dst: dst.write(arr.astype("float32"),1)
    print("✓ tif 3종")
    # 구별 계정 표
    gu["순배출_tCO2"]=(gu["순배출_tC"]*CO2).round(0)
    gu.round(1).to_csv(p("module2_구별탄소계정.csv"),index=False,encoding="utf-8-sig")
    print(gu.round(1).sort_values("순배출_tC",ascending=False).to_string(index=False))

if __name__=="__main__":
    main()
