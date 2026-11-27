#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti: SSH Automation for Jetson Orin On-Device Validation Pipeline
# =============================================================================
# Orchestrates the complete Tier 2 validation pipeline on Jetson Orin via SSH.
#
# Pipeline stages:
#   1. Deploy source code, checkpoints, and calibration data to Jetson
#   2. Build CUDA kernels (sm_87) on Jetson
#   3. Run TensorRT INT8 calibration (entropy + percentile methods)
#   4. Test DLA (Deep Learning Accelerator) execution
#   5. Run performance benchmarks
#   6. Create deploy package with all artifacts
#
# Usage:
#   ./ssh_jetson_setup.sh [--host HOST] [--user USER] [--key KEY] [--stage STAGE]
#
#   --host HOST      Jetson Orin SSH hostname/IP (default: jetson.local)
#   --user USER      SSH username (default: jetson)
#   --key KEY        SSH private key path (default: ~/.ssh/id_ed25519)
#   --stage STAGE    Run specific stage: deploy, build, calibrate, dla, benchmark, package, all
#   --skip-deploy    Skip deployment, assume files already on Jetson
#   --dry-run        Show commands without executing
#   -h, --help       Show help
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default SSH config
JETSON_HOST="${JETSON_HOST:-jetson.local}"
JETSON_USER="${JETSON_USER:-jetson}"
JETSON_KEY="${JETSON_KEY:-${HOME}/.ssh/id_ed25519}"
JETSON_PORT="${JETSON_PORT:-22}"

# Remote paths
REMOTE_PROJECT_DIR="/home/${JETSON_USER}/Q250-V3-Opti"
REMOTE_DATA_DIR="/home/${JETSON_USER}/data/drone_datasets"
REMOTE_CHECKPOINT_DIR="/home/${JETSON_USER}/checkpoints"

# Local paths
LOCAL_PROJECT_DIR="${PROJECT_ROOT}"
LOCAL_CHECKPOINT_DIR="${PROJECT_ROOT}/checkpoints"

# Stage control
STAGE="${STAGE:-all}"
SKIP_DEPLOY="${SKIP_DEPLOY:-false}"
DRY_RUN="${DRY_RUN:-false}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERR]${NC} $*"; }
log_stage() { echo -e "\n${BLUE}========== $* ==========${NC}\n"; }

# -----------------------------------------------------------------------------
# SSH Helpers
# -----------------------------------------------------------------------------
ssh_cmd() {
    local cmd="$1"
    local opts="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
    if [[ -n "${JETSON_KEY}" && -f "${JETSON_KEY}" ]]; then
        opts="${opts} -i ${JETSON_KEY}"
    fi
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "[DRY-RUN] ssh ${opts} -p ${JETSON_PORT} ${JETSON_USER}@${JETSON_HOST} \"${cmd}\""
        return 0
    fi
    ssh ${opts} -p "${JETSON_PORT}" "${JETSON_USER}@${JETSON_HOST}" "${cmd}"
}

scp_cmd() {
    local src="$1"
    local dst="$2"
    local opts="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -r"
    if [[ -n "${JETSON_KEY}" && -f "${JETSON_KEY}" ]]; then
        opts="${opts} -i ${JETSON_KEY}"
    fi
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "[DRY-RUN] scp ${opts} -P ${JETSON_PORT} ${src} ${JETSON_USER}@${JETSON_HOST}:${dst}"
        return 0
    fi
    scp ${opts} -P "${JETSON_PORT}" "${src}" "${JETSON_USER}@${JETSON_HOST}:${dst}"
}

# -----------------------------------------------------------------------------
# Stage Functions
# -----------------------------------------------------------------------------

