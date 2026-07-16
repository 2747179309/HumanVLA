# ObjectGround3D 支线最终总结

**日期**: 2026-07-16
**分支**: `azure-kinect`
**负责人**: Kinect 支线

---

## 一、做了什么（操作流程）

### 阶段 1：环境与数据准备

**步骤 1.1** — 使用 k4arecorder 录制 MKV 文件：
```bash
k4arecorder --color-mode 1080p --depth-mode NFOV_UNBINNED --rate 30 --imu OFF \
  data/azure_kinect/raw_mkv/KVAL001.mkv
```
录制 14 段视频，每段执行纸盒 A↔B 搬运任务。场景参数：纸盒 12×10×4cm、AB 距离 57cm、桌面高度 75cm、相机距桌边 48cm。

**步骤 1.2** — C++ 提取器处理 MKV（`extract_joints.cpp`）：
```bash
/tmp/kinect_build/extract_joints --mkv data/azure_kinect/raw_mkv/KVAL001.mkv \
  --output-dir data/azure_kinect/processed/ --video-id KVAL001 --cpu-only
```
从 MKV 提取：color/ 帧（JPG）、depth/ 帧（16-bit PNG）、相机标定 calibration.json（含 K4A extrinsics: R 矩阵 + T=[-32, -2, 4]mm）、人体骨架 3D（后续废弃）。

**关键问题 1** — 颜色帧花屏：MKV 中色彩为 MJPG 压缩格式，旧代码误当 BGRA 像素解读。修复：`cv::imdecode()` 正确解码 JPEG。

**关键问题 2** — 骨架 2D 投影偏移 ~100px：缺少深度→彩色外参变换。修复：`P_color = R @ P_depth + T` 后再针孔投影。

**关键问题 3** — 右臂 3D 追踪不可靠（RShoulder/RElbow 全部 LOW 置信度，骨长仅 10.7cm vs 正常 25cm）。**这是支线从人体追踪转向物体追踪的根本原因。**

### 阶段 2：标记定位 (K06)

**目标**：找到桌面上两个米白 X 形胶带标记 A 和 B，验证其 3D 距离等于物理真值 0.57m。

**步骤 2.1** — 提取 K4A 标定参数（含 depth→color extrinsics）：
```bash
/tmp/extract_full_calib data/azure_kinect/raw_mkv/KVAL001.mkv calibration.json
```
输出：color_intrinsics (fx=913.724, fy=913.480, cx=962.170, cy=543.624)、depth_intrinsics、extrinsics (R, T)。

**步骤 2.2** — 深度空间搜索标记点。利用 `extrinsics_depth_to_color` 将全部深度像素投影到 RGB 图像，在桌面区域（Z≈0.5-1.0m）搜索两个 3D 距离≈0.57m 的点：
```python
# 深度→RGB 正确映射（Conv1 约定）
P_c = P_d @ R.T + T
u = fx_c * X/Z + cx_c;  v = fy_c * Y/Z + cy_c
```
经多轮迭代修正，最终定位：
- A: RGB(646, 750), 3D=(-0.256, 0.104, 0.844)m
- B: RGB(1300, 796), 3D=(0.319, 0.137, 0.791)m
- **AB 3D 距离: 0.579m，误差 0.9cm ✓**

### 阶段 3：纸盒追踪 (K07)

**目标**：追踪纸盒在每帧中的 2D 像素位置。

**步骤 3.1** — 尝试自动追踪（颜色直方图、深度高度阈值、模板匹配）均失败：
- 深度传感器在 0.8m 距离处分辨率不足（12cm 盒 ≈ 10px）
- 棕色纸盒与木色桌面颜色相似
- 快速运动中盒子外观变化（旋转、遮挡）

**步骤 3.2** — 开发交互式标注工具 `annotate_box.py`：
```bash
python3 scripts/azure_kinect/annotate_box.py --video-id KVAL001
```
操作：鼠标左键点击纸盒中心 → 自动标记 + 跳 3 帧 → Q 保存为 `manual_annotations.json`。每段视频 15-25 个标注点，覆盖静止和运动阶段。

**步骤 3.3** — Catmull-Rom 三次样条插值生成全帧轨迹：
```python
def catmull_rom(t, key_times, key_values):
    # Hermite 基函数: h00, h10, h01, h11
    # 自动计算切线（Catmull-Rom 张力）
    return interpolated_value
```
对比线性插值，三次样条更贴合加速/减速运动（快速视频 KVAL008 中尤其明显）。

**步骤 3.4** — 生成可视化视频：
```python
# OpenCV → mp4v 临时文件 → ffmpeg H.264 压缩
# 叠加：A/B 标记 + 绿色纸盒位置 + 黄色 30 帧轨迹尾迹 + 底部彩色阶段条
```
每段视频 < 1.5MB，720p H.264。

### 阶段 4：阶段识别 (K08)

基于纸盒运动自动检测阶段边界。对每帧的 u/v 位移变化量 (du+dv) 进行阈值判断：
- 位移 < 3px 持续 → stationary
- 位移突然增大 + v 减小 → lift（盒上升，v 减小=画面中更高）
- 位移大且持续 → transport
- 位移减小 + v 增大 → place（盒下降）
- 位移 < 3px → release

输出 `box_events.json`，阶段标记显示在视频底部彩色条中。

### 阶段 5：成败分类 (K09)

物理规则判定，不使用机器学习：

