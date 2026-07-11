# Claude 项目状态审查

审查日期：2026-07-11  
审查人：Claude（科研负责人角色）  
审查范围：HumanVideo2VLA 项目全部已有文件  
是否执行代码：否  

---

## 一、已读取的文件清单

### 治理与项目文档
- `AGENTS.md` — 工作规则，已完整阅读
- `README.md` — 项目概述与快速入口，已完整阅读
- `experiment_lab_notebook.md` — E1-E6 实验设计方案，已完整阅读

### 上下文文件
- `context/PROJECT_CONTEXT.md` — 项目定位与优先级，已完整阅读
- `context/RESEARCH_SCOPE.md` — 研究范围与边界，已完整阅读
- `context/DATA_SCHEMA.md` — 数据模式定义，已完整阅读
- `context/PAPER_CLAIMS.md` — 论文主张边界，已完整阅读

### 任务文件
- `tasks/CURRENT_TASK.md` — 当前任务 T01，状态 IN_PROGRESS
- `tasks/TASK_QUEUE.md` — T01-T10 任务队列
- `tasks/DECISIONS.md` — D001-D003 三项重要决定

### 环境文件
- `environment/system_info.txt` — 系统审计报告（只读审计，未安装软件）
- `environment/setup_notes.md` — 安装与执行计划（仅计划，未执行）
- `environment/requirements/README.md` — 依赖记录说明（尚无实际内容）

### 日志文件
- `logs/daily/2026-07-11.md` — 今日工作日志
- `logs/runs/README.md` — 运行日志模板

### 配置文件
- `.gitignore` — Git 忽略规则
- `.vscode/settings.json` — VS Code 编辑器配置
- `.vscode/extensions.json` — 推荐扩展

### 已检查但缺失的文件
- `tasks/CODEX_REPORT.md` — **不存在**（README.md 中引用但未创建）
- `tasks/CLAUDE_REVIEW.md` — **不存在**（本应记录 Codex 工作审查）
- `tasks/CLAUDE_PROJECT_REVIEW.md` — **不存在**（本次创建）
- `tasks/CLAUDE_REPORT.md` — **不存在**（本应记录 Claude 工作汇总）

---

## 二、当前已完成内容

### 2.1 项目治理框架 ✅
- 工作规则（AGENTS.md）清晰定义了数据约束、工作边界和协作规范
- README.md 提供了项目概览和入口指引
- 研究范围（RESEARCH_SCOPE.md）明确划定当前阶段的"做"与"不做"
- 论文主张边界（PAPER_CLAIMS.md）约束了允许和禁止的表述

### 2.2 数据模式定义 ✅
- DATA_SCHEMA.md 定义了完整的帧级主记录 JSONL 格式
- 区分了 track_id、subject_id、action_id 等关键字段语义
- 定义了 BODY_25 存储约束、MOT 文件结构、校验规则
- 字段设计合理，覆盖了当前流水线所需

### 2.3 环境审计 ✅
- system_info.txt 提供了只读审计：Ubuntu 20.04、RTX 3090、CUDA 11.3、Python 3.11.5
- 判定适合创建独立 `motpose` Conda 环境
- 明确指出 Docker、FFmpeg、PyTorch、OpenCV、cuDNN 均未安装或未验证

### 2.4 实验设计框架 ✅
- experiment_lab_notebook.md 规划了 E1-E6 六个实验
- 每个实验有明确目的、数据集、对比方法、指标、执行步骤、结果模板
- 实验体系覆盖面合理

### 2.5 目录结构骨架 ✅
- 完整的 data/、scripts/、configs/、experiments/、results/、logs/、paper/ 骨架
- 所有叶子目录均有 .gitkeep 占位

### 2.6 重要决策记录 ✅
- D001：track_id vs subject_id 区分和人工复核要求
- D002：OpenPose people 数组下标不可作为 ID
- D003：motpose/CVAT/OpenPose 环境隔离方案

---

## 三、当前未完成内容

### 3.1 软件环境 ❌
- `motpose` Conda 环境尚未创建
- PyTorch、OpenCV、FFmpeg 均未安装
- Docker Engine 和 Docker Compose 未安装
- cuDNN 状态未验证
- OpenPose 未构建
- CVAT 未部署

### 3.2 核心流水线 ❌
- 无测试视频
- YOLO 检测未运行
- DeepSORT 跟踪未运行
- 无可视化输出
- 无 JSONL/MOT 格式输出
- 无人工复核
- 无 subject_id 映射

### 3.3 脚本与代码 ❌
- 所有 scripts/ 子目录仅含 .gitkeep
- 无可执行代码、无配置参数文件、无模型权重

### 3.4 数据 ❌
- 所有 data/ 子目录仅含 .gitkeep
- 无原始视频、无帧、无标注、无骨架数据

