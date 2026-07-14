#!/usr/bin/env python3
"""Evaluate T07C-B3 predictions without feeding ground truth to any filter."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


METRIC_COLUMNS = (
    "corrupted_region_mae_px",
    "corrupted_region_rmse_px",
    "corrupted_region_mae_norm",
    "corrupted_region_rmse_norm",
    "corrupted_region_rmse_norm_with_missing_penalty",
    "clean_region_displacement_px",
    "clean_region_displacement_norm",
    "max_error_px",
    "max_error_norm",
    "velocity_rmse_px_s",
    "velocity_rmse_norm_s",
    "acceleration_rmse_px_s2",
    "acceleration_rmse_norm_s2",
    "jerk_rmse_px_s3",
    "jerk_rmse_norm_s3",
    "phase_boundary_shift_norm",
    "real_motion_attenuation",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the single frozen T07C-B3 test run and generate grouped reports.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--selected-parameters", required=True, type=Path)
    parser.add_argument("--test-audit", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--output-plot", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def optional_points(values: list[list[float] | None]) -> np.ndarray:
    result = np.full((len(values), 2), np.nan, dtype=float)
    for index, value in enumerate(values):
        if value is not None:
            result[index] = np.asarray(value, dtype=float)
    return result


def mean_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if len(finite) else None


def rmse_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(np.square(finite)))) if len(finite) else None


def max_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.max(finite)) if len(finite) else None


def derivative_rmse(predicted: np.ndarray, truth: np.ndarray, dt: float, order: int) -> float | None:
    """Compute derivative-vector RMSE only where all required points are available."""
    pred = predicted.copy()
    target = truth.copy()
    for _ in range(order):
        pred = np.diff(pred, axis=0) / dt
        target = np.diff(target, axis=0) / dt
    valid = np.isfinite(pred).all(axis=1) & np.isfinite(target).all(axis=1)
    if not valid.any():
        return None
    errors = np.linalg.norm(pred[valid] - target[valid], axis=1)
    return float(np.sqrt(np.mean(np.square(errors))))


def compute_sample_metrics(
    sample: dict[str, Any], prediction: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Compare output to held-out truth; masks are used only here, never by filters."""
    truth_norm = np.asarray(sample["clean_trajectory_norm"], dtype=float)
    truth_px = np.asarray(sample["clean_trajectory_px"], dtype=float)
    pred_norm = optional_points(prediction["predicted_trajectory_norm"])
    pred_px = optional_points(prediction["predicted_trajectory_px"])
    corruption = np.asarray(sample["corruption_mask"], dtype=bool)
    available = np.isfinite(pred_norm).all(axis=1) & np.isfinite(pred_px).all(axis=1)
    error_norm = np.full(len(truth_norm), np.nan)
    error_px = np.full(len(truth_px), np.nan)
    error_norm[available] = np.linalg.norm(pred_norm[available] - truth_norm[available], axis=1)
    error_px[available] = np.linalg.norm(pred_px[available] - truth_px[available], axis=1)
    corrupted_available = corruption & available
    clean_available = ~corruption & available
    penalty = float(config["selection_protocol"]["missing_prediction_penalty_norm"])
    penalized_corrupted = np.where(corrupted_available, error_norm, np.where(corruption, penalty, np.nan))
    dt = float(config["evaluation"]["derivative_dt_sec"])

    clean_truth_path = float(np.sum(np.linalg.norm(np.diff(truth_norm, axis=0), axis=1)))
    real_motion_threshold = float(config["evaluation"]["real_motion_minimum_clean_path_norm"])
    if clean_truth_path >= real_motion_threshold and available.all():
        output_path = float(np.sum(np.linalg.norm(np.diff(pred_norm, axis=0), axis=1)))
        attenuation = 1.0 - output_path / clean_truth_path
        attenuation_status = "computed"
    else:
        attenuation = None
        attenuation_status = "not_applicable_low_clean_motion" if clean_truth_path < real_motion_threshold else "not_available_missing_output"

    complete_output = bool(available.all())
    return {
        "sample_id": sample["sample_id"],
        "method": prediction["method"],
        "parameter_id": prediction["parameter_id"],
        "joint": sample["target_joint"],
        "corruption_type": sample["corruption_type"],
        "severity": sample["intensity_id"],
        "phase": sample["phase_label"],
        "split": sample["split"],
        "source_window_id": sample["source_window_id"],
        "corrupted_region_frame_count": int(corruption.sum()),
        "corrupted_region_prediction_count": int(corrupted_available.sum()),
        "corrupted_region_missing_prediction_count": int((corruption & ~available).sum()),
        "clean_region_frame_count": int((~corruption).sum()),
        "clean_region_prediction_count": int(clean_available.sum()),
        "output_coverage": float(np.mean(available)),
        "corrupted_region_mae_px": mean_or_none(error_px[corrupted_available]),
        "corrupted_region_rmse_px": rmse_or_none(error_px[corrupted_available]),
        "corrupted_region_mae_norm": mean_or_none(error_norm[corrupted_available]),
        "corrupted_region_rmse_norm": rmse_or_none(error_norm[corrupted_available]),
        "corrupted_region_rmse_norm_with_missing_penalty": rmse_or_none(penalized_corrupted[corruption]),
        "clean_region_displacement_px": mean_or_none(error_px[clean_available]),
        "clean_region_displacement_norm": mean_or_none(error_norm[clean_available]),
        # A maximum over only the surviving points would hide a missing prediction.
        "max_error_px": max_or_none(error_px) if complete_output else None,
        "max_error_norm": max_or_none(error_norm) if complete_output else None,
        "max_error_status": "computed" if complete_output else "not_available_missing_output",
        "velocity_rmse_px_s": derivative_rmse(pred_px, truth_px, dt, 1) if complete_output else None,
        "velocity_rmse_norm_s": derivative_rmse(pred_norm, truth_norm, dt, 1) if complete_output else None,
        "acceleration_rmse_px_s2": derivative_rmse(pred_px, truth_px, dt, 2) if complete_output else None,
        "acceleration_rmse_norm_s2": derivative_rmse(pred_norm, truth_norm, dt, 2) if complete_output else None,
        "jerk_rmse_px_s3": derivative_rmse(pred_px, truth_px, dt, 3) if complete_output else None,
        "jerk_rmse_norm_s3": derivative_rmse(pred_norm, truth_norm, dt, 3) if complete_output else None,
        "derivative_metric_status": "computed" if complete_output else "not_available_missing_output",
        "phase_boundary_shift_norm": None,
        "phase_boundary_shift_status": "not_applicable_same_phase_b2_window",
        "real_motion_attenuation": attenuation,
        "real_motion_attenuation_status": attenuation_status,
        "clean_truth_path_norm": clean_truth_path,
    }


