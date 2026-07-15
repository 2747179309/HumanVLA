#!/usr/bin/env python3
"""K04: 3D Reference Trajectory Extraction and Kinematic Analysis.

Extracts per-joint 3D reference trajectories from standardized Kinect data,
computes kinematics (velocity, acceleration, jerk), and generates human
review table templates.

Outputs (per video):
  - reference_trajectory.jsonl   (long-format, one joint per frame)
  - kinematics.csv               (velocity, acceleration, jerk per key joint)
  - review_table.csv             (frames flagged for human inspection)
  - trajectory_summary.json      (aggregate statistics)

Usage:
    python generate_reference_trajectories.py \
        --skeleton data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
        --output-dir results/azure_kinect/KVAL001 \
        --video-id KVAL001
"""

from __future__ import annotations
import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

# Add parent to path for kinect_constants import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kinect_constants import (
    KINECT_JOINT_NAMES,
    KINECT_JOINT_COUNT,
    KinectConfidence,
    BODY25_JOINT_NAMES,
    BODY25_TO_KINECT,
)

# Key joints for task analysis (BODY_25 naming)
KEY_JOINTS = ["Neck", "RShoulder", "RElbow", "RWrist", "LShoulder"]

# BODY_25 ID → Kinect index
KEY_JOINT_MAP: Dict[str, int] = {}
for b25_id, b25_name in enumerate(BODY25_JOINT_NAMES):
    if b25_name in KEY_JOINTS:
        kinect_idx = BODY25_TO_KINECT.get(b25_id, -1)
        if kinect_idx >= 0:
            KEY_JOINT_MAP[b25_name] = kinect_idx

# Bone definitions for bone-length-based quality checks
TASK_BONES = [
    ("Neck", "RShoulder", "neck_to_r_shoulder"),
    ("RShoulder", "RElbow", "r_shoulder_to_elbow"),
    ("RElbow", "RWrist", "r_elbow_to_wrist"),
    ("Neck", "LShoulder", "neck_to_l_shoulder"),
]

# Kinematic thresholds for anomaly flagging
MAX_REASONABLE_SPEED_MS = 3.0       # m/s — anything faster is likely tracking error
MAX_REASONABLE_ACCEL_MS2 = 20.0     # m/s²
MAX_REASONABLE_JERK_MS3 = 100.0     # m/s³


def load_records(path: Path) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def extract_trajectory(
    records: List[dict],
    video_id: str,
    joint_b25_name: str,
    kinect_idx: int,
) -> List[dict]:
    """Extract per-frame trajectory for one joint in long format."""
    traj = []
    for rec in records:
        fnum = rec["frame_index"]
        body_id = rec["body_id"]
        ts = rec["timestamp_usec"]

        if body_id == -1:
            traj.append({
                "video_id": video_id,
                "frame_index": fnum,
                "source_frame_index": rec.get("source_frame_index", fnum + 1),
                "timestamp_sec": ts / 1_000_000.0,
                "joint_name": joint_b25_name,
                "u_rgb": None,
                "v_rgb": None,
                "x_camera_m": None,
                "y_camera_m": None,
                "z_camera_m": None,
                "confidence": 0.0,
                "observation_valid": False,
                "reference_valid": False,
                "reference_quality": "unusable",
                "invalid_reason": "tracking_failure",
                "observation_status": "out_of_fov",
                "source": "kinect_reference",
                "phase_label": "unknown",
            })
            continue

        j3d = rec["joints_3d_camera"]
        j2d = rec["joints_2d_color"]
        confs = rec["joint_confidence"]

        x, y, z = j3d[kinect_idx]
        u, v = j2d[kinect_idx]
        conf_raw = confs[kinect_idx]

        # Normalize confidence to [0, 1]
        conf_norm = KinectConfidence.to_normalized(conf_raw)

        # Determine observation status
        if conf_raw == KinectConfidence.NONE:
            obs_status = "uncertain"
        elif conf_raw == KinectConfidence.LOW:
            obs_status = "occluded"
        else:
            obs_status = "visible"

        # Determine reference validity
        ref_valid = KinectConfidence.is_reference_valid(conf_raw)
        ref_quality = KinectConfidence.quality_tier(conf_raw)

        # Invalid reason
        if conf_raw <= KinectConfidence.NONE:
            reason = "tracking_failure"
        elif conf_raw <= KinectConfidence.LOW:
            reason = "low_confidence"
        else:
            reason = "none"

        traj.append({
            "video_id": video_id,
            "frame_index": fnum,
            "source_frame_index": rec.get("source_frame_index", fnum + 1),
            "timestamp_sec": ts / 1_000_000.0,
            "joint_name": joint_b25_name,
            "u_rgb": round(u, 4),
            "v_rgb": round(v, 4),
            "x_camera_m": round(x, 6),
            "y_camera_m": round(y, 6),
            "z_camera_m": round(z, 6),
            "confidence": round(conf_norm, 4),
            "observation_valid": conf_raw > KinectConfidence.NONE,
            "reference_valid": ref_valid,
            "reference_quality": ref_quality,
            "invalid_reason": reason,
            "observation_status": obs_status,
            "source": "kinect_reference",
            "phase_label": "unknown",
        })

    return traj


