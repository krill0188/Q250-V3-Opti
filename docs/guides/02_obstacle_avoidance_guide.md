# Q250-V3 Opti 실전 가이드: 자율 회피 파이프라인 (Step-by-Step)

> **목표**: Depth/LiDAR → Costmap → TEB Planner → PX4 OFFBOARD 완전 자율 회피 비행  
> **전제**: VIO→EKF2 연동 완료 (Position 모드 안정 비행 가능)  
> **예상 소요**: 5~7일 (시뮬 2일, 벤치 1일, 실내 비행 2~3일)  
> **안전**: **모든 단계 프로펠러 제거 상태에서 시작**, 각 단계 로그 검증 후 다음 진행

---

## 📋 Phase 0: 하드웨어 및 사전 준비

### 0.1 센서 구성 확인 (Q250-V3-Opti 기준)

| 센서 | 포트 | PX4 파라미터 | 용도 |
|------|------|--------------|------|
| RealSense D435i | USB 3.0 | - | Depth/IMU (회피용) |
| TF-Luna LiDAR | TELEM4/UART4 | `SENS_TF_LUNA_CFG=1` | 전방 거리/고도 |
| PMW3901 Optical-Flow | TELEM4/UART4 | `EKF2_OF_CTRL=1` | 속도/위치 보조 |

### 0.2 PX4 파라미터 확인 (이미 설정돼 있어야 함)
```bash
# Optical-Flow
EKF2_OF_CTRL=1
EKF2_OF_DELAY=5
EKF2_OF_POS_Z=-0.035

# LiDAR
EKF2_RNG_CTRL=2
EKF2_RNG_DELAY=5
EKF2_RNG_POS_Z=-0.040

# 회피/안전
CP_DIST=1.0           # 충돌 방지 최소 거리
COM_OF_LOSS_T=1.0     # OFFBOARD setpoint 손실 허용 시간
COM_OBL_RC_ACT=2      # RC 손실 시 Position 모드 복귀
GF_ACTION=1           # Geofence 위반 시 RTL
```

### 0.3 ROS 2 패키지 빌드
```bash
cd /Users/amaster/projectm/Q250-V3-Opti/ros2_ws
colcon build --symlink-install --packages-select obstacle_avoidance
source install/setup.bash
```

---

## 📋 Phase 1: 센서 파이프라인 검증 (정지 상태, Day 1)

### 1.1 RealSense Depth 카메라 확인
```bash
# 1. 카메라 실행
ros2 launch realsense2_camera rs_launch.py \
  enable_depth:=true \
  depth_module.profile:=640x480x30 \
  pointcloud.enable:=true

# 2. 토픽 확인 (별도 터미널)
ros2 topic hz /camera/depth/image_rect_raw    # 30Hz
ros2 topic hz /camera/depth/points            # 30Hz
ros2 topic hz /camera/imu                     # 200Hz

# 3. Depth 이미지 품질 확인 (RViz2)
rviz2
# Add → Image → Topic: /camera/depth/image_rect_raw
# Color Scheme: Rainbow → 가까운 것 빨강, 먼 것 파랑
```

### 1.2 PointCloud 생성 확인
```bash
# depth_image_proc로 변환 확인
ros2 run depth_image_proc depth_image_proc \
  image_raw:=/camera/depth/image_rect_raw \
  camera_info:=/camera/depth/camera_info

# PointCloud 토픽 확인
ros2 topic hz /camera/depth/points
# 출력 예: average rate: 30.0 Hz

# 포인트 수 확인
ros2 topic echo /camera/depth/points --once --field width
# width * height = 포인트 수 (예: 640*480=307200, 다운샘플 후 ~10000)
```

### 1.3 LiDAR 거리 센서 확인
```bash
# MAVROS distance sensor 토픽
ros2 topic hz /mavros/distance_sensor/lidar
ros2 topic echo /mavros/distance_sensor/lidar --once
# 출력 예:
# current_distance: 2.5
# min_distance: 0.02
# max_distance: 11.0
# signal_quality: 100
```

### 1.4 TF 트리 확인 (좌표계 검증)
```bash
ros2 run tf2_tools view_frames.py
# frames.pdf 확인: odom → base_link → camera_link 체인 완전해야 함

# 카메라 프레임 확인
ros2 run tf2_ros tf2_echo base_link camera_link
# Translation: [0.15, 0.0, -0.05] (실측값과 일치해야 함)
```

**✅ Phase 1 완료 기준**:
- Depth 이미지 30Hz, PointCloud 발행, RViz에서 장애물 명확히 보임
- LiDAR 거리 값 정확 (실제 거리와 ±0.05m 이내)
- TF 트리 끊김 없음, 카메라 마운트 위치 실측값과 일치

