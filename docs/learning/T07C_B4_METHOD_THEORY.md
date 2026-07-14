# T07C-B4: Quality-Aware Phase-Preserving Skeletal Trajectory Refinement — Method Theory

## 1. 从 B3 到 B4：每个模块针对的具体失败

| B3 发现 | B4 模块 | 机制 |
|---------|---------|------|
| SG 在 clean 帧上引入 0.028 norm CRD | **M1: 质量权重** | 高 q_t 帧减少平滑，保护 clean 数据 |
| Kalman 对 burst jump 处理差 (RMSE 高) | **M1: 质量权重** | 低 q_t (mask) 帧允许大修正 |
| Kalman velocity RMSE 高 | **M2: 动态约束** | 显式惩罚速度和加速度误差 |
| phase-boundary shift 未测量但担心 | **M3: 阶段边界保护** | 边界 ±2 帧使用保守平滑 |
| frame 129-142 RElbow 遮挡区间骨骼不合理 | **M4: 骨骼约束** | 上臂-前臂长度守恒 |

---

## 2. M1: 质量加权观测项

### 2.1 q_t 的三源融合（修正 B3 的单一 confidence）

从 B3 我们学到：仅靠 OpenPose confidence 不够。B4 的 q_t 融合三个来源：

$$q_t = \min(q_t^{\text{conf}}, q_t^{\text{mask}}, q_t^{\text{source}})$$

其中：
- \(q_t^{\text{conf}}\)：OpenPose confidence（连续值）
- \(q_t^{\text{mask}}\)：T07C-A 人工判定（离散: mask=0.0, downweight=0.3, keep=1.0, defer=0.0）
- \(q_t^{\text{source}}\)：数据来源（raw=0.8, repaired=0.6）

### 2.2 加权目标函数

$$E_{\text{data}} = \sum_t q_t \cdot \|\hat{x}_t - z_t\|^2$$

当 q_t=0（mask 帧）：该项消失——优化完全由其他项驱动。
当 q_t=1（valid 帧）：该项相当于标准 L2 损失。

### 2.3 B3 证据

B3 中 KF-CW 改进 <1% → 需要更强的权重信号。M1 的 mask 分量提供了置信度无法提供的 binary 信号（某帧到底能不能用）。

---

## 3. M2: 速度/加速度连续性约束

### 3.1 目标函数扩展

$$E_{\text{dyn}} = \lambda_v \sum_t \|\hat{v}_t - v_t^{\text{ref}}\|^2 + \lambda_a \sum_t \|\hat{a}_t - a_t^{\text{ref}}\|^2$$

其中参考值 \(v_t^{\text{ref}}, a_t^{\text{ref}}\) 从相邻 valid 帧的中央差分估计。

### 3.2 为什么约束加速度而不是 Jerk

加速度直接对应力（\(F=ma\)），对机器人策略学习更有物理意义。Jerk 约束可能导致"过度平滑"——所有运动都被压制成恒速。

### 3.3 B3 证据

B3 中 Kalman 的 velocity RMSE 高 → 纯位置约束不足以保护运动动态。

---

## 4. M3: 阶段边界保护

### 4.1 边界区域定义

$$\mathcal{B} = \{t \mid t \in [\tau - 2, \tau + 2], \tau \text{ is a phase boundary}\}$$

### 4.2 边界处的处理

在 \(\mathcal{B}\) 内的帧，数据保真权重乘以放大因子（更信任观测）：

$$\tilde{q}_t = \min(1.0, q_t \cdot \gamma), \quad \gamma = 1.5 \text{ for } t \in \mathcal{B}$$

同时减小平滑惩罚的权重：

$$\tilde{\lambda}_v = \lambda_v / \gamma, \quad \tilde{\lambda}_a = \lambda_a / \gamma$$

效果：在阶段边界处，优化更信任原始观测，更少依赖平滑模型。这保护了 grasp→lift、place→release 等关键切换不被模糊。

### 4.3 B3 证据

B3 的 phase-boundary shift = not_applicable（B2 单 phase 窗口）→ B4 必须独立构建 boundary benchmark。

---

## 5. M4: 肩-肘-腕骨骼约束

### 5.1 骨骼长度估计

从该 episode 的 valid 帧中估计：
$$L_{\text{upper}} = \text{median}(\|\text{RElbow}_t - \text{RShoulder}_t\|)$$
$$L_{\text{forearm}} = \text{median}(\|\text{RWrist}_t - \text{RElbow}_t\|)$$

使用 median 而非 mean 以提高对 outlier 的鲁棒性。

### 5.2 软约束形式

$$E_{\text{bone}} = \sum_t \left(\|\hat{x}_t^{\text{RElbow}} - \hat{x}_t^{\text{RShoulder}}\| - L_{\text{upper}}\right)^2 + \left(\|\hat{x}_t^{\text{RWrist}} - \hat{x}_t^{\text{RElbow}}\| - L_{\text{forearm}}\right)^2$$

这是软约束——允许 ±5% 的长度变化（2D 投影中骨骼投影长度随 3D 旋转自然变化）。

### 5.3 B3 证据

B3 在 short_missing 上所有方法都差（完全缺失无观测约束）→ M4 在缺失帧提供物理约束。B3 验证了 Kalman 在缺失帧的预测会漂移 → 骨骼约束锚定漂移。

---

## 6. 为什么是递进消融设计（M1→M4）

递进消融（nested ablation）意味着 M2 ⊃ M1, M3 ⊃ M2, M4 ⊃ M3。这允许我们在 B5 中逐个移除组件，量化每个的边际贡献。

| 移除 | 预期影响 |
|------|---------|
| M4→M3 (移除骨骼) | short_missing RMSE ↑, bone_length_error ↑ |
| M3→M2 (移除阶段) | phase-boundary shift ↑ |
| M2→M1 (移除动态) | velocity RMSE ↑, acceleration RMSE ↑ |
| M1→M0 (移除质量) | CRD ↑ (类似 B3 SG 的问题) |
