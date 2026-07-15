/**
 * Azure Kinect MKV Offline Extractor
 *
 * Extracts color frames, depth frames, 3D skeleton data, and calibration
 * from a recorded MKV file. Uses K4A playback API + K4ABT body tracking.
 *
 * Build:
 *   mkdir build && cd build
 *   cmake .. -DCMAKE_BUILD_TYPE=Release
 *   make -j$(nproc)
 *
 * Usage:
 *   ./extract_joints \
 *       --mkv /path/to/video.mkv \
 *       --output-dir /path/to/output \
 *       --video-id K01_reach_grasp_001 \
 *       [--cpu-only]
 *
 * Output structure:
 *   <output-dir>/
 *     color/           # frame_000001.jpg ...
 *     depth/           # frame_000001.png ...
 *     frame_sync.csv   # frame_index,color_ts,depth_ts,color_path,depth_path
 *     skeleton_3d_raw.txt  # frame_index|timestamp|body_id|joints...
 *     calibration.json # camera intrinsics and extrinsics
 */

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cstring>
#include <cstdint>
#include <sys/stat.h>
#include <k4a/k4a.h>
#include <k4arecord/playback.h>
#include <k4abt.h>
#include <opencv2/opencv.hpp>

void make_dir(const std::string& path) {
    mkdir(path.c_str(), 0777);
}

void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog << "\n"
              << "  --mkv <path>         Input MKV file\n"
              << "  --output-dir <path>   Output directory\n"
              << "  --video-id <id>       Video identifier\n"
              << "  --cpu-only            Force CPU processing mode (optional)\n"
              << std::endl;
}

void write_calibration_json(const k4a_calibration_t& calib, const std::string& path) {
    // Extract color camera intrinsics
    k4a_calibration_intrinsic_parameters_t color_params =
        calib.color_camera_calibration.intrinsics.parameters;

    std::ofstream f(path);
    f << "{\n";
    f << "  \"color_intrinsics\": {\n";
    f << "    \"fx\": " << color_params.param.fx << ",\n";
    f << "    \"fy\": " << color_params.param.fy << ",\n";
    f << "    \"cx\": " << color_params.param.cx << ",\n";
    f << "    \"cy\": " << color_params.param.cy << ",\n";
    f << "    \"k1\": " << color_params.param.k1 << ",\n";
    f << "    \"k2\": " << color_params.param.k2 << ",\n";
    f << "    \"k3\": " << color_params.param.k3 << ",\n";
    f << "    \"k4\": " << color_params.param.k4 << ",\n";
    f << "    \"k5\": " << color_params.param.k5 << ",\n";
    f << "    \"k6\": " << color_params.param.k6 << ",\n";
    f << "    \"p1\": " << color_params.param.p1 << ",\n";
    f << "    \"p2\": " << color_params.param.p2 << "\n";
    f << "  },\n";

    // Depth camera intrinsics
    k4a_calibration_intrinsic_parameters_t depth_params =
        calib.depth_camera_calibration.intrinsics.parameters;
    f << "  \"depth_intrinsics\": {\n";
    f << "    \"fx\": " << depth_params.param.fx << ",\n";
    f << "    \"fy\": " << depth_params.param.fy << ",\n";
    f << "    \"cx\": " << depth_params.param.cx << ",\n";
    f << "    \"cy\": " << depth_params.param.cy << ",\n";
    f << "    \"k1\": " << depth_params.param.k1 << ",\n";
    f << "    \"k2\": " << depth_params.param.k2 << ",\n";
    f << "    \"k3\": " << depth_params.param.k3 << ",\n";
    f << "    \"k4\": " << depth_params.param.k4 << ",\n";
    f << "    \"k5\": " << depth_params.param.k5 << ",\n";
    f << "    \"k6\": " << depth_params.param.k6 << ",\n";
    f << "    \"p1\": " << depth_params.param.p1 << ",\n";
    f << "    \"p2\": " << depth_params.param.p2 << "\n";
    f << "  },\n";
    f << "  \"color_resolution\": {\n";
    f << "    \"width\": " << calib.color_camera_calibration.resolution_width << ",\n";
    f << "    \"height\": " << calib.color_camera_calibration.resolution_height << "\n";
    f << "  },\n";
    f << "  \"depth_resolution\": {\n";
    f << "    \"width\": " << calib.depth_camera_calibration.resolution_width << ",\n";
    f << "    \"height\": " << calib.depth_camera_calibration.resolution_height << "\n";
    f << "  }\n";
    f << "}\n";
    f.close();
    std::cout << "  Calibration written to: " << path << std::endl;
}

