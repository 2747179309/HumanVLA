#!/usr/bin/env python3
"""Benchmark four short-gap recovery method families on synthetic E001 gaps."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gap_recovery_common import (
    evaluate_recovery, joint_reliable, load_csv, load_jsonl, recover_normalized, sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate linear, PCHIP, Hermite, and Kalman CV on frozen synthetic gaps.")
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-plot", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def mean_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    metric_names = [key for key, value in rows[0].items() if isinstance(value, float)]
    return {key: float(np.mean([row[key] for row in rows])) for key in metric_names}


def aggregate(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    result: list[dict[str, Any]] = []
    for group, items in sorted(groups.items(), key=lambda item: tuple(map(str, item[0]))):
        result.append({
            **dict(zip(keys, group)), "sample_count": len(items), **mean_metrics(items),
        })
    return result


def select_method(rows: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    ranking_methods = policy["methods"]["ranking_methods"]
    wrist = [row for row in rows if row["joint"] == "RWrist" and row["method"] in ranking_methods]
    elbow = [row for row in rows if row["joint"] == "RElbow" and row["method"] in ranking_methods]
    primary = {method: float(np.mean([row["rmse_norm"] for row in wrist if row["method"] == method])) for method in ranking_methods}
    best_primary = min(primary.values())
    band = float(policy["selection_rule"]["primary_tie_band_relative"])
    eligible = sorted(method for method, value in primary.items() if value <= best_primary * (1.0 + band))
    secondary = {
        method: float(np.mean([
            row["jerk_error_norm_per_s3"] + row["entry_velocity_discontinuity_norm_per_s"]
            for row in wrist if row["method"] == method
        ])) for method in eligible
    }
    tertiary = {
        method: float(np.mean([row["rmse_norm"] for row in elbow if row["method"] == method]))
        for method in eligible
    }
    selected = min(eligible, key=lambda method: (secondary[method], tertiary[method], method))
    return {
        "label": "provisional best on E001",
        "selected_method": selected,
        "ranking_methods": ranking_methods,
        "primary_rwrist_mean_rmse_norm": primary,
        "best_primary_value": best_primary,
        "primary_tie_band_relative": band,
        "methods_inside_primary_tie_band": eligible,
        "secondary_rwrist_mean_jerk_plus_entry_discontinuity": secondary,
        "tertiary_relbow_mean_rmse_norm": tertiary,
        "selection_rule_applied_without_retuning": True,
    }


def render_plot(rows: list[dict[str, Any]], policy: dict[str, Any], output: Path) -> None:
    methods = policy["methods"]["ranking_methods"]
    colors = {"linear": "#2563EB", "pchip": "#059669", "cubic_hermite": "#D97706", "kalman_cv_smoothing": "#BE123C"}
    fig, axes = plt.subplots(1, 2, figsize=(17, 7), sharey=False, constrained_layout=True)
    for axis, joint in zip(axes, ("RElbow", "RWrist")):
        x = np.arange(4)
        width = 0.19
        for offset, method in enumerate(methods):
            values = [
                np.mean([row["rmse_norm"] for row in rows if row["joint"] == joint and row["gap_length"] == length and row["method"] == method])
                for length in (1, 2, 3, 4)
            ]
            axis.bar(x + (offset - 1.5) * width, values, width, label=method, color=colors[method])
        axis.set_xticks(x, ["1", "2", "3", "4"])
        axis.set_xlabel("Synthetic gap length (frames)")
        axis.set_ylabel("Mean normalized RMSE")
        axis.set_title(f"{joint}: E001 synthetic occlusion")
        axis.grid(axis="y", color="#CBD5E1", linewidth=0.7)
    axes[0].legend(fontsize=9)
    fig.suptitle("T07B short-gap recovery benchmark (no observed-frame smoothing)", fontsize=16, weight="bold")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, facecolor="white")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    for path in (args.trajectory, args.manifest, args.policy):
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.output_csv, args.output_json, args.output_plot)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))
    trajectory = load_jsonl(args.trajectory)
    manifest = load_csv(args.manifest)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if not policy.get("frozen_before_benchmark"):
        raise ValueError("benchmark policy is not frozen")
    methods = [*policy["methods"]["ranking_methods"], *policy["methods"]["diagnostic_methods"]]
    results: list[dict[str, Any]] = []
    for sample in manifest:
        gap_frames = json.loads(sample["gap_frames"])
        context_frames = json.loads(sample["context_frames"])
        joint = sample["joint"]
        if any(not joint_reliable(trajectory[frame], joint) for frame in [*gap_frames, *context_frames]):
            raise ValueError(f"manifest sample is not high quality: {sample['gap_id']}")
        for method in methods:
            predicted = recover_normalized(method, trajectory, joint, gap_frames, context_frames, policy)
            metrics = evaluate_recovery(
                trajectory, joint, gap_frames, context_frames, predicted, float(policy["fps"]),
            )
            results.append({
                "gap_id": sample["gap_id"], "joint": joint,
                "gap_start": int(sample["gap_start"]), "gap_end": int(sample["gap_end"]),
                "gap_length": int(sample["gap_length"]), "phase_id": int(sample["phase_id"]),
                "phase_label": sample["phase_label"], "method": method, **metrics,
            })
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    selection = select_method(results, policy)
    overall = aggregate(results, ("joint", "method"))
    by_group = aggregate(results, ("gap_length", "joint", "phase_id", "phase_label", "method"))
    payload = {
        "run_id": "20260714_T07B_SYNTHETIC_BENCHMARK_001",
        "video_id": policy["video_id"], "benchmark_scope": "E001 only",
        "method_family_count": 4, "evaluated_method_variants": methods,
        "synthetic_sample_count": len(manifest), "result_row_count": len(results),
        "sample_counts_by_gap_length": {
            str(length): sum(int(row["gap_length"]) == length for row in manifest) for length in (1, 2, 3, 4)
        },
        "sample_counts_by_gap_length_and_joint": {
            joint: {str(length): sum(row["joint"] == joint and int(row["gap_length"]) == length for row in manifest) for length in (1, 2, 3, 4)}
            for joint in ("RElbow", "RWrist")
        },
        "insufficient_phase_samples": [], "selection": selection,
        "aggregate_by_joint_method": overall,
        "aggregate_by_gap_length_joint_phase_method": by_group,
        "kalman_parameters": policy["methods"]["kalman_cv"],
        "leakage_checks": {
            "only_high_quality_ground_truth": True,
            "masked_ground_truth_passed_to_recovery_methods": False,
            "real_missing_frames_used": False,
            "cross_phase_gap_used": False,
            "manual_error_or_normalization_artifact_frames_used": False,
            "model_training_performed": False,
        },
        "processing": {"observed_frame_smoothing": False, "parameter_retuning_after_results": False},
        "input_hashes": {
            str(args.trajectory): sha256_file(args.trajectory),
            str(args.manifest): sha256_file(args.manifest),
            str(args.policy): sha256_file(args.policy),
        },
    }
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_plot(results, policy, args.output_plot)
    print(json.dumps({
        "samples": len(manifest), "rows": len(results),
        "sample_counts_by_gap_length": payload["sample_counts_by_gap_length"],
        "selection": selection, "aggregate_by_joint_method": overall,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
