# T06C E001 Perception Pipeline

## Run 信息

- Run ID：`20260713_T06C_E001_001`
- 日期：2026-07-13 13:56 CST
- 代码版本：Git `231fe97dc5788b0c5d40b677c0bf7f116b1b8182`，运行时工作区含未提交修改。
- 目的：仅对 `pick_place_pilot_v1_E001` 执行DeepSORT、OpenPose BODY_25、pose-track关联、上半身质量掩码和动作标签合并。
- 最终状态：**自动流水线完成，等待人工复核**。DeepSORT成功；OpenPose后续在普通宿主机终端成功；关联、质量掩码、动作阶段合并、可视化和独立验证已完成。frame 226额外pose及7个low-quality帧尚未人工裁决。
- 是否可用于论文：当前可作为流水线实现与原型统计记录；frame 226和低质量帧完成人工复核前，不作为最终论文定量结果。

## 输入

- 视频：`data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4`
- 固定 `video_id`：`pick_place_pilot_v1_E001`
- 视频SHA-256：`c29458cd3b2f638ad7ca3d63c44bf17aa442c5954f311a1a7f070b1b814745a2`
- 动作frame标签：`data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl`，345行，SHA-256 `a9b42220053136d3751cbf3de699680f5e63a1e4161b3e23bd53e60c0392301f`
- 任务指定的 `E001_action_phase_annotations.csv` 实际不存在；唯一修正版为 `E001_action_phase_annotations_corrected.csv`，SHA-256 `8d972c7c70418b7220fb947f6d511067c909c611919da637a3b46936631b5409`。
- YOLO模型：`yolov8n.pt`，SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`。
- BODY_25模型：`tools/openpose/models/pose/body_25/pose_iter_584000.caffemodel`，SHA-256 `44e3d7ebd8c8b62d4366d67127f1b562611a9e8fd0f4f3cdeeb4bb4a6ed12be6`。

## 初次Codex受限环境检查（历史记录）

- GPU PCI设备和NVIDIA 550.144.03内核模块可见。
- `/dev/nvidia*` 设备节点不存在。
- `nvidia-smi`：失败，`couldn't communicate with the NVIDIA driver`。
- PyTorch 2.5.1+cu121：`torch.cuda.is_available()=false`。
- 本地OpenPose是CUDA构建并链接CUDA 11.3；现有二进制不能在当前状态下退回CPU执行。
- 未修改NVIDIA驱动、设备节点、系统CUDA或系统配置。

## DeepSORT完整命令

```bash
/home/a531/anaconda3/envs/motpose/bin/python scripts/mot/run_deepsort.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --video-id pick_place_pilot_v1_E001 \
  --model ./yolov8n.pt \
  --output-root results/mot \
  --conf 0.3 \
  --iou 0.45 \
  --imgsz 640 \
  --device cpu \
  --max-age 30 \
  --n-init 3 \
  --nn-budget 100 \
  --max-cosine-distance 0.2 \
  --max-iou-distance 0.7 \
  --seed 42 \
  --run-id 20260713_T06C_E001_MOT_001
```

## DeepSORT结果

- 处理帧：345/345；person检测：345个。
- 原始track总数：1；短track（少于5帧）：0；未删除任何原始track。
- `track_id=1`：frame 2-344，343帧，跨度343帧，内部缺口0，平均检测置信度0.754752，最小0.362280，最大0.908885。
- frame 0-1没有confirmed track，原因是 `n_init=3` 确认前不输出轨迹；未回溯或插值身份。
- track 1是唯一连续轨迹。抽查frame 2、45、100、172、244、300、344均为同一操作者，未观察到ID切换。
- `track_id=1 -> P001` 写入临时subject map，状态为 `provisional_needs_human_confirmation`；不声称已经CVAT或用户人工验收。
- 跟踪视频：H.264、1280x720、30 FPS、345帧、11.5秒，完整解码通过。

