#!/usr/bin/env python3
"""Build blank T07C-A corruption review materials without masking observations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np


VIDEO_ID = "pick_place_pilot_v1_E001"
REVIEW_LABELS = {"occlusion_error", "normalization_artifact"}
JOINT_PREFIX = {"RElbow": "relbow", "RWrist": "rwrist"}
CONFIDENCE_INDEX = {"RElbow": 2, "RWrist": 3}
MANUAL_FIELDS = (
    "manual_from_frame_status", "manual_to_frame_status", "manual_error_frames",
    "manual_valid_frames", "manual_corruption_type", "manual_confidence",
    "manual_reason", "manual_proposed_action",
)
CSV_FIELDS = (
    "candidate_id", "source_type", "source_event_id", "from_frame", "to_frame",
    "joint_name", "phase_before", "phase_after", "source_label",
    "source_confidence", "source_note", "raw_status_from", "raw_status_to",
    "confidence_from", "confidence_to", "shoulder_width_from_px",
    "shoulder_width_to_px", "neck_displacement_to_px",
    "boundary_entry_velocity_discontinuity_norm_per_s", "review_start_frame",
    "review_end_frame", "clip_path", *MANUAL_FIELDS,
)
COLORS = {
    "skeleton": (55, 205, 80),
    "raw": (20, 150, 255),
    "repaired": (255, 220, 30),
    "event": (35, 35, 245),
    "neck_scale": (255, 100, 180),
    "text": (245, 245, 245),
    "panel": (26, 31, 37),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate blank per-event T07C-A review CSV and H.264 clips. "
            "No corruption decision or trajectory mask is created."
        )
    )
    parser.add_argument("--jump-review", required=True, type=Path)
    parser.add_argument("--raw-trajectory", required=True, type=Path)
    parser.add_argument("--repaired-trajectory", required=True, type=Path)
    parser.add_argument("--quality-mask", required=True, type=Path)
    parser.add_argument("--repair-summary", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--clips-dir", required=True, type=Path)
    parser.add_argument("--output-video", required=True, type=Path)
    parser.add_argument("--output-summary", required=True, type=Path)
    parser.add_argument("--context-frames", type=int, default=8)
    parser.add_argument("--review-fps", type=float, default=6.0)
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Read the existing review CSV and only replace review videos/summary; never rewrite the CSV.",
    )
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


def ensure_output_policy(args: argparse.Namespace) -> None:
    outputs = (args.output_csv, args.output_video, args.output_summary)
    existing_clips = list(args.clips_dir.glob("*.mp4")) if args.clips_dir.exists() else []
    if not args.overwrite and (existing := [path for path in outputs if path.exists()] + existing_clips):
        raise FileExistsError("refusing to overwrite: " + ", ".join(map(str, existing)))
    if args.output_csv.exists() and args.overwrite:
        rows = load_csv(args.output_csv)
        if any(any((row.get(field) or "").strip() for field in MANUAL_FIELDS) for row in rows):
            raise ValueError("refusing to overwrite a CSV containing T07C-A manual decisions")


def quality_status(raw_row: dict[str, Any], joint: str) -> str:
    return str(raw_row[f"{JOINT_PREFIX[joint]}_effective_status"])


def raw_confidence(row: dict[str, Any], joint: str) -> float | None:
    value = row.get("raw_confidence", [None] * 5)[CONFIDENCE_INDEX[joint]]
    return None if value is None else float(value)


def make_event(
    candidate_id: str,
    source_type: str,
    source_event_id: str,
    start: int,
    end: int,
    joint: str,
    source_label: str,
    source_confidence: str,
    source_note: str,
    rows: list[dict[str, Any]],
    context: int,
    boundary_value: float | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "source_type": source_type,
        "source_event_id": source_event_id,
        "from_frame": start,
        "to_frame": end,
        "joint_name": joint,
        "phase_before": rows[start]["phase_label"],
        "phase_after": rows[end]["phase_label"],
        "source_label": source_label,
        "source_confidence": source_confidence,
        "source_note": source_note,
        "raw_status_from": quality_status(rows[start], joint),
        "raw_status_to": quality_status(rows[end], joint),
        "confidence_from": raw_confidence(rows[start], joint),
        "confidence_to": raw_confidence(rows[end], joint),
        "shoulder_width_from_px": rows[start]["shoulder_width_px"],
        "shoulder_width_to_px": rows[end]["shoulder_width_px"],
        "neck_displacement_to_px": rows[end]["neck_frame_displacement_px"],
        "boundary_entry_velocity_discontinuity_norm_per_s": boundary_value,
        "review_start_frame": max(0, start - context),
        "review_end_frame": min(len(rows) - 1, end + context),
        "clip_path": "",
        **{field: "" for field in MANUAL_FIELDS},
    }


def build_events(
    jump_rows: list[dict[str, str]],
    raw_rows: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
    repair_summary: dict[str, Any],
    context: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    selected = [row for row in jump_rows if row["manual_label"] in REVIEW_LABELS]
    if len(selected) != 9:
        raise ValueError(f"expected 9 jump review events, found {len(selected)}")
    if sum(row["manual_label"] == "occlusion_error" for row in selected) != 8:
        raise ValueError("expected exactly 8 occlusion_error jump events")
    if sum(row["manual_label"] == "normalization_artifact" for row in selected) != 1:
        raise ValueError("expected exactly 1 normalization_artifact jump event")
    for row in selected:
        source_id = row["candidate_id"]
        events.append(make_event(
            candidate_id=f"T07C_{source_id}",
            source_type="jump_candidate_review",
            source_event_id=source_id,
            start=int(row["from_frame"]),
            end=int(row["to_frame"]),
            joint=row["joint_name"],
            source_label=row["manual_label"],
            source_confidence=row["manual_confidence"],
            source_note=row["manual_note"],
            rows=raw_rows,
            context=context,
        ))

    for frame in (64, 65):
        quality = quality_rows[frame]
        if quality["joint_observation_status"][3] != "low_quality":
            raise ValueError(f"frame {frame}: T06C RElbow is not low_quality")
    events.append(make_event(
        candidate_id="T07C_T06C_RELBOW_064_065",
        source_type="T06C_quality_mask",
        source_event_id="T06C_LOW_QUALITY_RELBOW_064_065",
        start=64,
        end=65,
        joint="RElbow",
        source_label="low_quality_observation",
        source_confidence="not_specified",
        source_note="forearm_self_occlusion; raw coordinates retained; requires frame-level review",
        rows=raw_rows,
        context=context,
    ))

    warnings = repair_summary.get("manual_review", {}).get("boundary_continuity_warnings", [])
    if len(warnings) != 1 or warnings[0].get("frames") != [182, 183, 184, 185]:
        raise ValueError("T07B 182-185 boundary continuity warning is missing")
    boundary_value = float(warnings[0]["entry_velocity_discontinuity_norm_per_s"])
    events.append(make_event(
        candidate_id="T07C_T07B_BOUNDARY_RWrist_182_185",
        source_type="T07B_repair_summary",
        source_event_id="T07B_BOUNDARY_RWrist_182_185",
        start=182,
        end=185,
        joint="RWrist",
        source_label="boundary_continuity_warning",
        source_confidence="high",
        source_note=(
            "repaired positions passed manual review; boundary warning retained at "
            f"{boundary_value:.6f} norm/s"
        ),
        rows=raw_rows,
        context=context,
        boundary_value=boundary_value,
    ))
    events.sort(key=lambda item: (item["from_frame"], item["to_frame"], item["candidate_id"]))
    if len(events) != 11:
        raise ValueError(f"expected 11 T07C-A review events, found {len(events)}")
    return events


def events_from_existing_review(path: Path) -> list[dict[str, Any]]:
    rows = load_csv(path)
    if len(rows) != 11:
        raise ValueError(f"render-only review CSV must contain 11 rows, found {len(rows)}")
    if any(any((row.get(field) or "").strip() for field in MANUAL_FIELDS) for row in rows):
        raise ValueError("render-only refuses a review CSV containing manual decisions")
    integer_fields = ("from_frame", "to_frame", "review_start_frame", "review_end_frame")
    events: list[dict[str, Any]] = []
    for source in rows:
        event: dict[str, Any] = dict(source)
        for field in integer_fields:
            event[field] = int(event[field])
        events.append(event)
    return events


def point(row: dict[str, Any], prefix: str, repaired: bool = False) -> tuple[int, int] | None:
    suffix = "_repaired_px" if repaired and prefix == "rwrist" else "_px"
    x = row.get(f"{prefix}_x{suffix}")
    y = row.get(f"{prefix}_y{suffix}")
    return None if x is None or y is None else (round(float(x)), round(float(y)))


def draw_raw_skeleton(frame: np.ndarray, row: dict[str, Any]) -> None:
    points = {name: point(row, prefix) for name, prefix in (
        ("Neck", "neck"), ("RShoulder", "rshoulder"), ("LShoulder", "lshoulder"),
        ("RElbow", "relbow"), ("RWrist", "rwrist"),
    )}
    for first, second in (("Neck", "RShoulder"), ("Neck", "LShoulder"),
                          ("RShoulder", "RElbow"), ("RElbow", "RWrist")):
        if points[first] and points[second]:
            cv2.line(frame, points[first], points[second], COLORS["skeleton"], 3, cv2.LINE_AA)
    for name, location in points.items():
        if location:
            cv2.circle(frame, location, 5, COLORS["skeleton"], -1, cv2.LINE_AA)
            cv2.putText(frame, name, (location[0] + 6, location[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLORS["text"], 1, cv2.LINE_AA)
    if points["RShoulder"] and points["LShoulder"]:
        cv2.line(frame, points["RShoulder"], points["LShoulder"], COLORS["neck_scale"], 2, cv2.LINE_AA)


def draw_trajectory_paths(
    frame: np.ndarray,
    raw_rows: list[dict[str, Any]],
    repaired_rows: list[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    prefix = JOINT_PREFIX[event["joint_name"]]
    start, end = event["review_start_frame"], event["review_end_frame"]
    for rows, repaired, color, thickness in (
        (raw_rows, False, COLORS["raw"], 5),
        (repaired_rows, True, COLORS["repaired"], 2),
    ):
        for frame_index in range(start, end):
            before = point(rows[frame_index], prefix, repaired)
            after = point(rows[frame_index + 1], prefix, repaired)
            if before and after:
                cv2.line(frame, before, after, color, thickness, cv2.LINE_AA)
def draw_current_repair(frame: np.ndarray, row: dict[str, Any], joint: str) -> None:
    prefix = JOINT_PREFIX[joint]
    raw_location = point(row, prefix)
    repaired_location = point(row, prefix, True)
    if raw_location:
        cv2.circle(frame, raw_location, 9, COLORS["raw"], 3, cv2.LINE_AA)
    if repaired_location:
        cv2.drawMarker(frame, repaired_location, COLORS["repaired"], cv2.MARKER_CROSS, 18, 3, cv2.LINE_AA)


def draw_information(frame: np.ndarray, row: dict[str, Any], event: dict[str, Any]) -> None:
    joint = event["joint_name"]
    confidence = raw_confidence(row, joint)
    overlay = frame.copy()
    panel_top = frame.shape[0] - 112
    cv2.rectangle(overlay, (0, panel_top), (frame.shape[1], frame.shape[0]), COLORS["panel"], -1)
    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0.0, frame)
    lines = [
        f"{event['candidate_id']} | frame={row['frame_index']} | joint={joint} | phase={row['phase_label']}",
        f"confidence={confidence if confidence is not None else 'null'} | source label={event['source_label']}",
    ]
    for index, text in enumerate(lines):
        cv2.putText(frame, text, (24, panel_top + 38 + index * 38), cv2.FONT_HERSHEY_SIMPLEX,
                    0.62 if index == 0 else 0.56, COLORS["text"],
                    2 if index == 0 else 1, cv2.LINE_AA)
    active = event["from_frame"] <= row["frame_index"] <= event["to_frame"]
    badge = "CANDIDATE FRAME" if active else f"CANDIDATE {event['from_frame']}..{event['to_frame']}"
    badge_color = COLORS["event"] if active else (75, 90, 215)
    cv2.rectangle(frame, (995, panel_top + 19), (1262, panel_top + 88), badge_color, 3)
    cv2.putText(frame, badge, (1011, panel_top + 61), cv2.FONT_HERSHEY_SIMPLEX,
                0.57, badge_color, 2, cv2.LINE_AA)


def read_frames(video: Path, start: int, end: int) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames = []
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
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", str(path),
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


def concatenate(clips: list[Path], output: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as stream:
        list_path = Path(stream.name)
        for clip in clips:
            escaped = str(clip.resolve()).replace("'", "'\\''")
            stream.write(f"file '{escaped}'\n")
    try:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
            "-safe", "0", "-i", str(list_path), "-c", "copy", str(output),
        ], check=True)
    finally:
        list_path.unlink(missing_ok=True)


def probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    stream = json.loads(completed.stdout)["streams"][0]
    return {
        "codec": stream["codec_name"], "width": int(stream["width"]),
        "height": int(stream["height"]), "fps": stream["avg_frame_rate"],
        "frames": int(stream["nb_read_frames"]),
    }


def main() -> int:
    args = parse_args()
    if args.context_frames < 8:
        raise ValueError("context-frames must be at least 8")
    if args.review_fps <= 0:
        raise ValueError("review-fps must be positive")
    inputs = (
        args.jump_review, args.raw_trajectory, args.repaired_trajectory,
        args.quality_mask, args.repair_summary, args.video,
    )
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    ensure_output_policy(args)
    readonly_inputs = (*inputs, args.output_csv) if args.render_only else inputs
    hashes_before = {str(path): sha256_file(path) for path in readonly_inputs}
    jump_rows = load_csv(args.jump_review)
    raw_rows = load_jsonl(args.raw_trajectory)
    repaired_rows = load_jsonl(args.repaired_trajectory)
    quality_rows = load_jsonl(args.quality_mask)
    repair_summary = json.loads(args.repair_summary.read_text(encoding="utf-8"))
    if any(len(rows) != 345 for rows in (raw_rows, repaired_rows, quality_rows)):
        raise ValueError("trajectory and quality inputs must each cover 345 frames")
    if any(row.get("frame_index") != frame for frame, row in enumerate(raw_rows)):
        raise ValueError("raw trajectory does not cover frame 0..344")
    events = (
        events_from_existing_review(args.output_csv)
        if args.render_only
        else build_events(jump_rows, raw_rows, quality_rows, repair_summary, args.context_frames)
    )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.clips_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for event in events:
        clip = args.clips_dir / (
            f"{event['candidate_id']}_{event['joint_name']}_{event['from_frame']}_{event['to_frame']}.mp4"
        )
        event["clip_path"] = str(clip)
        source_frames = read_frames(args.video, event["review_start_frame"], event["review_end_frame"])
        rendered = []
        for offset, frame in enumerate(source_frames):
            frame_index = event["review_start_frame"] + offset
            draw_raw_skeleton(frame, raw_rows[frame_index])
            draw_trajectory_paths(frame, raw_rows, repaired_rows, event)
            draw_current_repair(frame, repaired_rows[frame_index], event["joint_name"])
            draw_information(frame, raw_rows[frame_index], event)
            rendered.append(frame)
        write_h264(clip, rendered, args.review_fps)
        expected = event["review_end_frame"] - event["review_start_frame"] + 1
        if probe(clip)["frames"] != expected:
            raise RuntimeError(f"clip frame count mismatch: {clip}")
        clips.append(clip)

    if not args.render_only:
        with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(events)
    concatenate(clips, args.output_video)
    output_probe = probe(args.output_video)
    expected_total = sum(event["review_end_frame"] - event["review_start_frame"] + 1 for event in events)
    if output_probe["frames"] != expected_total:
        raise RuntimeError("combined review video frame count mismatch")
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(args.output_video), "-f", "null", "-"],
        capture_output=True,
    )
    if decode.returncode:
        raise RuntimeError("combined review video failed full decode")
    hashes_after = {str(path): sha256_file(path) for path in readonly_inputs}
    if hashes_after != hashes_before:
        raise RuntimeError("a read-only input changed during material generation")
    summary = {
        "run_id": "20260714_T07C_A_REVIEW_MATERIALS_001",
        "video_id": VIDEO_ID,
        "status": "review_materials_complete_pending_human_frame_decisions",
        "candidate_count": len(events),
        "jump_candidate_count": 9,
        "occlusion_error_event_count": 8,
        "normalization_artifact_event_count": 1,
        "low_quality_event_count": 1,
        "boundary_warning_event_count": 1,
        "real_motion_events_re_reviewed": 0,
        "context_frames_each_side": args.context_frames,
        "manual_fields_blank": True,
        "automatic_frame_error_decisions": False,
        "automatic_masking_performed": False,
        "frame_joint_corruption_mask_generated": False,
        "filtering_or_interpolation_performed": False,
        "render_only": args.render_only,
        "layout_version": "t07c_a_bottom_panel_v2",
        "information_panel_location": "bottom_table_front_edge",
        "information_panel_background": "semi_transparent",
        "candidate_csv_rewritten": not args.render_only,
        "clips": [{"candidate_id": event["candidate_id"], **probe(clip)} for event, clip in zip(events, clips)],
        "combined_video": output_probe,
        "combined_video_full_decode_passed": True,
        "input_hashes": hashes_before,
        "outputs": {
            "review_csv": str(args.output_csv),
            "clips_dir": str(args.clips_dir),
            "review_video": str(args.output_video),
        },
    }
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
