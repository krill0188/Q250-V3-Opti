#!/bin/bash
# monitor.sh - 비행 중 실시간 모니터링
# 실행: ./monitor.sh [position|battery|status|all]

set -e

MODE=${1:-all}

source /opt/ros/humble/setup.bash
source ~/ros2_px4_ws/install/setup.bash

case $MODE in
    position)
        echo "Monitoring Position (Ctrl+C to stop)..."
        watch -n 0.5 'ros2 topic echo /fmu/out/vehicle_local_position --once 2>/dev/null | grep -E "x:|y:|z:|vx:|vy:|vz:"'
        ;;
    battery)
        echo "Monitoring Battery (Ctrl+C to stop)..."
        watch -n 1 'ros2 topic echo /fmu/out/battery_status --once 2>/dev/null | grep -E "voltage:|current:|remaining:"'
        ;;
    status)
        echo "Monitoring Vehicle Status (Ctrl+C to stop)..."
        watch -n 0.5 'ros2 topic echo /fmu/out/vehicle_status --once 2>/dev/null | grep -E "nav_state:|arming_state:|failsafe:"'
        ;;
    all)
        echo "Starting multi-pane monitor (requires tmux)..."
        tmux new-session -d -s monitor
        tmux send-keys -t monitor:0 'watch -n 0.5 "ros2 topic echo /fmu/out/vehicle_local_position --once 2>/dev/null | grep -E \"x:|y:|z:|vx:|vy:|vz:\""' Enter
        tmux split-window -h -t monitor:0
        tmux send-keys -t monitor:0.1 'watch -n 1 "ros2 topic echo /fmu/out/battery_status --once 2>/dev/null | grep -E \"voltage:|current:|remaining:\""' Enter
        tmux split-window -v -t monitor:0.0
        tmux send-keys -t monitor:0.2 'watch -n 0.5 "ros2 topic echo /fmu/out/vehicle_status --once 2>/dev/null | grep -E \"nav_state:|arming_state:|failsafe:\""' Enter
        tmux split-window -v -t monitor:0.1
        tmux send-keys -t monitor:0.3 'journalctl -fu uxrce-dds-agent' Enter
        tmux select-layout -t monitor:0 tiled
        tmux attach -t monitor
        ;;
    *)
        echo "Usage: $0 [position|battery|status|all]"
        exit 1
        ;;
esac
