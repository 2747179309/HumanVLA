# T07B Short-Gap Recovery Benchmark

## Run信息

- Run ID：`20260714_T07B_SYNTHETIC_BENCHMARK_001` / `20260714_T07B_REAL_GAP_REPAIR_001`
- 日期：2026-07-14 CST
- 目的：先用E001人工确认高质量轨迹构建合成遮挡基准，比较4个方法族，再用E001 provisional best修复3段真实RWrist缺口。
- 环境：Ubuntu 20.04；`motpose` Python 3.10.20；OpenCV 5.0.0、NumPy 2.2.6、SciPy 1.15.3、Matplotlib 3.10.9；FFmpeg/libx264。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。
- 是否可用于论文：可作为E001短缺口恢复原型基准；仅限单episode，不能声称跨视频最优。

## 预注册policy与输入

- 在任何benchmark运行前创建`configs/dataset/t07b_gap_recovery_policy.json`，SHA-256 `bd2775782f5b03d847e7cd4fdce40037017564dfe0f56f8d1801b91938da52e4`。
- 主排名仅含linear、PCHIP、cubic Hermite、Kalman CV smoothing；Kalman prediction-only单独记录但不参与排名。
- 主要指标：全部RWrist合成样本mean RMSE_norm。进入最佳值相对10%范围后，次级使用mean jerk_error_norm + entry_velocity_discontinuity_norm；再以RElbow RMSE_norm和方法名字典序决胜。
- Kalman固定参数：state `[x,y,vx,vy]`，`Q diag=[0.0001,0.0001,0.001,0.001]`，`R diag=[0.0001,0.0001]`，`P0 diag=[0.001,0.001,0.01,0.01]`。prediction不使用后端观测，smoothing使用；运行后未调参。
- Linear使用SciPy `interp1d(kind='linear')`；PCHIP使用`PchipInterpolator`；Hermite使用`CubicHermiteSpline`且端点导数来自相邻可靠观测差分。四方法均只预测gap内部。
- raw trajectory：SHA-256 `c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`。
- quality mask：SHA-256 `b98397817df55b93efe903469f1070a88349a30f95eedbc2e8c512b8f4ccf273`。
- T07A review CSV：SHA-256 `0a40f2a78a4a26720132f0c2cd06a2a150949906431f41abb7e5dba637ebbc84`。
- T07A summary：SHA-256 `03eb575160c5998eca970faf1cf863d23f81bde22c74324d74d0651ab6fa3528`。
- E001视频：SHA-256 `c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`。

## 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/gap_recovery_common.py \
  scripts/trajectory/generate_synthetic_gaps.py \
  scripts/trajectory/benchmark_gap_recovery.py \
  scripts/trajectory/repair_short_gaps.py \
  scripts/trajectory/validate_repaired_trajectory.py

for script in generate_synthetic_gaps.py benchmark_gap_recovery.py repair_short_gaps.py validate_repaired_trajectory.py; do
  env -u PYTHONPATH MPLCONFIGDIR=/tmp/humanvla-matplotlib \
    /home/a531/anaconda3/envs/motpose/bin/python scripts/trajectory/$script --help
done

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/generate_synthetic_gaps.py \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --policy configs/dataset/t07b_gap_recovery_policy.json \
  --output results/trajectories/pick_place_pilot_v1_E001/synthetic_gap_manifest.csv

