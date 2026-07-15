# K02 — Azure Kinect 数据管道概览

**学习目标**: 理解 Azure Kinect 离线数据提取、标准化、验证的完整流程
**前置知识**: 基本 Python, 针孔相机模型, JSON/CSV 数据处理
**配套任务**: K02_STATUS_AUDIT.md, K02_ACCEPTANCE_CRITERIA.md

---

## 1. Theory — 关键原理

### 1.1 Azure Kinect DK 数据流

```
MKV 录制文件
  ├── Color 流 (1920×1080 @ 30fps, BGRA)
  ├── Depth 流 (640×576 @ 30fps, 16-bit mm)
  ├── IMU 数据
  └── 设备标定 (内参 + 外参)
```

### 1.2 人体骨骼追踪 (Body Tracking SDK)

Azure Kinect Body Tracking SDK (`k4abt`) 从深度图像估计 32 个关节的三维位置。

**32 关节列表** (按 SDK 索引):
```
0:  PELVIS           11: WRIST_RIGHT       22: EYE_LEFT
1:  SPINE_NAVAL      12: HIP_LEFT          23: EAR_LEFT
2:  SPINE_CHEST      13: KNEE_LEFT         24: EYE_RIGHT
3:  NECK             14: ANKLE_LEFT        25: EAR_RIGHT
4:  CLAVICLE_LEFT    15: FOOT_LEFT         26: WRIST_THUMB_LEFT (Hand tip)
5:  SHOULDER_LEFT    16: HIP_RIGHT         27: BICEPS_LEFT (Arm)
6:  ELBOW_LEFT       17: KNEE_RIGHT        28: WRIST_THUMB_RIGHT (Hand tip)
7:  WRIST_LEFT       18: ANKLE_RIGHT       29: BICEPS_RIGHT (Arm)
8:  CLAVICLE_RIGHT   19: FOOT_RIGHT        30: BACK_LEFT
9:  SHOULDER_RIGHT   20: HEAD              31: BACK_RIGHT
10: ELBOW_RIGHT      21: NOSE
```

**置信度等级** (来自 SDK enum `k4abt_joint_confidence_level_t`):

| 值 | 名称 | 含义 |
|----|------|------|
| 0 | NONE | 关节完全不可见/不可跟踪 |
| 1 | LOW | 关节推断或深度数据质量低 |
| 2 | MEDIUM | 关节基于中等质量深度数据 |
| 3 | HIGH | 关节基于高质量深度数据 |

**坐标系统** (右手坐标系):
- **X**: 向右 (从相机视角)
- **Y**: 向下
- **Z**: 向前 (深度方向)
- **单位**: SDK 原始为毫米，本项目除以 1000 转为米

### 1.3 针孔相机投影模型

将三维相机空间点 (X, Y, Z) 投影到二维图像平面 (u, v):

```
u = fx * (X / Z) + cx
v = fy * (Y / Z) + cy
```

其中:
- **fx, fy**: 焦距 (像素单位)，将角度转换为像素
- **cx, cy**: 主点 (通常是图像中心)
- **(X/Z, Y/Z)**: 归一化图像坐标 (无单位)

**代码对应** (build_dataset.py):
```python
u = (x * fx) / z + cx  # x → 水平像素 u
v = (y * fy) / z + cy  # y → 垂直像素 v
```

**⚠️ 常见错误**: 如果使用错误的 fx/fy/cx/cy，投影点会系统性地偏离真实位置。Azure Kinect 每台设备的标定参数不同，必须从 MKV 文件中提取 `k4a_playback_get_calibration()` 的结果。

### 1.4 完整畸变模型

实际相机镜头存在畸变，简单针孔模型不精确。Azure Kinect 使用 Brown-Conrady 畸变模型:

```
x' = X / Z
y' = Y / Z
r² = x'² + y'²

x'' = x' * (1 + k1*r² + k2*r⁴ + k3*r⁶ + k4*r⁸ + k5*r¹⁰ + k6*r¹²)
      + 2*p1*x'*y' + p2*(r² + 2*x'²)
y'' = y' * (1 + k1*r² + k2*r⁴ + k3*r⁶ + k4*r⁸ + k5*r¹⁰ + k6*r¹²)
      + p1*(r² + 2*y'²) + 2*p2*x'*y'

u = fx * x'' + cx
v = fy * y'' + cy
```

