# T07C-B3: Traditional Trajectory Refinement — Experiment Protocol

## 1. 基线方法

| ID | 方法 | 因果 | 超参数 |
|----|------|------|--------|
| CORR | Corrupted input (no processing) | — | 无 |
| SG | Savitzky-Golay | 非因果 | window, poly_order |
| OE | One Euro (forward-backward) | 非因果 | fc_min, beta |
| KF-CV | Kalman CV smoother | 非因果 | Q_diag, R_diag |
| KF-CW | Confidence-weighted Kalman CV | 非因果 | Q_diag, R0_diag |

## 2. 超参数搜索空间

| 方法 | 参数 | 搜索范围 | 搜索方式 |
|------|------|---------|---------|
| SG | window | {3, 5, 7, 9, 11, 15} | grid |
| SG | poly_order | 2 (固定) | — |
| OE | fc_min | {0.5, 1.0, 2.0, 5.0} | grid |
| OE | beta | {0.001, 0.005, 0.01, 0.05} | grid |
| KF-CV | Q_diag (pos) | {1e-4, 1e-3, 1e-2, 0.1, 1.0} | grid |
| KF-CV | Q_diag (vel) | {1e-3, 1e-2, 0.1, 1.0, 10.0} | grid |
| KF-CV | R_diag | {1e-3, 1e-2, 0.1, 1.0, 10.0} | grid |
| KF-CW | Q_diag | {1e-4, 1e-3, 1e-2} | grid |
| KF-CW | R0_diag | {0.01, 0.1, 1.0, 10.0} | grid |

## 3. 参数选择协议

```
Phase 1: Grid search on TRAIN set
  For each (method, param_combo):
    Run on all TRAIN samples
    Record mean corrupted-region RMSE_norm + clean-region displacement_norm
    
Phase 2: Selection on VAL set  
  For each method's top-3 param combos (by TRAIN composite score):
    Run on all VAL samples
  Select best param by: 0.6 * corrupted_RMSE_norm + 0.4 * CRD_norm

Phase 3: Single evaluation on TEST set
  For each method with best VAL params:
    Run ONCE on all TEST samples
    Record ALL metrics
  NO parameter adjustment allowed after TEST results seen
```

## 4. 评估指标

### 主要指标
- **Corrupted-region RMSE_norm**：仅在 corruption_mask=true 的帧上计算

### 次要指标（全部报告）
- Clean-region displacement_norm (CRD)
- Max error (pixel, normalized)
- Velocity error (norm/s)
- Acceleration error (norm/s²)
- Jerk error (norm/s³)
- Phase-boundary shift: boundary 前后 2 帧的位移偏差
- Real-motion attenuation: 合成快速运动帧的速度被压低了多少

### 分组报告
所有指标按以下维度分组：
- corruption_type × intensity × joint × phase × split

## 5. 并列结果判定规则

当两种方法的 corrupted RMSE 差异 < 5% 时，使用以下次级标准：
1. 更低的 CRD（保护干净数据）
2. 更低的 phase-boundary shift（保护阶段边界）
3. 更低的 real-motion attenuation（保护快速运动）

## 6. Train/Val/Test 使用规则

| 集合 | 样本数 | 用途 | 使用次数 |
|------|--------|------|---------|
| Train | 168 | 超参数搜索 | 多次（grid search） |
| Val | 72 | 参数选择、方法初步比较 | 多次（top-3 × 5 methods） |
| Test | 96 | 最终评估 | **严格一次** |

## 7. 代码结构

```
scripts/trajectory/
├── baselines/
│   ├── __init__.py
│   ├── savitzky_golay.py
│   ├── one_euro.py
│   ├── kalman_cv.py
│   └── kalman_cw.py
├── grid_search_baselines.py    # Phase 1: train grid search
├── evaluate_baselines.py       # Phase 2+3: val selection + test eval
└── report_baseline_results.py  # Generate tables and plots
```

## 8. 预期结果（假设，不可作为调参指导）

| 假设 | 可能的结果 |
|------|-----------|
| SG 对高斯噪声最好 | 需要验证——固定窗口可能不如自适应方法 |
| One Euro 对 burst jump 最好 | 自适应可能减少跳变的扩散 |
| KF-CW 对 short missing 最好 | 置信度信息在完全缺失时帮助有限 |
| 没有方法在所有 corruption 类型上最好 | 很可能——为 B4 的质量感知方法提供动机 |

## 9. 论文记录

- 所有超参数搜索记录保存在 `results/trajectories/pick_place_pilot_v1_E001/baseline_grid_search.csv`
- 预注册时间戳记录在 `configs/dataset/t07c_b3_baseline_protocol.json`
- Test 结果不可用于修改方法或参数
