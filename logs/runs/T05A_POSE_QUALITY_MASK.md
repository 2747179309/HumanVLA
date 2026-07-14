# Run ID: 20260713_T05A_001

- 日期：2026-07-13
- 实验目的：从T04关联结果构建P001/P002/P003连续BODY_25序列，并生成逐帧逐关节质量掩码。
- 当前状态：自动构建、验证和12帧颜色抽查完成；等待用户人工检查重点帧。
- 是否可以用于论文：否；这是单视频质量标记工程验证，不能作为公开实验结论。
- 代码基线：项目HEAD `827fba667264289049cff3b3545bb93e77bcdab1`；本轮脚本尚未提交。

## 环境

- Python 3.10.20 (`motpose`)
- OpenCV 5.0.0
- NumPy 2.2.6
- SciPy 1.15.3
- FFmpeg 4.2.7

## 输入

| 输入 | SHA-256 |
|---|---|
| `data/openpose/associated/three-people-walking.jsonl` | `78c8132a2d920d4028e0402fa167a60178c736ba1863d2cb779f78b2df0c2d1b` |
| `data/openpose/associated/reviewed/three-people-walking_T04_review.csv` | `84832965ffa6c68451333d05cd20c5895561b6d8100a7e74e4fb4bcffdfdc776` |
| `data/openpose/manual_gt/three-people-walking_pose_quality_review.csv` | `95548952d6c3e72c32ca2316277fd4633518d02a6ebe1811a1ea3df17712ef3c` |
| `results/openpose/three-people-walking/raw_json/` | 240文件，聚合SHA-256 `c174f901c73646b64b3f4a4ebbf3bb99c41534405324757e951a2449b14f0a8f` |
| `data/raw_videos/three-people-walking.mp4` | `1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd` |

输入哈希在质量掩码生成前后保持一致。未修改关联JSONL、OpenPose JSON、人工CSV或视频。

## 方法与规则

1. 帧2-239直接使用T04中已绑定subject_id的原始关键点。
2. 帧0-1没有DeepSORT confirmed track。根据当前T05A验收标准，以首个完整匹配帧2为起点，按骨架框中心距离逐帧向后执行Hungarian一对一分配；未使用OpenPose people数组顺序。
3. 帧0-1的最大归一化中心距离为0.01346463；分配方法、pose_index和代价保存在`raw_subject_sequences/metadata.json`。
4. P001帧15-19、54-61的关节2/3/4标记`low_quality`，其他关节保持`valid`。
5. P001/P003帧43-45的关节5/6/7标记`invalid_identity_mix`，其他关节标记`low_quality`；整帧`frame_valid=false`。
6. 帧188三名主人物保持`valid`，额外pose记录为`excluded_phantom`；帧207-208三名主人物保持`valid`，额外pose记录为`excluded_non_target`。
7. confidence原值完整复制，未将大于1作为删除条件；最终序列仍包含101个大于1的值。
8. 未执行滤波、插值、坐标平滑、Kinect对齐或动作标注。

## 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/build_subject_sequences.py \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --output-dir data/openpose/processed/three-people-walking/raw_subject_sequences \
  --subjects P001 P002 P003 --expected-frames 240 --annotation-version v0.2.0

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/build_quality_mask.py \
  --raw-sequence-dir data/openpose/processed/three-people-walking/raw_subject_sequences \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --t04-review data/openpose/associated/reviewed/three-people-walking_T04_review.csv \
  --pose-quality-review data/openpose/manual_gt/three-people-walking_pose_quality_review.csv \
  --output-dir data/openpose/processed/three-people-walking \
  --summary results/openpose/three-people-walking/quality_mask_summary.json \
  --expected-frames 240 --annotation-version v0.2.0

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/render_quality_mask.py \
  --video data/raw_videos/three-people-walking.mp4 \
  --processed-dir data/openpose/processed/three-people-walking \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --output-video results/openpose/three-people-walking/quality_mask_visualization.mp4 \
  --expected-frames 240

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/validate_quality_mask.py \
  --processed-dir data/openpose/processed/three-people-walking \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --openpose-json-dir results/openpose/three-people-walking/raw_json \
  --t04-review data/openpose/associated/reviewed/three-people-walking_T04_review.csv \
  --pose-quality-review data/openpose/manual_gt/three-people-walking_pose_quality_review.csv \
  --summary results/openpose/three-people-walking/quality_mask_summary.json \
  --visualization results/openpose/three-people-walking/quality_mask_visualization.mp4 \
  --expected-frames 240
