# T07C-A Corruption Candidate Review Materials

## Run信息

- Run ID：`20260714_T07C_A_REVIEW_MATERIALS_001`
- 日期：2026-07-14 CST
- 实验目的：把9个既有异常跳变事件、frame 64-65 RElbow低质量事件和frame 182-185边界连续性警告整理为逐帧错误判定所需的人工复核材料。
- 当前阶段：复核材料完成，等待人工逐帧裁决；最终frame-joint corruption mask尚未生成。
- 环境：`motpose` Python 3.10.20、OpenCV 5.0.0、FFmpeg 4.2.7/libx264。
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。
- 是否可以用于论文：当前仅为标注与质量审计材料；没有完成人工逐帧判定，不能作为滤波输入或最终实验结果。

## 输入及哈希

- `jump_candidate_review.csv`：`0a40f2a78a4a26720132f0c2cd06a2a150949906431f41abb7e5dba637ebbc84`
- raw trajectory：`c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`
- repaired trajectory：`4a04a6e418fe2e0f875a92ed44a8507eaa4cc8dc5e2efe8320255ceae1fe7411`
- T06C quality mask：`b98397817df55b93efe903469f1070a88349a30f95eedbc2e8c512b8f4ccf273`
- T07B actual repair summary：`41ddcb4e585538bb6bb1ee94c8ecdde4e4a918b99aa563a2ea556c125184d1e1`
- E001视频：`c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`

生成后以上输入哈希全部不变。

## 参数与完整命令

- `context_frames=8`：事件from frame前8帧和to frame后8帧。
- `review_fps=6`：慢放人工复核。
- 跳变事件只选8个`occlusion_error`和1个`normalization_artifact`；3个已判定`real_motion`不重复复核。

```bash
/home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/build_corruption_candidate_review.py \
  scripts/trajectory/validate_corruption_review_materials.py

/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_corruption_candidate_review.py --help
/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_corruption_review_materials.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_corruption_candidate_review.py \
  --jump-review results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --repaired-trajectory data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --repair-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --output-csv results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.csv \
  --clips-dir results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_clips \
  --output-video results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.mp4 \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review_summary.json \
  --context-frames 8 --review-fps 6

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_corruption_review_materials.py \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.csv \
  --clips-dir results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_clips \
  --review-video results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.mp4 \
  --summary results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review_summary.json \
  --jump-review results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --repaired-trajectory data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --repair-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --final-mask data/trajectories/pick_place_pilot_v1_E001/frame_joint_corruption_mask.jsonl
```

## 输出与定量结果

- 复核CSV：11行事件、30列；8个本轮人工字段均为空。SHA-256 `474f7c1e95db17db17a3f9df6c47a98bdfce48c599cbc238ce6309e923282bef`。
- 候选组成：8个occlusion error、1个normalization artifact、1个T06C RElbow low-quality区间、1个T07B RWrist boundary warning区间。
- 11个独立H.264片段：前10个各18帧；182-185区间片段20帧；均为1280x720、6 FPS。
- 汇总视频：H.264、1280x720、6 FPS、200帧，SHA-256 `93fd783cf35eedddc395f00459fbcf00c6911b59aa1b11f171b2e8c438867a3e`。
- 机器可读summary：SHA-256 `165bd0ef65d57dd228adb38d8228d15fe7f368c6bc7b35c7f941fe0da5527911`。
- 每帧画面显示原始上肢骨架、raw与repaired局部轨迹、Neck、肩宽、当前关节置信度、动作阶段、候选from/to和复核窗口。

## 验证、异常与下一步

