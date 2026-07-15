# Run Log: K02-STATUS-AUDIT

**Run ID**: 20260715_K02_STATUS_AUDIT
**日期**: 2026-07-15
**任务**: Azure Kinect 支线现状审计
**分支**: `azure-kinect` @ `e676660`
**审计人**: Claude

---

## 执行摘要

对 `azure-kinect` 分支进行了全面审计。检查了 2 个提交、13 个文件、7 个脚本、240 帧 K01 数据和 5 个结果文件。

**结论**: K02 部分完成。数据提取管道功能可用，但存在多个关键技术问题需在进入 K03 前修复。核心问题包括：硬编码相机内参导致 2D 投影不准确、2D 坐标非独立测量、合并逻辑使用危险的 zip() 静默截断、右臂 3D 跟踪质量严重不足。

---

## 审计范围

### 文件检查
- [x] `AGENTS.md`
- [x] `context/KINECT_TO_BODY25_MAPPING.csv` (27 行, 完整 25 关节)
- [x] `context/DATA_SCHEMA.md`
- [x] `context/PROJECT_CONTEXT.md`
- [x] `context/RESEARCH_SCOPE.md`
- [x] `context/PAPER_CLAIMS.md`
- [x] 全部 tasks/ 文件
- [x] 全部 scripts/azure_kinect/ 脚本
- [x] 全部 data/azure_kinect/ 文件
- [x] 全部 results/azure_kinect/ 文件

### 数据验证
- [x] 240/240 frame_sync.csv 行数 (241 含表头)
- [x] 240/240 kinect_skeleton.jsonl 行数
- [x] frame_index 连续性 (0-239)
- [x] original_frame_number 连续性 (1-240)
- [x] 时间戳单调递增
- [x] 32 关节 3D/2D/confidence 维度
- [x] NaN/Inf 检查
- [x] body_id 稳定性 (无切换)
- [x] 重投影误差 (当前 0.000，因 2D 由投影计算)
- [x] 骨长稳定性分析
- [x] 置信度分布分析

---

## 真实命令

```bash
# Git 状态检查
git branch --show-current
git log --oneline -20
git log --oneline main..azure-kinect
git status --short | head -80
git log --stat e676660 -1
git log --stat 8fd69ae -1
git diff --stat main..azure-kinect

# 目录结构
find scripts/azure_kinect/ -type f | sort
find data/azure_kinect/ -type f
find results/azure_kinect/ -type f
find logs/runs/ -type f

# 数据行数
wc -l data/azure_kinect/processed/K01/*.jsonl
wc -l data/azure_kinect/processed/K01/frame_sync.csv

# 完整性验证
python3 -c "
import json
with open('data/azure_kinect/processed/K01/kinect_skeleton.jsonl') as f:
    prev_ts = -1
    for i, line in enumerate(f):
        d = json.loads(line)
        assert d['frame_index'] == i
        assert d['original_frame_number'] == i + 1
        assert d['timestamp_usec'] > prev_ts
        prev_ts = d['timestamp_usec']
        if d['body_id'] == 1:
            assert len(d['joints_3d_camera']) == 32
            assert len(d['joints_2d_color']) == 32
            assert len(d['joint_confidence']) == 32
print('All 240 frames pass integrity checks')
"

# 重投影分析
python3 -c "
import json
fx, fy, cx, cy = 912.0, 911.0, 956.0, 545.0
with open('data/azure_kinect/processed/K01/kinect_skeleton.jsonl') as f:
    all_errors = []
    for line in f:
        d = json.loads(line)
        for j in range(32):
            x,y,z = d['joints_3d_camera'][j]
            u_sdk, v_sdk = d['joints_2d_color'][j]
            if z > 0:
                r_u = x*fx/z + cx
                r_v = y*fy/z + cy
                err = ((r_u-u_sdk)**2 + (r_v-v_sdk)**2)**0.5
                all_errors.append(err)
import statistics
print(f'Mean: {statistics.mean(all_errors):.3f}px, Max: {max(all_errors):.3f}px')
"

# 骨长分析
python3 -c "
[骨长稳定性计算 - 见审计报告第六节]
"

# 置信度分析
python3 -c "
[置信度分布 - 见审计报告第六节]
"
```

---

## 发现汇总

### 关键发现 (CRITICAL)

1. 🔴 **zip() 静默截断**: `merge_kinect_skeleton.py:25` 使用 `zip(f2d, f3d)` 合并文件，行数不一致时静默丢失数据
2. 🔴 **硬编码内参**: `build_dataset.py:22` 使用 `fx=912,fy=911,cx=956,cy=545`，非设备实际标定值
3. 🔴 **循环投影**: 2D 坐标由 3D + 硬编码内参计算而来，不是独立测量（重投影误差恒为 0）
4. 🔴 **右臂数据不可靠**: 右肩-肘骨长 6.6cm (正常~25cm)，变异 91.6%
5. 🔴 **硬编码绝对路径**: 5 个脚本包含 `/home/lcy/` 或 `os.path.expanduser()` 路径

### 高优先级发现 (HIGH)

6. 🟡 **置信度映射错误**: `analyze_joint_confidence.py` 将 SDK level 2 标为 "HIGH"，实际为 "MEDIUM"
7. 🟡 **低置信度原因编造**: 基于关节名称模式而非实际观察分配原因
8. 🟡 **42.3% 关节低置信度**: 全部关节中仅 57.7% 达到 MEDIUM 置信度
9. 🟡 **缺失必需字段**: video_id, color_ts, depth_ts, reference_valid 等
10. 🟡 **视觉复核 FAIL**: 骨架叠加存在系统性几何偏移

### 中等优先级 (MEDIUM)

11. 🟡 **缺少 SHA-256 清单**
12. 🟡 **缺少时间同步独立验证报告**
13. 🟡 **无 K02 验收标准和学习文档** (本次审计创建)
14. 🟡 **K01 与主线 E001 非同次操作**，不能逐帧对比
15. 🟡 **数据重复**: K01 数据同时存在于 repo 根目录和 data/azure_kinect/

---

## 后续步骤

1. 执行 K02A-R1 到 K02A-R10 修正任务（详见 `tasks/K02_ACCEPTANCE_CRITERIA.md`）
2. 完成后重新运行全部验证
3. Claude 验收通过后进入 K03

---

## 人工确认事项

见 `tasks/K02_STATUS_AUDIT.md` 第十一节。
