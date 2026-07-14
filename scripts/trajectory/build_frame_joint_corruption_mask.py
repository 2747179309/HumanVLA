#!/usr/bin/env python3
"""Build the T07C-A frame/joint mask while separating raw and repaired layers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2


VIDEO_ID = "pick_place_pilot_v1_E001"
JOINTS = ("Neck", "RShoulder", "RElbow", "RWrist")
BODY25_INDEX = {"Neck": 1, "RShoulder": 2, "RElbow": 3, "RWrist": 4}
PREFIX = {"Neck": "neck", "RShoulder": "rshoulder", "RElbow": "relbow", "RWrist": "rwrist"}
ALLOWED_SOURCES = {"raw", "repaired", "none"}
TYPE_PRIORITY = {
    "occlusion_error": 6,
    "openpose_jitter": 5,
    "low_quality_observation": 4,
    "boundary_continuity_warning": 3,
    "normalization_artifact": 2,
    "real_motion": 1,
    "valid": 0,
}
ACTION_PRIORITY = {"mask": 3, "defer": 2, "downweight": 1, "keep": 0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the 345x4 T07C-A corruption mask and overlay.")
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--jump-review", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--repaired-trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--output-overlay", required=True, type=Path)
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


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_frames(text: str) -> set[int]:
    result: set[int] = set()
    for token in (part.strip() for part in text.split(",")):
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid frame range: {token}")
            result.update(range(start, end + 1))
        else:
            result.add(int(token))
    if any(frame < 0 or frame >= 345 for frame in result):
        raise ValueError(f"frame list is outside 0..344: {text}")
    return result


def add_event_evidence(
    evidence: dict[tuple[int, str], list[dict[str, Any]]], row: dict[str, str]
) -> None:
    required = (
        "manual_from_frame_status", "manual_to_frame_status", "manual_corruption_type",
        "manual_confidence", "manual_reason", "manual_proposed_action",
    )
    if any(not row[field].strip() for field in required):
        raise ValueError(f"{row['candidate_id']}: required manual decision is incomplete")
    joint = row["joint_name"]
    errors, valids = parse_frames(row["manual_error_frames"]), parse_frames(row["manual_valid_frames"])
    roles: dict[int, set[str]] = defaultdict(set)
    for frame in errors:
        roles[frame].add("manual_error_frames")
    for frame in valids:
        roles[frame].add("manual_valid_frames")
    endpoints = (
        (int(row["from_frame"]), row["manual_from_frame_status"], "from_frame_status"),
        (int(row["to_frame"]), row["manual_to_frame_status"], "to_frame_status"),
    )
    for frame, status, role in endpoints:
        roles[frame].add(role)
        if status == "corrupted":
            errors.add(frame)
        elif status == "valid":
            valids.add(frame)
        else:
            raise ValueError(f"{row['candidate_id']}: unsupported endpoint status {status}")
    candidate_frames = set(range(int(row["from_frame"]), int(row["to_frame"]) + 1))
    for frame in sorted(set(roles) | errors | valids):
        judgment = "conflict" if frame in errors and frame in valids else "error" if frame in errors else "valid"
        evidence[(frame, joint)].append({
            "source_event_id": row["source_event_id"],
            "candidate_id": row["candidate_id"],
            "source_type": row["source_type"],
            "judgment": judgment,
            "roles": sorted(roles[frame]),
            "candidate_interval_member": frame in candidate_frames,
            "manual_corruption_type": row["manual_corruption_type"],
            "manual_confidence": row["manual_confidence"],
            "manual_reason": row["manual_reason"],
            "manual_proposed_action": row["manual_proposed_action"],
        })


def add_real_motion_evidence(
    evidence: dict[tuple[int, str], list[dict[str, Any]]], jump_rows: list[dict[str, str]]
) -> None:
    real = [row for row in jump_rows if row["manual_label"] == "real_motion"]
    if len(real) != 3:
        raise ValueError(f"expected 3 real_motion events, found {len(real)}")
    for row in real:
        for frame, role in ((int(row["from_frame"]), "from_frame"), (int(row["to_frame"]), "to_frame")):
            evidence[(frame, row["joint_name"])].append({
                "source_event_id": row["candidate_id"],
                "candidate_id": row["candidate_id"],
                "source_type": "T07A_jump_candidate_review",
                "judgment": "valid",
                "roles": [role],
                "candidate_interval_member": True,
                "manual_corruption_type": "real_motion",
                "manual_confidence": row["manual_confidence"],
                "manual_reason": row["manual_note"],
                "manual_proposed_action": "keep",
            })


def coordinates_available(row: dict[str, Any], joint: str) -> bool:
    prefix = PREFIX[joint]
    return row.get(f"{prefix}_x_px") is not None and row.get(f"{prefix}_y_px") is not None


def base_raw_status(raw: dict[str, Any], quality: dict[str, Any], joint: str) -> tuple[str, bool]:
    if joint in {"RElbow", "RWrist"}:
        status = str(raw[f"{PREFIX[joint]}_effective_status"])
        return status, status == "valid" and coordinates_available(raw, joint)
    index = BODY25_INDEX[joint]
    status = str(quality["joint_observation_status"][index])
    return status, bool(quality["joint_valid"][index]) and coordinates_available(raw, joint)


def primary(values: set[str], priorities: dict[str, int], default: str) -> str:
    return max(values, key=lambda item: priorities[item]) if values else default


def build_record(
    frame: int,
    joint: str,
    raw: dict[str, Any],
    repaired: dict[str, Any],
    quality: dict[str, Any],
    manual_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    status, raw_valid = base_raw_status(raw, quality, joint)
    raw_available = coordinates_available(raw, joint)
    errors = [item for item in manual_evidence if item["judgment"] in {"error", "conflict"}]
    valids = [item for item in manual_evidence if item["judgment"] in {"valid", "conflict"}]
    evidence_conflict = bool(errors and valids)
    if errors:
        raw_valid = False
        if status != "missing":
            status = "manual_uncertain_corruption" if all(
                item["manual_proposed_action"] == "defer" for item in errors
            ) else "manual_corrupted"
    elif valids and raw_available:
        raw_valid = True
        status = "valid_manual_confirmed"

    repair_map = repaired.get("repair_applied", {})
    accepted_map = repaired.get("repair_acceptance", {})
    downstream_map = repaired.get("downstream_valid", {})
    repaired_available = bool(repair_map.get(joint, False))
    if joint == "RWrist":
        repaired_available = repaired_available and repaired.get("rwrist_x_repaired_px") is not None
    else:
        repaired_available = False
    repaired_valid = bool(
        repaired_available
        and accepted_map.get(joint) == "accepted"
        and downstream_map.get(joint) is True
    )
    repaired_status = "accepted" if repaired_valid else "rejected" if repaired_available else "not_available"

    types: set[str] = set()
    actions: set[str] = set()
    source_ids = {item["source_event_id"] for item in manual_evidence}
    for item in manual_evidence:
        if item["judgment"] in {"error", "conflict"}:
            types.add(item["manual_corruption_type"])
            actions.add(item["manual_proposed_action"])
        elif item["candidate_interval_member"] and item["manual_corruption_type"] in {
            "normalization_artifact", "real_motion"
        }:
            types.add(item["manual_corruption_type"])
            actions.add("keep")

    boundary_warning = bool(repaired.get("boundary_continuity_warning", {}).get(joint, False))
    if boundary_warning:
        types.add("boundary_continuity_warning")
        source_ids.add("T07B_BOUNDARY_RWrist_182_185")
    if repaired_available:
        source_ids.add(f"T07B_{repaired['repair_gap_id']}")
    if not raw_valid and not errors:
        source_ids.add("T06C_QUALITY_MASK")
        if status == "low_quality":
            types.add("low_quality_observation")
            actions.add("defer")
        elif joint == "RWrist" and raw.get("rwrist_quality_reason"):
            types.add("occlusion_error")
            actions.add("mask")

    corruption_type = primary(types, TYPE_PRIORITY, "valid")
    proposed_action = primary(actions, ACTION_PRIORITY, "keep" if raw_valid else "mask")
    action_conflict = len(actions) > 1
    if raw_valid:
        selected = "raw"
    elif repaired_valid:
        selected = "repaired"
    elif proposed_action == "downweight" and raw_available:
        selected = "raw"
    else:
        selected = "none"
    if selected not in ALLOWED_SOURCES:
        raise RuntimeError(f"unsupported downstream source {selected}")
    downstream_valid = selected != "none"
    defer_to = "T07C-B" if proposed_action == "defer" or (
        selected == "none" and corruption_type in {
            "occlusion_error", "openpose_jitter", "low_quality_observation"
        }
    ) else None
    return {
        "video_id": VIDEO_ID,
        "frame_index": frame,
        "timestamp_sec": raw["timestamp_sec"],
        "phase_label": raw["phase_label"],
        "joint_name": joint,
        "raw_observation_available": raw_available,
        "raw_observation_valid": raw_valid,
        "raw_observation_status": status,
        "repaired_observation_available": repaired_available,
        "repaired_observation_valid": repaired_valid,
        "repaired_observation_status": repaired_status,
        "selected_downstream_source": selected,
        "downstream_valid": downstream_valid,
        "source_event_ids": sorted(source_ids),
        "corruption_type": corruption_type,
        "corruption_types": sorted(types, key=lambda item: (-TYPE_PRIORITY[item], item)) or ["valid"],
        "proposed_action": proposed_action,
        "proposed_actions": sorted(actions, key=lambda item: (-ACTION_PRIORITY[item], item)) or [
            "keep" if raw_valid else proposed_action
        ],
        "boundary_continuity_warning": boundary_warning,
        "normalization_scale_warning": "normalization_artifact" in types,
        "manual_evidence_conflict": evidence_conflict,
        "manual_action_conflict": action_conflict,
        "manual_evidence": manual_evidence,
        "defer_to_task": defer_to,
        "downstream_use_mode": "downweight" if selected == "raw" and not raw_valid else "normal" if downstream_valid else "excluded",
        "filtered": False,
        "new_interpolation_performed": False,
        "annotation_version": "t07c_a_corruption_mask_v1.0.0",
    }


def selected_point(raw: dict[str, Any], repaired: dict[str, Any], mask: dict[str, Any]) -> tuple[int, int] | None:
    joint, source = mask["joint_name"], mask["selected_downstream_source"]
    prefix = PREFIX[joint]
    if source == "repaired" and joint == "RWrist":
        x, y = repaired["rwrist_x_repaired_px"], repaired["rwrist_y_repaired_px"]
    else:
        x, y = raw.get(f"{prefix}_x_px"), raw.get(f"{prefix}_y_px")
    return None if x is None or y is None else (round(float(x)), round(float(y)))


def render_overlay(
    video: Path,
    raw_rows: list[dict[str, Any]],
    repaired_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    output: Path,
) -> None:
    by_frame = {frame: {row["joint_name"]: row for row in records if row["frame_index"] == frame} for frame in range(345)}
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    colors = {"raw": (50, 210, 70), "repaired": (255, 220, 30), "none": (35, 35, 235)}
    try:
        for frame in range(345):
            ok, image = capture.read()
            if not ok:
                raise RuntimeError(f"video decode failed at frame {frame}")
            masks = by_frame[frame]
            points = {
                joint: selected_point(raw_rows[frame], repaired_rows[frame], masks[joint]) for joint in JOINTS
            }
            for first, second in (("Neck", "RShoulder"), ("RShoulder", "RElbow"), ("RElbow", "RWrist")):
                if points[first] and points[second]:
                    cv2.line(image, points[first], points[second], colors[masks[second]["selected_downstream_source"]], 4, cv2.LINE_AA)
            for joint in JOINTS:
                location = points[joint]
                mask = masks[joint]
                if location:
                    color = (30, 210, 255) if mask["downstream_use_mode"] == "downweight" else colors[mask["selected_downstream_source"]]
                    cv2.circle(image, location, 7, color, -1, cv2.LINE_AA)
                    cv2.putText(image, joint, (location[0] + 7, location[1] - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (245, 245, 245), 1, cv2.LINE_AA)
            overlay = image.copy()
            top = height - 122
            cv2.rectangle(overlay, (0, top), (width, height), (26, 31, 37), -1)
            cv2.addWeighted(overlay, 0.80, image, 0.20, 0, image)
            cv2.putText(image, f"T07C-A frame={frame} phase={raw_rows[frame]['phase_label']}", (20, top + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (245, 245, 245), 2, cv2.LINE_AA)
            for index, joint in enumerate(JOINTS):
                mask = masks[joint]
                text = f"{joint}: raw={mask['raw_observation_status']} selected={mask['selected_downstream_source']} action={mask['proposed_action']}"
                x, y = (20 if index < 2 else 650), top + (70 if index % 2 == 0 else 104)
                color = (30, 210, 255) if mask["downstream_use_mode"] == "downweight" else colors[mask["selected_downstream_source"]]
                cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
            process.stdin.write(image.tobytes())
    finally:
        capture.release()
        process.stdin.close()
    stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
    if process.wait():
        raise RuntimeError(f"ffmpeg failed: {stderr}")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    args = parse_args()
    inputs = (
        args.review_csv, args.jump_review, args.raw_trajectory, args.repaired_trajectory,
        args.quality_mask, args.video,
    )
    outputs = (args.output_jsonl, args.output_summary, args.output_overlay)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    if not args.overwrite and (existing := [str(path) for path in outputs if path.exists()]):
        raise FileExistsError("refusing to overwrite: " + ", ".join(existing))
    hashes_before = {str(path): sha256_file(path) for path in inputs}
    review_rows, jump_rows = load_csv(args.review_csv), load_csv(args.jump_review)
    if len(review_rows) != 11:
        raise ValueError(f"expected 11 reviewed events, found {len(review_rows)}")
    raw_rows, repaired_rows, quality_rows = (
        load_jsonl(args.raw_trajectory), load_jsonl(args.repaired_trajectory), load_jsonl(args.quality_mask)
    )
    if any(len(rows) != 345 for rows in (raw_rows, repaired_rows, quality_rows)):
        raise ValueError("all trajectory inputs must contain 345 frames")
    evidence: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        add_event_evidence(evidence, row)
    add_real_motion_evidence(evidence, jump_rows)
    records = [
        build_record(frame, joint, raw_rows[frame], repaired_rows[frame], quality_rows[frame], evidence[(frame, joint)])
        for frame in range(345) for joint in JOINTS
    ]
    if len(records) != 1380:
        raise RuntimeError("mask row count is not 1380")
    atomic_write(args.output_jsonl, "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in records))
    args.output_overlay.parent.mkdir(parents=True, exist_ok=True)
    render_overlay(args.video, raw_rows, repaired_rows, records, args.output_overlay)
    hashes_after = {str(path): sha256_file(path) for path in inputs}
    if hashes_after != hashes_before:
        raise RuntimeError("a read-only input changed")
    by_joint = {}
    for joint in JOINTS:
        subset = [row for row in records if row["joint_name"] == joint]
        by_joint[joint] = {
            "raw_valid": sum(row["raw_observation_valid"] for row in subset),
            "raw_invalid": sum(not row["raw_observation_valid"] for row in subset),
            "repaired_available": sum(row["repaired_observation_available"] for row in subset),
            "repaired_valid": sum(row["repaired_observation_valid"] for row in subset),
            "downstream_valid": sum(row["downstream_valid"] for row in subset),
            "selected_downstream_source": dict(Counter(row["selected_downstream_source"] for row in subset)),
        }
    duplicate_rows = [row for row in records if len(row["source_event_ids"]) > 1]
    conflicts = [row for row in records if row["manual_evidence_conflict"]]
    action_conflicts = [row for row in records if row["manual_action_conflict"]]
    summary = {
        "run_id": "20260714_T07C_A_CORRUPTION_MASK_001",
        "video_id": VIDEO_ID,
        "status": "complete_pending_claude_acceptance",
        "total_frames": 345,
        "joint_count": 4,
        "total_records": len(records),
        "records_by_joint": by_joint,
        "corruption_type_counts": dict(Counter(row["corruption_type"] for row in records)),
        "proposed_action_counts": dict(Counter(row["proposed_action"] for row in records)),
        "selected_downstream_source_counts": dict(Counter(row["selected_downstream_source"] for row in records)),
        "boundary_continuity_warning_count": sum(row["boundary_continuity_warning"] for row in records),
        "normalization_scale_warning_count": sum(row["normalization_scale_warning"] for row in records),
        "multi_source_record_count": len(duplicate_rows),
        "multi_source_records": [{"frame_index": row["frame_index"], "joint_name": row["joint_name"], "source_event_ids": row["source_event_ids"]} for row in duplicate_rows],
        "manual_evidence_conflict_count": len(conflicts),
        "manual_evidence_conflicts": [{"frame_index": row["frame_index"], "joint_name": row["joint_name"], "manual_evidence": row["manual_evidence"]} for row in conflicts],
        "manual_action_conflict_count": len(action_conflicts),
        "manual_action_conflicts": [{
            "frame_index": row["frame_index"],
            "joint_name": row["joint_name"],
            "proposed_action": row["proposed_action"],
            "proposed_actions": row["proposed_actions"],
            "manual_evidence": row["manual_evidence"],
        } for row in action_conflicts],
        "critical_records": [row for row in records if (row["joint_name"], row["frame_index"]) in {
            *(("RWrist", frame) for frame in (64, 65, 143, 178, 179, 182, 183, 184, 185)),
            *(("RElbow", frame) for frame in (54, 55, 64, 65)),
        }],
        "raw_and_repaired_layers_separate": True,
        "human_review_csv_modified": False,
        "filtering_performed": False,
        "new_interpolation_performed": False,
        "input_hashes": hashes_before,
        "outputs": {"mask": str(args.output_jsonl), "overlay": str(args.output_overlay)},
    }
    atomic_write(args.output_summary, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "total_records": len(records), "records_by_joint": by_joint,
        "corruption_type_counts": summary["corruption_type_counts"],
        "proposed_action_counts": summary["proposed_action_counts"],
        "multi_source_record_count": len(duplicate_rows),
        "manual_evidence_conflict_count": len(conflicts),
        "manual_action_conflict_count": len(action_conflicts),
        "input_hashes_unchanged": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
