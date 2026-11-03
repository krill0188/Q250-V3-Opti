# 12. 자율 회피 파이프라인 & 테스트 시나리오 (실내 비행 안전성)

> `jetson-px4-ros2-autonomous-drone/docs/12-obstacle-avoidance.md`를 Q250-V3-Opti 실기체 환경(Silvus 데이터링크, Optical-Flow+LiDAR+RealSense 옵션)에 맞춰 재구성했습니다.

---

## 12.1 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        센서 계층                                     │
├─────────────────────────────────────────────────────────────────────┤
│  RealSense D435i (RGB/Depth/IMU)    │  LiDAR (TF-Luna/SF45 등)     │
│  Optical-Flow (PMW3901)             │  Ultrasonic (착륙용)          │
└─────────────────────┬─────────────────┬─────────────────────────────┘
                      ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    인식/표현 계층 (ROS 2)                            │
├─────────────────────────────────────────────────────────────────────┤
│  depth_image → pointcloud (depth_image_proc)                        │
│  pointcloud → voxel grid / costmap (voxel_grid, costmap_2d)        │
│  Optical-Flow → velocity XY (PX4 내부 EKF2 융합)                    │
│  LiDAR → obstacle_distance (MAVLink OBSTACLE_DISTANCE)             │
└─────────────────────┬───────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     플래너 계층 (ROS 2)                              │
├─────────────────────────────────────────────────────────────────────┤
│  Local Planner (TEB / DWA / 커스텀)                                 │
│  입력: goal pose, costmap, current velocity, obstacle_distance     │
│  출력: velocity setpoint (vx, vy, vz, yaw_rate)                    │
│  안전: max_vel, max_acc, min_obstacle_dist, inflation_radius       │
└─────────────────────┬───────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   제어 인터페이스 계층                               │
├─────────────────────────────────────────────────────────────────────┤
│  MAVROS: /mavros/setpoint_velocity/cmd_vel (Twist)                 │
│  px4_ros_com: VehicleVelocitySetpoint (uXRCE-DDS)                  │
│  둘 중 하나만 활성화 (동시 사용 금지)                               │
└─────────────────────┬───────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PX4 비행 컨트롤러                               │
├─────────────────────────────────────────────────────────────────────┤
│  Position/Velocity Controller → Attitude → Rate → Actuator         │
│  OFFBOARD 모드 유지: 2Hz 이상 setpoint 전송 필수                   │
│  Failsafe: COM_OF_LOSS_T, COM_OBL_RC_ACT, GF_ACTION                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 12.2 센서별 설정 (Q250-V3-Opti 하드웨어 기준)

### 12.2.1 RealSense D435i (선택: 자율비행 확장 시 장착)
```yaml
# config/ros2/realsense.yaml
realsense:
  ros__parameters:
    enable_depth: true
    enable_color: true
    enable_infra: false
    depth_module:
      profile: "640x480x30"
    color_module:
      profile: "640x480x30"
    unite_imu_method: 1  # IMU 프레임 통합
    pointcloud:
      enable: true
      stream_filter: 2  # depth만
```

### 12.2.2 LiDAR (TF-Luna, UART/TELEM4)
```bash
# PX4 파라미터 (기존 baseline에 포함)
SENS_TF_LUNA_CFG  1     # TF-Luna 활성화
SER_TEL4_BAUD     115200
EKF2_RNG_CTRL     2     # Range finder continuous mode
EKF2_RNG_POS_Z   -0.04  # LiDAR 위치 (m)
EKF2_RNG_NOISE    0.02
```

### 12.2.3 Optical-Flow (PMW3901, UART/TELEM4) - **이미 장착됨**
```bash
# PX4 파라미터 (기존 baseline에 포함)
MAV_1_CONFIG      4     # TELEM4 = Optical-Flow
SER_TEL4_BAUD     115200
EKF2_OF_CTRL      1     # OF velocity fusion
EKF2_OF_POS_Z    -0.035
EKF2_OF_DELAY     5
EKF2_OF_QMIN      100
EKF2_OF_NEIG_NR   3
```

---

## 12.3 ROS 2 노드 구성 (권장 최소 세트)

