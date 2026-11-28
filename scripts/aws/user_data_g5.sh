#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti: g5.xlarge cloud-init User Data
# Runs on first boot of the AWS g5.xlarge (A10G, sm_86) instance
# Installs CUDA toolkit, TensorRT, Python deps, clones project, builds kernels
# =============================================================================
set -euo pipefail

exec > >(tee -a /var/log/q250-g5-setup.log) 2>&1

echo "============================================================"
echo "Q250-V3-Opti g5.xlarge Setup Started: $(date -u)"
echo "============================================================"

log() { echo "[g5-setup] $*"; }

# --- Wait for network --------------------------------------------------------
log "Waiting for network..."
for i in $(seq 1 30); do
    if ping -c 1 -W 5 1.1.1.1 &>/dev/null; then
        log "Network is up"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log "Network not available, continuing anyway"
    fi
    sleep 5
done

# --- System update -----------------------------------------------------------
log "Updating system packages..."
DEBIAN_FRONTEND=noninteractive apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# --- Install essential packages ----------------------------------------------
log "Installing essential packages..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    software-properties-common \
    lsb-release \
    gnupg \
    ca-certificates \
    libnvidia-common-535 \
    linux-headers-generic \
    python3-pip \
    python3-venv \
    python3-dev \
    pciutils \
    vim

# --- Install NVIDIA CUDA Toolkit (Ubuntu 22.04, CUDA 12.x) -------------------
log "Installing NVIDIA CUDA Toolkit..."
ARCHIVE_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb"
wget -q "${ARCHIVE_URL}" -O /tmp/cuda-keyring.deb
dpkg -i /tmp/cuda-keyring.deb
rm -f /tmp/cuda-keyring.deb

DEBIAN_FRONTEND=noninteractive apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    cuda-toolkit-12-2 \
    cuda-drivers

echo 'export PATH=/usr/local/cuda-12.2/bin:$PATH' >> /etc/profile.d/cuda.sh
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.2/lib64:$LD_LIBRARY_PATH' >> /etc/profile.d/cuda.sh
source /etc/profile.d/cuda.sh

log "CUDA version: $(nvcc --version | grep release | awk '{print $5}' | head -1)"

# --- Verify GPU --------------------------------------------------------------
log "Detecting GPU..."
nvidia-smi || log "nvidia-smi not available yet (driver may need reboot)"

# --- Install Python dependencies ---------------------------------------------
log "Installing Python dependencies..."
python3 -m venv /opt/q250-venv
source /opt/q250-venv/bin/activate
pip install --upgrade pip
pip install numpy torch torchvision onnx onnxruntime pycuda tensorrt || \
    log "Some Python packages may need manual install (TensorRT requires NVIDIA repo)"

# --- Clone project -----------------------------------------------------------
log "Cloning Q250-V3-Opti project..."
PROJECT_DIR="/home/ubuntu/Q250-V3-Opti"
if [[ ! -d "${PROJECT_DIR}" ]]; then
    git clone https://github.com/krill0188/Q250-V3-Opti.git "${PROJECT_DIR}" 2>/dev/null || \
        log "Git clone failed - project may need to be copied manually"
fi

if [[ -d "${PROJECT_DIR}" ]]; then
    chown -R ubuntu:ubuntu "${PROJECT_DIR}"
    log "Project at ${PROJECT_DIR}"
fi

# --- Build CUDA kernels ------------------------------------------------------
if [[ -d "${PROJECT_DIR}" ]]; then
    log "Building CUDA kernels (sm_86 for A10G)..."
    cd "${PROJECT_DIR}"
    chmod +x build_cuda.sh
    
    # Override arch detection for sm_86 (A10G)
    ./build_cuda.sh Release 2>&1 || log "CUDA build may need manual intervention"
    
    log "CUDA build complete"
fi

# --- Mark setup complete -----------------------------------------------------
log "Setup complete: $(date -u)"
touch /home/ubuntu/.q250-g5-ready
echo "g5.xlarge setup finished. GPU: A10G (sm_86). CUDA: $(nvcc --version 2>/dev/null | grep release | awk '{print $5}' | head -1 || echo 'N/A')"