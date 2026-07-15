#!/usr/bin/env python3
"""Bone-length-constrained pose correction for LOW-confidence Kinect joints.

Problem: Right arm joints often have LOW confidence because of self-occlusion.
The Kinect SDK infers their positions, but bone lengths vary wildly (6-12cm
for upper arm vs expected ~25cm), causing visible misalignment in overlay.

Solution: Use the WELL-TRACKED symmetric joints (left arm) as reference for
bone lengths, then correct LOW-confidence right arm joints by:
  1. Keeping the DIRECTION from parent joint (preserves reaching motion)
  2. Scaling the bone to the REFERENCE length from left arm

This preserves the actual reaching trajectory while fixing bone length jitter.

Usage:
    python correct_pose_bone_constraints.py \
        --skeleton data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
        --output data/azure_kinect/processed/KVAL001/kinect_skeleton_corrected.jsonl \
        [--min-confidence 2]
"""

from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kinect_constants import KINECT_JOINT_NAMES, KINECT_JOINT_COUNT, KinectConfidence

# Kinect joint indices for key arm joints
# Left arm: SHOULDER_LEFT(5), ELBOW_LEFT(6), WRIST_LEFT(7)
# Right arm: SHOULDER_RIGHT(9), ELBOW_RIGHT(10), WRIST_RIGHT(11)
# Reference: NECK(3)
NECK = 3
L_SHOULDER = 5
L_ELBOW = 6
L_WRIST = 7
R_SHOULDER = 9
R_ELBOW = 10
R_WRIST = 11

# Bone definitions: (parent, child, left_parent, left_child)
BONE_CHAINS = [
    # Right bone          Left reference
    (R_SHOULDER, R_ELBOW, L_SHOULDER, L_ELBOW),   # upper arm
    (R_ELBOW, R_WRIST,   L_ELBOW, L_WRIST),        # forearm
]


def compute_bone_length(joints: np.ndarray, parent: int, child: int) -> float:
    """Compute Euclidean distance between two joints in meters."""
    return float(np.linalg.norm(joints[parent] - joints[child]))


def correct_arm_pose(
    joints_3d: np.ndarray,
    confidences: list,
    ref_bone_lengths: Dict[Tuple[int, int], float],
) -> np.ndarray:
    """Correct LOW-confidence right arm joints using bone length constraints.

    Strategy:
      For each bone (parent → child) where child has LOW confidence:
        1. Compute the DIRECTION vector from parent to child
        2. Normalize and scale to the reference bone length
        3. New child position = parent + direction_normalized * ref_length

    This preserves the reaching motion (direction) while enforcing
    anatomically correct bone lengths.
    """
    corrected = joints_3d.copy()

    for (r_parent, r_child, l_parent, l_child) in BONE_CHAINS:
        # Get reference bone length from left arm (current frame if valid)
        ref_len = ref_bone_lengths.get((l_parent, l_child))

        if ref_len is None or ref_len <= 0:
            continue

        child_conf = confidences[r_child]

        # Check bone length plausibility
        direction = corrected[r_child] - corrected[r_parent]
        current_len = float(np.linalg.norm(direction))

        # Correct if:
        # 1. Child has LOW/NONE confidence (always fix), OR
        # 2. Bone length deviates >30% from reference (fix even if MEDIUM)
        needs_correction = (child_conf < KinectConfidence.MEDIUM)
        if not needs_correction and current_len > 0.01:
            deviation = abs(current_len - ref_len) / ref_len
            if deviation > 0.30:  # >30% off from reference
                needs_correction = True

        if not needs_correction:
            continue

        if current_len < 0.001:
            continue  # degenerate

        # Normalize and scale to reference length
        direction_norm = direction / current_len
        corrected[r_child] = corrected[r_parent] + direction_norm * ref_len

    return corrected


