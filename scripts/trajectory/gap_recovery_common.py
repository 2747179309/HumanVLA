"""Shared deterministic primitives for the T07B short-gap benchmark."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import CubicHermiteSpline, PchipInterpolator, interp1d

JOINT_PREFIX = {"RElbow": "relbow", "RWrist": "rwrist"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manual_excluded_frames(review_rows: list[dict[str, str]], labels: set[str]) -> set[int]:
    frames: set[int] = set()
    for row in review_rows:
        if row["manual_label"] in labels:
            frames.update((int(row["from_frame"]), int(row["to_frame"])))
    return frames


def joint_reliable(row: dict[str, Any], joint: str) -> bool:
    if row["trajectory_quality"] != "valid" or not row["normalization_anchor_valid"]:
        return False
    prefix = JOINT_PREFIX[joint]
    if row[f"{prefix}_x_norm"] is None or row[f"{prefix}_y_norm"] is None:
        return False
    if joint == "RWrist":
        return bool(row["rwrist_coordinate_available"] and row["rwrist_effective_status"] == "valid")
    return bool(row["relbow_coordinate_available"] and row["relbow_effective_status"] == "valid")


def normalized_point(row: dict[str, Any], joint: str) -> np.ndarray:
    prefix = JOINT_PREFIX[joint]
    return np.array([row[f"{prefix}_x_norm"], row[f"{prefix}_y_norm"]], dtype=float)


def pixel_point(row: dict[str, Any], joint: str) -> np.ndarray:
    prefix = JOINT_PREFIX[joint]
    return np.array([row[f"{prefix}_x_px"], row[f"{prefix}_y_px"]], dtype=float)


def norm_to_pixel(row: dict[str, Any], point_norm: np.ndarray) -> np.ndarray:
    return np.array([
        row["neck_x_px"] + point_norm[0] * row["shoulder_width_px"],
        row["neck_y_px"] + point_norm[1] * row["shoulder_width_px"],
    ], dtype=float)


def _kalman_filter_smoother(
    frames: list[int], observations: dict[int, np.ndarray], policy: dict[str, Any],
) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray]]:
    params = policy["methods"]["kalman_cv"]
    q = np.diag(np.asarray(params["process_covariance_diagonal"], dtype=float))
    r = np.diag(np.asarray(params["observation_covariance_diagonal"], dtype=float))
    p0 = np.diag(np.asarray(params["initial_covariance_diagonal"], dtype=float))
    f = np.array([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
    h = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
    observed_frames = sorted(observations)
    first, second = observed_frames[:2]
    velocity = (observations[second] - observations[first]) / (second - first)
    state = np.array([*observations[first], *velocity], dtype=float)
    covariance = p0.copy()
    filtered_states: list[np.ndarray] = []
    filtered_covariances: list[np.ndarray] = []
    predicted_states: list[np.ndarray] = []
    predicted_covariances: list[np.ndarray] = []
    previous_frame = first
    for frame in frames:
        if frame == first:
            predicted_state, predicted_covariance = state.copy(), covariance.copy()
        else:
            steps = frame - previous_frame
            predicted_state, predicted_covariance = state.copy(), covariance.copy()
            for _ in range(steps):
                predicted_state = f @ predicted_state
                predicted_covariance = f @ predicted_covariance @ f.T + q
        if frame in observations:
            innovation = observations[frame] - h @ predicted_state
            innovation_covariance = h @ predicted_covariance @ h.T + r
            gain = predicted_covariance @ h.T @ np.linalg.inv(innovation_covariance)
            state = predicted_state + gain @ innovation
            covariance = (np.eye(4) - gain @ h) @ predicted_covariance
        else:
            state, covariance = predicted_state, predicted_covariance
        predicted_states.append(predicted_state.copy())
        predicted_covariances.append(predicted_covariance.copy())
        filtered_states.append(state.copy())
        filtered_covariances.append(covariance.copy())
        previous_frame = frame

    smoothed_states = [state.copy() for state in filtered_states]
    smoothed_covariances = [value.copy() for value in filtered_covariances]
    for index in range(len(frames) - 2, -1, -1):
        predicted_covariance = predicted_covariances[index + 1]
        gain = filtered_covariances[index] @ f.T @ np.linalg.inv(predicted_covariance)
        smoothed_states[index] = filtered_states[index] + gain @ (
            smoothed_states[index + 1] - predicted_states[index + 1]
        )
        smoothed_covariances[index] = filtered_covariances[index] + gain @ (
            smoothed_covariances[index + 1] - predicted_covariance
        ) @ gain.T
    filtered = {frame: filtered_states[index][:2] for index, frame in enumerate(frames)}
    smoothed = {frame: smoothed_states[index][:2] for index, frame in enumerate(frames)}
    return filtered, smoothed


def recover_normalized(
    method: str, rows: list[dict[str, Any]], joint: str, gap_frames: list[int],
    context_frames: list[int], policy: dict[str, Any],
) -> dict[int, np.ndarray]:
    if len(context_frames) != 4:
        raise ValueError("exactly two reliable observations on each side are required")
    b2, b1, a1, a2 = context_frames
    if not (b2 < b1 < min(gap_frames) <= max(gap_frames) < a1 < a2):
        raise ValueError("invalid context/gap ordering")
    times = np.asarray(context_frames, dtype=float)
    values = np.stack([normalized_point(rows[frame], joint) for frame in context_frames])
    targets = np.asarray(gap_frames, dtype=float)
    if method == "linear":
        result = interp1d(
            [b1, a1], values[[1, 2]], kind="linear", axis=0, assume_sorted=True,
        )(targets)
    elif method == "pchip":
        result = PchipInterpolator(times, values, axis=0)(targets)
    elif method == "cubic_hermite":
        left_slope = (values[1] - values[0]) / (b1 - b2)
        right_slope = (values[3] - values[2]) / (a2 - a1)
        result = CubicHermiteSpline(
            [b1, a1], np.stack([values[1], values[2]]),
            np.stack([left_slope, right_slope]), axis=0,
        )(targets)
    elif method == "kalman_cv_prediction":
        velocity = (values[1] - values[0]) / (b1 - b2)
        result = np.stack([values[1] + velocity * (frame - b1) for frame in targets])
    elif method == "kalman_cv_smoothing":
        frames = list(range(b2, a2 + 1))
        observations = {frame: normalized_point(rows[frame], joint) for frame in context_frames}
        _, smoothed = _kalman_filter_smoother(frames, observations, policy)
        result = np.stack([smoothed[frame] for frame in gap_frames])
    else:
        raise ValueError(f"unknown recovery method: {method}")
    return {frame: result[index] for index, frame in enumerate(gap_frames)}


def _derivative(points: np.ndarray, dt: float, order: int) -> np.ndarray:
    result = points.copy()
    for _ in range(order):
        result = np.diff(result, axis=0) / dt
    return result


def _mean_abs_error(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.mean(np.abs(first - second)))


def _path_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def _curvatures(points: np.ndarray) -> np.ndarray:
    values: list[float] = []
    for first, middle, last in zip(points, points[1:], points[2:]):
        a, b, c = middle - first, last - middle, last - first
        denominator = np.linalg.norm(a) * np.linalg.norm(b) * np.linalg.norm(c)
        values.append(0.0 if denominator <= 1e-12 else abs(a[0] * b[1] - a[1] * b[0]) / denominator)
    return np.asarray(values, dtype=float)


def evaluate_recovery(
    rows: list[dict[str, Any]], joint: str, gap_frames: list[int], context_frames: list[int],
    predicted_norm: dict[int, np.ndarray], fps: float,
) -> dict[str, float]:
    predicted_gap_norm = np.stack([predicted_norm[frame] for frame in gap_frames])
    truth_gap_norm = np.stack([normalized_point(rows[frame], joint) for frame in gap_frames])
    predicted_gap_px = np.stack([norm_to_pixel(rows[frame], predicted_norm[frame]) for frame in gap_frames])
    truth_gap_px = np.stack([pixel_point(rows[frame], joint) for frame in gap_frames])
    b2, b1, a1, a2 = context_frames
    sequence_frames = [b2, b1, *gap_frames, a1, a2]
    truth_norm = np.stack([normalized_point(rows[frame], joint) for frame in sequence_frames])
    truth_px = np.stack([pixel_point(rows[frame], joint) for frame in sequence_frames])
    predicted_norm_sequence = truth_norm.copy()
    predicted_px_sequence = truth_px.copy()
    for index, frame in enumerate(sequence_frames):
        if frame in predicted_norm:
            predicted_norm_sequence[index] = predicted_norm[frame]
            predicted_px_sequence[index] = norm_to_pixel(rows[frame], predicted_norm[frame])
    dt = 1.0 / fps
    result: dict[str, float] = {
        "mae_px": _mean_abs_error(predicted_gap_px, truth_gap_px),
        "rmse_px": float(np.sqrt(np.mean(np.square(predicted_gap_px - truth_gap_px)))),
        "mae_norm": _mean_abs_error(predicted_gap_norm, truth_gap_norm),
        "rmse_norm": float(np.sqrt(np.mean(np.square(predicted_gap_norm - truth_gap_norm)))),
        "max_error_px": float(np.max(np.abs(predicted_gap_px - truth_gap_px))),
        "max_error_norm": float(np.max(np.abs(predicted_gap_norm - truth_gap_norm))),
        "endpoint_error_px": float(np.linalg.norm(predicted_gap_px[-1] - truth_gap_px[-1])),
        "endpoint_error_norm": float(np.linalg.norm(predicted_gap_norm[-1] - truth_gap_norm[-1])),
        "trajectory_length_error_px": abs(_path_length(predicted_px_sequence) - _path_length(truth_px)),
        "trajectory_length_error_norm": abs(_path_length(predicted_norm_sequence) - _path_length(truth_norm)),
        "curvature_error_px": _mean_abs_error(_curvatures(predicted_px_sequence), _curvatures(truth_px)),
        "curvature_error_norm": _mean_abs_error(_curvatures(predicted_norm_sequence), _curvatures(truth_norm)),
    }
    for name, predicted, truth in (
        ("px", predicted_px_sequence, truth_px), ("norm", predicted_norm_sequence, truth_norm),
    ):
        result[f"velocity_error_{name}_per_s"] = _mean_abs_error(
            _derivative(predicted, dt, 1), _derivative(truth, dt, 1)
        )
        result[f"acceleration_error_{name}_per_s2"] = _mean_abs_error(
            _derivative(predicted, dt, 2), _derivative(truth, dt, 2)
        )
        result[f"jerk_error_{name}_per_s3"] = _mean_abs_error(
            _derivative(predicted, dt, 3), _derivative(truth, dt, 3)
        )
        result[f"entry_velocity_discontinuity_{name}_per_s"] = float(np.linalg.norm(
            (predicted[2] - predicted[1]) / dt - (predicted[1] - predicted[0]) / dt
        ))
        result[f"exit_velocity_discontinuity_{name}_per_s"] = float(np.linalg.norm(
            (predicted[-1] - predicted[-2]) / dt - (predicted[-2] - predicted[-3]) / dt
        ))
    return result
