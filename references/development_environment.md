# 개발 환경 표준 가이드 (WSL2 + Jetson)

## 아키텍처
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  개발 PC (Windows + WSL2 Ubuntu 22.04)                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ VS Code (Remote-WSL / Dev Container)                                 │   │
│  │   ├── ROS 2 Humble + Gazebo Harmonic + PX4 v1.15 빌드               │   │
│  │   ├── Docker 컨테이너 (CI/CD, 재현 가능 환경)                        │   │
│  │   └── Git, CMake, Ninja, ccache                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │ USB/이더넷 (usbipd-win)                              │
│                    ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Jetson Orin Nano (타겟)                                              │   │
│  │   ├── ROS 2 Humble (런타임)                                         │   │
│  │   ├── 실버스 Air Unit (이더넷)                                      │   │
│  │   └── Pixhawk 6C mini (UART)                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 환경 변수 표준화

### ~/.bashrc (WSL2 + Jetson 공통)
```bash
# ROS 2
source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash 2>/dev/null || true

# PX4
export PX4_DIR=~/PX4-Autopilot
export PX4_SIM_MODEL=q250_v3_opti

# Gazebo
export GZ_SIM_RESOURCE_PATH=~/simulation/models:${GZ_SIM_RESOURCE_PATH}

# Fast-DDS (Silvus 최적화)
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_config.xml
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# ccache
export CCACHE_DIR=~/.ccache
export CCACHE_MAXSIZE=10G

# 유용한 별칭
alias px4-build='cd ~/PX4-Autopilot && make px4_fmu-v6c_default -j$(nproc)'
alias px4-sitl='cd ~/PX4-Autopilot && make px4_sitl gz_${PX4_SIM_MODEL}'
alias ros2-build='cd ~/ros2_px4_ws && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release'
alias ros2-test='cd ~/ros2_px4_ws && colcon test --event-handlers console_direct+'
alias preflight='~/scripts/preflight/check_all.sh'
alias postflight='~/scripts/postflight/archive_logs.sh'
alias silvus-monitor='python3 ~/scripts/silvus_monitor.py --air-unit-ip 192.168.10.11'
alias ddslog='journalctl -fu uxrce-dds-agent'
alias mavlog='journalctl -fu mavlink-router'
```

## VS Code 설정 (.vscode/settings.json)
```json
{
  "cmake.configureOnOpen": true,
  "cmake.buildDirectory": "${workspaceFolder}/build",
  "cmake.generator": "Ninja",
  "cmake.configureArgs": [
    "-DCMAKE_BUILD_TYPE=Release",
    "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
    "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache"
  ],
  "cmake.buildBeforeRun": true,
  "terminal.integrated.defaultProfile.linux": "bash",
  "terminal.integrated.profiles.linux": {
    "bash": {
      "path": "bash",
      "args": ["-l"],
      "env": {
        "ROS_DOMAIN_ID": "0"
      }
    }
  },
  "files.associations": {
    "*.sdf": "xml",
    "*.launch.py": "python",
    "*.px4": "text",
    "*.mmd": "markdown"
  },
  "remote.SSH.remotePlatform": {
    "192.168.10.11": "linux",
    "192.168.10.12": "linux",
    "192.168.10.13": "linux",
    "192.168.10.14": "linux"
  }
}
```

## Docker 개발 컨테이너 (재현 가능 환경)

### Dockerfile.dev
```dockerfile
FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build ccache \
    git curl wget vim htop tmux net-tools \
    python3-pip python3-venv python3-dev \
    libssl-dev libudev-dev \
    software-properties-common \
    gnupg2 lsb-release \
    usbutils pciutils \
    gz-harmonic \
    && rm -rf /var/lib/apt/lists/*

RUN bash -c "$(curl -s https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/Tools/setup/ubuntu.sh)"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-px4-msgs \
    ros-humble-mavros \
    ros-humble-mavros-extras \
    ros-humble-tf2-tools \
    ros-humble-rviz2 \
    && rm -rf /var/lib/apt/lists/*

ENV CCACHE_DIR=/workspace/.ccache
ENV CCACHE_MAXSIZE=10G
RUN ccache --max-size=10G

WORKDIR /workspace

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
```

## Git Hooks (코드 품질)

### .git/hooks/pre-commit
```bash
#!/bin/bash
# clang-format, black/isort, cmake-format 자동 검사
```

## 다음 단계 체크리스트
- [ ] WSL2 개발 PC에 `scripts/setup/00_wsl2_dev_pc.sh` 실행
- [ ] VS Code Remote-WSL 연결 테스트
- [ ] Docker 컨테이너 빌드/실행 테스트
- [ ] Jetson과 개발 PC 간 SSH 키 교환
- [ ] `fastdds_config.xml` 동기화 (개발 PC ↔ Jetson)
- [ ] Git pre-commit 훅 설치
- [ ] CI/CD 파이프라인 (GitHub Actions) 구성