- 独立验证：`validation_passed=true`、errors为空；11行/11片段覆盖正确，人工字段全空，汇总视频全片FFmpeg解码通过。
- 视觉抽查：JUMP_010 frame 177和boundary frame 184信息层、骨架、raw/repaired轨迹与候选标识可读。
- 未生成`frame_joint_corruption_mask.jsonl`。这是有意的安全门槛：当前没有人工逐帧错误端点判定，自动生成会违反“不得自动决定或mask候选”。
- 未执行过滤、插值、轨迹覆盖或候选自动删除。
- 失败与异常：无脚本或视频编码失败。当前唯一未完成项是人工逐帧裁决及其后的1380行最终mask。
- 下一步：用户填写`corruption_candidate_review.csv`的8个manual字段后，验证每个事件的错误帧，再生成345帧×4关节mask。当前停止等待，不开始滤波。

## 人工复核视频布局修订（2026-07-14）

- 修订目的：原左上角不透明信息框遮挡头部、Neck、双肩和部分上臂，仅重新渲染复核材料。
- 代码变更：生成脚本新增`--render-only`，将现有`corruption_candidate_review.csv`作为只读输入；禁止重写CSV，并在渲染前后核对其哈希。
- 新布局：信息面板移动到画面底部桌面前沿，使用112像素高半透明背景；只显示candidate_id、frame、joint、phase、confidence和source label。红色候选提示放在同一底栏右侧，不覆盖人体。
- 移除画面中的次要数值和人体附近红色端点圈；raw骨架、raw/repaired轨迹及Neck-双肩尺度线保持显示。

完整重渲染命令：

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_corruption_candidate_review.py \
  --jump-review results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --repaired-trajectory data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --repair-summary results/trajectories/pick_place_pilot_v1_E001/actual_gap_repair_summary.json \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --output-csv results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.csv \
  --clips-dir results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_clips \
  --output-video results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.mp4 \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review_summary.json \
  --context-frames 8 --review-fps 6 --render-only --overwrite
```

- 复核CSV重渲染前后SHA-256均为`474f7c1e95db17db17a3f9df6c47a98bdfce48c599cbc238ce6309e923282bef`。
- raw/repaired trajectory、quality mask、jump review和T07B summary哈希均与首次材料生成时一致。
- 新汇总视频SHA-256：`e6d9400e0fd1fc9ca7d5c479f72066c59cbb390bf11dccd8bc700ba199dd0d22`。
- 新summary SHA-256：`85c9779471cb267ed08f60a49f6d0b55e03ca2f3dbb2b018df213ae318a4003b`。
- 验证：11个片段仍为H.264、1280x720、6 FPS；前10个18帧、边界片段20帧。汇总视频200帧，全片解码通过。
- 视觉抽查JUMP_010 frame 177：人体头部、Neck、双肩、右肘和右腕无遮挡，底栏文本及红色提示可读。
- 未运行OpenPose、关联、轨迹计算、插值或滤波；未生成最终corruption mask。

## 最终逐帧逐关节mask（2026-07-14）

### Run信息与层级语义

- Run ID：`20260714_T07C_A_CORRUPTION_MASK_001`。
- 人工依据：用户填写后的`corruption_candidate_review.csv`，SHA-256 `d6a2f289aeb7f642c42c2d5c763477389fb635b0bbe12adde542c2b7c556bac1`。生成过程只读该文件，不修改、重映射或推翻人工错误帧判断。
- raw层：`manual_error_frames`只决定原始OpenPose观测是否有效；raw无效不直接传播为repaired无效。
- repaired层：只承认T07B已写入、人工accepted且`downstream_valid=true`的7个RWrist修复帧。
- 下游层：`selected_downstream_source`只允许`raw/repaired/none`。downweight事件可选择raw但显式标记downweight；defer事件选择none并延期T07C-B。
- 重复事件按`frame_index + joint_name`聚合为唯一记录，所有来源保存在`source_event_ids`和`manual_evidence`；不同action同时保存在`proposed_actions`。

### 完整命令

```bash
/home/a531/anaconda3/envs/motpose/bin/python -m py_compile \
  scripts/trajectory/build_frame_joint_corruption_mask.py \
  scripts/trajectory/validate_frame_joint_corruption_mask.py

