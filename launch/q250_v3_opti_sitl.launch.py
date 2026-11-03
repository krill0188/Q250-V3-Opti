from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # 경로 설정
    model_path = os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'models')
    world_path = os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'worlds')
    config_path = os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'config')
    
    # Launch 인자
    world_arg = DeclareLaunchArgument(
        'world', default_value='indoor_empty.world',
        description='Gazebo world file'
    )
    bridge_config_arg = DeclareLaunchArgument(
        'bridge_config', 
        default_value=os.path.join(config_path, 'ros_gz_bridge.yaml'),
        description='ros_gz_bridge YAML config file'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation time'
    )

    # Gazebo Server (ros_gz_bridge 플러그인 로드)
    gzserver = ExecuteProcess(
        cmd=['gzserver', '--verbose', 
             '-s', 'libgz-sim-ros.so',           # ros_gz_bridge 플러그인
             '-s', 'libgazebo_ros_factory.so',   # 엔티티 팩토리 (스폰용)
             PathJoinSubstitution([world_path, LaunchConfiguration('world')])],
        output='screen',
        env={'GZ_SIM_RESOURCE_PATH': os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'models')}
    )
    
    gzclient = ExecuteProcess(
        cmd=['gzclient'],
        output='screen'
    )

    # ============================================================
    # ros_gz_bridge 노드 (핵심!)
    # ============================================================
    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge',
        output='screen',
        parameters=[{
            'config_file': LaunchConfiguration('bridge_config'),
            'expand_gz_topics': True,
            'lazy': False,
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
        remappings=[
            ('/clock', '/clock'),  # 시뮬레이션 클럭 동기화
        ]
    )

    # uXRCE-DDS Agent
    uxrce_agent = ExecuteProcess(
        cmd=['MicroXRCEAgent', 'udp4', '-p', '8888'],
        output='screen'
    )

    # Offboard Control Node
    offboard_control = Node(
        package='offboard_control',
        executable='offboard_control',
        name='offboard_control',
        output='screen',
        parameters=[{
            'takeoff_height': -1.5,
            'hover_duration': 10.0,
            'square_size': 2.0,
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='indoor_empty.world'),
        DeclareLaunchArgument('bridge_config', default_value=os.path.join(
            os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'config', 'ros_gz_bridge.yaml')),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        SetEnvironmentVariable('GAZEBO_MODEL_PATH', 
            os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'models')),
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', 
            os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'models')),
        SetEnvironmentVariable('ROS_DOMAIN_ID', '0'),
        
        # Gazebo 서버 (ros_gz_bridge 플러그인 로드)
        ExecuteProcess(
            cmd=['gzserver', '--verbose', 
                 '-s', 'libgz-sim-ros.so',           # ros_gz_bridge 플러그인
                 '-s', 'libgazebo_ros_factory.so',   # 엔티티 팩토리
                 '-r', '-v', '4',
                 PathJoinSubstitution([
                     os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'worlds', 
                     LaunchConfiguration('world')
                 ])],
        output='screen',
        env={
            'GZ_SIM_RESOURCE_PATH': os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'models'),
            'GAZEBO_MODEL_PATH': os.path.join(os.path.expanduser('~'), 'projectm', 'Q250-V3-Opti', 'simulation', 'models'),
        }),
        
        ExecuteProcess(
            cmd=['gzclient'],
            output='screen'
        ),
        
        # ros_gz_bridge 노드 (Gazebo 서버 시작 후 실행)
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='ros_gz_bridge',
            output='screen',
            parameters=[{
                'config_file': '/home/user/projectm/Q250-V3-Opti/config/ros_gz_bridge.yaml',
                'expand_gz_topics': True,
                'lazy': False,
                'use_sim_time': True,
            }],
        ),
        
        # uXRCE-DDS Agent
        ExecuteProcess(
            cmd=['MicroXRCEAgent', 'udp4', '-p', '8888'],
            output='screen'
        ),
        
        # Offboard Control Node
        Node(
            package='offboard_control',
            executable='offboard_control',
            name='offboard_control',
            output='screen',
            parameters=[{
                'takeoff_height': -1.5,
                'hover_duration': 10.0,
                'square_size': 2.0,
                'use_sim_time': True,
            }],
        ),
    ])
