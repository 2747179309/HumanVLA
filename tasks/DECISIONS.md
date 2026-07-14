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

## D026 — T05A 六种质量状态定义

- 日期：2026-07-13
- 状态：已确认
- 决定：骨架序列清洗使用 6 种质量状态：`valid`（正常可平滑）、`low_quality`（定位偏差但身份正确，保留且可平滑但结果另存）、`invalid_identity_mix`（跨人物错误，帧级排除且禁止平滑）、`missing`（无骨架）、`excluded_phantom`（虚假骨架排除）、`excluded_non_target`（非主要人物排除）。
- 逐关节映射规则：
  - 帧 15-19/54-61 P001 关节 2,3,4 → `low_quality`，其余 22 关节 → `valid`
  - 帧 43-45 P001 关节 5,6,7 和 P003 关节 5,6,7 → `invalid_identity_mix`，同帧其余关节 → `low_quality`
  - 帧 43-45 额外骨架(pose_index=3) → `excluded_phantom`
  - 帧 188 额外骨架 → `excluded_phantom`
  - 帧 207-208 额外骨架 → `excluded_non_target`
- 原因：逐关节粒度避免因局部偏差丢弃整帧有效数据；同时确保跨人物错误被整体排除而非局部修补。

## D027 — 主线分叉：three-people-walking 退出操作训练主线

- 日期：2026-07-13
- 状态：已确认
- 决定：`three-people-walking.mp4` 仅作为多人 MOT、姿态关联和质量掩码的回归样本。不作为后续 VLA 操作训练主样本。主线操作训练使用 K01 及后续单人操作视频。
- 原因：three-people-walking 是多人行走场景，不含操作动作（reach/grasp/transport 等），不适用于操作型 VLA 策略学习。

## D028 — Kinect 降级为独立评价支线

- 日期：2026-07-13
- 状态：已确认
- 决定：Kinect K01 数据不进入主线数据构建流程。主线仅使用 RGB 视频 + OpenPose 骨架。Kinect 骨架（2D+3D）仅留作后续独立定量评价（如 T05B OpenPose-Kinect 对齐实验）。主线不等待 Kinect 完成。
- 原因：主线定位为"低成本"（普通 RGB 相机 + OpenPose），依赖 Kinect 作为输入端违背低成本叙事；但 Kinect 作为评价端（验证 OpenPose 精度）是合理的。

## D029 — T06A 动作阶段词表

- 日期：2026-07-13
- 状态：已确认
- 决定：操作型视频使用 12 类动作阶段词表：8 个标准操作阶段 (reach→align→grasp→lift→transport→place→release→retract) + 4 个扩展阶段 (idle/occluded/failed_attempt/unknown)。phase_id 按此编号固定，Codex 不得修改。
- 原因：统一词表是跨视频、跨标注者一致性的基础。阶段编号固定确保脚本和可视化颜色编码稳定。

## D030 — K01 仅使用 RGB 流

- 日期：2026-07-13
- 状态：已确认
- 决定：T06A 对 K01 仅使用 `color/` 下的 RGB 帧。不使用 depth/、skeleton_2d.jsonl、skeleton_3d.jsonl 或 KINECT_TO_BODY25_MAPPING.csv。帧号从 1-240 重新映射为 0-239。
- 原因：主线定位为低成本 RGB 方案；深度和 Kinect 骨架仅用于支线评价。

## D031 — T06A 分阶段验收

- 日期：2026-07-13
- 状态：已确认
- 决定：T06A 分两阶段验收：(1) 规范设计阶段 — 已通过（ACTION_PHASE_SCHEMA.md v0.2.0 + T06A_ACCEPTANCE_CRITERIA.md）；(2) 工具实现阶段 — 待 Codex 在 T06B 标注前按验收标准实现 7 个脚本。T06A 标记为 `ACCEPTED (spec)`。
- 原因：Codex 仅完成了规范修订，未实现脚本。规范质量良好可直接进入下一阶段，但标注工具必须在实际标注前完成。

## D032 — T06B 试采集规格

- 日期：2026-07-13
- 状态：已确认
- 决定：T06B 采集 5 段单人操作视频（普通手机/RGB 相机，非 Kinect），标注其中 1 段作为端到端验证。标注前 Codex 必须先实现 T06A 的 7 个脚本。不进行 LeRobot 转换、滤波或训练。
- 原因：用低成本设备采集验证"低成本"主线叙事；5 段中仅标注 1 段控制初期投入。

## D032 状态更新

