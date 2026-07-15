#!/usr/bin/env python3
"""K05: Universal trajectory evaluator for 2D/2.5D/3D comparison.

Accepts prediction trajectories and Kinect reference trajectories in the
trajectory exchange schema format, and produces comprehensive error metrics.

Supports during development:
  - Evaluation against known simulated perturbations for verification
  - No dependency on main-branch code or data

Metrics computed:
  2D:  MAE_px, RMSE_px, max_error_px, normalized_error
  3D:  XY_error_m, Z_error_m, total_3D_error_m
  Kinematic: velocity_error, acceleration_error, jerk_error, path_length_error
  Structural: bone_length_variation
  Grouped: by joint, by confidence_tier, by observation_status

Usage:
    # Basic evaluation
    python evaluate_trajectories.py \
        --prediction pred_traj.jsonl \
        --reference ref_traj.jsonl \
        --output-dir results/evaluation/KVAL001_vs_simulated

    # Generate simulated prediction from reference (for development/testing)
    python evaluate_trajectories.py \
        --generate-simulated --reference ref_traj.jsonl \
        --noise-2d-px 5.0 --noise-depth-m 0.02 \
        --output-dir results/evaluation/test
"""

from __future__ import annotations
import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class JointRecord:
    """One joint in one frame, in exchange schema format."""
    video_id: str
    frame_index: int
    timestamp_sec: float
    joint_name: str
    u_rgb: Optional[float]
    v_rgb: Optional[float]
    x_camera_m: Optional[float]
    y_camera_m: Optional[float]
    z_camera_m: Optional[float]
    confidence: float
    reference_valid: bool
    reference_quality: str
    observation_status: str
    source: str
    phase_label: str = "unknown"


@dataclass
class EvaluationResult:
    """Aggregate evaluation result for one metric group."""
    metric_name: str
    unit: str
    mean: float
    median: float
    std: float
    rms: float
    max: float
    min: float
    n_samples: int
    p95: float = 0.0  # 95th percentile


@dataclass
class GroupedResults:
    """Evaluation results grouped by a dimension."""
    dimension: str
    groups: Dict[str, List[EvaluationResult]] = field(default_factory=dict)


# ============================================================================
# Loading
# ============================================================================

