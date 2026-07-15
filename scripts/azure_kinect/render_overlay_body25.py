#!/usr/bin/env python3
"""Render 5-joint arm skeleton overlay for Kinect validation review videos.

Only shows the 5 key task-relevant joints:
  Neck, RShoulder, RElbow, RWrist, LShoulder

Bones drawn: Neck→RShoulder→RElbow→RWrist (green, thick)
            Neck→LShoulder (green, thinner)

Confidence color coding:
  HIGH (3)   = Green
  MEDIUM (2) = Yellow
  LOW (1)    = Orange
  NONE (0)   = Red

Usage:
    python render_overlay_body25.py \
        --skeleton data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
        --color-dir data/azure_kinect/processed/KVAL001/color \
        --output results/azure_kinect/KVAL001/skeleton_overlay.mp4
"""

from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2

# ── 5 key joints (BODY_25 name → Kinect SDK index) ─────────────────────
KEY_JOINTS = {
    "Neck":       3,   # NECK
    "RShoulder":  9,   # SHOULDER_RIGHT
    "RElbow":     10,  # ELBOW_RIGHT
    "RWrist":     11,  # WRIST_RIGHT
    "LShoulder":  5,   # SHOULDER_LEFT
}

# Bones to draw: (parent_name, child_name)
BONES = [
    ("Neck", "RShoulder"),
    ("RShoulder", "RElbow"),
    ("RElbow", "RWrist"),
    ("Neck", "LShoulder"),
]

# Confidence → BGR color
CONF_COLORS = {
    3: (0, 255, 0),     # HIGH   = Green
    2: (0, 255, 255),   # MEDIUM = Yellow
    1: (0, 140, 255),   # LOW    = Orange
    0: (0, 0, 255),     # NONE   = Red
}

FONT = cv2.FONT_HERSHEY_SIMPLEX


def find_color_frame(color_dir: Path, source_fnum: int) -> Path | None:
    """Find a color frame by its source frame number."""
    for fmt in [f"frame_{source_fnum:06d}.jpg",
                f"frame_{source_fnum}.jpg",
                f"frame_{source_fnum:06d}.png"]:
        p = color_dir / fmt
        if p.exists():
            return p
    # Try nearby frames (±1, ±2) in case of timestamp drift
    for offset in [1, -1, 2, -2]:
        for fmt in [f"frame_{source_fnum + offset:06d}.jpg",
                    f"frame_{source_fnum + offset}.jpg"]:
            p = color_dir / fmt
            if p.exists():
                return p
    return None