```

四个脚本的`py_compile`和`--help`测试均通过。

## 输出与哈希

| 输出 | 行数/大小 | SHA-256 |
|---|---:|---|
| `data/openpose/processed/three-people-walking/P001.jsonl` | 240行 / 393250 bytes | `c2fc08e4bdf0e2acf9a84077c5fa7ff7e733e5f65a446e13f950349f337e6cfc` |
| `data/openpose/processed/three-people-walking/P002.jsonl` | 240行 / 389961 bytes | `9ff7b5317c8acdaa5182bf2287dd025fd1644a1f36404f3d1b257325d28b00c1` |
| `data/openpose/processed/three-people-walking/P003.jsonl` | 240行 / 391053 bytes | `6d3a49881cb3d89d0e7b0bfa615727f0a6820f068182ee535315474a0ba60a5f` |
| `data/openpose/processed/three-people-walking/quality_mask.jsonl` | 720行 / 520922 bytes | `7fba95d0efe1b958a39df4ae7459f4f577bca87626defded7735341286114919` |
| `results/openpose/three-people-walking/quality_mask_summary.json` | 4845 bytes | `c4d4f72b4b1d71d8266df7df7774dbfa144818c7d1c9e9d8efafb9e7ae4f16ab` |
| `results/openpose/three-people-walking/quality_mask_visualization.mp4` | 62724897 bytes | `2550a7650fb9ed5a1733f0493d07f07ee28f266e6bf5e85e5bfc320f6a2ea4d0` |

另保留raw派生中间序列和OpenCV中间视频，没有自动删除实验中间件。

## 定量结果

| subject | valid | low_quality | invalid_identity_mix | missing | frame_valid |
|---|---:|---:|---:|---:|---:|
| P001 | 224 | 13 | 3 | 0 | 237 |
| P002 | 240 | 0 | 0 | 0 | 240 |
| P003 | 237 | 0 | 3 | 0 | 237 |

全局720个person-frame：701个`valid`、13个`low_quality`、6个`invalid_identity_mix`、0个`missing`；714个`frame_valid=true`。额外pose层包含3个excluded ambiguous pose、1个excluded phantom和2个excluded non-target。

逐关节统计：

- P001：5886 valid、105 low_quality、9 invalid_identity_mix。
- P002：6000 valid。
- P003：5925 valid、66 low_quality、9 invalid_identity_mix。

## 自动验证

- P001/P002/P003各240行，帧号连续0-239；每帧每subject最多一条。
- `quality_mask.jsonl`为720行且按frame/subject完整覆盖。
- 所有`keypoints_raw`为25x3，`confidence_raw`为25个数值。
- 每个pose的关键点和confidence与T04 JSONL逐值相同；帧0-1通过保存的source_pose_index回查。
- 43-45的P001/P003均为`invalid_identity_mix`且`frame_valid=false`，P002保持`valid`。
- 188、207-208的三名主人物均为`valid`，额外pose在摘要中分别排除。
- 原OpenPose目录仍为240文件，聚合SHA-256与T03锁定值相同。
- 可视化为H.264、2160x3840、240帧、23.976 FPS。
- 最终验证器输出`validation_passed=true`，错误列表为空。

## 可视化抽查

抽查帧：0、15、19、43、44、45、46、54、61、188、207、208，共12帧。

- 帧0为三名人物绿色`valid`。
- 帧15、19、54、61仅P001受影响手臂为黄色，其他骨架为绿色。
- 帧43-45的P001/P003显示红色无效标记，P002保持绿色；额外pose为紫色排除。
- 帧46恢复绿色。
- 帧188的额外phantom为紫色，三名主人物绿色。
- 帧207-208的额外背景pose为紫色，三名主人物绿色。

## 当前问题与下一步

1. 帧0-1的subject归属是几何回溯派生结果，不是DeepSORT或人工确认身份，需重点人工检查。
2. P001帧15-19、54-61仍保留原始定位偏差；本任务没有修复。
3. 帧43-45已正确排除，但原始跨人物连接仍保留在raw数据中，任何下游必须同时检查`frame_valid`。
4. T05A完成后停止，不开始T05B、卡尔曼滤波或Kinect对齐。

## 帧0-1身份可靠性最小修正

- 修正日期：2026-07-13
- 修正原因：帧0-1没有DeepSORT confirmed track，几何回溯不能作为可靠subject身份，因此不得标记为有效数据。
- 本节取代上文所有“帧0-1几何回溯并标记valid”的旧结果；旧结果仅作为首次运行历史保留。

### 修正规则

P001、P002、P003在帧0-1统一设置：

- `frame_quality_status = "missing"`
- `frame_valid = false`
- `exclusion_reason = "no_confirmed_track_identity"`
- `keypoints_raw = [[0,0,0], ...]`，共25项
- `confidence_raw = [0, ..., 0]`，共25项
- `source_pose_index = null`
- `track_id = null`
- `sequence_assignment_method = "missing_fill_no_interpolation"`

脚本中已删除几何回溯/Hungarian早期身份分配逻辑。原始T04帧0-1的unmatched pose仍完整保留在T04 JSONL中，本修正只改变T05A派生序列。

### 重生成命令

以下命令使用用户明确要求的`--overwrite`，仅覆盖T05A派生产物：

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/build_subject_sequences.py \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --output-dir data/openpose/processed/three-people-walking/raw_subject_sequences \
  --subjects P001 P002 P003 --expected-frames 240 --annotation-version v0.2.0 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/build_quality_mask.py \
  --raw-sequence-dir data/openpose/processed/three-people-walking/raw_subject_sequences \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --t04-review data/openpose/associated/reviewed/three-people-walking_T04_review.csv \
  --pose-quality-review data/openpose/manual_gt/three-people-walking_pose_quality_review.csv \
  --output-dir data/openpose/processed/three-people-walking \
  --summary results/openpose/three-people-walking/quality_mask_summary.json \
  --expected-frames 240 --annotation-version v0.2.0 --overwrite

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/openpose/render_quality_mask.py \
  --video data/raw_videos/three-people-walking.mp4 \
  --processed-dir data/openpose/processed/three-people-walking \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --output-video results/openpose/three-people-walking/quality_mask_visualization.mp4 \
  --expected-frames 240 --overwrite
```

