#!/bin/bash
# 05_uxrce_dds_agent.sh - uXRCE-DDS Agent 설치 및 설정
# 실행: ./05_uxrce_dds_agent.sh

set -e

echo "=========================================="
echo "uXRCE-DDS Agent Setup for Q250-V3 Opti"
echo "=========================================="

# ROS 2 워크스페이스 생성
echo "[1/6] Setting up ROS 2 workspace..."
mkdir -p ~/ros2_px4_ws/src
cd ~/ros2_px4_ws/src

# px4_msgs (v1.15 브랜치)
if [ ! -d "px4_msgs" ]; then
    echo "Cloning px4_msgs..."
    git clone -b v1.15 https://github.com/PX4/px4_msgs.git
else
    echo "px4_msgs already exists"
fi

# Micro-XRCE-DDS-Agent
if [ ! -d "Micro-XRCE-DDS-Agent" ]; then
    echo "Cloning Micro-XRCE-DDS-Agent..."
    git clone -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
else
    echo "Micro-XRCE-DDS-Agent already exists"
fi

# px4_ros_com (메시지 번역 노드)
if [ ! -d "px4_ros_com" ]; then
    echo "Cloning px4_ros_com..."
    git clone https://github.com/PX4/px4_ros_com.git
else
    echo "px4_ros_com already exists"
fi

# 빌드
echo "[2/6] Building ROS 2 workspace..."
cd ~/ros2_px4_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release

# 환경 설정
echo "[3/6] Setting up environment..."
if ! grep -q "ros2_px4_ws/install/setup.bash" ~/.bashrc; then
    echo "source ~/ros2_px4_ws/install/setup.bash" >> ~/.bashrc
fi
source ~/ros2_px4_ws/install/setup.bash

# Fast-DDS 설정 복사
echo "[4/6] Configuring Fast-DDS..."
cp ~/Q250-V3-Opti/config/jetson/fastdds_config.xml ~/fastdds_config.xml

# 시스템 서비스 복사 및 등록
echo "[5/6] Installing systemd service..."
sudo cp ~/Q250-V3-Opti/config/jetson/uxrce-dds-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable uxrce-dds-agent
sudo systemctl start uxrce-dds-agent

# 상태 확인
sleep 3
echo "[6/6] Checking service status..."
systemctl status uxrce-dds-agent --no-pager

# ROS 2 토픽 확인
echo ""
echo "Verifying ROS 2 topics..."
source ~/ros2_px4_ws/install/setup.bash
ros2 topic list | grep fmu | head -20

echo ""
echo "=========================================="
echo "uXRCE-DDS Agent setup complete!"
echo "=========================================="
echo ""
echo "Verify:"
echo "  journalctl -fu uxrce-dds-agent"
echo "  ros2 topic echo /fmu/out/vehicle_status --once"
echo ""
echo "Next: Apply PX4 parameters from config/px4/q250-v3-opti_v1.15_baseline.params via QGC"
