# T07C-B4: Pre-Registered Experimental Hypotheses

## 冻结日期：2026-07-14

以下假设在 B4 代码运行前冻结。任何偏离需在 B5 中报告为 post-hoc analysis。

---

## H1: M1 相较 SG 显著降低 clean-region displacement

- **H0**: \(\text{CRD}_{M1} \geq \text{CRD}_{SG}\)
- **H1**: \(\text{CRD}_{M1} < \text{CRD}_{SG}\)
- **检验**: paired t-test, α=0.05, 96 test samples
- **定量预期**: M1 CRD 应 < 0.015 norm (SG 约 0.028)
- **可能推翻**: 如果 q_t 的 min 策略过于保守，大量 borderline 帧被误判为 low quality

---

## H2: M2 相较 M1 降低 acceleration 和 jerk error

- **H0**: \(\text{AccelRMSE}_{M2} \geq \text{AccelRMSE}_{M1}\)
- **H1**: \(\text{AccelRMSE}_{M2} < \text{AccelRMSE}_{M1}\)
- **检验**: paired t-test, α=0.05
- **定量预期**: acceleration RMSE 降低 ≥ 10%
- **可能推翻**: 如果 λ_a 过小，动态约束不够强

---

## H3: M3 相较 M2 降低 phase-boundary shift 和 real-motion attenuation

- **H0**: \(\text{PBS}_{M3} \geq \text{PBS}_{M2}\)
- **H1**: \(\text{PBS}_{M3} < \text{PBS}_{M2}\)
- **检验**: 独立 boundary benchmark (非 B2 普通窗口)
- **定量预期**: boundary shift 降低 ≥ 20%；real-motion attenuation 降低 ≥ 15%
- **可能推翻**: 如果阶段边界标记不准确，保护了错误的帧

---

## H4: M4 相较 M3 降低骨长波动和遮挡区间恢复误差

- **H0**: \(\text{BoneRMSE}_{M4} \geq \text{BoneRMSE}_{M3}\)
- **H1**: \(\text{BoneRMSE}_{M4} < \text{BoneRMSE}_{M3}\)
- **检验**: paired t-test, α=0.05
- **定量预期**: bone_length_error std 降低 ≥ 30%
- **可能推翻**: 如果 2D 骨骼投影长度本身变化大（3D 旋转效应），软约束效果有限

---

## H5: M4 在综合指标上优于所有 B3 基线

- **H0**: \(\text{Score}_{M4} \geq \min(\text{Score}_{SG}, \text{Score}_{KF-CV}, \text{Score}_{OE})\)
- **H1**: \(\text{Score}_{M4} < \text{Score}_{\text{best B3 baseline}}\)
- **Score**: \(0.4 \cdot \text{RMSE} + 0.2 \cdot \text{Jerk} + 0.2 \cdot \text{VelErr} + 0.2 \cdot \text{BoneErr}\)
- **检验**: 非劣效性检验，在综合得分上 M4 不低于最优传统基线
- **可能推翻**: 如果某传统基线在特定 corruption 类型上特别强，综合得分可能持平

---

## 独立 Boundary Benchmark 构建规则

B4 独立构建 boundary benchmark（B2 窗口不跨阶段）：

1. 从 E001 valid 帧中选择包含阶段边界的 16 帧窗口（边界前 8 帧 + 后 8 帧）
2. 边界类型：grasp→lift, lift→transport, transport→place, place→release, release→retract
3. 注入合成污染在 boundary ±4 帧范围
4. 评价指标：boundary position shift, velocity shift, phase action amplitude preservation（边界附近的运动幅度是否被平滑压低）
5. 此 benchmark 不参与 B2 普通排名

---

## 论文表达限制

- 所有结果仅限 E001 within-episode。不声称跨视频泛化。
- H1-H5 的结果仅对合成污染有效。真实 E001 异常区间的表现在 B5 中单独讨论。
- M1-M4 的超参数（λ_v, λ_a, γ, 骨骼约束权重）在 train 上调优，val 上选择，test 上报告一次。
