# -*- coding: utf-8 -*-
r"""
중간산출물 4패널 이미지 수정: 각 패널별로 분리된 라벨 추가
실행: python src/fix_intermediates_labels.py
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

# 좌표 시스템 정보 추출 (TIF 파일로부터)
with rasterio.open(GRID) as ds:
    transform = ds.transform
    shape = ds.shape

bounds = rasterio.transform.array_bounds(shape[0], shape[1], transform)
extent = (bounds[0], bounds[2], bounds[1], bounds[3])  # (left, right, bottom, top)

# 구 데이터 로드
dist = gpd.read_file(DIST, engine="pyogrio")

# 기존 4패널 이미지 로드
img_path = os.path.join(OUTDIR_INPUT, "module4_중간산출물_4패널.png")
img = Image.open(img_path)
img_array = np.array(img)
img_h, img_w = img_array.shape[:2]

print(f"Image dimensions: {img_w} x {img_h}")
print(f"Extent: {extent}")

# 각 패널의 경계 (이미지 픽셀 좌표)
panel_w = img_w // 2
panel_h = img_h // 2

panels = {
    'A': (0, 0, panel_w, panel_h),
    'B': (panel_w, 0, img_w, panel_h),
    'C': (0, panel_h, panel_w, img_h),
    'D': (panel_w, panel_h, img_w, img_h)
}

# 각 패널별 지리적 extent를 정의
# 패널별로 다를 수 있으므로, 일단 모든 패널이 같은 extent를 사용한다고 가정
# (module4_intermediates_fig.py 확인 결과)
panel_extents = {
    'A': extent,
    'B': extent,
    'C': extent,
    'D': extent
}

fig = plt.figure(figsize=(20, 18.67))
ax = fig.add_subplot(111)
ax.imshow(img_array, extent=[0, img_w, img_h, 0], aspect='auto', origin='upper')

def geom_to_panel_pixel(geom, panel_name, panels, panel_extents, img_w, img_h):
    """EPSG:5179 기하학을 이미지 픽셀 좌표로 변환 (각 패널별로)"""
    extent_p = panel_extents[panel_name]
    x1, y1, x2, y2 = panels[panel_name]
    panel_w_px = x2 - x1
    panel_h_px = y2 - y1

    centroid = geom.centroid
    x_norm = (centroid.x - extent_p[0]) / (extent_p[1] - extent_p[0])
    y_norm = (extent_p[3] - centroid.y) / (extent_p[3] - extent_p[2])

    # 패널 내에서의 픽셀 좌표
    px_rel = x_norm * panel_w_px
    py_rel = y_norm * panel_h_px

    # 전체 이미지에서의 픽셀 좌표
    px = x1 + px_rel
    py = y1 + py_rel

    return px, py, (0 <= px_rel <= panel_w_px and 0 <= py_rel <= panel_h_px)

# 각 패널에 구군 레이블 추가
for idx, row in dist.iterrows():
    for panel_name in ['A', 'B', 'C', 'D']:
        px, py, in_bounds = geom_to_panel_pixel(row.geometry, panel_name, panels, panel_extents, img_w, img_h)

        # 패널 경계 내에 있는지 확인
        if in_bounds:
            # 여백(패널 가장자리에서 5% 이상)
            panel_x1, panel_y1, panel_x2, panel_y2 = panels[panel_name]
            panel_w_px = panel_x2 - panel_x1
            panel_h_px = panel_y2 - panel_y1

            px_rel = px - panel_x1
            py_rel = py - panel_y1
            margin = 0.05

            if margin < px_rel / panel_w_px < 1 - margin and margin < py_rel / panel_h_px < 1 - margin:
                t = ax.text(px, py, row["구군"],
                           fontsize=13, ha="center", va="center",
                           color="white")
                t.set_path_effects([withStroke(linewidth=2, foreground="black")])

ax.set_xlim(0, img_w)
ax.set_ylim(img_h, 0)
ax.axis("off")
fig.tight_layout(pad=0)

output_path = os.path.join(OUTDIR_OUTPUT, "module4_중간산출물_4패널_레이블.png")
fig.savefig(output_path, dpi=100, bbox_inches='tight', pad_inches=0)
plt.close(fig)

print(f"✓ {output_path}")
