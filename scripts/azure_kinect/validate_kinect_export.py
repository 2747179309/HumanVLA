#!/usr/bin/env python3
import json
import os

def main():
    skeleton_path = "data/azure_kinect/processed/K01/kinect_skeleton.jsonl"
    csv_path = "data/azure_kinect/processed/K01/frame_sync.csv"
    
    # 1. 检查交付文件是否存在
    if not os.path.exists(csv_path):
        print("❌ 错误：未找到 frame_sync.csv！")
        return
        
    if not os.path.exists(skeleton_path):
        print("❌ 错误：未找到 kinect_skeleton.jsonl，请先运行合并脚本！")
        return

    print("🔍 开始对 240 帧数据进行全方位质量复核...")
    
    # 2. 核对同步表行数
    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_lines = len(f.readlines()) - 1  # 扣除表头
        if csv_lines != 240:
            print(f"⚠️ 警告：frame_sync.csv 包含 {csv_lines} 帧，预期 240 帧")

    last_ts = -1
    frame_count = 0
    
    # 3. 逐帧强校验
    with open(skeleton_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            data = json.loads(line.strip())
            frame_count += 1
            
            # 强验指标 1：派生索引必须从 0 开始且严格连续
            assert data["frame_index"] == i, f"❌ 第 {i} 行派生索引异常，读取值为 {data['frame_index']}"
            
            # 强验指标 2：原始帧号必须从 1 开始且严格连续 (1～240)
            assert data["original_frame_number"] == i + 1, f"❌ 第 {i} 行原始帧号不连续，读取值为 {data['original_frame_number']}"
            
            # 强验指标 3：时间戳必须严格单调递增
            ts = data["timestamp_usec"]
            assert ts > last_ts, f"❌ 第 {i} 帧时间戳未单调递增！当前: {ts}, 上一帧: {last_ts}"
            last_ts = ts
            
            # 强验指标 4：若捕获到有效人体，必须完整具备 Azure Kinect 固有的 32 个关节点
            if data["body_id"] != -1:
                assert len(data["joints_3d_camera"]) == 32, f"❌ 第 {i} 帧 3D 相机空间关节数异常"
                assert len(data["joints_2d_color"]) == 32, f"❌ 第 {i} 帧 2D 像素空间关节数异常"
                assert len(data["joint_confidence"]) == 32, f"❌ 第 {i} 帧关节置信度数量异常"
                
    print(f"✅ 质检完毕！成功复核 {frame_count} 帧数据。")
    print("✅ 帧号双索引一致性、时间戳单调递增性、32个拓扑关节边界验证 100% 通过！")

if __name__ == '__main__':
    main()
