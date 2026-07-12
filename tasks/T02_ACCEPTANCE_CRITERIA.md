# T02 验收标准：DeepSORT MOT 最小闭环实验

版本：v0.1.0  
创建日期：2026-07-11  
适用范围：T02 任务"DeepSORT MOT 最小闭环实验"  
前置任务：T01（环境审计和 motpose 环境创建）  
后续任务：T03（OpenPose BODY_25 提取和关联）  

---

## 一、任务定位

T02 是 HumanVideo2VLA 项目的第一个有实际输出的计算实验。目标是在一段短视频上跑通 YOLO + DeepSORT 全流程，输出结构化数据，并由人工检查自动跟踪质量。**DeepSORT 输出是自动预标注，不是 ground truth。**

T02 明确不包含：
- OpenPose 安装或运行 → T03
- CVAT/Docker 安装或导入 → T04
- subject_id 分配 → T04（MOT 人工复核后）
- 动作标注或语言描述 → T09

---

## 二、前置条件（Pre-conditions）

Codex 在执行 T02 任何脚本之前，必须逐一验证：

| 编号 | 前置条件 | 验证命令 | 阻塞级别 |
|------|---------|---------|----------|
| P1 | `motpose` Conda 环境存在 | `conda env list \| grep motpose` | 阻塞 |
| P2 | PyTorch 可 import 且 CUDA 可用 | `python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"` | 阻塞 |
| P3 | OpenCV 可 import 且可读视频 | `python -c "import cv2; print(cv2.__version__)"` | 阻塞 |
| P4 | ultralytics 可 import | `python -c "from ultralytics import YOLO; print('ok')"` | 阻塞 |
| P5 | deep-sort-realtime 可 import | `python -c "from deep_sort_realtime.deepsort_tracker import DeepSort; print('ok')"` | 阻塞 |
| P6 | FFmpeg 可调用 | `ffmpeg -version` | 阻塞 |
| P7 | 测试视频存在于 `data/raw_videos/` | `ls -l data/raw_videos/<video_id>.*` | 阻塞 |
| P8 | 测试视频可被 OpenCV 正常打开 | Python 脚本验证 | 阻塞 |
| P9 | 环境依赖已冻结 | `environment/requirements/motpose.*` 文件存在 | 非阻塞 |

任何阻塞级别的前置条件不满足 → 不得开始执行，先报告缺失项。

---

## 三、输入视频验收

### 3.1 视频登记

Codex 必须读取视频并记录以下元数据，写入 `data/mot/raw/<video_id>/metadata.json` 的 `video` 字段：

```json
{
  "video": {
    "video_id": "<user_provided_or_generated>",
    "file_path": "data/raw_videos/<filename>",
    "sha256": "<computed>",
    "format": "mp4",
    "codec": "h264",
    "duration_sec": <float, 1 decimal>,
    "fps": <float, 2 decimals>,
    "width": <int>,
    "height": <int>,
    "total_frames": <int>,
    "num_persons_visible": <int, human count>,
    "description": "<short scene description>"
  }
}
```

### 3.2 视频约束（不满足则报告，不自动拒绝）

- 时长：10-30 秒
- 人物数：2-3 人同时在画面中
- FPS：稳定（非 VFR，或已转为 CFR）
- 画面：人物大部分可见，非背光剪影

如果视频不满足约束，Codex 应报告具体偏差但不阻止执行——用户可能仍希望用该视频测试。

---

## 四、实验参数规定

以下参数由 Claude（科研负责人）指定，Codex 不得擅自更改。如需调整必须先报告并获得批准。

### 4.1 YOLO 检测参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | `yolov8n.pt` | YOLOv8 nano，最轻量。如效果极差可升级至 `yolov8s.pt`（需记录在报告中） |
| 目标类别 | `person` (class 0) | 仅输出 person，过滤所有其他类别 |
| 置信度阈值 (conf) | `0.3` | 低于此值的检测框丢弃。较低的阈值允许更多候选，由人工在复核阶段排除 FP |
| IoU 阈值 (iou) | `0.45` | NMS 的 IoU 阈值 |
| 帧步长 | `1` | 每帧都检测 |
| 图像尺寸 (imgsz) | `640` | YOLO 输入分辨率 |

