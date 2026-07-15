# K02 STATUS AUDIT — Azure Kinect 支线现状审计

**日期**: 2026-07-15
**审计人**: Claude (azure-kinect 支线负责人)
**分支**: `azure-kinect`
**HEAD**: `e676660` — `fix: resolve temporal jitter, achieve perfect skeleton alignment, and deliver audited K02 datasets`

---

## 一、分支与提交状态

| 项目 | 值 |
|------|-----|
| 当前分支 | `azure-kinect` |
| HEAD commit | `e676660` |
| 领先 main 的提交 | 2 个 (`8fd69ae`, `e676660`) |
| 工作树状态 | 干净（K01 图片文件在 .gitignore 覆盖外的暂存区） |

### Kinect 相关提交

| Commit | 日期 | 说明 | 文件数 |
|--------|------|------|--------|
| `8fd69ae` | Jul 13 | 离线数据榨取与标准化流水线第一阶段 | 8 files (+1116) |
| `e676660` | Jul 13 | 修复时序抖动、完美骨骼对齐、交付审计后 K02 数据集 | 9 files (+1251) |

---

## 二、已有数据资产

### 2.1 K01 数据集 (`K01_reach_grasp_001`)

| 属性 | 值 |
|------|-----|
| 帧数 | 240 |
| 有效骨架帧 | 240 (100%) |
| Body ID | 1（全程无切换） |
| 帧率 | ~30 FPS (33-34ms 间隔) |
| 时长 | ~7.97 秒 |
| 低置信度关节比例 | 42.3% |
| Body ID 切换 | 0 |
| 重复帧 | 0 |
| 丢帧 | 0 |
| NaN/Inf | 0 |

#### 数据文件清单

```
data/azure_kinect/processed/K01/
├── frame_sync.csv           (241 行含表头, 14KB)
├── kinect_skeleton.jsonl    (240 行, 623KB) ← 主交付文件
├── skeleton_2d_raw.jsonl    (240 行, 369KB)
└── skeleton_3d_raw.jsonl    (240 行, 301KB)

data/azure_kinect/reviewed/
└── K01_visual_review.csv    (8 行, 459B)

results/azure_kinect/K01/
├── confidence_by_joint.csv  (33 行, 1.4KB)
├── suspicious_transitions.csv (7 行, 184B)
└── kinect_skeleton_overlay.mp4 (11.5MB)

K01_reach_grasp_001/  (repo 根目录，原始输出)
├── color/                   (240 JPG)
├── depth/                   (240 PNG)
├── frame_sync.csv
├── quality_summary.json
├── KINECT_TO_BODY25_MAPPING.csv  (仅 7 行)
├── skeleton_2d.jsonl
└── skeleton_3d.jsonl
```

### 2.2 已知质量问题

| 问题 | 严重度 | 详情 |
|------|--------|------|
| 低置信度关节比例高 | 🔴 | 42.3% 关节为 LOW (confidence=1) |
| 右臂骨长异常 | 🔴 | 右肩-肘均值 6.6cm（应为 ~25cm），变异 91.6% |
| 右前臂骨长异常 | 🔴 | 右肘-腕均值 56.5cm（应为 ~25cm），变异 20.5% |
| 骨架叠加视觉偏移 | 🔴 | 人工复核发现系统性几何偏移 |
| 2D 坐标非 SDK 原生 | 🔴 | 由 3D + 硬编码内参投影计算，非独立测量 |
| 硬编码相机内参 | 🔴 | fx=912, fy=911, cx=956, cy=545，非设备标定值 |
| 时间戳完全一致 | 🟡 | 所有帧 color_ts == depth_ts，需验证硬件同步 |
| 帧间时间步长不均 | 🟡 | 33ms 和 34ms 交替（160+79 帧） |

---

## 三、已有脚本清单

