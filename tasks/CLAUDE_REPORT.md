# Claude 第一轮工作报告

日期：2026-07-11  
轮次：Round 1 — 项目继承与科研审查  

---

## 一、已读取的关键文件

| 文件 | 状态 |
|------|------|
| `AGENTS.md` | ✅ 已读取 |
| `README.md` | ✅ 已读取 |
| `experiment_lab_notebook.md` | ✅ 已读取 |
| `context/PROJECT_CONTEXT.md` | ✅ 已读取 |
| `context/RESEARCH_SCOPE.md` | ✅ 已读取 |
| `context/DATA_SCHEMA.md` | ✅ 已读取 |
| `context/PAPER_CLAIMS.md` | ✅ 已读取 |
| `tasks/CURRENT_TASK.md` | ✅ 已读取 |
| `tasks/TASK_QUEUE.md` | ✅ 已读取 |
| `tasks/DECISIONS.md` | ✅ 已读取 |
| `environment/system_info.txt` | ✅ 已读取 |
| `environment/setup_notes.md` | ✅ 已读取 |
| `environment/requirements/README.md` | ✅ 已读取 |
| `.gitignore` | ✅ 已读取 |
| `logs/daily/2026-07-11.md` | ✅ 已读取 |
| `logs/runs/README.md` | ✅ 已读取 |
| `.vscode/settings.json` | ✅ 已读取 |
| `.vscode/extensions.json` | ✅ 已读取 |

---

## 二、项目状态摘要

- **环境**：Ubuntu 20.04, RTX 3090 (24GB), NVIDIA 550.144.03, CUDA Toolkit 11.3, Python 3.11.5 (Conda base), 293GB 可用磁盘
- **软件**：Docker、FFmpeg、PyTorch、OpenCV、cuDNN 均未安装
- **代码**：scripts/ 所有目录为空（仅 .gitkeep）
- **数据**：无原始视频、无标注、无骨架数据
- **Git**：.git 目录无效，版本控制未运行
- **实验**：E1-E6 全部为空模板，无任何实际结果

**一句话总结：框架已搭建，执行尚未开始。**

---

## 三、发现的问题

| # | 严重程度 | 问题 |
|---|---------|------|
| 1 | 🔴 | Git 仓库未初始化——原始数据无版本保护 |
| 2 | 🔴 | 无测试视频——所有后续工作阻塞 |
| 3 | 🔴 | 所有安装待用户批准——环境不可用 |
| 4 | 🟡 | experiment_lab_notebook.md 范围可能过大（E1-E6 含多个外部数据集+数十组对比） |
| 5 | 🟡 | E5 "可行性已验证"标记来自旧电脑，当前环境未复现 |
| 6 | 🟡 | .gitignore 中 `*.mp4` 等规则过于激进，可能误忽略结果视频 |
| 7 | 🟡 | DATA_SCHEMA 缺少 detection_confidence、review_status 等辅助字段 |
| 8 | 🟡 | OpenPose 与 CUDA 11.3/GCC 9.4.0 的构建兼容性未知，无备选方案 |
| 9 | 🟢 | CODEX_REPORT.md 缺失 |
| 10 | 🟢 | action_label 受控词表未定义 |

---

## 四、新建文件

| 文件 | 说明 |
|------|------|
| `tasks/CLAUDE_PROJECT_REVIEW.md` | 项目状态全面审查 |
| `tasks/CLAUDE_REVIEW.md` | 对 Codex 初始化结果的审查，含 11 项问题发现 |
| `context/MOT_ANNOTATION_PROTOCOL.md` | MOT 人工复核标注规范（~250 行） |
| `context/OPENPOSE_BODY25_PROTOCOL.md` | OpenPose BODY_25 标注与评估规范（~350 行） |
| `tasks/T01_ACCEPTANCE_CRITERIA.md` | T01 第一段测试视频验收标准（~250 行） |
| `tasks/CLAUDE_REPORT.md` | 本文件 |

---