---

## 📋 Phase 2: Costmap 및 장애물 표현 검증 (정지 상태, Day 1~2)

### 2.1 Costmap 2D 실행
```bash
# 로컬 코스트맵 실행 (파라미터 파일 사용)
ros2 launch nav2_costmap_2d costmap_2d.launch.py \
  params_file:=/Users/amaster/projectm/Q250-V3-Opti/ros2_ws/src/obstacle_avoidance/config/costmap_params.yaml
```

### 2.2 Costmap 시각화 및 검증
```bash
# RViz2에서 확인
rviz2
# Add → Map → Topic: /local_costmap/costmap
# Color Scheme: costmap (0=자유, 255=치명적)

# 확인 사항:
# □ 전방 1m 장애물 → costmap에 빨간 영역(255) 표시
# □ 장애물 주변 0.8m 팽창(inflation) 영역 주황색(100~200)
# □ 카메라 블라인드 스팟(하단/후방) → 회색(unknown, 127)
# □ 업데이트율 5Hz 이상
```

### 2.3 Voxel Grid 확인 (3D 장애물)
```bash
# voxel_grid 노드 실행
ros2 run voxel_grid voxel_grid_node \
  --ros-args -p input_topic:=/camera/depth/points \
  -p output_topic:=/obstacles/voxel_grid \
  -p leaf_size:=0.05

# RViz에서 확인
# Add → MarkerArray → Topic: /obstacles/voxel_grid
# 3D 복셀이 장애물 위치에 생성되는지 확인
```

### 2.4 블라인드 스팟 측정 및 문서화
```bash
# 카메라 하단 블라인드 스팟 측정
# 기체 중심에서 카메라까지 거리: 0.15m 앞, 0.05m 아래
# 카메라 FOV: 87° (수평), 58° (수직)
# 근접 최소 거리: ~0.3m (RealSense D435i 최소 초점)

# 문서화 (비행 시 참고)
# 블라인드 스팟: 전방 0~0.3m, 하방 0~0.5m, 후방 전체
# → LiDAR로 전방 근접 보완, 하방은 Optical-Flow/LiDAR 의존
```

**✅ Phase 2 완료 기준**:
- Costmap 5Hz 업데이트, 장애물 실시간 반영
- Inflation radius 0.8m 적용 확인
- 블라인드 스팟 측정 완료 및 문서화

---

## 📋 Phase 3: 플래너 단독 테스트 (시뮬/정지, Day 2)

### 3.1 TEB Local Planner 실행
```bash
# TEB 플래너 실행 (파라미터 파일 사용)
ros2 launch teb_local_planner teb_local_planner.launch.py \
  params_file:=/Users/amaster/projectm/Q250-V3-Opti/ros2_ws/src/obstacle_avoidance/config/teb_params.yaml
```

### 3.2 가상 목표/장애물로 플래너 동작 확인
```bash
# 1. 가상 목표 발행 (목표: 전방 2m)
ros2 topic pub /move_base_simple/goal geometry_msgs/PoseStamped "
header:
  frame_id: 'odom'
  stamp: {sec: 0, nanosec: 0}
pose:
  position: {x: 2.0, y: 0.0, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
" --once

# 2. 플래너 출력 확인
ros2 topic hz /cmd_vel
ros2 topic echo /cmd_vel
# 출력 예: linear.x=0.5, angular.z=0.0 (전진)

# 3. 가상 장애물 주입 (costmap에 직접)
# RViz에서 "Publish Point"로 전방 1m에 장애물 클릭
# → 플래너가 속도 0 또는 회피 벡터 출력하는지 확인
```

### 3.3 플래너 동작 검증 시나리오

| 테스트 | 입력 | 기대 출력 | 통과 기준 |
|--------|------|-----------|-----------|
| 장애물 없음 | 목표 (2,0,0) | vx=0.5~2.0, vz=0 | 직진 속도 출력 |
| 전방 장애물 1m | 목표 + 전방 장애물 | vx=0.0 또는 회피 각도 | 정지 또는 우회 |
| 좌측 벽 근접 | 목표 + 좌측 벽 | vy>0 (우측 회피) | 좌측 회피 벡터 |
| 좁은 통로 (1.5m) | 목표 + 양측 벽 | vx=0.3, vy≈0 | 저속 직진 |
| 플래너 중단 (kill) | 플래너 프로세스 종료 | vx=0, vy=0 | 안전 출력 (0) |

### 3.4 플래너 주기 및 지연 측정
```bash
# 플래너 루프 주기 측정
ros2 topic hz /cmd_vel
# 10Hz 이상 권장 (최소 5Hz)

# 엔드투엔드 지연: Depth → Costmap → Planner → cmd_vel
# rosbag으로 타임스탬프 분석
# 목표: < 200ms (센서~액추에이터)
```

