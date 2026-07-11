# MOT 人工复核与标注规范

版本：v0.1.0  
生效日期：2026-07-11  
适用范围：HumanVideo2VLA 项目中所有多人视频的 MOT 轨迹人工复核  

---

## 一、核心概念定义

### 1.1 track_id（局部轨迹编号）

- **定义**：由 DeepSORT（或其他 MOT 算法）在单个连续视频内为每个检测到的人物分配的连续整数编号。
- **作用域**：仅在一个视频内有效。跨视频无意义。
- **产生方式**：由算法自动生成，在算法输出时刻 (frame 0) 开始分配。
- **稳定性**：不保证。同一人物在视频不同时间段可能被分配不同 track_id（ID Switch）；不同人物可能被错误合并为同一 track_id（ID Merge）。
- **在人工复核中的角色**：track_id 是待修正的输入，不是真值。

### 1.2 subject_id（全局人物编号）

- **定义**：经人工确认的、跨视频唯一的人物标识。
- **格式**：`P001`、`P002`、...（P 后三位数字，从 001 开始连续编号）。
- **作用域**：全项目全局。同一个人在不同视频中 `subject_id` 必须一致（如果能够跨视频识别）。
- **产生方式**：仅由人工在 CVAT 复核后分配。自动算法不得直接生成 subject_id。
- **注意**：如果无法跨视频确认人物身份（如不同视频中人物穿着不同、面部不可见），不同视频中的人物应分配不同 subject_id，不可猜测合并。

### 1.3 frame_index

- **定义**：原始视频帧索引，从 0 开始。
- **作用域**：单个视频内。
- **与时间戳关系**：`timestamp_sec = frame_index / fps`。

### 1.4 annotation_version

- **格式**：语义化版本 `v<MAJOR>.<MINOR>.<PATCH>`。
- **含义**：
  - MAJOR：大幅重标注（如重新定义 ID 体系）
  - MINOR：新增或修改若干帧的标注
  - PATCH：修正笔误或单帧错误
- **示例**：`v0.1.0`（第一次人工复核）、`v0.1.1`（修正了 3 帧的 ID 错误）

---

## 二、MOT 错误类型定义

### 2.1 ID Switch（身份交换）

**定义**：同一条 track_id 轨迹在视频中间某时刻从人物 A 切换到了人物 B。

**可视化判断**：跟踪框在相邻帧间突然从一个人物位置"跳"到另一个人物位置，而中间无遮挡或交叉。

**典型场景**：
- 两人交叉经过后，跟踪器将二人的 ID 互换
- 人物 A 离开画面后，track_id 被重新分配给新进入的人物 B

**修正规则**：
- 在 ID Switch 发生的帧之前：保持原 track_id（对应 subject_id X）
- 在 ID Switch 发生的帧之后：将 track_id 修正为正确的 subject_id（或新建 track_id 分配给不同 subject_id）
- 如果原 track_id 无法确定归属，应将 Switch 后的帧分配给新 track_id

**记录格式**（在修正日志中）：
```
ID Switch: track_3, frame 147→148
  Before: track_3 = P001 (confirmed)
  After:  track_3 switched to P002 (actual)
  Fix: split track_3 at frame 147; create track_8 for P001 from frame 148 onwards
```

### 2.2 Track Fragmentation（轨迹断裂）

**定义**：同一人物在视频中被分配了多个不同的 track_id，通常因为短暂遮挡或检测丢失后重新出现。

**典型场景**：
- 人物被物体短暂遮挡 5 帧，DeepSORT 丢失跟踪，重新出现时获得新 track_id
- 人物走出画面后 10 帧再走进，被分配新 track_id

**修正规则**：
- 如果断裂发生在同一人物短暂离开后重新出现（且可确认是同一人）：将两段合并为同一 subject_id
- 如果断裂发生在两个不同的人物之间：不合并
- 合并时需在 subject_map.csv 的 `valid_from_frame` 和 `valid_to_frame` 中记录每段的起止帧

**记录格式**：
```
Fragmentation: track_2 (frame 0-50) + track_7 (frame 58-120)
  Reason: occlusion by table, frame 51-57
  Fix: merge into subject_id P001
  Segments: [0,50] + [58,120]
```

### 2.3 False Positive Track（误检轨迹）

**定义**：track_id 对应的检测框不包含任何真实人物。

**典型场景**：
- 背景物体（椅子、衣服）被误检测为 person
- 检测框内是人物的一部分（如一只手）但不构成完整人体
- 检测框飘移到无人区域（跟踪漂移）

**修正规则**：
- 标记该 track_id 为 `FP`，在 subject_map.csv 中不分配 subject_id
- 在 reviewed MOT 文件中删除对应行，或标记为 ignore region
- 误检轨迹不计入最终数据集

