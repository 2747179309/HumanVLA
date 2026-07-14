#!/usr/bin/env python3
"""Independently validate T07A raw upper-limb trajectory outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

EXPECTED_WRIST_MISSING = {64, 65, 143, 182, 183, 184, 185}
EXPECTED_LOW_QUALITY_ELBOW = {64, 65, 143}
EXPECTED_UNSTABLE_ELBOW = {182, 183, 184, 185}
LOCKED_HASHES = {
    "p001": "36ded0a2f3c903e2dc9613709dbd2454a5078a0fe838ccc5ed32e1743a76ee5a",
    "quality_mask": "b98397817df55b93efe903469f1070a88349a30f95eedbc2e8c512b8f4ccf273",
    "phase_frames": "a9b42220053136d3751cbf3de699680f5e63a1e4161b3e23bd53e60c0392301f",
    "t06c_validation": "9d65c1605b95343def57d1f0563f270e30eba8b748c3663ae88e8867ad0f0393",
    "video": "c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2",
}
COORDINATE_FIELDS = (
    "neck_x_px", "neck_y_px", "neck_x_norm", "neck_y_norm", "shoulder_width_px",
    "rshoulder_x_px", "rshoulder_y_px", "rshoulder_x_norm", "rshoulder_y_norm",
    "relbow_x_px", "relbow_y_px", "relbow_x_norm", "relbow_y_norm",
    "rwrist_x_px", "rwrist_y_px", "rwrist_x_norm", "rwrist_y_norm",
    "lshoulder_x_px", "lshoulder_y_px", "lshoulder_x_norm", "lshoulder_y_norm",
    "neck_dx_from_first_valid_px", "neck_dy_from_first_valid_px",
    "neck_frame_dx_px", "neck_frame_dy_px",
    "neck_frame_displacement_px", "rshoulder_frame_displacement_px",
    "lshoulder_frame_displacement_px", "rshoulder_frame_dx_px",
    "rshoulder_frame_dy_px", "lshoulder_frame_dx_px", "lshoulder_frame_dy_px",
)
REQUIRED_FIELDS = {
    "video_id", "frame_index", "timestamp_sec", "subject_id", "source_pose_index",
    "phase_id", "phase_label", *COORDINATE_FIELDS, "raw_confidence",
    "trajectory_valid", "trajectory_quality", "quality_reason", "source_observation_status",
    "normalization_anchor_valid", "normalization_origin", "normalization_scale",
    "first_valid_anchor_frame", "absolute_pixel_coordinates_preserved",
    "relbow_coordinate_available", "relbow_joint_valid", "relbow_source_status",
    "relbow_effective_status", "relbow_manual_status", "relbow_quality_reason",
    "rwrist_coordinate_available", "rwrist_joint_valid", "rwrist_source_status",
    "rwrist_effective_status", "rwrist_manual_status", "rwrist_quality_reason",
    "interpolated", "filtered", "source", "annotation_version",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate T07A JSONL/CSV, normalization, missingness, summary, plot, video, and input hashes."
    )
    parser.add_argument("--p001", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--phase-frames", required=True, type=Path)
    parser.add_argument("--t06c-validation", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--trajectory-jsonl", required=True, type=Path)
    parser.add_argument("--trajectory-csv", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--plot", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--expected-frames", type=int, default=345)
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


def csv_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def close(first: float | None, second: float, tolerance: float = 1e-9) -> bool:
    return first is not None and math.isclose(first, second, rel_tol=0.0, abs_tol=tolerance)


def video_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(result.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"], "width": int(stream["width"]),
        "height": int(stream["height"]), "fps": stream["avg_frame_rate"],
        "frames": int(stream["nb_read_frames"]),
    }


def main() -> int:
    args = parse_args()
    paths = [
        args.p001, args.quality_mask, args.phase_frames, args.t06c_validation, args.video,
        args.trajectory_jsonl, args.trajectory_csv, args.summary, args.plot, args.overlay,
    ]
    if missing := [str(path) for path in paths if not path.exists()]:
        raise FileNotFoundError("missing input/output(s): " + ", ".join(missing))
    errors: list[str] = []
    source_paths = {
        "p001": args.p001, "quality_mask": args.quality_mask,
        "phase_frames": args.phase_frames, "t06c_validation": args.t06c_validation,
        "video": args.video,
    }
    current_hashes = {name: sha256_file(path) for name, path in source_paths.items()}
    for name, expected in LOCKED_HASHES.items():
        if current_hashes[name] != expected:
            errors.append(f"locked input hash changed: {name}={current_hashes[name]}")

    p001 = load_jsonl(args.p001)
    masks = load_jsonl(args.quality_mask)
    phases = load_jsonl(args.phase_frames)
    trajectory = load_jsonl(args.trajectory_jsonl)
    for name, rows in (("P001", p001), ("quality mask", masks), ("phase frames", phases), ("trajectory", trajectory)):
        if len(rows) != args.expected_frames:
            errors.append(f"{name} has {len(rows)} rows")
        if [row.get("frame_index") for row in rows] != list(range(args.expected_frames)):
            errors.append(f"{name} frame coverage/order is invalid")

    t06c = json.loads(args.t06c_validation.read_text(encoding="utf-8"))
    artifact = t06c.get("manual_review", {}).get("excluded_pose_artifacts", [])
    if not any(item.get("frame_index") == 226 and item.get("pose_index") == 1 for item in artifact):
        errors.append("T06C frame 226 reflection artifact exclusion is absent")

    for frame, (pose, mask, phase, row) in enumerate(zip(p001, masks, phases, trajectory)):
        absent = REQUIRED_FIELDS - set(row)
        if absent:
            errors.append(f"frame {frame}: missing fields {sorted(absent)}")
            continue
        if row["video_id"] != "pick_place_pilot_v1_E001" or row["subject_id"] != "P001":
            errors.append(f"frame {frame}: identity mismatch")
        if row["phase_id"] != phase["phase_id"] or row["phase_label"] != phase["phase_label"]:
            errors.append(f"frame {frame}: phase mismatch")
        if row["timestamp_sec"] != phase["timestamp_sec"]:
            errors.append(f"frame {frame}: timestamp mismatch")
        if row["normalization_origin"] != "Neck" or row["normalization_scale"] != "shoulder_width":
            errors.append(f"frame {frame}: forbidden normalization strategy")
        if row["absolute_pixel_coordinates_preserved"] is not True:
            errors.append(f"frame {frame}: absolute pixel preservation flag is not true")
        if row["interpolated"] is not False or row["filtered"] is not False:
            errors.append(f"frame {frame}: interpolation/filter flag is not false")
        if not isinstance(row["raw_confidence"], list) or len(row["raw_confidence"]) != 5:
            errors.append(f"frame {frame}: raw_confidence length != 5")
        elif row["raw_confidence"] != [pose["confidence_raw"][index] for index in (1, 2, 3, 4, 5)]:
            errors.append(f"frame {frame}: raw confidence changed")

        if frame in {0, 1}:
            if any(row[field] is not None for field in COORDINATE_FIELDS):
                errors.append(f"frame {frame}: invalid identity frame has coordinates")
            if row["trajectory_valid"] or row["normalization_anchor_valid"]:
                errors.append(f"frame {frame}: invalid identity marked valid")
            continue

        keypoints = pose["keypoints_raw"]
        neck, right_shoulder, left_shoulder = keypoints[1], keypoints[2], keypoints[5]
        width = math.hypot(right_shoulder[0] - left_shoulder[0], right_shoulder[1] - left_shoulder[1])
        if width <= 0 or not close(row["shoulder_width_px"], width):
            errors.append(f"frame {frame}: shoulder width formula mismatch")
            continue
        expected_pixels = {
            "neck": neck, "rshoulder": right_shoulder, "lshoulder": left_shoulder,
        }
        for prefix, value in expected_pixels.items():
            if not close(row[f"{prefix}_x_px"], value[0]) or not close(row[f"{prefix}_y_px"], value[1]):
                errors.append(f"frame {frame}: {prefix} raw pixel changed")
        if not close(row["neck_x_norm"], 0.0) or not close(row["neck_y_norm"], 0.0):
            errors.append(f"frame {frame}: Neck is not normalized origin")
        first_neck = p001[2]["keypoints_raw"][1]
        if row["first_valid_anchor_frame"] != 2:
            errors.append(f"frame {frame}: first valid anchor frame is not 2")
        if not close(row["neck_dx_from_first_valid_px"], neck[0] - first_neck[0]):
            errors.append(f"frame {frame}: Neck dx from first valid frame mismatch")
        if not close(row["neck_dy_from_first_valid_px"], neck[1] - first_neck[1]):
            errors.append(f"frame {frame}: Neck dy from first valid frame mismatch")
        if frame == 2:
            for field in (
                "neck_frame_dx_px", "neck_frame_dy_px",
                "neck_frame_displacement_px", "rshoulder_frame_displacement_px",
                "lshoulder_frame_displacement_px", "rshoulder_frame_dx_px",
                "rshoulder_frame_dy_px", "lshoulder_frame_dx_px", "lshoulder_frame_dy_px",
            ):
                if row[field] is not None:
                    errors.append(f"frame 2: {field} must be null without a prior valid anchor")
        else:
            previous_keypoints = p001[frame - 1]["keypoints_raw"]
            for field, joint_id in (
                ("neck_frame_displacement_px", 1),
                ("rshoulder_frame_displacement_px", 2),
                ("lshoulder_frame_displacement_px", 5),
            ):
                prefix = field.removesuffix("_frame_displacement_px")
                expected_dx = keypoints[joint_id][0] - previous_keypoints[joint_id][0]
                expected_dy = keypoints[joint_id][1] - previous_keypoints[joint_id][1]
                if not close(row[f"{prefix}_frame_dx_px"], expected_dx):
                    errors.append(f"frame {frame}: {prefix}_frame_dx_px mismatch")
                if not close(row[f"{prefix}_frame_dy_px"], expected_dy):
                    errors.append(f"frame {frame}: {prefix}_frame_dy_px mismatch")
                expected_displacement = math.hypot(expected_dx, expected_dy)
                if not close(row[field], expected_displacement):
                    errors.append(f"frame {frame}: {field} mismatch")
        for prefix, joint_id in (("rshoulder", 2), ("lshoulder", 5)):
            if not close(row[f"{prefix}_x_norm"], (keypoints[joint_id][0] - neck[0]) / width):
                errors.append(f"frame {frame}: {prefix} x normalization mismatch")
            if not close(row[f"{prefix}_y_norm"], (keypoints[joint_id][1] - neck[1]) / width):
                errors.append(f"frame {frame}: {prefix} y normalization mismatch")

        elbow = keypoints[3]
        if elbow[2] <= 0:
            errors.append(f"frame {frame}: unexpected RElbow raw missing")
        else:
            if not close(row["relbow_x_px"], elbow[0]) or not close(row["relbow_y_px"], elbow[1]):
                errors.append(f"frame {frame}: RElbow raw pixel was not preserved")
            if not close(row["relbow_x_norm"], (elbow[0] - neck[0]) / width) or not close(row["relbow_y_norm"], (elbow[1] - neck[1]) / width):
                errors.append(f"frame {frame}: RElbow normalization mismatch")
        if frame in EXPECTED_LOW_QUALITY_ELBOW:
            if row["relbow_source_status"] != "low_quality" or row["relbow_effective_status"] != "low_quality":
                errors.append(f"frame {frame}: low-quality RElbow was promoted")
        if frame in EXPECTED_UNSTABLE_ELBOW:
            if row["relbow_manual_status"] != "unstable" or row["relbow_effective_status"] != "low_quality":
                errors.append(f"frame {frame}: manual unstable RElbow was promoted")

        wrist_fields = ("rwrist_x_px", "rwrist_y_px", "rwrist_x_norm", "rwrist_y_norm")
        if frame in EXPECTED_WRIST_MISSING:
            if any(row[field] is not None for field in wrist_fields):
                errors.append(f"frame {frame}: missing RWrist contains coordinates")
            if row["rwrist_coordinate_available"] or row["trajectory_valid"]:
                errors.append(f"frame {frame}: missing RWrist marked trajectory valid")
        else:
            wrist = keypoints[4]
            if not close(row["rwrist_x_px"], wrist[0]) or not close(row["rwrist_y_px"], wrist[1]):
                errors.append(f"frame {frame}: RWrist raw pixel changed")
            if not close(row["rwrist_x_norm"], (wrist[0] - neck[0]) / width) or not close(row["rwrist_y_norm"], (wrist[1] - neck[1]) / width):
                errors.append(f"frame {frame}: RWrist normalization mismatch")
        if frame == 226 and (row["source_pose_index"] != 0 or not row["trajectory_valid"]):
            errors.append("frame 226 did not retain valid P001 pose_index=0")

    with args.trajectory_csv.open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != len(trajectory):
        errors.append(f"CSV has {len(csv_rows)} rows, expected {len(trajectory)}")
    else:
        for frame, (json_row, csv_row) in enumerate(zip(trajectory, csv_rows)):
            if set(csv_row) != set(json_row):
                errors.append(f"CSV field set mismatch at frame {frame}")
                break
            if any(csv_row[key] != csv_value(value) for key, value in json_row.items()):
                errors.append(f"CSV value mismatch at frame {frame}")
                break

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    if summary.get("total_frames") != args.expected_frames:
        errors.append("summary total_frames mismatch")
    if summary.get("coordinate_system", {}).get("pelvis_or_lower_body_used") is not False:
        errors.append("summary indicates pelvis/lower body use")
    if summary.get("processing_policy", {}).get("interpolation") is not False or summary.get("processing_policy", {}).get("filtering") is not False:
        errors.append("summary interpolation/filtering policy mismatch")
    policy = summary.get("processing_policy", {})
    if policy.get("neck_and_shoulders_forced_fixed") is not False or policy.get("neck_and_shoulders_modified") is not False:
        errors.append("summary incorrectly fixes or modifies Neck/shoulder coordinates")
    review = summary.get("human_review_supplement", {})
    correction = review.get("abnormal_frame_correction", {})
    if correction != {"correct_frame": 143, "incorrect_frame": 43}:
        errors.append("summary abnormal-frame correction is not 143-not-43")
    if review.get("occlusion_affected_frames") != sorted(EXPECTED_WRIST_MISSING):
        errors.append("summary human-review occlusion frames mismatch")
    future_policy = summary.get("future_simulation_mapping_policy", {})
    if future_policy.get("neck_relative_trajectory_alone_is_sufficient") is not False:
        errors.append("summary permits Neck-relative-only future mapping")
    if future_policy.get("preserve_absolute_pixel_trajectory") is not True:
        errors.append("summary does not preserve absolute pixel trajectory")
    if future_policy.get("preserve_tabletop_path_and_A_B_references") is not True:
        errors.append("summary does not retain tabletop/A-B mapping requirement")
    expected_source_hashes = {
        str(args.p001): current_hashes["p001"], str(args.quality_mask): current_hashes["quality_mask"],
        str(args.phase_frames): current_hashes["phase_frames"],
        str(args.t06c_validation): current_hashes["t06c_validation"],
        str(args.trajectory_jsonl): sha256_file(args.trajectory_jsonl),
    }
    if summary.get("input_hashes") != expected_source_hashes:
        errors.append("summary input hashes differ from current files")
    if summary.get("missing_frames") != [0, 1] or summary.get("missing_joints", {}).get("RWrist") != sorted(EXPECTED_WRIST_MISSING):
        errors.append("summary missing frame/joint lists mismatch")
    if summary.get("validity", {}).get("relbow", {}).get("coordinate_available_frames") != 343:
        errors.append("summary RElbow coordinate count != 343")
    if summary.get("validity", {}).get("relbow", {}).get("source_joint_valid_frames") != 340:
        errors.append("summary RElbow source-valid count != 340")
    if summary.get("validity", {}).get("rwrist", {}).get("coordinate_available_frames") != 336:
        errors.append("summary RWrist valid count != 336")
    shoulder = summary.get("shoulder_width_stats", {})
    widths = [row["shoulder_width_px"] for row in trajectory if row["shoulder_width_px"] is not None]
    if shoulder.get("valid_frame_count") != 343:
        errors.append("shoulder valid-frame count !=343")
    for key, expected in (
        ("mean_px", sum(widths) / len(widths)), ("min_px", min(widths)), ("max_px", max(widths)),
    ):
        if not close(shoulder.get(key), expected):
            errors.append(f"shoulder summary {key} mismatch")
    absolute_motion = summary.get("absolute_motion", {})
    if absolute_motion.get("first_valid_anchor_frame") != 2:
        errors.append("summary first valid anchor frame mismatch")
    for label, field in (
        ("Neck", "neck_frame_displacement_px"),
        ("RShoulder", "rshoulder_frame_displacement_px"),
        ("LShoulder", "lshoulder_frame_displacement_px"),
    ):
        expected_count = sum(row[field] is not None for row in trajectory)
        actual_count = absolute_motion.get("consecutive_frame_displacement", {}).get(label, {}).get("frame_count")
        if actual_count != expected_count:
            errors.append(f"summary {label} displacement count mismatch")
    phase_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trajectory:
        phase_groups[row["phase_label"]].append(row)
    for label, rows in phase_groups.items():
        item = summary.get("per_phase_statistics", {}).get(label, {})
        if item.get("frame_count") != len(rows):
            errors.append(f"phase {label} frame count mismatch")
        if item.get("rwrist_valid_frames") != sum(row["rwrist_coordinate_available"] for row in rows):
            errors.append(f"phase {label} RWrist count mismatch")

    with Image.open(args.plot) as image:
        plot_info = {"format": image.format, "width": image.width, "height": image.height}
    if plot_info["format"] != "PNG" or plot_info["width"] < 1000 or plot_info["height"] < 500:
        errors.append(f"plot format/dimensions invalid: {plot_info}")
    overlay_info = video_probe(args.overlay)
    expected_video = {"codec": "h264", "width": 1280, "height": 720, "fps": "30/1", "frames": 345}
    if overlay_info != expected_video:
        errors.append(f"overlay metadata mismatch: {overlay_info}")
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(args.overlay), "-f", "null", "-"], capture_output=True)
    if decode.returncode:
        errors.append("overlay full decode failed: " + decode.stderr.decode(errors="replace"))

    result = {
        "validation_passed": not errors, "errors": errors,
        "total_frames": len(trajectory), "input_hashes": current_hashes,
        "trajectory_jsonl_sha256": sha256_file(args.trajectory_jsonl),
        "trajectory_csv_sha256": sha256_file(args.trajectory_csv),
        "summary_sha256": sha256_file(args.summary), "plot": plot_info,
        "overlay": overlay_info, "overlay_full_decode_passed": decode.returncode == 0,
        "checks": {
            "frame_0_1_all_coordinates_null": not any("invalid identity frame has coordinates" in error for error in errors),
            "forced_rwrist_missing_null": not any("missing RWrist contains coordinates" in error for error in errors),
            "low_quality_relbow_raw_preserved": not any("RElbow raw pixel" in error or "RElbow was promoted" in error for error in errors),
            "frame_226_artifact_excluded": not any("frame 226" in error for error in errors),
            "normalization_formula": not any("normalization mismatch" in error or "normalized origin" in error for error in errors),
            "absolute_neck_and_shoulder_motion": not any(
                "first valid anchor" in error or "frame_displacement_px" in error or "Neck dx" in error or "Neck dy" in error
                for error in errors
            ),
            "no_interpolation_or_filtering": not any("interpolation/filter" in error for error in errors),
            "csv_matches_jsonl": not any("CSV" in error for error in errors),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
