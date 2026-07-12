# Codex 工作报告

## Codex CLI自动批准设置（2026-07-12）

- 本机`codex-cli 0.144.1`已不提供`--full-auto`参数。
- 在`/home/a531/.codex/config.toml`设置`approval_policy = "never"`和`sandbox_mode = "workspace-write"`。
- `codex --strict-config doctor --summary --ascii`确认配置已加载，显示`restricted fs + restricted network · approval Never`。
- 保留workspace沙箱，没有启用`danger-full-access`或`--dangerously-bypass-approvals-and-sandbox`。
- Doctor另报WebSocket/HTTP provider连通性警告，与本次自动批准配置无关。

## T04 人工复核结果整理（2026-07-12）

### CSV与输出

- `three-people-walking_T04_review.csv`：240条逐帧记录，完整覆盖0-239，字段和枚举值有效；与关联JSONL自动状态完全一致。
- `three-people-walking_pose_quality_review.csv`：5条帧段级质量记录，覆盖19个问题帧，区间无重叠；该文件按设计不是240条逐帧记录。
- 两份人工CSV均未修改。
- 新增 `results/association/three-people-walking/manual_review_summary.json`，SHA-256 `ae2916482543af9e9a921a076b4caa8063fd2f24d03d17a38334fb1e20d0fde5`。

### 人工复核统计

- 身份关联错误0帧；P001/P002/P003未发现身份交换。帧2-239的238个可复核帧全部`subject_id_correct=yes`。
- P001持杯手臂的OpenPose关键点定位误差13帧：15-19、54-61；身份及骨架归属正确。
- identity mix 3帧：43-45；pose assignment人工判定失败，必须排除出后续平滑和训练数据。
- 帧46恢复正常。
- phantom pose 1帧：188。
- out-of-scope unmatched pose 2帧：207-208。
- 237帧人工`pass`、3帧`fail`；其余221帧未报告肉眼可见异常。

### 边界与当前问题

- 43-45的跨人物手臂连接没有修复，也不得用滤波强制修复。
- 15-19、54-61仍有原生局部定位误差，后续若处理必须另存派生结果。
- 本轮未修改关联JSONL、OpenPose JSON或视频，未运行新实验，未开始T05。
- 建议提交信息：`docs: finalize T04 human association review`。

## T04 自动骨架-轨迹关联（2026-07-12）

### 状态

- 创建并运行 `scripts/association/associate_pose_to_tracks.py`。
- 创建并运行独立验证器 `scripts/association/validate_association.py`。
- 240帧自动关联和格式验证完成，等待用户人工抽查；未宣称T04最终通过，未开始T05。

### 输入路径裁决

- `data/mot/subject_maps/three-people-walking_subject_map.csv` 实际不存在。
- 自动选择 `data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv`。
- 人工review CSV没有逐帧修正框；track 1/2/3均为`no_issue`，因此使用`results/mot/three-people-walking/tracks_raw.jsonl`的逐帧框，并以人工subject map过滤。
- track 4为`confirmed_false_positive`，没有进入关联。

### 输出与结果

- `data/openpose/associated/three-people-walking.jsonl`：726行。
- `results/association/three-people-walking/summary.json`。
- `results/association/three-people-walking/association_visualization.mp4`：H.264、2160x3840、240帧。
- `results/association/three-people-walking/manual_review_template.csv`：20个待复核帧。
- `logs/runs/T04_POSE_TRACK_ASSOCIATION.md`：完整参数、哈希、命令和异常记录。

真实统计：714/714个现有白名单轨迹实例自动匹配，matched rate 1.0；unmatched track 0，unmatched pose 8，ambiguous pose 3，phantom pose 1。P001/P002/P003各有238个matched frame。平均match cost 0.173401，最大0.417309，均低于0.5阈值。

独立验证器通过：726个pose逐条回查raw JSON一致，raw confidence包括大于1的值均未修改；同帧subject无重复；六个异常帧状态正确；raw目录哈希保持`c174f901...f0a8f`。

### 当前风险

- matched rate的分母是714个实际track实例。帧0-1没有DeepSORT confirmed track，对应6副pose保留为unmatched。
- 43-45帧虽然各自动匹配3个主人物pose，但P003/P001处于全视频低分区域，identity mix仍需人工确认。
- 188、207、208的额外pose已按人工规则自动隔离，但仍应在可视化中确认。
- 自动验证仅证明格式、一致性和约束执行，不证明身份关联人工正确。

### 真实命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/association/associate_pose_to_tracks.py \
  --video-id three-people-walking --iou-weight 0.6 \
  --center-distance-weight 0.4 --cost-threshold 0.5 \
  --run-id 20260712_T04_001

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/association/validate_association.py \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --summary results/association/three-people-walking/summary.json \
  --pose-json-dir results/openpose/three-people-walking/raw_json \
  --subject-map data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv \
  --manual-review-summary results/openpose/three-people-walking/manual_review_summary.json \
  --visualization results/association/three-people-walking/association_visualization.mp4 \
  --manual-review-template results/association/three-people-walking/manual_review_template.csv \
  --expected-frames 240
