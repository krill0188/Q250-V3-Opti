# Gazebo ros_gz_bridge 마이그레이션 완료 (2024 최신 표준)

## 마이그레이션 요약: 구형 -> 신형

| 변경 전 (구형 gazebo_ros) | 변경 후 (신형 ros_gz_bridge) |
|---------------------------|------------------------------|
| libgazebo_ros_init.so + libgazebo_ros_factory.so | libgz-sim-ros.so (ros_gz_bridge) |
| SDF 내 센서별 플러그인 (libImuPlugin.so 등) | SDF에서 플러그인 제거, YAML로 브리지 설정 |
| 토픽명 하드코딩 | YAML 설정 파일로 관리 (config/ros_gz_bridge.yaml) |
| 메시지 변환 수동 | 자동 타입 매핑 (gz.msgs.IMU -> px4_msgs/SensorCombined) |
| 시뮬레이션 클럭 별도 동기화 | /clock 토픽 + use_sim_time: true로 자동 동기화 |

## 핵심 파일 변경 사항

### 1. 브리지 설정 YAML (config/ros_gz_bridge.yaml)
- IMU (400Hz): gz.msgs.IMU -> px4_msgs/SensorCombined
- Optical-Flow (100Hz): gz.msgs.OpticalFlow -> px4_msgs/OpticalFlow
- LiDAR (100Hz): gz.msgs.LaserScan -> px4_msgs/DistanceSensor
- GPS/Camera/Odometry: 선택적 브리지
- Offboard 제어: ROS_TO_GZ 방향 브리지 추가
- Clock 동기화: /clock 토픽 브리지

### 2. Launch 파일 업데이트 (launch/q250_v3_opti_sitl.launch.py)
- ros_gz_bridge 노드 추가 (parameter_bridge 실행)
- libgz-sim-ros.so 플러그인 로드 (gzserver -s libgz-sim-ros.so)
- Bridge 설정 YAML 파일 로드
- use_sim_time: true 파라미터 전달

### 3. 모델 SDF 정리 (model.sdf)
- 구형 센서 플러그인 제거: libImuPlugin.so, libOpticalFlowPlugin.so, libGazeboRosRaySensor.so, libGpsPlugin.so, libGazeboRosCamera.so
- 센서 정의만 유지 (플러그인 제거, ros_gz_bridge가 담당)
- PX4 SITL 플러그인(libPx4SITLPlugin.so)만 유지

### 4. 월드 파일 업데이트 (worlds/indoor_empty.world)
- plugin filename=libgz-sim-ros.so name=ros_gz_bridge 추가
- 설정 파일 경로 지정: config_file...

### 5. Offboard Control 노드 (offboard_control.cpp)
- use_sim_time: true 파라미터 설정
- /clock 토픽 구독으로 시뮬레이션 시간 동기화
- timestamp_ 우선, 없으면 sim_time_ 사용

## 필수 패키지 설치
sudo apt install gz-harmonic ros-humble-ros-gz-bridge ros-humble-ros-gz-sim

## 실행 방법 (ros_gz_bridge 버전)

### 터미널 1: Gazebo + PX4 SITL (ros_gz_bridge 플러그인 로드)
cd ~/PX4-Autopilot
PX4_SIM_MODEL=q250_v3_opti make px4_sitl gz_q250_v3_opti

### 터미널 2: ros_gz_bridge 노드 (별도 실행 권장)
ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/home/user/projectm/Q250-V3-Opti/config/ros_gz_bridge.yaml

### 터미널 3: uXRCE-DDS Agent
MicroXRCEAgent udp4 -p 8888

### 터미널 4: ROS2 Offboard 제어
cd ~/ros2_px4_ws
source install/setup.bash
ros2 launch offboard_control offboard_control.launch.py

### 터미널 5: 모니터링
ros2 topic echo /fmu/out/vehicle_local_position
ros2 topic echo /fmu/out/optical_flow
ros2 topic echo /fmu/out/distance_sensor
ros2 topic echo /clock

## 검증 체크리스트

1. 브리지 실행 확인
ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=config/ros_gz_bridge.yaml

2. 브리지 토픽 목록 확인
ros2 topic list | grep -E "(gz|fmu|clock)"

3. 브리지 상태 확인
ros2 service call /ros_gz_bridge/get_bridges ros_gz_interfaces/srv/GetBridges

4. 센서 데이터 수신 확인
ros2 topic echo /fmu/out/sensor_combined --once
ros2 topic echo /fmu/out/optical_flow --once
ros2 topic echo /fmu/out/distance_sensor --once

5. 시뮬레이션 클럭 확인
ros2 topic echo /clock --once

