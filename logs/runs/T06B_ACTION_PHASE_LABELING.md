# T06B Action Phase Labeling

## Run 信息

- Run ID：`20260713_T06B_STAGE1_E001`
- 日期：2026-07-13 11:55 CST
- 实验目的：验证 E001 视频解码和元数据，建立人工动作阶段标注空白模板及带 0 基帧号/时间戳的预览视频。
- 状态：第一阶段准备完成，人工动作阶段记录为 0 条，等待人工填写。
- 是否可以用于论文：否。当前只有视频审计和空白人工标注材料，没有动作标签或实验指标。

## 环境

- Git commit：`231fe97dc5788b0c5d40b677c0bf7f116b1b8182`（运行时工作区另有未提交修改）
- FFmpeg：`4.2.7-0ubuntu0.1`
- FFprobe：`4.2.7-0ubuntu0.1`

## 输入

- 文件：`data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4`
- SHA-256（处理前后相同）：`c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`
- 本次未读取或处理 E002-E012。

## 完整命令与参数

### 源视频元数据和全量解码

```bash
ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=codec_name,codec_long_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration:format=duration,size,format_name \
  -of json \
  data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4

ffmpeg -v error -stats \
  -i data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  -map 0:v:0 -f null -
```

### 预览视频

```bash
ffmpeg -y -v warning -stats \
  -i data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  -map 0:v:0 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:text='frame_index=%{n}  timestamp=%{pts\\:hms}':x=24:y=24:fontsize=28:fontcolor=white:borderw=2:bordercolor=black:box=1:boxcolor=black@0.35" \
  -an -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -movflags +faststart \
  results/action_labels/pick_place_pilot_v1_E001/preview_frame_index_timestamp.mp4
```

### 输出验证

```bash
ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration \
  -of json \
  results/action_labels/pick_place_pilot_v1_E001/preview_frame_index_timestamp.mp4

ffmpeg -v error \
  -i results/action_labels/pick_place_pilot_v1_E001/preview_frame_index_timestamp.mp4 \
  -map 0:v:0 -f null -
```

## 输出

- `data/action_labels/video_manifest.csv`：1 条 E001 记录，23 个字段。
- `data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations.csv`：18 个字段，仅表头，0 条人工标签。
- `results/action_labels/pick_place_pilot_v1_E001/preview_frame_index_timestamp.mp4`：H.264 预览视频。

## 真实结果

- 源编码：HEVC/H.265，像素格式 `yuv420p`。
- 分辨率：1280×720。
- FPS：30/1（30.0）。
- 总帧数：345，0 基有效范围为 0-344。
- 时长：11.500000 秒。
- 源视频全量解码：345/345 帧，无 FFmpeg 错误输出。
- 预览视频：H.264、1280×720、30 FPS、345 帧、11.5 秒；全量解码无错误。
- 可视化抽查：预览帧 172 显示 `frame_index=172` 和 `timestamp=00:00:05.733`，文字清晰。
- 原始文件哈希未变化。

## 失败与异常

- 无解码或输出格式错误。
- 拍摄设备类型尚未核实，manifest 中仅记录 `capture_device_type_not_yet_verified`，未擅自写为 phone 或其他相机类型。
- T06A 的 7 个标注工具仍未实现；本阶段不依赖这些工具，也不声称端到端T06B已完成。

## 下一步

- 用户依据预览视频人工填写 E001 阶段区间 CSV。
- 收到人工CSV后再校验区间、阶段枚举和边界，不自动推测动作阶段。
- 当前停止，不处理E002-E012，不进行滤波、LeRobot转换或训练。

---

## E001 验证阶段

### Run 信息

- Run ID：`20260713_T06B_E001_VALIDATE_001`
- 日期：2026-07-13 13:25 CST
- 目的：验证用户人工填写的动作阶段CSV，确定性导出逐帧标签并生成人工复核overlay。
- 状态：E001验证阶段完成；T06B整体未宣称完成，未开始其他episode。
- 是否可以用于论文：当前可作为标注流程原型证据；单个episode不足以支持数据集或方法效果结论。

