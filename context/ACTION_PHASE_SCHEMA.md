# 操作型人类视频动作阶段标注规范

版本：v0.2.0  
日期：2026-07-13  
适用范围：HumanVideo2VLA 操作型 RGB 视频的 episode、动作阶段和双语文本标注

## 1. 定位与数据边界

- 适用数据为单人操作、固定机位，手、目标物体和主要上肢可见，每段视频包含一个或多个完整 episode。
- 所有逻辑帧使用从 0 开始的 `frame_index`。源文件帧号必须通过 manifest 显式映射，禁止从文件名直接假定逻辑帧号。
- 原始 RGB、原始骨架和人工标签分别保存，原始输入只读。
- 人工确认的阶段区间是语义阶段权威标签。自动建议只能作为候选，不能覆盖人工结论。
- `three-people-walking` 只用于 MOT、姿态关联和质量掩码回归，不进入操作训练主样本。
- K01 仅使用 RGB 彩色流。深度和 Kinect 骨架不加载、不关联，仅保留给后续独立评价。
- 后续必须补充普通手机或 RGB 相机数据，才能评价低成本场景的适用性。

多人协同、第一人称、移动机位和纯导航数据不在本规范范围内，需另立协议。

## 2. Episode 定义与字段

### 2.1 边界

一个 episode 是操作者为同一任务目标而连续作用于目标物体的一段视频。

- 起点：从可见证据判断，操作手首次出现明确、持续的目标导向运动；不得使用 RGB 无法可靠测量的“30 cm”距离或视线方向作为硬阈值。
- 终点：释放后操作手完成收回，或操作者明确终止/放弃任务。若视频在收回前结束，保留 episode，但标记质量和成功状态。
- 同一目标的短暂失败后立即重试可保留在同一 episode；放弃后重新开始的新尝试建立新 episode。
- Episode 区间为闭区间 `[start_frame, end_frame]`，不得重叠。

### 2.2 Episode 级字段

| 字段 | 类型 | 必需 | 约束或说明 |
|---|---|---|---|
| `video_id` | string | 是 | 视频唯一标识 |
| `episode_id` | string | 是 | `<video_id>_E0001`，同视频内连续编号 |
| `subject_id` | string | 是 | 人工确认的全局操作者编号 |
| `source_type` | string | 是 | `kinect_rgb` / `phone_rgb` / `rgb_camera` |
| `start_frame` | integer | 是 | 0 基，含起点 |
| `end_frame` | integer | 是 | 0 基，含终点且不小于起点 |
| `start_timestamp_sec` | number | 是 | 由已验证 FPS/时间戳计算 |
| `end_timestamp_sec` | number | 是 | 由已验证 FPS/时间戳计算 |
| `task_type` | string | 是 | 受控词表任务类型 |
| `object_id` | string | 是 | 当前视频内可追溯的物体标识 |
| `object_category` | string | 是 | 受控词表物体类别 |
| `active_hand_summary` | string | 是 | `left` / `right` / `both` / `mixed` / `na` |
| `instruction_zh` | string | 是 | episode 级中文任务指令 |
| `instruction_en` | string | 是 | 与中文语义一致的英文任务指令 |
| `episode_success` | boolean | 是 | 是否完成预定任务 |
| `failure_reason` | string/null | 是 | 成功时为 `null`，失败时说明原因 |
| `num_phase_segments` | integer | 是 | 人工阶段区间数量 |
| `annotation_valid` | boolean | 是 | episode 标注是否可用 |
| `quality_status` | string | 是 | 见第 6 节 |
| `split` | string | 是 | `train` / `val` / `test` / `unsplit` |
| `split_group_id` | string | 是 | 同一录制会话的防泄漏分组 |
| `annotator_id` | string | 是 | 初标人员标识 |
| `reviewer_id` | string/null | 是 | 未复核时为 `null` |
| `annotation_version` | string | 是 | 语义标注版本 |
| `notes` | string | 否 | 边界、失败、遮挡等补充说明 |

## 3. 动作阶段词表

### 3.1 固定阶段

| phase_id | phase_label | 中文 | 定义 |
|---|---|---|---|
| 0 | `idle` | 空闲 | episode 外或 episode 内无目标导向操作 |
| 1 | `reach` | 伸手 | 操作手向目标物体移动，尚未接触 |
| 2 | `align` | 对准 | 接触前在物体附近调整手掌或手指姿态 |
| 3 | `grasp` | 抓取 | 从首次接触到形成稳定抓握 |
| 4 | `lift` | 举起 | 物体开始脱离支撑面并上升 |
| 5 | `transport` | 运输 | 稳定持物向目标位置移动 |
| 6 | `place` | 放置 | 物体接近并接触目标支撑位置 |
| 7 | `release` | 释放 | 抓握开始解除直到手与物体脱离 |
| 8 | `retract` | 收回 | 手离开物体并返回休息/下一准备位置 |
| 90 | `occluded` | 遮挡 | 遮挡导致无法可靠判断语义阶段 |
| 91 | `failed_attempt` | 失败尝试 | 可观察到某次尝试失败、滑脱或中断 |
| 98 | `unknown` | 未知 | 非遮挡原因导致语义无法确定 |

