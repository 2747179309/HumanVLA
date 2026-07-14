#!/usr/bin/env python3
"""Independently validate T07C-A raw/repaired/downstream mask semantics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


JOINTS = ("Neck", "RShoulder", "RElbow", "RWrist")
ALLOWED_SOURCES = {"raw", "repaired", "none"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the 1380-row T07C-A mask and H.264 overlay.")
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--jump-review", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--repaired-trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
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


def probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(completed.stdout)["streams"][0]
    return {"codec": stream["codec_name"], "width": int(stream["width"]), "height": int(stream["height"]), "fps": stream["avg_frame_rate"], "frames": int(stream["nb_read_frames"])}


def main() -> int:
    args = parse_args()
    files = tuple(Path(value) for value in vars(args).values())
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    errors: list[str] = []
    rows = load_jsonl(args.mask)
    if len(rows) != 1380:
        errors.append(f"mask has {len(rows)} rows instead of 1380")
    expected_keys = [(frame, joint) for frame in range(345) for joint in JOINTS]
    actual_keys = [(row.get("frame_index"), row.get("joint_name")) for row in rows]
    if actual_keys != expected_keys or len(set(actual_keys)) != 1380:
        errors.append("mask does not uniquely cover 345x4 in canonical order")
    by_key = {(row["frame_index"], row["joint_name"]): row for row in rows}
    for row in rows:
        selected = row.get("selected_downstream_source")
        if selected not in ALLOWED_SOURCES:
            errors.append(f"invalid selected source at {row.get('frame_index')}/{row.get('joint_name')}")
            continue
        if row.get("downstream_valid") is not (selected != "none"):
            errors.append(f"downstream validity/source mismatch at {row['frame_index']}/{row['joint_name']}")
        if selected == "repaired" and not (
            row.get("repaired_observation_available") and row.get("repaired_observation_valid")
        ):
            errors.append(f"invalid repaired selection at {row['frame_index']}/{row['joint_name']}")
        if selected == "raw" and not row.get("raw_observation_available"):
            errors.append(f"unavailable raw selection at {row['frame_index']}/{row['joint_name']}")
        if selected == "raw" and not row.get("raw_observation_valid") and row.get("proposed_action") != "downweight":
            errors.append(f"invalid raw selected without downweight at {row['frame_index']}/{row['joint_name']}")
        if row.get("filtered") is not False or row.get("new_interpolation_performed") is not False:
            errors.append(f"processing boundary violated at {row['frame_index']}/{row['joint_name']}")

    for frame in (64, 65, 143, 182, 183, 184, 185):
        row = by_key[(frame, "RWrist")]
        if not (row["raw_observation_valid"] is False and row["repaired_observation_available"] is True and row["repaired_observation_valid"] is True and row["selected_downstream_source"] == "repaired" and row["downstream_valid"] is True):
            errors.append(f"accepted RWrist repair layering mismatch at frame {frame}")
    for frame in (64, 65):
        row = by_key[(frame, "RElbow")]
        if not (row["raw_observation_valid"] is False and row["repaired_observation_available"] is False and row["selected_downstream_source"] == "none" and row["downstream_valid"] is False and row["defer_to_task"] == "T07C-B"):
            errors.append(f"RElbow 64-65 deferral mismatch at frame {frame}")
    for frame in (178, 179):
        row = by_key[(frame, "RWrist")]
        if not (row["raw_observation_valid"] is False and row["repaired_observation_available"] is False and row["selected_downstream_source"] == "none" and row["downstream_valid"] is False and row["defer_to_task"] == "T07C-B"):
            errors.append(f"RWrist 178-179 deferral mismatch at frame {frame}")
    for frame in (182, 183, 184, 185):
        if by_key[(frame, "RWrist")]["boundary_continuity_warning"] is not True:
            errors.append(f"boundary warning missing at frame {frame}")
    for frame in (54, 55):
        row = by_key[(frame, "RElbow")]
        if not (row["raw_observation_valid"] is True and row["selected_downstream_source"] == "raw" and row["proposed_action"] == "keep" and row["normalization_scale_warning"] is True):
            errors.append(f"normalization artifact semantics mismatch at frame {frame}")
    if not {"JUMP_002", "JUMP_003", "T06C_LOW_QUALITY_RELBOW_064_065"} <= set(by_key[(64, "RElbow")]["source_event_ids"]):
        errors.append("frame64 RElbow duplicate sources were lost")
    if not {"JUMP_002", "JUMP_003", "JUMP_005", "T06C_LOW_QUALITY_RELBOW_064_065"} <= set(by_key[(72, "RElbow")]["source_event_ids"]):
        errors.append("frame72 RElbow duplicate sources were lost")
    for frame in (72, 73, 74):
        row = by_key[(frame, "RElbow")]
        if row.get("manual_action_conflict") is not True or set(row.get("proposed_actions", [])) != {"mask", "downweight"}:
            errors.append(f"frame{frame} RElbow mask/downweight evidence difference was lost")
    for frame in range(129, 144):
        row = by_key[(frame, "RElbow")]
        if row["proposed_action"] != "defer" or row["defer_to_task"] != "T07C-B":
            errors.append(f"defer evidence was remapped at frame {frame}")

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    input_paths = (args.review_csv, args.jump_review, args.raw_trajectory, args.repaired_trajectory, args.quality_mask, args.video)
    for path in input_paths:
        if summary.get("input_hashes", {}).get(str(path)) != sha256_file(path):
            errors.append(f"input hash mismatch: {path}")
    if summary.get("raw_and_repaired_layers_separate") is not True:
        errors.append("summary does not declare layer separation")
    if summary.get("filtering_performed") is not False or summary.get("new_interpolation_performed") is not False:
        errors.append("summary claims new processing")
    overlay = probe(args.overlay)
    if overlay != {"codec": "h264", "width": 1280, "height": 720, "fps": "30/1", "frames": 345}:
        errors.append(f"overlay metadata mismatch: {overlay}")
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(args.overlay), "-f", "null", "-"], capture_output=True)
    if decode.returncode:
        errors.append("overlay full decode failed")
    result = {
        "validation_passed": not errors,
        "errors": errors,
        "total_records": len(rows),
        "records_per_joint": dict(Counter(row["joint_name"] for row in rows)),
        "raw_invalid_count": sum(not row["raw_observation_valid"] for row in rows),
        "repaired_valid_count": sum(row["repaired_observation_valid"] for row in rows),
        "selected_source_counts": dict(Counter(row["selected_downstream_source"] for row in rows)),
        "overlay": overlay,
        "overlay_full_decode_passed": decode.returncode == 0,
        "input_hashes": {str(path): sha256_file(path) for path in input_paths},
        "output_hashes": {str(path): sha256_file(path) for path in (args.mask, args.summary, args.overlay)},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