**记录格式**：
```
FP track_12 (frame 89-95): detection on a coat rack
  Fix: mark as FP, exclude from dataset
```

### 2.4 Missing Track（漏检轨迹）

**定义**：真实人物存在于画面中，但无任何 track_id 覆盖。

**典型场景**：
- YOLO 未检测到远处的小人物
- 人物部分遮挡导致检测置信度低于阈值
- 人物处于画面边缘

**修正规则**：
- 在 CVAT 中手动补框
- 为补框分配新的 track_id（建议使用 1000+ 范围的编号以区分自动生成的 ID）
- 建立该 track_id 到 subject_id 的映射
- 记录漏检发生的原因和帧范围

**记录格式**：
```
Missing: P003 not detected frame 34-41
  Reason: person partially behind door
  Fix: manually add bounding boxes, assign track_1001 → subject_id P003
```

---

## 三、特殊场景修正规则

### 3.1 人物进入画面

**定义**：人物从画面边缘进入（不是从遮挡后重新出现）。

**规则**：
- 如果人物是首次出现且未在之前帧中见过：分配新 subject_id
- 如果人物之前曾离开画面（见 3.2）：判断是否与之前的人物相同
- 进入帧为第一帧能确认人物身份的帧（不是只露出一只手的帧）

### 3.2 人物离开画面

**定义**：人物完全走出画面边界。

**规则**：
- 离开帧为最后一帧仍可见人物大部分身体的帧
- track_id 的 `valid_to_frame` 记录为离开帧（含）
- 如果同一人物稍后重新进入画面：
  - 如果能确认是同一人（衣着、体态、位置连续）：使用相同 subject_id
  - 如果不能确认：使用不同 subject_id，并在 subject_map.csv 备注中说明原因

### 3.3 人物重新进入画面

**定义**：离开画面一段时间后再次进入。

**规则**：
- 离开时间 < 5 秒（或 < 150 帧 @30fps）且位置、衣着一致 → 可判定为同一人
- 离开时间 ≥ 5 秒 → 需要额外证据（衣着颜色、体态、携带物品）才能判定为同一人
- 如果无法确定，保守处理：分配不同 subject_id
- 绝对不依赖 DeepSORT 的 ReID 特征来跨长时间间隔确认身份（ReID 特征本身可能有偏差）

### 3.4 两人交叉或遮挡

**定义**：两个人物在画面中路径交叉，或一人部分遮挡另一人。

**规则**：
1. **交叉前**：确认两人的 track_id 和 subject_id 分配正确
2. **交叉帧**：逐帧检查跟踪框是否正确跟随各自人物
3. **交叉后**：确认跟踪框未交换——这是 ID Switch 最高发的场景
4. 交叉期间如果两人几乎完全重叠（如 < 50% 可见），标记 `occluded: true` 在该时间段的帧记录中
5. 如果交叉后无法确定谁是谁（衣着相似、面部不可见），在修正日志中记录不确定性

### 3.5 部分遮挡

**定义**：人物被静态物体（桌子、门、柱子）部分遮挡。

**规则**：
- 遮挡 < 50%（身体大部分可见）→ 标注为无遮挡，正常跟踪
- 遮挡 ≥ 50% → 在帧记录中标记 `occluded: true`
- 遮挡 ≥ 80%（仅头部可见等）→ 该帧可以不要求有框；如果在 CVAT 中也无法确定位置，标记为 missing

---

## 四、CVAT 人工复核流程

### 4.1 准备工作

1. 将 DeepSORT 输出的 MOT 格式文件转换为 CVAT 可导入格式
2. 在 CVAT 中创建任务，导入视频和 MOT 标注
3. 确认视频 FPS 显示正确

### 4.2 复核步骤（按优先级排序）

**第一遍：ID Switch 检查**
- 在 CVAT 中播放视频，关注轨迹标签颜色是否有突然交换
- 重点检查交叉帧前后
- 标记所有疑似 ID Switch 的帧

**第二遍：轨迹断裂检查**
- 逐条 track_id 检查，确认其在时间轴上是否连续
- 检查每段轨迹的首尾：起始帧是否合理（人物刚进入还是从遮挡后出现），结束帧是否合理（人物离开还是检测丢失）
- 标记所有疑似断裂的轨迹段

**第三遍：误检和漏检检查**
- 逐帧扫描，确认每个检测框是否真的包含一个完整人物
- 扫视画面中是否有人物未被任何框覆盖
- 标记误检和漏检帧

**第四遍：边界精修**
- 修正检测框的边界使其更贴合人物
- 统一框的标注规范（框应包含整个人体，含头发和脚）

### 4.3 人工复核质量检查清单

每条视频复核完成后，确认以下各项：

