#!/bin/bash
# 00_wsl2_dev_pc.sh - WSL2 개발 PC 초기 설정 (Windows 호스트에서 WSL2 내부에서 실행)
# 실행: ./00_wsl2_dev_pc.sh

set -e

echo "=========================================="
echo "WSL2 Development PC Setup for Q250-V3 Opti"
echo "=========================================="

# WSL2 환경 확인
if ! grep -qi microsoft /proc/version; then
    echo "Error: This script must run inside WSL2 Ubuntu 22.04"
    echo "Install: wsl --install -d Ubuntu-22.04 (PowerShell Admin)"
    exit 1
fi

# Ubuntu 버전 확인
UBUNTU_VERSION=$(lsb_release -rs)
if [[ "$UBUNTU_VERSION" != "22.04" ]]; then
    echo "Warning: Ubuntu $UBUNTU_VERSION detected. Recommended: 22.04"
fi

# systemd 활성화 확인 (WSL2 22.04+ 기본)
if [ ! -f /etc/wsl.conf ] || ! grep -q "systemd=true" /etc/wsl.conf; then
    echo "[systemd] Enabling systemd in /etc/wsl.conf"
    echo -e "[boot]\nsystemd=true" | sudo tee /etc/wsl.conf > /dev/null
    echo "Note: Run 'wsl --shutdown' in PowerShell and restart WSL after this script"
fi

# 1. 시스템 업데이트 & 필수 패키지
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    build-essential cmake ninja-build ccache \
    git curl wget vim htop tmux net-tools \
    python3-pip python3-venv python3-dev \
    libssl-dev libudev-dev \
    software-properties-common \
    gnupg2 lsb-release \
    usbutils pciutils

# 2. ROS 2 Humble (데스크톱 - 시뮬레이터용)
echo "[2/8] Installing ROS 2 Humble Desktop..."
sudo apt install -y software-properties-common
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y \
    ros-humble-desktop \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    python3-argcomplete

# ROS 2 환경 설정
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
fi
source /opt/ros/humble/setup.bash

# rosdep 초기화
sudo rosdep init 2>/dev/null || true
rosdep update

# 3. Gazebo Harmonic (Ubuntu 22.04 호환)
echo "[3/8] Installing Gazebo Harmonic..."
sudo apt install -y gz-harmonic

# 4. PX4 빌드 의존성
echo "[4/8] Installing PX4 build dependencies..."
bash -c "$(curl -s https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/Tools/setup/ubuntu.sh)"

# 5. 개발 도구
echo "[5/8] Installing development tools..."
sudo apt install -y \
    code \  # VS Code (또는 수동 설치)
    docker.io \
    docker-compose \
    wireguard \
    wireguard-tools \
    tailscale

# Docker 권한
sudo usermod -aG docker $USER

# 6. USB/IP 설정 안내 (Windows 측에서 실행)
echo "[6/8] USB/IP setup (run on Windows PowerShell Admin):"
cat << 'EOF'
# Windows PowerShell (Admin)에서 실행:
winget install usbipd
usbipd list
# Jetson/실버스/FC 장치 BUSID 확인 후:
usbipd bind --busid <BUSID> --autoattach
# WSL에서 연결:
# usbipd attach --wsl --busid <BUSID>
EOF

# 7. VS Code Extensions (WSL에서 code 명령어로 설치)
echo "[7/8] Installing VS Code extensions..."
if command -v code &> /dev/null; then
    code --install-extension ms-vscode.cpptools
    code --install-extension ms-vscode.cmake-tools
    code --install-extension ms-python.python
    code --install-extension ms-vscode-remote.remote-wsl
    code --install-extension ms-azuretools.vscode-docker
    code --install-extension twxs.cmake
    code --install-extension twxs.cmake-format
    code --install-extension ms-python.black-formatter
    code --install-extension ms-python.isort
    code --install-extension foxundermoon.shell-format
else
    echo "VS Code not installed. Install from: https://code.visualstudio.com/"
    echo "Then run: code --install-extension ms-vscode.cpptools ..."
fi

# 7. Docker 설정
echo "[7/8] Configuring Docker..."
sudo usermod -aG docker $USER
sudo systemctl enable docker

# 8. 개발 환경 설정 파일 복사
echo "[8/8] Setting up development environment configs..."

# bashrc 추가 (중복 방지)
BASHRC_ADDITIONS='
# ROS 2
source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash 2>/dev/null || true

# PX4
export PX4_DIR=~/PX4-Autopilot
export PX4_SIM_MODEL=q250_v3_opti

# Gazebo
export GZ_SIM_RESOURCE_PATH=~/simulation/models:${GZ_SIM_RESOURCE_PATH}

# Fast-DDS (Silvus optimized)
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_config.xml
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# ccache
export CCACHE_DIR=~/.ccache
export CCACHE_MAXSIZE=10G

# 유용한 별칭
alias px4-build="cd ~/PX4-Autopilot && make px4_fmu-v6c_default -j$(nproc)"
alias px4-sitl="cd ~/PX4-Autopilot && make px4_sitl gz_${PX4_SIM_MODEL}"
alias ros2-build="cd ~/ros2_px4_ws && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release"
alias ros2-test="cd ~/ros2_px4_ws && colcon test --event-handlers console_direct+"
alias preflight="~/scripts/preflight/check_all.sh"
alias postflight="~/scripts/postflight/archive_logs.sh"
alias silvus-monitor="python3 ~/scripts/silvus_monitor.py --air-unit-ip 192.168.10.11"
alias ddslog="journalctl -fu uxrce-dds-agent"
alias mavlog="journalctl -fu mavlink-router"
'

# bashrc에 추가 (중복 방지)
for line in $BASHRC_ADDITIONS; do
    if ! grep -qF "$line" ~/.bashrc; then
        echo "$line" >> ~/.bashrc
    fi
done

# 9. Git 설정
git config --global user.name "Q250 Developer" 2>/dev/null || true
git config --global user.email "dev@q250.local" 2>/dev/null || true
git config --global init.defaultBranch main
git config --global pull.rebase false

echo ""
echo "=========================================="
echo "WSL2 Development PC Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart WSL: wsl --shutdown (in PowerShell) then restart"
echo "2. Run: source ~/.bashrc"
echo "3. Clone PX4: git clone --branch v1.15 --recursive https://github.com/PX4/PX4-Autopilot.git ~/PX4-Autopilot"
echo "4. Build PX4: cd ~/PX4-Autopilot && make px4_fmu-v6c_default"
echo "4. Setup ROS2 workspace: mkdir -p ~/ros2_px4_ws/src && cd ~/ros2_px4_ws && colcon build"
echo "5. Setup Jetson SSH: ssh-copy-id jetson@192.168.10.11"
echo ""
echo "USB/IP note: Run 'usbipd bind --busid <BUSID> --autoattach' in Windows PowerShell Admin"
echo "for each device (Jetson, Silvus, FC, Modem)."