标准顺序为 `reach → align → grasp → lift → transport → place → release → retract`。可按真实任务跳过不发生的阶段，禁止为满足完整链条而补造标签。例如滑动可跳过 `lift`，原地操作可跳过 `transport`。

### 3.2 阶段区间字段

人工标注的权威记录是阶段区间，每个连续区间一条：

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `video_id` | string | 是 | |
| `episode_id` | string | 是 | |
| `segment_id` | string | 是 | `<episode_id>_S001` |
| `start_frame` | integer | 是 | 0 基闭区间起点 |
| `end_frame` | integer | 是 | 0 基闭区间终点 |
| `phase_id` | integer | 是 | 固定词表 ID |
| `phase_label` | string | 是 | 必须与 ID 一致 |
| `phase_text_zh` | string | 是 | 当前阶段中文描述 |
| `phase_text_en` | string | 是 | 当前阶段英文描述 |
| `object_id` | string/null | 是 | 无交互对象时为 `null` |
| `active_hand` | string | 是 | `left` / `right` / `both` / `na` |
| `boundary_confidence` | string | 是 | `high` / `medium` / `low` |
| `annotation_valid` | boolean | 是 | |
| `quality_status` | string | 是 | |
| `annotator_id` | string | 是 | |
| `reviewer_id` | string/null | 是 | |
| `annotation_version` | string | 是 | |
| `notes` | string | 否 | |

### 3.3 边界规则

1. 新阶段的 `start_frame` 是首次可观察到该阶段定义条件的帧；前一阶段在 `start_frame - 1` 结束。边界帧归属新阶段。
2. `align→grasp` 以首次可见接触为 `grasp` 起点；`grasp→lift` 以物体首次离开支撑面为 `lift` 起点。
3. `lift→transport` 以主要运动从抬升转为向目标位置移动为界；无法分辨时降低 `boundary_confidence`，不得用固定像素速度编造边界。
4. `transport→place` 以物体开始进入最终放置过程为界；`place→release` 以抓握开始解除为界；`release→retract` 以手完全脱离并开始远离为界。
5. 阶段允许只有 1 至 2 帧。不得仅因持续时间短而合并真实可见的 `grasp`、`release` 等阶段；不确定时使用低边界置信度、`unknown` 或 `occluded` 并写明原因。
6. 相邻区间必须连续且不重叠。真实跳过的阶段不产生区间；失败重试可使顺序回退，但必须由 `failed_attempt` 区间或备注说明。

## 4. Frame 级字段

阶段区间经确定性展开后，每个逻辑帧、每个操作者最多一条记录：

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `video_id` | string | 是 | |
| `episode_id` | string/null | 是 | episode 外使用 JSON `null`，禁止字符串 `"none"` |
| `frame_index` | integer | 是 | 从 0 连续编号 |
| `timestamp_sec` | number | 是 | 必须来自已验证 FPS/时间戳 |
| `subject_id` | string | 是 | |
| `phase_id` | integer | 是 | episode 外为 0 (`idle`) |
| `phase_label` | string | 是 | 与 ID 一致 |
| `phase_text_zh` | string | 是 | 当前阶段中文语义 |
| `phase_text_en` | string | 是 | 当前阶段英文语义 |
| `object_id` | string/null | 是 | |
| `active_hand` | string | 是 | `left` / `right` / `both` / `na` |
| `episode_success` | boolean/null | 是 | episode 外为 `null` |
| `annotation_valid` | boolean | 是 | 人工语义标签是否可靠 |
| `quality_status` | string | 是 | |
| `source_segment_id` | string/null | 是 | 从哪个人工区间展开 |
| `annotation_version` | string | 是 | |
| `notes` | string | 否 | |

不得对 `phase_id` 做数值插值。逐帧标签只能由人工确认的闭区间展开。

## 5. 中文和英文文本

- Episode 文本描述任务目标：中文 `instruction_zh` 与英文 `instruction_en` 必须语义一致。
- Frame/segment 文本描述当前可见动作：`phase_text_zh` 与 `phase_text_en` 必须随阶段变化，允许同一区间复用。
- 中文建议为“操作手 + 动作 + 可见物体”，英文建议为祈使式短语；物体属性只能来自可见证据。
- 不确定属性使用通用名称，不因属性不确定直接判整帧无效；将不确定性写入 `notes`。
- `occluded`、`failed_attempt` 和 `unknown` 必须明确表达对应语义，不得复用正常阶段文本掩盖异常。