## OpenPose诊断命令与错误

使用E001的frame 0进行有界CPU回退探针：

```bash
ffmpeg -v error \
  -i data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  -frames:v 1 /tmp/t06c_openpose_cpu_probe/images/frame000.jpg

export CUDA_HOME=/home/a531/CUDA11.3.0
export LD_LIBRARY_PATH="$CUDA_HOME/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
/usr/bin/time -f 'elapsed_sec=%e' \
  tools/openpose/build/examples/openpose/openpose.bin \
  --image_dir /tmp/t06c_openpose_cpu_probe/images \
  --model_folder tools/openpose/models/ \
  --model_pose BODY_25 \
  --net_resolution=-1x368 \
  --number_people_max 6 \
  --num_gpu 0 \
  --display 0 \
  --render_pose 0 \
  --write_json /tmp/t06c_openpose_cpu_probe/json
```

- 返回码：255；耗时0.20秒。
- 原始错误：`Cuda check failed (100 vs. 0): no CUDA-capable device is detected`。
- 失败发生在初始化阶段，没有生成BODY_25 JSON。
- 因单帧探针已证明现有构建不能运行，没有启动完整345帧OpenPose命令，也没有创建空raw JSON目录冒充输出。

## 输出

- `results/mot/pick_place_pilot_v1_E001/tracks_raw.jsonl`，343行，SHA-256 `d5dff496bf7df73f8b280150ff71558c67271a3cd80ba918427ca9cc81dba55c`。
- `results/mot/pick_place_pilot_v1_E001/tracked.mp4`，SHA-256 `9a6058ce6e8af6da15379ea84475f356433d99e026fed8ad43680ef086756798`。
- `results/mot/pick_place_pilot_v1_E001/mot/gt.txt`、`labels.txt`、`metadata.json`。
- `results/mot/pick_place_pilot_v1_E001/track_review.csv`。
- `results/mot/pick_place_pilot_v1_E001/track_review_contact_sheet.jpg`，SHA-256 `7ba4afa4e56443fc2a28841601c73ed7d4880e5ed7f00c13519a051839e84710`。
- `data/mot/subject_maps/pick_place_pilot_v1_E001.csv`。

## 初次受限环境运行时未生成的项目（历史记录，已由后续宿主机运行解除）

- 初次Codex运行没有生成OpenPose `raw_json/`或`rendered.mp4`；随后由宿主机运行生成，真实结果见本日志后续章节。
- 初次运行没有执行pose-track association、质量掩码、骨架动作合并或merged overlay；随后已使用真实宿主机BODY_25输出完成。
- 初次运行时OpenPose检出率、关联率和核心关节指标不可计算，因此当时没有填0或编造；后续真实统计见本日志后续章节。
- 初次运行未做动作阶段关键边界骨架检查；后续已对真实overlay完成抽查。

## 初次受限环境运行时的风险与处置（历史记录）

- 当时主阻塞是Codex受限环境缺少 `/dev/nvidia*`，不是模型或脚本缺失；宿主机随后确认GPU正常并完成OpenPose。
- 在用户批准系统级排查前，不创建设备节点、不重载驱动、不重启系统，也不重新编译CPU版OpenPose。
- 后续实际复用了现有MOT raw；用户已确认track 1映射P001，宿主机OpenPose及下游步骤已完成。
- 未处理E002-E012，未运行纸盒检测、滤波、插值、仿真映射、LeRobot转换或训练。

## 宿主机OpenPose恢复结果

