# ROS2 Offboard 제어 예제 (강좌 4편 기반)

## 패키지 구조
```
ros2_ws/src/offboard_control/
├── CMakeLists.txt
├── package.xml
├── src/
│   ├── offboard_control.cpp
│   └── offboard_control_node.cpp
├── launch/
│   └── offboard_control.launch.py
└── config/
    └── offboard_params.yaml
```

## package.xml
```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>offboard_control</name>
  <version>0.1.0</name>
  <description>PX4 Offboard Control for Q250-V3 Opti</description>
  <maintainer email="user@example.com">User</maintainer>
  <license>MIT</license>

  <buildtool_depend>ament_cmake</buildtool_depend>
  
  <depend>rclcpp</depend>
  <depend>px4_msgs</depend>
  <depend>geometry_msgs</depend>
  <depend>nav_msgs</depend>
  <depend>sensor_msgs</depend>
  <depend>std_msgs</depend>
  <depend>builtin_interfaces</depend>
  <depend>rclcpp_action</depend>

  <test_depend>ament_lint_auto</test_depend>
  <test_depend>ament_lint_common</test_depend>
</package>
```

## CMakeLists.txt
```cmake
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

add_executable(offboard_control src/offboard_control.cpp)
ament_target_dependencies(offboard_control rclcpp px4_msgs geometry_msgs nav_msgs sensor_msgs std_msgs builtin_interfaces rclcpp_action)

add_executable(offboard_control_node src/offboard_control_node.cpp)
ament_target_dependencies(offboard_control_node rclcpp px4_msgs geometry_msgs nav_msgs sensor_msgs std_msgs builtin_interfaces rclcpp_action)

install(TARGETS offboard_control offboard_control_node DESTINATION lib/${PROJECT_NAME})

ament_package()
```