env -u PYTHONPATH MPLCONFIGDIR=/tmp/humanvla-matplotlib \
  /home/a531/anaconda3/envs/motpose/bin/python scripts/trajectory/benchmark_gap_recovery.py \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --manifest results/trajectories/pick_place_pilot_v1_E001/synthetic_gap_manifest.csv \
  --policy configs/dataset/t07b_gap_recovery_policy.json \
  --output-csv results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.csv \
  --output-json results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.json \
  --output-plot results/trajectories/pick_place_pilot_v1_E001/gap_recovery_comparison.png

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/repair_short_gaps.py \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --benchmark-json results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.json \
  --policy configs/dataset/t07b_gap_recovery_policy.json \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --output-jsonl data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --output-csv data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.csv \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --output-corruption-list results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_list.json \
  --output-overlay results/trajectories/pick_place_pilot_v1_E001/repaired_trajectory_overlay.mp4

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_repaired_trajectory.py \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --trajectory-summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --policy configs/dataset/t07b_gap_recovery_policy.json \
  --manifest results/trajectories/pick_place_pilot_v1_E001/synthetic_gap_manifest.csv \
  --benchmark-csv results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.csv \
  --benchmark-json results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.json \
  --repaired-jsonl data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --repaired-csv data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.csv \
  --repair-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --corruption-list results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_list.json \
  --comparison-plot results/trajectories/pick_place_pilot_v1_E001/gap_recovery_comparison.png \
  --overlay results/trajectories/pick_place_pilot_v1_E001/repaired_trajectory_overlay.mp4
