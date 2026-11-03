#!/bin/bash
# Jetson 방화벽 설정 (UFW)
# 실행: sudo ./setup_ufw.sh

set -e

echo "Setting up UFW firewall for Q250-V3 Opti..."

# 기본 정책
ufw default deny incoming
ufw default allow outgoing

# 로컬 네트워크에서만 허용 (AP 모드: 192.168.10.0/24, 라우터 모드: 192.168.1.0/24)
# 둘 다 허용하려면 둘 다 추가
ufw allow from 192.168.10.0/24 to any port 22      # SSH
ufw allow from 192.168.10.0/24 to any port 5760    # MAVLink Router TCP
ufw allow from 192.168.10.0/24 to any port 14550   # QGC UDP
ufw allow from 192.168.10.0/24 to any port 14540   # MAVROS UDP
ufw allow from 192.168.10.0/24 to any port 8888    # uXRCE-DDS UDP
ufw allow from 192.168.10.0/24 to any port 7400    # Fast-DDS

ufw allow from 192.168.1.0/24 to any port 22       # SSH (라우터 모드)
ufw allow from 192.168.1.0/24 to any port 5760     # MAVLink Router TCP
ufw allow from 192.168.1.0/24 to any port 14550    # QGC UDP
ufw allow from 192.168.1.0/24 to any port 14540    # MAVROS UDP
ufw allow from 192.168.1.0/24 to any port 8888     # uXRCE-DDS UDP
ufw allow from 192.168.1.0/24 to any port 7400     # Fast-DDS

# VNC (선택)
# ufw allow from 192.168.10.0/24 to any port 5901

ufw enable
ufw status verbose

echo "UFW setup complete."
