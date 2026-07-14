#!/usr/bin/env python3
"""Render T05A per-joint quality states without modifying skeleton coordinates."""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SUBJECTS = ("P001", "P002", "P003")
BODY_25_EDGES = (
    (1, 0), (1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10), (10, 11), (11, 24), (11, 22),
    (22, 23), (8, 12), (12, 13), (13, 14), (14, 21), (14, 19),
    (19, 20), (0, 15), (15, 17), (0, 16), (16, 18),
)
COLORS = {
    "valid": (0, 210, 0),
    "low_quality": (0, 255, 255),
    "invalid_identity_mix": (0, 0, 255),
    "missing": (150, 150, 150),
    "excluded": (255, 0, 255),
}
PRIORITY = {"valid": 0, "low_quality": 1, "invalid_identity_mix": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render T05A quality masks as an H.264 video.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--processed-dir", required=True, type=Path)
    parser.add_argument("--association-jsonl", required=True, type=Path)
    parser.add_argument("--output-video", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=240)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def bbox_from_keypoints(keypoints: list[list[float]]) -> list[float] | None:
    valid = [(point[0], point[1]) for point in keypoints if point[2] > 0]
    if not valid:
        return None
    xs, ys = zip(*valid)
    return [min(xs), min(ys), max(xs), max(ys)]


def joint_color(status: str) -> tuple[int, int, int]:
    return COLORS[status]


def draw_subject(frame: np.ndarray, record: dict[str, Any]) -> None:
    keypoints = record["keypoints_raw"]
    mask = record["quality_mask"]
    for first, second in BODY_25_EDGES:
        if keypoints[first][2] <= 0 or keypoints[second][2] <= 0:
            continue
        status = max((mask[first], mask[second]), key=lambda value: PRIORITY.get(value, 3))
        cv2.line(
            frame,
            (int(round(keypoints[first][0])), int(round(keypoints[first][1]))),
            (int(round(keypoints[second][0])), int(round(keypoints[second][1]))),
            joint_color(status), 6, cv2.LINE_AA,
        )
    for index, (x, y, confidence) in enumerate(keypoints):
        if confidence > 0:
            cv2.circle(
                frame, (int(round(x)), int(round(y))), 8,
                joint_color(mask[index]), -1, cv2.LINE_AA,
            )
    bbox = bbox_from_keypoints(keypoints)
    if bbox is None:
        return
    x1, y1, x2, y2 = [int(round(value)) for value in bbox]
    frame_color = COLORS.get(record["frame_quality_status"], COLORS["valid"])
    cv2.rectangle(frame, (x1, y1), (x2, y2), frame_color, 5, cv2.LINE_AA)
    cv2.putText(
        frame, f"{record['subject_id']} {record['frame_quality_status']}",
        (x1, max(45, y1 - 15)), cv2.FONT_HERSHEY_SIMPLEX, 1.05,
        frame_color, 4, cv2.LINE_AA,
    )
    if not record["frame_valid"]:
        cv2.line(frame, (x1, y1), (x2, y2), COLORS["invalid_identity_mix"], 12, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x1, y2), COLORS["invalid_identity_mix"], 12, cv2.LINE_AA)


def draw_excluded(frame: np.ndarray, record: dict[str, Any]) -> None:
    keypoints = record.get("keypoints")
    if not keypoints:
        return
    color = COLORS["excluded"]
    for first, second in BODY_25_EDGES:
        if keypoints[first][2] > 0 and keypoints[second][2] > 0:
            cv2.line(
                frame,
                (int(round(keypoints[first][0])), int(round(keypoints[first][1]))),
                (int(round(keypoints[second][0])), int(round(keypoints[second][1]))),
                color, 5, cv2.LINE_AA,
            )
    bbox = record.get("pose_bbox_xyxy")
    if bbox:
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 5, cv2.LINE_AA)
        cv2.putText(
            frame, "excluded extra pose", (x1, max(45, y1 - 15)),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 4, cv2.LINE_AA,
        )


def main() -> int:
    args = parse_args()
    video = args.video.resolve()
    processed_dir = args.processed_dir.resolve()
    association = args.association_jsonl.resolve()
    output = args.output_video.resolve()
    for path in (video, processed_dir, association):
        if not path.exists():
            raise FileNotFoundError(path)
    intermediate = output.with_name(output.stem + "_opencv.mp4")
    if not args.overwrite:
        existing = [str(path) for path in (output, intermediate) if path.exists()]
        if existing:
            raise FileExistsError("refusing to overwrite derived output(s): " + ", ".join(existing))
    output.parent.mkdir(parents=True, exist_ok=True)

    sequences = {
        subject: load_jsonl(processed_dir / f"{subject}.jsonl") for subject in SUBJECTS
    }
    for subject, records in sequences.items():
        if len(records) != args.expected_frames:
            raise ValueError(f"{subject}: expected {args.expected_frames} records")
    association_records = load_jsonl(association)
    excluded_by_frame: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in association_records:
        if record["match_status"] in {"ambiguous_pose", "phantom_pose"}:
            excluded_by_frame[record["frame_index"]].append(record)
        elif record["match_status"] == "unmatched_pose" and record["frame_index"] in {207, 208}:
            excluded_by_frame[record["frame_index"]].append(record)

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(intermediate), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"cannot create video: {intermediate}")
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        cv2.putText(
            frame, f"frame_index={frame_index}", (35, 75),
            cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 5, cv2.LINE_AA,
        )
        for subject in SUBJECTS:
            record = sequences[subject][frame_index]
            if record["frame_quality_status"] == "missing":
                cv2.putText(
                    frame, f"{subject} missing", (35, 130 + 45 * SUBJECTS.index(subject)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLORS["missing"], 3, cv2.LINE_AA,
                )
            else:
                draw_subject(frame, record)
        for record in excluded_by_frame.get(frame_index, []):
            draw_excluded(frame, record)
        writer.write(frame)
        frame_index += 1
    capture.release()
    writer.release()
    if frame_index != args.expected_frames:
        raise RuntimeError(f"rendered {frame_index} frames, expected {args.expected_frames}")
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(intermediate),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", str(output),
    ], check=True)
    print(json.dumps({
        "output_video": str(output), "intermediate_video": str(intermediate),
        "codec": "h264", "frames": frame_index, "fps": fps,
        "width": width, "height": height,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
