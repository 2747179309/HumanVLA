# T06B 验收标准：操作视频试采集数据验证与动作阶段人工标注

版本：v0.1.0
创建日期：2026-07-13
前置任务：T06A（规范已通过，工具已实现）
处理视频：`data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4`

---

## 一、任务定位

对首段成功 pick-and-place 视频完成 T06A 规范的端到端标注验证。这是整个项目第一段被完整标注的操作视频，目标是以此验证标注规范、工具和流程的可用性。

---

## 二、视频信息

| 字段 | 值 |
|------|-----|
| video_id | `pick_place_pilot_v1_E001` |
| 源文件 | `P01_BOX01_R_A_B_E001_S.mp4` |
| 操作者 | P01 |
| 物体 | BOX01（纸盒 12×10×4 cm） |
| 操作手 | 右手 |
| 路径 | A → B（57 cm） |
| 预期结果 | 成功 |
| 场景 | 桌面高度 75 cm，固定机位 |

---

## 三、前置条件

| 编号 | 条件 | 验证 |
|------|------|------|
| P1 | T06A 7 个脚本已实现 | `scripts/annotation/*.py` 全部 `--help` + `py_compile` 通过 |
| P2 | `taxonomy.yaml` 已生成 | `data/action_labels/taxonomy.yaml` 存在，12 phase + 受控词表完整 |
| P3 | E001 视频可正常读取 | OpenCV `VideoCapture.isOpened()=true` |
| P4 | E001 元数据已登记 | SHA-256, FPS, 分辨率, 帧数, 时长 |

---

## 四、标注要求

### 4.1 Episode 级

- `video_id`: `pick_place_pilot_v1_E001`
- `episode_id`: `pick_place_pilot_v1_E001_E0001`
- `subject_id`: `P01`
- `source_type`: `phone_rgb`（根据实际拍摄设备调整）
- `task_type`: `pick_and_place`
- `object_id`: `BOX01`
- `object_category`: `box`
- `active_hand_summary`: `right`
- `split`: `unsplit`（单次录制，仅验证工具）

### 4.2 动作阶段标注（segment 级）

预期阶段序列（以实际观察为准）：
```
idle → reach → align → grasp → lift → transport → place → release → retract → idle
```

每个 segment 必须填写：
- `segment_id`（E0001_S001 起编号）
- `start_frame` / `end_frame`（0 基闭区间）
- `phase_id` / `phase_label`（词表内）
- `phase_text_zh` / `phase_text_en`（语义准确的当前动作描述）
- `boundary_confidence`（high/medium/low）
- `active_hand`（逐段记录）

### 4.3 Frame 级

- 从 segments 确定性展开，不对 phase_id 插值
- 每帧 `phase_id` 来自所在 segment
- `episode_id` 在 episode 区间内非 null，区间外为 JSON null
- `quality_status` 按 T06A 规范第 6 节填写

### 4.4 双语文本

- Episode 级：`instruction_zh` / `instruction_en`（任务目标描述）
- Frame 级：`phase_text_zh` / `phase_text_en`（当前动作描述）
- 物体属性仅基于可见证据

---

## 五、验收 checklist

### 5.1 工具和词表
- [ ] 7 个脚本全部 `--help` + `py_compile` 通过
- [ ] `taxonomy.yaml` 含 12 phase_id + object_categories + task_types
- [ ] `source_frames.jsonl` 含 frame_index 0..N-1 连续映射

### 5.2 Episode 标注
- [ ] 至少 1 个 episode，`episode_id` 格式正确
- [ ] `start_frame < end_frame`
- [ ] `episode_success=true`（本段为成功操作）
- [ ] `instruction_zh` 和 `instruction_en` 非空且语义一致

### 5.3 Segment 标注
- [ ] 相邻 segment 连续不重叠：`end_frame_i + 1 == start_frame_{i+1}`
- [ ] `phase_id` 序列语义合理（不含无 `failed_attempt` 解释的逆序）
- [ ] 每个 segment 的 `phase_text_zh/en` 非空
- [ ] `boundary_confidence` 全部填写

### 5.4 Frame 标注
- [ ] `frames.jsonl` 行数 = 视频总帧数
- [ ] `frame_index` 连续 0..N-1
- [ ] `phase_id` 全部在 12 种合法值中
- [ ] `episode_id` 在非 episode 帧为 JSON null（非字符串 "none"）

### 5.5 文本
- [ ] `text_zh.jsonl` 和 `text_en.jsonl` 行数与 `frames.jsonl` 一致
- [ ] 中英文文本不空且语义对应
- [ ] `occluded`/`failed_attempt`/`unknown` 帧有明确的异常语义表述

### 5.6 验证器
- [ ] `validate_labels.py` 报告 0 个错误
- [ ] 无阶段重叠
- [ ] 无阶段越界（frame_index 超出 segment 范围）
- [ ] 无非法标签
- [ ] 无缺失 episode start/end
- [ ] 无缺失 success 状态

### 5.7 可视化
- [ ] overlay 视频可正常播放，H.264
- [ ] 叠加显示：video_id, episode_id, frame_index, timestamp, phase_label（中英文）
- [ ] 12 种颜色编码区分不同 phase_id
- [ ] 非 episode 帧有灰色半透明标记

### 5.8 数据隔离
- [ ] 原始 MP4 未被修改
- [ ] T05A/OpenPose 文件未被修改
- [ ] 标注输出写入 `data/action_labels/` 和 `results/action_labels/`

### 5.9 运行日志
- [ ] `logs/runs/T06B_ACTION_PHASE_LABELING.md` 含完整命令、参数、统计

---

## 六、不通过条件

1. 标注验证器报告未解决的错误
2. frames.jsonl 行数 ≠ 视频总帧数
3. segment 存在重叠或间隙
4. phase_id 使用非法值
5. episode 缺少 instruction_zh/en
6. 原始视频被修改
7. 标注工具脚本在标注前未通过 `py_compile`

---

## 七、通过条件

所有验收 checklist 标记为 [x] + 验证器 0 错误 + 可视化可播放 + 原始文件未被修改。

通过后：T06B → COMPLETED。可讨论下一步（继续标注剩余视频、LeRobot 转换、或骨架提取）。
