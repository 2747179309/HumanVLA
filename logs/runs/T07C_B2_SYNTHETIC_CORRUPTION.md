# T07C-B2 Synthetic Corruption Dataset

## Run信息

- Run ID：`20260714_T07C_B2_SYNTHETIC_CORRUPTION_001`
- 日期：2026-07-14 CST
- 目的：从E001严格干净raw窗口构建ground-truth已知的四类合成污染配对数据，只完成数据集，不运行传统滤波或恢复。
- 环境：`motpose` Python 3.10.20、NumPy 2.2.6。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，工作区含未提交修改。
- 是否可用于论文：可作为E001合成污染原型基准输入；尚未运行B3/B4方法，且单episode结果不能外推到其他视频。

## 预注册配置

- 配置：`configs/dataset/t07c_b2_synthetic_corruption.json`。
- 配置在首次dataset生成前固定，SHA-256 `35785fabb07bde8da38ed11bea0968e49e6f233e2ae2526c9e311778d8256055`。
- 全局seed `20260714`；clean窗口8帧，guard 2帧。
- split固定为train 2-120、val 121-206、test 207-344，边界与phase边界一致。
- 目标关节RElbow/RWrist；四类污染Gaussian noise、burst jump、continuous drift、short missing；每类low/medium/high三档。
- clean门槛要求Neck/RShoulder/RElbow/RWrist同时为raw valid、selected raw、无repair、type valid、source events为空且同phase。

## 输入与哈希

- raw trajectory：`c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`。
- T07C-A mask：`9d9654dce8da02a4d28e4109af1a6f257ef44b30cf77169f1e41be9d615f1b53`。
- 生成前后配置、raw和mask哈希完全不变。

## 完整命令

```bash
/home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/build_synthetic_corruption_dataset.py \
  scripts/trajectory/validate_synthetic_corruption_dataset.py

/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_synthetic_corruption_dataset.py --help
/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_synthetic_corruption_dataset.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_synthetic_corruption_dataset.py \
  --config configs/dataset/t07c_b2_synthetic_corruption.json \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --corruption-mask data/trajectories/pick_place_pilot_v1_E001/frame_joint_corruption_mask.jsonl \
  --output-jsonl data/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_dataset.jsonl \
  --output-metadata results/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_metadata.json

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_synthetic_corruption_dataset.py \
  --config configs/dataset/t07c_b2_synthetic_corruption.json \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --corruption-mask data/trajectories/pick_place_pilot_v1_E001/frame_joint_corruption_mask.jsonl \
  --dataset data/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_dataset.jsonl \
  --metadata results/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_metadata.json
```

确定性复跑使用同一命令加`--overwrite`，dataset与metadata哈希完全一致。

## 真实结果

- 14个clean base windows；train/val/test为7/3/4个。
- 336个配对样本；train/val/test为168/72/96。
- RElbow/RWrist各168个；四类污染各84个；low/medium/high各112个。
- 每个base window恰好24个变体：2关节×4污染×3强度。
- 独立源帧数train 56、val 24、test 32；任意split间源帧交集为空。
- phase窗口覆盖：train idle/reach/align/grasp；val lift/transport/release；test retract/idle。
- Gaussian low/medium/high平均位移为1.9712/6.4238/12.4621 px。
- Burst low/medium/high固定幅度样本均值为13.4156/26.8313/50.3087 px，持续1/2/3帧。
- Drift low/medium/high受影响帧平均位移为4.8911/11.7387/24.4556 px，内部持续6帧。
- Missing low/medium/high总缺失观测为28/56/112，对应每样本1/2/4帧。

## 验证、异常与输出

- 独立验证`validation_passed=true`、errors为空。
- 验证逐样本clean坐标与T07A raw完全一致；四参考关节均满足strict-clean门槛；没有accepted repair、真实异常帧或跨phase窗口作为真值。
- 验证四类污染的区间、duration、offset、线性alpha和null位置符合预注册数学定义。
- dataset SHA-256：`ee84857e856986a43c2d8d24bc96ce6d1ad0fd2a3c9d06e2fd0599093b724d4e`。
- metadata SHA-256：`aacde9f18ec6b463ecefc3232269d9bfee2398bec8769698de53771752fd0666`。
- 教学指南SHA-256：`fdf90a30e111f4914cfac4c9236231e1c6e0bbe224f18297e9b5f2ca9c0acf1a`。
- 可视化结果：本阶段不要求或生成恢复结果图；指南用真实`SYN_0005`表格展示完整clean-to-corrupted转换。
- 失败与异常：无生成或验证失败。局限是单episode且split阶段分布不同，后续结果必须按phase报告并谨慎解释。
- 下一步：先进行B2质量审查；当前停止，不开始T07C-B3传统滤波。
