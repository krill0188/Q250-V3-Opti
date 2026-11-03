# Q250-V3 Opti 실전 가이드: VIO → EKF2 연동 (Step-by-Step)

> **목표**: RealSense D435i VIO 포즈를 PX4 EKF2에 융합해 실내 Position 모드 비행 달성  
> **예상 소요**: 3~5일 (하드웨어 준비 1일, SW 설정 1~2일, 튜닝 1~2일)  
> **사전 조건**: Jetson에 JetPack 6 + ROS 2 Humble 설치済, PX4 v1.15 펌웨어 플래싱済

---

## 📋 Phase 0: 사전 준비 체크리스트

| 항목 | 확인 방법 | 완료 |
|------|-----------|------|
| RealSense D435i 펌웨어 최신 | `rs-fw-update -l` → 최신 버전 확인 | ☐ |
| RealSense 캘리브레이션 완료 | `rs-calibrate` 실행 또는 공장 캘리브레이션 확인 | ☐ |
| Jetson USB 3.0 포트 인식 | `lsusb | grep Intel` → RealSense D435i 표시 | ☐ |
| PX4 파라미터 백업 | QGC → Parameters → Tools → Save to File | ☐ |
| Silvus 링크 벤치 테스트 통과 | `scripts/silvus_monitor.py` 실행 → RSSI > -70dBm | ☐ |

---

## 📋 Phase 1: 카메라 드라이버 및 토픽 검증 (Day 1)

### 1.1 RealSense 드라이버 실행
```bash
# Jetson에서 실행
ros2 launch realsense2_camera rs_launch.py \
  enable_gyro:=true \
  enable_accel:=true \
  unite_imu_method:=1 \
  depth_module.profile:=640x480x30 \
  rgb_camera.profile:=640x480x30 \
  pointcloud.enable:=true
```

### 1.2 토픽 발행 확인 (별도 터미널)
```bash
# IMU 토픽 확인 (200Hz 기대)
ros2 topic hz /camera/imu
# 출력 예: average rate: 200.0 Hz

# Depth 이미지 확인 (30Hz 기대)
ros2 topic hz /camera/depth/image_rect_raw

# 토픽 리스트 확인
ros2 topic list | grep camera
# /camera/imu, /camera/depth/image_rect_raw, /camera/color/image_raw 등
```

### 1.3 데이터 품질 확인
```bash
# IMU 데이터 샘플 확인
ros2 topic echo /camera/imu --once
# linear_acceleration, angular_velocity 값이 합리적인지 확인 (정지 시 ~9.8, 0)

# Depth 이미지 시각화 (RViz2)
rviz2
# Add → Image → Topic: /camera/depth/image_rect_raw
```

**✅ Phase 1 완료 기준**: 모든 토픽이 지정된 Hz로 안정 발행, RViz에서 depth 이미지 정상 표시

---

## 📋 Phase 2: VIO 노드 설치 및 포즈 출력 검증 (Day 1~2)

### 2.1 VIO 노드 선택 및 설치 (택1)

#### 옵션 A: OpenVINS (ov_msckf) - 권장, 가장 검증됨
```bash
# ROS 2 워크스페이스에 클론
cd ~/ros2_ws/src
git clone https://github.com/ovins/ovins_ros2.git -b ros2
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select ov_msckf
source install/setup.bash
```

#### 옵션 B: vio_ros (가볍음, Jetson Nano급 적합)
```bash
cd ~/ros2_ws/src
git clone https://github.com/vio-ros/vio_ros.git
cd ~/ros2_ws
colcon build --symlink-install --packages-select vio_ros
```

#### 옵션 C: RTAB-Map (SLAM + VIO, 루프 클로저 지원)
```bash
sudo apt install ros-humble-rtabmap-ros
```

