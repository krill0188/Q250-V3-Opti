# 7. VIO → EKF2 연동 가이드 (실내 자율비행 핵심)

> 이 문서는 `jetson-px4-ros2-autonomous-drone/docs/07-vio-autonomy.md`, `11-vio-non-gps-flight.md`를 Q250-V3-Opti 실기체 환경에 맞춰 재구성했습니다.

---

## 7.1 개요: 왜 VIO→EKF2인가?

실내에서 GPS 없이 자율비행하려면 **PX4 EKF2가 외부 비전(VIO) 자세/위치를 융합**해야 합니다.

```
RealSense D435i → VIO estimator (ROS 2) → MAVROS/px4_ros_com → PX4 EKF2 External Vision
                                                      ↓
                                    Local Position Estimate (NED)
                                                      ↓
                                    PX4 Position/Velocity Controller
                                                      ↓
                                    OFFBOARD / Position Mode 비행
```

**Q250-V3-Opti 현재 상태**: `config/px4/q250-v3-opti_v1.15_baseline.params`에 `EKF2_EV_CTRL=15` 설정돼 있으나, 실제 VIO 노드→PX4 연동 파이프라인이 문서화되지 않음.

---

## 7.2 하드웨어 요구사항

| 구성요소 | Q250-V3-Opti 사양 | 비고 |
|----------|-------------------|------|
| 카메라 | Intel RealSense D435i (또는 T265) | USB 3.0, IMU 내장 |
| 장착 | 기체 전방 강성 마운트, 진동 차단 | `EKF2_EV_POS_X/Y/Z` 측정 필수 |
| 시간동기 | Jetson ↔ Pixhawk NTP/PTP 또는 MAVLink TIMESYNC | 지연 보정용 `EKF2_EV_DELAY` 튜닝 필요 |
| 컴패니언 | Jetson Orin Nano 8GB, JetPack 6 | CUDA/TensorRT 가속 VIO용 |

---

## 7.3 소프트웨어 스택

```bash
# Jetson에서 설치 확인
ros2 --version                    # Humble
ros2 pkg list | grep realsense    # realsense-ros
ros2 pkg list | grep vio          # vio_ros, ov_msckf, 또는 커스텀
ros2 pkg list | grep px4          # px4_msgs, px4_ros_com
ros2 pkg list | grep mavros       # mavros, mavros-extras (MAVROS 경로 시)
```

**권장 VIO 노드** (택1):
| 노드 | 특징 | 비고 |
|------|------|------|
| `ov_msckf` (OpenVINS) | MSCKF 기반, ROS 2 포팅됨 | 학습용 권장 |
| `vio_ros` | 키포인트 기반, 가볍음 | Jetson Nano급 적합 |
| `rtabmap_ros` | SLAM + VIO, 루프 클로저 | 메모리 더 필요 |
| 커스텀 | 자체 개발 | 검증 데이터 필수 |

---

## 7.4 단계별 연동 절차

### Step 1: 카메라 드라이버 및 토픽 확인
```bash
# RealSense 실행
ros2 launch realsense2_camera rs_launch.py \
  enable_gyro:=true enable_accel:=true \
  unite_imu_method:=1 \
  depth_module.profile:=640x480x30 \
  rgb_camera.profile:=640x480x30

# 토픽 확인
ros2 topic list | grep -E "(imu|image|depth)"
# /camera/imu, /camera/color/image_raw, /camera/depth/image_rect_raw 등
```

### Step 2: VIO 노드 실행 및 pose 토픽 확인
```bash
# 예: ov_msckf 실행
ros2 launch ov_msckf ov_msckf.launch.py \
  camera_topic:=/camera/color/image_raw \
  imu_topic:=/camera/imu

# pose 토픽 확인 (ENU 프레임)
ros2 topic echo /ov_msckf/pose
# geometry_msgs/PoseWithCovarianceStamped
# header.frame_id: "odom" 또는 "map"
# child_frame_id: "base_link" 또는 "camera_link"
```

