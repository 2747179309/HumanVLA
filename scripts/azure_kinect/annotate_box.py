#!/usr/bin/env python3
"""
============================================================
  纸盒标注工具 — 用鼠标点击纸盒中心，系统自动记录坐标
============================================================

操作说明（显示在画面右下角）：
  鼠标移动  → 十字准星跟随
  鼠标左键  → 标记纸盒中心（自动跳到下一帧）
  鼠标右键  → 撤销当前帧的标记
  滚轮      → 前进/后退 10 帧
  D键       → 删除当前帧标记
  S键       → 保存所有标注
  Q键/ESC   → 退出

技巧：
  - 静止阶段每 20-30 帧点一次即可
  - 运动阶段每 5-10 帧点一次
  - 总共只需点 15-25 次

用法：
  python annotate_box.py --video-id KVAL009
============================================================
"""

import cv2, json, argparse, sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--video-id", required=True)
args = parser.parse_args()
VID = args.video_id

color_dir = Path(f"data/azure_kinect/processed/{VID}/color")
cfs = sorted(color_dir.glob("frame_*.jpg"))
n = len(cfs)
marks = {}  # frame_idx -> (u, v)

idx = 0
mx, my = 640, 360  # mouse in display coords

def mouse_cb(event, x, y, flags, param):
    global mx, my, idx
    mx, my = x, y
    if event == cv2.EVENT_LBUTTONDOWN:
        marks[idx] = (int(x * 1920/1280), int(y * 1080/720))
        idx = min(n - 1, idx + 3)  # auto-advance 3 frames
        print(f"  ✓ F{idx-10}: ({marks[idx-10][0]}, {marks[idx-10][1]})  → jumped to F{idx}")
    elif event == cv2.EVENT_RBUTTONDOWN:
        if idx in marks:
            del marks[idx]
            print(f"  ✗ Deleted F{idx}")
    elif event == cv2.EVENT_MOUSEWHEEL:
        delta = 3 if flags < 0 else -3
        idx = max(0, min(n-1, idx + delta))

cv2.namedWindow("Box Annotator", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Box Annotator", 1280, 720)
cv2.setMouseCallback("Box Annotator", mouse_cb)

# Load existing annotations
existing_path = Path(f"results/azure_kinect/{VID}/object3d/manual_annotations.json")
if existing_path.exists():
    with open(existing_path) as f:
        existing = json.load(f)
        for f_idx, u, v in existing["annotations"]:
            marks[f_idx] = (u, v)
    print(f"Loaded {len(marks)} existing annotations")
    # Jump to first unmarked frame
    for i in range(n):
        if i not in marks:
            idx = i
            break

print(f"\n{'='*50}")
print(f"  {VID} ({n} 帧) | 已有标注: {len(marks)}")
print(f"  左键标记 | 滚轮翻页 | S保存 | Q退出")
print(f"{'='*50}\n")

while True:
    img = cv2.imread(str(cfs[idx]))
    h, w = img.shape[:2]
    display = cv2.resize(img, (1280, 720))

    # Faint grid
    for x in range(0, 1280, 100):
        cv2.line(display, (x, 0), (x, 720), (50, 50, 50), 1)
    for y in range(0, 720, 100):
        cv2.line(display, (0, y), (1280, y), (50, 50, 50), 1)

    # Yellow crosshair at mouse
    cv2.line(display, (mx-15, my), (mx+15, my), (0, 255, 255), 2)
    cv2.line(display, (mx, my-15), (mx, my+15), (0, 255, 255), 2)

    # Show current mark
    m = marks.get(idx)
    if m:
        mx2 = int(m[0] * 1280/1920); my2 = int(m[1] * 720/1080)
        cv2.circle(display, (mx2, my2), 10, (0, 255, 0), -1)
        cv2.putText(display, f"({m[0]},{m[1]})", (mx2+15, my2),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Show nearby marks as yellow dots
    for fi in range(max(0, idx-30), min(n, idx+30)):
        mi = marks.get(fi)
        if mi and fi != idx:
            cv2.circle(display, (int(mi[0]*1280/1920), int(mi[1]*720/1080)), 4, (0, 200, 200), -1)

    # === HUD ===
    # Top bar
    cv2.rectangle(display, (0, 0), (1280, 55), (20, 20, 20), -1)
    cv2.putText(display, f"{VID} | Frame {idx}/{n-1} | Marks: {len(marks)}",
               (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Bottom bar
    cv2.rectangle(display, (0, 660), (1280, 720), (20, 20, 20), -1)
    yb = 685
    cv2.putText(display, "LEFT CLICK: mark  |  RIGHT CLICK: undo  |  SCROLL: +/-10 frames  |  S: save  |  Q: quit",
               (15, yb), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    cv2.putText(display, f"Mouse: u={int(mx*1920/1280)} v={int(my*1080/720)}",
               (15, yb+20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

    # Right panel — quick stats
    panel_x = 1050
    cv2.putText(display, "Marked frames:", (panel_x, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    for i, fi in enumerate(sorted(marks.keys())[-8:]):
        mfi = marks[fi]
        cv2.putText(display, f"  F{fi}: ({mfi[0]},{mfi[1]})", (panel_x, 120 + i*18),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

    cv2.imshow("Box Annotator", display)
    key = cv2.waitKey(0) & 0xFF

    if key == 27 or key == ord('q'):
        break
    elif key == ord('s'):
        out_path = f"results/azure_kinect/{VID}/object3d/manual_annotations.json"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        ann_list = sorted([[f, u, v] for f, (u, v) in marks.items()])
        with open(out_path, "w") as f_out:
            json.dump({"video_id": VID, "annotations": ann_list}, f_out, indent=2)
        print(f"\n  💾 Saved {len(ann_list)} marks to {out_path}\n")
    elif key == ord('d'):
        if idx in marks:
            del marks[idx]
            print(f"  ✗ Deleted F{idx}")
    elif key == 81:  # LEFT
        idx = max(0, idx - 10)
    elif key == 83:  # RIGHT
        idx = min(n-1, idx + 10)
    elif key == ord('j'):
        idx = min(n-1, idx + 60)
    elif key == ord('k'):
        idx = max(0, idx - 60)
    elif key == ord('g'):
        try:
            new_i = int(input(f"  Go to frame (0-{n-1}): "))
            if 0 <= new_i < n: idx = new_i
        except: pass

if marks:
    out_path = f"results/azure_kinect/{VID}/object3d/manual_annotations.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    ann_list = sorted([[f, u, v] for f, (u, v) in marks.items()])
    with open(out_path, "w") as f_out:
        json.dump({"video_id": VID, "annotations": ann_list}, f_out, indent=2)
    print(f"\n💾 Auto-saved {len(ann_list)} marks to {out_path}")

cv2.destroyAllWindows()
print("Done. Annotations saved.")
