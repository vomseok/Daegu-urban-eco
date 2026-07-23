# -*- coding: utf-8 -*-
r"""
중간산출물 4패널 이미지에 구군 레이블 추가
실행: python src/add_labels_to_intermediates.py
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
# 상단: A(유형), B(저항) / 하단: C(도로), D(인구)
panel_bounds = {
    'A': (0, 0, img_w//2, img_h//2),         # 좌상단
    'B': (img_w//2, 0, img_w, img_h//2),     # 우상단
    'C': (0, img_h//2, img_w//2, img_h),     # 좌하단
    'D': (img_w//2, img_h//2, img_w, img_h)  # 우하단
}

fig, ax = plt.subplots(figsize=(20, 18.67))
ax.imshow(img_array, extent=[0, img_w, img_h, 0], aspect='auto', origin='upper')

# 대략적인 픽셀-좌표 변환 함수
# 전체 이미지가 모두 범위를 커버한다고 가정
def geom_to_pixel(geom, extent, img_w, img_h):
    """EPSG:5179 기하학 좌표를 이미지 픽셀 좌표로 변환"""
    # extent = (left, right, bottom, top)
    centroid = geom.centroid
    x_norm = (centroid.x - extent[0]) / (extent[1] - extent[0])
    y_norm = (extent[3] - centroid.y) / (extent[3] - extent[2])

    px = x_norm * img_w
    py = y_norm * img_h
    return px, py

# 각 패널에 구군 레이블 추가
for idx, row in dist.iterrows():
    px, py = geom_to_pixel(row.geometry, extent, img_w, img_h)

    # 어느 패널에 속하는지 확인
    in_panel = None
    for panel_name, (x1, y1, x2, y2) in panel_bounds.items():
        if x1 <= px < x2 and y1 <= py < y2:
            in_panel = panel_name
            break

    if in_panel:
        # 패널 내에서 표시 (가장자리 제약 없음)
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