def draw_skeleton(img, joints_2d: list, confidences: list) -> None:
    """Draw 5-joint arm skeleton with confidence colors and labels."""
    # Extract pixel positions for the 5 joints
    pos: dict[str, tuple[int, int] | None] = {}
    for name, kidx in KEY_JOINTS.items():
        u, v = joints_2d[kidx]
        if abs(u) < 0.01 and abs(v) < 0.01:
            pos[name] = None
        else:
            pos[name] = (int(u), int(v))

    # Draw bones
    for pa, pb in BONES:
        if pos.get(pa) and pos.get(pb):
            thickness = 4 if pb == "RWrist" else 3
            cv2.line(img, pos[pa], pos[pb], (0, 220, 0), thickness)

    # Draw joints (size based on importance, color by confidence)
    for name, kidx in KEY_JOINTS.items():
        if pos[name] is None:
            continue
        conf = confidences[kidx] if kidx < len(confidences) else 0
        color = CONF_COLORS.get(conf, (0, 0, 255))

        if name in ("RWrist", "RElbow"):
            radius = 9
        elif name == "RShoulder":
            radius = 7
        else:
            radius = 6

        cv2.circle(img, pos[name], radius, color, -1)
        cv2.circle(img, pos[name], radius, (255, 255, 255), 1)  # white outline

        # Label
        label = name
        cv2.putText(img, label, (pos[name][0] + 12, pos[name][1] + 5),
                   FONT, 0.5, (255, 255, 255), 2)
        cv2.putText(img, label, (pos[name][0] + 12, pos[name][1] + 5),
                   FONT, 0.5, color, 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render 5-joint arm skeleton overlay for Kinect review video"
    )
    parser.add_argument("--skeleton", required=True, type=Path)
    parser.add_argument("--color-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--output-height", type=int, default=720)
    parser.add_argument("--no-reencode", action="store_true",
                       help="Skip ffmpeg H.264 re-encoding")
    args = parser.parse_args()

    if not args.skeleton.exists():
        print(f"ERROR: skeleton not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)
    if not args.color_dir.exists():
        print(f"ERROR: color dir not found: {args.color_dir}", file=sys.stderr)
        sys.exit(1)

    video_id = args.skeleton.parent.name

    # Load skeleton
    with open(args.skeleton, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    n_total = len(records)
    n_body = sum(1 for r in records if r["body_id"] != -1)
    print(f"{video_id}: {n_total} frames ({n_body} with body)")

    # Build color frame index
    color_dir = args.color_dir
    color_idx: dict[int, Path] = {}
    for cf in sorted(color_dir.iterdir()):
        if cf.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        try:
            num = int(cf.stem.split("_")[-1])
            color_idx[num] = cf
        except (ValueError, IndexError):
            continue
    print(f"  Color frames: {len(color_idx)} indexed")

    # Get output dimensions from a middle frame
    mid_frames = sorted(color_idx.keys())
    if not mid_frames:
        print("ERROR: no color frames found", file=sys.stderr)
        sys.exit(1)
    sample_img = cv2.imread(str(color_idx[mid_frames[len(mid_frames)//2]]))
    if sample_img is None:
        sample_img = cv2.imread(str(color_idx[mid_frames[0]]))
    in_h, in_w = sample_img.shape[:2]
    out_h = args.output_height
    out_w = int(in_w * out_h / in_h)
    print(f"  Resolution: {in_w}x{in_h} → {out_w}x{out_h}")

    # ── Step 1: Render with OpenCV mp4v ──
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = args.output.with_suffix(".temp.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(temp_path), fourcc, args.fps, (out_w, out_h))
    if not writer.isOpened():
        print("ERROR: cannot create video writer", file=sys.stderr)
        sys.exit(1)

    rendered = 0
    skipped_color = 0
    skipped_body = 0

    for rec in records:
        sfn = rec.get("source_frame_index", rec["frame_index"] + 1)
        cf = color_idx.get(sfn)
        if cf is None:
            skipped_color += 1
            continue

        img = cv2.imread(str(cf))
        if img is None:
            skipped_color += 1
            continue

        body_id = rec["body_id"]

        if body_id != -1:
            j2d = rec.get("joints_2d_color", [])
            confs = rec.get("joint_confidence", [])
            if len(j2d) == 32:
                draw_skeleton(img, j2d, confs)
        else:
            skipped_body += 1

        # Frame counter
        cv2.putText(img, f"{video_id} | F{sfn}/{n_total}",
                   (20, 32), FONT, 0.65, (255, 255, 255), 2)

        # Body status
        if body_id != -1:
            cv2.putText(img, f"Body {body_id}",
                       (out_w - 150 if out_w > 200 else 20, 32),
                       FONT, 0.55, (0, 255, 0), 2)

        # Confidence legend (bottom-left)
        lx, ly = 15, out_h - 80
        cv2.rectangle(img, (lx-3, ly-16), (lx+115, ly+68), (25, 25, 25), -1)
        for i, (label, color) in enumerate([
            ("HIGH", (0, 255, 0)), ("MEDIUM", (0, 255, 255)),
            ("LOW", (0, 140, 255)), ("NONE", (0, 0, 255)),
        ]):
            cy = ly + i * 16
            cv2.circle(img, (lx+6, cy-4), 4, color, -1)
            cv2.putText(img, label, (lx+15, cy), FONT, 0.38, (200, 200, 200), 1)

        img_out = cv2.resize(img, (out_w, out_h))
        writer.write(img_out)
        rendered += 1

    writer.release()
    print(f"  Rendered: {rendered} frames ({skipped_color} skipped-color, {skipped_body} skipped-body)")

    # ── Step 2: Re-encode with ffmpeg H.264 for smaller file ──
    if not args.no_reencode:
        print("  Re-encoding with H.264 ...")
        result = subprocess.run([
            "ffmpeg", "-y", "-v", "error",
            "-i", str(temp_path),
            "-c:v", "libx264", "-preset", "medium", "-crf", "25",
            "-pix_fmt", "yuv420p",
            str(args.output),
        ], capture_output=True, text=True)
        if result.returncode == 0:
            temp_path.unlink()  # remove temp
            sz = args.output.stat().st_size / 1e6
            print(f"  Done: {args.output} ({sz:.1f} MB)")
        else:
            # ffmpeg failed, keep mp4v
            temp_path.rename(args.output)
            print(f"  H.264 failed, kept MPEG4: {args.output}")
            if result.stderr:
                print(f"  ffmpeg: {result.stderr[:200]}")
    else:
        temp_path.rename(args.output)
        sz = args.output.stat().st_size / 1e6
        print(f"  Done: {args.output} ({sz:.1f} MB)")


if __name__ == "__main__":
    main()