### Step 3: 좌표계 검증 (가장 중요!)
```bash
# TF 트리 확인
ros2 run tf2_tools view_frames.py
# odom → base_link → camera_link 체인 확인

# PX4는 NED (North-East-Down), ROS는 ENU (East-North-Up)
# 변환: x_ned = y_enu, y_ned = x_enu, z_ned = -z_enu
# yaw_ned = -yaw_enu + 90° (또는 π/2)
```

**체크리스트**:
- [ ] VIO pose가 `odom` 프레임에서 출력되는가?
- [ ] `base_link`가 기체 중심(COG)에 맞는가?
- [ ] 카메라가 기체 앞쪽을 향하는가? (`EKF2_EV_POS_X > 0`)
- [ ] IMU와 카메라 시간 동기화됐는가? (ROS 2 시간 vs PX4 시간)

### Step 4: PX4로 pose 전송 경로 선택 (둘 중 하나만!)

#### 경로 A: MAVROS vision/odometry (범용, 검증됨)
```yaml
# mavros.launch.py에 추가
mavros:
  plugin_whitelist:
    - vision_pose
    - odometry
  vision_pose:
    source: "OV_MSCKF"
    tf:
      frame_id: "odom"
      child_frame_id: "base_link"
```

```bash
# MAVROS vision_pose 토픽으로 발행 (ENU → MAVROS가 NED 변환)
ros2 topic pub /mavros/vision_pose/pose geometry_msgs/PoseWithCovarianceStamped ...
```

**PX4 파라미터** (MAVROS 경로):
```bash
EKF2_EV_CTRL    15      # Pos + Vel + Yaw fusion
EKF2_EV_DELAY   5       # ms (측정 후 튜닝)
EKF2_EV_POS_X   0.15    # 카메라 위치 (m, 기체 중심 기준)
EKF2_EV_POS_Y   0.0
EKF2_EV_POS_Z  -0.05
MAV_1_CONFIG    102     # TELEM1을 MAVROS용
```

#### 경로 B: px4_ros_com (uXRCE-DDS, 저지연, PX4 네이티브)
```bash
# px4_ros_com의 external_estimator 노드 사용
# VehicleVisualOdometry 메시지로 직접 발행 (NED 프레임)
```

**PX4 파라미터** (px4_ros_com 경로):
```bash
UXRCE_DDS_CFG   2       # uXRCE-DDS 활성화
SER_TEL2_BAUD   921600  # TELEM2 포트
EKF2_EV_CTRL    15
EKF2_EV_DELAY   5
# px4_ros_com이 NED로 변환해 주므로 좌표변환 불필요
```

> **경로 선택 규칙**: 처음엔 MAVROS로 검증 → 안정되면 px4_ros_com으로 전환. **둘을 동시에 쓰지 마세요** (setpoint 충돌).

### Step 5: EKF2 파라미터 적용 및 검증

```bash
# QGroundControl에서 파라미터 업로드 후 재부팅
# 또는 명령행
px4-param load config/px4/q250-v3-opti_v1.15_baseline.params
```

**필수 확인 파라미터**:
```bash
EKF2_EV_CTRL    15      # 0=off, 1=pos, 2=vel, 4=yaw, 15=all
EKF2_AID_MASK   352     # 비트 3(OF), 6(EV yaw), 7(range height) 활성화
EKF2_HGT_REF    2       # Range sensor primary
EKF2_GPS_CTRL   0       # GPS 비활성화 (실내)
EKF2_MAG_TYPE   5       # Mag 비활성화 (실내)
```

### Step 6: 무프로펠러 벤치 테스트

