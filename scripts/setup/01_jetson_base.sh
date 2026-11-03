#!/bin/bash
# 01_jetson_base.sh - Jetson Nano 기본 설정
# 실행: ./01_jetson_base.sh

set -e

echo "=========================================="
echo "Jetson Nano Base Setup for Q250-V3 Opti"
echo "=========================================="

# 시스템 업데이트
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
echo "[2/6] Installing essential packages..."
sudo apt install -y \
    git curl wget vim htop tmux net-tools \
    build-essential cmake pkg-config \
    python3-pip python3-venv python3-dev \
    libssl-dev libudev-dev \
    usbutils pciutils lsb-release \
    software-properties-common

# 시리얼 포트 권한
echo "[3/6] Setting up serial port permissions..."
sudo usermod -a -G dialout $USER
echo "Note: Re-login required for dialout group to take effect"

# 스왑 파일 늘리기 (4GB 추가)
echo "[4/6] Increasing swap file to 4GB..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
else
    echo "Swap file already exists"
fi

# Jetson 성능 모드 설정
echo "[5/6] Setting up Jetson performance mode..."
sudo nvpmodel -m 0
sudo jetson_clocks

# 성능 모드 자동 시작 서비스
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

# SSH 보안 강화
echo "[6/6] Hardening SSH..."
sudo sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# 유용한 별칭 추가
cat >> ~/.bashrc << 'EOF'

# Q250-V3 Opti aliases
alias ddslog='journalctl -fu uxrce-dds-agent'
alias mavlog='journalctl -fu mavlink-router'
alias ros2ws='cd ~/ros2_px4_ws && source install/setup.bash'
alias px4log='cd ~/PX4-Autopilot && make px4_sitl gz_x500'
alias preflight='~/scripts/preflight/check_all.sh'
alias postflight='~/scripts/postflight/archive_logs.sh'

# TMUX 자동 연결 (SSH 시)
if [ -z "$TMUX" ] && [ "$SSH_CONNECTION" ]; then
    tmux attach -t jetson 2>/dev/null || tmux new -s jetson
fi
EOF

echo ""
echo "=========================================="
echo "Jetson base setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Re-login (or run: newgrp dialout) for serial permissions"
echo "2. Run: ./02_ros2_humble.sh"
echo "3. Run: ./03_px4_firmware.sh (on development PC)"
echo "4. Run: ./04_mavlink_router.sh"
echo "5. Run: ./05_uxrce_dds_agent.sh"
