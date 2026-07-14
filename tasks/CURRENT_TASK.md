# T07C-B3 → ACCEPTED | T07C-B4 — 质量感知阶段保持骨骼轨迹优化

## B3 验收结论：通过

47 候选在 validation 评估，test 运行一次。SG 在 idle 低噪声时反比 corrupted input 差（CRD=0.028 → clean 数据被过度平滑）。KF-CW 仅比 KF-CV 略好（<1%）——单一 confidence 不够。详见科学解读。

## B4 任务

实现 M0→M4 递进消融：质量权重 → 动态约束 → 阶段边界保护 → 骨骼约束。每模块针对 B3 暴露的具体失败模式。独立构建 boundary benchmark。

## 本轮产出

| 文件 | 说明 |
|------|------|
| `docs/learning/T07C_B3_SCIENTIFIC_INTERPRETATION.md` | 10 项深入分析 |
| `docs/learning/T07C_B3_ORAL_EXAM.md` | 10 个检查问题 |
| `docs/learning/T07C_B4_METHOD_THEORY.md` | M1-M4 理论+与B3的关联 |
| `docs/learning/T07C_B4_EXPERIMENT_HYPOTHESES.md` | H1-H5 冻结假设+boundary benchmark |
| `docs/learning/T07C_B4_IMPLEMENTATION_PLAN.md` | 代码结构+超参数 |
| `tasks/T07C_B4_ACCEPTANCE_CRITERIA.md` | 验收标准 |

## 状态

B3: ACCEPTED. B4: 本轮只设计和教学，不运行算法。
