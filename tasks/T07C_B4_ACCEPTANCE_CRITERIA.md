# T07C-B4 验收标准：Quality-Aware Phase-Preserving Skeletal Trajectory Refinement

版本：v0.1.0
日期：2026-07-14
前置：T07C-B3 (已通过)

---

## 一、实现验收

- [ ] M0-M4 全部实现，消融开关独立可测试
- [ ] q_t 三源融合 (confidence + mask + source) 正确
- [ ] 骨骼长度从 valid 帧估计，使用 median
- [ ] 优化问题凸性验证（保证全局最优）
- [ ] 所有脚本 `py_compile` + `--help`

## 二、实验验收

### 2.1 主实验 (B2 test split, 96 样本)
- [ ] M0-M4 + B3 best baselines (SG, KF-CV) 全部评估
- [ ] 主指标 corrupted-region RMSE_norm
- [ ] CRD, max_error, velocity/acceleration/jerk error 完整
- [ ] 按 corruption_type × severity × joint × phase 分组
- [ ] H1-H5 假设检验结果明确

### 2.2 Boundary benchmark (独立)
- [ ] 5 个阶段边界 × 多种污染
- [ ] Phase-boundary shift, velocity shift, action amplitude preservation 可计算
- [ ] M3 vs M2 对比（隔离阶段保护效果）

### 2.3 隔离纪律
- [ ] 超参数仅在 train 上搜索
- [ ] Test 仅运行一次
- [ ] Boundary benchmark 不参与 B2 排名

## 三、输出

| 文件 | 路径 |
|------|------|
| 实现 | `scripts/trajectory/refinement/` (6 个 .py) |
| 主结果 | `results/trajectories/.../b4_test_results.csv` + `.json` |
| Boundary | `results/trajectories/.../b4_boundary_results.csv` |
| 消融对比 | `results/trajectories/.../b4_ablation_comparison.png` |
| 预注册 | `configs/refinement/t07c_b4_ablation.json` |
| 运行日志 | `logs/runs/T07C_B4_REFINEMENT.md` |

## 四、不通过条件

1. Test 用于超参数选择
2. q_t 仅使用 OpenPose confidence（未融合 mask 和 source）
3. 骨骼约束为硬约束（而非软约束）
4. Phase-boundary shift 仍为 not_applicable
5. H1-H5 未报告 p 值

## 五、通过条件

M0-M4 全部实现 + H1-H5 完整检验 + boundary benchmark 独立 + train/val/test 隔离正确。