def compute_reference_bone_lengths(
    records: List[dict],
) -> Dict[Tuple[int, int], float]:
    """Compute median bone lengths from well-tracked left arm across all frames.

    Only uses frames where BOTH parent and child have MEDIUM+ confidence.
    Returns median length for each bone pair.
    """
    bone_samples = defaultdict(list)

    for rec in records:
        if rec["body_id"] == -1:
            continue
        joints = np.array(rec["joints_3d_camera"])
        confs = rec["joint_confidence"]

        for (r_parent, r_child, l_parent, l_child) in BONE_CHAINS:
            # Only use left arm (reference) when well-tracked
            if confs[l_parent] >= KinectConfidence.MEDIUM and \
               confs[l_child] >= KinectConfidence.MEDIUM:
                length = compute_bone_length(joints, l_parent, l_child)
                if 0.05 < length < 0.60:  # anatomical sanity check (5cm-60cm)
                    bone_samples[(l_parent, l_child)].append(length)

    ref_lengths = {}
    for bone, samples in bone_samples.items():
        if len(samples) >= 10:
            ref_lengths[bone] = float(np.median(samples))
            pname = KINECT_JOINT_NAMES[bone[0]]
            cname = KINECT_JOINT_NAMES[bone[1]]
            print(f"  Reference bone {pname}→{cname}: "
                  f"median={ref_lengths[bone]:.4f}m (n={len(samples)})")

    return ref_lengths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bone-length-constrained pose correction for LOW-confidence joints"
    )
    parser.add_argument("--skeleton", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-confidence", type=int, default=2,
                       help="Minimum confidence to consider a joint reliable (default: 2=MEDIUM)")
    args = parser.parse_args()

    if not args.skeleton.exists():
        print(f"ERROR: skeleton not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)

    # Load data
    with open(args.skeleton, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    n_frames = len(records)
    n_with_body = sum(1 for r in records if r["body_id"] != -1)
    print(f"Loaded {n_frames} frames ({n_with_body} with body)")

    # Compute reference bone lengths from well-tracked left arm
    print("\nComputing reference bone lengths from left arm...")
    ref_lengths = compute_reference_bone_lengths(records)

    if not ref_lengths:
        print("ERROR: Could not compute any reference bone lengths", file=sys.stderr)
        sys.exit(1)

    # Apply corrections
    print(f"\nApplying bone-length constraints...")
    corrected_count = defaultdict(int)
    corrected_records = []

    for rec in records:
        if rec["body_id"] == -1:
            corrected_records.append(rec)
            continue

        joints = np.array(rec["joints_3d_camera"])
        confs = rec["joint_confidence"]
        corrected = correct_arm_pose(joints, confs, ref_lengths)

        # Count corrections
        for (r_parent, r_child, l_parent, l_child) in BONE_CHAINS:
            if confs[r_child] < KinectConfidence.MEDIUM:
                old_len = compute_bone_length(joints, r_parent, r_child)
                new_len = compute_bone_length(corrected, r_parent, r_child)
                if abs(new_len - ref_lengths[(l_parent, l_child)]) < 0.001:
                    corrected_count[KINECT_JOINT_NAMES[r_child]] += 1

        rec_new = dict(rec)
        rec_new["joints_3d_camera"] = corrected.tolist()
        # Recompute 2D will happen after re-projection
        corrected_records.append(rec_new)

    # Summary
    print(f"\nCorrections applied:")
    for name, count in sorted(corrected_count.items()):
        print(f"  {name}: {count}/{n_with_body} frames corrected")

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in corrected_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nCorrected skeleton written to {args.output}")

    # Re-project to 2D using the same calibration
    calib_path = args.skeleton.parent / "calibration.json"
    if calib_path.exists():
        with open(calib_path) as f:
            calib = json.load(f)

        ci = calib["color_intrinsics"]
        fx, fy, cx, cy = ci["fx"], ci["fy"], ci["cx"], ci["cy"]
        ext = calib.get("extrinsics_depth_to_color", {})
        R = np.array(ext["rotation"]) if ext else np.eye(3)
        T = np.array(ext["translation"]) / 1000.0 if ext else np.zeros(3)

        print(f"\nRe-projecting corrected 3D to 2D (with extrinsics)...")
        for rec in corrected_records:
            if rec["body_id"] == -1:
                continue
            joints = np.array(rec["joints_3d_camera"])
            # Transform depth→color
            joints_color = joints @ R.T + T
            # Project
            X, Y, Z = joints_color[:, 0], joints_color[:, 1], joints_color[:, 2]
            uv = np.zeros((len(joints), 2))
            valid = Z > 1e-6
            uv[valid, 0] = fx * X[valid] / Z[valid] + cx
            uv[valid, 1] = fy * Y[valid] / Z[valid] + cy
            rec["joints_2d_color"] = uv.tolist()

    # Write final output with updated 2D
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in corrected_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Final output with reprojected 2D written to {args.output}")


if __name__ == "__main__":
    main()