- 用户在普通宿主机终端执行`scripts/run_t06c_openpose_host.sh`；Codex受限环境未实际运行OpenPose。
- 单帧BODY_25探针通过；完整视频输出345个连续JSON，`detected_frames=345`，344帧检测1人、1帧检测2人，格式异常0，confidence大于1的值0。
- 双人/双pose帧为frame 226：`pose_index=0`有14个有效关键点且四个核心关节均存在；`pose_index=1`仅3个有效关键点，Neck缺失。两副原始pose均未修改。
- `rendered.mp4`为H.264、1280x720、30 FPS、345帧，完整解码通过。
- 原始JSON目录锁定哈希：`b068dc2db1de56feb714cfb18e8f15514e52d1c05c9c9c0b935dc0645d522c5e`，关联前后相同。

## T06C下游完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/association/associate_single_operator.py \
  --video-id pick_place_pilot_v1_E001 \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --pose-json-dir results/openpose/pick_place_pilot_v1_E001/raw_json \
  --mot-tracks results/mot/pick_place_pilot_v1_E001/tracks_raw.jsonl \
  --subject-map data/mot/subject_maps/pick_place_pilot_v1_E001.csv \
  --output-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --summary results/association/pick_place_pilot_v1_E001/summary.json \
  --manual-review results/association/pick_place_pilot_v1_E001/manual_review.csv \
  --expected-frames 345 --iou-weight 0.6 --center-weight 0.4 \
  --cost-threshold 0.6 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/build_upper_body_sequence.py \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --subject-output data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask-output data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --joint-stats results/merged/pick_place_pilot_v1_E001_joint_stats.json \
  --expected-frames 345 --confidence-threshold 0.3 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/render_pose_phase_overlay.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --subject-jsonl data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --output results/merged/pick_place_pilot_v1_E001_pose_phase_overlay.mp4 \
  --expected-frames 345

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/validate_e001_perception.py \
  --pose-json-dir results/openpose/pick_place_pilot_v1_E001/raw_json \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --association-summary results/association/pick_place_pilot_v1_E001/summary.json \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --subject-jsonl data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --joint-stats results/merged/pick_place_pilot_v1_E001_joint_stats.json \
  --overlay results/merged/pick_place_pilot_v1_E001_pose_phase_overlay.mp4 \
  --output-summary results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --expected-frames 345
