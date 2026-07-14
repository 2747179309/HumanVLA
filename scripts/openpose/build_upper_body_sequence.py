#!/usr/bin/env python3
"""Build an upper-body quality mask and merge P001 poses with phase labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

CORE_JOINTS = {"Neck": 1, "RShoulder": 2, "RElbow": 3, "RWrist": 4}
AUXILIARY_JOINTS = {"Nose": 0, "LShoulder": 5, "LElbow": 6, "LWrist": 7}
VISIBLE_JOINT_IDS = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 18})
OUT_OF_FRAME_JOINT_IDS = frozenset({8, 9, 10, 11, 12, 13, 14, 19, 20, 21, 22, 23, 24})
ANNOTATION_VERSION = "t06c_m1_v0.2.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge matched P001 BODY_25 data with T06B frame labels.")
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--phase-frames", required=True, type=Path)
    parser.add_argument("--subject-output", required=True, type=Path)
    parser.add_argument("--quality-mask-output", required=True, type=Path)
    parser.add_argument("--joint-stats", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
    parser.add_argument("--confidence-threshold", type=float, default=0.3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def joint_status(confidence: float, threshold: float) -> str:
    if confidence <= 0:
        return "missing"
    return "low_quality" if confidence < threshold else "valid"


def build_observation_mask(confidence: list[float], threshold: float) -> tuple[list[str], list[bool], list[str]]:
    observation_status: list[str] = []
    joint_valid: list[bool] = []
    visibility_reason: list[str] = []
    for joint_id, value in enumerate(confidence):
        if joint_id in OUT_OF_FRAME_JOINT_IDS:
            observation_status.append("out_of_frame")
            joint_valid.append(False)
            visibility_reason.append("outside_capture_scope")
            continue
        status = joint_status(value, threshold)
        observation_status.append(status)
        joint_valid.append(status == "valid")
        visibility_reason.append({
            "valid": "observed_within_capture_scope",
            "low_quality": "confidence_below_0.3",
            "missing": "openpose_not_detected_within_capture_scope",
        }[status])
    return observation_status, joint_valid, visibility_reason


def main() -> int:
    args = parse_args()
    for path in (args.association_jsonl, args.phase_frames):
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.subject_output, args.quality_mask_output, args.joint_stats)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))

    association = load_jsonl(args.association_jsonl)
    phases = load_jsonl(args.phase_frames)
    if len(phases) != args.expected_frames or [row["frame_index"] for row in phases] != list(range(args.expected_frames)):
        raise ValueError("phase JSONL must cover frame 0 through expected_frames-1 exactly")
    matched: dict[int, dict[str, Any]] = {}
    for record in association:
        if record.get("subject_id") == "P001":
            frame = record["frame_index"]
            if frame in matched:
                raise ValueError(f"multiple P001 association records at frame {frame}")
            matched[frame] = record

    records: list[dict[str, Any]] = []
    masks: list[dict[str, Any]] = []
    for frame, phase in enumerate(phases):
        source = matched.get(frame)
        if frame in {0, 1}:
            source = None
            missing_reason = "no_confirmed_track_identity"
        elif source is None or source.get("match_status") != "matched":
            source = None
            missing_reason = "no_reliable_pose_track_match"
        else:
            missing_reason = None
        if source is None:
            keypoints = [[0.0, 0.0, 0.0] for _ in range(25)]
            confidence = [0.0] * 25
            track_id = None if frame < 2 else (matched.get(frame) or {}).get("track_id")
            bbox = (matched.get(frame) or {}).get("bbox_xyxy")
            pose_index = None
            match_status = "missing"
            frame_status = "missing"
            frame_valid = False
        else:
            keypoints = source["keypoints"]
            confidence = source["confidence_raw"]
            if len(keypoints) != 25 or any(len(point) != 3 for point in keypoints):
                raise ValueError(f"invalid BODY_25 at frame {frame}")
            if confidence != [point[2] for point in keypoints]:
                raise ValueError(f"confidence mismatch at frame {frame}")
            track_id, bbox, pose_index = source["track_id"], source["bbox_xyxy"], source["pose_index"]
            match_status = source["match_status"]
        observation_status, joint_valid, visibility_reason = build_observation_mask(
            confidence, args.confidence_threshold
        )
        if source is not None:
            core_statuses = [observation_status[index] for index in CORE_JOINTS.values()]
            if all(status == "missing" for status in core_statuses):
                frame_status, frame_valid, missing_reason = "missing", False, "all_core_joints_missing"
            elif any(status != "valid" for status in core_statuses):
                frame_status, frame_valid = "low_quality", True
                missing_reason = "core_joint_missing_or_below_0.3"
            else:
                frame_status, frame_valid, missing_reason = "valid", True, None

        core_valid = {
            name: observation_status[index] == "valid" for name, index in CORE_JOINTS.items()
        }
        core_status = {name: observation_status[index] for name, index in CORE_JOINTS.items()}
        record = {
            "video_id": phase["video_id"], "episode_id": phase["episode_id"],
            "frame_index": frame, "timestamp_sec": phase["timestamp_sec"],
            "subject_id": "P001", "track_id": track_id, "bbox_xyxy": bbox,
            "phase_id": phase["phase_id"], "phase_label": phase["phase_label"],
            "phase_text_zh": phase["phase_text_zh"], "phase_text_en": phase["phase_text_en"],
            "object_id": phase["object_id"], "active_hand": phase["active_hand"],
            "episode_success": phase["episode_success"], "annotation_valid": phase["annotation_valid"],
            "keypoints_raw": keypoints, "confidence_raw": confidence,
            "pose_index": pose_index, "match_status": match_status,
            "quality_mask": observation_status,
            "joint_observation_status": observation_status,
            "joint_valid": joint_valid,
            "visibility_reason": visibility_reason,
            "core_joint_valid": core_valid, "core_joint_status": core_status,
            "frame_quality_status": frame_status, "frame_valid": frame_valid,
            "exclusion_reason": missing_reason,
            "phase_annotation_version": phase["annotation_version"],
            "annotation_version": ANNOTATION_VERSION,
        }
        records.append(record)
        masks.append({
            "video_id": record["video_id"], "frame_index": frame,
            "timestamp_sec": record["timestamp_sec"], "subject_id": "P001",
            "track_id": track_id, "quality_mask": observation_status,
            "joint_observation_status": observation_status,
            "joint_valid": joint_valid, "visibility_reason": visibility_reason,
            "core_joint_valid": core_valid, "core_joint_status": core_status,
            "frame_quality_status": frame_status, "frame_valid": frame_valid,
            "exclusion_reason": missing_reason, "annotation_version": ANNOTATION_VERSION,
        })

    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    for path, rows in ((args.subject_output, records), (args.quality_mask_output, masks)):
        with path.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    per_joint: dict[str, Any] = {}
    for name, index in {**CORE_JOINTS, **AUXILIARY_JOINTS}.items():
        values = [record["confidence_raw"][index] for record in records]
        tracked_values = values[2:]
        per_joint[name] = {
            "body_25_id": index, "confidence_by_frame": values,
            "detected_frame_count": sum(value > 0 for value in values),
            "detected_rate_all_frames": sum(value > 0 for value in values) / len(values),
            "detected_rate_confirmed_track_frames": sum(value > 0 for value in tracked_values) / len(tracked_values),
            "quality_pass_frame_count": sum(value >= args.confidence_threshold for value in values),
            "quality_pass_rate_confirmed_track_frames": sum(value >= args.confidence_threshold for value in tracked_values) / len(tracked_values),
            "mean_confidence_confirmed_track_frames": fmean(tracked_values),
            "std_confidence_confirmed_track_frames": pstdev(tracked_values),
        }

    phase_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        phase_rows[record["phase_label"]].append(record)
    per_phase = {}
    for label, rows in phase_rows.items():
        per_phase[label] = {
            "frame_count": len(rows),
            "frame_range_segments": sorted({phase["source_segment_id"] for phase in phases if phase["phase_label"] == label}),
            "core_joint_detected_rate": {
                name: sum(row["confidence_raw"][index] > 0 for row in rows) / len(rows)
                for name, index in CORE_JOINTS.items()
            },
            "core_joint_quality_pass_rate": {
                name: sum(row["confidence_raw"][index] >= args.confidence_threshold for row in rows) / len(rows)
                for name, index in CORE_JOINTS.items()
            },
            "all_core_quality_pass_rate": sum(all(row["core_joint_valid"].values()) for row in rows) / len(rows),
        }
    status_counts = Counter(record["frame_quality_status"] for record in records)
    joint_observation_counts = Counter(
        status for record in records for status in record["joint_observation_status"]
    )
    masked_out_of_frame_nonzero_values = sum(
        record["confidence_raw"][joint_id] > 0
        for record in records for joint_id in OUT_OF_FRAME_JOINT_IDS
    )
    raw_openpose_detected_frames = len({
        row["frame_index"] for row in association
        if row.get("pose_index") is not None and any(value > 0 for value in row["confidence_raw"])
    })
    stats = {
        "video_id": phases[0]["video_id"], "total_frames": args.expected_frames,
        "confirmed_track_frames": args.expected_frames - 2,
        "openpose_detected_frames": raw_openpose_detected_frames,
        "openpose_detected_rate": raw_openpose_detected_frames / args.expected_frames,
        "p001_pose_frames": sum(row["match_status"] == "matched" for row in records),
        "p001_pose_rate_all_frames": sum(row["match_status"] == "matched" for row in records) / args.expected_frames,
        "p001_pose_rate_confirmed_track_frames": sum(row["match_status"] == "matched" for row in records) / (args.expected_frames - 2),
        "frame_quality_distribution": dict(sorted(status_counts.items())),
        "low_quality_frames": [row["frame_index"] for row in records if row["frame_quality_status"] == "low_quality"],
        "identity_uncertain_frames": [row["frame_index"] for row in records if row["match_status"] != "matched"],
        "missing_frames": [row["frame_index"] for row in records if not row["frame_valid"]],
        "ambiguous_frames": [],
        "joint_observation_status_distribution": dict(sorted(joint_observation_counts.items())),
        "masked_out_of_frame_nonzero_confidence_values": masked_out_of_frame_nonzero_values,
        "core_joints": {name: per_joint[name] for name in CORE_JOINTS},
        "auxiliary_joints": {name: per_joint[name] for name in AUXILIARY_JOINTS},
        "per_phase": per_phase,
        "quality_rules": {"core_joint_ids": CORE_JOINTS, "auxiliary_joint_ids": AUXILIARY_JOINTS,
                          "visible_joint_ids": sorted(VISIBLE_JOINT_IDS),
                          "out_of_frame_joint_ids": sorted(OUT_OF_FRAME_JOINT_IDS),
                          "out_of_frame_status": "out_of_frame",
                          "out_of_frame_visibility_reason": "outside_capture_scope",
                          "confidence_threshold": args.confidence_threshold,
                          "frame_invalid_only_when_all_core_missing": True,
                          "lower_body_missing_does_not_invalidate_frame": True,
                          "raw_confidence_preserved": True, "filtering_or_interpolation": False},
        "normalization_strategy": {
            "origin_joint": "Neck",
            "scale_reference": "shoulder_width",
            "pelvis_centered_normalization": "unavailable_for_this_capture",
        },
        "main_overlay_policy": {
            "joint_ids": sorted(VISIBLE_JOINT_IDS),
            "edges": [[1, 0], [1, 2], [2, 3], [3, 4], [1, 5], [5, 6], [6, 7],
                      [0, 15], [15, 17], [0, 16], [16, 18]],
            "raw_inferred_out_of_frame_joints_rendered": False,
        },
        "inputs": {"association_jsonl": str(args.association_jsonl),
                   "association_sha256": sha256_file(args.association_jsonl),
                   "phase_frames": str(args.phase_frames), "phase_frames_sha256": sha256_file(args.phase_frames)},
        "outputs": {"subject_sequence": str(args.subject_output), "quality_mask": str(args.quality_mask_output)},
        "annotation_version": ANNOTATION_VERSION,
    }
    args.joint_stats.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frame_quality_distribution": stats["frame_quality_distribution"], "low_quality_frames": stats["low_quality_frames"], "missing_frames": stats["missing_frames"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
