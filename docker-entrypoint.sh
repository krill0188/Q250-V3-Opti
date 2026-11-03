#!/bin/bash
# docker-entrypoint.sh - 개발 컨테이너 엔트리포인트

set -e

# ROS 2 환경 설정
source /opt/ros/humble/setup.bash

# 워크스페이스 환경 (빌드된 경우)
if [ -f /workspace/ros2_px4_ws/install/setup.bash ]; then
    source /workspace/ros2_px4_ws/install/setup.bash
fi

# PX4 환경 변수
export PX4_DIR=/workspace/PX4-Autopilot
export PX4_SIM_MODEL=q250_v3_opti

# Gazebo 모델 경로
export GZ_SIM_RESOURCE_PATH=/workspace/simulation/models:${GZ_SIM_RESOURCE_PATH}

# Fast-DDS 설정 (Silvus 최적화)
export FASTRTPS_DEFAULT_PROFILES_FILE=/workspace/fastdds_config.xml
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# PX4 환경
export PX4_DIR=/workspace/PX4-Autopilot
export PX4_SIM_MODEL=q250_v3_opti

# Gazebo 모델 경로
export GZ_SIM_RESOURCE_PATH=/workspace/simulation/models:${GZ_SIM_RESOURCE_PATH}

# ccache
export CCACHE_DIR=/workspace/.ccache
export CCACHE_MAXSIZE=10G

# ROS 2 도메인
export ROS_DOMAIN_ID=0

# Fast-DDS
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/workspace/fastdds_config.xml

# ccache
export CCACHE_DIR=/workspace/.ccache
export CCACHE_MAXSIZE=10G

# 유용한 별칭
alias px4-build='cd /workspace/PX4-Autopilot && make px4_fmu-v6c_default -j$(nproc)'
alias px4-sitl='cd /workspace/PX4-Autopilot && make px4_sitl gz_q250_v3_opti'
alias ros2-build='cd /workspace/ros2_px4_ws && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release'
alias ros2-test='cd /workspace/ros2_px4_ws && colcon test --event-handlers console_direct+'

# 프롬프트 설정
export PS1='\[\033[01;32m\]q250-dev\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

# 명령 실행
exec "$@"