**✅ Phase 3 완료 기준**:
- 모든 검증 시나리오 통과
- 플래너 주기 10Hz 이상, 지연 < 200ms
- 플래너 크래시 시 `cmd_vel=0` 안전 출력 확인

---

## 📋 Phase 4: PX4 OFFBOARD 연동 (무프로펠러, Day 3)

### 4.1 MAVROS/px4_ros_com 통신 확인
```bash
# MAVROS 경로 사용 시
ros2 topic hz /mavros/setpoint_velocity/cmd_vel  # 10Hz 이상
ros2 topic echo /mavros/setpoint_velocity/cmd_vel --once

# px4_ros_com 경로 사용 시
ros2 topic hz /fmu/in/vehicle_velocity_setpoint
```

### 4.2 OFFBOARD 모드 진입 테스트 (프로펠러 제거!)
```bash
# 1. 기체 아밍 (안전 스위치 누른 상태)
# 2. RC로 OFFBOARD 모드 전환
# 3. QGC에서 확인:
#    - Flight Mode: OFFBOARD
#    - Actuator Outputs: 모터 아이들 (0% 추력)
#    - Setpoint 수신: 10Hz 이상 (초록불)

# 4. 간단 속도 명령 테스트
ros2 topic pub /mavros/setpoint_velocity/cmd_vel geometry_msgs/Twist "
linear: {x: 0.3, y: 0.0, z: 0.0}
angular: {x: 0.0, y: 0.0, z: 0.0}
" --rate 10
# → 기체 자세 변화 확인 (피치 각도 -5도 정도, 프로펠러 없음)
```

### 4.3 플래너 → PX4 연동 통합 테스트
```bash
# 전체 파이프라인 실행
ros2 launch obstacle_avoidance obstacle_avoidance.launch.py \
  use_teb:=true \
  odom_topic:=/mavros/local_position/odom \
  cmd_vel_topic:=/mavros/setpoint_velocity/cmd_vel

# 시나리오 테스트 (무프로펠러):
# 1. 가상 목표 발행 → 플래너 → PX4 속도 제어
# 2. 전방 장애물 시뮬레이션 → 플래너 속도 0 → PX4 호버 유지
# 3. RC 비상복귀 → Position 모드 즉시 전환 확인
```

### 4.4 OFFBOARD 유지 조건 검증
```bash
# PX4 요구사항: 2Hz 이상 setpoint 수신
# 확인:
ros2 topic hz /mavros/setpoint_velocity/cmd_vel
# 최소 5Hz 권장 (여유)

# COM_OF_LOSS_T 확인 (기본 1.0s)
# QGC Parameters → COM_OF_LOSS_T
```

**✅ Phase 4 완료 기준**:
- OFFBOARD 모드 진입/유지 안정 (setpoint 10Hz 이상)
- 플래너 출력 → PX4 속도 제어 동작 확인
- RC 비상복귀 즉시 작동 (Position/Manual 모드 전환 < 0.5s)

---

## 📋 Phase 5: 실내 비행 테스트 (프로펠러 장착, Day 4~6)

### 5.1 안전 준비 (필수!)
- [ ] 비행 구역 네트/패딩 설치
- [ ] 비상정지 버튼 (RC 킬 스위치) 작동 확인
- [ ] 배터리 100% 충전, 예비 배터리 준비
- [ ] 관측자 1명 배치 (RC 수동 오버라이드 준비)
- [ ] 소화기, 구급상자 비치

### 5.2 단계별 비행 시나리오 (docs/12-obstacle-avoidance-pipeline.md Phase 5 참조)

| 단계 | 시나리오 | 성공 기준 | 최대 시간 |
|------|----------|-----------|-----------|
| 5.1 | 이륙 → 1m 호버 (Position) | ±0.2m 유지 30초 | 2분 |
| 5.2 | 저속 직진 → 전방 장애물 정지 | 0.5m/s → 1m 전 장애물 정지 | 3분 |
| 5.3 | 좌/우 회피 기동 | 측면 장애물 감지 시 우회 | 3분 |
| 5.4 | 좁은 통로 통과 (1.5m) | 0.3m/s 통과, 충돌 없음 | 2분 |
| 5.5 | 카메라 가림 → 안전 동작 | 호버/브레이크/랜드 중 하나 | 2분 |
| 5.6 | 플래너 크래시 시뮬 | kill → 1초 내 Position 복귀 | 1분 |
| 5.7 | RC 킬 스위치 | 즉시 모터 정지/수동 모드 | 즉시 |
| 5.8 | 배터리 저전압 시뮬 | Land 모드 자동 진입 | 2분 |