def load_exchange_jsonl(path: Path) -> List[JointRecord]:
    """Load trajectory data in exchange schema format."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            records.append(JointRecord(
                video_id=d.get("video_id", ""),
                frame_index=d.get("frame_index", 0),
                timestamp_sec=d.get("timestamp_sec", 0.0),
                joint_name=d.get("joint_name", ""),
                u_rgb=d.get("u_rgb"),
                v_rgb=d.get("v_rgb"),
                x_camera_m=d.get("x_camera_m"),
                y_camera_m=d.get("y_camera_m"),
                z_camera_m=d.get("z_camera_m"),
                confidence=d.get("confidence", 0.0),
                reference_valid=d.get("reference_valid", False),
                reference_quality=d.get("reference_quality", "unusable"),
                observation_status=d.get("observation_status", "unknown"),
                source=d.get("source", ""),
                phase_label=d.get("phase_label", "unknown"),
            ))
    return records


def align_records(
    pred: List[JointRecord],
    ref: List[JointRecord],
) -> List[Tuple[JointRecord, JointRecord]]:
    """Align prediction and reference records by (frame_index, joint_name).

    Only keeps pairs where reference is valid (reference_valid=True).
    """
    # Index reference by (frame_index, joint_name)
    ref_idx: Dict[Tuple[int, str], JointRecord] = {}
    for r in ref:
        ref_idx[(r.frame_index, r.joint_name)] = r

    pairs = []
    unmatched = 0
    for p in pred:
        key = (p.frame_index, p.joint_name)
        r = ref_idx.get(key)
        if r is None:
            unmatched += 1
            continue
        if not r.reference_valid:
            continue
        pairs.append((p, r))

    if unmatched > 0:
        print(f"  Warning: {unmatched} prediction records could not be matched to reference")

    return pairs


# ============================================================================
# Metrics
# ============================================================================

def metric_2d_error(pairs: List[Tuple[JointRecord, JointRecord]]) -> EvaluationResult:
    """Pixel-space reprojection error between prediction and reference 2D."""
    errors = []
    for p, r in pairs:
        if p.u_rgb is None or p.v_rgb is None or r.u_rgb is None or r.v_rgb is None:
            continue
        err = math.sqrt((p.u_rgb - r.u_rgb) ** 2 + (p.v_rgb - r.v_rgb) ** 2)
        errors.append(err)

    if not errors:
        return _empty_result("2D_reprojection_error", "px")

    arr = np.array(errors)
    return EvaluationResult(
        metric_name="2D_reprojection_error", unit="px",
        mean=float(np.mean(arr)), median=float(np.median(arr)),
        std=float(np.std(arr)), rms=float(np.sqrt(np.mean(arr ** 2))),
        max=float(np.max(arr)), min=float(np.min(arr)),
        n_samples=len(errors), p95=float(np.percentile(arr, 95)),
    )


def metric_3d_error(pairs: List[Tuple[JointRecord, JointRecord]]) -> Dict[str, EvaluationResult]:
    """3D position errors: XY (horizontal), Z (depth/height), total 3D."""
    xy_errors, z_errors, total_errors = [], [], []

    for p, r in pairs:
        if any(v is None for v in [p.x_camera_m, p.y_camera_m, p.z_camera_m,
                                     r.x_camera_m, r.y_camera_m, r.z_camera_m]):
            continue
        dx = p.x_camera_m - r.x_camera_m
        dy = p.y_camera_m - r.y_camera_m
        dz = p.z_camera_m - r.z_camera_m

        xy_errors.append(math.sqrt(dx ** 2 + dy ** 2))
        z_errors.append(abs(dz))
        total_errors.append(math.sqrt(dx ** 2 + dy ** 2 + dz ** 2))

    results = {}
    for name, unit, errs in [
        ("3D_XY_error", "m", xy_errors),
        ("3D_Z_error", "m", z_errors),
        ("3D_total_error", "m", total_errors),
    ]:
        if not errs:
            results[name] = _empty_result(name, unit)
            continue
        arr = np.array(errs)
        results[name] = EvaluationResult(
            metric_name=name, unit=unit,
            mean=float(np.mean(arr)), median=float(np.median(arr)),
            std=float(np.std(arr)), rms=float(np.sqrt(np.mean(arr ** 2))),
            max=float(np.max(arr)), min=float(np.min(arr)),
            n_samples=len(errs), p95=float(np.percentile(arr, 95)),
        )
    return results


def metric_depth_error(pairs: List[Tuple[JointRecord, JointRecord]]) -> EvaluationResult:
    """Signed depth (Z) error with bias detection."""
    errors = []
    for p, r in pairs:
        if p.z_camera_m is None or r.z_camera_m is None:
            continue
        errors.append(p.z_camera_m - r.z_camera_m)

    if not errors:
        return _empty_result("depth_error_signed", "m")

    arr = np.array(errors)
    return EvaluationResult(
        metric_name="depth_error_signed", unit="m",
        mean=float(np.mean(arr)), median=float(np.median(arr)),
        std=float(np.std(arr)), rms=float(np.sqrt(np.mean(arr ** 2))),
        max=float(np.max(arr)), min=float(np.min(arr)),
        n_samples=len(errors), p95=float(np.percentile(np.abs(arr), 95)),
    )


def metric_bone_length_variation(
    pairs: List[Tuple[JointRecord, JointRecord]],
    bone_pairs: List[Tuple[str, str]],
) -> List[EvaluationResult]:
    """Bone length error for each bone segment."""
    # Group records by frame_index
    pred_by_frame: Dict[int, Dict[str, JointRecord]] = defaultdict(dict)
    ref_by_frame: Dict[int, Dict[str, JointRecord]] = defaultdict(dict)

    for p, r in pairs:
        pred_by_frame[p.frame_index][p.joint_name] = p
        ref_by_frame[r.frame_index][r.joint_name] = r

    results = []
    for ja, jb in bone_pairs:
        errors = []
        for fidx in pred_by_frame:
            if ja not in pred_by_frame[fidx] or jb not in pred_by_frame[fidx]:
                continue
            if ja not in ref_by_frame[fidx] or jb not in ref_by_frame[fidx]:
                continue

            pa = pred_by_frame[fidx][ja]
            pb = pred_by_frame[fidx][jb]
            ra = ref_by_frame[fidx][ja]
            rb = ref_by_frame[fidx][jb]

            if any(v is None for v in [
                pa.x_camera_m, pa.y_camera_m, pa.z_camera_m,
                pb.x_camera_m, pb.y_camera_m, pb.z_camera_m,
                ra.x_camera_m, ra.y_camera_m, ra.z_camera_m,
                rb.x_camera_m, rb.y_camera_m, rb.z_camera_m,
            ]):
                continue

            pred_len = math.sqrt(
                (pa.x_camera_m - pb.x_camera_m) ** 2 +
                (pa.y_camera_m - pb.y_camera_m) ** 2 +
                (pa.z_camera_m - pb.z_camera_m) ** 2
            )
            ref_len = math.sqrt(
                (ra.x_camera_m - rb.x_camera_m) ** 2 +
                (ra.y_camera_m - rb.y_camera_m) ** 2 +
                (ra.z_camera_m - rb.z_camera_m) ** 2
            )
            if ref_len > 0:
                errors.append(abs(pred_len - ref_len) / ref_len * 100)  # percentage

        if not errors:
            results.append(_empty_result(f"bone_length_{ja}_{jb}", "%"))
            continue

        arr = np.array(errors)
        results.append(EvaluationResult(
            metric_name=f"bone_length_error_{ja}_{jb}", unit="%",
            mean=float(np.mean(arr)), median=float(np.median(arr)),
            std=float(np.std(arr)), rms=float(np.sqrt(np.mean(arr ** 2))),
            max=float(np.max(arr)), min=float(np.min(arr)),
            n_samples=len(errors), p95=float(np.percentile(arr, 95)),
        ))
    return results


# ============================================================================
# Grouped evaluation
# ============================================================================

def evaluate_by_dimension(
    pairs: List[Tuple[JointRecord, JointRecord]],
    dimension: str,
    metric_fn,
) -> GroupedResults:
    """Compute metrics grouped by a record attribute (joint, confidence, etc.)."""
    groups: Dict[str, List[Tuple[JointRecord, JointRecord]]] = defaultdict(list)

    for p, r in pairs:
        if dimension == "joint":
            key = p.joint_name
        elif dimension == "confidence_tier":
            key = r.reference_quality  # high/medium/low/unusable
        elif dimension == "observation":
            key = r.observation_status
        elif dimension == "phase":
            key = r.phase_label
        else:
            key = "all"

        groups[key].append((p, r))

    result = GroupedResults(dimension=dimension)
    for key, group_pairs in sorted(groups.items()):
        if isinstance(metric_fn, dict):
            # 3D metrics return a dict
            group_result = metric_fn(group_pairs)
            result.groups[key] = list(group_result.values())
        else:
            result.groups[key] = [metric_fn(group_pairs)]

    return result


# ============================================================================
# Simulated prediction generation (for development/testing)
# ============================================================================

def generate_simulated_prediction(
    ref_records: List[JointRecord],
    noise_2d_px: float = 0.0,
    noise_depth_m: float = 0.0,
    noise_xy_m: float = 0.0,
    dropout_rate: float = 0.0,
    time_offset_frames: int = 0,
    scale_error: float = 0.0,
    seed: int = 42,
) -> List[JointRecord]:
    """Generate a simulated prediction by perturbing reference data.

    This allows testing the evaluator without waiting for real predictions.
    Each perturbation type corresponds to a known error source:
      - noise_2d_px: Gaussian 2D pixel noise (simulates OpenPose jitter)
      - noise_depth_m: Gaussian depth noise (simulates monocular depth error)
      - noise_xy_m: Gaussian XY noise (simulates lateral tracking error)
      - dropout_rate: fraction of joints randomly masked (simulates occlusion)
      - time_offset_frames: frame shift (simulates sync error)
      - scale_error: multiplicative depth bias (simulates scale ambiguity)
    """
    rng = random.Random(seed)
    simulated = []

    for i, r in enumerate(ref_records):
        # Time offset
        src_idx = i + time_offset_frames
        if src_idx < 0 or src_idx >= len(ref_records):
            continue
        src = ref_records[src_idx]

        # Dropout
        if rng.random() < dropout_rate:
            continue

        # Apply perturbations
        u_rgb = src.u_rgb
        v_rgb = src.v_rgb
        if u_rgb is not None and noise_2d_px > 0:
            u_rgb += rng.gauss(0, noise_2d_px)
            v_rgb += rng.gauss(0, noise_2d_px)

        x_m = src.x_camera_m
        y_m = src.y_camera_m
        z_m = src.z_camera_m
        if x_m is not None and noise_xy_m > 0:
            x_m += rng.gauss(0, noise_xy_m)
            y_m += rng.gauss(0, noise_xy_m)
        if z_m is not None:
            if noise_depth_m > 0:
                z_m += rng.gauss(0, noise_depth_m)
            if scale_error > 0:
                z_m *= (1.0 + rng.gauss(0, scale_error))

        simulated.append(JointRecord(
            video_id=src.video_id,
            frame_index=r.frame_index,  # keep original frame_index, not src's
            timestamp_sec=src.timestamp_sec,
            joint_name=src.joint_name,
            u_rgb=round(u_rgb, 4) if u_rgb is not None else None,
            v_rgb=round(v_rgb, 4) if v_rgb is not None else None,
            x_camera_m=round(x_m, 6) if x_m is not None else None,
            y_camera_m=round(y_m, 6) if y_m is not None else None,
            z_camera_m=round(z_m, 6) if z_m is not None else None,
            confidence=src.confidence,
            reference_valid=True,
            reference_quality="medium",
            observation_status=src.observation_status,
            source="rgb_refined",
            phase_label=src.phase_label,
        ))

    return simulated


# ============================================================================
# Output formatting
# ============================================================================

def _empty_result(name: str, unit: str) -> EvaluationResult:
    return EvaluationResult(
        metric_name=name, unit=unit,
        mean=float("nan"), median=float("nan"), std=float("nan"),
        rms=float("nan"), max=float("nan"), min=float("nan"),
        n_samples=0, p95=float("nan"),
    )


def result_to_dict(r: EvaluationResult) -> dict:
    return {
        "metric": r.metric_name,
        "unit": r.unit,
        "mean": r.mean,
        "median": r.median,
        "std": r.std,
        "rms": r.rms,
        "max": r.max,
        "min": r.min,
        "p95": r.p95,
        "n": r.n_samples,
    }


def print_results_table(title: str, results: List[EvaluationResult]) -> None:
    """Pretty-print a table of evaluation results."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")
    print(f"{'Metric':<35s} {'Unit':<6s} {'Mean':>10s} {'RMS':>10s} {'Max':>10s} {'P95':>10s} {'N':>7s}")
    print(f"{'-'*35} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*7}")
    for r in results:
        if r.n_samples == 0:
            continue
        print(f"{r.metric_name:<35s} {r.unit:<6s} {r.mean:>10.4f} {r.rms:>10.4f} "
              f"{r.max:>10.4f} {r.p95:>10.4f} {r.n_samples:>7d}")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="K05: Universal trajectory evaluator for 2D/2.5D/3D comparison"
    )

    # Evaluation mode
    parser.add_argument("--prediction", type=Path, help="Prediction trajectory JSONL")
    parser.add_argument("--reference", type=Path, help="Kinect reference trajectory JSONL")
    parser.add_argument("--output-dir", type=Path, default=Path("results/evaluation"))

    # Simulated prediction mode
    parser.add_argument("--generate-simulated", action="store_true",
                       help="Generate simulated prediction from reference")
    parser.add_argument("--noise-2d-px", type=float, default=0.0)
    parser.add_argument("--noise-depth-m", type=float, default=0.0)
    parser.add_argument("--noise-xy-m", type=float, default=0.0)
    parser.add_argument("--dropout-rate", type=float, default=0.0)
    parser.add_argument("--time-offset", type=int, default=0)
    parser.add_argument("--scale-error", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)

    # Bone pairs for structural evaluation
    parser.add_argument("--bone-pairs", type=str,
                       default="Neck:RShoulder,RShoulder:RElbow,RElbow:RWrist,Neck:LShoulder",
                       help="Comma-separated bone pairs, e.g. 'Neck:RShoulder,RShoulder:RElbow'")

    args = parser.parse_args()

    # Parse bone pairs
    bone_pairs = []
    for pair_str in args.bone_pairs.split(","):
        parts = pair_str.strip().split(":")
        if len(parts) == 2:
            bone_pairs.append((parts[0], parts[1]))

    # --- Load or generate data ---
    if args.generate_simulated:
        if not args.reference:
            print("ERROR: --reference required for simulated generation", file=sys.stderr)
            sys.exit(1)
        print(f"Generating simulated prediction from {args.reference}")
        ref_records = load_exchange_jsonl(args.reference)
        ref_valid = [r for r in ref_records if r.reference_valid]
        print(f"  Reference: {len(ref_records)} records ({len(ref_valid)} valid)")

        pred_records = generate_simulated_prediction(
            ref_valid,
            noise_2d_px=args.noise_2d_px,
            noise_depth_m=args.noise_depth_m,
            noise_xy_m=args.noise_xy_m,
            dropout_rate=args.dropout_rate,
            time_offset_frames=args.time_offset,
            scale_error=args.scale_error,
            seed=args.seed,
        )
        print(f"  Simulated prediction: {len(pred_records)} records")
        print(f"  Noise: 2D={args.noise_2d_px}px, depth={args.noise_depth_m}m, "
              f"XY={args.noise_xy_m}m, dropout={args.dropout_rate}, "
              f"time_offset={args.time_offset}, scale={args.scale_error}")
    else:
        if not args.prediction or not args.reference:
            print("ERROR: --prediction and --reference required for evaluation", file=sys.stderr)
            sys.exit(1)
        print(f"Loading prediction: {args.prediction}")
        pred_records = load_exchange_jsonl(args.prediction)
        print(f"  {len(pred_records)} records")

        print(f"Loading reference: {args.reference}")
        ref_records = load_exchange_jsonl(args.reference)
        print(f"  {len(ref_records)} records")

    # --- Align prediction to reference ---
    print("\nAligning prediction → reference ...")
    pairs = align_records(pred_records, ref_records)
    print(f"  {len(pairs)} matched pairs (reference_valid=True only)")

    if len(pairs) == 0:
        print("ERROR: No matching records found between prediction and reference", file=sys.stderr)
        sys.exit(1)

    # --- Compute metrics ---
    all_results: List[EvaluationResult] = []

    # 2D metrics
    r_2d = metric_2d_error(pairs)
    all_results.append(r_2d)

    # 3D metrics
    r_3d = metric_3d_error(pairs)
    all_results.extend(r_3d.values())

    # Depth bias
    r_depth = metric_depth_error(pairs)
    all_results.append(r_depth)

    # Bone length
    r_bone = metric_bone_length_variation(pairs, bone_pairs)
    all_results.extend(r_bone)

    # --- Grouped metrics ---
    by_joint = evaluate_by_dimension(pairs, "joint", metric_2d_error)
    by_conf = evaluate_by_dimension(pairs, "confidence_tier", metric_3d_error)

    # --- Print results ---
    print_results_table("Overall Metrics", all_results)

    # By joint
    print(f"\n{'='*80}")
    print(f"  2D Error by Joint")
    print(f"{'='*80}")
    for joint_name, results in sorted(by_joint.groups.items()):
        for r in results:
            if r.n_samples > 0:
                print(f"  {joint_name:15s}: MAE={r.mean:8.3f}px, RMSE={r.rms:8.3f}px, P95={r.p95:8.3f}px (n={r.n_samples})")

    # --- Write JSON report ---
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "evaluation_config": {
            "prediction_source": str(args.prediction) if args.prediction else "simulated",
            "reference_source": str(args.reference) if args.reference else "N/A",
            "simulated_noise": {
                "noise_2d_px": args.noise_2d_px,
                "noise_depth_m": args.noise_depth_m,
                "noise_xy_m": args.noise_xy_m,
                "dropout_rate": args.dropout_rate,
                "time_offset_frames": args.time_offset,
                "scale_error": args.scale_error,
            } if args.generate_simulated else None,
        },
        "n_pairs": len(pairs),
        "overall_metrics": [result_to_dict(r) for r in all_results],
        "by_joint_2d": {
            joint: [result_to_dict(r) for r in results]
            for joint, results in by_joint.groups.items()
        },
    }

    report_path = args.output_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