### 3.5 实验执行 ❌
- E1-E6 全部为"未开始"状态
- 仅有 E5 标注"可行性已验证"（但该验证来自旧电脑，当前环境未复现）

### 3.6 文档 ❌
- `tasks/CODEX_REPORT.md` 尚未创建
- 无 MOT 标注协议
- 无 OpenPose 标注协议
- 无 T01 验收标准
- 论文正文尚未开始

### 3.7 版本控制 ❌
- `.git` 目录存在但 git 报告"不是 git 仓库"，版本控制未生效

---

## 四、Codex 已创建的目录和文件

| 类型 | 路径 | 状态 |
|------|------|------|
| 治理 | `AGENTS.md` | ✅ 已创建，内容合理 |
| 治理 | `README.md` | ✅ 已创建，内容合理 |
| 上下文 | `context/PROJECT_CONTEXT.md` | ✅ 已创建 |
| 上下文 | `context/RESEARCH_SCOPE.md` | ✅ 已创建 |
| 上下文 | `context/DATA_SCHEMA.md` | ✅ 已创建 |
| 上下文 | `context/PAPER_CLAIMS.md` | ✅ 已创建 |
| 任务 | `tasks/CURRENT_TASK.md` | ✅ 已创建 |
| 任务 | `tasks/TASK_QUEUE.md` | ✅ 已创建 |
| 任务 | `tasks/DECISIONS.md` | ✅ 已创建 |
| 环境 | `environment/system_info.txt` | ✅ 已创建，审计较完整 |
| 环境 | `environment/setup_notes.md` | ✅ 已创建，方案合理 |
| 环境 | `environment/requirements/README.md` | ✅ 已创建 |
| 实验 | `experiment_lab_notebook.md` | ✅ 已创建，设计详细 |
| 日志 | `logs/daily/2026-07-11.md` | ✅ 已创建 |
| 日志 | `logs/runs/README.md` | ✅ 已创建 |
| 配置 | `.gitignore` | ✅ 已创建 |
| 配置 | `.vscode/settings.json` | ✅ 已创建 |
| 配置 | `.vscode/extensions.json` | ✅ 已创建 |
| 目录 | 完整目录骨架（含 .gitkeep） | ✅ 已创建 |
| 任务 | `tasks/CODEX_REPORT.md` | ❌ **缺失** |
| 任务 | `tasks/CLAUDE_REVIEW.md` | ❌ **缺失** |
| 任务 | `tasks/CLAUDE_REPORT.md` | ❌ **缺失** |
| 代码 | `scripts/` 下所有脚本 | ❌ **全部为空** |
| 配置 | `configs/` 下所有配置 | ❌ **全部为空** |
| 数据 | `data/` 下所有数据 | ❌ **全部为空** |

---

## 五、环境审计是否完整

### 已完成
- OS 版本 ✅
- CPU/内存 ✅
- GPU 型号和驱动 ✅
- nvcc 版本 ✅
- Python/Conda 版本 ✅
- 现有 Conda 环境列表 ✅
- 磁盘空间 ✅
- Git/GCC/CMake 版本 ✅

### 未完成
- cuDNN 状态 ❌（仅检查了 Debian 包，未检查手动安装）
- PyTorch CUDA 可用性 ❌（因未安装 PyTorch，无法验证）
- OpenCV 视频编解码支持 ❌
- FFmpeg 版本和支持的编码器 ❌
- Docker 可用性 ❌（未安装）
- 网络连通性（PyPI、GitHub、Docker Hub）❌
- NVIDIA 驱动与 CUDA 11.3 的实际运行时兼容性 ❌（仅验证了 nvidia-smi）

### 结论
环境审计在"只读"范围内已经比较完整。关键缺口主要在运行时验证层面，这需要先安装才能完成。

---

## 六、当前最大技术风险

| 排名 | 风险 | 严重程度 | 说明 |
|------|------|----------|------|
| 1 | **OpenPose 构建兼容性未知** | 🔴 高 | CUDA 11.3 + gcc 9.4.0 + 未验证的 cuDNN + 较旧的 Caffe 依赖链。CMU OpenPose 已多年未维护，可能在当前工具链上无法直接编译。如果 OpenPose 无法构建，需要考虑替代方案（如 MMPose、ViTPose），但这会改变论文中的 BODY_25 pipeline 设计 |
| 2 | **无测试视频** | 🔴 高 | 所有实验依赖真实视频数据。如果没有合适的多人操作视频，流水线无法验证 |
| 3 | **cuDNN 未验证** | 🟡 中 | 直接影响 PyTorch GPU 训练和 OpenPose 构建 |
| 4 | **.git 无效** | 🟡 中 | 未初始化 Git 仓库，无版本控制保护——原始数据一旦被误改无法恢复 |
| 5 | **旧实验记录不可用** | 🟡 中 | 旧电脑上的 LeRobot/ACT 实验记录、代码和模型权重不可直接获取。E5 标注"可行性已验证"但证据充分性未知 |

