#!/usr/bin/env python3
"""Analyze and plot the unfiltered T07A upper-limb trajectory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PHASE_COLORS = {
    0: "#6B7280", 1: "#D97706", 2: "#CA8A04", 3: "#DC2626",
    4: "#EA580C", 5: "#0891B2", 6: "#2563EB", 7: "#7C3AED",
    8: "#059669", 90: "#64748B", 91: "#BE123C", 98: "#111827",
}
OPERATION_PHASES = {"reach", "align", "grasp", "lift", "transport", "place", "release", "retract"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute raw trajectory statistics and a phase-colored normalized 2D plot."
    )
    parser.add_argument("--trajectory-jsonl", required=True, type=Path)
    parser.add_argument("--p001", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--phase-frames", required=True, type=Path)
    parser.add_argument("--t06c-validation", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--output-plot", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
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


def intervals(frames: list[int]) -> list[dict[str, int]]:
    if not frames:
        return []
    result: list[dict[str, int]] = []
    start = previous = frames[0]
    for frame in frames[1:]:
        if frame != previous + 1:
            result.append({"start_frame": start, "end_frame": previous, "length": previous - start + 1})
            start = frame
        previous = frame
    result.append({"start_frame": start, "end_frame": previous, "length": previous - start + 1})
    return result


def coordinate_range(rows: list[dict[str, Any]], prefix: str) -> dict[str, float | int | None]:
    points = [
        (row[f"{prefix}_x_norm"], row[f"{prefix}_y_norm"])
        for row in rows if row[f"{prefix}_x_norm"] is not None
    ]
    if not points:
        return {"frame_count": 0, "x_min": None, "x_max": None, "y_min": None, "y_max": None}
    xs, ys = zip(*points)
    return {
        "frame_count": len(points), "x_min": min(xs), "x_max": max(xs),
        "y_min": min(ys), "y_max": max(ys),
    }


def displacement_statistics(rows: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    displacements: list[dict[str, Any]] = []
    for previous, current in zip(rows, rows[1:]):
        if current["frame_index"] != previous["frame_index"] + 1:
            continue
        first = (previous[f"{prefix}_x_norm"], previous[f"{prefix}_y_norm"])
        second = (current[f"{prefix}_x_norm"], current[f"{prefix}_y_norm"])
        if None in first or None in second:
            continue
        distance = math.hypot(second[0] - first[0], second[1] - first[1])
        displacements.append({
            "from_frame": previous["frame_index"], "to_frame": current["frame_index"],
            "distance_norm": distance,
        })
    if not displacements:
        return {
            "consecutive_valid_edges": 0, "max": None,
            "suspicious_jump_rule": "Tukey extreme: displacement > Q3 + 3*IQR",
            "suspicious_jump_threshold": None, "suspicious_jumps": [],
        }
    values = np.array([item["distance_norm"] for item in displacements], dtype=float)
    q1, q3 = np.percentile(values, [25, 75])
    threshold = float(q3 + 3.0 * (q3 - q1))
    maximum = max(displacements, key=lambda item: item["distance_norm"])
    suspicious = [item for item in displacements if item["distance_norm"] > threshold]
    return {
        "consecutive_valid_edges": len(displacements),
        "mean_distance_norm": float(values.mean()), "median_distance_norm": float(np.median(values)),
        "q1": float(q1), "q3": float(q3), "iqr": float(q3 - q1),
        "max": maximum,
        "suspicious_jump_rule": "Tukey extreme: displacement > Q3 + 3*IQR",
        "suspicious_jump_threshold": threshold,
        "suspicious_jumps": suspicious,
    }


def scalar_field_statistics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    observations = [
        {"frame_index": row["frame_index"], "value_px": row[field]}
        for row in rows if row[field] is not None
    ]
    if not observations:
        return {"frame_count": 0, "mean_px": None, "std_px": None, "min_px": None, "max_px": None}
    values = np.array([item["value_px"] for item in observations], dtype=float)
    return {
        "frame_count": len(observations),
        "mean_px": float(values.mean()), "std_px": float(values.std()),
        "min_px": float(values.min()), "max_px": float(values.max()),
        "maximum_observation": max(observations, key=lambda item: item["value_px"]),
    }


def path_length(rows: list[dict[str, Any]], prefix: str, included_frames: set[int]) -> dict[str, Any]:
    length = 0.0
    edges_used = 0
    skipped = 0
    for previous, current in zip(rows, rows[1:]):
        if previous["frame_index"] not in included_frames or current["frame_index"] not in included_frames:
            continue
        first = (previous[f"{prefix}_x_norm"], previous[f"{prefix}_y_norm"])
        second = (current[f"{prefix}_x_norm"], current[f"{prefix}_y_norm"])
        if None in first or None in second:
            skipped += 1
            continue
        length += math.hypot(second[0] - first[0], second[1] - first[1])
        edges_used += 1
    return {
        "length_norm": length, "consecutive_edges_used": edges_used,
        "consecutive_edges_skipped_due_missing": skipped,
        "gap_bridging": False,
    }


def render_plot(rows: list[dict[str, Any]], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(18, 8), constrained_layout=True)
    for axis, prefix, title in zip(axes, ("relbow", "rwrist"), ("RElbow raw normalized trajectory", "RWrist raw normalized trajectory")):
        for previous, current in zip(rows, rows[1:]):
            if (
                previous[f"{prefix}_x_norm"] is not None and current[f"{prefix}_x_norm"] is not None
                and current["frame_index"] == previous["frame_index"] + 1
            ):
                axis.plot(
                    [previous[f"{prefix}_x_norm"], current[f"{prefix}_x_norm"]],
                    [previous[f"{prefix}_y_norm"], current[f"{prefix}_y_norm"]],
                    color="#CBD5E1", linewidth=0.7, zorder=1,
                )
        for phase_id in PHASE_COLORS:
            selected = [row for row in rows if row["phase_id"] == phase_id and row[f"{prefix}_x_norm"] is not None]
            if not selected:
                continue
            axis.scatter(
                [row[f"{prefix}_x_norm"] for row in selected],
                [row[f"{prefix}_y_norm"] for row in selected],
                s=22, color=PHASE_COLORS[phase_id], alpha=0.82,
                label=f"{selected[0]['phase_label']} ({phase_id})", zorder=2,
            )
        axis.scatter([0.0], [0.0], marker="*", s=220, color="#111827", label="Neck origin", zorder=3)
        axis.axhline(0, color="#94A3B8", linewidth=0.7)
        axis.axvline(0, color="#94A3B8", linewidth=0.7)
        axis.set_title(title, fontsize=15, weight="bold")
        axis.set_xlabel("x / shoulder width (right positive)")
        axis.set_ylabel("y / shoulder width (down positive; display inverted)")
        axis.invert_yaxis()
        axis.set_aspect("equal", adjustable="datalim")
        axis.grid(True, color="#E2E8F0", linewidth=0.7)
        axis.legend(fontsize=8, loc="best", ncol=2)
    fig.suptitle("T07A E001: unfiltered, non-interpolated upper-limb trajectories", fontsize=18, weight="bold")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, facecolor="white")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    inputs = (args.trajectory_jsonl, args.p001, args.quality_mask, args.phase_frames, args.t06c_validation)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.output_summary, args.output_plot)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))
    rows = load_jsonl(args.trajectory_jsonl)
    if len(rows) != args.expected_frames or [row["frame_index"] for row in rows] != list(range(args.expected_frames)):
        raise ValueError("trajectory must contain ordered frames 0..344")

    shoulder_rows = [row for row in rows if row["shoulder_width_px"] is not None]
    shoulder_values = np.array([row["shoulder_width_px"] for row in shoulder_rows], dtype=float)
    if len(shoulder_values) == 0 or np.any(shoulder_values <= 0):
        raise ValueError("no positive shoulder-width observations")
    shoulder_mean = float(shoulder_values.mean())
    shoulder_anomalies = []
    for previous, current in zip(rows, rows[1:]):
        if previous["shoulder_width_px"] is None or current["shoulder_width_px"] is None:
            continue
        change = abs(current["shoulder_width_px"] - previous["shoulder_width_px"])
        if change > shoulder_mean * 0.30:
            shoulder_anomalies.append({
                "from_frame": previous["frame_index"], "to_frame": current["frame_index"],
                "absolute_change_px": change, "threshold_px": shoulder_mean * 0.30,
            })

    per_phase: dict[str, Any] = {}
    phase_groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        phase_groups[(row["phase_id"], row["phase_label"])].append(row)
    for (phase_id, label), phase_rows in sorted(phase_groups.items()):
        frame_count = len(phase_rows)
        per_phase[label] = {
            "phase_id": phase_id, "frame_count": frame_count,
            "trajectory_valid_frames": sum(row["trajectory_valid"] for row in phase_rows),
            "trajectory_valid_rate": sum(row["trajectory_valid"] for row in phase_rows) / frame_count,
            "relbow_coordinate_frames": sum(row["relbow_coordinate_available"] for row in phase_rows),
            "relbow_source_valid_frames": sum(row["relbow_joint_valid"] for row in phase_rows),
            "relbow_effective_high_quality_frames": sum(row["relbow_effective_status"] == "valid" for row in phase_rows),
            "rwrist_valid_frames": sum(row["rwrist_coordinate_available"] for row in phase_rows),
            "rwrist_missing_frames": [row["frame_index"] for row in phase_rows if not row["rwrist_coordinate_available"]],
            "rwrist_valid_rate": sum(row["rwrist_coordinate_available"] for row in phase_rows) / frame_count,
        }

    operation_frames = {row["frame_index"] for row in rows if row["phase_label"] in OPERATION_PHASES}
    operation_range = [min(operation_frames), max(operation_frames)] if operation_frames else None
    relbow_missing = [row["frame_index"] for row in rows if not row["relbow_coordinate_available"]]
    rwrist_missing = [row["frame_index"] for row in rows if not row["rwrist_coordinate_available"]]
    frame_invalid = [row["frame_index"] for row in rows if not row["normalization_anchor_valid"]]
    summary = {
        "run_id": "20260714_T07A_REVIEW_SUPPLEMENT_001",
        "video_id": "pick_place_pilot_v1_E001", "total_frames": len(rows),
        "coordinate_system": {
            "origin_joint": "Neck", "scale_reference": "shoulder_width",
            "x_axis": "image_right_positive", "y_axis": "image_down_positive",
            "pelvis_or_lower_body_used": False,
        },
        "processing_policy": {
            "raw_coordinates_preserved": True, "interpolation": False,
            "filtering": False, "gap_bridging_for_distance": False,
            "low_quality_relbow_coordinates_retained_for_audit": True,
            "neck_and_shoulders_forced_fixed": False,
            "neck_and_shoulders_modified": False,
        },
        "human_review_supplement": {
            "abnormal_frame_correction": {"correct_frame": 143, "incorrect_frame": 43},
            "occlusion_affected_frames": [64, 65, 143, 182, 183, 184, 185],
            "occlusion_effect": "RWrist missing and/or RElbow low_quality",
            "neck_shoulder_motion_interpretation": (
                "real trunk and shoulder compensation near placement point B; not a detection error"
            ),
            "manual_action": "preserve raw Neck and bilateral shoulder coordinates without fixing, filtering, or removal",
        },
        "validity": {
            "trajectory_valid_frames": sum(row["trajectory_valid"] for row in rows),
            "trajectory_invalid_frames": [row["frame_index"] for row in rows if not row["trajectory_valid"]],
            "frame_invalid_frames": frame_invalid,
            "frame_invalid_intervals": intervals(frame_invalid),
            "relbow": {
                "coordinate_available_frames": sum(row["relbow_coordinate_available"] for row in rows),
                "source_joint_valid_frames": sum(row["relbow_joint_valid"] for row in rows),
                "effective_high_quality_frames": sum(row["relbow_effective_status"] == "valid" for row in rows),
                "low_quality_or_unstable_frames": [row["frame_index"] for row in rows if row["relbow_effective_status"] == "low_quality"],
                "coordinate_missing_frames": relbow_missing,
                "coordinate_missing_intervals": intervals(relbow_missing),
            },
            "rwrist": {
                "coordinate_available_frames": sum(row["rwrist_coordinate_available"] for row in rows),
                "source_joint_valid_frames": sum(row["rwrist_joint_valid"] for row in rows),
                "coordinate_missing_frames": rwrist_missing,
                "coordinate_missing_intervals": intervals(rwrist_missing),
                "forced_joint_missing_frames_excluding_frame_invalid": [64, 65, 143, 182, 183, 184, 185],
            },
        },
        "missing_frames": [0, 1],
        "missing_joints": {"RWrist": [64, 65, 143, 182, 183, 184, 185]},
        "shoulder_width_stats": {
            "valid_frame_count": len(shoulder_values),
            "mean_px": shoulder_mean, "std_px": float(shoulder_values.std()),
            "min_px": float(shoulder_values.min()), "max_px": float(shoulder_values.max()),
            "sudden_change_rule": "absolute consecutive change > 30% of global mean shoulder width",
            "sudden_change_threshold_px": shoulder_mean * 0.30,
            "anomaly_frames": shoulder_anomalies,
        },
        "absolute_motion": {
            "first_valid_anchor_frame": 2,
            "consecutive_displacement_vector_components_preserved": True,
            "neck_offset_from_first_valid": {
                "dx": scalar_field_statistics(rows, "neck_dx_from_first_valid_px"),
                "dy": scalar_field_statistics(rows, "neck_dy_from_first_valid_px"),
            },
            "consecutive_frame_displacement": {
                "Neck": scalar_field_statistics(rows, "neck_frame_displacement_px"),
                "RShoulder": scalar_field_statistics(rows, "rshoulder_frame_displacement_px"),
                "LShoulder": scalar_field_statistics(rows, "lshoulder_frame_displacement_px"),
            },
            "interpretation": "observed absolute pixel motion is retained and is not automatically classified as error",
        },
        "normalized_trajectory_range": {
            "RElbow": coordinate_range(rows, "relbow"),
            "RWrist": coordinate_range(rows, "rwrist"),
        },
        "per_frame_displacement": {
            "RElbow": displacement_statistics(rows, "relbow"),
            "RWrist": displacement_statistics(rows, "rwrist"),
        },
        "suspicious_jump_frames": sorted({
            item["to_frame"]
            for prefix in ("relbow", "rwrist")
            for item in displacement_statistics(rows, prefix)["suspicious_jumps"]
        }),
        "reach_to_retract": {
            "frame_range": operation_range,
            "included_phase_labels": sorted(OPERATION_PHASES),
            "RElbow": path_length(rows, "relbow", operation_frames),
            "RWrist": path_length(rows, "rwrist", operation_frames),
        },
        "future_simulation_mapping_policy": {
            "neck_relative_trajectory_alone_is_sufficient": False,
            "preserve_absolute_pixel_trajectory": True,
            "preserve_tabletop_path_and_A_B_references": True,
            "A_B_reference_coordinates_available_in_T07A": False,
            "note": "T07A does not detect the box or estimate A/B coordinates; those references remain required future inputs.",
        },
        "per_phase_statistics": per_phase,
        "input_hashes": {
            str(args.trajectory_jsonl): sha256_file(args.trajectory_jsonl),
            str(args.p001): sha256_file(args.p001),
            str(args.quality_mask): sha256_file(args.quality_mask),
            str(args.phase_frames): sha256_file(args.phase_frames),
            str(args.t06c_validation): sha256_file(args.t06c_validation),
        },
        "outputs": {"summary": str(args.output_summary), "plot": str(args.output_plot)},
        "annotation_version": "t07a_raw_v0.2.0",
    }
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_plot(rows, args.output_plot)
    print(json.dumps({
        "trajectory_valid_frames": summary["validity"]["trajectory_valid_frames"],
        "relbow": summary["validity"]["relbow"],
        "rwrist": summary["validity"]["rwrist"],
        "shoulder_width_stats": summary["shoulder_width_stats"],
        "suspicious_jump_frames": summary["suspicious_jump_frames"],
        "reach_to_retract": summary["reach_to_retract"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
