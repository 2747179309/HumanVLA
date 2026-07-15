#!/usr/bin/env python3
"""Merge 2D and 3D skeleton JSONL files into a unified per-frame record.

Replaces the previous zip()-based merging with explicit frame_index matching.
Each output record contains both joints_2d_color and joints_3d_camera for the
same frame.

Usage:
    python merge_kinect_skeleton.py \
        --2d-input data/azure_kinect/processed/K01/skeleton_2d_raw.jsonl \
        --3d-input data/azure_kinect/processed/K01/skeleton_3d_raw.jsonl \
        --sync-csv data/azure_kinect/processed/K01/frame_sync.csv \
        --output data/azure_kinect/processed/K01/kinect_skeleton.jsonl \
        --video-id K01_reach_grasp_001
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, returning list of records."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_sync_csv(path: Path) -> Dict[int, dict]:
    """Load frame_sync.csv, returning dict keyed by frame_index."""
    sync = {}
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 5:
                continue
            frame_idx = int(parts[0])
            sync[frame_idx] = {
                "color_timestamp_usec": int(parts[1]),
                "depth_timestamp_usec": int(parts[2]),
                "color_path": parts[3],
                "depth_path": parts[4],
            }
    return sync


def build_index(records: list[dict], key: str = "frame_index") -> Dict[int, dict]:
    """Index records by a key field. Errors on duplicates."""
    index: Dict[int, dict] = {}
    for rec in records:
        k = rec.get(key)
        if k is None:
            print(f"ERROR: record missing field '{key}': {rec}", file=sys.stderr)
            sys.exit(1)
        if k in index:
            print(f"ERROR: duplicate {key}={k} found. Each frame must appear exactly once.", file=sys.stderr)
            sys.exit(1)
        index[k] = rec
    return index


def merge_skeletons(
    records_2d_indexed: Dict[int, dict],
    records_3d_indexed: Dict[int, dict],
    sync_data: Dict[int, dict],
    video_id: str,
) -> list[dict]:
    """Merge 2D and 3D records by explicit frame_index matching.

    Returns list of merged records sorted by frame_index.
    Exits with error if frames don't match.
    """
    all_frames = sorted(set(records_2d_indexed.keys()) | set(records_3d_indexed.keys()))

    only_2d = sorted(set(records_2d_indexed.keys()) - set(records_3d_indexed.keys()))
    only_3d = sorted(set(records_3d_indexed.keys()) - set(records_2d_indexed.keys()))

    if only_2d:
        print(f"ERROR: {len(only_2d)} frames exist ONLY in 2D file: {only_2d[:20]}{'...' if len(only_2d) > 20 else ''}", file=sys.stderr)
    if only_3d:
        print(f"ERROR: {len(only_3d)} frames exist ONLY in 3D file: {only_3d[:20]}{'...' if len(only_3d) > 20 else ''}", file=sys.stderr)
    if only_2d or only_3d:
        print("FATAL: 2D and 3D frame sets do not match. Refusing to merge.", file=sys.stderr)
        sys.exit(1)

    merged = []
    warnings = []

    # Normalize to 0-based indexing: the spec requires frame_index starting at 0.
    # Raw data may use 1-based indexing. source_frame_index preserves the original.
    min_raw_frame = min(all_frames) if all_frames else 0

    for new_idx, raw_frame_idx in enumerate(all_frames):
        r2d = records_2d_indexed[raw_frame_idx]
        r3d = records_3d_indexed[raw_frame_idx]

        # Cross-validate timestamps
        ts_2d = r2d.get("timestamp_usec")
        ts_3d = r3d.get("timestamp_usec")
        if ts_2d != ts_3d:
            warnings.append(f"source_frame {raw_frame_idx}: timestamp mismatch 2D={ts_2d} vs 3D={ts_3d}")

        # Cross-validate body_id
        body_2d = r2d.get("body_id")
        body_3d = r3d.get("body_id")
        if body_2d != body_3d:
            warnings.append(f"source_frame {raw_frame_idx}: body_id mismatch 2D={body_2d} vs 3D={body_3d}")

        # Build sync info — look up by original frame number
        s = sync_data.get(raw_frame_idx, {})
        color_ts = s.get("color_timestamp_usec", ts_3d)
        depth_ts = s.get("depth_timestamp_usec", ts_3d)
        color_path = s.get("color_path", "")
        depth_path = s.get("depth_path", "")

        merged_frame = {
            "video_id": video_id,
            "frame_index": new_idx,                        # 0-based, contiguous
            "source_frame_index": raw_frame_idx,           # original frame number preserved
            "timestamp_usec": ts_3d,
            "color_timestamp_usec": color_ts,
            "depth_timestamp_usec": depth_ts,
            "color_path": color_path,
            "depth_path": depth_path,
            "body_id": body_3d,
            "joints_3d_camera": r3d.get("joints_3d_camera", []),
            "joints_2d_color": r2d.get("joints_2d_color", []),
            "joint_confidence": r3d.get("joint_confidence", []),
        }

        # Validate joint counts
        if body_3d != -1:
            n3d = len(merged_frame["joints_3d_camera"])
            n2d = len(merged_frame["joints_2d_color"])
            nc = len(merged_frame["joint_confidence"])
            if n3d != 32 or n2d != 32 or nc != 32:
                warnings.append(
                    f"frame {frame_idx}: joint count anomaly 3D={n3d}, 2D={n2d}, conf={nc}"
                )

        merged.append(merged_frame)

    if warnings:
        print(f"WARNING: {len(warnings)} issue(s) found during merge:", file=sys.stderr)
        for w in warnings[:30]:
            print(f"  - {w}", file=sys.stderr)
        if len(warnings) > 30:
            print(f"  ... and {len(warnings) - 30} more", file=sys.stderr)

    return merged


def validate_output(merged: list[dict]) -> bool:
    """Run integrity checks on merged output. Returns True if all pass."""
    ok = True
    prev_ts = -1
    prev_body = None

    for i, rec in enumerate(merged):
        # frame_index continuity
        if rec["frame_index"] != i:
            print(f"ERROR: frame_index discontinuity at record {i}: got {rec['frame_index']}", file=sys.stderr)
            ok = False

        # timestamp monotonicity
        ts = rec["timestamp_usec"]
        if ts <= prev_ts:
            print(f"ERROR: timestamp not monotonic at record {i}: {ts} <= {prev_ts}", file=sys.stderr)
            ok = False
        prev_ts = ts

        # body_id switch detection
        if prev_body is not None and rec["body_id"] != prev_body:
            print(f"INFO: body_id switch at frame {rec['frame_index']}: {prev_body} -> {rec['body_id']}")
        prev_body = rec["body_id"]

    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge 2D and 3D Kinect skeleton JSONL files with explicit frame matching"
    )
    parser.add_argument(
        "--2d-input", required=True, type=Path,
        help="Path to skeleton_2d_raw.jsonl"
    )
    parser.add_argument(
        "--3d-input", required=True, type=Path,
        help="Path to skeleton_3d_raw.jsonl"
    )
    parser.add_argument(
        "--sync-csv", required=True, type=Path,
        help="Path to frame_sync.csv"
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Output path for merged kinect_skeleton.jsonl"
    )
    parser.add_argument(
        "--video-id", required=True, type=str,
        help="Video identifier (e.g. K01_reach_grasp_001)"
    )
    args = parser.parse_args()

    # Validate inputs exist
    input_2d = getattr(args, "2d_input")
    input_3d = getattr(args, "3d_input")
    for path, label in [
        (input_2d, "2D input"),
        (input_3d, "3D input"),
        (args.sync_csv, "sync CSV"),
    ]:
        if not path.exists():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    print(f"Loading 2D records from {input_2d} ...")
    records_2d = load_jsonl(input_2d)
    print(f"  Loaded {len(records_2d)} records")

    print(f"Loading 3D records from {input_3d} ...")
    records_3d = load_jsonl(input_3d)
    print(f"  Loaded {len(records_3d)} records")

    print(f"Loading sync data from {args.sync_csv} ...")
    sync_data = load_sync_csv(args.sync_csv)
    print(f"  Loaded {len(sync_data)} sync entries")

    # Index by frame_index
    idx_2d = build_index(records_2d, "frame_index")
    idx_3d = build_index(records_3d, "frame_index")

    print(f"\nMerging {len(idx_2d)} 2D frames with {len(idx_3d)} 3D frames ...")
    merged = merge_skeletons(idx_2d, idx_3d, sync_data, args.video_id)
    print(f"  Merged {len(merged)} frames")

    print("Validating merged output ...")
    if not validate_output(merged):
        print("FATAL: validation failed. Output NOT written.", file=sys.stderr)
        sys.exit(1)

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in merged:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nDone. Wrote {len(merged)} frames to {args.output}")
    print(f"  video_id: {args.video_id}")
    print(f"  frame_index range: {merged[0]['frame_index']} – {merged[-1]['frame_index']}")
    print(f"  timestamp range: {merged[0]['timestamp_usec']} – {merged[-1]['timestamp_usec']} usec")


if __name__ == "__main__":
    main()
