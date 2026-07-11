# HumanVideo2VLA — 实验记录手册

## 实验总览

| Exp | 名称 | 核心指标 | 输入 | 优先级 | 状态 |
|-----|------|---------|------|--------|------|
| E1 | 动作语义分段 | Boundary F1, mIoU | 50Salads, Breakfast, 自采视频 | P0-Critical | ⬜ 未开始 |
| E2 | 文本-动作对齐 | R@1, R@5, CLIP-Sim, 人工评分 | YouCook2, 自采视频 | P0-Critical | ⬜ 未开始 |
| E3 | 3D骨架质量 | MPJPE, PA-MPJPE, Jerk | Human3.6M, 3DPW | P0-Critical | ⬜ 未开始 |
| E4 | 人机动作映射 | EE误差, IK成功率, 碰撞率 | PyBullet (xArm/Franka/Kinova) | P0-Critical | ⬜ 未开始 |
| E5 | 策略学习验证 | 成功率, MSE, Loss曲线 | 自建数据集 + ACT/DP | P1-High | 🔄 可行性已验证 |
| E6 | 消融实验 | Δ成功率 per component | 7种数据变体 + ACT | P1-High | ⬜ 未开始 |

---

## E1: 动作语义分段实验

### 实验目的
验证多模态特征融合（光流+CLIP+关键点）的动作边界检测精度，证明融合方法优于单一特征。

### 数据集