```

确定性复跑使用同一输入和参数，把manifest、benchmark三文件及repair五文件分别写到`/tmp/t07b_rerun_20260714/`并逐文件`sha256sum`比较；所有主输出与复跑输出哈希相同。

## 合成样本与泄漏检查

- 共44个样本；每个关节22个。gap length 1/2/3/4分别16/16/6/6个，即每个关节8/8/3/3个。
- length 1和2覆盖reach、align、grasp、lift、transport、place、release、retract；length 3和4覆盖reach、transport、place。阶段样本不足为0。
- 只使用`trajectory_quality=valid`且对应关节effective valid的真实观测；gap及前后各2帧上下文均同阶段。
- 未使用frame 0-1、真实缺失64-65/143/182-185、occlusion error或normalization artifact边的任何帧。
- 不同长度样本允许复用masked frame；policy在运行前说明原因。每项独立评测、无模型训练，恢复函数只接收masked gap外的4个上下文点；ground truth仅用于指标。

## 核心基准指标

下表均为22个样本的均值。Kalman prediction-only是诊断pass，不参与provisional best排名。

| Joint | Method | RMSE px | RMSE norm | velocity err norm/s | acceleration err norm/s² | jerk err norm/s³ | entry discontinuity norm/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| RWrist | linear | 3.257650 | 0.019819 | 0.286867 | 20.240788 | 1279.881028 | 1.162744 |
| RWrist | PCHIP | 3.709436 | 0.022681 | 0.315511 | 22.385460 | 1403.903798 | 1.012557 |
| RWrist | cubic Hermite | 4.287258 | 0.026315 | 0.376089 | 26.371289 | 1640.048336 | 0.753034 |
| RWrist | Kalman smoothing | 3.720823 | 0.022746 | 0.318896 | 22.661690 | 1410.250505 | 0.947090 |
| RWrist | Kalman prediction-only | 8.154520 | 0.051374 | 0.697907 | 46.672772 | 2842.077861 | 0.000000 |
| RElbow | linear | 2.424836 | 0.014997 | 0.233510 | 16.549975 | 1077.048710 | 0.934578 |
| RElbow | PCHIP | 2.602989 | 0.016126 | 0.246775 | 17.398179 | 1134.680228 | 0.844451 |
| RElbow | cubic Hermite | 3.403519 | 0.021253 | 0.321141 | 22.304178 | 1441.477997 | 0.644336 |
| RElbow | Kalman smoothing | 2.851629 | 0.017739 | 0.264593 | 18.567841 | 1196.752440 | 0.814467 |
| RElbow | Kalman prediction-only | 6.592791 | 0.041553 | 0.549963 | 36.399901 | 2155.569298 | 0.000000 |

- RWrist linear RMSE_norm按gap length 1/2/3/4为0.021179/0.020076/0.018018/0.017307。
- 完整位置、速度、加速度、jerk、入口/出口连续性、endpoint、路径长度和曲率指标按gap/joint/phase/method保存在benchmark CSV/JSON。
- 主要RWrist RMSE_norm：linear 0.019819、PCHIP 0.022681、Hermite 0.026315、Kalman smoothing 0.022746。只有linear进入最佳值10%带，因此provisional best on E001为linear；没有启动次级决胜或结果后调参。

## 真实缺口修复

- 使用linear修复RWrist 64-65、143、182-185共7帧；frame 0-1保持null且`repair_mask=false`。
- 64-65：context 61/62/67/68，confidence medium，最大逐帧位移0.058510 shoulder-width，入口/出口速度不连续性0.692649/3.093106 norm/s。
- 143：context 141/142/145/146，confidence high，最大逐帧位移0.149972，入口/出口不连续性1.929442/4.319544 norm/s。
- 182-185：context 176/181/186/187，confidence low，最大逐帧位移0.039001，入口/出口不连续性7.959980/1.071849 norm/s。
- 三段均无单帧位移超过0.5肩宽；boundary abnormal gap count为0。速度不连续性不是ground-truth误差，仍需结合视频人工检查，尤其182-185入口。
- repaired文件逐帧保留所有raw字段，新增repaired像素/归一化坐标、`repair_mask`、joint mask、method/source/gap/confidence和原始质量原因。observed frame没有平滑或替换。
- 8个occlusion error事件写入`corruption_candidate_list.json`并标记`deferred_to_T07C`；事件关节raw未修复。frame 64虽修复缺失RWrist，但同帧RElbow候选仍保持raw且joint repair mask为false。

## 输出与哈希

- manifest：`5d670f4a8f6020156c92c2439bad281b0c26b0286067fff92a026c4a4f5571bc`。
- benchmark CSV：`d59b0e4c7d866870ffa52bce71f045be7e082a65427a01396947bace533cf933`。
- benchmark JSON：`405a63fa1d33c1612c0d4e5c57f671611eb4caecbcbe740b815b4c98bfe4028d`。
- comparison PNG：`611fb82e101ffc3ebd8867defeb69251d78e39f437dab576af5e427d2039275e`。
- repaired JSONL：`870789ffac84cb00b7b9eaa144f1039a55795c1bbe387fcdce187f581f8488b2`。
- repaired CSV：`b59e34927d67a5912a5668e581f1e89207e463c112d46922546215eab38778c2`。
- repair summary：`8b2e8c47c0ab04fdb3f3b4dfee947c4b3b5c3be67e30f94d63f23c946d6ab58c`。
- corruption list：`36abcada0ee556770e525bd671f08c1660ccafe8dbfaeafc74816880ff6eb17f`。
- overlay：`f413a2f0f286915ebaf5c953cecbc6b4433339986710bcd1d7683fa5ca368eba`，H.264、1280x720、30 FPS、345帧，全片解码通过。

## 验证、错误和下一步

- 四个要求脚本及common module通过`py_compile`；四脚本`--help`通过。
- 独立验证`validation_passed=true`、errors为空：合成样本泄漏、分组字段、220条method结果、345帧JSONL/CSV一致性、raw逐字段不变、7帧repair mask、8事件延期和overlay全解码全部通过。
- PNG视觉检查可辨识四方法和四种长度；overlay抽查64、143、183，蓝色修复RWrist与状态文字正确。
- 失败与异常：无方法执行失败、无PCHIP/Hermite/Kalman数值异常、无>0.5肩宽边界异常。环境版本查询未设置`MPLCONFIGDIR`时出现Matplotlib临时cache提示，不影响实验；正式benchmark已显式使用`/tmp/humanvla-matplotlib`。
- 尚需人工复核：全部修复帧64-65、143、182-185；优先182-185，其次143和64-65。8个occlusion error事件继续留给T07C，本轮不处理。
- 当前停止，不开始T07C，不进行任何平滑滤波。

## T07B-R1人工复核固化（2026-07-14）

### Run信息与审计结论

- Run ID：`20260714_T07B_R1_MANUAL_FINALIZATION_001`。
- 目的：固化用户对真实缺口逐关节的人工复核，不改变合成基准、全局方法排名或raw数据。
- frame 64-65审计事实：T06C quality mask中BODY_25 index 3 `RElbow`均为`low_quality`，人工原因为`forearm_self_occlusion`；raw trajectory中原始像素坐标分别为`(490.177, 239.449)`和`(488.262, 239.457)`，`relbow_coordinate_available=true`、`relbow_effective_status=low_quality`。因此它们不是missing/invalid，也没有生成RElbow插值候选。
- 处理决定：保留上述原始RElbow坐标；`repair_applied=false`、`repair_acceptance=rejected`、`downstream_valid=false`、`reason=low_quality_observation_requires_quality_aware_refinement`、`defer_to_task=T07C`。
- RWrist 64-65、143、182-185均由人工判定`pass/accepted/high/downstream_valid=true`。182-185保留`boundary_continuity_warning=true`，对应入口速度不连续性原始精度`7.9599797880017285 norm/s`（报告值`7.959980`）。
- `repair_confidence`现为RElbow/RWrist逐关节人工置信度；原先按缺口长度自动给出的置信度保存在`automatic_repair_confidence`，没有丢失。

### 完整命令

```bash
/home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/finalize_t07b_manual_review.py \
  scripts/trajectory/validate_repaired_trajectory.py