### 输入及哈希

- 人工CSV：`data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations.csv`
- 人工CSV SHA-256：`d492cb6fffadb41fa5e89cd9402a04205c303038e909d01c9b1cf7ed16cffe43`
- 源视频SHA-256：`c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`
- Manifest SHA-256（验证状态更新后）：`2c6ee29944434d740a8c063b0fdf85887dc564e259137944c7bf2b61777d2b65`
- Git commit：`231fe97dc5788b0c5d40b677c0bf7f116b1b8182`（工作区含未提交修改）

### 新建脚本

- `scripts/annotation/validate_labels.py`：验证覆盖、重叠、空洞、越界、枚举、顺序和双语字段。
- `scripts/annotation/expand_frame_labels.py`：只从验证通过的人工闭区间展开frame JSONL。
- `scripts/annotation/render_labels.py`：从frame JSONL渲染双语动作阶段overlay。
- 三个脚本均通过 `py_compile` 和 `--help`；未实现或宣称T06A其余4个脚本已完成。

### 完整命令

```bash
PY=/home/a531/anaconda3/envs/motpose/bin/python

$PY -m py_compile \
  scripts/annotation/validate_labels.py \
  scripts/annotation/expand_frame_labels.py \
  scripts/annotation/render_labels.py

$PY scripts/annotation/validate_labels.py \
  --segments-csv data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations.csv \
  --manifest-csv data/action_labels/video_manifest.csv \
  --video-id pick_place_pilot_v1_E001 \
  --output results/action_labels/pick_place_pilot_v1_E001_validation_summary.json

$PY scripts/annotation/expand_frame_labels.py \
  --segments-csv data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations.csv \
  --manifest-csv data/action_labels/video_manifest.csv \
  --video-id pick_place_pilot_v1_E001 \
  --output data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl

$PY scripts/annotation/render_labels.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --frames-jsonl data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --output results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4

ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration \
  -of json results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4

ffmpeg -v error \
  -i results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4 \
  -map 0:v:0 -f null -
```

### 验证结果

- 人工区间：10条，覆盖0-344共345帧。
- 空洞：0帧；重叠：0帧；越界：0条；非法phase：0条；验证错误/警告：0/0。
- `phase_id` 与 `phase_label` 全部匹配固定词表；10条中文和英文阶段文本均非空且通过文字类型检查。
- 独立逐帧回查：345/345条JSONL与人工CSV的segment、phase、双语文本一致；时间戳为 `frame_index / 30.0`。
- Overlay：H.264、1280×720、30 FPS、345帧、11.5秒；完整解码无错误。
- 可视化抽查帧：0、46、98、107、121、140、176、194、207、214、344；阶段切换、颜色、中文、英文、frame_index和timestamp显示正确。
- 原始人工CSV和源视频未修改。

### 阶段统计

| phase_id | phase_label | 区间数 | 帧数 | 持续时间（秒） |
|---:|---|---:|---:|---:|
| 0 | idle | 2 | 177 | 5.900000 |
| 1 | reach | 1 | 52 | 1.733333 |
| 2 | align | 1 | 9 | 0.300000 |
| 3 | grasp | 1 | 14 | 0.466667 |
| 4 | lift | 1 | 19 | 0.633333 |
| 5 | transport | 1 | 36 | 1.200000 |
| 6 | place | 1 | 18 | 0.600000 |
| 7 | release | 1 | 13 | 0.433333 |
| 8 | retract | 1 | 7 | 0.233333 |
| 90 | occluded | 0 | 0 | 0.000000 |
| 91 | failed_attempt | 0 | 0 | 0.000000 |
| 98 | unknown | 0 | 0 | 0.000000 |

总计345帧、11.5秒。

### 输出

