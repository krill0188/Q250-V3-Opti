#!/bin/bash
# Q250-V3-Opti Docker Entry Point
# ML/Voice 개발 환경 (ROS 2 Humble, CUDA 12.1, MAVSDK, MAVROS2)

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERR]${NC} $*"; }

# =============================================================================
# 환경 확인
# =============================================================================
log_info "Q250-V3-Opti Development Container Starting..."
log_info "ROS Distro: ${ROS_DISTRO:-humble}"
log_info "Workspace: /workspace"

# ROS 2 환경 로드
if [ -f "/opt/ros/${ROS_DISTRO:-humble}/setup.bash" ]; then
    source "/opt/ros/${ROS_DISTRO:-humble}/setup.bash"
    log_ok "ROS 2 ${ROS_DISTRO:-humble} sourced"
else
    log_warn "ROS 2 setup.bash not found"
fi

# 워크스페이스 빌드 결과 로드 (있으면)
if [ -f "/workspace/install/setup.bash" ]; then
    source "/workspace/install/setup.bash"
    log_ok "Workspace install/setup.bash sourced"
fi

# =============================================================================
# GPU 확인
# =============================================================================
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    log_ok "GPU detected: $GPU_INFO"
else
    log_warn "nvidia-smi not available (CPU mode)"
fi

# PyTorch CUDA 확인
python3 -c "
import torch
if torch.cuda.is_available():
    print(f'  PyTorch CUDA: YES | Device: {torch.cuda.get_device_name(0)} | VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB')
else:
    print('  PyTorch CUDA: NO (CPU mode)')
" 2>/dev/null || log_warn "PyTorch not installed or error"

# =============================================================================
# 프로젝트 구조 확인
# =============================================================================
if [ -d "/workspace/q250_msgs" ]; then
    log_ok "q250_msgs found"
fi

if [ -d "/workspace/bridge" ]; then
    log_ok "bridge package found"
fi

if [ -d "/workspace/voice" ]; then
    log_ok "voice package found"
fi

if [ -d "/workspace/src" ]; then
    log_ok "src/ (ROS 2 packages) found"
fi

# =============================================================================
# 환경 변수 설정
# =============================================================================
export MAVLINK_DIALECT=voice_control
export PYTHONPATH=/workspace:${PYTHONPATH}
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# =============================================================================
# 유용한 별칭
# =============================================================================
alias ll='ls -la'
alias la='ls -A'
alias ..='cd ..'
alias ...='cd ../..'

# 빌드/테스트
alias colcon-build='cd /workspace && colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release'
alias colcon-test='cd /workspace && colcon test --event-handlers console_direct+'
alias pytest-voice='cd /workspace && python -m pytest voice/ -v'
alias pytest-bridge='cd /workspace && python -m pytest bridge/ -v'

# 음성 파이프라인 테스트
alias asr-test='cd /workspace && python voice/realtime_asr_pipeline.py'
alias asr-test-small='cd /workspace && python -c "from voice.realtime_asr_pipeline import ASRConfig; print(ASRConfig().model_size)"'

# 브릿지 테스트
alias bridge-test='cd /workspace && python bridge/test_bridge.py'

# MAVLink 메시지 확인
alias mavlink-check='cd /workspace && python -c "import sys; sys.path.insert(0, \"generated/mavlink\"); import python as m; [print(k, v) for k,v in vars(m).items() if \"VOICE\" in k]"'

# 프롬프트 설정
export PS1='\[\033[01;32m\]q250-ml\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

# =============================================================================
# 명령 실행
# =============================================================================
if [ $# -eq 0 ]; then
    log_info "Starting interactive bash..."
    exec bash
else
    log_info "Executing: $*"
    exec "$@"
fi