# T04 验收标准：OpenPose BODY_25 骨架与 DeepSORT 人物轨迹关联

版本：v0.1.0
创建日期：2026-07-12
前置任务：T02（MOT 闭环，已关闭）、T03（OpenPose BODY_25，已通过）
处理视频：`three-people-walking.mp4`（240 帧，P001/P002/P003）

---

## 一、任务定位

将 OpenPose 逐帧骨架与人工复核后的 DeepSORT 轨迹进行一对一匹配，输出 `subject_id` 对应的连续骨架序列。**OpenPose people 数组顺序不是身份。**

---

## 二、输入

| 输入 | 路径 |
|------|------|
| MOT 复核轨迹 | `data/mot/reviewed/three-people-walking.csv` |
| Subject map | `data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv` |
| OpenPose JSON | `results/openpose/three-people-walking/raw_json/` (240 帧) |
| T03 异常帧分类 | `results/openpose/three-people-walking/manual_review_summary.json` |

已知约束：
- P001(track_1), P002(track_2), P003(track_3) — main_subject, frame 0-239
- track_id 4 — confirmed_false_positive, 不在 subject_map 中
- 帧 43/44/45 — ambiguous_pose（人物重叠，骨架混合）
- 帧 188 — phantom_pose（非人物区域骨架）
- 帧 207/208 — unmatched_pose（远处背景人物，无对应 track）

---

## 三、匹配算法要求

### 3.1 骨架派生框

从 BODY_25 关键点计算用于匹配的派生框。方法（至少一种）：
- **肩-髋包围框**：取肩部(2,5)和髋部(9,12)的 min/max 作为 torso 框
- **全关键点包围框**：取所有有效关键点(conf > 0)的 min/max
- 使用哪种方法记录在 metadata 中

### 3.2 匹配策略

对每帧：
1. 获取该帧的 MOT bbox 集合（按 track_id）和 OpenPose 骨架集合
2. 计算骨架派生框与 MOT bbox 的匹配代价矩阵
   - 代价 = `α × (1 - IoU) + β × center_distance_normalized`
   - 建议 α=0.6, β=0.4，实际值记录在 metadata
3. 使用 Hungarian 算法求最优一对一匹配
4. 匹配阈值：代价 < 阈值才接受匹配（建议 0.5），否则标记 unmatched
5. 同一 subject_id 在同一帧最多对应一副骨架

### 3.3 匹配状态标记

每条输出记录必须包含 `match_status`：

| 状态 | 含义 |
|------|------|
| `matched` | 骨架成功匹配到 subject_id |
| `unmatched_pose` | 骨架存在但无对应 MOT 轨迹（如帧 207/208 背景人物） |
| `unmatched_track` | MOT 轨迹存在但无对应骨架（检测丢失） |
| `ambiguous_pose` | 帧 43/44/45 的混合骨架，不强制关联 |
| `phantom_pose` | 帧 188 的 phantom 骨架，排除 |

---

## 四、异常帧处理规则（强制执行）

| 帧 | 规则 |
|----|------|
| 43, 44, 45 | 额外骨架标记 `ambiguous_pose`，不强制关联到任何 subject_id。三名主要人物的正常骨架仍尝试匹配。如果正常骨架也因重叠无法可靠匹配，标记 unmatched |
| 188 | 第 4 个骨架标记 `phantom_pose`，排除。三名主要人物的 3 个正常骨架正常匹配 |
| 207, 208 | 第 4 个骨架标记 `unmatched_pose`，不绑定到 P001-P003。三名主要人物正常匹配 |

**匹配失败时保留 unmatched 状态，不允许强行分配给最近 subject_id。**

---

## 五、输出文件

### 5.1 关联骨架序列
路径：`data/openpose/associated/three-people-walking.jsonl`

每行一条 person-帧记录：
```json
{
  "video_id": "three-people-walking",
  "frame_index": 0,
  "timestamp_sec": 0.0,
  "track_id": 1,
  "subject_id": "P001",
  "bbox_xyxy": [x1, y1, x2, y2],
  "keypoints": [[x0,y0,c0], ..., [x24,y24,c24]],
  "keypoint_confidence_raw": [c0, ..., c24],
  "match_status": "matched",
  "match_cost": 0.12,
  "annotation_version": "v0.1.0"
}
```

