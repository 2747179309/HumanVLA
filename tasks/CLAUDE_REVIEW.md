# Claude 对 Codex 初始化结果的审查

审查日期：2026-07-11  
审查人：Claude  
审查对象：Codex 在 2026-07-11 执行的初始化工作  

---

## 一、审查总评

Codex 在初始化阶段完成了三件事：
1. 创建了完整的项目目录骨架
2. 编写了治理文档（AGENTS.md, README.md）和上下文文件（PROJECT_CONTEXT, RESEARCH_SCOPE, DATA_SCHEMA, PAPER_CLAIMS）
3. 执行了只读环境审计

总体质量：**中上**。文档内容基本合理，但仍发现了若干需要修正的问题。

---

## 二、逐项审查

### 2.1 目录结构

**评审：通过，有一个建议**

优点：
- 目录层次清晰，data/ 区分 raw/processed/mot/openpose，scripts/ 按功能分目录，experiments/ 按实验编号组织
- 关键目录均使用 .gitkeep 占位，Git 可追踪空目录结构
- 符合项目治理文档描述的数据流

建议：
- `data/processed/` 的 .gitignore 中有 `data/processed/**/*.npy` 等规则——但在当前骨架阶段，这些文件尚不存在。后期需确认该目录下的 .parquet 等文件是否被妥善排除
- 建议在 `configs/` 目录下补充一个 README.md 说明各配置文件用途和格式要求

### 2.2 DATA_SCHEMA 字段审查

**评审：基本通过，有补充建议**

字段设计完整性：

| 方面 | 评价 |
|------|------|
| 身份字段（video_id, track_id, subject_id） | ✅ 语义清晰，区分度足够 |
| 空间字段（bbox_xyxy, keypoints） | ✅ 格式定义明确 |
| 时间字段（frame_index, timestamp_sec） | ✅ 双字段设计合理 |
| 标注字段（action_id, action_label, language_instruction） | ✅ 覆盖当前需求 |
| 元数据（source, annotation_version, occluded） | ✅ 基本足够 |

应补充或明确的字段：

1. **`confidence`** — 当前 DATA_SCHEMA 中 bbox_xyxy 没有记录检测置信度。对于 MOT 评估（MOTA、IDF1）和质量控制，每帧的检测置信度是必要的。建议补充 `detection_confidence: number`。

2. **`track_quality` 或 `review_status`** — 人工复核后，需要标记每帧轨迹的质量：`auto`（未复核）、`reviewed_ok`（复核通过）、`reviewed_fixed`（已修正）、`flagged`（待讨论）。当前 schema 中缺少这一字段。

3. **`camera_id`** — 当前 schema 假设单视频，但未来多视角采集需要区分相机。建议预留 `camera_id: string/null`。

4. **`keypoints` 的 confidence 字段** — 已在 `keypoint_confidence` 冗余提取，这是合理的设计，便于质量控制查询。但建议补充说明：`keypoint_confidence` 是派生字段，不得手动修改。

5. **`action_label` 的受控词表** — DATA_SCHEMA 提到"受控动作词表标签"但未定义词表。建议在 `data/action_labels/` 中维护一份 `taxonomy.yaml` 或 `taxonomy.json`。

6. **分数字段精度** — bbox 坐标为像素整数还是浮点数？keypoints 坐标同理。建议明确类型：`bbox_xyxy` 建议为整数像素，`keypoints[*][0:2]` 为浮点像素坐标。

### 2.3 .gitignore 规则审查

**评审：需要两处修正**

当前规则：

```
# Video and model artifacts
*.mp4 *.avi *.mov *.mkv
*.pt *.pth *.onnx *.engine
checkpoints/
```

问题 1：**视频文件规则过于激进**

`*.mp4` 和 `*.avi` 等规则作用于全仓库。这意味着如果将来在 `data/raw_videos/` 之外有任何演示视频（如结果可视化视频放在 `results/mot/` 下），也会被忽略。实际上 `data/raw_videos/*` 已经有专门的忽略规则。

但更重要的是：**结果视频（如带 ID 追踪的可视化视频）不应被忽略**——它们是实验输出的重要证据，且文件大小通常可控（一段 10-30 秒的短视频通常 < 50MB）。

**建议修改**：将 `*.mp4`、`*.avi`、`*.mov`、`*.mkv` 限制为仅忽略原始数据目录下的视频：

