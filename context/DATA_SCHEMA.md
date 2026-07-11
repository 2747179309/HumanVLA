# 数据模式

## 标识符语义

- `video_id`：视频级稳定标识，在整个项目中唯一。
- `track_id`：DeepSORT 或人工修正轨迹在单个视频内的局部整数编号；不得跨视频解释。
- `subject_id`：人工确认的全局人物编号，格式为 `P001`、`P002` 等。
- `action_id`：单个人物的一段连续动作实例标识，建议格式为 `<video_id>_<subject_id>_A0001`。
- `action_label`：动作类别，如 `reach`、`grasp`、`move`、`place`。

## 帧级主记录

推荐使用 UTF-8 JSONL；每行对应一个视频帧中的一个人物。坐标均基于原始视频像素坐标系。

| 字段 | 类型 | 必需 | 定义 |
|---|---|---:|---|
| `video_id` | string | 是 | 项目内唯一视频标识 |
| `frame_index` | integer | 是 | 从 0 开始的原视频帧号 |
| `timestamp_sec` | number | 是 | 相对视频起点的秒数 |
| `track_id` | integer/null | 是 | 单视频内经人工复核的局部轨迹编号 |
| `subject_id` | string/null | 是 | 人工确认的全局人物编号 |
| `bbox_xyxy` | array[4]/null | 是 | `[x_min, y_min, x_max, y_max]`，原图像素坐标 |
| `detection_confidence` | number/null | 是 | 人体检测置信度，自动预标注时范围为 `[0, 1]` |
| `pose_model` | string/null | 是 | 例如 `openpose_BODY_25`；无骨架时为 null |
| `keypoints` | array[25][3]/null | 是 | BODY_25 点，单点格式 `[x, y, confidence]` |
| `keypoint_confidence` | array[25]/null | 是 | 从 `keypoints[*][2]` 冗余提取，便于质量控制 |
| `action_id` | string/null | 是 | 当前动作段实例标识 |
| `action_label` | string/null | 是 | 受控动作词表标签 |
| `object_label` | string/array/null | 是 | 交互对象标签；多对象时使用数组 |
| `language_instruction` | string/null | 是 | 与动作段对齐的语言指令 |
| `occluded` | boolean | 是 | 人体或关键动作区域是否被明显遮挡 |
| `source` | string | 是 | 来源，如 `self_collected` 或公开数据集名 |
| `annotation_version` | string | 是 | 标注版本，如 `v0.1.0` |

## BODY_25 约束

OpenPose BODY_25 必须严格保存为 `25 x 3`：

```text
[
  [x_0,  y_0,  confidence_0],
  ...,
  [x_24, y_24, confidence_24]
]
```

禁止丢弃低置信度点来改变数组长度。缺失点保持 OpenPose 原始约定并保留置信度；后续清洗不得覆盖 `raw_json`。`people` 数组顺序不能作为身份依据，必须通过骨架包围框/关键点与人工复核轨迹关联。

## MOT 与映射文件

- 原始跟踪输出：`data/mot/raw/<video_id>/`。
- 人工复核轨迹：`data/mot/reviewed/<video_id>/`。
- 人物映射：`data/mot/subject_maps/<video_id>.csv`，至少包含 `video_id,track_id,subject_id,valid_from_frame,valid_to_frame,reviewer,annotation_version`。
- BODY_25 原始输出：`data/openpose/raw_json/<video_id>/`，只读保留。
- 身份关联骨架：`data/openpose/associated/<video_id>.jsonl`。
- 人工骨架真值：`data/openpose/manual_gt/<video_id>/`。

## 校验规则

- `frame_index >= 0`，同一视频内时间戳单调不减。
- 非空 `bbox_xyxy` 满足 `x_min < x_max` 且 `y_min < y_max`。
- 非空 `detection_confidence` 必须在 `[0, 1]`，人工补框可按标注协议另行约定。
- 非空 `keypoints` 的形状必须为 `(25, 3)`，置信度应在 `[0, 1]`。
- `subject_id` 只能由人工复核映射产生，不能直接复制 DeepSORT ID。
- 每条处理记录必须能够追溯到原视频、轨迹版本和标注版本。
