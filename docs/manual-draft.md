# Q250-V3 Opti 자율비행 드론 운용 매뉴얼 (초안)

> **작성 기준**: HW 설정 → SW 설치 → SW 설정 → SW 운용 융합 순서  
> **대상 기체**: Q250-V3 Opti (Holybro Pixhawk 6C mini + Jetson Nano)  
> **펌웨어**: PX4 v1.15 (v1.16 미지원: Optical-Flow/LiDAR)  
> **운용 모델**: 헤드리스 컴패니언 + 원격 QGC + RC 비상 조종  
> **작성일**: 2026-11-02  
> **버전**: 0.1 (초안)

---

## 목차

1. [하드웨어 설정 (HW Setup)](#1-하드웨어-설정-hw-setup)
2. [소프트웨어 설치 (SW Installation)](#2-소프트웨어-설치-sw-installation)
3. [소프트웨어 설정 (SW Configuration)](#3-소프트웨어-설정-sw-configuration)
4. [운용 융합 (Operation Integration)](#4-운용-융합-operation-integration)
5. [부록: 참조 자료 및 링크](#부록-참조-자료-및-링크)

---

# 1. 하드웨어 설정 (HW Setup)

## 1.1 기체 스펙 및 구성품 확인

### 1.1.1 주요 하드웨어 사양

| 구성품 | 모델/사양 | 비고 |
|--------|-----------|------|
| **비행 컨트롤러** | Holybro Pixhawk 6C mini (FMUv6C) | PX4/ArduPilot 호환 |
| **Optical-Flow + LiDAR** | 내장 Micolink 모듈 | UART4, 115200 baud, 100Hz |
| **ESC** | F4 4in1 50A BLHeli_32 | DShot300 지원 |
| **모터** | BrotherHobby 브러시리스 | 고성능 저소음 |
| **프레임** | 풀카본 케이지 타입 (250mm) | 프롭 가드 일체형 |
| **컴패니언 컴퓨터** | NVIDIA Jetson Nano (J41 헤더) | Ubuntu 20.04 / JetPack 4.6+ |
| **전원 모듈** | Holybro PM07 (내장) | 6.6V/3.3V ADC, 전류 센서 |
| **외부 전원** | 2채널 UBEC (5V/4A + 12V/2A) | Jetson 및 페이로드용 |
| **배터리** | 4S LiPo 4000mAh 50C (XT60) | 별도 구매 |
| **RC 조종기/수신기** | SBUS/CRSF/PPM 호환 | 별도 구매 |
| **Telemetry** | SiK Radio V3 433MHz | 옵션 (GCS 장거리용) |
| **GPS/Compass** | M10Q-5883 | 옵션 (실외 비행용) |

### 1.1.2 무게 및 비행 성능

| 항목 | 값 |
|------|-----|
| 기체 중량 (배터리 제외) | 475g |
| 전체 중량 (카메라+Jetson+배터리) | ~1080g |
| 최대 비행 시간 (4000mAh, 페이로드 제외) | 10분 이상 |
| 실내 최대 고도 (Optical-Flow 기준) | 8m |
| 권장 실내 조도 | > 100 Lux |

---

## 1.2 FC 포트맵 및 배선도

### 1.2.1 Pixhawk 6C mini 포트 할당표

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Pixhawk 6C mini 포트맵 (Q250-V3 Opti)                    │
├──────────────┬──────────────────────┬──────────────────────────────────────┤
│ 포트         │ 기능                 │ 연결 대상                            │
├──────────────┼──────────────────────┼──────────────────────────────────────┤
│ TELEM1       │ MAVLink GCS          │ SiK Telemetry / USB-TTL (QGC용)      │
│ TELEM2       │ **Companion (DDS)**  │ **Jetson Nano UART (J41) - 921600**  │
│ TELEM3/GPS1  │ GPS + Compass        │ M10Q-5883 (옵션, 실외용)             │
│ UART4/GPS2   │ **Optical-Flow/LiDAR**│ **내장 Micolink 모듈 - 115200**      │
│ I2C1         │ External Compass     │ GPS 모듈 내장 Compass                │
│ I2C2         │ 보조 센서            │ -                                    │
│ CAN1         │ DroneCAN ESC         │ 미사용 (DShot 사용)                  │
│ CAN2         │ -                    │ -                                    │
│ PWM MAIN 1-6 │ 미사용               │ -                                    │
│ **PWM AUX 1-4** │ **Motor 1-4 (DShot300)** │ **F4 4in1 ESC**            │
│ PWM AUX 5-6  │ LED / 파라슈트       │ 선택                                 │
│ ADC 6.6V     │ 배터리 전압          │ 파워 모듈                            │
│ ADC 3.3V     │ 배터리 전류          │ 파워 모듈                            │
│ USB-C        │ 펌웨어/설정          │ PC (QGC)                             │
│ MicroSD      │ 로그 저장            │ U3 Class 10+ 32GB 권장               │
└──────────────┴──────────────────────┴──────────────────────────────────────┘
```

### 1.2.2 Jetson Nano ↔ FC UART 배선 (TELEM2)

```
Pixhawk 6C mini TELEM2 (SH 6P)          Jetson Nano J41 Header
┌─────────────────────────────┐         ┌─────────────────────────────┐
│ 1  VCC (5V)      ────────── │ ─────── │ Pin 2  (5V Power)           │
│ 2  TX (FC→Jetson) ──────────│ ─────── │ Pin 10 (UART2 RXD / ttyTHS1)│
│ 3  RX (Jetson→FC) ──────────│ ─────── │ Pin 8  (UART2 TXD / ttyTHS1)│
│ 4  CTS ─────────────────────│         │ (미연결 또는 Loopback)       │
│ 5  RTS ─────────────────────│         │ (미연결 또는 Loopback)       │
│ 6  GND      ────────────────│ ─────── │ Pin 6  (GND)                 │
└─────────────────────────────┘         └─────────────────────────────┘
```

> **권장**: USB-TTL 컨버터(CP2102/FT232) 중계 사용 → 전송 안정성↑, 전기적 절연
> - FC TELEM2 TX → USB-TTL RX
> - FC TELEM2 RX ← USB-TTL TX
> - Jetson `/dev/ttyUSB0` 또는 `/dev/ttyTHS1` 인식 확인

### 1.2.3 모터 배선 및 회전 방향 (DShot300, AUX 1-4)

```
        전방 (Front, +X)
            ▲
            │
      Motor 3 (CCW)  ●───────●  Motor 1 (CW)
        AUX 3          │       │          AUX 1
                       │  FC   │
                       │ (COG) │
      Motor 2 (CW)   ●───────●  Motor 4 (CCW)
        AUX 2                  AUX 4
            │
            ▼
        후방 (Rear, -X)
```

| 모터 | AUX 포트 | 위치 (FRD, m) | 회전 방향 | 비고 |
|------|----------|---------------|-----------|------|
| 1 | AUX 1 | (+0.120, -0.120, -0.025) | CW (시계) | 전방 오른쪽 |
| 2 | AUX 2 | (-0.120, -0.120, -0.025) | CW (시계) | 후방 오른쪽 |
| 3 | AUX 3 | (+0.120, +0.120, -0.025) | CCW (반시계) | 전방 왼쪽 |
| 4 | AUX 4 | (-0.120, +0.120, -0.025) | CCW (반시계) | 후방 왼쪽 |

> **좌표계**: FRD (Forward-Right-Down), 원점 = **무게중심(COG)**
> **프레임 대각선**: 약 250mm → 모터 반경 ≈ 0.177m

### 1.2.4 전원 시스템 배선

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           전원 시스템 블록 다이어그램                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   [4S LiPo 4000mAh] ──XT60──► [PM07 Power Module] ──► [Pixhawk 6C mini]   │
│         │                      │  ├─ 5V/3A BEC ──► [Servo/RX Power]         │
│         │                      │  ├─ 6.6V ADC ──► [Battery Voltage Sense]   │
│         │                      │  └─ 3.3V ADC ──► [Battery Current Sense]   │
│         │                      │                                             │
│         └──────► [2-Channel UBEC] ──► 5V/4A ──► [Jetson Nano]               │
│                            │              12V/2A ──► [Payload/Camera]        │
│                            │                                             │
│                            └──────► [SBC 상단 통합 마운트] (배터리 홀더 일체)  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**전원 시퀀스 검증:**
1. 메인 배터리 연결 → FC 부팅 (LED 시퀀스 확인: 안전→부팅→준비)
2. Jetson 전원 투자 → 부팅 완료 대기 (약 60초, 녹색 LED 고정)
3. uXRCE-DDS Agent 자동 시작 확인 (`systemctl status uxrce-dds-agent`)
4. QGC 연결 → MAVLink 통신/파라미터 동기화 확인

---

## 1.3 RC 수신기 연결 (비상 조종용)

```
RC 수신기 (SBUS/CRSF/PPM) ──► Pixhawk 6C mini RC IN 포트
├── 채널 1: Roll (우측 스틱 좌우)
├── 채널 2: Pitch (우측 스틱 상하)
├── 채널 3: Throttle (좌측 스틱 상하)
├── 채널 4: Yaw (좌측 스틱 좌우)
├── 채널 5: Flight Mode Switch (Pos/Alt/Stab/Offboard/Return)
├── 채널 6: Arm/Disarm Switch (필수)
├── 채널 7: **Kill Switch (즉시 모터 정지) — 필수!**
└── 채널 8: Return/RTL Switch
```

> **핵심**: RC는 **FC에 직접 연결**되어 WiFi/Jetson/QGC 장애와 무관하게 작동
> **Kill Switch는 반드시 별도 스위치(토글/버튼)에 할당** — 실수 방지 가드 권장

---

## 1.4 네트워크 토폴로지

### 1.4.1 권장 구성: Jetson WiFi AP 모드 (단일 기체, 가장 안정적)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         네트워크 토폴로지 (AP 모드)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐       WiFi (192.168.10.x)       ┌─────────────────┐  │
│   │  콘솔 노트북     │ ◄─────────────────────────────► │  Jetson Nano    │  │
│   │  (Operator)     │      SSID: Q250-Opti            │  (AP: 192.168.10.1)│  │
│   │                 │      PW: quad250opti            │                 │  │
│   │  - QGC (UDP:14550)                                 │  - MAVLink      │  │
│   │  - SSH (TCP:22)                                    │    Router       │  │
│   │  - VS Code Remote                                  │  - uXRCE-DDS    │  │
│   │  - ROS 2 개발                                       │    Agent        │  │
│   └─────────────────┘                                  └────────┬────────┘  │
│                                                                     │         │
│                                                          ┌──────────┴────────┐ │
│                                                          │  Pixhawk 6C mini │ │
│                                                          │  (TELEM2: UART)  │ │
│                                                          └──────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Jetson AP 모드 설정:**
```bash
# NetworkManager로 AP 생성
sudo nmcli device wifi hotspot con-name "Q250-AP"     ssid "Q250-Opti" band bg     password "quad250opti" ip4 192.168.10.1/24

# 확인
nmcli connection show Q250-AP
```

### 1.4.2 대안: 공유 라우터/핫스팟 (멀티 드론/고정 환경)

| 장치 | IP | 역할 |
|------|-----|------|
| 라우터/AP | 192.168.1.1 | 게이트웨이, DHCP |
| **Jetson Nano** | **192.168.1.100 (고정)** | 컴패니언 컴퓨터 |
| **콘솔 노트북** | **192.168.1.101 (DHCP)** | 운영자 스테이션 |
| 기체 2 (확장) | 192.168.1.102 | 멀티 드론 |

**Jetson 고정 IP 설정 (Netplan):**
```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  renderer: networkd
  wifis:
    wlan0:
      dhcp4: false
      addresses: [192.168.1.100/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
      access-points:
        "MyRouter":
          password: "router_password"
```

---

# 2. 소프트웨어 설치 (SW Installation)

## 2.1 설치 순서 개요

```
설치 순서 (의존성 고려):
├── 2.2 Jetson Base OS (JetPack 4.6+, Ubuntu 20.04)
├── 2.3 ROS 2 Humble (Ubuntu 20.04 호환)
├── 2.4 PX4 펌웨어 빌드/플래싱 (v1.15 브랜치)
├── 2.5 MAVLink Router (MAVLink 라우팅)
├── 2.6 uXRCE-DDS Agent (ROS 2 ↔ PX4 브리지)
├── 2.7 QGroundControl (노트북, GCS)
└── 2.8 개발 도구 (VS Code, Git, TMUX 등)
```

---

## 2.2 Jetson Nano Base OS 설치

### 2.2.1 JetPack 4.6.1 (L4T 32.7.1) 플래싱

```bash
# 호스트 PC (Linux x86_64)에서 수행
# 1. NVIDIA SDK Manager 설치
wget https://developer.nvidia.com/sdk-manager
chmod +x sdkmanager_*.deb
sudo apt install ./sdkmanager_*.deb

# 2. SDK Manager 실행 → Jetson Nano Developer Kit 선택
#    - JetPack 4.6.1 선택
#    - Target OS: Ubuntu 20.04
#    - Flash 시 Jetson을 Recovery Mode로 진입 (FC REC 버튼 누른 상태에서 전원)

# 3. 또는 SD 카드 이미지 직접 쓰기 (더 간단)
#    https://developer.nvidia.com/jetpack-sdk-461 에서 이미지 다운로드
#    balenaEtcher 등으로 SD 카드에 플래싱
```

### 2.2.2 Jetson 초기 설정

```bash
# Jetson 부팅 후 첫 로그인 (기본: jetson/jetson)
# 비밀번호 변경 필수
passwd

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지
sudo apt install -y     git curl wget vim htop tmux net-tools     build-essential cmake pkg-config     python3-pip python3-venv python3-dev     libssl-dev libudev-dev     usbutils pciutils lsb-release

# 시리얼 포트 권한 (다이얼아웃 그룹)
sudo usermod -a -G dialout $USER
# 재로그인 필요

# 스왑 파일 늘리기 (빌드용, 4GB→8GB)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2.2.3 Jetson 전용 최적화

```bash
# 최대 성능 모드 (전원 연결 시)
sudo nvpmodel -m 0
sudo jetson_clocks

# 자동 시작 등록 (rc.local 또는 systemd)
sudo tee /etc/systemd/system/jetson-performance.service > /dev/null << 'EOF'
[Unit]
Description=Jetson Performance Mode
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c "nvpmodel -m 0 && jetson_clocks"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable jetson-performance.service
```

---

## 2.3 ROS 2 Humble 설치 (Ubuntu 20.04)

```bash
# ROS 2 Humble 리포지토리 추가
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key     -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg]     http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" |     sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y     ros-humble-desktop     python3-colcon-common-extensions     python3-rosdep     python3-vcstool

# 환경 설정 (bashrc에 추가)
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc

# rosdep 초기화
sudo rosdep init
rosdep update

# 추가 유용한 패키지
sudo apt install -y     ros-humble-rmw-fastrtps-cpp     ros-humble-px4-msgs     ros-humble-mavros     ros-humble-mavros-extras
```

---

## 2.4 PX4 펌웨어 빌드 및 플래싱

### 2.4.1 소스 코드 준비 (v1.15 브랜치)

```bash
# 개발 PC (또는 Jetson)에서 수행
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --branch v1.15 --recursive
cd PX4-Autopilot

# 서브모듈 업데이트
git submodule update --init --recursive

# 툴체인 설치 (Ubuntu 20.04/22.04)
bash ./Tools/setup/ubuntu.sh

# 의존성 확인
make px4_fmu-v6c_default  # 빌드 테스트 (플래싱 안 함)
```

### 2.4.2 Q250-V3 Opti용 보드 설정 확인

`boards/holybro/pixhawk6c/default.px4board` 필수 모듈:

```kconfig
# uXRCE-DDS Client (ROS 2 브리지) - 기본 포함됨
CONFIG_MODULES_UXRCE_DDS_CLIENT=y

# DShot ESC 드라이버
CONFIG_DRIVERS_DSHOT=y

# Optical Flow MAVLink 수신
CONFIG_MAVLINK_RECEIVER=y

# EKF2 Optical Flow / Range Finder
CONFIG_EKF2_OPTICAL_FLOW=y
CONFIG_EKF2_RANGE_FINDER=y

# Fake GPS (실내 Mission/RTL 테스트용, 선택)
# CONFIG_DRIVERS_FAKE_GPS=y
```

### 2.4.3 펌웨어 플래싱 (QGroundControl 권장)

```bash
# 방법 1: QGC 사용 (가장 쉬움, 권장)
# 1. QGC 실행 → 기어 아이콘 → Firmware
# 2. "Custom firmware file..." 선택 후 빌드된 .px4 파일 로드
# 3. 또는 "Standard Version" → "Holybro Pixhawk 6C mini" 선택

# 방법 2: CLI 직접 플래싱
cd ~/PX4-Autopilot
make px4_fmu-v6c_default upload  # USB 연결 상태에서

# 방법 3: 부트로더 모드 강제 진입 후 플래싱
# FC 안전 스위치 누른 상태에서 USB 연결 → 부트로더 모드 진입
make px4_fmu-v6c_default upload
```

> **중요**: PX4 v1.15 사용 필수. v1.16부터 Optical-Flow/LiDAR 드라이버 변경으로 Q250-V3 Opti 내장 센서 미지원.

---

## 2.5 MAVLink Router 설치 및 설정

```bash
# Jetson에서 설치
sudo apt install -y mavlink-router

# 설정 파일: /etc/mavlink-router/main.conf
sudo tee /etc/mavlink-router/main.conf > /dev/null << 'EOF'
[General]
TcpServerPort=5760
ReportStats=true
MavlinkDialect=auto

[UartEndpoint fc]
Device=/dev/ttyTHS1
Baud=921600
FlowControl=none

[UdpEndpoint qgc]
Mode=Normal
Address=192.168.10.255  # 브로드캐스트 (노트북 자동 발견)
Port=14550

[UdpEndpoint ros2]
Mode=Normal
Address=127.0.0.1
Port=14540  # MAVROS용 (필요 시)

# 멀티 기체 시 추가 엔드포인트 예시
#[UdpEndpoint uav2]
#Mode=Normal
#Address=192.168.1.102
#Port=14550
EOF

# 서비스 등록 및 시작
sudo systemctl enable mavlink-router
sudo systemctl start mavlink-router

# 상태 확인
systemctl status mavlink-router
journalctl -fu mavlink-router
```

---

## 2.6 uXRCE-DDS Agent 설치 (ROS 2 브리지)

### 2.6.1 Agent 빌드

```bash
# ROS 2 워크스페이스 생성
mkdir -p ~/ros2_px4_ws/src
cd ~/ros2_px4_ws/src

# px4_msgs (PX4 v1.15 브랜치)
git clone -b v1.15 https://github.com/PX4/px4_msgs.git

# Micro-XRCE-DDS-Agent
git clone -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git

# px4_ros_com (메시지 번역 노드, v1.16+ 호환용)
git clone https://github.com/PX4/px4_ros_com.git

# 빌드
cd ~/ros2_px4_ws
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# 환경 설정 자동화
echo "source ~/ros2_px4_ws/install/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 2.6.2 Fast-DDS 설정 (WiFi 최적화)

```xml
<!-- /home/jetson/fastdds_config.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
    <participant profile_name="px4_participant" is_default_profile="true">
        <rtps>
            <builtin>
                <discovery_config>
                    <discoveryProtocol>SIMPLE</discoveryProtocol>
                    <leaseDuration>
                        <sec>30</sec>
                    </leaseDuration>
                    <metatrafficUnicastLocatorList>
                        <locator>
                            <udpv4>
                                <address>192.168.10.1</address>
                                <port>7400</port>
                            </udpv4>
                        </locator>
                    </metatrafficUnicastLocatorList>
                    <initialPeersList>
                        <!-- 멀티 기체 시 다른 기체 IP 추가 -->
                        <!-- <locator>
                            <udpv4>
                                <address>192.168.10.2</address>
                                <port>7400</port>
                            </udpv4>
                        </locator> -->
                    </initialPeersList>
                </discovery_config>
            </builtin>
            <port>
                <portBase>7400</portBase>
            </port>
        </rtps>
    </participant>
</profiles>
```

### 2.6.3 Agent 시스템 서비스 (UDP 모드 권장)

```bash
# /etc/systemd/system/uxrce-dds-agent.service
sudo tee /etc/systemd/system/uxrce-dds-agent.service > /dev/null << 'EOF'
[Unit]
Description=Micro XRCE-DDS Agent for PX4 (UDP)
After=network.target mavlink-router.service
Wants=mavlink-router.service

[Service]
Type=simple
User=jetson
Group=jetson
WorkingDirectory=/home/jetson/ros2_px4_ws
Environment=FASTRTPS_DEFAULT_PROFILES_FILE=/home/jetson/fastdds_config.xml
Environment=RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ExecStart=/bin/bash -c "source /opt/ros/humble/setup.bash && source install/setup.bash && MicroXRCEAgent udp4 -p 8888"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 서비스 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable uxrce-dds-agent
sudo systemctl start uxrce-dds-agent

# 로그 확인
journalctl -fu uxrce-dds-agent
```

---

## 2.7 QGroundControl 설치 (노트북)

```bash
# Ubuntu/Debian
sudo apt install -y qgroundcontrol

# 또는 AppImage 다운로드 (최신 버전)
wget https://d176tv9ibo4jno.cloudfront.net/latest/QGroundControl.AppImage
chmod +x QGroundControl.AppImage
./QGroundControl.AppImage

# Windows/Mac: https://docs.qgroundcontrol.com/master/en/getting_started/download_and_install.html
```

---

## 2.8 개발 환경 설정 (노트북 + Jetson)

### 2.8.1 SSH 키 기반 인증

```bash
# 노트북에서 키 생성 및 복사
ssh-keygen -t ed25519 -C "q250-operator"
ssh-copy-id jetson@192.168.10.1

# Jetson에서 보안 강화
sudo sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### 2.8.2 TMUX 자동 세션 (Jetson)

```bash
# ~/.bashrc 에 추가
cat >> ~/.bashrc << 'EOF'

# SSH 접속 시 TMUX 자동 연결
if [ -z "$TMUX" ] && [ "$SSH_CONNECTION" ]; then
    tmux attach -t jetson 2>/dev/null || tmux new -s jetson
fi

# 유용한 별칭
alias ddslog='journalctl -fu uxrce-dds-agent'
alias mavlog='journalctl -fu mavlink-router'
alias ros2ws='cd ~/ros2_px4_ws && source install/setup.bash'
alias px4log='cd ~/PX4-Autopilot && make px4_sitl gz_x500'
EOF

# TMUX 세션 레이아웃 저장 스크립트
cat > ~/scripts/tmux_layout.sh << 'EOF'
#!/bin/bash
# tmux 세션 생성 및 레이아웃 설정
tmux new-session -d -s jetson

# 창 0: 메인 터미널
tmux rename-window -t jetson:0 'main'

# 창 1: DDS Agent 로그
tmux new-window -t jetson:1 -n 'dds-log'
tmux send-keys -t jetson:1 'journalctl -fu uxrce-dds-agent' Enter

# 창 2: MAVLink Router 로그
tmux new-window -t jetson:2 -n 'mav-log'
tmux send-keys -t jetson:2 'journalctl -fu mavlink-router' Enter

# 창 3: ROS 2 토픽 모니터링
tmux new-window -t jetson:3 -n 'ros2-topics'
tmux send-keys -t jetson:3 'source /opt/ros/humble/setup.bash && source ~/ros2_px4_ws/install/setup.bash && ros2 topic list | grep fmu' Enter

# 창 4: 시스템 리소스
tmux new-window -t jetson:4 -n 'htop'
tmux send-keys -t jetson:4 'htop' Enter

tmux select-window -t jetson:0
EOF

chmod +x ~/scripts/tmux_layout.sh
```

### 2.8.3 VS Code Remote SSH 설정 (노트북)

```json
// ~/.ssh/config (노트북)
Host q250-jetson
    HostName 192.168.10.1
    User jetson
    IdentityFile ~/.ssh/id_ed25519
    ForwardX11 yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

VS Code에서 `Remote-SSH: Connect to Host...` → `q250-jetson` 선택

---

# 3. 소프트웨어 설정 (SW Configuration)

## 3.1 설정 순서 개요

```
설정 순서:
├── 3.2 PX4 파라미터 설정 (QGC)
├── 3.3 MAVLink Router 검증
├── 3.4 uXRCE-DDS Agent 검증
├── 3.5 ROS 2 통신 검증
├── 3.6 네트워크/방화벽/보안 설정
└── 3.7 설정 백업 및 버전 관리
```

---

## 3.2 PX4 파라미터 설정 (QGroundControl)

### 3.2.1 Airframe 선택

```
Vehicle Setup → Airframe
├── Quadrotor X → Generic Quadrotor X
├── Apply & Reboot
└── 확인: CA_AIRFRAME=0, CA_ROTOR_COUNT=4
```

> **주의**: Q250-V3 전용 에어프레임 정의 없음 → Generic 사용 후 Geometry 수동 설정

### 3.2.2 Actuators / Motor Geometry (필수 수동 설정)

```
Vehicle Setup → Actuators → Geometry (Advanced 체크)
```

| 모터 | Position X (m) | Position Y (m) | Position Z (m) | Direction CCW |
|------|----------------|----------------|----------------|---------------|
| 1 (AUX1) | +0.120 | -0.120 | -0.025 | False (CW) |
| 2 (AUX2) | -0.120 | -0.120 | -0.025 | False (CW) |
| 3 (AUX3) | +0.120 | +0.120 | -0.025 | True (CCW) |
| 4 (AUX4) | -0.120 | +0.120 | -0.025 | True (CCW) |

```
Vehicle Setup → Actuators → Outputs
├── Motor 1 → AUX1 (DShot300)
├── Motor 2 → AUX2 (DShot300)
├── Motor 3 → AUX3 (DShot300)
├── Motor 4 → AUX4 (DShot300)
├── Output Mode: DShot300 (모든 모터)
└── Disarmed: 0, Min: 48, Max: 2000
```

**Actuator Testing으로 모터 방향 검증:**
```
1. 프로펠러 제거 필수!
2. 슬라이더 10%씩 올리며 회전 방향 확인
3. 방향 불일치 시 MAVLink Console에서:
   > dshot reverse -m 1   (모터 번호: AUX 인덱스 1-4)
   > dshot save
4. 재테스트 후 프로펠러 장착
```

### 3.2.3 Optical-Flow & LiDAR 설정 (UART4, PX4 v1.14+)

**하드웨어 연결**: FC UART4 (GPS2 포트) ↔ 내장 Optical-Flow 모듈

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `MAV_1_CONFIG` | `TELEM 4` | Optical-Flow 포트 할당 (UART4 번호 확인) |
| `MAV_1_MODE` | `Normal` (1) | MAVLink 스트리밍 모드 |
| `SER_TEL4_BAUD` | `115200` | 보드레이트 |
| `SENS_FLOW_ROT` | `0` (No rotation) | 센서 장착 회전 (전방=0) |
| `EKF2_OF_CTRL` | `1` (Enabled) | Optical Flow 융합 활성화 |
| `EKF2_RNG_CTRL` | `2` (Enabled: Range height fusion) | LiDAR 고도 융합 모드 |
| `EKF2_HGT_REF` | `2` (Range sensor) | 고도 기준 = LiDAR |
| `EKF2_OF_POS_X` | `0.0` | Flow 센터 X 오프셋 (COG 기준, m) |
| `EKF2_OF_POS_Y` | `0.0` | Flow 센터 Y 오프셋 |
| `EKF2_OF_POS_Z` | `-0.035` | Flow 센터 Z 오프셋 (아래로 -) |
| `EKF2_RNG_POS_X` | `0.0` | LiDAR X 오프셋 |
| `EKF2_RNG_POS_Y` | `0.0` | LiDAR Y 오프셋 |
| `EKF2_RNG_POS_Z` | `-0.040` | LiDAR Z 오프셋 |
| `EKF2_RNG_NOISE` | `0.02` | LiDAR 노이즈 (m, 데이터시트 2% 반영) |
| `EKF2_OF_QMIN` | `100` | 최소 품질 임계값 (0~255) |
| `EKF2_OF_NEIG_NR` | `3` | 노이즈 게이트 이웃 수 |

**센서 설치 방향 검증 (QGC MAVLink Inspector):**
```
1. QGC → Analyze Tools → MAVLink Inspector
2. OPTICAL_FLOW_RAD 메시지 확인
   ├─ integrated_x, integrated_y: 전진 시 +Y, 우진 시 -X
   ├─ quality: 200+ 정상, <100 시 조도/바닥 텍스처 확인
3. DISTANCE_SENSOR 메시지 확인
   ├─ current_distance: 실제 높이와 일치 (±0.02m)
   ├─ type: 1 (Laser), orientation: 25 (Down)
```

### 3.2.4 EKF2 고급 튜닝 (실내 Position Mode 안정화)

```yaml
# 핵심 EKF2 파라미터 (파라미터 파일로 저장/로드 권장)
EKF2_OF_CTRL: 1              # Optical Flow 활성화
EKF2_RNG_CTRL: 2             # Range height fusion (연속)
EKF2_HGT_REF: 2              # 고도 기준 = Range sensor
EKF2_GPS_CTRL: 0             # 실내: GPS 비활성화
EKF2_MAG_TYPE: 5             # None (자기장 간섭 시) 또는 1 (Auto)
EKF2_AID_MASK: 200           # Bit 3(OF)+6(EV yaw)+7(RNG) = 8+64+128
EKF2_EV_CTRL: 0              # External Vision 미사용 시 0
EKF2_FUSE_BETA: 1            # 합성 측면미끄럼각 융합
EKF2_DRAG_CTRL: 3            # 드래그 모델 활성화
EKF2_DRAG_NOISE: 0.5
EKF2_GND_EFF_DZ: 0.1         # 그라운드 이펙트 데드존
EKF2_GND_EFF_MAX_HGT: 0.5    # 최대 영향 고도
EKF2_GND_MAX_HGT: 1.0

# EKF2_AID_MASK 비트맵:
# Bit 0 (1):   GPS horizontal position
# Bit 1 (2):   GPS velocity
# Bit 2 (4):   GPS height
# Bit 3 (8):   Optical Flow
# Bit 4 (16):  External Vision position
# Bit 5 (32):  External Vision velocity
# Bit 6 (64):  External Vision yaw
# Bit 7 (128): Range finder height
# Bit 8 (256): Synthetic sideslip
# Bit 9 (512): Fixed-wing airspeed
# Bit 10 (1024): Multi-rotor drag
# Bit 11 (2048): External Vision heading
#
# 실내 Position Mode: Bit 3+6+7 = 8+64+128 = 200
# 외부 비전(VIO) 사용 시: +16+32 = 248
```

### 3.2.5 컴패니언 컴퓨터 연결 (uXRCE-DDS, TELEM2)

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `UXRCE_DDS_CFG` | `TELEM 2` | Jetson 연결 포트 |
| `UXRCE_DDS_AG_IP` | `2130706433` | Agent IP (INT32: 127.0.0.1) |
| `UXRCE_DDS_PRT` | `8888` | UDP 포트 |
| `UXRCE_DDS_NS` | `""` | 네임스페이스 (멀티 기체 시 설정) |
| `SER_TEL2_BAUD` | `921600` | uXRCE-DDS 시리얼 보드레이트 |

> **IP INT32 변환**: `127.0.0.1` → `0x7F000001` = `2130706433`
> Jetson에서 Agent가 다른 IP면 해당 IP로 변환 (예: `192.168.1.100` → `3232235876`)

### 3.2.6 Flight Behavior / Safety

```
Vehicle Setup → Flight Behavior
├── MP_THR_HOVER: 0.5 (호버링 쓰로틀, 실측 후 보정)
├── MPC_XY_VEL_MAX: 3.0 (최대 수평 속도, m/s)
├── MPC_Z_VEL_MAX_UP: 2.0 (상승 속도)
├── MPC_Z_VEL_MAX_DN: 1.5 (하강 속도, 그라운드 이펙트 고려)
├── MPC_TILTMAX_AIR: 35.0 (최대 틸트 각도, deg)
├── MPC_THR_MIN: 0.12 (최소 쓰로틀, 모터 정지 방지)
├── MPC_THR_MAX: 0.95 (최대 쓰로틀)
```

```
Vehicle Setup → Safety
├── Battery: 셀 수 4, 빈전압 3.3V, 가득 4.2V
├── Battery Capacity: 4000 mAh
├── Failsafe: RC Loss → Return (GPS 시) / Land (실내)
├── Geofence: 실내 비행 반경 10m, 고도 2.5m 제한
├── Land Detector: 다중콥터 기본값 유지
```

### 3.2.7 RC 채널 매핑 및 Flight Modes

```
Vehicle Setup → Radio → 캘리브레이션 완료 후
Vehicle Setup → Flight Modes
├── Channel 5 (Mode Switch):
│   ├── Pos 0: Position (실내 호버링 기본)
│   ├── Pos 1: Altitude
│   ├── Pos 2: Stabilized
│   ├── Pos 3: Offboard (자율비행)
│   └── Pos 4: Return (RTL)
├── Channel 6: Arm/Disarm
├── Channel 7: **Kill Switch (즉시 모터 정지)**
└── Channel 8: RTL (Return to Launch)
```

---

## 3.3 MAVLink Router 검증

```bash
# Jetson에서
journalctl -fu mavlink-router

# 기대 로그:
# [INFO] Endpoint 'fc' connected on /dev/ttyTHS1
# [INFO] Endpoint 'qgc' listening on UDP 14550
# [INFO] MAVLink message routing active
```

**QGC 연결 확인:**
- QGC 우측 상단 링크 상태: "Connected"
- 하트비트 수신: 1Hz
- MAVLink Inspector: HEARTBEAT, SYS_STATUS 등 수신 확인

---

## 3.4 uXRCE-DDS Agent 검증

```bash
# Jetson에서
journalctl -fu uxrce-dds-agent

# 기대 로그:
# [INFO] Starting Micro XRCE-DDS Agent...
# [INFO] Listening on UDP port 8888
# [INFO] Client connected: 192.168.10.1:8888 (또는 FC에서 연결)
# [INFO] Participant created: px4_participant
```

**ROS 2 토픽 확인 (별도 터미널):**
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash

# 토픽 리스트
ros2 topic list | grep fmu

# 기대 토픽 (출력 예시):
# /fmu/out/vehicle_status
# /fmu/out/vehicle_local_position
# /fmu/out/sensor_combined
# /fmu/out/timesync_status
# /fmu/out/vehicle_odometry
# /fmu/in/vehicle_command
# /fmu/in/offboard_control_mode
# /fmu/in/trajectory_setpoint

# 실시간 데이터 확인
ros2 topic echo /fmu/out/vehicle_local_position
ros2 topic echo /fmu/out/vehicle_status
```

---

## 3.5 ROS 2 통신 검증 (Offboard 테스트)

```bash
# 간단한 리스너 노드로 데이터 수신 확인
ros2 run px4_ros_com sensor_combined_listener

# 또는 Python 테스트 스크립트
python3 << 'EOF'
import rclpy
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

rclpy.init()
node = rclpy.create_node('test_subscriber')

qos = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    depth=1
)

def status_cb(msg):
    print(f"NAV_STATE: {msg.nav_state}, ARMING: {msg.arming_state}")

def pos_cb(msg):
    print(f"POS: x={msg.x:.2f}, y={msg.y:.2f}, z={msg.z:.2f}")

node.create_subscription(VehicleStatus, '/fmu/out/vehicle_status', status_cb, qos)
node.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position', pos_cb, qos)

try:
    rclpy.spin(node)
except KeyboardInterrupt:
    pass
finally:
    rclpy.shutdown()
EOF
```

---

## 3.6 네트워크/방화벽/보안 설정

### 3.6.1 Jetson 방화벽 (UFW)

```bash
# 필수 포트만 개방
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 로컬 네트워크(192.168.10.0/24)에서만 허용
sudo ufw allow from 192.168.10.0/24 to any port 22      # SSH
sudo ufw allow from 192.168.10.0/24 to any port 5760    # MAVLink Router TCP
sudo ufw allow from 192.168.10.0/24 to any port 14550   # QGC UDP
sudo ufw allow from 192.168.10.0/24 to any port 14540   # MAVROS UDP
sudo ufw allow from 192.168.10.0/24 to any port 8888    # uXRCE-DDS UDP
sudo ufw allow from 192.168.10.0/24 to any port 7400    # Fast-DDS
sudo ufw allow from 192.168.10.0/24 to any port 5901    # VNC (선택)

sudo ufw enable
sudo ufw status verbose
```

### 3.6.2 서비스 워치독 (자동 복구)

```bash
# /etc/systemd/system/px4-watchdog.service
sudo tee /etc/systemd/system/px4-watchdog.service > /dev/null << 'EOF'
[Unit]
Description=PX4 Services Watchdog
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for svc in mavlink-router uxrce-dds-agent; do systemctl is-active --quiet $svc || (logger "PX4 WATCHDOG: $svc down, restarting" && systemctl restart $svc); done'

[Install]
WantedBy=multi-user.target
EOF

# /etc/systemd/system/px4-watchdog.timer
sudo tee /etc/systemd/system/px4-watchdog.timer > /dev/null << 'EOF'
[Unit]
Description=Run PX4 watchdog every minute
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now px4-watchdog.timer
```

---

## 3.7 설정 백업 및 버전 관리

```bash
# 1. QGC에서 파라미터 파일 저장
# Vehicle Setup → Parameters → Tools → Save to File
# 파일명: q250-v3-opti_px4-v1.15_YYYYMMDD.params

# 2. Git으로 버전 관리
mkdir -p ~/px4_params
cp ~/Downloads/q250-v3-opti_*.params ~/px4_params/
cd ~/px4_params
git init
git add .
git commit -m "Initial Q250-V3 Opti params for PX4 v1.15"
git tag v1.0-baseline

# 3. 주요 설정 파일 백업
mkdir -p ~/config_backup
cp /etc/mavlink-router/main.conf ~/config_backup/
cp /etc/systemd/system/uxrce-dds-agent.service ~/config_backup/
cp ~/fastdds_config.xml ~/config_backup/
cp ~/.bashrc ~/config_backup/
```

---

# 4. 운용 융합 (Operation Integration)

## 4.1 운용 모델 요약

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Q250-V3 Opti 운용 아키텍처                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 콘솔 노트북 (Operator Station)                                       │   │
│  │ ├── QGroundControl (MAVLink over UDP:14550)                         │   │
│  │ ├── SSH / VS Code Remote → Jetson Nano                              │   │
│  │ ├── ROS 2 개발 터미널 (원격 실행)                                    │   │
│  │ └── 비상시: RC 조종기 (Direct to FC)                                │   │
│  └──────────────────────────────────┬──────────────────────────────────┘   │
│                                     │ WiFi (192.168.10.x)                  │
│                                     ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Q250-V3 Opti 기체                                                    │   │
│  │ ┌─────────────────┐    UART (TELEM2)    ┌───────────────────────┐  │   │
│  │ │ Pixhawk 6C mini │ ◄─────────────────► │ Jetson Nano (Onboard) │  │   │
│  │ │ - PX4 v1.15     │   921600 baud       │ - Ubuntu 20.04        │  │   │
│  │ │ - uXRCE-DDS Clt │   MAVLink + DDS     │ - uXRCE-DDS Agent     │  │   │
│  │ │ - EKF2 (OF+LiDAR)│                     │   (UDP 8888)          │  │   │
│  │ │ - DShot300 ESC  │                     │ - MAVLink Router      │  │   │
│  │ └────────┬────────┘                     │ - ROS 2 Humble        │  │   │
│  │          │                              └───────────┬────────────┘  │   │
│  │          │                                          │               │   │
│  │          │ SBUS/CRSF/PPM (RC 수신기)                │               │   │
│  │          ▼                                          ▼               │   │
│  │ ┌─────────────────┐                        ┌─────────────────┐     │   │
│  │ │ RC 조종기       │                        │ WiFi AP / Router│     │   │
│  │ │ (비상 수동조종)  │                        │ (노트북 ↔ Jetson)│     │   │
│  │ └─────────────────┘                        └─────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**핵심 원칙**: Jetson은 비행 제어 컴퓨터, 노트북은 운영자 스테이션, RC는 최후의 안전장치. 세 계층이 독립적으로 동작하며, 상위 계층 장애 시 하위 계층이 즉시 인계받는 **계층적 안전 구조** 유지.

---

## 4.2 비행 전 체크리스트 (Pre-Flight)

### 4.2.1 하드웨어 점검

```markdown
# Q250-V3 Opti Pre-Flight Checklist v1.0
Date: ________  Pilot: ________  Location: ________
Battery ID: ________  Voltage: _____V  Capacity: _____mAh

## 기체 하드웨어
[ ] 프레임 크랙/나사 풀림 점검 (M3 나사 토크 0.5Nm)
[ ] 프로펠러 손상/균형/장착 방향 (CW/CCW 확인)
[ ] 모터 베어링/축 흔들림, 자유 회전 확인
[ ] Optical-Flow 렌즈 청결, LiDAR 창 청결
[ ] Jetson Nano 고정, 케이블 연결 상태 (TELEM2, 전원)
[ ] 안테나(GPS/Telemetry) 장착 및 방향
[ ] 배터리 홀더 잠금, 스트랩 고정

## 전원 시스템
[ ] 메인 배터리 완충 (셀 밸런스 ±0.01V)
[ ] Jetson 전원 UBEC 출력 5V/12V 확인
[ ] 전원 케이블 커넥터 확실한 체결

## 소프트웨어/통신 (원격 접속으로 수행)
[ ] SSH 접속: `ssh jetson@192.168.10.1` → TMUX 세션 진입
[ ] 서비스 상태 확인:
    [ ] `journalctl -fu uxrce-dds-agent` → "Client connected" 확인
    [ ] `journalctl -fu mavlink-router` → "Endpoint fc connected" 확인
[ ] ROS 2 토픽 확인:
    [ ] `ros2 topic list | grep fmu` → 최소 10개 토픽 수신
    [ ] `ros2 topic echo /fmu/out/vehicle_status --once` → NAV_STATE 확인
[ ] QGC 연결 확인:
    [ ] 링크 상태: Connected
    [ ] 센서: Optical-Flow quality > 150, LiDAR 거리 정상
[ ] RC 링크 확인:
    [ ] QGC Radio 탭: RSSI > -80dBm
    [ ] 채널 모니터: 스틱/스위치 정상 반응
[ ] 배터리 전압/전류 확인:
    [ ] QGC: 4S 16.0V 근처, 셀 밸런스 ±0.01V

## 비행 계획
[ ] 비행 모드 시퀀스: Stabilized → Position → Offboard
[ ] 비상 착륙 위치 및 Disarm 절차 숙지
[ ] 지오펜스/고도 제한 설정 확인 (반경 10m, 고도 2.5m)
[ ] 환경: 실내 조도 > 100 Lux, 바닥 텍스처 있음, 기류 없음

Sign-off: ________________
```

### 4.2.2 자동화된 비행 전 체크 스크립트

```bash
# ~/scripts/preflight/check_all.sh
#!/bin/bash
set -e

echo "=========================================="
echo "Q250-V3 Opti Pre-Flight Check"
echo "=========================================="

# 색상 정의
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m'

check_service() {
    local svc=$1
    if systemctl is-active --quiet $svc; then
        echo -e "${GREEN}✓${NC} $svc: Active"
        return 0
    else
        echo -e "${RED}✗${NC} $svc: Inactive"
        return 1
    fi
}

check_topic() {
    local topic=$1
    if timeout 5 ros2 topic echo $topic --once >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} ROS 2 Topic: $topic"
        return 0
    else
        echo -e "${RED}✗${NC} ROS 2 Topic: $topic (timeout)"
        return 1
    fi
}

# 1. 서비스 체크
echo -e "
${YELLOW}[1/5] System Services${NC}"
check_service mavlink-router
check_service uxrce-dds-agent

# 2. ROS 2 토픽 체크
echo -e "
${YELLOW}[2/5] ROS 2 Topics (source setup first)${NC}"
source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash

check_topic /fmu/out/vehicle_status
check_topic /fmu/out/vehicle_local_position
check_topic /fmu/out/sensor_combined
check_topic /fmu/out/timesync_status

# 3. MAVLink Router 체크
echo -e "
${YELLOW}[3/5] MAVLink Router${NC}"
if timeout 5 mavlink-routerd -c /etc/mavlink-router/main.conf -d 2>&1 | grep -q "connected"; then
    echo -e "${GREEN}✓${NC} MAVLink Router: FC connected"
else
    echo -e "${RED}✗${NC} MAVLink Router: FC not connected"
fi

# 4. 네트워크 체크
echo -e "
${YELLOW}[4/5] Network${NC}"
if ping -c 3 -W 1 192.168.10.2 >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Network: Laptop reachable"
else
    echo -e "${YELLOW}⚠${NC} Network: Laptop not reachable (check WiFi)"
fi

# 5. 디스크/메모리 체크
echo -e "
${YELLOW}[5/5] Resources${NC}"
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    echo -e "${GREEN}✓${NC} Disk: ${DISK_USAGE}% used"
else
    echo -e "${YELLOW}⚠${NC} Disk: ${DISK_USAGE}% used (cleanup recommended)"
fi

MEM_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
if [ $MEM_USAGE -lt 85 ]; then
    echo -e "${GREEN}✓${NC} Memory: ${MEM_USAGE}% used"
else
    echo -e "${YELLOW}⚠${NC} Memory: ${MEM_USAGE}% used"
fi

echo -e "
=========================================="
echo "Pre-flight check completed"
echo "=========================================="
```

---

## 4.3 비행 모드별 운용 절차

### 4.3.1 1단계: 기본 조종 & 실내 호버링 (Position Mode)

**목표**: 기체 기본 동작 검증, Optical-Flow/LiDAR 안정성 확인

```
절차:
1. 안전 구역 확보 (3m×3m×2.5m 이상, 조도 >100 Lux, 바닥 텍스처)
2. QGC 연결 확인 → Position Mode 선택
3. RC Arm 스위치 ON
4. 쓰로틀 중립 → 서서히 올림 (20% → 40% → 60%)
5. 이륙 후 호버링 안정성 관찰 (30초)
   - XY 드리프트 < 0.1m
   - 고도 유지 ±0.05m
   - 요 드리프트 < 5°/min
6. 스틱 입력 테스트 (Roll/Pitch/Yaw 소폭)
7. 쓰로틀 중립 → 서서히 내려 착륙
8. Disarm

합격 기준:
- Position Mode 진입 성공 (EKF2 수렴)
- 호버링 30초 무드리프트 유지
- 모든 방향 스틱 입력 정상 반응
- 착륙 후 Disarm 정상
```

### 4.3.2 2단계: GPS 없는 실내 자율비행 (Position → Offboard)

**목표**: Offboard 모드 전환, 기본 궤적 추종 검증

```
절차:
1. Position Mode에서 안정적 호버링 확인 (드리프트 < 0.1m, 30초)
2. 노트북 터미널에서 Offboard 노드 실행:
   ros2 run offboard_control offboard_control
3. RC Flight Mode 스위치 → Offboard (또는 QGC 툴바)
4. 기체 반응 확인:
   - OffboardControlMode 수신 시작 (2Hz+)
   - VehicleCommand ARM 수신
   - TrajectorySetpoint 이륙 명령 수행 (1.5m 고도)
5. 호버링 유지 확인 (Offboard 상태에서 30초)
6. 간단 웨이포인트 테스트 (사각형 1m×1m)
7. Land 명령 → 착륙 → Disarm

핵심 규칙 (Offboard):
- OffboardControlMode 2Hz 이상 지속 발행 필수 (Position=true)
- TrajectorySetpoint 동시 발행
- VehicleCommand로 ARM + OFFBOARD 모드 전환
- 하트비트 타임아웃(0.5초) 내 연속 발행 필수
- 이상 시 즉시 RC로 Position Mode 복귀 또는 Kill Switch
```

### 4.3.3 3단계: ROS 2 / MAVROS 자율비행 개발

**목표**: 커스텀 자율비행 알고리즘 검증

```
개발 워크플로우:
1. 시뮬레이션에서 검증 (Gazebo SITL)
   cd ~/PX4-Autopilot
   PX4_UXRCE_DDS_NS=uav_1 make px4_sitl gz_x500
   # 별도 터미널: MicroXRCEAgent udp4 -p 8888

2. ROS 2 노드 시뮬에서 테스트
   ros2 run my_pkg offboard_control

3. 실기체 플래싱 및 실내 테스트
   make px4_fmu-v6c_default upload
   # 실내에서 안전 테스트 (프롭 가드, 테더링 권장)

MAVROS 병행 사용 시:
- 설치: sudo apt install ros-humble-mavros ros-humble-mavros-extras
- 실행: ros2 launch mavros px4.launch fcu_url:="serial:///dev/ttyTHS1:921600"
- 좌표계 주의: MAVROS=ENU, PX4 uXRCE-DDS=FRD (NED)
- 변환: px4_ros_com/frame_transforms.h 사용 권장
```

### 4.3.4 4단계: 군집비행 및 자율비행 연구

**목표**: 다중 기체 협업, 형성 비행, 상대 위치 측정

```
확장 아키텍처:
# 각 기체별 고유 네임스페이스
# 기체 1: UXRCE_DDS_NS=uav_1, Jetson IP=192.168.10.10
# 기체 2: UXRCE_DDS_NS=uav_2, Jetson IP=192.168.10.11
# 기체 3: UXRCE_DDS_NS=uav_3, Jetson IP=192.168.10.12

# Fast-DDS 초기 피어 리스트에 서로 IP 등록
# Ground Station: 단일 QGC + MAVLink Router 멀티 엔드포인트

상대 위치 측정 (필수):
| 방식 | 하드웨어 | 정밀도 | 범위 | 추천도 |
|------|----------|--------|------|--------|
| UWB | DW1000/DW3000 | ~10-30cm | 50m+ | ⭐⭐⭐ |
| VIO + AprilTag | T265/D435i | ~5-20cm | 10m | ⭐⭐ |
| LiDAR SLAM | 2D/3D LiDAR | ~5cm | 20m | ⭐ |

형성 제어 패턴:
- Leader-Follower: 리더 궤적 + 고정 오프셋
- Virtual Structure: 가상 강체 유지
- Consensus-based: 분산 합의 알고리즘
```

---

## 4.4 비행 중 모니터링

### 4.4.1 듀얼 모니터 구성 권장

| 화면 | 내용 | 도구 |
|------|------|------|
| **메인: QGC** | 실시간 위치, 고도, 배터리, 모드, 링크 품질 | QGroundControl |
| **서브: 터미널 (SSH)** | ROS 2 토픽 실시간 모니터링 | `ros2 topic echo /fmu/out/vehicle_local_position` |
| **비상: RC 조종기** | 손 닿는 곳에 상시 비치, Kill Switch 가드 해제 | 물리 조종기 |

### 4.4.2 실시간 모니터링 명령어

```bash
# TMUX 창별 모니터링 (Jetson SSH 접속 시)
# 창 1: DDS Agent 로그
journalctl -fu uxrce-dds-agent

# 창 2: MAVLink Router 로그
journalctl -fu mavlink-router

# 창 3: ROS 2 토픽 (위치/속도/상태)
watch -n 0.5 'ros2 topic echo /fmu/out/vehicle_local_position --once 2>/dev/null | grep -E "x:|y:|z:|vx:|vy:|vz:"'

# 창 4: 배터리/시스템 상태
watch -n 1 'ros2 topic echo /fmu/out/battery_status --once 2>/dev/null | grep -E "voltage:|current:|remaining:"'
```

---

## 4.5 비상 절차 (Emergency Procedures)

| 상황 | 감지 방법 | 즉시 조치 | 우선순위 |
|------|-----------|-----------|----------|
| **통신 두절 (QGC/SSH 끊김)** | QGC "No Vehicle", SSH 타임아웃 | **RC로 Position Mode 전환 → 수동 착륙** | 1순위 |
| **자율비행 폭주 (Offboard 이상)** | 기체 급가속, 궤적 이탈, 고도 폭주 | **Kill Switch (채널 7) → 즉시 모터 정지** | 1순위 |
| **배터리 부족 (Critical)** | QGC 경고, 전압 < 14.0V (4S) | RTL 스위치 (채널 8) → 자동 복귀/착륙 | 1순위 |
| **Optical-Flow 품질 저하** | quality < 100, 드리프트 증가 | Position → Altitude → Stabilized 단계적 수동 | 2순위 |
| **LiDAR 고도 데이터 상실** | DISTANCE_SENSOR NaN, 고도 폭주 | Land Mode 전환, 수동 고도 조절 착륙 | 2순위 |
| **자기장 간섭 (Yaw 에러)** | "Magnetic Interference" 경고 | EKF2_MAG_TYPE=5 (나침반 OFF), Optical-Flow만으로 Yaw 추정 | 2순위 |
| **모터/ESC 이상** | 진동, 이상음, 모터 정지 | 즉시 Kill Switch → Disarm → 점검 | 1순위 |

> **핵심**: RC는 FC에 직접 연결되어 WiFi/Jetson/QGC 장애와 무관하게 작동
> **Kill Switch는 반드시 별도 스위치에 할당, 가드 권장**

---

## 4.6 비행 후 처리 (Post-Flight)

### 4.6.1 로그 다운로드 및 아카이브

```bash
# ~/scripts/postflight/archive_logs.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
LOG_DIR=~/flight_logs/$DATE
mkdir -p $LOG_DIR

echo "Archiving flight logs to $LOG_DIR"

# 1. QGC에서 다운로드한 .ulg 복사 (수동 다운로드 후)
# cp ~/Downloads/*.ulg $LOG_DIR/

# 2. Jetson 서비스 로그 아카이브
journalctl -u uxrce-dds-agent --since "2 hours ago" > $LOG_DIR/dds_agent.log
journalctl -u mavlink-router --since "2 hours ago" > $LOG_DIR/mavlink_router.log

# 3. 파라미터 스냅샷
cp ~/px4_params/q250-v3-opti_latest.params $LOG_DIR/params_backup.params

# 4. 비행 메모 템플릿 생성
cat > $LOG_DIR/flight_note.md << EOF
# Flight Log: $DATE
- Duration: ___ min
- Mode: Position / Offboard / Mission
- Purpose: ________________
- Weather: Indoor, Lux: ___, Temp: ___°C
- Battery: ID ___, Start: ___V, End: ___V
- Issues: ________________
- Observations: ________________
- Next Action: ________________
EOF

# 5. Git 커밋 (선택)
cd ~/flight_logs
git add $DATE
git commit -m "Flight log $DATE" 2>/dev/null || true

echo "Archive complete: $LOG_DIR"
```

### 4.6.2 비행 로그 분석 (필수)

```bash
# pyulog 설치
pip install pyulog numpy pandas matplotlib

# .ulg → CSV 변환
ulog2csv flight_log.ulg -o ./logs/

# 핵심 분석 스크립트
python3 << 'EOF'
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 데이터 로드
pos = pd.read_csv('./logs/vehicle_local_position_0.csv')
est = pd.read_csv('./logs/estimator_status_0.csv')
act = pd.read_csv('./logs/actuator_outputs_0.csv')
bat = pd.read_csv('./logs/battery_status_0.csv')

# 1. 위치 정확도 (호버링 구간)
print("=== Position Stability ===")
print(f"X Std: {pos['x'].std():.4f} m")
print(f"Y Std: {pos['y'].std():.4f} m")
print(f"Z Std: {pos['z'].std():.4f} m")

# 2. EKF2 혁신(Innovation) 분석
of_innov_cols = [c for c in est.columns if 'flow' in c.lower()]
rng_innov_cols = [c for c in est.columns if 'hagl' in c.lower() or 'rng' in c.lower()]

if of_innov_cols:
    of_innov = est[of_innov_cols].values
    print(f"
=== Optical Flow Innovation RMS: {np.sqrt(np.mean(of_innov**2)):.4f} ===")

if rng_innov_cols:
    rng_innov = est[rng_innov_cols].values
    print(f"=== Range Finder Innovation RMS: {np.sqrt(np.mean(rng_innov**2)):.4f} ===")

# 3. 모터 출력 균형 (호버링 구간)
motors = act[['output[0]', 'output[1]', 'output[2]', 'output[3]']].values
hover_motors = motors[motors.mean(axis=1) > 0.2]  # 아밍 후만
print(f"
=== Motor Balance (hover avg) ===")
print(f"Motor 1: {hover_motors[:,0].mean():.3f}")
print(f"Motor 2: {hover_motors[:,1].mean():.3f}")
print(f"Motor 3: {hover_motors[:,2].mean():.3f}")
print(f"Motor 4: {hover_motors[:,3].mean():.3f}")
print(f"Max Deviation: {np.max(np.std(hover_motors, axis=1)):.3f}")

# 4. 배터리 소비
if 'voltage' in bat.columns and 'current' in bat.columns:
    print(f"
=== Battery ===")
    print(f"Start Voltage: {bat['voltage'].iloc[0]:.2f} V")
    print(f"End Voltage: {bat['voltage'].iloc[-1]:.2f} V")
    print(f"Avg Current: {bat['current'].mean():.2f} A")
    print(f"Capacity Used: {(bat['current'].mean() * (bat['timestamp'].iloc[-1] - bat['timestamp'].iloc[0]) / 1e6 / 3600):.3f} Ah")

print("
=== Pass/Fail Criteria ===")
print(f"XY Position Std < 0.05m: {'PASS' if max(pos['x'].std(), pos['y'].std()) < 0.05 else 'FAIL'}")
print(f"Z Position Std < 0.03m: {'PASS' if pos['z'].std() < 0.03 else 'FAIL'}")
print(f"Motor Balance < 5%: {'PASS' if np.max(np.std(hover_motors, axis=1)) < 0.05 else 'FAIL'}")
EOF
```

**합격 기준:**
- XY Position Std < 0.05m (호버링 중)
- Z Position Std < 0.03m
- Flow Innovation RMS < 0.1 rad/s
- Range Innovation RMS < 0.05m
- 모터 출력 편차 < 5%

---

## 4.7 정기 점검 주기

| 주기 | 항목 | 상세 |
|------|------|------|
| **매 비행 전** | 육안 점검, 배터리, RC 링크, 센서 데이터 | 체크리스트 필수 수행 |
| **주 1회 (활발 운용 시)** | 모터 베어링, ESC 온도, 프레임 나사 토크 | 나사 토크 렌치 사용 (M3: 0.5Nm) |
| **월 1회** | 펌웨어 업데이트 확인, 파라미터 백업, SD 카드 포맷 | PX4 v1.15 안정 버전 유지 |
| **분기 1회** | Optical-Flow/LiDAR 캘리브레이션, 나침반 재캘 | 실외에서 수행 |
| **배터리 50사이클마다** | 용량 테스트, 내부 저항 측정 | IR < 10mΩ/셀 유지 |

---

# 5. 부록: 참조 자료 및 링크

## 5.1 쿼드 드론연구소 공식 문서

| 문서 | 링크 |
|------|------|
| Q250-V3 Opti 메인 가이드 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/q250-v3-opti |
| Optical-Flow & LiDAR 설정 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/q250-v3-opti/optical-flow-and-lidar |
| Actuators / DShot 설정 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/actuators |
| 컴패니언 컴퓨터 연결 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/undefined-3 |
| 전원 설정 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/undefined-1 |
| Flight Behavior 설정 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/flight-behavior |
| VIO non-GPS 비행 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/1-vio-non-gps |
| 자율 회피 주행 | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/2 |
| Fake GPS (가상 GPS) | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/3-fake_gps-gps |
| MAVROS Teleop (키보드 조종) | https://quad-drone-lab.gitbook.io/quad-drone-start/q250/4-mavros_teleop |
| 전체 문서 인덱스 (llms.txt) | https://quad-drone-lab.gitbook.io/quad-drone-start/llms.txt |

## 5.2 PX4 공식 문서 (v1.15 기준)

| 문서 | 링크 |
|------|------|
| Multicopter Configuration | https://docs.px4.io/main/en/config_mc |
| Actuator Configuration | https://docs.px4.io/main/en/config/actuators |
| Airframe Selection | https://docs.px4.io/main/en/config/airframe |
| Optical Flow Setup | https://docs.px4.io/main/en/sensor/optical_flow |
| EKF2 Tuning Guide | https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf |
| Parameter Reference | https://docs.px4.io/main/en/advanced_config/parameter_reference |
| ROS 2 User Guide (uXRCE-DDS) | https://docs.px4.io/main/en/ros2/user_guide |
| uXRCE-DDS Middleware | https://docs.px4.io/main/en/middleware/uxrce_dds |
| Companion Computer | https://docs.px4.io/main/en/companion_computer/index |
| Offboard Control Example | https://docs.px4.io/main/en/ros2/offboard_control |

## 5.3 ROS 2 / MAVROS / 개발 도구

| 문서 | 링크 |
|------|------|
| MAVROS ROS 2 | https://github.com/mavlink/mavros/blob/ros2/mavros/README.md |
| MAVROS Documentation | https://mavros.readthedocs.io/en/latest/ |
| px4_msgs (ROS 2 인터페이스) | https://github.com/PX4/px4_msgs |
| px4_ros_com (메시지 번역/프레임 변환) | https://github.com/PX4/px4_ros_com |
| Fast-DDS Discovery 설정 | https://fast-dds.docs.eprosima.com/en/latest/fastdds/discovery/discovery.html |
| Micro-XRCE-DDS-Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent |

## 5.4 하드웨어 레퍼런스

| 문서 | 링크 |
|------|------|
| Pixhawk 6C mini | https://docs.px4.io/main/en/flight_controller/pixhawk6c_mini.html |
| Holybro PM07 Power Module | https://holybro.com/products/pm07 |
| Jetson Nano Developer Kit | https://developer.nvidia.com/embedded/jetson-nano-developer-kit |
| BLHeli_32 ESC 설정 | https://github.com/bitdump/BLHeli |

---

## 5.5 파라미터 한글 요약표 (인쇄용)

```
┌─────────────────────┬─────────┬──────────────────────────────────────────────┐
│ 파라미터            │ 설정값  │ 비고                                           │
├─────────────────────┼─────────┼──────────────────────────────────────────────┤
│ CA_AIRFRAME         │ 0       │ Quadrotor X                                   │
│ CA_ROTOR_COUNT      │ 4       │                                               │
│ EKF2_OF_CTRL        │ 1       │ Optical Flow 활성화                           │
│ EKF2_RNG_CTRL       │ 2       │ Range height fusion (연속)                    │
│ EKF2_HGT_REF        │ 2       │ 고도 기준 = Range sensor                      │
│ SENS_FLOW_ROT       │ 0       │ 센서 회전 없음                                │
│ EKF2_OF_POS_X/Y/Z   │ 0/0/-0.035 │ Flow 센터 오프셋 (COG 기준)               │
│ EKF2_RNG_POS_X/Y/Z  │ 0/0/-0.040 │ LiDAR 센터 오프셋                         │
│ EKF2_RNG_NOISE      │ 0.02    │ LiDAR 노이즈 (m)                             │
│ EKF2_MAG_TYPE       │ 5       │ None (실내 자기장 간섭 시)                    │
│ UXRCE_DDS_CFG       │ TELEM2  │ Jetson 연결 포트                              │
│ UXRCE_DDS_AG_IP     │ 2130706433 │ Agent IP (127.0.0.1 INT32)               │
│ UXRCE_DDS_PRT       │ 8888    │ UDP 포트                                      │
│ SER_TEL2_BAUD       │ 921600  │ uXRCE-DDS 시리얼 보드레이트                   │
│ SER_TEL4_BAUD       │ 115200  │ Optical-Flow UART 보드레이트                  │
│ MAV_1_CONFIG        │ TELEM4  │ Optical-Flow MAVLink 포트                     │
│ MAV_1_MODE          │ 1       │ Normal                                        │
│ BAT_V_DIV           │ 54.5    │ 4S 전압 분배비 (PM07)                         │
│ BAT_A_PER_V         │ 18.0    │ 전류 센서 스케일 (PM07)                       │
│ MPC_XY_VEL_MAX      │ 3.0     │ 최대 수평 속도 (m/s)                          │
│ MPC_Z_VEL_MAX_UP    │ 2.0     │ 최대 상승 속도                                │
│ MPC_Z_VEL_MAX_DN    │ 1.5     │ 최대 하강 속도                                │
│ MPC_TILTMAX_AIR     │ 35.0    │ 최대 틸트 각도 (deg)                          │
└─────────────────────┴─────────┴──────────────────────────────────────────────┘
```

---

---

*문서 끝 (초안 v0.1)*

> **다음 단계**: 이 초안을 바탕으로 `docs/images/`에 실제 사진 배치, `docs/diagrams/`에 Mermaid/PlantUML 다이어그램 렌더링 후 `manual-final.docx`로 변환하여 완성본 제작 예정.


---

# 5. 실버스(StreamCaster) 데이터링크 통합 (Silvus Data Link Integration)

## 5.1 보유 자산 현황

| 장비 | 수량 | 모델 추정 | 용도 |
|------|------|-----------|------|
| **GDT (Ground Data Terminal)** | 1대 | StreamCaster GDT | 지상국 게이트웨이 |
| **Air Unit** | 4대 | StreamCaster Air (Lite/Mini) | 기체 4대 장착 (예비 1대 포함) |
| **안테나/케이블/마운트** | 1식 | MIMO 패치/옴니 안테나 | 다양체 구성 |

**자산 가치**: 약 $12,700 (~1,700만원 중고가 기준)

---

## 5.2 실버스 MN-MIMO 웨이브폼 핵심 특성

| 특성 | 상세 |
|------|------|
| **웨이브폼** | **MN-MIMO** (Mobile Networked MIMO) — 독자 TDMA/OFDMA 기반 매쉬 |
| **주파수** | 1.3~2.5 GHz / 4.4~5.8 GHz (모델依存, 튜닝 가능) |
| **RF 파워** | **2~5 W** (일반 WiFi 0.1W의 20~50배) |
| **매쉬** | **완전 분산 매쉬** — 라우팅/릴레이/자가회복 자동, 홉 제한 없음 |
| **처리량** | **단일 홉 100+ Mbps**, 멀티홉 선형 확장 |
| **지연** | **< 10 ms (1홉)**, 홉당 +2~5 ms |
| **거리** | **LOS 20~50 km**, NLOS/도심 2~5 km (5W 기준) |
| **암호화** | **AES-256**, TRANSEC (주파수 호핑/확산) |
| **인터페이스** | **이더넷 (RJ45/밀착형) + 시리얼 (MAVLink)** |
| **전원** | 12~30 VDC (기체: 5~10W, GDT: 10~20W) |

---

## 5.3 시스템 아키텍처 (실버스 통합)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PC USB 테더링 + 실버스 MN-MIMO 메쉬                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   [GCS PC: RTX 4090 + QGC + ROS2]                                           │
│        │ 이더넷 (RJ45) / USB 3.0                                             │
│        ▼                                                                     │
│   ┌─────────────────────┐                                                   │
│   │  Silvus GDT         │  ← 게이트웨이 (고정, 고이득 안테나, 외부 전원)      │
│   │  (Gateway Node)     │                                                   │
│   └──────────┬──────────┘                                                   │
│              │ RF MN-MIMO Mesh (자가 치유, TDMA, 주파수 호핑)                │
│       ┌──────┼──────┐                                                        │
│       ▼      ▼      ▼                                                        │
│   ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                                          │
│   │기체1│ │기체2│ │기체3│ │기체4│  ← Air Unit (경량, MIMO, AES-256)         │
│   │Q250 │ │Q250 │ │Q250 │ │Q250 │                                          │
│   └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘                                          │
│      │       │       │       │                                              │
│      ▼       ▼       ▼       ▼                                              │
│   [Jetson] [Jetson] [Jetson] [Jetson]                                       │
│    │        │        │        │                                              │
│    ▼        ▼        ▼        ▼                                              │
│   [FC]     [FC]     [FC]     [FC]                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5.4 하드웨어 통합 상세

### 5.4.1 그라운드 스테이션 (PC + GDT)

**연결 방식 (우선순위):**
1. **이더넷 (RJ45) 직결** — 가장 안정적, 저지연, 관리 UI/스트리밍/MAVLink 모두 가능
2. **USB 3.0** — 이더넷 포트 없는 노트북용 (내장 어댑터 모델)
3. **시리얼 (DB9/RJ45 콘솔)** — 펌웨어 복구/초기 설정용

**PC 네트워크 설정:**
```bash
# 고정 IP 할당
sudo nmcli con add type ethernet ifname eth0 con-name silvus-gdt     ip4 192.168.10.1/24 gw4 192.168.10.1

# GDT 웹 관리 접속: http://192.168.10.254 (기본 ID/PW: admin/admin)
```

### 5.4.2 기체 측 통합 (Q250-V3 Opti × 4 + Jetson + Air Unit)

```
┌────────────────────────────────────────────────────────────┐
│  Q250-V3 Opti 기체 (×4)                                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [Silvus Air Unit]                                         │
│   ├─ RF 포트: SMA × 2 (MIMO) → 옴니/패치 안테나 대각선 장착 │
│   ├─ 전원: UBEC 12V/5A → Air Unit DC-IN (12~30V)           │
│   ├─ 이더넷 (RJ45/밀착) → [Jetson eth0] ← **권장**         │
│   └─ 시리얼 (UART/MAVLink) → [FC TELEM2/3] ← 백업/보조     │
│                                                            │
│  [Jetson Orin Nano]                                        │
│   ├─ eth0 ← Air Unit (고정 IP: 192.168.10.11~14)           │
│   ├─ MAVLink Router: FC(UART) + Air Unit(Eth) 라우팅       │
│   ├─ uXRCE-DDS Agent: FC → ROS2                            │
│   └─ ROS2 DDS: 기체간 P2P (Fast-DDS Discovery via Mesh)    │
│                                                            │
│  [Pixhawk 6C mini]                                         │
│   ├─ TELEM2 → Jetson UART (921600, MAVLink + uXRCE-DDS)    │
│   └─ TELEM3 → Air Unit 시리얼 (MAVLink 백업, 57600)        │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Air Unit 장착 핵심 체크리스트:**
- [ ] **MIMO 안테나 2개 필수** — λ/2(~6cm@2.4GHz) 이상 이격, 대각선 모서리
- [ ] **별도 UBEC 12V/5A** — Jetson 5V 라인과 분리
- [ ] **이더넷 직결 (Jetson eth0)** — MAVLink/ROS2/DDS/비디오 통합
- [ ] **시리얼 백업 (FC TELEM3)** — 이더넷 단절 시 페일세이프
- [ ] **진동 방지 마운트** — 고무 마운트, 금속 차폐 최소화

---

## 5.5 네트워크 토폴로지 & IP 계획

실버스 매쉬는 **레이어 2 투명 브리지**처럼 동작합니다.

```
서브넷: 192.168.10.0/24 (관리용 VLAN 별도: 10.10.10.0/24)

역할                    IP              비고
──────────────────────────────────────────────────────
PC (GCS)                192.168.10.1    고정
GDT (게이트웨이)         192.168.10.254  실버스 기본 GW
기체 1 (Jetson)         192.168.10.11   고정 / DHCP 예약
기체 2 (Jetson)         192.168.10.12   고정 / DHCP 예약
기체 3 (Jetson)         192.168.10.13   고정 / DHCP 예약
기체 4 (Jetson)         192.168.10.14   고정 / DHCP 예약
예비 Air Unit           192.168.10.15   벤치 테스트용
──────────────────────────────────────────────────────
실버스 관리 VLAN        10.10.10.0/24   웹 UI/펌웨어/모니터링 전용 (태그드)
```

> **DHCP 서버**: GDT 내부 기본값 사용 또는 **PC에서 끄고 고정 IP 사용** (매쉬 안정성↑)

---

## 5.6 소프트웨어 스택 통합

### 5.6.1 MAVLink Router 설정 (`/etc/mavlink-router/main.conf`)

```ini
[General]
TcpServerPort=5760
ReportStats=true

[UartEndpoint fc]
Device=/dev/ttyTHS1
Baud=921600

[UdpEndpoint gcs]             # GDT → PC (실버스 매쉬 경유)
Mode=Normal
Address=192.168.10.1          # PC IP
Port=14550

[UdpEndpoint swarm]           # 기체간 P2P (실버스 매쉬 = 브로드캐스트 가능)
Mode=Normal
Address=192.168.10.255
Port=14560

[TcpEndpoint silvus_mavlink]  # Air Unit 이더넷 MAVLink 직접 수신 (옵션)
Mode=Normal
Address=192.168.10.11         # 자기 IP
Port=14551
```

### 5.6.2 Fast-DDS 설정 (`fastdds_config.xml`)

```xml
<profiles>
    <participant profile_name="swarm_participant" is_default_profile="true">
        <rtps>
            <builtin>
                <discovery_config>
                    <discoveryProtocol>SIMPLE</discoveryProtocol>
                    <leaseDuration><sec>30</sec></leaseDuration>
                    <metatrafficUnicastLocatorList>
                        <locator>
                            <udpv4>
                                <address>192.168.10.11</address>  <!-- 자기 IP -->
                                <port>7400</port>
                            </udpv4>
                        </locator>
                    </metatrafficUnicastLocatorList>
                    <initialPeersList>
                        <locator><udpv4><address>192.168.10.1</address><port>7400</port></udpv4></locator>   <!-- PC -->
                        <locator><udpv4><address>192.168.10.12</address><port>7400</port></udpv4></locator>  <!-- 기체2 -->
                        <locator><udpv4><address>192.168.10.13</address><port>7400</port></udpv4></locator>  <!-- 기체3 -->
                        <locator><udpv4><address>192.168.10.14</address><port>7400</port></udpv4></locator>  <!-- 기체4 -->
                    </initialPeersList>
                </discovery_config>
            </builtin>
            <port><portBase>7400</portBase></port>
        </rtps>
    </participant>
</profiles>
```

### 5.6.3 실버스 링크 모니터링 ROS2 노드 (`silvus_monitor.py`)

```python
# scripts/silvus_monitor.py
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Int32
import requests

class SilvusMonitor(Node):
    def __init__(self, air_unit_ip="192.168.10.11"):
        super().__init__('silvus_monitor')
        self.air_unit_ip = air_unit_ip
        self.pub_rssi = self.create_publisher(Float32, '/silvus/rssi', 10)
        self.pub_snr = self.create_publisher(Float32, '/silvus/snr', 10)
        self.pub_throughput = self.create_publisher(Float32, '/silvus/throughput_mbps', 10)
        self.pub_hops = self.create_publisher(Int32, '/silvus/hops', 10)
        self.pub_neighbors = self.create_publisher(Int32, '/silvus/neighbor_count', 10)
        self.timer = self.create_timer(1.0, self.poll)
    
    def poll(self):
        try:
            r = requests.get(f'http://{self.air_unit_ip}/api/v1/link/status', timeout=0.5)
            data = r.json()
            self.pub_rssi.publish(Float32(data=data.get('rssi', -99)))
            self.pub_snr.publish(Float32(data=data.get('snr', 0)))
            self.pub_throughput.publish(Float32(data=data.get('throughput_mbps', 0)))
            self.pub_hops.publish(Int32(data=data.get('hops', 0)))
            self.pub_neighbors.publish(Int32(data=data.get('neighbor_count', 0)))
        except Exception as e:
            self.get_logger().warn(f'Silvus poll failed: {e}')

def main():
    rclpy.init()
    node = SilvusMonitor()
    rclpy.spin(node)
```

---

## 5.7 실버스 매쉬 운용 포인트 (일반 무선과 다름)

| 특징 | 운용 팁 |
|------|---------|
| **자가 치유 매쉬** | 기체 이탈/진입 자동 감지, 라우팅 테이블 자동 갱신 — **수동 라우팅 불필요** |
| **주파수 호핑/확산** | 간섭/재밍 내성 강함 — **채널 고정 불필요**, 대역폭/파워만 설정 |
| **TDMA 슬롯 자동 할당** | 기체 수/트래픽에 따라 슬롯 동적 할당 — **고정 슬롯 설정 금지** |
| **멀티홉 릴레이** | 중간 기체가 릴레이 자동 수행 — **중계 기체 배터리 더 씀** (전력 10~20%↑) |
| **LPI/LPD** | 저피탐/저피격 — **스펙트럼 분석기에 안 잡힘**, 보안 비행 시 유리 |
| **AES-256 + TRANSEC** | 키 관리만 잘하면 도청/스푸핑 불가능 — **키 로테이션 주기 설정** |

---

## 5.8 초기 설정 체크리스트 (수령 후 첫 주)

### 1. 펌웨어 통일 (최중요)
```bash
# 모든 장비(GDT + Air 4대) **동일 펌웨어 버전**으로 업데이트
# 웹 UI → System → Firmware Update → .bin 파일 업로드
# 버전 불일치 시 매쉬 형성 안 됨 / 불안정
```

### 2. 주파수/대역폭/파워/암호화 설정
| 설정 | 추천 값 |
|------|---------|
| **주파수 밴드** | 국내 전파법 허용 대역 확인 후 선택 (2.4GHz/5.8GHz 중 택1) |
| **채널 폭** | **20 MHz** (안정성) 또는 **40 MHz** (처리량↑, 간섭↑) |
| **TX 파워** | **최대(5W)** — 기체 발열/배터리 확인 후 필요시 2~3W로 낮춤 |
| **모드** | **Mesh (MANET)** — 고정 |
| **암호화 키** | **AES-256 키 동일하게** (32바이트 Hex) — 모든 장비 동일 입력 |

### 3. 안테나 다양체 확인
```bash
# 웹 UI → Radio → Status → Antenna Diversity → "Enabled" 확인
# RSSI 차이 < 3dB 면 양호
```

### 4. 매쉬 형성 테스트
```bash
# 1) GDT 단독 부팅 → 웹 UI Mesh Topology → "Gateway" 표시 확인
# 2) Air Unit 1대 부팅 → Topology에 "Node 1" 나타나는지, RSSI/SNR 확인
# 3) 2대, 3대, 4대 순차 추가 → 각 홉 수(Hops=1) 확인
# 4) 기체 이동하며 링크 유지/재형성 확인 (홉 수 변화, 지연 측정)
```

### 5. MAVLink/ROS2 트래픽 테스트
```bash
# PC에서
ping -i 0.01 -c 1000 192.168.10.11  # 지연/지터/패킷로스
# 목표: 평균 < 10ms, 지터 < 2ms, 손실 < 0.01%
```

---

## 5.9 성능 기대치 (실버스 StreamCaster 실측 기반)

| 지표 | 기대치 | 비고 |
|------|--------|------|
| **단일 홉 처리량** | **80~120 Mbps** (UDP) | 40MHz 채널, 5W, LOS |
| **멀티홉 (2홉) 처리량** | **50~80 Mbps** | 릴레이 오버헤드 ~30% |
| **지연 (1홉)** | **3~8 ms** (RTT) | 제어 루프 100Hz 여유 |
| **지연 (2홉)** | **8~15 ms** | 여전히 제어 가능 |
| **최대 홉 수** | **5~8 홉** | 실버스 MANET 설계 한계 |
| **링크 재형성 시간** | **< 500 ms** | TDMA 슬롯 재할당 시간 |
| **비디오 스트림** | **1080p60 H.264 (8~15 Mbps) × 2~3채널** | 동시 전송 가능 |
| **제어 패킷 우선순위** | **DSCP 46 (EF) 자동 매핑** | 실버스 QoS 엔진 내장 |

---

## 5.10 실버스만 있는 함정 (꼭 확인)

| 함정 | 증상 | 해결 |
|------|------|------|
| **펌웨어 버전 불일치** | 매쉬 안 맺힘, 랜덤 디스커넥트 | **전 장비 동일 버전 강제** |
| **국내 전파법 위반** | 5.8GHz 5W 출력 불법 (실내/옥외 제한) | **전파법 제23조/제24조 확인 → 2.4GHz 1W 이하 또는 면허 취득** |
| **안테나 미스매치** | MIMO 게인 안 나옴, 다양체 효과 없음 | **동일 이득/편파 안테나 2개 필수, λ/2 이격** |
| **발열/전압강하** | Air Unit 과열 셧다운, Jetson 리부트 | **UBEC 12V/5A 별도, 히트싱크/쿨링팬 장착** |
| **관리 VLAN 태그 누락** | 웹 UI 접속 안 됨, 펌웨어 업데이트 실패 | **스위치/PC VLAN 태깅(10.10.10.x) 설정** |
| **키 관리 소홀** | 키 유출 시 전체 매쉬 도청 가능 | **키 분기별 로테이션, 오프라인 저장** |

---

## 5.11 다음 주 액션 플랜

1.  **[ ] 펌웨어 통일** — 최신 안정 버전으로 5대 모두 업데이트
2.  **[ ] 주파수/파워/암호화 키 설정** — 국내 전파법 준수 채널/출력 확인
3.  **[ ] 벤치 매쉬 형성** — 5대 책상 위 연결, 웹 UI 토폴로지/링크 품질 확인
4.  **[ ] 기체 1대 통합** — Air Unit + Jetson + FC 배선, 이더넷/시리얼 동시 테스트
5.  **[ ] MAVLink/ROS2 트래픽 검증** — ping, QGC, ROS2 토픽 지연/손실 측정
6.  **[ ] 실내 호버링 + 매쉬 유지 테스트** — 기체 1대 비행하며 링크 품질 로깅
7.  **[ ] 2~4대 순차 확장** — 매쉬 형성/릴레이/페일세이브 검증

---

*이 섹션은 실버스 StreamCaster 장비 보유 상황에 맞춰 작성되었습니다.*
