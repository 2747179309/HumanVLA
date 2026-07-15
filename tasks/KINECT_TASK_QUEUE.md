# Kinect 支线任务队列

**分支**: `azure-kinect`
**负责人**: Claude (Kinect 支线)
**更新日期**: 2026-07-15

---

## 任务总览

| 优先级 | ID | 任务 | 状态 | 依赖 |
|--------|-----|------|------|------|
| P0 | K02 | Kinect 标准化与同步审计 | 🔄 进行中 | — |
| P0 | K02A-R1~R10 | K02 修正任务 (见验收标准) | ⬜ 待办 | K02-STATUS-AUDIT ✅ |
| P1 | K03 | 匹配纸盒任务 RGB-D 数据采集 | ⬜ 待办 | K02 ✅ |
| P1 | K04 | 三维参考轨迹生成与质量掩码 | ⬜ 待办 | K03 ✅ |
| P2 | K05 | 2D/2.5D/3D 统一评价工具 | ⬜ 待办 | K04 ✅ |
| P2 | K06 | 主线方法接入与论文验证实验 | ⬜ 待办 | K05 ✅ |

---

## 详细任务分解

### K02 — Kinect 标准化与同步审计

**当前子任务**:

| ID | 说明 | 状态 | 预计工作量 |
|----|------|------|-----------|
| K02-STATUS-AUDIT | 支线现状全面审计 | ✅ 完成 | 已完成 |
| K02A-R1 | 修复 zip() 合并逻辑 | ⬜ | 小 |
| K02A-R2 | 提取实际相机标定 | ⬜ | 中 |
| K02A-R3 | 正确标定重新投影 | ⬜ | 中 |
| K02A-R4 | 补全标准化字段 | ⬜ | 中 |
| K02A-R5 | 消除硬编码路径 | ⬜ | 中 |
| K02A-R6 | 文件完整性校验 | ⬜ | 小 |
| K02A-R7 | 时间同步验证 | ⬜ | 小 |
| K02A-R8 | 置信度与质量掩码 | ⬜ | 中 |
| K02A-R9 | 创建学习文档 | ⬜ | 中 |
| K02A-R10 | 创建交换 Schema | ⬜ | 中 |

### K03 — 匹配纸盒任务 RGB-D 数据采集

**计划录制**:

| ID | 条件 | 帧数估计 | 状态 |
|----|------|---------|------|
| KVAL001 | 正常速度, A→B, 成功 | ~300 | ⬜ |
| KVAL002 | 慢速, A→B, 成功 | ~450 | ⬜ |
| KVAL003 | 快速, A→B, 成功 | ~150 | ⬜ |
| KVAL004 | 轻度遮挡, A→B | ~350 | ⬜ |
| KVAL005 | 纸盒旋转90度 | ~300 | ⬜ |
| KVAL006 | 抓取/放置失败 | ~300 | ⬜ |

**前置条件**: K02 完全通过验收

### K04 — 三维参考轨迹生成与质量掩码

**重点关节**: Neck, RShoulder, RElbow, RWrist, LShoulder

**交付物**:
- 原始 3D 轨迹 (CSV/JSONL)
- 质量掩码 (每帧每关节)
- 人工复核表
- 骨长稳定性统计
- 速度/加速度/jerk 统计
- 重投影轨迹

### K05 — 统一评价工具

**评价维度**:
- 2D: MAE_px, RMSE_px, max error, normalized error
- 3D/2.5D: XY error, depth error, total 3D error, phase-height error
- 运动学: velocity, acceleration, jerk, trajectory length, curvature, bone length variation
- 分组: by joint, phase, speed, occlusion, confidence, video_id

### K06 — 主线方法接入与论文验证实验

**实验矩阵** (与主线通过冻结接口集成):
- 2D 误差 vs 3D reference projection
- 2.5D 误差 vs 3D reference (after coordinate alignment)
- 阶段高度模板验证
- 遮挡/快速运动/低置信度条件下的误差分析
- 质量优化前后对比

---

## 与主线任务的关系

| 主线任务 | Kinect 支线角色 |
|----------|----------------|
| T07C-B4 (轨迹优化) | 在 K06 阶段提供独立参考测量 |
| E001-E012 (RGB 视频) | KVAL 数据提供同任务结构的 RGB-D 对照 |
| LeRobot 数据集 | 不直接参与，仅通过交换 Schema 提供参考 |
| ACT/VLA 训练 | 不参与 |

**集成方式**: 仅通过 `data/interfaces/trajectory_exchange_schema.json` 冻结格式交换数据。

---

## 风险登记

| 风险 | 缓解措施 |
|------|----------|
| K01 右臂数据不可靠 | 新 KVAL 录制时优化手臂姿态；K01 仅用左臂/躯干作为参考 |
| 相机内参未知 | 从 MKV 文件提取实际标定 |
| Azure Kinect 不可用 | 使用 K01 离线数据完成工具开发；KVAL 录制推迟到设备可用 |
| K01 与主线 E001 不同次操作 | 仅做阶段统计对比；KVAL 数据与新的主线录制同步 |