### 4.2 DeepSORT 跟踪参数

| 参数 | 值 | 说明 |
|------|-----|------|
| max_age | `30` | 丢失跟踪后保留轨迹的最大帧数（约 1 秒 @30fps） |
| n_init | `3` | 连续检测到多少帧后才确认新轨迹 |
| nn_budget | `100` | 每轨存储的外观特征向量数上限 |
| max_cosine_distance | `0.2` | 外观匹配阈值（越小越严格） |
| max_iou_distance | `0.7` | IoU 匹配阈值 |
| embedder | `mobilenet` | DeepSORT 外观特征提取器（deep-sort-realtime 默认） |

### 4.3 可视化参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 框颜色 | 按 track_id 分配固定颜色 | 同 ID 同色，便于检查 ID Switch |
| 框线宽 | `2` px | |
| ID 字号 | `0.8` (相对于框高度) | track_id 数字清晰可辨 |
| 输出编码 | `H.264` (avc1) | OpenCV `VideoWriter_fourcc(*'avc1')` 或 `*'mp4v'` |
| 输出 FPS | 与源视频相同 | |

### 4.4 固定随机种子

DeepSORT 的外观特征提取和匹配过程涉及随机性。为确保可复现：

| 参数 | 值 |
|------|-----|
| Python `random.seed` | `42` |
| NumPy `np.random.seed` | `42` |
| PyTorch `torch.manual_seed` | `42` |

注意：即使固定种子，不同 PyTorch/CUDA 版本或不同硬件的浮点运算可能产生微小差异。如果复现结果有差异，在报告中记录。

---

## 五、Codex 脚本接口定义

Codex 需要创建以下脚本。每个脚本必须支持 `--help`。

### 5.1 检测脚本：`scripts/mot/detect_persons.py`

```bash
python scripts/mot/detect_persons.py \
    --video data/raw_videos/<video_id>.mp4 \
    --model yolov8n.pt \
    --conf 0.3 \
    --iou 0.45 \
    --output data/mot/raw/<video_id>/detections_raw.jsonl
```

**输入**：MP4 视频文件  
**输出**：`detections_raw.jsonl`，每行：
```json
{"frame_index": 0, "detections": [[x1, y1, x2, y2, conf], ...], "num_detections": N}
```
- `frame_index`：0 起始
- `detections`：该帧所有 person 检测框，格式 `[x_min, y_min, x_max, y_max, confidence]`
- `num_detections`：该帧检测数（可为 0）
- 行数 = 视频总帧数

### 5.2 跟踪脚本：`scripts/mot/track_deepsort.py`

```bash
python scripts/mot/track_deepsort.py \
    --detections data/mot/raw/<video_id>/detections_raw.jsonl \
    --video data/raw_videos/<video_id>.mp4 \
    --video-id <video_id> \
    --max-age 30 \
    --n-init 3 \
    --nn-budget 100 \
    --max-cosine-distance 0.2 \
    --max-iou-distance 0.7 \
    --output-tracks data/mot/raw/<video_id>/tracks_raw.jsonl \
    --output-mot data/mot/raw/<video_id>/gt.txt \
    --output-video results/mot/<video_id>_tracked.mp4 \
    --output-metadata data/mot/raw/<video_id>/metadata.json \
    --seed 42
```

**输入**：
- `detections_raw.jsonl`（来自 5.1）
- 原始视频（用于可视化叠加）

**输出**：四个文件（见第六节格式定义）

### 5.3 可选的单脚本一键运行

如果两个脚本都通过验证，可以提供一个 wrapper：
```bash
python scripts/mot/run_pipeline.py \
    --video data/raw_videos/<video_id>.mp4 \
    --video-id <video_id> \
    [all above params with same defaults]
```
该 wrapper 依次调用 detect_persons.py 和 track_deepsort.py，并生成一个 Run ID。

