"""把 roseflower2.jpg（小红书截图）处理成 index_photo.html 用的两个资源。

产出:
  col.jpg  抠好背景、提过亮的花束
  msk.png  1 位蒙版

蒙版必须单独出。如果让页面按"接近黑"自己判断背景，暗红花瓣会被整片啃掉——
这张照片的花瓣暗到 p10 亮度只有 13。

用法: python dl/prep_photo.py <输出目录>
"""
import os
import sys

import cv2
import numpy as np

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "roseflower2.jpg")
LONG_EDGE = 680     # 长边。太大就会有比粒子还多的源像素，取样只能随机丢，会留洞
GAMMA = 0.60        # 提亮曲线。原图中位亮度只有 53/255，不提的话渲染出来一团黑
SAT = 1.16          # 提亮会冲淡颜色，饱和度补回来


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    im = cv2.imread(SRC)
    if im is None:
        raise SystemExit("读不到 " + SRC)
    h, w = im.shape[:2]

    # 1. 去掉小红书的 App 界面：上下两条纯黑带，取中间最长的一段
    rows = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).mean(axis=1)
    on = np.nonzero(rows > 30)[0]
    seg = max(np.split(on, np.where(np.diff(on) > 4)[0] + 1), key=len)
    im = im[int(seg[0]):int(seg[-1])]
    h, w = im.shape[:2]

    # 2. GrabCut 抠花束
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    cv2.rectangle(mask, (20, 180), (1000, 1580), cv2.GC_PR_FGD, -1)
    cv2.rectangle(mask, (230, 560), (880, 1250), cv2.GC_FGD, -1)
    cv2.rectangle(mask, (1010, 0), (w, h), cv2.GC_BGD, -1)      # 右边的礼品袋
    cv2.rectangle(mask, (0, 0), (w, 150), cv2.GC_BGD, -1)       # 墙面
    cv2.rectangle(mask, (0, 0), (15, h), cv2.GC_BGD, -1)
    cv2.grabCut(im, mask, None, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), 6, cv2.GC_INIT_WITH_MASK)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # 3. 礼品袋的黑缎带紧贴着花束，会被 GrabCut 带进来。
    #    那块又暗又不饱和，按颜色剔掉；右半边放宽阈值，那里缎带最粗。
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    V, S = hsv[:, :, 2].astype(int), hsv[:, :, 1].astype(int)
    right = np.zeros_like(m, bool)
    right[:, int(w * 0.60):] = True
    m[((V < 62) & (S < 80)) & right] = 0
    m[(V < 34) & (S < 90)] = 0          # 全图的死黑一律不要

    # 开运算要够大，才能把缎带那种细长条整段去掉；再闭合补回花瓣间的小洞
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((19, 19), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    nl, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    m = np.where(lab == 1 + int(np.argmax(st[1:, 4])), 255, 0).astype(np.uint8)

    ys, xs = np.nonzero(m)
    pad = 8
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(w - 1, xs.max() + pad), min(h - 1, ys.max() + pad)
    im, m = im[y0:y1 + 1, x0:x1 + 1], m[y0:y1 + 1, x0:x1 + 1]

    # 4. 缩放
    sc = LONG_EDGE / max(im.shape[:2])
    nw, nh = int(round(im.shape[1] * sc)), int(round(im.shape[0] * sc))
    im = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_AREA)
    m = np.where(cv2.resize(m, (nw, nh), interpolation=cv2.INTER_AREA) > 127, 255, 0).astype(np.uint8)

    # 5. 提亮 + 补饱和度
    lut = np.array([255.0 * ((i / 255.0) ** GAMMA) for i in range(256)]).clip(0, 255).astype(np.uint8)
    im = cv2.LUT(im, lut)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * SAT, 0, 255)
    im = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    im[m == 0] = (0, 0, 0)
    cv2.imwrite(os.path.join(out_dir, "col.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 86])
    cv2.imwrite(os.path.join(out_dir, "msk.png"), m, [cv2.IMWRITE_PNG_BILEVEL, 1])

    lum = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)[m > 127]
    print("%dx%d  前景 %.0f%%  亮度 p10=%d p50=%d p90=%d" % (
        nw, nh, 100 * m.mean() / 255,
        np.percentile(lum, 10), np.percentile(lum, 50), np.percentile(lum, 90)))
    for f in ("col.jpg", "msk.png"):
        print("  %s %d KB" % (f, os.path.getsize(os.path.join(out_dir, f)) // 1024))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