```

## 参数试运行与最终关联

- 使用T04的`cost_threshold=0.5`试运行：306/343 matched，37 unmatched tracks，40 unmatched poses。该试运行结果随后由最终派生输出覆盖，但命令参数和真实统计保留在本日志。
- 被拒帧的最佳候选最大代价0.561254、最低IoU 0.267540、最大归一化中心距离0.323350；全部为上半身骨架框比完整人物框小造成，且无第二个竞争人物。
- 最终使用`cost_threshold=0.6`：343/343个确认轨迹实例matched，关联率1.0，unmatched track 0。匹配代价均值0.370944、最小0.234783、最大0.561254。
- 全部346副原始pose均进入关联JSONL且逐值保持：343副绑定P001；frame 0、1各1副因无确认轨迹保持unmatched；frame 226的`pose_index=1`作为额外残缺pose保持unmatched并写入人工检查CSV。

## 上半身质量与阶段统计

- P001逐帧序列345条：valid 336、low_quality 7、missing 2、ambiguous 0。
- missing：frame 0-1，`frame_valid=false`，`exclusion_reason=no_confirmed_track_identity`。
- low_quality：frame 64、65、143、182、183、184、185；这些帧仍有至少一个核心关节有效，因此`frame_valid=true`。
- 核心关节`conf>0`有效率（确认轨迹帧2-344）：Neck 343/343=100%；RShoulder 343/343=100%；RElbow 343/343=100%；RWrist 336/343=97.959%。
- 核心关节`conf>=0.3`质量通过率：Neck 100%；RShoulder 100%；RElbow 340/343=99.125%；RWrist 336/343=97.959%。
- 确认轨迹帧原始confidence均值±总体标准差：Neck 0.785364±0.038529；RShoulder 0.709966±0.052827；RElbow 0.729429±0.116298；RWrist 0.716365±0.134937。
- 各动作阶段的四核心关节逐项检出率和质量通过率已写入`results/merged/pick_place_pilot_v1_E001_joint_stats.json`；最低项是place阶段RWrist，14/18=77.778%。
- 质量规则只使用Neck、RShoulder、RElbow和RWrist。MidHip只作辅助统计，膝、踝、脚缺失没有导致任何整帧invalid。未裁剪、归一化、滤波或插值关键点。

## 可视化、验证和输出

- 合并overlay：H.264、1280x720、30 FPS、345帧，全量解码通过。显示P001框、BODY_25、frame_index、双语动作阶段、四核心关节状态及missing/low_quality告警。
- 视觉抽查关键边界：45-47、96-98、105-107、119-121、138-140、174-176、192-194、205-208、243-246；显示阶段切换与T06B人工标签一致。
- 独立验证最终`validation_passed=true`、errors为空；验证全部346副raw pose逐值保持、P001同帧最多一副、frame 0-1策略、345帧动作字段一致、核心关节帧级规则和视频全量解码。
- 关联JSONL SHA-256：`345b9e478214f9a53c3feb9567d146da2f32a8598bf7ebeead4ec0d512bbf5cd`。
- P001合并序列 SHA-256：`9f70d30484eaa5f769d61031a4c60c664827deaa7fcbdfd88052b2629ef16f3c`。
- quality mask SHA-256：`7ebc053bfc7517377f6e2946f84b5e4e69c3294fa24de8684131cffc3dbb10dc`。
- joint stats SHA-256：`0aad929a99216616af8b409ccd4007b019bc29af873415dbb03ce70f6f5e40d9`。
- overlay SHA-256：`b353ba2666c75b0eb204cc9dd0fb9d1a900194d3175317cef74b0be4fabb6d14`。
- validation summary SHA-256：`df597b954d763f0d92b24a639015823ca9c62aff1f3cd2326ab9d0776040ab2d`。

## 当前问题与停止边界

- frame 226的`pose_index=1`是仅3个有效点的残缺额外pose，自动保留为`unmatched_pose`，等待人工确认其性质；没有绑定P001或删除原始记录。
- frame 64、65、143、182-185需要人工检查右臂核心关节低置信/缺失是否符合画面。
- 自动验证通过不等于T06C人工验收通过。当前停止等待人工检查。
- 未重跑DeepSORT，未修改OpenPose raw JSON或人工动作阶段，未处理E002-E012，未滤波、插值、纸盒检测、仿真映射、LeRobot转换或训练。

## T06C-M1 — 上半身可见范围掩码与可视化修正

### Run信息

- Run ID：`20260713_T06C_M1_001`
- 日期：2026-07-13
- 目的：将画面外BODY_25模型推测值与真实可见观测分离，并修正主overlay。
- 环境：`motpose` Python 3.10；复用既有MOT、association、OpenPose raw和动作标签。
- 代码版本：工作区含未提交修改；未创建虚假commit标识。

### 输入与保护

- MOT raw SHA-256：`d5dff496bf7df73f8b280150ff71558c67271a3cd80ba918427ca9cc81dba55c`。
- subject map SHA-256：`d39db0e098e9ccca8b71321f53f5960c7120fa15c31610d3330878ef51c1cac1`。
- T06B frames SHA-256：`a9b42220053136d3751cbf3de699680f5e63a1e4161b3e23bd53e60c0392301f`。
- association JSONL SHA-256：`345b9e478214f9a53c3feb9567d146da2f32a8598bf7ebeead4ec0d512bbf5cd`。
- OpenPose raw目录SHA-256：`b068dc2db1de56feb714cfb18e8f15514e52d1c05c9c9c0b935dc0645d522c5e`，修正前后相同。
- 未运行DeepSORT/OpenPose；未写入上述输入。

### 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/build_upper_body_sequence.py \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --subject-output data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask-output data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --joint-stats results/merged/pick_place_pilot_v1_E001_joint_stats.json \
  --expected-frames 345 --confidence-threshold 0.3 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/render_pose_phase_overlay.py \
  --video data/raw_videos/pick_place_pilot_v1/episodes/P01_BOX01_R_A_B_E001_S.mp4 \
  --subject-jsonl data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --output results/merged/pick_place_pilot_v1_E001_pose_phase_overlay.mp4 \
  --expected-frames 345 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/validate_e001_perception.py \
  --pose-json-dir results/openpose/pick_place_pilot_v1_E001/raw_json \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --association-summary results/association/pick_place_pilot_v1_E001/summary.json \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --subject-jsonl data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --joint-stats results/merged/pick_place_pilot_v1_E001_joint_stats.json \
  --overlay results/merged/pick_place_pilot_v1_E001_pose_phase_overlay.mp4 \
  --output-summary results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --expected-frames 345
```

