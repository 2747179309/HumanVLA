#!/usr/bin/env python3
"""Bone-length-constrained pose correction for LOW-confidence Kinect joints.

Uses well-tracked left arm as anatomical reference to correct right arm joints.
Only re-projects CORRECTED joints — leaves all other 2D coordinates untouched.

Usage:
    python correct_pose_bone_constraints.py \
        --skeleton data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
        --output data/azure_kinect/processed/KVAL001/kinect_skeleton_corrected.jsonl
"""

from __future__ import annotations
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kinect_constants import KINECT_JOINT_NAMES, KinectConfidence

# Key indices
NECK, LSHO, LELB, LWRI = 3, 5, 6, 7
RSHO, RELB, RWRI = 9, 10, 11

# Bones: (right_parent, right_child, left_parent, left_child)
BONES = [(RSHO, RELB, LSHO, LELB), (RELB, RWRI, LELB, LWRI)]

# Only these 5 joints are rendered in overlay
RENDER_JOINTS = {3: "Neck", 9: "RShoulder", 10: "RElbow", 11: "RWrist", 5: "LShoulder"}


def project_one(x: float, y: float, z: float, fx: float, fy: float, cx: float, cy: float,
                R: np.ndarray, T: np.ndarray) -> Tuple[float, float]:
    """Project ONE 3D point (meters, depth frame) to 2D (color image)."""
    pc = np.array([x, y, z]) @ R.T + T  # depth→color
    if pc[2] < 1e-9:
        return (0.0, 0.0)
    u = fx * pc[0] / pc[2] + cx
    v = fy * pc[1] / pc[2] + cy
    return (float(u), float(v))


def main():
    parser = argparse.ArgumentParser(description="Bone-length-constrained pose correction")
    parser.add_argument("--skeleton", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    # Load
    with open(args.skeleton, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f if l.strip()]
    n_body = sum(1 for r in recs if r["body_id"] != -1)
    print(f"Loaded {len(recs)} frames ({n_body} with body)")

    # Load calibration
    calib_path = args.skeleton.parent / "calibration.json"
    with open(calib_path) as f:
        cal = json.load(f)
    ci = cal["color_intrinsics"]
    fx, fy, cx, cy = ci["fx"], ci["fy"], ci["cx"], ci["cy"]
    ext = cal.get("extrinsics_depth_to_color", {})
    R = np.array(ext["rotation"]) if ext else np.eye(3)
    T = np.array(ext["translation"]) / 1000.0 if ext else np.zeros(3)

    # --- Compute reference bone lengths from left arm ---
    samples = defaultdict(list)
    for r in recs:
        if r["body_id"] == -1:
            continue
        j = np.array(r["joints_3d_camera"])
        c = r["joint_confidence"]
        for rp, rc, lp, lc in BONES:
            if c[lp] >= KinectConfidence.MEDIUM and c[lc] >= KinectConfidence.MEDIUM:
                L = float(np.linalg.norm(j[lp] - j[lc]))
                if 0.05 < L < 0.60:
                    samples[(lp, lc)].append(L)

    ref = {}
    for (lp, lc), vals in samples.items():
        if len(vals) >= 10:
            ref[(lp, lc)] = float(np.median(vals))
            print(f"  Reference {KINECT_JOINT_NAMES[lp]}→{KINECT_JOINT_NAMES[lc]}: "
                  f"{ref[(lp,lc)]*100:.1f}cm (n={len(vals)})")

    if not ref:
        print("ERROR: no reference bone lengths", file=sys.stderr)
        sys.exit(1)

    # --- Apply corrections ---
    out = []
    stats = defaultdict(int)

    for r in recs:
        nr = dict(r)
        if r["body_id"] == -1:
            out.append(nr)
            continue

        j3d = np.array(r["joints_3d_camera"], dtype=np.float64)
        conf = r["joint_confidence"]

        # For each bone, correct LOW-confidence child OR child with >30% length error
        for rp, rc, lp, lc in BONES:
            ref_len = ref.get((lp, lc))
            if ref_len is None or ref_len <= 0:
                continue

            direction = j3d[rc] - j3d[rp]
            cur_len = float(np.linalg.norm(direction))

            needs_fix = (conf[rc] < KinectConfidence.MEDIUM)
            if not needs_fix and cur_len > 0.01:
                if abs(cur_len - ref_len) / ref_len > 0.30:
                    needs_fix = True

            if needs_fix and cur_len > 0.001:
                j3d[rc] = j3d[rp] + direction / cur_len * ref_len
                stats[KINECT_JOINT_NAMES[rc]] += 1

        nr["joints_3d_camera"] = j3d.tolist()

        # --- Re-project ONLY corrected joints to 2D ---
        # Keep original 2D for all other joints
        j2d = [list(uv) for uv in r["joints_2d_color"]]
        for rp, rc, lp, lc in BONES:
            rc_name = KINECT_JOINT_NAMES[rc]
            if stats.get(rc_name, 0) > 0:  # was corrected at least once
                x, y, z = j3d[rc]
                u, v = project_one(x, y, z, fx, fy, cx, cy, R, T)
                j2d[rc] = [u, v]
        nr["joints_2d_color"] = j2d
        out.append(nr)

    # Stats
    print(f"\nCorrections (per frame):")
    for name in sorted(stats):
        print(f"  {name}: {stats[name]}/{n_body} frames")

    # Write
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for nr in out:
            f.write(json.dumps(nr, ensure_ascii=False) + "\n")
    print(f"\nWritten: {args.output}")


if __name__ == "__main__":
    main()
