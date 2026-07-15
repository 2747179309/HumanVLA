# K02 验收标准 — Kinect 标准化与同步审计

**创建日期**: 2026-07-15
**依赖**: K02_STATUS_AUDIT.md
**状态**: K02 部分完成，以下为完成 K02 所需的修正任务

---

## K02 总体目标

建立 Azure Kinect 数据的标准化输入格式、同步验证、关节映射和参考有效性评估体系。

---

## 子任务与验收标准

### K02A-R1: 修复骨架合并逻辑

**当前问题**: `merge_kinect_skeleton.py` 使用 `zip()` 按行号静默合并，行数不一致时截断无警告。

**要求**:
- [ ] 先验证 2D 和 3D 文件记录数相等
- [ ] 按 `frame_index` 或 `timestamp_usec` 显式匹配
- [ ] 不匹配时报告具体差异（哪些帧仅在 2D 或仅在 3D 中存在）
- [ ] 任一硬性条件不满足时返回非 0 退出码

**验收**:
```bash
# 测试：创建不匹配的输入文件，脚本应报错退出
python scripts/azure_kinect/merge_kinect_skeleton.py --2d ... --3d ... --output ...
# 预期：非0退出码 + 清晰的错误消息
```

---

### K02A-R2: 提取实际相机标定参数

**当前问题**: `build_dataset.py` 使用硬编码 `fx=912, fy=911, cx=956, cy=545`。

**要求**:
- [ ] C++ 代码从 `k4a_playback_get_calibration()` 提取标定参数
- [ ] 输出 `calibration.json` 包含:
  - `color_intrinsics`: fx, fy, cx, cy, k1, k2, k3, k4, k5, k6, p1, p2
  - `depth_intrinsics`: 同上
  - `color_resolution`: width, height
  - `depth_resolution`: width, height
  - `extrinsics_depth_to_color`: rotation, translation
- [ ] Python 脚本从 `calibration.json` 读取参数，不接受硬编码回退

**验收**:
```bash
python -c "import json; c=json.load(open('calibration.json')); assert 'color_intrinsics' in c; print('fx={}, fy={}'.format(c['color_intrinsics']['fx'], c['color_intrinsics']['fy']))"
```

---

### K02A-R3: 使用正确标定重新投影并对比

**要求**:
- [ ] 使用实际标定参数（含畸变校正）计算 2D 投影
- [ ] 保存两套 2D 坐标：
  - `joints_2d_color_pinhole`: 简单针孔投影（用于对比）
  - `joints_2d_color_calibrated`: 完整畸变模型投影（作为参考）
- [ ] 报告两种投影之间的差异统计
- [ ] 将完整畸变模型投影作为最终的 `joints_2d_color`

**验收**:
- [ ] 输出 `results/azure_kinect/K01/reprojection_comparison.csv`
- [ ] 报告包含 pinhole vs calibrated 的 MAE, RMSE, max error

---

### K02A-R4: 补全标准化字段

**当前缺失字段**:
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

**要求**:
- [ ] 每条 JSONL 记录包含上述全部字段
- [ ] `video_id` 从配置或命令行参数传入
- [ ] `source_frame_index` 保留原始帧号
- [ ] `color_timestamp_usec` 和 `depth_timestamp_usec` 从 frame_sync.csv 合并
- [ ] `reference_valid`: 基于 confidence 和骨长稳定性判定
- [ ] `reference_quality`: "high" (conf≥2, bone_ok), "medium" (conf=1, bone_ok), "low" (conf≤1, bone_bad)
- [ ] `invalid_reason`: 枚举值 (low_confidence, bone_length_anomaly, occlusion, tracking_failure, fov_edge)
- [ ] `observation_status`: "visible", "occluded", "out_of_fov", "uncertain"

**验收**:
```bash
python scripts/azure_kinect/validate_kinect_export.py --input data/azure_kinect/processed/K01/kinect_skeleton.jsonl
# 应检查所有必需字段存在且类型正确
```

---

### K02A-R5: 消除所有硬编码路径

**要求**:
- [ ] 所有脚本的输入/输出路径通过 `argparse` 传入
- [ ] 不接受 `os.path.expanduser()` 或绝对路径硬编码
- [ ] 默认值仅使用相对于项目根目录的路径
- [ ] 每个脚本支持 `--help` 输出完整参数说明

**影响文件**:
- `extract_joints.cpp`
- `build_dataset.py`
- `merge_kinect_skeleton.py`
- `validate_kinect_export.py`
- `analyze_joint_confidence.py`
- `render_kinect_overlay.py`
- `make_verification_video.py`

---

### K02A-R6: 文件完整性校验

**要求**:
- [ ] 为每个原始输出文件生成 SHA-256 清单
- [ ] 清单文件保存在 `data/azure_kinect/processed/K01/file_manifest.json`
- [ ] 验证脚本可读取清单并校验所有文件完整性
- [ ] 原始 MKV 文件 SHA-256 必须记录

---

### K02A-R7: 时间同步独立验证

**当前问题**: 所有帧 `color_ts == depth_ts`，需验证这是硬件同步还是仅记录了 color_ts。

**要求**:
- [ ] 验证报告说明 RGB 和 depth 时间戳来源
- [ ] 如果硬件同步，记录同步机制
- [ ] 计算并报告：
  - 帧间时间步长分布
  - 实际帧率（均值、标准差）
  - 是否有时间戳回退
  - 是否有异常大的间隔

---

### K02A-R8: 置信度与质量掩码完善

**要求**:
- [ ] 修正置信度等级映射（NONE=0, LOW=1, MEDIUM=2, HIGH=3）
- [ ] 为每帧每关节生成 `reference_valid` 和 `reference_quality` 标签
- [ ] 质量判定规则：
  - HIGH confidence (3) + 骨长在均值±2σ内 → quality="high"
  - MEDIUM confidence (2) + 骨长在均值±3σ内 → quality="medium"
  - LOW confidence (1) 或骨长异常 → quality="low"
  - NONE confidence (0) → quality="unusable"
- [ ] 移除基于关节名称模式自动编造低置信度原因的逻辑
- [ ] 生成 `results/azure_kinect/K01/quality_mask.csv`

---

### K02A-R9: 创建学习文档

**要求**:
- [ ] 创建 `docs/learning/K02_KINECT_PIPELINE_OVERVIEW.md`

---

### K02A-R10: 创建交换 Schema 草案

**要求**:
- [ ] 创建 `data/interfaces/trajectory_exchange_schema.json`
- [ ] 定义全部字段的类型、单位、取值范围和语义
- [ ] 定义 `source` 字段的允许值枚举

---

## K02 最终验收

满足以下所有条件时，K02 可标记为 COMPLETED：

1. ✅ K02A-R1 到 K02A-R10 全部通过
2. ✅ 验证脚本对 K01 数据返回 0（全部检查通过）
3. ✅ 重投影误差使用实际标定后 < 5px MAE
4. ✅ 所有脚本 `--help` 可运行且信息完整
5. ✅ Claude 人工审查通过 K02 交付物
6. ✅ 学习文档经过审查