```

## T03 人工复核收尾（2026-07-12）

### 状态与文件

- 人工 CSV 字段、数据类型、6 个唯一帧和必填文本均有效，未修改用户判断。
- 新增 `results/openpose/three-people-walking/manual_review_summary.json`。
- 更新 `logs/runs/T03_OPENPOSE_SMOKE_TEST.md` 和 `tasks/CODEX_REPORT.md`。
- 按项目规则将用户确认的收尾处置记录为 `tasks/DECISIONS.md` D021。
- 未修改 raw JSON，未开始 T04。

### 人工结论

- 视觉骨架异常帧共 6 帧，不是 79 帧。
- 43、44、45：重叠造成 `identity_mix`，收尾标记 `ambiguous_pose`；保留人工决定 `needs_recheck`，不强制修复。
- 188：非人物区域 phantom，保留人工决定 `exclude_extra_pose`，下游排除额外骨架。
- 207、208：远处真实人物但无对应 DeepSORT 轨迹，标记 `unmatched_pose`；保留人工决定 `keep_raw_exclude_main`，不纳入三名主要人物数据。
- 79 帧的 101 个 confidence 大于 1 是独立数值范围警告，不等同于视觉异常；原值保持不变。

### Raw 完整性

- 240 个 JSON，帧号连续 0-239，0 个解析/结构/75 长度错误。
- 每帧人数与 `summary.json` 一致；6 个人工异常帧均有 4 个 pose 记录。
- raw 目录聚合 SHA-256 为 `c174f901c73646b64b3f4a4ebbf3bb99c41534405324757e951a2449b14f0a8f`，按排序后的 `filename + NUL + raw bytes` 计算。

### 验收判断与未解决项

- T03 验收材料齐全，可以提交 Claude 验收。
- `summary.json` 仍如实记录严格验证 `false`，唯一原因是当前协议 `[0,1]` 与 OpenPose 原生 1.0002-1.03636 数值不一致；需 Claude 裁决是否作为带警告的协议例外。
- 43-45 的姿态归属仍有歧义且未修复；188、207、208 的额外 pose 需要在未来下游处理中按人工决定排除，但本轮没有执行关联或过滤。

### 执行核对

```bash
python -c "检查人工 CSV 字段、类型、唯一帧和必填值"
python -c "全量解析 240 个 raw JSON，并交叉检查 summary.json"
sha256sum data/openpose/manual_gt/three-people-walking_visual_review.csv \
  results/openpose/three-people-walking/summary.json \
  results/openpose/three-people-walking/suspicious_frames.csv
