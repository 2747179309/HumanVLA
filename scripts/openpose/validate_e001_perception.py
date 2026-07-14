#!/usr/bin/env python3
"""Independently validate T06C association, merged data, and overlay outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CORE_IDS = (1, 2, 3, 4)
VISIBLE_IDS = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 18})
OUT_OF_FRAME_IDS = frozenset({8, 9, 10, 11, 12, 13, 14, 19, 20, 21, 22, 23, 24})
EXPECTED_AUXILIARY = {"Nose": 0, "LShoulder": 5, "LElbow": 6, "LWrist": 7}
EXPECTED_EDGES = [[1, 0], [1, 2], [2, 3], [3, 4], [1, 5], [5, 6], [6, 7],
                  [0, 15], [15, 17], [0, 16], [16, 18]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate T06C E001 raw-pose preservation and merged outputs.")
    parser.add_argument("--pose-json-dir", required=True, type=Path)
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--association-summary", required=True, type=Path)
    parser.add_argument("--phase-frames", required=True, type=Path)
    parser.add_argument("--subject-jsonl", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--joint-stats", required=True, type=Path)
    parser.add_argument("--manual-review", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def directory_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def video_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(result.stdout)["streams"][0]
    return {"codec": stream["codec_name"], "width": int(stream["width"]), "height": int(stream["height"]),
            "fps": stream["avg_frame_rate"], "frames": int(stream["nb_read_frames"])}


def main() -> int:
    args = parse_args()
    required = [args.pose_json_dir, args.association_jsonl, args.association_summary, args.phase_frames,
                args.subject_jsonl, args.quality_mask, args.joint_stats, args.manual_review, args.overlay]
    if missing := [str(path) for path in required if not path.exists()]:
        raise FileNotFoundError("missing input(s): " + ", ".join(missing))
    errors: list[str] = []
    pose_files = sorted(args.pose_json_dir.glob("*_keypoints.json"))
    if len(pose_files) != args.expected_frames:
        errors.append(f"raw JSON count {len(pose_files)} != {args.expected_frames}")
    raw_poses: dict[tuple[int, int], list[list[float]]] = {}
    people_counts = Counter()
    malformed = 0
    for frame, path in enumerate(pose_files):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            people = payload["people"]
            people_counts[len(people)] += 1
            for pose_index, person in enumerate(people):
                flat = person["pose_keypoints_2d"]
                if len(flat) != 75:
                    raise ValueError("BODY_25 length != 75")
                raw_poses[(frame, pose_index)] = [[float(flat[i]), float(flat[i + 1]), float(flat[i + 2])] for i in range(0, 75, 3)]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            malformed += 1
    if malformed:
        errors.append(f"malformed raw JSON frames: {malformed}")
    if people_counts != Counter({1: 344, 2: 1}):
        errors.append(f"unexpected people distribution: {dict(people_counts)}")
    double_frames = sorted({frame for frame, _ in raw_poses if sum(key[0] == frame for key in raw_poses) == 2})
    if double_frames != [226]:
        errors.append(f"expected only frame 226 to contain two poses, got {double_frames}")

    association = load_jsonl(args.association_jsonl)
    associated_pose = {(row["frame_index"], row["pose_index"]): row for row in association if row["pose_index"] is not None}
    if set(associated_pose) != set(raw_poses):
        errors.append("association does not preserve every raw pose exactly once")
    else:
        for key, keypoints in raw_poses.items():
            row = associated_pose[key]
            if row["keypoints"] != keypoints or row["confidence_raw"] != [point[2] for point in keypoints]:
                errors.append(f"raw pose values changed at {key}")
                break
    p001_by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in association:
        if row.get("subject_id") == "P001":
            p001_by_frame[row["frame_index"]].append(row)
    duplicates = [frame for frame, rows in p001_by_frame.items() if len(rows) > 1]
    if duplicates:
        errors.append(f"multiple P001 association records: {duplicates}")
    frame226 = associated_pose.get((226, 1), {})
    if frame226.get("match_status") != "unmatched_pose" or frame226.get("subject_id") is not None:
        errors.append("frame 226 pose_index=1 was not retained as unmatched_pose")

    phases = load_jsonl(args.phase_frames)
    subjects = load_jsonl(args.subject_jsonl)
    masks = load_jsonl(args.quality_mask)
    with args.manual_review.open(encoding="utf-8-sig", newline="") as stream:
        manual_rows = list(csv.DictReader(stream))
    if len(manual_rows) != 17:
        errors.append(f"manual review has {len(manual_rows)} rows, expected 17")
    manual_by_key = {
        (row["review_type"], int(row["frame_index"]), row["joint_id"] or row["pose_index"]): row
        for row in manual_rows
    }
    if len(manual_by_key) != len(manual_rows):
        errors.append("manual review contains duplicate review keys")
    expected_joint_reviews: dict[tuple[int, int], tuple[str, str, str, str]] = {}
    for frame in (64, 65):
        expected_joint_reviews[(frame, 3)] = ("low_quality", "low_quality", "forearm_self_occlusion", "not_specified")
        expected_joint_reviews[(frame, 4)] = ("missing", "missing", "hand_occludes_wrist", "not_specified")
    expected_joint_reviews[(143, 3)] = ("low_quality", "low_quality", "forearm_self_occlusion", "not_specified")
    expected_joint_reviews[(143, 4)] = ("missing", "missing", "hand_and_box_occlude_wrist", "not_specified")
    for frame in range(182, 186):
        expected_joint_reviews[(frame, 3)] = ("valid", "unstable", "suspected_self_occlusion_and_face_overlap", "medium")
        expected_joint_reviews[(frame, 4)] = ("missing", "missing_or_unstable", "suspected_self_occlusion_and_face_overlap", "medium")
    for (frame, joint_id), expected in expected_joint_reviews.items():
        row = manual_by_key.get(("joint_quality", frame, str(joint_id)))
        actual = None if row is None else (
            row["automatic_status"], row["manual_status"], row["reason"], row["manual_confidence"]
        )
        if actual != expected:
            errors.append(f"manual joint review mismatch: frame={frame}, joint={joint_id}, actual={actual}")
    artifact_row = manual_by_key.get(("pose_exclusion", 226, "1"))
    if artifact_row is None or artifact_row["manual_status"] != "excluded_reflection_artifact":
        errors.append("frame 226 reflection-artifact review is missing")
    if any(len(rows) != args.expected_frames for rows in (phases, subjects, masks)):
        errors.append("phase, subject, or quality-mask record count is not 345")
    for name, rows in (("phases", phases), ("subjects", subjects), ("masks", masks)):
        if [row.get("frame_index") for row in rows] != list(range(args.expected_frames)):
            errors.append(f"{name} frame coverage is not 0..344")
    for frame, (phase, subject, mask) in enumerate(zip(phases, subjects, masks)):
        for field in ("phase_id", "phase_label", "phase_text_zh", "phase_text_en"):
            if subject.get(field) != phase.get(field):
                errors.append(f"phase field changed at frame {frame}: {field}")
        for field in ("quality_mask", "joint_observation_status", "joint_valid", "visibility_reason",
                      "core_joint_valid", "frame_quality_status", "frame_valid", "exclusion_reason"):
            if subject.get(field) != mask.get(field):
                errors.append(f"quality mask mismatch at frame {frame}: {field}")
        keypoints = subject.get("keypoints_raw")
        confidence = subject.get("confidence_raw")
        if not isinstance(keypoints, list) or len(keypoints) != 25 or any(len(point) != 3 for point in keypoints):
            errors.append(f"invalid merged BODY_25 at frame {frame}")
            continue
        if confidence != [point[2] for point in keypoints]:
            errors.append(f"merged confidence mismatch at frame {frame}")
        observation = subject.get("joint_observation_status")
        joint_valid = subject.get("joint_valid")
        reasons = subject.get("visibility_reason")
        if not all(isinstance(values, list) and len(values) == 25 for values in (observation, joint_valid, reasons)):
            errors.append(f"joint observation arrays invalid at frame {frame}")
            continue
        manual_status = mask.get("manual_joint_status")
        manual_reason = mask.get("manual_joint_reason")
        manual_confidence = mask.get("manual_joint_confidence")
        if not all(isinstance(values, list) and len(values) == 25 for values in (manual_status, manual_reason, manual_confidence)):
            errors.append(f"manual joint arrays invalid at frame {frame}")
            continue
        expected_for_frame = {
            joint_id: expected for (review_frame, joint_id), expected in expected_joint_reviews.items()
            if review_frame == frame
        }
        for joint_id in range(25):
            expected = expected_for_frame.get(joint_id)
            actual = (manual_status[joint_id], manual_reason[joint_id], manual_confidence[joint_id])
            expected_values = (None, None, None) if expected is None else (expected[1], expected[2], expected[3])
            if actual != expected_values:
                errors.append(f"quality-mask manual reason mismatch: frame={frame}, joint={joint_id}")
                break
        for joint_id in OUT_OF_FRAME_IDS:
            if not (observation[joint_id] == "out_of_frame" and joint_valid[joint_id] is False and
                    reasons[joint_id] == "outside_capture_scope"):
                errors.append(f"out-of-frame policy failed at frame {frame}, joint {joint_id}")
                break
        for joint_id in VISIBLE_IDS:
            expected_status = "missing" if confidence[joint_id] <= 0 else (
                "low_quality" if confidence[joint_id] < 0.3 else "valid"
            )
            if observation[joint_id] != expected_status or joint_valid[joint_id] != (expected_status == "valid"):
                errors.append(f"visible-joint policy failed at frame {frame}, joint {joint_id}")
                break
        if frame in {0, 1}:
            if not (subject["frame_quality_status"] == "missing" and subject["frame_valid"] is False and
                    subject["exclusion_reason"] == "no_confirmed_track_identity" and subject["track_id"] is None):
                errors.append(f"frame {frame} missing-identity policy not applied")
        else:
            source = p001_by_frame.get(frame, [])
            if len(source) != 1 or source[0]["match_status"] != "matched":
                errors.append(f"frame {frame} lacks one matched P001 pose")
            elif keypoints != source[0]["keypoints"]:
                errors.append(f"merged raw keypoints changed at frame {frame}")
            core_status = [subject["joint_observation_status"][index] for index in CORE_IDS]
            expected_valid = not all(status == "missing" for status in core_status)
            if subject["frame_valid"] != expected_valid:
                errors.append(f"core-only frame validity rule failed at frame {frame}")

    stats = json.loads(args.joint_stats.read_text(encoding="utf-8"))
    if stats.get("total_frames") != args.expected_frames:
        errors.append("joint stats total_frames mismatch")
    if set(stats.get("core_joints", {})) != {"Neck", "RShoulder", "RElbow", "RWrist"}:
        errors.append("joint stats core-joint set mismatch")
    if stats.get("quality_rules", {}).get("auxiliary_joint_ids") != EXPECTED_AUXILIARY:
        errors.append("joint stats auxiliary-joint set mismatch")
    if stats.get("quality_rules", {}).get("visible_joint_ids") != sorted(VISIBLE_IDS):
        errors.append("visible-joint capture scope mismatch")
    if stats.get("quality_rules", {}).get("out_of_frame_joint_ids") != sorted(OUT_OF_FRAME_IDS):
        errors.append("out-of-frame capture scope mismatch")
    if stats.get("normalization_strategy") != {
        "origin_joint": "Neck", "scale_reference": "shoulder_width",
        "pelvis_centered_normalization": "unavailable_for_this_capture",
    }:
        errors.append("normalization strategy mismatch")
    overlay_policy = stats.get("main_overlay_policy", {})
    if (overlay_policy.get("joint_ids") != sorted(VISIBLE_IDS) or
            overlay_policy.get("edges") != EXPECTED_EDGES or
            overlay_policy.get("raw_inferred_out_of_frame_joints_rendered") is not False):
        errors.append("main overlay upper-body-only policy mismatch")
    if stats.get("frame_quality_distribution") != {"low_quality": 7, "missing": 2, "valid": 336}:
        errors.append("T06C-M1 unexpectedly changed frame-level quality counts")
    expected_masked_nonzero = sum(
        subject["confidence_raw"][joint_id] > 0
        for subject in subjects for joint_id in OUT_OF_FRAME_IDS
    )
    if stats.get("masked_out_of_frame_nonzero_confidence_values") != expected_masked_nonzero:
        errors.append("masked out-of-frame nonzero-confidence count mismatch")
    if masks[226].get("frame_valid") is not True or masks[226].get("frame_quality_status") != "valid":
        errors.append("frame 226 P001 was incorrectly invalidated")
    frame226_pose_reviews = masks[226].get("manual_pose_reviews", [])
    if len(frame226_pose_reviews) != 1 or frame226_pose_reviews[0].get("manual_status") != "excluded_reflection_artifact":
        errors.append("frame 226 quality-mask artifact decision mismatch")
    association_summary = json.loads(args.association_summary.read_text(encoding="utf-8"))
    raw_digest = directory_digest(pose_files)
    if raw_digest != association_summary["inputs"]["pose_json_directory_sha256_before"] or raw_digest != association_summary["inputs"]["pose_json_directory_sha256_after"]:
        errors.append("raw OpenPose directory hash differs from association lock")
    overlay = video_probe(args.overlay)
    if overlay != {"codec": "h264", "width": 1280, "height": 720, "fps": "30/1", "frames": 345}:
        errors.append(f"overlay properties mismatch: {overlay}")
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(args.overlay), "-f", "null", "-"], capture_output=True)
    if decode.returncode:
        errors.append("overlay full decode failed: " + decode.stderr.decode(errors="replace"))

    joint_level_missing_confirmed_track = {
        name: sum(row["joint_observation_status"][joint_id] == "missing" for row in masks[2:])
        for name, joint_id in {"Neck": 1, "RShoulder": 2, "RElbow": 3, "RWrist": 4}.items()
    }
    output = {
        "validation_passed": not errors, "errors": errors, "total_frames": args.expected_frames,
        "raw_json_count": len(pose_files), "raw_pose_count": len(raw_poses),
        "people_per_frame_distribution": dict(sorted(people_counts.items())), "multi_pose_frames": double_frames,
        "association_records": len(association), "matched_p001_frames": sum(bool(rows) and rows[0]["match_status"] == "matched" for rows in p001_by_frame.values()),
        "unmatched_pose_instances": [
            {"frame_index": row["frame_index"], "pose_index": row["pose_index"]}
            for row in association if row["match_status"] == "unmatched_pose"
        ],
        "subject_records": len(subjects), "quality_mask_records": len(masks),
        "masked_out_of_frame_nonzero_confidence_values": expected_masked_nonzero,
        "manual_review": {
            "status": "complete",
            "reviewed_issue_frames": [64, 65, 143, 182, 183, 184, 185, 226],
            "prior_identity_policy_frames": [0, 1],
            "confirmed_joint_low_quality": {"RElbow": [64, 65, 143]},
            "confirmed_joint_missing": {"RWrist": [64, 65, 143]},
            "uncertain_joint_missing_or_unstable": {
                "joint_scope": ["RElbow", "RWrist"], "frames": [182, 183, 184, 185],
                "reason": "suspected_self_occlusion_and_face_overlap", "manual_confidence": "medium",
                "cause_certainty": "suspected_not_confirmed",
            },
            "excluded_pose_artifacts": [{
                "frame_index": 226, "pose_index": 1,
                "manual_status": "excluded_reflection_artifact",
                "reason": "table_reflection_false_positive",
                "affects_p001_frame_valid": False,
            }],
            "p001_frame_226_status": {"frame_quality_status": "valid", "frame_valid": True},
            "frame_quality_distribution_unchanged": {"valid": 336, "low_quality": 7, "missing": 2},
            "joint_level_missing_confirmed_track_frames": joint_level_missing_confirmed_track,
        },
        "raw_pose_directory_sha256": raw_digest, "overlay": overlay, "overlay_full_decode_passed": decode.returncode == 0,
        "rules_verified": {"frame_0_1_missing_identity": True, "one_pose_max_per_P001_frame": not duplicates,
                           "raw_pose_values_preserved": not any("raw pose values changed" in error for error in errors),
                           "phase_fields_preserved": not any("phase field changed" in error for error in errors),
                           "lower_body_not_used_for_frame_validity": not any("core-only" in error for error in errors),
                           "out_of_frame_joints_forced_invalid": not any("out-of-frame policy" in error for error in errors),
                           "upper_body_overlay_policy": not any("overlay upper-body-only" in error for error in errors),
                           "normalization_strategy_recorded": not any("normalization strategy" in error for error in errors),
                           "manual_review_applied": not any("manual" in error or "artifact" in error for error in errors),
                           "p001_frame_226_remains_valid": not any("frame 226 P001" in error for error in errors)},
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