- 实际采集：12 段 episode + 2 段 calibration = 14 段视频
- 命名规范：`P<NN>_<OBJ>_<HAND>_<FROM>_<TO>_E<NNN>_<TAG>_<SUCCESS>.mp4`
- T06B 第一阶段仅处理 E001

## D033 — T06B 第一阶段仅处理 E001

- 日期：2026-07-13
- 状态：已确认
- 决定：T06B 第一阶段仅处理 `P01_BOX01_R_A_B_E001_S.mp4`（A→B 右手成功操作）。不处理 E002-E012、calibration 视频、K01 或其他数据源。
- 场景参数：纸盒 12×10×4 cm，A→B 中心距离 57 cm，桌面 75 cm，相机到桌面近边 ~30 cm，相机到标记中心连线 ~67 cm。这些参数足够当前动作标注和初步仿真映射，不将额外环境测量设为硬前置条件。
- 原因：单段端到端验证足以检验标注规范和工具；先验证再扩展。

## D034 — T06B-E001 验收通过

- 日期：2026-07-13
- 状态：已确认
- 决定：T06B-E001 验收通过。结果：1280×720, 30 FPS, 345 帧 (0-344), 10 个动作阶段, retract=207-244, end idle=245-344。validation + frames.jsonl + phase overlay 人工复核通过。

## D035 — T06C 上半身质量掩码规则

- 日期：2026-07-13
- 状态：已确认
- 决定：E001 单人上半身操作场景的质量掩码规则：(1) 核心关节 Neck(1)/RShoulder(2)/RElbow(3)/RWrist(4) 必须逐帧统计置信度和有效率；(2) MidHip(8) 仅作辅助参考，不作为硬性有效条件；(3) 膝/踝/脚(9-14, 19-24) 不可见标记为 missing，不传播到整帧无效；(4) 完整 BODY_25 结构保留。核心关节缺失率 > 30% 为不通过条件。
- 原因：操作视频仅露出上半身，强制下半身关节有效会导致大量误排除。核心上肢关节才是人机映射的关键输入。

## D036 — T06C 验收通过

- 日期：2026-07-13
- 状态：已确认
- 决定：T06C 验收通过。结果：
  - DeepSORT: track_id=1 (frame 2-344), P001 确认, 0 身份切换
  - OpenPose: 345 JSON, 346 pose (frame 226 双 pose)
  - 关联: 343/343 匹配, frame 0-1 missing (n_init)
  - 上半身掩码: 关节 8-14/19-24 强制 outside_capture_scope
  - 帧级: 336 valid / 7 low_quality (64/65/143/182-185) / 2 missing (0-1)
  - frame 226 pose_index=1: excluded_reflection_artifact
  - 核心关节有效率: Neck/RShoulder/RElbow 100%, RWrist 97.96%
- 原始文件哈希全部锁定。T06C-M1 上半身可见范围修正完成。

## D037 — T07A Neck-肩宽归一化

- 日期：2026-07-13
- 状态：已确认
- 决定：右上肢轨迹归一化使用 Neck(1) 为原点、RShoulder-LShoulder 欧氏距离为尺度因子。不使用 pelvis/MidHip 归一化（操作视频中 MidHip 不可靠）。像素坐标和归一化坐标同时保留。逐帧 scale 值记录用于检测肩宽异常帧。
- 原因：Neck 是上半身最稳定的参考点；肩宽归一化消除人物-相机距离的影响，且不需要下半身关键点。这是后续人机映射的基础预处理。

## D038 — T07A 缺失数据零容忍规则

- 日期：2026-07-14
- 状态：已确认
- 决定：T07A 轨迹提取对缺失关节采用严格的 null 输出规则：缺失关节的归一化坐标和像素坐标均填 JSON `null`，不填 0.0。禁止插值、前向填充、后向填充、或用前后帧推算缺失关节。`trajectory_valid` 字段逐帧标记。
- 原因：轨迹数据将直接用于人机映射和策略学习。伪造的缺失数据比缺失本身危害更大——会让策略学到不存在的运动模式。缺失由后续平滑阶段（T07B）显式处理。

## D039 — T07A 无效帧列表（强制）

- 日期：2026-07-14
- 状态：已确认
- 决定：以下帧/关节在 T07A 中强制为无效：(1) 帧 0-1 全部关节（n_init 确认前）；(2) RWrist 缺失帧 64/65/143/182-185；(3) T06C quality_mask 中 `joint_valid=false` 的对应关节；(4) frame 226 pose_index=1 不进入 P001。不使用 MidHip 或腰部作为坐标原点。
- 原因：这些无效条件均来自 T06C 人工复核确认的结果，T07A 直接继承而不重新判断。