6. 전체 통합 테스트 (터미널 5개)
T1: ros2 launch q250_v3_opti q250_v3_opti_sitl.launch.py
T2: ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=config/ros_gz_bridge.yaml
T3: MicroXRCEAgent udp4 -p 8888
T4: ros2 launch offboard_control offboard_control.launch.py
T5: ros2 topic echo /fmu/out/vehicle_local_position

패키지 의존성 업데이트:

package.xml:
<depend>ros_gz_bridge</depend>
<depend>ros_gz_sim</depend>
<depend>gz_msgs</depend>
<depend>gz_sensors</depend>
<depend>rosgraph_msgs</depend>

CMakeLists.txt:
find_package(ros_gz_bridge REQUIRED)
find_package(ros_gz_sim REQUIRED)
find_package(gz_msgs REQUIRED)
find_package(gz_sensors REQUIRED)

ament_target_dependencies(offboard_control
  rclcpp px4_msgs geometry_msgs nav_msgs sensor_msgs std_msgs
  builtin_interfaces rclcpp_action ros_gz_bridge gz_msgs gz_sensors rosgraph_msgs
)

핵심 변경 사항 한 줄 요약:

Gazebo 센서 플러그인 제거 -> ros_gz_bridge YAML 설정으로 통합 -> Gazebo libgz-sim-ros.so 플러그인으로 로드 -> ROS 2에서 use_sim_time + /clock으로 시간 동기화

---

---

# Q250-V3 Opti 실전 실행 가이드 (Gazebo + PX4 + ROS2 + Silvus)

## 🎯 전체 아키텍처
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              개발 PC (WSL2/Ubuntu 22.04)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Gazebo Harmonic │  │ PX4 SITL        │  │ ROS 2 Humble                │  │
│  │ - q250_v3_opti  │◄─┤ libPx4SITLPlugin│◄─┤ offboard_control (C++)      │  │
│  │ - Indoor/Outdoor│  │ - MAVLink UDP   │  │ uXRCE-DDS Agent (8888)      │  │
│  │ - Sensors       │  │ - uXRCE-DDS     │  │ Silvus Monitor              │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────────┬──────────────┘  │
└───────────┼────────────────────┼──────────────────────────┼──────────────────┘
            │                    │                          │
            ▼                    ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Jetson Orin Nano (Onboard)                      │
│  ┌─────────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │ Silvus Air Unit │  │ ROS 2 Humble                                    │   │
│  │ (eth0, MN-MIMO) │◄─┤ - silvus_monitor (Link Quality)                │   │
│  └────────┬────────┘  │ - Offboard Control (Backup/Monitor)            │   │
│           │           │ - MAVLink Router (FC ↔ Silvus)                 │   │
│           ▼           └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Pixhawk 6C mini (FC)                                                │   │
│  │ - TELEM2: Jetson UART (921600) - MAVLink + uXRCE-DDS               │   │
│  │ - TELEM3: Silvus Serial (57600) - MAVLink Backup                   │   │
│  │ - UART4: Optical-Flow + LiDAR (115200)                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 실전 실행 순서 (단계별)

### Phase 1: 개발 환경 세팅 (1회만)
```bash
# 1. 개발 PC (WSL2) 세팅
cd /Users/amaster/projectm/Q250-V3-Opti
./scripts/setup/00_wsl2_dev_pc.sh
# → PowerShell에서: wsl --shutdown 후 재시작

# 2. Gazebo 모델 등록
./scripts/setup_gazebo_model.sh
source ~/.bashrc

# 3. PX4 펌웨어 빌드
cd ~/PX4-Autopilot
make px4_fmu-v6c_default -j8

# 4. ROS2 워크스페이스 빌드
cd ~/ros2_px4_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash
```

### Phase 2: 시뮬레이터 검증 (개발 PC)
```bash
# 터미널 1: Gazebo + PX4 SITL
cd ~/PX4-Autopilot
PX4_SIM_MODEL=q250_v3_opti make px4_sitl gz_q250_v3_opti

# 터미널 2: uXRCE-DDS Agent
MicroXRCEAgent udp4 -p 8888

# 터미널 3: ROS2 Offboard 제어
cd ~/ros2_px4_ws
source install/setup.bash
ros2 launch offboard_control offboard_control.launch.py

# 터미널 4: 모니터링
ros2 topic echo /fmu/out/vehicle_local_position
ros2 topic echo /fmu/out/vehicle_status
ros2 topic echo /fmu/out/optical_flow
ros2 topic echo /fmu/out/distance_sensor
```

**검증 체크리스트:**
- [ ] Gazebo에서 기체 모델 정상 로드 (프레임, 모터, 센서)
- [ ] PX4 SITL 부팅 완료 (QGC 연결됨)
- [ ] uXRCE-DDS Agent: "Client connected" 로그 확인
- [ ] ROS2 토픽 수신: vehicle_local_position, optical_flow, distance_sensor
- [ ] Offboard 모드 진입 → ARM → 이륙 → 사각형 미션 → 착륙 → Disarm
- [ ] 비행 로그 분석: `python3 scripts/postflight/analyze_log.py <log.ulg>`

