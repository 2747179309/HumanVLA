#!/usr/bin/env python3
"""Associate BODY_25 poses with one human-confirmed operator track."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

ANNOTATION_VERSION = "t06c_v0.1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Associate raw BODY_25 poses to a human-confirmed single-operator MOT track."
    )
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--pose-json-dir", required=True, type=Path)
    parser.add_argument("--mot-tracks", required=True, type=Path)
    parser.add_argument("--subject-map", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--manual-review", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
    parser.add_argument("--iou-weight", type=float, default=0.6)
    parser.add_argument("--center-weight", type=float, default=0.4)
    parser.add_argument("--cost-threshold", type=float, default=0.5)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_digest(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def pose_bbox(keypoints: list[list[float]]) -> list[float] | None:
    visible = [(point[0], point[1]) for point in keypoints if point[2] > 0]
    if not visible:
        return None
    xs, ys = zip(*visible)
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_iou(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    area_b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def pair_metrics(track_box: list[float], pose_box: list[float] | None) -> tuple[float, float, float]:
    if pose_box is None:
        return math.inf, 0.0, math.inf
    iou = bbox_iou(track_box, pose_box)
    tcx, tcy = (track_box[0] + track_box[2]) / 2, (track_box[1] + track_box[3]) / 2
    pcx, pcy = (pose_box[0] + pose_box[2]) / 2, (pose_box[1] + pose_box[3]) / 2
    diagonal = math.hypot(track_box[2] - track_box[0], track_box[3] - track_box[1])
    center_distance = math.hypot(tcx - pcx, tcy - pcy) / diagonal if diagonal else math.inf
    return 0.6 * (1.0 - iou) + 0.4 * center_distance, iou, center_distance


def load_subject_map(path: Path, video_id: str) -> tuple[int, str, int, int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    eligible = [
        row for row in rows
        if row.get("video_id") == video_id and row.get("include_for_pose") == "1"
    ]
    if len(eligible) != 1:
        raise ValueError(f"expected one included subject-map row, found {len(eligible)}")
    row = eligible[0]
    if row.get("subject_id") != "P001" or row.get("review_status") != "human_confirmed":
        raise ValueError("subject map must contain a human-confirmed P001")
    return int(row["track_id"]), row["subject_id"], int(row["valid_from_frame"]), int(row["valid_to_frame"]), row


def load_tracks(path: Path, video_id: str, track_id: int, start: int, end: int) -> dict[int, dict[str, Any]]:
    tracks: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record["video_id"] != video_id or int(record["track_id"]) != track_id:
                continue
            frame = int(record["frame_index"])
            if not start <= frame <= end:
                continue
            if frame in tracks:
                raise ValueError(f"duplicate track record for frame {frame}")
            box = [float(value) for value in record["bbox_xyxy"]]
            if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError(f"invalid MOT bbox at line {line_number}")
            tracks[frame] = {**record, "bbox_xyxy": box}
    return tracks


def load_poses(path: Path, expected_frames: int) -> tuple[dict[int, list[dict[str, Any]]], list[Path]]:
    files = sorted(path.glob("*_keypoints.json"))
    if len(files) != expected_frames:
        raise ValueError(f"OpenPose JSON count {len(files)} != {expected_frames}")
    poses: dict[int, list[dict[str, Any]]] = {}
    for frame, json_path in enumerate(files):
        if not json_path.name.endswith(f"_{frame:012d}_keypoints.json"):
            raise ValueError(f"non-contiguous OpenPose filename: {json_path.name}")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        people = payload.get("people")
        if not isinstance(people, list):
            raise ValueError(f"people is not a list: {json_path}")
        frame_poses = []
        for pose_index, person in enumerate(people):
            flat = person.get("pose_keypoints_2d")
            if not isinstance(flat, list) or len(flat) != 75:
                raise ValueError(f"invalid BODY_25: frame={frame}, pose={pose_index}")
            keypoints = [[float(flat[i]), float(flat[i + 1]), float(flat[i + 2])] for i in range(0, 75, 3)]
            frame_poses.append({
                "pose_index": pose_index,
                "keypoints": keypoints,
                "confidence_raw": [point[2] for point in keypoints],
                "pose_bbox_xyxy": pose_bbox(keypoints),
                "valid_keypoint_count": sum(point[2] > 0 for point in keypoints),
            })
        poses[frame] = frame_poses
    return poses, files


def pose_record(video_id: str, frame: int, fps: float, pose: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "frame_index": frame,
        "timestamp_sec": round(frame / fps, 6),
        "track_id": None,
        "subject_id": None,
        "bbox_xyxy": pose["pose_bbox_xyxy"],
        "track_bbox_xyxy": None,
        "pose_bbox_xyxy": pose["pose_bbox_xyxy"],
        "pose_index": pose["pose_index"],
        "pose_model": "OpenPose_BODY_25",
        "keypoints": pose["keypoints"],
        "confidence_raw": pose["confidence_raw"],
        "detection_confidence": None,
        "match_score": None,
        "match_cost": None,
        "match_iou": None,
        "center_distance": None,
        "match_status": status,
        "source": "openpose_deepsort_association",
        "annotation_version": ANNOTATION_VERSION,
    }


def main() -> int:
    args = parse_args()
    inputs = [args.video, args.pose_json_dir, args.mot_tracks, args.subject_map]
    if missing := [str(path) for path in inputs if not path.exists()]:
        raise FileNotFoundError("missing input(s): " + ", ".join(missing))
    outputs = [args.output_jsonl, args.summary, args.manual_review]
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))
    if not math.isclose(args.iou_weight + args.center_weight, 1.0):
        raise ValueError("IoU and center weights must sum to 1")
    if (args.iou_weight, args.center_weight) != (0.6, 0.4):
        raise ValueError("this locked T06C implementation uses weights 0.6 and 0.4")

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot decode video: {args.video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    if total_frames != args.expected_frames:
        raise ValueError(f"video frame count {total_frames} != {args.expected_frames}")

    track_id, subject_id, start, end, map_row = load_subject_map(args.subject_map, args.video_id)
    tracks = load_tracks(args.mot_tracks, args.video_id, track_id, start, end)
    poses, pose_files = load_poses(args.pose_json_dir, args.expected_frames)
    if sorted(tracks) != list(range(start, end + 1)):
        raise ValueError("confirmed operator track is not continuous over its mapped range")
    raw_digest_before = directory_digest(pose_files)

    records: list[dict[str, Any]] = []
    by_frame: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frame in range(args.expected_frames):
        track = tracks.get(frame)
        frame_poses = poses[frame]
        assigned: set[int] = set()
        if track is not None and frame_poses:
            costs = np.array([[pair_metrics(track["bbox_xyxy"], pose["pose_bbox_xyxy"])[0] for pose in frame_poses]])
            rows, columns = linear_sum_assignment(costs)
            for row, column in zip(rows.tolist(), columns.tolist()):
                cost, iou, distance = pair_metrics(track["bbox_xyxy"], frame_poses[column]["pose_bbox_xyxy"])
                if cost >= args.cost_threshold:
                    continue
                record = pose_record(args.video_id, frame, fps, frame_poses[column], "matched")
                record.update({
                    "track_id": track_id,
                    "subject_id": subject_id,
                    "bbox_xyxy": track["bbox_xyxy"],
                    "track_bbox_xyxy": track["bbox_xyxy"],
                    "detection_confidence": float(track["detection_confidence"]),
                    "match_cost": round(cost, 8),
                    "match_score": round(1.0 - cost, 8),
                    "match_iou": round(iou, 8),
                    "center_distance": round(distance, 8),
                })
                records.append(record)
                by_frame[frame].append(record)
                assigned.add(column)
        if track is not None and not assigned:
            record = {
                "video_id": args.video_id, "frame_index": frame,
                "timestamp_sec": round(frame / fps, 6), "track_id": track_id,
                "subject_id": subject_id, "bbox_xyxy": track["bbox_xyxy"],
                "track_bbox_xyxy": track["bbox_xyxy"], "pose_bbox_xyxy": None,
                "pose_index": None, "pose_model": "OpenPose_BODY_25", "keypoints": None,
                "confidence_raw": None, "detection_confidence": float(track["detection_confidence"]),
                "match_score": None, "match_cost": None, "match_iou": None,
                "center_distance": None, "match_status": "unmatched_track",
                "source": "openpose_deepsort_association", "annotation_version": ANNOTATION_VERSION,
            }
            records.append(record)
            by_frame[frame].append(record)
        for pose_index, pose in enumerate(frame_poses):
            if pose_index not in assigned:
                record = pose_record(args.video_id, frame, fps, pose, "unmatched_pose")
                records.append(record)
                by_frame[frame].append(record)

    for frame_records in by_frame.values():
        if sum(record["subject_id"] == subject_id for record in frame_records) > 1:
            raise RuntimeError(f"multiple P001 records at frame {frame}")
    raw_digest_after = directory_digest(pose_files)
    if raw_digest_before != raw_digest_after:
        raise RuntimeError("raw OpenPose JSON changed during association")

    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as stream:
        for record in sorted(records, key=lambda item: (item["frame_index"], item["pose_index"] is None, item["pose_index"] or 0)):
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    unmatched = [record for record in records if record["match_status"] in {"unmatched_pose", "unmatched_track"}]
    with args.manual_review.open("w", encoding="utf-8", newline="") as stream:
        fields = ["video_id", "frame_index", "pose_index", "automatic_status", "reason", "reviewer_decision", "notes"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in unmatched:
            reason = "no_confirmed_track_identity" if record["frame_index"] < start else (
                "extra_pose_not_assigned_to_P001" if record["match_status"] == "unmatched_pose" else "no_reliable_pose_match"
            )
            writer.writerow({
                "video_id": args.video_id, "frame_index": record["frame_index"],
                "pose_index": "" if record["pose_index"] is None else record["pose_index"],
                "automatic_status": record["match_status"], "reason": reason,
                "reviewer_decision": "pending", "notes": "",
            })

    statuses = Counter(record["match_status"] for record in records)
    match_costs = [record["match_cost"] for record in records if record["match_status"] == "matched"]
    multi_pose_frames = [frame for frame in range(args.expected_frames) if len(poses[frame]) > 1]
    summary = {
        "video_id": args.video_id, "total_frames": args.expected_frames,
        "raw_json_count": len(pose_files), "raw_pose_count": sum(map(len, poses.values())),
        "people_per_frame_distribution": dict(sorted(Counter(map(len, poses.values())).items())),
        "multi_pose_frames": multi_pose_frames, "confirmed_track_id": track_id,
        "confirmed_subject_id": subject_id, "confirmed_track_frames": len(tracks),
        "confirmed_track_range": [start, end], "identity_review_status": map_row["review_status"],
        "matched_pairs": statuses["matched"],
        "association_rate_over_confirmed_track_frames": statuses["matched"] / len(tracks),
        "unmatched_tracks": statuses["unmatched_track"], "unmatched_poses": statuses["unmatched_pose"],
        "unmatched_pose_instances": [
            {"frame_index": record["frame_index"], "pose_index": record["pose_index"],
             "valid_keypoint_count": sum(value > 0 for value in record["confidence_raw"])}
            for record in records if record["match_status"] == "unmatched_pose"
        ],
        "match_cost": {"mean": float(np.mean(match_costs)), "min": min(match_costs), "max": max(match_costs)},
        "matching": {"assignment": "Hungarian_one_to_one", "iou_weight": args.iou_weight,
                     "center_weight": args.center_weight, "cost_threshold": args.cost_threshold,
                     "pose_bbox": "all_BODY_25_joints_with_confidence_gt_0",
                     "people_array_order_used_as_identity": False},
        "inputs": {"video": str(args.video), "video_sha256": sha256_file(args.video),
                   "mot_tracks": str(args.mot_tracks), "mot_tracks_sha256": sha256_file(args.mot_tracks),
                   "subject_map": str(args.subject_map), "subject_map_sha256": sha256_file(args.subject_map),
                   "pose_json_dir": str(args.pose_json_dir),
                   "pose_json_directory_sha256_before": raw_digest_before,
                   "pose_json_directory_sha256_after": raw_digest_after},
        "outputs": {"association_jsonl": str(args.output_jsonl), "manual_review": str(args.manual_review)},
        "raw_confidence_preserved": True, "filtering_or_interpolation": False,
        "annotation_version": ANNOTATION_VERSION, "human_review_status": "pending_for_unmatched_poses",
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("matched_pairs", "association_rate_over_confirmed_track_frames", "unmatched_tracks", "unmatched_poses", "multi_pose_frames")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
