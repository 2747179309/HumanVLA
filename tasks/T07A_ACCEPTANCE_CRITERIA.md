# T07A 验收标准：基于 Neck 和肩宽归一化的右上肢原始轨迹提取

版本：v0.2.0
日期：2026-07-14
前置：T06C（E001 感知流水线，已通过）
输入：`P001.jsonl` (345 帧) + `frames.jsonl` (动作标签)

---

## 一、每帧输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `video_id` | string | `pick_place_pilot_v1_E001` |
| `frame_index` | integer | 0-344 |
| `timestamp_sec` | number | |
| `phase_id` | integer | 来自 frames.jsonl |
| `phase_label` | string | 来自 frames.jsonl |
| `neck_x_px` | number | Neck(1) 原始像素 x |
| `neck_y_px` | number | Neck(1) 原始像素 y |
| `neck_dx_from_first_valid_px` | number/null | 相对首个有效身份帧（frame 2）的Neck x位移 |
| `neck_dy_from_first_valid_px` | number/null | 相对首个有效身份帧（frame 2）的Neck y位移 |
| `neck_frame_dx_px` / `neck_frame_dy_px` | number/null | Neck相对前一相邻有效帧的位移向量 |
| `neck_frame_displacement_px` | number/null | Neck相对前一相邻有效帧的欧氏位移 |
| `shoulder_width_px` | number | RShoulder-LShoulder 欧氏距离，始终 > 0 |
| `rshoulder_x_px` | number | RShoulder(2) 像素 x |
| `rshoulder_y_px` | number | |
| `rshoulder_frame_displacement_px` | number/null | RShoulder相对前一相邻有效帧的欧氏位移 |
| `rshoulder_frame_dx_px` / `rshoulder_frame_dy_px` | number/null | RShoulder相对前一相邻有效帧的位移向量 |
| `relbow_x_px` | number | RElbow(3) 像素 x |
| `relbow_y_px` | number | |
| `rwrist_x_px` | number | RWrist(4) 像素 x |
| `rwrist_y_px` | number | |
| `lshoulder_x_px` | number | LShoulder(5) 像素 x |
| `lshoulder_y_px` | number | |
| `lshoulder_frame_displacement_px` | number/null | LShoulder相对前一相邻有效帧的欧氏位移 |
| `lshoulder_frame_dx_px` / `lshoulder_frame_dy_px` | number/null | LShoulder相对前一相邻有效帧的位移向量 |
| `rwrist_x_norm` | number/null | (rwrist_x_px - neck_x_px) / shoulder_width_px |
| `rwrist_y_norm` | number/null | |
| `relbow_x_norm` | number/null | |
| `relbow_y_norm` | number/null | |
| `raw_confidence` | array[5] | Neck/RShoulder/RElbow/RWrist/LShoulder 原始置信度 |
| `trajectory_valid` | boolean | 该帧轨迹是否可用 |
| `trajectory_quality` | string | `valid` / `low_quality` / `missing` |
| `quality_reason` | string/null | 无效/低质量的原因 |
| `source_observation_status` | string | 来自 `joint_observation_status`（核心关节最差状态） |

---

## 二、无效数据规则（强制执行）

### 2.1 帧级无效（trajectory_valid=false，全部坐标 null）

| 帧 | 原因 |
|----|------|
| 0, 1 | DeepSORT n_init 确认前无 track，frame_valid=false |

### 2.2 关节级无效（对应坐标 null，其余关节不受影响）

| 帧 | 关节 | 原因 |
|----|------|------|
| 64, 65 | RWrist | 手部自遮挡 |
| 143 | RWrist | 手+纸盒遮挡 |
| 182-185 | RWrist | 疑似自遮挡与面部重叠 |

### 2.3 质量掩码联动

`joint_valid=false`（来自 T06C quality_mask）的关节 → 该关节坐标 null，`trajectory_quality=missing`（关节级）。