## D040 — T07A 验收通过

- 日期：2026-07-14
- 状态：已确认
- 决定：T07A 验收通过。12 个跳变候选经人工复核分类为 normalization_artifact=1 (JUMP_001), occlusion_error=8 (JUMP_002/003/005/007/008/009/010/011), real_motion=3 (JUMP_004/006/012)。轨迹 345 帧完整，Neck 归一化正确，缺失关节 null 不填补。原始文件未修改。

## D041 — T07B 合成遮挡实验设计

- 日期：2026-07-14
- 状态：已确认
- 决定：T07B 采用合成遮挡恢复实验设计：(1) 从 E001 有效帧中人为屏蔽 1/2/3/4 帧短片段；(2) 比较 Linear/PCHIP/Cubic Hermite/Kalman CV 四种方法；(3) 以 normalized RMSE 为主指标、jerk_error + 边界连续性为次级指标；(4) provisional best 仅限 E001，不声称全数据集最优。真实缺失区间 64-65/143/182-185 用 provisional best 修复，frame 0-1 不修复。
- 原因：真实缺失位置无 ground truth，无法直接计算恢复误差。合成遮挡实验提供可量化的方法比较。

## D042 — T07B occlusion_error 延期处理

- 日期：2026-07-14
- 状态：已确认
- 决定：T07B 不自动修复 8 个 occlusion_error 候选跳变。这些候选标记为 `deferred_to_T07C`，保留原始 raw 坐标，不删除、不替换。输出 `corruption_candidate_list.json` 供 T07C 处理。
- 原因：occlusion_error 表示帧间跳变事件，不一定能确定是哪一端的观测错误。需要先建立逐帧 corruption mask（T07C-A）再决定修复策略。

## D043 — T07B 验收通过

- 日期：2026-07-14
- 状态：已确认
- 决定：T07B 验收通过。44 合成缺口 (1:16/2:16/3:6/4:6)，linear 为 provisional best on E001 (RWrist RMSE_norm=0.0198)。7 帧 RWrist 真实修复全部 accepted/high；182-185 保留 boundary_continuity_warning。64-65 RElbow low_quality 未插值，repair_acceptance=rejected，延期 T07C。frame 0-1 未修复。原始文件哈希锁定。

## D044 — T07C-A corruption_type 与 proposed_action 词表

- 日期：2026-07-14
- 状态：已确认
- 决定：T07C-A 使用 7 种 corruption_type（occlusion_error/openpose_jitter/normalization_artifact/low_quality_observation/boundary_continuity_warning/real_motion/valid）和 4 种 proposed_action（keep/mask/downweight/defer）。每个 occlusion_error 事件必须逐帧判定 from/to 哪端错误，不得整段删除。real_motion 标记为 valid + keep。
- 原因：精确的逐帧 corruption mask 是后续质量感知滤波（T07C-B）的前提。粗粒度的整段删除会丢弃有效数据。

## D045 — T07C-A 验收通过

- 日期：2026-07-14
- 状态：已确认
- 决定：T07C-A 验收通过。1380 行 (345×4), raw/repaired/downstream 三层分离。7 条 repaired RWrist 全部 downstream_valid=true。64-65 RElbow: mask→T07C-B。178-179 RWrist: openpose_jitter→mask。9 条 raw_invalid 但 source=raw：全部 downweight (JUMP_005 f75-80 RElbow + JUMP_007 f136-138 RWrist)，语义正确。frame 129-142 RElbow: observed-but-unverifiable, defer→T07C-B 骨骼重建。原始文件哈希全部锁定。

## D046 — T07C-B 质量感知优化规则

- 日期：2026-07-14
- 状态：已确认
- 决定：T07C-B 按 corruption_type 分四类处理：mask(21)→骨骼运动学重建, downweight(10)→降权平滑, defer(19)→运动学+阶段约束重建(含 frame 129-142 RElbow), keep(1330)→正常优化。阶段边界 ±2 帧使用保守平滑参数，禁止跨阶段平滑。frame 129-142 RElbow 使用 RShoulder→RWrist 距离约束 + 上臂/前臂长度守恒重建。
- 原因：不同类型的 corruption 需要不同的处理策略。observed-but-unverifiable 的观测不能被直接使用，但骨骼运动学提供物理约束。

## D047 — T07C-B2 验收通过

