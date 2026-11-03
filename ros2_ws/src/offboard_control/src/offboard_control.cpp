#include <rclcpp/rclcpp.hpp>
#include <px4_msgs/msg/offboard_control_mode.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_command.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <px4_msgs/msg/timesync.hpp>
#include <rosgraph_msgs/msg/clock.hpp>
#include <chrono>
#include <cmath>

using namespace std::chrono_literals;

class OffboardControl : public rclcpp::Node {
public:
    OffboardControl() : Node("offboard_control") {
        // use_sim_time 파라미터 선언 및 설정
        this->declare_parameter("use_sim_time", true);
        rclcpp::Parameter sim_time_param("use_sim_time", true);
        this->set_parameters({sim_time_param});
        
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
        
        // 시뮬레이션 클럭 구독 (use_sim_time용)
        clock_sub_ = this->create_subscription<rosgraph_msgs::msg::Clock>(
            "/clock", 10,
            std::bind(&OffboardControl::clock_callback, this, std::placeholders::_1));
        
        // Timer (20Hz = 50ms)
        timer_ = this->create_wall_timer(50ms, std::bind(&OffboardControl::timer_callback, this));
        
        // 파라미터
        this->declare_parameter("takeoff_height", -1.5);
        this->declare_parameter("hover_duration", 10.0);
        this->declare_parameter("square_size", 2.0);
        takeoff_height_ = this->get_parameter("takeoff_height").as_double();
        hover_duration_ = this->get_parameter("hover_duration").as_double();
        square_size_ = this->get_parameter("square_size").as_double();
        
        RCLCPP_INFO(this->get_logger(), "Offboard control node started (use_sim_time: true)");
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

    void clock_callback(const rosgraph_msgs::msg::Clock::SharedPtr msg) {
        sim_time_ = rclcpp::Time(msg->clock);
    }
    
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
        
        if (dist < 0.3) {
            mission_step_++;
            RCLCPP_INFO(this->get_logger(), "Waypoint %d reached, moving to %d", mission_step_, mission_step_ + 1);
        }
    }
    
    void publish_offboard_control_mode() {
        auto msg = px4_msgs::msg::OffboardControlMode();
        msg.timestamp = timestamp_ > 0 ? timestamp_ : (sim_time_.nanoseconds() / 1000);
        msg.position = true;
        msg.velocity = false;
        msg.acceleration = false;
        msg.attitude = false;
        msg.body_rate = false;
        offboard_control_mode_pub_->publish(msg);
    }
    
    void publish_trajectory_setpoint(double x, double y, double z, double yaw) {
        auto msg = px4_msgs::msg::TrajectorySetpoint();
        msg.timestamp = timestamp_ > 0 ? timestamp_ : (sim_time_.nanoseconds() / 1000);
        msg.position = {x, y, z};
        msg.yaw = yaw;
        trajectory_setpoint_pub_->publish(msg);
    }
    
    void publish_vehicle_command(uint16_t command, double param1 = 0.0, double param2 = 0.0) {
        auto msg = px4_msgs::msg::VehicleCommand();
        msg.timestamp = timestamp_ > 0 ? timestamp_ : (sim_time_.nanoseconds() / 1000);
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

    enum class State { INIT, ARMING, TAKEOFF, HOVER, SQUARE_MISSION, LAND, DISARM };
    State state_ = State::INIT;
    
    uint64_t timestamp_ = 0;
    rclcpp::Time sim_time_;
    px4_msgs::msg::VehicleStatus::SharedPtr vehicle_status_;
    px4_msgs::msg::VehicleLocalPosition::SharedPtr vehicle_local_position_;
    
    rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr offboard_control_mode_pub_;
    rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr trajectory_setpoint_pub_;
    rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr vehicle_command_pub_;
    rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr vehicle_status_sub_;
    rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr vehicle_local_position_sub_;
    rclcpp::Subscription<px4_msgs::msg::Timesync>::SharedPtr timesync_sub_;
    rclcpp::Subscription<rosgraph_msgs::msg::Clock>::SharedPtr clock_sub_;
    rclcpp::TimerBase::SharedPtr timer_;
    
    double takeoff_height_;
    double hover_duration_;
    double square_size_;
    int mission_step_ = 0;
    rclcpp::Time takeoff_start_time_;
    rclcpp::Time hover_start_time_;
    rclcpp::Time mission_start_time_;
    rclcpp::Time sim_time_;
};

int main(int argc, char *argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<OffboardControl>());
    rclcpp::shutdown();
    return 0;
}
