#!/usr/bin/env python3
"""Expand validated manual phase intervals into frame-level JSONL records."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from validate_labels import parse_bool, validate_annotations


LOGGER = logging.getLogger(__name__)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Expand validated manual action-phase intervals to JSONL."
    )
    parser.add_argument("--segments-csv", type=Path, required=True)
    parser.add_argument("--manifest-csv", type=Path, required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    try:
        summary, segments, manifest = validate_annotations(
            args.segments_csv, args.manifest_csv, args.video_id
        )
        if not summary["validation_passed"]:
            for error in summary["errors"]:
                LOGGER.error("validation error: %s", error)
            return 1

        fps = float(manifest["fps"])
        subject_id = manifest["subject_id"]
        episode_success = parse_bool(manifest["declared_episode_success"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        record_count = 0
        with temporary.open("w", encoding="utf-8") as handle:
            for segment in segments:
                for frame_index in range(
                    segment["start_frame"], segment["end_frame"] + 1
                ):
                    record = {
                        "video_id": args.video_id,
                        "episode_id": segment["episode_id"],
                        "frame_index": frame_index,
                        "timestamp_sec": round(frame_index / fps, 6),
                        "subject_id": subject_id,
                        "phase_id": segment["phase_id"],
                        "phase_label": segment["phase_label"],
                        "phase_text_zh": segment["phase_text_zh"],
                        "phase_text_en": segment["phase_text_en"],
                        "object_id": segment["object_id"],
                        "active_hand": segment["active_hand"],
                        "episode_success": episode_success,
                        "annotation_valid": segment["annotation_valid"],
                        "quality_status": segment["quality_status"],
                        "boundary_confidence": segment["boundary_confidence"],
                        "source_segment_id": segment["segment_id"],
                        "annotator_id": segment["annotator_id"],
                        "reviewer_id": segment["reviewer_id"] or None,
                        "annotation_version": segment["annotation_version"],
                        "notes": segment["notes"],
                    }
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    record_count += 1
        temporary.replace(args.output)
    except (OSError, ValueError, KeyError) as exc:
        LOGGER.error("frame expansion failed: %s", exc)
        return 2

    print(
        json.dumps(
            {"output": str(args.output), "frame_records": record_count},
            ensure_ascii=False,
        )
    )
    LOGGER.info("expanded %d frame records", record_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
