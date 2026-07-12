# T03 验收标准：OpenPose BODY_25 构建与最小闭环测试

版本：v0.3.0
创建日期：2026-07-12
适用范围：T03 — OpenPose BODY_25 构建与最小闭环测试
前置任务：T02（DeepSORT MOT 最小闭环，已关闭）
后续任务：T04（OpenPose 骨架与 DeepSORT ID 关联）
处理视频：`data/raw_videos/three-people-walking.mp4`

---

## 一、任务定位

对已完成 MOT 复核的 `three-people-walking.mp4` 运行 CMU OpenPose BODY_25 关键点提取，验证 OpenPose 可以在 RTX 3090 上正常工作，输出结构正确的逐帧 JSON，并统计关键点检测质量。

MOT 复核结果（已完成）：
- P001(track_1), P002(track_2), P003(track_3) — main_subject, frame 0-239
- track_id 4 — confirmed_false_positive，不在 subject_map 中
- ID Switch / Fragmentation / Missing Track — 全部 no_issue

T03 明确不包含：
- OpenPose 骨架与 DeepSORT track_id/subject_id 的关联 → T04
- 3D 骨架提升 → E3
- 动作标注 → T06
- CVAT 操作、NVIDIA 驱动修改、系统 CUDA/Python 修改、VLA 训练

---

## 二、前置条件

| 编号 | 前置条件 | 验证方式 | 阻塞 |
|------|---------|---------|------|
| P1 | `three-people-walking.mp4` 在 `data/raw_videos/` | SHA-256 `1dafa388...` | 阻塞 |
| P2 | MOT 复核 CSV 存在 | `data/mot/reviewed/three-people-walking.csv` | 阻塞 |
| P3 | subject_map CSV 存在 | `data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv` | 阻塞 |
| P4 | OpenPose 在 `tools/openpose/` 构建成功 (GPU) | openpose.bin 存在 | 阻塞 |
| P5 | BODY_25 caffemodel 已下载 | `pose_iter_584000.caffemodel` 存在 | 阻塞 |
| P6 | OpenPose 单帧冒烟测试通过 | 测试命令 | 阻塞 |
| P7 | 构建记录已写入 | `environment/requirements/openpose-build.txt` | 非阻塞 |

---

## 三、OpenPose 构建与运行参数

### 3.1 构建要求

- 源码目录：`tools/openpose/`，项目内构建，不 `sudo make install`
- GPU 模式 (CUDA)，RTX 3090
- 记录内容（`environment/requirements/openpose-build.txt`）：
  - Git commit hash 和仓库 URL
  - CMake 参数（特别是 GPU_MODE、CUDA 版本、cuDNN 路径）
  - `apt` 安装的系统依赖列表
  - 编译警告或错误
  - 许可证类型

### 3.2 运行参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | BODY_25 | |
| 输入 | `data/raw_videos/three-people-walking.mp4` | 240 帧, 2160×3840, 23.976 FPS |
| `--write_json` | `results/openpose/three-people-walking/raw_json/` | 逐帧 JSON |
| `--write_video` | `results/openpose/three-people-walking/rendered.mp4` | 骨架渲染视频 |
| `--display` | `0` | 无 GUI |
| `--render_pose` | `1` | 渲染骨架 |
| `--number_people_max` | `6` | |
| `--net_resolution` | `-1x368` | 实际值记录在 metadata |
| GPU | CUDA 模式优先 | 如不可用记录原因 |

---

## 四、输出文件规范

### 4.1 逐帧 JSON

路径：`results/openpose/three-people-walking/raw_json/`

命名：`three-people-walking_<frame_index:012d>_keypoints.json`

```json
{
  "version": 1.3,
  "people": [
    {
      "person_id": [-1],
      "pose_keypoints_2d": [x0, y0, c0, ..., x24, y24, c24],
      "face_keypoints_2d": [],
      "hand_left_keypoints_2d": [],
      "hand_right_keypoints_2d": [],
      "pose_keypoints_3d": [],
      "face_keypoints_3d": [],
      "hand_left_keypoints_3d": [],
      "hand_right_keypoints_3d": []
    }
  ]
}
```

格式约束：
- `pose_keypoints_2d` 长度必须 = 75 (25×3)，不得截断
- 缺失点保持 `[0.0, 0.0, 0.0]`，不得删除
- `people` 可为空数组
- JSON 文件总数 = 240（视频总帧数）
- **people 数组顺序不表示身份，禁止关联到 subject_id**

### 4.2 骨架渲染视频

路径：`results/openpose/three-people-walking/rendered.mp4`

- H.264 编码，240 帧，23.976 FPS，2160×3840
- OpenPose 默认骨架颜色方案
- 如果 OpenPose 无法直接输出 H.264，使用 `--write_images` + FFmpeg 合成

### 4.3 metadata.json

路径：`results/openpose/three-people-walking/metadata.json`

