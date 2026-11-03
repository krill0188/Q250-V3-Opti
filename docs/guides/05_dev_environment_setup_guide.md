# Q250-V3 Opti 실전 가이드: 개발 환경 설정 (Step-by-Step)

> **목적**: WSL2 개발 PC + Jetson 타겟 완전 동기화된 개발 환경 구축  
> **대상**: 개발 PC (Windows 11 + WSL2 Ubuntu 22.04), Jetson Orin Nano (JetPack 6)  
> **예상 소요**: 2~3시간 (자동화 스크립트 사용 시)  
> **핵심**: **한 번 설정으로 양쪽에서 동일한 빌드/실행 환경 보장** (Docker + VS Code Remote + 공통 환경변수)

---

## 📋 Phase 0: 사전 요구사항 확인

### 0.1 개발 PC (Windows) 사전 준비

| 항목 | 버전/사양 | 확인 명령 |
|------|-----------|-----------|
| Windows | 11 Pro/Enterprise (WSL2 지원) | `winver` |
| WSL2 | Ubuntu 22.04 LTS | `wsl -l -v` |
| Docker Desktop | 최신 (WSL2 백엔드) | `docker version` |
| VS Code | 최신 + WSL 확장 | `code --version` |
| Git | 최신 | `git --version` |
| usbipd-win | 최신 (USB 포워딩) | `usbipd list` |

### 0.2 Jetson 타겟 사전 준비

| 항목 | 버전/사양 | 확인 명령 |
|------|-----------|-----------|
| JetPack | 6.0 (L4T R36.x) | `cat /etc/nv_tegra_release` |
| Ubuntu | 22.04 (Jetson용) | `lsb_release -a` |
| SSH 서버 | 활성화 | `systemctl status ssh` |
| 사용자 권한 | dialout, video, docker 그룹 | `groups $USER` |
| 고정 IP | 192.168.10.11 (권장) | `ip addr show` |

---

## 📋 Phase 1: 개발 PC (WSL2) 환경 구축 (30분)

### 1.1 자동 설정 스크립트 실행
```bash
# WSL2 터미널에서 실행
cd /Users/amaster/projectm/Q250-V3-Opti
./scripts/setup/00_wsl2_dev_pc.sh

# 스크립트 내용 (자동 수행):
# 1. 시스템 패키지 업데이트 및 필수 툴 설치
#    - build-essential, cmake, ninja-build, ccache
#    - git, curl, wget, vim, htop, tmux
#    - python3-pip, python3-venv, python3-dev
# 2. ROS 2 Humble 설치 (apt 저장소 추가)
# 3. Gazebo Harmonic 설치
# 4. PX4 개발 툴체인 설치 (Tools/setup/ubuntu.sh)
# 5. Docker 이미지 빌드 (Dockerfile.dev)
# 6. VS Code 설정 동기화 (.vscode/settings.json)
# 7. Git hooks 설치 (pre-commit: clang-format, black, cmake-format)
# 8. 환경변수 설정 (~/.bashrc에 공통 alias, 경로 추가)
```

### 1.2 수동 확인 항목 (스크립트 완료 후)
```bash
# ROS 2 확인
ros2 --version
# 출력: ROS 2 Humble Hawksbill

# 빌드 툴 확인
colcon version-check
cmake --version
ninja --version
ccache --version

# Gazebo 확인
gz sim --version
# 출력: Gazebo Harmonic (예: 8.x.x)

# PX4 소스 확인
ls ~/PX4-Autopilot
# 없으면: git clone https://github.com/PX4/PX4-Autopilot.git --branch v1.15 --recursive ~/PX4-Autopilot

# Docker 이미지 확인
docker images | grep q250-v3-opti-dev
# q250-v3-opti-dev  latest  xxxx  xxMB

# VS Code Remote-WSL 연결 테스트
# VS Code → Ctrl+Shift+P → "WSL: Connect to WSL" → Ubuntu 선택
```

