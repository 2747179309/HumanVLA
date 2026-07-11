#!/usr/bin/env python3
"""Run person-only YOLO detection and DeepSORT tracking on one local video."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger("run_deepsort")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect only COCO person class (class 0) with YOLO and assign local "
            "DeepSORT track_id values. Outputs are automatic pre-annotations, not GT."
        )
    )
    parser.add_argument("--video", required=True, type=Path, help="Local input video path.")
    parser.add_argument(
        "--video-id",
        help="Stable video identifier; defaults to the sanitized input filename stem.",
    )
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO model path or model name.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "mot",
        help="Root directory for <video_id>/ outputs.",
    )
    parser.add_argument("--conf", type=float, default=0.3, help="YOLO confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO NMS IoU threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO inference image size.")
    parser.add_argument(
        "--device",
        default="auto",
        help="YOLO device: auto, cpu, or a CUDA index such as 0.",
    )
    parser.add_argument("--max-age", type=int, default=30, help="DeepSORT max_age.")
    parser.add_argument("--n-init", type=int, default=3, help="DeepSORT n_init.")
    parser.add_argument("--nn-budget", type=int, default=100, help="DeepSORT nn_budget.")
    parser.add_argument(
        "--max-cosine-distance", type=float, default=0.2, help="DeepSORT appearance threshold."
    )
    parser.add_argument(
        "--max-iou-distance", type=float, default=0.7, help="DeepSORT IoU threshold."
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--run-id", help="Optional explicit run identifier.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing this script's existing output files; never affects source video.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {args.video}")
    if not 0.0 <= args.conf <= 1.0:
        raise ValueError("--conf must be in [0, 1]")
    if not 0.0 <= args.iou <= 1.0:
        raise ValueError("--iou must be in [0, 1]")
    if args.imgsz <= 0 or args.max_age <= 0 or args.n_init <= 0 or args.nn_budget <= 0:
        raise ValueError("imgsz, max-age, n-init, and nn-budget must be positive")


def sanitize_video_id(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    if not sanitized:
        raise ValueError("video_id is empty after sanitization")
    return sanitized


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def track_color(track_id: int) -> tuple[int, int, int]:
    # Bright BGR colors remain distinguishable over foliage, pavement, and clothing.
    palette = (
        (0, 255, 0),
        (255, 255, 0),
        (0, 165, 255),
        (255, 0, 255),
        (255, 128, 0),
        (0, 255, 255),
    )
    return palette[(track_id - 1) % len(palette)]


def draw_outlined_text(
    cv2: Any,
    frame: Any,
    text: str,
    origin: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
) -> None:
    cv2.putText(
        frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 5, cv2.LINE_AA
    )
    cv2.putText(
        frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA
    )


def create_video_writer(cv2: Any, path: Path, fps: float, size: tuple[int, int]) -> tuple[Any, str]:
    for codec in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, size)
        if writer.isOpened():
            return writer, codec
        writer.release()
    raise RuntimeError("OpenCV could not create MP4 output with avc1 or mp4v")


def ensure_h264_output(path: Path, current_codec: str) -> str:
    """Transcode OpenCV's MPEG-4 fallback to H.264 when the FFmpeg CLI is available."""
    if current_codec == "avc1":
        return "h264"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        LOGGER.warning("FFmpeg CLI unavailable; retaining mp4v output")
        return current_codec

    transcoded = path.with_name(f"{path.stem}.h264.tmp.mp4")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        str(transcoded),
    ]
    LOGGER.info("Transcoding OpenCV mp4v output to H.264 with FFmpeg")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        transcoded.replace(path)
        return "h264"
    except (OSError, subprocess.CalledProcessError) as exc:
        LOGGER.warning("H.264 transcode failed; retaining mp4v output: %s", exc)
        return current_codec


def output_paths(output_dir: Path) -> dict[str, Path]:
    mot_dir = output_dir / "mot"
    return {
        "video": output_dir / "tracked.mp4",
        "tracks": output_dir / "tracks_raw.jsonl",
        "mot": mot_dir / "gt.txt",
        "labels": mot_dir / "labels.txt",
        "metadata": output_dir / "metadata.json",
    }


