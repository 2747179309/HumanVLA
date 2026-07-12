# 重要决定

## D001 — 身份定义与人工复核

- 日期：2026-07-11
- 状态：已确认（来自项目要求）
- 决定：`track_id` 仅表示单视频局部轨迹；`subject_id` 是人工确认的全局人物标识。DeepSORT 输出必须经 CVAT 或等价工具人工复核。
- 原因：自动跟踪会出现 ID Switch、断轨、误检和漏检，不能作为人工真值。

## D002 — OpenPose 身份关联

- 日期：2026-07-11
- 状态：已确认（来自项目要求）
- 决定：OpenPose 每帧 `people` 数组下标不得作为人物 ID；BODY_25 必须与人工复核轨迹框进行显式关联。
- 原因：OpenPose 不保证跨帧人物数组顺序稳定。

## D003 — 环境隔离建议

- 日期：2026-07-11
- 状态：建议，等待用户批准执行
- 决定：Python MOT 流水线使用独立 Conda 环境 `motpose`；OpenPose 优先在项目内 `tools/openpose/` 独立源码构建；CVAT 使用 Docker Compose 隔离部署。
- 原因：当前 base 环境为 Python 3.11 且无 PyTorch/OpenCV；OpenPose 的 Caffe/CUDA 构建依赖与现代 Python MOT 栈存在冲突风险。

## D004 — T01 范围缩减

- 日期：2026-07-11
- 状态：已确认（Claude 第一轮审查）
- 决定：T01 完成标准从"一段短视频完成 MOT、人工复核和 BODY_25 关联闭环"缩减为"MOT 闭环完成（含人工复核），OpenPose 在 MOT 复核完成后单独审批"。
- 原因：原始 T01 范围过大，实际覆盖了 T02-T08 全部内容；将 OpenPose 独立可降低环境构建风险。

## D005 — Git 仓库初始化

- 日期：2026-07-11
- 状态：建议，等待用户批准执行
- 决定：需立即初始化 Git 仓库，当前 `.git` 目录无效。初始化后方可保护原始数据不被误改。
- 原因：无版本控制下，原始视频和标注一旦被覆盖无法恢复。

## D006 — .gitignore 视频规则修正

- 日期：2026-07-11
- 状态：建议，等待用户批准执行
- 决定：将 `*.mp4` 等全局视频忽略规则限制为 `data/raw_videos/` 范围内，避免误忽略结果可视化视频。
- 原因：结果可视化视频（如带 ID 追踪的 .mp4）是小体积的关键实验证据，应纳入版本控制或至少不被自动忽略。

## D007 — OpenPose 备选方案

- 日期：2026-07-11
- 状态：建议
- 决定：在构建 CMU OpenPose 的同时，应调查 MMPose 等现代框架的 BODY_25 支持作为备选方案。如果 OpenPose 在当前 CUDA 11.3 + GCC 9.4.0 环境下无法编译，不花费过多时间修复老旧 Caffe 依赖。
- 原因：CMU OpenPose 已多年未维护，构建兼容性风险高。

## D008 — 实验范围需在 E1 前重新对齐

- 日期：2026-07-11
- 状态：观察，暂不执行
- 决定：experiment_lab_notebook.md 中 E1-E6 的实验设计（尤其是 E1 的 7 组方法对比和 E2 的 3 种 MLLM 对比）在执行前需重新评估是否与"低成本数据构建框架"的论文主线一致。当前保持模板状态，不修改。
- 原因：过早修改实验设计可能丢失有用信息；等到 MOT+OpenPose 闭环完成、对数据质量有定量认知后再决策。

## D005 状态更新

- 日期：2026-07-11
- 状态：✅ 已完成（Codex 初始化收尾中完成 Git 仓库初始化，commit `27b4c34`）

## D006 状态更新

- 日期：2026-07-11
- 状态：已关闭
- 原因：用户明确要求 `.gitignore` 保留 `*.mp4` 等全局规则。结果视频（如 tracked.mp4）体积可接受时不影响，后续如需纳入版本控制可针对性 `git add -f`。

## D009 — T01/T02 任务拆分

