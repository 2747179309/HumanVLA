# Run ID: 20260712_T03_001

- 日期：2026-07-12
- 实验目的：构建 CMU OpenPose GPU/BODY_25，并在 `three-people-walking.mp4` 上完成最小闭环测试。
- 当前状态：构建和 GPU 视频运行完成；严格 JSON 验证因置信度越界未通过。
- 输入文件：`data/raw_videos/three-people-walking.mp4`，SHA-256 `1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd`。
- 代码版本或 Git commit：项目基线 `8235143f1e1edae88f509fc87522f906ba47eafe`；OpenPose `5c5d96523ef917bd30301245fdc8343937cae48d`；Caffe `1807aadafc934a2a1341021620981cb1ec526b83`。
- 是否可以用于论文：否；这是单视频工程 smoke test，且严格置信度约束未通过。

## 第一阶段：环境检查

| 检查项 | 真实结果 | 状态 |
|---|---|---|
| GPU | NVIDIA GeForce RTX 3090, 24576 MiB | 可用 |
| NVIDIA 驱动 | 550.144.03 | 可用 |
| 驱动报告 CUDA | 12.4（驱动支持级别） | 记录 |
| 系统 CUDA Toolkit | 11.3, nvcc V11.3.58 | 可用 |
| nvcc 路径 | `/home/a531/CUDA11.3.0/bin/nvcc` | 可用 |
| GCC | 9.4.0 | 可用 |
| CMake | 3.16.3 | 可用 |
| GNU Make | 4.2.1 | 可用 |
| 系统 Python | 3.11.5 | 仅记录，不修改、不用于 OpenPose Python API |
| cuDNN | 8.6.0，位于 `/home/a531/CUDA11.3.0/` | 可见，非 dpkg 管理 |
| 系统 OpenCV | 4.2.0 (`pkg-config opencv4`) | 可用 |
| FFmpeg | 4.2.7 | 可用 |
| OpenPose | `tools/openpose/` 不存在，未安装 | 待构建 |
| 可用磁盘 | 284 GiB | 足够最小构建与视频输出 |

### 缺失构建依赖

环境检查发现 `libprotobuf-dev`、`protobuf-compiler`、`libleveldb-dev`、`libsnappy-dev`、`liblmdb-dev` 和 `libatlas-base-dev` 未安装。`build-essential`、OpenCV、Boost、gflags、glog 和 HDF5 已安装。

### 冲突判断

未发现必须立即停止的明确冲突。构建将显式使用 CUDA 11.3、cuDNN 8.6.0 和 Ampere `sm_86`，并禁用 Python API，避免系统 Python/ROS 环境污染。OpenPose/Caffe 代码较旧，若 CMake 或编译阶段出现 CUDA 11.3、cuDNN 8、GCC 9 或 `sm_86` 不兼容，将停止强行安装并在本日志记录原始错误。

### 已执行的环境命令

```bash
nvidia-smi
nvcc --version
gcc --version
cmake --version
python3 --version
rg -n "CUDNN_(MAJOR|MINOR|PATCHLEVEL)" /home/a531/CUDA11.3.0/include/cudnn_version.h
find /home/a531/CUDA11.3.0 -name 'libcudnn.so*'
pkg-config --modversion opencv4
find tools -name openpose.bin
dpkg-query -W build-essential libopencv-dev libprotobuf-dev protobuf-compiler \
  libgoogle-glog-dev libgflags-dev libboost-all-dev libhdf5-dev \
  libatlas-base-dev libleveldb-dev libsnappy-dev liblmdb-dev
sha256sum data/raw_videos/three-people-walking.mp4
df -h /home/a531/HumanVLA
```

## 构建记录

安装了最小 Caffe 构建依赖：`libprotobuf-dev`、`protobuf-compiler`、`libleveldb-dev`、`libsnappy-dev`、`liblmdb-dev`、`libatlas-base-dev`。未修改 NVIDIA 驱动、系统 CUDA 或系统 Python，未执行 `sudo make install`。

- OpenPose 源码：官方仓库，commit `5c5d96523ef917bd30301245fdc8343937cae48d`。
- 构建模式：CUDA 11.3 + cuDNN 8.6 + `sm_86`，`BUILD_PYTHON=OFF`。
- BODY_25 模型：104715850 bytes；MD5 `78287b57cf85fa89c03f1393d368e5b7` 与官方 CMake 声明一致；SHA-256 `44e3d7ebd8c8b62d4366d67127f1b562611a9e8fd0f4f3cdeeb4bb4a6ed12be6`。
- 构建结果：`tools/openpose/build/examples/openpose/openpose.bin` 存在且可执行。
- 完整依赖、选项和失败日志索引：`environment/requirements/openpose-build.txt`。

最终配置和构建命令：

