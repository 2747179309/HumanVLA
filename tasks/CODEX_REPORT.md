# Codex 工作报告

## T07C-B3传统轨迹优化基线（2026-07-14）

- 编码前完成算法教学说明；只实现no-processing、SG、因果One Euro、因果Kalman CV和仅使用OpenPose confidence的confidence-weighted Kalman，没有启动B4质量感知方法。
- 预注册配置哈希`0815fe96...db16`；冻结B2 split为168/72/96且未重建。共47个候选，train只作开发诊断，全部候选由val评分选参。
- validation选择SG(window 7/order 2)、One Euro(5Hz/beta 0)、Kalman CV(q=8/r=0.005)和confidence-weighted Kalman(q=8/r0=0.005/gamma=1)。选参文件在test前记录配置、数据和raw轨迹哈希。
- test只运行一次：96样本×5方法=480条；全部split输出336×5=1680条且唯一。主指标penalized corrupted RMSE norm为SG 0.058489、One Euro 0.062395、confidence-weighted Kalman 0.081717、Kalman CV 0.082074、no-processing 0.328990。
- SG主误差最低但clean displacement最高(0.022568)；Kalman CV最保护clean region(0.008250)。One Euro在continuous drift上最低；没有方法在所有指标绝对最优。
- missing没有替换为0。no-processing short-missing正式位置/最大/导数指标为空，另用预注册1.0 penalty及coverage 0.927083显式记录失败。phase-boundary shift因B2窗口均为单phase而全部not applicable，不伪造为0。
- `py_compile`、三个`--help`、1680输出唯一性、480 test完整性、240完整分组、PNG、输入哈希与filter-input leakage检查全部通过。报告语义修正仅重建CSV/JSON/PNG，没有重跑算法、test或调参。
- 新增两份教学文档，包含公式、函数映射、真实`SYN_0263`全过程、参数影响、复现、常见错误和自测问题。当前停止等待B3独立验收，不开始T07C-B4。

## T07C-B2合成污染数据集（2026-07-14）

- 先输出教学实施说明，再按阶段计划只实现B2；没有启动B3传统滤波。
- 新增预注册配置`configs/dataset/t07c_b2_synthetic_corruption.json`，首次生成前哈希`35785fa...6055`；集中固定seed、clean门槛、时间split、窗口、强度和四类公式。
- 新增生成器和独立验证器，关键污染函数包含输入/输出/数学定义docstring，必要注释集中在真值筛选、split选择和随机种子处；两个脚本均通过`py_compile`和`--help`。
- clean truth要求四个参考关节同时为纯raw有效、无repair、无source event且同phase。生成14个clean窗口、336个样本；四类各84，三强度各112，split为168/72/96。
- 独立验证通过：clean逐点回查raw、污染公式、窗口阶段、24变体/窗口及split源帧零交集全部正确；输入哈希未变化，确定性复跑输出哈希一致。
- 输出：dataset `ee84857e...24d4e`，metadata `aacde9f1...0666`。
- 新增263行教学指南，包含数据流图、公式/伪代码、关键函数、真实`SYN_0005`完整实例、运行检查和常见错误。
- 当前局限：仅E001，split阶段分布不同；不能把后续误差差异直接外推为跨视频结论。当前停止等待B2质量审查，不开始B3。

## T07C-A最终frame-joint mask（2026-07-14）