- 日期：2026-07-11
- 状态：已确认（Claude 第二轮）
- 决定：将原始大 T01 拆分为 T01（环境审计 + workspace 初始化，已完成）→ T02（DeepSORT MOT 最小闭环）→ T03（OpenPose BODY_25）→ T04（CVAT 人工复核）→ T05（骨架关联）。每个子任务有独立验收标准和完成条件。
- 原因：大任务难以追踪进度和定位问题；拆分后每个任务有单一明确目标。

## D010 — T02 实验参数锁定

- 日期：2026-07-11
- 状态：已确认（Claude 第二轮）
- 决定：T02 的 YOLO（yolov8n, conf=0.3, iou=0.45, person only）和 DeepSORT（max_age=30, n_init=3, nn_budget=100, max_cosine_distance=0.2, max_iou_distance=0.7）参数由 Claude 指定。Codex 不得擅自修改；如需调整必须先报告并获得批准。
- 原因：实验可复现性要求参数固定；参数变更需要科研理由而非工程便利。

## D011 — T02 暂不使用 CVAT

- 日期：2026-07-11
- 状态：已确认（Claude 第二轮）
- 决定：T02 阶段的人工检查通过直接观看 tracked.mp4 和阅读 tracks_raw.jsonl 完成，不安装 Docker/CVAT。CVAT 人工复核推迟到 T04。
- 原因：Docker/CVAT 安装需单独批准；T02 的自动输出错误通常肉眼可见，不需要 CVAT 逐帧修正；T04 才需精修框和分配 subject_id。

## D012 — T02 spec 偏差处理

- 日期：2026-07-11
- 状态：已确认（Claude R2 审查）
- 决定：Codex 的 run_deepsort.py 与 T02 spec 有 4 处偏差，全部接受：(1) 输出目录 results/mot/ 替代 data/mot/raw/ — 保留现状，后续统一路径约定；(2) 单一脚本替代两脚本 — 接受，不影响功能；(3) 未保存 detections_raw.jsonl — 接受，当前不需要；(4) JSONL per-person 格式替代 per-frame 格式 — Codex 的选择更符合 DATA_SCHEMA，spec 设计有误，接受。
- 原因：所有偏差均为合理的工程判断，不影响数据质量或可复现性。spec 中的 per-frame JSONL 格式设计本身有缺陷。

## D013 — T02-HR 为明天唯一任务

- 日期：2026-07-11
- 状态：已确认（Claude R2）
- 决定：明天唯一任务为 T02-HR：对 Run 20260711_T02_001 的 240 帧进行全视频人工轨迹复核。不安装软件、不写代码、不启动 T03。
- 原因：自动流水线已完成且格式通过，人工复核是 T02 的唯一阻塞项。在确认自动跟踪质量前，启动 T03（OpenPose）没有意义。

## D013 状态更新

- 日期：2026-07-12
- 状态：已覆盖
- 说明：T02-HR 未独立执行（human_review_notes.md 未产出）。用户决定关闭 T02 并进入 T03，人工 MOT 复核推迟到 T04（CVAT）。

## D014 — T02 关闭条件

- 日期：2026-07-12
- 状态：已确认（Claude R3）
- 决定：T02 自动流水线通过即视为 T02 关闭。全视频人工轨迹复核（T02-HR）推迟到 T04 与 CVAT 精修合并执行。T02 不标记 COMPLETED 但允许 T03 并行启动。
- 原因：自动流水线的输出格式、元数据和运行日志均通过审查；CVAT 环境下的人工复核效率远高于手动观看视频+阅读 JSONL。推迟不会丢失信息（原始自动输出已 SHA-256 锁定）。

## D015 — track_id 4 分类（已由用户修正）

- 日期：2026-07-12
- 状态：已由用户修正为 confirmed_false_positive
- 用户最终判定：**confirmed_false_positive**（第 86 帧未对应真实人物，单帧误检）
- 结果：track_id 4 不在 subject_map 中。P001/P002/P003 为全部有效人物。
- 原因：用户经更仔细复核后判定该检测框无真实人物对应。

## D016 — T03 处理 three-people-walking.mp4（修正）

