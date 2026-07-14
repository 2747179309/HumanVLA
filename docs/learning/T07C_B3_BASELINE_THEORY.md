# T07C-B3: Traditional Trajectory Refinement Baselines — Theory

## 1. Savitzky-Golay：局部多项式拟合

### 1.1 核心思想

在一个滑动窗口内，用低阶多项式最小二乘拟合局部数据点。平滑值 = 多项式在窗口中心的值。

设窗口大小为 \(2w+1\)（奇数），多项式阶数为 \(k\)（通常 \(k=2\) 或 \(3\)）。对窗口内的数据点 \(\{z_{t-w}, ..., z_t, ..., z_{t+w}\}\)，找到多项式 \(p(i) = a_0 + a_1 i + a_2 i^2 + ... + a_k i^k\) 最小化：

$$\min_{a_0,...,a_k} \sum_{i=-w}^{w} (p(i) - z_{t+i})^2$$

平滑值 \(\hat{x}_t = p(0) = a_0\)。

### 1.2 等效卷积

由于最小二乘解是线性的，平滑值可以写为窗口内数据的线性组合：

$$\hat{x}_t = \sum_{i=-w}^{w} c_i \cdot z_{t+i}$$

其中系数 \(c_i\) 只依赖于 \(w\) 和 \(k\)，与数据无关。SG 本质是一个固定系数的 FIR 滤波器。

### 1.3 参数选择

| 参数 | 太小 | 太大 |
|------|------|------|
| 窗口 \(w\) | 噪声保留过多 | 信号（尤其快速运动）被过度平滑 |
| 阶数 \(k\) | 欠拟合，削平峰谷 | 过拟合噪声 |

### 1.4 因果性

SG 使用对称窗口 → **非因果**（需要未来帧）。在实时应用中不可用，但在离线数据处理中完全可行。

---

## 2. One Euro Filter：自适应低通

### 2.1 核心思想

一阶低通滤波器，但截止频率根据信号速度自动调整。

$$\hat{x}_t = \alpha_t \cdot z_t + (1 - \alpha_t) \cdot \hat{x}_{t-1}$$

$$\alpha_t = \frac{1}{1 + \tau / T_e}$$

其中 \(\tau = 1/(2\pi f_c)\) 是时间常数，\(T_e = 1/f_s\) 是采样周期。

### 2.2 速度自适应

截止频率由速度决定：
$$f_c = f_{c_{\min}} + \beta \cdot |\dot{\hat{x}}_t|$$

- 低速（静止或慢速运动）→ \(f_c\) ≈ \(f_{c_{\min}}\) → 强平滑
- 高速（快速运动）→ \(f_c\) 增大 → 减少平滑，保护快速运动

### 2.3 为什么自适应

传统低通滤波器在高速运动时会引入**滞后**（延迟）。One Euro 在快速运动时自动提高截止频率，减少滞后。这是它相对于 SG 的主要优势。

### 2.4 参数

| 参数 | 含义 | 典型范围 |
|------|------|---------|
| \(f_{c_{\min}}\) | 最小截止频率 (Hz) | 0.5-5 |
| \(\beta\) | 速度增益 | 0.001-0.1 |

### 2.5 因果性

递归结构 → **因果**（仅用过去帧）。但在离线应用中，可以 forward-backward 两次滤波消除相位延迟（→ 非因果）。

---

## 3. Kalman Filter：贝叶斯状态估计

### 3.1 状态空间模型

**状态**：系统在时刻 \(t\) 的真实状态 \(s_t\)（我们想估计但无法直接观测的）。

对于轨迹平滑，恒速 (CV) 模型的状态：
$$s_t = \begin{bmatrix} x_t \\ y_t \\ \dot{x}_t \\ \dot{y}_t \end{bmatrix}$$

**状态转移**（预测）：
$$s_{t+1} = F \cdot s_t + w_t, \quad w_t \sim \mathcal{N}(0, Q)$$

$$F = \begin{bmatrix} 1 & 0 & \Delta t & 0 \\ 0 & 1 & 0 & \Delta t \\ 0 & 0 & 1 & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix}$$

物理含义：位置 = 上一位置 + 速度 × 时间。\(w_t\) 是过程噪声——模型不完美（运动不是完美的匀速直线）。

**观测**（更新）：
$$z_t = H \cdot s_t + \nu_t, \quad \nu_t \sim \mathcal{N}(0, R)$$

$$H = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 1 & 0 & 0 \end{bmatrix}$$

物理含义：我们只能观测位置（OpenPose 输出），不能直接观测速度。\(\nu_t\) 是观测噪声。