### 1.3 환경변수 로드 확인
```bash
# ~/.bashrc 재로드
source ~/.bashrc

# 핵심 alias 확인
px4-build --help    # 빌드 명령 테스트
px4-sitl --help     # SITL 실행 테스트
ros2-build --help   # ROS 2 빌드 테스트
preflight           # 사전 체크 스크립트
silvus-monitor      # Silvus 모니터링

# 환경변수 확인
echo $PX4_DIR
echo $PX4_SIM_MODEL
echo $GZ_SIM_RESOURCE_PATH
echo $FASTRTPS_DEFAULT_PROFILES_FILE
```

---

## 📋 Phase 2: Jetson 타겟 환경 구축 (45분)

### 2.1 SSH 키 교환 (개발 PC → Jetson)
```bash
# 개발 PC (WSL2)에서:
ssh-keygen -t ed25519 -C "q250-v3-opti-dev"
ssh-copy-id jetson@192.168.10.11

# 접속 테스트
ssh jetson@192.168.10.11 "echo 'Jetson connected'"
```

### 2.2 Jetson 기본 설정 스크립트 실행
```bash
# 개발 PC에서 Jetson으로 스크립트 복사 후 실행
scp scripts/setup/01_jetson_base.sh jetson@192.168.10.11:~/
ssh jetson@192.168.10.11 "chmod +x ~/01_jetson_base.sh && ~/01_jetson_base.sh"

# 스크립트 주요 작업:
# 1. 시스템 업데이트 및 필수 패키지 설치
# 2. 스왑 파일 설정 (8GB 권장, 빌드용)
# 3. 전원 모드 설정 (MAXN: 최대 성능)
# 4. 실시간 커널 패치 확인/적용
# 5. USB 권한 설정 (dialout, video 그룹)
# 6. 네트워크 고정 IP 설정 (192.168.10.11/24)
# 7. 방화벽 열기 (ROS 2 DDS 포트: 7400-7500, MAVLink: 14550)
```

### 2.3 ROS 2 Humble 설치 (Jetson)
```bash
# Jetson에서 실행
ssh jetson@192.168.10.11
scp ../scripts/setup/02_ros2_humble.sh jetson@192.168.10.11:~/
ssh jetson@192.168.10.11 "chmod +x ~/02_ros2_humble.sh && ~/02_ros2_humble.sh"

# 스크립트 주요 작업:
# 1. ROS 2 Humble apt 저장소 추가 (Ubuntu 22.04 arm64)
# 2. ros-humble-desktop 설치 (RViz2, Gazebo 제외 - Jetson용 경량)
# 3. ros-humble-px4-msgs, ros-humble-mavros, ros-humble-mavros-extras
# 4. ros-humble-realsense2-camera, ros-humble-depth-image-proc
# 5. ros-humble-nav2-costmap-2d, ros-humble-teb-local-planner
# 6. ros-humble-voxel-grid, ros-humble-tf2-tools
# 7. 환경변수 설정 (~/.bashrc)
# 8. colcon 빌드 테스트 (간단 패키지)
```

### 2.4 Jetson 검증
```bash
# Jetson에서 확인
ros2 --version
ros2 pkg list | grep -E "(px4|mavros|realsense|nav2|teb|voxel)"
colcon version-check

# RealSense SDK 확인
rs-fw-update -l
# Intel RealSense D435i 펌웨어 버전 표시

# 카메라 장착 후 테스트
ros2 launch realsense2_camera rs_launch.py enable_depth:=true
# 별도 터미널: ros2 topic hz /camera/depth/image_rect_raw
```

---

## 📋 Phase 3: PX4 펌웨어 빌드/플래싱 (30분)

### 3.1 개발 PC에서 PX4 빌드
```bash
# 개발 PC (WSL2)에서 실행
cd /Users/amaster/projectm/Q250-V3-Opti
./scripts/setup/03_px4_firmware.sh build

# 또는 수동:
cd ~/PX4-Autopilot
git fetch origin
git checkout v1.15
git submodule update --init --recursive
make px4_fmu-v6c_default -j$(nproc)

# 빌드 성공 확인:
ls -la build/px4_fmu-v6c_default/*.px4
# px4_fmu-v6c_default.px4 (약 1.96MB) 생성됨
```