### 5.3 비행 로그 분석 (각 비행 후 필수)
```bash
# .ulg 다운로드 후 분석
ulog_info log_XXX.ulg | grep -E "(obstacle|avoidance|offboard|teb)"

# 핵심 지표:
# □ OFFBOARD 유지율: setpoint 수신률 > 95%
# □ 플래너 주기: 평균 < 100ms, 최대 < 200ms
# □ 최소 장애물 거리: 임계값(0.5m) 대비 여유 > 0.2m
# □ EKF2 혁신: ±3σ 내 유지
# □ 회피 성공률: 장애물 시나리오 100% 정지/우회
```

### 5.4 Silvus 링크 품질 연동 검증 (Q250-V3-Opti 특화)
```bash
# silvus_monitor.py 실행 중 비행
python3 scripts/silvus_monitor.py --air-unit-ip 192.168.10.11

# 링크 열화 시 플래너 자동 감속 확인:
# 패킷로스 > 10% 또는 RTT > 50ms → max_vel 50% 감소, inflation 1.5배 증가
# 로그에서 안전 파라미터 변경 이벤트 확인
```

---

## 📋 Phase 6: 지속적 개선 및 문서화 (Day 7+)

### 6.1 파라미터 튜닝 이력 관리
```bash
# px4_params/CHANGELOG.md에 기록
## 2026-11-04: Obstacle Avoidance Initial Tuning
- CP_DIST: 1.0 → 1.2 (안전 여유 증가)
- TEB weight_obstacle: 50 → 80 (장애물 회피 적극성 증가)
- TEB inflation_dist: 0.8 → 1.0 (팽창 반경 증가)
- Test: Phase 5.2~5.4 통과, 최소 거리 0.7m 확보
```

### 6.2 회피 성능 메트릭 추적
```bash
# scripts/postflight/analyze_log.py 실행
python3 scripts/postflight/analyze_log.py log_XXX.ulg

# 출력 예:
# Obstacle Avoidance Metrics:
#   Total flights: 5
#   Avoidance triggered: 12 times
#   Successful stops: 12 (100%)
#   Successful detours: 8 (100%)
#   Min obstacle distance: 0.62m (threshold: 0.5m)
#   Avg planner cycle: 67ms (max: 145ms)
```

### 6.3 실패 케이스 문서화
```bash
# docs/troubleshooting.md에 추가
## 2026-11-04: Camera blind spot collision
# 상황: 전방 0.2m 낮은 장애물 (카메라 블라인드 스팟) 충돌
# 원인: RealSense 최소 초점 0.3m, 하방 0.5m 블라인드
# 해결: LiDAR 하방 장착 추가, costmap min_obstacle_height 조정
# 예방: Phase 1.4 블라인드 스팟 측정 필수화
```

---

## 🚨 트러블슈팅 퀵 레퍼런스

| 증상 | 즉시 확인 | 해결 |
|------|-----------|------|
| Costmap 업데이트 안 됨 | `/camera/depth/points` 토픽 확인 | depth_image_proc 재시작, TF 확인 |
| 플래너 속도 0 (장애물 없음) | Costmap에 장애물 있는지 확인 | Inflation radius 축소, min_obstacle_dist 확인 |
| 플래너 주기 > 200ms | CPU 사용률 확인 (`htop`) | TEB `no_inner_iterations` 감소, multithreading 활성화 |
| OFFBOARD 이탈 | `COM_OF_LOSS_T` 확인, setpoint Hz 확인 | 플래너 → PX4 파이프라인 지연 단축 |
| 회피 후 진동/오실레이션 | TEB `weight_obstacle` 과대 | weight_obstacle 감소, `optimization_verbose`로 분석 |
| Silvus 링크 열화 미감지 | `/silvus/link_quality` 토픽 확인 | silvus_monitor.py 실행 확인, 토픽 발행률 확인 |

---

## 📚 참고 문서

| 문서 | 위치 |
|------|------|
| 자율 회피 파이프라인 상세 | `docs/12-obstacle-avoidance-pipeline.md` |
| TEB 파라미터 | `ros2_ws/src/obstacle_avoidance/config/teb_params.yaml` |
| Costmap 파라미터 | `ros2_ws/src/obstacle_avoidance/config/costmap_params.yaml` |
| Launch 파일 | `ros2_ws/src/obstacle_avoidance/launch/obstacle_avoidance.launch.py` |
| 학습 로드맵 | `docs/learning-roadmap.md` (7단계) |
| 아키텍처 원칙 | `docs/architecture.md` (결정론적 vs 보조 계층) |

---

*작성: 2026-11-04 | 기반: docs/12-obstacle-avoidance-pipeline.md*