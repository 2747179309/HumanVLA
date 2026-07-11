# Codex 工作报告

## T02 执行更新（2026-07-11）

### 状态

- `motpose` 环境、代码、严格环境检查和单段本地视频自动 smoke test 已完成。
- 视频格式和数据一致性检查通过；只做了 10 个整秒帧及第 86、120 帧的抽样可视检查。
- T02 尚未完成全视频人工 ID Switch、断轨、误检、漏检复核，因此不标记为 `COMPLETED`。
- 未安装 OpenPose、Docker 或 CVAT，未开始 T03。

### 新建文件

- `scripts/environment/check_mot_environment.py`
- `scripts/mot/run_deepsort.py`
- `environment/requirements/motpose.environment.yml`
- `environment/requirements/motpose.requirements.txt`
- `environment/requirements/motpose.pip-freeze.txt`
- `logs/runs/T02_MOT_SMOKE_TEST.md`

### 修改文件

- `context/DATA_SCHEMA.md`：增加 `detection_confidence`。
- `environment/system_info.txt`：追加 T02 安装和 CUDA smoke test 的真实结果。
- `logs/daily/2026-07-11.md`：追加 T02 当日记录。
- `tasks/CODEX_REPORT.md`：本节。

用户或并行进程已有的 `tasks/CURRENT_TASK.md`、`tasks/TASK_QUEUE.md`、`tasks/DECISIONS.md`、`tasks/CLAUDE_REPORT.md` 和未跟踪的 `tasks/T02_ACCEPTANCE_CRITERIA.md` 均保留，Codex 未覆盖或夹带提交。

### 关键执行命令

```bash
/home/a531/anaconda3/bin/conda create -n motpose python=3.10 pip -y
/home/a531/anaconda3/envs/motpose/bin/python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
/home/a531/anaconda3/envs/motpose/bin/python -m pip install ultralytics==8.4.57 deep-sort-realtime==1.3.2 opencv-python numpy==2.2.6 scipy pandas tqdm
/home/a531/anaconda3/envs/motpose/bin/python -m pip install setuptools==80.9.0
sudo apt-get update
sudo apt-get install -y ffmpeg
env -u PYTHONPATH YOLO_CONFIG_DIR=/tmp /home/a531/anaconda3/envs/motpose/bin/python scripts/environment/check_mot_environment.py
env -u PYTHONPATH YOLO_CONFIG_DIR=/tmp /home/a531/anaconda3/envs/motpose/bin/python scripts/mot/run_deepsort.py --video data/raw_videos/three-people-walking.mp4 --video-id three-people-walking --run-id 20260711_T02_001 --overwrite
```

### 环境结果

- Python 3.10.20，PyTorch 2.5.1+cu121，torchvision 0.20.1+cu121。
- RTX 3090 CUDA 可用，compute capability 8.6，GPU 张量 smoke test 通过。
- PyTorch 内置 CUDA runtime 12.1、cuDNN 9.1；没有修改系统 CUDA 11.3。
- ultralytics 8.4.57、deep-sort-realtime 1.3.2、OpenCV 5.0.0、NumPy 2.2.6、SciPy 1.15.3、Pandas 2.3.3、tqdm 4.68.4。
- FFmpeg 4.2.7 安装成功；严格环境检查通过。

### 视频实验结果

- Run ID：`20260711_T02_001`。
- 输入：`three-people-walking.mp4`，10.01 秒，240 帧，2160x3840，23.976 FPS，SHA-256 `1dafa388...b0ccd`。
- 输出目录：`results/mot/three-people-walking/`。
- 723 个 person 检测，715 条轨迹帧记录，4 个 track_id。
- ID 1/2/3 各持续 238 帧；ID 4 仅在第 86 帧出现，画面检查确认其对应远处真实儿童，是需要人工处理的单帧短轨/周边漏检问题。
- 检测 62.291 FPS；DeepSORT 跟踪 31.965 FPS。
- 最终视频为 H.264/yuv420p、240 帧、10.010 秒；JSONL、MOT 10 列格式、labels 与 metadata 一致性检查通过。
- 自动输出不是 ground truth，`mot/gt.txt` 只是用户指定的 MOTChallenge 交换文件名。

