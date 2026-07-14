#!/usr/bin/env python3
"""Build the preregistered T07C-B2 paired clean/corrupted trajectory dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


JOINT_PREFIX = {"Neck": "neck", "RShoulder": "rshoulder", "RElbow": "relbow", "RWrist": "rwrist"}
SPLIT_ORDER = ("train", "val", "test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate T07C-B2 synthetic corruptions from strictly clean E001 raw windows.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--corruption-mask", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-metadata", required=True, type=Path)
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


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def derived_seed(global_seed: int, *parts: str) -> int:
    """Return a stable uint64 seed independent of Python hash randomization."""
    payload = "|".join((str(global_seed), *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def corrupt_gaussian_noise(
    clean_px: np.ndarray, scale_px: float, rng: np.random.Generator, parameters: dict[str, Any]
) -> tuple[list[list[float]], list[bool], dict[str, Any]]:
    """Add independent isotropic Gaussian noise.

    Input is an Lx2 clean pixel trajectory and shoulder-width scale ``s``.
    Output is ``z_t = x_t + eps_t``, where
    ``eps_t ~ Normal(0, (sigma * s)^2 I_2)`` for every frame.
    """
    sigma_px = float(parameters["sigma_shoulder_width"]) * scale_px
    offsets = rng.normal(0.0, sigma_px, size=clean_px.shape)
    corrupted = clean_px + offsets
    return corrupted.tolist(), [True] * len(clean_px), {
        "sigma_px": sigma_px,
        "offsets_px": offsets.tolist(),
    }


def random_unit_vector(rng: np.random.Generator) -> np.ndarray:
    angle = float(rng.uniform(0.0, 2.0 * np.pi))
    return np.array([np.cos(angle), np.sin(angle)], dtype=float)


def interior_start(length: int, duration: int, rng: np.random.Generator) -> int:
    """Choose a contiguous interval with at least one clean frame on each side."""
    if duration > length - 2:
        raise ValueError(f"duration {duration} leaves no two-sided context in length {length}")
    return int(rng.integers(1, length - duration))


def corrupt_burst_jump(
    clean_px: np.ndarray, scale_px: float, rng: np.random.Generator, parameters: dict[str, Any]
) -> tuple[list[list[float]], list[bool], dict[str, Any]]:
    """Apply a constant vector offset to a short contiguous burst.

    For a seeded unit direction ``u`` and interval B, the output is
    ``z_t = x_t + magnitude * s * u`` when ``t in B`` and ``z_t = x_t`` otherwise.
    This models a keypoint snapping briefly to the wrong image location.
    """
    duration = int(parameters["duration_frames"])
    start = interior_start(len(clean_px), duration, rng)
    direction = random_unit_vector(rng)
    magnitude_px = float(parameters["magnitude_shoulder_width"]) * scale_px
    offset = magnitude_px * direction
    corrupted = clean_px.copy()
    corrupted[start:start + duration] += offset
    mask = [start <= index < start + duration for index in range(len(clean_px))]
    return corrupted.tolist(), mask, {
        "start_offset": start,
        "end_offset": start + duration - 1,
        "direction_unit": direction.tolist(),
        "magnitude_px": magnitude_px,
        "offset_px": offset.tolist(),
    }


def corrupt_continuous_drift(
    clean_px: np.ndarray, scale_px: float, rng: np.random.Generator, parameters: dict[str, Any]
) -> tuple[list[list[float]], list[bool], dict[str, Any]]:
    """Add a linearly increasing directional bias over an interior interval.

    For interval length L, ``alpha_k=(k+1)/L`` and
    ``z_t = x_t + alpha_k * magnitude * s * u``. The first and last window
    frames remain clean context. This models gradual pose drift under occlusion.
    """
    duration = int(parameters["duration_frames"])
    start = (len(clean_px) - duration) // 2
    if start < 1 or start + duration >= len(clean_px):
        raise ValueError("continuous drift must retain clean context on both sides")
    direction = random_unit_vector(rng)
    magnitude_px = float(parameters["magnitude_shoulder_width"]) * scale_px
    alphas = np.arange(1, duration + 1, dtype=float) / duration
    offsets = alphas[:, None] * magnitude_px * direction[None, :]
    corrupted = clean_px.copy()
    corrupted[start:start + duration] += offsets
    mask = [start <= index < start + duration for index in range(len(clean_px))]
    return corrupted.tolist(), mask, {
        "start_offset": start,
        "end_offset": start + duration - 1,
        "direction_unit": direction.tolist(),
        "maximum_magnitude_px": magnitude_px,
        "alphas": alphas.tolist(),
        "offsets_px": offsets.tolist(),
    }


def corrupt_short_missing(
    clean_px: np.ndarray, scale_px: float, rng: np.random.Generator, parameters: dict[str, Any]
) -> tuple[list[list[float] | None], list[bool], dict[str, Any]]:
    """Replace a short interior interval with missing observations.

    The mathematical observation model is ``z_t = null`` for ``t in M`` and
    ``z_t = x_t`` otherwise. ``scale_px`` is accepted for a uniform interface
    but is not used by this corruption.
    """
    del scale_px
    duration = int(parameters["gap_length_frames"])
    start = interior_start(len(clean_px), duration, rng)
    corrupted: list[list[float] | None] = clean_px.tolist()
    for index in range(start, start + duration):
        corrupted[index] = None
    mask = [start <= index < start + duration for index in range(len(clean_px))]
    return corrupted, mask, {
        "start_offset": start,
        "end_offset": start + duration - 1,
    }


CORRUPTION_FUNCTIONS = {
    "gaussian_noise": corrupt_gaussian_noise,
    "burst_jump": corrupt_burst_jump,
    "continuous_drift": corrupt_continuous_drift,
    "short_missing": corrupt_short_missing,
}


def strict_clean_frame(mask_by_key: dict[tuple[int, str], dict[str, Any]], frame: int, joints: list[str]) -> bool:
    """Accept only untouched raw observations as synthetic ground truth."""
    for joint in joints:
        row = mask_by_key[(frame, joint)]
        if not (
            row["raw_observation_valid"]
            and row["selected_downstream_source"] == "raw"
            and not row["repaired_observation_available"]
            and row["corruption_type"] == "valid"
            and not row["source_event_ids"]
        ):
            return False
    return True


def candidate_windows(
    split: str,
    start: int,
    end: int,
    raw_rows: list[dict[str, Any]],
    mask_by_key: dict[tuple[int, str], dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    length = int(config["clean_selection"]["window_length_frames"])
    guard = int(config["clean_selection"]["guard_frames_between_windows"])
    joints = config["reference_joints"]
    windows: list[dict[str, Any]] = []
    frame = start
    while frame <= end:
        if not strict_clean_frame(mask_by_key, frame, joints):
            frame += 1
            continue
        phase = raw_rows[frame]["phase_label"]
        run_end = frame
        while (
            run_end + 1 <= end
            and raw_rows[run_end + 1]["phase_label"] == phase
            and strict_clean_frame(mask_by_key, run_end + 1, joints)
        ):
            run_end += 1
        window_start = frame
        while window_start + length - 1 <= run_end:
            frames = list(range(window_start, window_start + length))
            windows.append({"split": split, "phase_label": phase, "frame_indices": frames})
            window_start += length + guard
        frame = run_end + 1
    return windows


def phase_stratified_select(
    candidates: list[dict[str, Any]], count: int, global_seed: int, split: str
) -> list[dict[str, Any]]:
    """Select one window per available phase, then fill remaining slots reproducibly."""
    if len(candidates) < count:
        raise ValueError(f"split {split} has only {len(candidates)} candidates for requested {count}")
    rng = np.random.default_rng(derived_seed(global_seed, "base_window_selection", split))
    by_phase: dict[str, list[int]] = defaultdict(list)
    for index, window in enumerate(candidates):
        by_phase[window["phase_label"]].append(index)
    selected: list[int] = []
    phases = sorted(by_phase)
    if count < len(phases):
        raise ValueError(f"split {split} cannot represent all {len(phases)} phases with {count} windows")
    for phase in phases:
        selected.append(int(rng.choice(by_phase[phase])))
    remaining = [index for index in range(len(candidates)) if index not in selected]
    rng.shuffle(remaining)
    selected.extend(remaining[:count - len(selected)])
    return [candidates[index] for index in sorted(selected, key=lambda i: candidates[i]["frame_indices"][0])]


def joint_xy(row: dict[str, Any], joint: str) -> list[float]:
    prefix = JOINT_PREFIX[joint]
    return [float(row[f"{prefix}_x_px"]), float(row[f"{prefix}_y_px"])]


def normalize_points(
    points: list[list[float] | None], neck: list[list[float]], shoulder_width: list[float]
) -> list[list[float] | None]:
    result: list[list[float] | None] = []
    for point, origin, scale in zip(points, neck, shoulder_width):
        result.append(None if point is None else [(point[0] - origin[0]) / scale, (point[1] - origin[1]) / scale])
    return result


def main() -> int:
    args = parse_args()
    inputs = (args.config, args.raw_trajectory, args.corruption_mask)
    outputs = (args.output_jsonl, args.output_metadata)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))
    input_hashes = {str(path): sha256_file(path) for path in inputs}
    config = json.loads(args.config.read_text(encoding="utf-8"))
    raw_rows, mask_rows = load_jsonl(args.raw_trajectory), load_jsonl(args.corruption_mask)
    if len(raw_rows) != 345 or len(mask_rows) != 1380:
        raise ValueError("expected 345 raw rows and 1380 corruption-mask rows")
    mask_by_key = {(row["frame_index"], row["joint_name"]): row for row in mask_rows}
    seed = int(config["random_seed"])

    selected_windows: list[dict[str, Any]] = []
    candidate_counts: dict[str, int] = {}
    for split in SPLIT_ORDER:
        start, end = config["split_policy"]["ranges"][split]
        candidates = candidate_windows(split, int(start), int(end), raw_rows, mask_by_key, config)
        candidate_counts[split] = len(candidates)
        count = int(config["split_policy"]["selected_base_windows"][split])
        selected_windows.extend(phase_stratified_select(candidates, count, seed, split))
    for index, window in enumerate(selected_windows, start=1):
        window["source_window_id"] = f"CLEAN_{window['split'].upper()}_{index:03d}"

    samples: list[dict[str, Any]] = []
    sample_index = 0
    for window in selected_windows:
        frames = window["frame_indices"]
        neck = [joint_xy(raw_rows[frame], "Neck") for frame in frames]
        shoulder_width = [float(raw_rows[frame]["shoulder_width_px"]) for frame in frames]
        scale_px = float(np.median(shoulder_width))
        context = {
            joint: [joint_xy(raw_rows[frame], joint) for frame in frames]
            for joint in config["reference_joints"]
        }
        for joint in config["target_joints"]:
            clean_px = np.asarray(context[joint], dtype=float)
            clean_norm = normalize_points(clean_px.tolist(), neck, shoulder_width)
            for corruption_type, specification in config["corruptions"].items():
                function = CORRUPTION_FUNCTIONS[corruption_type]
                for level in specification["levels"]:
                    sample_index += 1
                    sample_seed = derived_seed(
                        seed, window["source_window_id"], joint, corruption_type, level["intensity_id"]
                    )
                    rng = np.random.default_rng(sample_seed)
                    parameters = dict(level)
                    if corruption_type == "continuous_drift":
                        parameters["duration_frames"] = int(specification["duration_frames"])
                    corrupted_px, corruption_mask, realized = function(clean_px, scale_px, rng, parameters)
                    samples.append({
                        "sample_id": f"SYN_{sample_index:04d}",
                        "dataset_version": config["config_version"],
                        "video_id": config["video_id"],
                        "split": window["split"],
                        "source_window_id": window["source_window_id"],
                        "source_frame_indices": frames,
                        "phase_label": window["phase_label"],
                        "target_joint": joint,
                        "corruption_type": corruption_type,
                        "intensity_id": level["intensity_id"],
                        "sample_seed": sample_seed,
                        "configured_parameters": parameters,
                        "realized_parameters": realized,
                        "clean_ground_truth_source": "T07A_raw_strict_clean",
                        "clean_trajectory_px": clean_px.tolist(),
                        "corrupted_trajectory_px": corrupted_px,
                        "clean_trajectory_norm": clean_norm,
                        "corrupted_trajectory_norm": normalize_points(corrupted_px, neck, shoulder_width),
                        "corruption_mask": corruption_mask,
                        "observation_available": [point is not None for point in corrupted_px],
                        "neck_origin_px": neck,
                        "shoulder_width_px": shoulder_width,
                        "window_scale_px": scale_px,
                        "clean_reference_trajectories_px": context,
                        "filtering_performed": False,
                        "recovery_performed": False,
                    })

    expected = config["expected_dataset"]
    if len(samples) != int(expected["total_sample_count"]):
        raise RuntimeError(f"generated {len(samples)} samples, expected {expected['total_sample_count']}")
    atomic_write(args.output_jsonl, "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in samples))
    hashes_after = {str(path): sha256_file(path) for path in inputs}
    if hashes_after != input_hashes:
        raise RuntimeError("a read-only input changed during generation")
    split_frame_sets = {
        split: sorted({frame for window in selected_windows if window["split"] == split for frame in window["frame_indices"]})
        for split in SPLIT_ORDER
    }
    leakage = any(set(split_frame_sets[a]) & set(split_frame_sets[b]) for i, a in enumerate(SPLIT_ORDER) for b in SPLIT_ORDER[i + 1:])
    corruption_statistics: dict[str, dict[str, Any]] = {}
    for corruption_type in config["corruptions"]:
        for intensity in ("low", "medium", "high"):
            subset = [
                row for row in samples
                if row["corruption_type"] == corruption_type and row["intensity_id"] == intensity
            ]
            displacements = []
            missing_count = 0
            affected_count = 0
            for row in subset:
                for clean_point, corrupted_point, affected in zip(
                    row["clean_trajectory_px"], row["corrupted_trajectory_px"], row["corruption_mask"]
                ):
                    if not affected:
                        continue
                    affected_count += 1
                    if corrupted_point is None:
                        missing_count += 1
                    else:
                        displacements.append(float(np.linalg.norm(np.asarray(corrupted_point) - np.asarray(clean_point))))
            corruption_statistics[f"{corruption_type}/{intensity}"] = {
                "sample_count": len(subset),
                "affected_frame_count": affected_count,
                "missing_observation_count": missing_count,
                "mean_displacement_px": float(np.mean(displacements)) if displacements else None,
                "max_displacement_px": float(np.max(displacements)) if displacements else None,
            }
    metadata = {
        "run_id": "20260714_T07C_B2_SYNTHETIC_CORRUPTION_001",
        "dataset_version": config["config_version"],
        "status": "complete_pending_quality_review",
        "config_preregistered_before_generation": True,
        "random_seed": seed,
        "total_sample_count": len(samples),
        "base_window_count": len(selected_windows),
        "candidate_window_counts": candidate_counts,
        "selected_base_windows": selected_windows,
        "sample_counts_by_split": dict(Counter(row["split"] for row in samples)),
        "sample_counts_by_joint": dict(Counter(row["target_joint"] for row in samples)),
        "sample_counts_by_corruption": dict(Counter(row["corruption_type"] for row in samples)),
        "sample_counts_by_intensity": dict(Counter(row["intensity_id"] for row in samples)),
        "sample_counts_by_phase": dict(Counter(row["phase_label"] for row in samples)),
        "corruption_statistics": corruption_statistics,
        "split_source_frames": split_frame_sets,
        "leakage_checks": {
            "source_frame_overlap_between_splits": leakage,
            "real_corruption_frame_used_as_ground_truth": False,
            "accepted_repair_used_as_ground_truth": False,
            "cross_phase_window_used": False,
            "filter_or_recovery_run": False,
        },
        "input_hashes": input_hashes,
        "outputs": {"dataset_jsonl": str(args.output_jsonl)},
    }
    atomic_write(args.output_metadata, json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "total_sample_count": len(samples),
        "base_window_count": len(selected_windows),
        "sample_counts_by_split": metadata["sample_counts_by_split"],
        "sample_counts_by_corruption": metadata["sample_counts_by_corruption"],
        "sample_counts_by_intensity": metadata["sample_counts_by_intensity"],
        "source_frame_overlap_between_splits": leakage,
        "input_hashes_unchanged": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
