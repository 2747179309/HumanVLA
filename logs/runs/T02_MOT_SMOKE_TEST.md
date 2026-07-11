# Run ID: 20260711_T02_001

- 日期：2026-07-11
- 实验目的：验证单段本地多人视频的 YOLO person 检测与 DeepSORT 自动预标注流水线。
- 当前状态：自动流水线已运行并通过格式检查；完整人工轨迹复核未完成。
- 环境：`motpose`，Python 3.10.20，PyTorch 2.5.1+cu121，torchvision 0.20.1+cu121，cuDNN 9.1，OpenCV 5.0.0，ultralytics 8.4.57，deep-sort-realtime 1.3.2，FFmpeg 4.2.7，NVIDIA GeForce RTX 3090。
- 输入文件：`data/raw_videos/three-people-walking.mp4`，SHA-256 `1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd`，H.264，2160x3840，23.976 FPS，240 帧，10.01 秒。
- 代码版本或 Git commit：`3411faf6e8de579a38d94a73c2e9339b0043b13b`
- 参数：`yolov8n.pt`（SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`），person class 0，conf 0.3，IoU 0.45，imgsz 640，DeepSORT max_age 30，n_init 3，nn_budget 100，max_cosine_distance 0.2，max_iou_distance 0.7，Mobilenet GPU embedder，seed 42。
- 输出文件：`results/mot/three-people-walking/tracked.mp4`、`tracks_raw.jsonl`、`mot/gt.txt`、`mot/labels.txt`、`metadata.json`。
- 定量结果：处理 240/240 帧；723 个 person 检测；715 条已确认轨迹帧记录；4 个 track_id；ID 1/2/3 各 238 帧；ID 4 为第 86 帧的 1 帧短轨；检测 62.291 FPS；跟踪 31.965 FPS；最终视频 H.264/yuv420p、240 帧、10.010 秒。
- 可视化结果：`results/mot/three-people-walking/tracked.mp4`。抽样 10 个整秒帧并重点检查第 86、120 帧；第 120 帧三名主要人物的框、ID 和 frame_index 清晰可见。
- 失败与异常：初始环境缺少 FFmpeg，用户批准后安装 4.2.7；APT 的无关 `antigravity` 第三方源索引超时但 Ubuntu 镜像可用；DeepSORT 依赖 `pkg_resources`，已固定 setuptools 80.9.0；OpenCV `avc1` 硬件编码失败后以 mp4v 写入并由 FFmpeg/libx264 转为 H.264；系统 `ldconfig` 报告 CUDA 11.3 目录中手工 cuDNN 8 文件不是符号链接，未修改；`PYTHONPATH` 注入 ROS Foxy Python 3.8 路径，实际命令通过 `env -u PYTHONPATH` 隔离。
- 原因分析：OpenCV wheel 尝试 `h264_v4l2m2m`，本机没有可用 V4L2 H.264 编码设备；因此采用可复现的软件编码回退。`deep-sort-realtime 1.3.2` 发布较早，仍依赖已弃用的 `pkg_resources`。
- 下一步计划：完整观看输出视频并逐帧复核疑似交叉/遮挡段；重点处理第 86 帧真实背景儿童产生的单帧短轨及其周边漏检，再进入人工修正流程。不得自动开始 T03。
- 是否可以用于论文：否。当前仅为单视频自动 smoke test，且尚未完成全视频人工复核或定量 MOT 真值评估。

## 完整命令

```bash
env -u PYTHONPATH YOLO_CONFIG_DIR=/tmp \
  /home/a531/anaconda3/envs/motpose/bin/python scripts/mot/run_deepsort.py \
  --video data/raw_videos/three-people-walking.mp4 \
  --video-id three-people-walking \
  --run-id 20260711_T02_001 \
  --overwrite
```

## 输出 SHA-256

```text
c3f3a203430e56af1f1b6f5061dd4129bb1f15bda76d3d017a89ca8bb447b605  tracked.mp4
6d0650897c2bf7efa509cb384a2bdbbeeeba78f9e6cd035caa36df6e1c595869  tracks_raw.jsonl
d8828313bf25449286cb17f8366e57e6ec51b7d578354d15f9a84376500fa881  mot/gt.txt
168064dcf53459756ca094efdc5a049b34d2727b57dc5d7036035a583410990c  mot/labels.txt
b0d44c4e6cd67614900bd66ff744cc3057d946b1e95da304ebc16dc2d0a1b07d  metadata.json
```

`mot/gt.txt` 是用户指定的 MOTChallenge 交换文件名，内容仍是未经人工复核的自动预标注，不是 ground truth。