### 2.2 VIO 실행 및 포즈 토픽 확인
```bash
# OpenVINS 예시
ros2 launch ov_msckf ov_msckf.launch.py \
  camera_topic:=/camera/color/image_raw \
  imu_topic:=/camera/imu \
  config_path:=$(ros2 pkg prefix ov_msckf)/share/ov_msckf/config/ov_msckf.yaml

# 포즈 토픽 확인
ros2 topic hz /ov_msckf/pose
# 출력 예: average rate: 30.0 Hz

# 포즈 데이터 샘플 확인
ros2 topic echo /ov_msckf/pose --once
# 출력 예:
# header:
#   frame_id: "odom"
#   stamp: {sec: 1234567890, nanosec: 123456789}
# pose:
#   pose:
#     position: {x: 0.012, y: -0.003, z: 0.001}
#     orientation: {x: 0.0, y: 0.0, z: 0.005, w: 0.999}
#   covariance: [0.001, 0, ...]
```

### 2.3 정지 상태 드리프트 측정 (중요!)
```bash
# 기체를 완전히 정지시킨 상태에서 60초간 포즈 기록
ros2 topic echo /ov_msckf/pose --field pose.pose.position > /tmp/vio_drift.log &
sleep 60
kill %1

# 분석
python3 << 'EOF'
import numpy as np
data = np.loadtxt('/tmp/vio_drift.log')
if len(data) > 10:
    drift_per_sec = np.linalg.norm(data[-1] - data[0]) / 60.0
    print(f"드리프트: {drift_per_sec*100:.2f} cm/s")
    print(f"최대 편차: {np.max(np.linalg.norm(data - data[0], axis=1))*100:.2f} cm")
EOF
```

**✅ Phase 2 완료 기준**: 
- VIO 포즈 토픽 30Hz 안정 발행
- 정지 시 드리프트 **< 1 cm/s** (OpenVINS 기준)
- covariance 값이 0이 아니고 합리적 범위 (0.001~0.1)

---

## 📋 Phase 3: 좌표계 검증 (TF 트리) (Day 2)

### 3.1 TF 트리 시각화
```bash
# TF 트리 PDF 생성
ros2 run tf2_tools view_frames.py
# frames.pdf 생성됨 → 열어서 확인

# 또는 터미널에서 확인
ros2 run tf2_ros tf2_echo odom base_link
# 출력 예:
# Translation: [0.01, -0.00, 0.00]
# Rotation: [0.00, 0.00, 0.00, 1.00]
```

### 3.2 필수 TF 체인 확인
```
odom → base_link → camera_link
```

| 프레임 | 의미 | 확인 사항 |
|--------|------|-----------|
| `odom` | VIO 세계 좌표계 (ENU) | VIO 포즈의 `header.frame_id` |
| `base_link` | 기체 중심 (COG) | PX4와 일치해야 함 |
| `camera_link` | 카메라 광학 중심 | RealSense 드라이버가 발행 |

### 3.3 카메라 마운트 위치 측정 및 설정
```bash
# 실측: 기체 중심(COG) 기준으로 카메라 위치 측정 (m)
# 예: 카메라가 앞쪽 15cm, 아래 5cm에 장착
# FRD 프레임 기준 (PX4 표준):
#   X: 앞(+), Y: 오른쪽(+), Z: 아래(+)

# 측정값을 EKF2 파라미터로 설정 (나중 Phase 5에서 적용)
EKF2_EV_POS_X  0.15   # 카메라 앞쪽 오프셋
EKF2_EV_POS_Y  0.00
EKF2_EV_POS_Z -0.05   # 카메라 아래 오프셋 (음수 = 위)
```

### 3.4 ENU ↔ NED 좌표계 변환 확인
```bash
# VIO(ROS)는 ENU: x=East, y=North, z=Up
# PX4는 NED: x=North, y=East, z=Down
# 변환: x_ned = y_enu, y_ned = x_enu, z_ned = -z_enu

# MAVROS vision_pose 경로 사용 시: MAVROS가 자동 변환
# px4_ros_com 경로 사용 시: 수동 변환 필요 (또는 px4_ros_com이 처리)
```

**✅ Phase 3 완료 기준**: 
- TF 트리 끊김 없음 (`odom → base_link → camera_link`)
- 카메라 마운트 위치 실측 완료
- ENU→NED 변환 방식 결정 (MAVROS vs px4_ros_com)

---

## 📋 Phase 4: 통신 경로 선택 및 PX4 연동 (Day 2~3)

### 4.1 경로 선택 (둘 중 하나만!)

