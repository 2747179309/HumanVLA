# T06C 验收标准：E001 操作视频人体感知流水线适配与验证

版本：v0.1.0
创建日期：2026-07-13
前置任务：T06B（E001 动作标注已完成）、T02-T05A（感知流水线已在 three-people-walking 上验证）
处理视频：`data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4`
视频参数：1280×720, 30 FPS, 345 帧 (0-344)

---

## 一、任务定位

将已在 three-people-walking 上验证的 DeepSORT + OpenPose + 关联流水线适配到单人上半身操作场景。关键适配点：单人场景简化了身份关联；下半身不可见需要调整质量掩码规则。

---

## 二、核心关节定义（仅上半身）

| 关节 | BODY_25 ID | 角色 |
|------|-----------|------|
| Neck | 1 | 核心 — 必须统计 |
| RShoulder | 2 | 核心 — 必须统计 |
| RElbow | 3 | 核心 — 必须统计 |
| RWrist | 4 | 核心 — 必须统计 |
| MidHip | 8 | 辅助 — 统计但不作硬性有效条件 |
| 其余 20 关节 | — | 保留完整结构，正常统计 |

---

## 三、验收 checklist

### 3.1 DeepSORT 跟踪
- [ ] 345 帧全部处理
- [ ] 主操作者 track_id 唯一且连续（无身份切换）
- [ ] 输出 tracked.mp4 + tracks_raw.jsonl + gt.txt + metadata.json
- [ ] track_id 确认映射到 P001

### 3.2 OpenPose BODY_25
- [ ] 345 帧全部输出 JSON
- [ ] 每个 pose_keypoints_2d 长度 75
- [ ] 渲染视频 rendered.mp4 可正常播放
- [ ] 原始 JSON 未被修改

### 3.3 骨架-轨迹关联
- [ ] 每帧最多一个骨架关联到 P001
- [ ] 匹配方法：Hungarian 一对一（单人场景退化为直接匹配）
- [ ] 输出关联 JSONL：含 frame_index, track_id, subject_id=P001, keypoints, match_status
- [ ] 关联 JSONL 行数合理（预期 ~345，对应每帧一副骨架）

### 3.4 质量掩码

| 规则 | 说明 |
|------|------|
| 膝/踝/脚不可见 | 对应关节标记 `missing`，不传播到整帧 |
| Neck/RShoulder/RElbow/RWrist 缺失 | 对应关节标记 `missing`，帧仍为 `frame_valid=true` 除非全部四个核心关节同时缺失 |
| MidHip 不可见 | 标记 `missing`，不作为硬性无效条件 |
| 置信度 < 0.3 | 对应关节标记 `low_quality` |
| 置信度 > 1 | 保留原始值，同 D022 规则 |

### 3.5 骨架与动作阶段合并
- [ ] 按 `frame_index` 精确合并（0-344）
- [ ] 合并后每帧含：frame_index, phase_id, phase_label, subject_id, keypoints, quality_mask
- [ ] 动作阶段字段来自 T06B `frames.jsonl`
- [ ] 骨架字段来自 T06C 关联输出

### 3.6 核心关节统计
- [ ] 输出 `joint_stats.json`，含：
  - Neck/RShoulder/RElbow/RWrist 逐帧置信度
  - 四个核心关节的有效率（conf > 0 的帧占比）
  - 四个核心关节的均值 ± 标准差
- [ ] 低质量帧列表（任何核心关节 conf < 0.3 或 missing）
- [ ] 身份不确定帧列表（match_status ≠ matched）
- [ ] 缺失帧列表（frame_valid=false）

### 3.7 可视化
- [ ] 合并叠加视频含：人体骨架 + P001 标签 + phase_label（中英文）+ frame_index
- [ ] H.264, 345 帧, 30 FPS, 1280×720
- [ ] 可正常播放
- [ ] 动作阶段边界附近（phase 切换 ±5 帧）进行人工抽查

### 3.8 数据隔离
- [ ] 原始视频未被修改
- [ ] T06B frames.jsonl 和 segments 未被修改
- [ ] OpenPose 原始 JSON 未被覆盖

### 3.9 运行日志
- [ ] `logs/runs/T06C_E001_POSE_PIPELINE.md` 含完整命令、参数、统计、异常

---

## 四、逐帧记录要求

345 帧均有统一记录。每帧记录形式（合并后）：
```json
{
  "frame_index": 0,
  "timestamp_sec": 0.0,
  "video_id": "pick_place_pilot_v1_E001",
  "subject_id": "P001",
  "phase_id": 0,
  "phase_label": "idle",
  "keypoints": [[x0,y0,c0], ..., [x24,y24,c24]],
  "confidence_raw": [c0, ..., c24],
  "quality_mask": ["valid", ..., "missing"],
  "frame_valid": true,
  "joint_valid": [true, ..., false],
  "match_status": "matched"
}
```

---

## 五、不通过条件

1. DeepSORT 出现 P001 身份切换
2. 任何帧 P001 被关联超过一副骨架
3. 膝/踝/脚不可见导致整帧被标记 invalid
4. 核心关节（Neck/RShoulder/RElbow/RWrist）缺失率 > 30%
5. frames.jsonl 的 phase_label 被修改
6. 原始视频被修改
7. 处理了 E002-E012

---

## 六、通过条件

所有验收 checklist 标记为 [x] + 345 帧完整覆盖 + P001 身份唯一 + 核心关节统计完整 + 可视化可播放 + 原始文件未被修改。
