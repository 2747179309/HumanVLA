#!/usr/bin/env python3
"""Run frozen T07C-B3 traditional baselines on the B2 synthetic dataset."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import savgol_filter


METHODS = (
    "corrupted_input",
    "savitzky_golay",
    "one_euro",
    "kalman_cv",
    "confidence_weighted_kalman",
)
CONFIDENCE_INDEX = {"RElbow": 2, "RWrist": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply frozen traditional baselines to all B2 splits. The test split is "
            "processed once and recorded in a separate audit file."
        )
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--selected-parameters", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--test-audit", required=True, type=Path)
    parser.add_argument("--overwrite-nontest-output", action="store_true")
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


def parameter_id(method: str, parameters: dict[str, Any]) -> str:
    payload = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    suffix = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"{method}:{suffix}"


def expand_parameter_grid(config: dict[str, Any], method: str) -> list[dict[str, Any]]:
    """Return the Cartesian product of a preregistered method search space."""
    if method == "corrupted_input":
        return [{}]
    space = config["parameter_search"][method]
    names = list(space)
    return [dict(zip(names, values)) for values in itertools.product(*(space[name] for name in names))]


def optional_points(values: list[list[float] | None]) -> np.ndarray:
    """Convert JSON points to an Lx2 array while preserving missing values as NaN."""
    result = np.full((len(values), 2), np.nan, dtype=float)
    for index, value in enumerate(values):
        if value is not None:
            result[index] = np.asarray(value, dtype=float)
    return result


def points_to_json(points: np.ndarray) -> list[list[float] | None]:
    return [row.tolist() if np.isfinite(row).all() else None for row in points]


def interpolate_observed(points: np.ndarray) -> np.ndarray:
    """Linearly fill missing values using observed input only, never clean truth.

    Interior gaps use two-sided interpolation. An edge gap uses the nearest observed
    value, which is explicit offline boundary handling rather than a zero fill.
    """
    result = points.copy()
    indices = np.arange(len(points))
    for dimension in range(2):
        observed = np.isfinite(points[:, dimension])
        if not observed.any():
            continue
        result[:, dimension] = np.interp(indices, indices[observed], points[observed, dimension])
    return result


def apply_savitzky_golay(points: np.ndarray, parameters: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Offline symmetric local-polynomial smoothing.

    Input: Lx2 corrupted normalized observations, possibly containing NaN.
    Output: Lx2 smoothed positions. Missing input is first linearly interpolated from
    observed input only. For window W and order p, each center estimate is the value
    at zero of the least-squares polynomial fitted over W samples.
    """
    window = int(parameters["window_length"])
    polyorder = int(parameters["polyorder"])
    if window % 2 != 1 or window > len(points) or polyorder >= window:
        raise ValueError(f"invalid Savitzky-Golay parameters W={window}, p={polyorder}")
    filled = interpolate_observed(points)
    if not np.isfinite(filled).all():
        return filled, {"missing_preprocess": "failed_no_observation", "edge_mode": "interp"}
    output = savgol_filter(filled, window_length=window, polyorder=polyorder, axis=0, mode="interp")
    return output, {"missing_preprocess": "observed_only_linear_interpolation", "edge_mode": "interp"}


def smoothing_alpha(cutoff_hz: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff_hz)
    return 1.0 / (1.0 + tau / dt)


def apply_one_euro(points: np.ndarray, parameters: dict[str, Any], fps: float) -> tuple[np.ndarray, dict[str, Any]]:
    """Causal One Euro filtering with explicit predict-by-hold on missing input.

    Input: Lx2 corrupted normalized observations. Output: Lx2 causal estimates.
    The update is xhat_t=a_t*z_t+(1-a_t)*xhat_(t-1), where cutoff
    f_c=min_cutoff+beta*||filtered_velocity||. Missing z_t never becomes zero;
    the previous filtered state is retained.
    """
    dt = 1.0 / fps
    min_cutoff = float(parameters["min_cutoff_hz"])
    beta = float(parameters["beta"])
    derivative_cutoff = float(parameters["derivative_cutoff_hz"])
    output = np.full_like(points, np.nan)
    filtered = None
    previous_observation = None
    filtered_derivative = np.zeros(2, dtype=float)
    missing_steps = 0
    for index, observation in enumerate(points):
        if not np.isfinite(observation).all():
            missing_steps += 1
            if filtered is not None:
                output[index] = filtered
            continue
        if filtered is None:
            filtered = observation.copy()
            previous_observation = observation.copy()
            output[index] = filtered
            continue
        derivative = (observation - previous_observation) / dt
        alpha_d = smoothing_alpha(derivative_cutoff, dt)
        filtered_derivative = alpha_d * derivative + (1.0 - alpha_d) * filtered_derivative
        cutoff = min_cutoff + beta * float(np.linalg.norm(filtered_derivative))
        alpha = smoothing_alpha(cutoff, dt)
        filtered = alpha * observation + (1.0 - alpha) * filtered
        previous_observation = observation.copy()
        output[index] = filtered
    return output, {"missing_policy": "causal_hold_last_state", "missing_steps": missing_steps}