- 新建`build_frame_joint_corruption_mask.py`和独立验证器，均通过`py_compile`与`--help`。
- 以用户填写后的CSV哈希`d6a2f289...bac1`为最终人工依据，生成恰好1380行、345×4关节唯一覆盖的mask；人工CSV与raw/repaired/quality输入均未修改。
- raw、repaired和selected downstream三层独立：50条raw无效；7条accepted RWrist repair有效并被选用；selected source为raw 1339、repaired 7、none 34。
- 关键语义全部通过独立验证：RWrist 64-65/143/182-185选repaired；RElbow 64-65和RWrist 178-179选none并延期T07C-B；182-185保留boundary warning；RElbow 54-55保留raw和normalization scale warning。
- 44条记录聚合多个source；RElbow 72-74的mask/downweight差异显式保存为3条action conflict，没有删除任何事件证据。129-143 defer没有被自动改写为mask。
- 输出哈希：mask `9d9654dc...1b53`，summary `e7246a07...e3bd`，overlay `831489ac...f659`。
- overlay为H.264、1280x720、30 FPS、345帧，全片解码通过；确定性复跑三项哈希一致。
- 未过滤、未新增插值、未修改轨迹、未开始T07C-B。当前停止等待Claude验收。

## T07C-A复核视频布局修订（2026-07-14）

- `build_corruption_candidate_review.py`新增`--render-only`，现有候选CSV作为只读输入；只覆盖11个短片、汇总视频和渲染summary。
- 信息面板从左上角移至底部桌面前沿，改为112像素半透明底栏，仅保留candidate_id、frame、joint、phase、confidence和source label；红色提示也移至底栏。
- 移除人体附近红色端点圈。视觉抽查确认头部、Neck、双肩、右肘和右腕不再被面板遮挡。
- 独立验证通过：11个短片编码和帧数保持完整，200帧H.264汇总视频全片解码通过。
- 候选CSV哈希仍为`474f7c1e...2bef`；raw/repaired trajectory、quality mask、jump review和repair summary哈希全部不变。
- 新汇总视频哈希`e6d9400e...0d22`，summary哈希`85c97794...003b`。未重跑OpenPose、关联、插值、轨迹计算或滤波。

## T07C-A候选复核材料（2026-07-14）

- 新建`scripts/trajectory/build_corruption_candidate_review.py`和`validate_corruption_review_materials.py`，均支持`--help`并通过`py_compile`。
- 从8个occlusion error、1个normalization artifact、64-65 RElbow low-quality和182-185 RWrist boundary warning生成11行空白人工复核CSV；3个已判定real motion未重复复核。
- 生成11个前后各8帧的H.264慢放短片及200帧汇总视频；画面包含raw骨架、raw/repaired轨迹、Neck/肩宽、关节置信度、阶段及from/to。
- 独立验证通过：11个人工复核字段组均为空、11个片段元数据正确、汇总视频全片解码无错误，输入哈希未变化。
- 输出：`corruption_candidate_review.csv`哈希`474f7c1e...2bef`；汇总视频`93fd783c...7a3e`；summary `165bd0ef...7911`。
- 未生成最终1380行`frame_joint_corruption_mask.jsonl`，因为用户要求不得自动决定错误帧或自动mask。当前材料阶段完成，任务等待人工逐帧裁决，不能标记T07C-A最终验收通过。
- 未修改raw/repaired trajectory、T06C quality mask或T07B summary；未运行过滤、插值、仿真或E002-E012。

## T07B-R1真实缺口人工复核固化（2026-07-14）

- 新建`scripts/trajectory/finalize_t07b_manual_review.py`，支持`--help`和显式`--overwrite`保护；逐关节写入人工复核、接受状态、置信度、下游有效性、备注和延期任务。
- 审计确认frame 64-65的RElbow是有原始坐标的`low_quality/forearm_self_occlusion`，并非missing。其原始值保持不变，未创建或采用肘部插值；人工状态为fail/rejected、下游无效，延期T07C。
- RWrist 64-65、143、182-185共7帧全部固化为pass/accepted/high/downstream-valid；182-185保留`boundary_continuity_warning=true`及`7.959980 norm/s`入口速度不连续性。
- 更新repaired JSONL/CSV和actual summary；自动置信度移至`automatic_repair_confidence`保存，`repair_confidence`改为逐关节人工字段。
- 扩展独立验证器并通过：345帧完整、CSV/JSONL一致、raw字段不变、人工规则正确、overlay全片解码通过。固化命令幂等复跑输出哈希一致。
- raw trajectory、T06C quality mask、44样本manifest和benchmark CSV/JSON哈希均未改变；linear仍是`provisional best on E001`，没有改变合成结果或全局排名。
- 输出哈希：repaired JSONL `4a04a6e...7411`，CSV `f55b38bc...f7b5`，summary `41ddcb4e...d1e1`。
- 当前状态：T07B-R1已固化，停止等待验收；未开始T07C，未进行新的插值、滤波或候选修复。

