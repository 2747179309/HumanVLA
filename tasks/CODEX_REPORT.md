# Codex 工作报告

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