### 2.4 frame 226 反光 pose

P001 的 pose_index=0 正常提取。pose_index=1 不进入轨迹。不影响 frame 226 的 P001 数据。

---

## 三、归一化验证

### 3.1 公式正确性
- [ ] `x_norm = (x_joint - x_neck) / shoulder_width`
- [ ] `y_norm = (y_joint - y_neck) / shoulder_width`
- [ ] Neck 归一化后为 (0, 0)（容差 < 1e-9）
- [ ] `shoulder_width_px` = `||(rshoulder_x, rshoulder_y) - (lshoulder_x, lshoulder_y)||_2`

### 3.2 肩宽异常检测
- [ ] `shoulder_width_px > 0` 始终成立
- [ ] 肩宽异常帧（突然变化 > 平均值 30%）记录在 trajectory_summary.json 中

### 3.3 绝对运动保留
- [ ] Neck、RShoulder、LShoulder原始像素坐标不得固定、修改或滤除
- [ ] frame 2的Neck相对首个有效帧位移为(0,0)，相邻帧位移为null
- [ ] frame 3-344的Neck和双肩逐帧位移由相邻原始像素坐标直接计算
- [ ] frame 0-1的上述位移字段保持null，不跨无身份帧连接

---

## 四、输出文件验收

### 4.1 JSONL + CSV
- [ ] 345 行，frame_index 连续 0-344
- [ ] 所有指定字段存在
- [ ] 原始像素坐标与 P001.jsonl 的 `keypoints_raw` 逐帧一致
- [ ] 缺失关节的坐标字段为 JSON `null`（非 0.0，非空字符串）
- [ ] `trajectory_valid=false` 的帧所有坐标字段为 null

### 4.2 trajectory_summary.json
- [ ] 含 `missing_frames` 列表（帧 0-1）
- [ ] 含 `missing_joints` 列表（RWrist: 64/65/143/182-185）
- [ ] 含 `shoulder_width_stats`（min/max/mean/std/异常帧列表）
- [ ] 含 `per_phase_statistics`（每阶段帧数、有效帧数、RWrist 缺失数）
- [ ] 含 `absolute_motion`、人工确认的143-not-43修正和Neck/肩部真实代偿解释
- [ ] 明确后续仿真映射不能仅依赖Neck相对轨迹，须保留绝对桌面路径和A/B参考

### 4.3 raw_trajectory_plot.png
- [ ] 归一化坐标 2D 散点图（x_norm vs y_norm, y 轴翻转使上方=上方）
- [ ] 按 phase_id 着色（12 种颜色）
- [ ] Neck 原点标记
- [ ] 缺失/无效帧不在图中

### 4.4 raw_trajectory_overlay.mp4
- [ ] H.264, 345 帧, 1280×720, 30 FPS
- [ ] 显示：归一化轨迹历史（前 30 帧淡入）+ 当前帧骨架 + phase_label
- [ ] 有效帧绿色，low_quality 帧黄色，missing 帧灰色

### 4.5 运行日志
- [ ] `logs/runs/T07A_RAW_UPPER_LIMB_TRAJECTORY.md` 含完整命令、参数、输入哈希、统计

---

## 五、数据隔离
- [ ] P001.jsonl 未被修改
- [ ] frames.jsonl 未被修改
- [ ] T06C 全部文件哈希不变

---

## 六、不通过条件

1. 缺失关节被 0.0 或插值填充
2. 肩宽为 0 或负值未被标记
3. 行数 ≠ 345
4. 归一化公式错误（Neck ≠ 0,0）
5. frame 226 反光 pose 进入 P001
6. 使用了 MidHip/腰部作为原点
7. 原始文件被修改
8. 缺少任一输出文件

---

## 七、通过条件

所有验收项标记为 [x] + 345 帧完整 + 坐标一致性 + 缺失关节无隐式填补 + 原始文件未修改。