### 参数、规则和真实结果

- 固定可见关节：0、1、2、3、4、5、6、7、15、16、17、18。
- 固定不可见关节：8、9、10、11、12、13、14、19、20、21、22、23、24。
- 每帧新增25项并写入P001和quality mask：`joint_observation_status`、`joint_valid`、`visibility_reason`。
- 固定不可见关节全部为`out_of_frame/false/outside_capture_scope`；共4485个person-joint实例，其中1061个原始confidence非零，raw值均保留。
- joint observation总分布：valid 3685、low_quality 234、missing 221、out_of_frame 4485。
- 辅助关节：Nose、LShoulder、LElbow、LWrist；MidHip已移除。核心关节不变。
- 帧级分布未变化：336 valid、7 low_quality、2 missing。low_quality仍为64、65、143、182-185；missing仍为0-1。
- 主overlay仅绘制Nose-Neck、双侧肩肘腕链及头部可见边，不绘制Neck-MidHip、髋腿脚节点或边。
- normalization记录：`origin_joint=Neck`、`scale_reference=shoulder_width`、`pelvis_centered_normalization=unavailable_for_this_capture`。

### 输出、验证和可视化

- P001 SHA-256：`36ded0a2f3c903e2dc9613709dbd2454a5078a0fe838ccc5ed32e1743a76ee5a`。
- quality mask SHA-256：`5f5115be15d8cdf52d4bcd7b8cb3f9a17f2097b5a1ff533154a657bf71d6ccec`。
- joint stats SHA-256：`5cca1c9de854a7d2b1f28a34637732f585f57bb5cbd83551dcc58f11ffe86eb9`。
- 主overlay SHA-256：`ad7e852a6cf3edf38333e13f3e697363e3034b623e49725ccc02e2be944b6700`；H.264、1280x720、30 FPS、345帧，全量解码通过。
- validation summary SHA-256：`aa651d622efdf9ac8f5f3619ed192d5980d56ea9efb7b43e1bb9aebb527edc38`；`validation_passed=true`、errors为空。
- 视觉抽查frame 2、45、64、65、100、143、182、183、184、185、226、300：未显示腰部、髋部、腿部或脚部推测骨架；frame 226的额外pose只显示可见范围内的紫色残缺手臂。

### 异常、下一步和论文可用性

- 运行失败与异常：无。静态检查、`--help`、独立验证及视频全量解码通过。
- 待人工检查：frame 226额外`pose_index=1`、frame 64/65/143/182-185及主overlay上半身范围。
- 是否可用于论文：作为可见范围掩码实现证据可用；人工检查完成前不作为最终定量结论。
- 停止边界：未滤波、未检测纸盒、未做仿真映射、未处理E002-E012。

## T06C最终人工复核

### Run信息

- Run ID：`20260713_T06C_FINAL_REVIEW_001`
- 日期：2026-07-13
- 目的：将用户人工检查结论写入结构化review、quality mask和validation summary。
- 输入：既有manual review模板、quality mask、association JSONL及用户本轮明确结论。
- 环境：`motpose` Python 3.10；未调用GPU，不运行DeepSORT或OpenPose。

