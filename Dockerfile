# Q250-V3-Opti Development Environment
# Target: WSL2 Ubuntu 22.04, RTX 5070 8GB, CUDA 12.1, ROS 2 Humble
# Build on host, run on target PC

FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# =============================================================================
# 빌드 인자
# =============================================================================
ARG ROS_DISTRO=humble
ARG USERNAME=developer
ARG USER_UID=1000
ARG USER_GID=1000
ARG TZ=Asia/Seoul

# =============================================================================
# 환경 변수
# =============================================================================
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=${TZ} \
    ROS_DISTRO=${ROS_DISTRO} \
    ROS_ROOT=/opt/ros/${ROS_DISTRO} \
    ROS_VERSION=2 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# =============================================================================
# 기본 패키지 설치
# =============================================================================
RUN ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone

RUN apt-get update && apt-get install -y --no-install-recommends \
    # 기본 도구
    curl wget git vim tmux htop tree jq unzip \
    # 빌드 도구
    build-essential cmake ninja-build pkg-config \
    # Python
    python3 python3-pip python3-venv python3-dev \
    # 네트워크/시스템
    iproute2 net-tools iputils-ping \
    # ROS 2 의존성
    lsb-release gnupg2 software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# ROS 2 Humble 설치
# =============================================================================
RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
    | tee /etc/apt/sources.list.d/ros2.list > /dev/null

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-ros-base \
    ros-${ROS_DISTRO}-mavros \
    ros-${ROS_DISTRO}-mavros-msgs \
    ros-${ROS_DISTRO}-mavros-extras \
    ros-${ROS_DISTRO}-tf-transformations \
    ros-${ROS_DISTRO}-rviz2 \
    python3-colcon-common-extensions \
    python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

# rosdep 초기화
RUN rosdep init || true && rosdep update

# =============================================================================
# MAVSDK 설치 (Python)
# =============================================================================
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    && pip3 install --no-cache-dir mavsdk==1.0.0

# =============================================================================
# ML/오디오 패키지 (CUDA 12.1 호환)
# =============================================================================
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 \
    && pip3 install --no-cache-dir \
    faster-whisper \
    ctranslate2 \
    onnx onnxruntime-gpu onnxsim \
    librosa soundfile \
    scikit-learn scipy numpy pandas \
    opencv-python-headless \
    tensorboard \
    pydantic pyyaml tqdm

# =============================================================================
# 오디오 시스템 (PortAudio for sounddevice)
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev libasound2-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir sounddevice

# =============================================================================
# 사용자 생성 (호스트 UID/GID 매핑)
# =============================================================================
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# =============================================================================
# 작업 디렉토리 및 권한
# =============================================================================
WORKDIR /workspace
RUN chown -R ${USERNAME}:${USERNAME} /workspace

# =============================================================================
# 엔트리포인트 스크립트
# =============================================================================
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# =============================================================================
# ROS 2 환경 설정 (사용자 bash에 자동 소싱)
# =============================================================================
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> /home/${USERNAME}/.bashrc \
    && echo "source /workspace/install/setup.bash 2>/dev/null || true" >> /home/${USERNAME}/.bashrc \
    && echo "export PYTHONPATH=/workspace:\$PYTHONPATH" >> /home/${USERNAME}/.bashrc \
    && echo "export MAVLINK_DIALECT=voice_control" >> /home/${USERNAME}/.bashrc

# =============================================================================
# 헬스체크
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')" || exit 1

# =============================================================================
# 기본 사용자 및 진입점
# =============================================================================
USER ${USERNAME}
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["bash"]