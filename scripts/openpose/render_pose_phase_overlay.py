#!/usr/bin/env python3
"""Render only trusted upper-body observations, phase labels, and unmatched poses."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

UPPER_BODY_EDGES = (
    (1, 0), (1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (6, 7),
    (0, 15), (15, 17), (0, 16), (16, 18),
)
VISIBLE_JOINT_IDS = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 15, 16, 17, 18})
CORE_JOINTS = {"Neck": 1, "RShoulder": 2, "RElbow": 3, "RWrist": 4}
STATUS_COLORS = {"valid": (40, 210, 40), "low_quality": (0, 215, 255), "missing": (150, 150, 150)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the T06C merged P001 pose/phase overlay as H.264.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--subject-jsonl", required=True, type=Path)
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
    parser.add_argument("--font", type=Path, default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def draw_skeleton(frame: np.ndarray, keypoints: list[list[float]], mask: list[str], unmatched: bool = False) -> None:
    for first, second in UPPER_BODY_EDGES:
        if keypoints[first][2] <= 0 or keypoints[second][2] <= 0:
            continue
        color = (200, 40, 200) if unmatched else STATUS_COLORS[
            "low_quality" if "low_quality" in {mask[first], mask[second]} else "valid"
        ]
        cv2.line(frame, tuple(map(round, keypoints[first][:2])), tuple(map(round, keypoints[second][:2])), color, 3, cv2.LINE_AA)
    for index, (x, y, confidence) in enumerate(keypoints):
        if index not in VISIBLE_JOINT_IDS or confidence <= 0:
            continue
        color = (200, 40, 200) if unmatched else STATUS_COLORS[mask[index]]
        cv2.circle(frame, (round(x), round(y)), 5 if index in CORE_JOINTS.values() else 3, color, -1, cv2.LINE_AA)


def put_panel_text(frame: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]], font_path: Path) -> np.ndarray:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((18, 15, 845, 232), radius=12, fill=(0, 0, 0, 175))
    font = ImageFont.truetype(str(font_path), 25)
    for row, (line, bgr) in enumerate(lines):
        draw.text((35, 27 + row * 38), line, font=font, fill=(bgr[2], bgr[1], bgr[0], 255))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def main() -> int:
    args = parse_args()
    for path in (args.video, args.subject_jsonl, args.association_jsonl, args.font):
        if not path.exists():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    records = load_jsonl(args.subject_jsonl)
    if len(records) != args.expected_frames or [row["frame_index"] for row in records] != list(range(args.expected_frames)):
        raise ValueError("subject JSONL does not cover every frame exactly once")
    extras: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in load_jsonl(args.association_jsonl):
        if record["match_status"] == "unmatched_pose":
            extras[record["frame_index"]].append(record)

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {args.video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        str(args.output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame_index, record in enumerate(records):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"video decode stopped at frame {frame_index}")
            box = record["bbox_xyxy"]
            if box is not None:
                cv2.rectangle(frame, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), (50, 220, 50), 3, cv2.LINE_AA)
                cv2.putText(frame, "track_id=1  P001", (round(box[0]), max(25, round(box[1]) - 9)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (50, 220, 50), 2, cv2.LINE_AA)
            if record["match_status"] == "matched":
                draw_skeleton(frame, record["keypoints_raw"], record["quality_mask"])
            for extra in extras.get(frame_index, []):
                draw_skeleton(frame, extra["keypoints"], ["valid"] * 25, unmatched=True)
                pose_box = extra["pose_bbox_xyxy"]
                if pose_box:
                    cv2.putText(frame, f"unmatched_pose index={extra['pose_index']}", (round(pose_box[0]), max(25, round(pose_box[1]) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (200, 40, 200), 2, cv2.LINE_AA)
            core_line = "  ".join(f"{name}:{record['core_joint_status'][name]}" for name in CORE_JOINTS)
            warning = "" if record["frame_quality_status"] == "valid" else f"WARNING: {record['frame_quality_status']} ({record['exclusion_reason']})"
            lines = [
                (f"frame_index={frame_index}  phase={record['phase_label']}  P001", (255, 255, 255)),
                (record["phase_text_en"], (255, 255, 255)),
                (record["phase_text_zh"], (255, 255, 255)),
                (core_line, STATUS_COLORS[record["frame_quality_status"]]),
                ((warning or "quality: valid") + " | observed upper body only", STATUS_COLORS[record["frame_quality_status"]]),
            ]
            frame = put_panel_text(frame, lines, args.font)
            assert process.stdin is not None
            process.stdin.write(frame.tobytes())
        ok, _ = capture.read()
        if ok:
            raise RuntimeError("source video has more frames than expected")
    finally:
        capture.release()
        if process.stdin:
            process.stdin.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    return_code = process.wait()
    if return_code:
        raise RuntimeError(f"ffmpeg exited {return_code}: {stderr}")
    print(json.dumps({"output": str(args.output), "frames": len(records), "fps": fps, "resolution": [width, height]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
