# T07A Raw Upper-Limb Trajectory

## Run信息

- Run ID：`20260714_T07A_RAW_UPPER_LIMB_001`
- 日期：2026-07-14 CST
- 目的：仅从E001的T06C P001序列提取未滤波、未插值的RElbow/RWrist像素与Neck/肩宽归一化轨迹。
- 环境：Ubuntu 20.04；`motpose` Python 3.10；OpenCV 5.0.0、NumPy 2.2.6、Matplotlib 3.10.9、Pillow 12.2.0；FFmpeg/libx264。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。
- 是否可用于论文：可作为E001原型轨迹与质量分析记录；单视频结果不能外推为总体性能。

## 输入与哈希

- P001：`data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl`，SHA-256 `36ded0a2f3c903e2dc9613709dbd2454a5078a0fe838ccc5ed32e1743a76ee5a`。
- quality mask：`data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl`，SHA-256 `b98397817df55b93efe903469f1070a88349a30f95eedbc2e8c512b8f4ccf273`。
- phase frames：`data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl`，SHA-256 `a9b42220053136d3751cbf3de699680f5e63a1e4161b3e23bd53e60c0392301f`。
- T06C validation：`results/merged/pick_place_pilot_v1_E001_validation_summary.json`，SHA-256 `9d65c1605b95343def57d1f0563f270e30eba8b748c3663ae88e8867ad0f0393`。
- 源视频：`data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4`，SHA-256 `c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`。
- 完成后复核以上哈希全部未变化。

## 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/extract_upper_limb_trajectory.py \
  --p001 data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --t06c-validation results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --output-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output-csv data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.csv \
  --expected-frames 345

env -u PYTHONPATH MPLCONFIGDIR=/tmp/humanvla-matplotlib \
  /home/a531/anaconda3/envs/motpose/bin/python scripts/trajectory/analyze_raw_trajectory.py \
  --trajectory-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --p001 data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --t06c-validation results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --output-plot results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_plot.png \
  --expected-frames 345

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/render_raw_trajectory.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --trajectory-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_overlay.mp4 \
  --expected-frames 345 --history-frames 30

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_upper_limb_trajectory.py \
  --p001 data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --t06c-validation results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --trajectory-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --trajectory-csv data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.csv \
  --summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --plot results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_plot.png \
  --overlay results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_overlay.mp4 \
  --expected-frames 345
