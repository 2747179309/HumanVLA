#!/usr/bin/env python3
"""Repair only the declared real RWrist gaps using the E001 provisional best method."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from gap_recovery_common import (
    joint_reliable, load_csv, load_jsonl, manual_excluded_frames, norm_to_pixel,
    recover_normalized, sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a derived 345-frame trajectory with only declared RWrist gaps repaired.")
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--benchmark-json", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--output-corruption-list", required=True, type=Path)
    parser.add_argument("--output-overlay", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def csv_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def select_context(
    rows: list[dict[str, Any]], start: int, end: int, excluded: set[int],
) -> list[int]:
    phase = rows[start]["phase_label"]
    before = [
        frame for frame in range(start - 1, -1, -1)
        if rows[frame]["phase_label"] == phase and frame not in excluded and joint_reliable(rows[frame], "RWrist")
    ][:2]
    after = [
        frame for frame in range(end + 1, len(rows))
        if rows[frame]["phase_label"] == phase and frame not in excluded and joint_reliable(rows[frame], "RWrist")
    ][:2]
    if len(before) < 2 or len(after) < 2:
        raise RuntimeError(f"not enough reliable same-phase context for {start}-{end}")
    return [before[1], before[0], after[0], after[1]]


def boundary_metrics(
    rows: list[dict[str, Any]], gap_frames: list[int], context: list[int],
    predictions: dict[int, Any], fps: float,
) -> dict[str, Any]:
    b2, b1, a1, a2 = context
    sequence = [b1, *gap_frames, a1]
    norm_points = []
    px_points = []
    for frame in sequence:
        norm = predictions[frame] if frame in predictions else np.array([
            rows[frame]["rwrist_x_norm"], rows[frame]["rwrist_y_norm"]
        ], dtype=float)
        norm_points.append(norm)
        px_points.append(norm_to_pixel(rows[frame], norm))
    norm_points = np.stack(norm_points)
    px_points = np.stack(px_points)
    norm_steps = np.linalg.norm(np.diff(norm_points, axis=0), axis=1)
    px_steps = np.linalg.norm(np.diff(px_points, axis=0), axis=1)
    previous_norm_velocity = np.array([
        rows[b1]["rwrist_x_norm"] - rows[b2]["rwrist_x_norm"],
        rows[b1]["rwrist_y_norm"] - rows[b2]["rwrist_y_norm"],
    ]) * fps
    entry_norm_velocity = (norm_points[1] - norm_points[0]) * fps
    exit_norm_velocity = (norm_points[-1] - norm_points[-2]) * fps
    next_norm_velocity = np.array([
        rows[a2]["rwrist_x_norm"] - rows[a1]["rwrist_x_norm"],
        rows[a2]["rwrist_y_norm"] - rows[a1]["rwrist_y_norm"],
    ]) * fps
    return {
        "max_single_frame_displacement_norm": float(norm_steps.max()),
        "max_single_frame_displacement_px": float(px_steps.max()),
        "entry_velocity_discontinuity_norm_per_s": float(np.linalg.norm(entry_norm_velocity - previous_norm_velocity)),
        "exit_velocity_discontinuity_norm_per_s": float(np.linalg.norm(next_norm_velocity - exit_norm_velocity)),
        "single_frame_displacements_norm": norm_steps.tolist(),
        "boundary_abnormal_over_half_shoulder_width": bool((norm_steps > 0.5).any()),
    }


def render_overlay(video: Path, rows: list[dict[str, Any]], output: Path) -> None:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame_index, row in enumerate(rows):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"video decode failed at frame {frame_index}")
            points = {
                "Neck": (row["neck_x_px"], row["neck_y_px"]),
                "RShoulder": (row["rshoulder_x_px"], row["rshoulder_y_px"]),
                "LShoulder": (row["lshoulder_x_px"], row["lshoulder_y_px"]),
                "RElbow": (row["relbow_x_px"], row["relbow_y_px"]),
                "RWrist": (row["rwrist_x_repaired_px"], row["rwrist_y_repaired_px"]),
            }
            converted = {name: None if value[0] is None else (round(value[0]), round(value[1])) for name, value in points.items()}
            for first, second in (("Neck", "RShoulder"), ("Neck", "LShoulder"), ("RShoulder", "RElbow"), ("RElbow", "RWrist")):
                if converted[first] and converted[second]:
                    cv2.line(frame, converted[first], converted[second], (255, 120, 30) if row["repair_mask"] else (40, 210, 50), 4, cv2.LINE_AA)
            for location in converted.values():
                if location:
                    cv2.circle(frame, location, 6, (255, 120, 30) if row["repair_mask"] else (40, 210, 50), -1, cv2.LINE_AA)
            cv2.rectangle(frame, (12, 12), (850, 126), (20, 25, 30), -1)
            cv2.putText(frame, f"frame={frame_index} phase={row['phase_label']} T07B derived trajectory", (28, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (245, 245, 245), 2, cv2.LINE_AA)
            status = f"REPAIRED {row['repair_method']} {row['repair_gap_id']}" if row["repair_mask"] else "raw observation / unrepaired"
            cv2.putText(frame, status, (28, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 160, 50) if row["repair_mask"] else (80, 230, 100), 2, cv2.LINE_AA)
            cv2.putText(frame, "Blue-orange = repaired RWrist; observed frames are not smoothed", (28, 111), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
            process.stdin.write(frame.tobytes())
    finally:
        capture.release()
        process.stdin.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait():
        raise RuntimeError(f"ffmpeg failed: {stderr}")


def main() -> int:
    args = parse_args()
    inputs = (args.trajectory, args.quality_mask, args.review_csv, args.benchmark_json, args.policy, args.video)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = (args.output_jsonl, args.output_csv, args.output_summary, args.output_corruption_list, args.output_overlay)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))
    input_hashes = {str(path): sha256_file(path) for path in inputs}
    rows = load_jsonl(args.trajectory)
    quality = load_jsonl(args.quality_mask)
    review = load_csv(args.review_csv)
    benchmark = json.loads(args.benchmark_json.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if len(rows) != 345 or len(quality) != 345:
        raise ValueError("trajectory/quality mask must contain 345 frames")
    method = benchmark["selection"]["selected_method"]
    if method not in policy["methods"]["ranking_methods"]:
        raise ValueError("selected method is not ranking-eligible")
    actual_gaps = [tuple(value) for value in policy["actual_repair"]["gaps"]]
    actual_frames = {frame for start, end in actual_gaps for frame in range(start, end + 1)}
    if actual_frames != {64, 65, 143, 182, 183, 184, 185}:
        raise ValueError("actual gap policy differs from approved seven frames")
    excluded_context = manual_excluded_frames(review, {"occlusion_error", "normalization_artifact"}) | actual_frames | {0, 1}
    predictions: dict[int, Any] = {}
    gap_details: list[dict[str, Any]] = []
    frame_gap: dict[int, tuple[str, str]] = {}
    for start, end in actual_gaps:
        gap_frames = list(range(start, end + 1))
        context = select_context(rows, start, end, excluded_context)
        recovered = recover_normalized(method, rows, "RWrist", gap_frames, context, policy)
        predictions.update(recovered)
        gap_id = f"GAP_{start:03d}_{end:03d}"
        confidence = policy["actual_repair"]["repair_confidence_by_gap_length"][str(len(gap_frames))]
        for frame in gap_frames:
            frame_gap[frame] = (gap_id, confidence)
        metrics = boundary_metrics(rows, gap_frames, context, recovered, float(policy["fps"]))
        gap_details.append({
            "repair_gap_id": gap_id, "start_frame": start, "end_frame": end,
            "gap_length": len(gap_frames), "phase_label": rows[start]["phase_label"],
            "context_frames": context, "repair_method": method,
            "repair_confidence": confidence, **metrics,
        })
    threshold = float(policy["actual_repair"]["max_allowed_single_frame_displacement_shoulder_width"])
    if any(item["max_single_frame_displacement_norm"] > threshold for item in gap_details):
        raise RuntimeError("real-gap repair exceeds the pre-registered half-shoulder-width boundary")

    corruption = []
    by_frame_candidates: dict[int, list[str]] = {}
    for row in review:
        if row["manual_label"] != "occlusion_error":
            continue
        item = {
            "candidate_id": row["candidate_id"], "from_frame": int(row["from_frame"]),
            "frame_index": int(row["to_frame"]), "to_frame": int(row["to_frame"]),
            "joint": row["joint_name"], "displacement_px": float(row["displacement_px"]),
            "displacement_norm": float(row["displacement_norm"]),
            "manual_label": row["manual_label"], "manual_note": row["manual_note"],
            "status": "deferred_to_T07C", "raw_observation_preserved": True,
            "candidate_joint_repaired_in_T07B": False,
        }
        corruption.append(item)
        for frame in (item["from_frame"], item["to_frame"]):
            by_frame_candidates.setdefault(frame, []).append(item["candidate_id"])
    if len(corruption) != 8:
        raise ValueError(f"expected 8 occlusion_error candidates, got {len(corruption)}")

    repaired: list[dict[str, Any]] = []
    for frame, source in enumerate(rows):
        record = dict(source)
        mask = frame in predictions
        if mask:
            norm = predictions[frame]
            pixel = norm_to_pixel(source, norm)
            gap_id, confidence = frame_gap[frame]
            values = {
                "rwrist_x_repaired_px": float(pixel[0]), "rwrist_y_repaired_px": float(pixel[1]),
                "rwrist_x_repaired_norm": float(norm[0]), "rwrist_y_repaired_norm": float(norm[1]),
                "repair_method": method, "repair_source": "synthetic_benchmark",
                "repair_gap_id": gap_id, "repair_confidence": confidence,
            }
        else:
            values = {
                "rwrist_x_repaired_px": source["rwrist_x_px"], "rwrist_y_repaired_px": source["rwrist_y_px"],
                "rwrist_x_repaired_norm": source["rwrist_x_norm"], "rwrist_y_repaired_norm": source["rwrist_y_norm"],
                "repair_method": None,
                "repair_source": "raw_observation" if source["rwrist_x_px"] is not None else "unrepaired_missing",
                "repair_gap_id": None, "repair_confidence": None,
            }
        record.update({
            **values, "repair_mask": mask,
            "repair_mask_by_joint": {"RElbow": False, "RWrist": mask},
            "original_quality_reason": source["quality_reason"],
            "deferred_corruption_candidate_ids": sorted(by_frame_candidates.get(frame, [])),
            "repair_annotation_version": "t07b_repair_v1.0.0",
        })
        repaired.append(record)
    if any(repaired[frame]["repair_mask"] for frame in (0, 1)):
        raise RuntimeError("frame 0-1 was repaired")

    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as stream:
        for row in repaired:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(repaired[0]))
        writer.writeheader()
        writer.writerows({key: csv_value(value) for key, value in row.items()} for row in repaired)
    args.output_corruption_list.write_text(json.dumps({
        "video_id": policy["video_id"], "candidate_count": len(corruption),
        "handling": "deferred_to_T07C_no_automatic_repair", "candidates": corruption,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "run_id": "20260714_T07B_REAL_GAP_REPAIR_001", "video_id": policy["video_id"],
        "method_label": "provisional best on E001", "selected_method": method,
        "repaired_joint": "RWrist", "repaired_frame_count": len(predictions),
        "repaired_frames": sorted(predictions), "unrepaired_identity_init_frames": [0, 1],
        "gap_details": gap_details, "boundary_threshold_norm": threshold,
        "boundary_abnormal_gap_count": sum(item["boundary_abnormal_over_half_shoulder_width"] for item in gap_details),
        "occlusion_error_candidates_deferred": len(corruption),
        "processing": {"observed_frames_smoothed": False, "raw_fields_overwritten": False, "interpolation_outside_declared_gaps": False},
        "input_hashes": input_hashes,
    }
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_overlay(args.video, repaired, args.output_overlay)
    if {str(path): sha256_file(path) for path in inputs} != input_hashes:
        raise RuntimeError("an input changed during repair")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