def aggregate_metrics(rows: list[dict[str, Any]], dimensions: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[name] for name in dimensions)].append(row)
    output = []
    for key, members in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        aggregate = {name: value for name, value in zip(dimensions, key)}
        aggregate["sample_count"] = len(members)
        for metric in METRIC_COLUMNS:
            values = [member[metric] for member in members if member.get(metric) is not None]
            aggregate[f"mean_{metric}"] = float(np.mean(values)) if values else None
            aggregate[f"defined_{metric}_count"] = len(values)
        aggregate["total_corrupted_missing_predictions"] = sum(member["corrupted_region_missing_prediction_count"] for member in members)
        aggregate["mean_output_coverage"] = float(np.mean([member["output_coverage"] for member in members]))
        output.append(aggregate)
    return output


def csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("cannot write empty CSV")
    from io import StringIO

    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def render_plot(method_summary: list[dict[str, Any]], path: Path) -> None:
    methods = [row["method"] for row in method_summary]
    rmse = [row["mean_corrupted_region_rmse_norm_with_missing_penalty"] for row in method_summary]
    crd = [row["mean_clean_region_displacement_norm"] for row in method_summary]
    coverage = [row["mean_output_coverage"] for row in method_summary]
    labels = [name.replace("confidence_weighted_kalman", "conf-weighted KF").replace("corrupted_input", "no processing").replace("savitzky_golay", "SG").replace("one_euro", "One Euro").replace("kalman_cv", "Kalman CV") for name in methods]
    positions = np.arange(len(methods))
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    width = 0.36
    axes[0].bar(positions - width / 2, rmse, width, label="Corrupted RMSE (penalized)", color="#C94C38")
    axes[0].bar(positions + width / 2, crd, width, label="Clean displacement", color="#2A7F9E")
    axes[0].set_ylabel("Neck/shoulder normalized distance")
    axes[0].set_title("Frozen T07C-B3 test metrics")
    axes[0].set_xticks(positions, labels, rotation=20, ha="right")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(positions, coverage, color="#587A52")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_ylabel("Output coverage")
    axes[1].set_title("Missing outputs are not replaced by zero")
    axes[1].set_xticks(positions, labels, rotation=20, ha="right")
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("E001 within-episode synthetic benchmark; test used once", fontweight="bold")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    for path in (args.config, args.dataset, args.predictions, args.selected_parameters, args.test_audit):
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.output_csv, args.output_summary, args.output_plot)
    if not args.overwrite and any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite existing evaluation output")

    config = load_json(args.config)
    samples = {row["sample_id"]: row for row in load_jsonl(args.dataset)}
    predictions = [row for row in load_jsonl(args.predictions) if row["split"] == "test"]
    selected = load_json(args.selected_parameters)
    audit = load_json(args.test_audit)
    if audit.get("test_evaluation_count") != 1 or audit.get("test_prediction_count") != 480:
        raise ValueError(f"invalid single-test audit: {audit}")
    if len(predictions) != 480:
        raise ValueError(f"expected 96 test samples x 5 methods, got {len(predictions)}")
    keys = [(row["sample_id"], row["method"]) for row in predictions]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate test sample/method predictions")
    if any(row["ground_truth_used_as_filter_input"] or row["corruption_mask_used_as_filter_input"] for row in predictions):
        raise ValueError("filter-input leakage flag detected")

    rows = [compute_sample_metrics(samples[prediction["sample_id"]], prediction, config) for prediction in predictions]
    dimensions = config["evaluation"]["group_dimensions"]
    grouped = aggregate_metrics(rows, dimensions)
    method_summary = aggregate_metrics(rows, ["method"])
    method_summary.sort(key=lambda row: row["mean_corrupted_region_rmse_norm_with_missing_penalty"])
    phase_boundary_defined = sum(row["phase_boundary_shift_norm"] is not None for row in rows)
    summary = {
        "run_id": "20260714_T07C_B3_TEST_EVALUATION_001",
        "status": "complete_pending_quality_review",
        "scope": "E001 within-episode synthetic benchmark only",
        "test_was_run_once": True,
        "test_sample_count": 96,
        "test_prediction_count": 480,
        "methods": sorted({row["method"] for row in rows}),
        "selected_parameters": selected["selected_parameters"],
        "method_summary": method_summary,
        "group_dimensions": dimensions,
        "grouped_results": grouped,
        "phase_boundary_shift": {
            "defined_sample_count": phase_boundary_defined,
            "status": "not_applicable_same_phase_b2_windows",
            "note": "B2 clean windows never cross an action-phase boundary; null is reported rather than a fabricated zero.",
        },
        "nan_policy": "Undefined metrics remain null/blank; no NaN is converted to zero.",
        "test_adjustment_performed": False,
        "provenance_sha256": {
            "config": sha256_file(args.config),
            "dataset": sha256_file(args.dataset),
            "predictions": sha256_file(args.predictions),
            "selected_parameters": sha256_file(args.selected_parameters),
            "test_audit": sha256_file(args.test_audit),
        },
    }
    atomic_write(args.output_csv, csv_text(rows))
    atomic_write(args.output_summary, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    render_plot(method_summary, args.output_plot)
    print(json.dumps({"test_rows": len(rows), "group_count": len(grouped), "method_summary": method_summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