---

## 六、输出文件格式定义

### 6.1 `tracks_raw.jsonl` — 逐帧轨迹

路径：`data/mot/raw/<video_id>/tracks_raw.jsonl`

每行：
```json
{
  "frame_index": 0,
  "tracks": [
    {
      "track_id": 1,
      "bbox_xyxy": [100.0, 200.0, 250.0, 480.0],
      "confidence": 0.85
    }
  ],
  "num_tracks": 1
}
```

格式约束：
- `frame_index`：0 起始，从 0 到 total_frames-1
- `track_id`：正整数，首次从 1 开始
- `bbox_xyxy`：`[x_min, y_min, x_max, y_max]`，浮点数像素坐标
- `confidence`：来自 YOLO 检测置信度
- 同一帧内 `track_id` 不重复
- 同一 track_id 的 bbox 在相邻帧间不应出现无故跳变（> 画面宽度的 50%）
- 行数 = 视频总帧数

### 6.2 `gt.txt` — MOTChallenge 格式

路径：`data/mot/raw/<video_id>/gt.txt`

格式：
```
<frame>, <id>, <bb_left>, <bb_top>, <bb_width>, <bb_height>, <conf>, <x>, <y>, <z>
```

示例：
```
1, 1, 100.0, 200.0, 150.0, 280.0, 0.85, -1, -1, -1
1, 2, 350.0, 180.0, 140.0, 300.0, 0.92, -1, -1, -1
2, 1, 102.0, 201.0, 148.0, 279.0, 0.83, -1, -1, -1
```

格式约束：
- `frame`：从 1 开始（MOTChallenge 惯例）
- `bb_left, bb_top`：左上角坐标
- `bb_width, bb_height`：宽高（不是右下角坐标），必须 > 0
- `conf`：检测置信度
- 最后三列填 `-1`（本项目无 3D 信息）
- 逗号后有一个空格（标准 MOTChallenge CSV 格式）
- 文件名使用 `gt.txt`（MOTChallenge 标准命名）

### 6.3 `tracked.mp4` — 可视化视频

路径：`results/mot/<video_id>_tracked.mp4`

要求：
- H.264 编码，兼容主流播放器
- 每个检测框叠加在原始帧上
- 框上方显示 `ID: <track_id>` 文字
- 同一 track_id 在所有帧中框颜色一致（按 track_id 数值分配颜色映射）
- 框线宽 2 px，文字大小可辨
- 帧数、FPS、分辨率与源视频一致
- 文件大小合理（< 50 MB/30 秒为参照）

### 6.4 `metadata.json` — 实验元数据

路径：`data/mot/raw/<video_id>/metadata.json`

```json
{
  "run_id": "20260711_T02_001",
  "date": "2026-07-11",
  "experiment": "T02 DeepSORT MOT minimal closed-loop",
  "video": {
    "video_id": "...",
    "file_path": "data/raw_videos/...",
    "sha256": "...",
    "duration_sec": 15.0,
    "fps": 30.00,
    "width": 1920,
    "height": 1080,
    "total_frames": 450,
    "num_persons_visible": 2
  },
  "yolo": {
    "model": "yolov8n.pt",
    "model_sha256": "...",
    "conf_threshold": 0.3,
    "iou_threshold": 0.45,
    "imgsz": 640,
    "class_filter": "person"
  },
  "deepsort": {
    "implementation": "deep-sort-realtime",
    "version": "<pip show output>",
    "max_age": 30,
    "n_init": 3,
    "nn_budget": 100,
    "max_cosine_distance": 0.2,
    "max_iou_distance": 0.7,
    "embedder": "mobilenet"
  },
  "random_seeds": {
    "python": 42,
    "numpy": 42,
    "torch": 42
  },
  "statistics": {
    "num_tracks_total": 5,
    "num_tracks_short": 1,
    "avg_track_duration_frames": 250.0,
    "min_track_duration_frames": 12,
    "max_track_duration_frames": 440,
    "total_person_detections": 880,
    "avg_detections_per_frame": 1.96,
    "processing_fps_detection": 45.0,
    "processing_fps_tracking": 120.0
  },
  "git_commit": "<git rev-parse HEAD output>",
  "environment": {
    "conda_env": "motpose",
    "python_version": "3.10.x",
    "torch_version": "2.x.x",
    "cuda_version": "12.x",
    "gpu_name": "NVIDIA GeForce RTX 3090"
  },
  "output_files": [
    "data/mot/raw/<video_id>/tracks_raw.jsonl",
    "data/mot/raw/<video_id>/gt.txt",
    "data/mot/raw/<video_id>/detections_raw.jsonl",
    "results/mot/<video_id>_tracked.mp4"
  ]
}
```

