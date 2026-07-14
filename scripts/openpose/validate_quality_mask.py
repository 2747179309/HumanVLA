#!/usr/bin/env python3
"""Validate T05A continuous sequences and quality masks against T04 inputs."""

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

SUBJECTS = ("P001", "P002", "P003")
VALID_STATUSES = {
    "valid", "low_quality", "invalid_identity_mix", "missing",
    "excluded_phantom", "excluded_non_target",
}
USABLE_JOINT_STATUSES = {"valid", "low_quality"}
REQUIRED_SEQUENCE_FIELDS = {
    "frame_index", "timestamp_sec", "track_id", "subject_id", "keypoints_raw",
    "confidence_raw", "frame_quality_status", "quality_mask", "joint_valid",
    "frame_valid", "exclusion_reason", "annotation_version", "source_pose_index",
    "sequence_assignment_method",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate 240x3 T05A quality masks and exact raw-keypoint preservation."
    )
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--openpose-json-dir", required=True, type=Path)
    parser.add_argument("--t04-review", required=True, type=Path)
    parser.add_argument("--pose-quality-review", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--visualization", type=Path)
    parser.add_argument("--expected-frames", type=int, default=240)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def probe_video(path: Path) -> dict[str, Any]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(result.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"],
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frames": int(stream["nb_frames"]),
        "fps": stream["avg_frame_rate"],
    }


def expected_quality(subject: str, frame: int) -> tuple[str, list[str], bool]:
    if frame in {0, 1}:
        return "missing", ["missing"] * 25, False
    mask = ["valid"] * 25
    status = "valid"
    frame_valid = True
    if subject == "P001" and (15 <= frame <= 19 or 54 <= frame <= 61):
        for joint in (2, 3, 4):
            mask[joint] = "low_quality"
        status = "low_quality"
    if subject in {"P001", "P003"} and 43 <= frame <= 45:
        mask = ["low_quality"] * 25
        for joint in (5, 6, 7):
            mask[joint] = "invalid_identity_mix"
        status = "invalid_identity_mix"
        frame_valid = False
    return status, mask, frame_valid


def main() -> int:
    args = parse_args()
    paths = [
        args.processed_dir, args.association_jsonl, args.openpose_json_dir,
        args.t04_review, args.pose_quality_review, args.summary,
    ]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit("missing path(s): " + ", ".join(missing))
    errors: list[str] = []
    association_records = load_jsonl(args.association_jsonl)
    matched = {
        (record["frame_index"], record["subject_id"]): record
        for record in association_records if record["subject_id"] in SUBJECTS
    }
    pose_records = {
        (record["frame_index"], record["pose_index"]): record
        for record in association_records if record["pose_index"] is not None
    }
    if len(matched) != 714:
        errors.append(f"expected 714 matched subject records, found {len(matched)}")

    sequence_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    frame_status_counts: dict[str, collections.Counter[str]] = {}
    processed_over_one = 0
    for subject in SUBJECTS:
        path = args.processed_dir / f"{subject}.jsonl"
        records = load_jsonl(path)
        if len(records) != args.expected_frames:
            errors.append(f"{subject}: {len(records)} rows != {args.expected_frames}")
            continue
        if [record.get("frame_index") for record in records] != list(range(args.expected_frames)):
            errors.append(f"{subject}: frame sequence is not 0..239")
        counts: collections.Counter[str] = collections.Counter()
        for line_number, record in enumerate(records, 1):
            absent = REQUIRED_SEQUENCE_FIELDS - set(record)
            if absent:
                errors.append(f"{subject} line {line_number}: missing {sorted(absent)}")
                continue
            frame = record["frame_index"]
            key = (frame, subject)
            if key in sequence_by_key:
                errors.append(f"duplicate person-frame {key}")
            sequence_by_key[key] = record
            if record["subject_id"] != subject:
                errors.append(f"{subject} line {line_number}: subject mismatch")
            keypoints = record["keypoints_raw"]
            confidence = record["confidence_raw"]
            if not isinstance(keypoints, list) or len(keypoints) != 25 or any(
                not isinstance(point, list) or len(point) != 3 for point in keypoints
            ):
                errors.append(f"{subject} frame {frame}: keypoints not 25x3")
                continue
            if not isinstance(confidence, list) or len(confidence) != 25:
                errors.append(f"{subject} frame {frame}: confidence length !=25")
                continue
            if [point[2] for point in keypoints] != confidence:
                errors.append(f"{subject} frame {frame}: confidence/keypoint mismatch")
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for point in keypoints for value in point
            ):
                errors.append(f"{subject} frame {frame}: non-numeric/non-finite keypoint")
            processed_over_one += sum(value > 1 for value in confidence)
            source_pose_index = record["source_pose_index"]
            if source_pose_index is None:
                if keypoints != [[0.0, 0.0, 0.0] for _ in range(25)]:
                    errors.append(f"{subject} frame {frame}: missing source has nonzero keypoints")
                if frame in {0, 1}:
                    if record["sequence_assignment_method"] != "missing_fill_no_interpolation":
                        errors.append(f"{subject} frame {frame}: unconfirmed identity was assigned")
                    if record["track_id"] is not None:
                        errors.append(f"{subject} frame {frame}: unconfirmed identity has track_id")
            else:
                source = pose_records.get((frame, source_pose_index))
                if source is None:
                    errors.append(f"{subject} frame {frame}: source pose does not exist")
                elif keypoints != source["keypoints"] or confidence != source["keypoint_confidence_raw"]:
                    errors.append(f"{subject} frame {frame}: raw values differ from T04 JSONL")
                matched_source = matched.get(key)
                if source != matched_source:
                    errors.append(f"{subject} frame {frame}: source is not T04 subject match")
            mask = record["quality_mask"]
            joint_valid = record["joint_valid"]
            if not isinstance(mask, list) or len(mask) != 25 or not set(mask) <= VALID_STATUSES:
                errors.append(f"{subject} frame {frame}: invalid quality_mask")
                continue
            if not isinstance(joint_valid, list) or len(joint_valid) != 25:
                errors.append(f"{subject} frame {frame}: invalid joint_valid")
            elif joint_valid != [status in USABLE_JOINT_STATUSES for status in mask]:
                errors.append(f"{subject} frame {frame}: joint_valid inconsistent")
            expected_status, expected_mask, expected_frame_valid = expected_quality(subject, frame)
            if record["frame_quality_status"] != expected_status:
                errors.append(f"{subject} frame {frame}: frame status mismatch")
            if mask != expected_mask:
                errors.append(f"{subject} frame {frame}: joint quality rule mismatch")
            if record["frame_valid"] != expected_frame_valid:
                errors.append(f"{subject} frame {frame}: frame_valid mismatch")
            if frame in {0, 1} and record["exclusion_reason"] != "no_confirmed_track_identity":
                errors.append(f"{subject} frame {frame}: missing exclusion reason mismatch")
            counts[record["frame_quality_status"]] += 1
        frame_status_counts[subject] = counts

    mask_path = args.processed_dir / "quality_mask.jsonl"
    mask_records = load_jsonl(mask_path)
    if len(mask_records) != args.expected_frames * len(SUBJECTS):
        errors.append(f"quality_mask has {len(mask_records)} rows, expected 720")
    mask_keys = [(record["frame_index"], record["subject_id"]) for record in mask_records]
    expected_keys = [(frame, subject) for frame in range(args.expected_frames) for subject in SUBJECTS]
    if mask_keys != expected_keys:
        errors.append("quality_mask person-frame ordering/coverage mismatch")
    for record in mask_records:
        source = sequence_by_key.get((record["frame_index"], record["subject_id"]))
        if source is None:
            continue
        for field in ("frame_quality_status", "quality_mask", "joint_valid", "frame_valid", "exclusion_reason"):
            if record[field] != source[field]:
                errors.append(
                    f"mask mismatch: frame={record['frame_index']} subject={record['subject_id']} field={field}"
                )

    if processed_over_one == 0:
        errors.append("processed sequences contain no confidence >1; possible clipping")
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    if summary["total_person_frames"] != 720:
        errors.append("summary total_person_frames !=720")
    for subject in SUBJECTS:
        expected_counts = dict(sorted(frame_status_counts[subject].items()))
        if summary["per_subject"][subject]["frame_status_distribution"] != expected_counts:
            errors.append(f"summary frame counts mismatch for {subject}")
    if summary["global"]["excluded_ambiguous_pose_instances"] != 3:
        errors.append("summary ambiguous extra count !=3")
    if summary["global"]["excluded_phantom_instances"] != 1:
        errors.append("summary phantom count !=1")
    if summary["global"]["excluded_non_target_instances"] != 2:
        errors.append("summary non-target count !=2")
    current_hashes = {
        str(args.association_jsonl.resolve()): sha256_file(args.association_jsonl),
        str(args.t04_review.resolve()): sha256_file(args.t04_review),
        str(args.pose_quality_review.resolve()): sha256_file(args.pose_quality_review),
    }
    if summary["input_hashes_before"] != current_hashes or summary["input_hashes_after"] != current_hashes:
        errors.append("input hashes differ from summary")
    pose_files = sorted(args.openpose_json_dir.glob("*_keypoints.json"))
    raw_pose_digest = directory_digest(pose_files)
    if len(pose_files) != args.expected_frames:
        errors.append(f"OpenPose raw JSON count {len(pose_files)} !=240")
    if raw_pose_digest != "c174f901c73646b64b3f4a4ebbf3bb99c41534405324757e951a2449b14f0a8f":
        errors.append("OpenPose raw directory digest changed")

    video_info = None
    if args.visualization is not None:
        if not args.visualization.is_file():
            errors.append(f"visualization missing: {args.visualization}")
        else:
            video_info = probe_video(args.visualization)
            if (
                video_info["codec"] != "h264"
                or video_info["frames"] != args.expected_frames
                or video_info["width"] != 2160
                or video_info["height"] != 3840
            ):
                errors.append(f"visualization format mismatch: {video_info}")

    result = {
        "validation_passed": not errors,
        "errors": errors,
        "subject_frame_status_counts": {
            subject: dict(sorted(counts.items())) for subject, counts in frame_status_counts.items()
        },
        "quality_mask_records": len(mask_records),
        "processed_confidence_over_one_count": processed_over_one,
        "openpose_raw_json_count": len(pose_files),
        "openpose_raw_directory_sha256": raw_pose_digest,
        "visualization": video_info,
    }
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