## 6. 成功、质量与特殊场景

`quality_status` 固定为 `full_valid`、`partial_occlusion`、`heavy_occlusion`、`ambiguous`、`out_of_scope`。

- 局部遮挡但仍可可靠判断阶段：保留真实阶段，设 `partial_occlusion`。
- 遮挡使阶段不可判断：使用 `occluded`，`annotation_valid=false`；不得依赖未来帧强行猜测。
- 非遮挡但语义不清：使用 `unknown`，通常 `annotation_valid=false`。
- 失败动作：失败区间使用 `failed_attempt`，在备注记录目标阶段；之后可重试。`episode_success` 只表示 episode 最终结果，不要求出现 `failed_attempt` 就必然失败。
- 他人短暂经过且不遮挡、不参与操作：保持操作者标签并记录范围。
- 他人遮挡操作者：按遮挡规则处理。若他人参与操作或无法唯一确定操作者，则结束/拆分 episode，受影响区间设 `out_of_scope` 或 `annotation_valid=false`，不得当作单人样本。
- Episode 中换手时逐帧更新 `active_hand`；双手共同作用时为 `both`，episode 汇总为 `mixed` 或 `both`。

## 7. 数据集划分原则

- 划分单位是 `split_group_id`，默认对应一次录制会话；同一源视频的帧和 episode 不得跨 train/val/test。
- 数据量允许时，测试集优先与训练集 subject-disjoint；至少不得把同一次录制的相邻片段分到不同集合。
- 在分组约束下平衡 `task_type`、`object_category`、操作者和成功/失败状态。建议目标比例为 60/20/20，实际比例、随机种子和分组清单必须保存。
- K01 是单次受控录制，只标记 `split=unsplit`，用于规范和工具原型验证，不用于宣称 train/val/test 性能。
- 后续普通手机/RGB 相机数据必须以独立录制会话进入划分，测试低成本来源的跨设备适用性。

## 8. 文件与目录

```text
data/action_labels/
├── taxonomy.yaml
├── manifests/<video_id>/source_frames.jsonl
├── episodes/<video_id>/episodes.jsonl
├── segments/<video_id>/segments.jsonl
├── frames/<video_id>/frames.jsonl
├── text/<video_id>/text_zh.jsonl
├── text/<video_id>/text_en.jsonl
└── reviewed/<video_id>/review.csv
data/splits/action_phase_split.json
results/action_labels/<video_id>/phase_overlay.mp4
results/action_labels/<video_id>/validation_summary.json
results/action_labels/<video_id>/manual_review_summary.json
logs/runs/T06A_ACTION_PHASE_LABELING.md
```

`source_frames.jsonl` 至少保存 `frame_index`、源文件名、源帧号、时间戳和已验证 FPS 来源。K01 的 `frame_1` 至 `frame_240` 映射到逻辑帧 0 至 239，但时间戳必须等 FPS 元数据核实后生成，禁止猜测。

## 9. T06A 后续实现范围

Codex 后续实现以下脚本，本轮规范制定不运行它们：

1. `create_taxonomy.py`：生成并校验固定词表。
2. `prepare_rgb_manifest.py`：只读扫描 RGB 帧并建立 0 基映射。
3. `label_episodes.py`：录入 episode 边界和元数据。
4. `label_phases.py`：录入人工阶段区间及双语文本。
5. `expand_frame_labels.py`：将已确认区间确定性展开为 frame 标签和文本视图。
6. `validate_labels.py`：验证格式、覆盖、边界、词表、数据隔离和划分防泄漏。
7. `render_labels.py`：生成逐帧语义叠加视频。

所有脚本必须支持 `--help`、logging 和基本异常处理。工具不得加载 Kinect 深度/骨架，不得把自动推断写成人工真值。

## 10. 人工验收

1. 初标者逐 episode 标注边界、阶段区间、物体、手别、成功状态和双语文本。
2. 复核者检查全部 episode/phase 边界，以及全部异常、遮挡和失败区间；K01 原型应逐帧查看叠加视频。
3. 验收程序报告阶段一致率、边界帧绝对差、未覆盖/重叠帧和枚举错误。边界差大于 2 帧或阶段标签不一致必须裁决，不能自动取平均。
4. 裁决后的 review 文件记录原值、最终值、复核者、原因和版本；不得覆盖初标文件。
5. 人工确认原始 RGB 未修改、Kinect 输入未加载、所有输出真实存在后，T06A 才能进入最终验收。

## 11. 与骨架数据的关系

动作阶段标注独立于 OpenPose/Kinect 骨架，以 `(video_id, frame_index, subject_id)` 连接。动作语义质量与骨架关键点质量是两个字段体系：骨架无效不自动改变人工语义标签，反之亦然。当前不做滤波、Kinect 对齐、LeRobot 转换或模型训练。