Codex 应填写所有字段，不要输出 `"TBD"` 或占位符。如果某些值无法获取（如模型 SHA-256），记录为 `"unavailable"` 并说明原因。

---

## 七、人工检查规则

T02 阶段暂不安装 CVAT。人工检查通过观看 `tracked.mp4` 并逐帧检查 `tracks_raw.jsonl` 完成。

### 7.1 检查方法

1. **快速播放检查**：以 1× 速度观看 `tracked.mp4`，关注：
   - 框是否始终跟随同一个人（无突然"跳"到另一个人身上）
   - 人物交叉时 ID 是否交换
2. **逐帧扫描交叉段**：在两人靠近/交叉的帧段，逐帧检查 ID 归属
3. **轨迹统计审查**：读取 `metadata.json`，检查是否有过于短的轨迹（< 5 帧）

### 7.2 四类错误定义和记录模板

以下定义与 `context/MOT_ANNOTATION_PROTOCOL.md` 一致，T02 阶段执行简化版。

#### ID Switch（身份交换）

**定义**：一条 track_id 在视频中途从人物 A 切换到人物 B。

**记录模板**：
```
ID Switch #1:
  track_id: 3
  switch frame: ~147
  description: track_3 was on person in blue shirt (frames 0-146), then jumped to person in red shirt (frames 147+)
  severity: CRITICAL
```

#### Track Fragmentation（轨迹断裂）

**定义**：同一人物被分配多个不同 track_id。

**记录模板**：
```
Fragmentation #1:
  person: "blue shirt"
  track_ids: track_2 (frame 0-50) + track_7 (frame 58-120)
  missing frames: 51-57
  cause: occlusion by table
  should_merge: yes
```

#### False Positive Track（误检轨迹）

**定义**：track_id 对应的框不包含真实人物。

**记录模板**：
```
FP #1:
  track_id: 5
  frames: 200-215
  description: detection on a chair/coat rack
  action: mark for deletion in review phase
```

#### Missing Track（漏检）

**定义**：画面中有真实人物但无任何 track_id。

**记录模板**：
```
Missing #1:
  frames: 89-95
  person_description: person in white shirt, far side of room
  cause: low detection confidence (likely too far/small)
  action: note for manual box addition in review phase
```

### 7.3 检查记录输出

人工检查结果写入：`data/mot/raw/<video_id>/human_review_notes.md`

```markdown
# Human Review Notes: <video_id>

- 审查日期：
- 审查人：
- 输入：data/mot/raw/<video_id>/tracks_raw.jsonl
- 参考视频：results/mot/<video_id>_tracked.mp4

## 汇总
- ID Switch: N 处
- Track Fragmentation: N 处
- False Positive Track: N 处
- Missing Track: N 段

## 逐项记录
（按 7.2 模板逐项填写）

## 整体评价
（一两句话总结自动跟踪质量，必须引用具体数字，不得使用"效果好""较稳定"等模糊表述）
```

---

## 八、运行日志要求

Codex 完成脚本执行后，生成 `logs/runs/<RunID>.md`，必须包含：

