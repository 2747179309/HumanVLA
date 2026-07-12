# Run ID: 20260712_T04_001

- 日期：2026-07-12
- 实验目的：将 OpenPose BODY_25 逐帧骨架与人工复核白名单内的 DeepSORT 轨迹进行一对一自动关联。
- 当前状态：自动关联和格式验证完成，等待用户人工抽查；T04 未最终验收。
- 是否可用于论文：否；当前是单视频自动关联结果，尚未完成人工关联质量验收。
- 代码基线：项目 HEAD `8235143f1e1edae88f509fc87522f906ba47eafe`，本轮脚本尚未提交。

## 环境

- Python 3.10.20 (`motpose`)
- OpenCV 5.0.0
- NumPy 2.2.6
- SciPy 1.15.3
- FFmpeg 4.2.7

## 输入解析

用户列出的 `data/mot/subject_maps/three-people-walking_subject_map.csv` 不存在。脚本按优先级自动发现并使用人工复核目录中的真实文件：

- MOT 人工结论：`data/mot/reviewed/three-people-walking.csv`，SHA-256 `85c2261629156b8cd673d010882d25e9219ed812d7909cced375b57eb58b0643`
- Subject map：`data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv`，SHA-256 `5d451ef1cc3dbbeccc4d200dd5b8b996f98daa7e6a110c0fd344406642a79dbb`
- 逐帧 MOT 框：`results/mot/three-people-walking/tracks_raw.jsonl`，SHA-256 `6d0650897c2bf7efa509cb384a2bdbbeeeba78f9e6cd035caa36df6e1c595869`
- OpenPose raw JSON：`results/openpose/three-people-walking/raw_json/`，240 文件，聚合 SHA-256 `c174f901c73646b64b3f4a4ebbf3bb99c41534405324757e951a2449b14f0a8f`
- T03 人工异常汇总：`results/openpose/three-people-walking/manual_review_summary.json`，SHA-256 `7e973b9fa72facd5147bb2d0ab710f7d780a01c3969c76eb801a37b056367446`
- 输入视频：`data/raw_videos/three-people-walking.mp4`，SHA-256 `1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd`

人工 review CSV 只包含轨迹质量结论，没有逐帧修正框。由于 track 1/2/3 被人工确认 `no_issue`，本次使用原逐帧 DeepSORT 框并以 reviewed subject map 作为唯一白名单；track 4 为 `confirmed_false_positive`，未进入关联。

## 算法与参数

- 骨架框：所有 `confidence > 0` 的 BODY_25 关键点的 min/max 包围框。
- 代价：`0.6 * (1 - IoU) + 0.4 * center_distance_normalized`。
- 中心距离：以对应 MOT bbox 对角线归一化。
- 分配：SciPy Hungarian 一对一分配。
- 接受阈值：`match_cost < 0.5`；未达到阈值保留 unmatched。
- 原始 confidence：逐值保留，包括大于 1 的值；未裁剪或归一化。
- 异常 pose 选择：在人工指定的6个异常帧中，以“最低有效关键点数，再按平均有效置信度”选择额外 pose，先赋予人工规定状态，再匹配其余 pose。
- 标注版本：`v0.1.0`。

## 完整命令

```bash
env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/association/associate_pose_to_tracks.py \
  --video-id three-people-walking \
  --iou-weight 0.6 \
  --center-distance-weight 0.4 \
  --cost-threshold 0.5 \
  --run-id 20260712_T04_001

env -u PYTHONPATH /home/a531/anaconda3/envs/motpose/bin/python \
  scripts/association/validate_association.py \
  --association-jsonl data/openpose/associated/three-people-walking.jsonl \
  --summary results/association/three-people-walking/summary.json \
  --pose-json-dir results/openpose/three-people-walking/raw_json \
  --subject-map data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv \
  --manual-review-summary results/openpose/three-people-walking/manual_review_summary.json \
  --visualization results/association/three-people-walking/association_visualization.mp4 \
  --manual-review-template results/association/three-people-walking/manual_review_template.csv \
  --expected-frames 240
```

静态检查：两个脚本的 Python `py_compile`、`--help` 和 whitespace diff 检查均通过。

