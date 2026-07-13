#include <iostream>
#include <fstream>
#include <vector>
#include <sys/stat.h>
#include <k4a/k4a.h>
#include <k4arecord/playback.h>
#include <k4abt.h>
#include <opencv2/opencv.hpp>

// 辅助创建文件夹函数
void make_dir(std::string path) {
    mkdir(path.c_str(), 0777);
}

int main() {
    // 🎯 任务定义：你可以随时更换视频名称
    std::string video_id = "K01_reach_grasp_001";
    
    std::string base_path = "/home/lcy/data/azure_kinect/results/azure_kinect/" + video_id + "/";
    std::string mkv_path = "/home/lcy/data/azure_kinect/raw_mkv/" + video_id + ".mkv";
    
    make_dir("/home/lcy/data/azure_kinect/results/");
    make_dir("/home/lcy/data/azure_kinect/results/azure_kinect/");
    make_dir(base_path);
    make_dir(base_path + "color");
    make_dir(base_path + "depth");

    std::cout << "🎬 [C++ 全量数据导出] 正在处理视频: " << video_id << std::endl;

    k4a_playback_t playback = NULL;
    if (k4a_playback_open(mkv_path.c_str(), &playback) != K4A_RESULT_SUCCEEDED) {
        std::cerr << "❌ 无法打开 MKV 文件: " << mkv_path << std::endl;
        return -1;
    }

    k4a_calibration_t calibration;
    if (k4a_playback_get_calibration(playback, &calibration) != K4A_RESULT_SUCCEEDED) {
        std::cerr << "❌ 无法获取相机标定内参！" << std::endl;
        k4a_playback_close(playback);
        return -1;
    }

    // 强制锁死 CPU 推理模式，百分之百防崩溃
    k4abt_tracker_configuration_t tracker_config = K4ABT_TRACKER_CONFIG_DEFAULT;
    tracker_config.processing_mode = K4ABT_TRACKER_PROCESSING_MODE_CPU; 

    k4abt_tracker_t tracker = NULL;
    if (k4abt_tracker_create(&calibration, tracker_config, &tracker) != K4A_RESULT_SUCCEEDED) {
        std::cerr << "❌ 骨骼追踪器初始化失败！" << std::endl;
        k4a_playback_close(playback);
        return -1;
    }

    // 建立任务书要求的同步 CSV 和 3D 原始数据暂存
    std::ofstream csv_file(base_path + "frame_sync.csv");
    csv_file << "frame_index,color_timestamp_usec,depth_timestamp_usec,color_path,depth_path\n";

    std::ofstream json_3d_temp(base_path + "skeleton_3d_raw.txt");

    k4a_capture_t capture = NULL;
    k4a_stream_result_t stream_result = K4A_STREAM_RESULT_SUCCEEDED;
    int frame_index = 0;

    while (true) {
        stream_result = k4a_playback_get_next_capture(playback, &capture);
        if (stream_result == K4A_STREAM_RESULT_EOF) break;
        if (stream_result != K4A_STREAM_RESULT_SUCCEEDED) continue;

        frame_index++;

        // 1. 获取并导出图像与深度帧
        k4a_image_t color_img = k4a_capture_get_color_image(capture);
        k4a_image_t depth_img = k4a_capture_get_depth_image(capture);

        uint64_t color_ts = 0, depth_ts = 0;
        std::string c_path = "color/frame_" + std::to_string(frame_index) + ".jpg";
        std::string d_path = "depth/frame_" + std::to_string(frame_index) + ".png";

        if (color_img) {
            color_ts = k4a_image_get_device_timestamp_usec(color_img);
            uint8_t* buffer = k4a_image_get_buffer(color_img);
            int h = k4a_image_get_height_pixels(color_img);
            int w = k4a_image_get_width_pixels(color_img);
            cv::Mat mat(h, w, CV_8UC4, buffer);
            cv::Mat bgr;
            cv::cvtColor(mat, bgr, cv::COLOR_BGRA2BGR);
            cv::imwrite(base_path + c_path, bgr);
            k4a_image_release(color_img);
        }
        if (depth_img) {
            depth_ts = k4a_image_get_device_timestamp_usec(depth_img);
            uint16_t* buffer = (uint16_t*)(void*)k4a_image_get_buffer(depth_img);
            int h = k4a_image_get_height_pixels(depth_img);
            int w = k4a_image_get_width_pixels(depth_img);
            cv::Mat mat(h, w, CV_16UC1, buffer);
            cv::imwrite(base_path + d_path, mat);
            k4a_image_release(depth_img);
        }

        // 写入 frame_sync.csv
        csv_file << frame_index << "," << color_ts << "," << depth_ts << "," << c_path << "," << d_path << "\n";

        // 2. 压入追踪器解算 3D 骨骼
        k4abt_tracker_enqueue_capture(tracker, capture, K4A_WAIT_INFINITE);
        k4a_capture_release(capture);

        k4abt_frame_t body_frame = NULL;
        if (k4abt_tracker_pop_result(tracker, &body_frame, K4A_WAIT_INFINITE) == K4A_WAIT_RESULT_SUCCEEDED) {
            uint32_t num_bodies = k4abt_frame_get_num_bodies(body_frame);
            int body_id = -1;
            
            json_3d_temp << frame_index << "|" << color_ts << "|";
            if (num_bodies > 0) {
                body_id = k4abt_frame_get_body_id(body_frame, 0);
                k4abt_body_t body;
                k4abt_frame_get_body_skeleton(body_frame, 0, &body.skeleton);
                
                json_3d_temp << body_id;
                for (int i = 0; i < 32; i++) {
                    json_3d_temp << "|" << body.skeleton.joints[i].position.xyz.x / 1000.0f
                                 << "," << body.skeleton.joints[i].position.xyz.y / 1000.0f
                                 << "," << body.skeleton.joints[i].position.xyz.z / 1000.0f
                                 << "," << (int)body.skeleton.joints[i].confidence_level;
                }
            } else {
                json_3d_temp << "-1";
            }
            json_3d_temp << "\n";
            k4abt_frame_release(body_frame);
        }
        std::cout << "\r⚡ 已处理帧数: " << frame_index << std::flush;
    }

    csv_file.close();
    json_3d_temp.close();
    k4abt_tracker_shutdown(tracker);
    k4abt_tracker_destroy(tracker);
    k4a_playback_close(playback);
    std::cout << "\n🎉 C++ 基础数据榨取完成！" << std::endl;
    return 0;
}
