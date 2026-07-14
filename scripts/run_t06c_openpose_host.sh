#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/run_t06c_openpose_host.sh [--gpu INDEX] [--overwrite]

Run the T06C E001 OpenPose BODY_25 stage from a normal host terminal with GPU
device access. This script never runs DeepSORT. It validates and reuses the
existing tracks and confirmed P001 subject map.

Options:
  --gpu INDEX    CUDA device index (default: 0)
  --overwrite    Archive an existing OpenPose output directory before running
  --help, -h     Show this help

Without --overwrite, any existing E001 OpenPose output directory causes an
immediate failure. --overwrite preserves the old directory as a timestamped
backup; it does not delete previous results.
EOF
}

gpu="0"
overwrite="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --gpu)
      [[ $# -ge 2 ]] || { echo "error: --gpu requires an index" >&2; exit 2; }
      gpu="$2"
      shift 2
      ;;
    --overwrite)
      overwrite="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ "$gpu" =~ ^[0-9]+$ ]] || { echo "error: --gpu must be a non-negative integer" >&2; exit 2; }

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
video_id="pick_place_pilot_v1_E001"
video="$project_root/data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4"
mot_tracks="$project_root/results/mot/$video_id/tracks_raw.jsonl"
subject_map="$project_root/data/mot/subject_maps/$video_id.csv"
openpose_root="$project_root/tools/openpose"
openpose_binary="$openpose_root/build/examples/openpose/openpose.bin"
body25_model="$openpose_root/models/pose/body_25/pose_iter_584000.caffemodel"
output_dir="$project_root/results/openpose/$video_id"
probe_dir="$output_dir/probe"
raw_json_dir="$output_dir/raw_json"
rendered_video="$output_dir/rendered.mp4"
summary_json="$output_dir/host_run_summary.json"
log_file="$project_root/logs/runs/T06C_OPENPOSE_HOST_RUN.log"

mkdir -p "$(dirname "$log_file")"
exec > >(tee -a "$log_file") 2>&1

started_at="$(date --iso-8601=seconds)"
trap 'rc=$?; printf "[%s] T06C host OpenPose exit_code=%d\n" "$(date --iso-8601=seconds)" "$rc"' EXIT

echo "============================================================"
echo "T06C host OpenPose run"
echo "started_at=$started_at"
echo "video_id=$video_id"
echo "gpu=$gpu"
echo "overwrite=$overwrite"
echo "project_root=$project_root"

for command in nvidia-smi ffmpeg ffprobe python3; do
  command -v "$command" >/dev/null || { echo "error: missing command: $command" >&2; exit 1; }
done

echo "--- GPU checks ---"
nvidia-smi
for device in /dev/nvidia0 /dev/nvidiactl /dev/nvidia-uvm; do
  [[ -c "$device" ]] || { echo "error: required NVIDIA character device missing: $device" >&2; exit 1; }
  ls -l "$device"
done

echo "--- Fixed input and prerequisite checks ---"
for path in "$video" "$mot_tracks" "$subject_map" "$openpose_binary" "$body25_model"; do
  [[ -s "$path" ]] || { echo "error: required file missing or empty: $path" >&2; exit 1; }
done
[[ -x "$openpose_binary" ]] || { echo "error: OpenPose binary is not executable" >&2; exit 1; }

python3 - "$mot_tracks" "$subject_map" <<'PY'
import csv
import json
import sys
from pathlib import Path

tracks_path = Path(sys.argv[1])
subject_map_path = Path(sys.argv[2])
tracks = [json.loads(line) for line in tracks_path.open(encoding="utf-8") if line.strip()]
with subject_map_path.open(encoding="utf-8-sig", newline="") as handle:
    subject_rows = list(csv.DictReader(handle))

if len(tracks) != 343:
    raise SystemExit(f"expected 343 existing DeepSORT records, found {len(tracks)}")
if {int(row["track_id"]) for row in tracks} != {1}:
    raise SystemExit("existing DeepSORT output must contain only track_id=1")
if [int(row["frame_index"]) for row in tracks] != list(range(2, 345)):
    raise SystemExit("existing track_id=1 must cover frames 2-344 continuously")
if len(subject_rows) != 1:
    raise SystemExit("subject map must contain exactly one row")
row = subject_rows[0]
if not (
    row["track_id"] == "1"
    and row["subject_id"] == "P001"
    and row["review_status"] == "human_confirmed"
    and row["start_frame"] == "2"
    and row["end_frame"] == "344"
):
    raise SystemExit("subject map does not contain the confirmed track_id=1 -> P001 mapping")
print("DeepSORT reuse check passed: track_id=1 -> P001, frames 2-344; frames 0-1 remain missing")
PY

source_frames="$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$video")"
[[ "$source_frames" == "345" ]] || { echo "error: expected 345 video frames, found $source_frames" >&2; exit 1; }

if [[ -e "$output_dir" ]]; then
  if [[ "$overwrite" != "true" ]]; then
    echo "error: refusing to overwrite existing output directory: $output_dir" >&2
    echo "rerun with --overwrite to archive it before creating new outputs" >&2
    exit 1
  fi
  backup_dir="${output_dir}.backup-$(date +%Y%m%dT%H%M%S)-$$"
  echo "Archiving existing output: $output_dir -> $backup_dir"
  mv "$output_dir" "$backup_dir"
fi

mkdir -p "$probe_dir/input" "$probe_dir/raw_json" "$probe_dir/rendered"

export CUDA_HOME="${CUDA_HOME:-/home/a531/CUDA11.3.0}"
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"

