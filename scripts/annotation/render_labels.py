#!/usr/bin/env python3
"""Render frame-level manual action labels over a source video."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


LOGGER = logging.getLogger(__name__)

PHASE_COLORS = {
    0: (128, 128, 128),
    1: (46, 204, 113),
    2: (241, 196, 15),
    3: (230, 126, 34),
    4: (231, 76, 60),
    5: (52, 152, 219),
    6: (155, 89, 182),
    7: (26, 188, 156),
    8: (52, 73, 94),
    90: (142, 68, 173),
    91: (192, 57, 43),
    98: (127, 140, 141),
}


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
    for frame_index, record in enumerate(records):
        if record.get("frame_index") != frame_index:
            raise ValueError(
                f"frame JSONL must be continuous; row {frame_index} has "
                f"frame_index={record.get('frame_index')}"
            )
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render manual frame-level action labels over a video."
    )
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--frames-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--font",
        type=Path,
        default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    )
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    try:
        records = load_records(args.frames_jsonl)
        capture = cv2.VideoCapture(str(args.video))
        if not capture.isOpened():
            raise RuntimeError(f"cannot open video: {args.video}")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        source_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or width <= 0 or height <= 0:
            raise RuntimeError("invalid source video metadata")
        if len(records) != source_frame_count:
            raise ValueError(
                f"JSONL has {len(records)} records but video reports "
                f"{source_frame_count} frames"
            )
        if not args.font.is_file():
            raise FileNotFoundError(f"font not found: {args.font}")

        font_large = ImageFont.truetype(str(args.font), 28)
        font_medium = ImageFont.truetype(str(args.font), 23)
        font_small = ImageFont.truetype(str(args.font), 20)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.stem + ".tmp" + args.output.suffix)
        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s:v",
            f"{width}x{height}",
            "-r",
            f"{fps:.12g}",
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        if process.stdin is None:
            raise RuntimeError("failed to open FFmpeg stdin")

        rendered = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            record = records[rendered]
            panel = frame.copy()
            cv2.rectangle(panel, (0, 0), (width, 205), (0, 0, 0), thickness=-1)
            frame = cv2.addWeighted(panel, 0.68, frame, 0.32, 0)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            draw = ImageDraw.Draw(image)
            color = PHASE_COLORS.get(record["phase_id"], (255, 255, 255))
            draw.rectangle((0, 0, 14, 205), fill=color)
            draw.text(
                (26, 14),
                f"{record['video_id']} | {record['episode_id']}",
                font=font_small,
                fill=(255, 255, 255),
            )
            draw.text(
                (26, 48),
                f"frame_index={record['frame_index']}  "
                f"timestamp_sec={record['timestamp_sec']:.3f}",
                font=font_large,
                fill=(255, 255, 255),
            )
            draw.text(
                (26, 88),
                f"phase={record['phase_id']} {record['phase_label']}  "
                f"hand={record['active_hand']}  object={record['object_id']}",
                font=font_medium,
                fill=color,
            )
            draw.text(
                (26, 124), record["phase_text_zh"], font=font_medium, fill=(255, 255, 255)
            )
            draw.text(
                (26, 162), record["phase_text_en"], font=font_small, fill=(235, 235, 235)
            )
            annotated = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
            process.stdin.write(annotated.tobytes())
            rendered += 1

        capture.release()
        process.stdin.close()
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg exited with status {return_code}")
        if rendered != len(records):
            raise RuntimeError(
                f"decoded {rendered} frames but expected {len(records)}"
            )
        temporary.replace(args.output)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        LOGGER.error("render failed: %s", exc)
        return 2

    print(json.dumps({"output": str(args.output), "rendered_frames": rendered}))
    LOGGER.info("rendered %d frames", rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