/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/finalize_t07b_manual_review.py --help
/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_repaired_trajectory.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/finalize_t07b_manual_review.py \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --repaired-jsonl data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --repaired-csv data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.csv \
  --repair-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --synthetic-manifest results/trajectories/pick_place_pilot_v1_E001/synthetic_gap_manifest.csv \
  --benchmark-csv results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.csv \
  --benchmark-json results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.json \
  --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_repaired_trajectory.py \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --trajectory-summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --policy configs/dataset/t07b_gap_recovery_policy.json \
  --manifest results/trajectories/pick_place_pilot_v1_E001/synthetic_gap_manifest.csv \
  --benchmark-csv results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.csv \
  --benchmark-json results/trajectories/pick_place_pilot_v1_E001/gap_recovery_benchmark.json \
  --repaired-jsonl data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --repaired-csv data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.csv \
  --repair-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --corruption-list results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_list.json \
  --comparison-plot results/trajectories/pick_place_pilot_v1_E001/gap_recovery_comparison.png \
  --overlay results/trajectories/pick_place_pilot_v1_E001/repaired_trajectory_overlay.mp4
```

同一固化命令再次运行，三个获准更新的输出哈希完全相同，幂等复跑通过。

### 输出、验证与数据保护

- repaired JSONL SHA-256：`4a04a6e418fe2e0f875a92ed44a8507eaa4cc8dc5e2efe8320255ceae1fe7411`。
- repaired CSV SHA-256：`f55b38bc6b10cfa6626d35148c5939def0922c83ce5801b30d039874bd72f7b5`。
- actual repair summary SHA-256：`41ddcb4e585538bb6bb1ee94c8ecdde4e4a918b99aa563a2ea556c125184d1e1`。
- 独立验证结果：`validation_passed=true`、errors为空；345帧JSONL/CSV一致，raw字段逐字段未变，7帧RWrist人工状态正确，64-65 RElbow原始值未变，182-185警告值正确，overlay仍可完整解码。
- raw trajectory哈希保持`c29b2a66...5506`；T06C quality mask保持`b9839781...f273`。
- 44样本manifest保持`5d670f4a...571bc`；benchmark CSV/JSON保持`d59b0e4...9433`/`405a63fa...028d`，方法排名未变化，linear仍仅为`provisional best on E001`。
- 失败与异常：无脚本失败。人工拒绝的是64-65帧低质量RElbow观测用于下游，不是一个已经写入的RElbow插值结果；需避免将其误报为“撤销了肘部修复”。
- 当前停止，不开始T07C，不修改8个occlusion error候选，不进行插值扩展或平滑。
