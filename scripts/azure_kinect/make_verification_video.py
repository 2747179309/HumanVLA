#!/usr/bin/env python3
"""Render skeleton overlay from ROS2 live-recording data into a verification video.

This is for the ROS2 real-time skeleton recording workflow, distinct from the
offline MKV extraction pipeline handled by render_kinect_overlay.py.

Usage:
    python make_verification_video.py \
        --color-dir /path/to/datasets/VIDEO_NAME/color \
        --metadata-dir /path/to/datasets/VIDEO_NAME/metadata \
        --output /path/to/output/verification_result.mp4 \
        [--fps 30]
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import cv2

from kinect_constants import KINECT_BONES_CORRECTED, KINECT_JOINT_COUNT

BONE_COLOR = (0, 255, 0)
JOINT_COLOR = (0, 0, 255)
BONE_THICKNESS = 4
JOINT_RADIUS = 7


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render skeleton overlay from ROS2 recording data"
    )
    parser.add_argument(
        "--color-dir", required=True, type=Path,
        help="Directory containing color frame images"
    )
    parser.add_argument(
        "--metadata-dir", required=True, type=Path,
        help="Directory containing per-frame skeleton JSON files"
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Output MP4 video path"
    )
    parser.add_argument(
        "--fps", type=float, default=30.0,
        help="Output video frame rate (default: 30)"
    )
    args = parser.parse_args()

    if not args.color_dir.exists():
        print(f"ERROR: color directory not found: {args.color_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.metadata_dir.exists():
        print(f"ERROR: metadata directory not found: {args.metadata_dir}", file=sys.stderr)
        sys.exit(1)

    # Sort color files
    color_files = sorted([
        f for f in args.color_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png")
    ])
    if not color_files:
        print(f"ERROR: no image files found in {args.color_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(color_files)} color frames")

    # Get video dimensions from first frame
    first_img = cv2.imread(str(color_files[0]))
    if first_img is None:
        print(f"ERROR: cannot read first image: {color_files[0]}", file=sys.stderr)
        sys.exit(1)
    height, width = first_img.shape[:2]

    # Create writer
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(args.output), fourcc, args.fps, (width, height))

    rendered = 0
    for img_path in color_files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        # Extract frame index from filename (e.g. frame_000001.jpg -> 1)
        stem = img_path.stem
        try:
            frame_idx = int(stem.split("_")[-1])
        except (ValueError, IndexError):
            frame_idx = rendered + 1

        # Load corresponding skeleton JSON
        json_path = args.metadata_dir / f"frame_{frame_idx:06d}.json"
        if json_path.exists():
            with open(json_path, "r") as f:
                data = json.load(f)
            joints_2d = data.get("joints_2d_color", [])

            if len(joints_2d) > 0:
                # Draw bones
                for p_idx, c_idx in KINECT_BONES_CORRECTED:
                    if p_idx < len(joints_2d) and c_idx < len(joints_2d):
                        p1 = (int(joints_2d[p_idx][0]), int(joints_2d[p_idx][1]))
                        p2 = (int(joints_2d[c_idx][0]), int(joints_2d[c_idx][1]))
                        if p1 != (0, 0) and p2 != (0, 0):
                            cv2.line(img, p1, p2, BONE_COLOR, BONE_THICKNESS)

                # Draw joints
                for pt in joints_2d:
                    p = (int(pt[0]), int(pt[1]))
                    if p != (0, 0):
                        cv2.circle(img, p, JOINT_RADIUS, JOINT_COLOR, -1)

                # Body ID at neck
                if len(joints_2d) > 3:
                    neck = (int(joints_2d[3][0]), int(joints_2d[3][1]))
                    if neck != (0, 0):
                        cv2.putText(img, "Body ID: 1", (neck[0], neck[1] - 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

        cv2.putText(img, f"Frame: {frame_idx}", (50, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        writer.write(img)
        rendered += 1

    writer.release()
    print(f"Done. Rendered {rendered} frames to {args.output}")


if __name__ == "__main__":
    main()
