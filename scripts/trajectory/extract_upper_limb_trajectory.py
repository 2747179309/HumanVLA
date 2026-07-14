#!/usr/bin/env python3
"""Extract an unfiltered Neck/shoulder-normalized right upper-limb trajectory."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

VIDEO_ID = "pick_place_pilot_v1_E001"
ANNOTATION_VERSION = "t07a_raw_v0.2.0"
JOINT_IDS = {"Neck": 1, "RShoulder": 2, "RElbow": 3, "RWrist": 4, "LShoulder": 5}
FORCED_WRIST_MISSING = {64, 65, 143, 182, 183, 184, 185}
COORDINATE_FIELDS = (
    "neck_x_px", "neck_y_px", "neck_x_norm", "neck_y_norm",
    "shoulder_width_px", "rshoulder_x_px", "rshoulder_y_px",
    "rshoulder_x_norm", "rshoulder_y_norm", "relbow_x_px", "relbow_y_px",
    "relbow_x_norm", "relbow_y_norm", "rwrist_x_px", "rwrist_y_px",
    "rwrist_x_norm", "rwrist_y_norm", "lshoulder_x_px", "lshoulder_y_px",
    "lshoulder_x_norm", "lshoulder_y_norm",
    "neck_dx_from_first_valid_px", "neck_dy_from_first_valid_px",
    "neck_frame_dx_px", "neck_frame_dy_px",
    "neck_frame_displacement_px", "rshoulder_frame_displacement_px",
    "lshoulder_frame_displacement_px", "rshoulder_frame_dx_px",
    "rshoulder_frame_dy_px", "lshoulder_frame_dx_px", "lshoulder_frame_dy_px",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract raw RElbow/RWrist pixel and Neck/shoulder-width-normalized coordinates. "
            "No interpolation, filtering, smoothing, or filling is performed."
        )
    )
    parser.add_argument("--p001", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--phase-frames", required=True, type=Path)
    parser.add_argument("--t06c-validation", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate_sequence(rows: list[dict[str, Any]], expected: int, label: str) -> None:
    if len(rows) != expected:
        raise ValueError(f"{label} has {len(rows)} rows, expected {expected}")
    if [row.get("frame_index") for row in rows] != list(range(expected)):
        raise ValueError(f"{label} frame sequence is not 0..{expected - 1}")


def point(keypoints: list[list[float]], joint_id: int) -> tuple[float, float]:
    value = keypoints[joint_id]
    if len(value) != 3:
        raise ValueError(f"joint {joint_id} is not [x,y,confidence]")
    return float(value[0]), float(value[1])


def manual_value(mask: dict[str, Any], field: str, joint_id: int) -> str | None:
    values = mask.get(field)
    if not isinstance(values, list) or len(values) != 25:
        raise ValueError(f"quality mask lacks 25-entry {field} at frame {mask['frame_index']}")
    value = values[joint_id]
    return None if value is None else str(value)


def csv_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def worst_status(statuses: list[str]) -> str:
    priority = {"valid": 0, "low_quality": 1, "missing": 2, "out_of_frame": 3}
    return max(statuses, key=lambda status: priority[status])


def main() -> int:
    args = parse_args()
    inputs = (args.p001, args.quality_mask, args.phase_frames, args.t06c_validation)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.output_jsonl, args.output_csv)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))

    p001 = load_jsonl(args.p001)
    masks = load_jsonl(args.quality_mask)
    phases = load_jsonl(args.phase_frames)
    for rows, label in ((p001, "P001"), (masks, "quality mask"), (phases, "phase frames")):
        validate_sequence(rows, args.expected_frames, label)
    t06c_validation = json.loads(args.t06c_validation.read_text(encoding="utf-8"))
    if not t06c_validation.get("validation_passed") or t06c_validation.get("errors"):
        raise ValueError("T06C validation is not passed")
    artifacts = t06c_validation.get("manual_review", {}).get("excluded_pose_artifacts", [])
    expected_artifact = {
        "frame_index": 226, "pose_index": 1,
        "manual_status": "excluded_reflection_artifact",
    }
    if not any(all(item.get(key) == value for key, value in expected_artifact.items()) for item in artifacts):
        raise ValueError("T06C validation does not lock frame 226 pose_index=1 as excluded artifact")

    records: list[dict[str, Any]] = []
    first_valid_anchor_frame: int | None = None
    first_valid_neck: tuple[float, float] | None = None
    previous_anchor_frame: int | None = None
    previous_anchor_points: dict[str, tuple[float, float]] | None = None
    for frame, (pose, mask, phase) in enumerate(zip(p001, masks, phases)):
        if pose["video_id"] != VIDEO_ID or mask["video_id"] != VIDEO_ID or phase["video_id"] != VIDEO_ID:
            raise ValueError(f"video_id mismatch at frame {frame}")
        if pose["timestamp_sec"] != phase["timestamp_sec"] or mask["timestamp_sec"] != phase["timestamp_sec"]:
            raise ValueError(f"timestamp mismatch at frame {frame}")
        keypoints = pose["keypoints_raw"]
        confidence = pose["confidence_raw"]
        observation = mask["joint_observation_status"]
        joint_valid = mask["joint_valid"]
        if len(keypoints) != 25 or any(len(value) != 3 for value in keypoints):
            raise ValueError(f"invalid BODY_25 at frame {frame}")
        if len(confidence) != 25 or confidence != [value[2] for value in keypoints]:
            raise ValueError(f"confidence mismatch at frame {frame}")
        if len(observation) != 25 or len(joint_valid) != 25:
            raise ValueError(f"invalid quality mask at frame {frame}")

        relbow_manual_status = manual_value(mask, "manual_joint_status", 3)
        relbow_manual_reason = manual_value(mask, "manual_joint_reason", 3)
        relbow_manual_confidence = manual_value(mask, "manual_joint_confidence", 3)
        rwrist_manual_status = manual_value(mask, "manual_joint_status", 4)
        rwrist_manual_reason = manual_value(mask, "manual_joint_reason", 4)
        rwrist_manual_confidence = manual_value(mask, "manual_joint_confidence", 4)
        relbow_effective_status = (
            "low_quality" if relbow_manual_status == "unstable" else observation[3]
        )
        rwrist_effective_status = (
            "missing" if rwrist_manual_status in {"missing", "missing_or_unstable"} else observation[4]
        )

        frame_identity_valid = bool(pose["frame_valid"]) and frame not in {0, 1}
        anchor_valid = frame_identity_valid and all(joint_valid[index] for index in (1, 2, 5))
        shoulder_width: float | None = None
        neck_xy = rshoulder_xy = lshoulder_xy = None
        if anchor_valid:
            neck_xy = point(keypoints, 1)
            rshoulder_xy = point(keypoints, 2)
            lshoulder_xy = point(keypoints, 5)
            shoulder_width = math.hypot(
                rshoulder_xy[0] - lshoulder_xy[0], rshoulder_xy[1] - lshoulder_xy[1]
            )
            if not math.isfinite(shoulder_width) or shoulder_width <= 0:
                anchor_valid = False
                shoulder_width = None

        relbow_coordinate_available = (
            anchor_valid and observation[3] in {"valid", "low_quality"} and confidence[3] > 0
        )
        rwrist_coordinate_available = (
            anchor_valid and joint_valid[4] and rwrist_effective_status == "valid" and confidence[4] > 0
        )
        if frame in FORCED_WRIST_MISSING:
            rwrist_coordinate_available = False
            if rwrist_effective_status != "missing":
                raise ValueError(f"forced RWrist-missing frame {frame} is not missing in quality mask")
        relbow_xy = point(keypoints, 3) if relbow_coordinate_available else None
        rwrist_xy = point(keypoints, 4) if rwrist_coordinate_available else None

        values: dict[str, float | None] = {field: None for field in COORDINATE_FIELDS}
        if anchor_valid and neck_xy and rshoulder_xy and lshoulder_xy and shoulder_width:
            current_anchor_points = {
                "neck": neck_xy,
                "rshoulder": rshoulder_xy,
                "lshoulder": lshoulder_xy,
            }
            if first_valid_neck is None:
                first_valid_anchor_frame = frame
                first_valid_neck = neck_xy
            values.update({
                "neck_x_px": neck_xy[0], "neck_y_px": neck_xy[1],
                "neck_x_norm": 0.0, "neck_y_norm": 0.0,
                "shoulder_width_px": shoulder_width,
                "rshoulder_x_px": rshoulder_xy[0], "rshoulder_y_px": rshoulder_xy[1],
                "rshoulder_x_norm": (rshoulder_xy[0] - neck_xy[0]) / shoulder_width,
                "rshoulder_y_norm": (rshoulder_xy[1] - neck_xy[1]) / shoulder_width,
                "lshoulder_x_px": lshoulder_xy[0], "lshoulder_y_px": lshoulder_xy[1],
                "lshoulder_x_norm": (lshoulder_xy[0] - neck_xy[0]) / shoulder_width,
                "lshoulder_y_norm": (lshoulder_xy[1] - neck_xy[1]) / shoulder_width,
                "neck_dx_from_first_valid_px": neck_xy[0] - first_valid_neck[0],
                "neck_dy_from_first_valid_px": neck_xy[1] - first_valid_neck[1],
            })
            if previous_anchor_frame == frame - 1 and previous_anchor_points is not None:
                for prefix, current_point in current_anchor_points.items():
                    previous_point = previous_anchor_points[prefix]
                    dx = current_point[0] - previous_point[0]
                    dy = current_point[1] - previous_point[1]
                    values[f"{prefix}_frame_dx_px"] = dx
                    values[f"{prefix}_frame_dy_px"] = dy
                    values[f"{prefix}_frame_displacement_px"] = math.hypot(dx, dy)
            previous_anchor_frame = frame
            previous_anchor_points = current_anchor_points
            if relbow_xy:
                values.update({
                    "relbow_x_px": relbow_xy[0], "relbow_y_px": relbow_xy[1],
                    "relbow_x_norm": (relbow_xy[0] - neck_xy[0]) / shoulder_width,
                    "relbow_y_norm": (relbow_xy[1] - neck_xy[1]) / shoulder_width,
                })
            if rwrist_xy:
                values.update({
                    "rwrist_x_px": rwrist_xy[0], "rwrist_y_px": rwrist_xy[1],
                    "rwrist_x_norm": (rwrist_xy[0] - neck_xy[0]) / shoulder_width,
                    "rwrist_y_norm": (rwrist_xy[1] - neck_xy[1]) / shoulder_width,
                })

        trajectory_valid = bool(
            anchor_valid and joint_valid[3] and relbow_effective_status == "valid"
            and rwrist_coordinate_available
        )
        if not frame_identity_valid or not anchor_valid:
            trajectory_quality = "missing"
            quality_reason = pose["exclusion_reason"] or "normalization_anchor_missing"
        elif not rwrist_coordinate_available or relbow_xy is None:
            trajectory_quality = "missing"
            quality_reason = rwrist_manual_reason or relbow_manual_reason or "required_joint_missing"
        elif relbow_effective_status != "valid":
            trajectory_quality = "low_quality"
            quality_reason = relbow_manual_reason or "relbow_confidence_below_0.3"
        else:
            trajectory_quality = "valid"
            quality_reason = None

        record = {
            "video_id": VIDEO_ID, "frame_index": frame,
            "timestamp_sec": phase["timestamp_sec"], "subject_id": "P001",
            "source_pose_index": pose["pose_index"],
            "phase_id": phase["phase_id"], "phase_label": phase["phase_label"],
            **values,
            "raw_confidence": [float(confidence[JOINT_IDS[name]]) for name in JOINT_IDS],
            "trajectory_valid": trajectory_valid,
            "trajectory_quality": trajectory_quality, "quality_reason": quality_reason,
            "source_observation_status": worst_status([observation[index] for index in (1, 2, 3, 4, 5)]),
            "normalization_anchor_valid": anchor_valid,
            "normalization_origin": "Neck",
            "normalization_scale": "shoulder_width",
            "first_valid_anchor_frame": first_valid_anchor_frame,
            "absolute_pixel_coordinates_preserved": True,
            "relbow_coordinate_available": relbow_coordinate_available,
            "relbow_joint_valid": bool(joint_valid[3]),
            "relbow_source_status": observation[3],
            "relbow_effective_status": relbow_effective_status,
            "relbow_manual_status": relbow_manual_status,
            "relbow_quality_reason": relbow_manual_reason,
            "relbow_manual_confidence": relbow_manual_confidence,
            "rwrist_coordinate_available": rwrist_coordinate_available,
            "rwrist_joint_valid": bool(joint_valid[4]),
            "rwrist_source_status": observation[4],
            "rwrist_effective_status": rwrist_effective_status,
            "rwrist_manual_status": rwrist_manual_status,
            "rwrist_quality_reason": rwrist_manual_reason,
            "rwrist_manual_confidence": rwrist_manual_confidence,
            "interpolated": False, "filtered": False,
            "source": "T06C_P001_raw_BODY_25",
            "annotation_version": ANNOTATION_VERSION,
        }
        if frame in {0, 1} and any(record[field] is not None for field in COORDINATE_FIELDS):
            raise RuntimeError(f"frame {frame} contains coordinates despite invalid identity")
        if frame in FORCED_WRIST_MISSING and any(
            record[field] is not None for field in ("rwrist_x_px", "rwrist_y_px", "rwrist_x_norm", "rwrist_y_norm")
        ):
            raise RuntimeError(f"frame {frame} contains forbidden RWrist coordinates")
        records.append(record)

    if records[226]["source_pose_index"] != 0 or not records[226]["trajectory_valid"]:
        raise ValueError("frame 226 must use valid P001 pose_index=0")
    if first_valid_anchor_frame != 2:
        raise ValueError(f"first valid anchor frame is {first_valid_anchor_frame}, expected 2")
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    fieldnames = list(records[0])
    with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow({key: csv_value(value) for key, value in record.items()})
    print(json.dumps({
        "video_id": VIDEO_ID, "total_frames": len(records),
        "trajectory_valid_frames": sum(record["trajectory_valid"] for record in records),
        "relbow_coordinate_frames": sum(record["relbow_coordinate_available"] for record in records),
        "relbow_source_valid_frames": sum(record["relbow_joint_valid"] for record in records),
        "rwrist_coordinate_frames": sum(record["rwrist_coordinate_available"] for record in records),
        "forced_rwrist_missing_frames": sorted(FORCED_WRIST_MISSING),
        "output_jsonl": str(args.output_jsonl), "output_csv": str(args.output_csv),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