| 脚本 | 状态 | 主要问题 |
|------|------|----------|
| `extract_joints.cpp` | ⚠️ 可用但需修复 | 硬编码路径 `/home/lcy/...`；未提取相机标定内参 |
| `build_dataset.py` | ⚠️ 可用但需修复 | 硬编码路径和相机内参；2D 坐标是投影计算值而非 SDK 原生 |
| `merge_kinect_skeleton.py` | 🔴 需重写 | 使用 `zip()` 静默截断；未做显式 frame_index 匹配 |
| `validate_kinect_export.py` | ⚠️ 部分可用 | 硬编码路径；仅做基本断言；缺少同步时间戳验证 |
| `analyze_joint_confidence.py` | ⚠️ 需改进 | 置信度等级映射错误；低置信度原因自动编造而非观察 |
| `render_kinect_overlay.py` | ⚠️ 可用 | 硬编码路径；依赖 `os.path.expanduser` |
| `make_verification_video.py` | ⚠️ 可用 | 用于 ROS 实时录制场景，非当前 K01 离线流程 |

---

## 四、BODY_25 映射审计

### 4.1 当前状态：🔴 严重不完整

`context/KINECT_TO_BODY25_MAPPING.csv` 仅含 **7 行**（应有 25 行）。

已映射：
| OpenPose ID | Joint | Kinect Joint | Type | 备注 |
|-------------|-------|-------------|------|------|
| 0 | Nose | NOSE | exact | 正确 |
| 1 | Neck | NECK | exact | 正确 |
| 2 | RShoulder | SHOULDER_RIGHT | exact | 正确 |
| 3 | RElbow | ELBOW_RIGHT | exact | 正确 |
| 4 | RWrist | WRIST_RIGHT | exact | 正确 |
| 5 | LShoulder | SHOULDER_LEFT | exact | 正确 |
| 6 | LElbow | ELBOW_LEFT | exact | 正确 |
| 7 | LWrist | WRIST_LEFT | exact | 正确 |
| 8 | MidHip | PELVIS | approximate | 正确 |
| 9 | RHip | HIP_RIGHT | exact | 正确 |
| 10 | RKnee | KNEE_RIGHT | exact | 正确 |
| 11 | RAnkle | ANKLE_RIGHT | exact | 正确 |
| 12 | LHip | HIP_LEFT | exact | 正确 |
| 13 | LKnee | KNEE_LEFT | exact | 正确 |
| 14 | LAnkle | ANKLE_LEFT | exact | 正确 |
| 15 | REye | EYE_RIGHT | exact | 正确 |
| 16 | LEye | EYE_LEFT | exact | 正确 |
| 17 | REar | EAR_RIGHT | exact | 正确 |
| 18 | LEar | EAR_LEFT | exact | 正确 |
| 19 | LBigToe | FOOT_LEFT | approximate | 使用足部中心近似 |
| 20 | LSmallToe | UNAVAILABLE | unavailable | 传感器视场外 |
| 21 | LHeel | UNAVAILABLE | unavailable | — |
| 22 | RBigToe | FOOT_RIGHT | approximate | — |
| 23 | RSmallToe | UNAVAILABLE | unavailable | — |
| 24 | RHeel | UNAVAILABLE | unavailable | — |

**✅ 实际已完整：** `context/KINECT_TO_BODY25_MAPPING.csv` 已包含全部 25 个 BODY_25 关节！
（审计时重新读取发现文件有 27 行含表头，但之前的 Read 显示有 26 行数据行... 让我再确认一下）

**更正：** 重新检查确认 `context/KINECT_TO_BODY25_MAPPING.csv` 有完整的 25 行映射（ID 0-24 全部有一行）。mapping_type 分布：
- exact: 18 关节
- approximate: 3 关节 (MidHip→PELVIS, LBigToe→FOOT_LEFT, RBigToe→FOOT_RIGHT)
- unavailable: 3 关节 (LSmallToe, LHeel, RSmallToe, RHeel=4个)
- derived: 1 关节 (Nose→NOSE, 但注释说从头部中心计算)

**⚠️ 问题：** `K01_reach_grasp_001/KINECT_TO_BODY25_MAPPING.csv` 仍只有 7 行（陈旧副本）。

### 4.2 映射质量问题

1. **Nose 映射为 "NOSB"**：在 K01 副本中写为 "NOSB"（应为 "NOSE"），已在 context 版本修正
2. **REye/LEye 标为 unavailable**：在 K01 副本中标为 unavailable，但在 context 版本中为 exact — context 版本正确
3. **MidHip → PELVIS**：标记为 approximate，这是合理的（BODY_25 MidHip 与 Kinect PELVIS 位置接近但不完全相同）
4. **脚趾/脚跟**：大部分标为 unavailable 或 approximate，因为 Kinect 只跟踪到 FOOT 级别

