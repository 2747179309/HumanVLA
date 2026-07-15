#!/usr/bin/env python3
"""Analyze per-joint confidence levels and temporal stability in Kinect skeleton data.

Generates:
  1. confidence_by_joint.csv — per-joint confidence distribution statistics
  2. suspicious_transitions.csv — frames with large inter-frame joint jumps
  3. quality_mask.csv — per-frame per-joint reference_valid/quality labels

Usage:
    python analyze_joint_confidence.py \
        --skeleton data/azure_kinect/processed/K01/kinect_skeleton.jsonl \
        --output-dir results/azure_kinect/K01 \
        [--target-frames "35,36;39,40;48,49;62,63;103,104;204,205"]
"""

from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from kinect_constants import (
    KINECT_JOINT_NAMES,
    KINECT_JOINT_COUNT,
    UPPER_BODY_BONES,
    KinectConfidence,
    classify_reference_quality,
    get_invalid_reason,
    BONE_LENGTH_VARIATION_FAIL,
)


def load_skeleton(path: Path) -> List[dict]:
    """Load kinect_skeleton.jsonl."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        print(f"ERROR: no records found in {path}", file=sys.stderr)
        sys.exit(1)
    return records


def compute_confidence_stats(records: List[dict]) -> Dict[str, dict]:
    """Compute per-joint confidence statistics across all valid frames.

    Returns dict keyed by joint_name with:
      - mean, median, std of confidence level
      - counts per level (NONE=0, LOW=1, MEDIUM=2, HIGH=3)
      - valid_frame_count (frames where body_id != -1)
      - reference_valid_ratio (proportion of frames with confidence >= MEDIUM)
    """
    # Accumulate confidence values per joint
    joint_confs: Dict[str, List[int]] = {name: [] for name in KINECT_JOINT_NAMES}
    valid_frames = 0

    for rec in records:
        if rec["body_id"] == -1:
            continue
        valid_frames += 1
        confs = rec["joint_confidence"]
        for j in range(KINECT_JOINT_COUNT):
            joint_confs[KINECT_JOINT_NAMES[j]].append(confs[j])

    stats = {}
    for name in KINECT_JOINT_NAMES:
        vals = joint_confs[name]
        if not vals:
            stats[name] = {
                "mean": None, "median": None, "std": None,
                "count_none": 0, "count_low": 0, "count_medium": 0, "count_high": 0,
                "total": 0, "reference_valid_ratio": 0.0,
            }
            continue

        arr = np.array(vals, dtype=float)
        stats[name] = {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr)),
            "count_none": int(np.sum(arr == KinectConfidence.NONE)),
            "count_low": int(np.sum(arr == KinectConfidence.LOW)),
            "count_medium": int(np.sum(arr == KinectConfidence.MEDIUM)),
            "count_high": int(np.sum(arr == KinectConfidence.HIGH)),
            "total": len(vals),
            "reference_valid_ratio": float(
                np.sum(arr >= KinectConfidence.MEDIUM) / len(vals)
            ),
        }
    return stats


def compute_bone_lengths(
    records: List[dict],
) -> Dict[str, dict]:
    """Compute bone length statistics for upper-body bones.

    Returns dict keyed by bone_name with mean, std, cv (coefficient of variation),
    and per-frame lengths.
    """
    bone_data: Dict[str, List[float]] = {
        name: [] for _, _, name in UPPER_BODY_BONES
    }

    for rec in records:
        if rec["body_id"] == -1:
            continue
        j3d = np.array(rec["joints_3d_camera"])
        for p_idx, c_idx, name in UPPER_BODY_BONES:
            p = j3d[p_idx]
            c = j3d[c_idx]
            length = float(np.linalg.norm(c - p))
            bone_data[name].append(length)

    stats = {}
    for name, lengths in bone_data.items():
        if not lengths:
            stats[name] = {"mean": None, "std": None, "cv": None, "stable": False}
            continue
        arr = np.array(lengths)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        cv = std / mean if mean > 0 else float("inf")
        stats[name] = {
            "mean": mean,
            "std": std,
            "cv": cv,
            "stable": cv < BONE_LENGTH_VARIATION_FAIL,
        }
    return stats


def detect_suspicious_transitions(
    records: List[dict],
    target_pairs: Optional[Set[Tuple[int, int]]] = None,
) -> List[dict]:
    """Detect frames with large inter-frame joint jumps.

    If target_pairs is provided, only checks those (source_frame_number, source_frame_number) pairs.
    Otherwise checks all consecutive frames.
    """
    transitions = []
    last_joints = None
    last_fnum = None

    for rec in records:
        if rec["body_id"] == -1:
            last_joints = None
            last_fnum = None
            continue

        curr_joints = np.array(rec["joints_3d_camera"])
        curr_fnum = rec["source_frame_index"]

        if last_joints is not None and last_fnum is not None:
            pair = (last_fnum, curr_fnum)
            if target_pairs is None or pair in target_pairs:
                distances = np.linalg.norm(curr_joints - last_joints, axis=1)
                transitions.append({
                    "prev_frame": last_fnum,
                    "curr_frame": curr_fnum,
                    "mean_jump_m": round(float(np.mean(distances)), 4),
                    "max_jump_m": round(float(np.max(distances)), 4),
                    "max_jump_joint": KINECT_JOINT_NAMES[int(np.argmax(distances))],
                })

        last_joints = curr_joints
        last_fnum = curr_fnum

    return transitions


def generate_quality_mask(
    records: List[dict],
    bone_stats: Dict[str, dict],
) -> List[dict]:
    """Generate per-frame per-joint quality labels.

    Rules:
      - confidence >= MEDIUM + bone stable → reference_valid=true
      - confidence = LOW + bone stable → reference_valid=false, quality=low
      - confidence = NONE OR bone unstable → reference_valid=false, quality=unusable
    """
    # Map joint index to whether its associated bone is stable
    # For simplicity: a joint is "bone_stable" if all bones it participates in are stable
    joint_bone_stable = {j: True for j in range(KINECT_JOINT_COUNT)}
    for p_idx, c_idx, name in UPPER_BODY_BONES:
        stable = bone_stats.get(name, {}).get("stable", False)
        if not stable:
            joint_bone_stable[p_idx] = False
            joint_bone_stable[c_idx] = False

    mask_records = []
    for rec in records:
        fnum = rec["frame_index"]
        body_id = rec["body_id"]
        confs = rec["joint_confidence"]

        row = {
            "video_id": rec.get("video_id", ""),
            "frame_index": fnum,
            "source_frame_index": rec.get("source_frame_index", fnum),
            "body_id": body_id,
        }

        if body_id == -1:
            for j in range(KINECT_JOINT_COUNT):
                row[f"j{j:02d}_{KINECT_JOINT_NAMES[j]}_valid"] = False
                row[f"j{j:02d}_{KINECT_JOINT_NAMES[j]}_quality"] = "unusable"
                row[f"j{j:02d}_{KINECT_JOINT_NAMES[j]}_reason"] = "tracking_failure"
            mask_records.append(row)
            continue

        for j in range(KINECT_JOINT_COUNT):
            prefix = f"j{j:02d}_{KINECT_JOINT_NAMES[j]}"
            conf = confs[j]
            bone_ok = joint_bone_stable.get(j, True)
            # Determine observation status from confidence (heuristic)
            if conf == KinectConfidence.NONE:
                obs_status = "uncertain"
            elif conf == KinectConfidence.LOW:
                obs_status = "occluded"  # likely occluded or at depth edge
            else:
                obs_status = "visible"

            quality = classify_reference_quality(conf, bone_ok, obs_status)
            reason = get_invalid_reason(conf, bone_ok, obs_status)
            valid = (quality in ("high", "medium"))

            row[f"{prefix}_valid"] = valid
            row[f"{prefix}_quality"] = quality
            row[f"{prefix}_reason"] = reason

        mask_records.append(row)

    return mask_records


def write_confidence_csv(stats: Dict[str, dict], path: Path) -> None:
    """Write per-joint confidence statistics to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "joint_name", "mean_confidence", "median_confidence", "std_confidence",
            "count_none", "count_low", "count_medium", "count_high",
            "total", "reference_valid_ratio",
        ])
        for name in KINECT_JOINT_NAMES:
            s = stats[name]
            writer.writerow([
                name,
                f"{s['mean']:.3f}" if s['mean'] is not None else "N/A",
                f"{s['median']:.3f}" if s['median'] is not None else "N/A",
                f"{s['std']:.3f}" if s['std'] is not None else "N/A",
                s['count_none'], s['count_low'], s['count_medium'], s['count_high'],
                s['total'],
                f"{s['reference_valid_ratio']:.4f}",
            ])