### 3.2 펌웨어 플래싱 (개발 PC → Pixhawk via USB)
```bash
# Pixhawk를 USB로 개발 PC 연결 (부트로더 모드: 안전 스위치 누른 상태에서 연결)
./scripts/setup/03_px4_firmware.sh flash

# 또는 QGroundControl 사용 (초보자 권장):
# QGC → 기어 아이콘 → Firmware → Custom firmware file → px4_fmu-v6c_default.px4 선택
```

### 3.3 펌웨어 버전 확인
```bash
# QGC 연결 후: Vehicle Setup → Firmware → 현재 버전 확인
# PX4 v1.15.0 (custom) 표시되어야 함
```

---

## 📋 Phase 4: 통신 미들웨어 설정 (30분)

### 4.1 MAVLink Router 설정 (Jetson)
```bash
# Jetson에서 설정 파일 복사 및 서비스 등록
scp config/mavlink-router/main_silvus.conf jetson@192.168.10.11:/etc/mavlink-router/main.conf
scp scripts/setup/04_mavlink_router.sh jetson@192.168.10.11:~/
ssh jetson@192.168.10.11 "chmod +x ~/04_mavlink_router.sh && ~/04_mavlink_router.sh"

# 설정 확인:
# /etc/mavlink-router/main.conf 에 다음 엔드포인트 포함:
# [UartEndpoint pixhawk]
# Device = /dev/ttyTHS1
# Baud = 921600
# 
# [UdpEndpoint gcs]
# Address = 192.168.10.10
# Port = 14550
# 
# [UdpEndpoint silvus]
# Address = 192.168.10.11
# Port = 14540
```

### 4.2 uXRCE-DDS Agent 설정 (Jetson)
```bash
scp scripts/setup/05_uxrce_dds_agent.sh jetson@192.168.10.11:~/
ssh jetson@192.168.10.11 "chmod +x ~/05_uxrce_dds_agent.sh && ~/05_uxrce_dds_agent.sh"

# systemd 서비스 등록 확인:
systemctl status uxrce-dds-agent
# Active: active (running)

# 로그 확인:
journalctl -fu uxrce-dds-agent
# 출력: "Client connected", "Session created"
```

### 4.3 설정 파일 동기화 (개발 PC ↔ Jetson)
```bash
# 개발 PC에서 Jetson으로 설정 파일 동기화
./scripts/setup/apply_configs.sh

# 수동 동기화 (상세):
# 1. Fast-DDS 설정 (Silvus 최적화)
scp config/jetson/fastdds_silvus_config.xml jetson@192.168.10.11:/home/jetson/fastdds_config.xml

# 2. MAVLink Router 설정
scp config/mavlink-router/main_silvus.conf jetson@192.168.10.11:/etc/mavlink-router/main.conf

# 3. 네트워크 설정 (Silvus 연동)
scp config/network/01-netcfg-ap.yaml jetson@192.168.10.11:/etc/netplan/
scp config/network/01-netcfg-router.yaml jetson@192.168.10.11:/etc/netplan/
scp config/network/setup_ufw.sh jetson@192.168.10.11:~/
ssh jetson@192.168.10.11 "sudo ~/setup_ufw.sh"

# 4. ROS 2 DDS 설정 동기화
ssh jetson@192.168.10.11 "mkdir -p ~/ros2_ws/src && cp fastdds_config.xml ~/ros2_ws/"
```

---

## 📋 Phase 5: 사전 비행 체크 및 검증 (15분)

### 5.1 자동 체크 스크립트 실행
```bash
# 개발 PC에서 실행 (Jetson SSH로 원격 실행 포함)
./scripts/preflight/check_all.sh

# 체크 항목:
# □ 개발 PC: ROS 2, Gazebo, PX4 빌드 환경
# □ Jetson: ROS 2, RealSense, MAVLink Router, uXRCE-DDS Agent
# □ 통신: MAVLink Router 양방향, uXRCE-DDS Agent 연결
# □ 센서: RealSense 토픽, LiDAR 거리, Optical-Flow 품질
# □ PX4: 파라미터 적용, EKF2 설정, 펌웨어 버전
# □ Silvus: 링크 품질 (RSSI, 패킷로스, RTT)
```

