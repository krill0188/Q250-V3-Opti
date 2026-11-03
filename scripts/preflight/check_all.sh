#!/bin/bash
# check_all.sh - 비행 전 종합 체크
# 실행: ./check_all.sh

set -e

echo "=========================================="
echo "Q250-V3 Opti Pre-Flight Check"
echo "=========================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

FAILED=0

# 1. 서비스 체크
echo -e "\n${YELLOW}[1/5] System Services${NC}"
check_service mavlink-router || FAILED=1
check_service uxrce-dds-agent || FAILED=1

# 2. ROS 2 토픽 체크
echo -e "\n${YELLOW}[2/5] ROS 2 Topics${NC}"
source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash

check_topic /fmu/out/vehicle_status || FAILED=1
check_topic /fmu/out/vehicle_local_position || FAILED=1
check_topic /fmu/out/sensor_combined || FAILED=1
check_topic /fmu/out/timesync_status || FAILED=1

# 3. MAVLink Router 체크
echo -e "\n${YELLOW}[3/5] MAVLink Router${NC}"
if timeout 5 mavlink-routerd -c /etc/mavlink-router/main.conf -d 2>&1 | grep -q "connected"; then
    echo -e "${GREEN}✓${NC} MAVLink Router: FC connected"
else
    echo -e "${RED}✗${NC} MAVLink Router: FC not connected"
    FAILED=1
fi

# 4. 네트워크 체크
echo -e "\n${YELLOW}[4/5] Network${NC}"
if ping -c 3 -W 1 192.168.10.2 >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Network: Laptop reachable"
else
    echo -e "${YELLOW}⚠${NC} Network: Laptop not reachable (check WiFi)"
fi

# 5. 리소스 체크
echo -e "\n${YELLOW}[5/5] Resources${NC}"
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

echo -e "\n=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All critical checks passed!${NC}"
else
    echo -e "${RED}Some checks failed. Review before flight.${NC}"
fi
echo "=========================================="

exit $FAILED