### 3.2 两步递归

**Predict**（先验估计）：
$$\hat{s}_{t|t-1} = F \cdot \hat{s}_{t-1|t-1}$$
$$P_{t|t-1} = F \cdot P_{t-1|t-1} \cdot F^T + Q$$

**Update**（后验估计）：
$$K_t = P_{t|t-1} \cdot H^T \cdot (H \cdot P_{t|t-1} \cdot H^T + R)^{-1}$$
$$\hat{s}_{t|t} = \hat{s}_{t|t-1} + K_t \cdot (z_t - H \cdot \hat{s}_{t|t-1})$$
$$P_{t|t} = (I - K_t \cdot H) \cdot P_{t|t-1}$$

### 3.3 \(Q\) 和 \(R\) 的物理含义

**\(Q\)（过程噪声协方差）**：我们对运动模型有多不信任。
- \(Q\) 大 → 更信任观测 → 更少平滑 → 更适合快速变化
- \(Q\) 小 → 更信任模型 → 更多平滑 → 更适合慢速运动

**\(R\)（观测噪声协方差）**：我们对 OpenPose 观测有多不信任。
- \(R\) 大 → 不信任观测 → 更多平滑
- \(R\) 小 → 信任观测 → 更少平滑

在标准 Kalman 中，\(R\) 对所有帧是常数。**Confidence-weighted Kalman 的核心创新**：让 \(R_t\) 随置信度变化：

$$R_t = \frac{R_0}{\text{confidence}_t}$$

当 confidence 低时，\(R_t\) 大 → Kalman 更少信任该观测 → 更多依赖运动模型预测。这是将 OpenPose 的置信度信息融入 Kalman 的最简单方式。

### 3.4 因果性

标准 Kalman filter → **因果**。Kalman smoother（RTS smoother）→ **非因果**（forward-backward pass）。

离线轨迹处理通常用 smoother。

### 3.5 恒速 vs 恒加速

| 模型 | 状态维度 | 适用场景 |
|------|---------|---------|
| CV | 4 (x, y, vx, vy) | 运输、闲置、缓慢移动 |
| CA | 6 (x, y, vx, vy, ax, ay) | 伸手、举起（有加速） |

对 E001，CV 在 transport/idle 阶段好，CA 在 reach/lift 阶段好。两者的选择是 bias-variance tradeoff。

---

## 4. 为什么离线平滑和在线滤波要区分

| | 在线滤波 | 离线平滑 |
|--|---------|---------|
| 可用数据 | 仅过去帧 | 全部帧 |
| 因果性 | 必须因果 | 可以非因果 |
| 延迟 | 有 | 无（但整体延迟整个序列） |
| 应用 | 实时机器人控制 | 数据集预处理 |
| 方法 | Kalman filter | Kalman smoother, SG, forward-backward One Euro |

**我们的场景是离线数据处理**——整个 episode 已经录制完成，我们拥有全部帧。因此可以使用非因果方法（SG, smoother），它们通常比因果方法效果更好。

---

## 5. 为什么 clean-region displacement 很重要

### 5.1 定义

Clean-region displacement 是滤波方法在**未被污染的帧**上引入的偏差：

$$\text{CRD} = \frac{1}{|\mathcal{C}|} \sum_{t \in \mathcal{C}} \|\hat{x}_t - x_t^{\text{gt}}\|$$

其中 \(\mathcal{C}\) 是 corruption_mask=false 的帧（没有被合成污染）。

### 5.2 为什么不能只看 corrupted-region RMSE

一个极端的"好"方法可以输出常数（完全忽略所有观测）——它在 corrupted region 上的 RMSE 可能很好（如果 ground truth 恰好接近常数），但 clean-region displacement 会暴露它破坏了正常数据。

**好的滤波应该**：
1. 在 corrupted region：有效抑制噪声（低 corrupted RMSE）
2. 在 clean region：尽可能保留原始信号（低 CRD）

这两个目标通常是矛盾的——更强的平滑同时降低 corrupted RMSE 和增加 CRD。

---

## 6. 为什么测试集不能参与参数选择

如果我们根据测试集上的表现调整超参数，我们实际上是在**用测试集进行训练**。选出的"最优"参数可能只是恰好对这批测试数据效果好，不能泛化到新数据。

正确流程：
1. **Train** 上尝试不同的超参数组合（如不同的 SG 窗口大小）
2. **Val** 上选择表现最好的组合
3. **Test** 上**仅运行一次**，报告最终结果

这是机器学习的基本纪律。违反它会导致过拟合的"好结果"在现实中无效。