| 노드 | 패키지 | 역할 | 입력 | 출력 |
|------|--------|------|------|------|
| `realsense_node` | `realsense2_camera` | 카메라 드라이버 | - | `/camera/depth/image_rect_raw`, `/camera/imu` |
| `depth_to_pc` | `depth_image_proc` | Depth → PointCloud | `/camera/depth/image_rect_raw` | `/camera/depth/points` |
| `voxel_grid` | `voxel_grid` | PointCloud 다운샘플/보옐화 | `/camera/depth/points` | `/obstacles/voxel_grid` |
| `costmap_2d` | `nav2_costmap_2d` | 2D/3D 코스트맵 | `/obstacles/voxel_grid`, `/tf` | `/local_costmap` |
| `local_planner` | `teb_local_planner` 또는 커스텀 | 로컬 경로/속도 생성 | `/local_costmap`, `/odom`, `/goal` | `/cmd_vel` (Twist) |
| `obstacle_distance_pub` | 커스텀/MAVROS | LiDAR → MAVLink | `/tf`, `/mavros/distance_sensor` | `OBSTACLE_DISTANCE` |

---

## 12.4 플래너 설정 예시 (TEB Local Planner)

```yaml
# config/ros2/teb_local_planner_params.yaml
TebLocalPlannerROS:
  odom_topic: /mavros/local_position/odom  # 또는 /fmu/out/vehicle_local_position
  map_frame: odom
  robot_frame: base_link

  # 로봇 제약
  max_vel_x: 2.0
  max_vel_x_backwards: 0.5
  max_vel_y: 1.0
  max_vel_theta: 1.5
  acc_lim_x: 1.0
  acc_lim_y: 1.0
  acc_lim_theta: 1.0

  # 목표 공차
  xy_goal_tolerance: 0.2
  yaw_goal_tolerance: 0.1
  free_goal_vel: false

  # 장애물
  min_obstacle_dist: 0.5      # 최소 장애물 거리 (m)
  inflation_dist: 0.8         # 팽창 반경 (m)
  include_costmap_obstacles: true
  costmap_obstacles_behind_robot_dist: 1.5
  obstacle_poses_affected: 30

  # 최적화
  no_inner_iterations: 5
  no_outer_iterations: 4
  optimization_activate: true
  optimization_verbose: false

  # 가중치
  weight_max_vel_x: 2
  weight_max_vel_theta: 1
  weight_acc_lim_x: 1
  weight_acc_lim_theta: 1
  weight_kinematics_nh: 1
  weight_kinematics_forward_drive: 1
  weight_kinematics_turning_radius: 1
  weight_optimaltime: 1
  weight_obstacle: 50
  weight_inflation: 10
```

---

## 12.5 PX4 파라미터 (회피/안전 관련)

```bash
# OFFBOARD 유지
COM_OF_LOSS_T   1.0     # OFFBOARD setpoint 손실 시 이탈 시간 (s)
COM_OBL_RC_ACT  2       # RC 손실 시: 2=Position 모드로 복귀
COM_RC_LOSS_T   0.5     # RC 손실 감지 시간 (s)

# Geofence (실내 안전)
GF_ACTION       1       # 1=RTL, 2=Land, 3=Terminate
GF_MAX_HOR_DIST 10.0    # 최대 수평 거리 (m)
GF_MAX_VER_DIST 2.5     # 최대 고도 (m)
GF_SOURCE       1       # 1=GPS, 2=Local position

# Obstacle avoidance (PX4 네이티브, MAVROS/px4_ros_com로 obstacle_distance 수신 시)
CP_DIST         1.0     # 충돌 방지 최소 거리 (m)
CP_GAIN         1.0     # 회피 게인
CP_MAX_ANGLE    30.0    # 최대 회피 각도 (deg)
```

---

## 12.6 단계별 테스트 시나리오 (필수 통과)

> **원칙**: 각 단계가 로그로 검증된 뒤에만 다음 단계 진행. 프로펠러 제거 상태에서 시작.