---

### Phase 3: 실버스 데이터링크 벤치 테스트 (실기체 없음)
```bash
# 1. 실버스 장비 연결 (GDT 1대 + Air Unit 4대)
#    - GDT: 이더넷 → 개발 PC (192.168.10.254)
#    - Air Unit: 이더넷 → Jetson (각각 192.168.10.11~14)

# 2. 실버스 웹 UI 접속
#    http://192.168.10.254
#    → Mesh Topology 확인 (Gateway + 4 Nodes)
#    → RSSI/SNR/Throughput/Hops 확인

# 3. 네트워크 테스트
ping -i 0.01 -c 1000 192.168.10.11  # RTT < 10ms, Jitter < 2ms

# 4. MAVLink/ROS2 트래픽 테스트 (Jetson SSH 접속)
ssh jetson@192.168.10.11
ros2 topic list | grep fmu
ros2 topic echo /fmu/out/vehicle_status --once
```

---

### Phase 4: 기체 1대 통합 테스트 (실기체 + 실버스)
```bash
# 1. 하드웨어 연결 확인
# - Pixhawk 6C mini TELEM2 → Jetson UART (ttyTHS1, 921600)
# - Pixhawk UART4 → Optical-Flow/LiDAR (115200)
# - Silvus Air Unit eth0 → Jetson eth0 (이더넷)
# - Silvus Air Unit Serial → Pixhawk TELEM3 (57600, 백업)

# 2. Jetson 서비스 시작
sudo systemctl start mavlink-router
sudo systemctl start uxrce-dds-agent
systemctl status mavlink-router uxrce-dds-agent

# 3. 실버스 링크 모니터링 실행
python3 scripts/silvus_monitor.py --air-unit-ip 192.168.10.11

# 4. 비행 전 체크
./scripts/preflight/check_all.sh

# 5. 실내 호버링 테스트 (Position Mode)
# - QGC에서 Position Mode 선택
# - Arm → Throttle 50% 이륙 → 30초 호버링 → Land → Disarm
# - 드리프트 < 0.1m, 고도 ±0.05m 확인
```

---

### Phase 5: 다중 기체 군집 테스트 (2~4대)
```bash
# 1. 각 기체별 IP/네임스페이스 설정
# 기체 1: 192.168.10.11, namespace=uav1
# 기체 2: 192.168.10.12, namespace=uav2
# ...

# 2. Fast-DDS Discovery 설정 (각 기체 fastdds_config.xml)
# initialPeersList에 모든 기체 IP + Ground Station IP 등록

# 3. ROS2 DDS 통신 테스트
ros2 topic list | grep uav1
ros2 topic echo /uav1/fmu/out/vehicle_local_position

# 4. 군집 형성 비행 (Leader-Follower)
# - Leader: Offboard 사각형 미션
# - Follower: 상대 위치 오프셋 유지 (Behavior Tree)

# 5. 실버스 메쉬 릴레이 테스트
# - 기체 1-2-3-4 체인 구성 → 끝단 기체도 GCS 통신 가능한지 확인
```

---

### Phase 6: 자율비행 미션 (Offboard + Computer Vision)
```bash
# 1. Optical-Flow/LiDAR 기반 실내 웨이포인트 비행
ros2 launch offboard_control offboard_control.launch.py square_size:=3.0

# 2. VIO/카메라 연동 (옵션)
# - T265/D435i 장착 → EKF2_EV_CTRL=15 (EV fusion)
# - Fake GPS 테스트: GPS_FAKE=1 + EKF2_GPS_CTRL=7

# 3. 장애물 회피 (Depth Camera + nvblox)
# - Isaac ROS nvblox + cuMotion (Orin만 지원)
# - CP_DIST=1.0, CP_GAIN=1.0 설정

# 4. 군집 자율 미션
# - Swarm Coordinator (Ground Station) → 각 기체 Mission Upload
# - 실버스 메쉬로 상대 위치 공유 → 충돌 회피
```

---

## 🛠️ 트러블슈팅 퀵 레퍼런스

