# Claude 对 Codex 工作的审查

## R1-R6 (2026-07-11~12)
T01✅ T02✅ T03✅ T04✅ T05A✅。详见历史。

## R7 (2026-07-14) — T07A 验收 + T07B 创建

### T07A 验收：通过

| 核查项 | 结果 |
|--------|------|
| jump_candidate_review.csv 12行×20列, 无Unnamed列 | ✅ |
| manual_label 仅 3 种合法值 | ✅ |
| normalization_artifact=1, occlusion_error=8, real_motion=3 | ✅ |
| 12 clip_path 有效 | ✅ |
| trajectory_summary.json 已同步人工裁决 | ✅ |
| raw trajectory/OpenPose/T06C 未修改 | ✅ |
| interpolated=false, filtered=false 全部帧 | ✅ |

### T07B 创建
- 合成遮挡实验：4 gap_length × 4 methods × 8 phases
- 真实修复：3 intervals (7 frames RWrist)
- occlusion_error 延期到 T07C
- D040-D042

## R7 (2026-07-13) — T06A 验收 (历史)

### 实际状态

Codex 仅完成了 **规范设计阶段**，未实现工具。Codex 报告明确声明："本轮仅执行文档读取、编辑和一致性检查；未运行标注代码，未处理K01，未创建实验结果。"

### 逐项检查

| # | 检查项 | 状态 | 说明 |
|---|--------|------|------|
| 1 | 7 个标注脚本 | ❌ | `scripts/annotation/` 仅含 `.gitkeep`，0 个 .py 文件 |
| 2 | MP4 + RGB 帧目录支持 | ❌ | 无脚本，无法验证 |
| 3 | 0 基 frame_index | ✅ | 规范 v0.2.0 明确要求 manifest 显式映射 |
| 4 | 单视频多 episode | ✅ | 规范定义了 episode 闭区间不重叠 |
| 5 | 中英文文本保留 | ✅ | 规范含 phase_text_zh/en + instruction_zh/en |
| 6 | 不自动猜测阶段 | ✅ | 规范："人工确认的阶段区间是权威标签，自动建议不能覆盖人工结论" |
| 7 | Validator 检测重叠/越界/非法标签/缺失边界/缺失 success | ❌ | `validate_labels.py` 不存在 |
| 8 | Overlay 显示 video_id/episode_id/frame_index/timestamp/phase_label | ❌ | `render_labels.py` 不存在 |
| 9 | JSONL 与 CSV 一致性 | ❌ | 无输出文件可比较 |
| 10 | 未修改 T05A/OpenPose/原始视频 | ✅ | Codex 报告确认未加载任何数据文件 |

### 规范质量评估

`context/ACTION_PHASE_SCHEMA.md` v0.2.0 质量良好：
- 12 类阶段词表完整 ✅
- Episode/segment/frame 三层字段清晰 ✅
- 边界规则具体可操作 ✅
- 数据集划分防泄漏（按 split_group_id）✅
- K01 标记 unsplit ✅
- 文本规范中英文独立 ✅

### T06A 验收结论：**规范通过，工具实现待执行**

T06A 规范设计阶段已完成且质量良好。7 个脚本的实现是下一步工作。标记为 `ACCEPTED (spec)`。