### Phase 1: 센서/토픽 검증 (정지 상태)
| # | 테스트 | 성공 기준 |
|---|--------|-----------|
| 1.1 | Depth image 발행 확인 | `ros2 topic hz /camera/depth/image_rect_raw` → 30Hz 안정 |
| 1.2 | PointCloud 생성 확인 | `/camera/depth/points` 발행, 포인트 수 > 10000 |
| 1.3 | TF 트리 확인 | `odom → base_link → camera_link` 끊김 없음 |
| 1.4 | LiDAR 거리 측정 확인 | `/mavros/distance_sensor/rangefinder_pub` 발행, 값 정확 |
| 1.5 | Optical-Flow 품질 확인 | QGC: `OPTICAL_FLOW_RAD` 품질 > 100, 유량 데이터 안정 |

### Phase 2: 비용맵/장애물 표현 검증 (정지 상태)
| # | 테스트 | 성공 기준 |
|---|--------|-----------|
| 2.1 | Voxel grid 생성 | `/obstacles/voxel_grid` 발행, 장애물 보이셀 확인 |
| 2.2 | Costmap 생성 | `/local_costmap/costmap` 발행, 장애물 주변 팽창 확인 |
| 2.3 | Costmap 업데이트율 | 5Hz 이상, 지연 < 200ms |
| 2.4 | Blind spot 확인 | 카메라 하단/후방 블라인드 스팟 크기 측정 |

### Phase 3: 플래너 단독 테스트 (시뮬레이션/정지)
| # | 테스트 | 성공 기준 |
|---|--------|-----------|
| 3.1 | 목표 없이 정지 | `/cmd_vel` = 0 출력 |
| 3.2 | 전방 목표 → 직진 | 장애물 없을 때 목표 방향 속도 출력 |
| 3.3 | 전방 장애물 → 정지/회피 | 장애물 거리 < `min_obstacle_dist` 시 속도 0 또는 회피 벡터 |
| 3.4 | 좌/우 벽 → 속도 제한 | 좁은 통로에서 속도 비례 제한 |
| 3.5 | 플래너 중단 → 안전 출력 | 플래너 노드 kill 시 `/cmd_vel` = 0 (watchdog) |

### Phase 4: PX4 연동 테스트 (무프로펠러, OFFBOARD)
| # | 테스트 | 성공 기준 |
|---|--------|-----------|
| 4.1 | OFFBOARD 진입 | RC 스위치로 OFFBOARD → 기체 아밍, 모터 아이들 |
| 4.2 | Setpoint 2Hz 유지 | `/mavros/setpoint_velocity/cmd_vel` 또는 `VehicleVelocitySetpoint` 2Hz 이상 |
| 4.3 | 간단 속도 명령 → 자세 변화 | vx=0.5 → 피치 각도 변화 확인 (프로펠러 없음) |
| 4.4 | 장애물 시뮬 → 속도 0 | 가상 장애물 주입 → 플래너 출력 0 → PX4 호버 유지 |
| 4.5 | RC 비상복귀 | RC 모드 스위치 → Position/Manual 즉시 전환 확인 |

### Phase 5: 통합 비행 테스트 (프로펠러 장착, 실내)
| # | 테스트 | 성공 기준 |
|---|--------|-----------|
| 5.1 | 이륙 → 호버 (Position) | 1m 고도에서 ±0.2m 유지, 30초 |
| 5.2 | 저속 직진 → 장애물 정지 | 0.5m/s 전진 → 전방 1m 장애물에서 정지 |
| 5.3 | 좌/우 회피 기동 | 측면 장애물 감지 시 목표 방향 유지하며 회피 |
| 5.4 | 좁은 통로 통과 | 1.5m 폭 통로에서 0.3m/s 통과 |
| 5.5 | 센서 가림 → 안전 동작 | 카메라 렌즈 가림 → 호버/브레이크/랜드 중 하나 |
| 5.6 | 플래너 크래시 → OFFBOARD 이탈 | 플래너 kill → 1초 내 PX4 Position 모드 복귀 |
| 5.7 | RC 킬 스위치 → 즉시 수동 | 비행 중 RC 킬 → 모터 정지/수동 모드 |
| 5.8 | 배터리 저전압 → Land | `COM_LOW_BAT_ACT=2` → 자동 착륙 |

---

## 12.7 로그 분석 체크리스트 (각 비행 후)