```markdown
# Run ID: 20260711_T02_001

- 日期：2026-07-11
- 实验目的：T02 DeepSORT MOT 最小闭环实验
- 环境：motpose, Python 3.10.x, torch 2.x.x, RTX 3090
- 输入文件：
  - data/raw_videos/<video_id>.mp4 (SHA-256: ...)
- Git commit: <git rev-parse HEAD>
- 完整命令：
  （5.1、5.2 的实际运行命令）
- 参数：见 metadata.json
- 输出文件：
  - data/mot/raw/<video_id>/detections_raw.jsonl
  - data/mot/raw/<video_id>/tracks_raw.jsonl
  - data/mot/raw/<video_id>/gt.txt
  - data/mot/raw/<video_id>/metadata.json
  - results/mot/<video_id>_tracked.mp4
- 定量结果：
  - 总帧数：
  - 总检测数：
  - 轨迹数：
  - 短轨数（< 5 帧）：
  - 平均轨迹时长（帧）：
  - 检测速度（fps）：
  - 跟踪速度（fps，不含检测）：
- 可视化结果：results/mot/<video_id>_tracked.mp4
- 异常与失败：（如无，写"无"；如有，详细描述）
- 原因分析：（如有异常）
- 下一步计划：人工检查 -> 修正 -> T03 OpenPose
- 是否可以用于论文：否（自动输出，未经人工复核）
```

---

## 九、验收 checklist

### 9.1 脚本质量

- [ ] `detect_persons.py --help` 输出完整参数说明
- [ ] `track_deepsort.py --help` 输出完整参数说明
- [ ] 脚本包含 try/except 异常处理，不在中间步骤静默失败
- [ ] 脚本使用 `logging` 模块（非 `print` 散落）
- [ ] 脚本包含文件头 docstring 说明功能

### 9.2 输出文件格式

- [ ] `detections_raw.jsonl` 行数 = 视频总帧数
- [ ] `tracks_raw.jsonl` 行数 = 视频总帧数
- [ ] `gt.txt` 每行格式正确（10 列，逗号+空格分隔）
- [ ] `metadata.json` 所有字段已填写，无 "TBD"
- [ ] `tracked.mp4` 可正常播放，无花屏/丢帧

### 9.3 数据合理性

- [ ] track_id 为正整数，1 起始
- [ ] 同一帧内无重复 track_id
- [ ] 检测置信度在 [0, 1]
- [ ] bbox 坐标 `x_min < x_max`, `y_min < y_max`
- [ ] 无全帧零检测（除非视频中确实无人）
- [ ] bbox 大小合理（不覆盖整个画面，不太小如一像素）

### 9.4 文档完整性

- [ ] 运行日志 `logs/runs/<RunID>.md` 填写完整
- [ ] `human_review_notes.md` 包含具体错误记录（非仅"无错误"）
- [ ] metadata.json 中的 statistics 数字与实际文件一致

---

## 十、不通过条件

以下任一情况出现，T02 视为未通过：

1. **脚本无法运行或中途崩溃且无错误处理**
2. **detections_raw.jsonl 行数 ≠ 视频总帧数**
3. **tracks_raw.jsonl 行数 ≠ 视频总帧数**
4. **gt.txt 格式与 MOTChallenge 标准不一致（列数、坐标格式错误）**
5. **tracked.mp4 无法播放或帧数/FPS/时长与源视频不一致**
6. **metadata.json 中参数与实际运行参数不一致**
7. **所有帧检测数 = 0（YOLO 未检测到任何人）**
8. **所有帧 tracks = [] 或所有 track_id = 同一值**
9. **运行日志缺失命令或参数**
10. **原始视频被覆盖**
11. **DeepSORT 输出被称为 "GT" 或 "真值"**

---

## 十一、通过条件

T02 通过 = 所有验收 checklist 标记为 [x] + 零条不通过条件触发 + 人工确认输出文件。

通过后动作：
- 将 T02 状态更新为 `COMPLETED`
- 将 T03（OpenPose BODY_25）置为 `PENDING`（仍需用户单独批准 OpenPose 安装）
- 将 T04（CVAT 人工复核）置为 `PENDING`（仍需 Docker/CVAT 安装批准）
