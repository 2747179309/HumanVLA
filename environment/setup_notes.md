# 安装与执行计划

> 状态：仅计划，尚未执行。任何系统包、Docker、模型权重或大规模下载都需用户批准。

## 环境判断

建议创建独立 Conda 环境 `motpose`。当前 base 使用 Python 3.11.5，且无 PyTorch/OpenCV；项目另有 TensorRT、bevfusion、rknn230 环境，不应污染或复用。建议 MOT Python 栈以 Python 3.10 起步，再根据安装时的官方 PyTorch 兼容矩阵固定版本。

系统驱动 550.144.03 可见 RTX 3090，系统 `nvcc` 为 11.3。PyTorch 二进制可携带自己的 CUDA runtime，因此不能仅凭 `nvcc` 版本选择安装命令；安装当天必须从 [PyTorch 官方安装页](https://pytorch.org/get-started/locally/) 生成命令并记录实际解析版本。

## A. YOLO + DeepSORT（推荐先做）

推荐架构：YOLO 只输出 `person` 检测，DeepSORT 独立接收检测框与置信度；本仓库自己负责逐帧读取、ID 可视化，以及 JSONL/MOTChallenge 双格式导出。这样可固定输入输出模式并保留后续替换检测器或跟踪器的能力。

候选 DeepSORT 实现优先评估 `deep-sort-realtime`，同时以 [原始 Deep SORT 仓库](https://github.com/nwojke/deep_sort) 和论文定义为算法依据。原始仓库依赖老旧 TensorFlow 工作流，不建议直接污染现代 MOT 环境。最终包名、版本、许可证和 commit 必须在安装前记录，不把第三方 tracker 的输出视为真值。

待批准的环境创建骨架：

```bash
conda create -n motpose python=3.10 pip
conda activate motpose
# 按安装当天 PyTorch 官方矩阵安装 torch/torchvision。
# 再安装并锁定 ultralytics、deep-sort-realtime、opencv-python、numpy 等。
```

安装后必须先运行：Python/包版本打印、`torch.cuda.is_available()`、RTX 3090 名称读取、一个小张量 CUDA 运算、单帧 YOLO person 检测。通过后导出 `environment/requirements/` 中的直接依赖与完整冻结清单。

## B. OpenPose（与 MOT 环境分离）

必须使用 CMU OpenPose BODY_25。推荐在 `tools/openpose/` 做项目内源码构建，不运行 `sudo make install`，避免修改系统级库。官方仓库声明支持 Ubuntu 20，并提供 `--write_json`；参考 [OpenPose 官方仓库](https://github.com/CMU-Perceptual-Computing-Lab/openpose) 与 [官方安装文档](https://github.com/CMU-Perceptual-Computing-Lab/openpose/blob/master/doc/installation/0_index.md)。

执行前需要：

1. 记录 OpenPose commit 和许可证。
2. 核对 CMake、CUDA、cuDNN、OpenCV/Caffe 构建兼容性。
3. 经用户批准后安装缺失系统构建依赖并下载 BODY_25 模型。
4. 只在一段短视频上输出 `data/openpose/raw_json/<video_id>/`。
5. 验证每个人的 `pose_keypoints_2d` 可重塑为 `25 x 3`。

OpenPose 原始 JSON 永不覆盖。身份关联另写到 `data/openpose/associated/`；`people` 数组下标禁止作为人物 ID。

## C. CVAT（Docker Compose 隔离）

当前 Docker 与 Compose 均未安装。推荐按 [CVAT 官方 Ubuntu 20.04 安装指南](https://docs.cvat.ai/docs/administration/basics/installation/) 安装 Docker Engine 与 Compose plugin，再把 CVAT clone 到 `tools/cvat/`，固定明确版本而非长期跟随 `latest`。

Docker 安装会修改系统软件源、服务和用户组，CVAT 会下载较大容器镜像，因此必须单独获得用户批准。部署前确认端口、磁盘位置、备份策略和是否仅本机访问。人工复核应至少处理 ID Switch、断轨合并、误检删除、漏检补框和 `track_id -> subject_id` 映射。

## 最小测试计划

1. 用户提供或确认一段 10 至 30 秒的多人视频，复制到 `data/raw_videos/` 后设为只读工作源，并登记 SHA-256、FPS、分辨率、帧数和时长。
2. YOLO 仅检测 `person`，保存原始检测，不覆盖视频。
3. DeepSORT 生成单视频局部 `track_id`。
4. 输出带 ID 的可视化视频、逐人物逐帧 JSONL 和 MOTChallenge 文本结果。
5. 记录轨迹数量、有效检测数、短轨数量和处理速度；这些不是人工准确率。
6. 导入 CVAT，人工修复 ID Switch、断轨、误检和漏检。
7. 导出复核轨迹，创建 `track_id -> subject_id` 映射并版本化。
8. 仅在 MOT 人工复核完成后运行 OpenPose BODY_25。
9. 以关键点派生框/有效点集合对复核人物框进行匹配；保存匹配得分、阈值和未匹配原因。
10. 抽样人工检查关联，随后才添加动作阶段和语言描述。

## 建议验收输出

```text
data/mot/raw/<video_id>/tracks.jsonl
data/mot/raw/<video_id>/mot.txt
results/mot/<video_id>_tracked.mp4
data/mot/reviewed/<video_id>/mot_reviewed.txt
data/mot/subject_maps/<video_id>.csv
data/openpose/raw_json/<video_id>/*.json
data/openpose/associated/<video_id>.jsonl
logs/runs/<RunID>.md
```

## 当前阻塞与风险

- Docker、FFmpeg、PyTorch、OpenCV 未安装。
- cuDNN 状态未验证，OpenPose 与 CUDA 11.3 的实际构建兼容性未知。
- 原始 OpenPose/Caffe 栈较旧，可能需要独立补丁或容器；未完成 smoke test 前不能承诺可编译。
- 尚无用户确认的测试视频、YOLO 权重或标注人员安排。
- 293 GB 可用空间足够最小测试，但视频帧、OpenPose JSON、CVAT volume 和模型会持续增长，需记录磁盘预算。

## 需要用户确认

1. 是否批准创建 `motpose` 并安装 Python 依赖及一个轻量 YOLO 权重。
2. 是否批准安装系统 FFmpeg。
3. 是否批准安装 Docker Engine/Compose 并拉取固定版本 CVAT 镜像。
4. 是否批准下载并源码构建 OpenPose BODY_25 及其模型。
5. 指定第一段 10 至 30 秒多人视频，并确认其使用与标注授权。