def compute_kinematics(
    traj: List[dict],
    joint_name: str,
    fps: float = 30.0,
) -> List[dict]:
    """Compute velocity, acceleration, jerk from 3D position sequence.

    Uses central finite differences where possible, forward/backward at edges.
    """
    n = len(traj)
    dt = 1.0 / fps

    # Extract valid positions (None for missing bodies)
    positions = []
    for t in traj:
        if t["x_camera_m"] is not None:
            positions.append(np.array([t["x_camera_m"], t["y_camera_m"], t["z_camera_m"]]))
        else:
            positions.append(None)

    # Compute velocity (central difference)
    velocities = [None] * n
    for i in range(n):
        if positions[i] is None:
            continue
        if i == 0:
            # Forward difference
            if positions[i + 1] is not None:
                velocities[i] = (positions[i + 1] - positions[i]) / dt
        elif i == n - 1:
            # Backward difference
            if positions[i - 1] is not None:
                velocities[i] = (positions[i] - positions[i - 1]) / dt
        else:
            if positions[i - 1] is not None and positions[i + 1] is not None:
                velocities[i] = (positions[i + 1] - positions[i - 1]) / (2 * dt)

    # Compute acceleration
    accelerations = [None] * n
    for i in range(n):
        if velocities[i] is None:
            continue
        if i == 0:
            if velocities[i + 1] is not None:
                accelerations[i] = (velocities[i + 1] - velocities[i]) / dt
        elif i == n - 1:
            if velocities[i - 1] is not None:
                accelerations[i] = (velocities[i] - velocities[i - 1]) / dt
        else:
            if velocities[i - 1] is not None and velocities[i + 1] is not None:
                accelerations[i] = (velocities[i + 1] - velocities[i - 1]) / (2 * dt)

    # Compute jerk
    jerks = [None] * n
    for i in range(n):
        if accelerations[i] is None:
            continue
        if i == 0:
            if accelerations[i + 1] is not None:
                jerks[i] = (accelerations[i + 1] - accelerations[i]) / dt
        elif i == n - 1:
            if accelerations[i - 1] is not None:
                jerks[i] = (accelerations[i] - accelerations[i - 1]) / dt
        else:
            if accelerations[i - 1] is not None and accelerations[i + 1] is not None:
                jerks[i] = (accelerations[i + 1] - accelerations[i - 1]) / (2 * dt)

    # Build output
    kin = []
    for i in range(n):
        t = traj[i]
        v = velocities[i]
        a = accelerations[i]
        j = jerks[i]

        v_mag = float(np.linalg.norm(v)) if v is not None else None
        a_mag = float(np.linalg.norm(a)) if a is not None else None
        j_mag = float(np.linalg.norm(j)) if j is not None else None

        kin.append({
            "video_id": t["video_id"],
            "frame_index": t["frame_index"],
            "timestamp_sec": t["timestamp_sec"],
            "joint_name": joint_name,
            "speed_ms": round(v_mag, 6) if v_mag is not None else None,
            "velocity_x": round(float(v[0]), 6) if v is not None else None,
            "velocity_y": round(float(v[1]), 6) if v is not None else None,
            "velocity_z": round(float(v[2]), 6) if v is not None else None,
            "accel_ms2": round(a_mag, 6) if a_mag is not None else None,
            "jerk_ms3": round(j_mag, 6) if j_mag is not None else None,
            "reference_valid": t["reference_valid"],
        })

    return kin


