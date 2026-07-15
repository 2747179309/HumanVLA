#!/usr/bin/env python3
"""Render skeleton overlay on RGB frames to produce a verification video.

Reads the merged kinect_skeleton.jsonl and corresponding color frames,
draws skeleton bones and joints (color-coded by confidence), and writes
an MP4 video for visual inspection.

Usage:
    python render_kinect_overlay.py \
        --skeleton data/azure_kinect/processed/K01/kinect_skeleton.jsonl \
        --color-dir /path/to/K01/color \
        --output results/azure_kinect/K01/kinect_skeleton_overlay.mp4 \
        [--fps 30] [--bone-set corrected]
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import cv2

from kinect_constants import (
    KINECT_BONES,
    KINECT_BONES_CORRECTED,
    KINECT_JOINT_COUNT,
    KinectConfidence,
)

# Confidence level → BGR color for joint circles
CONFIDENCE_COLORS = {
    KinectConfidence.NONE: (0, 0, 255),      # Red
    KinectConfidence.LOW: (0, 165, 255),      # Orange
    KinectConfidence.MEDIUM: (0, 255, 255),    # Yellow
    KinectConfidence.HIGH: (0, 255, 0),        # Green
}

BONE_COLOR = (0, 255, 0)       # Green
BONE_THICKNESS = 4
JOINT_RADIUS = 7
FONT = cv2.FONT_HERSHEY_SIMPLEX


def find_color_frame(
    color_dir: Path,
    frame_number: int,
) -> Path | None:
    """Find a color frame file by frame number, trying multiple naming patterns."""
    patterns = [
        color_dir / f"frame_{frame_number}.jpg",
        color_dir / f"frame_{frame_number:06d}.jpg",
        color_dir / f"frame_{frame_number}.png",
        color_dir / f"frame_{frame_number:06d}.png",
    ]
    for p in patterns:
        if p.exists():
            return p
    return None


def draw_skeleton(
    img,
    joints_2d: list,
    confidences: list,
    body_id: int,
    bones: list,
) -> None:
    """Draw skeleton bones and joints on an image."""
    # Draw bones
    for p_idx, c_idx in bones:
        if p_idx >= len(joints_2d) or c_idx >= len(joints_2d):
            continue
        p1 = (int(joints_2d[p_idx][0]), int(joints_2d[p_idx][1]))
        p2 = (int(joints_2d[c_idx][0]), int(joints_2d[c_idx][1]))
        if p1 != (0, 0) and p2 != (0, 0):
            cv2.line(img, p1, p2, BONE_COLOR, BONE_THICKNESS)

    # Draw joints
    for idx, pt in enumerate(joints_2d):
        p = (int(pt[0]), int(pt[1]))
        if p == (0, 0):
            continue
        conf = confidences[idx] if idx < len(confidences) else 0
        color = CONFIDENCE_COLORS.get(conf, (0, 0, 255))
        cv2.circle(img, p, JOINT_RADIUS, color, -1)

    # Draw body ID near neck (joint 3)
    if body_id != -1 and len(joints_2d) > 3:
        neck = (int(joints_2d[3][0]), int(joints_2d[3][1]))
        if neck != (0, 0):
            cv2.putText(img, f"Body ID: {body_id}",
                       (neck[0], neck[1] - 30),
                       FONT, 1.0, (255, 255, 0), 2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render Kinect skeleton overlay on RGB frames"
    )
    parser.add_argument(
        "--skeleton", required=True, type=Path,
        help="Path to kinect_skeleton.jsonl"
    )
    parser.add_argument(
        "--color-dir", required=True, type=Path,
        help="Directory containing color frame images"
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Output MP4 video path"
    )
    parser.add_argument(
        "--fps", type=float, default=30.0,
        help="Output video frame rate (default: 30)"
    )
    parser.add_argument(
        "--bone-set", choices=["legacy", "corrected"], default="corrected",
        help="Which bone topology to use (default: corrected)"
    )
    args = parser.parse_args()

    # Validate inputs
    if not args.skeleton.exists():
        print(f"ERROR: skeleton file not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)
    if not args.color_dir.exists():
        print(f"ERROR: color directory not found: {args.color_dir}", file=sys.stderr)
        sys.exit(1)

    bones = KINECT_BONES_CORRECTED if args.bone_set == "corrected" else KINECT_BONES

    # Load skeleton data
    print(f"Loading skeleton data from {args.skeleton} ...")
    with open(args.skeleton, "r", encoding="utf-8") as f:
        records = [json.loads(line.strip()) for line in f if line.strip()]
    print(f"  Loaded {len(records)} frames")

    # Get video dimensions from first available color frame
    # Scan records to find the first valid frame
    first_img = None
    test_frame = 1
    while first_img is None and test_frame <= len(records):
        img_path = find_color_frame(args.color_dir, test_frame)
        if img_path:
            first_img = cv2.imread(str(img_path))
        test_frame += 1

    if first_img is None:
        print(f"ERROR: no color frames found in {args.color_dir}", file=sys.stderr)
        sys.exit(1)

    height, width = first_img.shape[:2]
    print(f"  Video dimensions: {width}x{height}")

    # Create video writer
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(str(args.output), fourcc, args.fps, (width, height))

    rendered = 0
    skipped = 0

    for rec in records:
        body_id = rec["body_id"]
        source_fnum = rec.get("source_frame_index", rec.get("original_frame_number", rec["frame_index"] + 1))

        # Find color frame
        img_path = find_color_frame(args.color_dir, source_fnum)
        if img_path is None:
            skipped += 1
            # Use a black frame as fallback
            img = first_img.copy() * 0
        else:
            img = cv2.imread(str(img_path))
            if img is None:
                skipped += 1
                continue

        # Draw skeleton if valid
        if body_id != -1:
            joints_2d = rec.get("joints_2d_color", [])
            confidences = rec.get("joint_confidence", [])
            if len(joints_2d) == KINECT_JOINT_COUNT:
                draw_skeleton(img, joints_2d, confidences, body_id, bones)

        # Draw overlay text
        fnum_text = f"Frame: {source_fnum} | {rec['frame_index']}"
        cv2.putText(img, fnum_text, (50, 50), FONT, 1.0, (0, 255, 255), 2)

        # Confidence legend (bottom-left)
        legend_y = height - 120
        cv2.putText(img, "Confidence:", (20, legend_y), FONT, 0.6, (255, 255, 255), 1)
        for i, (level, color) in enumerate([
            ("HIGH", (0, 255, 0)),
            ("MEDIUM", (0, 255, 255)),
            ("LOW", (0, 165, 255)),
            ("NONE", (0, 0, 255)),
        ]):
            cy = legend_y + 20 + i * 22
            cv2.circle(img, (30, cy - 6), 5, color, -1)
            cv2.putText(img, level, (42, cy), FONT, 0.5, (255, 255, 255), 1)

        video_writer.write(img)
        rendered += 1

    video_writer.release()

    print(f"\nDone. Rendered {rendered} frames ({skipped} skipped)")
    print(f"  Output: {args.output}")
    print(f"  Bone set: {args.bone_set}")


if __name__ == "__main__":
    main()
