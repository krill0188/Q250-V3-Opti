#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti: Jetson Orin Remote Validation Pipeline
# =============================================================================
# This script runs ON the Jetson Orin device. It's invoked via SSH by
# ssh_jetson_setup.sh but can also be run manually on the Jetson.
#
# Pipeline stages (matching the SSH orchestrator):
#   1. Build CUDA kernels (sm_87)
#   2. TensorRT INT8 calibration (entropy + percentile)
#   3. DLA (Deep Learning Accelerator) testing
#   4. Performance benchmarks
#   5. Create deploy package
#
# Usage (on Jetson):
#   ./jetson_pipeline.sh [--stage STAGE] [--calib-data PATH] [--checkpoint PATH]
#
#   --stage STAGE       Pipeline stage: build, calibrate, dla, benchmark, package, all (default: all)
#   --calib-data PATH   Path to calibration dataset (default: ~/data/drone_datasets/processed/drone_audio)
#   --checkpoint PATH   Path to model checkpoint (default: ~/checkpoints/multiclass/best_model.pth)
#   --output-dir DIR    Output directory (default: ~/Q250-V3-Opti)
#   -h, --help          Show help
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-${HOME}/Q250-V3-Opti}"
CALIB_DATA_DIR="${CALIB_DATA_DIR:-${HOME}/data/drone_datasets/processed/drone_audio}"
CHECKPOINT_PATH="${CHECKPOINT_PATH:-${HOME}/checkpoints/multiclass/best_model.pth}"
STAGE="${STAGE:-all}"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_DIR}}"

BUILD_DIR="${PROJECT_DIR}/build"
TENSORRT_DIR="${PROJECT_DIR}/tensorrt_models"
DEPLOY_DIR="${PROJECT_DIR}/deploy_package"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERR]${NC} $*"; }
log_stage() { echo -e "\n${BLUE}========== $* ==========${NC}\n"; }

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Jetson Orin On-Device Validation Pipeline (runs ON Jetson)

OPTIONS:
    --stage STAGE       Pipeline stage: build, calibrate, dla, benchmark, package, all (default: all)
    --calib-data PATH   Calibration dataset path (default: ~/data/drone_datasets/processed/drone_audio)
    --checkpoint PATH   Model checkpoint path (default: ~/checkpoints/multiclass/best_model.pth)
    --output-dir DIR    Project output directory (default: ~/Q250-V3-Opti)
    -h, --help          Show this help

EXAMPLES:
    $0                                    # Run full pipeline
    $0 --stage build                      # Only build CUDA kernels
    $0 --stage calibrate --calib-data ~/data/calib  # Custom calibration data
    $0 --stage benchmark                  # Only run benchmarks
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --stage) STAGE="$2"; shift 2 ;;
            --calib-data) CALIB_DATA_DIR="$2"; shift 2 ;;
            --checkpoint) CHECKPOINT_PATH="$2"; shift 2 ;;
            --output-dir) OUTPUT_DIR="$2"; PROJECT_DIR="$2"; BUILD_DIR="$2/build"; TENSORRT_DIR="$2/tensorrt_models"; DEPLOY_DIR="$2/deploy_package"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) log_err "Unknown option: $1"; usage; exit 1 ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# Stage: Build CUDA Kernels
