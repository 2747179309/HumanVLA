# T07C-B4: Implementation Plan

## 1. 代码结构

```
scripts/trajectory/
├── refinement/
│   ├── __init__.py
│   ├── quality_weights.py       # q_t 三源融合
│   ├── objective.py             # E_data + E_dyn + E_boundary + E_bone
│   ├── bone_constants.py        # L_upper, L_forearm 估计
│   ├── optimizer.py             # 凸优化求解器
│   └── ablation_config.py       # M1-M4 开关
├── build_boundary_benchmark.py  # 独立 boundary benchmark
├── run_refinement.py            # B4 主入口
└── evaluate_refinement.py       # 与 B3 相同的指标 + bone/phase
```

## 2. M1-M4 实现矩阵

| 模块 | 开关 | 目标函数项 | 新超参数 |
|------|------|-----------|---------|
| M1 | quality_weights=True | q_t \|x̂ - z\|² | 无（q_t 从 T07C-A 读取） |
| M2 | +dynamics=True | + λ_v\|v̂ - v_ref\|² + λ_a\|â - a_ref\|² | λ_v, λ_a |
| M3 | +phase_preserving=True | + boundary q_t amplification + λ reduction | γ=1.5 |
| M4 | +bone_constraints=True | + \|L_upper\|² + \|L_forearm\|² | w_bone |

## 3. 超参数搜索 (M2-M4, 仅在 train 上)

| 参数 | 搜索空间 | 选择依据 |
|------|---------|---------|
| λ_v | {0.01, 0.1, 1.0, 10.0} | val composite score |
| λ_a | {0.001, 0.01, 0.1, 1.0} | val composite score |
| w_bone | {0.1, 0.5, 1.0, 5.0} | val composite score |
| γ | 1.5 (固定) | — |

## 4. 评估数据集

- **B2 test split**: 96 样本 (M0-M4 主评估)
- **Boundary benchmark**: 独立 5 个边界 × 多种污染 (M3 专项评估)
- **B3 baselines**: 复用 B3 已计算的 test 结果

## 5. Pre-commit 检查

- [ ] 所有超参数写入 `configs/refinement/t07c_b4_ablation.json`
- [ ] 配置文件 SHA-256 在首次运行前记录
- [ ] Test 集仅在全部参数冻结后运行一次
- [ ] M1-M4 的消融开关全部独立可测试
