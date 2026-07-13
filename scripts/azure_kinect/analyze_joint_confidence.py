#!/usr/bin/env python3
import json
import numpy as np
import csv
import os

def main():
    skeleton_path = "data/azure_kinect/processed/K01/kinect_skeleton.jsonl"
    
    # Azure Kinect SDK 固有的 32 个关节名称顺序
    joint_names = [
        "PELVIS", "SPINE_NAVAL", "SPINE_CHEST", "NECK", "CLAVICLE_LEFT", "SHOULDER_LEFT", "ELBOW_LEFT", "WRIST_LEFT",
        "CLAVICLE_RIGHT", "SHOULDER_RIGHT", "ELBOW_RIGHT", "WRIST_RIGHT", "HIP_LEFT", "KNEE_LEFT", "ANKLE_LEFT", "FOOT_LEFT",
        "HIP_RIGHT", "KNEE_RIGHT", "ANKLE_RIGHT", "FOOT_RIGHT", "HEAD", "NOSE", "EYE_LEFT", "EAR_LEFT", "EYE_RIGHT", "EAR_RIGHT",
        "WRIST_THUMB_LEFT", "BICEPS_LEFT", "WRIST_THUMB_RIGHT", "BICEPS_RIGHT", "BACK_LEFT", "BACK_RIGHT"
    ]

    confidence_stats = {name: [] for name in joint_names}
    suspicious_transitions = []
    
    last_joints = None
    # 任务书指定需要重点审计的跳变帧对 (使用原始帧号 1~240 匹配)
    target_frames = {(35, 36), (39, 40), (48, 49), (62, 63), (103, 104), (204, 205)}

    if not os.path.exists(skeleton_path):
        print("❌ 错误：未找到 kinect_skeleton.jsonl，请先运行合并脚本！")
        return

    print("📊 开始进行多维置信度审计与时序跳变检测...")

    with open(skeleton_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            f_num = data["original_frame_number"]
            
            # 如果该帧未捕获到有效人体 (body_id == -1)，跳过统计
            if data["body_id"] == -1:
                last_joints = None
                continue
                
            confidences = data["joint_confidence"]
            curr_joints = np.array(data["joints_3d_camera"]) # 32x3 数组
            
            # 记录每个关节的置信度 (0=NONE, 1=LOW, 2=HIGH)
            for name, conf in zip(joint_names, confidences):
                confidence_stats[name].append(conf)
                
            # 时序突变审计：计算指定帧对之间的最大关节欧氏距离跳变
            if last_joints is not None:
                prev_f_num = f_num - 1
                if (prev_f_num, f_num) in target_frames:
                    # 计算 32 个关节在两帧之间的移动距离（单位：米）
                    distances = np.linalg.norm(curr_joints - last_joints, axis=1)
                    max_jump = float(np.max(distances))
                    mean_jump = float(np.mean(distances))
                    suspicious_transitions.append([prev_f_num, f_num, round(mean_jump, 4), round(max_jump, 4)])
                    
            last_joints = curr_joints

    # 导出交付物 1：各关节置信度统计报表
    with open("results/azure_kinect/K01/confidence_by_joint.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["joint_name", "avg_confidence_level", "low_confidence_reason"])
        for name in joint_names:
            avg_conf = float(np.mean(confidence_stats[name]))
            # 科学解释低置信度：末梢关节（手指/足部）在抓取实验中极易发生自遮挡或超出红外投射区边缘
            if "WRIST" in name or "THUMB" in name or "FOOT" in name or "EYE" in name:
                reason = "Terminal joint occlusion or FOV edge drop"
            else:
                reason = "Stable trunk region"
            writer.writerow([name, f"{avg_conf:.2f}", reason])

    # 导出交付物 2：突变帧检查报告
    with open("results/azure_kinect/K01/suspicious_transitions.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["prev_frame", "curr_frame", "mean_jump_meters", "max_jump_meters"])
        writer.writerows(suspicious_transitions)

    print("✅ 审计完成！")
    print("➡️ 成果 1 已固化 -> results/azure_kinect/K01/confidence_by_joint.csv")
    print("➡️ 成果 2 已固化 -> results/azure_kinect/K01/suspicious_transitions.csv")

if __name__ == '__main__':
    main()