```bash
env CUDA_HOME=/home/a531/CUDA11.3.0 \
  CUDA_INC_PATH=/home/a531/CUDA11.3.0/targets/x86_64-linux/include \
  CUDNN_ROOT=/home/a531/CUDA11.3.0 \
  PATH=/home/a531/CUDA11.3.0/bin:/usr/bin:/bin \
  LD_LIBRARY_PATH=/home/a531/CUDA11.3.0/lib:/home/a531/CUDA11.3.0/lib64 \
  cmake -S tools/openpose -B tools/openpose/build \
  -DGPU_MODE=CUDA -DCUDA_TOOLKIT_ROOT_DIR=/home/a531/CUDA11.3.0 \
  -DCUDA_nppicom_LIBRARY=/home/a531/CUDA11.3.0/lib64/libnppc.so \
  -DCUDNN_ROOT=/home/a531/CUDA11.3.0 \
  -DCUDNN_INCLUDE=/home/a531/CUDA11.3.0/include \
  -DCUDNN_LIBRARY=/home/a531/CUDA11.3.0/lib/libcudnn.so \
  -DUSE_CUDNN=ON -DCUDA_ARCH=Manual -DCUDA_ARCH_BIN=8.6 -DCUDA_ARCH_PTX= \
  -DBUILD_PYTHON=OFF -DBUILD_EXAMPLES=ON \
  -DDOWNLOAD_BODY_25_MODEL=OFF -DDOWNLOAD_BODY_COCO_MODEL=OFF \
  -DDOWNLOAD_BODY_MPI_MODEL=OFF -DDOWNLOAD_FACE_MODEL=OFF \
  -DDOWNLOAD_HAND_MODEL=OFF

env CUDA_HOME=/home/a531/CUDA11.3.0 \
  CUDA_INC_PATH=/home/a531/CUDA11.3.0/targets/x86_64-linux/include \
  LD_LIBRARY_PATH=/home/a531/CUDA11.3.0/lib:/home/a531/CUDA11.3.0/lib64 \
  cmake --build tools/openpose/build --parallel 8
```

## 视频运行与结果

单帧 GPU 冒烟测试检测到 3 人，三条 `pose_keypoints_2d` 长度均为 75。完整运行命令：

```bash
scripts/openpose/run_openpose.sh \
  --video data/raw_videos/three-people-walking.mp4 \
  --output-dir results/openpose/three-people-walking \
  --openpose-root tools/openpose \
  --net-resolution "-1x368" --number-people-max 6 --gpu 0

/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/validate_openpose_json.py \
  --json-dir results/openpose/three-people-walking/raw_json \
  --input-video data/raw_videos/three-people-walking.mp4 \
  --rendered-video results/openpose/three-people-walking/rendered.mp4 \
  --summary results/openpose/three-people-walking/summary.json \
  --metadata results/openpose/three-people-walking/metadata.json \
  --expected-frames 240 --run-id 20260712_T03_001 \
  --openpose-root tools/openpose \
  --runtime-file results/openpose/three-people-walking/processing_seconds.txt \
  --net-resolution=-1x368 --number-people-max 6
```

真实输出和统计：

| 指标 | 结果 |
|---|---:|
| JSON 文件 | 240，frame 0-239 |
| JSON 解析异常 | 0 |
| `pose_keypoints_2d` 长度异常 | 0 |
| 无人体骨架帧 | 0 |
| 每帧人数分布 | 3 人: 234 帧；4 人: 6 帧 |
| person 实例总数 | 726 |
| 平均每帧人数 | 3.025 |
| 平均有效关键点/实例 | 24.177686 |
| 右/左肩缺失率 | 0.550964% / 0.550964% |
| 右/左肘缺失率 | 1.101928% / 0.826446% |
| 右/左腕缺失率 | 1.652893% / 1.377410% |
| OpenPose 处理时间 | 34.37 秒 |
| OpenPose 处理速度 | 6.983 FPS |
| rendered 视频 | H.264, 2160x3840, 240 帧, 23.976 FPS |

输出完整性命令通过，`ffmpeg -v error -i rendered.mp4 -f null -` 全片解码退出码为 0。20 帧预检记录见 `results/openpose/three-people-walking/human_spot_check.md`。

静态检查：`bash -n scripts/openpose/run_openpose.sh`、Python `py_compile` 和两个脚本的 `--help` 均通过；本机未安装 `shellcheck`，未为此额外安装工具。

## 失败与异常

1. 初次 CMake 未找到 CUDA include；通过显式 `CUDA_INC_PATH` 修正。原始日志保留。
2. 官方 SNU 模型服务器无响应；终止挂起请求后，只下载备用 BODY_25 权重并用官方 MD5 严格校验。未下载其他模型。
3. 默认 face/hand 下载造成一次配置失败；随后显式关闭，与 BODY_25 任务范围一致。
4. 初次 Caffe 构建因缺少 Atlas 开发包失败；安装 `libatlas-base-dev` 后构建成功。
5. 沙箱内单帧测试返回 CUDA error 100；在获批的主机 GPU 上同一二进制成功完成，确认是设备隔离而非 CUDA 冲突。
6. 原始 JSON 中 101/18150 个置信度值位于 1.0002-1.03636，涉及 79 帧、96 个 person 记录。原始 JSON 未修改；因违反协议 `[0,1]` 约束，严格 JSON 验证结果为 `false`。
7. 4 人检测出现在帧 43、44、45、188、207、208。前 3 帧的额外记录只有 3 个有效点，后 3 帧为低置信度背景或 phantom 候选，必须人工确认。

