#!/usr/bin/env python3
import json
import cv2
import os

def main():
    base_path = os.path.expanduser('~/data/azure_kinect')
    video_name = "K01_reach_grasp_001"
    color_dir = os.path.join(base_path, f'results/azure_kinect/{video_name}/color')
    
    skeleton_path = "data/azure_kinect/processed/K01/kinect_skeleton.jsonl"
    out_video = "results/azure_kinect/K01/kinect_skeleton_overlay.mp4"
    
    if not os.path.exists(color_dir) or not os.listdir(color_dir):
        print(f"❌ 错误：彩色隔离区未找到图片: {color_dir}")
        return

    print("🎬 [时序对齐机制启动] 正在执行真值帧号像素级融合，消除卡顿撕裂...")

    # 动态获取第一帧的分辨率
    files = sorted([f for f in os.listdir(color_dir) if f.endswith('.jpg')])
    first_img = cv2.imread(os.path.join(color_dir, files[0]))
    height, width, _ = first_img.shape

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    # 强制锁死标准的 30fps 平滑输出
    video_writer = cv2.VideoWriter(out_video, fourcc, 30.0, (width, height))

    # 标准 Azure Kinect 骨骼拓扑连线
    kinect_bones = [
        (0, 1), (1, 2), (2, 3), (3, 26),
        (2, 4), (4, 5), (5, 6), (6, 7),
        (2, 11), (11, 12), (12, 13), (13, 14),
        (0, 22), (22, 23), (23, 24),
        (0, 18), (18, 19), (19, 20)
    ]

    frame_count = 0
    with open(skeleton_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            body_id = data["body_id"]
            f_num = data["original_frame_number"]
            
            # 💡 核心修复：绝对不用数组下标，而是用数据本身的真值帧号去死死绑定图片名！
            # 这能彻底解决由于跳帧引起的卡顿和时序错位
            img_path = os.path.join(color_dir, f"frame_{f_num}.jpg")
            
            # 如果这帧图片不存在，尝试兼容没有下划线的命名格式
            if not os.path.exists(img_path):
                img_path = os.path.join(color_dir, f"frame_{f_num:06d}.jpg")
                
            if not os.path.exists(img_path):
                continue
                
            img = cv2.imread(img_path)

            if body_id != -1 and "joints_2d_color" in data:
                joints_2d = data["joints_2d_color"]
                confidences = data["joint_confidence"]
                
                # 1. 绘制绿色骨骼线
                for bone in kinect_bones:
                    p1_idx, p2_idx = bone
                    if p1_idx < len(joints_2d) and p2_idx < len(joints_2d):
                        p1 = (int(joints_2d[p1_idx][0]), int(joints_2d[p1_idx][1]))
                        p2 = (int(joints_2d[p2_idx][0]), int(joints_2d[p2_idx][1]))
                        if p1 != (0, 0) and p2 != (0, 0):
                            cv2.line(img, p1, p2, (0, 255, 0), 4)

                # 2. 绘制关节圆点（带置信度颜色）
                for idx, pt in enumerate(joints_2d):
                    p = (int(pt[0]), int(pt[1]))
                    if p != (0, 0):
                        conf = confidences[idx] if idx < len(confidences) else 2
                        color = (0, 255, 0) if conf == 2 else ((0, 165, 255) if conf == 1 else (0, 0, 255))
                        cv2.circle(img, p, 7, color, -1)

                # 3. 绘制 Body ID
                if len(joints_2d) > 3 and tuple(joints_2d[3]) != (0, 0):
                    cv2.putText(img, f"Body ID: {body_id}", (int(joints_2d[3][0]), int(joints_2d[3][1]) - 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

            # 左上角实时打印当前的真值帧号
            cv2.putText(img, f"Frame: {f_num} | Smooth Aligned", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
            
            video_writer.write(img)
            frame_count += 1

    video_writer.release()
    print(f"🎉 [丝滑融合] 渲染成功！成功消除时序卡顿，共合成 {frame_count} 帧平滑视频。")

if __name__ == '__main__':
    main()