```gitignore
# Raw video data (large, user-provided)
data/raw_videos/*.mp4
data/raw_videos/*.avi
data/raw_videos/*.mov
data/raw_videos/*.mkv
```

同时保留 `results/` 下特定格式的结果视频不被忽略（当前 results/mot/* 已被忽略，需评估是否改为不忽略可视化的 .mp4）。

问题 2：**模型权重文件规则可能遗漏恢复需求**

`*.pt`、`*.pth`、`*.onnx`、`*.engine` 全局忽略是合理的（这些文件通常很大），但建议在 `configs/` 或 `environment/` 中维护一个 `MODEL_REGISTRY.md` 记录所有使用的模型名称、下载链接、SHA-256 和用途。否则未来复现时无法确定使用了哪些权重。

问题 3：**tools/ 目录整体忽略**

`tools/openpose/` 和 `tools/cvat/` 被忽略是合理的（它们是大体积外部仓库）。但建议同时跟踪以下内容：
- 使用的 commit hash
- 应用的本地补丁（如有）
- 构建配置和 CMake 参数

建议在 `environment/setup_notes.md` 相关的构建部分或独立的 `tools/README.md` 中记录。

**规则检查结论**：
- 不会误删重要文件 ✅
- 视频文件规则应限制范围 ⚠️
- 结果可视化视频可能被误忽略 ⚠️
- tools/ 目录忽略合理但需补充记录 ⚠️

### 2.4 CURRENT_TASK 审查

**评审：任务描述合理，但范围较大**

T01 标题为"新电脑环境审计与 DeepSORT/OpenPose 工作区初始化"，内容包括：
1. 环境审计（已完成）
2. 判断是否适合创建 motpose 环境（已完成）
3. 给出安装推荐方案（已完成）
4. 制定最小测试计划（已完成）
5. 不开始论文写作/下载大数据/长时间训练（遵守中）

问题：
- T01 的"完成标准"包括"一段经确认的短视频完成 MOT、人工复核和 BODY_25 关联闭环"——这实际上覆盖了 T02-T08 的全部内容
- 建议将 T01 的完成标准缩小为"环境审计完成 + 安装方案经用户批准"
- T02-T08 应分别有各自独立的完成标准

当前不需要修改 CURRENT_TASK.md，但在用户批准安装后应更新。

### 2.5 是否擅自改变研究方向

**评审：未发现改变方向**

Codex 的初始化工作与用户指定的研究方向一致：
- 项目定位为"低成本数据构建框架"而非"新 VLA 模型" ✅
- 当前优先 MOT + OpenPose 流水线 ✅
- experiment_lab_notebook.md 的实验规划在纸面上是合理的（但范围问题见下一节）✅
- PAPER_CLAIMS.md 明确约束了允许和禁止的表述 ✅

未发现以下违规：
- 未声称要训练新的大模型
- 未声称替代 OpenVLA
- 未声称 SOTA
- 未修改论文主线

### 2.6 是否存在未验证即写入的实验结论

**评审：发现一项需要注意的事项**

`experiment_lab_notebook.md` 中 E5（策略学习验证）标注：

```
| E5 | 策略学习验证 | 成功率, MSE, Loss曲线 | 自建数据集 + ACT/DP | P1-High | 🔄 可行性已验证 |
```

并在"已完成"部分列出了：
- LeRobot 环境搭建 ✅
- PushT 数据集加载+可视化 ✅
- ACT CPU 100步训练 ✅
- PushT 仿真评估 ✅
- 原型数据集构建 ✅

**问题**：这些"已完成"的标记来自旧电脑的旧实验。在当前新环境（`environment/system_info.txt`）中：
- PyTorch 未安装
- 无任何 LeRobot 相关环境
- 无 checkpoint 文件
- 无数据集文件

**结论**：experiment_lab_notebook.md 中的 E5 完成标记属于历史经验记录，不属于"当前环境已验证"。如果该文档被视为"当前项目状态"，建议将 E5 状态改为 `⬜ 未在当前环境复现` 并添加脚注说明来源。

这不视为 Codex 编造实验结果——这些条目描述的是 Codex 在旧会话中的工作记忆。但在当前新环境中，需要重新验证。

### 2.7 环境兼容性风险评估

**评审：setup_notes.md 中的方案基本合理，有一项补充风险**

setup_notes.md 建议：
- motpose 使用 Python 3.10
- 使用 PyTorch 官方二进制（自带 CUDA runtime）
- OpenPose 在 tools/openpose/ 源码构建
- CVAT 使用 Docker Compose

补充风险：

1. **PyTorch 与 CUDA 11.3 兼容性**：当前 nvcc 为 11.3。PyTorch 官方提供的 CUDA 11.8/12.1 二进制自带 runtime，可以在驱动 550 上运行（因为驱动支持到 CUDA 12.4）。但需要注意：
   - 如果后续有任何需要从源码编译的 CUDA 扩展（如 OpenPose 的 Caffe），它们会依赖系统的 nvcc 11.3。PyTorch 自带的 CUDA runtime 与系统 nvcc 版本不匹配可能导致 ABI 问题。
   - **建议**：PyTorch 安装后立即运行 `torch.cuda.is_available()` + `torch.cuda.get_device_capability()` 并记录。

2. **OpenPose 与新 GCC 的兼容性**：CMU OpenPose 原始开发时的 GCC 版本较旧。当前系统的 GCC 9.4.0 可能触发 Caffe 编译警告或错误。setup_notes.md 已注意到此风险但未提供应急方案。建议预先调查：
   - MMPose 作为 BODY_25 的备选方案
   - 或在 Docker 中构建 OpenPose（虽然 setup_notes.md 建议源码构建）

3. **deep-sort-realtime 的维护状态**：setup_notes.md 推荐评估 `deep-sort-realtime`，但该包的 PyPI 版本和 GitHub 仓库维护频率需在安装前确认。备选方案包括直接使用 DeepSORT 的核心算法（Kalman + Hungarian + 外观特征）自主实现。

### 2.8 tasks/CODEX_REPORT.md 缺失

**评审：需补充**

AGENTS.md 第 11 条要求"每轮工作结束必须更新 `tasks/CODEX_REPORT.md`"。Codex 尚未创建此文件。

这不影响当前工作，但应在 Codex 下次执行任务时补齐。

当前环境审计的内容部分记录在 `logs/daily/2026-07-11.md`，但不构成符合模板的 Codex 报告。

---

## 三、发现的问题汇总

| 编号 | 类别 | 问题 | 建议 |
|------|------|------|------|
| I1 | 数据模式 | 缺少 detection_confidence 字段 | 在 DATA_SCHEMA 中补充 |
| I2 | 数据模式 | 缺少 track review_status 字段 | 补充人工复核状态标记 |
| I3 | 数据模式 | 缺少 camera_id 预留 | 补充可空字段 |
| I4 | 数据模式 | action_label 词表未定义 | 创建 data/action_labels/taxonomy.yaml |
| I5 | Git 忽略 | *.mp4 等规则过于激进 | 限制为 data/raw_videos/ 范围内 |
| I6 | Git 忽略 | 结果可视化视频可能被误忽略 | 评估 results/mot/ 是否应保留小体积 .mp4 |
| I7 | Git | .git 目录无效 | 初始化 Git 仓库 |
| I8 | 任务 | T01 完成标准过大 | 缩小为环境审计 + 安装批准 |
| I9 | 实验 | E5 "可行性已验证"在当前环境未复现 | 标注为"待复现" |
| I10 | 环境 | OpenPose 构建兼容性无备选方案 | 调查 MMPose 等备选 |
| I11 | 文档 | CODEX_REPORT.md 缺失 | 下次执行任务时补齐 |

---

## 四、不建议直接修改的内容

以下内容建议保留现状、在下一次审查或用户确认后再修改：

1. **experiment_lab_notebook.md 的实验范围** — 目前仅作模板使用，不宜在无用户输入的情况下删除或缩减实验条目
2. **CURRENT_TASK.md 的任务描述** — 等到用户批准安装方案后再缩小完成标准
3. **TASK_QUEUE.md** — T02-T10 的依赖关系当前合理，暂不需要调整

---

## 五、审查结论

Codex 初始化工作质量合格。治理文档、数据模式和环境审计是本次初始化的亮点。发现的问题（I1-I11）多数为补充性建议，而非根本性错误。

需要在进入执行阶段前解决的关键问题（按优先级）：
1. **I7**：初始化 Git 仓库（保护原始数据的基础）
2. **I5**：修正 .gitignore 视频规则（防止结果视频被误忽略）
3. **I1-I3**：补充 DATA_SCHEMA 字段（影响后续数据格式一致性）
4. **I10**：为 OpenPose 构建准备备选方案

建议在用户批准安装方案后、Codex 开始安装之前，先完成 I7 和 I5。
