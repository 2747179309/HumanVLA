#!/usr/bin/env python3
"""Build human-review CSV and videos for T07A statistical jump candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

VIDEO_ID = "pick_place_pilot_v1_E001"
JOINT_PREFIX = {"RElbow": "relbow", "RWrist": "rwrist"}
CONFIDENCE_INDEX = {"RElbow": 2, "RWrist": 3}
CSV_FIELDS = [
    "candidate_id", "from_frame", "to_frame", "joint_name", "phase_before",
    "phase_after", "displacement_px", "displacement_norm", "confidence_before",
    "confidence_after", "shoulder_width_before", "shoulder_width_after",
    "neck_displacement_px", "automatic_trigger_reason", "manual_label",
    "manual_confidence", "manual_note", "review_start_frame", "review_end_frame",
    "clip_path",
]
MANUAL_FIELDS = ("manual_label", "manual_confidence", "manual_note")
COLORS = {
    "skeleton": (45, 220, 70), "joint": (30, 210, 255), "path": (255, 190, 40),
    "candidate": (35, 35, 245), "origin": (235, 235, 235), "panel": (35, 42, 50),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a blank human-review CSV, one slow clip per T07A jump candidate, "
            "and a concatenated review video. Trajectory inputs are read-only."
        )
    )
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--clips-dir", required=True, type=Path)
    parser.add_argument("--output-video", required=True, type=Path)
    parser.add_argument("--context-frames", type=int, default=5)
    parser.add_argument("--review-fps", type=float, default=6.0)
    parser.add_argument("--expected-candidates", type=int, default=12)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def ensure_output_policy(args: argparse.Namespace) -> None:
    outputs = [args.output_csv, args.output_video]
    existing_clips = list(args.clips_dir.glob("JUMP_*.mp4")) if args.clips_dir.exists() else []
    if not args.overwrite and (existing := [path for path in outputs if path.exists()] + existing_clips):
        raise FileExistsError("refusing to overwrite: " + ", ".join(map(str, existing)))
    if args.output_csv.exists() and args.overwrite:
        with args.output_csv.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                if any((row.get(field) or "").strip() for field in MANUAL_FIELDS):
                    raise ValueError("refusing to overwrite CSV containing manual review decisions")


def extract_candidates(
    summary: dict[str, Any], rows: list[dict[str, Any]], context: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    displacement = summary.get("per_frame_displacement", {})
    for joint_name in ("RElbow", "RWrist"):
        item = displacement.get(joint_name)
        if not isinstance(item, dict):
            raise ValueError(f"summary lacks per-frame displacement for {joint_name}")
        threshold = item.get("suspicious_jump_threshold")
        rule = item.get("suspicious_jump_rule")
        for jump in item.get("suspicious_jumps", []):
            from_frame = int(jump["from_frame"])
            to_frame = int(jump["to_frame"])
            if to_frame != from_frame + 1:
                raise ValueError(f"candidate {from_frame}->{to_frame} is not consecutive")
            before, after = rows[from_frame], rows[to_frame]
            prefix = JOINT_PREFIX[joint_name]
            before_xy = (before[f"{prefix}_x_px"], before[f"{prefix}_y_px"])
            after_xy = (after[f"{prefix}_x_px"], after[f"{prefix}_y_px"])
            if None in before_xy or None in after_xy:
                raise ValueError(f"candidate {joint_name} {from_frame}->{to_frame} lacks pixel coordinates")
            displacement_px = math.hypot(after_xy[0] - before_xy[0], after_xy[1] - before_xy[1])
            events.append({
                "from_frame": from_frame, "to_frame": to_frame, "joint_name": joint_name,
                "phase_before": before["phase_label"], "phase_after": after["phase_label"],
                "displacement_px": displacement_px,
                "displacement_norm": float(jump["distance_norm"]),
                "confidence_before": before["raw_confidence"][CONFIDENCE_INDEX[joint_name]],
                "confidence_after": after["raw_confidence"][CONFIDENCE_INDEX[joint_name]],
                "shoulder_width_before": before["shoulder_width_px"],
                "shoulder_width_after": after["shoulder_width_px"],
                "neck_displacement_px": after["neck_frame_displacement_px"],
                "automatic_trigger_reason": (
                    f"{rule}; {joint_name} displacement_norm={jump['distance_norm']:.9f} "
                    f"> threshold={threshold:.9f}"
                ),
                "manual_label": "", "manual_confidence": "", "manual_note": "",
                "review_start_frame": max(0, from_frame - context),
                "review_end_frame": min(len(rows) - 1, to_frame + context),
            })
    events.sort(key=lambda event: (event["to_frame"], event["joint_name"]))
    for index, event in enumerate(events, start=1):
        event["candidate_id"] = f"JUMP_{index:03d}"
    summary_frames = summary.get("suspicious_jump_frames")
    if sorted({event["to_frame"] for event in events}) != summary_frames:
        raise ValueError("candidate events do not reproduce summary suspicious_jump_frames")
    return events


def point(row: dict[str, Any], prefix: str) -> tuple[int, int] | None:
    x, y = row[f"{prefix}_x_px"], row[f"{prefix}_y_px"]
    return None if x is None else (round(x), round(y))


def draw_skeleton(frame: np.ndarray, row: dict[str, Any]) -> None:
    points = {name: point(row, prefix) for name, prefix in (
        ("Neck", "neck"), ("RShoulder", "rshoulder"), ("LShoulder", "lshoulder"),
        ("RElbow", "relbow"), ("RWrist", "rwrist"),
    )}
    for start, end in (
        ("Neck", "RShoulder"), ("Neck", "LShoulder"),
        ("RShoulder", "RElbow"), ("RElbow", "RWrist"),
    ):
        if points[start] and points[end]:
            cv2.line(frame, points[start], points[end], COLORS["skeleton"], 3, cv2.LINE_AA)
    for name, location in points.items():
        if location:
            cv2.circle(frame, location, 6, COLORS["joint"], -1, cv2.LINE_AA)
            cv2.putText(frame, name, (location[0] + 7, location[1] - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (245, 245, 245), 1, cv2.LINE_AA)


def draw_absolute_path(
    frame: np.ndarray, rows: list[dict[str, Any]], event: dict[str, Any],
) -> None:
    prefix = JOINT_PREFIX[event["joint_name"]]
    local = rows[event["review_start_frame"]:event["review_end_frame"] + 1]
    for before, after in zip(local, local[1:]):
        start, end = point(before, prefix), point(after, prefix)
        if start is None or end is None or after["frame_index"] != before["frame_index"] + 1:
            continue
        candidate_edge = (
            before["frame_index"] == event["from_frame"]
            and after["frame_index"] == event["to_frame"]
        )
        cv2.line(frame, start, end, COLORS["candidate"] if candidate_edge else COLORS["path"],
                 6 if candidate_edge else 2, cv2.LINE_AA)
    start = point(rows[event["from_frame"]], prefix)
    end = point(rows[event["to_frame"]], prefix)
    assert start is not None and end is not None
    cv2.circle(frame, start, 10, COLORS["candidate"], 2, cv2.LINE_AA)
    cv2.circle(frame, end, 10, COLORS["candidate"], -1, cv2.LINE_AA)
    cv2.putText(frame, "jump A", (start[0] + 12, start[1] + 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.48, COLORS["candidate"], 2, cv2.LINE_AA)
    cv2.putText(frame, "jump B", (end[0] + 12, end[1] + 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.48, COLORS["candidate"], 2, cv2.LINE_AA)


def normalized_bounds(rows: list[dict[str, Any]], event: dict[str, Any]) -> tuple[float, float, float, float]:
    prefix = JOINT_PREFIX[event["joint_name"]]
    points = [(0.0, 0.0)]
    for row in rows[event["review_start_frame"]:event["review_end_frame"] + 1]:
        x, y = row[f"{prefix}_x_norm"], row[f"{prefix}_y_norm"]
        if x is not None:
            points.append((float(x), float(y)))
    xs, ys = zip(*points)
    x_pad = max(0.08, (max(xs) - min(xs)) * 0.12)
    y_pad = max(0.08, (max(ys) - min(ys)) * 0.12)
    return min(xs) - x_pad, max(xs) + x_pad, min(ys) - y_pad, max(ys) + y_pad


def map_normalized(
    x: float, y: float, bounds: tuple[float, float, float, float],
    panel: tuple[int, int, int, int],
) -> tuple[int, int]:
    x_min, x_max, y_min, y_max = bounds
    left, top, width, height = panel
    return (
        left + round((x - x_min) / (x_max - x_min) * width),
        top + round((y - y_min) / (y_max - y_min) * height),
    )


def draw_normalized_panel(
    frame: np.ndarray, rows: list[dict[str, Any]], event: dict[str, Any],
) -> None:
    outer = (895, 330, 365, 370)
    panel = (925, 385, 305, 260)
    cv2.rectangle(frame, (outer[0], outer[1]), (outer[0] + outer[2], outer[1] + outer[3]),
                  COLORS["panel"], -1)
    cv2.putText(frame, f"{event['joint_name']} normalized local path", (910, 360),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 245, 245), 1, cv2.LINE_AA)
    bounds = normalized_bounds(rows, event)
    origin = map_normalized(0.0, 0.0, bounds, panel)
    cv2.drawMarker(frame, origin, COLORS["origin"], cv2.MARKER_STAR, 13, 2, cv2.LINE_AA)
    prefix = JOINT_PREFIX[event["joint_name"]]
    local = rows[event["review_start_frame"]:event["review_end_frame"] + 1]
    for before, after in zip(local, local[1:]):
        first = (before[f"{prefix}_x_norm"], before[f"{prefix}_y_norm"])
        second = (after[f"{prefix}_x_norm"], after[f"{prefix}_y_norm"])
        if None in first or None in second:
            continue
        start = map_normalized(float(first[0]), float(first[1]), bounds, panel)
        end = map_normalized(float(second[0]), float(second[1]), bounds, panel)
        candidate_edge = (
            before["frame_index"] == event["from_frame"]
            and after["frame_index"] == event["to_frame"]
        )
        cv2.line(frame, start, end, COLORS["candidate"] if candidate_edge else COLORS["path"],
                 5 if candidate_edge else 2, cv2.LINE_AA)
        cv2.circle(frame, end, 3, COLORS["candidate"] if candidate_edge else COLORS["path"], -1)
    cv2.putText(frame, "red = statistical candidate", (925, 675), cv2.FONT_HERSHEY_SIMPLEX,
                0.5, (235, 235, 235), 1, cv2.LINE_AA)


def draw_information(frame: np.ndarray, row: dict[str, Any], event: dict[str, Any]) -> None:
    cv2.rectangle(frame, (12, 12), (880, 183), (20, 25, 30), -1)
    lines = [
        f"{event['candidate_id']}  {event['joint_name']}  candidate {event['from_frame']} -> {event['to_frame']}",
        f"frame={row['frame_index']}  phase={row['phase_label']}  review={event['review_start_frame']}..{event['review_end_frame']}",
        f"jump: {event['displacement_px']:.3f}px / {event['displacement_norm']:.6f} shoulder-width",
        f"confidence: {event['confidence_before']:.6f} -> {event['confidence_after']:.6f}",
        f"neck step={event['neck_displacement_px']:.3f}px  manual label: [blank]",
    ]
    for index, text in enumerate(lines):
        color = COLORS["candidate"] if index == 0 else (245, 245, 245)
        cv2.putText(frame, text, (28, 42 + index * 31), cv2.FONT_HERSHEY_SIMPLEX,
                    0.68 if index == 0 else 0.58, color, 2 if index == 0 else 1, cv2.LINE_AA)


def read_frames(video: Path, start: int, end: int) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames: list[np.ndarray] = []
    for frame_index in range(start, end + 1):
        ok, frame = capture.read()
        if not ok:
            capture.release()
            raise RuntimeError(f"video decode failed at frame {frame_index}")
        frames.append(frame)
    capture.release()
    return frames


def write_h264(path: Path, frames: list[np.ndarray], fps: float) -> None:
    height, width = frames[0].shape[:2]
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        str(path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in frames:
            process.stdin.write(frame.tobytes())
    finally:
        process.stdin.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait():
        raise RuntimeError(f"ffmpeg failed for {path}: {stderr}")


def concatenate_clips(clips: list[Path], output: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as stream:
        concat_path = Path(stream.name)
        for clip in clips:
            escaped = str(clip.resolve()).replace("'", "'\\''")
            stream.write(f"file '{escaped}'\n")
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
            "-safe", "0", "-i", str(concat_path), "-c", "copy", str(output),
        ], check=True)
    finally:
        concat_path.unlink(missing_ok=True)


def video_frame_count(path: Path) -> int:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path),
    ], check=True, text=True, capture_output=True)
    return int(result.stdout.strip())


def main() -> int:
    args = parse_args()
    if args.context_frames < 0 or args.review_fps <= 0 or args.expected_candidates <= 0:
        raise ValueError("context-frames, review-fps, and expected-candidates must be valid positive values")
    for path in (args.summary, args.trajectory, args.video):
        if not path.is_file():
            raise FileNotFoundError(path)
    ensure_output_policy(args)
    input_hashes_before = {path: sha256_file(path) for path in (args.summary, args.trajectory, args.video)}
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    rows = load_jsonl(args.trajectory)
    if summary.get("video_id") != VIDEO_ID or len(rows) != 345:
        raise ValueError("inputs are not the fixed E001 345-frame T07A result")
    if [row.get("frame_index") for row in rows] != list(range(345)):
        raise ValueError("trajectory frame coverage is not 0..344")
    events = extract_candidates(summary, rows, args.context_frames)
    if len(events) != args.expected_candidates:
        raise ValueError(f"found {len(events)} candidates, expected {args.expected_candidates}")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.clips_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for event in events:
        clip = args.clips_dir / f"{event['candidate_id']}_{event['joint_name']}_{event['from_frame']}_{event['to_frame']}.mp4"
        event["clip_path"] = str(clip)
        source_frames = read_frames(args.video, event["review_start_frame"], event["review_end_frame"])
        rendered: list[np.ndarray] = []
        for offset, frame in enumerate(source_frames):
            frame_index = event["review_start_frame"] + offset
            draw_skeleton(frame, rows[frame_index])
            draw_absolute_path(frame, rows, event)
            draw_normalized_panel(frame, rows, event)
            draw_information(frame, rows[frame_index], event)
            rendered.append(frame)
        write_h264(clip, rendered, args.review_fps)
        expected_frames = event["review_end_frame"] - event["review_start_frame"] + 1
        if video_frame_count(clip) != expected_frames:
            raise RuntimeError(f"clip frame count mismatch: {clip}")
        clips.append(clip)

    with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(events)
    concatenate_clips(clips, args.output_video)
    expected_total_frames = sum(
        event["review_end_frame"] - event["review_start_frame"] + 1 for event in events
    )
    combined_frames = video_frame_count(args.output_video)
    if combined_frames != expected_total_frames:
        raise RuntimeError(f"combined video has {combined_frames} frames, expected {expected_total_frames}")
    input_hashes_after = {path: sha256_file(path) for path in input_hashes_before}
    if input_hashes_after != input_hashes_before:
        raise RuntimeError("an input file changed during review-material generation")
    print(json.dumps({
        "video_id": VIDEO_ID, "candidate_count": len(events),
        "candidate_frames": [event["to_frame"] for event in events],
        "joint_counts": {
            joint: sum(event["joint_name"] == joint for event in events) for joint in JOINT_PREFIX
        },
        "clip_count": len(clips), "frames_per_clip": [video_frame_count(path) for path in clips],
        "combined_frames": combined_frames, "review_fps": args.review_fps,
        "output_csv": str(args.output_csv), "output_video": str(args.output_video),
        "input_hashes_unchanged": True,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