- 日期：2026-07-14
- 状态：已确认
- 决定：T07C-B2 验收通过。14 clean 窗口 (train=7/val=3/test=4), 336 配对样本。split 按固定时间范围隔离 (2-120/121-206/207-344), 0 源帧泄漏, 同窗口所有变体在同一 split。4 类合成污染对应 E001 真实错误模式。idle 占 7/14 窗口 + 缺失 "place" 阶段是数据固有特征, 非设计缺陷。论文只能声称 within-episode synthetic benchmark。

## D048 — T07C-B3 train/val/test 隔离纪律

- 日期：2026-07-14
- 状态：已确认
- 决定：T07C-B3 严格执行 train (168样本)→val (72样本)→test (96样本) 三级隔离。train 用于 grid search, val 用于 top-3 参数选择, test 严格运行一次。参数搜索空间和评估协议预注册于 `configs/dataset/t07c_b3_baseline_protocol.json`。违反 test 隔离将导致 B3 不通过。
- 原因：合成数据集只有 336 个样本, 全部来自 E001。train/val/test 的时间隔离是最小化过拟合的基本保障。

## D027 - T05A帧0-1连续序列派生方法（已废止）

- 日期：2026-07-13
- 状态：已由D028废止
- 决定：按当前T05A验收标准，将帧0-1的三副正常骨架纳入P001/P002/P003连续序列并标记`valid`。由于这两帧没有DeepSORT confirmed track，从首个完整匹配帧2开始，使用骨架框中心归一化距离和Hungarian一对一逐帧向后分配。
- 可追溯性：保存每个subject的原始pose_index、分配方法和代价；最大归一化中心距离为0.01346463。
- 安全边界：不使用OpenPose people数组顺序，不修改T04 JSONL，不把派生结果描述为人工确认身份；帧0-1列为人工重点检查。
- 处理边界：不执行滤波、插值、坐标平滑或Kinect对齐，不开始T05B。

## D028 - T05A帧0-1无确认身份时必须标记missing

- 日期：2026-07-13
- 状态：已由用户确认并执行
- 决定：P001、P002、P003在帧0-1统一标记`missing`，`frame_valid=false`，`exclusion_reason=no_confirmed_track_identity`。
- 数据规则：不保留几何回溯身份作为有效数据；派生序列使用零骨架、零confidence、null track_id和null source_pose_index。
- 原因：这两帧没有DeepSORT confirmed track，几何接近不能证明subject身份可靠。
- 保留边界：原始T04 unmatched pose保持不变；只重生成T05A派生产物。不做滤波，不开始T05B。

## D031 — T06A人工阶段区间为语义权威源

- 日期：2026-07-13
- 状态：已确认
- 决定：人工确认的 `segments.jsonl` 阶段闭区间是动作语义权威标签；逐帧标签和中英文文本文件只能从已确认区间确定性展开。自动建议仅可作为候选，不得覆盖人工判断，也不得对 `phase_id` 做数值插值。
- 边界约定：新阶段首次可观察帧归属新阶段；不设强制三帧最小长度，真实可见的短阶段必须保留。
- 原因：阶段ID是离散语义而非连续数值，插值或强制合并会制造不存在的标签并丢失短暂抓取/释放动作。

## D032 — T06A数据划分按录制会话防泄漏

- 日期：2026-07-13
- 状态：已确认
- 决定：train/val/test 使用 `split_group_id` 按源视频或录制会话划分；同一视频的帧和episode不得跨集合。K01是单次受控录制，当前标记 `split=unsplit`，仅用于规范和工具原型验证。
- 数据边界：K01只读取RGB，Kinect深度和骨架不进入主线运行时；后续补充普通手机/RGB相机的独立录制。
- 原因：同视频相邻episode高度相关，按episode随机拆分会造成背景、人物和时间上的评估泄漏。

## D033 — T06A主线不依赖Kinect或three-people-walking

- 日期：2026-07-13
- 状态：已确认
- 决定：`three-people-walking`永久保留为MOT/姿态/质量掩码回归样本；T06A主线不等待K02，也不加载Kinect骨架。Kinect仅为后续独立定量评价支线。
- 当前边界：暂不进行LeRobot转换、滤波、模型训练或T06B大规模标注。

## D034 — T06B E001第一阶段停在人工标注前