## T07B短缺口恢复基准（2026-07-14）

- 新建预注册policy、common module和4个验收脚本；`py_compile`、全部`--help`、独立验证和确定性复跑均通过。
- 合成样本44个，length 1/2/3/4为16/16/6/6；每关节22个，覆盖全部八个操作阶段，无阶段样本不足、真实缺失/人工错误帧泄漏或模型训练。
- 比较linear、PCHIP、cubic Hermite、Kalman CV；prediction-only和smoothing分别记录。RWrist mean RMSE_norm分别0.019819/0.022681/0.026315/0.022746，linear是预注册规则下唯一进入10%主指标带的方法。
- provisional best严格称为`provisional best on E001`。用linear修复RWrist 64-65、143、182-185共7帧；frame 0-1不修复，所有raw字段保持不变。
- 三段最大单帧位移0.058510/0.149972/0.039001肩宽，均低于0.5阈值；无方法失败或边界阈值异常。182-185入口速度不连续性7.959980 norm/s，列为最高人工复核优先级。
- 8个occlusion error事件只写入corruption list并延期T07C，候选关节不修复、不删除。修复数据使用独立字段和joint repair mask，observed frame未平滑。
- 生成benchmark CSV/JSON、PNG、345帧repaired JSONL/CSV、repair summary、corruption list和H.264 overlay；overlay全片解码通过，确定性复跑所有输出哈希一致。
- raw trajectory、quality mask、T07A review/summary和源视频哈希未变化。当前停止，不开始T07C。

## T07A-R1最小清理（2026-07-14）

- 新建`clean_jump_review_r1.py`并更新finalizer的7类允许标签校验；两个脚本通过`py_compile`和`--help`。
- JUMP_001改为normalization artifact；JUMP_005保留用户最终occlusion error并具体化右肘遮挡原因；JUMP_010/011统一为occlusion error且备注保留“骨架完全没有在手臂上”。
- 本轮开始时CSV已由外部更新为规范20列；R1确定性重写并再次验证无空表头、12个review区间和12个实际MP4路径。CSV SHA-256由`d7fc8d4c...e97a`变为`0a40f2a7...c84`。
- 新统计：normalization artifact 1、occlusion error 8、real motion 3；所有自定义标签已清除，其他允许标签为0，候选总数仍为12。
- summary已重新固化12项决定与新统计，SHA-256为`03eb5751...3528`；独立一致性检查通过。
- raw trajectory JSONL/CSV哈希未变化；未修改OpenPose输入、插值、滤波、删除真实/阶段边界/人体代偿运动或修复错误。当前等待Claude最终验收。

## T07A人工裁决最终固化（2026-07-14）

- 新建`finalize_jump_review.py`并通过`py_compile`和`--help`；逐项回查12行候选与summary/raw轨迹，三个manual字段均已填写。
- 人工标签原样统计：occlusion_error 6、openpose_jitter 1、real_motion 3、自定义“骨架完全没有在手臂上”2；confidence为high 9、medium 3。
- 关节统计为RElbow 9、RWrist 3；11项同阶段、1项跨阶段边界。所有候选均保留，真实运动、跨阶段运动和人体代偿删除标志均为false。
- openpose_jitter、occlusion_error和normalization_artifact只记录标记，修复数为0；两项自定义标签按用户原文保留，也未修复或重命名。
- 用户CSV存在统一的辅助列右移格式，但人工字段与核心候选字段完整。首次严格验证因此停止且未写summary；确认模式后只读接受，未修改CSV。
- `trajectory_summary.json`已写入12项裁决、分类统计、处理政策和输入哈希；独立一致性检查通过。
- raw trajectory JSONL哈希保持`c29b2a66...65506`，raw trajectory CSV保持`e2ae2e87...ab2c`；未插值、滤波或开始新实验。当前等待Claude最终验收。