字段约束：
- `keypoints` 长度 = 25×3，缺失点 `[0,0,0]`
- `keypoint_confidence_raw` 保留 OpenPose 原始值（含 >1 的值）
- `match_status` 必填
- subject_id 仅来自 subject_map，不得自行分配

### 5.2 关联摘要
路径：`results/association/three-people-walking/summary.json`

```json
{
  "video_id": "three-people-walking",
  "total_frames": 240,
  "total_person_frames": null,
  "match_statistics": {
    "matched": null,
    "unmatched_pose": null,
    "unmatched_track": null,
    "ambiguous_pose": 3,
    "phantom_pose": 1
  },
  "per_subject": {
    "P001": {"matched_frames": null, "unmatched_frames": null, "avg_match_cost": null},
    "P002": {...},
    "P003": {...}
  },
  "anomaly_frames": {
    "43": "ambiguous_pose",
    "44": "ambiguous_pose",
    "45": "ambiguous_pose",
    "188": "phantom_pose",
    "207": "unmatched_pose",
    "208": "unmatched_pose"
  },
  "matching_params": {
    "iou_weight": 0.6,
    "center_distance_weight": 0.4,
    "cost_threshold": 0.5,
    "derived_bbox_method": "shoulder_hip"
  }
}
```

### 5.3 关联可视化
路径：`results/association/three-people-walking/association_visualization.mp4`

- H.264, 240 帧, 23.976 FPS, 2160×3840
- 每帧叠加：MOT bbox + subject_id 标签 + BODY_25 骨架
- 匹配成功：绿色框 + subject_id
- unmatched_pose：红色骨架
- unmatched_track：黄色虚线框
- ambiguous：橙色标记
- phantom：红色 X

### 5.4 运行日志
路径：`logs/runs/T04_POSE_TRACK_ASSOCIATION.md`

含完整命令、参数、输入文件 SHA-256、定量结果、异常记录。

---

## 六、验收标准

### 6.1 自动检查
- [ ] 240 帧全部处理
- [ ] JSONL 行数合理（约 715-726，对应 3 人 × ~240 帧减去异常）
- [ ] 每条记录含 frame_index, track_id, subject_id, bbox, keypoints, match_status
- [ ] P001/P002/P003 均存在于输出中
- [ ] match_status 仅有 5 种合法值
- [ ] 同一帧同一 subject_id 无重复记录
- [ ] 帧 43/44/45 额外骨架为 ambiguous_pose
- [ ] 帧 188 额外骨架为 phantom_pose
- [ ] 帧 207/208 额外骨架为 unmatched_pose
- [ ] 原始 DeepSORT 输出未被覆盖
- [ ] 原始 OpenPose JSON 未被覆盖

### 6.2 统计指标
- [ ] 成功匹配率（matched / total_person_frames）
- [ ] unmatched_pose 数量
- [ ] unmatched_track 数量
- [ ] ambiguous 数量（预期=3 帧中的额外骨架）
- [ ] 每 subject 的平均匹配代价

### 6.3 人工抽查
- [ ] ≥20 帧抽查
- [ ] 重点帧：43/44/45（交叉）、188（phantom）、207/208（背景人物）
- [ ] 检查：subject_id 标签与人物一致、骨架归属正确、异常帧按规定处理
- [ ] 抽查记录写入 `results/association/three-people-walking/human_spot_check.md`

---

## 七、不通过条件

1. 任何帧的 subject_id 来自 people 数组下标而非匹配结果
2. 帧 43/44/45 的混合骨架被强行分配给 P001-P003
3. 帧 188 的 phantom 骨架被匹配到任何 subject_id
4. 原始 DeepSORT 输出或 OpenPose JSON 被修改
5. 同一帧同一 subject_id 有多条记录
6. summary.json 缺少 match_statistics
7. unmatched_pose 或 unmatched_track 被静默丢弃

---

## 八、通过条件

所有自动检查通过 + 统计指标合理 + 人工抽查确认异常帧按规则处理 + 原始文件未被覆盖。
