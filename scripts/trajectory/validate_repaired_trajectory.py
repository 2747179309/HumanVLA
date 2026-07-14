#!/usr/bin/env python3
"""Independently validate T07B benchmark and derived repair artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from gap_recovery_common import joint_reliable, load_csv, load_jsonl, manual_excluded_frames, sha256_file

EXPECTED_REPAIRED = {64, 65, 143, 182, 183, 184, 185}
ADDED_FIELDS = {
    "rwrist_x_repaired_px", "rwrist_y_repaired_px", "rwrist_x_repaired_norm",
    "rwrist_y_repaired_norm", "repair_mask", "repair_mask_by_joint", "repair_method",
    "repair_source", "repair_gap_id", "repair_confidence", "original_quality_reason",
    "deferred_corruption_candidate_ids", "repair_annotation_version",
    "automatic_repair_confidence", "repair_applied", "manual_review_status",
    "repair_acceptance", "downstream_valid", "manual_note", "defer_to_task",
    "repair_reason", "boundary_continuity_warning",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate T07B leakage controls, benchmark groups, repairs, hashes, and overlay decode.")
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--trajectory-summary", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--benchmark-csv", required=True, type=Path)
    parser.add_argument("--benchmark-json", required=True, type=Path)
    parser.add_argument("--repaired-jsonl", required=True, type=Path)
    parser.add_argument("--repaired-csv", required=True, type=Path)
    parser.add_argument("--repair-summary", required=True, type=Path)
    parser.add_argument("--corruption-list", required=True, type=Path)
    parser.add_argument("--comparison-plot", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    return parser.parse_args()


def csv_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def video_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(result.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"], "width": int(stream["width"]),
        "height": int(stream["height"]), "fps": stream["avg_frame_rate"],
        "frames": int(stream["nb_read_frames"]),
    }


def main() -> int:
    args = parse_args()
    paths = vars(args)
    for value in paths.values():
        if isinstance(value, Path) and not value.is_file():
            raise FileNotFoundError(value)
    errors: list[str] = []
    raw = load_jsonl(args.trajectory)
    quality = load_jsonl(args.quality_mask)
    review = load_csv(args.review_csv)
    repaired = load_jsonl(args.repaired_jsonl)
    manifest = load_csv(args.manifest)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    benchmark = json.loads(args.benchmark_json.read_text(encoding="utf-8"))
    repair_summary = json.loads(args.repair_summary.read_text(encoding="utf-8"))
    corruption = json.loads(args.corruption_list.read_text(encoding="utf-8"))
    source_hashes = {
        str(path): sha256_file(path) for path in
        (args.trajectory, args.quality_mask, args.review_csv, args.trajectory_summary, args.policy)
    }
    if len(raw) != 345 or len(repaired) != 345 or len(quality) != 345:
        errors.append("raw/repaired/quality row count is not 345")
    if [row.get("frame_index") for row in repaired] != list(range(345)):
        errors.append("repaired frame coverage is not 0..344")
    for frame, (raw_row, repaired_row) in enumerate(zip(raw, repaired)):
        if set(repaired_row) != set(raw_row) | ADDED_FIELDS:
            errors.append(f"frame {frame}: repaired field set mismatch")
            continue
        if any(repaired_row[key] != value for key, value in raw_row.items()):
            errors.append(f"frame {frame}: raw field changed")
        expected_mask = frame in EXPECTED_REPAIRED
        if repaired_row["repair_mask"] is not expected_mask:
            errors.append(f"frame {frame}: repair mask mismatch")
        if repaired_row["repair_mask_by_joint"] != {"RElbow": False, "RWrist": expected_mask}:
            errors.append(f"frame {frame}: joint repair mask mismatch")
        if repaired_row["repair_applied"] != {"RElbow": False, "RWrist": expected_mask}:
            errors.append(f"frame {frame}: per-joint repair_applied mismatch")
        if expected_mask:
            if raw_row["rwrist_x_px"] is not None or raw_row["rwrist_x_norm"] is not None:
                errors.append(f"frame {frame}: declared real gap has non-null raw wrist")
            if any(repaired_row[key] is None for key in (
                "rwrist_x_repaired_px", "rwrist_y_repaired_px", "rwrist_x_repaired_norm", "rwrist_y_repaired_norm",
            )):
                errors.append(f"frame {frame}: repair coordinate is null")
            expected_x = raw_row["neck_x_px"] + repaired_row["rwrist_x_repaired_norm"] * raw_row["shoulder_width_px"]
            expected_y = raw_row["neck_y_px"] + repaired_row["rwrist_y_repaired_norm"] * raw_row["shoulder_width_px"]
            if not math.isclose(repaired_row["rwrist_x_repaired_px"], expected_x, abs_tol=1e-9):
                errors.append(f"frame {frame}: repaired x pixel/norm inconsistency")
            if not math.isclose(repaired_row["rwrist_y_repaired_px"], expected_y, abs_tol=1e-9):
                errors.append(f"frame {frame}: repaired y pixel/norm inconsistency")
        elif repaired_row["rwrist_x_repaired_px"] != raw_row["rwrist_x_px"]:
            errors.append(f"frame {frame}: observed x was changed")
        if frame in EXPECTED_REPAIRED:
            if repaired_row["manual_review_status"]["RWrist"] != "pass":
                errors.append(f"frame {frame}: RWrist manual review is not pass")
            if repaired_row["repair_acceptance"]["RWrist"] != "accepted":
                errors.append(f"frame {frame}: RWrist repair is not accepted")
            if repaired_row["repair_confidence"]["RWrist"] != "high":
                errors.append(f"frame {frame}: RWrist manual confidence is not high")
            if repaired_row["downstream_valid"]["RWrist"] is not True:
                errors.append(f"frame {frame}: accepted RWrist is not downstream-valid")
        expected_warning = frame in {182, 183, 184, 185}
        if repaired_row["boundary_continuity_warning"]["RWrist"] is not expected_warning:
            errors.append(f"frame {frame}: RWrist boundary warning mismatch")
        if frame in {64, 65}:
            if repaired_row["manual_review_status"]["RElbow"] != "fail":
                errors.append(f"frame {frame}: RElbow manual review is not fail")
            if repaired_row["repair_acceptance"]["RElbow"] != "rejected":
                errors.append(f"frame {frame}: RElbow review is not rejected")
            if repaired_row["repair_applied"]["RElbow"] is not False:
                errors.append(f"frame {frame}: RElbow repair was incorrectly applied")
            if repaired_row["downstream_valid"]["RElbow"] is not False:
                errors.append(f"frame {frame}: rejected RElbow is downstream-valid")
            if repaired_row["defer_to_task"]["RElbow"] != "T07C":
                errors.append(f"frame {frame}: rejected RElbow is not deferred to T07C")
            if repaired_row["repair_reason"]["RElbow"] != "low_quality_observation_requires_quality_aware_refinement":
                errors.append(f"frame {frame}: rejected RElbow reason mismatch")
            if raw_row["relbow_x_px"] is None or repaired_row["relbow_x_px"] != raw_row["relbow_x_px"]:
                errors.append(f"frame {frame}: original low-quality RElbow was not preserved")
    if any(repaired[frame]["repair_mask"] for frame in (0, 1)):
        errors.append("frame 0-1 was repaired")

    with args.repaired_csv.open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != 345:
        errors.append("repaired CSV row count is not 345")
    else:
        for frame, (json_row, csv_row) in enumerate(zip(repaired, csv_rows)):
            if set(csv_row) != set(json_row) or any(csv_row[key] != csv_value(value) for key, value in json_row.items()):
                errors.append(f"frame {frame}: repaired CSV differs from JSONL")
                break

    excluded = manual_excluded_frames(review, {"occlusion_error", "normalization_artifact"})
    real_missing = set(policy["synthetic_selection"]["exclude_real_missing_frames"])
    seen_samples: set[tuple[str, int, int]] = set()
    for sample in manifest:
        gap = json.loads(sample["gap_frames"])
        context = json.loads(sample["context_frames"])
        joint = sample["joint"]
        key = (joint, int(sample["gap_start"]), int(sample["gap_end"]))
        if key in seen_samples:
            errors.append(f"duplicate synthetic sample {key}")
        seen_samples.add(key)
        window = [*gap, *context]
        if set(window) & (real_missing | excluded | {0, 1}):
            errors.append(f"sample {sample['gap_id']} leaks excluded frames")
        if len({raw[frame]["phase_label"] for frame in window}) != 1:
            errors.append(f"sample {sample['gap_id']} crosses phase")
        if any(not joint_reliable(raw[frame], joint) for frame in window):
            errors.append(f"sample {sample['gap_id']} uses low-quality data")
    length_counts = {length: sum(int(row["gap_length"]) == length for row in manifest) for length in (1, 2, 3, 4)}
    if length_counts != {1: 16, 2: 16, 3: 6, 4: 6}:
        errors.append(f"synthetic length counts mismatch: {length_counts}")

    benchmark_rows = load_csv(args.benchmark_csv)
    expected_methods = set(policy["methods"]["ranking_methods"] + policy["methods"]["diagnostic_methods"])
    if len(benchmark_rows) != len(manifest) * len(expected_methods):
        errors.append("benchmark CSV row count mismatch")
    if {row["method"] for row in benchmark_rows} != expected_methods:
        errors.append("benchmark method variants mismatch")
    required_metrics = {
        "mae_px", "rmse_px", "mae_norm", "rmse_norm", "max_error_px",
        "velocity_error_px_per_s", "velocity_error_norm_per_s",
        "acceleration_error_px_per_s2", "acceleration_error_norm_per_s2",
        "jerk_error_px_per_s3", "jerk_error_norm_per_s3",
        "entry_velocity_discontinuity_px_per_s", "exit_velocity_discontinuity_px_per_s",
        "endpoint_error_px", "trajectory_length_error_px", "curvature_error_px",
    }
    if benchmark_rows and not required_metrics <= set(benchmark_rows[0]):
        errors.append("benchmark required metrics are incomplete")
    if benchmark.get("synthetic_sample_count") != len(manifest):
        errors.append("benchmark JSON sample count mismatch")
    leakage = benchmark.get("leakage_checks", {})
    if not all(leakage.get(key) is expected for key, expected in {
        "only_high_quality_ground_truth": True,
        "masked_ground_truth_passed_to_recovery_methods": False,
        "real_missing_frames_used": False,
        "cross_phase_gap_used": False,
        "manual_error_or_normalization_artifact_frames_used": False,
        "model_training_performed": False,
    }.items()):
        errors.append("benchmark leakage declaration mismatch")
    selected = benchmark.get("selection", {}).get("selected_method")
    if selected not in policy["methods"]["ranking_methods"]:
        errors.append("provisional best is invalid")
    if benchmark.get("selection", {}).get("label") != "provisional best on E001":
        errors.append("provisional best scope label mismatch")

    if repair_summary.get("repaired_frames") != sorted(EXPECTED_REPAIRED):
        errors.append("repair summary frame list mismatch")
    if repair_summary.get("selected_method") != selected:
        errors.append("repair method differs from benchmark selection")
    if repair_summary.get("boundary_abnormal_gap_count") != 0:
        errors.append("real repair has a >0.5 shoulder-width boundary")
    manual_review = repair_summary.get("manual_review", {})
    if manual_review.get("accepted_rwrist_frames") != sorted(EXPECTED_REPAIRED):
        errors.append("manual summary accepted RWrist frames mismatch")
    if manual_review.get("rejected_relbow_frames") != [64, 65]:
        errors.append("manual summary rejected RElbow frames mismatch")
    if manual_review.get("global_method_ranking_changed") is not False:
        errors.append("manual finalization changed the global method ranking")
    warnings = manual_review.get("boundary_continuity_warnings", [])
    if len(warnings) != 1 or not math.isclose(
        warnings[0].get("entry_velocity_discontinuity_norm_per_s", math.nan),
        7.9599797880017285,
        abs_tol=1e-12,
    ):
        errors.append("182-185 boundary continuity warning is missing or changed")
    summary_input_hashes = repair_summary.get("input_hashes", {})
    for path in (args.trajectory, args.quality_mask, args.review_csv, args.benchmark_json, args.policy):
        if summary_input_hashes.get(str(path)) != sha256_file(path):
            errors.append(f"repair summary input hash mismatch: {path}")
    if corruption.get("candidate_count") != 8 or len(corruption.get("candidates", [])) != 8:
        errors.append("corruption candidate count is not 8")
    if any(item.get("status") != "deferred_to_T07C" or item.get("candidate_joint_repaired_in_T07B") is not False for item in corruption.get("candidates", [])):
        errors.append("corruption candidate deferral mismatch")

    if args.comparison_plot.stat().st_size <= 0:
        errors.append("comparison plot is empty")
    overlay = video_probe(args.overlay)
    if overlay != {"codec": "h264", "width": 1280, "height": 720, "fps": "30/1", "frames": 345}:
        errors.append(f"overlay metadata mismatch: {overlay}")
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(args.overlay), "-f", "null", "-"], capture_output=True)
    if decode.returncode:
        errors.append("overlay full decode failed")

    result = {
        "validation_passed": not errors, "errors": errors,
        "total_frames": len(repaired), "repaired_frames": sorted(EXPECTED_REPAIRED),
        "synthetic_sample_counts_by_length": length_counts,
        "provisional_best_on_E001": selected,
        "corruption_candidates_deferred": corruption.get("candidate_count"),
        "overlay": overlay, "overlay_full_decode_passed": decode.returncode == 0,
        "source_hashes": source_hashes,
        "output_hashes": {
            str(path): sha256_file(path) for path in
            (args.manifest, args.benchmark_csv, args.benchmark_json, args.repaired_jsonl,
             args.repaired_csv, args.repair_summary, args.corruption_list, args.comparison_plot, args.overlay)
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