- 日期：2026-07-13
- 状态：已由用户明确要求并执行
- 决定：第一阶段仅审计 `P01_BOX01_R_A_B_E001_S.mp4`，登记真实元数据，生成空白阶段CSV和带0基帧号/时间戳的预览视频。CSV保持0条阶段记录，等待人工填写。
- 输出约定：全局视频清单为 `data/action_labels/video_manifest.csv`；E001人工阶段CSV为 `data/action_labels/segments/pick_place_pilot_v1_E001/E001_action_phase_annotations.csv`；预览为 `results/action_labels/pick_place_pilot_v1_E001/preview_frame_index_timestamp.mp4`。
- 边界：不自动推测阶段，不处理E002-E012，不开始滤波、LeRobot转换或仿真训练。

## D036 — T06C在OpenPose GPU设备不可用时停止派生

- 日期：2026-07-13
- 状态：基于真实环境检查执行
- 决定：DeepSORT允许显式使用CPU完成并保留原始输出；现有OpenPose CUDA构建在缺少`/dev/nvidia*`时不得用空骨架或替代模型伪造BODY_25结果。关联、质量掩码、合并和核心关节指标必须等待真实OpenPose输出。
- 身份边界：唯一track 1临时映射为P001，但标记为`provisional_needs_human_confirmation`，不能描述为最终人工真值。
- 系统边界：未获单独批准前，不创建GPU设备节点、不重载/修改NVIDIA驱动、不重启系统、不编译CPU版OpenPose。
- 原因：当前`nvidia-smi`、PyTorch和OpenPose单帧探针均证实CUDA不可用；继续生成下游文件会把环境失败误写成数据缺失。

## D037 — T06C-R分类G并要求主机终端恢复设备节点

- 日期：2026-07-13
- 状态：阶段A完成，阶段B受运行环境权限阻塞
- 决定：故障分类为G。驱动550.144.03模块已加载，DKMS/headers/用户态库匹配，Secure Boot未启用；当前Codex运行环境缺少`/dev/nvidia*`且不能使用sudo。不得手工mknod、重装驱动或用替代骨架绕过。
- 恢复路径：用户先在主机普通终端检查`nvidia-smi`；若同样缺节点，安装`nvidia-modprobe`并执行`sudo nvidia-modprobe -u -c=0`。设备与`nvidia-smi`恢复后才能执行OpenPose单帧探针。
- 身份更新：用户人工确认E001 track 1始终属于主操作者，正式映射为P001；frame 0-1仍为missing。

## D038 — T06C OpenPose改由普通宿主机终端执行

- 日期：2026-07-13
- 状态：已由用户宿主机检查确认
- 决定：宿主机GPU、设备节点和`nvidia-smi`正常，故不修改驱动、内核、Secure Boot或系统配置。Codex仅生成宿主机运行脚本，不在受限环境尝试OpenPose。
- 安全门槛：先通过单帧BODY_25 CUDA探针、JSON、渲染图、人物和核心关节检查，才能处理完整345帧。失败立即退出。
- 数据边界：复用现有DeepSORT和人工确认P001映射，不重跑DeepSORT，不处理E002-E012。已有OpenPose输出默认拒绝覆盖；显式覆盖时先归档。

## D039 — T06C单人上半身关联阈值与未匹配pose保留策略

- 日期：2026-07-13
- 状态：自动结果已生成，待人工复核
- 决定：E001仍使用IoU 0.6、归一化中心距离0.4和Hungarian一对一关联，但将上半身场景拒绝阈值从T04试运行的0.5适配为0.6。0.5只匹配306/343帧；被拒帧是上半身骨架框小于完整人物框造成，候选最大代价0.561254、最大归一化中心距离0.32335，且单人场景无竞争人物。0.6匹配343/343确认轨迹帧，仍保留有限拒绝条件，不是无阈值强制分配。
- 异常保留：frame 0-1的pose因无确认轨迹保持`unmatched_pose`，P001主体序列填充`missing/no_confirmed_track_identity`；frame 226的第二副残缺pose完整保留为`unmatched_pose`并列入人工检查，只有完整pose绑定P001。
- 质量边界：帧级质量只由Neck、RShoulder、RElbow、RWrist决定；下肢缺失不传播为整帧无效。confidence原值保持不变，不做滤波或插值。

## D040 — T06C-M1固定拍摄可见范围覆盖OpenPose推测值

