# Q250-V3 Opti 버전 호환성 매트릭스 (Version Compatibility Matrix)

> **업그레이드/변경 시 반드시 확인** - 호환되지 않는 조합은 빌드 실패 또는 런타임 오류 발생

---

## 🖥️ 시스템 소프트웨어 스택

| 구성요소 | 필수 버전 | 호환 범위 | 비고 |
|----------|-----------|-----------|------|
| **PX4 Firmware** | v1.15.0 | v1.15.x만 | v1.16+ Optical-Flow 미지원 |
| **px4_msgs** | release/1.15 | release/1.15만 | PX4와 정확히 일치해야 함 |
| **px4_ros_com** | release/1.15 | release/1.15만 | PX4/px4_msgs와 트리플 일치 필수 |
| **ROS 2** | Humble (humble) | Humble만 | Rolling/Iron 호환 안 됨 |
| **Gazebo** | Harmonic (8.x) | Harmonic만 | Classic/Fortress 호환 안 됨 |
| **Ubuntu (PC)** | 22.04 LTS (Jammy) | 22.04만 | WSL2 권장 |
| **Ubuntu (Jetson)** | 22.04 (JetPack 6) | JetPack 6.x만 | JetPack 5.x 호환 안 됨 |
| **JetPack** | 6.0 (L4T R36.3) | 6.0~6.1 | 5.x 사용 불가 |
| **MAVROS** | 2.0+ (humble) | 2.x | ROS 2 버전과 맞춤 |
| **MAVLink Router** | 최신 main | 2023.12+ | systemd 서비스용 |
| **uXRCE-DDS Agent** | 2.4.3+ | 2.4.x | Fast-DDS 2.10+ 필요 |
| **Fast-DDS** | 2.10+ | 2.10~2.12 | 3.x 미지원 |
| **RealSense SDK** | 2.55+ | 2.55~2.56 | 펌웨어 1.5.12+ 권장 |
| **realsense-ros** | 4.55+ | 4.55+ | ROS 2 Humble용 |
| **OpenVINS (ov_msckf)** | ROS 2 포트 | main 브랜치 | v1.0 태그 없음 |
| **TEB Local Planner** | 0.9+ | 0.9~0.10 | ROS 2 Humble용 |
| **Nav2 Costmap 2D** | 1.1+ | 1.1~1.2 | Humble 호환 |
| **Python** | 3.10+ | 3.10~3.11 | 3.12 미테스트 |
| **CMake** | 3.22+ | 3.22~3.27 | PX4 빌드용 |
| **GCC/G++** | 11+ | 11~12 | PX4 툴체인 |

---

## 🔗 크로스 의존성 체크리스트 (Cross-Dependency Checklist)

### PX4 ↔ ROS 2 통신 경로별 필수 일치 항목

| 경로 | PX4 | px4_msgs | px4_ros_com | MAVROS | 비고 |
|------|-----|----------|-------------|--------|------|
| **uXRCE-DDS (px4_ros_com)** | v1.15.x | release/1.15 | release/1.15 | - | **권장 경로** |
| **MAVLink (MAVROS)** | v1.15.x | - | - | 2.x | 호환 경로 |

> ⚠️ **절대 규칙**: PX4 v1.15 + px4_msgs release/1.15 + px4_ros_com release/1.15 **트리플 일치** 필수

### 센서 드라이버 호환성

| 센서 | 드라이버 | ROS 2 | 펌웨어 | 비고 |
|------|----------|-------|--------|------|
| RealSense D435i | realsense-ros | 4.55+ | 1.5.12+ | USB 3.0 필수 |
| TF-Luna LiDAR | MAVLink (PX4 내장) | - | - | PX4 SENS_TF_LUNA_CFG |
| PMW3901 Optical-Flow | MAVLink (PX4 내장) | - | - | PX4 EKF2_OF_CTRL |
| Silvus StreamCaster | MAVLink Router | - | MN-MIMO | 웹 UI 별도 관리 |

---

## 📦 패키지 버전 고정 가이드 (Pinning Guide)

