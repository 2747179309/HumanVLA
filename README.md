# HumanVideo2VLA

HumanVideo2VLA 是一个从普通多人操作视频构建语言对齐机器人策略数据集的低成本研究框架。本仓库当前聚焦可审计的数据构建流水线，而不是训练通用 VLA 基础模型。

## 当前阶段

第一阶段流水线：

```text
原始多人视频
  -> YOLO person 检测
  -> DeepSORT 多目标跟踪（局部 track_id）
  -> CVAT 人工复核与修正
  -> track_id 到全局 subject_id 映射
  -> OpenPose BODY_25
  -> 骨架与修正轨迹关联
  -> 动作阶段与语言标注
  -> 结构化数据集
```

DeepSORT 输出不是人工真值；OpenPose `people` 数组下标也不是稳定身份。具体约束见 [AGENTS.md](AGENTS.md) 和 [数据模式](context/DATA_SCHEMA.md)。

## 快速入口

- 当前任务：`tasks/CURRENT_TASK.md`
- 环境审计：`environment/system_info.txt`
- 安装与执行计划：`environment/setup_notes.md`
- 项目上下文：`context/PROJECT_CONTEXT.md`
- 任务报告：`tasks/CODEX_REPORT.md`

任何安装前先阅读 `environment/setup_notes.md`。当前尚未安装 OpenPose、模型权重或 CVAT。
