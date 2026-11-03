# Q250-V3 Opti 빠른 참조 카드 (Quick Reference Card)

> **프린트해서 책상에 붙여두세요** - A4 1장, 양면 인쇄 권장

---

## 🚨 비상 절차 (Emergency Procedures)

| 상황 | 즉시 행동 | RC 조작 |
|------|-----------|---------|
| **제어 상실/이상 동작** | 1. 당황하지 말고 RC 킬 스위치 2. 수동 모드 전환 3. 착륙 유도 | `Kill Switch` → `Manual Mode` |
| **배터리 저전압 경보** | 1. 즉시 RTL 모드 2. 착륙 확인 3. 배터리 교체 | `RTL Switch` |
| **Silvus 링크 끊김** | 1. 자동 Position 모드 전환 확인 2. 수동 조종 준비 3. 링크 복구 대기 | `Position Mode` |
| **VIO/EKF2 발산** | 1. Position → Manual 즉시 전환 2. 프로펠러 정지 3. 로그 분석 후 재시도 | `Manual Mode` → `Kill` |
| **충돌 임박** | 1. 킬 스위치 2. 프로펠러 정지 확인 3. 안전 거리 확보 | `Kill Switch` |

---

## ⌨️ 필수 단축 명령어 (Essential Commands)

### 개발 PC (WSL2)
```bash
# 빌드/테스트
px4-build          # PX4 펌웨어 빌드
px4-sitl           # SITL 실행 (Gazebo)
ros2-build         # ROS 2 워크스페이스 빌드
ros2-test          # 테스트 실행

# 환경
preflight          # 사전 비행 체크
silvus-monitor     # Silvus 링크 모니터링

# Git
git status && git diff
```

### Jetson (SSH)
```bash
# 서비스 상태
systemctl status mavlink-router uxrce-dds-agent
journalctl -fu mavlink-router -n 20
journalctl -fu uxrce-dds-agent -n 20

# 토픽 확인
ros2 topic list | grep -E "(camera|mavros|px4|silvus)"
ros2 topic hz /camera/depth/image_rect_raw
ros2 topic hz /mavros/local_position/odom

# 네트워크
ping 192.168.10.10  # GCS
ping 192.168.10.11  # Silvus Air Unit
```

### 비행 중 모니터링
```bash
# MAVLink Console (QGC)
ekf2 innovation           # EKF2 혁신 모니터링
ekf2 status               # 추정기 상태
param show EKF2_*         # EKF2 파라미터 확인

# 실시간 토픽
ros2 topic echo /fmu/out/vehicle_local_position
ros2 topic echo /fmu/out/estimator_status
ros2 topic echo /silvus/link_quality
```

---

## 🔧 핵심 파라미터 치트시트 (Key Parameters)

### 실내 모드 필수 (Indoor Mode)
```bash
EKF2_GPS_CTRL=0      # GPS 비활성화
EKF2_MAG_TYPE=5      # Mag 비활성화
EKF2_HGT_REF=2       # Range sensor primary (LiDAR)
EKF2_AID_MASK=200    # OF(bit3) + Range(bit7) - 기본
# VIO 사용 시: EKF2_AID_MASK=352 (OF+EV Yaw+Range)
```

### VIO/External Vision 활성화
```bash
EKF2_EV_CTRL=15      # Pos+Vel+Yaw fusion
EKF2_EV_DELAY=10     # ms (튜닝: innovation 최소값)
EKF2_EV_POS_X=0.15   # 카메라 전방 오프셋 (m, 실측!)
EKF2_EV_POS_Y=0.00
EKF2_EV_POS_Z=-0.05
EKF2_EVP_NOISE=0.1   # Vision position noise
EKF2_EVV_NOISE=0.1   # Vision velocity noise
```

### Fake GPS (Mission/RTL용)
```bash
EKF2_GPS_CTRL=7      # GPS Pos+Vel+Hgt 모두 융합
EKF2_GPS_CHECK=31    # 품질 체크 완화
EKF2_GPS_P_NOISE=0.5
EKF2_GPS_V_NOISE=0.5
```

### 통신/안전
```bash
UXRCE_DDS_CFG=2      # uXRCE-DDS 활성화
SER_TEL2_BAUD=921600 # TELEM2 보드레이트
COM_OF_LOSS_T=1.0    # OFFBOARD setpoint 손실 허용 (s)
COM_OBL_RC_ACT=2     # RC 손실 시 Position 모드
GF_ACTION=1          # Geofence 위반 시 RTL
CP_DIST=1.0          # 충돌 방지 최소 거리 (m)
```

### 회피/플래너 (TEB)
```bash
# TEB 파라미터 (ros2 param set /teb_local_planner ...)
max_vel_x=2.0
min_obstacle_dist=0.5
inflation_dist=0.8
weight_obstacle=50
weight_inflation=10
```

---

## 📊 혁신 모니터링 기준 (Innovation Thresholds)

| 혁신 타입 | 정상 범위 | 경고 | 위험 (즉시 조치) |
|-----------|-----------|------|------------------|
| **Position (m)** | ±0.1 | ±0.3 | > ±0.5 |
| **Velocity (m/s)** | ±0.05 | ±0.15 | > ±0.3 |
| **Yaw (rad)** | ±0.02 | ±0.05 | > ±0.1 |
| **3σ 위반율** | < 1% | 1~5% | > 5% |

