from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Launch arguments
    args = [
        DeclareLaunchArgument(
            "datum_lat", default_value="37.5665", description="Datum latitude (degrees)"
        ),
        DeclareLaunchArgument(
            "datum_lon",
            default_value="126.9780",
            description="Datum longitude (degrees)",
        ),
        DeclareLaunchArgument(
            "datum_alt", default_value="28.0", description="Datum altitude MSL (meters)"
        ),
        DeclareLaunchArgument(
            "fix_type",
            default_value="3",
            description="GPS fix type (3=3D, 4=DGPS, 5=RTK)",
        ),
        DeclareLaunchArgument(
            "satellites_visible",
            default_value="10",
            description="Simulated satellites visible",
        ),
        DeclareLaunchArgument(
            "horiz_accuracy",
            default_value="0.5",
            description="Minimum horizontal accuracy (meters)",
        ),
        DeclareLaunchArgument(
            "vert_accuracy",
            default_value="0.5",
            description="Minimum vertical accuracy (meters)",
        ),
        DeclareLaunchArgument(
            "vio_pose_topic",
            default_value="/ov_msckf/pose",
            description="Input VIO pose topic (geometry_msgs/PoseWithCovarianceStamped)",
        ),
        DeclareLaunchArgument(
            "gps_input_topic",
            default_value="/mavros/gps_input/input",
            description="Output MAVROS GPS_INPUT topic",
        ),
        DeclareLaunchArgument(
            "input_frame",
            default_value="enu",
            description="Input pose frame: enu or ned",
        ),
        DeclareLaunchArgument(
            "ignore_velocity",
            default_value="true",
            description="Ignore velocity in GPS_INPUT (no VIO velocity)",
        ),
        DeclareLaunchArgument(
            "ignore_yaw",
            default_value="true",
            description="Ignore yaw in GPS_INPUT (use EV yaw instead)",
        ),
        DeclareLaunchArgument(
            "max_rate_hz",
            default_value="10.0",
            description="Maximum publish rate (Hz, 0 = unlimited)",
        ),
        DeclareLaunchArgument(
            "debug_logging", default_value="false", description="Enable debug logging"
        ),
        DeclareLaunchArgument(
            "config_file",
            default_value=PathJoinSubstitution(
                [FindPackageShare("fake_gps"), "config", "fake_gps.yaml"]
            ),
            description="Path to config YAML file",
        ),
    ]

    def launch_setup(context, *args, **kwargs):
        # Create node with parameters from launch arguments
        node = Node(
            package="fake_gps",
            executable="fake_gps_node",
            name="fake_gps_node",
            output="screen",
            parameters=[
                LaunchConfiguration("config_file"),
                {
                    "datum_lat": LaunchConfiguration("datum_lat"),
                    "datum_lon": LaunchConfiguration("datum_lon"),
                    "datum_alt": LaunchConfiguration("datum_alt"),
                    "fix_type": LaunchConfiguration("fix_type"),
                    "satellites_visible": LaunchConfiguration("satellites_visible"),
                    "horiz_accuracy": LaunchConfiguration("horiz_accuracy"),
                    "vert_accuracy": LaunchConfiguration("vert_accuracy"),
                    "vio_pose_topic": LaunchConfiguration("vio_pose_topic"),
                    "gps_input_topic": LaunchConfiguration("gps_input_topic"),
                    "input_frame": LaunchConfiguration("input_frame"),
                    "ignore_velocity": LaunchConfiguration("ignore_velocity"),
                    "ignore_yaw": LaunchConfiguration("ignore_yaw"),
                    "max_rate_hz": LaunchConfiguration("max_rate_hz"),
                    "debug_logging": LaunchConfiguration("debug_logging"),
                },
            ],
            remappings=[
                # Allow topic remapping via launch args
                (
                    LaunchConfiguration("vio_pose_topic"),
                    LaunchConfiguration("vio_pose_topic"),
                ),
                (
                    LaunchConfiguration("gps_input_topic"),
                    LaunchConfiguration("gps_input_topic"),
                ),
            ],
        )
        return [node]

    return LaunchDescription(args + [OpaqueFunction(function=launch_setup)])