### 5.2 개별 수동 검증 (체크리스트)

#### 개발 PC (WSL2)
```bash
# ROS 2 환경
ros2 --version && colcon version-check
px4-build --help
ros2-build --help

# SITL 테스트
px4-sitl  # Gazebo + PX4 SITL 실행 테스트 (Ctrl+C로 종료)

# VS Code 연결
# Ctrl+Shift+P → "WSL: Connect to WSL" → 터미널에서 `px4-build` 테스트
```

#### Jetson (SSH 접속 후)
```bash
# 서비스 상태
systemctl status mavlink-router uxrce-dds-agent
journalctl -fu mavlink-router -n 20
journalctl -fu uxrce-dds-agent -n 20

# ROS 2 토픽 확인
ros2 topic list | grep -E "(camera|mavros|px4|silvus)"
ros2 topic hz /camera/depth/image_rect_raw
ros2 topic hz /mavros/distance_sensor/lidar

# MAVLink 통신 확인
ros2 topic echo /mavros/local_position/odom --once
ros2 topic echo /fmu/out/vehicle_status --once
```

#### Silvus 데이터링크
```bash
# 웹 UI 접속 (브라우저)
http://192.168.10.11  # Air Unit 웹 UI
# → Status: Connected, RSSI > -70dBm, Packet Loss < 1%

# 모니터링 스크립트
python3 scripts/silvus_monitor.py --air-unit-ip 192.168.10.11
# 출력: RSSI, SNR, Packet Loss, RTT, Hop Count 실시간 표시
```

---

## 📋 Phase 6: VS Code 개발 워크플로우 (10분)

### 6.1 VS Code Remote-WSL + SSH 설정
```bash
# 개발 PC에서 VS Code 열기
# 1. Ctrl+Shift+P → "WSL: Connect to WSL" → Ubuntu 선택
# 2. 터미널에서 `cd /Users/amaster/projectm/Q250-V3-Opti`
# 3. Ctrl+Shift+P → "Remote-SSH: Connect to Host" → jetson@192.168.10.11 추가
# 4. 멀티 루트 워크스페이스 저장: `Q250-V3-Opti.code-workspace`
```

### 6.2 추천 확장 프로그램 (자동 설치됨)
```json
// .vscode/extensions.json
{
  "recommendations": [
    "ms-vscode.cpptools",
    "ms-python.python",
    "ms-ros.ros2",
    "ms-vscode.cmake-tools",
    "ms-vscode.docker",
    "redhat.vscode-yaml",
    "foxundermoon.shell-format",
    "streetsidesoftware.code-spell-checker"
  ]
}
```

### 6.3 디버깅 설정 (launch.json)
```json
// .vscode/launch.json
{
  "configurations": [
    {
      "name": "PX4 SITL Debug",
      "type": "cppdbg",
      "request": "launch",
      "program": "${workspaceFolder}/PX4-Autopilot/build/px4_sitl_default/px4",
      "args": ["gazebo", "q250_v3_opti"],
      "cwd": "${workspaceFolder}/PX4-Autopilot",
      "MIMode": "gdb",
      "setupCommands": [{ "text": "-enable-pretty-printing", "ignoreFailures": true }]
    },
    {
      "name": "ROS 2 Node Debug (Jetson)",
      "type": "python",
      "request": "attach",
      "connect": { "host": "192.168.10.11", "port": 5678 },
      "pathMappings": [{ "localRoot": "${workspaceFolder}", "remoteRoot": "/home/jetson/ros2_ws" }]
    }
  ]
}
```

---

## 📋 Phase 7: CI/CD 파이프라인 (GitHub Actions) - 선택사항