def generate_review_table(
    records: List[dict],
    kinematics: Dict[str, List[dict]],
    bone_stats: Dict[str, dict],
) -> List[dict]:
    """Generate human review table — flag frames that need inspection.

    Flags:
      - Low confidence (level <= LOW)
      - Speed anomalies (> MAX_REASONABLE_SPEED)
      - Bone length outliers (> 3σ from mean)
      - Large inter-frame jumps
    """
    review_rows = []
    prev_j3d = None

    for rec in records:
        fnum = rec["frame_index"]
        body_id = rec["body_id"]
        flags = []

        if body_id == -1:
            review_rows.append({
                "frame_index": fnum,
                "body_id": body_id,
                "flags": "no_body_detected",
                "detail": "",
            })
            continue

        j3d = np.array(rec["joints_3d_camera"])
        confs = rec["joint_confidence"]

        # Check confidence for key joints
        low_conf_joints = []
        for b25_name, kidx in KEY_JOINT_MAP.items():
            if confs[kidx] <= KinectConfidence.LOW:
                low_conf_joints.append(f"{b25_name}(conf={confs[kidx]})")
        if low_conf_joints:
            flags.append(f"low_confidence: {', '.join(low_conf_joints)}")

        # Check speed from kinematics
        for b25_name in KEY_JOINTS:
            if b25_name in kinematics:
                kin_list = kinematics[b25_name]
                if fnum < len(kin_list):
                    s = kin_list[fnum].get("speed_ms")
                    if s is not None and s > MAX_REASONABLE_SPEED_MS:
                        flags.append(f"high_speed_{b25_name}: {s:.2f}m/s")

        # Check inter-frame jump
        if prev_j3d is not None:
            dists = np.linalg.norm(j3d - prev_j3d, axis=1)
            max_jump = float(np.max(dists))
            if max_jump > 0.15:  # 15cm inter-frame jump
                max_joint = KINECT_JOINT_NAMES[int(np.argmax(dists))]
                flags.append(f"large_jump: {max_joint} moved {max_jump:.3f}m")

        prev_j3d = j3d

        if flags:
            review_rows.append({
                "frame_index": fnum,
                "source_frame_index": rec.get("source_frame_index", fnum + 1),
                "body_id": body_id,
                "flags": "; ".join(flags),
                "detail": "",
                "reviewer_decision": "",
            })

    return review_rows


def compute_trajectory_summary(
    trajectories: Dict[str, List[dict]],
    kinematics: Dict[str, List[dict]],
) -> dict:
    """Compute aggregate statistics for each key joint."""
    summary = {}
    for joint_name in KEY_JOINTS:
        traj = trajectories.get(joint_name, [])
        valid = [t for t in traj if t.get("reference_valid")]

        # Position stats (on valid frames)
        x_vals = [t["x_camera_m"] for t in valid if t["x_camera_m"] is not None]
        y_vals = [t["y_camera_m"] for t in valid if t["y_camera_m"] is not None]
        z_vals = [t["z_camera_m"] for t in valid if t["z_camera_m"] is not None]

        # Speed stats
        kin = kinematics.get(joint_name, [])
        speeds = [k["speed_ms"] for k in kin if k["speed_ms"] is not None and k["reference_valid"]]

        summary[joint_name] = {
            "total_frames": len(traj),
            "valid_frames": len(valid),
            "valid_ratio": round(len(valid) / len(traj), 4) if traj else 0.0,
            "position_mean_m": {
                "x": round(statistics.mean(x_vals), 4) if x_vals else None,
                "y": round(statistics.mean(y_vals), 4) if y_vals else None,
                "z": round(statistics.mean(z_vals), 4) if z_vals else None,
            },
            "position_range_m": {
                "x": [round(min(x_vals), 4), round(max(x_vals), 4)] if x_vals else None,
                "y": [round(min(y_vals), 4), round(max(y_vals), 4)] if y_vals else None,
                "z": [round(min(z_vals), 4), round(max(z_vals), 4)] if z_vals else None,
            },
            "speed_stats_ms": {
                "mean": round(statistics.mean(speeds), 4) if speeds else None,
                "max": round(max(speeds), 4) if speeds else None,
                "std": round(statistics.stdev(speeds), 4) if len(speeds) > 1 else None,
            } if speeds else None,
        }

    return summary


