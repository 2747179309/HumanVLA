# T07C-B3 验收标准：传统轨迹滤波基线实现与比较

版本：v0.1.0
日期：2026-07-14
前置：T07C-B2 (合成数据集, 已通过)

---

## 一、实现验收

### 1.1 代码
- [ ] 4 种方法 + 1 corrupted-input 对照全部实现
- [ ] 所有脚本 `py_compile` + `--help` 通过
- [ ] 超参数搜索空间与预注册协议一致
- [ ] Confidence-weighted Kalman 仅使用 OpenPose confidence，未混入人工 mask

### 1.2 搜索与评估
- [ ] Grid search 仅在 train 上执行
- [ ] Val 仅用于 top-3 参数选择
- [ ] Test 严格运行一次
- [ ] 搜索记录完整保存

---

## 二、结果验收

### 2.1 完整性
- [ ] 所有 336 个合成样本均有 5 种方法的输出
- [ ] Corrupted-region RMSE_norm 为主要指标
- [ ] CRD、max_error、velocity_error、jerk_error、phase-boundary shift、real-motion attenuation 全部报告
- [ ] 按 corruption_type × intensity × joint × phase 分组

### 2.2 一致性
- [ ] Corrupted-input RMSE 与合成污染的施加量一致（如 gaussian σ=5px → RMSE≈5px）
- [ ] Clean-region displacement 在合理范围（不应 > 5px 对 valid 帧）
- [ ] 无方法在所有指标上绝对最优

---

## 三、输出文件

| 文件 | 路径 |
|------|------|
| 基线实现 | `scripts/trajectory/baselines/` (4 个 .py) |
| 搜索+评估 | `scripts/trajectory/grid_search_baselines.py` + `evaluate_baselines.py` |
| 搜索结果 | `results/trajectories/pick_place_pilot_v1_E001/baseline_grid_search.csv` |
| 最终指标 | `results/trajectories/pick_place_pilot_v1_E001/baseline_results.json` |
| 对比图 | `results/trajectories/pick_place_pilot_v1_E001/baseline_comparison.png` |
| 协议配置 | `configs/dataset/t07c_b3_baseline_protocol.json` |
| 运行日志 | `logs/runs/T07C_B3_BASELINES.md` |

---

## 四、不通过条件

1. Test 集被用于参数选择或方法修改
2. Confidence-weighted Kalman 混入了人工 mask 信息
3. 搜索空间与预注册协议不一致
4. Clean-region displacement 异常高（> 10 px）
5. 分组报告缺少任一维度

---

## 五、通过条件

5 种方法全部运行 + 指标完整 + train/val/test 隔离正确 + 结果合理。
