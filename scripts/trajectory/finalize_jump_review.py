#!/usr/bin/env python3
"""Validate and freeze human decisions for T07A jump candidates into the summary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_VIDEO_ID = "pick_place_pilot_v1_E001"
EXPECTED_MANUAL_FIELDS = ("manual_label", "manual_confidence", "manual_note")
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_LABELS = {
    "real_motion", "normal_body_compensation", "phase_boundary_motion",
    "openpose_jitter", "occlusion_error", "normalization_artifact", "uncertain",
}
PRESERVE_MOTION_LABELS = ("real_motion", "normal_body_compensation", "phase_boundary_motion")
MARK_ONLY_LABELS = ("openpose_jitter", "occlusion_error", "normalization_artifact")
JOINT_PREFIX = {"RElbow": "relbow", "RWrist": "rwrist"}
CONFIDENCE_INDEX = {"RElbow": 2, "RWrist": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate all T07A jump-candidate human fields and write the verbatim decisions "
            "and counts into trajectory_summary.json. No trajectory repair is performed."
        )
    )
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--expected-candidates", type=int, default=12)
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


def close(first: str, second: float, tolerance: float = 1e-9) -> bool:
    try:
        value = float(first)
    except (TypeError, ValueError):
        return False
    return math.isclose(value, second, rel_tol=0.0, abs_tol=tolerance)


def summary_candidates(summary: dict[str, Any]) -> dict[tuple[str, int, int], dict[str, Any]]:
    result: dict[tuple[str, int, int], dict[str, Any]] = {}
    for joint_name in ("RElbow", "RWrist"):
        details = summary.get("per_frame_displacement", {}).get(joint_name, {})
        for item in details.get("suspicious_jumps", []):
            key = (joint_name, int(item["from_frame"]), int(item["to_frame"]))
            if key in result:
                raise ValueError(f"duplicate summary candidate: {key}")
            result[key] = {
                **item,
                "threshold": details.get("suspicious_jump_threshold"),
                "rule": details.get("suspicious_jump_rule"),
            }
    return result


def validate_csv(
    path: Path, summary: dict[str, Any], trajectory: list[dict[str, Any]], expected: int,
) -> tuple[list[dict[str, str]], str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    required = {
        "candidate_id", "from_frame", "to_frame", "joint_name", "phase_before",
        "phase_after", "displacement_px", "displacement_norm", "confidence_before",
        "confidence_after", "shoulder_width_before", "shoulder_width_after",
        "neck_displacement_px", "automatic_trigger_reason", *EXPECTED_MANUAL_FIELDS,
    }
    if missing := required - set(fieldnames):
        raise ValueError(f"review CSV lacks fields: {sorted(missing)}")
    unnamed_present = "" in fieldnames
    unnamed_has_data = unnamed_present and any((row.get("") or "").strip() for row in rows)
    unexpected_named = set(fieldnames) - required - {
        "review_start_frame", "review_end_frame", "clip_path", "",
    }
    if unexpected_named:
        raise ValueError(f"unexpected named CSV fields: {sorted(unexpected_named)}")
    if len(rows) != expected:
        raise ValueError(f"review CSV has {len(rows)} rows, expected {expected}")
    if unnamed_has_data:
        shifted_layout_valid = all(
            not (row.get("review_start_frame") or "").strip()
            and (row.get("review_end_frame") or "").strip() == str(max(0, int(row["from_frame"]) - 5))
            and (row.get("clip_path") or "").strip() == str(min(344, int(row["to_frame"]) + 5))
            and (row.get("") or "").strip().endswith(
                f"{row['candidate_id']}_{row['joint_name']}_{row['from_frame']}_{row['to_frame']}.mp4"
            )
            for row in rows
        )
        if not shifted_layout_valid:
            raise ValueError("unnamed CSV column contains data outside the known shifted ancillary layout")
        csv_layout = "ancillary_review_metadata_shifted_one_column_right_after_manual_note"
    elif unnamed_present:
        csv_layout = "trailing_unnamed_empty_column"
    else:
        csv_layout = "canonical"
    expected_ids = [f"JUMP_{index:03d}" for index in range(1, expected + 1)]
    if [row["candidate_id"].strip() for row in rows] != expected_ids:
        raise ValueError("candidate_id sequence is not JUMP_001..JUMP_012")
    candidates = summary_candidates(summary)
    if len(candidates) != expected:
        raise ValueError(f"summary has {len(candidates)} candidate events, expected {expected}")
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        for field in EXPECTED_MANUAL_FIELDS:
            if not row[field].strip():
                raise ValueError(f"{row['candidate_id']} has blank {field}")
        confidence = row["manual_confidence"].strip()
        if confidence not in VALID_CONFIDENCE:
            raise ValueError(f"{row['candidate_id']} has invalid manual_confidence={confidence!r}")
        if row["manual_label"].strip() not in VALID_LABELS:
            raise ValueError(f"{row['candidate_id']} has disallowed manual_label={row['manual_label']!r}")
        try:
            from_frame, to_frame = int(row["from_frame"]), int(row["to_frame"])
        except ValueError as error:
            raise ValueError(f"{row['candidate_id']} has non-integer frame") from error
        joint_name = row["joint_name"].strip()
        key = (joint_name, from_frame, to_frame)
        if key not in candidates or key in seen:
            raise ValueError(f"unknown or duplicate CSV candidate: {key}")
        seen.add(key)
        before, after = trajectory[from_frame], trajectory[to_frame]
        prefix = JOINT_PREFIX[joint_name]
        before_xy = (before[f"{prefix}_x_px"], before[f"{prefix}_y_px"])
        after_xy = (after[f"{prefix}_x_px"], after[f"{prefix}_y_px"])
        expected_px = math.hypot(after_xy[0] - before_xy[0], after_xy[1] - before_xy[1])
        checks = {
            "displacement_px": expected_px,
            "displacement_norm": float(candidates[key]["distance_norm"]),
            "confidence_before": float(before["raw_confidence"][CONFIDENCE_INDEX[joint_name]]),
            "confidence_after": float(after["raw_confidence"][CONFIDENCE_INDEX[joint_name]]),
            "shoulder_width_before": float(before["shoulder_width_px"]),
            "shoulder_width_after": float(after["shoulder_width_px"]),
            "neck_displacement_px": float(after["neck_frame_displacement_px"]),
        }
        for field, expected_value in checks.items():
            if not close(row[field], expected_value):
                raise ValueError(f"{row['candidate_id']} {field} differs from trajectory/summary")
        if row["phase_before"] != before["phase_label"] or row["phase_after"] != after["phase_label"]:
            raise ValueError(f"{row['candidate_id']} phase fields differ from trajectory")
    if seen != set(candidates):
        raise ValueError("review CSV does not cover every summary candidate exactly once")
    return rows, csv_layout


def nested_counts(rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[row["joint_name"]][row["manual_label"].strip()] += 1
    return {joint: dict(sorted(values.items())) for joint, values in sorted(counts.items())}


def build_review_section(
    rows: list[dict[str, str]], csv_path: Path, csv_hash: str,
    trajectory_path: Path, trajectory_hash: str, csv_layout: str,
) -> dict[str, Any]:
    labels = Counter(row["manual_label"].strip() for row in rows)
    confidence = Counter(row["manual_confidence"].strip() for row in rows)
    joints = Counter(row["joint_name"].strip() for row in rows)
    phase_boundary_count = sum(row["phase_before"] != row["phase_after"] for row in rows)
    custom_labels = sorted(set(labels) - VALID_LABELS)
    decisions: list[dict[str, Any]] = []
    for row in rows:
        label = row["manual_label"].strip()
        if label in PRESERVE_MOTION_LABELS:
            handling = "preserve_motion_no_deletion"
        elif label in MARK_ONLY_LABELS:
            handling = "mark_only_no_repair"
        elif label == "uncertain":
            handling = "mark_only_no_repair_pending_future_review"
        else:
            raise ValueError(f"unexpected manual label after validation: {label}")
        decisions.append({
            "candidate_id": row["candidate_id"], "from_frame": int(row["from_frame"]),
            "to_frame": int(row["to_frame"]), "joint_name": row["joint_name"],
            "phase_before": row["phase_before"], "phase_after": row["phase_after"],
            "displacement_px": float(row["displacement_px"]),
            "displacement_norm": float(row["displacement_norm"]),
            "manual_label": label,
            "manual_confidence": row["manual_confidence"].strip(),
            "manual_note": row["manual_note"].strip(),
            "handling": handling,
        })
    return {
        "status": "human_adjudication_complete",
        "finalization_run_id": "20260714_T07A_JUMP_REVIEW_FINALIZE_001",
        "source_csv": str(csv_path), "source_csv_sha256": csv_hash,
        "trajectory_source": str(trajectory_path), "trajectory_sha256": trajectory_hash,
        "total_candidates": len(rows), "manual_fields_complete": True,
        "csv_format": {
            "row_count": len(rows),
            "layout": csv_layout,
            "manual_decision_fields_unaffected": True,
            "ancillary_review_metadata_used_for_finalization": False,
            "source_csv_modified": False,
        },
        "counts": {
            "by_manual_label": dict(sorted(labels.items())),
            "by_allowed_manual_label": {label: labels.get(label, 0) for label in sorted(VALID_LABELS)},
            "by_manual_confidence": dict(sorted(confidence.items())),
            "by_joint": dict(sorted(joints.items())),
            "by_joint_and_manual_label": nested_counts(rows),
            "same_phase_candidates": len(rows) - phase_boundary_count,
            "cross_phase_boundary_candidates": phase_boundary_count,
            "preserve_motion_labels": {label: labels.get(label, 0) for label in PRESERVE_MOTION_LABELS},
            "mark_only_labels": {label: labels.get(label, 0) for label in MARK_ONLY_LABELS},
            "custom_manual_labels": {label: labels[label] for label in custom_labels},
        },
        "policy": {
            "raw_trajectory_modified": False, "candidate_deleted": False,
            "real_motion_deleted": False, "phase_boundary_motion_deleted": False,
            "normal_body_compensation_deleted": False,
            "openpose_jitter_repaired": False, "occlusion_error_repaired": False,
            "normalization_artifact_repaired": False,
            "interpolation_applied": False, "filtering_applied": False,
            "uncertain_candidate_repaired": False,
        },
        "custom_manual_labels_preserved_verbatim": custom_labels,
        "decisions": decisions,
        "manual_review_annotation_version": "t07a_jump_review_v1.0.0",
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False,
    ) as stream:
        temp_path = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temp_path.replace(path)


def main() -> int:
    args = parse_args()
    for path in (args.summary, args.review_csv, args.trajectory):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.expected_candidates <= 0:
        raise ValueError("expected-candidates must be positive")
    same_output = args.summary.resolve() == args.output_summary.resolve()
    if args.output_summary.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite: {args.output_summary}")
    if not same_output and args.output_summary.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite: {args.output_summary}")

    trajectory_hash_before = sha256_file(args.trajectory)
    csv_hash_before = sha256_file(args.review_csv)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    trajectory = load_jsonl(args.trajectory)
    if summary.get("video_id") != EXPECTED_VIDEO_ID or len(trajectory) != 345:
        raise ValueError("inputs are not the fixed E001 T07A outputs")
    if [row.get("frame_index") for row in trajectory] != list(range(345)):
        raise ValueError("trajectory frame coverage is not 0..344")
    rows, csv_layout = validate_csv(
        args.review_csv, summary, trajectory, args.expected_candidates,
    )
    summary["jump_candidate_manual_review"] = build_review_section(
        rows, args.review_csv, csv_hash_before, args.trajectory, trajectory_hash_before,
        csv_layout,
    )
    summary["finalization_run_id"] = "20260714_T07A_JUMP_REVIEW_FINALIZE_001"
    write_json_atomic(args.output_summary, summary)

    if sha256_file(args.trajectory) != trajectory_hash_before:
        raise RuntimeError("raw trajectory changed during finalization")
    if sha256_file(args.review_csv) != csv_hash_before:
        raise RuntimeError("human review CSV changed during finalization")
    written = json.loads(args.output_summary.read_text(encoding="utf-8"))
    review = written.get("jump_candidate_manual_review", {})
    if review.get("total_candidates") != args.expected_candidates or len(review.get("decisions", [])) != args.expected_candidates:
        raise RuntimeError("written summary did not retain all manual decisions")
    print(json.dumps({
        "video_id": EXPECTED_VIDEO_ID,
        "manual_review_status": review["status"],
        "total_candidates": review["total_candidates"],
        "counts": review["counts"],
        "custom_manual_labels_preserved_verbatim": review["custom_manual_labels_preserved_verbatim"],
        "trajectory_sha256": trajectory_hash_before,
        "trajectory_unchanged": True, "review_csv_unchanged": True,
        "output_summary": str(args.output_summary),
        "output_summary_sha256": sha256_file(args.output_summary),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