int main(int argc, char* argv[]) {
    // --- Parse command-line arguments ---
    std::string mkv_path;
    std::string output_dir;
    std::string video_id;
    bool cpu_only = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--mkv" && i + 1 < argc) {
            mkv_path = argv[++i];
        } else if (arg == "--output-dir" && i + 1 < argc) {
            output_dir = argv[++i];
        } else if (arg == "--video-id" && i + 1 < argc) {
            video_id = argv[++i];
        } else if (arg == "--cpu-only") {
            cpu_only = true;
        } else if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        }
    }

    if (mkv_path.empty() || output_dir.empty() || video_id.empty()) {
        std::cerr << "ERROR: --mkv, --output-dir, and --video-id are required.\n\n";
        print_usage(argv[0]);
        return 1;
    }

    // Ensure trailing slash on output_dir
    if (output_dir.back() != '/') output_dir += '/';
    std::string base_path = output_dir + video_id + "/";

    make_dir(output_dir);
    make_dir((output_dir + video_id));
    make_dir(base_path);
    make_dir(base_path + "color");
    make_dir(base_path + "depth");

    std::cout << "Extracting: " << video_id << std::endl;
    std::cout << "  MKV:   " << mkv_path << std::endl;
    std::cout << "  Output: " << base_path << std::endl;
    std::cout << "  Mode:  " << (cpu_only ? "CPU" : "GPU (default)") << std::endl;

    // --- Open MKV ---
    k4a_playback_t playback = NULL;
    if (k4a_playback_open(mkv_path.c_str(), &playback) != K4A_RESULT_SUCCEEDED) {
        std::cerr << "ERROR: Cannot open MKV file: " << mkv_path << std::endl;
        return 1;
    }

    // --- Get calibration ---
    k4a_calibration_t calibration;
    if (k4a_playback_get_calibration(playback, &calibration) != K4A_RESULT_SUCCEEDED) {
        std::cerr << "ERROR: Cannot get camera calibration from MKV." << std::endl;
        k4a_playback_close(playback);
        return 1;
    }
    write_calibration_json(calibration, base_path + "calibration.json");

    std::cout << "  Color resolution: "
              << calibration.color_camera_calibration.resolution_width << "x"
              << calibration.color_camera_calibration.resolution_height << std::endl;

    // --- Create body tracker ---
    k4abt_tracker_configuration_t tracker_config = K4ABT_TRACKER_CONFIG_DEFAULT;
    if (cpu_only) {
        tracker_config.processing_mode = K4ABT_TRACKER_PROCESSING_MODE_CPU;
    }

    k4abt_tracker_t tracker = NULL;
    if (k4abt_tracker_create(&calibration, tracker_config, &tracker) != K4A_RESULT_SUCCEEDED) {
        std::cerr << "ERROR: Body tracker initialization failed." << std::endl;
        k4a_playback_close(playback);
        return 1;
    }

    // --- Output files ---
    std::ofstream csv_file(base_path + "frame_sync.csv");
    csv_file << "frame_index,color_timestamp_usec,depth_timestamp_usec,color_path,depth_path\n";

    std::ofstream json_3d_temp(base_path + "skeleton_3d_raw.txt");

    // --- Main extraction loop ---
    k4a_capture_t capture = NULL;
    int frame_index = 0;
    int color_count = 0;
    int depth_count = 0;

    while (true) {
        k4a_stream_result_t stream_result = k4a_playback_get_next_capture(playback, &capture);
        if (stream_result == K4A_STREAM_RESULT_EOF) break;
        if (stream_result != K4A_STREAM_RESULT_SUCCEEDED) continue;

        frame_index++;

        // Extract color image
        k4a_image_t color_img = k4a_capture_get_color_image(capture);
        k4a_image_t depth_img = k4a_capture_get_depth_image(capture);

        uint64_t color_ts = 0, depth_ts = 0;
        char color_fname[64], depth_fname[64];
        snprintf(color_fname, sizeof(color_fname), "color/frame_%06d.jpg", frame_index);
        snprintf(depth_fname, sizeof(depth_fname), "depth/frame_%06d.png", frame_index);

        if (color_img) {
            color_ts = k4a_image_get_device_timestamp_usec(color_img);
            uint8_t* buffer = k4a_image_get_buffer(color_img);
            size_t size = k4a_image_get_size(color_img);
            k4a_image_format_t fmt = k4a_image_get_format(color_img);

            cv::Mat bgr;
            if (fmt == K4A_IMAGE_FORMAT_COLOR_MJPG) {
                // MJPG (compressed JPEG): decode with OpenCV
                std::vector<uint8_t> jpeg_buf(buffer, buffer + size);
                bgr = cv::imdecode(jpeg_buf, cv::IMREAD_COLOR);
            } else if (fmt == K4A_IMAGE_FORMAT_COLOR_BGRA32) {
                // BGRA32 (raw): convert to BGR
                int h = k4a_image_get_height_pixels(color_img);
                int w = k4a_image_get_width_pixels(color_img);
                int stride = k4a_image_get_stride_bytes(color_img);
                if (stride == 0) stride = w * 4;
                cv::Mat mat(h, w, CV_8UC4, buffer, stride);
                cv::cvtColor(mat, bgr, cv::COLOR_BGRA2BGR);
            } else {
                std::cerr << "  Warning: unsupported color format " << (int)fmt
                          << " at frame " << frame_index << std::endl;
            }

            if (!bgr.empty()) {
                cv::imwrite(base_path + color_fname, bgr);
                color_count++;
            }
            k4a_image_release(color_img);
        }

        if (depth_img) {
            depth_ts = k4a_image_get_device_timestamp_usec(depth_img);
            uint16_t* buffer = (uint16_t*)(void*)k4a_image_get_buffer(depth_img);
            int h = k4a_image_get_height_pixels(depth_img);
            int w = k4a_image_get_width_pixels(depth_img);
            cv::Mat mat(h, w, CV_16UC1, buffer);
            cv::imwrite(base_path + depth_fname, mat);
            k4a_image_release(depth_img);
            depth_count++;
        }

        csv_file << frame_index << "," << color_ts << "," << depth_ts << ","
                 << color_fname << "," << depth_fname << "\n";

        // Body tracking
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
                    // SDK positions are in millimeters; convert to meters
                    float x_m = body.skeleton.joints[i].position.xyz.x / 1000.0f;
                    float y_m = body.skeleton.joints[i].position.xyz.y / 1000.0f;
                    float z_m = body.skeleton.joints[i].position.xyz.z / 1000.0f;
                    int conf = static_cast<int>(body.skeleton.joints[i].confidence_level);

                    json_3d_temp << "|" << x_m << "," << y_m << "," << z_m << "," << conf;
                }
            } else {
                json_3d_temp << "-1";
            }
            json_3d_temp << "\n";
            k4abt_frame_release(body_frame);
        }

        if (frame_index % 30 == 0) {
            std::cout << "\r  Processed " << frame_index << " frames ..." << std::flush;
        }
    }

    csv_file.close();
    json_3d_temp.close();
    k4abt_tracker_shutdown(tracker);
    k4abt_tracker_destroy(tracker);
    k4a_playback_close(playback);

    std::cout << "\r  Processed " << frame_index << " frames total." << std::endl;
    std::cout << "\nDone." << std::endl;
    std::cout << "  Color frames: " << color_count << std::endl;
    std::cout << "  Depth frames: " << depth_count << std::endl;
    std::cout << "  Output:       " << base_path << std::endl;
    return 0;
}