## 메인 Offboard 제어 노드 (src/offboard_control.cpp)
```cpp
#include <rclcpp/rclcpp.hpp>
#include <px4_msgs/msg/offboard_control_mode.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_command.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <px4_msgs/msg/timesync.hpp>
#include <chrono>
#include <cmath>

using namespace std::chrono_literals;

class OffboardControl : public rclcpp::Node {
public:
    OffboardControl() : Node("offboard_control") {
        // QoS 설정 (PX4 호환: BEST_EFFORT + TRANSIENT_LOCAL)
        auto qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(rmw_qos_profile_sensor_data));
        qos.reliability(RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
        qos.durability(RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL);
        qos.history(RMW_QOS_POLICY_HISTORY_KEEP_LAST);
        qos.depth(1);

        // Publishers
        offboard_control_mode_pub_ = this->create_publisher<px4_msgs::msg::OffboardControlMode>(
            "/fmu/in/offboard_control_mode", qos);
        trajectory_setpoint_pub_ = this->create_publisher<px4_msgs::msg::TrajectorySetpoint>(
            "/fmu/in/trajectory_setpoint", qos);
        vehicle_command_pub_ = this->create_publisher<px4_msgs::msg::VehicleCommand>(
            "/fmu/in/vehicle_command", qos);

        // Subscribers
        vehicle_status_sub_ = this->create_subscription<px4_msgs::msg::VehicleStatus>(
            "/fmu/out/vehicle_status", qos,
            std::bind(&OffboardControl::vehicle_status_callback, this, std::placeholders::_1));
        vehicle_local_position_sub_ = this->create_subscription<px4_msgs::msg::VehicleLocalPosition>(
            "/fmu/out/vehicle_local_position", qos,
            std::bind(&OffboardControl::vehicle_local_position_callback, this, std::placeholders::_1));
        timesync_sub_ = this->create_subscription<px4_msgs::msg::Timesync>(
            "/fmu/out/timesync", qos,
            std::bind(&OffboardControl::timesync_callback, this, std::placeholders::_1));

        // Timer (20Hz = 50ms)
        timer_ = this->create_wall_timer(50ms, std::bind(&OffboardControl::timer_callback, this));

        // 파라미터
        this->declare_parameter("takeoff_height", -1.5);  // NED: 음수 = 위
        this->declare_parameter("hover_duration", 10.0);  // 초
        this->declare_parameter("square_size", 2.0);      // 미터
        takeoff_height_ = this->get_parameter("takeoff_height").as_double();
        hover_duration_ = this->get_parameter("hover_duration").as_double();
        square_size_ = this->get_parameter("square_size").as_double();

        RCLCPP_INFO(this->get_logger(), "Offboard control node started");
    }

private:
    enum class State {
        INIT,
        ARMING,
        TAKEOFF,
        HOVER,
        SQUARE_MISSION,
        LAND,
        DISARM
    };

    void timesync_callback(const px4_msgs::msg::Timesync::SharedPtr msg) {
        timestamp_ = msg->timestamp;
    }

    void vehicle_status_callback(const px4_msgs::msg::VehicleStatus::SharedPtr msg) {
        vehicle_status_ = msg;
    }

    void vehicle_local_position_callback(const px4_msgs::msg::VehicleLocalPosition::SharedPtr msg) {
        vehicle_local_position_ = msg;
    }

    void timer_callback() {
        if (!vehicle_status_ || !vehicle_local_position_) return;

        // 1. OffboardControlMode 발행 (필수: 2Hz 이상)
        publish_offboard_control_mode();

        // 2. 상태 머신
        switch (state_) {
            case State::INIT:
                if (vehicle_status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD) {
                    state_ = State::ARMING;
                } else {
                    // Offboard 모드 요청
                    publish_vehicle_command(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_DO_SET_MODE, 1, 6);
                }
                break;

            case State::ARMING:
                if (vehicle_status_->arming_state == px4_msgs::msg::VehicleStatus::ARMING_STATE_ARMED) {
                    state_ = State::TAKEOFF;
                    takeoff_start_time_ = this->now();
                } else {
                    arm();
                }
                break;

            case State::TAKEOFF:
                publish_trajectory_setpoint(0.0, 0.0, takeoff_height_, 0.0);
                if (std::abs(vehicle_local_position_->z - takeoff_height_) < 0.2) {
                    state_ = State::HOVER;
                    hover_start_time_ = this->now();
                }
                break;

            case State::HOVER:
                publish_trajectory_setpoint(0.0, 0.0, takeoff_height_, 0.0);
                if ((this->now() - hover_start_time_).seconds() > hover_duration_) {
                    state_ = State::SQUARE_MISSION;
                    mission_step_ = 0;
                    mission_start_time_ = this->now();
                }
                break;

            case State::SQUARE_MISSION:
                execute_square_mission();
                break;

            case State::LAND:
                publish_vehicle_command(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_NAV_LAND);
                if (vehicle_status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_AUTO_LAND) {
                    state_ = State::DISARM;
                }
                break;

            case State::DISARM:
                publish_vehicle_command(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0);
                break;
        }
    }

    void execute_square_mission() {
        // 사각형 4코너: (0,0) -> (L,0) -> (L,L) -> (0,L) -> (0,0)
        static const std::vector<std::pair<double, double>> waypoints = {
            {0.0, 0.0},
            {square_size_, 0.0},
            {square_size_, square_size_},
            {0.0, square_size_},
            {0.0, 0.0}
        };

        if (mission_step_ >= waypoints.size()) {
            state_ = State::LAND;
            return;
        }

        auto [target_x, target_y] = waypoints[mission_step_];
        double current_x = vehicle_local_position_->x;
        double current_y = vehicle_local_position_->y;
        double dist = std::hypot(target_x - current_x, target_y - current_y);

        publish_trajectory_setpoint(target_x, target_y, takeoff_height_, 0.0);

        if (dist < 0.3) {  // 30cm 이내 도달
            mission_step_++;
            RCLCPP_INFO(this->get_logger(), "Waypoint %d reached, moving to %d", mission_step_, mission_step_ + 1);
        }
    }

    void publish_offboard_control_mode() {
        auto msg = px4_msgs::msg::OffboardControlMode();
        msg.timestamp = timestamp_;
        msg.position = true;
        msg.velocity = false;
        msg.acceleration = false;
        msg.attitude = false;
        msg.body_rate = false;
        offboard_control_mode_pub_->publish(msg);
    }

    void publish_trajectory_setpoint(double x, double y, double z, double yaw) {
        auto msg = px4_msgs::msg::TrajectorySetpoint();
        msg.timestamp = timestamp_;
        msg.position = {x, y, z};
        msg.yaw = yaw;
        trajectory_setpoint_pub_->publish(msg);
    }

    void publish_vehicle_command(uint16_t command, double param1 = 0.0, double param2 = 0.0) {
        auto msg = px4_msgs::msg::VehicleCommand();
        msg.timestamp = timestamp_;
        msg.command = command;
        msg.param1 = param1;
        msg.param2 = param2;
        msg.target_system = 1;
        msg.target_component = 1;
        msg.source_system = 1;
        msg.source_component = 1;
        msg.from_external = true;
        vehicle_command_pub_->publish(msg);
    }

    void arm() {
        publish_vehicle_command(px4_msgs::msg::VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0);
    }

    // Members
    State state_ = State::INIT;
    uint64_t timestamp_ = 0;
    px4_msgs::msg::VehicleStatus::SharedPtr vehicle_status_;
    px4_msgs::msg::VehicleLocalPosition::SharedPtr vehicle_local_position_;
    
    rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr offboard_control_mode_pub_;
    rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr trajectory_setpoint_pub_;
    rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr vehicle_command_pub_;
    rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr vehicle_status_sub_;
    rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr vehicle_local_position_sub_;
    rclcpp::Subscription<px4_msgs::msg::Timesync>::SharedPtr timesync_sub_;
    rclcpp::TimerBase::SharedPtr timer_;

    double takeoff_height_;
    double hover_duration_;
    double square_size_;
    int mission_step_ = 0;
    rclcpp::Time takeoff_start_time_;
    rclcpp::Time hover_start_time_;
    rclcpp::Time mission_start_time_;
};

int main(int argc, char *argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<OffboardControl>());
    rclcpp::shutdown();
    return 0;
}
```