| 경로 | 장점 | 단점 | 권장 상황 |
|------|------|------|-----------|
| **MAVROS vision_pose** | 검증됨, MAVROS 기능 전체 사용, 자동 ENU→NED 변환 | UART 대역폭 제한, 지연 약간 큼 | 초보, 첫 검증, MAVROS 다른 기능도 쓸 때 |
| **px4_ros_com (uXRCE-DDS)** | 저지연, PX4 네이티브, 대역폭 효율적 | PX4/px4_msgs 버전 정확히 맞춰야 함, 디버깅 어려움 | 실전 배포, 고성능 필요, 실기체 운용 |

### 4.2 경로 A: MAVROS vision_pose 설정
```bash
# 1. MAVROS 실행 (이미 실행 중이라면 재시작)
ros2 launch mavros px4.launch.py \
  fcu_url:=/dev/ttyUSB0:921600 \
  gcs_url:="" \
  tgt_system:=1 \
  tgt_component:=1

# 2. vision_pose 플러그인 활성화 확인
ros2 param get /mavros vision_pose/use_tf
# true여야 함

# 3. VIO 포즈를 MAVROS vision_pose 토픽으로 리발행 (브리지 노드 필요)
# 간단 브리지 스크립트:
cat > ~/vio_to_mavros.py << 'EOF'
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from mavros_msgs.msg import VisionPoseEstimate

class VioToMavros(Node):
    def __init__(self):
        super().__init__('vio_to_mavros')
        self.sub = self.create_subscription(
            PoseWithCovarianceStamped, '/ov_msckf/pose', self.callback, 10)
        self.pub = self.create_publisher(
            VisionPoseEstimate, '/mavros/vision_pose/pose', 10)
    
    def callback(self, msg):
        out = VisionPoseEstimate()
        out.header = msg.header
        out.pose = msg.pose
        self.pub.publish(out)

rclpy.init()
rclpy.spin(VioToMavros())
EOF
chmod +x ~/vio_to_mavros.py
python3 ~/vio_to_mavros.py
```

### 4.3 경로 B: px4_ros_com 설정
```bash
# 1. px4_ros_com 빌드 (PX4 v1.15 브랜치와 맞춰야 함)
cd ~/ros2_ws/src
git clone https://github.com/PX4/px4_ros_com.git -b release/1.15
git clone https://github.com/PX4/px4_msgs.git -b release/1.15
cd ~/ros2_ws
colcon build --symlink-install --packages-select px4_ros_com px4_msgs

# 2. Micro XRCE-DDS Agent 실행 (Jetson에서)
MicroXRCEAgent serial --dev /dev/ttyUSB0 -b 921600

# 3. px4_ros_com 노드 실행
ros2 launch px4_ros_com px4_ros_com.launch.py

# 4. External Vision 발행 (VehicleVisualOdometry 메시지)
# 자체 노드 작성 필요 - MAVROS 경로보다 복잡
```

**✅ Phase 4 완료 기준**: 
- 선택한 경로로 VIO 포즈가 PX4로 전송됨
- QGroundControl MAVLink Inspector에서 `VISION_POSITION_ESTIMATE` 또는 `VEHICLE_VISUAL_ODOMETRY` 수신 확인

---

## 📋 Phase 5: EKF2 파라미터 적용 및 혁신 모니터링 (Day 3)

### 5.1 핵심 파라미터 설정 (QGroundControl 또는 명령행)
```bash
# QGC에서 Vehicle Setup → Parameters 검색 후 변경 후 Write Params → Reboot

# 실내 모드 필수
EKF2_GPS_CTRL   0       # GPS 비활성화
EKF2_MAG_TYPE   5       # Mag 비활성화 (실내)
EKF2_HGT_REF    2       # Range sensor primary (LiDAR 고도 기준)

# External Vision 활성화
EKF2_EV_CTRL    15      # Pos + Vel + Yaw fusion (비트 0,1,2)
EKF2_EV_DELAY   10      # ms (측정 후 튜닝, 초기값 10)
EKF2_EV_POS_X   0.15    # 카메라 위치 실측값 (m)
EKF2_EV_POS_Y   0.00
EKF2_EV_POS_Z  -0.05

# Aid Mask: OF + EV Yaw + Range Height
EKF2_AID_MASK   352     # 비트 3(OF) + 6(EV Yaw) + 7(Range)

# Optical-Flow (기존 유지)
EKF2_OF_CTRL    1
EKF2_OF_DELAY   5
EKF2_RNG_CTRL   2
EKF2_RNG_DELAY  5
```