其中 k1-k6 为径向畸变系数，p1-p2 为切向畸变系数。

### 1.5 骨长约束

人体骨骼段长度应当恒定 (刚性假设):

```
Shoulder-Elbow length = ||P_shoulder - P_elbow||₂
```

标准差/均值比 > 10% 表示跟踪质量差。

### 1.6 BODY_25 vs Kinect 32 映射

BODY_25 是 OpenPose 的 25 关节格式。Kinect SDK 输出 32 个关节。

**映射类型**:
- `exact`: 语义等价 (如 Kinect NECK → BODY_25 Neck)
- `approximate`: 位置接近但不完全相同 (如 Kinect PELVIS → BODY_25 MidHip)
- `derived`: 从其他关节计算 (如从 HEAD 中心推导 Nose)
- `unavailable`: Kinect 不跟踪该关节 (如脚尖、脚跟)

**关键教学点**: 不能伪造 unavailable 关节的坐标。这些关节在 BODY_25 中应标记为 (0, 0, 0) 置信度 0。

---

## 2. Hypothesis — 实验前预期

### 对于 K01 数据:
1. **预期**: 左臂 3D 数据应优于右臂 (右手动作可能导致更多自遮挡)
   - **验证**: 左臂骨长变异 9%，右臂 91% — ✅ 预期成立
2. **预期**: 躯干关节 (PELVIS, NECK) 置信度应高于末梢关节 (WRIST, ANKLE)
   - **验证**: PELVIS/NECK 平均置信度 2.0，ELBOW/WRIST 多为 1.0 — ✅ 成立
3. **预期**: 快速运动帧的关节跳跃应大于慢速帧
   - **待验证**: 需要动作阶段标注

### 可能导致失败的因素:
1. Kinect 在深度边缘处跟踪丢失
2. 右手靠近身体时与躯干混淆
3. 反光表面 (如桌面) 导致深度空洞
4. 人体离开 FoV 边缘时跟踪重置
5. 宽松衣物导致骨架估计偏移

---

## 3. Implementation — 数据流

### 3.1 当前管道架构

```
Phase 1 (C++): extract_joints.cpp
  Input:  <video_id>.mkv
  Output: color/*.jpg, depth/*.png, frame_sync.csv, skeleton_3d_raw.txt
  Tools:  K4A SDK + K4ABT SDK + OpenCV

Phase 2 (Python): build_dataset.py
  Input:  skeleton_3d_raw.txt
  Output: skeleton_2d.jsonl, skeleton_3d.jsonl, quality_summary.json
  Action: 3D → 2D 投影 (当前使用硬编码内参 ⚠️)

Phase 3 (Python): merge_kinect_skeleton.py
  Input:  skeleton_2d_raw.jsonl, skeleton_3d_raw.jsonl
  Output: kinect_skeleton.jsonl
  Action: 合并 2D/3D 为统一记录

Phase 4 (Python): validate_kinect_export.py
  Input:  kinect_skeleton.jsonl, frame_sync.csv
  Action: 帧号连续性、时间戳单调性、关节数量验证

Phase 5 (Python): analyze_joint_confidence.py
  Input:  kinect_skeleton.jsonl
  Output: confidence_by_joint.csv, suspicious_transitions.csv

Phase 6 (Python): render_kinect_overlay.py
  Input:  kinect_skeleton.jsonl, color/*.jpg
  Output: kinect_skeleton_overlay.mp4
```

### 3.2 关键参数含义

| 参数 | 典型值 | 含义 |
|------|--------|------|
| fx, fy | ~900-1100 | 焦距 (像素)，取决于设备和分辨率 |
| cx | ~960 | 主点 x (≈ 1920/2 for 1080p) |
| cy | ~540 | 主点 y (≈ 1080/2 for 1080p) |
| k1-k6 | ~0.1-0.5 | 径向畸变，影响图像边缘 |
| color_ts | ~200000-8000000 | 彩色帧时间戳 (微秒) |

