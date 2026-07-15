#!/usr/bin/env python3
"""K06: ObjectGround3D — Table plane + Marker detection + Box 3D tracking.

Detection strategy:
  - A/B markers: cream X-shaped tape crosses → corner points cluster into 2 groups
  - Box: light brown cardboard, 4cm tall, starts near marker A (left)
  - Box tracking: depth-based height above table + light brown color filter

Usage:
    python object_tracker_3d.py \
        --color-dir data/azure_kinect/processed/KVAL001/color \
        --depth-dir data/azure_kinect/processed/KVAL001/depth \
        --calibration data/azure_kinect/processed/KVAL001/calibration.json \
        --output-dir results/azure_kinect/KVAL001/object3d \
        --video-id KVAL001
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import List, Optional, Tuple
import cv2, numpy as np


def fit_table_plane(depth: np.ndarray) -> Tuple[np.ndarray, float]:
    """RANSAC plane fit on lower portion of depth image."""
    h, w = depth.shape
    y_crop = int(h * 0.55)
    uu, vv = np.meshgrid(np.arange(w), np.arange(y_crop, h))
    crop = depth[y_crop:, :]
    valid = crop > 0
    Z = crop[valid].astype(np.float64) / 1000.0
    # Use depth intrinsics for coordinate mapping
    fd = 504.887  # depth fx
    cd_x, cd_y = 320.274, 327.661
    X = (uu[valid] - cd_x) * Z / fd
    Y = (vv[valid] - cd_y) * Z / fd
    pts = np.column_stack([X, Y, Z])[::8]
    n = len(pts)
    if n < 10: raise RuntimeError("Too few depth points")

    best_n, best_plane = 0, None
    rng = np.random.RandomState(42)
    for _ in range(500):
        idx = rng.choice(n, 3, replace=False)
        p0, p1, p2 = pts[idx]
        normal = np.cross(p1-p0, p2-p0)
        nn = np.linalg.norm(normal)
        if nn < 1e-9: continue
        normal /= nn
        if normal[1] > 0: normal = -normal
        d_val = -np.dot(normal, p0)
        n_in = (np.abs(np.dot(pts, normal) + d_val) < 0.02).sum()
        if n_in > best_n:
            best_n = n_in; best_plane = (normal.copy(), d_val)
    return best_plane[0], best_plane[1]


def detect_markers_from_corners(img: np.ndarray, depth: np.ndarray,
                                 table_normal: np.ndarray, table_d: float) -> List[dict]:
    """Find A/B markers as clusters of corner points (X-shaped tape crosses)."""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detect corners ONLY in cream/white regions (tape color)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    cream_mask = cv2.inRange(hsv, (0, 0, 150), (35, 60, 255))  # cream/off-white
    # Also detect via brightness: cream tape is brighter than wood table
    cream_gray = gray.copy()
    cream_gray[cream_mask == 0] = 0  # zero out non-cream pixels
    table_cream = cream_gray[2*h//3:, :]
    corners = cv2.goodFeaturesToTrack(table_cream, maxCorners=100, qualityLevel=0.01,
                                       minDistance=10, blockSize=7)
    if corners is None:
        return []

    corners = corners.reshape(-1, 2)
    # Offset back to full image
    corners[:, 1] += 2*h//3

    # Cluster corners: an X-cross has 2-4 nearby corners
    from collections import defaultdict
    clusters = []
    used = set()
    for i, (cx, cy) in enumerate(corners):
        if i in used: continue
        cluster = [(cx, cy)]
        used.add(i)
        for j, (cx2, cy2) in enumerate(corners):
            if j in used: continue
            if abs(cx-cx2) < 25 and abs(cy-cy2) < 25:
                cluster.append((cx2, cy2))
                used.add(j)
        if len(cluster) >= 1:
            cx_mean = np.mean([c[0] for c in cluster])
            cy_mean = np.mean([c[1] for c in cluster])
            # Get 3D from depth
            d_x = int(cx_mean * depth.shape[1] / w)
            d_y = int(cy_mean * depth.shape[0] / h)
            r = 3
            patch = depth[max(0,d_y-r):min(depth.shape[0],d_y+r),
                          max(0,d_x-r):min(depth.shape[1],d_x+r)]
            Z_vals = patch[patch > 0] / 1000.0
            if len(Z_vals) < 2: continue
            Z = np.median(Z_vals)
            if Z < 1.8 or Z > 4.0: continue  # table should be at 2-3m
            fd = 504.887; cd_x, cd_y = 320.274, 327.661
            X = (d_x - cd_x) * Z / fd
            Y = (d_y - cd_y) * Z / fd
            # Verify roughly on table
            height = X * table_normal[0] + Y * table_normal[1] + Z * table_normal[2] + table_d
            if abs(height) > 0.06: continue
            clusters.append({"u": float(cx_mean), "v": float(cy_mean),
                           "x": float(X), "y": float(Y), "z": float(Z),
                           "n_corners": len(cluster)})

    # Sort by horizontal position, pick two most distant clusters
    clusters.sort(key=lambda c: c["u"])
    if len(clusters) < 2:
        return clusters

    # Find the pair with distance closest to 57cm
    best = None; best_err = 999
    for i in range(len(clusters)):
        for j in range(i+1, len(clusters)):
            dist = np.sqrt((clusters[i]["x"]-clusters[j]["x"])**2 +
                          (clusters[i]["y"]-clusters[j]["y"])**2 +
                          (clusters[i]["z"]-clusters[j]["z"])**2)
            err = abs(dist - 0.57)
            if err < best_err and clusters[i]["u"] < clusters[j]["u"]:
                best_err = err; best = (clusters[i], clusters[j], dist)

    if best:
        return [best[0], best[1]]
    return clusters[:2]


def detect_box_light_brown(img: np.ndarray, depth: np.ndarray,
                            table_normal: np.ndarray, table_d: float,
                            near_marker: Optional[dict] = None) -> Optional[dict]:
    """Detect light brown box ~4cm above table, optionally near a marker."""
    h, w = img.shape[:2]
    dh, dw = depth.shape

    # Light brown: H=10-25, S=40-120, V=80-180
    img_d = cv2.resize(img, (dw, dh))
    hsv = cv2.cvtColor(img_d, cv2.COLOR_BGR2HSV)
    brown = cv2.inRange(hsv, (10, 40, 80), (25, 120, 180))

    # Height above table
    uu, vv = np.meshgrid(np.arange(dw), np.arange(dh))
    fd = 504.887; cd_x, cd_y = 320.274, 327.661
    Z = depth.astype(np.float64) / 1000.0
    Z[depth == 0] = np.nan
    X = (uu - cd_x) * Z / fd
    Y = (vv - cd_y) * Z / fd
    heights = X * table_normal[0] + Y * table_normal[1] + Z * table_normal[2] + table_d

    height_mask = (heights > 0.02) & (heights < 0.07) & (depth > 0)
    combined = height_mask & (brown > 0)

    # Restrict to near marker if provided (look within ~30cm radius)
    if near_marker:
        mx_d = int(near_marker["u"] * dw / w)
        my_d = int(near_marker["v"] * dh / h)
        dist_sq = (uu - mx_d)**2 + (vv - my_d)**2
        combined &= (dist_sq < 80**2)  # within ~80 depth-pixels (~25cm at 2.5m)

    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        combined.astype(np.uint8))

    best = None
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if 20 > area or area > 500: continue
        cx_d = int(centroids[i][0]); cy_d = int(centroids[i][1])
        Z_c = np.median(Z[labels == i])
        h_c = np.median(heights[labels == i])

        # Prefer height ~4cm
        score = area / (abs(h_c - 0.04) + 0.005)
        if best is None or score > best["score"]:
            bx = stats[i, cv2.CC_STAT_LEFT]; by = stats[i, cv2.CC_STAT_TOP]
            bw = stats[i, cv2.CC_STAT_WIDTH]; bh = stats[i, cv2.CC_STAT_HEIGHT]
            best = {"score": score,
                    "centroid_3d": [float(X[int(cy_d), int(cx_d)]),
                                    float(Y[int(cy_d), int(cx_d)]), float(Z_c)],
                    "centroid_2d": [float(cx_d * w/dw), float(cy_d * h/dh)],
                    "bbox_2d": [int(bx * w/dw), int(by * h/dh),
                               int((bx+bw) * w/dw), int((by+bh) * h/dh)],
                    "height_m": float(h_c), "area_px": int(area)}
    return best


def main():
    parser = argparse.ArgumentParser(description="K06: Object 3D Tracking")
    parser.add_argument("--color-dir", required=True, type=Path)
    parser.add_argument("--depth-dir", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--ab-distance-m", type=float, default=0.57)
    args = parser.parse_args()

    cfs = sorted(args.color_dir.glob("frame_*.jpg"))
    dfs = sorted(args.depth_dir.glob("frame_*.png"))
    print(f"{args.video_id}: {len(cfs)} frames")

    # ---- Frame 0: fit table, find markers ----
    img0 = cv2.imread(str(cfs[0]))
    dep0 = cv2.imread(str(dfs[0]), cv2.IMREAD_UNCHANGED)

    print("Fitting table plane...")
    normal, d_val = fit_table_plane(dep0)
    print(f"  Plane: {normal[0]:.4f}X + {normal[1]:.4f}Y + {normal[2]:.4f}Z + {d_val:.4f} = 0")

    print("Detecting X-tape markers (corner clusters)...")
    markers = detect_markers_from_corners(img0, dep0, normal, d_val)
    print(f"  Found {len(markers)} markers")
    marker_a, marker_b = None, None
    if len(markers) >= 2:
        marker_a, marker_b = markers[0], markers[1]  # sorted by u (left→right)
        ab_dist = np.sqrt((marker_a["x"]-marker_b["x"])**2 +
                         (marker_a["y"]-marker_b["y"])**2 +
                         (marker_a["z"]-marker_b["z"])**2)
        print(f"  A(left):  u=({marker_a['u']:.0f},{marker_a['v']:.0f}) 3D=({marker_a['x']:.3f},{marker_a['y']:.3f},{marker_a['z']:.3f})m")
        print(f"  B(right): u=({marker_b['u']:.0f},{marker_b['v']:.0f}) 3D=({marker_b['x']:.3f},{marker_b['y']:.3f},{marker_b['z']:.3f})m")
        print(f"  AB distance: {ab_dist:.3f}m (target: {args.ab_distance_m}m, error: {abs(ab_dist-args.ab_distance_m)*100:.1f}cm)")
    else:
        print("  ⚠ Could not find both markers")

    # ---- Frame-by-frame: track box ----
    print("\nTracking light brown box...")
    trajectories = []
    n_detected = 0

    for i, (cf, df_path) in enumerate(zip(cfs, dfs)):
        img = cv2.imread(str(cf))
        dep = cv2.imread(str(df_path), cv2.IMREAD_UNCHANGED)
        # Search near marker A in early frames, globally later
        near = marker_a if i < 30 else None
        box = detect_box_light_brown(img, dep, normal, d_val, near)

        rec = {"video_id": args.video_id, "frame_index": i,
               "timestamp_sec": i / 30.0, "box_detected": box is not None}
        if box:
            n_detected += 1
            rec.update({"centroid_3d_camera": box["centroid_3d"],
                        "centroid_2d_px": box["centroid_2d"],
                        "bbox_2d_px": box["bbox_2d"],
                        "height_above_table_m": box["height_m"]})
        trajectories.append(rec)

    print(f"  Detected in {n_detected}/{len(cfs)} frames ({n_detected/len(cfs)*100:.1f}%)")

    # ---- Generate annotated frames ----
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for idx in [0, len(cfs)//5, 2*len(cfs)//5, 3*len(cfs)//5, 4*len(cfs)//5, len(cfs)-1]:
        img = cv2.imread(str(cfs[idx]))
        # Draw markers
        if marker_a:
            cv2.circle(img, (int(marker_a["u"]), int(marker_a["v"])), 15, (255, 0, 0), 3)
            cv2.putText(img, "A", (int(marker_a["u"])+20, int(marker_a["v"])),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
        if marker_b:
            cv2.circle(img, (int(marker_b["u"]), int(marker_b["v"])), 15, (0, 0, 255), 3)
            cv2.putText(img, "B", (int(marker_b["u"])+20, int(marker_b["v"])),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
        # Draw box detection
        t = trajectories[idx]
        if t["box_detected"]:
            bx, by, bx2, by2 = t["bbox_2d_px"]
            cv2.rectangle(img, (bx, by), (bx2, by2), (0, 255, 0), 3)
            h_cm = t["height_above_table_m"] * 100
            cv2.putText(img, f'h={h_cm:.0f}cm',
                       (bx, by-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imwrite(str(args.output_dir / f"tracking_frame_{idx}.jpg"),
                   cv2.resize(img, (1280, 720)))

    # ---- Write outputs ----
    with open(args.output_dir / "table_plane.json", "w") as f:
        json.dump({"normal": normal.tolist(), "d": float(d_val),
                   "marker_A": marker_a, "marker_B": marker_b,
                   "ab_distance_m": ab_dist if marker_a and marker_b else None}, f, indent=2)
    with open(args.output_dir / "object_trajectory.jsonl", "w") as f:
        for rec in trajectories:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nAnnotated frames and data in {args.output_dir}/")


if __name__ == "__main__":
    main()
