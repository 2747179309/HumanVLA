#!/usr/bin/env python3
"""Independently validate T07C-B2 ground truth, formulas, counts, and split isolation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


JOINT_PREFIX = {"Neck": "neck", "RShoulder": "rshoulder", "RElbow": "relbow", "RWrist": "rwrist"}
SPLITS = ("train", "val", "test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the paired T07C-B2 synthetic corruption dataset.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--corruption-mask", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
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


def raw_xy(row: dict[str, Any], joint: str) -> list[float]:
    prefix = JOINT_PREFIX[joint]
    return [float(row[f"{prefix}_x_px"]), float(row[f"{prefix}_y_px"])]


def close_points(first: list[float], second: list[float], tolerance: float = 1e-9) -> bool:
    return bool(np.allclose(np.asarray(first), np.asarray(second), atol=tolerance, rtol=0.0))


def main() -> int:
    args = parse_args()
    for path in vars(args).values():
        if not path.is_file():
            raise FileNotFoundError(path)
    errors: list[str] = []
    config = json.loads(args.config.read_text(encoding="utf-8"))
    raw_rows, mask_rows, samples = (
        load_jsonl(args.raw_trajectory), load_jsonl(args.corruption_mask), load_jsonl(args.dataset)
    )
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    mask_by_key = {(row["frame_index"], row["joint_name"]): row for row in mask_rows}
    expected = config["expected_dataset"]
    if len(samples) != int(expected["total_sample_count"]):
        errors.append(f"sample count {len(samples)} != {expected['total_sample_count']}")
    if len({row["sample_id"] for row in samples}) != len(samples):
        errors.append("sample IDs are not unique")
    if len({row["sample_seed"] for row in samples}) != len(samples):
        errors.append("sample seeds are not unique")
    expected_distributions = {
        "split": expected["samples_by_split"],
        "corruption_type": {name: expected["samples_per_corruption_type"] for name in config["corruptions"]},
        "intensity_id": {name: expected["samples_per_intensity"] for name in ("low", "medium", "high")},
    }
    for field, wanted in expected_distributions.items():
        actual = dict(Counter(row[field] for row in samples))
        if actual != {key: int(value) for key, value in wanted.items()}:
            errors.append(f"{field} distribution mismatch: {actual}")

    frames_by_split: dict[str, set[int]] = defaultdict(set)
    windows: dict[str, tuple[str, tuple[int, ...]]] = {}
    variants_by_window: Counter[str] = Counter()
    for sample in samples:
        frames = [int(frame) for frame in sample["source_frame_indices"]]
        joint = sample["target_joint"]
        if len(frames) != int(config["clean_selection"]["window_length_frames"]):
            errors.append(f"{sample['sample_id']}: source window length mismatch")
            continue
        if frames != list(range(frames[0], frames[-1] + 1)):
            errors.append(f"{sample['sample_id']}: source frames are not contiguous")
        split_range = config["split_policy"]["ranges"][sample["split"]]
        if frames[0] < split_range[0] or frames[-1] > split_range[1]:
            errors.append(f"{sample['sample_id']}: source frames outside split range")
        frames_by_split[sample["split"]].update(frames)
        identity = (sample["split"], tuple(frames))
        previous = windows.setdefault(sample["source_window_id"], identity)
        if previous != identity:
            errors.append(f"{sample['source_window_id']}: inconsistent window identity")
        variants_by_window[sample["source_window_id"]] += 1
        phases = {raw_rows[frame]["phase_label"] for frame in frames}
        if phases != {sample["phase_label"]}:
            errors.append(f"{sample['sample_id']}: phase crossing")

        clean = sample["clean_trajectory_px"]
        for offset, frame in enumerate(frames):
            if not close_points(clean[offset], raw_xy(raw_rows[frame], joint)):
                errors.append(f"{sample['sample_id']}: clean truth differs from raw at frame {frame}")
                break
            for reference_joint in config["reference_joints"]:
                mask = mask_by_key[(frame, reference_joint)]
                if not (
                    mask["raw_observation_valid"]
                    and mask["selected_downstream_source"] == "raw"
                    and not mask["repaired_observation_available"]
                    and mask["corruption_type"] == "valid"
                    and not mask["source_event_ids"]
                ):
                    errors.append(f"{sample['sample_id']}: non-clean frame {frame}/{reference_joint} used")
                    break
            neck = sample["neck_origin_px"][offset]
            scale = float(sample["shoulder_width_px"][offset])
            expected_norm = [(clean[offset][0] - neck[0]) / scale, (clean[offset][1] - neck[1]) / scale]
            if not close_points(expected_norm, sample["clean_trajectory_norm"][offset]):
                errors.append(f"{sample['sample_id']}: clean normalization mismatch")
                break

        corruption = sample["corruption_type"]
        corrupted = sample["corrupted_trajectory_px"]
        mask = [bool(value) for value in sample["corruption_mask"]]
        parameters = sample["configured_parameters"]
        realized = sample["realized_parameters"]
        scale = float(sample["window_scale_px"])
        if len(corrupted) != len(clean) or len(mask) != len(clean):
            errors.append(f"{sample['sample_id']}: corrupted array length mismatch")
            continue
        if corruption == "gaussian_noise":
            if not all(mask):
                errors.append(f"{sample['sample_id']}: Gaussian mask is incomplete")
            offsets = realized["offsets_px"]
            for index in range(len(clean)):
                expected_point = np.asarray(clean[index]) + np.asarray(offsets[index])
                if corrupted[index] is None or not close_points(expected_point.tolist(), corrupted[index]):
                    errors.append(f"{sample['sample_id']}: Gaussian formula mismatch")
                    break
            expected_sigma = float(parameters["sigma_shoulder_width"]) * scale
            if not math.isclose(realized["sigma_px"], expected_sigma, abs_tol=1e-12):
                errors.append(f"{sample['sample_id']}: Gaussian scale mismatch")
        elif corruption == "burst_jump":
            start, end = int(realized["start_offset"]), int(realized["end_offset"])
            expected_offset = np.asarray(realized["offset_px"])
            if sum(mask) != int(parameters["duration_frames"]):
                errors.append(f"{sample['sample_id']}: burst duration mismatch")
            for index in range(len(clean)):
                delta = np.asarray(corrupted[index]) - np.asarray(clean[index])
                expected_delta = expected_offset if start <= index <= end else np.zeros(2)
                if not np.allclose(delta, expected_delta, atol=1e-9, rtol=0):
                    errors.append(f"{sample['sample_id']}: burst formula mismatch")
                    break
        elif corruption == "continuous_drift":
            start, end = int(realized["start_offset"]), int(realized["end_offset"])
            offsets = realized["offsets_px"]
            if sum(mask) != int(parameters["duration_frames"]):
                errors.append(f"{sample['sample_id']}: drift duration mismatch")
            for index in range(len(clean)):
                delta = np.asarray(corrupted[index]) - np.asarray(clean[index])
                expected_delta = np.asarray(offsets[index - start]) if start <= index <= end else np.zeros(2)
                if not np.allclose(delta, expected_delta, atol=1e-9, rtol=0):
                    errors.append(f"{sample['sample_id']}: drift formula mismatch")
                    break
        elif corruption == "short_missing":
            start, end = int(realized["start_offset"]), int(realized["end_offset"])
            if sum(mask) != int(parameters["gap_length_frames"]):
                errors.append(f"{sample['sample_id']}: missing duration mismatch")
            for index in range(len(clean)):
                if (corrupted[index] is None) is not (start <= index <= end):
                    errors.append(f"{sample['sample_id']}: missing formula mismatch")
                    break
        else:
            errors.append(f"{sample['sample_id']}: unknown corruption {corruption}")
        if sample.get("filtering_performed") is not False or sample.get("recovery_performed") is not False:
            errors.append(f"{sample['sample_id']}: filtering/recovery was marked as performed")

    for first_index, first in enumerate(SPLITS):
        for second in SPLITS[first_index + 1:]:
            if frames_by_split[first] & frames_by_split[second]:
                errors.append(f"source frame leakage between {first} and {second}")
    if any(count != int(expected["samples_per_base_window"]) for count in variants_by_window.values()):
        errors.append("a source window does not have exactly 24 preregistered variants")
    if len(variants_by_window) != int(expected["base_window_count"]):
        errors.append("base window count mismatch")
    for path in (args.config, args.raw_trajectory, args.corruption_mask):
        if metadata.get("input_hashes", {}).get(str(path)) != sha256_file(path):
            errors.append(f"metadata input hash mismatch: {path}")
    leakage = metadata.get("leakage_checks", {})
    if leakage.get("source_frame_overlap_between_splits") is not False:
        errors.append("metadata reports split leakage")
    if not all(leakage.get(key) is False for key in (
        "real_corruption_frame_used_as_ground_truth", "accepted_repair_used_as_ground_truth",
        "cross_phase_window_used", "filter_or_recovery_run",
    )):
        errors.append("metadata leakage/processing declarations are invalid")
    result = {
        "validation_passed": not errors,
        "errors": errors,
        "sample_count": len(samples),
        "base_window_count": len(variants_by_window),
        "samples_by_split": dict(Counter(row["split"] for row in samples)),
        "samples_by_corruption": dict(Counter(row["corruption_type"] for row in samples)),
        "samples_by_intensity": dict(Counter(row["intensity_id"] for row in samples)),
        "split_source_frame_counts": {split: len(frames_by_split[split]) for split in SPLITS},
        "split_source_frame_overlap": False if not errors else any(
            frames_by_split[a] & frames_by_split[b] for i, a in enumerate(SPLITS) for b in SPLITS[i + 1:]
        ),
        "input_hashes": {str(path): sha256_file(path) for path in (args.config, args.raw_trajectory, args.corruption_mask)},
        "output_hashes": {str(path): sha256_file(path) for path in (args.dataset, args.metadata)},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