---

## 4. Experiment — 数据验证

### 4.1 单条数据完整处理示例

以 K01 第 1 帧为例:

**输入 (从 MKV 提取)**:
- 彩色帧: `frame_1.jpg` (1920×1080)
- 深度帧: `frame_1.png` (640×576, 16-bit)
- 3D 关节 (NECK): position = (0.436, -0.193, 0.841) 米
- 置信度: NECK = 2 (MEDIUM)

**处理**:
1. 3D → 2D 投影: u = fx*X/Z + cx = 912*0.436/0.841 + 956 = 1429 px
2. 置信度审查: MEDIUM → reference_quality = "medium"
3. 骨长检查: NECK→SHOULDER_RIGHT = sqrt((0.436-0.296)² + (-0.193-0.380)² + (0.841-0.534)²)

**输出 (kinect_skeleton.jsonl)**:
```json
{
  "frame_index": 0,
  "original_frame_number": 1,
  "timestamp_usec": 201455,
  "body_id": 1,
  "joints_3d_camera": [[0.393, 0.245, 0.845], ...],
  "joints_2d_color": [[1380.5, 809.1], ...],
  "joint_confidence": [2, 2, 2, ...]
}
```

### 4.2 数据泄漏防护

- 验证数据 (KVAL) 与开发数据 (K01) 必须分离
- 相机内参从设备标定获取，不拟合到验证数据
- 质量掩码规则在查看 KVAL 数据前冻结
- 评价器用模拟数据+已知扰动验证后再用于真实数据

---

## 5. Interpretation — 结果解释

### 可以支持的结论:
1. "Kinect 参考数据在躯干和左臂关节上提供可靠的 3D 测量"
2. "右侧手臂在操作任务中存在系统性跟踪困难"
3. "约 42% 的关节置信度为 LOW，主要影响肘部和腕部"
4. "骨长变异可作为跟踪质量的自动检测指标"

### 不能过度延伸的结论:
1. ❌ "Kinect 3D 数据是真实无误的 ground truth"
2. ❌ "2D 单目方法在所有条件下都不如 3D 方法"
3. ❌ "K01 数据可以直接与主线 E001 逐帧对比" (非同次操作)

---

## 6. Paper Writing — 论文表述

### 可写入方法描述:
> We use Azure Kinect DK as an independent 3D reference measurement system. The Body Tracking SDK provides 32-joint 3D skeleton estimates at 30 Hz, with per-joint confidence levels (NONE/LOW/MEDIUM/HIGH). We validate the reference data through bone-length stability analysis, temporal consistency checks, and reprojection verification against RGB frames. Joints with low confidence or bone-length anomalies are flagged and reported separately, ensuring that reference quality is transparently documented rather than assumed.

### 实验结果表达:
> Kinect 3D reference measurements achieved MEDIUM or higher confidence for 57.7% of all joints, with trunk joints (pelvis, spine, neck) consistently at MEDIUM confidence. Limb extremities, particularly elbows and wrists on the active arm, showed higher rates of LOW confidence (42.3% overall), reflecting inherent limitations of single-view depth-based tracking during manipulation tasks.

### 局限性声明:
> The Azure Kinect reference is subject to its own error sources: depth noise, joint estimation uncertainty, self-occlusion during manipulation, and field-of-view constraints. We therefore treat Kinect measurements as pseudo-ground-truth rather than absolute ground truth, and we report reference quality metrics alongside all comparisons.

---

## 7. 常见错误

| 错误 | 后果 | 纠正 |
|------|------|------|
| 使用硬编码内参 | 所有 2D 投影系统性偏移 | 从 MKV 提取实际标定 |
| zip() 合并不同长度文件 | 静默数据丢失 | 显式按 frame_index 匹配合并 |
| 将 SDK 置信度 2 当作 HIGH | 高估参考质量 | 正确映射: 2=MEDIUM, 3=HIGH |
| 使用 (0,0,0) 坐标表示缺失 | 与原点混淆 | 缺失点用 NaN 或单独标记 |
| K01 与主线同日对比 | 不同次操作不可逐帧匹配 | 只用阶段统计对比 |

