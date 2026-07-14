#!/usr/bin/env python3
"""Apply reviewed joint reasons and extra-pose decisions to a T06C quality mask."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ANNOTATION_VERSION = "t06c_final_review_v0.3.0"
JOINT_NAMES = {1: "Neck", 2: "RShoulder", 3: "RElbow", 4: "RWrist"}
REQUIRED_FIELDS = {
    "video_id", "frame_index", "review_type", "pose_index", "joint_id", "joint_name",
    "automatic_status", "manual_status", "reason", "manual_confidence",
    "reviewer_decision", "affects_p001_frame_valid", "notes",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge T06C human joint/pose review into quality_mask.jsonl without changing raw poses."
    )
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--manual-review", required=True, type=Path)
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
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


def main() -> int:
    args = parse_args()
    for path in (args.quality_mask, args.manual_review, args.association_jsonl):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite: {args.output}")

    quality = load_jsonl(args.quality_mask)
    if len(quality) != args.expected_frames or [row["frame_index"] for row in quality] != list(range(args.expected_frames)):
        raise ValueError("quality mask must contain exactly one ordered row per frame")
    association = load_jsonl(args.association_jsonl)
    pose_records = {
        (row["frame_index"], row["pose_index"]): row
        for row in association if row.get("pose_index") is not None
    }
    with args.manual_review.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_FIELDS:
            raise ValueError(f"manual review fields differ: {reader.fieldnames}")
        reviews = list(reader)
    if not reviews:
        raise ValueError("manual review CSV is empty")

    quality_hash_before = sha256_file(args.quality_mask)
    association_hash_before = sha256_file(args.association_jsonl)
    joint_reviews: dict[int, list[dict[str, Any]]] = defaultdict(list)
    pose_reviews: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, int, str]] = set()
    for row in reviews:
        if row["video_id"] != "pick_place_pilot_v1_E001":
            raise ValueError(f"unexpected video_id: {row['video_id']}")
        frame = int(row["frame_index"])
        if not 0 <= frame < args.expected_frames:
            raise ValueError(f"review frame out of range: {frame}")
        review_type = row["review_type"]
        if review_type == "joint_quality":
            joint_id = int(row["joint_id"])
            key = (review_type, frame, str(joint_id))
            if key in seen:
                raise ValueError(f"duplicate joint review: frame={frame}, joint={joint_id}")
            if JOINT_NAMES.get(joint_id) != row["joint_name"]:
                raise ValueError(f"joint name/id mismatch: frame={frame}, joint={joint_id}")
            if quality[frame]["joint_observation_status"][joint_id] != row["automatic_status"]:
                raise ValueError(f"automatic joint status mismatch: frame={frame}, joint={joint_id}")
            review = {
                "joint_id": joint_id, "joint_name": row["joint_name"],
                "automatic_status": row["automatic_status"], "manual_status": row["manual_status"],
                "reason": row["reason"], "manual_confidence": row["manual_confidence"],
                "reviewer_decision": row["reviewer_decision"], "notes": row["notes"],
            }
            joint_reviews[frame].append(review)
        elif review_type == "pose_exclusion":
            pose_index = int(row["pose_index"])
            key = (review_type, frame, str(pose_index))
            if key in seen:
                raise ValueError(f"duplicate pose review: frame={frame}, pose={pose_index}")
            source = pose_records.get((frame, pose_index))
            if source is None or source["match_status"] != row["automatic_status"]:
                raise ValueError(f"association pose/status mismatch: frame={frame}, pose={pose_index}")
            review = {
                "pose_index": pose_index, "automatic_status": row["automatic_status"],
                "manual_status": row["manual_status"], "reason": row["reason"],
                "manual_confidence": row["manual_confidence"],
                "reviewer_decision": row["reviewer_decision"],
                "affects_p001_frame_valid": row["affects_p001_frame_valid"] == "1",
                "notes": row["notes"],
            }
            pose_reviews[frame].append(review)
        else:
            raise ValueError(f"invalid review_type: {review_type}")
        seen.add(key)

    output_rows: list[dict[str, Any]] = []
    for frame, source in enumerate(quality):
        output = dict(source)
        manual_status: list[str | None] = [None] * 25
        manual_reason: list[str | None] = [None] * 25
        manual_confidence: list[str | None] = [None] * 25
        for review in sorted(joint_reviews.get(frame, []), key=lambda item: item["joint_id"]):
            joint_id = review["joint_id"]
            manual_status[joint_id] = review["manual_status"]
            manual_reason[joint_id] = review["reason"]
            manual_confidence[joint_id] = review["manual_confidence"]
        output.update({
            "manual_joint_status": manual_status,
            "manual_joint_reason": manual_reason,
            "manual_joint_confidence": manual_confidence,
            "manual_joint_reviews": sorted(joint_reviews.get(frame, []), key=lambda item: item["joint_id"]),
            "manual_pose_reviews": sorted(pose_reviews.get(frame, []), key=lambda item: item["pose_index"]),
            "manual_review_status": "reviewed" if frame in joint_reviews or frame in pose_reviews else "not_targeted",
            "manual_review_version": ANNOTATION_VERSION,
        })
        output_rows.append(output)

    if output_rows[226]["frame_valid"] is not True or output_rows[226]["frame_quality_status"] != "valid":
        raise ValueError("frame 226 P001 must remain frame_valid=true and valid")
    if output_rows[226]["manual_pose_reviews"][0]["manual_status"] != "excluded_reflection_artifact":
        raise ValueError("frame 226 artifact decision missing")
    frame_counts_before = Counter(row["frame_quality_status"] for row in quality)
    frame_counts_after = Counter(row["frame_quality_status"] for row in output_rows)
    if frame_counts_after != frame_counts_before:
        raise RuntimeError("manual joint reasons changed frame-level quality counts")
    if sha256_file(args.association_jsonl) != association_hash_before:
        raise RuntimeError("association JSONL changed during manual-review merge")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in output_rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({
        "quality_input_sha256": quality_hash_before,
        "quality_output_sha256": sha256_file(args.output),
        "association_sha256_unchanged": association_hash_before,
        "review_csv_rows": len(reviews),
        "reviewed_frames": sorted(set(joint_reviews) | set(pose_reviews)),
        "joint_review_records": sum(map(len, joint_reviews.values())),
        "pose_review_records": sum(map(len, pose_reviews.values())),
        "frame_quality_distribution": dict(sorted(frame_counts_after.items())),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
