# T07C-B3 结果阅读指南

## 1. 先看评估边界

本结果是E001单episode内部、时间范围隔离的合成污染基准。test包含96个样本，来自retract和idle阶段；这不是跨人物、跨视频或真实机器人策略性能。B2窗口都在单一phase内，因此`phase_boundary_shift`的定义样本数为0，结果写为`null/not_applicable`，不能将其当作0误差。

## 2. validation选出的参数

| 方法 | validation选择参数 | selection score |
|---|---|---:|
| SG | window=7, polyorder=2 | 0.051879 |
| One Euro | min cutoff=5 Hz, beta=0, derivative cutoff=1 Hz | 0.059751 |
| Kalman CV | acceleration std=8.0 norm/s², measurement std=0.005 norm | 0.058598 |
| confidence-weighted Kalman | acceleration std=8.0, base measurement std=0.005, confidence power=1 | 0.059038 |

train指标只用于开发诊断，没有决定上述排名。选参后test方法运行一次，记录在`b3_test_once_audit.json`。

## 3. Test总体结果

主要指标是对缺失输出带显式惩罚的corrupted-region RMSE_norm：

| 方法 | penalized corrupted RMSE_norm | clean displacement_norm | output coverage |
|---|---:|---:|---:|
| SG | 0.058489 | 0.022568 | 1.000000 |
| One Euro | 0.062395 | 0.019928 | 1.000000 |
| confidence-weighted Kalman | 0.081717 | 0.009164 | 1.000000 |
| Kalman CV | 0.082074 | 0.008250 | 1.000000 |
| no processing | 0.328990 | 0.000000 | 0.927083 |

解读：SG在本次总体主指标上最低，但它对clean region的改动最大；Kalman CV最保护未污染观测，却对burst jump和drift抑制有限。因此不存在“所有指标绝对最好”的方法。confidence-weighted Kalman与普通Kalman非常接近，原因之一是合成错误不会篡改原OpenPose confidence；置信度不一定能识别人为加入的污染。

## 4. 按污染类型看

Test中每个方法、每种污染均有24个样本。

| 方法 | Gaussian | Burst jump | Continuous drift | Short missing |
|---|---:|---:|---:|---:|
| SG | 0.028019 | 0.115689 | 0.079102 | 0.011148 |
| One Euro | 0.029835 | 0.125488 | 0.072866 | 0.021391 |
| Kalman CV | 0.039944 | 0.178882 | 0.090943 | 0.018528 |
| confidence-weighted Kalman | 0.039409 | 0.178187 | 0.090959 | 0.018311 |
| no processing | 0.044551 | 0.180597 | 0.090810 | 1.000000 penalty |

SG在Gaussian、burst和short-missing上最低；One Euro在continuous drift上最低。no-processing的short-missing正式RMSE为空，因为没有预测；表中的1.0是预注册选择/比较用缺失惩罚，不能写成实际位置RMSE。

## 5. 其他指标怎么读

- `corrupted_region_mae/rmse`：只看被污染帧；RMSE比MAE更强调大误差。
- `clean_region_displacement`：滤波对未污染帧的副作用。Gaussian污染覆盖全窗口，因此该类样本没有clean region，值为空。
- `max_error`：整条输出完整时的最大位置误差；输出缺失时为空，避免只从剩余点得到虚假低值。
- `velocity/acceleration/jerk error`：对相邻差分逐阶计算。整条输出不完整时为空，不把缺口外的局部正确误写为完整轨迹正确。
- `phase_boundary_shift`：当前B2设计无法识别，全部为空。
- `real_motion_attenuation`：`1-output_path/clean_path`。正值表示运动被削弱，负值表示运动被放大。总体出现较大负值，主要说明污染和滤波残差增加了路径长度，不等于“负误差”。
- `output_coverage`：有数值输出的比例。它与误差必须一起看。

## 6. 为什么这些结果还不能支持B4结论

这些基线没有使用人工mask、phase边界或骨骼长度。当前test只有两个phase，窗口长度只有8帧，而且来自同一视频。可以陈述“在E001的冻结合成测试上，传统基线呈现降噪与clean保护的权衡”，不能陈述某方法普遍优于其他方法，也不能提前声称B4会胜出。

## 7. 复核路径

1. 在`b3_validation_parameter_search.csv`确认47个候选和全部val结果。
2. 在`b3_selected_parameters.json`确认四种方法只按val选择。
3. 在`b3_test_once_audit.json`确认`test_evaluation_count=1`。
4. 在`b3_test_results.csv`按method/joint/corruption_type/severity/phase/split筛选480条test明细。
5. 在`b3_test_summary.json`读取240个完整分组和总体method summary。
6. 用`b3_baseline_comparison.png`快速比较主误差、clean副作用与coverage，但论文数值应以CSV/JSON为准。

## 8. 常见误读

- SG总体第一不等于所有污染、所有指标第一。
- clean displacement为0的no-processing并不意味着它能处理缺失。
- confidence-weighted Kalman没有明显领先，不代表confidence无用，只说明这批合成污染与原confidence没有必然相关性。
- test只运行一次不等于结果自动具有外部有效性。
- test的idle/retract分布与train/val不同，方法差异同时受phase分布影响，必须保留phase分组。

## 9. 结果阅读自测问题

1. 为什么no-processing的clean displacement为0仍不能称为最好？
2. penalized RMSE和正式RMSE在short-missing上为什么必须分开？
3. SG总体主指标最低时，哪个指标揭示了它对clean region的副作用？
4. 哪种方法在continuous drift分组最低，这是否使它成为总体最优？
5. confidence-weighted Kalman没有明显领先普通Kalman，合成数据设计提供了什么解释？
6. negative real-motion attenuation在本实验中代表什么？
7. 为什么phase-boundary shift为null比写0更严谨？
8. test一次运行审计能防止哪类研究偏差，不能解决哪类外部有效性问题？
9. 为什么必须同时查看joint、severity、phase和corruption type分组？
10. 当前结果允许写入论文的最强但不过度的结论是什么？