def ensure_outputs_available(paths: dict[str, Path], overwrite: bool) -> None:
    existing = [path for path in paths.values() if path.exists()]
    if existing and not overwrite:
        formatted = "\n".join(f"  - {path}" for path in existing)
        raise FileExistsError(f"Refusing to overwrite existing outputs:\n{formatted}")
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        validate_args(args)
        video_id = sanitize_video_id(args.video_id or args.video.stem)
        output_dir = args.output_root.resolve() / video_id
        paths = output_paths(output_dir)
        ensure_outputs_available(paths, args.overwrite)

        os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / ".cache"))
        import cv2
        import numpy as np
        import torch
        from deep_sort_realtime.deepsort_tracker import DeepSort
        from tqdm import tqdm
        from ultralytics import YOLO

        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(args.seed)

        device = args.device
        if device == "auto":
            device = "0" if torch.cuda.is_available() else "cpu"

        capture = cv2.VideoCapture(str(args.video))
        if not capture.isOpened():
            raise RuntimeError(f"OpenCV could not open input video: {args.video}")

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or width <= 0 or height <= 0:
            capture.release()
            raise RuntimeError(f"Invalid video properties: fps={fps}, width={width}, height={height}")

        LOGGER.info("Loading YOLO model %s", args.model)
        model = YOLO(args.model)
        tracker = DeepSort(
            max_age=args.max_age,
            n_init=args.n_init,
            nn_budget=args.nn_budget,
            max_cosine_distance=args.max_cosine_distance,
            max_iou_distance=args.max_iou_distance,
            embedder="mobilenet",
            embedder_gpu=torch.cuda.is_available(),
        )
        writer, output_codec = create_video_writer(cv2, paths["video"], fps, (width, height))

        frame_index = 0
        total_detections = 0
        detection_seconds = 0.0
        tracking_seconds = 0.0
        track_frames: Counter[int] = Counter()
        track_confidences: defaultdict[int, list[float]] = defaultdict(list)
        labels: set[int] = set()

        with paths["tracks"].open("w", encoding="utf-8") as tracks_file, paths["mot"].open(
            "w", encoding="utf-8"
        ) as mot_file:
            progress = tqdm(total=reported_frames or None, unit="frame", desc="YOLO+DeepSORT")
            try:
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break

                    detection_start = time.perf_counter()
                    prediction = model.predict(
                        source=frame,
                        classes=[0],
                        conf=args.conf,
                        iou=args.iou,
                        imgsz=args.imgsz,
                        device=device,
                        verbose=False,
                    )[0]
                    detection_seconds += time.perf_counter() - detection_start

                    detections = []
                    if prediction.boxes is not None:
                        boxes = prediction.boxes.xyxy.detach().cpu().numpy()
                        confidences = prediction.boxes.conf.detach().cpu().numpy()
                        for box, confidence in zip(boxes, confidences):
                            x1, y1, x2, y2 = (float(value) for value in box)
                            if x1 >= x2 or y1 >= y2:
                                LOGGER.warning("Skipping invalid bbox at frame %d: %s", frame_index, box)
                                continue
                            detections.append(([x1, y1, x2 - x1, y2 - y1], float(confidence), "person"))
                    total_detections += len(detections)

                    tracking_start = time.perf_counter()
                    tracks = tracker.update_tracks(detections, frame=frame)
                    tracking_seconds += time.perf_counter() - tracking_start

                    draw_outlined_text(
                        cv2, frame, f"frame_index: {frame_index}", (20, 35), 0.8, (0, 255, 255)
                    )
                    for track in tracks:
                        if not track.is_confirmed():
                            continue
                        bbox = track.to_ltrb(orig=True, orig_strict=True)
                        confidence = track.get_det_conf()
                        if bbox is None or confidence is None:
                            continue

                        track_id = int(track.track_id)
                        x1, y1, x2, y2 = (float(value) for value in bbox)
                        if x1 >= x2 or y1 >= y2:
                            continue
                        confidence = float(confidence)
                        record = {
                            "video_id": video_id,
                            "frame_index": frame_index,
                            "timestamp_sec": round(frame_index / fps, 6),
                            "track_id": track_id,
                            "bbox_xyxy": [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)],
                            "detection_confidence": round(confidence, 6),
                        }
                        tracks_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                        mot_file.write(
                            f"{frame_index + 1}, {track_id}, {x1:.3f}, {y1:.3f}, "
                            f"{x2 - x1:.3f}, {y2 - y1:.3f}, {confidence:.6f}, -1, -1, -1\n"
                        )

                        labels.add(track_id)
                        track_frames[track_id] += 1
                        track_confidences[track_id].append(confidence)
                        color = track_color(track_id)
                        p1 = (max(0, int(round(x1))), max(0, int(round(y1))))
                        p2 = (min(width - 1, int(round(x2))), min(height - 1, int(round(y2))))
                        cv2.rectangle(frame, p1, p2, color, 2)
                        text_y = max(25, p1[1] - 8)
                        draw_outlined_text(
                            cv2, frame, f"track_id: {track_id}", (p1[0], text_y), 0.8, color
                        )

                    writer.write(frame)
                    frame_index += 1
                    progress.update(1)
            finally:
                progress.close()
                capture.release()
                writer.release()

        output_codec = ensure_h264_output(paths["video"], output_codec)

        with paths["labels"].open("w", encoding="utf-8") as labels_file:
            labels_file.write("track_id,class_name\n")
            for track_id in sorted(labels):
                labels_file.write(f"{track_id},person\n")

        model_path = Path(args.model)
        model_hash = sha256_file(model_path) if model_path.is_file() else "unavailable"
        durations = list(track_frames.values())
        run_id = args.run_id or datetime.now().strftime("%Y%m%d_T02_%H%M%S")
        metadata = {
            "run_id": run_id,
            "date": datetime.now().astimezone().isoformat(),
            "experiment": "T02 YOLO person detection + DeepSORT automatic pre-annotation",
            "artifact_semantics": (
                "Automatic DeepSORT output. mot/gt.txt is a MOTChallenge-compatible interchange "
                "filename and is not human-reviewed ground truth."
            ),
            "video": {
                "video_id": video_id,
                "file_path": str(args.video.resolve()),
                "sha256": sha256_file(args.video),
                "fps": fps,
                "width": width,
                "height": height,
                "reported_total_frames": reported_frames,
                "processed_total_frames": frame_index,
                "duration_sec": round(frame_index / fps, 3),
            },
            "yolo": {
                "model": args.model,
                "model_sha256": model_hash,
                "class_id": 0,
                "class_name": "person",
                "conf_threshold": args.conf,
                "iou_threshold": args.iou,
                "imgsz": args.imgsz,
                "device": device,
            },
            "deepsort": {
                "implementation": "deep-sort-realtime",
                "version": distribution_version("deep-sort-realtime"),
                "max_age": args.max_age,
                "n_init": args.n_init,
                "nn_budget": args.nn_budget,
                "max_cosine_distance": args.max_cosine_distance,
                "max_iou_distance": args.max_iou_distance,
                "embedder": "mobilenet",
                "embedder_gpu": torch.cuda.is_available(),
            },
            "random_seeds": {"python": args.seed, "numpy": args.seed, "torch": args.seed},
            "statistics": {
                "total_person_detections": total_detections,
                "num_tracks_total": len(track_frames),
                "num_tracks_short_lt_5_frames": sum(length < 5 for length in durations),
                "avg_track_duration_frames": round(sum(durations) / len(durations), 3) if durations else 0.0,
                "min_track_duration_frames": min(durations) if durations else 0,
                "max_track_duration_frames": max(durations) if durations else 0,
                "detection_fps": round(frame_index / detection_seconds, 3) if detection_seconds else 0.0,
                "tracking_fps": round(frame_index / tracking_seconds, 3) if tracking_seconds else 0.0,
                "mean_detection_confidence_by_track": {
                    str(track_id): round(sum(values) / len(values), 6)
                    for track_id, values in sorted(track_confidences.items())
                },
            },
            "environment": {
                "python": sys.version.split()[0],
                "conda_env": Path(sys.prefix).name,
                "torch": torch.__version__,
                "torchvision": distribution_version("torchvision"),
                "torch_built_cuda": torch.version.cuda,
                "cudnn": torch.backends.cudnn.version(),
                "cuda_available": torch.cuda.is_available(),
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                "opencv": cv2.__version__,
                "ultralytics": distribution_version("ultralytics"),
            },
            "video_output_codec": output_codec,
            "git_commit": git_commit(),
            "output_files": [str(path) for path in paths.values()],
        }
        paths["metadata"].write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        LOGGER.info("Completed %d frames; automatic outputs are in %s", frame_index, output_dir)
        return 0
    except Exception:
        LOGGER.exception("MOT pipeline failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
