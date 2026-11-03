from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    args = [
        DeclareLaunchArgument(
            "use_teb", default_value="true", description="Use TEB local planner (vs custom)"
        ),
        DeclareLaunchArgument(
            "odom_topic",
            default_value="/mavros/local_position/odom",
            description="Odometry topic for planner",
        ),
        DeclareLaunchArgument(
            "cmd_vel_topic",
            default_value="/mavros/setpoint_velocity/cmd_vel",
            description="Output velocity command topic",
        ),
        DeclareLaunchArgument(
            "depth_topic",
            default_value="/camera/depth/points",
            description="Depth camera pointcloud topic",
        ),
        DeclareLaunchArgument(
            "lidar_topic",
            default_value="/mavros/distance_sensor/lidar",
            description="LiDAR distance sensor topic",
        ),
        DeclareLaunchArgument(
            "enable_silvus_monitor",
            default_value="true",
            description="Enable Silvus link quality -> planner parameter adaptation",
        ),
    ]

    def launch_setup(context, *args, **kwargs):
        nodes = []

        # 1. Depth to costmap (uses nav2_costmap_2d)
        # This is configured via costmap_params.yaml

        # 2. TEB Local Planner
        if LaunchConfiguration("use_teb").perform(context).lower() == "true":
            teb_node = Node(
                package="teb_local_planner",
                executable="teb_local_planner_node",
                name="teb_local_planner",
                output="screen",
                parameters=[
                    PathJoinSubstitution(
                        [FindPackageShare("obstacle_avoidance"), "config", "teb_params.yaml"]
                    ),
                    {
                        "odom_topic": LaunchConfiguration("odom_topic"),
                    },
                ],
                remappings=[
                    ("cmd_vel", LaunchConfiguration("cmd_vel_topic")),
                ],
            )
            nodes.append(teb_node)

        # 3. Obstacle Distance Publisher (LiDAR -> MAVLink OBSTACLE_DISTANCE)
        obstacle_dist_node = Node(
            package="obstacle_avoidance",
            executable="obstacle_distance_pub",
            name="obstacle_distance_pub",
            output="screen",
            parameters=[
                {
                    "lidar_topic": LaunchConfiguration("lidar_topic"),
                    "mavros_obstacle_topic": "/mavros/obstacle_distance/send",
                    "num_sectors": 72,  # 5-degree sectors
                    "max_distance": 10.0,
                    "frame_id": "base_link",
                }
            ],
        )
        nodes.append(obstacle_dist_node)

        # 4. Safety Watchdog (planner health + Silvus link quality -> PX4 failsafe)
        if LaunchConfiguration("enable_silvus_monitor").perform(context).lower() == "true":
            watchdog_node = Node(
                package="obstacle_avoidance",
                executable="safety_watchdog",
                name="safety_watchdog",
                output="screen",
                parameters=[
                    {
                        "planner_topic": LaunchConfiguration("cmd_vel_topic"),
                        "silvus_topic": "/silvus/link_quality",
                        "mavros_param_topic": "/mavros/param/set",
                        "watchdog_timeout": 0.5,  # seconds
                        "silvus_loss_threshold": 0.1,  # 10% packet loss
                        "silvus_rtt_threshold": 50.0,  # ms
                    }
                ],
            )
            nodes.append(watchdog_node)

        return nodes

    return LaunchDescription(args + [OpaqueFunction(function=launch_setup)])
