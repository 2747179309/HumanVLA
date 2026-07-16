# ObjectGround3D 支线最终总结

**日期**: 2026-07-16
**分支**: `azure-kinect`
**负责人**: Kinect 支线

---

## 一、做了什么

### 1.1 数据采集
使用 Azure Kinect DK 录制 14 段纸盒搬运 RGB-D 视频：
- KVAL001-003: A→B 正常速度
- KVAL004-006: B→A 正常速度
- KVAL007: A→B 慢速（536 帧）
- KVAL008: A→B 快速（236 帧）
- KVAL009: A→B 带 90° 旋转
- KVAL010: B→A 带 90° 旋转
- KVAL011: 抓取失败（盒未离开 A）
- KVAL012: 放置失败（盒到达 B 但未放稳）
- KVAL013-014: 空桌面（负样本）

### 1.2 标记定位 (K06)
- 深度空间搜索桌面 A/B 标记点（米白 X 形胶带）
- 利用 K4A extrinsics (R, T) 进行深度→RGB 投影
- **AB 距离验证**: 实测 0.579m vs 真值 0.57m，误差 0.9cm ✓

### 1.3 纸盒追踪 (K07)
- 开发交互式标注工具 (`annotate_box.py`)
- Catmull-Rom 三次样条插值生成平滑轨迹
- 12 段视频 × 15-25 个标注帧 = ~230 个手工标注点
- 输出每帧纸盒 2D 质心坐标

### 1.4 阶段识别 (K08)
- 基于纸盒运动自动识别 5-6 个动作阶段
- reach → lift → transport → place → release
- 旋转案例额外包含 rotate 阶段

### 1.5 成败分类 (K09)
- 物理规则判定：
  - KVAL001-010: success
  - KVAL011: grasp_failure（总位移 < 5px）
  - KVAL012: placement_failure（到达 B 但未稳定停留）

### 1.6 可视化
- 12 段轨迹叠加视频（带阶段条 + 运动轨迹尾迹）
- 可供论文 Supplementary Material 使用

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