echo "--- OpenPose shared-library check ---"
ldd "$openpose_binary" | grep -E 'libcuda|libcudart|libcaffe|not found'
if ldd "$openpose_binary" | grep -q 'not found'; then
  echo "error: OpenPose has unresolved shared libraries" >&2
  exit 1
fi

echo "--- Extracting frame 0 for the mandatory CUDA probe ---"
ffmpeg -hide_banner -loglevel error -i "$video" -frames:v 1 "$probe_dir/input/frame_000000000000.png"

echo "--- Running mandatory single-frame BODY_25 probe ---"
"$openpose_binary" \
  --image_dir "$probe_dir/input" \
  --model_folder "$openpose_root/models/" \
  --model_pose BODY_25 \
  --net_resolution=-1x368 \
  --number_people_max 6 \
  --num_gpu 1 \
  --num_gpu_start "$gpu" \
  --display 0 \
  --render_pose 1 \
  --write_json "$probe_dir/raw_json" \
  --write_images "$probe_dir/rendered"

mapfile -t probe_json_files < <(find "$probe_dir/raw_json" -maxdepth 1 -type f -name '*_keypoints.json' | sort)
mapfile -t probe_render_files < <(find "$probe_dir/rendered" -maxdepth 1 -type f -size +0c | sort)
[[ ${#probe_json_files[@]} -eq 1 ]] || { echo "error: probe must generate exactly one JSON file" >&2; exit 1; }
[[ ${#probe_render_files[@]} -ge 1 ]] || { echo "error: probe did not generate a rendered image" >&2; exit 1; }

python3 - "${probe_json_files[0]}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
people = payload.get("people")
if not isinstance(people, list) or not people:
    raise SystemExit("probe JSON contains no detected operator")

valid_people = 0
core_nonzero = 0
for person in people:
    flat = person.get("pose_keypoints_2d")
    if not isinstance(flat, list) or len(flat) != 75:
        raise SystemExit("probe JSON does not contain a valid BODY_25 length of 75")
    valid_people += 1
    confidences = [float(flat[index * 3 + 2]) for index in (1, 2, 3, 4)]
    core_nonzero = max(core_nonzero, sum(value > 0 for value in confidences))

if core_nonzero == 0:
    raise SystemExit("Neck/RShoulder/RElbow/RWrist are all missing in the probe")
print(f"Single-frame probe passed: people={valid_people}, max_nonzero_core_joints={core_nonzero}/4")
PY

echo "Single-frame JSON: ${probe_json_files[0]}"
printf 'Single-frame render: %s\n' "${probe_render_files[@]}"
echo "--- Probe passed; starting the complete 345-frame OpenPose run ---"

bash "$project_root/scripts/openpose/run_openpose.sh" \
  --video "$video" \
  --output-dir "$output_dir" \
  --openpose-root "$openpose_root" \
  --net-resolution "-1x368" \
  --number-people-max 6 \
  --gpu "$gpu"

python3 - "$raw_json_dir" "$rendered_video" "$summary_json" "$video_id" <<'PY'
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

raw_dir = Path(sys.argv[1])
rendered_video = Path(sys.argv[2])
summary_path = Path(sys.argv[3])
video_id = sys.argv[4]
files = sorted(raw_dir.glob("*_keypoints.json"))
if len(files) != 345:
    raise SystemExit(f"expected 345 raw JSON files, found {len(files)}")

indices = []
malformed = []
detected_frames = 0
people_distribution = collections.Counter()
confidence_over_one = 0
for path in files:
    match = re.search(r"_(\d{12})_keypoints\.json$", path.name)
    if not match:
        raise SystemExit(f"unexpected OpenPose filename: {path.name}")
    indices.append(int(match.group(1)))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        people = payload.get("people")
        if not isinstance(people, list):
            raise ValueError("people is not a list")
        people_distribution[len(people)] += 1
        detected_frames += bool(people)
        for person in people:
            flat = person.get("pose_keypoints_2d")
            if not isinstance(flat, list) or len(flat) != 75:
                raise ValueError("pose_keypoints_2d length is not 75")
            confidence_over_one += sum(float(flat[index]) > 1 for index in range(2, 75, 3))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        malformed.append({"file": path.name, "error": str(exc)})

if indices != list(range(345)):
    raise SystemExit("OpenPose raw JSON frame indices are not exactly 0-344")
if malformed:
    raise SystemExit(f"malformed OpenPose records: {malformed[:5]}")

probe = subprocess.run(
    [
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(rendered_video),
    ],
    check=True,
    capture_output=True,
    text=True,
)
video_probe = json.loads(probe.stdout)["streams"][0]
if int(video_probe["nb_read_frames"]) != 345:
    raise SystemExit("rendered video does not contain exactly 345 frames")

summary = {
    "video_id": video_id,
    "model_pose": "BODY_25",
    "total_frames": 345,
    "raw_json_count": len(files),
    "detected_frames": detected_frames,
    "frames_without_people": 345 - detected_frames,
    "people_per_frame_distribution": dict(sorted(people_distribution.items())),
    "malformed_frame_count": len(malformed),
    "confidence_over_one_value_count": confidence_over_one,
    "confidence_policy": "raw values preserved without normalization or overwrite",
    "rendered_video": video_probe,
    "deepsort_reused": True,
    "deepsort_rerun": False,
}
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
PY

echo "--- Full rendered-video decode check ---"
ffmpeg -hide_banner -loglevel error -i "$rendered_video" -map 0:v:0 -f null -

echo "T06C host OpenPose stage completed successfully."
echo "Raw JSON: $raw_json_dir"
echo "Rendered video: $rendered_video"
echo "Summary: $summary_json"
echo "DeepSORT was not rerun. Return to Codex for association and T06C downstream steps."
