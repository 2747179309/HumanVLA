#!/usr/bin/env python3
"""Validate T04 pose-track association outputs against immutable source data."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

VALID_STATUSES = {
    "matched", "unmatched_pose", "unmatched_track", "ambiguous_pose", "phantom_pose"
}
REQUIRED_FIELDS = {
    "video_id", "frame_index", "timestamp_sec", "track_id", "subject_id",
    "bbox_xyxy", "pose_index", "keypoints", "match_score", "match_iou",
    "center_distance", "match_status", "annotation_version",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate T04 JSONL, summary, anomaly rules, and video.")
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--pose-json-dir", required=True, type=Path)
    parser.add_argument("--subject-map", required=True, type=Path)
    parser.add_argument("--manual-review-summary", required=True, type=Path)
    parser.add_argument("--visualization", required=True, type=Path)
    parser.add_argument("--manual-review-template", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=240)
    return parser.parse_args()


def directory_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_subject_map(path: Path) -> dict[int, str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {
        int(row["track_id"]): row["subject_id"]
        for row in rows if row.get("include_for_pose") == "1"
    }


def probe_video(path: Path) -> dict[str, Any]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(result.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"], "width": int(stream["width"]),
        "height": int(stream["height"]), "frames": int(stream["nb_frames"]),
        "fps": stream["avg_frame_rate"],
    }


def main() -> int:
    args = parse_args()
    required_paths = [
        args.association_jsonl, args.summary, args.pose_json_dir, args.subject_map,
        args.manual_review_summary, args.visualization, args.manual_review_template,
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise SystemExit("missing path(s): " + ", ".join(missing))
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    with args.association_jsonl.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: JSON error: {exc}")
                continue
            missing_fields = REQUIRED_FIELDS - set(record)
            if missing_fields:
                errors.append(f"line {line_number}: missing fields {sorted(missing_fields)}")
            records.append(record)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    manual = json.loads(args.manual_review_summary.read_text(encoding="utf-8"))
    mapping = load_subject_map(args.subject_map)
    pose_files = sorted(args.pose_json_dir.glob("*_keypoints.json"))
    if len(pose_files) != args.expected_frames:
        errors.append(f"raw pose JSON count {len(pose_files)} != {args.expected_frames}")
    raw_poses: dict[int, list[list[float]]] = {}
    for frame_index, path in enumerate(pose_files):
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_poses[frame_index] = [person["pose_keypoints_2d"] for person in payload["people"]]

    seen_subject_frames: set[tuple[int, str]] = set()
    seen_pose_frames: set[tuple[int, int]] = set()
    status_counts: collections.Counter[str] = collections.Counter()
    output_frames: set[int] = set()
    for line_number, record in enumerate(records, 1):
        frame = record.get("frame_index")
        status = record.get("match_status")
        output_frames.add(frame)
        if status not in VALID_STATUSES:
            errors.append(f"line {line_number}: invalid status {status}")
            continue
        status_counts[status] += 1
        track_id, subject_id = record.get("track_id"), record.get("subject_id")
        if track_id is not None:
            if track_id not in mapping or mapping[track_id] != subject_id:
                errors.append(f"line {line_number}: track/subject not from subject map")
            key = (frame, subject_id)
            if key in seen_subject_frames:
                errors.append(f"line {line_number}: duplicate subject in frame {key}")
            seen_subject_frames.add(key)
        elif subject_id is not None:
            errors.append(f"line {line_number}: subject without track")
        pose_index = record.get("pose_index")
        if pose_index is not None:
            key = (frame, pose_index)
            if key in seen_pose_frames:
                errors.append(f"line {line_number}: duplicate pose in frame {key}")
            seen_pose_frames.add(key)
            if frame not in raw_poses or not 0 <= pose_index < len(raw_poses[frame]):
                errors.append(f"line {line_number}: pose index outside raw data")
            else:
                flat = raw_poses[frame][pose_index]
                expected = [[float(flat[i]), float(flat[i + 1]), float(flat[i + 2])] for i in range(0, 75, 3)]
                if record.get("keypoints") != expected:
                    errors.append(f"line {line_number}: keypoints differ from raw OpenPose JSON")
                raw_confidence = [point[2] for point in expected]
                if record.get("keypoint_confidence_raw") != raw_confidence:
                    errors.append(f"line {line_number}: confidence differs from raw OpenPose JSON")
        elif record.get("keypoints") is not None:
            errors.append(f"line {line_number}: keypoints without pose_index")
        if status == "matched":
            numeric = [record.get(name) for name in ("match_score", "match_cost", "match_iou", "center_distance")]
            if any(value is None or not isinstance(value, (int, float)) or not math.isfinite(value) for value in numeric):
                errors.append(f"line {line_number}: invalid matched metrics")
            if track_id is None or pose_index is None:
                errors.append(f"line {line_number}: matched record missing track or pose")
        if status in {"unmatched_pose", "ambiguous_pose", "phantom_pose"} and track_id is not None:
            errors.append(f"line {line_number}: pose-only status bound to track")
        if status == "unmatched_track" and pose_index is not None:
            errors.append(f"line {line_number}: unmatched track has pose")

    if output_frames != set(range(args.expected_frames)):
        errors.append("association output does not cover frames 0..239")
    expected_pose_keys = {
        (frame, pose_index)
        for frame, poses in raw_poses.items() for pose_index in range(len(poses))
    }
    if seen_pose_frames != expected_pose_keys:
        errors.append(
            f"pose accounting mismatch: output={len(seen_pose_frames)}, raw={len(expected_pose_keys)}"
        )
    for status in VALID_STATUSES:
        if summary["match_statistics"].get(status) != status_counts[status]:
            errors.append(f"summary mismatch for {status}")
    if summary["total_output_records"] != len(records):
        errors.append("summary total_output_records mismatch")
    if summary["total_pose_instances"] != len(expected_pose_keys):
        errors.append("summary total_pose_instances mismatch")
    if summary["matched_pairs"] + summary["unmatched_tracks"] != summary["total_person_frames"]:
        errors.append("track accounting mismatch")
    expected_anomalies = {
        **{str(frame): "ambiguous_pose" for frame in manual["ambiguous_pose_frames"]},
        **{str(frame): "phantom_pose" for frame in manual["phantom_frames"]},
        **{str(frame): "unmatched_pose" for frame in manual["unmatched_background_person_frames"]},
    }
    for frame, expected_status in expected_anomalies.items():
        anomaly = summary["anomaly_frames"].get(frame)
        if not anomaly or anomaly["manual_status"] != expected_status:
            errors.append(f"frame {frame}: summary anomaly status mismatch")
        frame_records = [r for r in records if r["frame_index"] == int(frame)]
        if sum(r["match_status"] == expected_status for r in frame_records) != 1:
            errors.append(f"frame {frame}: expected exactly one {expected_status}")
        if sum(r["match_status"] == "matched" for r in frame_records) != 3:
            errors.append(f"frame {frame}: expected three matched main subjects")
    raw_digest = directory_digest(pose_files)
    if raw_digest != manual["source_files"]["raw_json_directory_sha256"]:
        errors.append("raw OpenPose directory digest changed")
    if summary["inputs"]["pose_json_directory_sha256_before"] != raw_digest:
        errors.append("summary raw digest before mismatch")
    if summary["inputs"]["pose_json_directory_sha256_after"] != raw_digest:
        errors.append("summary raw digest after mismatch")
    with args.manual_review_template.open(encoding="utf-8-sig", newline="") as stream:
        review_rows = list(csv.DictReader(stream))
    if len(review_rows) < 20:
        errors.append(f"manual review template has {len(review_rows)} rows, expected >=20")
    if any(row["reviewer_decision"] != "pending" for row in review_rows):
        errors.append("manual review template contains non-pending judgment")
    video = probe_video(args.visualization)
    if video["codec"] != "h264" or video["frames"] != args.expected_frames:
        errors.append(f"visualization invalid: {video}")
    if video["width"] != 2160 or video["height"] != 3840:
        errors.append(f"visualization dimensions invalid: {video}")

    result = {
        "validation_passed": not errors,
        "errors": errors,
        "records": len(records),
        "covered_frames": len(output_frames),
        "pose_records": len(seen_pose_frames),
        "status_counts": dict(status_counts),
        "raw_pose_directory_sha256": raw_digest,
        "visualization": video,
        "manual_review_template_rows": len(review_rows),
    }
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
