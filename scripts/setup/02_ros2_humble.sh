#!/bin/bash
# 02_ros2_humble.sh - ROS 2 Humble 설치 (Ubuntu 20.04)
# 실행: ./02_ros2_humble.sh

set -e

echo "=========================================="
echo "ROS 2 Humble Installation for Q250-V3 Opti"
echo "=========================================="

# ROS 2 리포지토리 추가
echo "[1/5] Adding ROS 2 repository..."
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key     -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg]     http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" |     sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update

# ROS 2 Humble 데스크톱 설치
echo "[2/5] Installing ROS 2 Humble Desktop..."
sudo apt install -y \
    ros-humble-desktop \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool

# 환경 설정
echo "[3/5] Setting up ROS 2 environment..."
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
fi
source /opt/ros/humble/setup.bash

# rosdep 초기화
echo "[4/5] Initializing rosdep..."
sudo rosdep init 2>/dev/null || true
rosdep update

# 추가 유용한 패키지
echo "[5/5] Installing additional packages..."
sudo apt install -y \
    ros-humble-rmw-fastrtps-cpp \
    ros-humble-px4-msgs \
    ros-humble-mavros \
    ros-humble-mavros-extras \
    ros-humble-tf2-tools \
    ros-humble-rviz2

# MAVROS geographiclib 데이터셋
echo "Installing MAVROS geographiclib datasets..."
sudo /opt/ros/humble/share/mavros/scripts/install_geographiclib_datasets.sh

echo ""
echo "=========================================="
echo "ROS 2 Humble installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Source environment: source /opt/ros/humble/setup.bash"
echo "2. Run: ./03_px4_firmware.sh (on development PC)"
echo "3. Run: ./04_mavlink_router.sh"
echo "4. Run: ./05_uxrce_dds_agent.sh"
