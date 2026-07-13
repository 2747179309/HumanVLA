#!/usr/bin/env python3
import os
import json
import cv2

# Azure Kinect 的标准骨骼连线
KINECT_BONES = [
    (0, 1), (1, 2), (2, 3), (3, 26),
    (2, 4), (4, 5), (5, 6), (6, 7),
    (2, 11), (11, 12), (12, 13), (13, 14),
    (0, 22), (22, 23), (23, 24),
    (0, 18), (18, 19), (19, 20)
]

# ====== 🛠️ 确保这里的名字和实时录制的名字完全对齐 ======
VIDEO_NAME = "kinect_ros_live_001" 
# ===================================================

def main():
    base_path = os.path.expanduser('~/data/azure_kinect')
    
    # 定位到专属隔离区
    color_dir = os.path.join(base_path, f'datasets/{VIDEO_NAME}/color')
    meta_dir = os.path.join(base_path, f'datasets/{VIDEO_NAME}/metadata')
    vis_dir = os.path.join(base_path, f'datasets/{VIDEO_NAME}/visualizations')
    
    os.makedirs(vis_dir, exist_ok=True)
    output_video_path = os.path.join(vis_dir, 'verification_result.mp4')

    if not os.path.exists(color_dir) or not os.listdir(color_dir):
        print(f"❌ 错误：在隔离区未找到解包后的彩色图片！请先确保运行了图片解包命令。")
        return

    # 过滤并排序隔离区中所有的单帧图片
    color_files = sorted([f for f in os.listdir(color_dir) if f.endswith('.jpg')])
    
    # 读取第一帧来获取视频分辨率
    first_img_path = os.path.join(color_dir, color_files[0])
    first_img = cv2.imread(first_img_path)
    height, width, _ = first_img.shape

    print(f"🎬 [第四阶段] 开始读取隔离区 {VIDEO_NAME} 的单帧高精数据，正在合成质检视频...")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(output_video_path, fourcc, 30.0, (width, height))

    for frame_file in color_files:
        # 从文件名提取帧号，例如从 frame_000001.jpg 提取出 1
        frame_index_str = frame_file.split('_')[1].split('.')[0]
        frame_index = int(frame_index_str)
        
        img_path = os.path.join(color_dir, frame_file)
        img = cv2.imread(img_path)

        # 动态去 metadata 隔离区读取对应帧的 ROS2 高精骨骼 JSON
        json_path = os.path.join(meta_dir, f'frame_{frame_index:06d}.json')
        joints_2d = []

        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
                joints_2d = data.get("joints_2d_color", [])

        # 强行硬渲染红绿骨骼线
        if len(joints_2d) > 0:
            # 1. 绘制绿色骨骼连线
            for bone in KINECT_BONES:
                p1_idx, p2_idx = bone
                if p1_idx < len(joints_2d) and p2_idx < len(joints_2d):
                    p1 = (int(joints_2d[p1_idx][0]), int(joints_2d[p1_idx][1]))
                    p2 = (int(joints_2d[p2_idx][0]), int(joints_2d[p2_idx][1]))
                    # 过滤无效的原点
                    if p1 != (0, 0) and p2 != (0, 0):
                        cv2.line(img, p1, p2, (0, 255, 0), 4)

            # 2. 绘制红色关节圆点
            for pt in joints_2d:
                p = (int(pt[0]), int(pt[1]))
                if p != (0, 0):
                    cv2.circle(img, p, 7, (0, 0, 255), -1)

            # 3. 绘制 Body ID
            if len(joints_2d) > 3 and tuple(joints_2d[3]) != (0, 0):
                cv2.putText(img, "Body ID: 1", (int(joints_2d[3][0]), int(joints_2d[3][1]) - 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

        # 绘制帧号
        cv2.putText(img, f"Frame: {frame_index}", (50, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        
        video_writer.write(img)

    cap.release() if 'cap' in locals() else None
    video_writer.release()
    print(f"\n🎉 [真值渲染成功] 官方高精实时骨骼质检视频已生成！")
    print(f"📂 视频安全保存在: {output_video_path}")

if __name__ == '__main__':
    main()