| 증상 | 원인 | 해결 |
|------|------|------|
| **Gazebo 모델 안 보임** | GAZEBO_MODEL_PATH 미설정 | `export GAZEBO_MODEL_PATH=~/projectm/Q250-V3-Opti/simulation/models:$GAZEBO_MODEL_PATH` |
| **PX4 SITL 모델 안 로드** | airframes/4001_q250_v3_opti 없음 | `./scripts/setup_gazebo_model.sh` 실행 |
| **uXRCE-DDS 연결 안됨** | Agent 포트 충돌/방화벽 | `sudo ufw allow 8888/udp`, `MicroXRCEAgent udp4 -p 8888` |
| **ROS2 토픽 안옴** | Fast-DDS Discovery 실패 | `fastdds_config.xml` initialPeersList 확인, `ROS_DOMAIN_ID=0` 확인 |
| **실버스 매쉬 안 맺힘** | 펌웨어 버전 불일치/채널/키 | 펌웨어 통일, AES-256 키 동일 입력, 채널폭 20MHz |
| **Optical-Flow 품질 낮음** | 조도 부족/바닥 단색 | 조도 > 100 Lux, 바닥 패턴 있는 매트 깔기 |
| **LiDAR 거리 NaN** | 센서 마운트 각도/장애물 | 센서 수평 장착 확인, 창문/거울 반사 제거 |
| **Position Mode 진입 안됨** | EKF2 수렴 실패 | EKF2_OF_CTRL=1, EKF2_RNG_CTRL=2, EKF2_HGT_REF=2 확인 |
| **Offboard 모드 거부** | 하트비트 타임아웃 | OffboardControlMode 2Hz+ 발행 확인, ARM 상태 확인 |
| **군집 DDS Discovery 안됨** | initialPeersList 누락/네트워크 | 각 기체 fastdds_config.xml에 모든 기체 IP 등록 |

---

## 📊 비행 로그 분석 자동화

```bash
# 비행 후 자동 분석
cd /Users/amaster/projectm/Q250-V3-Opti
python3 scripts/postflight/archive_logs.sh
python3 scripts/postflight/analyze_log.py ~/flight_logs/20261102_143000/flight_log.ulg

# 주요 지표 확인:
# ✓ XY Position Std < 0.05m (호버링)
# ✓ Z Position Std < 0.03m
# ✓ Flow Innovation RMS < 0.1 rad/s
# ✓ Range Innovation RMS < 0.05m
# ✓ Motor Balance < 5%
```

---

## 📅 주간/월간 정기 점검

| 주기 | 작업 |
|------|------|
| **매 비행 전** | `./scripts/preflight/check_all.sh`, 배터리/프롭/센서/링크 확인 |
| **주 1회** | 모터 베어링/ESC 온도, 프레임 나사 토크 (M3: 0.5Nm), 실버스 펌웨어 업데이트 확인 |
| **월 1회** | PX4 펌웨어/ROS2 패키지 업데이트, 파라미터 백업, SD카드 포맷 |
| **분기 1회** | Optical-Flow/LiDAR 캘리브레이션, 나침반 재캘 (실외), 실버스 안테나 점검 |

---

## 🔗 핵심 파일 위치 요약

| 카테고리 | 경로 |
|----------|------|
| **Gazebo 모델** | `~/projectm/Q250-V3-Opti/simulation/models/q250_v3_opti/` |
| **PX4 파라미터** | `~/projectm/Q250-V3-Opti/config/px4/q250-v3-opti_v1.15_baseline.params` |
| **PX4 Airframe** | `~/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/airframes/4001_q250_v3_opti` |
| **ROS2 Offboard** | `~/ros2_px4_ws/src/offboard_control/` |
| **실버스 모니터** | `~/projectm/Q250-V3-Opti/scripts/silvus_monitor.py` |
| **Fast-DDS 설정** | `~/fastdds_config.xml` (개발 PC) / `~/fastdds_config.xml` (Jetson) |
| **MAVLink Router** | `/etc/mavlink-router/main.conf` (Jetson) |
| **uXRCE-DDS Agent** | `/etc/systemd/system/uxrce-dds-agent.service` (Jetson) |
| **비행 로그** | `~/flight_logs/YYYYMMDD_HHMMSS/` |
| **Gazebo 월드** | `~/projectm/Q250-V3-Opti/simulation/worlds/` |

---

## 🎯 다음 단계 로드맵

| 단계 | 목표 | 예상 기간 |
|------|------|-----------|
| **Week 1** | 시뮬레이터 완성 (Gazebo + PX4 SITL + ROS2 Offboard) | 1주 |
| **Week 2** | 실버스 벤치 테스트 + 기체 1대 통합 | 1주 |
| **Week 3** | 실내 호버링 + Position Mode 자율비행 | 1주 |
| **Week 4** | Offboard 사각형 미션 + 로그 분석 튜닝 | 1주 |
| **Week 5-6** | 2~4대 군집 비행 (메쉬 릴레이/형성 비행) | 2주 |
| **Week 7-8** | VIO/카메라 연동 + 장애물 회피 + 실외 GPS 비행 | 2주 |

---

**💡 핵심 성공 요인**: **"시뮬레이터에서 파라미터/로직 100% 검증 → 실기체 1대 비행 검증 → 다중 기체 확장"**

이 순서를 지키면 하드웨어 파손/시간 낭비 최소화하며 군집 자율비행까지 도달 가능합니다.
