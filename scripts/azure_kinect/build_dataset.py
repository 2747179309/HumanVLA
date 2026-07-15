#!/usr/bin/env python3
"""Build standardized Kinect skeleton dataset from raw C++ extraction output.

Reads the raw skeleton_3d_raw.txt produced by extract_joints.cpp, applies
camera projection (pinhole + calibrated), and produces:
  - skeleton_3d_raw.jsonl  (3D joint positions, camera frame, meters)
  - skeleton_2d_raw.jsonl  (2D joint positions, calibrated projection)
  - skeleton_2d_pinhole.jsonl (2D joint positions, pinhole-only projection)
  - calibration_summary.json (extracted calibration parameters)

Usage:
    python build_dataset.py \
        --input-txt /path/to/skeleton_3d_raw.txt \
        --calibration /path/to/calibration.json \
        --output-dir data/azure_kinect/processed/K01 \
        --video-id K01_reach_grasp_001 \
        [--image-width 1920] [--image-height 1080]
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Camera projection
# ============================================================================

def project_pinhole(
    x: float, y: float, z: float,
    fx: float, fy: float, cx: float, cy: float,
) -> Tuple[float, float]:
    """Simple pinhole projection: (u, v) = (fx*X/Z + cx, fy*Y/Z + cy)."""
    if z == 0.0:
        return (0.0, 0.0)
    u = fx * x / z + cx
    v = fy * y / z + cy
    return (float(u), float(v))


def project_calibrated(
    x: float, y: float, z: float,
    fx: float, fy: float, cx: float, cy: float,
    k: List[float], p: List[float],
) -> Tuple[float, float]:
    """Project 3D point to 2D using full Brown-Conrady distortion model.

    Args:
        x, y, z: 3D point in camera coordinates (meters).
        fx, fy, cx, cy: Intrinsic parameters.
        k: Radial distortion coefficients [k1, k2, k3, k4, k5, k6].
        p: Tangential distortion coefficients [p1, p2].

    Returns:
        (u, v) pixel coordinates.
    """
    if z == 0.0:
        return (0.0, 0.0)

    # Normalized image coordinates
    xn = x / z
    yn = y / z

    r2 = xn * xn + yn * yn
    r4 = r2 * r2
    r6 = r4 * r2

    # Radial distortion
    # k1*r² + k2*r⁴ + k3*r⁶ + k4*r⁸ + k5*r¹⁰ + k6*r¹²
    radial = 1.0
    r_pow = r2
    for ki in k:
        radial += ki * r_pow
        r_pow *= r2

    # Tangential distortion
    # 2*p1*xn*yn + p2*(r² + 2*xn²)
    # p1*(r² + 2*yn²) + 2*p2*xn*yn
    x_tangential = 2.0 * p[0] * xn * yn + p[1] * (r2 + 2.0 * xn * xn)
    y_tangential = p[0] * (r2 + 2.0 * yn * yn) + 2.0 * p[1] * xn * yn

    xd = xn * radial + x_tangential
    yd = yn * radial + y_tangential

    u = fx * xd + cx
    v = fy * yd + cy
    return (float(u), float(v))


# ============================================================================
# Calibration loading
# ============================================================================

def load_calibration(path: Path) -> dict:
    """Load camera calibration from JSON file.

    Expected format (from extract_joints.cpp calibration export):
    {
        "color_intrinsics": {"fx": ..., "fy": ..., "cx": ..., "cy": ...,
                             "k1":..., "k2":..., "k3":..., "k4":..., "k5":..., "k6":...,
                             "p1": 0.0, "p2": 0.0},
        "color_resolution": {"width": 1920, "height": 1080},
        ...
    }
    """
    with open(path, "r", encoding="utf-8") as f:
        calib = json.load(f)
    return calib


def get_intrinsics(calib: dict) -> Tuple[float, float, float, float, List[float], List[float]]:
    """Extract pinhole + distortion parameters from calibration dict."""
    ci = calib.get("color_intrinsics", calib)  # support both nested and flat
    fx = float(ci["fx"])
    fy = float(ci["fy"])
    cx = float(ci["cx"])
    cy = float(ci["cy"])
    k = [
        float(ci.get("k1", 0.0)),
        float(ci.get("k2", 0.0)),
        float(ci.get("k3", 0.0)),
        float(ci.get("k4", 0.0)),
        float(ci.get("k5", 0.0)),
        float(ci.get("k6", 0.0)),
    ]
    p = [
        float(ci.get("p1", 0.0)),
        float(ci.get("p2", 0.0)),
    ]
    return fx, fy, cx, cy, k, p


# ============================================================================
# Raw data parsing
# ============================================================================

def parse_raw_txt(path: Path) -> List[dict]:
    """Parse skeleton_3d_raw.txt into structured records.

    Format: frame_index|timestamp_usec|body_id|x,y,z,conf|x,y,z,conf|...
    """
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue

            frame_idx = int(parts[0])
            ts = int(parts[1])
            body_id = int(parts[2])

            joints_3d = []
            confidences = []

            if body_id != -1:
                for j_str in parts[3:]:
                    coords = j_str.split(",")
                    if len(coords) < 4:
                        continue
                    x = float(coords[0])
                    y = float(coords[1])
                    z = float(coords[2])
                    conf = int(coords[3])
                    joints_3d.append([x, y, z])
                    confidences.append(conf)

            records.append({
                "frame_index": frame_idx,
                "timestamp_usec": ts,
                "body_id": body_id,
                "joints_3d_camera": joints_3d,
                "joint_confidence": confidences,
            })

    return records


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build standardized Kinect skeleton dataset from raw extraction"
    )
    parser.add_argument(
        "--input-txt", required=True, type=Path,
        help="Path to skeleton_3d_raw.txt from extract_joints.cpp"
    )
    parser.add_argument(
        "--calibration", required=True, type=Path,
        help="Path to calibration.json with camera intrinsics"
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Output directory for JSONL files"
    )
    parser.add_argument(
        "--video-id", required=True, type=str,
        help="Video identifier"
    )
    parser.add_argument(
        "--image-width", type=int, default=1920,
        help="Expected RGB image width (for sanity check)"
    )
    parser.add_argument(
        "--image-height", type=int, default=1080,
        help="Expected RGB image height (for sanity check)"
    )
    args = parser.parse_args()

    # Validate inputs
    if not args.input_txt.exists():
        print(f"ERROR: input file not found: {args.input_txt}", file=sys.stderr)
        sys.exit(1)
    if not args.calibration.exists():
        print(f"ERROR: calibration file not found: {args.calibration}", file=sys.stderr)
        sys.exit(1)

    # Load calibration
    print(f"Loading calibration from {args.calibration} ...")
    calib = load_calibration(args.calibration)
    fx, fy, cx, cy, k, p = get_intrinsics(calib)
    print(f"  fx={fx:.3f}, fy={fy:.3f}, cx={cx:.3f}, cy={cy:.3f}")
    print(f"  k={[round(v,6) for v in k]}, p={[round(v,6) for v in p]}")
    print(f"  Resolution: {calib.get('color_resolution', {}).get('width', '?')}x"
          f"{calib.get('color_resolution', {}).get('height', '?')}")

    # Sanity check intrinsics
    if fx <= 0 or fy <= 0:
        print("ERROR: invalid focal lengths (fx, fy must be positive)", file=sys.stderr)
        sys.exit(1)
    if cx < 0 or cy < 0 or cx > args.image_width * 2 or cy > args.image_height * 2:
        print(f"WARNING: principal point ({cx}, {cy}) seems unusual for "
              f"{args.image_width}x{args.image_height} image", file=sys.stderr)

    # Load raw data
    print(f"\nParsing raw data from {args.input_txt} ...")
    records = parse_raw_txt(args.input_txt)
    print(f"  Parsed {len(records)} frames")
    valid_frames = sum(1 for r in records if r["body_id"] != -1)
    print(f"  Valid body frames: {valid_frames}")

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Process and write
    f_3d = open(args.output_dir / "skeleton_3d_raw.jsonl", "w", encoding="utf-8")
    f_2d = open(args.output_dir / "skeleton_2d_raw.jsonl", "w", encoding="utf-8")
    f_2d_pinhole = open(args.output_dir / "skeleton_2d_pinhole.jsonl", "w", encoding="utf-8")

    reproj_errors = []
    body_id_switches = 0
    last_body_id = -1
    missing_count = 0
    low_conf_count = 0
    oob_count = 0

    for rec in records:
        joints_3d = rec["joints_3d_camera"]
        confs = rec["joint_confidence"]
        body_id = rec["body_id"]

        # Body ID switch detection
        if body_id != -1 and last_body_id != -1 and body_id != last_body_id:
            body_id_switches += 1
        if body_id != -1:
            last_body_id = body_id

        # Compute 2D projections
        joints_2d_pinhole = []
        joints_2d_calib = []

        for j, (xyz, conf) in enumerate(zip(joints_3d, confs)):
            x, y, z = xyz

            # Pinhole projection
            u_pin, v_pin = project_pinhole(x, y, z, fx, fy, cx, cy)
            joints_2d_pinhole.append([u_pin, v_pin])

            # Calibrated projection (with distortion)
            u_cal, v_cal = project_calibrated(x, y, z, fx, fy, cx, cy, k, p)
            joints_2d_calib.append([u_cal, v_cal])

            # Statistics
            if conf <= 1:
                low_conf_count += 1
            if x == 0.0 and y == 0.0 and z == 0.0:
                missing_count += 1

            # Out-of-bounds check
            if u_cal != 0.0 and v_cal != 0.0:
                if u_cal < 0 or v_cal < 0 or u_cal > args.image_width or v_cal > args.image_height:
                    oob_count += 1

            # Reprojection difference (pinhole vs calibrated)
            if z != 0.0:
                err = ((u_pin - u_cal) ** 2 + (v_pin - v_cal) ** 2) ** 0.5
                reproj_errors.append(err)

        # Build output records
        meta_3d = {
            "frame_index": rec["frame_index"],
            "timestamp_usec": rec["timestamp_usec"],
            "body_id": body_id,
            "joints_3d_camera": joints_3d,
            "joints_2d_color": [],       # filled by merge script
            "joint_confidence": confs,
        }
        meta_2d = {
            "frame_index": rec["frame_index"],
            "timestamp_usec": rec["timestamp_usec"],
            "body_id": body_id,
            "joints_3d_camera": [],      # filled by merge script
            "joints_2d_color": joints_2d_calib,  # calibrated projection as primary
            "joint_confidence": confs,
        }
        meta_2d_pinhole = {
            "frame_index": rec["frame_index"],
            "timestamp_usec": rec["timestamp_usec"],
            "body_id": body_id,
            "joints_3d_camera": [],
            "joints_2d_color": joints_2d_pinhole,
            "joint_confidence": confs,
        }

        f_3d.write(json.dumps(meta_3d, ensure_ascii=False) + "\n")
        f_2d.write(json.dumps(meta_2d, ensure_ascii=False) + "\n")
        f_2d_pinhole.write(json.dumps(meta_2d_pinhole, ensure_ascii=False) + "\n")

    f_3d.close()
    f_2d.close()
    f_2d_pinhole.close()

    # Reprojection comparison stats
    if reproj_errors:
        import statistics
        print(f"\nPinhole vs Calibrated reprojection difference:")
        print(f"  Mean:  {statistics.mean(reproj_errors):.4f} px")
        print(f"  Median: {statistics.median(reproj_errors):.4f} px")
        print(f"  Max:   {max(reproj_errors):.4f} px")
        print(f"  Std:   {statistics.stdev(reproj_errors):.4f} px")
        print(f"  RMS:   {(sum(e*e for e in reproj_errors)/len(reproj_errors))**0.5:.4f} px")

    # Write quality summary
    total_joints = len(records) * 32
    quality_summary = {
        "video_id": args.video_id,
        "total_frames": len(records),
        "valid_skeleton_frames": valid_frames,
        "body_id_switch_count": body_id_switches,
        "missing_joints_count": missing_count,
        "low_confidence_joints_ratio": low_conf_count / total_joints if total_joints > 0 else 0.0,
        "out_of_bounds_projection_count": oob_count,
        "calibration": {
            "fx": fx, "fy": fy, "cx": cx, "cy": cy,
            "k1": k[0], "k2": k[1], "k3": k[2], "k4": k[3], "k5": k[4], "k6": k[5],
            "p1": p[0], "p2": p[1],
        },
    }
    qpath = args.output_dir / "quality_summary.json"
    with open(qpath, "w", encoding="utf-8") as f:
        json.dump(quality_summary, f, indent=2)
    print(f"\nQuality summary written to {qpath}")

    # Calibration copy for reference
    calib_copy_path = args.output_dir / "calibration.json"
    with open(calib_copy_path, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2)
    print(f"Calibration copy written to {calib_copy_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Build complete for {args.video_id}")
    print(f"  Frames:        {len(records)}")
    print(f"  Valid bodies:  {valid_frames}")
    print(f"  Body switches: {body_id_switches}")
    print(f"  Missing joints: {missing_count}")
    print(f"  Low confidence: {low_conf_count} ({low_conf_count/total_joints*100:.1f}%)" if total_joints > 0 else "")
    print(f"  OOB projections: {oob_count}")
    print(f"  Output: {args.output_dir}/")


if __name__ == "__main__":
    main()
