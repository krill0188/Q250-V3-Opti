cmake_minimum_required(VERSION 3.8)
project(offboard_control)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(ros_gz_bridge REQUIRED)
find_package(ros_gz_sim REQUIRED)
find_package(gz_msgs REQUIRED)
find_package(gz_sensors REQUIRED)
find_package(rosgraph_msgs REQUIRED)

add_executable(offboard_control src/offboard_control.cpp)
ament_target_dependencies(
  offboard_control
  rclcpp
  px4_msgs
  geometry_msgs
  nav_msgs
  sensor_msgs
  std_msgs
  builtin_interfaces
  rclcpp_action
  ros_gz_bridge
  gz_msgs
  gz_sensors
  rosgraph_msgs)

install(TARGETS offboard_control DESTINATION lib/${PROJECT_NAME})
ament_package()
