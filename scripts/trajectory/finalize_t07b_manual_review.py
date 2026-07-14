#!/usr/bin/env python3
"""Finalize T07B per-joint manual review without changing raw observations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


JOINTS = ("RElbow", "RWrist")
WRIST_REVIEW_FRAMES = {64, 65, 143, 182, 183, 184, 185}
BOUNDARY_WARNING_FRAMES = {182, 183, 184, 185}
ELBOW_REJECTED_FRAMES = {64, 65}
ELBOW_REASON = "low_quality_observation_requires_quality_aware_refinement"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply the approved T07B-R1 per-joint review to derived repair outputs."
    )
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--repaired-jsonl", required=True, type=Path)
    parser.add_argument("--repaired-csv", required=True, type=Path)
    parser.add_argument("--repair-summary", required=True, type=Path)
    parser.add_argument("--synthetic-manifest", required=True, type=Path)
    parser.add_argument("--benchmark-csv", required=True, type=Path)
    parser.add_argument("--benchmark-json", required=True, type=Path)
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


def csv_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty repaired CSV")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({key: csv_value(value) for key, value in row.items()} for row in rows)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def default_joint_map(value: Any) -> dict[str, Any]:
    return {joint: value for joint in JOINTS}


def main() -> int:
    args = parse_args()
    readonly = (
        args.raw_trajectory,
        args.quality_mask,
        args.synthetic_manifest,
        args.benchmark_csv,
        args.benchmark_json,
    )
    outputs = (args.repaired_jsonl, args.repaired_csv, args.repair_summary)
    for path in (*readonly, *outputs):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not args.overwrite:
        raise FileExistsError("derived outputs exist; pass --overwrite to finalize them")

    readonly_hashes_before = {str(path): sha256_file(path) for path in readonly}
    raw_rows = load_jsonl(args.raw_trajectory)
    quality_rows = load_jsonl(args.quality_mask)
    repaired_rows = load_jsonl(args.repaired_jsonl)
    if len(raw_rows) != 345 or len(quality_rows) != 345 or len(repaired_rows) != 345:
        raise ValueError("raw, quality, and repaired JSONL must each contain 345 frames")
    if any(row.get("frame_index") != frame for frame, row in enumerate(raw_rows)):
        raise ValueError("raw trajectory coverage must be frame 0..344")

    for frame in sorted(ELBOW_REJECTED_FRAMES):
        raw = raw_rows[frame]
        quality = quality_rows[frame]
        if not raw.get("relbow_coordinate_available"):
            raise ValueError(f"frame {frame}: RElbow has no raw observation")
        if raw.get("relbow_effective_status") != "low_quality":
            raise ValueError(f"frame {frame}: RElbow is not low_quality in raw trajectory")
        if quality.get("joint_observation_status", [None] * 25)[3] != "low_quality":
            raise ValueError(f"frame {frame}: T06C RElbow status is not low_quality")
        if quality.get("manual_joint_reason", [None] * 25)[3] != "forearm_self_occlusion":
            raise ValueError(f"frame {frame}: unexpected T06C RElbow reason")

    finalized: list[dict[str, Any]] = []
    for frame, (raw, source) in enumerate(zip(raw_rows, repaired_rows)):
        if any(source.get(key) != value for key, value in raw.items()):
            raise ValueError(f"frame {frame}: repaired file already changed a raw field")
        record = dict(source)
        automatic_confidence = record.get("automatic_repair_confidence", record.get("repair_confidence"))
        record["automatic_repair_confidence"] = automatic_confidence

        repair_applied = {
            "RElbow": False,
            "RWrist": bool(record.get("repair_mask_by_joint", {}).get("RWrist", False)),
        }
        review_status = default_joint_map("not_reviewed")
        acceptance = default_joint_map("not_applicable")
        confidence = default_joint_map(None)
        note = default_joint_map(None)
        defer = default_joint_map(None)
        reason = default_joint_map(None)
        warning = default_joint_map(False)
        downstream = {
            "RElbow": bool(
                raw.get("relbow_coordinate_available")
                and raw.get("relbow_effective_status") == "valid"
                and raw.get("normalization_anchor_valid")
            ),
            "RWrist": bool(
                raw.get("rwrist_coordinate_available")
                and raw.get("rwrist_effective_status") == "valid"
                and raw.get("normalization_anchor_valid")
            ),
        }

        if frame in WRIST_REVIEW_FRAMES:
            review_status["RWrist"] = "pass"
            acceptance["RWrist"] = "accepted"
            confidence["RWrist"] = "high"
            downstream["RWrist"] = True
            note["RWrist"] = "人工确认线性修复位置合理。"
        if frame in BOUNDARY_WARNING_FRAMES:
            warning["RWrist"] = True
            note["RWrist"] = (
                "人工确认修复位置合理；保留入口速度不连续性"
                "7.959980 norm/s的boundary_continuity_warning。"
            )
        if frame in ELBOW_REJECTED_FRAMES:
            review_status["RElbow"] = "fail"
            acceptance["RElbow"] = "rejected"
            downstream["RElbow"] = False
            note["RElbow"] = (
                "原始RElbow为low_quality观测且坐标仍存在；人工认为其位置与真实肘关节偏差过大，"
                "未生成或采用插值修复值。"
            )
            defer["RElbow"] = "T07C"
            reason["RElbow"] = ELBOW_REASON

        record["repair_applied"] = repair_applied
        record["manual_review_status"] = review_status
        record["repair_acceptance"] = acceptance
        record["repair_confidence"] = confidence
        record["downstream_valid"] = downstream
        record["manual_note"] = note
        record["defer_to_task"] = defer
        record["repair_reason"] = reason
        record["boundary_continuity_warning"] = warning
        record["repair_annotation_version"] = "t07b_r1_manual_review_v1.1.0"
        finalized.append(record)

    summary = json.loads(args.repair_summary.read_text(encoding="utf-8"))
    if summary.get("selected_method") != "linear" or summary.get("method_label") != "provisional best on E001":
        raise ValueError("T07B method selection changed before R1 finalization")
    if summary.get("repaired_frames") != sorted(WRIST_REVIEW_FRAMES):
        raise ValueError("T07B repaired frame set changed before R1 finalization")
    for gap in summary.get("gap_details", []):
        gap["automatic_repair_confidence"] = gap.get(
            "automatic_repair_confidence", gap.get("repair_confidence")
        )
        gap["manual_review_status"] = "pass"
        gap["repair_acceptance"] = "accepted"
        gap["repair_confidence"] = "high"
        gap["downstream_valid"] = True
        gap["boundary_continuity_warning"] = gap["repair_gap_id"] == "GAP_182_185"
        gap["manual_note"] = (
            "人工确认RWrist线性修复位置合理。"
            if gap["repair_gap_id"] != "GAP_182_185"
            else "人工确认RWrist修复位置合理；入口速度不连续性7.959980 norm/s，保留边界连续性警告。"
        )
        gap["defer_to_task"] = None

    summary["manual_review"] = {
        "run_id": "20260714_T07B_R1_MANUAL_FINALIZATION_001",
        "status": "complete",
        "reviewed_joint_frame_count": 9,
        "accepted_rwrist_frames": sorted(WRIST_REVIEW_FRAMES),
        "accepted_rwrist_frame_count": len(WRIST_REVIEW_FRAMES),
        "rejected_relbow_frames": sorted(ELBOW_REJECTED_FRAMES),
        "rejected_relbow_frame_count": len(ELBOW_REJECTED_FRAMES),
        "relbow_64_65_audit": {
            "classification": "low_quality_observation_present",
            "raw_coordinates_present": True,
            "interpolated_relbow_candidate_present": False,
            "repair_applied": False,
            "repair_acceptance": "rejected",
            "downstream_valid": False,
            "reason": ELBOW_REASON,
            "defer_to_task": "T07C",
            "t06c_reason": "forearm_self_occlusion",
        },
        "boundary_continuity_warnings": [{
            "repair_gap_id": "GAP_182_185",
            "joint": "RWrist",
            "frames": [182, 183, 184, 185],
            "entry_velocity_discontinuity_norm_per_s": 7.9599797880017285,
            "reported_rounded_value": 7.959980,
        }],
        "benchmark_results_changed": False,
        "global_method_ranking_changed": False,
        "selected_method": "linear",
        "method_label": "provisional best on E001",
    }
    summary["accepted_repair_frame_count"] = 7
    summary["rejected_applied_repair_frame_count"] = 0
    summary["rejected_low_quality_observation_frame_count"] = 2
    summary["boundary_continuity_warning_gap_count"] = 1
    summary["processing"]["manual_review_finalized"] = True
    summary["processing"]["relbow_interpolation_created"] = False
    summary["processing"]["synthetic_benchmark_modified"] = False
    summary["readonly_hashes_at_r1"] = readonly_hashes_before

    jsonl_text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in finalized)
    atomic_write(args.repaired_jsonl, jsonl_text)
    write_csv(args.repaired_csv, finalized)
    atomic_write(args.repair_summary, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    readonly_hashes_after = {str(path): sha256_file(path) for path in readonly}
    if readonly_hashes_after != readonly_hashes_before:
        raise RuntimeError("a read-only T07B input changed during R1 finalization")
    result = {
        "status": "complete",
        "relbow_64_65_classification": "low_quality_observation_present",
        "accepted_rwrist_frames": sorted(WRIST_REVIEW_FRAMES),
        "rejected_relbow_frames": sorted(ELBOW_REJECTED_FRAMES),
        "boundary_warning_frames": sorted(BOUNDARY_WARNING_FRAMES),
        "readonly_hashes_unchanged": True,
        "output_hashes": {str(path): sha256_file(path) for path in outputs},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