### 5.2 파라미터 적용 및 재부팅
```bash
# QGC: Write Params → 기체 재부팅 (전원 재투입)
# 또는 명령행 (개발 PC에서)
px4-param load config/px4/q250-v3-opti_v1.15_baseline.params
```

### 5.3 EKF2 혁신 모니터링 (가장 중요!)
```bash
# QGroundControl: Analyze Tools → MAVLink Console
# 콘솔에서:
ekf2 innovation

# 또는 실시간 모니터링 (스크립트)
watch -n 1 'mavlink_console -c "ekf2 innovation"'

# 핵심 지표 (모두 ±3σ 내 있어야 함):
# ev_innov[0~2]: Position innovation (m) - VIO 위치 잔차
# ev_innov[3~5]: Velocity innovation (m/s) - VIO 속도 잔차  
# ev_innov[6]: Yaw innovation (rad) - VIO 요ー 잔차
```

### 5.4 혁신 값 해석 및 튜닝

| 혁신 패턴 | 원인 | 대응 |
|-----------|------|------|
| Position innovation 지속적으로 ±3σ 초과 | `EKF2_EV_POS_X/Y/Z` 오차, 좌표계 불일치 | 카메라 마운트 위치 재측정, TF 트리 재확인 |
| Velocity innovation 큼 | `EKF2_EV_DELAY` 과소/과대 | 지연 재측정 후 `EKF2_EV_DELAY` 조정 |
| Yaw innovation 큼 | Mag 간섭, VIO yaw 품질 나쁨 | `EKF2_MAG_TYPE=5` 확인, VIO yaw 품질 확인 |
| 혁신이 0에 가까움 (융합 안 됨) | `EKF2_EV_CTRL=0` 또는 aid mask 미설정 | 파라미터 재확인, 재부팅 |

### 5.5 지연 튜닝 절차 (EKF2_EV_DELAY)
```bash
# 1. rosbag으로 VIO 포즈 타임스탬프와 PX4 수신 타임스탬프 기록
ros2 bag record /ov_msckf/pose /mavros/vision_pose/pose

# 2. 분석
python3 << 'EOF'
import rosbag2_py
# 타임스탬프 차이 계산 → 평균 지연(ms) 구함
# EKF2_EV_DELAY = 평균 지연 + 여유(2~5ms)
EOF

# 3. 튜닝: innovation 최소화하는 값 찾기
# EKF2_EV_DELAY 5~20 범위에서 테스트
```

**✅ Phase 5 완료 기준**: 
- 모든 EKF2 혁신 ±3σ 내 유지 (최소 30초간 정지 상태)
- Position innovation < 0.1m, Velocity < 0.1m/s, Yaw < 0.05rad
- QGC Estimator Status에서 `ev_pos`, `ev_vel`, `ev_yaw` 플래그 모두 SET

---

## 📋 Phase 6: Position 모드 진입 테스트 (Day 3~4)

### 6.1 무프로펠러 벤치 테스트
```bash
# 1. 프로펠러 완전 제거!
# 2. 기체 아밍 (안전 스위치 눌린 상태에서)
# 3. RC로 Position 모드 전환
# 4. 기체가 제자리에 머무르는지 확인 (자세 변화만, 모터 아이들)
```

### 6.2 Position 모드 품질 확인
```bash
# QGC Fly View → Position 모드에서:
# - Local Position: x, y, z 값이 VIO 포즈와 일치하는지
# - Position Valid: 초록불 (EKF2가 위치 추정 유효 판단)
# - XY 드리프트: 정지 시 < 0.1m/분
```

### 6.3 저고도 수동/Position 비행 (프로펠러 장착, 실내)
```bash
# 안전 구역 확보 (네트, 패딩, 비상정지 버튼 준비)
# 1. 이륙 → 0.5m 호버 (Position 모드) → 30초 유지
# 2. 전후좌우 1m 이동 → 제자리 복귀
# 3. 요 회전 90도 → 정지
# 4. 착륙

# 각 단계 로그 저장 (QGC: Log Download → .ulg)
```

