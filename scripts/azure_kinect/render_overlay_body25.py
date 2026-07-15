#!/usr/bin/env python3
"""Render BODY_25 skeleton overlay on RGB frames — slim, readable review video.

Only renders joints that have valid BODY_25 mapping (excludes hand tips, back
joints, and other Kinect-only markers). Color-coded by confidence level.
Output matches teammate's format: 720p, H.264, moderate bitrate.

Usage:
    python render_overlay_body25.py \
        --skeleton data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
        --color-dir data/azure_kinect/processed/KVAL001/color \
        --output results/azure_kinect/KVAL001/skeleton_overlay.mp4 \
        --fps 30
"""

from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

# ── Path setup ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kinect_constants import (
    KINECT_JOINT_NAMES,
    KINECT_JOINT_COUNT,
    BODY25_JOINT_NAMES,
    BODY25_TO_KINECT,
    KinectConfidence,
)

# ── BODY_25 bones (OpenPose standard connections) ───────────────────────
BODY25_BONES = [
    # Torso
    (1, 8),    # Neck → MidHip
    (1, 0),    # Neck → Nose
    (0, 15),   # Nose → REye
    (0, 16),   # Nose → LEye
    (15, 17),  # REye → REar
    (16, 18),  # LEye → LEar
    # Arms
    (1, 2),    # Neck → RShoulder
    (2, 3),    # RShoulder → RElbow
    (3, 4),    # RElbow → RWrist
    (1, 5),    # Neck → LShoulder
    (5, 6),    # LShoulder → LElbow
    (6, 7),    # LElbow → LWrist
    # Legs
    (8, 9),    # MidHip → RHip
    (9, 10),   # RHip → RKnee
    (10, 11),  # RKnee → RAnkle
    (8, 12),   # MidHip → LHip
    (12, 13),  # LHip → LKnee
    (13, 14),  # LKnee → LAnkle
]

# Which BODY_25 joints are "essential" for upper-body task analysis
UPPER_BODY_JOINTS = {"Nose", "Neck", "RShoulder", "RElbow", "RWrist",
                      "LShoulder", "LElbow", "LWrist", "MidHip"}
# Leg joints shown but dimmed
LEG_JOINTS = {"RHip", "RKnee", "RAnkle", "LHip", "LKnee", "LAnkle"}
# Head details (eyes/ears) — optional, shown small
HEAD_JOINTS = {"REye", "LEye", "REar", "LEar"}

# ── Colors (BGR) ────────────────────────────────────────────────────────
CONFIDENCE_COLORS = {
    KinectConfidence.NONE:   (0, 0, 255),     # Red
    KinectConfidence.LOW:    (0, 140, 255),    # Orange
    KinectConfidence.MEDIUM: (0, 255, 255),    # Yellow
    KinectConfidence.HIGH:   (0, 255, 0),      # Green
}

BONE_COLOR_DEFAULT = (180, 180, 180)  # Grey for legs
BONE_COLOR_UPPER = (0, 220, 0)        # Green for upper body
FONT = cv2.FONT_HERSHEY_SIMPLEX

# ── BODY_25 → Kinect index mapping (bidirectional) ──────────────────────
# Build: for each BODY_25 joint, which Kinect index has the data
B25_TO_KINECT_IDX: dict[int, int] = {}
for b25_id, kinect_idx in BODY25_TO_KINECT.items():
    B25_TO_KINECT_IDX[b25_id] = kinect_idx


def get_b25_position(joints_2d: list, b25_id: int) -> tuple[float, float] | None:
    """Get 2D pixel position of a BODY_25 joint from Kinect 32-joint array."""
    kidx = B25_TO_KINECT_IDX.get(b25_id)
    if kidx is None or kidx >= len(joints_2d):
        return None
    u, v = joints_2d[kidx]
    if u == 0.0 and v == 0.0:
        return None
    return (u, v)


def get_b25_confidence(confidences: list, b25_id: int) -> int:
    """Get confidence level for a BODY_25 joint."""
    kidx = B25_TO_KINECT_IDX.get(b25_id)
    if kidx is None or kidx >= len(confidences):
        return KinectConfidence.NONE
    return confidences[kidx]


def find_color_frame(color_dir: Path, source_fnum: int) -> Path | None:
    """Find a color frame by its original frame number (source_frame_index)."""
    for fmt in [f"frame_{source_fnum:06d}.jpg",
                f"frame_{source_fnum}.jpg",
                f"frame_{source_fnum:06d}.png",
                f"frame_{source_fnum}.png"]:
        p = color_dir / fmt
        if p.exists():
            return p
    return None