python -c "验证 manual_review_summary.json 与人工 CSV 决定一致"
```

## T02 人工结论修订与重新验收（2026-07-12）

- 用户最终确认：第 86 帧 `track_id 4` 没有对应真实人物，是单帧 False Positive，raw conf=`0.343935`（约 `0.344`）。
- raw DeepSORT 五个输出文件保持原样，SHA-256 与 T02 日志记录一致。
- `data/mot/reviewed/three-people-walking.csv` 已验证：ID 4 为 `confirmed_false_positive`，`include_in_main_dataset=0`。
- subject map 已验证：仅包含 `1->P001`、`2->P002`、`3->P003`；ID 4 没有 `subject_id`。
- reviewed CSV SHA-256 为 `85c2261629156b8cd673d010882d25e9219ed812d7909cced375b57eb58b0643`；subject map SHA-256 为 `5d451ef1cc3dbbeccc4d200dd5b8b996f98daa7e6a110c0fd344406642a79dbb`。
- 下游排除规则：OpenPose 关联和数据集生成仅使用 subject map 中 `include_for_pose=1` 的 ID 1/2/3，禁止关联或导出 ID 4。
- T02 自动输出、人工复核和 subject map 重新验收通过，T02 关闭。本轮未运行任何新实验，也未启动 OpenPose。

## 日终核对（2026-07-11 18:47 CST）

### 核对范围

本轮响应用户“停止新工作”的要求，只读取并核对 Git、环境、最终 T02 文件、metadata、哈希和已有日志；没有安装软件、执行新实验、修改脚本或覆盖实验结果。

### 真实文件状态

- 最终结果目录：`results/mot/three-people-walking/`，包含用户要求的 5 个输出文件。
- `tracked.mp4`：48,385,300 字节，H.264/yuv420p，2160x3840，23.976 FPS，240 帧，10.010010 秒。
- `tracks_raw.jsonl`：132,968 字节，715 行。
- `mot/gt.txt`：47,663 字节，715 行；仍是自动预标注而非真值。
- `mot/labels.txt`：56 字节，5 行。
- `metadata.json`：2,539 字节；指标、环境、输入哈希和代码提交与 Run 日志一致。
- 原视频 SHA-256：`1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd`。
- YOLO 权重 SHA-256：`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`。

### 今日提交与工作树

- Git 提交链：`27b4c34` -> `3946e06` -> `29cda6e` -> `3411faf` -> `8235143`。
- 当前 HEAD：`8235143` (`docs: record T02 MOT smoke test`)。
- 当前未提交且非本轮收尾产生的任务文档：`tasks/CLAUDE_REPORT.md`、`tasks/CLAUDE_REVIEW.md`、`tasks/CURRENT_TASK.md`、`tasks/DECISIONS.md`、`tasks/TASK_QUEUE.md`。
- 当前未跟踪且非本轮收尾产生的文件：`tasks/T02_ACCEPTANCE_CRITERIA.md`。
- 本轮收尾修改：`logs/daily/2026-07-11.md`、`logs/runs/T02_MOT_SMOKE_TEST.md`、`tasks/CODEX_REPORT.md`。
- 本轮核对期间，并行进程在 `logs/daily/2026-07-11.md` 追加了“Claude 第二轮审查”和“明天任务”，同时更新 `tasks/CLAUDE_REVIEW.md`；Codex 未改写这些段落。提交 daily log 时这些并行内容会一同进入提交，需先人工确认。

### 未解决问题

1. T02 自动流水线和人工 MOT 复核已经完成，reviewed CSV 与 subject map 已重新验收。
2. 第 86 帧 `track_id 4` 已人工确认为单帧 False Positive，必须从下游处理排除。
3. 已有 `track_id -> subject_id` 映射，但尚无公开 MOT 指标。
4. DeepSORT 旧依赖、系统 cuDNN 8 链接警告、ROS Python 3.8 `PYTHONPATH` 污染和无关 APT 源超时仍存在。
5. 原视频、模型权重和结果目录被 Git 忽略；当前可复现性依赖环境锁定文件、metadata 和 SHA-256，而非仓库内结果二进制。
6. 工作树包含多份并行任务文档修改，提交前必须逐项审阅，避免把互相矛盾的任务状态一起提交。

### 建议 Git 提交方式

人工确认 daily log 中的并行 Claude 段落后，仅提交三份收尾日志，避免夹带其他任务文档：

```bash
git add logs/daily/2026-07-11.md logs/runs/T02_MOT_SMOKE_TEST.md tasks/CODEX_REPORT.md
git commit -m "docs: finalize 2026-07-11 T02 records"
```

随后单独审查 `tasks/` 中的并行修改，再决定是否用独立提交，例如 `docs: align T02 task and acceptance criteria`。在审查完成前不建议执行 `git add .`。

## T03 执行更新（2026-07-12）

### 状态

- OpenPose BODY_25 CUDA 构建成功，RTX 3090 单帧和 240 帧视频运行成功。
- 规定输出完整，渲染视频全片解码通过。
- 严格 JSON 验证未通过：原始 OpenPose 输出有 101 个置信度值大于 1，最大 1.03636，违反当前协议 `[0,1]` 约束。
- raw JSON 保持原样；未关联 DeepSORT ID，未开始 T04、动作标注或训练。

### 新建文件

- `environment/requirements/openpose-build.txt`
- `scripts/openpose/run_openpose.sh`
- `scripts/openpose/validate_openpose_json.py`
- `logs/runs/T03_OPENPOSE_SMOKE_TEST.md`
- `results/openpose/three-people-walking/raw_json/`（240 个自动输出 JSON，Git 忽略）
- `results/openpose/three-people-walking/rendered.mp4`（Git 忽略）
- `results/openpose/three-people-walking/rendered_openpose.avi`（中间件，Git 忽略）
- `results/openpose/three-people-walking/metadata.json`（Git 忽略）
- `results/openpose/three-people-walking/summary.json`（Git 忽略）
- `results/openpose/three-people-walking/human_spot_check.md`（Git 忽略）

### 修改文件

- `logs/daily/2026-07-12.md`：追加 T03 真实执行摘要。
- `tasks/CODEX_REPORT.md`：本节。

### 执行命令

主要命令如下；完整 CMake 参数、失败重试和日志路径见 `logs/runs/T03_OPENPOSE_SMOKE_TEST.md` 与 `environment/requirements/openpose-build.txt`。

```bash
sudo apt-get install -y libprotobuf-dev protobuf-compiler libleveldb-dev \
  libsnappy-dev liblmdb-dev libatlas-base-dev