**✅ Phase 6 완료 기준**: 
- 무프로펠러 Position 모드 안정 유지
- 실내 저고도 비행 3분 이상 무사고
- 비행 후 로그에서 EKF2 혁신 ±3σ 유지 확인

---

## 📋 Phase 7: non-GPS 비행 모드 및 fake GPS (Day 4~5)

### 7.1 Local Position만으로 가능한 것 확인
- ✅ Position 모드 호버/이동
- ✅ OFFBOARD 속도/위치 제어
- ❌ Mission (웨이포인트)
- ❌ RTL (Return to Launch)
- ❌ Geofence

### 7.2 fake GPS 노드 실행 (Mission/RTL 필요 시)
```bash
# ros2_ws/src/fake_gps 빌드 후
ros2 launch fake_gps fake_gps.launch.py \
  datum_lat:=37.5665 \
  datum_lon:=126.9780 \
  datum_alt:=28.0 \
  vio_pose_topic:=/ov_msckf/pose

# QGC에서 확인:
# - GPS: 3D Fix, 위성 10개 표시
# - Map에 기체 위치 표시
# - Global Position Valid 초록불
```

### 7.3 Mission/RTL 테스트
```bash
# QGC Plan 탭에서 웨이포인트 Mission 생성 → Upload
# Flight 탭에서 AUTO 모드 전환 → Mission 실행
# RTL 버튼 테스트 → 원점 복귀 → 착륙
```

---

## 🚨 트러블슈팅 퀵 레퍼런스

| 증상 | 즉시 확인할 것 | 해결 방법 |
|------|---------------|-----------|
| VIO 포즈 안 나옴 | `ros2 topic list \| grep ov_msckf` | 카메라 드라이버 재시작, IMU 토픽 확인 |
| EKF2가 EV 융합 안 함 | `ekf2 innovation` → ev_* 모두 0 | `EKF2_EV_CTRL=15`, `EKF2_AID_MASK=352`, 재부팅 |
| Position 모드서 드리프트 | 혁신 ±3σ 초과 | `EKF2_EV_DELAY` 조정, 카메라 위치 재측정 |
| Yaw 자꾸 리셋 | Mag 간섭, EV yaw 품질 | `EKF2_MAG_TYPE=5`, 실내 조명/텍스처 확보 |
| OFFBOARD 바로 이탈 | `COM_OF_LOSS_T` 너무 짧음 | `COM_OF_LOSS_T=1.0` 이상, 2Hz 이상 setpoint 확인 |

---

## 📝 비행 후 필수 로그 분석 체크리스트

```bash
# .ulg 파일 다운로드 후:
ulog_info log_XXX.ulg | grep -E "(ekf2|ev_|innov)"

# 핵심 확인 사항:
# □ ev_innov[0~2] (pos): ±3σ 내 유지율 > 95%
# □ ev_innov[3~5] (vel): ±3σ 내 유지율 > 95%  
# □ ev_innov[6] (yaw): ±3σ 내 유지율 > 95%
# □ estimator_status: ev_pos, ev_vel, ev_yaw 비트 SET
# □ output_tracking_error: 낮을수록 좋음 (< 0.5m)
# □ Position 모드 진입 후 XY 드리프트: < 0.2m/분
```

---

## 📚 참고 문서 (이 저장소 내)

| 문서 | 위치 | 용도 |
|------|------|------|
| VIO→EKF2 상세 가이드 | `docs/07-vio-ekf2-integration.md` | 전체 절차, 파라미터, 튜닝, 실패 모드 |
| fake GPS 구현 | `docs/13-fake-gps-implementation.md` | 코드, launch, 파라미터, 검증 |
| 자율 회피 파이프라인 | `docs/12-obstacle-avoidance-pipeline.md` | 다음 단계 (VIO 검증 후) |
| 학습 로드맵 | `docs/learning-roadmap.md` | 전체 10단계 타임라인 |
| 아키텍처 원칙 | `docs/architecture.md` | AI/LLM 역할 분리, 안전 계층 |

---

*작성: 2026-11-04 | 기반: docs/07-vio-ekf2-integration.md, docs/13-fake-gps-implementation.md*