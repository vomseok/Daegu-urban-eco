# -*- coding: utf-8 -*-
r"""
중간산출물 4패널을 분리해서 각각 라벨 추가 후 조합
실행: python src/separate_intermediates_panels.py
"""
import os, sys, io, platform
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patheffects import withStroke
from PIL import Image
import rasterio

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR_INPUT = os.path.join(PROJ, "outputs", "20260708")
OUTDIR_OUTPUT = os.path.join(PROJ, "outputs", "20260705")
DIST = os.path.join(PROJ, "data_clean", "districts_5179.gpkg")
GRID = os.path.join(OUTDIR_OUTPUT, "module4C_대구_2019_전류밀도.tif")

# 한글 폰트 설정
if platform.system() == "Windows":
    fp = r"C:\Windows\Fonts\malgun.ttf"
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
else:
    fp = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.sans-serif"] = ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"]
        plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["axes.unicode_minus"] = False

# 좌표 시스템 정보
with rasterio.open(GRID) as ds:
    transform = ds.transform
    shape = ds.shape

bounds = rasterio.transform.array_bounds(shape[0], shape[1], transform)
extent = (bounds[0], bounds[2], bounds[1], bounds[3])

dist = gpd.read_file(DIST, engine="pyogrio")

# 원본 4패널 이미지 로드
img_path = os.path.join(OUTDIR_INPUT, "module4_중간산출물_4패널.png")
img = Image.open(img_path)
img_array = np.array(img)
h, w = img_array.shape[:2]

print(f"Original image: {w}x{h}")

# 4개 패널로 분할
panel_w = w // 2
panel_h = h // 2

panels = {
    'A': img_array[0:panel_h, 0:panel_w],
    'B': img_array[0:panel_h, panel_w:w],
    'C': img_array[panel_h:h, 0:panel_w],
    'D': img_array[panel_h:h, panel_w:w]
}

def add_labels_to_panel(panel_img, panel_name, extent, dist, panel_h, panel_w):
    """각 패널에 district labels 추가"""
    fig, ax = plt.subplots(figsize=(9.33, 9.33), dpi=96)
    ax.imshow(panel_img, extent=[0, panel_w, panel_h, 0], aspect='auto', origin='upper')

    # district 중심을 패널 좌표로 변환
    for idx, row in dist.iterrows():
        centroid = row.geometry.centroid

        # extent 범위를 [0, panel_w] x [0, panel_h]로 정규화
        x_norm = (centroid.x - extent[0]) / (extent[1] - extent[0])
        y_norm = (extent[3] - centroid.y) / (extent[3] - extent[2])

        px = x_norm * panel_w
        py = y_norm * panel_h

        # 패널 경계 체크 (5% 여백)
        margin = 0.05
        if margin < x_norm < 1-margin and margin < y_norm < 1-margin:
            t = ax.text(px, py, row["구군"],
                       fontsize=13, ha="center", va="center",
                       color="white")
            t.set_path_effects([withStroke(linewidth=2, foreground="black")])

    ax.set_xlim(0, panel_w)
    ax.set_ylim(panel_h, 0)
    ax.axis("off")
    fig.tight_layout(pad=0)

    # 이미지로 저장
    buf_path = f"/tmp/panel_{panel_name}.png"
    fig.savefig(buf_path, dpi=96, bbox_inches='tight', pad_inches=0)
    plt.close(fig)

    # 저장된 이미지 다시 로드
    result_img = Image.open(buf_path)
    result_array = np.array(result_img)
    os.remove(buf_path)

    return result_array

# 각 패널에 라벨 추가
print("Adding labels to each panel...")
labeled_panels = {}
for name, panel in panels.items():
    print(f"  Panel {name}...")
    labeled_panels[name] = add_labels_to_panel(panel, name, extent, dist, panel_h, panel_w)

# 4개 패널 조합
print("Combining panels...")
top = np.hstack([labeled_panels['A'], labeled_panels['B']])
bottom = np.hstack([labeled_panels['C'], labeled_panels['D']])
final = np.vstack([top, bottom])

# 저장
output_path = os.path.join(OUTDIR_OUTPUT, "module4_중간산출물_4패널_레이블.png")
result_img = Image.fromarray(final)
result_img.save(output_path, dpi=(96, 96))

print(f"✓ {output_path}")