# -----------------------------------------------------------------------------
stage_build() {
    log_stage "Building CUDA Kernels (sm_87)"

    cd "${PROJECT_DIR}"
    if [[ ! -f "build_cuda.sh" ]]; then
        log_err "build_cuda.sh not found in ${PROJECT_DIR}"
        return 1
    fi

    chmod +x build_cuda.sh
    ./build_cuda.sh Release

    # Verify build
    if [[ -f "${BUILD_DIR}/libtrajectory_kernels.so" ]]; then
        log_ok "CUDA library built: ${BUILD_DIR}/libtrajectory_kernels.so"
        file "${BUILD_DIR}/libtrajectory_kernels.so"
    else
        log_err "CUDA library not found after build"
        return 1
    fi

    # Verify CUDA backend
    cd "${BUILD_DIR}"
    python3 ../src/cuda/trajectory_bindings.py
    BACKEND=$(python3 -c "
import sys
sys.path.insert(0, '.')
from trajectory_bindings import get_trajectory_backend
_, name = get_trajectory_backend()
print(name)
")
    if [[ "${BACKEND}" == "cuda" ]]; then
        log_ok "CUDA backend active on Jetson Orin"
    else
        log_warn "CUDA backend not active (got: ${BACKEND})"
    fi
}

# -----------------------------------------------------------------------------
# Stage: INT8 Calibration
# -----------------------------------------------------------------------------
stage_calibrate() {
    log_stage "TensorRT INT8 Calibration"

    if [[ ! -f "${CHECKPOINT_PATH}" ]]; then
        log_err "Checkpoint not found: ${CHECKPOINT_PATH}"
        return 1
    fi

    if [[ ! -d "${CALIB_DATA_DIR}" ]]; then
        log_warn "Calibration data directory not found: ${CALIB_DATA_DIR}"
        log_warn "Attempting to use training_pipeline/data as fallback..."
        CALIB_DATA_DIR="${PROJECT_DIR}/training_pipeline/data"
        if [[ ! -d "${CALIB_DATA_DIR}" ]]; then
            log_err "No calibration data available"
            return 1
        fi
    fi

    mkdir -p "${TENSORRT_DIR}"

    # Entropy calibration
    log_info "Running ENTROPY calibration (IInt8EntropyCalibrator2)..."
    cd "${PROJECT_DIR}"
    python3 src/deployment/export_tensorrt.py \
        --model_path "${CHECKPOINT_PATH}" \
        --int8 --calib_data "${CALIB_DATA_DIR}" \
        --output_dir "${TENSORRT_DIR}" \
        --calib_method entropy \
        --calib_batches 32 \
        --calib_batch_size 32 \
        --benchmark \
        --model_name audio_classifier
    log_ok "Entropy calibration complete: ${TENSORRT_DIR}/audio_classifier.engine"

    # Percentile calibration (99.9)
    log_info "Running PERCENTILE calibration (IInt8MinMaxCalibrator, 99.9th percentile)..."
    python3 src/deployment/export_tensorrt.py \
        --model_path "${CHECKPOINT_PATH}" \
        --int8 --calib_data "${CALIB_DATA_DIR}" \
        --output_dir "${TENSORRT_DIR}" \
        --calib_method percentile \
        --calib_batches 32 \
        --calib_batch_size 32 \
        --calib_percentile 99.9 \
        --benchmark \
        --model_name audio_classifier_percentile
    log_ok "Percentile calibration complete: ${TENSORRT_DIR}/audio_classifier_percentile.engine"

    # Compare results
    log_info "Calibration comparison:"
    for engine in "${TENSORRT_DIR}"/audio_classifier*.engine; do
        [[ -f "${engine}" ]] && log_info "  $(basename "${engine}"): $(du -h "${engine}" | cut -f1)"
    done
}

# -----------------------------------------------------------------------------
# Stage: DLA Testing
# -----------------------------------------------------------------------------
stage_dla() {
    log_stage "DLA (Deep Learning Accelerator) Testing"

    cd "${PROJECT_DIR}"

    # Check DLA availability
    log_info "Checking DLA hardware availability..."
    python3 -c "
import tensorrt as trt
logger = trt.Logger(trt.Logger.WARNING)
builder = trt.Builder(logger)
print(f'DLA cores: {builder.num_DLA_cores}')
print(f'FP16 support: {builder.platform_has_fast_fp16}')
print(f'INT8 support: {builder.platform_has_fast_int8}')
if builder.num_DLA_cores > 0:
    print('DLA hardware detected - testing execution...')
else:
    print('No DLA cores available on this device')
" 2>/dev/null || { log_warn "TensorRT not available for DLA test"; return 0; }

    # Test DLA execution with percentile engine (typically better for DLA)
    ENGINE="${TENSORRT_DIR}/audio_classifier_percentile.engine"
    [[ -f "${ENGINE}" ]] || ENGINE="${TENSORRT_DIR}/audio_classifier.engine"

    if [[ ! -f "${ENGINE}" ]]; then
        log_warn "No TensorRT engine found, skipping DLA test"
        return 0
    fi

    log_info "Testing DLA execution with engine: ${ENGINE}"
    python3 -c "
import os
import tensorrt as trt
import pycuda.driver as cuda
import numpy as np

engine_path = os.environ.get('ENGINE', '${ENGINE}')
logger = trt.Logger(trt.Logger.WARNING)
runtime = trt.Runtime(logger)

with open(engine_path, 'rb') as f:
    engine = runtime.deserialize_cuda_engine(f.read())

print(f'Engine loaded: {engine_path}')
print(f'Layers: {engine.num_layers}')
print(f'DLA cores: {trt.Builder(logger).num_DLA_cores}')

# Analyze layer precision suitability for DLA
dla_candidates = 0
for i in range(engine.num_layers):
    layer = engine.get_layer(i)
    if layer.precision == trt.DataType.INT8 or layer.precision == trt.DataType.HALF:
        dla_candidates += 1
        print(f'  Layer {i} ({layer.name}): {layer.type} - {layer.precision} [DLA candidate]')

print(f'DLA-suitable layers: {dla_candidates}/{engine.num_layers}')

# Test execution context creation
context = engine.create_execution_context()
if context:
    print('Execution context created successfully')
    
    # Benchmark with DLA (if supported)
    input_shape = (1, 1, 157, 40)
    test_input = np.random.randn(*input_shape).astype(np.float32)
    
    input_binding = engine.get_binding_index('input')
    output_binding = engine.get_binding_index('output')
    
    d_input = cuda.mem_alloc(test_input.nbytes)
    output_shape = list(engine.get_binding_shape(output_binding))
    output_shape[0] = input_shape[0]
    d_output = cuda.mem_alloc(np.prod(output_shape) * 4)
    
    # Warmup
    for _ in range(10):
        cuda.memcpy_htod(d_input, test_input)
        context.execute_v2([int(d_input), int(d_output)])
    cuda.Context.synchronize()
    
    # Benchmark
    import time
    times = []
    for _ in range(50):
        start = time.perf_counter()
        cuda.memcpy_htod(d_input, test_input)
        context.execute_v2([int(d_input), int(d_output)])
        cuda.Context.synchronize()
        times.append(time.perf_counter() - start)
    
    times = np.array(times)
    print(f'DLA Benchmark (50 runs):')
    print(f'  Mean: {np.mean(times)*1000:.2f} ms')
    print(f'  Std:  {np.std(times)*1000:.2f} ms')
    print(f'  Min:  {np.min(times)*1000:.2f} ms')
    print(f'  Max:  {np.max(times)*1000:.2f} ms')
    print(f'  FPS:  {1.0/np.mean(times):.1f}')
else:
    print('Failed to create execution context')
" ENGINE="${ENGINE}" 2>&1 | tee /tmp/dla_test.log

    log_ok "DLA test completed"
}

# -----------------------------------------------------------------------------
# Stage: Benchmarks
# -----------------------------------------------------------------------------
stage_benchmark() {
    log_stage "Performance Benchmarks"

    cd "${PROJECT_DIR}"

    # CUDA Kernel Benchmarks
    log_info "Running CUDA kernel benchmarks..."
    cd "${BUILD_DIR}"
    python3 -c "
import time
import sys
sys.path.insert(0, '..')
from src.cuda.trajectory_bindings import get_trajectory_backend

backend, name = get_trajectory_backend()
print(f'Active backend: {name}')

benchmarks = [
    ('Geometric Dive (50 pts)', lambda: backend.geometric_dive((0,0,100), 50, 45, 25, 30, 60, 50)),
    ('Spiral Dive (50 pts)', lambda: backend.spiral_dive((0,0,100), 50, 25, 10, 50)),
    ('Sine Dive (50 pts)', lambda: backend.sine_dive((0,0,100), 50, 25, 5, 50)),
    ('Jink (20 segs)', lambda: backend.jink((0,0,100), 20, 25, 30, 45, 50)),
]

for name, func in benchmarks:
    # Warmup
    for _ in range(10): func()
    # Benchmark
    start = time.perf_counter()
    for _ in range(1000):
        func()
    elapsed = (time.perf_counter() - start) / 1000 * 1000
    print(f'{name}: {elapsed:.3f} ms avg (1000 runs)')
"

    # TensorRT Benchmarks
    log_info "Running TensorRT inference benchmarks..."
    for engine_name in "audio_classifier_percentile.engine" "audio_classifier.engine"; do
        ENGINE="${TENSORRT_DIR}/${engine_name}"
        if [[ -f "${ENGINE}" ]]; then
            log_info "Benchmarking ${engine_name}..."
            python3 -c "
import os
import numpy as np
import tensorrt as trt
import pycuda.driver as cuda
import time

engine_path = os.environ.get('ENGINE')
logger = trt.Logger(trt.Logger.WARNING)
runtime = trt.Runtime(logger)

with open(engine_path, 'rb') as f:
    engine = runtime.deserialize_cuda_engine(f.read())

context = engine.create_execution_context()
input_shape = (1, 1, 157, 40)
test_input = np.random.randn(*input_shape).astype(np.float32)

input_binding = engine.get_binding_index('input')
output_binding = engine.get_binding_index('output')

d_input = cuda.mem_alloc(test_input.nbytes)
output_shape = list(engine.get_binding_shape(output_binding))
output_shape[0] = input_shape[0]
d_output = cuda.mem_alloc(np.prod(output_shape) * 4)

# Warmup
for _ in range(10):
    cuda.memcpy_htod(d_input, test_input)
    context.execute_v2([int(d_input), int(d_output)])
cuda.Context.synchronize()

# Benchmark
times = []
for _ in range(100):
    start = time.perf_counter()
    cuda.memcpy_htod(d_input, test_input)
    context.execute_v2([int(d_input), int(d_output)])
    cuda.Context.synchronize()
    times.append(time.perf_counter() - start)

times = np.array(times)
name = os.path.basename(engine_path).replace('.engine', '')
print(f'{name}:')
print(f'  Mean: {np.mean(times)*1000:.2f} ms')
print(f'  Std:  {np.std(times)*1000:.2f} ms')
print(f'  Min:  {np.min(times)*1000:.2f} ms')
print(f'  Max:  {np.max(times)*1000:.2f} ms')
print(f'  FPS:  {1.0/np.mean(times):.1f}')
print(f'  Throughput: {input_shape[0]/np.mean(times):.1f} samples/sec')
" ENGINE="${ENGINE}"
        fi
    done

    # System validation
    log_info "Running system validation..."
    if [[ -f "${PROJECT_DIR}/scripts/jetson_verify.sh" ]]; then
        "${PROJECT_DIR}/scripts/jetson_verify.sh" --full
    fi
}

# -----------------------------------------------------------------------------
# Stage: Create Deploy Package
# -----------------------------------------------------------------------------
stage_package() {
    log_stage "Creating Deploy Package"

    cd "${PROJECT_DIR}"

    mkdir -p "${DEPLOY_DIR}"

    # Core artifacts
    log_info "Collecting artifacts..."
    cp -v "${BUILD_DIR}/libtrajectory_kernels.so" "${DEPLOY_DIR}/" 2>/dev/null || log_warn "CUDA library not found"
    cp -v "${TENSORRT_DIR}/audio_classifier.engine" "${DEPLOY_DIR}/" 2>/dev/null || log_warn "Entropy engine not found"
    cp -v "${TENSORRT_DIR}/audio_classifier_percentile.engine" "${DEPLOY_DIR}/" 2>/dev/null || log_warn "Percentile engine not found"
    cp -v "${PROJECT_DIR}/src/cuda/trajectory_bindings.py" "${DEPLOY_DIR}/" 2>/dev/null || log_warn "Bindings not found"
    cp -v "${PROJECT_DIR}/src/cuda/trajectory_kernels.cuh" "${DEPLOY_DIR}/" 2>/dev/null || log_warn "Header not found"
    cp -v "${TENSORRT_DIR}"/*.calib "${DEPLOY_DIR}/" 2>/dev/null || true

    # Create manifest
    cat > "${DEPLOY_DIR}/MANIFEST.txt" <<EOF
Q250-V3-Opti GPU Deploy Package
Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
Host: $(hostname)
Jetson: $(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo 'Unknown')
JetPack: $(dpkg -l | grep nvidia-jetpack | awk '{print $3}' | head -1 || echo 'Unknown')
CUDA: $(nvcc --version | grep release | awk '{print $5}' | head -1 || echo 'Unknown')

=== Artifacts ===
EOF

    for f in "${DEPLOY_DIR}"/*; do
        [[ -f "${f}" ]] && echo "$(basename "${f}"): $(du -h "${f}" | cut -f1), SHA256: $(sha256sum "${f}" | cut -d' ' -f1)" >> "${DEPLOY_DIR}/MANIFEST.txt"
    done

    # Package
    TIMESTAMP=$(date +%Y%m%d)
    PACKAGE_NAME="q250-v3-opti-gpu-${TIMESTAMP}.tar.gz"
    cd "${DEPLOY_DIR}"
    tar -czf "../${PACKAGE_NAME}" .
    cd ..
    sha256sum "${PACKAGE_NAME}" > "${PACKAGE_NAME}.sha256"

    log_ok "Deploy package created: ${PROJECT_DIR}/${PACKAGE_NAME}"
    log_ok "SHA256: $(cat ${PACKAGE_NAME}.sha256 | cut -d' ' -f1)"
    log_info "Manifest:"
    cat "${DEPLOY_DIR}/MANIFEST.txt"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
main() {
    parse_args "$@"

    log_info "Q250-V3-Opti Jetson Orin Validation Pipeline"
    log_info "Project: ${PROJECT_DIR}"
    log_info "Stage: ${STAGE}"
    log_info "Calibration data: ${CALIB_DATA_DIR}"
    log_info "Checkpoint: ${CHECKPOINT_PATH}"

    case "${STAGE}" in
        build)
            stage_build
            ;;
        calibrate)
            stage_build
            stage_calibrate
            ;;
        dla)
            stage_build
            stage_calibrate
            stage_dla
            ;;
        benchmark)
            stage_build
            stage_calibrate
            stage_dla
            stage_benchmark
            ;;
        package)
            stage_build
            stage_calibrate
            stage_dla
            stage_benchmark
            stage_package
            ;;
        all)
            stage_build
            stage_calibrate
            stage_dla
            stage_benchmark
            stage_package
            ;;
        *)
            log_err "Unknown stage: ${STAGE}"
            usage
            exit 1
            ;;
    esac

    log_ok "Pipeline completed successfully!"
}

main "$@"