- 日期：2026-07-13
- 状态：已执行，待人工复核
- 决定：E001的可观测关节固定为0-7和15-18；8-14及19-24固定超出拍摄范围。后者无论OpenPose坐标或confidence是否非零，派生数据均标记`joint_observation_status=out_of_frame`、`joint_valid=false`、`visibility_reason=outside_capture_scope`，但`keypoints_raw/confidence_raw`不得修改。
- 核心与辅助：核心保持Neck、RShoulder、RElbow、RWrist；辅助改为Nose、LShoulder、LElbow、LWrist，移除MidHip。
- 可视化：主overlay只绘制Nose-Neck、双侧肩肘腕链和可见头部边，不绘制Neck-MidHip或任何髋腿脚节点/边。额外pose也只显示相同可见范围。
- 后续归一化：`origin_joint=Neck`、`scale_reference=shoulder_width`；本次拍摄无法使用pelvis-centered normalization。
- 原因：OpenPose对画面外BODY_25关节输出的是模型推测，不是真实视觉观测，不能因原始confidence非零进入训练有效掩码。

## D041 — T06C最终人工复核结论

- 日期：2026-07-13
- 状态：用户人工确认，已执行
- 决定：frame 64-65的RElbow为`low_quality/forearm_self_occlusion`、RWrist为`missing/hand_occludes_wrist`；frame 143的RElbow同类low quality，RWrist为`missing/hand_and_box_occlude_wrist`。
- 不确定性：frame 182-185右臂/右腕记录为`missing_or_unstable`，原因仅标记`suspected_self_occlusion_and_face_overlap`，`manual_confidence=medium`，不得表述为已确定因果。
- artifact：frame 226额外`pose_index=1`是桌面反光误检，标记`excluded_reflection_artifact`，不进入P001；同帧P001保持`valid/frame_valid=true`。
- 统计语义：确认轨迹帧的自动joint-level missing为Neck 0、RShoulder 0、RElbow 0、RWrist 7。人工明确确认RWrist missing为64、65、143；182-185单列为missing或不稳定，不混入确定原因统计。帧级统计保持336 valid、7 low_quality、2 missing。

## D042 — T07A原始轨迹的低质量保留与缺口距离规则

- 日期：2026-07-14
- 状态：已执行
- 决定：T07A以Neck为原点、左右肩欧氏距离为尺度。RElbow在64、65、143的原始像素和归一化数值保留，但显式标记`low_quality`且不计入source-valid；182-185人工unstable同样保留数值但不计入effective high-quality。RWrist在64、65、143、182-185严格写为null。
- 统计口径：RElbow分别报告coordinate available、T06C source-valid和人工复核后effective high-quality，避免把“有数值”混同“高质量有效”。RWrist valid只统计非null且质量有效帧。
- 距离规则：逐帧位移和reach-to-retract路径长度只使用相邻帧均有坐标的边；不得跨缺失区间连接或隐式插值。可疑跳变采用Tukey extreme规则`Q3 + 3*IQR`，只生成待复核候选，不自动删除或修复。
- 原因：直接要求保留低质量RElbow raw值，同时禁止伪装为高质量；分层状态和不跨缺口计算可同时保持可追溯性与统计诚实性。

## D043 — T07A保留绝对躯干运动并禁止仅用Neck相对轨迹映射

- 日期：2026-07-14
- 状态：用户人工确认，已执行
- 决定：T07A异常遮挡帧为143而非43；64-65、143、182-185继续按右腕缺失和/或右肘低质量处理。Neck和双肩在放置到B点附近的少量平移是正常躯干/肩部代偿，不作为检测错误。
- 数据规则：禁止固定、修改或滤除Neck与双肩原始坐标。逐帧输出必须同时保留右腕/右肘、Neck及双肩的绝对像素坐标，Neck相对首个有效frame 2的x/y位移，Neck/双肩相邻帧dx/dy向量与欧氏位移，以及Neck原点/肩宽尺度的相对坐标。
- 后续映射：仿真映射不得仅使用Neck相对轨迹；绝对桌面运动路径及A/B参考位置均为必要输入。T07A不检测纸盒且没有A/B坐标，因此只记录该约束，不编造参考位置。
- 处理边界：不插值、不滤波、不跨frame 0-1身份缺口计算位移，不修改T06C输入。

## D044 — T07A统计跳变候选只作为无偏人工复核项

- 日期：2026-07-14
- 状态：用户明确要求，已执行
- 决定：Tukey规则产生的12个候选不得自动标记为检测错误。人工复核CSV中的`manual_label`、`manual_confidence`和`manual_note`初始必须为空，只能由人工观看复核材料后填写。
- 材料规则：每项展示候选边前后各5帧、全部五个上肢锚点、绝对像素路径、Neck/肩宽归一化路径和统计触发边；缺失点不得跨缺口连接。
- 数据边界：只生成派生复核材料，不插值、不滤波、不修改轨迹或summary。已有人工字段非空时，生成脚本即使指定overwrite也拒绝覆盖。

