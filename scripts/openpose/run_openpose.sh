#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: run_openpose.sh --video VIDEO --output-dir DIR [options]

Run CMU OpenPose BODY_25 on one video and write raw JSON plus an H.264 render.

Required:
  --video PATH              Input video.
  --output-dir PATH         Output directory.

Options:
  --openpose-root PATH      OpenPose source/build root (default: tools/openpose).
  --net-resolution VALUE   Network resolution (default: -1x368).
  --number-people-max N     Maximum people per frame (default: 6).
  --gpu N                   CUDA device index (default: 0).
  --help                    Show this help.

The script refuses to overwrite existing artifacts. OpenPose people-array order
is not an identity and this script performs no track_id/subject_id association.
EOF
}

video=""
output_dir=""
openpose_root="tools/openpose"
net_resolution="-1x368"
number_people_max="6"
gpu="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --video) video="${2:?missing value for --video}"; shift 2 ;;
    --output-dir) output_dir="${2:?missing value for --output-dir}"; shift 2 ;;
    --openpose-root) openpose_root="${2:?missing value for --openpose-root}"; shift 2 ;;
    --net-resolution) net_resolution="${2:?missing value for --net-resolution}"; shift 2 ;;
    --number-people-max) number_people_max="${2:?missing value for --number-people-max}"; shift 2 ;;
    --gpu) gpu="${2:?missing value for --gpu}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$video" ]] || { echo "error: --video is required" >&2; exit 2; }
[[ -n "$output_dir" ]] || { echo "error: --output-dir is required" >&2; exit 2; }
[[ -f "$video" ]] || { echo "error: input video not found: $video" >&2; exit 1; }
[[ "$number_people_max" =~ ^[1-9][0-9]*$ ]] || { echo "error: invalid --number-people-max" >&2; exit 2; }
[[ "$gpu" =~ ^[0-9]+$ ]] || { echo "error: invalid --gpu" >&2; exit 2; }
command -v ffmpeg >/dev/null || { echo "error: ffmpeg is required" >&2; exit 1; }

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
video="$(realpath "$video")"
openpose_root="$(realpath "$openpose_root")"
output_dir="$(realpath -m "$output_dir")"
binary="$openpose_root/build/examples/openpose/openpose.bin"
model="$openpose_root/models/pose/body_25/pose_iter_584000.caffemodel"
raw_json="$output_dir/raw_json"
openpose_video="$output_dir/rendered_openpose.avi"
rendered_video="$output_dir/rendered.mp4"
runtime_file="$output_dir/processing_seconds.txt"

[[ -x "$binary" ]] || { echo "error: OpenPose binary not found: $binary" >&2; exit 1; }
[[ -s "$model" ]] || { echo "error: BODY_25 model not found: $model" >&2; exit 1; }
for path in "$openpose_video" "$rendered_video" "$runtime_file"; do
  [[ ! -e "$path" ]] || { echo "error: refusing to overwrite: $path" >&2; exit 1; }
done
if [[ -d "$raw_json" ]] && compgen -G "$raw_json/*.json" >/dev/null; then
  echo "error: refusing to overwrite JSON files in: $raw_json" >&2
  exit 1
fi

mkdir -p "$raw_json"
cd "$openpose_root"

export CUDA_HOME="${CUDA_HOME:-/home/a531/CUDA11.3.0}"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
/usr/bin/time -f '%e' -o "$runtime_file" \
  "$binary" \
  --video "$video" \
  --model_folder "$openpose_root/models/" \
  --model_pose BODY_25 \
  --net_resolution "$net_resolution" \
  --number_people_max "$number_people_max" \
  --num_gpu 1 \
  --num_gpu_start "$gpu" \
  --display 0 \
  --render_pose 1 \
  --write_json "$raw_json" \
  --write_video "$openpose_video"

# OpenPose/OpenCV writes a lossless intermediate; FFmpeg creates the required H.264 artifact.
ffmpeg -hide_banner -loglevel error -y -i "$openpose_video" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -an "$rendered_video"

printf 'OpenPose output: %s\n' "$output_dir"
printf 'Raw people arrays are detections, not identities. Association is deferred to T04.\n'