---

## 七、当前最大论文风险

| 排名 | 风险 | 严重程度 | 说明 |
|------|------|----------|------|
| 1 | **实验范围过大** | 🔴 高 | experiment_lab_notebook.md 规划的 E1-E6 包含大量需要外部数据集（50Salads, Breakfast, Human3.6M, 3DPW, YouCook2）的实验，且 E1 提出了 7 组方法对比、E3 提出了 7 种组合。这可能远超"低成本数据构建框架"论文的合理范围，且部分实验（如 E1 的 TCN/Transformer 基线对比）可以独立成文 |
| 2 | **核心贡献定义模糊** | 🟡 中 | 论文标题声称"低成本构建语言对齐机器人策略数据集"，但 E1（动作分段）和 E2（MLLM 文本对齐）使用的 GPT-4V、InternVL2 等 API 调用，以及 Human3.6M 等大型公开数据集训练，与"低成本"叙事存在张力。需要明确：哪些组件是贡献、哪些是工具 |
| 3 | **无基线数据** | 🟡 中 | 目前没有任何定量基线。所有结果表都是空模板，在获得第一批真实数据前无法评估实验方案的可行性 |
| 4 | **E5 可行性声明需谨慎** | 🟡 中 | "E5 可行性已验证"来自旧电脑，当前环境未复现。如不能在论文中引用可复现证据，此声明不应该写入 |
| 5 | **消融实验设计可能不够** | 🟢 低 | E6 的七种消融条件仅在三种任务上测试，如果主要 claim 围绕数据构建，可能需要更多关于数据组件的消融 |

---

## 八、下一步最小可执行任务

当前 T01 的正确拆分应该是：

1. **环境准备（需用户批准）**
   - 安装 FFmpeg
   - 创建 `motpose` Conda 环境
   - 安装 PyTorch + OpenCV + ultralytics + deep-sort-realtime
   - 验证 `torch.cuda.is_available()`
   - 冻结环境依赖

2. **获取测试视频（需用户提供）**
   - 确认一段 10-30 秒多人操作视频
   - 登记 SHA-256、FPS、分辨率、帧数、时长
   - 复制到 `data/raw_videos/` 并设为只读

3. **MOT 最小流水线**
   - 运行 YOLO person 检测 + DeepSORT
   - 输出带 ID 可视化视频
   - 输出 JSONL 和 MOT 格式轨迹

4. **人工复核流程**
   - 安装 Docker + CVAT
   - 导入 MOT 结果
   - 检查 ID Switch、断轨、误检、漏检
   - 导出 reviewed MOT
   - 建立 subject_map.csv

5. **OpenPose（MOT 复核后）**
   - 构建/安装 OpenPose
   - 提取 BODY_25
   - 骨架与复核轨迹关联

**当前阻塞项：**
- 等待用户批准安装方案（setup_notes.md 末尾五项确认）
- 等待用户提供测试视频
- 等待 Git 仓库初始化

---

## 九、对 experiment_lab_notebook.md 的初步意见

实验记录手册设计详细，但需要在下一次审查中讨论以下问题：

1. **E1 的 7 组方法对比（C2F-TCN, ASFormer, LTContext, Flow-Only, CLIP-Only, KP-Only, Ours）是否都必要？** 如果论文核心贡献是数据构建框架而非动作分段算法，E1 应聚焦于"我们的数据是否需要分段，分段质量对下游的影响"，而非"我们的分段方法是否 SOTA"。

2. **E2 引入了 GPT-4V、InternVL2、Qwen-VL 三种 MLLM**——这些 API 调用成本和本地部署开销是否与"低成本"主线一致？

3. **E3 声称为 3D 骨架实验，但当前流水线只到 2D BODY_25**。从 2D 到 3D 的提升（VideoPose3D, MotionBERT）需要额外的大量训练和数据集。

4. **experiment_lab_notebook.md 列出的执行顺序是 E3→E1→E2→E4→E5→E6（Week 1-12）**，但 CURRENT_TASK.md 的优先级是先 MOT+OpenPose 再 E1-E6。两者不完全一致，需要统一。

建议在下一次审查中重新对齐实验优先级和范围。

---

## 十、审查结论

项目状态：**框架已搭建，执行尚未开始。**

治理文档和环境审计质量良好。Codex 在初始化阶段完成了合理的文档创建和目录布局，但缺失了 CODEX_REPORT.md 和实际的代码/配置/数据。当前所有实验仍处于"模板"阶段。

**当前最优先的三件事：**
1. 获得用户对安装方案的批准
2. 初始化 Git 仓库，建立版本控制
3. 获取第一段测试视频

这三点阻塞了所有后续工作。
