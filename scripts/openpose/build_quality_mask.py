#!/usr/bin/env python3
"""Apply T05A human quality rules to continuous raw subject sequences."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

ANNOTATION_VERSION = "v0.2.0"
SUBJECTS = ("P001", "P002", "P003")
VALID_STATUSES = {
    "valid", "low_quality", "invalid_identity_mix", "missing",
    "excluded_phantom", "excluded_non_target",
}
INVALID_FRAME_STATUSES = {
    "invalid_identity_mix", "missing", "excluded_phantom", "excluded_non_target"
}
USABLE_JOINT_STATUSES = {"valid", "low_quality"}
STATUS_PRIORITY = {
    "valid": 0,
    "low_quality": 1,
    "missing": 2,
    "invalid_identity_mix": 3,
    "excluded_non_target": 4,
    "excluded_phantom": 5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply reviewed T05A per-frame/per-joint quality masks.")
    parser.add_argument("--raw-sequence-dir", required=True, type=Path)
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--t04-review", required=True, type=Path)
    parser.add_argument("--pose-quality-review", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--annotation-version", default=ANNOTATION_VERSION)
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


def validate_reviews(t04_path: Path, quality_path: Path, expected_frames: int) -> list[dict[str, str]]:
    with t04_path.open(encoding="utf-8-sig", newline="") as stream:
        t04_rows = list(csv.DictReader(stream))
    if len(t04_rows) != expected_frames:
        raise ValueError(f"T04 review has {len(t04_rows)} rows, expected {expected_frames}")
    if [int(row["frame_index"]) for row in t04_rows] != list(range(expected_frames)):
        raise ValueError("T04 review frame sequence is incomplete")
    with quality_path.open(encoding="utf-8-sig", newline="") as stream:
        quality_rows = list(csv.DictReader(stream))
    if len(quality_rows) != 5:
        raise ValueError(f"pose quality review has {len(quality_rows)} rows, expected 5")
    expected_segments = {
        (15, 19, "P001", "joint_localization_error"),
        (43, 45, "P003", "identity_mix_and_limb_connection"),
        (54, 61, "P001", "joint_localization_error"),
        (188, 188, "", "phantom_pose"),
        (207, 208, "", "out_of_scope_pose"),
    }
    actual_segments = {
        (int(row["start_frame"]), int(row["end_frame"]), row["subject_id"], row["issue_type"])
        for row in quality_rows
    }
    if actual_segments != expected_segments:
        raise ValueError(f"pose quality review segments differ from T05A rules: {actual_segments}")
    return quality_rows


def frame_and_joint_quality(
    subject: str, frame: int, source_status: str
) -> tuple[str, list[str], bool, list[bool], str | None]:
    if source_status == "missing":
        mask = ["missing"] * 25
        reason = "no_confirmed_track_identity" if frame in {0, 1} else "missing_pose"
        return "missing", mask, False, [False] * 25, reason
    mask = ["valid"] * 25
    frame_status = "valid"
    frame_valid = True
    reason = None
    if subject == "P001" and (15 <= frame <= 19 or 54 <= frame <= 61):
        for joint in (2, 3, 4):
            mask[joint] = "low_quality"
        frame_status = "low_quality"
        reason = "joint_localization_error_right_arm"
    if subject in {"P001", "P003"} and 43 <= frame <= 45:
        mask = ["low_quality"] * 25
        for joint in (5, 6, 7):
            mask[joint] = "invalid_identity_mix"
        frame_status = "invalid_identity_mix"
        frame_valid = False
        reason = "identity_mix_and_cross_person_limb_connection"
    joint_valid = [status in USABLE_JOINT_STATUSES for status in mask]
    return frame_status, mask, frame_valid, joint_valid, reason


def worst_status(mask: list[str]) -> str:
    return max(mask, key=lambda status: STATUS_PRIORITY[status])


def main() -> int:
    args = parse_args()
    raw_dir = args.raw_sequence_dir.resolve()
    association = args.association_jsonl.resolve()
    t04_review = args.t04_review.resolve()
    quality_review = args.pose_quality_review.resolve()
    output_dir = args.output_dir.resolve()
    summary_path = args.summary.resolve()
    input_paths = [association, t04_review, quality_review]
    for path in input_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    validate_reviews(t04_review, quality_review, args.expected_frames)
    output_paths = [output_dir / f"{subject}.jsonl" for subject in SUBJECTS]
    mask_path = output_dir / "quality_mask.jsonl"
    if not args.overwrite:
        existing = [str(path) for path in [*output_paths, mask_path, summary_path] if path.exists()]
        if existing:
            raise FileExistsError("refusing to overwrite derived output(s): " + ", ".join(existing))
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    input_hashes_before = {str(path): sha256_file(path) for path in input_paths}
    sequences: dict[str, list[dict[str, Any]]] = {}
    mask_records: list[dict[str, Any]] = []
    for subject in SUBJECTS:
        raw_path = raw_dir / f"{subject}.jsonl"
        raw_records = load_jsonl(raw_path)
        if len(raw_records) != args.expected_frames:
            raise ValueError(f"{subject}: {len(raw_records)} raw frames")
        if [record["frame_index"] for record in raw_records] != list(range(args.expected_frames)):
            raise ValueError(f"{subject}: non-contiguous raw sequence")
        output_records: list[dict[str, Any]] = []
        for raw in raw_records:
            frame = raw["frame_index"]
            frame_status, mask, frame_valid, joint_valid, reason = frame_and_joint_quality(
                subject, frame, raw["source_match_status"]
            )
            output = {
                **raw,
                "frame_quality_status": frame_status,
                "quality_mask": mask,
                "joint_valid": joint_valid,
                "frame_valid": frame_valid,
                "exclusion_reason": reason,
                "annotation_version": args.annotation_version,
            }
            output_records.append(output)
            mask_records.append({
                "video_id": raw["video_id"],
                "frame_index": frame,
                "timestamp_sec": raw["timestamp_sec"],
                "track_id": raw["track_id"],
                "subject_id": subject,
                "frame_quality_status": frame_status,
                "quality_mask": mask,
                "frame_valid": frame_valid,
                "joint_valid": joint_valid,
                "num_valid_joints": mask.count("valid"),
                "num_low_quality_joints": mask.count("low_quality"),
                "num_invalid_joints": sum(
                    status in INVALID_FRAME_STATUSES and status != "missing" for status in mask
                ),
                "num_missing_joints": mask.count("missing"),
                "num_usable_joints": sum(joint_valid),
                "worst_joint_status": worst_status(mask),
                "exclusion_reason": reason,
                "annotation_version": args.annotation_version,
            })
        sequences[subject] = output_records

    for subject, path in zip(SUBJECTS, output_paths):
        with path.open("w", encoding="utf-8") as stream:
            for record in sequences[subject]:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    mask_records.sort(key=lambda record: (record["frame_index"], record["subject_id"]))
    with mask_path.open("w", encoding="utf-8") as stream:
        for record in mask_records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    association_records = load_jsonl(association)
    excluded_instances = {
        "excluded_ambiguous_pose": [
            {"frame_index": record["frame_index"], "pose_index": record["pose_index"]}
            for record in association_records if record["match_status"] == "ambiguous_pose"
        ],
        "excluded_phantom": [
            {"frame_index": record["frame_index"], "pose_index": record["pose_index"]}
            for record in association_records if record["match_status"] == "phantom_pose"
        ],
        "excluded_non_target": [
            {"frame_index": record["frame_index"], "pose_index": record["pose_index"]}
            for record in association_records
            if record["match_status"] == "unmatched_pose" and record["frame_index"] in {207, 208}
        ],
    }
    per_subject: dict[str, Any] = {}
    for subject in SUBJECTS:
        records = sequences[subject]
        frame_counts = collections.Counter(record["frame_quality_status"] for record in records)
        joint_counts = collections.Counter(
            status for record in records for status in record["quality_mask"]
        )
        per_subject[subject] = {
            "total_frames": len(records),
            "frame_status_distribution": dict(sorted(frame_counts.items())),
            "valid_frames": frame_counts["valid"],
            "low_quality_frame_count": frame_counts["low_quality"],
            "low_quality_frames": [
                record["frame_index"] for record in records
                if record["frame_quality_status"] == "low_quality"
            ],
            "invalid_identity_mix_frame_count": frame_counts["invalid_identity_mix"],
            "invalid_identity_mix_frames": [
                record["frame_index"] for record in records
                if record["frame_quality_status"] == "invalid_identity_mix"
            ],
            "missing_frame_count": frame_counts["missing"],
            "missing_frames": [
                record["frame_index"] for record in records
                if record["frame_quality_status"] == "missing"
            ],
            "frame_valid_count": sum(record["frame_valid"] for record in records),
            "frame_invalid_count": sum(not record["frame_valid"] for record in records),
            "joint_status_distribution": dict(sorted(joint_counts.items())),
        }
    global_frame_counts = collections.Counter(
        record["frame_quality_status"] for records in sequences.values() for record in records
    )
    input_hashes_after = {str(path): sha256_file(path) for path in input_paths}
    if input_hashes_after != input_hashes_before:
        raise RuntimeError("an input file changed while building the quality mask")
    summary = {
        "video_id": sequences["P001"][0]["video_id"],
        "total_frames": args.expected_frames,
        "subjects": list(SUBJECTS),
        "total_person_frames": args.expected_frames * len(SUBJECTS),
        "per_subject": per_subject,
        "global": {
            "frame_status_distribution": dict(sorted(global_frame_counts.items())),
            "frame_valid_count": sum(
                record["frame_valid"] for records in sequences.values() for record in records
            ),
            "frame_invalid_count": sum(
                not record["frame_valid"] for records in sequences.values() for record in records
            ),
            "excluded_ambiguous_pose_instances": len(
                excluded_instances["excluded_ambiguous_pose"]
            ),
            "excluded_phantom_instances": len(excluded_instances["excluded_phantom"]),
            "excluded_non_target_instances": len(excluded_instances["excluded_non_target"]),
        },
        "extra_pose_exclusions": excluded_instances,
        "quality_rules": {
            "P001_right_arm_low_quality_joints": [2, 3, 4],
            "identity_mix_affected_subjects": ["P001", "P003"],
            "identity_mix_invalid_joints": [5, 6, 7],
            "identity_mix_frames": [43, 44, 45],
            "no_confidence_clipping": True,
            "no_filtering_or_interpolation": True,
        },
        "input_hashes_before": input_hashes_before,
        "input_hashes_after": input_hashes_after,
        "outputs": {
            "subject_sequences": {subject: str(path) for subject, path in zip(SUBJECTS, output_paths)},
            "quality_mask": str(mask_path),
        },
        "annotation_version": args.annotation_version,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "per_subject": {
            subject: values["frame_status_distribution"] for subject, values in per_subject.items()
        },
        "quality_mask_records": len(mask_records),
        "extra_pose_exclusions": excluded_instances,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