git clone --recursive https://github.com/CMU-Perceptual-Computing-Lab/openpose.git tools/openpose
cmake -S tools/openpose -B tools/openpose/build [记录中的 CUDA/cuDNN/sm_86 参数]
cmake --build tools/openpose/build --parallel 8
scripts/openpose/run_openpose.sh --video data/raw_videos/three-people-walking.mp4 \
  --output-dir results/openpose/three-people-walking \
  --openpose-root tools/openpose --net-resolution "-1x368" \
  --number-people-max 6 --gpu 0
/home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/validate_openpose_json.py [T03 日志中的完整参数]
ffmpeg -v error -i results/openpose/three-people-walking/rendered.mp4 -f null -
```

### 环境检查结果摘要

- RTX 3090 24 GiB，NVIDIA 驱动 550.144.03；GPU 运行成功。
- 项目 CUDA Toolkit 11.3、cuDNN 8.6.0、GCC 9.4.0、CMake 3.16.3。
- OpenPose commit `5c5d96523ef917bd30301245fdc8343937cae48d`；Caffe Ampere commit `1807aadafc934a2a1341021620981cb1ec526b83`。
- BODY_25 模型 MD5 `78287b57cf85fa89c03f1393d368e5b7`，与官方 CMake 声明一致。
- 没有修改 NVIDIA 驱动、系统 CUDA 或系统 Python。

### 真实结果

- 240 个 JSON，0 个解析异常，0 个长度异常，0 个无骨架帧。
- 234 帧检测 3 人，6 帧检测 4 人；总计 726 个 person 实例。
- 平均 3.025 人/帧，平均 24.177686 个有效关键点/实例。
- 肩、肘、腕组缺失率分别为 0.550964%、0.964187%、1.515152%。
- OpenPose 处理 34.37 秒，约 6.983 FPS。
- `rendered.mp4` 为 H.264、2160x3840、23.976 FPS、240 帧，FFmpeg 全片解码无错误。
- 严格验证 `false`：101 个置信度值在 1.0002-1.03636，涉及 79 帧、96 个 person 记录。

### 当前风险

- 当前协议把置信度限定为 `[0,1]`，但本次官方 OpenPose/CUDA 原始输出存在少量大于 1 的分数；在协议决定前不得静默裁剪或宣称验证通过。
- 帧 43、44、45、188、207、208 出现第 4 个低完整度骨架，需人工判断为背景人物、重复碎片或 phantom。
- OpenPose 使用非商业学术许可证；未来若涉及商业用途，需要另行核查许可。
- `people` 数组顺序不是身份，T03 结果尚不能直接映射到 P001-P003。

### 下一步建议和需要确认

- 可将完整输出提交人工检查，重点复核 6 个四人帧、腕部遮挡与左右方向。
- 需要用户决定协议如何保存和解释 OpenPose 原生大于 1 的置信度分数；在决定前 T03 不标记为严格验收通过。
- 本轮不启动 T04，也不修改 raw JSON。

## T02 执行更新（2026-07-11）

### 状态

- `motpose` 环境、代码、严格环境检查和单段本地视频自动 smoke test 已完成。
- 视频格式和数据一致性检查通过；只做了 10 个整秒帧及第 86、120 帧的抽样可视检查。
- T02 人工复核文件和 subject map 已由用户最终确认并重新验收，T02 可标记为 `COMPLETED`。
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
- ID 1/2/3 各持续 238 帧；raw 中 ID 4 仅在第 86 帧出现，人工最终确认其没有对应真实人物，是 `confirmed_false_positive`。
- 检测 62.291 FPS；DeepSORT 跟踪 31.965 FPS。
- 最终视频为 H.264/yuv420p、240 帧、10.010 秒；JSONL、MOT 10 列格式、labels 与 metadata 一致性检查通过。
- 自动输出不是 ground truth，`mot/gt.txt` 只是用户指定的 MOTChallenge 交换文件名。

### 当前风险与异常

- 人工复核 CSV 记录 ID 1/2/3 的 id_switch、fragmentation、missing 均为 `no_issue`，ID 4 为唯一 `confirmed_false_positive`。
- `deep-sort-realtime 1.3.2` 依赖已弃用的 `pkg_resources`，当前通过固定 setuptools 80.9.0 兼容。
- 系统 `ldconfig` 报告手工 cuDNN 8 文件不是符号链接；本轮未修改，且 PyTorch 使用 wheel 内置 cuDNN 9.1。
- shell 的 ROS Foxy `PYTHONPATH` 指向 Python 3.8，运行必须继续隔离该变量。
- APT 更新时无关 `antigravity` 第三方源超时；Ubuntu 镜像和 FFmpeg 安装成功，未修改该源。

### 下一步建议

保留 raw 输出；后续 OpenPose 关联和数据集生成仅允许使用 subject map 中的 P001/P002/P003，并排除 ID 4。本轮不启动新实验，当前单视频结果仍不作为公开 MOT 论文指标。

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
