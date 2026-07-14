#!/usr/bin/env python3
"""Render raw upper-limb skeletons and a 30-frame normalized trajectory inset."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

STATUS_COLORS = {"valid": (40, 210, 40), "low_quality": (0, 215, 255), "missing": (150, 150, 150)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render unfiltered T07A current skeleton and last-30-frame normalized history."
    )
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--trajectory-jsonl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
    parser.add_argument("--history-frames", type=int, default=30)
    parser.add_argument("--font", type=Path, default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def get_bounds(rows: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    points = [(0.0, 0.0)]
    for row in rows:
        for prefix in ("relbow", "rwrist"):
            x, y = row[f"{prefix}_x_norm"], row[f"{prefix}_y_norm"]
            if x is not None:
                points.append((float(x), float(y)))
    xs, ys = zip(*points)
    x_padding = max(0.1, (max(xs) - min(xs)) * 0.08)
    y_padding = max(0.1, (max(ys) - min(ys)) * 0.08)
    return min(xs) - x_padding, max(xs) + x_padding, min(ys) - y_padding, max(ys) + y_padding


def map_norm(
    x: float, y: float, bounds: tuple[float, float, float, float], panel: tuple[int, int, int, int]
) -> tuple[int, int]:
    x_min, x_max, y_min, y_max = bounds
    left, top, width, height = panel
    px = left + int(round((x - x_min) / (x_max - x_min) * width))
    py = top + int(round((y - y_min) / (y_max - y_min) * height))
    return px, py


def draw_current_skeleton(frame: np.ndarray, row: dict[str, Any]) -> None:
    def xy(prefix: str) -> tuple[int, int] | None:
        x, y = row[f"{prefix}_x_px"], row[f"{prefix}_y_px"]
        return None if x is None else (round(x), round(y))

    neck, right_shoulder = xy("neck"), xy("rshoulder")
    left_shoulder, elbow, wrist = xy("lshoulder"), xy("relbow"), xy("rwrist")
    if neck and left_shoulder:
        cv2.line(frame, neck, left_shoulder, (40, 210, 40), 3, cv2.LINE_AA)
    if neck and right_shoulder:
        cv2.line(frame, neck, right_shoulder, (40, 210, 40), 3, cv2.LINE_AA)
    elbow_color = STATUS_COLORS["low_quality"] if row["relbow_effective_status"] != "valid" else STATUS_COLORS["valid"]
    if right_shoulder and elbow:
        cv2.line(frame, right_shoulder, elbow, elbow_color, 4, cv2.LINE_AA)
    if elbow and wrist:
        cv2.line(frame, elbow, wrist, STATUS_COLORS["valid"], 4, cv2.LINE_AA)
    for location, color, radius in (
        (neck, STATUS_COLORS["valid"], 5), (right_shoulder, STATUS_COLORS["valid"], 5),
        (left_shoulder, STATUS_COLORS["valid"], 5), (elbow, elbow_color, 7),
        (wrist, STATUS_COLORS["valid"], 7),
    ):
        if location:
            cv2.circle(frame, location, radius, color, -1, cv2.LINE_AA)


def draw_history(
    frame: np.ndarray, rows: list[dict[str, Any]], frame_index: int, history_frames: int,
    bounds: tuple[float, float, float, float],
) -> None:
    outer = (800, 20, 460, 335)
    panel = (830, 65, 400, 245)
    cv2.rectangle(frame, (outer[0], outer[1]), (outer[0] + outer[2], outer[1] + outer[3]), (22, 28, 35), -1)
    cv2.rectangle(frame, (panel[0], panel[1]), (panel[0] + panel[2], panel[1] + panel[3]), (42, 49, 58), -1)
    origin = map_norm(0.0, 0.0, bounds, panel)
    cv2.line(frame, (panel[0], origin[1]), (panel[0] + panel[2], origin[1]), (105, 115, 125), 1)
    cv2.line(frame, (origin[0], panel[1]), (origin[0], panel[1] + panel[3]), (105, 115, 125), 1)
    cv2.drawMarker(frame, origin, (240, 240, 240), cv2.MARKER_STAR, 14, 2, cv2.LINE_AA)
    start = max(0, frame_index - history_frames + 1)
    history = rows[start:frame_index + 1]
    for prefix, marker in (("relbow", "E"), ("rwrist", "W")):
        previous: tuple[int, int, int] | None = None
        for offset, row in enumerate(history):
            x, y = row[f"{prefix}_x_norm"], row[f"{prefix}_y_norm"]
            if x is None:
                previous = None
                continue
            current = map_norm(float(x), float(y), bounds, panel)
            age_scale = (offset + 1) / len(history)
            base = STATUS_COLORS[row["trajectory_quality"]]
            color = tuple(max(25, int(component * (0.28 + 0.72 * age_scale))) for component in base)
            if previous is not None and row["frame_index"] == previous[2] + 1:
                cv2.line(frame, previous[:2], current, color, 2, cv2.LINE_AA)
            cv2.circle(frame, current, 4 if prefix == "rwrist" else 3, color, -1, cv2.LINE_AA)
            previous = (current[0], current[1], row["frame_index"])
        current_row = rows[frame_index]
        if current_row[f"{prefix}_x_norm"] is not None:
            current = map_norm(
                float(current_row[f"{prefix}_x_norm"]), float(current_row[f"{prefix}_y_norm"]), bounds, panel
            )
            cv2.putText(frame, marker, (current[0] + 5, current[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, "Normalized history: last 30 frames", (820, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (245, 245, 245), 2, cv2.LINE_AA)
    cv2.putText(frame, "E=RElbow  W=RWrist  gaps not bridged", (815, 337), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (210, 215, 220), 1, cv2.LINE_AA)


def put_text_panel(frame: np.ndarray, row: dict[str, Any], font_path: Path) -> np.ndarray:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((18, 15, 765, 239), radius=12, fill=(0, 0, 0, 180))
    font = ImageFont.truetype(str(font_path), 25)
    status = row["trajectory_quality"]
    bgr = STATUS_COLORS[status]
    rgb_color = (bgr[2], bgr[1], bgr[0], 255)
    wrist = "missing" if row["rwrist_x_norm"] is None else f"({row['rwrist_x_norm']:.3f}, {row['rwrist_y_norm']:.3f})"
    elbow = "missing" if row["relbow_x_norm"] is None else f"({row['relbow_x_norm']:.3f}, {row['relbow_y_norm']:.3f})"
    neck_motion = (
        "missing"
        if row["neck_dx_from_first_valid_px"] is None
        else (
            f"d_first=({row['neck_dx_from_first_valid_px']:.1f},"
            f" {row['neck_dy_from_first_valid_px']:.1f})px"
            f"  step={row['neck_frame_displacement_px']:.1f}px"
            if row["neck_frame_displacement_px"] is not None
            else f"d_first=({row['neck_dx_from_first_valid_px']:.1f}, {row['neck_dy_from_first_valid_px']:.1f})px  step=N/A"
        )
    )
    lines = [
        (f"frame={row['frame_index']}  phase={row['phase_label']}  T07A raw trajectory", (255, 255, 255, 255)),
        (f"trajectory={status}  reason={row['quality_reason'] or 'none'}", rgb_color),
        (f"RElbow norm={elbow}  status={row['relbow_effective_status']}", (255, 255, 255, 255)),
        (f"RWrist norm={wrist}  status={row['rwrist_effective_status']}", (255, 255, 255, 255)),
        (f"Neck absolute motion: {neck_motion}", (255, 255, 255, 255)),
        ("Neck origin | shoulder-width scale | RAW: no interpolation/filter", (210, 220, 230, 255)),
    ]
    for index, (text, color) in enumerate(lines):
        draw.text((35, 27 + index * 34), text, font=font, fill=color)
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def main() -> int:
    args = parse_args()
    for path in (args.video, args.trajectory_jsonl, args.font):
        if not path.exists():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite: {args.output}")
    if args.history_frames <= 0:
        raise ValueError("history-frames must be positive")
    rows = load_jsonl(args.trajectory_jsonl)
    if len(rows) != args.expected_frames or [row["frame_index"] for row in rows] != list(range(args.expected_frames)):
        raise ValueError("trajectory does not cover frames 0..344")
    bounds = get_bounds(rows)
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot decode source video: {args.video}")
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
        for frame_index, row in enumerate(rows):
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"source video decode stopped at frame {frame_index}")
            draw_current_skeleton(frame, row)
            draw_history(frame, rows, frame_index, args.history_frames, bounds)
            frame = put_text_panel(frame, row, args.font)
            assert process.stdin is not None
            process.stdin.write(frame.tobytes())
        if capture.read()[0]:
            raise RuntimeError("source video has more frames than trajectory")
    finally:
        capture.release()
        if process.stdin:
            process.stdin.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    return_code = process.wait()
    if return_code:
        raise RuntimeError(f"ffmpeg failed with {return_code}: {stderr}")
    print(json.dumps({
        "output": str(args.output), "frames": len(rows), "fps": fps,
        "resolution": [width, height], "history_frames": args.history_frames,
        "normalized_bounds": bounds,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