```

## 参数与数据规则

- 归一化：`origin=Neck(1)`；`scale=||(RShoulder(2)-LShoulder(5))||_2`；图像x向右、y向下。
- frame 0-1：所有像素、肩宽和归一化坐标均为JSON null。
- RWrist frame 64、65、143、182-185：像素与归一化坐标均为null，不填0、不插值。
- RElbow frame 64、65、143：保留raw数值，source/effective status均为low_quality；不得计为source-valid。
- RElbow frame 182-185：保留raw数值，source status为valid但manual unstable使effective status为low_quality。
- frame 226：仅使用P001 `pose_index=0`；已排除的反光`pose_index=1`不读取、不进入轨迹。
- 路径和逐帧位移只计算相邻帧均有坐标的边；缺失区间不跨越。
- 跳变检测：Tukey extreme，阈值=`Q3 + 3*IQR`；候选不自动删除或修复。
- 禁止并确认未使用：MidHip、髋/下肢、插值、Kalman、One Euro、Savitzky-Golay、纸盒检测、仿真映射。

## 定量结果

- 总帧数345；trajectory valid 336帧。
- RElbow：coordinate available 343帧；T06C source-valid 340帧；manual effective high-quality 336帧。坐标缺失区间仅0-1；low_quality/unstable为64、65、143、182-185。
- RWrist：valid/coordinate available 336帧；缺失区间0-1、64-65、143、182-185。人工强制关节缺失为64、65、143、182-185。
- 肩宽343帧：mean 165.425558709 px；population std 7.777305038 px；min 143.766790258 px；max 180.655605905 px。
- 肩宽突变阈值49.627667613 px；相邻变化超过全局均值30%的异常0个。
- RElbow归一化范围：x [-1.330856671, -0.520563476]，y [-0.391429540, 0.474371258]。
- RWrist归一化范围：x [-1.596031956, 0.617901672]，y [-0.793445564, 0.568244588]。
- 最大RElbow逐帧位移：65→66，0.323281195 shoulder-width。
- 最大RWrist逐帧位移：137→138，0.358744137 shoulder-width。
- 可疑跳变候选：55、64、66、68、72、90、138、140、144、178、180、224。
- reach至retract区间46-244：RElbow长度6.526922176，使用198条相邻边；RWrist长度8.213009177，使用188条边并因缺失跳过10条；均未跨缺口。
- 各phase帧数和有效率完整保存在`trajectory_summary.json`；最低RWrist有效率为place 14/18=77.7778%，reach 50/52=96.1538%，transport 35/36=97.2222%，其余操作phase为100%。

## 输出与哈希

- JSONL：`data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl`，345行，SHA-256 `d4317a6346e5c0c305ad7e50c32946ef0afaf042d182a691bca085ea2db07bf6`。
- CSV：`data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.csv`，345条数据行+表头，SHA-256 `ed1c3a45a8df334838c9764883ebd600860093ed5fb6fcc4accf70deb8b900b4`。
- summary：`results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json`，SHA-256 `1bc6a5c21c32e0fdfc11d37dd950045bac205e5f4937333c96675f8e598d7776`。
- plot：`results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_plot.png`，2880x1280 PNG，SHA-256 `7133e17df58492f826a721af51841a537a531c9e2ade2276c8aaec60b0416427`。
- overlay：`results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_overlay.mp4`，H.264、1280x720、30 FPS、345帧，SHA-256 `7126a09582bf929aa2e2e3e1750acdd1ca379dab35e591d93d5f0137300d9b54`。

## 验证、可视化与错误

- 四个脚本通过`py_compile`和`--help`。
- 独立验证`validation_passed=true`、errors为空；JSONL/CSV逐字段一致。
- 逐帧验证原始像素、肩宽和归一化公式；Neck归一化误差容限1e-9。
- 验证frame 0-1全坐标null、7个RWrist缺失帧null、低质量RElbow raw保留、frame 226只用pose 0。
- overlay全片FFmpeg解码成功；抽查0、1、2、55、64-66、68、72、90、138、140、143-144、178、180、182-185、224、226、244、344显示规则正确。
- 初次`--help`导入Matplotlib时因`~/.config/matplotlib`不可写产生cache warning；正式分析命令设置`MPLCONFIGDIR=/tmp/humanvla-matplotlib`，没有影响输出。
- 失败实验：无。没有自动消除可疑跳变。

## 原因分析与下一步

- 12个跳变候选由统计阈值产生，不等同于错误。64、66、144邻近已知缺失/低质量段；138、140、178、180可能包含真实快速阶段运动，其余需结合视频裁决。
- 建议人工重点复核：55、64、66、68、72、90、138、140、144、178、180、224，并记录`true_motion`或`pose_jump`。
- 当前停止。人工裁决前不进入滤波或轨迹修复；不开始纸盒检测、仿真映射、LeRobot转换或E002-E012。

---

## 人工复核补充运行

- Run ID：`20260714_T07A_REVIEW_SUPPLEMENT_001`
- 日期：2026-07-14 CST
- 目的：落实143-not-43人工修正，并在不改变原始坐标的前提下补充Neck与双肩绝对运动字段。
- 输入：与主运行相同的P001、quality mask、phase frames、T06C validation和E001源视频。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。
- 参数：`expected_frames=345`、`history_frames=30`、`overwrite=true`；只覆盖T07A派生输出。

### 人工规则

- 异常遮挡帧为frame 143，不是43；T07A遮挡集合为64、65、143、182-185。
- 放置到B点附近的Neck和双肩少量平移按正常躯干/肩部代偿解释，不作为检测错误。
- Neck、双肩、RElbow和可用RWrist绝对像素坐标保持T06C原值；未固定、修改、滤除或平滑。
- 首个有效身份帧为frame 2。新增Neck相对首个有效帧的dx/dy，以及Neck、RShoulder、LShoulder相邻帧dx/dy向量和欧氏位移字段。
- 后续仿真映射不得仅使用Neck相对轨迹；须保留绝对桌面路径与A/B参考。T07A没有检测纸盒或生成A/B坐标，不对其作伪造填充。

### 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/extract_upper_limb_trajectory.py \
  scripts/trajectory/analyze_raw_trajectory.py \
  scripts/trajectory/render_raw_trajectory.py \
  scripts/trajectory/validate_upper_limb_trajectory.py

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/extract_upper_limb_trajectory.py \
  --p001 data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --t06c-validation results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --output-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output-csv data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.csv \
  --expected-frames 345 --overwrite

env -u PYTHONPATH MPLCONFIGDIR=/tmp/humanvla-matplotlib \
  /home/a531/anaconda3/envs/motpose/bin/python scripts/trajectory/analyze_raw_trajectory.py \
  --trajectory-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --p001 data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --t06c-validation results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --output-plot results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_plot.png \
  --expected-frames 345 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/render_raw_trajectory.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --trajectory-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_overlay.mp4 \
  --expected-frames 345 --history-frames 30 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_upper_limb_trajectory.py \
  --p001 data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --t06c-validation results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --trajectory-jsonl data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --trajectory-csv data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.csv \
  --summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --plot results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_plot.png \
  --overlay results/trajectories/pick_place_pilot_v1_E001/raw_trajectory_overlay.mp4 \
  --expected-frames 345
```

