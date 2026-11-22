#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti CUDA Kernels Build Script
# Jetson Orin (sm_87) 및 데스크톱 GPU 지원
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
SRC_DIR="${SCRIPT_DIR}/src/cuda"

echo "============================================================"
echo "Q250-V3-Opti Trajectory CUDA Kernels Build"
echo "============================================================"

# 빌드 타입 설정
BUILD_TYPE="${1:-Release}"
echo "Build type: ${BUILD_TYPE}"

# CUDA 아키텍처 자동 감지
detect_cuda_arch() {
    if command -v nvidia-smi &> /dev/null; then
        # GPU 이름에서 아키텍처 추정
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        echo "Detected GPU: ${GPU_NAME}"
        
        case "${GPU_NAME}" in
            *Orin*|*T234*|*AGX*Orin*) echo "87" ;;      # Jetson Orin
            *RTX*30*|*A100*|*A30*) echo "80;86" ;;       # Ampere
            *RTX*40*|*H100*) echo "89;90" ;;            # Hopper/Ada
            *T4*|*RTX*20*) echo "75" ;;                  # Turing
            *V100*) echo "70" ;;                         # Volta
            *P100*) echo "60" ;;                         # Pascal
            *) echo "87;86;80;75;70;60" ;;               # 기본값: 광범위 지원
        esac
    else
        echo "87;86;80;75;70;60"
    fi
}

CUDA_ARCH=$(detect_cuda_arch)
echo "Target CUDA architectures: ${CUDA_ARCH}"

# 빌드 디렉토리 생성
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# CMake 구성
echo "Configuring with CMake..."
cmake .. \
    -DCMAKE_BUILD_TYPE="${BUILD_TYPE}" \
    -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH}" \
    -DBUILD_TESTING=ON \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

# 빌드
echo "Building..."
cmake --build . --config "${BUILD_TYPE}" -j$(nproc)

# 빌드 결과 확인
LIB_PATH="${BUILD_DIR}/libtrajectory_kernels.so"
if [[ -f "${LIB_PATH}" ]]; then
    echo ""
    echo "============================================================"
    echo "Build SUCCESS!"
    echo "Library: ${LIB_PATH}"
    echo "Size: $(du -h ${LIB_PATH} | cut -f1)"
    echo ""
    echo "Python bindings installed to: ${BUILD_DIR}/trajectory_bindings.py"
    echo ""
    echo "Test run:"
    echo "  cd ${BUILD_DIR}"
    echo "  python3 ../src/cuda/trajectory_bindings.py"
    echo "============================================================"
else
    echo "ERROR: Library not found at ${LIB_PATH}"
    exit 1
fi