## D045 — T07A人工跳变裁决原样固化且暂不修复

- 日期：2026-07-14
- 状态：用户人工裁决完成，已执行
- 决定：12项manual label/confidence/note原样写入summary。`real_motion`及任何阶段边界运动或人体代偿必须保留；`openpose_jitter`、`occlusion_error`和`normalization_artifact`仅标记，不在T07A修复。
- 自定义标签：JUMP_010和JUMP_011的人工标签“骨架完全没有在手臂上”不是既定枚举。不得擅自重命名或映射，按原文单列统计并使用`mark_only_no_repair`策略。
- 格式事实：人工CSV的三个辅助review列整体右移一列，但12行manual字段和核心候选字段完整一致。固化只读取核心字段，不改写用户CSV，并在summary记录该布局。
- 数据边界：raw trajectory JSONL/CSV保持只读；不删除候选，不插值、滤波或执行任何错误修复。T07A固化后停止等待Claude验收。

## D046 — T07A-R1人工标签枚举与schema规范化

- 日期：2026-07-14
- 状态：用户要求，已执行；本决定覆盖D045中保留自定义manual label的旧规则
- 决定：manual label仅允许`real_motion`、`normal_body_compensation`、`phase_boundary_motion`、`openpose_jitter`、`occlusion_error`、`normalization_artifact`、`uncertain`。JUMP_001归为normalization artifact；JUMP_005按当前用户裁决保留occlusion error；JUMP_010/011归为occlusion error。
- 备注规则：JUMP_001记录绝对像素位移小而肩宽变化放大归一化位移；JUMP_005明确右肘遮挡；JUMP_010/011保留“骨架完全没有在手臂上”及既有疑似重叠原因。
- Schema：人工CSV固定20个命名字段，辅助帧范围恢复到正确列，clip_path必须是实际MP4。R1开始时CSV已由外部变为规范布局，仍执行确定性规范化重写并记录前后哈希。
- 处理边界：候选数保持12；raw trajectory和OpenPose输入只读。错误和artifact只标记，不修复、不插值、不滤波、不删除真实运动或人体代偿。

## D047 — T07B预注册选择规则与E001 provisional best

- 日期：2026-07-14
- 状态：已执行，待人工复核修复帧
- 预注册：policy在benchmark前固定44个合成样本目标、四方法排名、Kalman Q/R/P0和选择规则。主要指标为RWrist mean RMSE_norm；仅在最佳值10%带内使用jerk+入口连续性，禁止结果后调参。
- 结果：linear/PCHIP/Hermite/Kalman smoothing的RWrist RMSE_norm为0.019819/0.022681/0.026315/0.022746；只有linear进入10%带。因此linear仅称为`provisional best on E001`。
- 修复：linear只写入RWrist 64-65、143、182-185的独立repaired字段；0-1不修复。observed raw字段不覆盖、不平滑。8个occlusion error事件的候选关节延期T07C。
- 验证：三段最大位移均低于0.5肩宽；182-185入口连续性数值较高，需优先人工复核。当前不开始T07C。

## D048 — T07B-R1逐关节人工接受状态

- 日期：2026-07-14
- 状态：用户人工复核已固化
- 审计：frame 64-65的RElbow在T06C和raw trajectory中是带原始坐标的`low_quality`观测，不是missing/invalid，也没有RElbow插值候选。因此保留原始坐标，但人工判为fail/rejected、`downstream_valid=false`，以`low_quality_observation_requires_quality_aware_refinement`延期T07C。
- 接受：RWrist 64-65、143、182-185的linear派生值均为pass/accepted/high并允许下游使用。182-185仍保留入口速度不连续性`7.959980 norm/s`的boundary warning；人工位置通过不等于边界连续性指标消失。
- Schema：逐关节复核字段采用RElbow/RWrist映射；原自动repair confidence另存为`automatic_repair_confidence`，不得与人工confidence混淆。
- 不变项：raw trajectory、T06C mask、44个合成样本、benchmark指标与排名不变；linear继续只称为`provisional best on E001`。不临时换方法，不开始T07C。

## D049 — T07C-A先复核候选再生成逐帧掩码

