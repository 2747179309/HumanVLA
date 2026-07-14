#!/usr/bin/env python3
"""Apply the approved T07A-R1 label and CSV schema cleanup."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

ALLOWED_LABELS = {
    "real_motion", "normal_body_compensation", "phase_boundary_motion",
    "openpose_jitter", "occlusion_error", "normalization_artifact", "uncertain",
}
FIELDS = [
    "candidate_id", "from_frame", "to_frame", "joint_name", "phase_before",
    "phase_after", "displacement_px", "displacement_norm", "confidence_before",
    "confidence_after", "shoulder_width_before", "shoulder_width_after",
    "neck_displacement_px", "automatic_trigger_reason", "manual_label",
    "manual_confidence", "manual_note", "review_start_frame", "review_end_frame",
    "clip_path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize the 12-row T07A review CSV schema and apply only the approved R1 "
            "manual-label corrections. Raw trajectory data are hash-checked read-only."
        )
    )
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    parser.add_argument("--expected-candidates", type=int, default=12)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recover_ancillary_fields(row: dict[str, Any]) -> dict[str, str]:
    result = {field: str(row.get(field) or "").strip() for field in FIELDS}
    unnamed = str(row.get("") or "").strip()
    if unnamed:
        if result["review_start_frame"]:
            raise ValueError(f"{result['candidate_id']}: ambiguous shifted ancillary fields")
        result["review_start_frame"] = result["review_end_frame"]
        result["review_end_frame"] = result["clip_path"]
        result["clip_path"] = unnamed
    return result


def apply_r1(rows: list[dict[str, str]]) -> None:
    by_id = {row["candidate_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("duplicate candidate_id")
    expected_ids = {f"JUMP_{index:03d}" for index in range(1, len(rows) + 1)}
    if set(by_id) != expected_ids:
        raise ValueError("candidate IDs are not the complete sequential set")

    by_id["JUMP_001"].update({
        "manual_label": "normalization_artifact",
        "manual_confidence": "high",
        "manual_note": "肘关节始终正常贴合，绝对像素位移很小，肩宽变化导致归一化位移被放大。",
    })

    jump_005 = by_id["JUMP_005"]
    if jump_005["manual_label"] not in {"openpose_jitter", "occlusion_error"}:
        raise ValueError("JUMP_005 must already carry the user's final jitter/occlusion choice")
    if jump_005["manual_label"] == "occlusion_error":
        jump_005["manual_note"] = "右肘关键点因手臂遮挡发生异常跳变。"
    elif not jump_005["manual_note"] or jump_005["manual_note"] == "异常跳变":
        jump_005["manual_note"] = "右肘关键点在无真实快速运动时发生OpenPose定位抖动。"

    for candidate_id in ("JUMP_010", "JUMP_011"):
        row = by_id[candidate_id]
        row["manual_label"] = "occlusion_error"
        original_note = row["manual_note"].strip().rstrip("。")
        required_text = "骨架完全没有在手臂上"
        if required_text not in original_note:
            original_note = f"{required_text}；{original_note}" if original_note else required_text
        row["manual_note"] = original_note + "。"


def validate(rows: list[dict[str, str]], expected: int) -> None:
    if len(rows) != expected:
        raise ValueError(f"CSV has {len(rows)} rows, expected {expected}")
    for row in rows:
        candidate_id = row["candidate_id"]
        if row["manual_label"] not in ALLOWED_LABELS:
            raise ValueError(f"{candidate_id}: disallowed manual_label={row['manual_label']!r}")
        for field in ("manual_label", "manual_confidence", "manual_note"):
            if not row[field]:
                raise ValueError(f"{candidate_id}: blank {field}")
        try:
            start, end = int(row["review_start_frame"]), int(row["review_end_frame"])
            from_frame, to_frame = int(row["from_frame"]), int(row["to_frame"])
        except ValueError as error:
            raise ValueError(f"{candidate_id}: invalid frame field") from error
        if start != max(0, from_frame - 5) or end != min(344, to_frame + 5):
            raise ValueError(f"{candidate_id}: review frame range mismatch")
        clip = Path(row["clip_path"])
        if clip.suffix.lower() != ".mp4" or not clip.is_file():
            raise FileNotFoundError(f"{candidate_id}: invalid clip_path={clip}")


def write_csv_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent,
        prefix=f".{path.name}.", delete=False,
    ) as stream:
        temp_path = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp_path, path)


def main() -> int:
    args = parse_args()
    for path in (args.review_csv, args.trajectory):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not args.overwrite:
        raise ValueError("R1 rewrites the review CSV; pass --overwrite after approval")
    if args.expected_candidates <= 0:
        raise ValueError("expected-candidates must be positive")

    csv_hash_before = sha256_file(args.review_csv)
    trajectory_hash_before = sha256_file(args.trajectory)
    with args.review_csv.open(encoding="utf-8-sig", newline="") as stream:
        raw_rows = list(csv.DictReader(stream))
    rows = [recover_ancillary_fields(row) for row in raw_rows]
    apply_r1(rows)
    validate(rows, args.expected_candidates)
    write_csv_atomic(args.review_csv, rows)

    with args.review_csv.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        written = list(reader)
        if reader.fieldnames != FIELDS:
            raise RuntimeError("written CSV field order is not canonical")
    validate(written, args.expected_candidates)
    if sha256_file(args.trajectory) != trajectory_hash_before:
        raise RuntimeError("raw trajectory changed during R1 cleanup")
    print({
        "rows": len(written), "field_count": len(FIELDS),
        "csv_sha256_before": csv_hash_before,
        "csv_sha256_after": sha256_file(args.review_csv),
        "trajectory_sha256": trajectory_hash_before,
        "trajectory_unchanged": True,
        "labels": {row["candidate_id"]: row["manual_label"] for row in written},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
