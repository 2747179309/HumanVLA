# T01 — 新电脑环境审计与DeepSORT/OpenPose工作区初始化

## 任务内容

1. 检查但不擅自修改 Ubuntu 版本、GPU、NVIDIA 驱动、CUDA、cuDNN、Python、Conda、Git、Docker、FFmpeg、OpenCV、PyTorch 和可用磁盘空间。
2. 将真实检查结果写入 `environment/system_info.txt`。
3. 判断当前是否适合创建独立 Conda 环境 `motpose`。
4. 给出 DeepSORT、OpenPose 和 CVAT 的推荐安装方案，用户确认前不进行大规模安装。
5. 制定单段 10 至 30 秒多人视频的最小测试计划：YOLO person 检测、DeepSORT `track_id`、带 ID 视频、JSONL、MOT 格式、CVAT 人工检查，然后运行 OpenPose。
6. 不开始论文写作，不下载大数据集，不运行长时间训练。

## 当前状态

`IN_PROGRESS`。工作区初始化和只读审计已完成；软件安装、样例视频选择和最小流水线执行等待用户确认。

## 完成标准

- 环境审计有真实命令输出和明确风险。
- 用户确认安装策略后，创建隔离的 `motpose` 环境。
- 一段经确认的短视频完成 MOT、人工复核和 BODY_25 关联闭环。
- 所有运行均具备 Run ID、命令、输入、输出、指标和异常记录。
