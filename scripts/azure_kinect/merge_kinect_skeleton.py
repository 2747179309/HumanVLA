#!/usr/bin/env python3
import json
import os

def main():
    # 定义输入与输出路径
    base_dir = "data/azure_kinect/processed/K01/"
    s2d_path = os.path.join(base_dir, "skeleton_2d_raw.jsonl")
    s3d_path = os.path.join(base_dir, "skeleton_3d_raw.jsonl")
    output_path = os.path.join(base_dir, "kinect_skeleton.jsonl")
    
    # 检查原材料是否存在
    if not os.path.exists(s2d_path) or not os.path.exists(s3d_path):
        print("❌ 错误：未在预期路径找到 skeleton_2d_raw.jsonl 或 skeleton_3d_raw.jsonl！")
        return

    print("🔄 开始合并 2D 与 3D 骨架数据流，重构双索引结构...")
    
    count = 0
    with open(s2d_path, 'r', encoding='utf-8') as f2d, \
         open(s3d_path, 'r', encoding='utf-8') as f3d, \
         open(output_path, 'w', encoding='utf-8') as fout:
         
        # 逐行读取，保持时间戳严格对齐
        for idx, (line_2d, line_3d) in enumerate(zip(f2d, f3d)):
            data_2d = json.loads(line_2d.strip())
            data_3d = json.loads(line_3d.strip())
            
            # 核心：构建标准化双索引结构
            merged_frame = {
                "frame_index": idx,                              # 任务要求：派生数据新增 0～239 索引
                "original_frame_number": data_3d["frame_index"],  # 任务要求：原始帧号 1～240 保持不变
                "timestamp_usec": data_3d["timestamp_usec"],
                "body_id": data_3d["body_id"],
                "joints_3d_camera": data_3d["joints_3d_camera"],
                "joints_2d_color": data_2d["joints_2d_color"],
                "joint_confidence": data_3d["joint_confidence"]
            }
            
            # 写入统一的交付文件
            fout.write(json.dumps(merged_frame, ensure_ascii=False) + '\n')
            count += 1
            
    print(f"✅ 成功！已合并 {count} 帧数据，最终统一骨架已固化至: {output_path}")

if __name__ == '__main__':
    main()