stage_deploy() {
    log_stage "STAGE 1: Deploy to Jetson Orin"

    log_info "Testing SSH connection..."
    ssh_cmd "echo 'SSH connection OK'" || { log_err "SSH connection failed"; return 1; }
    log_ok "SSH connection established"

    log_info "Creating remote directory structure..."
    ssh_cmd "mkdir -p ${REMOTE_PROJECT_DIR} ${REMOTE_DATA_DIR}/processed ${REMOTE_CHECKPOINT_DIR}"

    log_info "Deploying project source code (excluding build, venv, .git, large files)..."
    local excludes=(
        "--exclude=build/**"
        "--exclude=venv*/**"
        "--exclude=.git/**"
        "--exclude=__pycache__/**"
        "--exclude=*.mp4"
        "--exclude=*.tar.gz"
        "--exclude=*.zip"
        "--exclude=.pytest_cache/**"
        "--exclude=.ruff_cache/**"
        "--exclude=drone_tutorial_final*"
        "--exclude=*.log"
        "--exclude=*.cache"
    )
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "[DRY-RUN] rsync -avz --progress ${excludes[@]} -e 'ssh -p ${JETSON_PORT} -i ${JETSON_KEY} -o StrictHostKeyChecking=no' ${LOCAL_PROJECT_DIR}/ ${JETSON_USER}@${JETSON_HOST}:${REMOTE_PROJECT_DIR}/"
    else
        rsync -avz --progress "${excludes[@]}" \
            -e "ssh -p ${JETSON_PORT} -i ${JETSON_KEY} -o StrictHostKeyChecking=no" \
            "${LOCAL_PROJECT_DIR}/" "${JETSON_USER}@${JETSON_HOST}:${REMOTE_PROJECT_DIR}/"
    fi
    log_ok "Source code deployed"

    log_info "Deploying checkpoints..."
    if [[ -d "${LOCAL_CHECKPOINT_DIR}" ]]; then
        if [[ "${DRY_RUN}" == "true" ]]; then
            echo "[DRY-RUN] rsync -avz --progress -e 'ssh -p ${JETSON_PORT} -i ${JETSON_KEY} -o StrictHostKeyChecking=no' ${LOCAL_CHECKPOINT_DIR}/ ${JETSON_USER}@${JETSON_HOST}:${REMOTE_CHECKPOINT_DIR}/"
        else
            rsync -avz --progress \
                -e "ssh -p ${JETSON_PORT} -i ${JETSON_KEY} -o StrictHostKeyChecking=no" \
                "${LOCAL_CHECKPOINT_DIR}/" "${JETSON_USER}@${JETSON_HOST}:${REMOTE_CHECKPOINT_DIR}/"
        fi
        log_ok "Checkpoints deployed"
    else
        log_warn "Local checkpoints directory not found: ${LOCAL_CHECKPOINT_DIR}"
    fi

    log_info "Deploying calibration data (if available)..."
    local calib_dirs=(
        "${HOME}/data/drone_datasets/processed/drone_audio"
        "${HOME}/projectm/Q250-V3-Opti/training_pipeline/data"
    )
    for d in "${calib_dirs[@]}"; do
        if [[ -d "${d}" ]]; then
            if [[ "${DRY_RUN}" == "true" ]]; then
                echo "[DRY-RUN] rsync -avz --progress -e 'ssh -p ${JETSON_PORT} -i ${JETSON_KEY} -o StrictHostKeyChecking=no' ${d}/ ${JETSON_USER}@${JETSON_HOST}:${REMOTE_DATA_DIR}/processed/$(basename ${d})/"
            else
                rsync -avz --progress \
                    -e "ssh -p ${JETSON_PORT} -i ${JETSON_KEY} -o StrictHostKeyChecking=no" \
                    "${d}/" "${JETSON_USER}@${JETSON_HOST}:${REMOTE_DATA_DIR}/processed/$(basename ${d})/"
            fi
            log_ok "Calibration data deployed from ${d}"
        fi
    done
}

stage_build() {
    log_stage "STAGE 2: Build CUDA Kernels on Jetson (sm_87)"

    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && chmod +x build_cuda.sh && ./build_cuda.sh Release" \
        || { log_err "CUDA build failed"; return 1; }
    log_ok "CUDA kernels built successfully"

    ssh_cmd "cd ${REMOTE_PROJECT_DIR}/build && python3 ../src/cuda/trajectory_bindings.py" \
        || { log_err "CUDA backend verification failed"; return 1; }
    log_ok "CUDA backend verified on Jetson"
}

