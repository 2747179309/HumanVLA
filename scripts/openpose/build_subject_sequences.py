#!/usr/bin/env python3
"""Build continuous per-subject raw BODY_25 sequences from T04 associations."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any

ANNOTATION_VERSION = "v0.2.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build 240-frame raw subject sequences. Frames without confirmed track identity "
            "are filled as missing; OpenPose people-array order is never used as identity."
        )
    )
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--subjects", nargs="+", default=["P001", "P002", "P003"])
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


def load_records(path: Path, expected_frames: int) -> dict[int, list[dict[str, Any]]]:
    by_frame: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            frame = record.get("frame_index")
            if not isinstance(frame, int) or not 0 <= frame < expected_frames:
                raise ValueError(f"invalid frame_index at line {line_number}: {frame}")
            by_frame[frame].append(record)
    if set(by_frame) != set(range(expected_frames)):
        raise ValueError("association JSONL does not cover every expected frame")
    return by_frame


def validate_keypoints(record: dict[str, Any], context: str) -> None:
    keypoints = record.get("keypoints")
    confidence = record.get("keypoint_confidence_raw")
    if not isinstance(keypoints, list) or len(keypoints) != 25:
        raise ValueError(f"{context}: keypoints are not 25x3")
    if any(not isinstance(point, list) or len(point) != 3 for point in keypoints):
        raise ValueError(f"{context}: keypoints are not 25x3")
    if not isinstance(confidence, list) or len(confidence) != 25:
        raise ValueError(f"{context}: confidence_raw length is not 25")
    if [point[2] for point in keypoints] != confidence:
        raise ValueError(f"{context}: keypoint confidence mismatch")


def main() -> int:
    args = parse_args()
    association = args.association_jsonl.resolve()
    if not association.is_file():
        raise FileNotFoundError(f"association JSONL not found: {association}")
    output_dir = args.output_dir.resolve()
    output_files = [output_dir / f"{subject}.jsonl" for subject in args.subjects]
    metadata_path = output_dir / "metadata.json"
    if not args.overwrite:
        existing = [str(path) for path in [*output_files, metadata_path] if path.exists()]
        if existing:
            raise FileExistsError("refusing to overwrite derived output(s): " + ", ".join(existing))
    output_dir.mkdir(parents=True, exist_ok=True)

    by_frame = load_records(association, args.expected_frames)
    first_complete_matched_frame = next((
        frame for frame in range(args.expected_frames)
        if {
            record.get("subject_id") for record in by_frame[frame]
            if record.get("match_status") == "matched"
        } >= set(args.subjects)
    ), None)
    if first_complete_matched_frame is None:
        raise ValueError("no frame has one matched pose for every requested subject")
    track_by_subject: dict[str, int] = {}
    video_ids = {record["video_id"] for records in by_frame.values() for record in records}
    if len(video_ids) != 1:
        raise ValueError(f"expected one video_id, got {video_ids}")
    video_id = next(iter(video_ids))

    sequences: dict[str, list[dict[str, Any]]] = {subject: [] for subject in args.subjects}
    for frame in range(args.expected_frames):
        matched_by_subject: dict[str, dict[str, Any]] = {}
        for record in by_frame[frame]:
            subject = record.get("subject_id")
            if subject in args.subjects:
                if subject in matched_by_subject:
                    raise ValueError(f"duplicate subject {subject} in frame {frame}")
                matched_by_subject[subject] = record
                if record.get("track_id") is not None:
                    previous = track_by_subject.setdefault(subject, int(record["track_id"]))
                    if previous != int(record["track_id"]):
                        raise ValueError(f"subject {subject} has multiple track IDs")
        timestamp = min(record["timestamp_sec"] for record in by_frame[frame])
        for subject in args.subjects:
            record = matched_by_subject.get(subject)
            if record is None:
                keypoints = [[0.0, 0.0, 0.0] for _ in range(25)]
                confidence = [0.0 for _ in range(25)]
                source_status = "missing"
                source_pose_index = None
                track_id = track_by_subject.get(subject)
                assignment_method = "missing_fill_no_interpolation"
                assignment_cost = None
            else:
                validate_keypoints(record, f"frame={frame}, subject={subject}")
                keypoints = record["keypoints"]
                confidence = record["keypoint_confidence_raw"]
                source_status = record["match_status"]
                source_pose_index = record["pose_index"]
                track_id = record.get("track_id")
                assignment_method = "t04_subject_match"
                assignment_cost = record.get("match_cost")
            sequences[subject].append({
                "video_id": video_id,
                "frame_index": frame,
                "timestamp_sec": timestamp,
                "track_id": track_id,
                "subject_id": subject,
                "keypoints_raw": keypoints,
                "confidence_raw": confidence,
                "source_match_status": source_status,
                "source_pose_index": source_pose_index,
                "sequence_assignment_method": assignment_method,
                "sequence_assignment_cost": assignment_cost,
                "annotation_version": args.annotation_version,
            })

    for subject, path in zip(args.subjects, output_files):
        with path.open("w", encoding="utf-8") as stream:
            for record in sequences[subject]:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    metadata = {
        "video_id": video_id,
        "subjects": args.subjects,
        "expected_frames": args.expected_frames,
        "input_association_jsonl": str(association),
        "input_association_sha256": sha256_file(association),
        "first_complete_matched_frame": first_complete_matched_frame,
        "unconfirmed_identity_frames": list(range(first_complete_matched_frame)),
        "unconfirmed_identity_policy": "missing_fill_no_interpolation",
        "identity_rule": "Never use OpenPose people-array order as identity.",
        "processing_rule": "No interpolation, filtering, smoothing, or coordinate modification.",
        "annotation_version": args.annotation_version,
        "outputs": {subject: str(path) for subject, path in zip(args.subjects, output_files)},
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "video_id": video_id,
        "subjects": args.subjects,
        "frames_per_subject": {subject: len(records) for subject, records in sequences.items()},
        "missing_identity_frames": list(range(first_complete_matched_frame)),
        "output_dir": str(output_dir),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