```bash
# 1. VIO pose 품질 확인
ros2 topic echo /ov_msckf/pose --field pose.pose.position
# 정지 시 drift < 0.01m/s 확인

# 2. PX4가 external vision 수신하는지 확인 (QGC MAVLink Inspector)
# VEHICLE_VISUAL_ODOMETRY 또는 ODOMETRY 메시지 수신 확인

# 3. EKF2 혁신 모니터링
# QGC: Analyze Tools → MAVLink Console → ekf2 innovation 확인
# innovation이 ±3 sigma 내에 있어야 함

# 4. Position 모드 진입 테스트 (프로펠러 제거)
# RC로 Position 모드 전환 → 기체가 제자리에 머무르는지 확인
```

---

## 7.5 실전 튜닝 가이드

### 7.5.1 지연 보정 (`EKF2_EV_DELAY`)
```bash
# 측정 방법:
# 1. 카메라 프레임 타임스탬프와 PX4 수신 타임스탬프 차이 측정
# 2. rosbag으로 기록 후 분석
# 3. 일반적인 값: 5~20ms (Jetson 처리 + 전송 + MAVROS 변환)

EKF2_EV_DELAY 10  # 시작값, innovation 최소화하며 조정
```

### 7.5.2 카메라 위치 (`EKF2_EV_POS_X/Y/Z`)
```bash
# 실측 후 입력 (기체 중심 기준, FRD 프레임)
# 예: 카메라가 앞쪽 15cm, 아래 5cm에 장착
EKF2_EV_POS_X  0.15
EKF2_EV_POS_Y  0.00
EKF2_EV_POS_Z -0.05
```

### 7.5.3 공분산 스케일링
```bash
# VIO 노드가 출력하는 공분산이 과소/과대 평가됐을 때
# PX4 측에서 스케일 조정 (매개변수명 버전별 상이)
EKF2_EVP_NOISE  0.1   # external vision position noise
EKF2_EVV_NOISE  0.1   # external vision velocity noise
```

---

## 7.6 실패 모드 및 대응

| 증상 | 원인 | 대응 |
|------|------|------|
| EKF2가 EV를 융합 안 함 | `EKF2_EV_CTRL=0` 또는 aid mask 미설정 | 파라미터 확인, 재부팅 |
| Position 모드에서 드리프트 | VIO pose 품질 나쁨 / 공분산 과소 | 조명 확보, 텍스처 추가, 공분산 스케일링 |
| 급격한 자세 변화 시 추정 발산 | 시간 동기 오류 / 지연 과대 | `EKF2_EV_DELAY` 증가, NTP/PTP 확인 |
| EV yaw가 자꾸 리셋됨 | Mag 간섭 / EV yaw 품질 나쁨 | `EKF2_MAG_TYPE=5`, EV yaw fusion만 사용(bit 6) |
| OFFBOARD에서 바로 이탈 | EKF2가 position valid 판단 안 함 | innovation 모니터링, 최소 5초간 정지 후 진입 |

---

## 7.7 로그 분석 체크리스트 (비행 후)

```bash
# PX4 ulog에서 확인할 것
ulog_info log_001.ulg | grep -E "(ekf2|ev_|innov)"

# 핵심 지표:
# - ev_innov[0~2]: position innovation (m)
# - ev_innov[3~5]: velocity innovation (m/s)  
# - ev_innov[6]: yaw innovation (rad)
# - ev_innov 모든 값이 ±3 sigma 내
# - estimator_status_flags: ev_pos, ev_vel, ev_yaw 비트 설정됨
# - output_tracking_error: 낮을수록 좋음
```

---

## 7.8 다음 단계

1. **이 절차로 VIO→EKF2 검증 완료** → `docs/manual-draft.md` 3단계에 반영
2. **non-GPS 비행 모드** 구현 → `docs/11-vio-non-gps-flight.md` 참조
3. **fake GPS** 필요 시 (Mission/RTL용) → `docs/13-fake-gps-implementation.md` 참조
4. **자율 회피** 파이프라인 추가 → `docs/12-obstacle-avoidance-pipeline.md` 참조