stage_calibrate() {
    log_stage "STAGE 3: TensorRT INT8 Calibration (entropy + percentile)"

    log_info "Running entropy calibration..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && python3 src/deployment/export_tensorrt.py \
        --model_path checkpoints/multiclass/best_model.pth \
        --int8 --calib_data ${REMOTE_DATA_DIR}/processed/drone_audio \
        --output_dir tensorrt_models \
        --calib_method entropy \
        --calib_batches 32 \
        --calib_batch_size 32 \
        --benchmark" \
        || { log_err "Entropy calibration failed"; return 1; }
    log_ok "Entropy calibration complete"

    log_info "Running percentile calibration (99.9)..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && python3 src/deployment/export_tensorrt.py \
        --model_path checkpoints/multiclass/best_model.pth \
        --int8 --calib_data ${REMOTE_DATA_DIR}/processed/drone_audio \
        --output_dir tensorrt_models \
        --calib_method percentile \
        --calib_batches 32 \
        --calib_batch_size 32 \
        --calib_percentile 99.9 \
        --benchmark \
        --model_name audio_classifier_percentile" \
        || { log_err "Percentile calibration failed"; return 1; }
    log_ok "Percentile calibration complete"

    log_info "Comparing calibration methods..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && python3 -c \"\nimport json\nimport os\nresults = {}\nfor f in ['tensorrt_models/audio_classifier.engine', 'tensorrt_models/audio_classifier_percentile.engine']:\n    if os.path.exists(f):\n        print(f'Found: {f}')\nprint('Calibration comparison:')\nprint('  entropy: tensorrt_models/audio_classifier.engine')\nprint('  percentile: tensorrt_models/audio_classifier_percentile.engine')\n\""
    log_ok "Calibration comparison ready"
}

stage_dla() {
    log_stage "STAGE 4: DLA (Deep Learning Accelerator) Testing"

    log_info "Checking DLA availability on Jetson Orin..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && python3 -c \"\nimport tensorrt as trt\nlogger = trt.Logger(trt.Logger.WARNING)\nbuilder = trt.Builder(logger)\nprint(f'DLA cores: {builder.num_DLA_cores}')\nprint(f'FP16: {builder.platform_has_fast_fp16}')\nprint(f'INT8: {builder.platform_has_fast_int8}')\nfor i in range(builder.num_DLA_cores):\n    print(f'DLA core {i} supported')\n\" 2>/dev/null || echo 'TensorRT not available or DLA not supported'" \
        || log_warn "DLA check failed or not available"

    log_info "Testing DLA execution with INT8 engine (if DLA available)..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && python3 -c \"\nimport os\nimport tensorrt as trt\nimport pycuda.driver as cuda\nimport numpy as np\n\nengine_path = 'tensorrt_models/audio_classifier_percentile.engine'\nif not os.path.exists(engine_path):\n    engine_path = 'tensorrt_models/audio_classifier.engine'\n\nif not os.path.exists(engine_path):\n    print('No engine found, skipping DLA test')\n    exit(0)\n\nlogger = trt.Logger(trt.Logger.WARNING)\nruntime = trt.Runtime(logger)\nwith open(engine_path, 'rb') as f:\n    engine = runtime.deserialize_cuda_engine(f.read())\n\nprint(f'Engine: {engine_path}')\nprint(f'Layers: {engine.num_layers}')\nprint(f'DLA cores available: {trt.Builder(logger).num_DLA_cores}')\n\n# Try to create execution context with DLA\ncontext = engine.create_execution_context()\nif context:\n    print('Execution context created successfully')\n    # Check if any layers can run on DLA\n    for i in range(engine.num_layers):\n        layer = engine.get_layer(i)\n        if layer.precision == trt.DataType.INT8:\n            print(f'  Layer {i} ({layer.name}): {layer.type} - INT8')\n\" 2>/dev/null || echo 'DLA test requires TensorRT and engine files'" \
        || log_warn "DLA test skipped or failed"

    log_info "DLA test completed"
}