## 下一步计划

提交人工复核时重点检查 6 个四人帧、腕部遮挡和置信度越界语义。T03 在协议如何处理 OpenPose 原生大于 1 的分数得到人工决定前不能标记为严格验收通过；不得修改 raw JSON，不启动 T04 或身份关联。

## 人工复核收尾

- 收尾日期：2026-07-12
- 人工输入：`data/openpose/manual_gt/three-people-walking_visual_review.csv`
- 人工 CSV SHA-256：`7e131d1b00f742459412027ced7f371c4166d9d3bb49a2509539e7623b5d5e24`
- CSV 格式：9 个预期字段、6 条唯一帧记录；整数、二值字段、帧范围和必填文本检查均通过。
- 用户人工判断未被修改；收尾分类与原始 `decision` 分字段保存。

### 6 个视觉骨架异常帧

| frame | 人工判断 | 原人工决定 | T03 收尾分类 | 后续处理 |
|---:|---|---|---|---|
| 43 | 两名人物重叠，骨架粘连和 identity mix | `needs_recheck` | `ambiguous_pose` | 保留 raw，不强制修复，不作为无歧义姿态样本 |
| 44 | 两名人物持续重叠，关键点跨人物串联 | `needs_recheck` | `ambiguous_pose` | 保留 raw，不强制修复，不作为无歧义姿态样本 |
| 45 | 分离前仍有粘连，额外骨架无法可靠归属 | `needs_recheck` | `ambiguous_pose` | 保留 raw，不强制修复，不作为无歧义姿态样本 |
| 188 | 非人物区域产生 phantom 骨架 | `exclude_extra_pose` | `phantom_pose` | 保留 raw，下游排除额外骨架 |
| 207 | 远处真实人物，无对应 DeepSORT 轨迹 | `keep_raw_exclude_main` | `unmatched_pose` | 不纳入三名主要人物数据 |
| 208 | 远处真实人物，无对应 DeepSORT 轨迹 | `keep_raw_exclude_main` | `unmatched_pose` | 不纳入三名主要人物数据 |

视觉骨架异常共 6 帧。这里的 `identity_mix`、phantom 和 unmatched pose 是人工视觉结论；未执行 OpenPose 与 DeepSORT 关联，也没有使用 `people` 数组下标作为身份。

### Confidence 数值警告

- 79 帧中共有 101 个 confidence 值大于 1，范围为 1.0002-1.03636。
- 这是 OpenPose 原始数值范围警告，不等同于 79 帧存在视觉骨架错误，也不改变人工确认的 6 个视觉异常帧数量。
- 原始 confidence 值保持不变，未裁剪、归一化或覆盖。
- `summary.json` 的严格验证状态仍为 `false`，以保留当前协议 `[0,1]` 与原生输出之间的事实差异。

### Raw JSON 完整性复验

- 文件数：240；帧号连续 0-239。
- JSON 解析错误：0；`people` 结构错误：0；长度不为 75 的 `pose_keypoints_2d`：0。
- 每帧人数与 `summary.json` 完全一致；帧 43、44、45、188、207、208 均为 4 个 pose 记录。
- raw 目录聚合 SHA-256：`c174f901c73646b64b3f4a4ebbf3bb99c41534405324757e951a2449b14f0a8f`。计算方式为按文件名排序，依次哈希 `filename + NUL + raw bytes`。
- 本次收尾未修改、覆盖或重新生成任何 raw JSON。

### 收尾输出与验收判断

- 新增：`results/openpose/three-people-walking/manual_review_summary.json`。
- 二进制、BODY_25 模型、构建记录、运行/验证脚本、240 个 raw JSON、H.264 渲染视频、metadata、自动 summary、suspicious frames、人工 CSV、20 帧预检和人工收尾汇总均存在且非空。
- 材料可以提交 Claude 验收。需要 Claude 明确裁决 confidence 原生值大于 1 是否作为带警告的协议例外；本日志不自行把严格自动验证改写为通过。
- 未执行卡尔曼滤波、43-45 强制修复、骨架-ID 关联、动作标注或模型训练，未开始 T04。

### 收尾核对命令

```bash
python -c "使用 csv.DictReader 检查字段、数据类型、唯一帧和人工决定"
python -c "逐个解析 240 个 raw JSON，检查帧序列、people 和 75 值关键点数组，并计算目录聚合 SHA-256"
sha256sum data/openpose/manual_gt/three-people-walking_visual_review.csv \
  results/openpose/three-people-walking/summary.json \
  results/openpose/three-people-walking/suspicious_frames.csv
python -c "交叉检查 manual_review_summary.json 与人工 CSV 的 issue_type 和 decision 完全一致"
```
