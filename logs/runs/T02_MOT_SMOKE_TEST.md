# Run ID: 20260711_T02_001

- 日期：2026-07-11
- 实验目的：验证单段本地多人视频的 YOLO person 检测与 DeepSORT 自动预标注流水线。
- 当前状态：自动流水线、人工复核文件和 subject map 已重新验收通过；T02 已关闭。
- 环境：`motpose`，Python 3.10.20，PyTorch 2.5.1+cu121，torchvision 0.20.1+cu121，cuDNN 9.1，OpenCV 5.0.0，ultralytics 8.4.57，deep-sort-realtime 1.3.2，FFmpeg 4.2.7，NVIDIA GeForce RTX 3090。
- 输入文件：`data/raw_videos/three-people-walking.mp4`，SHA-256 `1dafa3880927509e0549c16f8657f0af89498bf2f67a47c006f99e5b648b0ccd`，H.264，2160x3840，23.976 FPS，240 帧，10.01 秒。
- 代码版本或 Git commit：`3411faf6e8de579a38d94a73c2e9339b0043b13b`
- 参数：`yolov8n.pt`（SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`），person class 0，conf 0.3，IoU 0.45，imgsz 640，DeepSORT max_age 30，n_init 3，nn_budget 100，max_cosine_distance 0.2，max_iou_distance 0.7，Mobilenet GPU embedder，seed 42。
- 输出文件：raw 输出为 `results/mot/three-people-walking/tracked.mp4`、`tracks_raw.jsonl`、`mot/gt.txt`、`mot/labels.txt`、`metadata.json`；人工复核输出为 `data/mot/reviewed/three-people-walking.csv` 和 `data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv`。
- 定量结果：处理 240/240 帧；723 个 person 检测；715 条自动轨迹帧记录；raw 中有 4 个 track_id。ID 1/2/3 各 238 帧；ID 4 仅出现在第 86 帧，conf=`0.343935`（三位小数为 `0.344`），人工确认是 False Positive。检测 62.291 FPS；跟踪 31.965 FPS；最终视频 H.264/yuv420p、240 帧、10.010 秒。
- 可视化结果：`results/mot/three-people-walking/tracked.mp4`。人工最终判定第 86 帧 `track_id 4` 没有对应真实人物；该判定优先于先前抽样观察。
- 失败与异常：初始环境缺少 FFmpeg，用户批准后安装 4.2.7；APT 的无关 `antigravity` 第三方源索引超时但 Ubuntu 镜像可用；DeepSORT 依赖 `pkg_resources`，已固定 setuptools 80.9.0；OpenCV `avc1` 硬件编码失败后以 mp4v 写入并由 FFmpeg/libx264 转为 H.264；系统 `ldconfig` 报告 CUDA 11.3 目录中手工 cuDNN 8 文件不是符号链接，未修改；`PYTHONPATH` 注入 ROS Foxy Python 3.8 路径，实际命令通过 `env -u PYTHONPATH` 隔离。
- 原因分析：OpenCV wheel 尝试 `h264_v4l2m2m`，本机没有可用 V4L2 H.264 编码设备；因此采用可复现的软件编码回退。`deep-sort-realtime 1.3.2` 发布较早，仍依赖已弃用的 `pkg_resources`。
- 下一步计划：保留 raw 输出不变；所有下游 OpenPose 关联和数据集生成只读取 subject map 中 `include_for_pose=1` 的 ID 1/2/3，排除 ID 4。本轮不开始新实验。
- 是否可以用于论文：否。当前仅为单视频 smoke test 与人工复核样例，未进行公开 MOT 真值评估。

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

## 执行历史与日终核对

流水线今天实际执行三次；只有最后一次输出被保留：

1. 首次执行使用本地视频和 Run ID `20260711_T02_001`，当时系统无 FFmpeg CLI。OpenCV `avc1` 失败后生成 MPEG-4 输出，用于发现编码回退和 metadata 环境名问题。
2. 安装 FFmpeg并提交代码 `29cda6e` 后，以相同参数加 `--overwrite` 重跑。输出经 libx264 转为 H.264，用于格式与抽样可视检查。
3. 提交高对比度标注修复 `3411faf` 后，以日志“完整命令”再次加 `--overwrite` 重跑；当前 5 个输出文件均来自这次最终运行。前两次的中间输出已被同一脚本覆盖，不能作为独立实验结果引用。

日终只读核对时间：2026-07-11 18:47:36 CST。

```text
tracked.mp4       48,385,300 bytes  sha256 c3f3a203430e56af1f1b6f5061dd4129bb1f15bda76d3d017a89ca8bb447b605
tracks_raw.jsonl     132,968 bytes  sha256 6d0650897c2bf7efa509cb384a2bdbbeeeba78f9e6cd035caa36df6e1c595869
mot/gt.txt            47,663 bytes  sha256 d8828313bf25449286cb17f8366e57e6ec51b7d578354d15f9a84376500fa881
mot/labels.txt            56 bytes  sha256 168064dcf53459756ca094efdc5a049b34d2727b57dc5d7036035a583410990c
metadata.json           2,539 bytes  sha256 b0d44c4e6cd67614900bd66ff744cc3057d946b1e95da304ebc16dc2d0a1b07d
```

### 人工复核修订与重新验收（2026-07-12）

- `data/mot/reviewed/three-people-walking.csv` 将第 86 帧 `track_id 4` 标记为 `confirmed_false_positive`，`include_in_main_dataset=0`。
- `data/mot/reviewed/subject_maps/three-people-walking_subject_map.csv` 仅包含 `1->P001`、`2->P002`、`3->P003`，不存在 ID 4 映射。
- reviewed CSV SHA-256：`85c2261629156b8cd673d010882d25e9219ed812d7909cced375b57eb58b0643`；subject map SHA-256：`5d451ef1cc3dbbeccc4d200dd5b8b996f98daa7e6a110c0fd344406642a79dbb`。
- P001/P002/P003 均为 frame 0-239 的 `main_subject` 且 `include_for_pose=1`。
- raw 五个输出文件未修改；人工复核结论仅保存在 reviewed 层。
- T02 自动输出、人工复核和 subject map 重新验收通过。仍未进行公开 MOT 真值评估，不能报告 MOTA、IDF1 或 HOTA。
