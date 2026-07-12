#!/usr/bin/env python3
"""Validate OpenPose BODY_25 JSON and record reproducible smoke-test statistics."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

JOINTS = {
    "right_shoulder": 2,
    "right_elbow": 3,
    "right_wrist": 4,
    "left_shoulder": 5,
    "left_elbow": 6,
    "left_wrist": 7,
}
FRAME_PATTERN = re.compile(r"_(\d+)_keypoints\.json$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate raw OpenPose BODY_25 JSON and generate summary/metadata."
    )
    parser.add_argument("--json-dir", required=True, type=Path)
    parser.add_argument("--input-video", required=True, type=Path)
    parser.add_argument("--rendered-video", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--expected-frames", required=True, type=int)
    parser.add_argument("--run-id", default="20260712_T03_001")
    parser.add_argument("--openpose-root", type=Path, default=Path("tools/openpose"))
    parser.add_argument("--runtime-file", type=Path)
    parser.add_argument("--net-resolution", default="-1x368")
    parser.add_argument("--number-people-max", type=int, default=6)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_video(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_frames,duration",
        "-show_entries", "format=duration", "-of", "json", str(path),
    ]
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    if not payload.get("streams"):
        raise ValueError(f"no readable video stream: {path}")
    stream = payload["streams"][0]
    numerator, denominator = stream["avg_frame_rate"].split("/", maxsplit=1)
    fps = float(numerator) / float(denominator)
    duration = float(stream.get("duration") or payload["format"]["duration"])
    frames = int(stream.get("nb_frames") or round(duration * fps))
    return {
        "codec": stream["codec_name"], "width": int(stream["width"]),
        "height": int(stream["height"]), "fps": fps,
        "total_frames": frames, "duration_sec": duration,
    }


def git_value(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments], check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def validate(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    files = sorted(args.json_dir.glob("*_keypoints.json"))
    errors: list[str] = []
    malformed_frames: list[str] = []
    invalid_people = 0
    confidence_out_of_range_values: list[float] = []
    confidence_out_of_range_records = 0
    confidence_out_of_range_frames: set[str] = set()
    frame_stats: list[dict[str, Any]] = []
    joint_present = collections.Counter({name: 0 for name in JOINTS})
    people_distribution: collections.Counter[int] = collections.Counter()
    person_instances = 0
    valid_keypoints_total = 0

    if len(files) != args.expected_frames:
        errors.append(f"JSON count {len(files)} != expected {args.expected_frames}")

    for ordinal, path in enumerate(files):
        match = FRAME_PATTERN.search(path.name)
        frame_index = int(match.group(1)) if match else ordinal
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            people = payload["people"]
            if not isinstance(people, list):
                raise TypeError("people is not a list")
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            malformed_frames.append(path.name)
            errors.append(f"{path.name}: {exc}")
            continue

        counts: list[int] = []
        confidences: list[float] = []
        frame_invalid = False
        for person_number, person in enumerate(people):
            values = person.get("pose_keypoints_2d") if isinstance(person, dict) else None
            if not isinstance(values, list) or len(values) != 75:
                invalid_people += 1
                frame_invalid = True
                errors.append(f"{path.name} person {person_number}: keypoint length != 75")
                continue
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
                invalid_people += 1
                frame_invalid = True
                errors.append(f"{path.name} person {person_number}: non-numeric value")
                continue
            if any(not math.isfinite(float(value)) for value in values):
                invalid_people += 1
                frame_invalid = True
                errors.append(f"{path.name} person {person_number}: NaN/Inf value")
                continue
            keypoints = [values[index:index + 3] for index in range(0, 75, 3)]
            out_of_range = [
                float(point[2]) for point in keypoints
                if float(point[2]) < 0 or float(point[2]) > 1
            ]
            if out_of_range:
                confidence_out_of_range_values.extend(out_of_range)
                confidence_out_of_range_records += 1
                confidence_out_of_range_frames.add(path.name)
                frame_invalid = True
            valid_confidences = [float(point[2]) for point in keypoints if float(point[2]) > 0]
            counts.append(len(valid_confidences))
            confidences.append(
                sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
            )
            valid_keypoints_total += len(valid_confidences)
            person_instances += 1
            for name, index in JOINTS.items():
                joint_present[name] += int(float(keypoints[index][2]) > 0)

        people_distribution[len(people)] += 1
        flagged = (
            len(people) == 0 or frame_invalid or any(count < 10 for count in counts)
            or any(confidence < 0.3 for confidence in confidences)
        )
        frame_stats.append({
            "frame_index": frame_index, "num_people": len(people),
            "person_keypoint_counts": counts,
            "mean_confidence": [round(value, 6) for value in confidences],
            "flagged": flagged,
        })

    if confidence_out_of_range_values:
        errors.append(
            f"{len(confidence_out_of_range_values)} confidence values in "
            f"{confidence_out_of_range_records} person records across "
            f"{len(confidence_out_of_range_frames)} frames are outside [0,1]"
        )

    missing = {
        name: (1.0 - joint_present[name] / person_instances if person_instances else None)
        for name in JOINTS
    }
    group_missing = {
        "shoulder": ((missing["right_shoulder"] + missing["left_shoulder"]) / 2)
        if person_instances else None,
        "elbow": ((missing["right_elbow"] + missing["left_elbow"]) / 2)
        if person_instances else None,
        "wrist": ((missing["right_wrist"] + missing["left_wrist"]) / 2)
        if person_instances else None,
    }
    summary = {
        "validation_passed": not errors,
        "errors": errors,
        "json_file_count": len(files),
        "malformed_frame_count": len(malformed_frames),
        "malformed_frames": malformed_frames,
        "invalid_person_records": invalid_people,
        "confidence_out_of_range_value_count": len(confidence_out_of_range_values),
        "confidence_out_of_range_person_records": confidence_out_of_range_records,
        "confidence_out_of_range_frame_count": len(confidence_out_of_range_frames),
        "confidence_out_of_range_min": min(confidence_out_of_range_values, default=None),
        "confidence_out_of_range_max": max(confidence_out_of_range_values, default=None),
        "frames_without_skeleton": sum(item["num_people"] == 0 for item in frame_stats),
        "people_per_frame_distribution": {
            str(key): value for key, value in sorted(people_distribution.items())
        },
        "person_instances": person_instances,
        "avg_people_per_frame": person_instances / len(frame_stats) if frame_stats else 0.0,
        "avg_valid_keypoints_per_person": (
            valid_keypoints_total / person_instances if person_instances else 0.0
        ),
        "joint_missing_rate": missing,
        "joint_group_missing_rate": group_missing,
        "flagged_frame_count": sum(item["flagged"] for item in frame_stats),
        "frame_stats": frame_stats,
    }
    return summary, errors


def main() -> int:
    args = parse_args()
    required = [args.json_dir, args.input_video, args.rendered_video, args.openpose_root]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing required path(s): " + ", ".join(missing))

    summary, errors = validate(args)
    input_probe = probe_video(args.input_video)
    rendered_probe = probe_video(args.rendered_video)
    if rendered_probe["codec"] != "h264":
        errors.append(f"rendered codec {rendered_probe['codec']} != h264")
    for field in ("width", "height", "total_frames"):
        if rendered_probe[field] != input_probe[field]:
            errors.append(
                f"rendered {field} {rendered_probe[field]} != input {input_probe[field]}"
            )
    summary["rendered_video"] = rendered_probe
    summary["validation_passed"] = not errors
    summary["errors"] = errors

    runtime_seconds = None
    if args.runtime_file:
        runtime_seconds = float(args.runtime_file.read_text(encoding="utf-8").strip())
    openpose_commit = git_value(args.openpose_root, "rev-parse", "HEAD")
    project_commit = git_value(Path.cwd(), "rev-parse", "HEAD")
    statistics = {
        key: summary[key] for key in (
            "frames_without_skeleton", "avg_people_per_frame",
            "avg_valid_keypoints_per_person", "people_per_frame_distribution",
            "joint_missing_rate", "joint_group_missing_rate", "flagged_frame_count",
        )
    }
    statistics["total_frames_processed"] = summary["json_file_count"]
    statistics["processing_seconds"] = runtime_seconds
    statistics["processing_fps"] = (
        summary["json_file_count"] / runtime_seconds if runtime_seconds else None
    )
    metadata = {
        "run_id": args.run_id,
        "experiment": "T03 OpenPose BODY_25 build and minimal closed-loop test",
        "video": {
            "video_id": args.input_video.stem, "sha256": sha256_file(args.input_video),
            **{key: input_probe[key] for key in ("fps", "width", "height", "total_frames", "duration_sec")},
        },
        "mot_review": {
            "review_csv": "data/mot/reviewed/three-people-walking.csv",
            "subject_map_csv": "data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv",
            "main_subjects": ["P001", "P002", "P003"],
            "excluded": ["track_id 4 = confirmed_false_positive"],
        },
        "openpose": {
            "git_commit": openpose_commit, "model": "BODY_25",
            "net_resolution": args.net_resolution,
            "number_people_max": args.number_people_max, "gpu_mode": True,
            "gpu_name": "NVIDIA GeForce RTX 3090",
            "build_cmake_flags": (
                "GPU_MODE=CUDA; CUDA_TOOLKIT_ROOT_DIR=/home/a531/CUDA11.3.0; "
                "USE_CUDNN=ON; CUDA_ARCH_BIN=8.6; BUILD_PYTHON=OFF"
            ),
            "model_sha256": sha256_file(args.openpose_root / "models/pose/body_25/pose_iter_584000.caffemodel"),
        },
        "statistics": statistics,
        "validation": {
            "passed": summary["validation_passed"],
            "malformed_frame_count": summary["malformed_frame_count"],
            "invalid_person_records": summary["invalid_person_records"],
            "confidence_out_of_range_value_count": summary[
                "confidence_out_of_range_value_count"
            ],
            "confidence_out_of_range_frame_count": summary[
                "confidence_out_of_range_frame_count"
            ],
            "rendered_video_readable": True,
        },
        "environment": {
            "cuda_version": "11.3 (project-local toolkit)",
            "driver_version": "550.144.03", "gcc_version": "9.4.0",
        },
        "git_commit": project_commit,
        "artifact_semantics": (
            "OpenPose automatic output. people array order is NOT identity. "
            "Association with subject_id is deferred to T04."
        ),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    args.metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "validation_passed": summary["validation_passed"],
        "json_file_count": summary["json_file_count"],
        "malformed_frame_count": summary["malformed_frame_count"],
        "frames_without_skeleton": summary["frames_without_skeleton"],
        "person_instances": summary["person_instances"],
    }, indent=2))
    return 0 if summary["validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
