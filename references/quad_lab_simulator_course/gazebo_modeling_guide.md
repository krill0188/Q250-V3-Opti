# Q250-V3 Opti Gazebo 모델링 가이드 (강좌 3편 기반)

## 디렉토리 구조
```
simulation/models/q250_v3_opti/
├── model.sdf                 # 메인 모델 정의
├── model.config              # 모델 메타데이터
├── meshes/                   # 3D 메쉬 파일 (STL/DAE/OBJ)
│   ├── frame.stl
│   ├── motor.stl
│   ├── propeller.stl
│   ├── camera_mount.stl
│   ├── jetson_mount.stl
│   └── battery_holder.stl
├── sensors/                  # 센서 플러그인 설정
│   ├── optical_flow.sdf
│   ├── lidar.sdf
│   ├── imu.sdf
│   ├── gps.sdf
│   └── camera.sdf
├── plugins/                  # 커스텀 플러그인 (필요시)
│   ├── q250_motor_plugin.cc
│   └── CMakeLists.txt
└── launch/
    ├── q250_v3_opti.launch.py
    └── q250_v3_opti_sitl.launch.py
```

## model.sdf 핵심 구조 (Q250-V3 Opti 실사양 반영)

```xml
<?xml version="1.0" ?>
<sdf version="1.9">
  <model name="q250_v3_opti">
    <static>false</static>
    
    <!-- 링크: 베이스 프레임 -->
    <link name="base_link">
      <pose>0 0 0.05 0 0 0</pose>  <!-- 지면에서 5cm 높이 -->
      <inertial>
        <mass>1.08</mass>  <!-- 총 중량: 배터리+Jetson+카메라 포함 1.08kg -->
        <inertia>
          <ixx>0.008</ixx>
          <ixy>0</ixy>
          <ixz>0</ixz>
          <iyy>0.008</iyy>
          <iyz>0</iyz>
          <izz>0.014</izz>
        </inertia>
        <pose>0 0 0 0 0 0</pose>
      </inertial>
      
      <collision name="base_collision">
        <geometry>
          <box><size>0.3 0.3 0.1</size></box>  <!-- 케이지 프레임 대략적 크기 -->
        </geometry>
      </collision>
      
      <visual name="base_visual">
        <geometry>
          <mesh><uri>model://q250_v3_opti/meshes/frame.stl</uri></mesh>
        </geometry>
      </visual>
    </link>

    <!-- 모터 4개 (AUX 1-4, DShot300) -->
    <!-- 모터 1: 전방 우측 (CW) -->
    <joint name="motor1_joint" type="revolute">
      <parent>base_link</parent>
      <child>motor1_link</child>
      <axis>
        <xyz>0 0 1</xyz>
        <limit><lower>-1e16</lower><upper>1e16</upper></limit>
        <dynamics><damping>0.001</damping><friction>0.001</friction></dynamics>
      </axis>
      <pose>0.12 -0.12 -0.025 0 0 0</pose>  <!-- FRD, COG 기준 -->
    </joint>
    <link name="motor1_link">
      <inertial>
        <mass>0.05</mass>
        <inertia><ixx>0.0001</ixx><iyy>0.0001</iyy><izz>0.0002</izz></inertia>
      </inertial>
      <collision><geometry><cylinder><radius>0.025</radius><length>0.03</length></cylinder></geometry></collision>
      <visual><geometry><mesh><uri>model://q250_v3_opti/meshes/motor.stl</uri></mesh></geometry></visual>
    </link>

    <!-- 모터 2: 후방 우측 (CW) -->
    <joint name="motor2_joint" type="revolute">
      <parent>base_link</parent>
      <child>motor2_link</child>
      <axis><xyz>0 0 1</xyz></axis>
      <pose>-0.12 -0.12 -0.025 0 0 0</pose>
    </joint>
    <!-- ... motor2_link 동일 정의 ... -->

    <!-- 모터 3: 전방 좌측 (CCW) -->
    <joint name="motor3_joint" type="revolute">
      <parent>base_link</parent>
      <child>motor3_link</child>
      <axis><xyz>0 0 1</xyz></axis>
      <pose>0.12 0.12 -0.025 0 0 0</pose>
    </joint>
    <!-- ... motor3_link ... -->

    <!-- 모터 4: 후방 좌측 (CCW) -->
    <joint name="motor4_joint" type="revolute">
      <parent>base_link</parent>
      <child>motor4_link</child>
      <axis><xyz>0 0 1</xyz></axis>
      <pose>-0.12 0.12 -0.025 0 0 0</pose>
    </joint>
    <!-- ... motor4_link ... -->

    <!-- 프로펠러 (시각화용, 물리엔진은 모터 조인트 토크로 처리) -->
    <!-- 각 모터 링크 하위에 visual만 추가 -->

    <!-- 센서: Optical-Flow + LiDAR (UART4, 전방 하향) -->
    <link name="of_lidar_link">
      <pose>0 0 -0.04 0 0 0</pose>  <!-- 베이스 아래 4cm -->
      <inertial><mass>0.02</mass><inertia><ixx>0.00001</ixx><iyy>0.00001</iyy><izz>0.00002</izz></inertia></inertial>
    </link>
    <joint name="of_lidar_joint" type="fixed">
      <parent>base_link</parent>
      <child>of_lidar_link</child>
    </joint>

    <!-- 센서: IMU (FC 내장, base_link 중심) -->
    <!-- link/base_link에 imu 센서 플러그인 추가 -->

    <!-- 센서: GPS (옵션, TELEM3) -->
    <link name="gps_link">
      <pose>0 0 0.05 0 0 0</pose>
    </link>
    <joint name="gps_joint" type="fixed">
      <parent>base_link</parent>
      <child>gps_link</child>
    </joint>

    <!-- 플러그인: Multicopter Motor Model (PX4 호환) -->
    <plugin name="multicopter_motor_model" filename="libMulticopterMotorModel.so">
      <rotorDragCoefficient>0.001</rotorDragCoefficient>
      <motorConstant>8.5e-06</motorConstant>  <!-- 추력 계수 -->
      <momentConstant>0.016</momentConstant>  <!-- 토크 계수 -->
      <maxRotVelocity>1200</maxRotVelocity>   <!-- rad/s -->
      <motorNumber>4</motorNumber>
      <rotorDragCoefficient>0.001</rotorDragCoefficient>
      <motorModelType>0</motorModelType>
      <motorConstantsFromKV>True</motorConstantsFromKV>
      <kv>1000</kv>  <!-- 모터 KV 값 -->
      <cellCount>4</cellCount>  <!-- 4S LiPo -->
      <motorResistance>0.05</motorResistance>
      <motorInductance>0.0001</motorInductance>
    </plugin>

    <!-- 플러그인: PX4 SITL 인터페이스 -->
    <plugin name="px4_sitl" filename="libPx4SITLPlugin.so">
      <modelName>q250_v3_opti</modelName>
      <paramFile>model://q250_v3_opti/px4_params.txt</paramFile>
    </plugin>
  </model>
</sdf>
```

