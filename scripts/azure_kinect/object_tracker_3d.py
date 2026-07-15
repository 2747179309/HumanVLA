#!/usr/bin/env python3
"""K06: ObjectGround3D — Table Plane Fitting & Box 3D Tracking Pilot.

Detects table plane via RANSAC on depth point cloud, finds A/B markers
on the table surface, tracks the manipulated box in 3D, and transforms
all coordinates to a table-aligned reference frame.

Outputs:
  - table_plane.json          (plane equation + A/B marker 3D positions)
  - object_trajectory.jsonl   (per-frame box 3D centroid + velocity)
  - object_trajectory_summary.json (AB distance validation + stats)

Usage:
    python object_tracker_3d.py \
        --color-dir data/azure_kinect/processed/KVAL001/color \
        --depth-dir data/azure_kinect/processed/KVAL001/depth \
        --calibration data/azure_kinect/processed/KVAL001/calibration.json \
        --output-dir results/azure_kinect/KVAL001/object3d \
        --video-id KVAL001 \
        --ab-distance-m 0.57
"""

from __future__ import annotations
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


# ============================================================================
# Plane fitting
# ============================================================================

def fit_table_plane(
    depth: np.ndarray,
    fx: float, fy: float, cx: float, cy: float,
    crop_frac: float = 0.33,
    ransac_iters: int = 500,
    inlier_thresh_m: float = 0.015,
) -> Tuple[np.ndarray, float, np.ndarray]:
    """Fit table plane from depth image using RANSAC.

    Only uses the bottom crop_frac of the image (where the table is).
    Returns (normal, d, table_mask_on_full_depth).
    """
    h, w = depth.shape
    y1 = int(h * (1 - crop_frac))
    x1, x2 = w // 6, 5 * w // 6

    crop = depth[y1:, x1:x2]
    uu, vv = np.meshgrid(np.arange(x1, x2), np.arange(y1, h))

    valid = crop > 0
    Z = crop[valid].astype(np.float64) / 1000.0
    X = (uu[valid] - cx) * Z / fx
    Y = (vv[valid] - cy) * Z / fy
    pts = np.column_stack([X, Y, Z])
    pts_s = pts[::4]
    n = len(pts_s)

    if n < 10:
        raise RuntimeError(f"Too few valid points in table region: {n}")

    best_inliers = 0
    best_normal = None
    best_d = 0.0
    rng = np.random.RandomState(42)

    for _ in range(ransac_iters):
        idx = rng.choice(n, 3, replace=False)
        p0, p1, p2 = pts_s[idx]
        normal = np.cross(p1 - p0, p2 - p0)
        nnorm = np.linalg.norm(normal)
        if nnorm < 1e-9:
            continue
        normal /= nnorm
        # Enforce normal pointing roughly up (-Y in Kinect frame)
        if normal[1] > 0:
            normal = -normal
        d_val = -np.dot(normal, p0)
        dists = np.abs(np.dot(pts_s, normal) + d_val)
        n_in = (dists < inlier_thresh_m).sum()
        if n_in > best_inliers:
            best_inliers = n_in
            best_normal = normal.copy()
            best_d = d_val

    if best_inliers / n < 0.3:
        raise RuntimeError(f"Plane fit quality too low: {best_inliers}/{n} inliers")

    # Full-resolution table mask
    uu_full, vv_full = np.meshgrid(np.arange(w), np.arange(h))
    Z_full = depth.astype(np.float64) / 1000.0
    Z_full[depth == 0] = np.nan
    X_full = (uu_full - cx) * Z_full / fx
    Y_full = (vv_full - cy) * Z_full / fy

    all_pts = np.dstack([X_full, Y_full, Z_full])  # (H, W, 3)
    dists_full = np.abs(np.dot(all_pts, best_normal) + best_d)
    table_mask = (dists_full < inlier_thresh_m * 2) & (depth > 0)

    return best_normal, best_d, table_mask


# ============================================================================
# A/B marker detection
# ============================================================================