### 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/apply_t06c_manual_review.py \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --manual-review results/association/pick_place_pilot_v1_E001/manual_review.csv \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --output data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --expected-frames 345 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/validate_e001_perception.py \
  --pose-json-dir results/openpose/pick_place_pilot_v1_E001/raw_json \
  --association-jsonl data/openpose/associated/pick_place_pilot_v1_E001.jsonl \
  --association-summary results/association/pick_place_pilot_v1_E001/summary.json \
  --phase-frames data/action_labels/frames/pick_place_pilot_v1_E001/frames.jsonl \
  --subject-jsonl data/openpose/processed/pick_place_pilot_v1_E001/P001.jsonl \
  --quality-mask data/openpose/processed/pick_place_pilot_v1_E001/quality_mask.jsonl \
  --joint-stats results/merged/pick_place_pilot_v1_E001_joint_stats.json \
  --manual-review results/association/pick_place_pilot_v1_E001/manual_review.csv \
  --overlay results/merged/pick_place_pilot_v1_E001_pose_phase_overlay.mp4 \
  --output-summary results/merged/pick_place_pilot_v1_E001_validation_summary.json \
  --expected-frames 345
```

### 人工结论与统计

- frame 64-65：RElbow=`low_quality`，reason=`forearm_self_occlusion`；RWrist=`missing`，reason=`hand_occludes_wrist`。
- frame 143：RElbow=`low_quality`，reason=`forearm_self_occlusion`；RWrist=`missing`，reason=`hand_and_box_occlude_wrist`。
- frame 182-185：RElbow=`unstable`，RWrist=`missing_or_unstable`；reason=`suspected_self_occlusion_and_face_overlap`，manual confidence=`medium`。该原因只是疑似解释，不表述为绝对确定。
- frame 226：额外`pose_index=1`为桌面反光误检，manual status=`excluded_reflection_artifact`，reason=`table_reflection_false_positive`；不影响P001，frame 226保持`valid/frame_valid=true`。
- 确认轨迹帧自动joint-level missing：Neck 0、RShoulder 0、RElbow 0、RWrist 7。人工明确确认RWrist missing：64、65、143共3帧；182-185另列为missing或不稳定，不冒充确定missing原因。
- 帧级统计保持valid 336、low_quality 7、missing 2。

### 输出、哈希与验证

- `manual_review.csv`：17条记录，SHA-256 `385658ea0b6bb85edb8111b98eed6ad106ce8814eec712120f20e2bb7f08fadf`。
- `quality_mask.jsonl`：345条，SHA-256 `b98397817df55b93efe903469f1070a88349a30f95eedbc2e8c512b8f4ccf273`。
- `validation_summary.json`：SHA-256 `9d65c1605b95343def57d1f0563f270e30eba8b748c3663ae88e8867ad0f0393`。
- 最终独立验证：`validation_passed=true`、errors为空；manual review applied、frame 226 P001 remains valid、raw pose preserved等规则全部通过。
- association JSONL哈希仍为`345b9e478214f9a53c3feb9567d146da2f32a8598bf7ebeead4ec0d512bbf5cd`；OpenPose raw目录哈希仍为`b068dc2db1de56feb714cfb18e8f15514e52d1c05c9c9c0b935dc0645d522c5e`。

### 失败、边界和论文使用

- 失败与异常：无。脚本`py_compile`、`--help`、独立验证均通过。
- 没有修改OpenPose raw JSON、association坐标或P001 raw关键点；没有插值、滤波、DeepSORT/OpenPose重跑。
- T06C最终人工复核记录完成。当前停止，不开始纸盒检测、仿真映射、滤波或E002-E012。
- 是否可用于论文：可作为E001人工复核后的原型质量记录；不扩大为多视频总体结论。