---

## 五、关键技术问题

### 5.1 🔴 CRITICAL: zip() 静默截断

`merge_kinect_skeleton.py:25`:
```python
for idx, (line_2d, line_3d) in enumerate(zip(f2d, f3d)):
```

**风险：** 如果 `skeleton_2d_raw.jsonl` 和 `skeleton_3d_raw.jsonl` 行数不同，`zip()` 会静默截断到较短的文件，导致数据丢失而无任何警告。

**所需修复：** 必须先验证两文件行数相等，再用显式 frame_index 或 timestamp 匹配。

### 5.2 🔴 CRITICAL: 硬编码相机内参

`build_dataset.py:22`:
```python
fx, fy, cx, cy = 912.0, 911.0, 956.0, 545.0
```

**风险：** 这些值不是从 MKV 文件的 `k4a_playback_get_calibration()` 获取的实际设备标定参数。Azure Kinect 每台设备的标定参数不同。使用错误内参导致 2D 投影系统性偏移。

**所需修复：** 从 C++ 代码提取实际标定参数（`k4a_calibration_t` 结构中的 `color_camera_calibration.intrinsics.parameters`），写入 JSON 文件，Python 端读取实际参数。

### 5.3 🔴 CRITICAL: 2D 坐标非独立测量

当前数据流：
```
C++ 提取 3D 关节 → build_dataset.py 用硬编码内参投影 → 得到 2D 坐标
```

这意味着 2D 坐标完全依赖于 3D 坐标，不能作为独立的二维参考。真正的验证需要：
- Kinect SDK 的 `k4a_calibration_3d_to_2d()` 函数进行畸变校正后的投影
- 或独立运行 2D 姿态估计器（如 OpenPose）在 Kinect RGB 图像上

**所需修复：** 分离两条路径：A) SDK 原生投影（含畸变校正），B) 简单针孔投影。比较两者差异。

### 5.4 🔴 CRITICAL: 硬编码绝对路径

| 文件 | 硬编码路径 |
|------|-----------|
| `extract_joints.cpp:19-20` | `/home/lcy/data/azure_kinect/...` |
| `build_dataset.py:6` | `os.path.expanduser('~/data/azure_kinect/...')` |
| `validate_kinect_export.py:5-6` | `data/azure_kinect/processed/K01/...` |
| `analyze_joint_confidence.py:8` | `data/azure_kinect/processed/K01/...` |
| `render_kinect_overlay.py:9-11` | `os.path.expanduser('~/data/azure_kinect')` |
| `make_verification_video.py:22` | `os.path.expanduser('~/data/azure_kinect')` |

**所需修复：** 全部改为命令行参数或配置文件传入。

### 5.5 🟡 HIGH: 置信度等级映射错误

`analyze_joint_confidence.py:45`:
```python
# 记录每个关节的置信度 (0=NONE, 1=LOW, 2=HIGH)
```

**实际 Azure Kinect SDK 等级：**
- `K4ABT_JOINT_CONFIDENCE_NONE = 0`
- `K4ABT_JOINT_CONFIDENCE_LOW = 1`
- `K4ABT_JOINT_CONFIDENCE_MEDIUM = 2`
- `K4ABT_JOINT_CONFIDENCE_HIGH = 3`

脚本将 level 2 视为 "HIGH"，但实际 level 2 是 "MEDIUM"。当前 K01 数据中无 level 3 (HIGH) 关节。

### 5.6 🟡 HIGH: 低置信度原因自动编造

`analyze_joint_confidence.py:67-70`:
```python
if "WRIST" in name or "THUMB" in name or "FOOT" in name or "EYE" in name:
    reason = "Terminal joint occlusion or FOV edge drop"
else:
    reason = "Stable trunk region"
```

这基于关节名称模式而非实际观察。例如 ELBOW_LEFT 标记为 "Stable trunk region" 但实际平均置信度仅 1.00 (LOW)。

### 5.7 🟡 HIGH: 缺少必需字段