### 真实结果

- 有效性统计不变：trajectory valid 336；RElbow coordinate 343/source-valid 340/effective high-quality 336；RWrist valid 336。
- frame 0-1所有坐标与位移为null；frame 2的Neck基准位移为(0,0)，三项逐帧位移为null；frame 3-344有342条连续Neck/双肩位移。
- Neck相对frame 2：dx范围[-7.850000, 48.933000] px，dy范围[-15.651000, 9.894000] px。
- 相邻帧位移均值/最大值：Neck 1.229844/13.804857 px；RShoulder 1.394922/16.714204 px；LShoulder 0.848750/11.785214 px。
- 肩宽统计保持mean 165.425559、std 7.777305、min 143.766790、max 180.655606 px，30%规则异常0帧。
- 12个Tukey跳变候选保持55、64、66、68、72、90、138、140、144、178、180、224；该统计候选不等同于人工异常，且不含错误写法frame 43。
- 独立验证`validation_passed=true`、errors为空；新增绝对运动公式、人工规则和未来映射约束检查全部通过。
- overlay仍为H.264、1280x720、30 FPS、345帧，全片解码通过；抽查143、185、226显示新增Neck绝对位移且质量状态正确。

### 输出哈希

- JSONL：`c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`。
- CSV：`e2ae2e8718c9cd6d4fe81dcac9983ac5bc1553ac947b1f486b0b752e04f4ab2c`。
- summary：`1268eac7581f8d59a20df22ebddce5f29da5f4e6d48367e0d083ee6b2fac0f28`。
- plot：`7133e17df58492f826a721af51841a537a531c9e2ade2276c8aaec60b0416427`。
- overlay：`a6a17372647dfcf31a8f3bd6627479ee12140a8a80d7b5f74479defb255688c8`。
- 五个T06C锁定输入哈希与主运行记录一致，未变化。

### 错误、边界与下一步

- 首次用系统`python3`执行`--help`时因其没有`cv2`而失败；随后使用既有`motpose`环境重新执行，四脚本`py_compile`和`--help`均通过。未安装或修改环境。
- 不把正常Neck/肩部代偿误写成检测错误；也不把统计跳变候选自动升级为错误。
- A/B绝对参考位置尚未检测或标注，是未来仿真映射的未解决输入；本轮没有运行仿真映射。
- 当前继续等待12个跳变候选的人工复核。不插值、不滤波，不处理E002-E012。

---

## 跳变候选人工复核材料

- Run ID：`20260714_T07A_JUMP_REVIEW_MATERIALS_001`
- 日期：2026-07-14 CST
- 目的：将T07A summary中的全部统计跳变候选整理为无预设结论的人工复核CSV、逐候选短片和汇总视频。
- 环境：既有`motpose` Python 3.10、OpenCV 5.0.0和FFmpeg/libx264。
- 输入：trajectory summary、345帧轨迹JSONL及E001源视频，全部只读。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。

### 完整命令和参数

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/build_jump_candidate_review.py

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_jump_candidate_review.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_jump_candidate_review.py \
  --summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --output-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --clips-dir results/trajectories/pick_place_pilot_v1_E001/jump_candidate_clips \
  --output-video results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.mp4 \
  --context-frames 5 --review-fps 6 --expected-candidates 12