## T07A跳变候选人工复核材料（2026-07-14）

- 新建`scripts/trajectory/build_jump_candidate_review.py`并通过`py_compile`与`--help`；脚本只读summary、轨迹和源视频，已有非空人工结论时拒绝覆盖CSV。
- 从summary完整读取12个候选：RElbow 9项、RWrist 3项；候选to_frame为55、64、66、68、72、90、138、140、144、178、180、224。
- 生成12行`jump_candidate_review.csv`，位移、置信度、肩宽、Neck位移和触发原因均来自真实轨迹/summary；三个manual字段全部留空。
- 生成12个逐候选短片，每项覆盖前后各5帧并包含候选边两端，共12个连续源帧；画面同时显示骨架、绝对像素路径、归一化路径和红色候选位置。
- 生成H.264汇总视频：1280x720、6 FPS、144帧、24秒。全部短片及汇总视频全片解码通过，JUMP_002/007/010视觉抽查通过。
- 轨迹JSONL、CSV、summary和源视频哈希未变化；未自动判错、插值、滤波或修改轨迹。当前停止等待人工填写复核CSV。

## T07A人工复核补充（2026-07-14）

- 修正T07A人工语义：异常遮挡帧为143而非43；64-65、143、182-185继续保留RWrist缺失和/或RElbow低质量，未插值。
- 扩展345帧JSONL/CSV，新增Neck相对首个有效frame 2的x/y位移，以及Neck、RShoulder、LShoulder逐帧dx/dy向量和欧氏像素位移；原有绝对Neck/肩/肘/腕像素和Neck/肩宽归一化坐标同时保留。
- Neck相对frame 2的dx范围[-7.850,48.933] px、dy范围[-15.651,9.894] px；连续位移均值为Neck 1.229844、RShoulder 1.394922、LShoulder 0.848750 px。
- 用户确认放置到B点附近的Neck/肩部平移为真实人体代偿；脚本不固定、不修改、不滤除这些坐标，summary明确禁止未来仅使用Neck相对轨迹进行仿真映射。
- 有效性与肩宽统计保持不变：trajectory 336、RElbow coordinate 343、RWrist 336；肩宽30%规则异常0帧。A/B绝对参考坐标尚未检测或标注，未伪造。
- `py_compile`、四个`--help`、独立验证和345帧overlay全片解码通过；frame 143/185/226视觉抽查正确。五个T06C锁定输入哈希未变化。
- T07A派生输出已重生成；12个Tukey候选仍只作为待人工复核项，不自动修复。未执行滤波、插值、纸盒检测、仿真映射或E002-E012处理。

## T07A E001原始右上肢轨迹（2026-07-14）

- 新建`extract_upper_limb_trajectory.py`、`analyze_raw_trajectory.py`、`render_raw_trajectory.py`、`validate_upper_limb_trajectory.py`；全部通过`py_compile`和`--help`。
- 仅处理`pick_place_pilot_v1_E001`，生成345行JSONL和345条数据行CSV。frame 0-1全部坐标null；RWrist在64、65、143、182-185为null；frame 226只使用P001 pose_index=0。
- RElbow坐标可用343帧、T06C source-valid 340帧、人工unstable规则后的effective high-quality 336帧；RWrist有效336帧。低质量RElbow raw像素/归一化值保留且标签未提升。
- 肩宽343帧：mean 165.425559 px、std 7.777305 px、min 143.766790 px、max 180.655606 px；按相邻变化超过全局均值30%的规则，异常0帧。
- Tukey extreme规则标出12个跳变候选：55、64、66、68、72、90、138、140、144、178、180、224。最大RElbow位移为65→66的0.323281 shoulder-width；最大RWrist位移为137→138的0.358744。
- reach至retract为frame 46-244；不跨缺失段的归一化路径长度为RElbow 6.526922、RWrist 8.213009，RWrist有10条相邻边因缺失跳过。
- 输出PNG为2880x1280；overlay为H.264、1280x720、30 FPS、345帧且全片解码通过。独立验证errors为空，公式、null规则、CSV一致性、frame 226和输入哈希全部通过。
- P001、quality mask、phase frames、T06C validation及源视频哈希未变化。未运行插值、Kalman、One Euro、Savitzky-Golay、纸盒检测、仿真映射、LeRobot或E002-E012。
- 当前只等待对12个跳变候选进行人工视觉裁决；自动结果不将候选声明为错误，也不自动修复。