## 센서 플러그인 별도 파일 예시

### Optical-Flow (sensors/optical_flow.sdf)
```xml
<sensor name="optical_flow" type="optical_flow">
  <always_on>true</always_on>
  <update_rate>100</update_rate>  <!-- 100Hz -->
  <visualize>true</visualize>
  <optical_flow>
    <focal_length>1.0</focal_length>  <!-- 픽셀 단위 초점 거리 -->
    <image_width>64</image_width>
    <image_height>64</image_height>
    <min_distance>0.1</min_distance>
    <max_distance>10.0</max_distance>
    <noise>
      <type>gaussian</type>
      <mean>0.0</mean>
      <stddev>0.01</stddev>  <!-- 픽셀 단위 노이즈 -->
    </noise>
  </optical_flow>
  <plugin name="optical_flow_plugin" filename="libOpticalFlowPlugin.so">
    <robotNamespace>/q250_v3_opti</robotNamespace>
    <topicName>/optical_flow</topicName>
    <frameId>of_lidar_link</frameId>
  </plugin>
</sensor>
```

### LiDAR (sensors/lidar.sdf)
```xml
<sensor name="lidar" type="ray">
  <always_on>true</always_on>
  <update_rate>100</update_rate>
  <visualize>true</visualize>
  <ray>
    <scan>
      <horizontal>
        <samples>1</samples>
        <resolution>1</resolution>
        <min_angle>0</min_angle>
        <max_angle>0</max_angle>
      </horizontal>
      <vertical>
        <samples>1</samples>
        <resolution>1</resolution>
        <min_angle>0</min_angle>
        <max_angle>0</max_angle>
      </vertical>
    </scan>
    <range>
      <min>0.02</min>
      <max>11.0</max>
      <resolution>0.01</resolution>
    </range>
    <noise>
      <type>gaussian</type>
      <mean>0.0</mean>
      <stddev>0.02</stddev>
    </noise>
  </ray>
  <plugin name="lidar_plugin" filename="libGazeboRosRaySensor.so">
    <topicName>/lidar</topicName>
    <frameId>of_lidar_link</frameId>
  </plugin>
</sensor>
```