```

### 输入哈希

- trajectory JSONL：`c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`。
- trajectory summary：`1268eac7581f8d59a20df22ebddce5f29da5f4e6d48367e0d083ee6b2fac0f28`。
- E001视频：`c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`。
- 生成前后哈希一致；轨迹JSONL/CSV和summary均未修改。

### 候选与输出

- 从`per_frame_displacement.*.suspicious_jumps`读取12项：RElbow 9项、RWrist 3项；to_frame为55、64、66、68、72、90、138、140、144、178、180、224，与summary顶层列表完全一致。
- CSV共12行，包含用户要求的17个核心字段，并附review起止帧和短片路径。`manual_label`、`manual_confidence`和`manual_note`全部为空，没有自动判错。
- 每项短片覆盖`from_frame-5`至`to_frame+5`，均为12个连续源帧、H.264、1280x720、6 FPS；12个短片全部完整解码。
- 画面显示当前frame/phase、Neck/双肩/RElbow/RWrist、候选关节局部绝对像素路径、归一化路径和红色候选边；缺失坐标不跨帧连接。
- 汇总视频为H.264、1280x720、6 FPS、144帧、24秒；全片解码通过。抽查JUMP_002、JUMP_007和JUMP_010，信息和候选红色边可见。
- 输出CSV SHA-256：`100d79758c6f2a79a3b3b7b2d5de1ae21aacc032afb4d20f024f942afbd9d888`。
- 汇总视频 SHA-256：`95e4fd06f17e53f3ac5c79f363110e56b78306fa5f2a57e93687db34e7d61b32`。
- 12个短片哈希清单的聚合SHA-256：`53536e37fed0294556a5b65d90457e231b15e2748ea7d08083af845878324e13`。

### 错误、限制和下一步

- 失败与异常：无。`py_compile`、`--help`、候选数量、CSV字段、空白人工字段、逐片帧数和视频全解码检查均通过。
- 自动触发只记录Tukey extreme规则及阈值，不表示检测错误。材料没有插值、滤波或修改轨迹。
- 当前停止，等待用户填写CSV中的三个manual字段；不进入后续滤波或仿真映射。

---

## 跳变候选人工裁决最终固化

- Run ID：`20260714_T07A_JUMP_REVIEW_FINALIZE_001`
- 日期：2026-07-14 CST
- 目的：验证12项人工裁决完整性，将原样裁决与分类统计固化到trajectory summary；不修改或修复raw轨迹。
- 输入：人工填写的`jump_candidate_review.csv`、固化前`trajectory_summary.json`及raw trajectory JSONL。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。

### 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/finalize_jump_review.py

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/finalize_jump_review.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/finalize_jump_review.py \
  --summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --expected-candidates 12 --overwrite
```

独立复核另用只读Python检查12个summary decisions与CSV三个manual字段逐项相等、分类计数相等、候选帧列表未变、所有repair/interpolation/filtering标志为false，并复算文件哈希。

### 人工字段与CSV格式验证

- 12/12行的`manual_label`、`manual_confidence`和`manual_note`均为非空；candidate_id严格为JUMP_001至JUMP_012，候选关节/帧/位移/置信度/肩宽/Neck位移均与summary和raw轨迹一致。
- manual confidence：high 9项、medium 3项，无非法值。
- 用户CSV存在表格编辑造成的辅助列右移：`review_start_frame`为空，原三项辅助值依次位于后一列，末尾匿名列保存真实clip path。三个manual字段及所有核心候选字段不受影响。
- 固化脚本仅在确认12行均符合这一统一布局后接受；辅助review metadata没有参与裁决固化，用户CSV未被改写。
- 首次严格运行因匿名列含数据而停止，退出码1，summary哈希仍为固化前`1268eac7...c0f28`。查明统一列右移模式后扩展只读验证规则，再次运行成功；没有丢弃匿名列内容。

### 人工裁决统计

- manual label原样计数：`occlusion_error=6`、`openpose_jitter=1`、`real_motion=3`、自定义中文标签`骨架完全没有在手臂上=2`。
- mark-only计数：openpose_jitter 1、occlusion_error 6、normalization_artifact 0；三类均未修复。
- preserve-motion计数：real_motion 3、phase_boundary_motion 0、human_compensation 0；没有删除任何候选。11项为同阶段边，1项跨阶段边界，跨边界候选同样保留。
- 关节计数：RElbow 9、RWrist 3。RElbow为occlusion 5/openpose jitter 1/real motion 3；RWrist为occlusion 1/自定义标签2。
- 两项自定义中文标签未擅自改名或映射，summary以`preserve_verbatim_custom_label_mark_only_no_repair`保存。

### 输出、哈希和处理边界