- 日期：2026-07-14
- 状态：复核材料完成，等待人工逐帧裁决
- 决定：8个occlusion error只有帧间事件标签，尚不能推导from/to哪一帧错误。不得把事件两端自动全部mask，也不得默认任一端有效；最终1380行frame-joint mask必须等待人工填写复核CSV后生成。
- 复核范围：9个异常/归一化跳变事件，加64-65 RElbow low-quality区间和182-185 RWrist boundary warning区间，共11个事件。3个已裁决real motion不重复进入本轮候选。
- 材料规则：每个事件至少前后8帧，必须同时展示raw骨架、raw/repaired轨迹、Neck/肩宽、关节confidence、动作阶段和from/to。新一轮manual字段初始为空。
- 数据边界：只生成复核CSV与视频，不修改raw/repaired trajectory，不自动mask、不滤波、不插值。材料完成不等于T07C-A最终验收完成。

## D050 — T07C-A分离raw、repaired与downstream三层有效性

- 日期：2026-07-14
- 状态：用户人工CSV已固化，mask已生成，待Claude验收
- 决定：`manual_error_frames`只否定raw OpenPose观测。T07B已人工accepted的repair独立判断；raw无效不能自动使repair失效。最终下游只从`raw/repaired/none`三者中选择。
- accepted repair：RWrist 64-65、143、182-185选择repaired并保持downstream valid；182-185同时保留boundary warning。RWrist 178-179无accepted repair，选择none并延期T07C-B。
- 无repair关节：RElbow 64-65 raw无效且无repair，选择none并延期T07C-B。normalization artifact 54-55保留像素raw有效和keep，只记录尺度warning。
- 重复证据：每个frame/joint仅一行；所有事件保存在`source_event_ids`和`manual_evidence`。72-74的mask/downweight差异不消解，显式保存两种action并用`manual_action_conflict`标记；单值action采用更保守的mask作为当前下游选择，但不改写原人工记录。
- defer语义：129-143 RElbow保持人工uncertain/defer，不自动重映射为mask；当前无可靠下游源，等待T07C-B质量感知处理。
- 数据边界：不修改人工CSV、raw/repaired trajectory或quality mask，不运行任何新插值或滤波。

## D051 — T07C-B2严格clean真值、预注册污染与时间split隔离

- 日期：2026-07-14
- 状态：已执行，待B2质量审查
- 真值：8帧窗口内Neck/RShoulder/RElbow/RWrist必须同时raw valid、selected raw、无repair、corruption type valid、source events为空且同phase。accepted repair虽可用于真实下游，但禁止作为合成ground truth。
- 污染：只实现阶段计划规定的Gaussian noise、burst jump、continuous drift、short missing四类，各三档；参数在首次生成前集中预注册，后续B3不得根据结果回调B2污染参数。
- 尺度：像素污染幅度使用clean窗口肩宽中位数；归一化仍逐帧使用Neck原点和肩宽，不使用MidHip。
- 随机：全局seed 20260714；样本seed由SHA-256(global seed/window/joint/type/intensity)确定，禁止使用进程不稳定的Python `hash()`。
- 隔离：固定train 2-120、val 121-206、test 207-344并与phase边界对齐；同一clean窗口的24个变体只能进入同一split，源帧跨split交集必须为空。
- 局限：时间隔离导致split的phase分布不同，后续必须同时报告按phase结果，不能只用总体平均声称算法优势。
- 边界：B2只生成配对数据，不运行传统滤波、恢复或超参数搜索。

## D052 — T07C-B3 validation选参、单次test与缺失指标语义

- 日期：2026-07-14
- 状态：已执行，待独立验收
- 选参：B2固定split不变；train仅作开发诊断，全部47个预注册候选在val上评价并由val固定每种方法的参数。该规则按用户本轮明确要求执行，并覆盖D048中“train先筛top-3”的旧描述。
- Test纪律：选参JSON先记录配置、B2数据和raw trajectory哈希，再执行一次96样本×5方法的test；独立audit记录`test_evaluation_count=1`。test结果没有用于改参数、方法或B2污染。
- 输入边界：普通基线不能读取truth、合成corruption mask或人工mask。confidence-weighted Kalman只读取源OpenPose confidence；SG缺失预处理只读取corrupted observations。
- 缺失语义：null不得变0。正式位置/最大/导数指标在输出不完整时保留null；另用预注册missing penalty和coverage进行可比较统计，禁止把penalty写成实际RMSE。
- 边界指标：B2每个窗口只有一个phase，phase-boundary shift不可识别，必须写null/not applicable。负real-motion attenuation表示路径放大而非负误差。
- 研究范围：结果只能称为E001 within-episode synthetic benchmark。B3完成后停止，不自动开始T07C-B4。