```bash
# PX4 ulog
ulog_info log_XXX.ulg | grep -E "(obstacle|avoidance|offboard|estimator)"

# ROS 2 bag
ros2 bag info flight_XXX.db3
ros2 bag play flight_XXX.db3 --topics /cmd_vel /local_costmap/costmap /camera/depth/points

# 핵심 지표:
# - OFFBOARD 유지율: setpoint 수신률 > 95%
# - 플래너 주기: 평균 < 100ms, 최대 < 200ms
# - 장애물 거리: 최소 거리 로그, 임계값 대비 여유
# - EKF2 혁신: 위치/속도 혁신 ±3 sigma
# - 배터리/온도: 임계값 도달 여부
```

---

## 12.8 실패 모드 매트릭스 & 안전 정책

| 실패 상황 | 감지 방법 | 안전 정책 (우선순위) | PX4 파라미터 |
|-----------|-----------|---------------------|--------------|
| Depth camera 끊김 | 토픽 타임아웃 / 프레임 드랍 | 1) 플래너 속도 0 → 2) 호버 → 3) Land | 플래너 watchdog |
| LiDAR 끊김 | `distance_sensor` 타임아웃 | 1) 범위 센서 무시 → 2) 호버 | `EKF2_RNG_CTRL=0` 동적 변경 |
| 플래너 크래시 | 노드 사망 / CPU 100% | 1) `/cmd_vel`=0 발행 → 2) OFFBOARD 이탈 | `COM_OF_LOSS_T` |
| EKF2 발산 | 혁신 > 5 sigma / estimator reset | 1) Position 모드 강제 → 2) Land | `COM_OBL_RC_ACT=2` |
| RC 링크 손실 | MAVLink 하트비트 타임아웃 | 1) RTL → 2) Land | `COM_RCL_ACT=2`, `GF_ACTION=1` |
| 배터리 임계 | `BAT_CRIT_THR` 도달 | 즉시 Land | `COM_LOW_BAT_ACT=2` |
| Geofence 위반 | Local position > `GF_MAX_HOR_DIST` | RTL | `GF_ACTION=1` |

**구현 팁**: ROS 2 측에서 `lifecycle node` 또는 `watchdog timer`로 플래너 생존 확인 → 사망 시 자동으로 `Twist(0)` 발행 + PX4 모드 변경 서비스 호출.

---

## 12.9 Silvus 데이터링크 연계 (Q250-V3-Opti 특화)

```bash
# Silvus 링크 품질 → 회피 파라미터 동적 조정
# scripts/silvus_monitor.py에서 퍼블리시하는 토픽 구독

# 링크 품질 지표:
# - RSSI, SNR, 패킷 로스, 지연 (RTT)
# - 토폴로지 변화 (홉 수 증가)

# 동적 조정 예시:
if packet_loss > 10% or rtt > 50ms:
    planner.max_vel_x *= 0.5      # 속도 절반
    planner.inflation_dist *= 1.5 # 안전 여유 증가
    PX4.COM_OF_LOSS_T = 0.5       # OFFBOARD 이탈 시간 단축
```

---

## 12.10 다음 단계

1. **ROS 2 패키지 생성**: `ros2_ws/src/obstacle_avoidance/` (launch, config, nodes)
2. **커스텀 플래너** 또는 TEB/DWA 설정 튜닝
3. **SITL Gazebo 시뮬레이션**에서 Phase 1~4 검증
4. **실기체 벤치 테스트** (Phase 1~4 무프로펠러)
5. **실내 비행 테스트** (Phase 5 프로펠러 장착)
6. **Silvus 링크 품질 연동** 로직 구현 및 검증

---

## 12.11 참고: 비AI vs AI 회피

| 구분 | 비AI (현재 권장) | AI (확장 시) |
|------|------------------|--------------|
| 센서 | Depth/LiDAR 거리값 | YOLO/Segformer 객체 검출 |
| 표현 | Costmap / Voxel grid | Semantic costmap |
| 플래너 | TEB / DWA / 규칙 기반 | RL / MPC / 학습 기반 |
| 검증 | 결정론적, 재현 쉬움 | 데이터셋/시뮬레이션 필요 |
| 안전성 | 높음 (규칙 기반) | 검증 복잡, 에지케이스 존재 |
| Jetson 부하 | 낮음 | 높음 (GPU 추론) |

> **Q250-V3-Opti 권장**: **비AI 방식(Depth/LiDAR + TEB/DWA) 먼저 완성** → 검증 후 필요 시 AI 객체 인식 계층 추가.