### 개발 PC (WSL2) - apt 패키지 고정
```bash
# /etc/apt/preferences.d/px4-pinning
Package: ros-humble-*
Pin: version 1.0.0*
Pin-Priority: 1001

Package: gz-harmonic
Pin: version 8.*
Pin-Priority: 1001

Package: python3-colcon-*
Pin: version 0.6.*
Pin-Priority: 1001
```

### ROS 2 워크스페이스 - colcon 메타
```yaml
# ros2_ws/colcon.meta
{
  "px4_msgs": {
    "version": "1.15.0",
    "repository": "https://github.com/PX4/px4_msgs.git",
    "branch": "release/1.15"
  },
  "px4_ros_com": {
    "version": "1.15.0",
    "repository": "https://github.com/PX4/px4_ros_com.git",
    "branch": "release/1.15"
  },
  "teb_local_planner": {
    "version": "0.9.0",
    "repository": "https://github.com/rst-tu-dortmund/teb_local_planner.git",
    "branch": "ros2"
  }
}
```

### Python 의존성 고정 (requirements.txt)
```txt
# scripts/requirements.txt
pyulog==2023.12.01
dpkt==1.9.8
pymavlink==2.4.43
pyserial==3.5
pyyaml==6.0.1
numpy==1.24.3
scipy==1.10.1
pandas==2.0.3
pyproj==3.5.0
geographiclib==2.0
```

### Docker 이미지 태그 전략
```dockerfile
# Dockerfile.dev - 베이스 이미지 고정
FROM ros:humble-ros-base-jammy-20231201  # 특정 날짜 태그 사용

# 빌드 시 태그
docker build -t ghcr.io/krill0188/q250-v3-opti-dev:v1.15.0-20240115 .
```

---

## 🧪 호환성 테스트 매트릭스 (Test Matrix)

| 테스트 케이스 | PX4 | px4_msgs | px4_ros_com | ROS 2 | Gazebo | 예상 결과 |
|---------------|-----|----------|-------------|-------|--------|-----------|
| **기준 조합** | v1.15.0 | release/1.15 | release/1.15 | Humble | Harmonic | ✅ PASS |
| PX4만 업그레이드 | v1.15.1 | release/1.15 | release/1.15 | Humble | Harmonic | ✅ PASS (패치) |
| px4_msgs만 업그레이드 | v1.15.0 | release/1.15.1 | release/1.15 | Humble | Harmonic | ❌ FAIL (uORB 불일치) |
| ROS 2만 업그레이드 | v1.15.0 | release/1.15 | release/1.15 | Iron | Harmonic | ❌ FAIL (API 변경) |
| Gazebo만 업그레이드 | v1.15.0 | release/1.15 | release/1.15 | Humble | Ionic | ❌ FAIL (API 변경) |
| JetPack 업그레이드 | v1.15.0 | release/1.15 | release/1.15 | Humble | Harmonic | ⚠️ TEST (Jetson 6.1 미검증) |

> **테스트 명령**:
```bash
# 전체 호환성 테스트 스위트
cd /Users/amaster/projectm/Q250-V3-Opti
./scripts/test_compatibility.sh  # 커스텀 스크립트 필요
```

---

## ⚠️ 알려진 호환성 이슈 (Known Issues)

| 이슈 | 영향 | 워크어라운드 | 해결 예정 |
|------|------|--------------|-----------|
| **PX4 v1.16+ Optical-Flow 미지원** | EKF2_OF_CTRL 동작 안 함 | **v1.15 고정** | PX4 v1.17에서 수정 예정 |
| **Fast-DDS 3.x + px4_ros_com** | DDS 통신 실패 | Fast-DDS 2.10 고정 | px4_ros_com 업데이트 필요 |
| **ROS 2 Iron + Gazebo Harmonic** | 시뮬레이션 실행 안 됨 | ROS 2 Humble 고정 | Gazebo Ionic 출시 시 재검토 |
| **JetPack 6.1 + RealSense SDK** | 카메라 프레임 드랍 | JetPack 6.0 유지 | SDK 2.56+에서 개선 예상 |
| **TEB Local Planner + Nav2 1.2** | 플래너 초기화 실패 | Nav2 1.1 고정 | TEB 업데이트 대기 |
| **MAVROS 2.0 + PX4 v1.15** | 일부 메시지 누락 | MAVROS 2.0.1+ 사용 | 지속 모니터링 |

