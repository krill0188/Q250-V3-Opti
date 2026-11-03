#!/bin/bash
# apply_configs.sh - 모든 설정 파일 적용
# 실행: ./apply_configs.sh

set -e

echo "=========================================="
echo "Applying All Configurations for Q250-V3 Opti"
echo "=========================================="

# MAVLink Router
echo "[1/5] Applying MAVLink Router config..."
sudo cp ~/Q250-V3-Opti/config/mavlink-router/main.conf /etc/mavlink-router/main.conf
sudo systemctl restart mavlink-router

# uXRCE-DDS Agent
echo "[2/5] Applying uXRCE-DDS Agent config..."
sudo cp ~/Q250-V3-Opti/config/jetson/uxrce-dds-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart uxrce-dds-agent

# Fast-DDS
echo "[3/5] Applying Fast-DDS config..."
cp ~/Q250-V3-Opti/config/jetson/fastdds_config.xml ~/fastdds_config.xml

# 네트워크 (선택적 - 현재 모드에 따라 하나만)
echo "[4/5] Network config available at:"
echo "  AP Mode:    ~/Q250-V3-Opti/config/network/01-netcfg-ap.yaml"
echo "  Router Mode: ~/Q250-V3-Opti/config/network/01-netcfg-router.yaml"
echo "  Apply manually: sudo cp <config> /etc/netplan/01-netcfg.yaml && sudo netplan apply"

# 방화벽
echo "[5/5] Applying firewall..."
sudo ~/Q250-V3-Opti/config/network/setup_ufw.sh

# PX4 파라미터 안내
echo ""
echo "=========================================="
echo "Configuration applied!"
echo "=========================================="
echo ""
echo "Manual steps required:"
echo "1. Apply PX4 parameters via QGC:"
echo "   Vehicle Setup → Parameters → Tools → Load from File"
echo "   Select: ~/Q250-V3-Opti/config/px4/q250-v3-opti_v1.15_baseline.params"
echo ""
echo "2. Verify all services:"
echo "   systemctl status mavlink-router uxrce-dds-agent"
echo ""
echo "3. Run pre-flight check:"
echo "   ~/scripts/preflight/check_all.sh"
