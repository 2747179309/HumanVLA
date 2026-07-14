#!/usr/bin/env python3
"""Validate manually authored action-phase segment annotations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

PHASES = {
    0: "idle",
    1: "reach",
    2: "align",
    3: "grasp",
    4: "lift",
    5: "transport",
    6: "place",
    7: "release",
    8: "retract",
    90: "occluded",
    91: "failed_attempt",
    98: "unknown",
}
ACTIVE_HANDS = {"left", "right", "both", "na"}
BOUNDARY_CONFIDENCE = {"high", "medium", "low"}
QUALITY_STATUSES = {
    "full_valid",
    "partial_occlusion",
    "heavy_occlusion",
    "ambiguous",
    "out_of_scope",
}
REQUIRED_COLUMNS = {
    "video_id",
    "episode_id",
    "segment_id",
    "start_frame",
    "end_frame",
    "phase_id",
    "phase_label",
    "phase_text_zh",
    "phase_text_en",
    "object_id",
    "active_hand",
    "boundary_confidence",
    "annotation_valid",
    "quality_status",
    "annotator_id",
    "reviewer_id",
    "annotation_version",
    "notes",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("expected true or false")


def compress_indices(indices: list[int]) -> list[list[int]]:
    if not indices:
        return []
    ranges: list[list[int]] = []
    start = previous = indices[0]
    for value in indices[1:]:
        if value != previous + 1:
            ranges.append([start, previous])
            start = value
        previous = value
    ranges.append([start, previous])
    return ranges


def load_manifest(manifest_path: Path, video_id: str) -> dict[str, str]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("video_id") == video_id]
    if len(rows) != 1:
        raise ValueError(
            f"manifest must contain exactly one row for {video_id}; found {len(rows)}"
        )
    return rows[0]


def validate_annotations(
    segments_path: Path, manifest_path: Path, video_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_manifest(manifest_path, video_id)
    total_frames = int(manifest["total_frames"])
    first_frame = int(manifest["first_frame_index"])
    last_frame = int(manifest["last_frame_index"])
    fps = float(manifest["fps"])

    if first_frame != 0 or last_frame != total_frames - 1:
        errors.append(
            "manifest frame range must be 0 through total_frames - 1; "
            f"got {first_frame} through {last_frame}"
        )
    if fps <= 0:
        errors.append(f"manifest fps must be positive; got {fps}")

    with segments_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        if missing_columns:
            errors.append(f"missing required columns: {missing_columns}")
        raw_rows = list(reader)

    if not raw_rows:
        errors.append("annotation CSV contains no segment rows")

    segments: list[dict[str, Any]] = []
    seen_segment_ids: set[str] = set()
    episode_ids: set[str] = set()
    cjk_pattern = re.compile(r"[\u3400-\u9fff]")
    english_pattern = re.compile(r"[A-Za-z]")

    for line_number, row in enumerate(raw_rows, start=2):
        prefix = f"line {line_number}"
        try:
            start_frame = int(row.get("start_frame", ""))
            end_frame = int(row.get("end_frame", ""))
            phase_id = int(row.get("phase_id", ""))
        except ValueError as exc:
            errors.append(f"{prefix}: invalid integer field: {exc}")
            continue

        segment_id = row.get("segment_id", "").strip()
        episode_id = row.get("episode_id", "").strip()
        phase_label = row.get("phase_label", "").strip()
        normalized: dict[str, Any] = {
            key: (value.strip() if isinstance(value, str) else value)
            for key, value in row.items()
        }
        normalized.update(
            start_frame=start_frame, end_frame=end_frame, phase_id=phase_id
        )

        if row.get("video_id", "").strip() != video_id:
            errors.append(f"{prefix}: video_id does not match {video_id}")
        if not episode_id:
            errors.append(f"{prefix}: episode_id is empty")
        else:
            episode_ids.add(episode_id)
        expected_segment_prefix = f"{episode_id}_S"
        if not re.fullmatch(re.escape(expected_segment_prefix) + r"\d{3}", segment_id):
            errors.append(f"{prefix}: invalid segment_id {segment_id!r}")
        if segment_id in seen_segment_ids:
            errors.append(f"{prefix}: duplicate segment_id {segment_id!r}")
        seen_segment_ids.add(segment_id)

        if start_frame > end_frame:
            errors.append(
                f"{prefix}: start_frame {start_frame} exceeds end_frame {end_frame}"
            )
        if start_frame < first_frame or end_frame > last_frame:
            errors.append(
                f"{prefix}: range {start_frame}-{end_frame} is outside "
                f"{first_frame}-{last_frame}"
            )
        if phase_id not in PHASES:
            errors.append(f"{prefix}: illegal phase_id {phase_id}")
        elif phase_label != PHASES[phase_id]:
            errors.append(
                f"{prefix}: phase_id {phase_id} requires label "
                f"{PHASES[phase_id]!r}, got {phase_label!r}"
            )

        zh_text = row.get("phase_text_zh", "").strip()
        en_text = row.get("phase_text_en", "").strip()
        if not zh_text or not cjk_pattern.search(zh_text):
            errors.append(f"{prefix}: phase_text_zh is empty or lacks Chinese text")
        if not en_text or not english_pattern.search(en_text):
            errors.append(f"{prefix}: phase_text_en is empty or lacks English text")
        if row.get("active_hand", "").strip() not in ACTIVE_HANDS:
            errors.append(f"{prefix}: illegal active_hand {row.get('active_hand')!r}")
        if row.get("boundary_confidence", "").strip() not in BOUNDARY_CONFIDENCE:
            errors.append(
                f"{prefix}: illegal boundary_confidence "
                f"{row.get('boundary_confidence')!r}"
            )
        if row.get("quality_status", "").strip() not in QUALITY_STATUSES:
            errors.append(
                f"{prefix}: illegal quality_status {row.get('quality_status')!r}"
            )
        try:
            normalized["annotation_valid"] = parse_bool(
                row.get("annotation_valid", "")
            )
        except ValueError as exc:
            errors.append(f"{prefix}: annotation_valid {exc}")
        for field in ("object_id", "annotator_id", "annotation_version"):
            if not row.get(field, "").strip():
                errors.append(f"{prefix}: {field} is empty")

        segments.append(normalized)

    if len(episode_ids) != 1:
        errors.append(f"expected one episode_id, found {sorted(episode_ids)}")

    ordered = sorted(segments, key=lambda item: (item["start_frame"], item["end_frame"]))
    if segments != ordered:
        errors.append("segment rows are not ordered by start_frame")

    coverage = [0] * total_frames
    for segment in ordered:
        clipped_start = max(first_frame, segment["start_frame"])
        clipped_end = min(last_frame, segment["end_frame"])
        for frame_index in range(clipped_start, clipped_end + 1):
            coverage[frame_index] += 1

    gaps = [index for index, count in enumerate(coverage) if count == 0]
    overlaps = [index for index, count in enumerate(coverage) if count > 1]
    if gaps:
        errors.append(f"uncovered frame ranges: {compress_indices(gaps)}")
    if overlaps:
        errors.append(f"overlapping frame ranges: {compress_indices(overlaps)}")

    previous_standard: int | None = None
    failed_since_previous = False
    for segment in ordered:
        phase_id = segment["phase_id"]
        if phase_id == 91:
            failed_since_previous = True
            continue
        if 1 <= phase_id <= 8:
            if (
                previous_standard is not None
                and phase_id < previous_standard
                and not failed_since_previous
            ):
                errors.append(
                    "semantic phase order moves backward without failed_attempt: "
                    f"{PHASES[previous_standard]} -> {PHASES[phase_id]}"
                )
            previous_standard = phase_id
            failed_since_previous = False

    stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"segment_count": 0, "frame_count": 0}
    )
    for segment in ordered:
        phase_id = segment["phase_id"]
        stats[phase_id]["segment_count"] += 1
        stats[phase_id]["frame_count"] += (
            segment["end_frame"] - segment["start_frame"] + 1
        )

    phase_statistics = []
    for phase_id, phase_label in PHASES.items():
        frame_count = stats[phase_id]["frame_count"]
        phase_statistics.append(
            {
                "phase_id": phase_id,
                "phase_label": phase_label,
                "segment_count": stats[phase_id]["segment_count"],
                "frame_count": frame_count,
                "duration_sec": round(frame_count / fps, 6),
            }
        )

    summary: dict[str, Any] = {
        "video_id": video_id,
        "validation_passed": not errors,
        "source_annotation_csv": str(segments_path),
        "source_annotation_sha256": sha256_file(segments_path),
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": sha256_file(manifest_path),
        "total_frames": total_frames,
        "first_frame_index": first_frame,
        "last_frame_index": last_frame,
        "fps": fps,
        "duration_sec": round(total_frames / fps, 6),
        "segment_count": len(ordered),
        "covered_frames": sum(count == 1 for count in coverage),
        "uncovered_frame_count": len(gaps),
        "overlap_frame_count": len(overlaps),
        "uncovered_ranges": compress_indices(gaps),
        "overlap_ranges": compress_indices(overlaps),
        "illegal_phase_count": sum("illegal phase" in error for error in errors),
        "errors": errors,
        "warnings": warnings,
        "phase_statistics": phase_statistics,
    }
    return summary, ordered, manifest


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a manually authored action-phase segment CSV."
    )
    parser.add_argument("--segments-csv", type=Path, required=True)
    parser.add_argument("--manifest-csv", type=Path, required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    try:
        summary, _, _ = validate_annotations(
            args.segments_csv, args.manifest_csv, args.video_id
        )
        write_json(args.output, summary)
    except (OSError, ValueError, KeyError) as exc:
        LOGGER.error("validation failed: %s", exc)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    LOGGER.info("validated %s segments", summary["segment_count"])
    return 0 if summary["validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
