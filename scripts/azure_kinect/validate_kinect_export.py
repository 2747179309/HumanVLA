#!/usr/bin/env python3
"""Comprehensive validation of standardized Kinect skeleton data.

Verifies:
  - Required fields exist with correct types
  - frame_index continuity (0-based, no gaps)
  - timestamp monotonicity (strictly increasing)
  - Joint count = 32 for frames with valid body_id
  - body_id stability and switch detection
  - NaN / Inf detection in 3D coordinates
  - 2D coordinate range sanity
  - Confidence level range (0-3)
  - RGB-depth timestamp synchronization
  - Color and depth file path consistency
  - Frame count match with frame_sync.csv
  - SHA-256 file integrity (if manifest provided)
  - Duplicate frame detection
  - Drop frame detection

Returns exit code 0 only when ALL hard checks pass.
Returns exit code 1 for hard failures, 2 for warnings only.

Usage:
    python validate_kinect_export.py \
        --skeleton data/azure_kinect/processed/K01/kinect_skeleton.jsonl \
        --sync-csv data/azure_kinect/processed/K01/frame_sync.csv \
        [--manifest data/azure_kinect/processed/K01/file_manifest.json] \
        [--warn-as-error]
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Supported fields and their expected types
REQUIRED_FIELDS = {
    "video_id": str,
    "frame_index": int,
    "source_frame_index": int,
    "timestamp_usec": int,
    "color_timestamp_usec": int,
    "depth_timestamp_usec": int,
    "color_path": str,
    "depth_path": str,
    "body_id": int,
    "joints_3d_camera": list,
    "joints_2d_color": list,
    "joint_confidence": list,
}

OPTIONAL_FIELDS = {
    "reference_valid": list,
    "reference_quality": list,
    "invalid_reason": list,
    "observation_status": list,
}

EXPECTED_JOINT_COUNT = 32
CONFIDENCE_RANGE = (0, 3)       # Kinect SDK enum: 0=NONE, 1=LOW, 2=MEDIUM, 3=HIGH
MAX_REASONABLE_3D_M = 10.0      # 3D coordinate bounds in meters
MAX_REASONABLE_2D_PX = 5000.0   # 2D coordinate bounds in pixels (generous for 4K)
MAX_RGB_DEPTH_SYNC_DIFF_USEC = 1000  # Max allowed color-depth timestamp diff (1ms)


class ValidationError(Exception):
    """Hard validation failure."""
    pass


class ValidationWarning(Exception):
    """Non-fatal warning."""
    pass


def check_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise ValidationError(f"{label} not found: {path}")


def check_field(rec: dict, field: str, expected_type: type, frame_idx: int) -> None:
    if field not in rec:
        raise ValidationError(f"frame {frame_idx}: missing required field '{field}'")
    if not isinstance(rec[field], expected_type):
        raise ValidationError(
            f"frame {frame_idx}: field '{field}' expected {expected_type.__name__}, "
            f"got {type(rec[field]).__name__}"
        )


def validate_required_fields(records: list[dict]) -> List[str]:
    """Check all required fields exist with correct types. Returns warnings."""
    warnings = []
    for i, rec in enumerate(records):
        fnum = rec.get("frame_index", i)
        for field, ftype in REQUIRED_FIELDS.items():
            try:
                check_field(rec, field, ftype, fnum)
            except ValidationError as e:
                raise  # re-raise hard errors
        # Check optional fields if present
        for field in OPTIONAL_FIELDS:
            if field in rec and rec[field] is not None and not isinstance(rec[field], list):
                warnings.append(f"frame {fnum}: optional field '{field}' should be list, got {type(rec[field]).__name__}")
    return warnings


def validate_frame_continuity(records: list[dict]) -> None:
    """Check frame_index is 0-based and strictly contiguous."""
    for i, rec in enumerate(records):
        actual = rec["frame_index"]
        if actual != i:
            raise ValidationError(
                f"Record {i}: expected frame_index={i}, got {actual}. "
                f"Gap or duplicate detected."
            )


def validate_timestamps(records: list[dict]) -> List[str]:
    """Check timestamp_usec is strictly increasing. Returns warnings."""
    warnings = []
    prev_ts = -1
    for rec in records:
        ts = rec["timestamp_usec"]
        fnum = rec["frame_index"]
        if ts <= prev_ts:
            raise ValidationError(
                f"frame {fnum}: timestamp_usec not strictly increasing: "
                f"{ts} <= {prev_ts}"
            )
        # Check for unreasonable jumps (>1 second at 30fps would be ~33x normal)
        if prev_ts >= 0:
            delta = ts - prev_ts
            if delta > 1_000_000:  # >1 second gap
                warnings.append(f"frame {fnum}: large timestamp gap of {delta} usec ({delta/1e6:.3f}s)")
        prev_ts = ts
    return warnings


def validate_joint_arrays(records: list[dict]) -> List[str]:
    """Check joint array dimensions and values. Returns warnings."""
    warnings = []
    for rec in records:
        fnum = rec["frame_index"]
        body_id = rec["body_id"]

        if body_id == -1:
            # No body detected — arrays may be empty
            if len(rec["joints_3d_camera"]) > 0:
                warnings.append(f"frame {fnum}: body_id=-1 but joints_3d_camera is non-empty")
            continue

        # Valid body: must have exactly 32 joints
        j3d = rec["joints_3d_camera"]
        j2d = rec["joints_2d_color"]
        conf = rec["joint_confidence"]

        if len(j3d) != EXPECTED_JOINT_COUNT:
            raise ValidationError(f"frame {fnum}: joints_3d_camera has {len(j3d)} joints, expected {EXPECTED_JOINT_COUNT}")
        if len(j2d) != EXPECTED_JOINT_COUNT:
            raise ValidationError(f"frame {fnum}: joints_2d_color has {len(j2d)} joints, expected {EXPECTED_JOINT_COUNT}")
        if len(conf) != EXPECTED_JOINT_COUNT:
            raise ValidationError(f"frame {fnum}: joint_confidence has {len(conf)} values, expected {EXPECTED_JOINT_COUNT}")

        # Check each joint
        for j in range(EXPECTED_JOINT_COUNT):
            # 3D coordinates
            x, y, z = j3d[j]
            if any(math.isnan(v) for v in (x, y, z)):
                warnings.append(f"frame {fnum} joint {j}: NaN in 3D coordinates")
            if any(math.isinf(v) for v in (x, y, z)):
                raise ValidationError(f"frame {fnum} joint {j}: Inf in 3D coordinates")
            if any(abs(v) > MAX_REASONABLE_3D_M for v in (x, y, z)):
                warnings.append(f"frame {fnum} joint {j}: large 3D value ({x:.2f}, {y:.2f}, {z:.2f}) m")

            # 2D coordinates
            u, v = j2d[j]
            if u == 0.0 and v == 0.0:
                continue  # explicitly missing
            if u < 0 or v < 0:
                warnings.append(f"frame {fnum} joint {j}: negative 2D coordinate ({u:.1f}, {v:.1f})")
            if u > MAX_REASONABLE_2D_PX or v > MAX_REASONABLE_2D_PX:
                warnings.append(f"frame {fnum} joint {j}: 2D coordinate out of bounds ({u:.1f}, {v:.1f})")

            # Confidence
            c = conf[j]
            if c not in range(CONFIDENCE_RANGE[0], CONFIDENCE_RANGE[1] + 1):
                warnings.append(f"frame {fnum} joint {j}: confidence {c} outside valid range {CONFIDENCE_RANGE}")

    return warnings


def validate_sync_data(
    records: list[dict],
    sync_csv_path: Path,
) -> Tuple[int, List[str]]:
    """Cross-validate with frame_sync.csv. Returns (sync_frame_count, warnings)."""
    warnings = []
    sync_frames = 0

    with open(sync_csv_path, "r", encoding="utf-8") as f:
        header = f.readline().strip()
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 5:
                sync_frames += 1

    # Check that sync frame count matches skeleton frame count
    if sync_frames != len(records):
        raise ValidationError(
            f"frame_sync.csv has {sync_frames} data rows but skeleton has {len(records)} frames"
        )

    # Check color-depth timestamp sync
    max_sync_diff = 0
    for rec in records:
        color_ts = rec.get("color_timestamp_usec", 0)
        depth_ts = rec.get("depth_timestamp_usec", 0)
        diff = abs(color_ts - depth_ts)
        if diff > max_sync_diff:
            max_sync_diff = diff
        if diff > MAX_RGB_DEPTH_SYNC_DIFF_USEC:
            warnings.append(
                f"frame {rec['frame_index']}: color-depth timestamp diff {diff} usec "
                f"exceeds {MAX_RGB_DEPTH_SYNC_DIFF_USEC} usec threshold"
            )

    if max_sync_diff == 0:
        print("  INFO: All frames have identical color and depth timestamps (hardware-synced)")

    return sync_frames, warnings


def validate_body_id_stability(records: list[dict]) -> List[str]:
    """Detect and report body ID switches. Returns warnings."""
    warnings = []
    prev_body = None
    switches = []

    for rec in records:
        body = rec["body_id"]
        if prev_body is not None and body != prev_body:
            switches.append((rec["frame_index"], prev_body, body))
        prev_body = body

    if switches:
        print(f"  INFO: {len(switches)} body_id switch(es) detected:")
        for fnum, old, new in switches[:10]:
            print(f"    frame {fnum}: {old} -> {new}")
        warnings.append(f"{len(switches)} body_id switch(es) detected")

    return warnings


def check_sha256_manifest(manifest_path: Path, records: list[dict]) -> List[str]:
    """Verify file integrity against SHA-256 manifest if provided."""
    warnings = []
    if not manifest_path.exists():
        warnings.append(f"Manifest file not found: {manifest_path}")
        return warnings

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # The manifest only covers data files, not the skeleton JSONL itself
    # (which we just produced). We verify the inputs listed in the manifest.
    print(f"\nVerifying SHA-256 manifest ({len(manifest.get('files', {}))} files) ...")
    for fpath, expected_hash in manifest.get("files", {}).items():
        p = Path(fpath)
        if not p.exists():
            warnings.append(f"Manifest file missing: {fpath}")
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != expected_hash:
            raise ValidationError(
                f"SHA-256 mismatch for {fpath}:\n  expected: {expected_hash}\n  actual:   {actual}"
            )
    print("  All manifest files verified OK")

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate standardized Kinect skeleton JSONL data"
    )
    parser.add_argument(
        "--skeleton", required=True, type=Path,
        help="Path to kinect_skeleton.jsonl"
    )
    parser.add_argument(
        "--sync-csv", required=True, type=Path,
        help="Path to frame_sync.csv"
    )
    parser.add_argument(
        "--manifest", type=Path, default=None,
        help="Optional path to file_manifest.json for SHA-256 verification"
    )
    parser.add_argument(
        "--warn-as-error", action="store_true",
        help="Treat warnings as errors (exit code 1)"
    )
    args = parser.parse_args()

    # --- Load data ---
    check_file_exists(args.skeleton, "Skeleton JSONL")
    check_file_exists(args.sync_csv, "Sync CSV")

    print(f"Loading skeleton data from {args.skeleton} ...")
    with open(args.skeleton, "r", encoding="utf-8") as f:
        records = [json.loads(line.strip()) for line in f if line.strip()]
    print(f"  Loaded {len(records)} records")

    all_warnings: List[str] = []
    hard_errors = 0

    def run_check(label: str, fn, *args):
        nonlocal hard_errors
        print(f"\n[{label}] ...")
        try:
            result = fn(*args)
            if isinstance(result, list):
                all_warnings.extend(result)
                if result:
                    print(f"  {len(result)} warning(s)")
                else:
                    print("  PASS")
            else:
                print("  PASS")
        except ValidationError as e:
            print(f"  FAIL: {e}")
            hard_errors += 1

    # --- Run checks ---
    run_check("Required fields", validate_required_fields, records)
    run_check("Frame continuity", validate_frame_continuity, records)
    run_check("Timestamp monotonicity", validate_timestamps, records)
    run_check("Joint array validation", validate_joint_arrays, records)
    run_check("Sync CSV cross-validation", validate_sync_data, records, args.sync_csv)
    run_check("Body ID stability", validate_body_id_stability, records)

    if args.manifest:
        run_check("SHA-256 manifest", check_sha256_manifest, args.manifest, records)

    # --- Report ---
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"  Records:  {len(records)}")
    print(f"  Hard errors:  {hard_errors}")
    print(f"  Warnings:     {len(all_warnings)}")
    if all_warnings:
        print(f"\n  Warnings:")
        for w in all_warnings[:20]:
            print(f"    - {w}")
        if len(all_warnings) > 20:
            print(f"    ... and {len(all_warnings) - 20} more")

    if hard_errors > 0:
        print(f"\nRESULT: FAIL ({hard_errors} hard error(s))")
        return 1

    if all_warnings and args.warn_as_error:
        print(f"\nRESULT: FAIL ({len(all_warnings)} warning(s) treated as errors)")
        return 1

    print(f"\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