- `trajectory_summary.json`新增`jump_candidate_manual_review`，包含12项逐候选原样决定、分类统计、CSV哈希、raw轨迹哈希及处理政策。
- summary固化后SHA-256：`acb243193a9781210038bbb8d6917bf9a081c4f2705f275c13aaa59698e18786`。
- 人工CSV SHA-256：`cddc0760b078b633270174a378291689fa9daf44db43d8ea5476cd5d269180b1`，固化前后未变化。
- raw trajectory JSONL SHA-256保持`c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`；CSV保持`e2ae2e8718c9cd6d4fe81dcac9983ac5bc1553ac947b1f486b0b752e04f4ab2c`。
- 独立一致性检查通过。没有删除真实运动、阶段边界运动或人体代偿；没有修复错误标签，没有插值或滤波。
- 当前停止，等待Claude最终验收，不开始T07B或其他实验。

---

## T07A-R1标签与CSV schema最小清理

- Run ID：`20260714_T07A_R1_CLEANUP_001`
- 日期：2026-07-14 CST
- 目的：将人工标签收敛到批准枚举、规范12行CSV辅助字段，并重新固化summary；不改变候选或raw trajectory。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。

### 输入状态与裁决

- 本轮开始时用户CSV已被外部更新为规范20列，末尾Unnamed列已不存在，12个辅助字段和MP4路径已归位；因此本轮没有把旧错位布局误当成当前事实。
- 修复前CSV SHA-256：`d7fc8d4c0d1bb5a6e113916cf2f62f389cf29b3bf56ead66b3ab71a23e0ce97a`。
- 修复前summary SHA-256：`acb243193a9781210038bbb8d6917bf9a081c4f2705f275c13aaa59698e18786`。
- JUMP_001按用户指定改为`normalization_artifact/high`，备注精确写为“肘关节始终正常贴合，绝对像素位移很小，肩宽变化导致归一化位移被放大。”
- JUMP_005沿用用户当前最终标签`occlusion_error/high`，备注具体化为“右肘关键点因手臂遮挡发生异常跳变。”，不再只写异常跳变。
- JUMP_010和JUMP_011统一为`occlusion_error/high`；原有右腕误定位原因保留，并补回要求的原句“骨架完全没有在手臂上”。

### 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/clean_jump_review_r1.py \
  scripts/trajectory/finalize_jump_review.py

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/clean_jump_review_r1.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/clean_jump_review_r1.py \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --expected-candidates 12 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/finalize_jump_review.py \
  --summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/trajectory_summary.json \
  --expected-candidates 12 --overwrite
```

### Schema验证与真实统计

- 修复后CSV严格为20个命名字段、12行；无空表头或Unnamed列。每行`review_start_frame=from_frame-5`、`review_end_frame=to_frame+5`，12个clip_path均指向实际MP4。
- 12行manual label/confidence/note全部非空，中文备注完整保留。
- 标签只来自允许枚举；实际计数为`normalization_artifact=1`、`occlusion_error=8`、`real_motion=3`，其余允许标签均为0。
- RElbow：normalization artifact 1、occlusion error 5、real motion 3；RWrist：occlusion error 3。high confidence 9、medium 3。
- 同阶段候选11、跨阶段边界候选1；候选总数仍为12，候选帧仍为55、64、66、68、72、90、138、140、144、178、180、224。
- 修复后CSV SHA-256：`0a40f2a78a4a26720132f0c2cd06a2a150949906431f41abb7e5dba637ebbc84`。这是人工备注/标签及schema规范化造成的受控变更。
- 重新固化后summary SHA-256：`03eb575160c5998eca970faf1cf863d23f81bde22c74324d74d0651ab6fa3528`。

### 验证、失败与处理边界

- 两个脚本通过`py_compile`和`--help`。独立检查通过：字段顺序、12个clip文件、允许标签、指定四项裁决、summary计数和12项decision全部一致。
- raw trajectory JSONL SHA-256保持`c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`；raw CSV保持`e2ae2e8718c9cd6d4fe81dcac9983ac5bc1553ac947b1f486b0b752e04f4ab2c`。
- 失败与异常：无。当前CSV在运行前已无Unnamed列，这是观测事实，不虚构删除动作；清理脚本仍强制输出规范schema并验证。
- normalization artifact和occlusion error只标记，未修复。未删除真实运动、阶段边界运动或正常人体代偿，未插值、滤波或修改OpenPose输入。
- 当前停止，等待Claude最终验收，不开始T07B。
