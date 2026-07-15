cmake_minimum_required(VERSION 3.10)
project(KinectExtractor VERSION 1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(OpenCV REQUIRED)
find_package(k4a REQUIRED)
find_package(k4arecord REQUIRED)
find_package(k4abt REQUIRED)
add_executable(extract_joints extract_joints.cpp)
target_include_directories(extract_joints PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(extract_joints
    ${OpenCV_LIBS}
    k4a::k4a
    k4arecord::k4arecord
    k4abt::k4abt
)
