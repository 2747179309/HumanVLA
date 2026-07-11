# T01 验收标准：第一段测试视频 MOT 流水线

版本：v0.1.0  
创建日期：2026-07-11  
适用范围：T01 任务"新电脑环境审计与 DeepSORT/OpenPose 工作区初始化"的最小可行验收  

---

## 一、验收范围说明

本文件定义的是 T01 的子任务——第一段测试视频的 **MOT 流水线最小闭环**——的验收标准。此闭环不包括 OpenPose 阶段（OpenPose 在 MOT 复核完成后才开始）。

完整 T01 的范围较大，本次审查将 T01 缩小为一组可逐一验证的子标准。

---

## 二、前置条件（Pre-conditions）

在开始任何流水线执行前，必须满足：

| 编号 | 前置条件 | 验证方式 |
|------|---------|---------|
| P1 | `motpose` Conda 环境已创建且激活 | `conda env list | grep motpose` |
| P2 | PyTorch 已安装且 CUDA 可用 | `python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"` 输出含 "RTX 3090" |
| P3 | OpenCV 已安装且可读取视频 | `python -c "import cv2; cap = cv2.VideoCapture('<test>'); print(cap.isOpened())"` 输出 True |
| P4 | FFmpeg 已安装 | `ffmpeg -version` 正常输出 |
| P5 | YOLO 权重已下载（轻量模型即可） | 文件存在且 SHA-256 已记录 |
| P6 | DeepSORT 实现已安装 | Python 可 import |
| P7 | 测试视频已放入 `data/raw_videos/` | 文件存在，已设为只读 |
| P8 | 环境依赖已冻结 | `environment/requirements/motpose.*` 文件存在 |

---

## 三、输入视频验收

### 3.1 视频基本信息

| 字段 | 要求 | 记录位置 |
|------|------|---------|
| 文件名 | 不含中文和特殊字符 | `data/raw_videos/` 下的实际路径 |
| 格式 | MP4（H.264 编码）优先 | 文件扩展名 |
| 时长 | 10-30 秒 | 秒，精确到小数点后一位 |
| FPS | 记录实际 FPS | 浮点数，精确到小数点后两位 |
| 分辨率 | 记录实际宽×高 | W×H（像素） |
| 总帧数 | 与实际帧数一致 | 整数 |
| SHA-256 | 计算并记录 | 64 位十六进制字符串 |
| 人物数 | 人工计数 | 至少 2 人，画面中同时出现 |
| 标注授权 | 已确认可使用 | 用户书面或消息确认 |

### 3.2 视频质量要求

- [ ] 视频可被 OpenCV `cv2.VideoCapture` 正常打开
- [ ] FPS 稳定（非可变帧率 VFR，或已转换为 CFR）
- [ ] 无明显花屏、丢帧段
- [ ] 人物至少部分可见（非全遮挡、非背光剪影）
- [ ] 无隐私风险（可公开发表的人脸需评估是否模糊处理）

---

## 四、YOLO Person 检测验收

### 4.1 功能验证

- [ ] `python scripts/mot/detect_persons.py --help` 正常输出帮助信息
- [ ] 脚本可读取测试视频每一帧
- [ ] 每帧输出包含检测框列表（可能为空）
- [ ] 每个检测框包含 `[x_min, y_min, x_max, y_max, confidence]`
- [ ] 仅输出 `class=person` 的检测框（不过滤其他类别时需标注）

### 4.2 输出验证

- [ ] 原始检测结果保存到 `data/mot/raw/<video_id>/detections.jsonl`
- [ ] JSONL 每行格式正确：`{"frame_index": int, "detections": [[x1,y1,x2,y2,conf], ...]}`
- [ ] 检测结果文件行数 = 视频总帧数

### 4.3 合理性检查（非精度评估）

以下检查不替代定量评估，但用于发现明显的配置错误：
- [ ] 大多数帧（>50%）检测到的人数与人工观察一致（±1 人）
- [ ] 没有出现"每帧都检测到 0 人"或"每帧固定检测到 N 人"的异常
- [ ] 检测框大小与人物在画面中的实际大小大致匹配（不出现覆盖整个画面的框）
- [ ] 置信度分布合理（不是全 0.99 或全 < 0.1）

---

## 五、DeepSORT 跟踪验收

### 5.1 功能验证

- [ ] `python scripts/mot/track_deepsort.py --help` 正常输出
- [ ] 脚本可读取检测结果并运行 DeepSORT
- [ ] 输出 track_id 为正整数

### 5.2 输出文件

| 输出 | 路径 | 格式要求 |
|------|------|---------|
| 逐帧轨迹 JSONL | `data/mot/raw/<video_id>/tracks.jsonl` | 每行含 frame_index, track_id, bbox, confidence |
| MOT 格式 | `data/mot/raw/<video_id>/mot.txt` | MOTChallenge 格式：`frame, id, x, y, w, h, conf, -1, -1, -1` |
| 可视化视频 | `results/mot/<video_id>_tracked.mp4` | 每个检测框上叠加 track_id 文字，H.264 编码 |

### 5.3 JSONL 格式验收

随机抽取 3 帧（首帧、中间帧、末帧），检查：
- [ ] `frame_index` 正确
- [ ] `track_id` 为正整数
- [ ] `bbox` 为 4 元素数组
- [ ] `confidence` 在 [0, 1] 范围内
- [ ] 同一帧内同一 track_id 不重复出现

### 5.4 MOT 格式验收

- [ ] `mot.txt` 符合 MOTChallenge 格式
- [ ] frame 编号从 1 开始（MOTChallenge 惯例）
- [ ] bbox 格式为 `[x_left, y_top, width, height]`（不是 `[x1,y1,x2,y2]`）
- [ ] conf 列的值与检测置信度一致
- [ ] 最后三列（3D 位置）填 -1

