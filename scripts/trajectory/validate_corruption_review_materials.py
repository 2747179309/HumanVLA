#!/usr/bin/env python3
"""Independently validate T07C-A blank human-review materials."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


MANUAL_FIELDS = (
    "manual_from_frame_status", "manual_to_frame_status", "manual_error_frames",
    "manual_valid_frames", "manual_corruption_type", "manual_confidence",
    "manual_reason", "manual_proposed_action",
)
EXPECTED_JUMPS = {
    "JUMP_001", "JUMP_002", "JUMP_003", "JUMP_005", "JUMP_007",
    "JUMP_008", "JUMP_009", "JUMP_010", "JUMP_011",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate T07C-A CSV, clips, combined video, and input hashes.")
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--clips-dir", required=True, type=Path)
    parser.add_argument("--review-video", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--jump-review", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--repaired-trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--repair-summary", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--final-mask", type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(completed.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"], "width": int(stream["width"]),
        "height": int(stream["height"]), "fps": stream["avg_frame_rate"],
        "frames": int(stream["nb_read_frames"]),
    }


def main() -> int:
    args = parse_args()
    files = (
        args.review_csv, args.review_video, args.summary, args.jump_review,
        args.raw_trajectory, args.repaired_trajectory, args.quality_mask,
        args.repair_summary, args.video,
    )
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    errors: list[str] = []
    with args.review_csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 11:
        errors.append(f"review CSV has {len(rows)} rows instead of 11")
    if rows and not set(MANUAL_FIELDS) <= set(rows[0]):
        errors.append("manual review fields are incomplete")
    if any(any((row.get(field) or "").strip() for field in MANUAL_FIELDS) for row in rows):
        errors.append("one or more manual review fields are not blank")
    source_ids = {row["source_event_id"] for row in rows}
    if not EXPECTED_JUMPS <= source_ids:
        errors.append("the 9 required jump events are incomplete")
    if "T06C_LOW_QUALITY_RELBOW_064_065" not in source_ids:
        errors.append("the T06C RElbow low-quality event is missing")
    if "T07B_BOUNDARY_RWrist_182_185" not in source_ids:
        errors.append("the T07B boundary warning event is missing")
    if any(int(row["from_frame"]) - int(row["review_start_frame"]) < 8 for row in rows):
        errors.append("a review clip lacks 8 pre-event frames")
    if any(int(row["review_end_frame"]) - int(row["to_frame"]) < 8 for row in rows):
        errors.append("a review clip lacks 8 post-event frames")

    clip_probes = []
    for row in rows:
        clip = Path(row["clip_path"])
        if not clip.is_file() or clip.parent.resolve() != args.clips_dir.resolve():
            errors.append(f"invalid clip path: {clip}")
            continue
        metadata = probe(clip)
        expected_frames = int(row["review_end_frame"]) - int(row["review_start_frame"]) + 1
        if metadata != {"codec": "h264", "width": 1280, "height": 720, "fps": "6/1", "frames": expected_frames}:
            errors.append(f"clip metadata mismatch: {clip}: {metadata}")
        clip_probes.append(metadata)
    combined = probe(args.review_video)
    expected_total = sum(int(row["review_end_frame"]) - int(row["review_start_frame"]) + 1 for row in rows)
    if combined != {"codec": "h264", "width": 1280, "height": 720, "fps": "6/1", "frames": expected_total}:
        errors.append(f"combined video metadata mismatch: {combined}")
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(args.review_video), "-f", "null", "-"],
        capture_output=True,
    )
    if decode.returncode:
        errors.append("combined video full decode failed")

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    input_paths = (
        args.jump_review, args.raw_trajectory, args.repaired_trajectory,
        args.quality_mask, args.repair_summary, args.video,
    )
    for path in input_paths:
        if summary.get("input_hashes", {}).get(str(path)) != sha256_file(path):
            errors.append(f"input hash mismatch: {path}")
    if summary.get("automatic_frame_error_decisions") is not False:
        errors.append("summary claims automatic frame decisions")
    if summary.get("automatic_masking_performed") is not False:
        errors.append("summary claims automatic masking")
    if summary.get("filtering_or_interpolation_performed") is not False:
        errors.append("summary claims filtering or interpolation")
    if args.final_mask is not None and args.final_mask.exists():
        errors.append("final frame-joint mask exists before human review")

    result = {
        "validation_passed": not errors,
        "errors": errors,
        "candidate_count": len(rows),
        "manual_fields_blank": not any(
            any((row.get(field) or "").strip() for field in MANUAL_FIELDS) for row in rows
        ),
        "clip_count": len(clip_probes),
        "combined_video": combined,
        "combined_video_full_decode_passed": decode.returncode == 0,
        "final_mask_generated": bool(args.final_mask and args.final_mask.exists()),
        "input_hashes": {str(path): sha256_file(path) for path in input_paths},
        "output_hashes": {
            str(path): sha256_file(path) for path in (args.review_csv, args.review_video, args.summary)
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