### 当前风险与异常

- 只进行了抽样视觉检查，尚不能报告 ID Switch、fragmentation、FP、missing 的完整数量。
- `deep-sort-realtime 1.3.2` 依赖已弃用的 `pkg_resources`，当前通过固定 setuptools 80.9.0 兼容。
- 系统 `ldconfig` 报告手工 cuDNN 8 文件不是符号链接；本轮未修改，且 PyTorch 使用 wheel 内置 cuDNN 9.1。
- shell 的 ROS Foxy `PYTHONPATH` 指向 Python 3.8，运行必须继续隔离该变量。
- APT 更新时无关 `antigravity` 第三方源超时；Ubuntu 镜像和 FFmpeg 安装成功，未修改该源。

### 下一步建议

完整观看 `tracked.mp4` 并按 `MOT_ANNOTATION_PROTOCOL.md` 逐帧记录四类错误，重点复核第 86 帧背景儿童和人物交叉段。人工复核结束前不启动 T03，不把当前结果用于论文指标。

## 本轮信息

- 日期：2026-07-11（Asia/Shanghai）
- 任务：T01 — 新电脑环境审计与 DeepSORT/OpenPose 工作区初始化
- 状态：第一轮初始化已完成；T01 保持 `IN_PROGRESS`，安装和最小视频流水线尚未执行
- Git 分支：`main`
- 初始提交：`27b4c34` (`chore: initialize HumanVideo2VLA research workspace`)

## 新建文件

Codex 本轮创建的主要文件：

- `AGENTS.md`
- `README.md`
- `.gitignore`
- `environment/system_info.txt`
- `environment/setup_notes.md`
- `environment/requirements/README.md`
- `context/PROJECT_CONTEXT.md`
- `context/RESEARCH_SCOPE.md`
- `context/DATA_SCHEMA.md`
- `context/PAPER_CLAIMS.md`
- `tasks/CURRENT_TASK.md`
- `tasks/TASK_QUEUE.md`
- `tasks/DECISIONS.md`（D001-D003 由 Codex 创建，后续条目由并行进程扩展）
- `logs/runs/README.md`
- `logs/daily/2026-07-11.md`（初始段落由 Codex 创建，后由并行进程扩展）
- 用户指定空目录中的 `.gitkeep` 占位文件
- `tasks/CODEX_REPORT.md`

本轮执行中发现以下文件由用户或另一进程并行新增，Codex 未覆盖，已随首次仓库快照提交：

- `context/MOT_ANNOTATION_PROTOCOL.md`
- `context/OPENPOSE_BODY25_PROTOCOL.md`
- `tasks/CLAUDE_PROJECT_REVIEW.md`
- `tasks/CLAUDE_REPORT.md`
- `tasks/CLAUDE_REVIEW.md`
- `tasks/T01_ACCEPTANCE_CRITERIA.md`

## 修改文件

- `.vscode/settings.json` 与 `.vscode/extensions.json` 来自上一轮 Markdown 工作区配置，本轮未覆盖，已纳入初始提交。
- `experiment_lab_notebook.md` 为初始化前已有文件，本轮未修改，已纳入初始提交。
- 并行进程扩展了 `tasks/DECISIONS.md` 和 `logs/daily/2026-07-11.md`；Codex 保留了这些变化。

## 执行命令

只读审计和验证使用了以下命令；未执行软件安装、模型下载、视频处理或训练：