## 输出

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `data/openpose/associated/three-people-walking.jsonl` | 1,209,576 bytes | `78c8132a2d920d4028e0402fa167a60178c736ba1863d2cb779f78b2df0c2d1b` |
| `results/association/three-people-walking/summary.json` | 9,727 bytes | `f3a2be169d6809eeb2f4dc903c4764d206aeb3eb2c8ce1f0cf6603a4128f9ee0` |
| `results/association/three-people-walking/association_visualization.mp4` | 63,754,482 bytes | `15e4ddc8ccb7d186777424783528814456e704a364c02079c8279d3e573a3682` |
| `results/association/three-people-walking/manual_review_template.csv` | 936 bytes | `2e6e1ab0f4f6d47f6c3ca3c8ccc29f8cb0f3d6a017f97bf9276573bfe3cc7d66` |

保留了 OpenCV 中间可视化 `association_visualization_opencv.mp4`，没有自动删除实验中间件。

## 定量结果

| 指标 | 真实结果 |
|---|---:|
| 处理帧数 | 240 |
| 人工白名单轨迹实例 | 714 |
| OpenPose pose 实例 | 726 |
| JSONL 记录 | 726 |
| matched pairs | 714 |
| matched rate | 1.000000（714/714 现有轨迹实例） |
| unmatched tracks | 0 |
| unmatched poses | 8 |
| ambiguous poses | 3 |
| phantom poses | 1 |
| 平均/最小/最大 match cost | 0.173401 / 0.085444 / 0.417309 |
| 自动运行时间 | 37.982 秒 |

每个 subject 的自动结果：

| subject_id | track_id | matched frames | unmatched frames | avg match cost | min match score |
|---|---:|---:|---:|---:|---:|
| P001 | 1 | 238 | 0 | 0.166550 | 0.673093 |
| P002 | 2 | 238 | 0 | 0.178459 | 0.744790 |
| P003 | 3 | 238 | 0 | 0.175193 | 0.582691 |

`matched_rate=1.0` 的分母是实际存在的714条白名单轨迹实例，不是名义上的720个subject-frame。DeepSORT在帧0和1尚未输出confirmed track，因此这两帧的6个pose保留为 `unmatched_pose`。

## 异常帧处理

| frame | 额外 pose_index | 状态 | 主人物匹配 | 自动处理 |
|---:|---:|---|---:|---|
| 43 | 3 | `ambiguous_pose` | 3 | 不绑定subject；其余三副pose尝试Hungarian匹配 |
| 44 | 3 | `ambiguous_pose` | 3 | 同上 |
| 45 | 3 | `ambiguous_pose` | 3 | 同上 |
| 188 | 3 | `phantom_pose` | 3 | 不绑定subject，下游排除 |
| 207 | 3 | `unmatched_pose` | 3 | 远处真实人物，不绑定P001-P003 |
| 208 | 3 | `unmatched_pose` | 3 | 远处真实人物，不绑定P001-P003 |

43-45帧的P003匹配分数分别约为0.5827、0.5985、0.6467，是全视频最低的一组，符合重叠场景风险，必须人工检查，不能因低于代价阈值就视为人工真值。

## 自动验证

独立验证器通过，真实输出如下：

- `validation_passed=true`，错误列表为空。
- 覆盖240帧，726个JSONL记录对应726个raw pose，未丢失或重复pose。
- 同一帧同一subject无重复；所有track/subject组合来自人工subject map。
- 六个异常帧均为3个matched主人物记录加1个规定异常状态。
- 每条pose的25x3关键点及raw confidence与原OpenPose JSON逐值一致。
- raw OpenPose目录在运行前后及验证时哈希一致。
- 可视化为H.264、2160x3840、240帧、23.976 FPS。
- 人工复核模板包含20帧，所有`reviewer_decision`均为`pending`。

## 当前问题与下一步

1. 自动格式验证通过不等于身份关联经人工确认；T04仍等待人工抽查。
2. 重点检查43-45帧的identity mix，尤其P003和P001自动分配；不强制修复。
3. 检查帧0-1无MOT轨迹但有6副pose的处理是否接受。
4. 检查188的phantom排除和207-208的背景人物unmatched处理。
5. 复核模板还包含低分帧58、17、59、60、57、219、14、56、35、220、167、52、75、6。
6. 本轮未执行滤波、插值、T05、动作标注或模型训练。

下一步只应由用户填写 `manual_review_template.csv` 或另存人工复核结果；在此之前不得声称T04最终通过。

