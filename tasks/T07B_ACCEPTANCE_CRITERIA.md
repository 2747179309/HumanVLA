# T07B 验收标准：Short-Gap Recovery Benchmark and Derived Trajectory Repair

版本：v0.1.0
日期：2026-07-14
前置：T07A（原始轨迹，已通过）
输入：`raw_upper_limb_trajectory.jsonl` (345 帧)

---

## 一、合成遮挡实验

### 1.1 样本生成约束

```python
valid_candidates = frames where:
   frame_index not in [0, 1]                    # no identity-init gap
   frame_index not in real_missing_frames         # [64,65,143,182-185]
   rwrist_coordinate_available == True           # real observation exists
   trajectory_quality == "valid"                 # only valid frames
   manual_label not in ["occlusion_error", "normalization_artifact"]
   gap_start-1 and gap_end+1 both valid          # context available
   phase_id at gap_start == phase_id at gap_end  # same phase
```

### 1.2 缺口长度与阶段覆盖

| gap_length | 目标样本数 | 必须覆盖的阶段 |
|-----------|----------|--------------|
| 1 | ≥5 | reach, grasp, transport, place, retract |
| 2 | ≥5 | reach, grasp, lift, transport, place |
| 3 | ≥3 | reach, transport, place |
| 4 | ≥3 | reach, transport, place |

若某阶段样本不足，在 `synthetic_gap_manifest.csv` 的 `note` 列注明，不伪造。

### 1.3 合成方法

对每个选定的 gap 区间 [g_start, g_end]：
1. 保存 gap 内的真实坐标作为 ground truth
2. 将 gap 内坐标标记为 "masked"（模拟缺失）
3. 用 4 种方法分别恢复
4. 计算恢复结果与真实坐标的误差

---

## 二、四种恢复方法

### 2.1 方法定义

| 方法 | 实现 | 使用缺口后观测？ |
|------|------|----------------|
| Linear | `scipy.interpolate.interp1d(kind='linear')` | 是（两端边界条件） |
| PCHIP | `scipy.interpolate.PchipInterpolator` | 是 |
| Cubic Hermite | `scipy.interpolate.CubicHermiteSpline`（导数由相邻帧差分估计） | 是 |
| Kalman CV | 恒速模型 Kalman 预测+平滑（`pykalman` 或等效实现） | 是（平滑 pass 使用） |

所有方法均为离线方法。Kalman 需明确分为 prediction-only 和 smoothing 两个 pass，结果分别记录。

### 2.2 方法约束
- 不得把滤波与缺口恢复混在一起
- Kalman 的状态转移和观测协方差必须记录在 benchmark 中
- 每种方法独立运行，不串联

---

## 三、评价指标

### 3.1 位置误差（RWrist 和 RElbow 分别计算）

| 指标 | 单位 | 公式 |
|------|------|------|
| MAE_px | pixel | mean(abs(pred - gt)) |
| RMSE_px | pixel | sqrt(mean((pred - gt)²)) |
| MAE_norm | — | mean(abs(pred_norm - gt_norm)) |
| RMSE_norm | — | sqrt(mean((pred_norm - gt_norm)²)) |
| max_error | pixel | max(abs(pred - gt)) |

### 3.2 运动连续性

| 指标 | 计算 |
|------|------|
| velocity_error | mean(abs(v_pred - v_gt)), v = dx/dt |
| acceleration_error | mean(abs(a_pred - a_gt)) |
| jerk_error | mean(abs(j_pred - j_gt)) |
| entry_velocity_discontinuity | abs(v_pred[0] - v_context_before[-1]) |
| exit_velocity_discontinuity | abs(v_pred[-1] - v_context_after[0]) |

### 3.3 保真性

| 指标 | 计算 |
|------|------|
| endpoint_error | L2 distance between predicted and true final point |
| trajectory_length_error | abs(total_path_length_pred - total_path_length_gt) |
| curvature_error | mean curvature difference along path |

### 3.4 分组统计

所有指标按以下维度分组报告：
- `gap_length` (1/2/3/4)
- `joint` (RElbow/RWrist)
- `phase_id` / `phase_label`
- `method`