## T06C最终人工复核记录（2026-07-13）

- 按用户结论扩展`manual_review.csv`为17条结构化记录：14条joint review和3条pose exclusion/identity policy记录。
- 新建`apply_t06c_manual_review.py`，将人工结论确定性写入quality mask的25项`manual_joint_status`、`manual_joint_reason`、`manual_joint_confidence`及pose review字段；不覆盖自动观测状态或raw值。
- frame 64-65：RElbow low_quality/forearm self-occlusion；RWrist missing/hand occludes wrist。frame 143：RElbow同类low quality；RWrist missing/hand and box occlusion。
- frame 182-185：RElbow记为unstable、RWrist记为missing_or_unstable；原因保留`suspected_`前缀，manual confidence为medium，不声称因果确定。
- frame 226的额外`pose_index=1`标记`excluded_reflection_artifact/table_reflection_false_positive`；P001的`pose_index=0`及frame_valid未改变，整帧保持valid。
- joint-level自动missing在确认轨迹帧中为Neck 0、RShoulder 0、RElbow 0、RWrist 7；人工明确确认的RWrist missing为3帧，182-185另列为missing或不稳定。
- 最终validation summary包含完整manual review结果，`validation_passed=true`且errors为空。帧级统计保持336 valid、7 low_quality、2 missing。
- 未运行DeepSORT/OpenPose，association SHA-256仍为`345b9e47...5cd`，raw OpenPose目录仍为`b068dc2d...d522c5e`；未插值、滤波或开始后续任务。

## T06C-M1上半身可见范围修正（2026-07-13）

- 未重跑DeepSORT或OpenPose，未修改关联JSONL、原始BODY_25 JSON或动作标签。OpenPose raw目录哈希仍为`b068dc2d...d522c5e`，MOT/subject map/phase/association输入哈希均未变化。
- 更新`build_upper_body_sequence.py`：345帧每帧新增25项`joint_observation_status`、`joint_valid`和`visibility_reason`。关节0-7、15-18按原始confidence判断；8-14、19-24无条件标记`out_of_frame/false/outside_capture_scope`。
- 完整25x3 `keypoints_raw`与25项`confidence_raw`保持不变。共1061个固定不可见关节的原始非零confidence被正确保留但强制判为无效。
- 辅助关节由Nose/LShoulder/MidHip改为Nose/LShoulder/LElbow/LWrist；核心关节仍为Neck/RShoulder/RElbow/RWrist。
- 更新主overlay，仅绘制可信上半身链和头部可见边；视觉抽查frame 2、45、64、65、100、143、182-185、226、300，未再显示Neck-MidHip、髋、腿或脚部推测骨架。
- 后续归一化策略记录为Neck原点、肩宽尺度，pelvis-centered normalization在本次拍摄中不可用。
- 重生成P001、quality mask、joint stats、H.264 345帧overlay和validation summary。独立验证通过，帧级统计保持336 valid、7 low_quality、2 missing。
- 仍需人工确认frame 226额外`pose_index=1`、frame 64/65/143/182-185及主overlay；未开始滤波、纸盒检测、仿真映射或E002-E012。

## T06C E001感知流水线下游完成（2026-07-13，待人工复核）