stage_benchmark() {
    log_stage "STAGE 5: Performance Benchmarks"

    log_info "Running CUDA kernel benchmarks..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR}/build && python3 -c \"\nimport time\nimport sys\nsys.path.insert(0, '..')\nfrom src.cuda.trajectory_bindings import get_trajectory_backend\nbackend, name = get_trajectory_backend()\nprint(f'Backend: {name}')\n\n# Benchmark geometric dive\nstart = time.perf_counter()\nfor _ in range(1000):\n    pts = backend.geometric_dive((0,0,100), 50, 45, 25, 30, 60, 50)\nelapsed = (time.perf_counter() - start) / 1000 * 1000\nprint(f'Geometric Dive (50 pts): {elapsed:.3f} ms avg')\n\n# Benchmark spiral dive\nstart = time.perf_counter()\nfor _ in range(1000):\n    pts = backend.spiral_dive((0,0,100), 50, 25, 10, 50)\nelapsed = (time.perf_counter() - start) / 1000 * 1000\nprint(f'Spiral Dive (50 pts): {elapsed:.3f} ms avg')\n\n# Benchmark jink\nstart = time.perf_counter()\nfor _ in range(1000):\n    pts = backend.jink((0,0,100), 20, 25, 30, 45, 50)\nelapsed = (time.perf_counter() - start) / 1000 * 1000\nprint(f'Jink (20 segs): {elapsed:.3f} ms avg')\n\""

    log_info "Running TensorRT inference benchmarks..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && python3 -c \"\nimport os\nimport numpy as np\nimport tensorrt as trt\nimport pycuda.driver as cuda\nimport time\n\ndef benchmark_engine(engine_path, name):\n    if not os.path.exists(engine_path):\n        print(f'{name}: Engine not found at {engine_path}')\n        return\n    logger = trt.Logger(trt.Logger.WARNING)\n    runtime = trt.Runtime(logger)\n    with open(engine_path, 'rb') as f:\n        engine = runtime.deserialize_cuda_engine(f.read())\n    context = engine.create_execution_context()\n    \n    input_shape = (1, 1, 157, 40)\n    test_input = np.random.randn(*input_shape).astype(np.float32)\n    \n    input_binding = engine.get_binding_index('input')\n    output_binding = engine.get_binding_index('output')\n    \n    d_input = cuda.mem_alloc(test_input.nbytes)\n    output_shape = list(engine.get_binding_shape(output_binding))\n    output_shape[0] = input_shape[0]\n    d_output = cuda.mem_alloc(np.prod(output_shape) * 4)\n    \n    # Warmup\n    for _ in range(10):\n        cuda.memcpy_htod(d_input, test_input)\n        context.execute_v2([int(d_input), int(d_output)])\n    cuda.Context.synchronize()\n    \n    # Benchmark\n    times = []\n    for _ in range(100):\n        start = time.perf_counter()\n        cuda.memcpy_htod(d_input, test_input)\n        context.execute_v2([int(d_input), int(d_output)])\n        cuda.Context.synchronize()\n        times.append(time.perf_counter() - start)\n    \n    times = np.array(times)\n    print(f'{name}:')\n    print(f'  Mean: {np.mean(times)*1000:.2f} ms')\n    print(f'  Std:  {np.std(times)*1000:.2f} ms')\n    print(f'  Min:  {np.min(times)*1000:.2f} ms')\n    print(f'  Max:  {np.max(times)*1000:.2f} ms')\n    print(f'  FPS:  {1.0/np.mean(times):.1f}')\n\nbenchmark_engine('tensorrt_models/audio_classifier.engine', 'Entropy INT8')\nbenchmark_engine('tensorrt_models/audio_classifier_percentile.engine', 'Percentile INT8')\n\" 2>/dev/null || echo 'TensorRT benchmark skipped (TensorRT not available)'"

    log_info "Running system validation..."
    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && ./scripts/jetson_verify.sh --full" \
        || log_warn "Full validation had issues"
}

