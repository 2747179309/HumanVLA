# T06A 验收标准：操作型视频规范与动作阶段标注工具

版本：v0.2.0  
日期：2026-07-13  
首个工具原型样本：`K01_reach_grasp_001` 的 RGB 彩色流

## 1. 范围

T06A 的后续执行范围是实现标注工具并用 K01 RGB 验证工具，不是大规模标注。本文档制定验收要求，本轮不运行脚本、不生成标签、不处理视频。

禁止事项：加载 Kinect 深度或骨架、修改原始 RGB、滤波、LeRobot 转换、模型训练，以及把自动建议声明为人工真值。

## 2. 固定规范

- 阶段 ID 固定为：`idle=0`、`reach=1`、`align=2`、`grasp=3`、`lift=4`、`transport=5`、`place=6`、`release=7`、`retract=8`、`occluded=90`、`failed_attempt=91`、`unknown=98`。
- 人工 `segments.jsonl` 是语义权威源；frame/text 文件是可追溯派生视图。
- 新阶段首次可观察帧归属新阶段；不强制三帧最小长度。
- 阶段可按真实任务跳过。逆序只允许失败重试等有 `failed_attempt` 或人工备注的情况。
- 同一录制会话不得跨 train/val/test。K01 使用 `split=unsplit`。

完整字段和处理规则见 `context/ACTION_PHASE_SCHEMA.md`。

## 3. 必须实现的脚本

| 脚本 | 验收功能 |
|---|---|
| `scripts/annotation/create_taxonomy.py` | 生成并验证固定阶段、手别、质量、任务和物体词表 |
| `scripts/annotation/prepare_rgb_manifest.py` | 只读扫描 RGB，建立源帧到 0 基逻辑帧映射 |
| `scripts/annotation/label_episodes.py` | 录入/修订 episode 边界及 episode 级字段 |
| `scripts/annotation/label_phases.py` | 录入人工阶段闭区间、双语文本和边界置信度 |
| `scripts/annotation/expand_frame_labels.py` | 从区间确定性展开 frame 和中英文文本文件 |
| `scripts/annotation/validate_labels.py` | 独立验证格式、语义约束、覆盖和数据隔离 |
| `scripts/annotation/render_labels.py` | 生成阶段叠加视频供人工复核 |

每个脚本必须支持 `--help`，使用 `logging`，包含非零退出码和清晰异常信息。不得用 phase ID 数值插值，不得默认伪造 FPS、时间戳、标签或人工复核状态。

## 4. 必须输出

| 输出 | 路径 |
|---|---|
| 受控词表 | `data/action_labels/taxonomy.yaml` |
| RGB manifest | `data/action_labels/manifests/<video_id>/source_frames.jsonl` |
| Episode 标签 | `data/action_labels/episodes/<video_id>/episodes.jsonl` |
| 人工阶段区间 | `data/action_labels/segments/<video_id>/segments.jsonl` |
| Frame 标签 | `data/action_labels/frames/<video_id>/frames.jsonl` |
| 双语文本视图 | `data/action_labels/text/<video_id>/text_zh.jsonl`、`text_en.jsonl` |
| 人工复核记录 | `data/action_labels/reviewed/<video_id>/review.csv` |
| 可视化 | `results/action_labels/<video_id>/phase_overlay.mp4` |
| 验证摘要 | `results/action_labels/<video_id>/validation_summary.json` |
| 人工复核摘要 | `results/action_labels/<video_id>/manual_review_summary.json` |
| 运行日志 | `logs/runs/T06A_ACTION_PHASE_LABELING.md` |

## 5. K01 数据隔离

- `frame_1` 至 `frame_240` 必须通过 manifest 映射为 `frame_index` 0 至 239。
- 只读取 K01 `color/` RGB 文件；不导入 `depth/`、`skeleton_2d.jsonl`、`skeleton_3d.jsonl` 或 Kinect 映射文件。
- FPS/时间戳必须来自可追溯元数据或显式命令参数，并记录来源；未知时工具必须停止，不能猜测。
- K01 原始文件哈希在前后保持不变，标签和结果写入新目录。

## 6. 自动验证

`validate_labels.py` 至少检查：

- manifest 的 `frame_index` 从 0 连续且源文件唯一；K01 为 240 帧。
- `episode_id` 格式正确，episode 闭区间合法、互不重叠并位于 manifest 范围内。
- 每个 episode 的 segment 连续覆盖、无重叠/空洞，ID/label 与词表一致。
- 标准阶段是允许跳过的单调子序列；只有带失败证据的重试允许回退。
- frame 文件逐帧完整且每个 subject 每帧最多一条；episode 外为 `episode_id=null` 和 `idle`。
- `active_hand`、`quality_status`、成功状态、物体和中英文文本字段符合 schema。
- frame/text 逐值可回溯到 segment，禁止 ID 插值或不可解释自动标签。
- `episode_success` 与失败段不做错误等价：最终成功的 episode 允许包含失败后重试。
- split 按 `split_group_id` 防泄漏；K01 为 `unsplit`。
- Kinect 路径未出现在运行输入或输出元数据中，原始 RGB 哈希未变化。

## 7. 可视化要求

- 输出视频与 RGB manifest 帧数、分辨率和已验证 FPS 一致，并能被 OpenCV/FFprobe 读取。
- 每帧显示 `frame_index`、`episode_id`、`phase_id/phase_label`、手别、物体和中文阶段文本。
- 12 个 phase 使用固定且可区分的颜色；episode 外 `idle` 使用灰色。
- 渲染只读取已保存标签，不得在渲染阶段修改标签。

## 8. 人工验收

- 初标者完成全部 episode 和阶段区间，复核者检查全部边界、异常、遮挡和失败段。
- K01 原型逐帧检查 overlay，确认 0/239 边界、阶段切换、双语语义和源帧映射。
- 工具输出阶段一致率、边界帧绝对差、未覆盖/重叠数；标签不一致或边界差大于 2 帧时人工裁决。
- review 文件保留初标值、复核值、最终值、人员、原因和版本，不能覆盖初标记录。

## 9. 验收清单

- [ ] 7 个脚本全部 `--help` 和 `py_compile` 通过。
- [ ] 所有规定输出真实存在，JSONL/CSV/YAML 可解析。
- [ ] K01 manifest 240 行，逻辑帧 0 至 239 连续。
- [ ] taxonomy 含固定 12 阶段且与 schema 一致。
- [ ] 至少一个由人工实际标注并复核的 K01 episode 通过独立验证。
- [ ] overlay 可读取且逐帧人工检查完成。
- [ ] 原始 RGB 哈希不变，未加载 Kinect 深度/骨架。
- [ ] 日志记录 Run ID、日期、环境、输入、commit、完整命令、参数、输出、统计、异常和论文可用性。

任一数据隔离违规、原始文件变化、未解决验证错误或把自动标签当人工真值，均不通过。通过后才能进入 T06B；不得自动开始 T06B、LeRobot 转换、滤波或训练。
