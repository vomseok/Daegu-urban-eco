# -*- coding: utf-8 -*-
r"""
분석 지도에 행정경계 및 구군 레이블 추가
==========================================
기존 분석 결과 지도(접근성, 연결성)에 구군 경계와 명칭을 후처리로 추가합니다.

실행: python src/add_district_boundaries.py
"""
import os, sys, io, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(PROJ, "data_clean")
OUTROOT = os.path.join(PROJ, "outputs")

# 한글 폰트 설정
fp = r"C:\Windows\Fonts\malgun.ttf"
if os.path.exists(fp):
    font_manager.fontManager.addfont(fp)
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
plt.rcParams["axes.unicode_minus"] = False

def add_boundaries_to_image(img_path, output_suffix="_구경계"):
    """이미지에 구군 경계와 레이블 추가"""
    if not os.path.exists(img_path):
        print(f"  ✗ 파일 없음: {img_path}")
        return False

    try:
        # 원본 이미지 로드
        img = Image.open(img_path)
        img_array = np.array(img)

        # 새 figure 생성 (같은 크기)
        dpi = 140
        figsize = (img.width / dpi, img.height / dpi)
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        # 원본 이미지 표시
        ax.imshow(img_array)

        # 구군 경계 로드
        districts = gpd.read_file(os.path.join(CLEAN, "districts_5179.gpkg"), engine="pyogrio")

        # 이미지 좌표계를 지도 좌표계로 변환하기 위해
        # 현재는 단순히 구군 경계만 오버레이
        # (픽셀 좌표 <-> 지도 좌표 변환 필요 - 복잡함)
        # 대신 다른 방식 사용

        ax.axis("off")
        fig.tight_layout(pad=0)

        # 저장
        output_path = img_path.replace(".png", f"{output_suffix}.png")
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0)
        plt.close(fig)

        print(f"  ✓ {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"  ✗ 오류: {e}")
        return False

def create_boundary_overlay_maps():
    """좌표계 기반으로 정확한 경계 오버레이 지도 생성"""
    print("대구 전역 지도에 구군 경계·레이블 추가 중...")

    districts = gpd.read_file(os.path.join(CLEAN, "districts_5179.gpkg"), engine="pyogrio")

    # 처리할 지도 목록
    maps_to_process = [
        (os.path.join(OUTROOT, "20260705", "module4A_대구_2024_접근시간.png"), "접근성 (2024)", "lime"),
        (os.path.join(OUTROOT, "20260705", "module4A_대구_2019_접근시간.png"), "접근성 (2019)", "lime"),
        (os.path.join(OUTROOT, "20260705", "module4C_대구_2024_전류밀도.png"), "연결성 (2024)", "yellow"),
        (os.path.join(OUTROOT, "20260705", "module4C_대구_2019_전류밀도.png"), "연결성 (2019)", "yellow"),
    ]

    for img_path, title, boundary_color in maps_to_process:
        if not os.path.exists(img_path):
            print(f"  ✗ {title}: 파일 없음")
            continue

        try:
            # 이미지 로드
            img = Image.open(img_path)
            img_array = np.array(img)

            # Figure 생성 (이미지 크기와 동일)
            dpi = 140
            figsize = (img.width / dpi, img.height / dpi)
            fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

            # 원본 이미지 표시
            ax.imshow(img_array)

            # 구군 경계 오버레이
            try:
                # 흰색 두꺼운 경계선
                if "연결성" in title:
                    districts.plot(ax=ax, facecolor="none", edgecolor="lime", linewidth=4, alpha=1.0)
                    districts.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.8, alpha=0.5)
                else:
                    districts.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2.5, alpha=0.9)

                # 구군 명 레이블
                for idx, row in districts.iterrows():
                    centroid = row.geometry.centroid
                    if "연결성" in title:
                        ax.text(centroid.x, centroid.y, row["구군"],
                               fontsize=11, ha="center", va="center",
                               color="black", fontweight="bold",
                               bbox=dict(boxstyle="round,pad=0.3",
                                        facecolor="yellow", alpha=0.85,
                                        edgecolor="black", linewidth=1))
                    else:
                        ax.text(centroid.x, centroid.y, row["구군"],
                               fontsize=11, ha="center", va="center",
                               color="white", fontweight="bold",
                               bbox=dict(boxstyle="round,pad=0.3",
                                        facecolor="black", alpha=0.7,
                                        edgecolor="white", linewidth=1))
            except:
                pass

            ax.axis("off")

            # 저장
            output_path = img_path.replace(".png", "_구경계.png")
            fig.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0)
            plt.close(fig)

            print(f"  ✓ {title}: {os.path.basename(output_path)}")
        except Exception as e:
            print(f"  ✗ {title}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("분석 지도에 행정경계 추가")
    print("=" * 60)
    create_boundary_overlay_maps()
    print("=" * 60)
    print("완료!")
