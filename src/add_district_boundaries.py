# -*- coding: utf-8 -*-
r"""
대구 전역 분석 지도 재생성 (구군 경계·레이블 포함)
================================================
GIS 데이터로부터 접근성, 연결성 지도를 재생성하되
구군 경계와 명칭을 포함시킵니다.

실행: python src/add_district_boundaries.py
"""
import os, sys, io, platform
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import warnings
warnings.filterwarnings('ignore')

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(PROJ, "data_clean")
OUTROOT = os.path.join(PROJ, "outputs")

# 한글 폰트 설정 (Windows/Linux 모두 지원)
if platform.system() == "Windows":
    font_path = r"C:\Windows\Fonts\malgun.ttf"
    if os.path.exists(font_path):
        font_manager.fontManager.addfont(font_path)
        plt.rcParams["font.family"] = "Malgun Gothic"
else:  # Linux/macOS
    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if os.path.exists(font_path):
        font_manager.fontManager.addfont(font_path)
        plt.rcParams["font.sans-serif"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
        plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["axes.unicode_minus"] = False

def create_daegu_accessibility_maps():
    """접근성 지도 재생성 (구군 경계·레이블 포함)"""
    print("접근성 지도 생성 중...")

    districts = gpd.read_file(os.path.join(CLEAN, "districts_5179.gpkg"), engine="pyogrio")
    outdir = os.path.join(OUTROOT, "20260705")

    for year in ["2019", "2024"]:
        try:
            gpkg_path = os.path.join(outdir, f"module4A_대구_{year}_접근시간.gpkg")
            if not os.path.exists(gpkg_path):
                print(f"  ✗ {year}: GPKG 없음")
                continue

            data = gpd.read_file(gpkg_path, engine="pyogrio")

            fig, ax = plt.subplots(figsize=(12, 12), dpi=140)
            data.plot(column="time_min", cmap="RdYlGn_r", ax=ax, markersize=3,
                     legend=True, legend_kwds={"label":"녹지까지 도보(분)","shrink":0.6})

            # 구군 경계
            districts.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2, alpha=0.8)

            # 구군 레이블
            for idx, row in districts.iterrows():
                centroid = row.geometry.centroid
                ax.text(centroid.x, centroid.y, row["구군"],
                       fontsize=15, ha="center", va="center",
                       color="white",
                       bbox=dict(boxstyle="round,pad=0.3",
                                facecolor="black", alpha=0.7,
                                edgecolor="white", linewidth=1))

            ax.set_title(f"대구 녹지 접근성(도보시간) {year}", fontsize=14)
            ax.axis("off")
            fig.tight_layout()

            output_path = os.path.join(outdir, f"module4A_대구_{year}_접근시간_구경계.png")
            fig.savefig(output_path, dpi=140, bbox_inches="tight", pad_inches=0.1)
            plt.close(fig)

            print(f"  ✓ {year}: {os.path.basename(output_path)}")
        except Exception as e:
            print(f"  ✗ {year}: {e}")

def create_daegu_connectivity_maps():
    """연결성 지도 재생성 (구군 경계·레이블 포함)"""
    print("연결성 지도 생성 중...")
    import rasterio
    import matplotlib.colors as mcolors

    districts = gpd.read_file(os.path.join(CLEAN, "districts_5179.gpkg"), engine="pyogrio")
    outdir = os.path.join(OUTROOT, "20260705")

    for year in ["2019", "2024"]:
        try:
            tif_path = os.path.join(outdir, f"module4C_대구_{year}_전류밀도.tif")
            if not os.path.exists(tif_path):
                print(f"  ✗ {year}: TIF 없음")
                continue

            # TIF 파일로부터 래스터 데이터와 좌표 읽기
            with rasterio.open(tif_path) as src:
                data = src.read(1)  # 첫 번째 밴드
                transform = src.transform
                bounds = src.bounds

            fig, ax = plt.subplots(figsize=(12, 12), dpi=140)

            # 래스터 데이터 시각화 (magma colormap)
            masked_data = np.ma.masked_where(np.isnan(data), data)
            im = ax.imshow(masked_data, cmap="magma", transform=None,
                          extent=[bounds.left, bounds.right, bounds.bottom, bounds.top],
                          aspect='auto', origin='upper', interpolation='nearest')

            # 컬러바 추가
            cbar = plt.colorbar(im, ax=ax, shrink=0.6)
            cbar.set_label("회로 전류밀도", fontsize=12)

            # 구군 경계 (lime green)
            districts.plot(ax=ax, facecolor="none", edgecolor="lime", linewidth=4, alpha=1.0)
            districts.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.8, alpha=0.5)

            # 구군 레이블 (yellow background)
            for idx, row in districts.iterrows():
                centroid = row.geometry.centroid
                ax.text(centroid.x, centroid.y, row["구군"],
                       fontsize=15, ha="center", va="center",
                       color="black",
                       bbox=dict(boxstyle="round,pad=0.3",
                                facecolor="yellow", alpha=0.85,
                                edgecolor="black", linewidth=1))

            ax.set_title(f"대구 생태계 연결성(회로밀도) {year}", fontsize=14)
            ax.axis("off")
            fig.tight_layout()

            output_path = os.path.join(outdir, f"module4C_대구_{year}_전류밀도_구경계.png")
            fig.savefig(output_path, dpi=140, bbox_inches="tight", pad_inches=0.1)
            plt.close(fig)

            print(f"  ✓ {year}: {os.path.basename(output_path)}")
        except Exception as e:
            print(f"  ✗ {year}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("대구 전역 분석 지도 생성 (구군 경계·레이블 포함)")
    print("=" * 60)
    create_daegu_accessibility_maps()
    create_daegu_connectivity_maps()
    print("=" * 60)
    print("완료!")
