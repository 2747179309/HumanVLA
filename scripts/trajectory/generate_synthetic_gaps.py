#!/usr/bin/env python3
"""Generate the deterministic T07B synthetic short-gap manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from gap_recovery_common import joint_reliable, load_csv, load_jsonl, manual_excluded_frames, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build leakage-controlled E001 synthetic gaps before any real-gap repair.")
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.trajectory, args.review_csv, args.policy):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    rows = load_jsonl(args.trajectory)
    review = load_csv(args.review_csv)
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if not policy.get("frozen_before_benchmark"):
        raise ValueError("selection policy is not frozen")
    selection = policy["synthetic_selection"]
    real_missing = set(selection["exclude_real_missing_frames"])
    excluded = manual_excluded_frames(review, set(selection["exclude_manual_labels"])) | real_missing | {0, 1}
    context_radius = int(selection["context_frames_each_side"])
    manifest: list[dict[str, object]] = []
    gap_id = 1
    for joint in ("RElbow", "RWrist"):
        for length_text, phases in selection["required_phases_by_gap_length"].items():
            length = int(length_text)
            for phase in phases:
                candidates: list[tuple[float, int, int, list[int]]] = []
                phase_frames = [row["frame_index"] for row in rows if row["phase_label"] == phase]
                phase_center = (min(phase_frames) + max(phase_frames)) / 2.0
                for start in phase_frames:
                    end = start + length - 1
                    context = [start - 2, start - 1, end + 1, end + 2]
                    window = list(range(start - context_radius, end + context_radius + 1))
                    if min(window) < 0 or max(window) >= len(rows):
                        continue
                    if any(rows[frame]["phase_label"] != phase for frame in window):
                        continue
                    if any(frame in excluded for frame in window):
                        continue
                    if any(not joint_reliable(rows[frame], joint) for frame in window):
                        continue
                    center = (start + end) / 2.0
                    candidates.append((abs(center - phase_center), start, end, context))
                if not candidates:
                    raise RuntimeError(f"insufficient valid synthetic samples: joint={joint} length={length} phase={phase}")
                _, start, end, context = min(candidates)
                gap_frames = list(range(start, end + 1))
                reused = any(
                    row["joint"] == joint and set(gap_frames) & set(json.loads(str(row["gap_frames"])))
                    for row in manifest
                )
                phase_row = rows[start]
                manifest.append({
                    "gap_id": f"SYN_{gap_id:03d}", "joint": joint,
                    "gap_start": start, "gap_end": end, "gap_length": length,
                    "gap_frames": json.dumps(gap_frames, separators=(",", ":")),
                    "context_frames": json.dumps(context, separators=(",", ":")),
                    "phase_id": phase_row["phase_id"], "phase_label": phase,
                    "selection_status": "selected",
                    "note": "target_coverage_met;masked_frame_reuse=" + str(reused).lower(),
                    "ground_truth_source": "human_confirmed_high_quality_raw_observation",
                })
                gap_id += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(manifest[0])
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest)
    print(json.dumps({
        "sample_count": len(manifest),
        "counts_by_length": {
            str(length): sum(row["gap_length"] == length for row in manifest) for length in (1, 2, 3, 4)
        },
        "counts_by_joint": {joint: sum(row["joint"] == joint for row in manifest) for joint in ("RElbow", "RWrist")},
        "phase_coverage": sorted({str(row["phase_label"]) for row in manifest}),
        "insufficient_phase_samples": [], "policy_sha256": sha256_file(args.policy),
        "trajectory_sha256": sha256_file(args.trajectory), "review_csv_sha256": sha256_file(args.review_csv),
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