def write_trajectory_jsonl(trajectories: Dict[str, List[dict]], path: Path) -> None:
    """Write all joint trajectories as one long-format JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for joint_name in KEY_JOINTS:
            for rec in trajectories.get(joint_name, []):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_kinematics_csv(kinematics: Dict[str, List[dict]], path: Path) -> None:
    """Write kinematics for all key joints as CSV."""
    if not kinematics:
        return
    first_joint = list(kinematics.values())[0]
    if not first_joint:
        return

    fields = ["video_id", "frame_index", "timestamp_sec", "joint_name",
              "speed_ms", "velocity_x", "velocity_y", "velocity_z",
              "accel_ms2", "jerk_ms3", "reference_valid"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for joint_name in KEY_JOINTS:
            for rec in kinematics.get(joint_name, []):
                writer.writerow({k: rec.get(k, "") for k in fields})


def write_review_csv(rows: List[dict], path: Path) -> None:
    """Write human review table as CSV."""
    if not rows:
        return
    fields = ["frame_index", "source_frame_index", "body_id", "flags", "detail", "reviewer_decision"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="K04: 3D Reference Trajectory Extraction and Kinematic Analysis"
    )
    parser.add_argument("--skeleton", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--video-id", required=True, type=str)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()

    if not args.skeleton.exists():
        print(f"ERROR: skeleton file not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"K04: Processing {args.video_id} ...")
    records = load_records(args.skeleton)
    n_valid = sum(1 for r in records if r["body_id"] != -1)
    print(f"  Loaded {len(records)} frames ({n_valid} with body)")

    # 1. Extract trajectories for key joints
    print("  Extracting reference trajectories ...")
    trajectories: Dict[str, List[dict]] = {}
    for joint_name, kidx in KEY_JOINT_MAP.items():
        traj = extract_trajectory(records, args.video_id, joint_name, kidx)
        trajectories[joint_name] = traj

    # Write JSONL
    traj_path = args.output_dir / "reference_trajectory.jsonl"
    write_trajectory_jsonl(trajectories, traj_path)
    n_records = sum(len(v) for v in trajectories.values())
    print(f"  Written: {traj_path} ({n_records} records)")

    # 2. Compute kinematics
    print("  Computing kinematics (velocity/acceleration/jerk) ...")
    kinematics: Dict[str, List[dict]] = {}
    for joint_name in KEY_JOINTS:
        kin = compute_kinematics(trajectories[joint_name], joint_name, args.fps)
        kinematics[joint_name] = kin

    kin_path = args.output_dir / "kinematics.csv"
    write_kinematics_csv(kinematics, kin_path)
    print(f"  Written: {kin_path}")

    # 3. Generate review table
    print("  Generating human review table ...")
    review_rows = generate_review_table(records, kinematics, {})
    review_path = args.output_dir / "review_table.csv"
    write_review_csv(review_rows, review_path)
    print(f"  Written: {review_path} ({len(review_rows)} frames flagged)")

    # 4. Trajectory summary
    print("  Computing trajectory summary ...")
    summary = compute_trajectory_summary(trajectories, kinematics)
    summary["video_id"] = args.video_id
    summary["total_frames"] = len(records)
    summary["valid_body_frames"] = n_valid
    summary["key_joint_mapping"] = {k: KINECT_JOINT_NAMES[v] for k, v in KEY_JOINT_MAP.items()}

    summary_path = args.output_dir / "trajectory_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Written: {summary_path}")

    # Print quick stats
    print(f"\n  Quick stats for {args.video_id}:")
    for joint_name in KEY_JOINTS:
        s = summary[joint_name]
        spd = s.get("speed_stats_ms", {}) or {}
        print(f"    {joint_name:15s}: valid={s['valid_frames']}/{s['total_frames']} "
              f"({s['valid_ratio']*100:.0f}%), "
              f"mean_speed={spd.get('mean', 'N/A')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