## 五、修改文件

无。本轮未修改任何已有文件。

---

## 六、对 Codex 工作的审查

**审查结果：质量合格，有可改进项。**

Codex 在初始化阶段完成了：
- 合理且完整的目录骨架
- 质量良好的治理文档（AGENTS.md, README.md）
- 完备的上下文文件（PROJECT_CONTEXT, RESEARCH_SCOPE, DATA_SCHEMA, PAPER_CLAIMS）
- 详尽的只读环境审计
- 深思熟虑的安装方案

主要缺失：
- CODEX_REPORT.md 未创建
- 无可执行代码或配置
- DATA_SCHEMA 可补充几个辅助字段
- .gitignore 视频规则需收紧

未发现 Codex 擅自改变研究方向、编造实验结果或偏离论文主线。

详见 `tasks/CLAUDE_REVIEW.md`。

---

## 七、当前风险

### 阻塞性风险
1. **无测试视频** — 用户尚未提供
2. **安装未批准** — setup_notes.md 末尾五项确认等待用户回复
3. **Git 无效** — 需初始化

### 技术风险
4. **OpenPose 构建兼容性** — 老旧 Caffe/CUDA 依赖链
5. **cuDNN 未验证** — 影响 PyTorch 和 OpenPose

### 论文风险
6. **实验范围膨胀** — E1-E6 的总工作量可能远超合理范围
7. **旧实验证据不可用** — 需重新验证

---

## 八、下一步建议

### 需用户确认的事项

1. **是否批准创建 `motpose` Conda 环境并安装 PyTorch + OpenCV + ultralytics + deep-sort-realtime？**
2. **是否批准安装系统 FFmpeg？**
3. **是否批准安装 Docker Engine/Compose 并拉取固定版本 CVAT 镜像？**
4. **是否批准下载并源码构建 OpenPose BODY_25？**（建议同时调查 MMPose 作为备选）
5. **请指定第一段 10-30 秒多人视频，并确认其使用与标注授权。**

### 用户确认后，建议执行顺序

1. 初始化 Git 仓库，创建 `.gitattributes`（可选）
2. 修复 `.gitignore` 中视频规则的过度匹配
3. 安装 FFmpeg
4. 创建 `motpose` 环境，安装依赖，运行 GPU smoke test
5. 登记测试视频（SHA-256, FPS, 分辨率, 帧数, 时长）
6. 执行 YOLO + DeepSORT 最小流水线
7. 生成可视化视频、JSONL、MOT 格式
8. 安装 Docker + CVAT
9. 导入并人工复核
10. 导出 reviewed MOT 和 subject_map.csv
11. 上述全部通过 T01 验收标准后，再考虑 OpenPose 安装

### 不建议立即做的事情

- 下载 50Salads/Breakfast/Human3.6M/3DPW/YouCook2 等外部数据集
- 开始 E1-E6 任何实验
- 训练 ACT 或 Diffusion Policy
- 开始论文写作
- 构建 OpenPose（在 MOT 闭环完成前）

---

## 九、需要用户确认的事项汇总

| 编号 | 事项 | 类型 |
|------|------|------|
| C1 | 批准 motpose 环境创建和 Python 依赖安装 | 环境 |
| C2 | 批准安装系统 FFmpeg | 环境 |
| C3 | 批准安装 Docker + CVAT | 环境 |
| C4 | 批准下载/构建 OpenPose BODY_25 | 环境 |
| C5 | 提供第一段 10-30 秒多人测试视频 | 数据 |
| C6 | 确认视频使用和标注授权 | 合规 |
| C7 | 批准初始化 Git 仓库 | 版本控制 |
| C8 | 确认是否接受 .gitignore 修订建议 | 配置 |
| C9 | 确认 T01 验收标准 | 流程 |
| C10 | 确认 experiment_lab_notebook.md 的实验范围是否需要调整 | 研究范围 |

---

## 十、终端的回复

已完成项目继承审查。详情见本报告。
