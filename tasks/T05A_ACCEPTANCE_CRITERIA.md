# T05A 验收标准：OpenPose 骨架序列清洗与质量掩码生成

版本：v0.1.0
创建日期：2026-07-13
前置任务：T04（骨架-轨迹关联，有条件通过）
处理视频：`three-people-walking.mp4`（240 帧，P001/P002/P003）

---

## 一、任务定位

从 T04 关联 JSONL 生成 P001/P002/P003 的逐帧 BODY_25 连续序列，为每帧每个关节打上质量标签。**不执行平滑、插值或滤波。**

---

## 二、输入

| 输入 | 路径 |
|------|------|
| 关联 JSONL | `data/openpose/associated/three-people-walking.jsonl` (726 行) |
| T04 人工复核 | `data/openpose/associated/reviewed/three-people-walking_T04_review.csv` (240 帧) |
| 骨架质量复核 | `data/openpose/manual_gt/three-people-walking_pose_quality_review.csv` (5 段) |

---

## 三、质量状态定义（6 种）

| 状态 | 含义 | 帧级可用 | 关节级可用 | 可平滑 |
|------|------|---------|-----------|--------|
| `valid` | 正常关键点，置信度在合理范围 | ✅ | ✅ | ✅ |
| `low_quality` | 定位偏差但身份正确（如 P001 手臂） | ✅ | ⚠️ 偏差关节 | ✅（结果另存） |
| `invalid_identity_mix` | 跨人物错误连接（43-45） | ❌ | ❌ | ❌ 禁止 |
| `missing` | 该帧该人物无骨架（如帧 0-1 无 track） | ❌ | ❌ | ❌ |
| `excluded_phantom` | 非人物区域虚假骨架（188） | ❌ | ❌ | ❌ |
| `excluded_non_target` | 非 P001-P003 的背景人物（207-208） | ❌ | ❌ | ❌ |

---

## 四、人工结论到质量掩码的映射（强制）

| 帧范围 | subject_id | 关节范围 | 质量状态 | 依据 |
|--------|-----------|---------|---------|------|
| 0-1 | P001/P002/P003 | 全部 25 | `valid` | T04 review: unmatched_pose 仅因无 MOT track，骨架质量正常 |
| 2-14 | 全部 | 全部 25 | `valid` | T04 review: pass |
| 15-19 | P001 | 2,3,4 (右肩/肘/腕) | `low_quality` | pose_quality_review: joint_localization_error |
| 15-19 | P001 | 其余 22 | `valid` | 仅手臂受影响 |
| 15-19 | P002/P003 | 全部 25 | `valid` | 未受影响 |
| 20-42 | 全部 | 全部 25 | `valid` | T04 review: pass |
| 43-45 | P001 | 5,6,7 (左肩/肘/腕) | `invalid_identity_mix` | P003→P001 跨人物连接 |
| 43-45 | P003 | 5,6,7 (左肩/肘/腕) | `invalid_identity_mix` | 手臂节点错误连接到 P001 |
| 43-45 | P001/P003 | 其余关节 | `low_quality` | 重叠帧，全身可信度下降 |
| 43-45 | P002 | 全部 25 | `valid` | 未参与重叠 |
| 43-45 | (pose_index=3) | — | `excluded_phantom` | 非真人额外骨架 |
| 46 | 全部 | 全部 25 | `valid` | T04 review: recovery confirmed |
| 47-53 | 全部 | 全部 25 | `valid` | T04 review: pass |
| 54-61 | P001 | 2,3,4 (右肩/肘/腕) | `low_quality` | pose_quality_review: joint_localization_error |
| 54-61 | P001 | 其余 22 | `valid` | 仅手臂受影响 |
| 54-61 | P002/P003 | 全部 25 | `valid` | 未受影响 |
| 62-187 | 全部 | 全部 25 | `valid` | T04 review: pass |
| 188 | (pose_index=3) | — | `excluded_phantom` | 非人物区域 |
| 188 | P001/P002/P003 | 全部 25 | `valid` | 主人物未受影响 |
| 189-206 | 全部 | 全部 25 | `valid` | T04 review: pass |
| 207-208 | (pose_index=3) | — | `excluded_non_target` | 背景人物 |
| 207-208 | P001/P002/P003 | 全部 25 | `valid` | 主人物未受影响 |
| 209-239 | 全部 | 全部 25 | `valid` | T04 review: pass |

---

## 五、输出文件规范

### 5.1 逐人物序列

路径：`data/openpose/processed/three-people-walking/P001.jsonl`（同理 P002, P003）

