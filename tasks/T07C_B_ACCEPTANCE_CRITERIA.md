# T07C-B 验收标准：Quality-Aware Phase-Preserving Trajectory Refinement

版本：v0.1.0
日期：2026-07-14
前置：T07C-A（corruption mask，已通过）

---

## 一、逐 corruption 类别的处理规则

| corruption_type | proposed_action | 处理方式 |
|----------------|----------------|---------|
| `valid` | keep | 直接使用 raw，正常平滑 |
| `real_motion` | keep | 同 valid |
| `normalization_artifact` | keep | 保留像素观测，标注尺度问题 |
| `occlusion_error` | mask/defer | 排除 raw，使用模型重建 |
| `openpose_jitter` | mask | 排除 raw，重建 |
| `low_quality_observation` | mask | 排除 raw，重建 |
| `boundary_continuity_warning` | mask | 保留 repaired，边界约束 |

---

## 二、阶段边界保持

- 任何平滑/重建方法不得跨越 phase 边界
- phase 切换帧 ±2 帧使用更保守的平滑参数
- 如果某 phase 内 masked 帧占比 > 50%，该 phase 整体降级为 low_confidence

---

## 三、frame 129-142 RElbow 重建规则

| 属性 | 值 |
|------|-----|
| raw 坐标 | 存在（OpenPose 输出） |
| 真实可见性 | 不可见（物体遮挡） |
| 可验证性 | observed-but-unverifiable |
| 下游来源 | none（T07C-A） |
| 重建方法 | 骨骼运动学模型：RShoulder→RWrist 距离约束 + 上臂/前臂长度守恒 |

---

## 四、比较方法

| 方法 | 使用 corruption mask？ | 阶段保持？ |
|------|----------------------|-----------|
| Kalman CV (baseline) | 否 | 否 |
| Kalman CV + mask weighted | 是，downweight 降权，masked 排除 | 否 |
| Phase-preserving cubic spline | 是 | 是（per-phase） |
| Bone-length constrained opt | 是 | 是 |

---

## 五、验收 checklist

### 5.1 轨迹完整性
- [ ] 345 帧 × 4 关节全部覆盖
- [ ] raw 坐标与 T07A raw trajectory 逐值一致
- [ ] refined 坐标仅覆盖 masked/deferred 帧，keep 帧使用 raw

### 5.2 重建质量
- [ ] 骨骼长度误差 < 肩宽的 15%
- [ ] 阶段边界无跨阶段平滑伪影
- [ ] frame 129-142 RElbow 重建轨迹物理合理

### 5.3 数据隔离
- [ ] raw trajectory 未修改
- [ ] repaired trajectory 未修改
- [ ] corruption mask 未修改

### 5.4 输出
- [ ] `refined_upper_limb_trajectory.jsonl` / `.csv` (345 行)
- [ ] `refinement_benchmark.json`
- [ ] `refinement_comparison.png`
- [ ] `refined_trajectory_overlay.mp4`

---

## 六、不通过条件

1. 阶段边界被跨阶段平滑
2. frame 129-142 RElbow 使用了被遮挡的 raw 观测
3. mask 帧的 raw 坐标被当作有效输入
4. 原始文件被修改
5. 执行了 SG/OneEuro 滤波

---

## 七、通过条件

重建物理合理 + 阶段边界保持 + 原始文件未修改 + 所有输出完整。