---

## 8. 运行与复现步骤

```bash
# 1. 编译 C++ 提取器
cd tools/azure_kinect_extractor && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)

# 2. 运行提取 (路径通过命令行参数传入)
./extract_joints --mkv /path/to/video.mkv --output /path/to/output/ --video-id KVAL001

# 3. 运行 Python 管道
python scripts/azure_kinect/build_dataset.py \
  --input-dir /path/to/output/KVAL001 \
  --calibration /path/to/output/KVAL001/calibration.json \
  --video-id KVAL001

python scripts/azure_kinect/merge_kinect_skeleton.py \
  --2d-input data/azure_kinect/processed/KVAL001/skeleton_2d_raw.jsonl \
  --3d-input data/azure_kinect/processed/KVAL001/skeleton_3d_raw.jsonl \
  --output data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
  --video-id KVAL001

python scripts/azure_kinect/validate_kinect_export.py \
  --skeleton data/azure_kinect/processed/KVAL001/kinect_skeleton.jsonl \
  --sync data/azure_kinect/processed/KVAL001/frame_sync.csv
```

---

## 9. 自测问题

1. **Q**: 为什么 `zip()` 合并 2D 和 3D 数据是危险的？
   **A**: 因为 zip 在任一迭代器耗尽时静默停止，不会警告行数不一致。如果 3D 文件有 240 行但 2D 文件只有 239 行，最后一帧的 3D 数据会被静默丢弃。

2. **Q**: fx=912 和 fx=1060 哪个更可能是 Azure Kinect 1080p 彩色相机的正确焦距？
   **A**: 需要从设备标定确认。Azure Kinect 彩色相机在 1920×1080 分辨率下的典型 fx 约 1050-1100。912 偏低。

3. **Q**: 如果某关节的 3D 坐标 Z=0，投影公式会发生什么？
   **A**: 除以零错误。在代码中必须检查 `if z == 0` 并处理为无效点。

4. **Q**: Kinect SDK 置信度 2 应该被解释为什么级别？
   **A**: MEDIUM（中等），不是 HIGH。HIGH 是 3。

5. **Q**: 为什么骨长分析很重要？
   **A**: 真实的人体骨骼段长度恒定。如果跟踪的骨长在不同帧之间剧烈变化，说明跟踪质量差，该段不适合作为参考。

6. **Q**: K01 的右臂数据能否作为 3D 参考？
   **A**: 不建议。右肩-肘骨长仅 6.6cm（正常 ~25cm）且变异 91.6%，表明跟踪严重失准。

7. **Q**: 如何区分 reference_valid=false 和 observation_status=occluded？
   **A**: `reference_valid=false` 表示该关节坐标不可靠（任何原因）；`observation_status=occluded` 表示具体原因是遮挡。一个关节可能被遮挡但仍有合理的推断位置（valid=true, status=occluded），也可能是可见但跟踪失败（valid=false, status=visible）。

8. **Q**: 为什么 color_ts 和 depth_ts 完全相同？
   **A**: Azure Kinect 硬件同步彩色和深度传感器。如果 MKV 录制模式为 `K4A_RECORD_MODE_COLOR_DEPTH_SYNCHRONIZED`，每对 color+depth 帧共享同一时间戳。

9. **Q**: 什么是 "pseudo-ground-truth" 的准确定义？
   **A**: 比纯自动方法更准确但仍有自身误差的参考测量。Kinect 3D 骨架比单目 2D 方法包含更多空间信息，但受到深度噪声、关节估计误差和遮挡的影响。

10. **Q**: 2D 投影验证中，为什么要同时报告 pinhole 和 calibrated 两种投影的误差？
    **A**: Pinhole 投影忽略镜头畸变，在图像边缘误差较大。如果两种投影结果差异很大，说明畸变显著，简单针孔模型不够准确。这帮助诊断投影误差的来源。