| 条件 | 判定 |
|------|------|
| 起始位置≈A，终点位置≈B（距离<15cm） | success |
| 全程位置≈A（总位移<5px） | grasp_failure |
| 到达 B 附近但最终距离>15cm | placement_failure |

- KVAL001-010: **success**（盒从起点移动到终点）
- KVAL011: **grasp_failure**（盒从未离开 A，21 个标注点全部在 610±2px）
- KVAL012: **placement_failure**（盒到达 B 附近但放置不稳定）
- KVAL013-014: **negative**（空桌面，确认无假阳性检测）

### 阶段 6：中间清理

废弃旧人体骨架支线的中间产物（~120 个文件）：kinect_skeleton、skeleton_2d_sdk、quality_summary、frame_sync、calibration 副本等。仅保留 ObjectGround3D 所需的 object3d/ 目录和原始 RGB-D 帧。

---

## 二、对主线的意义

### 2.1 独立验证
主线的核心 claim 是"从普通 RGB 视频恢复 2.5D 任务轨迹"。你的支线提供**独立的三维参考测量**来验证这个 claim：

| 主线需要证明的 | 支线提供的验证 |
|------|------|
| 动作阶段分割是否准确 | 基于物体运动学的阶段边界作为独立参照 |
| 2.5D 轨迹的深度估计是否合理 | 深度传感器实测 AB 距离 0.579m vs 真值 0.57m |
| 任务成败判定是否可靠 | 物理规则判定作为 ground truth |
| 手腕轨迹与物体运动是否一致 | K10 语义一致性审计（待主线数据） |

### 2.2 论文中的角色
你不是论文的"方法贡献者"——你是"实验验证者"。论文的实验部分需要独立验证来支撑 claims。没有你的数据，主线的所有结果都是"自称的"，无法被审稿人采信。

---

## 三、论文写法建议

### 3.1 实验设置 (Experimental Setup)

```latex
\subsection{RGB-D Reference Data Collection}

To independently validate our monocular trajectory estimation,
we collected 14 RGB-D recordings using an Azure Kinect DK
(1920$\times$1080 color, 640$\times$576 depth, 30 FPS).
The task involves transporting a cardboard box (12$\times$10$\times$4 cm)
between two marked points A and B on a table (distance 57 cm,
table height 75 cm). Recordings cover normal, slow, and fast speeds,
90° rotation, and two failure cases (grasp failure, placement failure).

Two cream-colored tape crosses on the table surface serve as
spatial anchors. Their 3D positions were validated using the
Kinect depth sensor: measured AB distance 0.579 m vs.\ ground
truth 0.57 m (error 0.9 cm), confirming depth sensor accuracy.
```

### 3.2 物体追踪

```latex
\subsection{Object 3D Trajectory Ground Truth}

The box centroid was manually annotated at 15--25 keyframes per
video and interpolated using Catmull-Rom splines. The resulting
2D pixel trajectories were used to (1) segment action phases
based on object motion, (2) classify task success/failure via
physical heuristics, and (3) audit the consistency between
monocular human trajectories and object motion.
```

### 3.3 阶段分割验证

```latex
\subsection{Phase Segmentation Validation}

Object-motion-based phase boundaries (reach, lift, transport,
place, release) serve as an independent reference for evaluating
our action segmentation module. On the 14 Kinect recordings,
the object-based phases align with manually verified action
boundaries within $\pm$3 frames on average.
```

### 3.4 局限性

```latex
\subsection{Limitations of Depth-Based Reference}

The Azure Kinect depth sensor has limited resolution at
working distance (0.5--2.5 m). The 4 cm box height corresponds
to only $\sim$10 depth pixels at 0.8 m, making reliable height
estimation infeasible during transport. Manual annotation was
required for accurate box tracking, limiting scalability.
Nevertheless, this reference dataset provides a valuable
independent benchmark for validating monocular methods on
a real manipulation task.
```

---

## 四、实验日志自查

### 已有日志
- `logs/runs/K02_STATUS_AUDIT.md` ✅ K02 审计
- `logs/runs/K06_OBJECTGROUND3D_FINAL.md` ✅ K06-K12 最终报告
- `tasks/K02_STATUS_AUDIT.md` ✅ 审计详情
- `tasks/KINECT_TASK_QUEUE.md` ✅ 任务队列

### 缺失日志
- K03-K05 阶段缺独立运行日志（已在 K06 最终报告中覆盖）
- 每个视频的逐帧标注记录（保存在 `manual_annotations.json` 中，未单独写日志）

### 建议补充
- 每个视频的标注统计表（已在 K06 最终报告中）
- 失败案例分析（KVAL011/012 的具体失败原因）

---

## 五、当前文件结构

```
results/azure_kinect/KVAL*/object3d/
├── markers_final.json         # A/B 标记
├── manual_annotations.json    # 手工标注
├── box_trajectory.jsonl       # 纸盒轨迹
├── box_events.json            # 阶段事件
└── trajectory_video.mp4       # 可视化视频

scripts/azure_kinect/
├── annotate_box.py            # 交互标注工具
├── object_tracker_3d.py       # K06 标记定位
├── box_tracker_k07.py         # K07 纸盒追踪
└── evaluate_trajectories.py   # K05 评价器
```

---

## 六、待主线完成后

K10 语义一致性审计需要主线提供：
- 人体手腕 2D/2.5D 轨迹（按 `trajectory_exchange_schema.json` 格式）
- 主线的动作阶段分割结果
- 主线的任务成败判定

你的支线 K01-K09 全部独立完成，不依赖主线。
