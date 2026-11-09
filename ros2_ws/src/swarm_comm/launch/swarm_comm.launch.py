from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    args = [
        DeclareLaunchArgument(
            "drone_id", default_value="drone_01", description="Unique drone identifier"
        ),
        DeclareLaunchArgument(
            "swarm_id", default_value="swarm_alpha", description="Swarm identifier"
        ),
        DeclareLaunchArgument(
            "broadcast_rate",
            default_value="20.0",
            description="Position broadcast rate (Hz)",
        ),
        DeclareLaunchArgument(
            "ca_algorithm",
            default_value="potential_field",
            description="Collision avoidance algorithm: potential_field, velocity_obstacle, mpc",
        ),
        DeclareLaunchArgument(
            "safety_radius",
            default_value="2.0",
            description="Minimum separation distance (m)",
        ),
        DeclareLaunchArgument(
            "warning_radius", default_value="5.0", description="Warning zone radius (m)"
        ),
        DeclareLaunchArgument(
            "formation_enabled",
            default_value="false",
            description="Enable formation flight",
        ),
        DeclareLaunchArgument(
            "formation_shape",
            default_value="line",
            description="Formation shape: line, wedge, diamond, circle",
        ),
        DeclareLaunchArgument(
            "formation_spacing",
            default_value="3.0",
            description="Spacing between drones in formation (m)",
        ),
        DeclareLaunchArgument(
            "leader_id", default_value="", description="Leader drone ID (empty = none)"
        ),
        DeclareLaunchArgument(
            "silvus_link_loss_threshold",
            default_value="0.1",
            description="Packet loss threshold for link degradation (0.0-1.0)",
        ),
        DeclareLaunchArgument(
            "silvus_rtt_threshold",
            default_value="50.0",
            description="RTT threshold for link degradation (ms)",
        ),
        DeclareLaunchArgument(
            "log_collision_events",
            default_value="true",
            description="Log collision avoidance events",
        ),
        DeclareLaunchArgument(
            "log_broadcast_stats",
            default_value="true",
            description="Log broadcast statistics",
        ),
    ]

    def launch_setup(context, *args, **kwargs):
        nodes = []

        # Position Broadcaster
        broadcaster_node = Node(
            package="swarm_comm",
            executable="position_broadcaster",
            name="position_broadcaster",
            output="screen",
            parameters=[
                {
                    "drone_id": LaunchConfiguration("drone_id"),
                    "swarm_id": LaunchConfiguration("swarm_id"),
                    "broadcast_rate": LaunchConfiguration("broadcast_rate"),
                    "silvus_link_loss_threshold": LaunchConfiguration(
                        "silvus_link_loss_threshold"
                    ),
                    "silvus_rtt_threshold": LaunchConfiguration("silvus_rtt_threshold"),
                    "log_broadcast_stats": LaunchConfiguration("log_broadcast_stats"),
                }
            ],
        )

        # Collision Avoidance
        ca_node = Node(
            package="swarm_comm",
            executable="collision_avoidance",
            name="collision_avoidance",
            output="screen",
            parameters=[
                {
                    "drone_id": LaunchConfiguration("drone_id"),
                    "ca_algorithm": LaunchConfiguration("ca_algorithm"),
                    "safety_radius": LaunchConfiguration("safety_radius"),
                    "warning_radius": LaunchConfiguration("warning_radius"),
                    "log_collision_events": LaunchConfiguration("log_collision_events"),
                }
            ],
        )

        # Swarm Coordinator
        coord_node = Node(
            package="swarm_comm",
            executable="swarm_coordinator",
            name="swarm_coordinator",
            output="screen",
            parameters=[
                {
                    "drone_id": LaunchConfiguration("drone_id"),
                    "swarm_id": LaunchConfiguration("swarm_id"),
                    "formation_enabled": LaunchConfiguration("formation_enabled"),
                    "formation_shape": LaunchConfiguration("formation_shape"),
                    "formation_spacing": LaunchConfiguration("formation_spacing"),
                    "leader_id": LaunchConfiguration("leader_id"),
                }
            ],
        )

        return [broadcaster_node, ca_node, coord_node]

    return LaunchDescription(args + [OpaqueFunction(function=launch_setup)])