def draw_skeleton_body25(img: np.ndarray, joints_2d: list, confidences: list) -> None:
    """Draw BODY_25 skeleton with confidence-colored joints."""
    # Determine line color per bone based on joint categories
    for (p_id, c_id) in BODY25_BONES:
        p_pos = get_b25_position(joints_2d, p_id)
        c_pos = get_b25_position(joints_2d, c_id)
        if p_pos is None or c_pos is None:
            continue

        p_name = BODY25_JOINT_NAMES[p_id]
        c_name = BODY25_JOINT_NAMES[c_id]

        # Upper body bones in green, legs in grey
        if p_name in UPPER_BODY_JOINTS and c_name in UPPER_BODY_JOINTS:
            color = BONE_COLOR_UPPER
            thickness = 3
        else:
            color = BONE_COLOR_DEFAULT
            thickness = 2

        p_px = (int(p_pos[0]), int(p_pos[1]))
        c_px = (int(c_pos[0]), int(c_pos[1]))
        cv2.line(img, p_px, c_px, color, thickness)

    # Draw joints (sized by importance)
    for b25_id in range(25):
        pos = get_b25_position(joints_2d, b25_id)
        if pos is None:
            continue
        name = BODY25_JOINT_NAMES[b25_id]
        conf = get_b25_confidence(confidences, b25_id)
        color = CONFIDENCE_COLORS.get(conf, (0, 0, 255))

        if name in UPPER_BODY_JOINTS:
            radius = 6
        elif name in LEG_JOINTS:
            radius = 3
        else:
            radius = 2  # eyes, ears

        cv2.circle(img, (int(pos[0]), int(pos[1])), radius, color, -1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render BODY_25 skeleton overlay for review video"
    )
    parser.add_argument("--skeleton", required=True, type=Path)
    parser.add_argument("--color-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--output-height", type=int, default=720,
                       help="Output video height in pixels (width auto-scaled)")
    args = parser.parse_args()

    if not args.skeleton.exists():
        print(f"ERROR: skeleton not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)
    if not args.color_dir.exists():
        print(f"ERROR: color dir not found: {args.color_dir}", file=sys.stderr)
        sys.exit(1)

    # Load skeleton
    with open(args.skeleton, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    print(f"Loaded {len(records)} skeleton frames")

    # Detect color frame naming pattern by scanning the directory
    all_colors = sorted([p for p in args.color_dir.iterdir()
                         if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if not all_colors:
        print(f"ERROR: no color frames in {args.color_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(all_colors)} color frames")

    # Determine scaling
    first_img = cv2.imread(str(all_colors[len(all_colors)//2]))  # middle frame
    if first_img is None:
        first_img = cv2.imread(str(all_colors[0]))
    in_h, in_w = first_img.shape[:2]
    out_h = args.output_height
    out_w = int(in_w * out_h / in_h)
    print(f"  Input: {in_w}x{in_h} → Output: {out_w}x{out_h}")

    # Build color frame lookup: source_frame_index → path
    color_map: dict[int, Path] = {}
    for cf in all_colors:
        stem = cf.stem  # e.g., "frame_000042"
        try:
            num = int(stem.split("_")[-1])
            color_map[num] = cf
        except (ValueError, IndexError):
            continue

    print(f"  Color map: {len(color_map)} frames indexed")

    # Create writer — prefer ffmpeg pipe with H.264 for small files
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Try to use ffmpeg subprocess for H.264 encoding
    use_ffmpeg = False
    ffmpeg_proc = None
    try:
        import subprocess
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{out_w}x{out_h}", "-pix_fmt", "bgr24",
            "-r", str(args.fps),
            "-i", "-",  # stdin
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(args.output),
        ]
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        use_ffmpeg = True
        print("  Using ffmpeg libx264 encoder")
    except Exception:
        pass

    if not use_ffmpeg:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(args.output), fourcc, args.fps, (out_w, out_h))

    rendered = 0
    skipped_color = 0
    skipped_body = 0

    for rec in records:
        body_id = rec["body_id"]
        src_fnum = rec.get("source_frame_index", rec["frame_index"] + 1)

        # Find matching color frame
        cf_path = color_map.get(src_fnum)
        if cf_path is None:
            # Try nearby frames (±1)
            for offset in [1, -1, 2, -2]:
                cf_path = color_map.get(src_fnum + offset)
                if cf_path:
                    break
        if cf_path is None:
            skipped_color += 1
            continue

        img = cv2.imread(str(cf_path))
        if img is None:
            skipped_color += 1
            continue

        # Draw skeleton if body detected
        if body_id != -1:
            joints_2d = rec.get("joints_2d_color", [])
            confidences = rec.get("joint_confidence", [])
            if len(joints_2d) == KINECT_JOINT_COUNT:
                draw_skeleton_body25(img, joints_2d, confidences)
        else:
            skipped_body += 1

        # Overlay: frame counter (top-left)
        cv2.putText(img, f"{args.skeleton.parent.name} | Frame {src_fnum}/{len(records)}",
                   (20, 30), FONT, 0.7, (255, 255, 255), 2)

        # Overlay: body ID (top-right if valid)
        if body_id != -1:
            cv2.putText(img, f"Body: {body_id}",
                       (out_w - 150 if out_w > 200 else out_w - 100, 30),
                       FONT, 0.6, (0, 255, 0), 2)

        # Confidence legend (bottom-left)
        legend_x, legend_y = 15, out_h - 90
        cv2.rectangle(img, (legend_x - 3, legend_y - 18),
                     (legend_x + 130, legend_y + 85), (30, 30, 30), -1)
        cv2.putText(img, "Conf:", (legend_x, legend_y), FONT, 0.45, (200, 200, 200), 1)
        for i, (label, color) in enumerate([
            ("HIGH", (0, 255, 0)), ("MEDIUM", (0, 255, 255)),
            ("LOW", (0, 140, 255)), ("NONE", (0, 0, 255)),
        ]):
            cy = legend_y + 16 + i * 16
            cv2.circle(img, (legend_x + 6, cy - 4), 4, color, -1)
            cv2.putText(img, label, (legend_x + 15, cy), FONT, 0.4, (200, 200, 200), 1)

        # Resize and write
        img_out = cv2.resize(img, (out_w, out_h))
        if use_ffmpeg:
            ffmpeg_proc.stdin.write(img_out.tobytes())
        else:
            writer.write(img_out)
        rendered += 1

    if use_ffmpeg:
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()
    else:
        writer.release()

    sz_mb = args.output.stat().st_size / 1e6 if args.output.exists() else 0
    print(f"\nDone: {args.output} ({sz_mb:.1f} MB)")
    print(f"  Rendered: {rendered} frames")
    print(f"  Skipped (no color): {skipped_color}")
    print(f"  Skipped (no body): {skipped_body}")


if __name__ == "__main__":
    main()