## 人工复核结果收尾

- 收尾日期：2026-07-12
- 全帧关联复核：`data/openpose/associated/reviewed/three-people-walking_T04_review.csv`
- 骨架质量分段复核：`data/openpose/manual_gt/three-people-walking_pose_quality_review.csv`
- 汇总输出：`results/association/three-people-walking/manual_review_summary.json`

### CSV格式与完整性

- 关联复核CSV包含预期8个字段和240条记录，`frame_index`连续覆盖0-239，无重复或缺帧。
- 240条`automatic_statuses`均与关联JSONL逐帧状态集合一致。
- 人工决定为237帧`pass`、3帧`fail`；失败帧仅为43、44、45。
- 骨架质量CSV采用帧段级格式，包含预期7个字段和5条互不重叠的区间记录，共覆盖19个已报告问题帧；它不是逐帧240行格式。
- 两份CSV均以UTF-8 BOM读取，数据类型、帧范围、枚举值和必填文本检查通过；未修改人工判断。

输入哈希：

- T04 review CSV：`84832965ffa6c68451333d05cd20c5895561b6d8100a7e74e4fb4bcffdfdc776`
- pose quality CSV：`95548952d6c3e72c32ca2316277fd4633518d02a6ebe1811a1ea3df17712ef3c`
- 自动关联JSONL：`78c8132a2d920d4028e0402fa167a60178c736ba1863d2cb779f78b2df0c2d1b`，保持不变
- 人工汇总JSON：`ae2916482543af9e9a921a076b4caa8063fd2f24d03d17a38334fb1e20d0fde5`

### 分类统计

| 类别 | 帧数 | 帧 | 人工结论 |
|---|---:|---|---|
| 身份关联错误 | 0 | 无 | P001、P002、P003未发现身份交换；可复核的238帧均为`subject_id_correct=yes` |
| OpenPose关键点定位误差 | 13 | 15-19、54-61 | P001持杯手臂关键点未完全贴合；身份和骨架归属仍正确 |
| identity_mix | 3 | 43-45 | P003手臂跨接到P001，且存在非真人额外骨架；pose assignment失败 |
| phantom_pose | 1 | 188 | 非人物区域的额外骨架；主人物关联正确 |
| out-of-scope unmatched_pose | 2 | 207-208 | 真实背景人物，不属于P001-P003，保持unmatched |
| 恢复检查 | 1 | 46 | 人物分离后身份关联和骨架恢复正常 |

上述问题帧并集为19帧，其余221帧未报告肉眼可见异常。帧0-1因无confirmed DeepSORT轨迹为`not_applicable`身份检查，但现有`unmatched_pose`处理被人工判定为正确。

### 下游边界

1. 帧43-45必须整体标记为歧义/无效，不得直接进入后续平滑或训练数据。
2. 不得用卡尔曼滤波强行修复43-45的跨人物错误连接。
3. 帧15-19和54-61保留原始结果，后续只能在独立骨架质量实验中统计或另存派生结果。
4. 帧188只排除额外phantom pose；原始OpenPose输出保持不变。
5. 帧207-208的额外背景pose保持unmatched，不纳入三名主要人物序列。

### 当前派生输出状态

当前ID区分配色版本的可视化SHA-256为`2d25a47a1afb8a3fc6d4e5921c5305d0130a6f996b760d083488310408ae3a25`；当前自动summary SHA-256为`0ce6e82b9f7dceab58bffb6cc0515738c5aa81c65b168915e31768767af46945`。本次人工收尾没有重新生成或覆盖它们。

### 收尾命令

```bash
python -c "使用csv.DictReader验证240帧关联复核和5条质量区间记录，并与JSONL逐帧状态交叉检查"
sha256sum data/openpose/associated/reviewed/three-people-walking_T04_review.csv \
  data/openpose/manual_gt/three-people-walking_pose_quality_review.csv \
  results/association/three-people-walking/summary.json \
  data/openpose/associated/three-people-walking.jsonl
python -c "验证manual_review_summary.json中的统计和所有source SHA-256"
git status --short
git diff --stat
```

本轮未运行新实验，未修改关联JSONL、OpenPose raw JSON或视频，未执行滤波，未开始T05。

建议提交信息：`docs: finalize T04 human association review`