- 宿主机OpenPose单帧探针和完整345帧BODY_25均成功；raw JSON为345个、原始pose为346副，344帧1人、frame 226为2人/pose，格式异常0。原始JSON目录哈希在关联前后均为`b068dc2d...d522c5e`。
- 未重跑DeepSORT。复用343条`track_id=1`轨迹及用户人工确认的P001映射；frame 0-1因`n_init`确认期保持`missing`。
- 新建`associate_single_operator.py`、`build_upper_body_sequence.py`、`render_pose_phase_overlay.py`、`validate_e001_perception.py`，均通过`py_compile`和`--help`。
- T04参数阈值0.5试运行只匹配306/343；审计确认是上半身骨架框/完整人物框尺度差异后，将有限拒绝阈值适配为0.6，最终关联343/343，确认轨迹关联率1.0。未匹配pose共3副：frame 0、1以及frame 226的`pose_index=1`。
- P001质量统计：336 valid、7 low_quality、2 missing；low_quality为64、65、143、182-185，missing为0-1，ambiguous为空。OpenPose原始检出345/345，P001确认身份骨架343/343。
- 核心关节在确认轨迹帧的`conf>0`有效率：Neck 100%、RShoulder 100%、RElbow 100%、RWrist 97.959%；`conf>=0.3`质量通过率分别为100%、100%、99.125%、97.959%。
- 生成346行关联JSONL、345行P001合并序列、345行quality mask、核心关节/逐阶段统计和H.264 1280x720/30 FPS/345帧overlay。独立验证通过且视频全量解码成功，动作阶段字段逐帧与T06B一致。
- 关键边界45-47、96-98、105-107、119-121、138-140、174-176、192-194、205-208、243-246已从overlay视觉抽查，显示的阶段切换与人工标签一致。
- 当前只等待人工重点检查frame 226的额外残缺pose，以及64、65、143、182-185的核心关节低质量告警；不宣称T06C最终人工验收通过。未处理E002-E012，未滤波、插值、检测纸盒或进行仿真映射。

## T06C宿主机OpenPose运行脚本（2026-07-13）

- 用户确认普通宿主机终端中NVIDIA设备节点完整且`nvidia-smi`正常识别RTX 3090；根因最终确定为Codex受限环境无GPU设备访问，不进行任何驱动、重启或系统配置操作。
- 新建可执行脚本`scripts/run_t06c_openpose_host.sh`，固定只处理`pick_place_pilot_v1_E001`，只验证并复用现有DeepSORT raw和P001/human_confirmed映射。
- 脚本先检查`nvidia-smi`和三个必需设备节点，再运行frame 0 BODY_25 CUDA探针；必须同时生成合法75值JSON、操作者检测和渲染图，且四个核心关节不能全部缺失，否则立即停止。
- 单帧通过后才调用现有OpenPose runner处理完整345帧，并验证0-344 JSON序列、BODY_25长度、原始confidence策略、H.264渲染帧数和可解码性。
- 默认拒绝已有输出；显式`--overwrite`会归档而非删除旧结果。所有stdout/stderr追加到`logs/runs/T06C_OPENPOSE_HOST_RUN.log`。
- `bash -n`和`--help`通过；未安装shellcheck。按用户要求，本轮未在Codex环境实际运行OpenPose，也未重跑DeepSORT。

## T06C-R GPU诊断与恢复（2026-07-13）