- `results/action_labels/pick_place_pilot_v1_E001_validation_summary.json`，SHA-256 `b1e382c8785d26bd90450f3f32662c855f072ac906a637e18aa64af6e2a6e76a`。
- `data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl`，345行，SHA-256 `070c9212ea654cf7f7da0ddb621cb258de09ebf5ae73db4c4c9b7325b824f62b`。
- `results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4`，SHA-256 `66cb608f19467a5413c676c5bac16bb6840858e1b030ae330f0801bb6c0958d8`。

### 当前边界

- 本次没有自动推测、修改或修复人工阶段边界。
- 没有处理E002-E012，没有运行OpenPose、DeepSORT、滤波、LeRobot转换或训练。
- 拍摄设备类型仍未核实；不影响本次阶段验证，但后续正式episode元数据需补充。

---

## E001 边界修正版复验

### Run 信息

- Run ID：`20260713_T06B_E001_REVALIDATE_001`
- 日期：2026-07-13 13:39 CST
- 目的：按用户修正的 `retract=207-244`、结束 `idle=245-344` 重建E001派生结果。
- 状态：复验通过并停止；未开始其他episode或其他算法。

### 输入裁决

- 原路径 `E001_action_phase_annotations.csv` 已不存在，未在缺少输入时覆盖任何派生结果。
- 实际修正版：`data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations_corrected.csv`。
- 修正版CSV SHA-256：`8d972c7c70418b7220fb947f6d511067c909c611919da637a3b46936631b5409`。
- CSV人工内容保持只读；源视频SHA-256仍为 `c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`。

### 完整命令

```bash
PY=/home/a531/anaconda3/envs/motpose/bin/python
SEGMENTS=data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations_corrected.csv

$PY scripts/annotation/validate_labels.py \
  --segments-csv "$SEGMENTS" \
  --manifest-csv data/action_labels/video_manifest.csv \
  --video-id pick_place_pilot_v1_E001 \
  --output results/action_labels/pick_place_pilot_v1_E001_validation_summary.json

$PY scripts/annotation/expand_frame_labels.py \
  --segments-csv "$SEGMENTS" \
  --manifest-csv data/action_labels/video_manifest.csv \
  --video-id pick_place_pilot_v1_E001 \
  --output data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl

$PY scripts/annotation/render_labels.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --frames-jsonl data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --output results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4

ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration \
  -of json results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4

ffmpeg -v error \
  -i results/action_labels/pick_place_pilot_v1_E001_phase_overlay.mp4 \
  -map 0:v:0 -f null -
```

### 真实结果

- 10个人工区间覆盖0-344共345帧；空洞0、重叠0、越界0、非法phase 0、错误0、警告0。
- 关键边界逐帧断言：frame 206=`release`；frame 207-244共38帧全部=`retract`；frame 245-344共100帧全部=`idle`。
- 新统计：`retract` 38帧/1.266667秒；全部 `idle` 合计146帧/4.866667秒。其他阶段统计不变，总计345帧/11.5秒。
- Overlay：H.264、1280×720、30 FPS、345帧、11.5秒，全量解码无错误。
- 可视化抽查206、207、244、245、344，阶段、颜色、文本、帧号和时间戳正确。

### 新输出哈希

- `frames.jsonl`：`a9b42220053136d3751cbf3de699680f5e63a1e4161b3e23bd53e60c0392301f`。
- `pick_place_pilot_v1_E001_phase_overlay.mp4`：`be57d872d5b975c679edd578224adbe4def1dd053b71b2d377b26d17b3406751`。
- `pick_place_pilot_v1_E001_validation_summary.json`：`3f7c34e4ee5b6ab51cca090652d714a2bb6029d3806458f25c4061af7164cb92`。

### 边界

- 未处理E002-E012；未运行OpenPose、DeepSORT、滤波、LeRobot转换或训练。
- 本次仅依据人工修正版重建派生文件，没有自动推测动作阶段。