当前 `kinect_skeleton.jsonl` 字段：
- `frame_index`, `original_frame_number`, `timestamp_usec`, `body_id`
- `joints_3d_camera`, `joints_2d_color`, `joint_confidence`

**缺少的必需字段：**
- `video_id`
- `source_frame_index`
- `color_timestamp_usec`
- `depth_timestamp_usec`
- `color_path`
- `depth_path`
- `reference_valid`
- `reference_quality`
- `invalid_reason`
- `observation_status`
- `joint_name` 列表（当前仅靠数组位置隐式定义）

### 5.8 🟡 HIGH: 视觉复核发现系统性偏移

`K01_visual_review.csv` 标注：**"Systemic geometric offset (projection error) of skeleton points, FAILED"**

这表明叠加在 RGB 图像上的骨骼与人体实际位置存在可观察的偏移，最可能由错误的相机内参导致。

---

## 六、数据质量深度分析

### 6.1 置信度分布

| 等级 | 数量 | 比例 |
|------|------|------|
| LOW (1) | 3,250 | 42.3% |
| MEDIUM (2) | 4,430 | 57.7% |
| HIGH (3) | 0 | 0% |
| NONE (0) | 0 | 0% |

**关键关节置信度：**

| 关节 | 平均置信度 | 评估 |
|------|-----------|------|
| PELVIS | 2.00 | 稳定 |
| NECK | 2.00 | 稳定 |
| SHOULDER_RIGHT | 1.00 | 🔴 全低 |
| ELBOW_RIGHT | 1.00 | 🔴 全低 |
| WRIST_RIGHT | 2.00 | 可接受 |
| SHOULDER_LEFT | 2.00 | 稳定 |
| ELBOW_LEFT | 1.00 | 🔴 全低 |
| WRIST_LEFT | 1.00 | 🔴 全低 |

### 6.2 骨长稳定性

| 骨骼段 | 均值 (m) | 标准差 (m) | 变异 | 评估 |
|--------|----------|-----------|------|------|
| R Shoulder-Elbow | 0.066 | 0.017 | 91.6% | 🔴 严重异常 |
| R Elbow-Wrist | 0.565 | 0.031 | 20.5% | 🔴 明显偏长 |
| L Shoulder-Elbow | 0.248 | 0.011 | 9.4% | ✅ 合理 |
| L Elbow-Wrist | 0.208 | 0.009 | 8.8% | ✅ 合理 |

**结论：** 右侧手臂追踪质量极差。右侧肩-肘骨长仅 6.6cm（正常成人约 25-30cm），且变异达 91.6%。右侧前臂长 56.5cm 明显超出正常范围（~25cm）。左侧手臂数据合理。

### 6.3 时序突变

| 帧对 | 平均跃变 (m) | 最大跃变 (m) | 评估 |
|------|-------------|-------------|------|
| 35→36 | 0.020 | 0.211 | ⚠️ 21cm 单关节跳跃 |
| 39→40 | 0.051 | 0.197 | ⚠️ 20cm 单关节跳跃 |
| 48→49 | 0.096 | 0.299 | 🔴 30cm 单关节跳跃 |
| 62→63 | 0.020 | 0.126 | ⚠️ |
| 103→104 | 0.030 | 0.126 | ⚠️ |
| 204→205 | 0.017 | 0.146 | ⚠️ |

较大的帧间跳跃（20-30cm）可能是真实快速运动或跟踪丢失后恢复导致。

---

## 七、完成度矩阵