每行 240 条（frame_index 0-239），每条：
```json
{
  "video_id": "three-people-walking",
  "subject_id": "P001",
  "frame_index": 0,
  "timestamp_sec": 0.0,
  "keypoints_raw": [[x0,y0,c0], ..., [x24,y24,c24]],
  "confidence_raw": [c0, ..., c24],
  "quality_mask": ["valid", "valid", ..., "missing"],
  "frame_valid": true,
  "joint_valid": [true, true, ..., false],
  "exclusion_reason": null,
  "annotation_version": "v0.2.0"
}
```

字段约束：
- `keypoints_raw`：25×3，直接复制自关联 JSONL。缺失帧填 `[[0,0,0], ...]`
- `confidence_raw`：25 个 float，保留 OpenPose 原生值（含 >1）
- `quality_mask`：25 个字符串，仅限 6 种合法值
- `frame_valid`：`invalid_identity_mix | missing | excluded_phantom | excluded_non_target` 时为 false
- `joint_valid`：`valid | low_quality` 时为 true，其余为 false
- 240 行，frame_index 连续 0-239

### 5.2 质量掩码

路径：`data/openpose/processed/three-people-walking/quality_mask.jsonl`

每行一个 person-帧，240×3=720 行：
```json
{
  "video_id": "three-people-walking",
  "frame_index": 0,
  "subject_id": "P001",
  "quality_mask": ["valid", ...],
  "frame_valid": true,
  "joint_valid": [true, ...],
  "num_valid_joints": 25,
  "num_low_quality_joints": 0,
  "num_invalid_joints": 0,
  "num_missing_joints": 0,
  "worst_joint_status": "valid"
}
```

### 5.3 掩码摘要

路径：`results/openpose/three-people-walking/quality_mask_summary.json`

```json
{
  "video_id": "three-people-walking",
  "total_frames": 240,
  "subjects": ["P001", "P002", "P003"],
  "per_subject": {
    "P001": {
      "total_frames": 240,
      "frame_valid_count": 237,
      "frame_invalid_count": 3,
      "invalid_frames": [43, 44, 45],
      "invalid_reason": "invalid_identity_mix",
      "low_quality_frames": [15,16,17,18,19,54,55,56,57,58,59,60,61],
      "low_quality_reason": "joint_localization_error_right_arm",
      "low_quality_joints": [2, 3, 4],
      "joint_status_distribution": {"valid": 5925, "low_quality": 39, "invalid_identity_mix": 9, "missing": 27}
    }
  },
  "global": {
    "total_person_frames": 720,
    "valid_frames": 711,
    "invalid_identity_mix_frames": 3,
    "low_quality_frames": 13,
    "excluded_phantom_instances": 1,
    "excluded_non_target_instances": 2
  }
}
```

### 5.4 掩码可视化

路径：`results/openpose/three-people-walking/quality_mask_visualization.mp4`

- H.264, 240 帧, 23.976 FPS, 2160×3840
- 骨架颜色按质量状态区分：
  - `valid` → 绿色
  - `low_quality` → 黄色（仅偏差关节，其余关节仍绿色）
  - `invalid_identity_mix` → 红色 X（整帧标记）
  - `missing` → 不渲染
  - 排除类 → 不渲染
- 每帧叠加 frame_index 和 subject_id

### 5.5 运行日志

路径：`logs/runs/T05A_POSE_QUALITY_MASK.md`

---

## 六、验收标准

### 6.1 自动检查
- [ ] P001/P002/P003 各 240 行，frame_index 连续 0-239
- [ ] quality_mask.jsonl 720 行（240×3）
- [ ] 每条记录 `keypoints_raw` 为 25×3 数组
- [ ] 每条记录 `confidence_raw` 为 25 元素数组
- [ ] `quality_mask` 仅含 6 种合法值
- [ ] `frame_valid` 与 `quality_mask` 中的排除状态一致
- [ ] 帧 43-45 的 P001/P003 为 `invalid_identity_mix`
- [ ] 帧 15-19/54-61 的 P001 关节 2,3,4 为 `low_quality`
- [ ] 帧 188/207-208 的主人物为 `valid`（额外骨架不在 per-subject 文件中）
- [ ] 关联 JSONL、OpenPose JSON、人工 CSV 未被修改
- [ ] `confidence_raw` 保留 >1 值

### 6.2 人工抽查
- [ ] ≥10 帧抽查质量掩码可视化
- [ ] 重点帧：15(黄色手臂)、43-45(红色)、46(恢复绿色)、54(黄色)、188(正常绿色)

---

## 七、不通过条件

1. 43-45 帧被标记为 `valid` 或 `low_quality`（必须为 `invalid_identity_mix`）
2. 原始文件被修改
3. 每个 subject 行数 ≠ 240
4. `quality_mask` 含非法值
5. 43-45 帧的关节被标记为可平滑
6. confidence_raw 被裁剪到 [0,1]

---

## 八、通过条件

所有自动检查通过 + 人工抽查颜色标注正确 + 原始文件未被修改。
