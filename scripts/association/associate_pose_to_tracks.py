#!/usr/bin/env python3
"""Associate per-frame OpenPose BODY_25 poses with reviewed DeepSORT tracks."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

ANNOTATION_VERSION = "v0.1.0"
VALID_STATUSES = {
    "matched", "unmatched_pose", "unmatched_track", "ambiguous_pose", "phantom_pose"
}
BODY_25_EDGES = (
    (1, 0), (1, 2), (2, 3), (3, 4), (1, 5), (5, 6), (6, 7),
    (1, 8), (8, 9), (9, 10), (10, 11), (11, 24), (11, 22),
    (22, 23), (8, 12), (12, 13), (13, 14), (14, 21), (14, 19),
    (19, 20), (0, 15), (15, 17), (0, 16), (16, 18),
)
STATUS_COLORS = {
    "matched": (40, 200, 40),
    "unmatched_pose": (220, 40, 220),
    "unmatched_track": (0, 220, 255),
    "ambiguous_pose": (0, 140, 255),
    "phantom_pose": (0, 0, 255),
}

# OpenCV使用BGR颜色顺序
SUBJECT_COLORS = {
    "P001": (0, 255, 0),      # 绿色
    "P002": (255, 0, 0),      # 蓝色
    "P003": (0, 0, 255),      # 红色
}

TRACK_COLORS = [
    (0, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
]

STATUS_COLORS = {
    "matched": (40, 200, 40),
    "unmatched_pose": (160, 160, 160),  # 灰色
    "unmatched_track": (160, 160, 160),
    "ambiguous_pose": (0, 255, 255),    # 黄色
    "phantom_pose": (255, 0, 255),      # 紫色
}


def get_record_color(record: dict[str, Any]) -> tuple[int, int, int]:
    """优先按subject_id固定颜色,异常pose按状态颜色。"""
    status = record["match_status"]

    if status in {"ambiguous_pose", "phantom_pose", "unmatched_pose"}:
        return STATUS_COLORS[status]

    subject_id = record.get("subject_id")
    if subject_id in SUBJECT_COLORS:
        return SUBJECT_COLORS[subject_id]

    track_id = record.get("track_id")
    if track_id is not None:
        return TRACK_COLORS[(int(track_id) - 1) % len(TRACK_COLORS)]

    return STATUS_COLORS.get(status, (200, 200, 200))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Associate BODY_25 poses to human-reviewed DeepSORT subjects with "
            "IoU/center-distance cost and Hungarian assignment."
        )
    )
    parser.add_argument("--video-id", default="three-people-walking")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--video", type=Path)
    parser.add_argument("--pose-json-dir", type=Path)
    parser.add_argument("--mot-review", type=Path)
    parser.add_argument("--subject-map", type=Path)
    parser.add_argument("--mot-tracks", type=Path)
    parser.add_argument("--manual-review-summary", type=Path)
    parser.add_argument("--output-jsonl", type=Path)
    parser.add_argument("--output-summary", type=Path)
    parser.add_argument("--output-video", type=Path)
    parser.add_argument("--manual-review-template", type=Path)
    parser.add_argument("--iou-weight", type=float, default=0.6)
    parser.add_argument("--center-distance-weight", type=float, default=0.4)
    parser.add_argument("--cost-threshold", type=float, default=0.5)
    parser.add_argument("--run-id", default="20260712_T04_001")
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite T04 derived outputs only."
    )
    return parser.parse_args()


def resolve_path(explicit: Path | None, candidates: list[Path], label: str) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")
        return path
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"could not auto-discover {label}; checked: {candidates}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_track_ids(value: str) -> set[int]:
    return {int(item.strip()) for item in value.split(";") if item.strip()}


def load_review(review_path: Path) -> tuple[list[dict[str, str]], set[int]]:
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "video_id", "start_frame", "end_frame", "check_item", "track_id",
        "result", "include_in_main_dataset", "note",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"invalid MOT review fields: {review_path}")
    excluded: set[int] = set()
    for row in rows:
        if row["result"] == "confirmed_false_positive" or row["include_in_main_dataset"] == "0":
            excluded.update(parse_track_ids(row["track_id"]))
    return rows, excluded


def load_subject_map(path: Path, excluded_tracks: set[int]) -> dict[int, dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "video_id", "track_id", "subject_id", "start_frame", "end_frame",
        "role", "include_for_pose",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"invalid subject map fields: {path}")
    mapping: dict[int, dict[str, Any]] = {}
    seen_subjects: set[str] = set()
    for row in rows:
        if row["include_for_pose"] != "1":
            continue
        track_id = int(row["track_id"])
        if track_id in excluded_tracks:
            raise ValueError(f"excluded track {track_id} appears in subject map")
        subject_id = row["subject_id"].strip()
        if track_id in mapping or subject_id in seen_subjects:
            raise ValueError("duplicate track_id or subject_id in subject map")
        mapping[track_id] = {
            "subject_id": subject_id,
            "start_frame": int(row["start_frame"]),
            "end_frame": int(row["end_frame"]),
            "role": row["role"],
        }
        seen_subjects.add(subject_id)
    if not mapping:
        raise ValueError("subject map has no include_for_pose=1 rows")
    return mapping


def load_tracks(path: Path, mapping: dict[int, dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_frame: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    seen: set[tuple[int, int]] = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            track_id = int(record["track_id"])
            if track_id not in mapping:
                continue
            frame_index = int(record["frame_index"])
            limits = mapping[track_id]
            if not limits["start_frame"] <= frame_index <= limits["end_frame"]:
                continue
            key = (frame_index, track_id)
            if key in seen:
                raise ValueError(f"duplicate track record: frame={frame_index}, track={track_id}")
            bbox = [float(value) for value in record["bbox_xyxy"]]
            if len(bbox) != 4 or not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
                raise ValueError(f"invalid bbox at MOT line {line_number}")
            by_frame[frame_index].append({
                "track_id": track_id,
                "subject_id": limits["subject_id"],
                "bbox_xyxy": bbox,
                "detection_confidence": float(record["detection_confidence"]),
                "timestamp_sec": float(record["timestamp_sec"]),
            })
            seen.add(key)
    for tracks in by_frame.values():
        tracks.sort(key=lambda item: item["track_id"])
    return by_frame


def pose_bbox(keypoints: list[list[float]]) -> list[float] | None:
    valid = [(point[0], point[1]) for point in keypoints if point[2] > 0]
    if not valid:
        return None
    xs, ys = zip(*valid)
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


def load_poses(json_dir: Path, expected_frames: int) -> tuple[dict[int, list[dict[str, Any]]], list[Path]]:
    files = sorted(json_dir.glob("*_keypoints.json"))
    if len(files) != expected_frames:
        raise ValueError(f"OpenPose JSON count {len(files)} != {expected_frames}")
    by_frame: dict[int, list[dict[str, Any]]] = {}
    for frame_index, path in enumerate(files):
        expected_suffix = f"_{frame_index:012d}_keypoints.json"
        if not path.name.endswith(expected_suffix):
            raise ValueError(f"unexpected OpenPose filename sequence: {path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        people = payload.get("people")
        if not isinstance(people, list):
            raise ValueError(f"people is not a list: {path}")
        poses: list[dict[str, Any]] = []
        for pose_index, person in enumerate(people):
            flat = person.get("pose_keypoints_2d")
            if not isinstance(flat, list) or len(flat) != 75:
                raise ValueError(f"invalid BODY_25 length: frame={frame_index}, pose={pose_index}")
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in flat):
                raise ValueError(f"non-numeric BODY_25 value: frame={frame_index}, pose={pose_index}")
            if any(not math.isfinite(float(value)) for value in flat):
                raise ValueError(f"non-finite BODY_25 value: frame={frame_index}, pose={pose_index}")
            keypoints = [
                [float(flat[index]), float(flat[index + 1]), float(flat[index + 2])]
                for index in range(0, 75, 3)
            ]
            confidences = [point[2] for point in keypoints]
            valid_confidences = [value for value in confidences if value > 0]
            poses.append({
                "pose_index": pose_index,
                "keypoints": keypoints,
                "keypoint_confidence_raw": confidences,
                "pose_bbox_xyxy": pose_bbox(keypoints),
                "valid_keypoints": len(valid_confidences),
                "mean_valid_confidence": (
                    sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
                ),
            })
        by_frame[frame_index] = poses
    return by_frame, files


def bbox_iou(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def normalized_center_distance(pose_box: list[float], track_box: list[float]) -> float:
    pose_center = ((pose_box[0] + pose_box[2]) / 2, (pose_box[1] + pose_box[3]) / 2)
    track_center = ((track_box[0] + track_box[2]) / 2, (track_box[1] + track_box[3]) / 2)
    distance = math.hypot(pose_center[0] - track_center[0], pose_center[1] - track_center[1])
    diagonal = math.hypot(track_box[2] - track_box[0], track_box[3] - track_box[1])
    return distance / diagonal if diagonal > 0 else math.inf


def pair_metrics(
    track_box: list[float], pose_box_value: list[float] | None,
    iou_weight: float, center_weight: float,
) -> tuple[float, float, float]:
    if pose_box_value is None:
        return math.inf, 0.0, math.inf
    iou = bbox_iou(track_box, pose_box_value)
    center_distance = normalized_center_distance(pose_box_value, track_box)
    cost = iou_weight * (1.0 - iou) + center_weight * center_distance
    return cost, iou, center_distance


def base_record(video_id: str, frame_index: int, timestamp: float) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "frame_index": frame_index,
        "timestamp_sec": round(timestamp, 6),
        "track_id": None,
        "subject_id": None,
        "bbox_xyxy": None,
        "pose_bbox_xyxy": None,
        "pose_index": None,
        "pose_model": None,
        "keypoints": None,
        "keypoint_confidence": None,
        "keypoint_confidence_raw": None,
        "detection_confidence": None,
        "match_score": None,
        "match_cost": None,
        "match_iou": None,
        "center_distance": None,
        "match_status": None,
        "anomaly_reason": None,
        "source": "openpose_deepsort_association",
        "annotation_version": ANNOTATION_VERSION,
    }


def pose_record(
    video_id: str, frame_index: int, timestamp: float, pose: dict[str, Any], status: str,
) -> dict[str, Any]:
    record = base_record(video_id, frame_index, timestamp)
    record.update({
        "bbox_xyxy": pose["pose_bbox_xyxy"],
        "pose_bbox_xyxy": pose["pose_bbox_xyxy"],
        "pose_index": pose["pose_index"],
        "pose_model": "openpose_BODY_25",
        "keypoints": pose["keypoints"],
        "keypoint_confidence": pose["keypoint_confidence_raw"],
        "keypoint_confidence_raw": pose["keypoint_confidence_raw"],
        "match_status": status,
    })
    return record


def associate_frame(
    video_id: str,
    frame_index: int,
    fps: float,
    tracks: list[dict[str, Any]],
    poses: list[dict[str, Any]],
    anomaly_status: str | None,
    iou_weight: float,
    center_weight: float,
    threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    timestamp = frame_index / fps
    candidate_poses = list(poses)
    anomaly_detail = None
    records: list[dict[str, Any]] = []
    if anomaly_status:
        if len(candidate_poses) <= len(tracks):
            raise ValueError(
                f"manual anomaly frame {frame_index} has no extra pose: "
                f"poses={len(candidate_poses)}, tracks={len(tracks)}"
            )
        anomaly_pose = min(
            candidate_poses,
            key=lambda item: (item["valid_keypoints"], item["mean_valid_confidence"]),
        )
        candidate_poses.remove(anomaly_pose)
        record = pose_record(video_id, frame_index, timestamp, anomaly_pose, anomaly_status)
        record["anomaly_reason"] = anomaly_status
        records.append(record)
        anomaly_detail = {
            "status": anomaly_status,
            "pose_index": anomaly_pose["pose_index"],
            "valid_keypoints": anomaly_pose["valid_keypoints"],
            "selection_method": "lowest_valid_keypoint_count_then_mean_confidence",
        }

    costs = np.empty((len(tracks), len(candidate_poses)), dtype=float)
    metrics: dict[tuple[int, int], tuple[float, float, float]] = {}
    for track_index, track in enumerate(tracks):
        for pose_index, pose in enumerate(candidate_poses):
            values = pair_metrics(
                track["bbox_xyxy"], pose["pose_bbox_xyxy"], iou_weight, center_weight
            )
            metrics[(track_index, pose_index)] = values
            costs[track_index, pose_index] = values[0] if math.isfinite(values[0]) else 1e6

    assigned_tracks: set[int] = set()
    assigned_poses: set[int] = set()
    if tracks and candidate_poses:
        row_indices, column_indices = linear_sum_assignment(costs)
        for track_index, pose_index in zip(row_indices.tolist(), column_indices.tolist()):
            cost, iou, center_distance = metrics[(track_index, pose_index)]
            if cost >= threshold:
                continue
            track, pose = tracks[track_index], candidate_poses[pose_index]
            record = pose_record(video_id, frame_index, timestamp, pose, "matched")
            record.update({
                "track_id": track["track_id"],
                "subject_id": track["subject_id"],
                "bbox_xyxy": track["bbox_xyxy"],
                "detection_confidence": track["detection_confidence"],
                "match_score": round(max(0.0, 1.0 - cost), 8),
                "match_cost": round(cost, 8),
                "match_iou": round(iou, 8),
                "center_distance": round(center_distance, 8),
            })
            records.append(record)
            assigned_tracks.add(track_index)
            assigned_poses.add(pose_index)

    for track_index, track in enumerate(tracks):
        if track_index in assigned_tracks:
            continue
        record = base_record(video_id, frame_index, timestamp)
        record.update({
            "track_id": track["track_id"],
            "subject_id": track["subject_id"],
            "bbox_xyxy": track["bbox_xyxy"],
            "detection_confidence": track["detection_confidence"],
            "match_status": "unmatched_track",
        })
        records.append(record)
    for pose_index, pose in enumerate(candidate_poses):
        if pose_index not in assigned_poses:
            records.append(pose_record(video_id, frame_index, timestamp, pose, "unmatched_pose"))

    records.sort(key=lambda item: (
        item["track_id"] is None,
        item["track_id"] if item["track_id"] is not None else 10**9,
        item["pose_index"] if item["pose_index"] is not None else 10**9,
    ))
    return records, anomaly_detail


def draw_pose(frame: np.ndarray, keypoints: list[list[float]], color: tuple[int, int, int]) -> None:
    for first, second in BODY_25_EDGES:
        if keypoints[first][2] > 0 and keypoints[second][2] > 0:
            start = (int(round(keypoints[first][0])), int(round(keypoints[first][1])))
            end = (int(round(keypoints[second][0])), int(round(keypoints[second][1])))
            cv2.line(frame, start, end, color, 5, cv2.LINE_AA)
    for x, y, confidence in keypoints:
        if confidence > 0:
            cv2.circle(frame, (int(round(x)), int(round(y))), 7, color, -1, cv2.LINE_AA)


def draw_frame(frame: np.ndarray, frame_index: int, records: list[dict[str, Any]]) -> np.ndarray:
    cv2.putText(
        frame, f"frame_index={frame_index}", (35, 75), cv2.FONT_HERSHEY_SIMPLEX,
        1.8, (255, 255, 255), 5, cv2.LINE_AA,
    )
    for record in records:
        status = record["match_status"]
        color = get_record_color(record)
        if record["keypoints"] is not None:
            draw_pose(frame, record["keypoints"], color)
        bbox = record["bbox_xyxy"]
        if bbox is not None:
            start = (int(round(bbox[0])), int(round(bbox[1])))
            end = (int(round(bbox[2])), int(round(bbox[3])))
            cv2.rectangle(frame, start, end, color, 6, cv2.LINE_AA)
            label = status
            if record["track_id"] is not None:
                label = f"track={record['track_id']} {record['subject_id']} {status}"
            elif record["pose_index"] is not None:
                label = f"pose={record['pose_index']} {status}"
            y = max(45, start[1] - 15)
            cv2.putText(
                frame, label, (start[0], y), cv2.FONT_HERSHEY_SIMPLEX,
                1.15, color, 4, cv2.LINE_AA,
            )
        if status == "phantom_pose" and record["pose_bbox_xyxy"] is not None:
            box = record["pose_bbox_xyxy"]
            cv2.line(
                frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])),
                color, 12, cv2.LINE_AA,
            )
            cv2.line(
                frame, (int(box[2]), int(box[1])), (int(box[0]), int(box[3])),
                color, 12, cv2.LINE_AA,
            )
    return frame


def make_visualization(
    video: Path, output: Path, records_by_frame: dict[int, list[dict[str, Any]]],
    expected_frames: int,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    intermediate = output.with_name(output.stem + "_opencv.mp4")
    writer = cv2.VideoWriter(
        str(intermediate), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"cannot create visualization: {intermediate}")
    frames_written = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        writer.write(draw_frame(frame, frames_written, records_by_frame[frames_written]))
        frames_written += 1
    capture.release()
    writer.release()
    if frames_written != expected_frames:
        raise RuntimeError(f"visualization frame count {frames_written} != {expected_frames}")
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(intermediate),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", str(output),
    ], check=True)
    return {
        "path": str(output), "intermediate_path": str(intermediate),
        "codec": "h264", "fps": fps, "width": width, "height": height,
        "frames": frames_written,
    }


def create_review_template(
    path: Path, records_by_frame: dict[int, list[dict[str, Any]]], anomaly_frames: set[int]
) -> list[int]:
    scores: dict[int, float] = {}
    for frame_index, records in records_by_frame.items():
        matched_scores = [
            record["match_score"] for record in records if record["match_status"] == "matched"
        ]
        if matched_scores:
            scores[frame_index] = min(matched_scores)
    candidates = [frame for frame, _ in sorted(scores.items(), key=lambda item: item[1])]
    selected = sorted(anomaly_frames)
    for frame_index in candidates:
        if frame_index not in anomaly_frames:
            selected.append(frame_index)
        if len(selected) == 20:
            break
    if len(selected) < 20:
        raise RuntimeError("could not select 20 unique manual-review frames")
    with path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = [
            "frame_index", "review_priority", "automatic_statuses", "subject_id_correct",
            "pose_assignment_correct", "anomaly_handling_correct", "reviewer_decision", "note",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for frame_index in selected:
            statuses = sorted({r["match_status"] for r in records_by_frame[frame_index]})
            writer.writerow({
                "frame_index": frame_index,
                "review_priority": "known_anomaly" if frame_index in anomaly_frames else "low_score",
                "automatic_statuses": ";".join(statuses),
                "subject_id_correct": "",
                "pose_assignment_correct": "",
                "anomaly_handling_correct": "",
                "reviewer_decision": "pending",
                "note": "",
            })
    return selected


def main() -> int:
    args = parse_args()
    root = args.project_root.expanduser().resolve()
    video_id = args.video_id
    video = resolve_path(args.video, [root / "data/raw_videos" / f"{video_id}.mp4"], "video")
    pose_dir = resolve_path(
        args.pose_json_dir,
        [root / "results/openpose" / video_id / "raw_json", root / "data/openpose/raw_json" / video_id],
        "OpenPose JSON directory",
    )
    mot_review = resolve_path(
        args.mot_review, [root / "data/mot/reviewed" / f"{video_id}.csv"], "MOT review CSV"
    )
    subject_map = resolve_path(args.subject_map, [
        root / "data/mot/reviewed/subject_maps" / f"{video_id}_subject_map.csv",
        root / "data/mot/subject_maps" / f"{video_id}_subject_map.csv",
    ], "subject map")
    mot_tracks = resolve_path(args.mot_tracks, [
        root / "data/mot/reviewed" / video_id / "tracks_reviewed.jsonl",
        root / "results/mot" / video_id / "tracks_reviewed.jsonl",
        root / "results/mot" / video_id / "tracks_raw.jsonl",
    ], "per-frame MOT tracks")
    manual_summary_path = resolve_path(args.manual_review_summary, [
        root / "results/openpose" / video_id / "manual_review_summary.json"
    ], "T03 manual review summary")
    output_jsonl = (args.output_jsonl or root / "data/openpose/associated" / f"{video_id}.jsonl").resolve()
    association_dir = root / "results/association" / video_id
    output_summary = (args.output_summary or association_dir / "summary.json").resolve()
    output_video = (args.output_video or association_dir / "association_visualization.mp4").resolve()
    review_template = (
        args.manual_review_template or association_dir / "manual_review_template.csv"
    ).resolve()
    outputs = [output_jsonl, output_summary, output_video, review_template]
    if not args.overwrite:
        existing = [str(path) for path in outputs if path.exists()]
        if existing:
            raise FileExistsError("refusing to overwrite derived output(s): " + ", ".join(existing))
    if args.iou_weight < 0 or args.center_distance_weight < 0:
        raise ValueError("matching weights must be non-negative")
    if not math.isclose(args.iou_weight + args.center_distance_weight, 1.0, abs_tol=1e-9):
        raise ValueError("matching weights must sum to 1")
    if not 0 < args.cost_threshold <= 1:
        raise ValueError("cost threshold must be in (0,1]")
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    if total_frames != 240:
        raise ValueError(f"video frame count {total_frames} != 240")

    review_rows, excluded_tracks = load_review(mot_review)
    mapping = load_subject_map(subject_map, excluded_tracks)
    tracks_by_frame = load_tracks(mot_tracks, mapping)
    poses_by_frame, pose_files = load_poses(pose_dir, total_frames)
    manual_summary = json.loads(manual_summary_path.read_text(encoding="utf-8"))
    anomaly_status_by_frame = {
        **{int(frame): "ambiguous_pose" for frame in manual_summary["ambiguous_pose_frames"]},
        **{int(frame): "phantom_pose" for frame in manual_summary["phantom_frames"]},
        **{
            int(frame): "unmatched_pose"
            for frame in manual_summary["unmatched_background_person_frames"]
        },
    }

    raw_digest_before = directory_digest(pose_files)
    expected_raw_digest = manual_summary["source_files"]["raw_json_directory_sha256"]
    if raw_digest_before != expected_raw_digest:
        raise ValueError("raw OpenPose directory SHA-256 differs from T03 locked digest")

    start_time = time.perf_counter()
    all_records: list[dict[str, Any]] = []
    records_by_frame: dict[int, list[dict[str, Any]]] = {}
    anomaly_details: dict[str, Any] = {}
    for frame_index in range(total_frames):
        frame_records, anomaly_detail = associate_frame(
            video_id, frame_index, fps, tracks_by_frame.get(frame_index, []),
            poses_by_frame[frame_index], anomaly_status_by_frame.get(frame_index),
            args.iou_weight, args.center_distance_weight, args.cost_threshold,
        )
        records_by_frame[frame_index] = frame_records
        all_records.extend(frame_records)
        if anomaly_detail:
            anomaly_details[str(frame_index)] = anomaly_detail

    with output_jsonl.open("w", encoding="utf-8") as stream:
        for record in all_records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    visualization = make_visualization(video, output_video, records_by_frame, total_frames)
    review_frames = create_review_template(
        review_template, records_by_frame, set(anomaly_status_by_frame)
    )
    raw_digest_after = directory_digest(pose_files)
    if raw_digest_after != raw_digest_before:
        raise RuntimeError("raw OpenPose JSON changed during association")

    status_counts = collections.Counter(record["match_status"] for record in all_records)
    matched_costs = [
        record["match_cost"] for record in all_records if record["match_status"] == "matched"
    ]
    per_subject: dict[str, Any] = {}
    for item in mapping.values():
        subject_id = item["subject_id"]
        subject_records = [r for r in all_records if r["subject_id"] == subject_id]
        costs = [r["match_cost"] for r in subject_records if r["match_status"] == "matched"]
        per_subject[subject_id] = {
            "track_id": next(
                track_id for track_id, value in mapping.items() if value["subject_id"] == subject_id
            ),
            "valid_frames": len(costs),
            "matched_frames": len(costs),
            "unmatched_frames": sum(r["match_status"] == "unmatched_track" for r in subject_records),
            "avg_match_cost": sum(costs) / len(costs) if costs else None,
            "min_match_score": min(
                (r["match_score"] for r in subject_records if r["match_status"] == "matched"),
                default=None,
            ),
        }
    total_track_instances = sum(len(values) for values in tracks_by_frame.values())
    summary = {
        "run_id": args.run_id,
        "video_id": video_id,
        "total_frames": total_frames,
        "total_person_frames": total_track_instances,
        "total_pose_instances": sum(len(values) for values in poses_by_frame.values()),
        "total_output_records": len(all_records),
        "matched_pairs": status_counts["matched"],
        "matched_rate": (
            status_counts["matched"] / total_track_instances if total_track_instances else 0.0
        ),
        "unmatched_tracks": status_counts["unmatched_track"],
        "unmatched_poses": status_counts["unmatched_pose"],
        "ambiguous_poses": status_counts["ambiguous_pose"],
        "phantom_poses": status_counts["phantom_pose"],
        "match_statistics": {status: status_counts[status] for status in sorted(VALID_STATUSES)},
        "match_cost_statistics": {
            "mean": sum(matched_costs) / len(matched_costs) if matched_costs else None,
            "min": min(matched_costs, default=None),
            "max": max(matched_costs, default=None),
        },
        "per_subject": per_subject,
        "valid_frames_by_subject_id": {
            subject: values["valid_frames"] for subject, values in per_subject.items()
        },
        "anomaly_frames": {
            str(frame): {
                "manual_status": status,
                "automatic_handling": anomaly_details[str(frame)],
                "records": [
                    {
                        "pose_index": record["pose_index"],
                        "track_id": record["track_id"],
                        "subject_id": record["subject_id"],
                        "match_status": record["match_status"],
                    }
                    for record in records_by_frame[frame]
                ],
            }
            for frame, status in sorted(anomaly_status_by_frame.items())
        },
        "matching_params": {
            "iou_weight": args.iou_weight,
            "center_distance_weight": args.center_distance_weight,
            "cost_threshold": args.cost_threshold,
            "derived_bbox_method": "all_keypoints_with_confidence_gt_0",
            "center_distance_normalization": "MOT_bbox_diagonal",
            "assignment": "Hungarian_one_to_one",
            "anomaly_pose_selection": "lowest_valid_keypoint_count_then_mean_confidence",
        },
        "input_resolution": {
            "mot_review_priority": True,
            "mot_bbox_semantics": (
                "Automatic DeepSORT frame boxes filtered by the human-reviewed subject whitelist; "
                "the review CSV contains decisions but no corrected per-frame boxes."
            ),
            "excluded_track_ids": sorted(excluded_tracks),
            "subject_map_track_ids": sorted(mapping),
        },
        "inputs": {
            "video": str(video), "video_sha256": sha256_file(video),
            "mot_review": str(mot_review), "mot_review_sha256": sha256_file(mot_review),
            "subject_map": str(subject_map), "subject_map_sha256": sha256_file(subject_map),
            "mot_tracks": str(mot_tracks), "mot_tracks_sha256": sha256_file(mot_tracks),
            "pose_json_dir": str(pose_dir), "pose_json_count": len(pose_files),
            "pose_json_directory_sha256_before": raw_digest_before,
            "pose_json_directory_sha256_after": raw_digest_after,
            "manual_review_summary": str(manual_summary_path),
            "manual_review_summary_sha256": sha256_file(manual_summary_path),
        },
        "outputs": {
            "association_jsonl": str(output_jsonl),
            "visualization": visualization,
            "manual_review_template": str(review_template),
            "manual_review_frames": review_frames,
        },
        "runtime_seconds": time.perf_counter() - start_time,
        "annotation_version": ANNOTATION_VERSION,
        "automatic_result_only": True,
        "human_review_status": "pending",
        "scope_note": (
            "OpenPose people-array order was not used as identity. No filtering, interpolation, "
            "Kalman smoothing, or confidence clipping was performed."
        ),
    }
    output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "matched_pairs": summary["matched_pairs"],
        "matched_rate": summary["matched_rate"],
        "unmatched_tracks": summary["unmatched_tracks"],
        "unmatched_poses": summary["unmatched_poses"],
        "ambiguous_poses": summary["ambiguous_poses"],
        "phantom_poses": summary["phantom_poses"],
        "output_records": summary["total_output_records"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
