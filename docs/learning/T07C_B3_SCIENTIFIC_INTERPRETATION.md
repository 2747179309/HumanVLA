# T07C-B3: Scientific Interpretation of Baseline Results

## 0. 验收确认

| 检查项 | 结果 |
|--------|------|
| 47 候选全部在 validation 评估 | ✅ |
| Test 仅在参数冻结后运行一次 | ✅ |
| 0 ground truth 泄漏 | ✅ |
| 5 方法符合理论定义 | ✅ |
| KF-CW 未使用 corruption mask | ✅ (仅用 OpenPose confidence) |
| 所有指标完整分组 | ✅ |
| phase-boundary shift = not_applicable | ✅ |
| 输入哈希 + 复现检查 | ✅ |

**B3 验收通过。**

---

## 1. 各方法在四类污染中的表现

基于 test summary 的 per-corruption 聚合：

### Gaussian Noise
SG 在高噪声 (σ=0.06 shoulder width ≈ 10 px) 时 RMSE 最低。但在低噪声时，SG 的 RMSE **高于** corrupted input——因为固定窗口平滑将 clean idle 轨迹也偏移了。这是 SG 的经典问题：对好数据的"过度医疗"。

### Burst Jump
所有方法都在 burst jump 上表现最差（RMSE 最高）。1-3 帧的突发位移很难在不影响周围帧的情况下修正。Kalman 在 jump 上的表现不如 SG，因为 Kalman 的运动模型假设平滑变化——突发跳变违反了这个假设。

### Continuous Drift
OE 在 drift 上表现最好。Drift 的渐进性质允许自适应方法逐步追踪偏差。Kalman 也表现良好——模型能从邻帧的速度推断漂移方向。

### Short Missing
这是最难的类型——观测完全缺失，仅靠上下文推断。Kalman 的预测能力在此处体现优势：CV 模型可以"滑过"缺口。SG 无法处理缺失帧（需要连续数据）。

---

## 2. 严重度与排名变化

| 严重度 | 最优方法 | SG vs Kalman |
|--------|---------|-------------|
| Low | KF-CV ≈ KF-CW | SG 在低噪声时 clean displacement 较高 |
| Medium | SG ≈ OE | SG 的去噪优势开始显现 |
| High | SG | SG 的大窗口在强噪声下更有效 |

**关键发现**：没有一种方法在所有严重度上都是最优的。这验证了 B1 的理论预测——固定策略无法同时处理不同强度的噪声。

---

## 3. RElbow vs RWrist

两个关节的 RMSE 排名一致，但绝对值不同：
- RWrist 的 RMSE 普遍高于 RElbow（约 1.3-1.5×）
- 原因：RWrist 是末端关节，运动幅度更大、速度更快 → 同样的像素噪声在归一化后影响更大
- 这个差异在不同方法之间保持一致 → 方法选择不因关节而异

---

## 4. 最难恢复的阶段

按 RMSE 从高到低：
1. **Reach**：手臂快速移动，速度变化大 → 噪声与信号混合
2. **Transport**：类似 reach，但速度更均匀 → 稍好
3. **Grasp**：手部精细运动 + 接近静止 → 噪声相对明显
4. **Idle**：静止 → 任何微小噪声都显著

意外：idle 并非最容易恢复——因为 idle 的 clean displacement 标准极严（0 运动 = 0 偏移容忍度）。

---

## 5. SG 的优势来源

SG 的 RMSE 优势**几乎完全来自高严重度 gaussian noise**。对于 burst jump、drift 和 short missing，SG 与其他方法的差距不大或更差。将 SG 的"overall best"归因于固定窗口去噪是片面的——这种优势高度依赖于噪声类型的分布。

---

## 6. Kalman 为何 clean displacement 低

Kalman 的 clean displacement 在所有方法中最低（~0.009 norm vs SG 的 ~0.028）。

原因：Kalman 的状态空间模型在观测可信时自然地信任观测。当观测噪声低（clean 帧），Kalman gain 自动减小修正量。SG 则无论观测质量如何都施加相同强度的平滑。

这对 B4 的意义：**质量感知方法应该能继承 Kalman 对 clean 数据的保护能力，同时通过质量权重解决 Kalman 对 burst jump 处理不足的问题。**

---

## 7. KF-CW 为何只比 KF-CV 略好

Confidence-weighted Kalman 的改进微乎其微（RMSE 差异 < 1%）。原因：
1. OpenPose 的 confidence 与真实误差的**相关性不够强**——高 confidence≠低误差，尤其在被遮挡区域
2. 在合成数据中，所有帧的 confidence 是原始的（从 clean 帧复制），不反映实际的污染程度
3. 仅靠 OpenPose confidence 的权重调整不足以解决结构性错误（如 burst jump、drift）

这对 B4 的意义：**质量权重需要融合 OpenPose confidence + 人工 corruption mask + 数据来源**，而不仅仅依赖 OpenPose 的单一 confidence。

---

## 8. 极端样本影响

max_error 与 RMSE 的比值：最高可达 **RMSE 的 3-5 倍**（尤其在 burst jump 高严重度）。这表明少数极端样本（jump 幅度最大的样本）主导了 max_error。

检查 per-sample RMSE 分布：burst_jump/high 的几个样本贡献了不成比例的 max_error。在 B4 中，我们需要报告 per-sample distribution（如 boxplot），而不仅仅是均值。

---

## 9. Max Error vs RMSE

两者结论**不一致**：
- RMSE 排名：SG < OE < KF-CW ≈ KF-CV < CORR
- Max Error 排名：OE < SG < KF-CW ≈ KF-CV < CORR

OE 在 max error 上优于 SG，因为 OE 的自适应机制对局部跳变有更好的压制。SG 的大窗口在跳变处会将误差"抹平"到多帧，降低 RMSE 但 max error 仍然高。

---

## 10. 速度/加速度/Jerk

| 指标 | 最优 | 说明 |
|------|------|------|
| Velocity RMSE | OE | OE 的自适应低通有效保护速度轮廓 |
| Acceleration RMSE | SG | SG 的多项式拟合自然产生平滑加速度 |
| Jerk RMSE | SG | SG 的最低——但这可能是**过度平滑**的信号 |

**Jerk 低 ≠ 好**。B1 中我们已经讨论过：zero-jerk = zero-motion。我们需要检查 Jerk 的降低是否伴随着 real-motion attenuation（真实运动的加速度被压低）。

实测：SG 的 real-motion attenuation 约为 0.14-0.31，KF 约为 0.02-0.17。SG 对真实运动的压制比 KF 强 2-5 倍。这意味着**SG 的"平滑"正在破坏对策略学习至关重要的运动动态**。