- 阶段A完整诊断保存于`results/system/T06C_gpu_diagnostic.txt`，分类为G：RTX 3090、550.144.03模块、DKMS、headers和用户态库均存在且版本匹配，但当前运行环境没有`/dev/nvidia*`。
- Secure Boot未启用；无DKMS/内核不匹配或driver/library mismatch证据。`nvidia-modprobe`未安装。
- APT模拟确认安装`nvidia-modprobe`只新增1包、升级0、删除0；实际sudo在APT执行前因受限环境的setuid/root能力缺失而失败，没有系统修改。
- 当前`/dev`与`sudo`所有权显示本进程处于受限命名空间，因此需用户先在主机普通终端运行`ls -l /dev/nvidia*`和`nvidia-smi`；主机同样缺失时再安装并运行`nvidia-modprobe -u -c=0`。
- Codex环境内`nvidia-smi`和设备节点仍不可用；随后用户确认宿主机终端GPU正常，故不再进行系统恢复。OpenPose改由宿主机脚本执行。
- 用户已人工确认track 1始终为主操作者，subject map正式更新为P001；frame 0-1继续保持missing。DeepSORT未重跑，既有raw结果未修改。

## T06C E001感知流水线（2026-07-13，部分完成/阻塞）

- Run ID `20260713_T06C_E001_001`。DeepSORT以CPU处理E001全部345帧，产生345个person检测和唯一 `track_id=1`。
- track 1连续覆盖frame 2-344共343帧、内部缺口0、平均置信度0.754752；frame 0-1为`n_init=3`确认前缺失。七个时刻视觉抽查未发现身份切换。
- track 1初始临时映射为P001；随后用户人工确认其始终为主操作者，subject map更新为`human_confirmed`。raw结果完整保留，无短track被删除。
- MOT视频为H.264、1280x720、30 FPS、345帧且完整解码通过。
- OpenPose阻塞：`nvidia-smi`失败、PyTorch CUDA不可用、`/dev/nvidia*`不存在。BODY_25单帧CPU回退探针仍返回CUDA错误100/退出255，未生成JSON。
- 因无真实BODY_25输入，未运行关联、质量掩码、骨架动作合并及核心关节统计，也未生成伪造的全missing结果。
- 完整命令、哈希、错误和未完成指标见 `logs/runs/T06C_E001_PERCEPTION_PIPELINE.md`。未处理E002-E012，未运行滤波、插值、纸盒检测、仿真映射、LeRobot转换或训练。

## T06B E001边界修正版复验（2026-07-13）

- Run ID `20260713_T06B_E001_REVALIDATE_001`。实际输入为 `E001_action_phase_annotations_corrected.csv`；原无后缀路径已不存在，因此先定位修正版后才重建派生结果。
- 人工边界确认：frame 206为release，207-244共38帧为retract，245-344共100帧为结束idle。
- 10个区间完整覆盖0-344共345帧；空洞、重叠、越界、非法阶段、错误和警告均为0。
- 重生成345条frame JSONL、validation summary及H.264 overlay；overlay保持1280×720、30 FPS、345帧、11.5秒并全量解码通过。
- 修正后统计：retract 38帧/1.266667秒，idle合计146帧/4.866667秒；其他阶段不变。
- 修正版人工CSV与源视频保持只读。未处理E002-E012，未运行OpenPose、DeepSORT、滤波、LeRobot转换或训练。

## T06B E001人工标签验证（2026-07-13）

- Run ID `20260713_T06B_E001_VALIDATE_001`。人工CSV含10个区间，完整覆盖0-344共345帧；空洞0、重叠0、越界0、非法阶段0，双语文本检查通过。
- 新建 `validate_labels.py`、`expand_frame_labels.py` 和 `render_labels.py`，均通过 `py_compile` 和 `--help`；未声称T06A其余4个工具已实现。
- 从人工区间确定性导出345条frame JSONL，独立逐条回查segment、phase、双语文本和时间戳全部一致，未推测或修改人工标签。
- 生成H.264双语overlay：1280×720、30 FPS、345帧、11.5秒；完整解码通过，抽查全部阶段切换首帧及末帧显示正确。
- 阶段帧数：idle 177、reach 52、align 9、grasp 14、lift 19、transport 36、place 18、release 13、retract 7；其余扩展阶段为0。
- 源视频和人工CSV哈希未变化。未处理E002-E012，未运行OpenPose、DeepSORT、滤波、LeRobot转换或训练。

## T06B E001第一阶段（2026-07-13）

