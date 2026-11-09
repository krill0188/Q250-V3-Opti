from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    fcu_url = LaunchConfiguration("fcu_url", default="udp://:14540@127.0.0.1:14557")
    launch_mavros = LaunchConfiguration("launch_mavros", default="true")
    launch_hybrid = LaunchConfiguration("launch_hybrid", default="true")
    hybrid_device = LaunchConfiguration("hybrid_device", default="hybrid_drone_1")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="true",
                description="SITL Gazebo 시뮬레이션 시간 사용 여부",
            ),
            DeclareLaunchArgument(
                "fcu_url",
                default_value="udp://:14540@127.0.0.1:14557",
                description="드론 FC 연결 주소 (실장비 예: /dev/ttyACM0:921600)",
            ),
            DeclareLaunchArgument(
                "launch_mavros",
                default_value="true",
                description="MAVROS2 노드 자동 기동 여부",
            ),
            DeclareLaunchArgument(
                "launch_hybrid",
                default_value="true",
                description="하이브리드 드론 브릿지 노드 기동 여부",
            ),
            DeclareLaunchArgument(
                "hybrid_device",
                default_value="hybrid_drone_1",
                description="하이브리드 드론 디바이스 ID",
            ),
            LogInfo(
                msg="[Hybrid Control Bringup] ROS2 & MAVROS2 & Hybrid 브릿지 환경을 기동합니다..."
            ),
            # MAVROS2 노드 (기존 드론용)
            Node(
                package="mavros",
                executable="mavros_node",
                namespace="drone_1",
                output="screen",
                condition=IfCondition(launch_mavros),
                parameters=[
                    {
                        "fcu_url": fcu_url,
                        "use_sim_time": use_sim_time,
                        "target_system_id": 1,
                        "target_component_id": 1,
                    }
                ],
            ),
            # 하이브리드 드론 브릿지 노드 (신규)
            Node(
                package="hybrid_drone_bridge",
                executable="hybrid_bridge_node",
                namespace=hybrid_device,
                output="screen",
                condition=IfCondition(launch_hybrid),
                parameters=[
                    {
                        "device_id": hybrid_device,
                        "use_sim_time": use_sim_time,
                    }
                ],
            ),
        ]
    )