def cv_process_noise(dt: float, acceleration_std: float) -> np.ndarray:
    """White-acceleration process covariance for state [x,y,vx,vy]."""
    base = np.array(
        [
            [dt**4 / 4.0, 0.0, dt**3 / 2.0, 0.0],
            [0.0, dt**4 / 4.0, 0.0, dt**3 / 2.0],
            [dt**3 / 2.0, 0.0, dt**2, 0.0],
            [0.0, dt**3 / 2.0, 0.0, dt**2],
        ],
        dtype=float,
    )
    return acceleration_std**2 * base


def apply_kalman_cv(
    points: np.ndarray,
    parameters: dict[str, Any],
    fps: float,
    confidence: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Causal constant-velocity Kalman filtering.

    Input is Lx2 corrupted normalized positions and optional OpenPose confidence.
    State s=[x,y,vx,vy]. Prediction is s_t=F*s_(t-1). Standard Kalman
    updates use R=r^2*I. In confidence-weighted mode,
    R_t=r0^2/max(confidence_t,c_min)^gamma * I. Missing observations perform
    prediction only; neither ground truth nor the synthetic corruption mask is used.
    """
    dt = 1.0 / fps
    acceleration_std = float(parameters["acceleration_noise_std_norm_s2"])
    weighted = confidence is not None
    if weighted:
        measurement_std = float(parameters["base_measurement_noise_std_norm"])
        confidence_power = float(parameters["confidence_power"])
        minimum_confidence = float(parameters["minimum_confidence"])
    else:
        measurement_std = float(parameters["measurement_noise_std_norm"])
        confidence_power = 0.0
        minimum_confidence = 1.0
    velocity_std = float(parameters["initial_velocity_std_norm_s"])
    transition = np.array(
        [[1.0, 0.0, dt, 0.0], [0.0, 1.0, 0.0, dt], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
        dtype=float,
    )
    observation_model = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=float)
    process_noise = cv_process_noise(dt, acceleration_std)
    output = np.full_like(points, np.nan)
    state = None
    covariance = None
    missing_steps = 0
    for index, observation in enumerate(points):
        available = np.isfinite(observation).all()
        if state is None:
            if not available:
                missing_steps += 1
                continue
            state = np.array([observation[0], observation[1], 0.0, 0.0], dtype=float)
            covariance = np.diag([measurement_std**2, measurement_std**2, velocity_std**2, velocity_std**2])
            output[index] = state[:2]
            continue
        state = transition @ state
        covariance = transition @ covariance @ transition.T + process_noise
        if available:
            if weighted:
                effective_confidence = max(float(confidence[index]), minimum_confidence)
                variance = measurement_std**2 / (effective_confidence**confidence_power)
            else:
                variance = measurement_std**2
            measurement_noise = np.eye(2, dtype=float) * variance
            innovation = observation - observation_model @ state
            innovation_covariance = observation_model @ covariance @ observation_model.T + measurement_noise
            gain = covariance @ observation_model.T @ np.linalg.inv(innovation_covariance)
            state = state + gain @ innovation
            covariance = (np.eye(4) - gain @ observation_model) @ covariance
        else:
            missing_steps += 1
        output[index] = state[:2]
    return output, {
        "missing_policy": "causal_predict_only",
        "missing_steps": missing_steps,
        "measurement_noise": "openpose_confidence_weighted" if weighted else "constant",
    }


def apply_method(
    method: str,
    corrupted_norm: np.ndarray,
    parameters: dict[str, Any],
    fps: float,
    confidence: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Dispatch without accepting clean truth or a corruption mask as input."""
    if method == "corrupted_input":
        return corrupted_norm.copy(), {"missing_policy": "preserve_null", "processing": "none"}
    if method == "savitzky_golay":
        return apply_savitzky_golay(corrupted_norm, parameters)
    if method == "one_euro":
        return apply_one_euro(corrupted_norm, parameters, fps)
    if method == "kalman_cv":
        return apply_kalman_cv(corrupted_norm, parameters, fps)
    if method == "confidence_weighted_kalman":
        return apply_kalman_cv(corrupted_norm, parameters, fps, confidence=confidence)
    raise ValueError(f"unknown method: {method}")


def source_confidence(sample: dict[str, Any], raw_by_frame: dict[int, dict[str, Any]]) -> np.ndarray:
    joint = sample["target_joint"]
    confidence_index = CONFIDENCE_INDEX[joint]
    values = []
    for frame in sample["source_frame_indices"]:
        raw = raw_by_frame[int(frame)]
        values.append(float(raw["raw_confidence"][confidence_index]))
    return np.asarray(values, dtype=float)


def reconstruct_pixels(normalized: np.ndarray, sample: dict[str, Any]) -> np.ndarray:
    origins = np.asarray(sample["neck_origin_px"], dtype=float)
    scales = np.asarray(sample["shoulder_width_px"], dtype=float)
    return origins + normalized * scales[:, None]


def run_sample(
    sample: dict[str, Any],
    method: str,
    parameters: dict[str, Any],
    raw_by_frame: dict[int, dict[str, Any]],
    fps: float,
) -> dict[str, Any]:
    corrupted_norm = optional_points(sample["corrupted_trajectory_norm"])
    confidence = source_confidence(sample, raw_by_frame)
    output_norm, processing = apply_method(method, corrupted_norm, parameters, fps, confidence)
    output_px = reconstruct_pixels(output_norm, sample)
    return {
        "sample_id": sample["sample_id"],
        "split": sample["split"],
        "source_window_id": sample["source_window_id"],
        "source_frame_indices": sample["source_frame_indices"],
        "phase_label": sample["phase_label"],
        "target_joint": sample["target_joint"],
        "corruption_type": sample["corruption_type"],
        "intensity_id": sample["intensity_id"],
        "method": method,
        "parameter_id": parameter_id(method, parameters),
        "parameters": parameters,
        "predicted_trajectory_norm": points_to_json(output_norm),
        "predicted_trajectory_px": points_to_json(output_px),
        "input_observation_available": sample["observation_available"],
        "openpose_confidence": confidence.tolist(),
        "processing_details": processing,
        "ground_truth_used_as_filter_input": False,
        "corruption_mask_used_as_filter_input": False,
    }


def validate_inputs(
    config: dict[str, Any],
    samples: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    selected: dict[str, Any],
) -> None:
    if len(samples) != 336:
        raise ValueError(f"expected 336 B2 samples, got {len(samples)}")
    counts = {split: sum(row["split"] == split for row in samples) for split in ("train", "val", "test")}
    if counts != {"train": 168, "val": 72, "test": 96}:
        raise ValueError(f"frozen split counts changed: {counts}")
    if [row["frame_index"] for row in raw_rows] != list(range(345)):
        raise ValueError("raw trajectory is not exactly frames 0..344")
    if selected.get("test_status") != "not_run":
        raise ValueError("selected parameter file does not declare test_status=not_run")
    for method in METHODS[1:]:
        if method not in selected.get("selected_parameters", {}):
            raise ValueError(f"missing selected parameters for {method}")
        parameters = selected["selected_parameters"][method]["parameters"]
        if parameters not in expand_parameter_grid(config, method):
            raise ValueError(f"selected parameters for {method} are outside preregistered grid")


def main() -> int:
    args = parse_args()
    for path in (args.config, args.dataset, args.raw_trajectory, args.selected_parameters):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.test_audit.exists():
        raise FileExistsError(f"test audit already exists; refusing a second test run: {args.test_audit}")
    if args.output.exists() and not args.overwrite_nontest_output:
        raise FileExistsError(f"refusing to overwrite output: {args.output}")

    config = load_json(args.config)
    samples = load_jsonl(args.dataset)
    raw_rows = load_jsonl(args.raw_trajectory)
    selected = load_json(args.selected_parameters)
    validate_inputs(config, samples, raw_rows, selected)
    expected_hashes = selected["provenance_sha256"]
    actual_hashes = {
        "config": sha256_file(args.config),
        "dataset": sha256_file(args.dataset),
        "raw_trajectory": sha256_file(args.raw_trajectory),
    }
    if actual_hashes != expected_hashes:
        raise ValueError(f"provenance hash mismatch before test: {actual_hashes} != {expected_hashes}")

    raw_by_frame = {int(row["frame_index"]): row for row in raw_rows}
    fps = float(config["fps"])
    predictions = []
    for sample in samples:
        for method in METHODS:
            parameters = {} if method == "corrupted_input" else selected["selected_parameters"][method]["parameters"]
            predictions.append(run_sample(sample, method, parameters, raw_by_frame, fps))
    if len(predictions) != 336 * len(METHODS):
        raise AssertionError("prediction count mismatch")
    output_text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in predictions)
    atomic_write(args.output, output_text)

    test_predictions = [row for row in predictions if row["split"] == "test"]
    audit = {
        "run_id": "20260714_T07C_B3_TEST_ONCE_001",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_evaluation_count": 1,
        "test_sample_count": 96,
        "test_prediction_count": len(test_predictions),
        "methods": list(METHODS),
        "selected_parameters_sha256": sha256_file(args.selected_parameters),
        "provenance_sha256": actual_hashes,
        "prediction_output": str(args.output),
        "prediction_output_sha256": sha256_file(args.output),
        "test_results_used_for_parameter_adjustment": False,
    }
    atomic_write(args.test_audit, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