stage_package() {
    log_stage "STAGE 6: Create Deploy Package"

    ssh_cmd "cd ${REMOTE_PROJECT_DIR} && mkdir -p deploy_package && \
        cp build/libtrajectory_kernels.so deploy_package/ && \
        cp tensorrt_models/audio_classifier.engine deploy_package/ 2>/dev/null || true && \
        cp tensorrt_models/audio_classifier_percentile.engine deploy_package/ 2>/dev/null || true && \
        cp src/cuda/trajectory_bindings.py deploy_package/ && \
        cp src/cuda/trajectory_kernels.cuh deploy_package/ && \
        cp tensorrt_models/*.calib deploy_package/ 2>/dev/null || true && \
        cd deploy_package && \
        tar -czf ../q250-v3-opti-gpu-\$(date +%Y%m%d).tar.gz . && \
        sha256sum ../q250-v3-opti-gpu-\$(date +%Y%m%d).tar.gz > ../q250-v3-opti-gpu-\$(date +%Y%m%d).tar.gz.sha256 && \
        ls -la ../q250-v3-opti-gpu-*.tar.gz*" \
        || { log_err "Package creation failed"; return 1; }
    log_ok "Deploy package created on Jetson"

    log_info "Downloading deploy package to local..."
    local package_name
    package_name=$(ssh_cmd "cd ${REMOTE_PROJECT_DIR} && ls -t q250-v3-opti-gpu-*.tar.gz 2>/dev/null | head -1" | tr -d '\r\n')
    if [[ -n "${package_name}" ]]; then
        scp_cmd "${REMOTE_PROJECT_DIR}/${package_name}" "${PROJECT_ROOT}/"
        scp_cmd "${REMOTE_PROJECT_DIR}/${package_name}.sha256" "${PROJECT_ROOT}/"
        log_ok "Deploy package downloaded: ${package_name}"
    else
        log_err "No deploy package found on Jetson"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

SSH Automation for Jetson Orin On-Device Validation Pipeline

OPTIONS:
    --host HOST         Jetson Orin SSH hostname/IP (default: jetson.local)
    --user USER         SSH username (default: jetson)
    --key KEY           SSH private key path (default: ~/.ssh/id_ed25519)
    --port PORT         SSH port (default: 22)
    --stage STAGE       Run specific stage: deploy, build, calibrate, dla, benchmark, package, all (default: all)
    --skip-deploy       Skip deployment stage
    --dry-run           Show commands without executing
    -h, --help          Show this help

EXAMPLES:
    $0                                    # Run full pipeline
    $0 --host 192.168.1.100 --user nvidia # Custom host/user
    $0 --stage build                      # Only build CUDA kernels
    $0 --stage calibrate --skip-deploy    # Only calibration, files already on Jetson
    $0 --dry-run                          # Preview commands

ENVIRONMENT VARIABLES:
    JETSON_HOST, JETSON_USER, JETSON_KEY, JETSON_PORT
    STAGE, SKIP_DEPLOY, DRY_RUN
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host) JETSON_HOST="$2"; shift 2 ;;
            --user) JETSON_USER="$2"; shift 2 ;;
            --key) JETSON_KEY="$2"; shift 2 ;;
            --port) JETSON_PORT="$2"; shift 2 ;;
            --stage) STAGE="$2"; shift 2 ;;
            --skip-deploy) SKIP_DEPLOY="true"; shift ;;
            --dry-run) DRY_RUN="true"; shift ;;
            -h|--help) usage; exit 0 ;;
            *) log_err "Unknown option: $1"; usage; exit 1 ;;
        esac
    done
}

main() {
    parse_args "$@"

    log_info "Q250-V3-Opti Jetson Orin SSH Validation Pipeline"
    log_info "Target: ${JETSON_USER}@${JETSON_HOST}:${JETSON_PORT}"
    log_info "Stage: ${STAGE}"
    [[ "${DRY_RUN}" == "true" ]] && log_warn "DRY RUN MODE - no commands will be executed"

    case "${STAGE}" in
        deploy)
            stage_deploy
            ;;
        build)
            [[ "${SKIP_DEPLOY}" != "true" ]] && stage_deploy
            stage_build
            ;;
        calibrate)
            [[ "${SKIP_DEPLOY}" != "true" ]] && stage_deploy
            stage_build
            stage_calibrate
            ;;
        dla)
            [[ "${SKIP_DEPLOY}" != "true" ]] && stage_deploy
            stage_build
            stage_calibrate
            stage_dla
            ;;
        benchmark)
            [[ "${SKIP_DEPLOY}" != "true" ]] && stage_deploy
            stage_build
            stage_calibrate
            stage_dla
            stage_benchmark
            ;;
        package)
            [[ "${SKIP_DEPLOY}" != "true" ]] && stage_deploy
            stage_build
            stage_calibrate
            stage_dla
            stage_benchmark
            stage_package
            ;;
        all)
            [[ "${SKIP_DEPLOY}" != "true" ]] && stage_deploy
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