# T07C-A 验收标准：Frame-Level Corruption Mask and Quality Audit

版本：v0.1.0
日期：2026-07-14
前置：T07B（短缺口恢复，已通过）
输入：jump_candidate_review.csv + T06C quality_mask + T07B repair_summary

---

## 一、覆盖的已知事件

| 来源 | 数量 | 涉及帧/关节 |
|------|------|-----------|
| occlusion_error 跳变 | 8 | JUMP_002/003/005/007/008/009/010/011 |
| normalization_artifact | 1 | JUMP_001 (frame 54-55 RElbow) |
| low_quality RElbow | 2 | frame 64-65 (T06C) |
| boundary_continuity_warning | 4 | frame 182-185 (T07B) |
| real_motion | 3 | JUMP_004/006/012 → corruption_type=real_motion, action=keep |

---

## 二、corruption_type 判定规则

| 事件来源 | corruption_type |
|----------|----------------|
| JUMP with manual_label=occlusion_error | `occlusion_error` — 需人工判断 from/to 哪端错误 |
| JUMP with manual_label=normalization_artifact | `normalization_artifact` — 两端观测均 valid |
| T06C low_quality RElbow (64-65) | `low_quality_observation` |
| T07B boundary_continuity_warning (182-185) | `boundary_continuity_warning` |
| JUMP with manual_label=real_motion | `real_motion` |

---

## 三、逐帧 corruption mask 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `video_id` | string | `pick_place_pilot_v1_E001` |
| `frame_index` | integer | 0-344 |
| `joint_name` | string | `RElbow` / `RWrist` / `RShoulder` / `Neck` |
| `source_event_id` | string | `JUMP_XXX` / `T06C_LOW_QUALITY` / `T07B_BOUNDARY` / `none` |
| `raw_observation_status` | string | T06C 原始观测状态 |
| `corruption_type` | string | 7 种合法值 |
| `observation_valid` | boolean | 原始观测是否可信 |
| `downstream_valid` | boolean | 下游是否可使用 |
| `manual_label` | string | 来自 jump_candidate_review |
| `manual_confidence` | string | `high` / `medium` / `low` |
| `manual_reason` | string | 人工判断依据 |
| `proposed_action` | string | `keep` / `mask` / `downweight` / `defer` |
| `phase_label` | string | 动作阶段 |

---

## 四、验收 checklist

### 4.1 覆盖完整性
- [ ] 12 个 JUMP 事件全部有对应记录
- [ ] frame 64-65 RElbow low_quality 已记录
- [ ] frame 182-185 boundary_continuity_warning 已记录
- [ ] 3 个 real_motion 事件 → corruption_type=real_motion, action=keep

### 4.2 判定正确性
- [ ] 每个 occlusion_error 事件的 from/to 帧有逐帧判定（非整段删除）
- [ ] normalization_artifact (JUMP_001) 两端均 valid
- [ ] 无跨帧批量标记（每个 frame_index × joint_name 独立判定）

### 4.3 输出文件
- [ ] `corruption_candidate_review.csv`：所有受影响帧的逐行记录
- [ ] `corruption_candidate_review.mp4`：H.264 审核视频
- [ ] `corruption_candidate_clips/`：每个事件的短片段
- [ ] `frame_joint_corruption_mask.jsonl`：完整掩码，覆盖 345 帧 × 4 关节 = 1380 行（默认 corruption_type=valid）

### 4.4 数据隔离
- [ ] raw trajectory 未修改
- [ ] repaired trajectory 未修改
- [ ] T06C/T07A/T07B 输入文件哈希不变

### 4.5 运行日志
- [ ] `logs/runs/T07C_A_CORRUPTION_MASK.md`

---

## 五、不通过条件

1. occlusion_error 事件被整段删除而非逐帧判定
2. real_motion 被标记为错误
3. 掩码覆盖了任何原始文件
4. 执行了滤波或插值
5. corruption_type 使用了非法值

---

## 六、通过条件

所有已知事件逐帧覆盖 + corruption_type 判定正确 + 原始文件未修改。