## Launch 파일 예시 (launch/q250_v3_opti_sitl.launch.py)
```python
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # 환경 변수
    gazebo_model_path = SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH',
        os.path.join(get_package_share_directory('q250_v3_opti'), 'models')
    )
    
    # Gazebo 실행 (PX4 SITL용 월드)
    gzserver = ExecuteProcess(
        cmd=['gzserver', '--verbose', '-s', 'libgazebo_ros_init.so', 
             '-s', 'libgazebo_ros_factory.so',
             os.path.join(get_package_share_directory('px4'), 'worlds', 'empty.world')],
        output='screen'
    )
    
    gzclient = ExecuteProcess(
        cmd=['gzclient'],
        output='screen'
    )
    
    # PX4 SITL 실행 (별도 터미널에서 실행 권장)
    # px4_sitl = ExecuteProcess(
    #     cmd=['make', 'px4_sitl', 'gz_q250_v3_opti'],
    #     cwd=os.path.expanduser('~/PX4-Autopilot'),
    #     output='screen'
    # )
    
    # ROS2 브리지 (uXRCE-DDS Agent)
    uxrce_agent = ExecuteProcess(
        cmd=['MicroXRCEAgent', 'udp4', '-p', '8888'],
        output='screen'
    )
    
    return LaunchDescription([
        gazebo_model_path,
        gzserver,
        gzclient,
        uxrce_agent,
    ])
```

## PX4 파라미터 파일 (simulation/models/q250_v3_opti/px4_params.txt)
```
# Q250-V3 Opti SITL 파라미터 (실기체와 동일하게)
SYS_AUTOSTART=4001  # Generic Quadrotor
SYS_AUTOCONFIG=1
MAV_TYPE=2

# 기체 지오메트리
CA_AIRFRAME=0
CA_ROTOR_COUNT=4
CA_MOT_POS_X1=0.12
CA_MOT_POS_Y1=-0.12
CA_MOT_POS_Z1=-0.025
CA_MOT_DIR_CCW1=0
CA_MOT_POS_X2=-0.12
CA_MOT_POS_Y2=-0.12
CA_MOT_POS_Z2=-0.025
CA_MOT_DIR_CCW2=0
CA_MOT_POS_X3=0.12
CA_MOT_POS_Y3=0.12
CA_MOT_POS_Z3=-0.025
CA_MOT_DIR_CCW3=1
CA_MOT_POS_X4=-0.12
CA_MOT_POS_Y4=0.12
CA_MOT_POS_Z4=-0.025
CA_MOT_DIR_CCW4=1

# Optical-Flow & LiDAR
EKF2_OF_CTRL=1
EKF2_RNG_CTRL=2
EKF2_HGT_REF=2
SENS_FLOW_ROT=0
EKF2_OF_POS_Z=-0.035
EKF2_RNG_POS_Z=-0.040
EKF2_RNG_NOISE=0.02

# Companion (uXRCE-DDS)
UXRCE_DDS_CFG=2
UXRCE_DDS_AG_IP=2130706433
UXRCE_DDS_PRT=8888
SER_TEL2_BAUD=921600

# 배터리
BAT_V_DIV=54.5
BAT_A_PER_V=18.0
BAT_N_CELLS=4
BAT_CAPACITY=4000
```

## 실행 순서 (터미널 3개 필요)

### 터미널 1: Gazebo + PX4 SITL
```bash
cd ~/PX4-Autopilot
# Q250-V3 Opti 모델을 PX4에 등록 후
make px4_sitl gz_q250_v3_opti
# 또는 커스텀 모델 경로 지정:
# PX4_SIM_MODEL=q250_v3_opti make px4_sitl gz_x500
```

### 터미널 2: uXRCE-DDS Agent
```bash
MicroXRCEAgent udp4 -p 8888
```

### 터미널 3: ROS2 워크스페이스 + Offboard 제어
```bash
cd ~/ros2_px4_ws
source install/setup.bash
ros2 run offboard_control offboard_control
```

## 강좌 3편 시청하면서 체크할 것
- [ ] 모델 질량/관성 텐서 값 (영상에서 언급하는 값)
- [ ] 모터 KV 값, 프로펠러 크기/피치
- [ ] Optical-Flow 센서 초점 거리, 해상도, 업데이트 레이트
- [ ] LiDAR 최대/최소 거리, 업데이트 레이트, FOV
- [ ] 카메라 센서 (있는 경우) 해상도, FOV, fps
- [ ] Gazebo 월드 설정 (중력, 공기 밀도, 지면 마찰)
- [ ] PX4 SITL에서 커스텀 모델 등록 방법 (ROMFS/px4fmu_common/init.d-posix/airframes/)