## Launch 파일 (launch/offboard_control.launch.py)
```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('takeoff_height', default_value='-1.5', description='Takeoff height (NED, negative=up)'),
        DeclareLaunchArgument('hover_duration', default_value='10.0', description='Hover duration in seconds'),
        DeclareLaunchArgument('square_size', default_value='2.0', description='Square mission size in meters'),
        
        Node(
            package='offboard_control',
            executable='offboard_control',
            name='offboard_control',
            output='screen',
            parameters=[{
                'takeoff_height': LaunchConfiguration('takeoff_height'),
                'hover_duration': LaunchConfiguration('hover_duration'),
                'square_size': LaunchConfiguration('square_size'),
            }],
        ),
    ])
```

## 실행 방법
```bash
# 1. 빌드
cd ~/ros2_px4_ws
colcon build --packages-select offboard_control --symlink-install
source install/setup.bash

# 2. 터미널 1: PX4 SITL (Gazebo)
cd ~/PX4-Autopilot
make px4_sitl gz_x500  # 또는 gz_q250_v3_opti

# 3. 터미널 2: uXRCE-DDS Agent
MicroXRCEAgent udp4 -p 8888

# 4. 터미널 3: Offboard 제어 노드
source ~/ros2_px4_ws/install/setup.bash
ros2 launch offboard_control offboard_control.launch.py

# 5. 모니터링 (별도 터미널)
ros2 topic echo /fmu/out/vehicle_local_position
ros2 topic echo /fmu/out/vehicle_status
```

## 강좌 4편 시청하면서 체크할 것
- [ ] Timesync 처리 방식 (타임스탬프 동기화)
- [ ] QoS 설정 (BEST_EFFORT + TRANSIENT_LOCAL) 이유
- [ ] OffboardControlMode 발행 주기 (2Hz 이상 필수)
- [ ] VehicleCommand 시퀀스 (ARM → OFFBOARD → TrajectorySetpoint)
- [ ] NED 좌표계 이해 (Z 음수 = 위)
- [ ] Timesync 콜백으로 timestamp 동기화
- [ ] 상태 머신 설계 패턴