| 组件 | 状态 | 达标 | 备注 |
|------|------|------|------|
| RGB 帧提取 | ✅ 完成 | ✅ | 240 帧 JPG |
| Depth 帧提取 | ✅ 完成 | ✅ | 240 帧 PNG |
| 3D 骨架提取 | ✅ 完成 | ⚠️ | 质量偏低 |
| 2D 骨架提取 | ⚠️ | ❌ | 非 SDK 原生，由投影计算 |
| frame_sync.csv | ✅ 完成 | ⚠️ | color_ts==depth_ts 需验证 |
| 骨架合并 | ⚠️ | ❌ | 使用 zip() 静默截断 |
| 验证脚本 | ⚠️ | ❌ | 硬编码路径；缺少多项检查 |
| 置信度分析 | ⚠️ | ❌ | 等级映射错误；原因编造 |
| BODY_25 映射 | ✅ 完成 | ⚠️ | 含 25 行但部分映射需审核 |
| 可视化视频 | ✅ 完成 | ⚠️ | 存在系统性几何偏移 |
| 人工复核 | ✅ 完成 | ⚠️ | 发现 FAIL 项但未修复 |
| SHA-256 校验 | ❌ 缺失 | ❌ | 无 |
| 时间同步验证 | ❌ 缺失 | ❌ | 无独立验证 |
| 相机标定提取 | ❌ 缺失 | ❌ | 使用硬编码值 |
| 2D/3D 重投影验证 | ❌ 缺失 | ❌ | 2D 由投影生成故循环验证 |
| 学习文档 | ❌ 缺失 | ❌ | `docs/learning/` 为空 |
| K02 验收标准 | ❌ 缺失 | ❌ | 无 |
| 交换 Schema | ❌ 缺失 | ❌ | 无 |

---

## 八、主要风险

| 排名 | 风险 | 严重度 | 影响 |
|------|------|--------|------|
| 1 | 右臂 3D 数据不可靠 | 🔴 CRITICAL | 无法作为右臂参考轨迹 |
| 2 | 相机内参错误 | 🔴 CRITICAL | 所有 2D 投影系统性偏移 |
| 3 | 42% 关节低置信度 | 🔴 CRITICAL | 参考数据自身质量受限 |
| 4 | 2D 非独立测量 | 🔴 CRITICAL | 无法验证重投影精度 |
| 5 | K01 与 E001 非同次操作 | 🟡 HIGH | 不能直接逐帧对比 |
| 6 | 无 KVAL 验证数据 | 🟡 HIGH | 缺少独立验证集 |
| 7 | 所有脚本硬编码路径 | 🟡 HIGH | 不可移植、不可复现 |
| 8 | 单视频单人物 | 🟡 MEDIUM | 泛化性未知 |

---

## 九、K02 剩余最小修正任务

详见 `tasks/K02_ACCEPTANCE_CRITERIA.md`。概要：

1. **K02A-R1**: 修复 zip() 合并逻辑，改为显式 frame_index 匹配
2. **K02A-R2**: 从 MKV 提取实际相机标定参数
3. **K02A-R3**: 使用实际标定重新计算 2D 投影，与硬编码版本对比
4. **K02A-R4**: 添加缺失字段（video_id, color_ts, depth_ts, reference_valid 等）
5. **K02A-R5**: 修复所有硬编码路径
6. **K02A-R6**: 生成 SHA-256 清单
7. **K02A-R7**: 同步时间戳独立验证
8. **K02A-R8**: 完善置信度分析与质量掩码
9. **K02A-R9**: 创建学习文档
10. **K02A-R10**: 创建交换 Schema 草案

---

## 十、K03 开始前必须满足的条件

1. ✅ K02 全部修正任务完成并通过验收
2. ✅ 相机标定参数已从设备正确提取
3. ✅ 2D 投影使用正确内参，重投影误差已验证
4. ✅ 质量掩码已建立（低置信度/遮挡区间已标记）
5. ✅ 所有脚本不再使用硬编码路径
6. ✅ KVAL 录制协议已编写并审查
7. ✅ 至少有 1 段独立 KVAL 数据已录制并验证

---

## 十一、需要人工确认的事项

1. **K01 右臂 3D 数据不可靠** — 是否仍可使用 K01 作为参考（仅使用左臂和躯干关节），还是需要重新采集？
2. **实际相机标定文件** — 原始 MKV 文件在哪里？需要提取 `k4a_playback_get_calibration()` 的结果。
3. **K01 与主线 E001 的关系** — K01 是独立的 reach_grasp 动作，与 E001 不是同一次操作。确认仅用于阶段统计对比（非逐帧对比）？
4. **新 KVAL 录制** — 是否有 Azure Kinect 设备可用？何时可以进行 K03 录制？
5. **数据目录重组** — 是否可以将 `K01_reach_grasp_001/` 从 repo 根目录移入 `data/azure_kinect/raw/` 统一管理？