> **규칙**: 3σ 위반율 5% 초과 시 **즉시 비행 중단** 후 원인 분석

---

## 🔌 하드웨어 포트맵 (Port Map)

| 포트 | 장치 | 보드레이트 | 프로토콜 |
|------|------|------------|----------|
| **TELEM1** | GCS (Silvus) | 57600 | MAVLink |
| **TELEM2** | Jetson (uXRCE-DDS) | 921600 | UART/ROS 2 |
| **TELEM3** | Silvus Air Unit | 115200 | MAVLink |
| **TELEM4** | Optical-Flow + LiDAR | 115200 | MAVLink |
| **USB** | 개발 PC (펌웨어/로그) | - | USB |
| **GPS** | (실내 미사용) | - | - |
| **RC** | 수신기 (SBUS/PPM) | - | - |

### 카메라 마운트 실측값 (필수 입력!)
```
EKF2_EV_POS_X = 0.15  # 전방 (m)
EKF2_EV_POS_Y = 0.00  # 좌우 (m)  
EKF2_EV_POS_Z = -0.05 # 하방 (m, 음수=위)
```
> **실측 후 입력 필수** - 추정 오차의 주원인

---

## ✅ 비행 전 체크리스트 (Pre-flight Checklist)

### 하드웨어
- [ ] 프로펠러 방향/고정 확인 (CW/CCW)
- [ ] 배터리 100% 충전, 커넥터 체결
- [ ] Silvus Air Unit 4대 모두 연결, RSSI > -70dBm
- [ ] RealSense D435i USB 3.0 연결, 토픽 30Hz 확인
- [ ] LiDAR/Optical-Flow 토픽 발행 확인
- [ ] RC 수신기 바인딩, 페일세이프 설정 확인

### 소프트웨어
- [ ] MAVLink Router 실행 중 (journalctl 확인)
- [ ] uXRCE-DDS Agent 실행 중 (Client connected)
- [ ] ROS 2 토픽: /camera/depth, /mavros/*, /fmu/out/* 모두 활성
- [ ] EKF2 파라미터: 실내 모드(GPS/Mag OFF) 적용 확인
- [ ] VIO 포즈: /ov_msckf/pose 30Hz, 드리프트 < 1cm/s

### 안전
- [ ] 비행 구역 네트/패딩 설치
- [ ] 비상정지 버튼 작동 확인 (RC 킬 스위치)
- [ ] 관측자 1명 배치 (RC 수동 오버라이드 준비)
- [ ] 소화기, 구급상자 비치
- [ ] 배터리 예비 1개 준비

---

## 📝 비행 후 필수 분석 (Post-flight)

```bash
# 1. 로그 다운로드 및 SHA-256 기록
sha256sum log_XXX.ulg > SHA256SUMS.txt

# 2. 자동 분석
python3 scripts/postflight/analyze_log.py log_XXX.ulg

# 3. 핵심 확인 사항
# □ EKF2 혁신 3σ 위반율 < 5%
# □ VIO 드리프트 < 0.5m/분
# □ OFFBOARD 유지율 > 95%
# □ 최소 장애물 거리 > 0.5m
# □ Silvus 패킷로스 < 1%
# □ 배터리 최소 전압 > 14.5V (4S)

# 4. CHANGELOG.md 기록
# px4_params/CHANGELOG.md에 파라미터 변경 이력 추가
```

---

## 🆘 자주 발생하는 문제 즉각 대처

| 증상 | 30초 내 확인 | 5분 내 해결 |
|------|--------------|-------------|
| **VIO 포즈 안 나옴** | `ros2 topic hz /camera/imu` | 카메라 재시작, IMU 토픽 확인 |
| **EKF2 EV 융합 안 됨** | `ekf2 innovation` → ev_* 확인 | `EKF2_EV_CTRL=15`, `AID_MASK=352`, 재부팅 |
| **Position 모드 드리프트** | 혁신 ±3σ 초과 여부 | `EKF2_EV_DELAY` 조정, 카메라 위치 재측정 |
| **OFFBOARD 바로 이탈** | `COM_OF_LOSS_T` 확인 | setpoint 10Hz 이상, 플래너 지연 단축 |
| **Silvus 링크 열화** | `silvus_monitor.py` RSSI/Loss | 안테나 방향, 채널 변경, 출력 증가 |
| **Fake GPS Mission 안 됨** | GPS 3D Fix, 위성 10개 확인 | `EKF2_GPS_CTRL=7`, `GPS_CHECK=31` |

---

## 📞 연락처 및 참고 문서

| 문서 | 위치 |
|------|------|
| 마스터 인덱스 | `docs/guides/README.md` |
| VIO→EKF2 가이드 | `docs/guides/01_vio_ekf2_integration_guide.md` |
| 회피 파이프라인 | `docs/guides/02_obstacle_avoidance_guide.md` |
| Fake GPS | `docs/guides/03_fake_gps_guide.md` |
| 로그 분석 | `docs/guides/04_flight_log_analysis_guide.md` |
| 환경 설정 | `docs/guides/05_dev_environment_setup_guide.md` |
| PX4 파라미터 | `config/px4/q250-v3-opti_v1.15_baseline.params` |
| CHANGELOG | `px4_params/CHANGELOG.md` |

---

*Quick Reference v1.0 | 2026-11-04 | A4 1장 양면 인쇄 권장*