- 日期：2026-07-12
- 状态：已确认（Claude R3 修正）
- 决定：T03 OpenPose BODY_25 处理 `three-people-walking.mp4`（唯一已完成 MOT 复核的视频）。原计划使用 test_multi_001.mp4 但该文件不存在。
- 原因：three-people-walking.mp4 有完整的 MOT 复核文件和 subject_map，可以直接进入 T05 关联阶段。使用已有复核的视频避免对未复核视频做无意义的骨架提取。

## D017 — T03 不进行骨架-MOT 关联

- 日期：2026-07-12
- 状态：已确认（Claude R3）
- 决定：T03 仅提取 BODY_25 关键点并验证格式完整性。OpenPose people 数组与 MOT track_id 的关联推迟到 T05。T03 阶段不将 people 数组下标用作人物 ID。
- 原因：关联需要 MOT 复核后的稳定轨迹（T04 产物）；在 MOT 轨迹未经人工修正前做关联会产生错误的骨架-身份绑定。

## D018 — T02 正式关闭（最终）

- 日期：2026-07-12
- 状态：已确认（基于用户最终复核文件）
- 决定：T02 正式关闭。依据：
  - `data/mot/reviewed/three-people-walking.csv`：4 条检查 (id_switch/fragmentation/missing 全部 no_issue, track_4 = confirmed_false_positive)
  - `data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv`：P001(track_1), P002(track_2), P003(track_3)，frame 0-239，全部 main_subject
  - 自动流水线 Run `20260711_T02_001` 输出格式全部通过
- 原因：自动流水线和人工复核证据均完整，T02 闭环达成。

## D019 — T04 重新定义为骨架-ID关联

- 日期：2026-07-12
- 状态：已确认
- 决定：T04 任务重新定义为"OpenPose 骨架与 DeepSORT ID 关联"。原 T04（CVAT 人工修正）合并入 T02 阶段（three-people-walking 人工复核已手动完成），CVAT 安装和操作在需要处理新视频时单独审批。
- 原因：three-people-walking 的 MOT 复核已手动完成，不需要 CVAT。下一个逻辑步骤是将 OpenPose 骨架与已确认的 subject_id 关联。

## D020 — T03 输出路径

- 日期：2026-07-12
- 状态：已确认
- 决定：T03 所有 OpenPose 输出写入 `results/openpose/three-people-walking/`（而非 `data/openpose/raw_json/`）。这与 T02 的 `results/mot/` 约定保持一致。
- 原因：results/ 作为实验输出根目录，data/ 保留原始数据和人工标注。

## D021 - T03 六个异常帧的人工处置

- 日期：2026-07-12
- 状态：已由用户确认
- 决定：帧 43-45 因重叠和 `identity_mix` 标记为 `ambiguous_pose`，保留 raw 且不强制修复；帧 188 的 phantom 额外骨架在下游排除；帧 207-208 的远处真实人物标记为 `unmatched_pose`，不纳入三名主要人物数据。
- 数值说明：79 帧的 101 个 confidence 大于 1 仅作为范围警告，不等同于视觉骨架错误；原始 confidence 保持不变。
- 边界：不修改 raw JSON，不在 T03 执行 OpenPose 与 DeepSORT 关联，不启动 T04。

## D022 - T04 MOT逐帧框输入与自动匹配参数

- 日期：2026-07-12
- 状态：自动执行参数已记录，等待人工复核结果
- 输入决定：人工review CSV不包含逐帧修正框，且track 1/2/3均为`no_issue`，因此使用`results/mot/three-people-walking/tracks_raw.jsonl`的逐帧框，并以reviewed subject map为身份白名单；排除track 4。
- 参数：全有效BODY_25关键点框；`0.6*(1-IoU)+0.4*normalized_center_distance`；Hungarian一对一；接受阈值0.5。
- 异常规则：43-45额外pose为`ambiguous_pose`，188为`phantom_pose`，207-208额外背景人物为`unmatched_pose`，均不绑定subject。
- 边界：这是自动结果，不是人工真值；T04等待人工抽查，不启动T05。

## D023 - T04人工复核后的下游排除规则