def write_transitions_csv(transitions: List[dict], path: Path) -> None:
    """Write suspicious transitions to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["prev_frame", "curr_frame", "mean_jump_m", "max_jump_m", "max_jump_joint"])
        for t in transitions:
            writer.writerow([t["prev_frame"], t["curr_frame"],
                           t["mean_jump_m"], t["max_jump_m"], t["max_jump_joint"]])


def write_quality_mask(mask: List[dict], path: Path) -> None:
    """Write quality mask to CSV."""
    if not mask:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        # Build header from first row
        static_fields = ["video_id", "frame_index", "source_frame_index", "body_id"]
        joint_fields = [k for k in mask[0].keys() if k not in static_fields]
        writer = csv.writer(f)
        writer.writerow(static_fields + joint_fields)
        for row in mask:
            writer.writerow([row.get(k, "") for k in static_fields] +
                          [row.get(k, "") for k in joint_fields])


def write_bone_stats_csv(bone_stats: Dict[str, dict], path: Path) -> None:
    """Write bone length statistics to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bone_name", "mean_length_m", "std_length_m", "cv", "stable"])
        for name, s in bone_stats.items():
            writer.writerow([
                name,
                f"{s['mean']:.4f}" if s['mean'] is not None else "N/A",
                f"{s['std']:.4f}" if s['std'] is not None else "N/A",
                f"{s['cv']:.4f}" if s['cv'] is not None else "N/A",
                s['stable'],
            ])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Kinect joint confidence levels and generate quality masks"
    )
    parser.add_argument(
        "--skeleton", required=True, type=Path,
        help="Path to kinect_skeleton.jsonl"
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Directory for output CSV files"
    )
    parser.add_argument(
        "--target-frames", type=str, default=None,
        help="Semicolon-separated frame pairs for transition audit, e.g. '35,36;39,40'"
    )
    args = parser.parse_args()

    # Parse target frame pairs
    target_pairs: Optional[Set[Tuple[int, int]]] = None
    if args.target_frames:
        target_pairs = set()
        for chunk in args.target_frames.split(";"):
            parts = chunk.strip().split(",")
            if len(parts) == 2:
                target_pairs.add((int(parts[0]), int(parts[1])))

    # Load data
    print(f"Loading skeleton data from {args.skeleton} ...")
    records = load_skeleton(args.skeleton)
    valid_frames = sum(1 for r in records if r["body_id"] != -1)
    print(f"  Total frames: {len(records)}, with valid body: {valid_frames}")

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Confidence statistics
    print("\nComputing per-joint confidence statistics ...")
    conf_stats = compute_confidence_stats(records)
    conf_path = args.output_dir / "confidence_by_joint.csv"
    write_confidence_csv(conf_stats, conf_path)
    print(f"  Written: {conf_path}")

    # Print summary
    overall_valid = sum(
        s["count_medium"] + s["count_high"]
        for s in conf_stats.values()
    )
    overall_total = sum(s["total"] for s in conf_stats.values())
    print(f"  Overall reference_valid ratio: {overall_valid}/{overall_total} = "
          f"{overall_valid/overall_total*100:.1f}%" if overall_total > 0 else "  No data")

    # 2. Bone length analysis
    print("\nComputing bone length statistics ...")
    bone_stats = compute_bone_lengths(records)
    bone_path = args.output_dir / "bone_length_stats.csv"
    write_bone_stats_csv(bone_stats, bone_path)
    print(f"  Written: {bone_path}")
    for name, s in bone_stats.items():
        stable_mark = "✓" if s["stable"] else "✗"
        print(f"  {name:30s}: mean={s['mean']:.4f}m, cv={s['cv']:.4f}, stable={stable_mark}" if s['mean'] else f"  {name}: no data")

    # 3. Suspicious transitions
    print("\nDetecting suspicious frame transitions ...")
    transitions = detect_suspicious_transitions(records, target_pairs)
    trans_path = args.output_dir / "suspicious_transitions.csv"
    write_transitions_csv(transitions, trans_path)
    print(f"  Written: {trans_path}")
    print(f"  Found {len(transitions)} transition(s)")
    for t in transitions:
        if t["max_jump_m"] > 0.2:
            print(f"    ⚠ frame {t['prev_frame']}→{t['curr_frame']}: "
                  f"max_jump={t['max_jump_m']:.3f}m at {t['max_jump_joint']}")

    # 4. Quality mask
    print("\nGenerating quality mask ...")
    mask = generate_quality_mask(records, bone_stats)
    mask_path = args.output_dir / "quality_mask.csv"
    write_quality_mask(mask, mask_path)
    print(f"  Written: {mask_path}")
    if mask:
        # Report quality distribution for key joints
        key_joints = ["NECK", "SHOULDER_RIGHT", "ELBOW_RIGHT", "WRIST_RIGHT", "SHOULDER_LEFT"]
        for jname in key_joints:
            jidx = KINECT_JOINT_NAMES.index(jname)
            field = f"j{jidx:02d}_{jname}_quality"
            qualities = [r[field] for r in mask]
            from collections import Counter
            qc = Counter(qualities)
            print(f"  {jname}: {dict(qc)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