```bash
cat /etc/os-release
uname -a
lscpu
free -h
lspci -nnk
cat /proc/driver/nvidia/version
nvidia-smi
nvcc --version
python3 --version
which python3
python3 -m pip --version
/home/a531/anaconda3/bin/conda --version
/home/a531/anaconda3/bin/conda env list
git --version
gcc --version
cmake --version
docker --version
docker compose version
ffmpeg -version
python3 -c "import cv2; print(cv2.__version__)"
python3 -c "import torch; print(torch.__version__)"
dpkg-query -W libcudnn8 libcudnn8-dev
df -h /home/a531/HumanVLA
find . -maxdepth 3 -type d -print
find . -maxdepth 3 -type f -print
git init
git symbolic-ref HEAD refs/heads/main
git add .
git -c user.name=HumanVideo2VLA -c user.email=humanvideo2vla@local commit -m "chore: initialize HumanVideo2VLA research workspace"
```

说明：受限沙箱内的 `nvidia-smi` 无法访问设备；获得批准后在沙箱外执行成功。Git 元数据同样是只读沙箱挂载，Git 写操作经批准在沙箱外完成。提交身份仅用于本次命令，未修改全局 Git 配置。

## 环境检查结果摘要

- Ubuntu 20.04.6 LTS，内核 5.15.0-139-generic。
- Intel Xeon E5-2680 v4，14 核/28 线程；31 GiB RAM。
- NVIDIA GeForce RTX 3090，24 GiB VRAM；驱动 550.144.03 工作正常。
- `nvidia-smi` 报告驱动支持 CUDA 12.4；本机 `nvcc`/Toolkit 实际为 CUDA 11.3 (V11.3.58)。
- Python 3.11.5，Conda 23.7.4；当前 base 无 PyTorch 和 OpenCV。
- Docker、Docker Compose、FFmpeg 未安装。
- Debian 包管理器未发现 `libcudnn8`/`libcudnn8-dev`；cuDNN 状态仍为未验证。
- 项目所在文件系统约 916 GB，总可用约 293 GB，使用率 67%。
- 适合创建独立 Conda 环境 `motpose`，不建议污染 base 或复用其他项目环境。

完整事实与命令结果见 `environment/system_info.txt`。

## 当前风险

- OpenPose/Caffe 较旧，CUDA 11.3、GCC 9.4 和系统依赖的实际构建兼容性未验证。
- PyTorch CUDA 和 cuDNN 尚未通过 smoke test，不能宣称深度学习环境已就绪。
- Docker/Compose 与 FFmpeg 缺失，分别阻塞 CVAT 和标准视频处理。
- 尚无经用户确认授权的 10 至 30 秒多人测试视频。
- YOLO 权重、DeepSORT 实现及版本尚未批准下载或锁定。
- 并行新增的 `tasks/DECISIONS.md` 中 D004 将 T01 范围缩减标成“已确认”，但本轮没有收到用户对此范围变更的明确确认；执行时仍以用户原始 T01 要求和 `tasks/CURRENT_TASK.md` 为准，等待用户裁决。
- 并行审查建议改变全局视频忽略规则，但用户明确要求 `.gitignore` 至少包含 `*.mp4`、`*.avi`、`*.mov`、`*.mkv`，因此本轮没有擅自移除这些规则。

## 下一步建议

用户批准后，先创建 `motpose` Python 3.10 隔离环境，再按安装当天的 PyTorch 官方矩阵安装并执行 RTX 3090 smoke test。随后安装 FFmpeg，固定 YOLO 与 DeepSORT 实现版本，最后选择一段短视频运行最小 MOT 流水线。CVAT 和 OpenPose 应分别单独审批，不与第一批 Python 依赖同时大规模安装。

建议批准后的下一条命令：

```bash
conda create -n motpose python=3.10 pip
```

## 需要用户确认的事项

1. 是否批准创建 `motpose` 并下载 Python/PyTorch/YOLO/DeepSORT 依赖。
2. 是否批准安装系统 FFmpeg。
3. 是否批准安装 Docker Engine/Compose 并拉取固定版本 CVAT 镜像。
4. 是否批准下载并源码构建 CMU OpenPose BODY_25 及模型。
5. 请指定第一段 10 至 30 秒多人视频，并确认数据使用和标注授权。
6. 是否认可并行文档 D004 对 T01 的范围缩减；未确认前不执行该范围变更。
