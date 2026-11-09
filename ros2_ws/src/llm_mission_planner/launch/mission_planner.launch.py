from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    args = [
        DeclareLaunchArgument(
            "llm_provider",
            default_value="openai",
            description="LLM provider: openai, anthropic, local",
        ),
        DeclareLaunchArgument(
            "llm_model", default_value="gpt-4o", description="LLM model name"
        ),
        DeclareLaunchArgument(
            "llm_temperature",
            default_value="0.1",
            description="LLM temperature (0.0-1.0)",
        ),
        DeclareLaunchArgument(
            "llm_max_tokens", default_value="2048", description="LLM max tokens"
        ),
        DeclareLaunchArgument(
            "llm_timeout", default_value="30.0", description="LLM timeout in seconds"
        ),
        DeclareLaunchArgument(
            "default_altitude",
            default_value="10.0",
            description="Default mission altitude (m)",
        ),
        DeclareLaunchArgument(
            "max_altitude", default_value="50.0", description="Maximum altitude (m)"
        ),
        DeclareLaunchArgument(
            "min_altitude", default_value="0.5", description="Minimum altitude (m)"
        ),
        DeclareLaunchArgument(
            "default_speed",
            default_value="3.0",
            description="Default cruise speed (m/s)",
        ),
        DeclareLaunchArgument(
            "max_speed", default_value="5.0", description="Maximum speed (m/s)"
        ),
        DeclareLaunchArgument(
            "safety_margin",
            default_value="2.0",
            description="Safety margin from geofence (m)",
        ),
        DeclareLaunchArgument(
            "max_waypoints",
            default_value="50",
            description="Maximum waypoints per mission",
        ),
        DeclareLaunchArgument(
            "max_waypoint_distance",
            default_value="500.0",
            description="Maximum distance between waypoints (m)",
        ),
        DeclareLaunchArgument(
            "geofence_polygon",
            default_value="[]",
            description="Geofence polygon as JSON array of [lat, lon]",
        ),
        DeclareLaunchArgument(
            "validate_waypoints",
            default_value="true",
            description="Enable waypoint validation",
        ),
        DeclareLaunchArgument(
            "max_retries",
            default_value="3",
            description="Max LLM retries on validation failure",
        ),
        DeclareLaunchArgument(
            "log_llm_requests", default_value="true", description="Log LLM requests"
        ),
        DeclareLaunchArgument(
            "log_llm_responses", default_value="true", description="Log LLM responses"
        ),
    ]

    def launch_setup(context, *args, **kwargs):
        nodes = []

        # Mission Planner Node
        planner_node = Node(
            package="llm_mission_planner",
            executable="mission_planner_node",
            name="mission_planner_node",
            output="screen",
            parameters=[
                {
                    "llm_provider": LaunchConfiguration("llm_provider"),
                    "llm_model": LaunchConfiguration("llm_model"),
                    "llm_temperature": LaunchConfiguration("llm_temperature"),
                    "llm_max_tokens": LaunchConfiguration("llm_max_tokens"),
                    "llm_timeout": LaunchConfiguration("llm_timeout"),
                    "default_altitude": LaunchConfiguration("default_altitude"),
                    "max_altitude": LaunchConfiguration("max_altitude"),
                    "min_altitude": LaunchConfiguration("min_altitude"),
                    "default_speed": LaunchConfiguration("default_speed"),
                    "max_speed": LaunchConfiguration("max_speed"),
                    "safety_margin": LaunchConfiguration("safety_margin"),
                    "max_waypoints": LaunchConfiguration("max_waypoints"),
                    "max_waypoint_distance": LaunchConfiguration(
                        "max_waypoint_distance"
                    ),
                    "geofence_polygon": LaunchConfiguration("geofence_polygon"),
                    "validate_waypoints": LaunchConfiguration("validate_waypoints"),
                    "max_retries": LaunchConfiguration("max_retries"),
                    "log_llm_requests": LaunchConfiguration("log_llm_requests"),
                    "log_llm_responses": LaunchConfiguration("log_llm_responses"),
                }
            ],
        )
        nodes.append(planner_node)

        # Mission Validator Node
        validator_node = Node(
            package="llm_mission_planner",
            executable="mission_validator_node",
            name="mission_validator_node",
            output="screen",
            parameters=[
                {
                    "max_altitude": LaunchConfiguration("max_altitude"),
                    "min_altitude": LaunchConfiguration("min_altitude"),
                    "max_speed": LaunchConfiguration("max_speed"),
                    "safety_margin": LaunchConfiguration("safety_margin"),
                    "max_waypoint_distance": LaunchConfiguration(
                        "max_waypoint_distance"
                    ),
                    "geofence_polygon": LaunchConfiguration("geofence_polygon"),
                }
            ],
        )
        nodes.append(validator_node)

        return nodes

    return LaunchDescription(args + [OpaqueFunction(function=launch_setup)])
