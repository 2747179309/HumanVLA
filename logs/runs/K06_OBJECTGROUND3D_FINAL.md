# ObjectGround3D — Final Experiment Log

**Run ID**: K06-K12_FINAL
**Date**: 2026-07-15 ~ 2026-07-16
**Branch**: `azure-kinect`
**Task**: ObjectGround3D 支线 — 纸盒 3D 追踪与动作阶段识别

---

## 一、任务概述

从人体骨架追踪转向物体中心追踪。利用 Azure Kinect RGB-D 数据：
1. 标定桌面 A/B 标记点
2. 追踪纸盒 3D 运动轨迹
3. 识别动作阶段
4. 分类任务成败

## 二、核心技术路线

### 标记定位 (K06)
- 深度空间搜索 A/B 标记点（米白 X 形胶带）
- 利用 K4A extrinsics 进行深度→RGB 投影
- AB 距离验证：实测 0.579m vs 真值 0.57m（误差 0.9cm）

### 纸盒追踪 (K07)
- 交互式标注工具 (`annotate_box.py`)
- Catmull-Rom 三次样条插值
- 14 段视频 × 15-25 个标注帧
- 输出：`box_trajectory.jsonl`

### 阶段识别 (K08)
- 基于纸盒运动自动检测阶段边界
- 5-6 阶段：reach → lift → transport → place → release

### 成败分类 (K09)
- 物理规则判定：位移距离、终点位置
- KVAL011: grasp_failure（盒未离开 A）
- KVAL012: placement_failure（盒到达 B 但放置失败）

## 三、数据产出

| 视频 | 条件 | 帧数 | 标注数 | 分类 |
|------|------|------|:---:|------|
| KVAL001 | A→B 正常 | 335 | 22 | success |
| KVAL002 | A→B 正常 | 305 | 16 | success |
| KVAL003 | A→B 正常 | 230 | 16 | success |
| KVAL004 | B→A 正常 | 241 | 16 | success |
| KVAL005 | B→A 正常 | 259 | 16 | success |
| KVAL006 | B→A 正常 | 278 | 16 | success |
| KVAL007 | A→B 慢速 | 536 | 17 | success |
| KVAL008 | A→B 快速 | 236 | 23 | success |
| KVAL009 | A→B 旋转 | 344 | 19 | success |
| KVAL010 | B→A 旋转 | 368 | 25 | success |
| KVAL011 | 抓取失败 | 290 | 21 | grasp_failure |
| KVAL012 | 放置失败 | 428 | 24 | placement_failure |
| KVAL013-014 | 空桌面 | — | — | negative |

## 四、关键文件

### 脚本
```
scripts/azure_kinect/annotate_box.py       # 交互式标注工具
scripts/azure_kinect/object_tracker_3d.py  # K06 标记定位
scripts/azure_kinect/box_tracker_k07.py    # K07 纸盒追踪
scripts/azure_kinect/evaluate_trajectories.py # K05 评价器
```

### 每个视频输出
```
results/azure_kinect/KVAL*/object3d/
├── markers_final.json         # A/B 标记坐标
├── manual_annotations.json    # 手工标注
├── box_trajectory.jsonl       # 纸盒 2D 轨迹
├── box_events.json            # 阶段事件
└── trajectory_video.mp4       # 可视化视频
```

## 五、经验教训

1. **深度传感器局限**：0.8m 距离处 4cm 纸盒仅 ~10 深度像素，高度测量不可靠
2. **颜色追踪困难**：棕色纸盒与木色桌面颜色相似
3. **手工标注必要**：快速运动时自动追踪不可靠，交互式标注是最有效方案
4. **三次样条 > 线性插值**：Catmull-Rom 曲线比线性插值更贴合真实运动

## 六、论文支撑

本支线为论文提供：
- 独立 RGB-D 参考测量系统
- 物体运动学与动作阶段对应关系
- 任务成败的物理规则判定
- 主线人体轨迹的语义一致性审计基础 (K10)