### 7.1 기본 워크플로우 생성
```bash
mkdir -p .github/workflows

cat > .github/workflows/ci.yml << 'EOF'
name: CI

on: [push, pull_request]

jobs:
  build-px4:
    runs-on: ubuntu-latest
    container: q250-v3-opti-dev:latest
    steps:
      - uses: actions/checkout@v4
        with: { submodules: recursive }
      - name: Build PX4
        run: make px4_fmu-v6c_default -j$(nproc)
      - name: Upload firmware
        uses: actions/upload-artifact@v4
        with: { name: px4-firmware, path: build/px4_fmu-v6c_default/*.px4 }

  build-ros2:
    runs-on: ubuntu-latest
    container: q250-v3-opti-dev:latest
    steps:
      - uses: actions/checkout@v4
      - name: Build ROS 2
        run: |
          cd ros2_ws
          colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release
      - name: Test
        run: |
          cd ros2_ws
          colcon test --event-handlers console_direct+
EOF
```

### 7.2 Docker 이미지 자동 빌드/푸시
```yaml
# .github/workflows/docker.yml
name: Docker

on:
  push:
    tags: ['v*']

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & Push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: Dockerfile.dev
          push: true
          tags: ghcr.io/krill0188/q250-v3-opti-dev:${{ github.ref_name }}
```

---

## 🚨 트러블슈팅 퀵 레퍼런스

| 증상 | 원인 | 해결 |
|------|------|------|
| WSL2에서 Docker 안 됨 | WSL2 integration 꺼짐 | Docker Desktop → Settings → Resources → WSL Integration → Enable |
| Jetson SSH 접속 안 됨 | 방화벽, IP 변경 | `ufw allow 22`, 고정 IP 확인, `ssh -v`로 디버깅 |
| MAVLink Router 연결 안 됨 | UART 권한, 포트 충돌 | `sudo usermod -aG dialout $USER`, 재로그인, 포트 중복 확인 |
| uXRCE-DDS Agent 연결 실패 | PX4 파라미터 불일치 | `UXRCE_DDS_CFG=2`, `SER_TEL2_BAUD=921600`, 펌웨어 재부팅 |
| ROS 2 토픽 안 보임 | DDS 도메인 불일치 | `ROS_DOMAIN_ID` 동일 설정 (기본 0), Fast-DDS 설정 동기화 |
| RealSense 토픽 안 나옴 | USB 3.0 포트 아님, 펌웨어 구버전 | USB 3.0 포트 사용, `rs-fw-update`로 최신 펌웨어 |
| Gazebo SITL 실행 안 됨 | GPU 드라이버, Vulkan 없음 | WSL2에서 `gpu` 지원 확인, `export LIBGL_ALWAYS_SOFTWARE=1` |
| Git pre-commit 실패 | 포맷터 버전 불일치 | `pre-commit autoupdate`, 로컬에서 `pre-commit run --all-files` |

---

## 📚 참고 문서 및 자동화 스크립트

| 스크립트/문서 | 위치 | 용도 |
|---------------|------|------|
| WSL2 개발 PC 설정 | `scripts/setup/00_wsl2_dev_pc.sh` | 개발 PC 원클릭 설정 |
| Jetson 기본 설정 | `scripts/setup/01_jetson_base.sh` | Jetson 시스템 설정 |
| ROS 2 설치 | `scripts/setup/02_ros2_humble.sh` | ROS 2 Humble 설치 |
| PX4 펌웨어 빌드/플래시 | `scripts/setup/03_px4_firmware.sh` | 펌웨어 빌드 및 플래싱 |
| MAVLink Router | `scripts/setup/04_mavlink_router.sh` | 라우터 설정 및 서비스 등록 |
| uXRCE-DDS Agent | `scripts/setup/05_uxrce_dds_agent.sh` | DDS 에이전트 서비스 등록 |
| 설정 동기화 | `scripts/setup/apply_configs.sh` | 개발 PC ↔ Jetson 설정 동기화 |
| 사전 비행 체크 | `scripts/preflight/check_all.sh` | 전체 시스템 검증 |
| 개발 환경 가이드 | `references/development_environment.md` | 상세 아키텍처, 환경변수, VS Code 설정 |
| Docker 개발 컨테이너 | `Dockerfile.dev` | 재현 가능 빌드 환경 |
| VS Code 설정 | `.vscode/settings.json` | CMake, 빌드, 터미널, SSH 설정 |

---

*작성: 2026-11-04 | 기반: references/development_environment.md, scripts/setup/*.sh*