### 5.5 可视化视频验收

- [ ] 视频可正常播放
- [ ] 检测框颜色一致（同一 track_id 颜色不变）
- [ ] track_id 数字清晰可辨
- [ ] 视频时长和帧数与源视频一致
- [ ] FPS 与源视频一致

### 5.6 合理性检查（非精度评估）

- [ ] track_id 数量在合理范围（不应为 0，不应远超画面中可能出现的人数）
- [ ] 存在时间过短的轨迹（< 5 帧）被记录并在报告中标注
- [ ] 输出轨迹总数、平均轨迹时长、最短/最长轨迹时长被记录
- [ ] DeepSORT 的配置参数（max_age, n_init, nn_budget, max_cosine_distance 等）完整记录在运行日志中

---

## 六、人工复核验收

### 6.1 CVAT 导入

- [ ] MOT 结果可成功导入 CVAT
- [ ] track_id 在 CVAT 中正确显示
- [ ] 帧号对齐无偏移

### 6.2 复核完成标准

- [ ] 所有 ID Switch 已标记（如存在）
- [ ] 所有轨迹断裂已评估（如存在）
- [ ] 所有超过 5 帧的漏检段已补框
- [ ] 所有误检轨迹已标记为 FP
- [ ] 所有交叉帧已逐帧确认
- [ ] subject_id 分配完成（连续编号，无重复）

### 6.3 复核输出

| 输出 | 路径 | 要求 |
|------|------|------|
| Reviewed MOT | `data/mot/reviewed/<video_id>/mot_reviewed_v0.1.0.txt` | MOTChallenge 格式 |
| Subject Map | `data/mot/subject_maps/<video_id>.csv` | 含所有必需字段 |
| 复核日志 | `data/mot/reviewed/<video_id>/review_log_v0.1.0.md` | 含逐项修正记录 |

### 6.4 subject_map.csv 验收

- [ ] 表头正确：`video_id,track_id,subject_id,valid_from_frame,valid_to_frame,review_status,reviewer,annotation_version,notes`
- [ ] 每个有效的 track_id 都有一条或多条映射记录
- [ ] subject_id 格式为 `P001`, `P002`...
- [ ] FP 轨迹在 subject_id 列填 null（或空），review_status 填 `fp`
- [ ] 断裂后合并的轨迹有多条记录（每条对应一个时间段）
- [ ] `annotation_version` 一致
- [ ] 无误检轨迹被分配了 subject_id
- [ ] 无 DeepSORT 原始 track_id 被直接复制为 subject_id（即使该轨迹看起来正确）——必须有人工确认记录

---

## 七、日志和文档验收

### 7.1 运行日志

每个子任务（检测、跟踪、复核）应生成 `logs/runs/<RunID>.md`，包含：

- [ ] Run ID
- [ ] 日期
- [ ] 实验目的
- [ ] 环境（Conda 环境名、关键包版本）
- [ ] 输入文件（含 SHA-256）
- [ ] Git commit（T01 时可能无 Git，记录"尚未初始化 Git"）
- [ ] 完整运行命令（可直接复制粘贴重新运行）
- [ ] 所有参数
- [ ] 输出文件列表
- [ ] 定量结果（轨迹数、帧数、检测数、处理速度等）
- [ ] 可视化结果路径
- [ ] 异常和失败（如有）
- [ ] 原因分析（如有异常）
- [ ] 下一步计划
- [ ] 是否可以用于论文（T01 阶段通常为"否"）

### 7.2 每日日志

- [ ] `logs/daily/YYYY-MM-DD.md` 已更新
- [ ] 记录了当日完成的工作、遇到的问题和决定

---

## 八、不通过条件（任何一条触发即为未通过）

以下任一情况出现，T01 MOT 阶段视为未通过：

1. **输入视频无法读取**
2. **YOLO 检测输出全空（所有帧检测到 0 人）**
3. **DeepSORT 无输出或输出全为同一 track_id**
4. **mtt.txt 格式与 MOTChallenge 标准不一致**
5. **可视化视频无法播放或 ID 标注不可辨**
6. **JSONL 行数与视频总帧数不一致**
7. **subject_map.csv 中存在 DeepSORT track_id 直接复制为 subject_id 且无人工确认**
8. **FP 轨迹未被标记**
9. **复核日志缺失或无法追溯到具体修正**
10. **运行日志缺失关键信息（命令、参数、输出、异常）**
11. **任何实验结论使用"效果好""跟踪稳定"等无定量证据表述**
12. **原始视频被覆盖或修改**
13. **原始 DeepSORT 输出 (data/mot/raw/) 被覆盖**

---

## 九、通过条件总结

T01 MOT 阶段通过 = 所有验收项标记为 [x] + 零条不通过条件触发 + 用户确认复核结果。

通过后：
- 将 T01 状态更新为 `COMPLETED`
- 将 T02-T06 标记为可开始（依赖 T01 的前置条件已满足）
- 不自动开始 T07（OpenPose 安装需单独批准）

---

## 十、与论文的关系

T01 MOT 阶段的输出**不能直接用于论文**。原因：
- 本次仅为单段 10-30 秒视频的最小测试
- 自动跟踪结果未经定量的精度评估
- 人工复核规范（MOT_ANNOTATION_PROTOCOL.md）的可行性本身也需要验证

T01 的价值在于：
- 验证环境、工具链、数据格式
- 验证人工复核流程可操作
- 为后续大规模处理建立模板
- 发现环境配置和代码中的早期问题
