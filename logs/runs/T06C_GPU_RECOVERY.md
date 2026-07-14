# T06C-R NVIDIA GPU Recovery

## Run 信息

- Run ID：`20260713_T06C_R_GPU_001`
- 日期：2026-07-13
- 目的：诊断并在授权边界内恢复T06C所需NVIDIA设备与OpenPose CUDA运行环境。
- 状态：阶段A完成；阶段B模拟通过但实际提权被Codex受限环境阻止；阶段D/E未执行。
- 是否可用于论文：否，仅为环境运维记录。

## 原始证据

- 完整只读诊断：`results/system/T06C_gpu_diagnostic.txt`
- SHA-256：`b5d9fda2c6801b92328f1a0e4f2cac55ff17dc4eb6d1a6f085f38857b5acac50`
- 阶段B模拟及失败输出：`results/system/T06C_gpu_recovery.txt`
- SHA-256：`33d1b2599aa7cad376cee4050dae6130a445635e1990f0b47229dae5d2729ee2`

## 阶段A结论

分类：**G — NVIDIA模块正常，但当前运行环境没有创建/暴露 `/dev/nvidia*` 设备节点。**

排除依据：

- A排除：PCI `02:00.0` 可见，型号由`/proc`确认为NVIDIA GeForce RTX 3090。
- B/C排除：`nvidia`、`nvidia_modeset`、`nvidia_drm`、`nvidia_uvm`均已加载，PCI显示`Kernel driver in use: nvidia`。
- D排除：Secure Boot不受支持/未启用；模块虽记录signature taint，但已实际加载并绑定GPU，不是加载阻断。
- E排除：DKMS 550.144.03已为当前`5.15.0-139-generic`安装；对应headers包存在且`/lib/modules/.../build`有效。
- F排除：内核模块、`nvidia-driver-550`、`nvidia-utils-550`、NVML/compute库均为550.144.03；未发现driver/library version mismatch。
- H尚不能评估：GPU节点未恢复前，OpenPose CUDA探针必然失败。

支持G的直接证据：

- `/dev/nvidia*`不存在。
- `nvidia-smi`退出9，无法与驱动通信。
- `nvidia-modprobe`包未安装。
- 当前受限环境中`/dev`为`a531:a531`，`/usr/bin/sudo`显示为`nobody:nogroup`，说明设备与提权能力处在受限命名空间，不能据此断言主机普通终端也缺少设备节点。

内核日志还记录多次`nvidia-drm Failed to grab modeset ownership`。这不是本次分类为F/D的证据，但若主机终端同样无法使用GPU，应在恢复设备节点后继续观察。

## 阶段B执行记录

模块已经加载，因此没有重复执行`modprobe nvidia*`。

APT模拟命令：

```bash
apt-cache policy nvidia-modprobe
apt-get --simulate install --no-install-recommends nvidia-modprobe
```

真实结果：候选版本`465.24.02-1~ubuntu20.04.1`；模拟显示仅新增`nvidia-modprobe`，升级0、删除0。

尝试的授权低风险安装：

```bash
sudo apt-get install -y --no-install-recommends nvidia-modprobe
```

安装在APT执行前失败：

```text
sudo: /usr/bin/sudo 必须属于用户 ID 0(的用户)并且设置 setuid 位
```

没有安装软件包，没有执行`nvidia-modprobe`，没有创建或伪造设备节点，没有修改驱动。

## 需要用户在主机普通终端执行

先判断故障是否仅存在于Codex受限环境：

```bash
ls -l /dev/nvidia* 2>&1
nvidia-smi
```

若主机终端同样缺少节点，再执行已模拟确认的低风险步骤：

```bash
sudo apt-get install -y --no-install-recommends nvidia-modprobe
sudo nvidia-modprobe -u -c=0
ls -l /dev/nvidia*
nvidia-smi
```

此时不需要重装/切换驱动，不需要修改内核、GRUB或Secure Boot，也没有证据要求重启。若`nvidia-smi`报告新的driver/library mismatch，停止并优先请求用户批准重启。

## 阶段D/E状态

- `/dev/nvidia0`、`/dev/nvidiactl`、`/dev/nvidia-uvm`：当前Codex环境未恢复。
- `nvidia-smi`：未恢复。
- OpenPose单帧BODY_25 CUDA探针：本轮未重试；上一探针仍为CUDA error 100。
- 完整345帧OpenPose与T06C后续：未执行。
- 未重跑DeepSORT，未处理E002-E012，未修改T06C实验结果。

## P001确认更新

用户已人工确认`track_id=1`始终属于主操作者，正式映射为`P001`；frame 0-1继续因DeepSORT `n_init`确认期保持missing。subject map和track review只更新确认状态，不修改raw轨迹。

## 宿主机复核与运行脚本

- 用户在普通宿主机终端确认`/dev/nvidia0`、`/dev/nvidiactl`、`/dev/nvidia-uvm`等节点存在，`nvidia-smi`正常识别RTX 3090。
- 根因最终确认：Codex受限执行环境没有GPU设备访问权限；宿主机驱动无需修复。
- 不执行驱动重装、重启、系统配置修改或`nvidia-modprobe`安装。
- 新建`scripts/run_t06c_openpose_host.sh`，供用户在普通宿主机终端执行。
- 脚本通过`bash -n`和`--help`；本机没有`shellcheck`，未运行该检查器。
- Codex受限环境中没有实际执行OpenPose，也没有重跑DeepSORT。

脚本执行顺序：GPU节点/`nvidia-smi`检查 → 现有DeepSORT/P001映射校验 → E001 frame 0 BODY_25 CUDA探针 → JSON/渲染图/核心关节验证 → 完整345帧OpenPose → JSON和rendered视频验证。

默认拒绝已有OpenPose输出。显式`--overwrite`只把旧目录移动到时间戳备份，不删除历史结果。stdout/stderr追加保存到`logs/runs/T06C_OPENPOSE_HOST_RUN.log`。

首次运行命令：

```bash
cd /home/a531/HumanVLA
bash scripts/run_t06c_openpose_host.sh
```
