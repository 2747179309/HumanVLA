#!/bin/bash
# End-to-end processing of a single Kinect MKV recording.
# Usage: ./process_video.sh <video_id>
# Example: ./process_video.sh KVAL002
set -euo pipefail

VIDEO_ID="$1"
MKV_PATH="data/azure_kinect/raw_mkv/${VIDEO_ID}.mkv"
OUT_DIR="data/azure_kinect/processed/${VIDEO_ID}"
RES_DIR="results/azure_kinect/${VIDEO_ID}"
EXTRACTOR="/tmp/kinect_build/extract_joints"

if [ ! -f "$MKV_PATH" ]; then
    echo "ERROR: MKV not found: $MKV_PATH"
    exit 1
fi

echo "============================================================"
echo "Processing: $VIDEO_ID"
echo "============================================================"

# Step 1: C++ extraction (CPU mode) — skip if already done
if [ -f "${OUT_DIR}/skeleton_3d_raw.txt" ]; then
    echo "[1/5] C++ extraction: SKIPPED (already exists)"
else
    echo "[1/5] C++ extraction (CPU mode) ..."
    mkdir -p "$OUT_DIR"
    $EXTRACTOR \
        --mkv "$MKV_PATH" \
        --output-dir data/azure_kinect/processed/ \
        --video-id "$VIDEO_ID" \
        --cpu-only
    echo "       Done."
fi

# Step 2: Build dataset (3D → 2D projection)
echo "[2/5] Build dataset ..."
python3 scripts/azure_kinect/build_dataset.py \
    --input-txt "${OUT_DIR}/skeleton_3d_raw.txt" \
    --calibration "${OUT_DIR}/calibration.json" \
    --output-dir "$OUT_DIR" \
    --video-id "$VIDEO_ID"

# Step 3: Merge 2D + 3D
echo "[3/5] Merge skeletons ..."
python3 scripts/azure_kinect/merge_kinect_skeleton.py \
    --2d-input "${OUT_DIR}/skeleton_2d_raw.jsonl" \
    --3d-input "${OUT_DIR}/skeleton_3d_raw.jsonl" \
    --sync-csv "${OUT_DIR}/frame_sync.csv" \
    --output "${OUT_DIR}/kinect_skeleton.jsonl" \
    --video-id "$VIDEO_ID"

# Step 4: Validate
echo "[4/5] Validate ..."
python3 scripts/azure_kinect/validate_kinect_export.py \
    --skeleton "${OUT_DIR}/kinect_skeleton.jsonl" \
    --sync-csv "${OUT_DIR}/frame_sync.csv"

# Step 5: Analyze
echo "[5/5] Analyze ..."
mkdir -p "$RES_DIR"
python3 scripts/azure_kinect/analyze_joint_confidence.py \
    --skeleton "${OUT_DIR}/kinect_skeleton.jsonl" \
    --output-dir "$RES_DIR"

# SHA-256 manifest
python3 scripts/azure_kinect/generate_manifest.py generate \
    --input-dir "$OUT_DIR" \
    --output "${OUT_DIR}/file_manifest.json"

echo ""
echo "✅ $VIDEO_ID complete"
echo "   Frames: $(wc -l < ${OUT_DIR}/kinect_skeleton.jsonl)"
echo "   Results: $RES_DIR/"
echo ""