| 数据集 | 规模 | 标注 | 获取方式 |
|--------|------|------|---------|
| **50Salads** | 50视频, 17动作类 | 帧级action label | [官网下载](https://cvip.computing.dundee.ac.uk/datasets/foodpreparation/50salads/) |
| **Breakfast** | 1712视频, 48动作类 | 帧级action label | [官网下载](https://serre-lab.clps.brown.edu/resource/breakfast-actions-dataset/) |
| **自采标注集** | ≥30视频 | 帧级phase label (6类) | 自己拍摄+人工标注 |

### 对比方法（共7组）

| ID | 方法 | 特征 | 说明 |
|----|------|------|------|
| B1 | C2F-TCN | RGB | 多阶段TCN基线 |
| B2 | ASFormer | RGB | Transformer基线 |
| B3 | LTContext | RGB | 长程上下文基线 |
| B4 | Flow-Only | 仅光流 (α=1.0) | 消融:纯运动 |
| B5 | CLIP-Only | 仅CLIP (β=1.0) | 消融:纯语义 |
| B6 | KP-Only | 仅关键点 (γ=1.0) | 消融:纯人体 |
| B7 | **Ours** | 融合 α=0.5,β=0.3,γ=0.2 | 完整方法 |

### 指标定义

| 指标 | 公式 | 含义 |
|------|------|------|
| **Boundary F1@3** | 预测边界与GT边界距离≤3帧视为正确 | 精确边界检测 |
| **Boundary F1@5** | 容差5帧 | 宽松边界检测 |
| **Boundary F1@10** | 容差10帧 | 粗粒度边界检测 |
| **mIoU** | mean(Intersection/Union) per segment | 段级别重叠度 |
| **ΔK** | \|K_pred - K_gt\| / K_gt | 段数误差 |
| **OverSeg Rate** | 假边界数 / 真边界数 | 过分割程度 |

### 执行步骤

```
Step 1: 下载50Salads和Breakfast数据集
Step 2: 安装依赖: pip install mmpose opencv-python torch torchvision
Step 3: 下载预训练模型: HRNet-w32 (MMPose), RAFT (torchvision), CLIP-ViT-B/32
Step 4: 对每个数据集视频:
  a. 运行 scripts/extract_features.py --video <path> --output <feat_dir>
     输出: flow/*.npy, clip/*.npy, keypoints/*.npy
  b. 运行 scripts/segment_actions.py --features <feat_dir> --alpha 0.5 --beta 0.3 --gamma 0.2
     输出: boundaries.json, segments.json
  c. 对B4/B5/B6: 修改 --alpha/--beta/--gamma 参数
Step 5: 运行 scripts/eval_segmentation.py --pred <boundaries.json> --gt <gt.json>
     输出: metrics.json (F1@3, F1@5, F1@10, mIoU, ΔK, OverSeg)
Step 6: 汇总所有7组方法的指标到结果表
Step 7: 生成可视化: ΔF(t)曲线+边界叠加图 (scripts/visualize_segmentation.py)
```

### 结果记录表

#### 表E1.1: 50Salads数据集

| Method | F1@3 | F1@5 | F1@10 | mIoU | ΔK | OverSeg |
|--------|------|------|-------|------|-----|---------|
| C2F-TCN | | | | | | |
| ASFormer | | | | | | |
| LTContext | | | | | | |
| Flow-Only | | | | | | |
| CLIP-Only | | | | | | |
| KP-Only | | | | | | |
| **Ours** | | | | | | |

#### 表E1.2: Breakfast数据集

| Method | F1@3 | F1@5 | F1@10 | mIoU | ΔK | OverSeg |
|--------|------|------|-------|------|-----|---------|
| C2F-TCN | | | | | | |
| ASFormer | | | | | | |
| LTContext | | | | | | |
| Flow-Only | | | | | | |
| CLIP-Only | | | | | | |
| KP-Only | | | | | | |
| **Ours** | | | | | | |

#### 表E1.3: 自采标注集

| Method | F1@3 | F1@5 | F1@10 | mIoU | ΔK | OverSeg |
|--------|------|------|-------|------|-----|---------|
| C2F-TCN | | | | | | |
| ASFormer | | | | | | |
| Flow-Only | | | | | | |
| CLIP-Only | | | | | | |
| KP-Only | | | | | | |
| **Ours** | | | | | | |

#### 表E1.4: 各权重组合对比 (自采标注集)

| α | β | γ | F1@3 | mIoU | ΔK | 备注 |
|---|---|-----|------|------|-----|------|
| 0.33 | 0.33 | 0.33 | | | | 等权重 |
| 0.5 | 0.3 | 0.2 | | | | **默认(Ours)** |
| 0.6 | 0.2 | 0.2 | | | | 偏重光流 |
| 0.4 | 0.4 | 0.2 | | | | 偏重语义 |
| 0.4 | 0.3 | 0.3 | | | | 偏重人体 |

#### 表E1.5: 自适应λ vs 固定λ (自采标注集)

| λ设置 | F1@3 | mIoU | ΔK | 备注 |
|-------|------|------|-----|------|
| λ=1.0 (固定) | | | | 低阈值=过分割 |
| λ=2.5 (固定) | | | | 高阈值=欠分割 |
| λ自适应 (Ours) | | | | [1.5, 2.5] |

---

## E2: 文本-动作对齐实验

### 实验目的
验证MLLM生成文本描述的质量和双向对齐的精度。

### 数据集

| 数据集 | 规模 | 获取方式 |
|--------|------|---------|
| **YouCook2** | 2000烹饪视频, 有标注步骤文本 | [官网](http://youcook2.eecs.umich.edu/) |
| **自采对齐验证集** | ≥30视频, ~180个动作段, 人工标注对齐GT | 自己拍摄+标注 |

### MLLM变体（≥3种）

| ID | MLLM | 获取方式 |
|----|------|---------|
| M1 | GPT-4V | OpenAI API |
| M2 | InternVL2-8B | 本地部署 |
| M3 | Qwen-VL-Plus | 阿里云API |

### 对比方法

| ID | 方法 | 对齐粒度 |
|----|------|---------|
| A1 | Global CLIP | 视频级 (整段视频 vs 整段文本) |
| A2 | MIL-NCE | 视频级 |
| A3 | **Ours (GPT-4V)** | 段级 (动作段 vs 动作描述) |
| A4 | **Ours (InternVL2)** | 段级 |
| A5 | **Ours (Qwen-VL)** | 段级 |

### 指标定义

| 指标 | 描述 | 测量方法 |
|------|------|---------|
| **Recall@1** | Top-1检索到的段是正确的 | 文本查询→检索视频段 |
| **Recall@5** | 正确段在Top-5中 | 文本查询→检索视频段 |
| **CLIP-Sim** | 配对文本-视频余弦相似度均值 | CLIP编码后计算 |
| **人工-相关性** | "描述与视频段相关吗?" (1-5) | 5人评分, 取均值 |
| **人工-完整性** | "描述完整覆盖了动作吗?" (1-5) | 5人评分, 取均值 |
| **人工-准确性** | "空间/动作细节正确吗?" (1-5) | 5人评分, 取均值 |
| **Fleiss' κ** | 评分者间一致性 | 统计检验 |

### 人工评分模板

```
评分者ID: _____  日期: _____  视频段ID: _____

请观看以下视频段并阅读生成的文本描述，按1-5分评价:

【视频段】[播放视频段, 时长2-5秒]
【生成文本】"[MLLM生成的描述]"
【参考文本】"[人工标注的GT描述]" (评分时不可见, 仅用于后续对比)

1. 相关性 (Relevance): 这段文字描述与视频中的动作相关吗?
   1=完全无关  2=弱相关  3=部分相关  4=大部分相关  5=完全相关
   评分: _____

2. 完整性 (Completeness): 描述是否完整覆盖了动作的各个阶段?
   1=严重缺失  2=缺失较多  3=基本覆盖  4=较完整  5=非常完整
   评分: _____

3. 准确性 (Accuracy): 描述中的空间关系、动作类型、操作对象是否正确?
   1=多处错误  2=有重要错误  3=基本正确  4=较准确  5=非常准确
   评分: _____

备注(如有): _________________________________
```

### 执行步骤

```
Step 1: 下载YouCook2数据集
Step 2: 对每个视频运行分段(使用E1的Ours方法)
Step 3: 对每个动作段, 调用3种MLLM生成文本描述
  a. GPT-4V: scripts/generate_text.py --mllm gpt4v --segment <segment_dir>
  b. InternVL2: scripts/generate_text.py --mllm internvl2 --segment <segment_dir>
  c. Qwen-VL: scripts/generate_text.py --mllm qwenvl --segment <segment_dir>
Step 4: CLIP编码所有文本和视频段
  scripts/encode_clip.py --texts <texts.json> --videos <video_dir> --output <embeddings.npy>
Step 5: 计算相似度矩阵 + Hungarian匹配
  scripts/align_text_video.py --text_emb <emb> --video_emb <emb> --output <alignment.json>
Step 6: 计算R@1, R@5, CLIP-Sim
  scripts/eval_alignment.py --alignment <alignment.json> --gt <gt_alignment.json>
Step 7: 人工评分: 准备评分表, 召集5名评分者, 每人评≥50个段
Step 8: 汇总所有结果到表E2.1和E2.2
```

### 结果记录表

#### 表E2.1: 定量对齐指标

| Method | R@1 | R@5 | CLIP-Sim | 相关性 | 完整性 | 准确性 | Fleiss' κ |
|--------|-----|-----|----------|--------|--------|--------|-----------|
| Global CLIP | | | | | | | |
| MIL-NCE | | | | | | | |
| Ours (GPT-4V) | | | | | | | |
| Ours (InternVL2) | | | | | | | |
| Ours (Qwen-VL) | | | | | | | |

#### 表E2.2: 按任务类型的对齐精度 (Ours最佳MLLM)

| 任务类型 | R@1 | CLIP-Sim | 相关性 | 完整性 |
|----------|-----|----------|--------|--------|
| reach (伸手) | | | | |
| grasp (抓取) | | | | |
| move (搬运) | | | | |
| place (放置) | | | | |
| pour (倒水) | | | | |
| open_door (开门) | | | | |
| wipe (擦拭) | | | | |

#### 表E2.3: 对齐成功/失败案例

| 视频段 | MLLM | 生成文本 | Sim | 相关性 | 成功/失败原因 |
|--------|------|---------|-----|--------|-------------|
| (例) 伸手抓杯 | GPT-4V | "伸手向桌上的白色杯子..." | 0.78 | 4.6 | ✅ 完整准确 |
| (例) 倒水 | InternVL2 | "一个人在倒东西" | 0.32 | 2.2 | ❌ 过于模糊 |

---

## E3: 3D骨架质量实验

### 实验目的
评估3D骨架提取精度和卡尔曼滤波平滑效果。

### 数据集

| 数据集 | 规模 | GT类型 | 获取方式 |
|--------|------|--------|---------|
| **Human3.6M** | 360万帧, 4相机 | Mocap (毫米级精度) | [官网申请](http://vision.imar.ro/human3.6m/) |
| **3DPW** | 野外场景 | IMU+相机GT | [官网](https://virtualhumans.mpi-inf.mpg.de/3DPW/) |
| **自采多视角验证集** | ≥10视频, 2相机 | 多视角三角化GT | 自己拍摄 |

### 实验变量组合（2D检测器 × 3D提升器 × 平滑方法）

| 组合ID | 2D Detector | 3D Lifter | Smoothing |
|--------|-------------|-----------|-----------|
| S1 | HRNet-w32 | VideoPose3D | None |
| S2 | HRNet-w32 | VideoPose3D | Moving Avg (w=5) |
| S3 | HRNet-w32 | VideoPose3D | Savitzky-Golay (w=5, ord=3) |
| S4 | HRNet-w32 | VideoPose3D | **Kalman (Ours)** |
| S5 | ViTPose | VideoPose3D | Kalman |
| S6 | RTMPose | VideoPose3D | Kalman |
| S7 | HRNet-w32 | MotionBERT | Kalman |

### 指标定义

| 指标 | 单位 | 计算公式 |
|------|------|---------|
| **MPJPE** | mm | (1/N)·Σ_i ‖q_pred_i - q_gt_i‖₂ |
| **PA-MPJPE** | mm | Procrustes对齐后的MPJPE |
| **Velocity Smoothness (Jerk)** | mm/f² | (1/(T-2))·Σ_t‖(q_{t+1}-q_t)-(q_t-q_{t-1})‖² |
| **Jitter Amplitude** | mm | 高频(>5Hz)分量幅值 |
| **Missing Rate** | % | 置信度<0.3的帧比例 |

### 执行步骤

```
Step 1: 申请并下载Human3.6M和3DPW
Step 2: 预处理: 提取视频帧, 对齐GT标注
Step 3: 运行2D关键点检测:
  scripts/detect_keypoints.py --detector hrnet --video <path> --output <kp2d_dir>
  scripts/detect_keypoints.py --detector vitpose --video <path> --output <kp2d_dir>
  scripts/detect_keypoints.py --detector rtmpose --video <path> --output <kp2d_dir>
Step 4: 运行2D→3D提升:
  scripts/lift_to_3d.py --keypoints <kp2d_dir> --lifter videopose3d --output <pose3d_dir>
  scripts/lift_to_3d.py --keypoints <kp2d_dir> --lifter motionbert --output <pose3d_dir>
Step 5: 运行平滑:
  scripts/smooth_skeleton.py --pose3d <pose3d_dir> --method none   --output <smoothed_none>
  scripts/smooth_skeleton.py --pose3d <pose3d_dir> --method movavg --output <smoothed_ma>
  scripts/smooth_skeleton.py --pose3d <pose3d_dir> --method savgol --output <smoothed_sg>
  scripts/smooth_skeleton.py --pose3d <pose3d_dir> --method kalman --output <smoothed_kf>
Step 6: 评估:
  scripts/eval_skeleton.py --pred <smoothed_dir> --gt <gt_dir> --output <metrics.json>
Step 7: 汇总到表E3
```

### 结果记录表

#### 表E3.1: Human3.6M (S9/S11协议)

| 2D Det | 3D Lifter | Smooth | MPJPE↓ | PA-MPJPE↓ | Jerk↓ | Jitter↓ | Miss%↓ |
|--------|-----------|--------|--------|-----------|-------|---------|--------|
| HRNet | VP3D | None | | | | | |
| HRNet | VP3D | MovAvg | | | | | |
| HRNet | VP3D | SavGol | | | | | |
| HRNet | VP3D | **Kalman** | | | | | |
| ViTPose | VP3D | Kalman | | | | | |
| RTMPose | VP3D | Kalman | | | | | |
| HRNet | MotionBERT | Kalman | | | | | |

#### 表E3.2: 3DPW

| 2D Det | 3D Lifter | Smooth | MPJPE↓ | PA-MPJPE↓ | Jerk↓ | Jitter↓ |
|--------|-----------|--------|--------|-----------|-------|---------|
| HRNet | VP3D | None | | | | |
| HRNet | VP3D | **Kalman** | | | | |

#### 表E3.3: 逐关节MPJPE (Human3.6M, HRNet+VP3D+Kalman)

| 关节 | MPJPE (mm) | 备注 |
|------|-----------|------|
| 鼻 (nose) | | |
| 左/右肩 (shoulder) | | |
| 左/右肘 (elbow) | | |
| 左/右腕 (wrist) | | ← 最关键，直接影响映射精度 |
| 左/右髋 (hip) | | |
| 左/右膝 (knee) | | |
| 左/右踝 (ankle) | | |
| **Mean** | | |

#### 表E3.4: 平滑效果对比-Jerk降低率

| 平滑方法 | 腕关节Jerk↓ | 肘关节Jerk↓ | 肩关节Jerk↓ | 平均Jerk↓ |
|----------|------------|------------|------------|----------|
| vs None (基线) | 0% | 0% | 0% | 0% |
| MovAvg | | | | |
| SavGol | | | | |
| **Kalman** | | | | ≥30%预期 |

---

## E4: 人机动作映射实验

### 实验目的
评估从人体骨架到机器人关节角/末端轨迹的映射精度和物理可行性。

### 平台

| 平台 | DOF | 仿真环境 | 关节范围文件 |
|------|-----|---------|------------|
| **xArm 6** | 6 | PyBullet | configs/xarm6_joint_limits.json |
| **Franka Emika Panda** | 7 | PyBullet | configs/franka_joint_limits.json |
| **Kinova Gen3** | 7 | PyBullet | configs/kinova_joint_limits.json |

### 校准数据
- **每平台100组**人-机配对动作样本
- 来源: PyBullet中同时记录人体骨架和对应机器人最优轨迹
- 格式: `calib/xarm6_pairs.json`, `calib/franka_pairs.json`, `calib/kinova_pairs.json`

### 对比方法

| ID | 方法 | 说明 |
|----|------|------|
| M1 | Direct Linear (no IK) | W,b线性映射, 无约束 |
| M2 | IK-Only (ICP) | 纯末端IK求解, 无骨架 |
| M3 | QP Optimization | Jiang 2025的QP方法 |
| M4 | **Ours (Linear+IK)** | W,b映射 + 限位clamp + 碰撞规避 |

### 测试任务（每平台×5任务）

| 任务 | 描述 | 难度 |
|------|------|------|
| reach | 伸手到固定目标 | 简单 |
| grasp | 抓取桌上物体 | 中等 |
| place | 放置物体到指定位置 | 中等 |
| pour | 倾斜容器倒水 | 中等 |
| transport | 搬运物体移动50cm | 较难 |

### 指标定义

| 指标 | 单位 | 计算 |
|------|------|------|
| **EE Position Error** | cm | ‖x_pred - x_gt‖₂ |
| **EE Orientation Error** | ° | angular_distance(R_pred, R_gt) |
| **Joint Limit Violation Rate** | % | 超出限位的帧数/总帧数 |
| **Self-Collision Rate** | % | 发生自碰撞的帧数/总帧数 |
| **IK Success Rate** | % | IK求解成功的帧数/总帧数 |
| **Action Smoothness** | rad/f² | 关节角加速度均值 |
| **Semantic Preservation** | 1-5 | 人工评分: "机器人动作是否保留了人类动作意图?" |

### 执行步骤

```
Step 1: 生成校准数据
  scripts/generate_calib_data.py --robot xarm6 --num_pairs 100 --output calib/xarm6_pairs.json
  (对franka, kinova重复)

Step 2: 校准W,b矩阵
  scripts/calibrate_mapping.py --pairs calib/xarm6_pairs.json --output calib/xarm6_W_b.npy
  (对franka, kinova重复)

Step 3: 对每个平台×方法×任务组合:
  scripts/run_mapping.py --robot <robot> --method <method> --task <task> \
    --calib calib/<robot>_W_b.npy --output results/E4/<robot>_<method>_<task>/
  输出: mapped_actions.npy, metrics.json, collision_log.txt

Step 4: 对M4(Ours)额外运行碰撞检测和IK验证
  scripts/validate_constraints.py --actions <mapped_actions.npy> --robot <robot>

Step 5: 人工语义评分
  每个平台的M1+M4方法, 每任务生成5段视频, 3人评分

Step 6: 汇总到表E4
```

### 结果记录表

#### 表E4.1: xArm 6 — 末端误差和可行性

| Method | EE Pos(cm)↓ | EE Ori(°)↓ | Viol%↓ | Coll%↓ | IK%↑ | Smooth↓ | Sem↑ |
|--------|------------|------------|--------|--------|------|---------|------|
| Direct Linear | | | | | | | |
| IK-Only | | | | | | | |
| QP | | | | | | | |
| **Ours** | | | | | | | |

#### 表E4.2: Franka Emika Panda

| Method | EE Pos(cm)↓ | EE Ori(°)↓ | Viol%↓ | Coll%↓ | IK%↑ | Smooth↓ | Sem↑ |
|--------|------------|------------|--------|--------|------|---------|------|
| Direct Linear | | | | | | | |
| **Ours** | | | | | | | |

#### 表E4.3: Kinova Gen3

| Method | EE Pos(cm)↓ | EE Ori(°)↓ | Viol%↓ | Coll%↓ | IK%↑ | Smooth↓ | Sem↑ |
|--------|------------|------------|--------|--------|------|---------|------|
| Direct Linear | | | | | | | |
| **Ours** | | | | | | | |

#### 表E4.4: 按任务的映射精度 (Ours, xArm 6)

| Task | EE Pos(cm)↓ | EE Ori(°)↓ | Viol%↓ | IK%↑ | 难度 |
|------|------------|------------|--------|------|------|
| reach | | | | | 简单 |
| grasp | | | | | 中等 |
| place | | | | | 中等 |
| pour | | | | | 中等 |
| transport | | | | | 较难 |

#### 表E4.5: 校准数据量对精度的影响 (Ours, xArm 6, reach任务)

| 校准对数 | EE Pos(cm)↓ | EE Ori(°)↓ | 备注 |
|----------|------------|------------|------|
| 20 | | | 少量样本 |
| 50 | | | |
| 100 | | | 默认(Ours) |
| 200 | | | 充足样本 |

---

## E5: 策略学习验证实验

### 实验目的
验证从人类视频构建的数据集能够训练出可工作的机器人策略。

### 已完成 (可行性验证)

| 项目 | 状态 | 备注 |
|------|------|------|
| LeRobot环境搭建 | ✅ | Ubuntu 20.04, Miniforge |
| PushT数据集加载+可视化 | ✅ | 理解obs/state/action结构 |
| ACT CPU 100步训练 | ✅ | checkpoint已保存 |
| PushT仿真评估 | ✅ | |
| 原型数据集构建 | ✅ | generic_manipulation_skeleton_dataset |

### 待完成

| 策略 | 任务 | 数据来源 | 目标成功率 |
|------|------|---------|-----------|
| **ACT** | PushT | 标准LeRobot数据 (对照组) | >80% (已知可行) |
| **ACT** | PushT | 我们的人类视频→机器人数据 | >0% (证明可用) |
| **ACT** | Cup Grasp | 我们的数据 | >50% |
| **ACT** | Pouring | 我们的数据 | >40% |
| **ACT** | Object Transport | 我们的数据 | >40% |
| **Diffusion Policy** | PushT | 标准LeRobot数据 (对照组) | >80% |
| **Diffusion Policy** | PushT | 我们的数据 | >0% |
| **Diffusion Policy** | Cup Grasp | 我们的数据 | >50% |
| **Diffusion Policy** | Pouring | 我们的数据 | >40% |

### 训练超参数

| 参数 | ACT | Diffusion Policy |
|------|-----|-----------------|
| Epochs | 100 | 200 |
| Learning Rate | 1e-4 | 1e-4 |
| Batch Size | 64 | 256 |
| Optimizer | AdamW | AdamW |
| Chunk Size (ACT) | 100 | N/A |
| Obs Horizon (DP) | N/A | 2 |
| Action Horizon (DP) | N/A | 16 |
| Execution Horizon (DP) | N/A | 8 |
| GPU | RTX 3090 24GB | RTX 3090 24GB |

### 指标定义

| 指标 | 含义 | 测量方法 |
|------|------|---------|
| **Training Loss** | 训练损失曲线 | TensorBoard记录 |
| **Validation Loss** | 验证损失 | 每10 epoch评估 |
| **Action MSE** | 预测动作与GT的MSE | 在held-out数据上计算 |
| **Task Success Rate** | 任务完成率 | 每任务≥50次rollout |
| **Completion Time** | 完成时间(秒) | rollout计时 |
| **Action Smoothness** | 执行动作的jerk均值 | 动作序列计算 |

### 执行步骤

```
Step 1: 准备数据
  - 确保我们的数据集在LeRobot可加载路径
  - 运行 scripts/convert_to_lerobot.py --input outputs/xxx/ --output ~/lerobot_data/human2vla/

Step 2: 对照组训练 (标准PushT)
  python lerobot/scripts/train.py \
    --policy.type=act \
    --dataset.repo_id=lerobot/pusht \
    --training.epochs=100 \
    --output_dir=checkpoints/act_pusht_baseline

Step 3: 实验组训练 (我们的数据, PushT任务)
  python lerobot/scripts/train.py \
    --policy.type=act \
    --dataset.repo_id=local/human2vla_pusht \
    --training.epochs=100 \
    --output_dir=checkpoints/act_pusht_ours

Step 4: 对其他任务重复Step 3
  - 修改--dataset.repo_id
  - 修改--output_dir

Step 5: Diffusion Policy同理
  python lerobot/scripts/train.py \
    --policy.type=diffusion \
    --dataset.repo_id=... \
    --training.epochs=200 \
    --output_dir=...

Step 6: 评估
  python lerobot/scripts/eval.py \
    --policy.path=checkpoints/act_pusht_ours/checkpoint_100.pth \
    --env.type=pusht \
    --eval.n_episodes=50

Step 7: 记录所有结果到表E5
```

### 结果记录表

#### 表E5.1: PushT

| 训练数据 | 策略 | Train Loss↓ | Val Loss↓ | Action MSE↓ | Succ%↑ | Smooth↓ |
|----------|------|------------|----------|------------|--------|---------|
| LeRobot标准 | ACT | | | | | |
| LeRobot标准 | Diff.Pol. | | | | | |
| **Ours** | ACT | | | | | |
| **Ours** | Diff.Pol. | | | | | |

#### 表E5.2: 多任务 (ACT)

| 任务 | 数据来源 | Train Loss↓ | Val Loss↓ | Action MSE↓ | Succ%↑ | Smooth↓ |
|------|---------|------------|----------|------------|--------|---------|
| PushT | Ours | | | | | |
| Cup Grasp | Ours | | | | | |
| Pouring | Ours | | | | | |
| Transport | Ours | | | | | |
| Door Open | Ours | | | | | |

#### 表E5.3: 多任务 (Diffusion Policy)

| 任务 | 数据来源 | Train Loss↓ | Val Loss↓ | Action MSE↓ | Succ%↑ | Smooth↓ |
|------|---------|------------|----------|------------|--------|---------|
| PushT | Ours | | | | | |
| Cup Grasp | Ours | | | | | |
| Pouring | Ours | | | | | |
| Transport | Ours | | | | | |

#### 表E5.4: 训练收敛记录

| 任务 | 策略 | Epoch | Train Loss | Val Loss | 备注 |
|------|------|-------|-----------|----------|------|
| PushT | ACT | 10 | | | |
| PushT | ACT | 50 | | | |
| PushT | ACT | 100 | | | |
| PushT | DP | 50 | | | |
| PushT | DP | 100 | | | |
| PushT | DP | 200 | | | |

---

## E6: 消融实验

### 实验目的
量化pipeline中每个组件对下游策略性能的贡献。

### 消融条件 (7组)

| ID | 条件 | Image | State | Language | Smoothing | IK Constraint | Text Align |
|----|------|-------|-------|----------|-----------|---------------|------------|
| A1 | No Language | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| A2 | No Smoothing | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ |
| A3 | No IK Constraints | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| A4 | Image Only | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ |
| A5 | State Only | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ |
| A6 | Image+State | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| A7 | **Full (Ours)** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### 执行步骤

```
Step 1: 为每个消融条件生成对应的数据集变体
  scripts/generate_ablation_data.py --condition A1 --output datasets/ablation/A1/
  ... (对A1-A7重复)

Step 2: 对每个消融条件, 在≥3个任务上训练ACT
  for condition in A1 A2 A3 A4 A5 A6 A7; do
    for task in pusht grasp pour; do
      python lerobot/scripts/train.py \
        --policy.type=act \
        --dataset.path=datasets/ablation/${condition}/${task} \
        --training.epochs=100 \
        --output_dir=checkpoints/ablation/${condition}_${task}
    done
  done

Step 3: 评估
  for condition in A1 A2 A3 A4 A5 A6 A7; do
    for task in pusht grasp pour; do
      python lerobot/scripts/eval.py \
        --policy.path=checkpoints/ablation/${condition}_${task}/checkpoint_100.pth \
        --eval.n_episodes=50 \
        --output results/E6/${condition}_${task}.json
    done
  done

Step 4: 计算ΔSuccess% = Succ%(A7) - Succ%(AX)
Step 5: 每个条件至少3个随机种子, 报告均值±标准差
Step 6: 汇总到表E6
```

### 结果记录表

#### 表E6.1: 消融实验结果 (ACT, 3 tasks × 3 seeds)

| Ablation | PushT Succ% | Grasp Succ% | Pour Succ% | Mean Δ | p-value vs A7 |
|----------|------------|-------------|------------|--------|---------------|
| A1: No Language | | | | | |
| A2: No Smooth | | | | | |
| A3: No IK | | | | | |
| A4: Image Only | | | | | |
| A5: State Only | | | | | |
| A6: Img+State | | | | | |
| **A7: Full** | | | | 0.0 | — |

#### 表E6.2: 各组件贡献排序

| 排名 | 组件 | 平均ΔSucc% | 最重要影响的任务 |
|------|------|-----------|---------------|
| 1 | (预期: Language) | | |
| 2 | (预期: Image) | | |
| 3 | (预期: IK Constraints) | | |
| 4 | (预期: Smoothing) | | |
| 5 | (预期: State) | | |

#### 表E6.3: 种子稳定性

| Condition | Seed 1 | Seed 2 | Seed 3 | Mean±Std |
|-----------|--------|--------|--------|----------|
| A7 (PushT) | | | | |
| A7 (Grasp) | | | | |
| A7 (Pour) | | | | |

---

## 实验执行顺序建议

```
Week 1-2:  E3 (3D骨架 → 基础设施, 不需要MLLM API)
Week 3-4:  E1 (动作分段 → 使用E3的HRNet关键点)
Week 5-6:  E2 (文本对齐 → 需要MLLM API, 使用E1的分段结果)
Week 7-8:  E4 (人机映射 → 使用E3的平滑骨架)
Week 9-10: E5 (策略验证 → 使用前4个实验的最佳配置)
Week 11-12: E6 (消融 → 在E5验证pipeline可行后进行)
```

## 结果汇总主表

论文最终需要填入的主结果表:

| 实验 | 核心指标 | 我们的结果 | SOTA/基线 | 提升 |
|------|---------|-----------|----------|------|
| E1 | Boundary F1@3 (50Salads) | | | |
| E2 | Recall@1 (YouCook2) | | | |
| E3 | MPJPE mm (Human3.6M) | | | |
| E3 | Jerk↓ (vs None) | | N/A | |
| E4 | EE误差 cm (xArm, reach) | | | |
| E4 | IK成功率 % (xArm) | | | |
| E5 | Succ% PushT (ACT, Ours data) | | | |
| E5 | Succ% Grasp (ACT, Ours data) | | | |
| E6 | Language组件贡献 (ΔSucc%) | | N/A | |
| E6 | Image组件贡献 (ΔSucc%) | | N/A | |