---

## 🔄 업그레이드 절차 (Upgrade Procedure)

### PX4 펌웨어 패치 버전 업그레이드 (v1.15.0 → v1.15.1)
```bash
# 1. 개발 PC에서
cd ~/PX4-Autopilot
git fetch origin
git checkout v1.15.1
git submodule update --init --recursive
make px4_fmu-v6c_default -j$(nproc)

# 2. 플래싱
make px4_fmu-v6c_default upload

# 3. 파라미터 재적용 (QGC에서 백업 복원)
# 4. 벤치 테스트 → SITL → 실내 비행 순서로 검증
```

### ROS 2 패키지 업데이트 (px4_msgs/px4_ros_com)
```bash
# 1. 브랜치 전환
cd ~/ros2_ws/src/px4_msgs
git fetch origin
git checkout release/1.15  # 태그 확인 후

cd ~/ros2_ws/src/px4_ros_com
git fetch origin
git checkout release/1.15

# 2. 재빌드
cd ~/ros2_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --packages-select px4_msgs px4_ros_com

# 3. 런타임 검증
ros2 run px4_ros_com px4_ros_com_node
# "Client connected" 로그 확인
```

### JetPack 업그레이드 (6.0 → 6.1)
```bash
# 1. 백업 필수
sudo apt update && sudo apt install -y nvidia-jetpack-backup
sudo nvidia-jetpack-backup --create

# 2. 업그레이드
sudo apt update && sudo apt dist-upgrade -y

# 3. 드라이버 재설치
sudo apt install --reinstall -y nvidia-l4t-cuda nvidia-l4t-tensorrt

# 4. ROS 2 재빌드 (ARM64 바이너리 변경)
cd ~/ros2_ws
rm -rf build install log
colcon build --symlink-install

# 5. RealSense SDK 재설치
rs-fw-update -l  # 펌웨어 확인
# 필요시 최신 펌웨어 플래싱
```

---

## 📋 호환성 체크리스트 (릴리즈 전 필수 확인)

```bash
# 자동 체크 스크립트 실행
./scripts/check_compatibility.sh

# 수동 확인 항목:
□ PX4 펌웨어 버전: v1.15.x
□ px4_msgs 브랜치: release/1.15
□ px4_ros_com 브랜치: release/1.15
□ ROS 2 버전: Humble
□ Gazebo 버전: Harmonic
□ Fast-DDS 버전: 2.10.x
□ JetPack 버전: 6.0.x
□ RealSense SDK: 2.55+
□ realsense-ros: 4.55+
□ MAVROS: 2.0.x
□ MAVLink Router: 2023.12+
□ uXRCE-DDS Agent: 2.4.3+
□ TEB Local Planner: 0.9.x
□ Nav2 Costmap 2D: 1.1.x
```

---

## 📚 버전 이력 (Changelog)

| 날짜 | 변경 내용 | 버전 | 검증 상태 |
|------|-----------|------|-----------|
| 2026-11-04 | 초기 베이스라인 확정 | v1.15.0-baseline | ✅ 검증됨 |
| 2026-11-01 | PX4 v1.15.0 + px4_msgs/ros_com release/1.15 고정 | v1.15.0 | ✅ 검증됨 |
| 2026-10-15 | JetPack 6.0 + RealSense SDK 2.55 확정 | - | ✅ 검증됨 |
| 2026-10-01 | ROS 2 Humble + Gazebo Harmonic 조합 확정 | - | ✅ 검증됨 |

---

*Version Compatibility Matrix v1.0 | 2026-11-04 | 업그레이드 전 필수 확인*