- 仅审计 `P01_BOX01_R_A_B_E001_S.mp4`：HEVC、1280×720、30 FPS、345帧、11.5秒；FFmpeg全量解码345/345帧无错误。
- 将唯一E001记录写入 `data/action_labels/video_manifest.csv`，源文件SHA-256为 `c29458c...745a2`，处理前后未变化。
- 生成18字段、仅表头、0条阶段记录的人工标注CSV；未自动推测任何动作阶段。
- 生成H.264预览视频，保持1280×720、30 FPS、345帧、11.5秒；全量解码通过，抽查帧172的帧号和时间戳显示正确。
- Run ID：`20260713_T06B_STAGE1_E001`，完整命令与真实结果见 `logs/runs/T06B_ACTION_PHASE_LABELING.md`。
- 该阶段当时停止等待人工CSV；后续人工标签验证结果见上一节。未处理E002-E012，未滤波，未进行LeRobot转换或训练。

## T06A 操作视频标注规范与任务设计（2026-07-13）

### 本轮完成

- 修订 `context/ACTION_PHASE_SCHEMA.md`，定义 episode、人工阶段区间、逐帧字段、双语文本、物体/手别/成功/质量状态及特殊场景规则。
- 新建并完善 `tasks/T06A_ACCEPTANCE_CRITERIA.md`，规定下一轮实现的7个脚本、输出、自动验证和人工验收方法。
- 更新 `tasks/CURRENT_TASK.md`、`tasks/TASK_QUEUE.md` 和 `tasks/DECISIONS.md`，确立主线、Kinect支线、K01 RGB-only和数据划分边界。

### 关键修正

- 人工阶段闭区间是权威标签，frame/text文件只做确定性展开，不对离散阶段ID插值。
- 边界帧归属新阶段，不强制最短3帧；真实的短暂抓取或释放阶段不得因时长被合并。
- 数据集按源视频/录制会话分组，禁止同一视频跨train/val/test；单次录制K01标记为`unsplit`。
- RGB无法可靠测量的固定物理距离和视线方向不作为硬边界条件；FPS未知时工具必须停止而非猜测时间戳。

### 执行与边界

- 本轮仅执行文档读取、编辑和一致性检查；未运行标注代码，未处理K01，未创建实验结果。
- 未加载Kinect深度/骨架，未修改原始数据，未进行LeRobot转换、滤波、训练或T06B。
- 下一步需用户另行要求后，按T06A验收标准实现工具并以K01 RGB进行真实原型验收。

## T05A 骨架序列与质量掩码（2026-07-13）

### 实现与输出

- 新建`build_subject_sequences.py`、`build_quality_mask.py`、`validate_quality_mask.py`、`render_quality_mask.py`，均支持`--help`并通过`py_compile`。
- 生成P001/P002/P003各240行连续序列、720行`quality_mask.jsonl`、摘要和240帧H.264可视化。
- 修正后帧0-1不再进行几何身份分配，统一填充为`missing`、`frame_valid=false`和`no_confirmed_track_identity`。

### 真实统计

- P001：222 valid、13 low_quality、3 invalid_identity_mix、2 missing。
- P002：238 valid、0 low_quality、0 invalid、2 missing。
- P003：235 valid、0 low_quality、3 invalid_identity_mix、2 missing。
- 全局：695 valid、13 low_quality、6 invalid、6 missing；额外pose层排除3个ambiguous、1个phantom、2个non-target。
- 最终序列含99个大于1的confidence；帧0-1整体missing置零，其他保留pose未裁剪且与T04 JSONL逐值相同。

### 验证与边界

- 独立验证器通过，720条掩码完整，43-45未误标为valid，输入文件和OpenPose raw目录哈希未变化。
- 修正后可视化检查通过：帧0-1只显示灰色missing标签，帧2恢复绿色；其余质量颜色规则不变。
- 几何回溯身份已从脚本和有效派生数据中移除。
- 未执行滤波、插值、平滑、Kinect对齐或T05B。

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