```json
{
  "run_id": "20260712_T03_001",
  "experiment": "T03 OpenPose BODY_25 build and minimal closed-loop test",
  "video": {
    "video_id": "three-people-walking",
    "sha256": "1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd",
    "fps": 23.976, "width": 2160, "height": 3840,
    "total_frames": 240, "duration_sec": 10.01
  },
  "mot_review": {
    "review_csv": "data/mot/reviewed/three-people-walking.csv",
    "subject_map_csv": "data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv",
    "main_subjects": ["P001", "P002", "P003"],
    "excluded": ["track_id 4 = confirmed_false_positive"]
  },
  "openpose": {
    "git_commit": "...",
    "model": "BODY_25",
    "net_resolution": "...",
    "number_people_max": 6,
    "gpu_mode": true,
    "gpu_name": "NVIDIA GeForce RTX 3090",
    "build_cmake_flags": "..."
  },
  "statistics": {
    "total_frames_processed": 240,
    "frames_without_skeleton": null,
    "avg_people_per_frame": null,
    "avg_valid_keypoints_per_person": null,
    "shoulder_missing_rate": null,
    "elbow_missing_rate": null,
    "wrist_missing_rate": null,
    "processing_fps": null
  },
  "environment": {
    "cuda_version": "11.3 (system nvcc)",
    "driver_version": "550.144.03",
    "gcc_version": "9.4.0"
  },
  "git_commit": "...",
  "artifact_semantics": "OpenPose automatic output. people array order is NOT identity. Association with subject_id deferred to T04."
}
```

### 4.4 summary.json

路径：`results/openpose/three-people-walking/summary.json`

240 条逐帧记录：
```json
{
  "frame_stats": [
    {
      "frame_index": 0,
      "num_people": 3,
      "person_keypoint_counts": [25, 25, 20],
      "mean_confidence": [0.78, 0.82, 0.45],
      "flagged": false
    }
  ]
}
```

flagged=true 条件：num_people=0 / mean_conf<0.3 / 有效点<10。

---

## 五、JSON 结构验证（自动）

| 检查项 | 不通过条件 |
|--------|-----------|
| JSON 文件数 = 240 | ≠ 240 |
| 每个 JSON 可被 `json.load` 解析 | 解析失败 |
| 每个 person 的 `pose_keypoints_2d` 长度 = 75 | ≠ 75 |
| 关键点坐标为数值类型 | 非数值 |
| 置信度 ∈ [0, 1] | 超出 |
| 无 NaN/Inf | 存在 |
| people 数组结构完整 | 缺少必需字段 |

---

## 六、关键点检测统计

### 6.1 基础统计

| 指标 | 计算方式 |
|------|---------|
| 无骨架帧数 | `num_people == 0` 的帧数 |
| 每帧平均人数 | `sum(num_people) / 240` |
| 平均有效关键点数 | 有效点总数 / person 实例总数（有效 = conf > 0） |

### 6.2 逐关节缺失率（必须报告）

```
缺失率 = 1 - (该关节 conf > 0 的实例数 / 总 person 实例数)
```

必须单独报告以下关节组：
- **肩部**：RShoulder(2), LShoulder(5)
- **肘部**：RElbow(3), LElbow(6)
- **腕部**：RWrist(4), LWrist(7)

腕部缺失率是最关键指标（直接影响 T04 和 E4 人机映射）。

### 6.3 报告位置

以上统计写入 `metadata.json` 的 `statistics` 字段和运行日志。

---

## 七、人工抽查

### 7.1 抽查量：≥20 帧

| 类型 | 数量 |
|------|------|
| 常规帧（人物清晰、姿态常规） | 10 帧 |
| 困难帧（遮挡/交叉/边缘/运动模糊） | 10 帧 |

困难帧选择参照 `context/OPENPOSE_BODY25_PROTOCOL.md` 5.2 节。

### 7.2 检查内容

每帧检查：
1. 骨架归属（叠加在正确人物上，非背景/他人/phantom）
2. 关键点解剖位置（腕/肘/肩/髋/膝/踝无严重偏移）
3. 左右方向（以被拍摄者自身为准，尤其背面人物）
4. 遮挡推断（无随机飘移）
5. phantom person（无真实人物对应但有骨架输出）

### 7.3 抽查记录

写入 `results/openpose/three-people-walking/human_spot_check.md`，包含逐帧记录、严重错误汇总、整体评价（定量表述）。

---

## 八、不通过条件

1. OpenPose 无法调用 RTX 3090
2. JSON 文件数 ≠ 240
3. 任何 `pose_keypoints_2d` 长度 ≠ 75
4. 渲染视频无法播放
5. 无骨架帧数 > 24 (10%)
6. wrist (关节 4, 7) 缺失率 > 50%
7. 骨架视频中 >20% 骨架明显错位或 phantom
8. metadata.json 或 summary.json 缺失或字段不完整
9. 运行日志缺失命令、参数或异常记录
10. people 数组下标被当作身份 ID 使用
11. NVIDIA 驱动、系统 CUDA 或系统 Python 被修改

---

## 九、通过条件

所有自动检查通过 + 人工抽查确认无系统性错误 + 全部统计指标已填写 + 运行日志完整。

通过后：T03 → COMPLETED，T04（骨架与 DeepSORT ID 关联）可讨论。不自动开始后续任务。

---

## 十、环境风险

| 风险 | 缓解 |
|------|------|
| OpenPose/Caffe 与 CUDA 11.3 + GCC 9.4 不兼容 | 记录具体错误；MMPose BODY_25 为备选 (D007) |
| cuDNN 版本冲突 | CMake 指定 cuDNN 路径 |
| Python 环境冲突 | T03 仅用 C++ CLI，不通过 Python 调用 OpenPose |
| 竖屏 2160×3840 | 非典型比例，记录在 metadata 中 |

**OpenPose 构建需用户单独批准（D003, D007）。本轮只制定任务和验收标准，不安装软件、不运行实验。**