- 日期：2026-07-12
- 状态：已由用户人工复核确认
- 身份结论：P001、P002、P003未发现身份交换。
- 质量结论：15-19、54-61为P001持杯手臂关键点定位偏差；43-45为跨人物手臂错误连接和非真人额外骨架；46恢复正常；188为phantom；207-208为范围外unmatched pose。
- 强制规则：43-45不得直接进入后续平滑或训练数据，不得用卡尔曼滤波强行修复。
- 保留规则：所有原始关联JSONL、OpenPose JSON和视频保持不变；任何后续派生处理必须另存。
- 边界：本次只完成T04人工复核收尾，不开始T05。

## D024 - Codex CLI默认自动批准策略

- 日期：2026-07-12
- 状态：已按用户要求配置
- 决定：Codex CLI默认使用`approval_policy = "never"`与`sandbox_mode = "workspace-write"`。
- 原因：当前CLI版本不再提供`--full-auto`；该组合实现工作区内无需逐次批准，同时保留文件系统和网络沙箱。
- 安全边界：未启用`danger-full-access`，未使用危险的全沙箱绕过参数。

## D022 — T03 验收通过 + confidence >1 裁决

- 日期：2026-07-12
- 状态：已确认（Claude R5）
- 决定：T03 验收通过。confidence >1（101 值/79 帧, 1.0002-1.03636）为 OpenPose 原生数值范围警告，不作为验收不通过条件。
- 置信度处理规则：
  1. 原始 JSON 中的 confidence 值永不被裁剪、归一化或覆盖
  2. 派生数据如需归一化，另存为 `confidence_used` 字段，与 `confidence_raw` 区分
  3. 归一化规则（如 `min(c, 1.0)`）记录在数据处理协议中
  4. `summary.json` 保持 `validation_passed: false` 以诚实记录协议偏差
- 原因：79 个 confidence warning 帧 ≠ 79 个视觉异常帧（视觉异常仅 6 帧）。OpenPose 原生输出偶尔产生略大于 1 的置信度是已知行为，不影响骨架空间精度。

## D023 — T04 匹配策略与异常处理规则

- 日期：2026-07-12
- 状态：已确认（Claude R5）
- 决定：T04 骨架-轨迹关联采用 Hungarian 一对一匹配，代价 = α×(1-IoU) + β×center_dist。异常帧强制执行以下规则：
  - 帧 43/44/45：额外骨架 → ambiguous_pose，不强制关联；正常骨架如可区分则正常匹配
  - 帧 188：第 4 骨架 → phantom_pose，排除
  - 帧 207/208：第 4 骨架 → unmatched_pose，不绑定到 P001-P003
  - 匹配失败保留 unmatched，不允许强行分配
  - 同一帧同一 subject_id 最多一副骨架
- 原因：强制关联混合/phantom/背景骨架会产生错误的骨架-身份绑定，污染下游数据集。

## D024 — T04 有条件通过

- 日期：2026-07-12
- 状态：已确认（Claude R6）
- 决定：T04 骨架-轨迹关联验收通过（有条件）。条件：帧 43-45 整体标记为无效，排除出下游平滑和训练；帧 15-19/54-61 为 OpenPose 定位误差（非身份错误），保留原始结果；帧 188 phantom 排除；帧 207-208 保持 unmatched。
- 证据：240 帧人工逐帧复核。238/238 可复核帧身份关联正确，0 次身份交换。237 pass / 3 fail (43-45)。原始文件未修改（SHA-256 锁定）。
- 原因：关联 pipeline 正确区分了身份错误（排除）和定位误差（保留）。异常帧全部按 T04 spec 规则正确处理。

## D025 — T05 四类数据区分

- 日期：2026-07-12
- 状态：已确认（Claude R6）
- 决定：T05 骨架质量清洗必须区分四类数据：(1) 可平滑的正常关键点抖动 → 卡尔曼/EMA；(2) identity_mix 帧 (43-45) → 直接排除，不得平滑；(3) phantom_pose (188) → 直接排除；(4) out-of-scope unmatched (0-1, 207-208) → 不纳入主要人物序列。对 P001 手臂定位误差 (15-19, 54-61) → 保留原始，平滑结果另存并统计偏差。
- 原因：不区分这四类会导致卡尔曼滤波尝试"修复"跨人物错误连接，产生虚假的平滑骨架。
