# Claude 对 Codex 工作的审查

## R1-R4 (2026-07-11~12) — T01-T03
见历史记录。T01✅ T02✅ T03✅。

## R5 (2026-07-12) — T04 最终验收

### 审查范围
- T04 自动关联：`associate_pose_to_tracks.py` + `validate_association.py`
- 人工复核：240 帧逐帧 CSV + 5 段骨架质量 CSV
- 输出：association JSONL (726 行), summary.json, visualization mp4
- 运行日志 + Codex 报告

### 一致性核对

| 数据源 | 记录数 | 关键数字 | 一致性 |
|--------|--------|---------|--------|
| CODEX_REPORT | — | 237 pass / 3 fail, 0 identity switch | — |
| T04_review.csv | 240 行 | 237 pass / 3 fail (43/44/45) | ✅ |
| manual_review_summary.json | — | identity_correct=238/238, pose_correct=235/238 | ✅ |
| summary.json | — | matched=714, unmatched_pose=8, ambiguous=3, phantom=1 | ✅ |
| Run log | — | 同上, SHA-256 全部匹配 | ✅ |

**Codex 报告与真实输出一致。** 无编造。

### 逐项判断

#### P001/P002/P003 身份关联：✅ 可靠
- 238 个可复核帧全部 `subject_id_correct=yes`
- **0 次身份交换**
- 帧 0-1 无 DeepSORT confirmed track → unmatched_pose，处理正确

#### 43-45 帧：✅ 必须排除
- 人工判定：identity_mix + 跨人物手臂连接 (P003→P001)
- `pose_assignment_correct=no`，`reviewer_decision=fail`
- 额外 ambiguous_pose 不对应真人
- 帧 46 恢复检查通过
- **规则：标记为无效，不得进入平滑或训练。禁止用卡尔曼滤波修复。**

#### 15-19 和 54-61 帧：✅ 定位误差，非身份错误
- `subject_id_correct=yes`，`pose_assignment_correct=yes`
- 问题：P001 持杯手臂关键点未完全贴合真实手臂
- 性质：**OpenPose 关键点定位误差**（moderate），非身份关联错误
- **规则：保留原始结果。后续可在骨架质量实验中统计误差，滤波结果另存。**

#### 188/207/208 帧：✅ 异常处理正确
- 188：phantom_pose 正确排除，主人物关联正确
- 207/208：unmatched_pose 正确保持不绑定，背景人物在范围外
- `anomaly_handling_correct=yes` 全部通过

### T04 验收结论

**T04 有条件通过。** 

条件（已由人工复核确认并写入 D023/D024）：
1. 帧 43-45 整体标记为无效，排除出下游平滑和训练
2. 帧 15-19、54-61 为定位误差，保留原始，滤波结果另存
3. 帧 188 phantom 排除，207-208 保持 unmatched
4. 原始文件（关联 JSONL、OpenPose JSON、视频）均未被修改

### 问题追踪更新
- I10 (OpenPose 备选): ✅ 不再需要 (T03 构建成功)
- I12 (yolov8n.pt 位置): ⬜ 仍待处理
- I2/I3/I4: ⬜ 延后到标注阶段
