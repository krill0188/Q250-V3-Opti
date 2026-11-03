#!/bin/bash
# 04_mavlink_router.sh - MAVLink Router 설치 및 설정
# 실행: ./04_mavlink_router.sh

set -e

echo "=========================================="
echo "MAVLink Router Setup for Q250-V3 Opti"
echo "=========================================="

# 설치
echo "[1/3] Installing MAVLink Router..."
sudo apt update
sudo apt install -y mavlink-router

# 설정 파일 복사
echo "[2/3] Configuring MAVLink Router..."
sudo cp ~/Q250-V3-Opti/config/mavlink-router/main.conf /etc/mavlink-router/main.conf

# 권한 설정 (시리얼 포트 접근)
sudo usermod -a -G dialout $USER

# 서비스 활성화
echo "[3/3] Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable mavlink-router
sudo systemctl start mavlink-router

# 상태 확인
sleep 2
systemctl status mavlink-router --no-pager

echo ""
echo "=========================================="
echo "MAVLink Router setup complete!"
echo "=========================================="
echo ""
echo "Verify connection:"
echo "  journalctl -fu mavlink-router"
echo "  QGC should show 'Connected' status"
