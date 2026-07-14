#!/usr/bin/env python3
"""Select T07C-B3 parameters on validation data using a preregistered grid."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from evaluate_refinement_baselines import compute_sample_metrics
from run_traditional_baselines import (
    METHODS,
    expand_parameter_grid,
    load_json,
    load_jsonl,
    parameter_id,
    run_sample,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate every preregistered candidate on train (diagnostic) and val "
            "(selection). This script never loads or evaluates test samples."
        )
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--output-search-csv", required=True, type=Path)
    parser.add_argument("--output-selected-json", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


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


def average(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return float(np.mean(values)) if values else None


def evaluate_candidate(
    method: str,
    parameters: dict[str, Any],
    samples: list[dict[str, Any]],
    raw_by_frame: dict[int, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one candidate; clean truth and masks enter metrics only after filtering."""
    metrics = []
    for sample in samples:
        prediction = run_sample(sample, method, parameters, raw_by_frame, float(config["fps"]))
        if prediction["ground_truth_used_as_filter_input"] or prediction["corruption_mask_used_as_filter_input"]:
            raise AssertionError("filter input leakage")
        metrics.append(compute_sample_metrics(sample, prediction, config))
    return {
        "sample_count": len(metrics),
        "mean_corrupted_region_rmse_norm": average(metrics, "corrupted_region_rmse_norm"),
        "mean_corrupted_region_rmse_norm_with_missing_penalty": average(
            metrics, "corrupted_region_rmse_norm_with_missing_penalty"
        ),
        "mean_clean_region_displacement_norm": average(metrics, "clean_region_displacement_norm"),
        "mean_velocity_rmse_norm_s": average(metrics, "velocity_rmse_norm_s"),
        "mean_acceleration_rmse_norm_s2": average(metrics, "acceleration_rmse_norm_s2"),
        "mean_jerk_rmse_norm_s3": average(metrics, "jerk_rmse_norm_s3"),
        "mean_output_coverage": average(metrics, "output_coverage"),
        "missing_prediction_count": sum(row["corrupted_region_missing_prediction_count"] for row in metrics),
    }


def selection_score(metrics: dict[str, Any]) -> float:
    """Apply the frozen 0.6 primary-error + 0.4 clean-preservation rule."""
    primary = metrics["mean_corrupted_region_rmse_norm_with_missing_penalty"]
    clean = metrics["mean_clean_region_displacement_norm"]
    if primary is None or clean is None:
        raise ValueError("selection metrics are undefined")
    return 0.6 * float(primary) + 0.4 * float(clean)


def flatten(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def csv_text(rows: list[dict[str, Any]]) -> str:
    from io import StringIO

    fieldnames = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main() -> int:
    args = parse_args()
    for path in (args.config, args.dataset, args.raw_trajectory):
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.output_search_csv, args.output_selected_json)
    if not args.overwrite and any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite tuning outputs")

    config = load_json(args.config)
    all_samples = load_jsonl(args.dataset)
    train_samples = [row for row in all_samples if row["split"] == "train"]
    validation_samples = [row for row in all_samples if row["split"] == "val"]
    # Test rows are deliberately never retained by this script.
    if len(train_samples) != 168 or len(validation_samples) != 72:
        raise ValueError("frozen train/val counts changed")
    raw_rows = load_jsonl(args.raw_trajectory)
    raw_by_frame = {int(row["frame_index"]): row for row in raw_rows}

    search_rows = []
    candidates_by_method: dict[str, list[dict[str, Any]]] = {}
    for method in METHODS:
        method_candidates = []
        for candidate_index, parameters in enumerate(expand_parameter_grid(config, method), start=1):
            train_metrics = evaluate_candidate(method, parameters, train_samples, raw_by_frame, config)
            validation_metrics = evaluate_candidate(method, parameters, validation_samples, raw_by_frame, config)
            score = selection_score(validation_metrics)
            row = {
                "method": method,
                "candidate_index": candidate_index,
                "parameter_id": parameter_id(method, parameters),
                "parameters_json": json.dumps(parameters, sort_keys=True, separators=(",", ":")),
                "validation_selection_score": score,
                **flatten("train", train_metrics),
                **flatten("val", validation_metrics),
            }
            search_rows.append(row)
            method_candidates.append(row)
        candidates_by_method[method] = method_candidates

    selected_parameters = {}
    tie_fields = (
        "validation_selection_score",
        "val_mean_corrupted_region_rmse_norm_with_missing_penalty",
        "val_mean_clean_region_displacement_norm",
        "val_mean_velocity_rmse_norm_s",
        "parameter_id",
    )
    for method in METHODS[1:]:
        ranked = sorted(candidates_by_method[method], key=lambda row: tuple(row[field] for field in tie_fields))
        winner = ranked[0]
        selected_parameters[method] = {
            "parameter_id": winner["parameter_id"],
            "parameters": json.loads(winner["parameters_json"]),
            "validation_rank": 1,
            "validation_selection_score": winner["validation_selection_score"],
            "validation_primary_rmse_norm_with_missing_penalty": winner[
                "val_mean_corrupted_region_rmse_norm_with_missing_penalty"
            ],
            "validation_clean_region_displacement_norm": winner["val_mean_clean_region_displacement_norm"],
        }

    atomic_write(args.output_search_csv, csv_text(search_rows))
    selected = {
        "run_id": "20260714_T07C_B3_VALIDATION_SELECTION_001",
        "config_version": config["config_version"],
        "selection_split": "val",
        "train_role": "development_diagnostics_only",
        "all_preregistered_candidates_evaluated_on_validation": True,
        "test_status": "not_run",
        "test_metrics_loaded_by_tuning_script": False,
        "candidate_count_by_method": {method: len(rows) for method, rows in candidates_by_method.items()},
        "selection_rule": config["selection_protocol"],
        "selected_parameters": selected_parameters,
        "provenance_sha256": {
            "config": sha256_file(args.config),
            "dataset": sha256_file(args.dataset),
            "raw_trajectory": sha256_file(args.raw_trajectory),
        },
        "validation_search_csv": str(args.output_search_csv),
        "validation_search_csv_sha256": sha256_file(args.output_search_csv),
    }
    atomic_write(args.output_selected_json, json.dumps(selected, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