- [ ] 所有 ID Switch 已标记并修正
- [ ] 所有轨迹断裂已评估（合并或保留分离）
- [ ] 所有误检轨迹已标记为 FP
- [ ] 所有超过 10 帧的漏检段已补框
- [ ] 所有交叉场景已逐帧检查
- [ ] 所有遮挡场景已标记 occluded 状态
- [ ] subject_id 分配无重复、无遗漏
- [ ] subject_map.csv 已填写完整
- [ ] 修正日志已记录所有修改及原因
- [ ] 复核人签名和日期已填写

---

## 五、MOT 结果版本与命名规则

### 5.1 文件路径约定

```
data/mot/raw/<video_id>/mot.txt           # DeepSORT 原始输出，永不覆盖
data/mot/reviewed/<video_id>/mot_reviewed_v<MAJOR>.<MINOR>.<PATCH>.txt
data/mot/subject_maps/<video_id>.csv       # track_id → subject_id 映射
```

### 5.2 MOT 文件格式

遵循 MOTChallenge 格式：
```
<frame>, <id>, <bb_left>, <bb_top>, <bb_width>, <bb_height>, <conf>, <x>, <y>, <z>
```
其中：
- `frame`：从 1 开始的帧号（MOTChallenge 惯例）
- `id`：track_id（修复后）
- `conf`：检测置信度，对于人工加框记为 1.0
- `x, y, z`：3D 场景中的位置，本项目填 -1

### 5.3 subject_map.csv 字段定义

```csv
video_id,track_id,subject_id,valid_from_frame,valid_to_frame,review_status,reviewer,annotation_version,notes
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| video_id | string | 是 | 视频唯一标识 |
| track_id | integer | 是 | 复核后的局部轨迹编号 |
| subject_id | string | 是/null | 全局人物编号；FP 时填 null |
| valid_from_frame | integer | 是 | 该 mapping 生效的起始帧（含，0-indexed） |
| valid_to_frame | integer | 是 | 该 mapping 生效的结束帧（含，0-indexed） |
| review_status | string | 是 | `reviewed_ok` / `reviewed_fixed` / `fp` / `flagged` |
| reviewer | string | 是 | 复核人姓名或 ID |
| annotation_version | string | 是 | 版本号，如 v0.1.0 |
| notes | string | 否 | 修正原因、不确定性说明等 |

### 5.4 修正日志

每次人工复核必须生成 `data/mot/reviewed/<video_id>/review_log_v<version>.md`，包含：

```markdown
# MOT Review Log: <video_id>

- 复核日期：
- 复核人：
- 标注版本：
- 输入文件：data/mot/raw/<video_id>/mot.txt
- 输出文件：data/mot/reviewed/<video_id>/mot_reviewed_vX.X.X.txt
- 原始轨迹数：
- 复核后轨迹数：
- ID Switch 修正数：
- 轨迹合并数：
- FP 删除数：
- 漏检补框数：

## 逐项修正记录

（每条修正按 2.1-2.4 格式记录）
```

---

## 六、常见错误和注意事项

1. **不要将 DeepSORT 的 track_id 直接复制为 subject_id**。即使 DeepSORT 在某个视频中看起来"没有出错"，也应通过人工确认。

2. **track_id 的连续性不代表正确性**。DeepSORT 可以生成 ID 序列 1, 2, 3, 4, 5 看起来"干净"，但实际上 ID 3 和 ID 5 可能是同一人。

3. **CVAT 中的跟踪插值**：CVAT 的跟踪插值功能（在关键帧之间自动插值框）可能引入位置偏差。插值段的首尾关键帧必须人工确认。

4. **不要仅凭衣着颜色判断身份**：同色衣服在低分辨率视频中可能是不同人。

5. **被复核人遮挡的人物**：如果人物 A 被人物 B 完全遮挡 > 5 帧，人物 A 在这段遮挡期间不需要补框（因为确实不可见）。

6. **双人复核建议**：对于训练/验证集中使用的视频，建议由第二人抽查至少 20% 的帧，计算标注一致性（见质量检查清单）。

---

## 七、与 DATA_SCHEMA 的关系

本协议与 `context/DATA_SCHEMA.md` 的关系：

- DATA_SCHEMA 定义了帧级 JSONL 的字段格式
- 本协议定义了如何从 MOT 输出产生那些字段中的 track_id、subject_id、bbox_xyxy、occluded
- 复核完成后，每个 (video_id, frame_index, subject_id) 三元组对应 JSONL 中的一行
- `annotation_version` 在 JSONL 和 subject_map.csv 中必须一致

---

## 八、参考资源

- MOTChallenge 格式：https://motchallenge.net/instructions/
- CVAT 文档：https://docs.cvat.ai/
- DeepSORT 论文：N. Wojke et al., "Simple Online and Realtime Tracking with a Deep Association Metric", ICIP 2017