### 修正后统计

| subject | valid | low_quality | invalid_identity_mix | missing | frame_valid |
|---|---:|---:|---:|---:|---:|
| P001 | 222 | 13 | 3 | 2 | 235 |
| P002 | 238 | 0 | 0 | 2 | 238 |
| P003 | 235 | 0 | 3 | 2 | 235 |

全局720个person-frame：695个`valid`、13个`low_quality`、6个`invalid_identity_mix`、6个`missing`；708个`frame_valid=true`。

修正后序列含99个大于1的confidence。数量减少2是因为帧0-1被整体标记missing并置零，不是对保留pose的confidence进行裁剪；所有帧2-239的raw关键点和confidence仍与T04 JSONL逐值相同。

### 修正后输出哈希

| 输出 | SHA-256 |
|---|---|
| `P001.jsonl` | `6941d47fdaa56e719ecc905aade2886bf1ba166b355ccc3eea80000ab7152f9f` |
| `P002.jsonl` | `0814fff0e5d9fe7826b20c75f90ab2af1c8fe93f52e131b915f1a5e0d46ec49f` |
| `P003.jsonl` | `754ae986351c39ed9f42249485042eaa0365e7a362cecefcbc8aff342bd573dc` |
| `quality_mask.jsonl` | `d15bce09a2a9370fea924988d75d9ffa007f2addfbdc244bd4fbb9781df8b20b` |
| `quality_mask_summary.json` | `77ff362a0edbb6f40a3a14e90b1516bbc9b92cadbe0c965a0b70392edb954000` |
| `quality_mask_visualization.mp4` | `bb76e1b08044c7fd3861bab48e92cd79d64dce2ad79622be9b3148f2dc5fe7f9` |

### 修正后验证

- 独立验证器`validation_passed=true`，错误列表为空。
- 每个subject仍为240行，质量掩码仍为720行。
- 帧0-1的6个person-frame均为missing、`frame_valid=false`、指定排除原因、零骨架且无source pose。
- 帧2-239仍逐值回查T04 JSONL；43-45规则未变化。
- OpenPose raw目录仍为240文件，聚合SHA-256 `c174f901c73646b64b3f4a4ebbf3bb99c41534405324757e951a2449b14f0a8f`。
- 可视化仍为H.264、2160x3840、240帧；帧0-1只显示灰色missing标签，帧2恢复绿色。
- 未修改T04关联结果，未执行滤波，未开始T05B。