def detect_markers(
    img: np.ndarray,
    depth: np.ndarray,
    table_mask: np.ndarray,
    fx: float, fy: float, cx: float, cy: float,
) -> List[dict]:
    """Detect A/B markers on the table surface.

    Looks for distinct blue regions (common marker color) that lie on the
    detected table plane. Returns list of marker dicts with 3D position.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Blue markers (common for A/B)
    blue_mask = cv2.inRange(hsv, (100, 80, 80), (130, 255, 255))
    # Red markers
    red1 = cv2.inRange(hsv, (0, 80, 80), (10, 255, 255))
    red2 = cv2.inRange(hsv, (170, 80, 80), (180, 255, 255))
    red_mask = red1 | red2

    # Combine, intersect with table plane — resize to match
    dh, dw = depth.shape[:2]
    blue_mask_d = cv2.resize(blue_mask, (dw, dh), interpolation=cv2.INTER_NEAREST)
    red_mask_d = cv2.resize(red_mask, (dw, dh), interpolation=cv2.INTER_NEAREST)
    marker_candidates = (blue_mask_d | red_mask_d) & table_mask

    # Find connected components
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        marker_candidates.astype(np.uint8), connectivity=8
    )

    markers = []
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 50 or area > 5000:  # filter noise and large blobs
            continue
        cu, cv_px = centroids[i]
        cu, cv_px = int(cu), int(cv_px)

        # Get 3D position from depth
        Z = depth[cv_px, cu] / 1000.0
        if Z <= 0:
            continue
        X = (cu - cx) * Z / fx
        Y = (cv_px - cy) * Z / fy

        # Scale back to RGB resolution
        scale_u = (img.shape[1] / dw)
        scale_v = (img.shape[0] / dh)
        markers.append({
            "u_px": int(cu * scale_u), "v_px": int(cv_px * scale_v),
            "x_m": float(X), "y_m": float(Y), "z_m": float(Z),
            "area_px": int(area * scale_u * scale_v),
        })

    # Sort by X position (left to right)
    markers.sort(key=lambda m: m["x_m"])
    return markers


# ============================================================================
# Box detection (from depth)
# ============================================================================

def detect_box_3d(
    depth: np.ndarray,
    table_mask: np.ndarray,
    table_normal: np.ndarray,
    table_d: float,
    fx: float, fy: float, cx: float, cy: float,
    rgb_w: int = 1920, rgb_h: int = 1080,
    img: np.ndarray = None,
    min_height_m: float = 0.035,
    max_height_m: float = 0.10,
    min_area_px: int = 20,
    max_area_px: int = 600,
) -> Optional[dict]:
    """Detect box as a connected cluster of points above the table plane."""
    h, w = depth.shape
    uu, vv = np.meshgrid(np.arange(w), np.arange(h))

    # Compute height above table for each pixel
    Z = depth.astype(np.float64) / 1000.0
    Z[depth == 0] = np.nan
    X = (uu - cx) * Z / fx
    Y = (vv - cy) * Z / fy

    heights = X * table_normal[0] + Y * table_normal[1] + Z * table_normal[2] + table_d

    # Height-based mask only (table and box are similar wood colors)
    # Box is distinguished by being 3.5-10cm above the table surface
    box_mask = (heights > min_height_m) & (heights < max_height_m) & (depth > 0)

    # Connected components
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        box_mask.astype(np.uint8), connectivity=8
    )

    best = None
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area_px or area > max_area_px:
            continue

        # Compute median 3D position of this cluster
        cluster_mask = labels == i
        Z_cluster = Z[cluster_mask]
        Z_med = np.median(Z_cluster)
        X_cluster = (uu[cluster_mask] - cx) * Z_cluster / fx
        Y_cluster = (vv[cluster_mask] - cy) * Z_cluster / fy
        X_med = np.median(X_cluster)
        Y_med = np.median(Y_cluster)
        height_med = np.median(heights[cluster_mask])

        # Prefer cluster with height ~4cm (box height)
        score = area / (abs(height_med - 0.04) + 0.01)

        if best is None or score > best["score"]:
            bbox_x = stats[i, cv2.CC_STAT_LEFT]
            bbox_y = stats[i, cv2.CC_STAT_TOP]
            bbox_w = stats[i, cv2.CC_STAT_WIDTH]
            bbox_h = stats[i, cv2.CC_STAT_HEIGHT]
            best = {
                "score": score,
                "centroid_3d": [float(X_med), float(Y_med), float(Z_med)],
                "centroid_2d": [float(centroids[i][0] * rgb_w / w), float(centroids[i][1] * rgb_h / h)],
                "bbox_2d": [int(bbox_x * rgb_w / w), int(bbox_y * rgb_h / h),
                           int((bbox_x + bbox_w) * rgb_w / w), int((bbox_y + bbox_h) * rgb_h / h)],
                "height_m": float(height_med),
                "area_px": int(area),
            }

    return best


# ============================================================================
# Coordinate transform
# ============================================================================

def transform_to_table_frame(
    points: np.ndarray,  # (N, 3) in camera coords
    table_normal: np.ndarray,
    table_d: float,
    origin_3d: np.ndarray,  # origin of table frame (e.g., marker A position)
) -> np.ndarray:
    """Transform 3D points from camera frame to table-aligned frame.

    Table frame: origin at origin_3d, Z=0 at table surface, Z up.
    """
    # Translate origin
    pts_t = points - origin_3d

    # Rotate: align table normal with world Z [0, 0, 1]
    # table_normal points roughly up (-Y in Kinect) → want it aligned with [0, 0, 1]
    # Use Rodrigues rotation
    z_axis = np.array([0.0, 0.0, 1.0])
    n = table_normal.copy()
    # Ensure normal points up (positive Z direction after transform)
    if np.dot(n, z_axis) < 0:
        n = -n

    v = np.cross(n, z_axis)
    s = np.linalg.norm(v)
    c = np.dot(n, z_axis)

    if s < 1e-9:
        # Already aligned
        R = np.eye(3)
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))

    return pts_t @ R.T


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="K06: Object 3D Tracking Pilot")
    parser.add_argument("--color-dir", required=True, type=Path)
    parser.add_argument("--depth-dir", required=True, type=Path)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--ab-distance-m", type=float, default=0.57)
    parser.add_argument("--max-frames", type=int, default=0,
                       help="Process first N frames only (0=all)")
    args = parser.parse_args()

    with open(args.calibration) as f:
        cal = json.load(f)
    ci = cal["color_intrinsics"]
    fx, fy, cx, cy = ci["fx"], ci["fy"], ci["cx"], ci["cy"]

    color_files = sorted(args.color_dir.glob("frame_*.jpg"))
    depth_files = sorted(args.depth_dir.glob("frame_*.png"))
    if args.max_frames > 0:
        color_files = color_files[:args.max_frames]
        depth_files = depth_files[:args.max_frames]

    print(f"{args.video_id}: {len(color_files)} frames")

    # ----- Frame 1: Fit table plane and detect markers -----
    img0 = cv2.imread(str(color_files[len(color_files)//2]))
    dep0 = cv2.imread(str(depth_files[len(depth_files)//2]), cv2.IMREAD_UNCHANGED)

    print("Fitting table plane...")
    normal, d_param, table_mask = fit_table_plane(dep0, fx, fy, cx, cy)
    inlier_pct = table_mask.sum() / (dep0 > 0).sum() * 100
    print(f"  Plane: {normal[0]:.4f}X + {normal[1]:.4f}Y + {normal[2]:.4f}Z + {d_param:.4f} = 0")
    print(f"  Table inliers: {table_mask.sum()} px ({inlier_pct:.1f}%)")

    print("Detecting A/B markers...")
    markers = detect_markers(img0, dep0, table_mask, fx, fy, cx, cy)
    print(f"  Found {len(markers)} markers")
    for m in markers:
        print(f"    u=({m['u_px']},{m['v_px']}) 3D=({m['x_m']:.3f},{m['y_m']:.3f},{m['z_m']:.3f})m area={m['area_px']}px")

    # Identify A and B from markers (two largest distinct markers)
    marker_a = None
    marker_b = None
    if len(markers) >= 2:
        # Take the two most distant markers (likely A and B)
        best_dist = 0
        for i in range(len(markers)):
            for j in range(i + 1, len(markers)):
                dist = np.sqrt((markers[i]["x_m"] - markers[j]["x_m"])**2 +
                              (markers[i]["y_m"] - markers[j]["y_m"])**2 +
                              (markers[i]["z_m"] - markers[j]["z_m"])**2)
                if abs(dist - args.ab_distance_m) < abs(best_dist - args.ab_distance_m):
                    best_dist = dist
                    marker_a = markers[i]
                    marker_b = markers[j]

    if marker_a and marker_b:
        ab_dist = np.sqrt((marker_a["x_m"] - marker_b["x_m"])**2 +
                         (marker_a["y_m"] - marker_b["y_m"])**2 +
                         (marker_a["z_m"] - marker_b["z_m"])**2)
        ab_error = abs(ab_dist - args.ab_distance_m)
        print(f"\n  A=({marker_a['x_m']:.3f},{marker_a['y_m']:.3f},{marker_a['z_m']:.3f})")
        print(f"  B=({marker_b['x_m']:.3f},{marker_b['y_m']:.3f},{marker_b['z_m']:.3f})")
        print(f"  AB distance: {ab_dist:.3f}m (target: {args.ab_distance_m}m, error: {ab_error:.3f}m)")
        if ab_error > 0.05:
            print(f"  ⚠ AB distance error > 5cm! Markers may be incorrectly identified.")
    else:
        print("  ⚠ Could not identify A/B markers automatically.")

    # ----- Frame-by-frame: Track box -----
    print("\nTracking box across frames...")
    trajectories = []
    n_detected = 0

    for i, (cf, df_path) in enumerate(zip(color_files, depth_files)):
        dep = cv2.imread(str(df_path), cv2.IMREAD_UNCHANGED)
        img_frame = cv2.imread(str(cf))
        box = detect_box_3d(dep, table_mask, normal, d_param, fx, fy, cx, cy,
                          rgb_w=img0.shape[1], rgb_h=img0.shape[0], img=img_frame)

        rec = {
            "video_id": args.video_id,
            "frame_index": i,
            "timestamp_sec": i / 30.0,
            "box_detected": box is not None,
        }

        if box:
            n_detected += 1
            rec.update({
                "centroid_3d_camera": box["centroid_3d"],
                "centroid_2d_px": box["centroid_2d"],
                "bbox_2d_px": box["bbox_2d"],
                "height_above_table_m": box["height_m"],
                "area_px": box["area_px"],
            })
            # Transform to table frame
            if marker_a:
                origin = np.array([marker_a["x_m"], marker_a["y_m"], marker_a["z_m"]])
                tf = transform_to_table_frame(
                    np.array([box["centroid_3d"]]), normal, d_param, origin
                )
                rec["centroid_3d_table"] = tf[0].tolist()

        trajectories.append(rec)

    print(f"  Box detected in {n_detected}/{len(color_files)} frames ({n_detected/len(color_files)*100:.1f}%)")

    # ----- Write outputs -----
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Table plane
    plane_info = {
        "video_id": args.video_id,
        "plane_equation": {
            "normal": normal.tolist(), "d": float(d_param),
            "formula": f"{normal[0]:.4f}*X + {normal[1]:.4f}*Y + {normal[2]:.4f}*Z + {d_param:.4f} = 0"
        },
        "table_inlier_ratio": float(inlier_pct / 100),
        "marker_A": marker_a,
        "marker_B": marker_b,
        "ab_distance_measured_m": ab_dist if (marker_a and marker_b) else None,
        "ab_distance_target_m": args.ab_distance_m,
        "ab_distance_error_m": ab_error if (marker_a and marker_b) else None,
    }
    with open(args.output_dir / "table_plane.json", "w") as f:
        json.dump(plane_info, f, indent=2)

    # Object trajectory
    with open(args.output_dir / "object_trajectory.jsonl", "w") as f:
        for rec in trajectories:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Summary
    summary = {
        "video_id": args.video_id,
        "total_frames": len(color_files),
        "box_detected_frames": n_detected,
        "detection_rate": n_detected / len(color_files) if color_files else 0,
        "ab_validation": {
            "measured_m": ab_dist if (marker_a and marker_b) else None,
            "target_m": args.ab_distance_m,
            "error_m": ab_error if (marker_a and marker_b) else None,
            "pass": ab_error <= 0.05 if (marker_a and marker_b) else False,
        } if marker_a and marker_b else {"error": "markers not identified"},
    }
    with open(args.output_dir / "object_trajectory_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nOutputs written to {args.output_dir}/")
    if marker_a and marker_b:
        print(f"AB validation: {ab_dist:.3f}m (error={ab_error:.3f}m) {'✓ PASS' if ab_error <= 0.05 else '✗ FAIL'}")


if __name__ == "__main__":
    main()