### 3.5 排名规则

- **主要排名**：normalized RMSE（RWrist 优先于 RElbow）
- **次级排名**：jerk_error + entry_velocity_discontinuity（差异 < 10% 时使用）
- **provisional best**：仅在 E001 上最优，不声称全数据集最优

---

## 四、真实缺失修复

### 4.1 修复区间

使用 provisional best 方法修复：
- frame 64-65：2 帧 RWrist
- frame 143：1 帧 RWrist
- frame 182-185：4 帧 RWrist

### 4.2 修复字段

每帧修复后必须同时保留：

| 字段 | 说明 |
|------|------|
| `rwrist_x_px` / `rwrist_y_px` | raw 坐标保持不变 |
| `rwrist_x_norm` / `rwrist_y_norm` | raw 归一化坐标保持不变 |
| `rwrist_x_repaired_px` / `rwrist_y_repaired_px` | 修复后像素坐标 |
| `rwrist_x_repaired_norm` / `rwrist_y_repaired_norm` | 修复后归一化坐标 |
| `repair_mask` | bool，该帧该关节是否被修复 |
| `repair_method` | string，使用的方法名 |
| `repair_source` | string，`synthetic_benchmark` |
| `repair_gap_id` | string，如 `GAP_064_065` |
| `repair_confidence` | string，`high`/`medium`/`low` |
| `original_quality_reason` | string，保留原始 T07A quality_reason |

修复点不得覆盖 raw 坐标字段。

### 4.3 修复验证
- 修复后的 RWrist 轨迹在修复区间入口和出口的速度连续性检查
- 修复区间内不应出现 > 肩宽 50% 的单帧位移

---

## 五、occlusion_error 跳变处理

T07B **不自动修复** 8 个 occlusion_error 候选。处理方式：

- [ ] 输出 `corruption_candidate_list.json`：含 8 个候选的 frame_index, joint, displacement, manual_label
- [ ] 候选帧在 repaired trajectory 中保留原始 raw 坐标
- [ ] `repair_mask=false` 对这些帧
- [ ] 不自动删除、不自动替换
- [ ] 标注为 `deferred_to_T07C`

---

## 六、输出文件验收

### 6.1 脚本
- [ ] `scripts/trajectory/generate_synthetic_gaps.py` — `--help` + `py_compile`
- [ ] `scripts/trajectory/benchmark_gap_recovery.py` — `--help` + `py_compile`
- [ ] `scripts/trajectory/repair_short_gaps.py` — `--help` + `py_compile`
- [ ] `scripts/trajectory/validate_repaired_trajectory.py` — `--help` + `py_compile`

### 6.2 数据文件
- [ ] `synthetic_gap_manifest.csv`：所有合成 gap 的 frame_range, joint, phase, gap_length, note（不足阶段注明）
- [ ] `gap_recovery_benchmark.csv` / `.json`：所有 method × gap × joint 的指标
- [ ] `repaired_upper_limb_trajectory.jsonl` / `.csv`：345 行，含 raw + repaired 字段
- [ ] `actual_gap_repair_summary.json`：真实修复区间的入口/出口速度、最大位移

### 6.3 可视化
- [ ] `gap_recovery_comparison.png`：4 种方法 × gap_length 的 RMSE 柱状图
- [ ] `repaired_trajectory_overlay.mp4`：H.264, 345 帧，修复帧用蓝色标记

### 6.4 运行日志
- [ ] `logs/runs/T07B_SHORT_GAP_RECOVERY.md`

---

## 七、不通过条件

1. 合成样本使用了真实缺失帧
2. 修复覆盖了 raw 坐标
3. frame 0-1 被修复
4. Kalman 滤波与缺口恢复边界不清晰
5. 指标缺少任一分组维度
6. provisional best 被声称为全数据集最优
7. occlusion_error 候选被自动修改
8. 原始 T07A 文件被修改

---

## 八、通过条件

合成实验完整 + 4 方法指标齐全 + 真实修复正确（raw 未被覆盖）+ provisional best 明确标记为 E001-only + 原始文件未修改。
