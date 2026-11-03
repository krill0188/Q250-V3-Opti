# Q250-V3 Opti 참조 자료 인덱스

## 📚 공식 문서 링크 모음

### 쿼드 드론연구소 (제조사 공식)
| 문서 | URL | 설명 |
|------|-----|------|
| Q250-V3 Opti 메인 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/q250-v3-opti | 전체 가이드 진입점 |
| Optical-Flow & LiDAR | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/q250-v3-opti/optical-flow-and-lidar | 센서 설정 상세 |
| Actuators / DShot | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/actuators | 모터/ESC 설정 |
| 컴패니언 컴퓨터 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/undefined-3 | Jetson 연결 |
| 전원 설정 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/undefined-1 | 배터리/UBEC |
| Flight Behavior | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/flight-behavior | 비행 특성 튜닝 |
| VIO non-GPS | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/1-vio-non-gps | 비전 기반 항법 |
| 자율 회피 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/2 | 장애물 회피 |
| Fake GPS | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/3-fake_gps-gps | 가상 GPS |
| MAVROS Teleop | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/4-mavros_teleop | 키보드 조종 |
| 전체 인덱스 (llms.txt) | https://quad-drone-lab.gitbook.io/quad-drone-start/llms.txt | 전체 문서 목록 |

### PX4 공식 문서 (v1.15)
| 문서 | URL |
|------|-----|
| Multicopter Config | https://docs.px4.io/main/en/config_mc |
| Actuator Configuration | https://docs.px4.io/main/en/config/actuators |
| Airframe Selection | https://docs.px4.io/main/en/config/airframe |
| Optical Flow Setup | https://docs.px4.io/main/en/sensor/optical_flow |
| EKF2 Tuning Guide | https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf |
| Parameter Reference | https://docs.px4.io/main/en/advanced_config/parameter_reference |
| ROS 2 User Guide | https://docs.px4.io/main/en/ros2/user_guide |
| uXRCE-DDS Middleware | https://docs.px4.io/main/en/middleware/uxrce_dds |
| Companion Computer | https://docs.px4.io/main/en/companion_computer/index |
| Offboard Control | https://docs.px4.io/main/en/ros2/offboard_control |

### ROS 2 / MAVROS
| 문서 | URL |
|------|-----|
| MAVROS ROS 2 | https://github.com/mavlink/mavros/blob/ros2/mavros/README.md |
| MAVROS Docs | https://mavros.readthedocs.io/en/latest/ |
| px4_msgs | https://github.com/PX4/px4_msgs |
| px4_ros_com | https://github.com/PX4/px4_ros_com |
| Fast-DDS Discovery | https://fast-dds.docs.eprosima.com/en/latest/fastdds/discovery/discovery.html |
| Micro-XRCE-DDS-Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent |

### 하드웨어 레퍼런스
| 문서 | URL |
|------|-----|
| Pixhawk 6C mini | https://docs.px4.io/main/en/flight_controller/pixhawk6c_mini.html |
| Holybro PM07 | https://holybro.com/products/pm07 |
| Jetson Nano DevKit | https://developer.nvidia.com/embedded/jetson-nano-developer-kit |
| BLHeli_32 Config | https://github.com/bitdump/BLHeli |

---

## 🔧 주요 파라미터 빠른 참조

### Optical-Flow & LiDAR (UART4)
```
MAV_1_CONFIG = 4 (TELEM4)
MAV_1_MODE = 1 (Normal)
SER_TEL4_BAUD = 115200
SENS_FLOW_ROT = 0
EKF2_OF_CTRL = 1
EKF2_RNG_CTRL = 2
EKF2_HGT_REF = 2
```

### EKF2 실내 튜닝
```
EKF2_GPS_CTRL = 0
EKF2_MAG_TYPE = 5
EKF2_AID_MASK = 200
EKF2_OF_POS_Z = -0.035
EKF2_RNG_POS_Z = -0.040
EKF2_RNG_NOISE = 0.02
```

### uXRCE-DDS (TELEM2)
```
UXRCE_DDS_CFG = 2
UXRCE_DDS_AG_IP = 2130706433 (127.0.0.1 INT32)
UXRCE_DDS_PRT = 8888
SER_TEL2_BAUD = 921600
```

### Battery (PM07)
```
BAT_V_DIV = 54.5
BAT_A_PER_V = 18.0
BAT_N_CELLS = 4
BAT_CAPACITY = 4000
```

### Flight Behavior
```
MPC_XY_VEL_MAX = 3.0
MPC_Z_VEL_MAX_UP = 2.0
MPC_Z_VEL_MAX_DN = 1.5
MPC_TILTMAX_AIR = 35.0
```

---

## 🛠️ 자주 사용하는 명령어

### Jetson 서비스 관리
```bash
# 서비스 상태
systemctl status mavlink-router uxrce-dds-agent

# 로그 실시간 확인
journalctl -fu mavlink-router
journalctl -fu uxrce-dds-agent

# 재시작
sudo systemctl restart mavlink-router uxrce-dds-agent
```

### ROS 2 토픽 확인
```bash
# 환경 설정
source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash

# 토픽 리스트
ros2 topic list | grep fmu

# 실시간 데이터
ros2 topic echo /fmu/out/vehicle_local_position
ros2 topic echo /fmu/out/vehicle_status
ros2 topic echo /fmu/out/battery_status
```

### 비행 로그 분석
```bash
# pyulog 설치
pip install pyulog

# .ulg → CSV
ulog2csv flight_log.ulg -o ./logs/

# 분석 스크립트
python3 ~/scripts/postflight/analyze_log.py flight_log.ulg
```

### 네트워크 진단
```bash
# 연결 확인
ping 192.168.10.1

# 포트 확인
nc -zv 192.168.10.1 8888
nc -zv 192.168.10.1 14550

# MAVLink 트래픽
mavlink-routerd -c /etc/mavlink-router/main.conf -d
```

---

## 📁 프로젝트 파일 구조 참조

```
Q250-V3-Opti/
├── docs/
│   ├── manual-draft.md          # 초안 (이 문서의 기반)
│   ├── manual-final.docx        # 완성본 (그림 포함)
│   ├── images/                  # 사진 파일들
│   └── diagrams/                # 다이어그램 소스
│       ├── system_architecture.mmd
│       ├── network_topology.mmd
│       ├── power_system.mmd
│       ├── fc_portmap.mmd
│       ├── flight_mode_fsm.mmd
│       ├── ekf2_sensor_fusion.mmd
│       └── complete_workflow.mmd
├── config/
│   ├── px4/q250-v3-opti_v1.15_baseline.params
│   ├── mavlink-router/main.conf
│   ├── jetson/uxrce-dds-agent.service
│   ├── jetson/fastdds_config.xml
│   └── network/*.yaml, setup_ufw.sh
├── scripts/
│   ├── setup/01-05_*.sh, apply_configs.sh
│   ├── preflight/check_all.sh
│   ├── inflight/monitor.sh
│   └── postflight/archive_logs.sh, analyze_log.py
├── ros2_ws/src/                 # ROS 2 패키지 소스
├── px4_params/                  # 파라미터 버전 관리
├── flight_logs/                 # 비행 로그 아카이브
└── simulation/                  # Gazebo SITL 환경
```

---

## 🎯 버전 히스토리

| 버전 | 날짜 | 변경사항 |
|------|------|----------|
| 0.1 | 2026-11-02 | 초기 초안 작성 (HW→SW설치→SW설정→운용 순서) |
| 1.0 | - | 그림/사진/개념도 포함 완성본 예정 |

---

*최종 업데이트: 2026-11-02*