/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_frame_joint_corruption_mask.py --help
/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_frame_joint_corruption_mask.py --help

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/build_frame_joint_corruption_mask.py \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.csv \
  --jump-review results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --repaired-trajectory data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --output-jsonl data/trajectories/pick_place_pilot_v1_E001/frame_joint_corruption_mask.jsonl \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/corruption_mask_summary.json \
  --output-overlay results/trajectories/pick_place_pilot_v1_E001/corruption_mask_overlay.mp4

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/trajectory/validate_frame_joint_corruption_mask.py \
  --mask data/trajectories/pick_place_pilot_v1_E001/frame_joint_corruption_mask.jsonl \
  --summary results/trajectories/pick_place_pilot_v1_E001/corruption_mask_summary.json \
  --overlay results/trajectories/pick_place_pilot_v1_E001/corruption_mask_overlay.mp4 \
  --review-csv results/trajectories/pick_place_pilot_v1_E001/corruption_candidate_review.csv \
  --jump-review results/trajectories/pick_place_pilot_v1_E001/jump_candidate_review.csv \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --repaired-trajectory data/trajectories/pick_place_pilot_v1_E001/repaired_upper_limb_trajectory.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4
```

同参数使用`--overwrite`确定性复跑，三个输出哈希完全一致。

### 真实统计结果

- 总记录1380：345帧×Neck/RShoulder/RElbow/RWrist各345行，无重复key。
- raw有效/无效：Neck 343/2，RShoulder 343/2，RElbow 313/32，RWrist 331/14；总raw无效50条。
- repaired available/valid：仅RWrist 7/7，其他关节均0。
- selected source：raw 1339、repaired 7、none 34；downstream valid共1346条。
- 主corruption type：valid 1330、normalization artifact 2、occlusion error 32、real motion 6、openpose jitter 6、low-quality observation 4。182-185的boundary warning作为并行类型和布尔字段保存，因此不覆盖其raw层openpose jitter主类型。
- action：keep 1330、mask 21、downweight 10、defer 19。
- 44条记录含多个source；无error/valid人工证据冲突。RElbow 72-74共3条存在mask/downweight action差异，`manual_action_conflict=true`并保留两种action和全部事件证据。

### 关键帧结果

- RWrist 64-65、143、182-185：raw无效；7帧repair均available/valid/accepted，selected=`repaired`且downstream valid。
- RElbow 64-65：raw无效、无repair、selected=`none`、downstream invalid、延期T07C-B。
- RWrist 178-179：raw无效且无accepted repair，selected=`none`、downstream invalid、延期T07C-B。
- RWrist 182-185：除使用accepted repair外，`boundary_continuity_warning=true`。
- RElbow 54-55：raw有效、selected=`raw`、action=`keep`，`normalization_scale_warning=true`，没有自动mask。
- RElbow 129-143：保留人工low-confidence uncertain/defer证据，selected=`none`并延期T07C-B；没有把action改写为mask。

### 输出、验证与数据保护

- mask SHA-256：`9d9654dce8da02a4d28e4109af1a6f257ef44b30cf77169f1e41be9d615f1b53`。
- summary SHA-256：`e7246a07f2451d64b3fcb669be6b8212b389b1b58b44bfcad527f49343ede3bd`。
- overlay SHA-256：`831489aca5d61ec2f01a73af5a6015c20b05cc19ef1a5f67014c21999313f659`；H.264、1280x720、30 FPS、345帧，全片解码通过。
- 独立验证`validation_passed=true`、errors为空：覆盖/唯一性、三层语义、关键帧、重复source、defer、normalization warning、边界warning和视频解码全部通过。
- 视觉抽查frame 64和183：红色表示raw无可用下游值、青色表示selected repaired、绿色表示selected raw；底栏不遮挡人体。
- 人工CSV、jump review、raw/repaired trajectory、quality mask和视频哈希在生成前后完全不变。
- 未执行任何滤波、新插值、OpenPose、关联、轨迹覆盖或T07C-B处理。
- 当前停止，等待Claude验收。
