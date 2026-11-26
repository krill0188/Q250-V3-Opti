#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti: Jetson Orin Target Validation Script
# =============================================================================
# Validates CUDA kernels and TensorRT engines on Jetson Orin (sm_87) target.
# Run this script directly on the Jetson Orin device after deploying build
# artifacts.
#
# Usage:
#   ./scripts/jetson_verify.sh [--full] [--quick]
#
#   --quick   Run smoke tests only (CUDA availability, backend selection)
#   --full    Run full verification suite (CUDA + TensorRT + benchmarks)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BUILD_DIR="${PROJECT_DIR}/build"
TESTS_DIR="${PROJECT_DIR}/tests"

QUICK=false
FULL=false

for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=true ;;
    --full)  FULL=true ;;
    -h|--help)
      echo "Usage: $0 [--quick|--full]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# Default to quick if neither specified
if [[ "$QUICK" == false && "$FULL" == false ]]; then
  QUICK=true
fi

echo "============================================================"
echo "Q250-V3-Opti Jetson Orin Target Validation"
echo "============================================================"
echo "Project: ${PROJECT_DIR}"
echo "Date:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

echo "[1/6] Pre-flight environment checks..."

# Check Jetson Orin
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "unknown")
echo "  GPU: ${GPU_NAME}"
if echo "${GPU_NAME}" | grep -qi "orin\|t234"; then
  echo "  ✓ Jetson Orin detected"
else
  echo "  ⚠ Not Jetson Orin (some tests may be skipped)"
fi

# Check CUDA
NVCC_VERSION=$(nvcc --version 2>/dev/null | grep "release" | awk '{print $5}' | head -1 || echo "unknown")
echo "  CUDA: ${NVCC_VERSION}"

# Check TensorRT
if python3 -c "import tensorrt; print('TensorRT', tensorrt.__version__)" 2>/dev/null; then
  echo "  ✓ TensorRT available"
else
  echo "  ⚠ TensorRT not installed (TensorRT tests will be skipped)"
fi

# Check pycuda
if python3 -c "import pycuda.driver" 2>/dev/null; then
  echo "  ✓ pycuda available"
else
  echo "  ⚠ pycuda not installed"
fi

echo ""

# ---------------------------------------------------------------------------
# Step 2: CUDA kernel build verification
# ---------------------------------------------------------------------------

echo "[2/6] CUDA kernel library verification..."

if [[ -f "${BUILD_DIR}/libtrajectory_kernels.so" ]]; then
  echo "  ✓ libtrajectory_kernels.so found"
  file "${BUILD_DIR}/libtrajectory_kernels.so"
else
  echo "  ✗ libtrajectory_kernels.so NOT found — build first:"
  echo "    cd ${PROJECT_DIR} && ./build_cuda.sh Release"
  echo ""
  echo "  Skipping CUDA tests..."
  CUDA_AVAILABLE=false
fi

if [[ -f "${BUILD_DIR}/trajectory_bindings.py" ]]; then
  echo "  ✓ trajectory_bindings.py found"
else
  echo "  ⚠ trajectory_bindings.py not found"
fi

echo ""

# ---------------------------------------------------------------------------
# Step 3: Quick smoke test
# ---------------------------------------------------------------------------

if [[ "$QUICK" == true ]]; then
  echo "[3/6] Quick smoke test (CUDA backend selection)..."
  cd "${BUILD_DIR}"
  if python3 "${PROJECT_DIR}/src/cuda/trajectory_bindings.py" 2>&1 | grep -q "Backend:"; then
    echo "  ✓ Backend selection works"
  else
    echo "  ✗ Backend selection failed"
    exit 1
  fi

  # Verify CUDA backend is selected on Jetson
  BACKEND_NAME=$(python3 -c "
import sys
sys.path.insert(0, '${BUILD_DIR}')
from trajectory_bindings import get_trajectory_backend
_, name = get_trajectory_backend()
print(name)
" 2>/dev/null || echo "unknown")

  echo "  Backend: ${BACKEND_NAME}"
  if [[ "${BACKEND_NAME}" == "cuda" ]]; then
    echo "  ✓ CUDA backend active on Jetson Orin"
  else
    echo "  ⚠ CUDA backend not active (falling back to Python)"
  fi
  echo ""
fi

# ---------------------------------------------------------------------------
# Step 4: Python test suite
# ---------------------------------------------------------------------------

echo "[4/6] Running Python test suite..."

cd "${PROJECT_DIR}"

# Install test dependencies if needed
pip install pytest pytest-asyncio numpy onnx 2>/dev/null || true

if [[ "$QUICK" == true ]]; then
  # Quick: run tests that don't require GPU
  python3 -m pytest tests/ \
    -v \
    -m "not requires_cuda and not requires_jetson_orin" \
    --tb=short \
    2>&1 | tail -30
else
  # Full: run all tests (CUDA tests will be skipped on non-GPU hosts)
  python3 -m pytest tests/ \
    -v \
    -m "not requires_jetson_orin or Q250_JETSON_ORIN" \
    --tb=short \
    2>&1 | tail -30
fi

TEST_EXIT=${PIPESTATUS[0]}
echo ""
if [[ ${TEST_EXIT} -eq 0 ]]; then
  echo "  ✓ All tests passed"
else
  echo "  ✗ Some tests failed (exit code: ${TEST_EXIT})"
fi

echo ""

# ---------------------------------------------------------------------------
# Step 5: TensorRT engine verification (full mode only)
# ---------------------------------------------------------------------------

if [[ "$FULL" == true ]]; then
  echo "[5/6] TensorRT engine verification..."

  if python3 -c "import tensorrt" 2>/dev/null; then
    echo "  TensorRT installed — checking for engine files..."

    ENGINE_DIR="${PROJECT_DIR}/tensorrt_models"
    if [[ -d "${ENGINE_DIR}" ]]; then
      ENGINE_COUNT=$(find "${ENGINE_DIR}" -name "*.engine" 2>/dev/null | wc -l)
      echo "  Found ${ENGINE_COUNT} engine file(s)"

      for engine in "${ENGINE_DIR}"/*.engine; do
        [[ -f "${engine}" ]] || continue
        echo "  ✓ Engine: $(basename "${engine}") ($(du -h "${engine}" | cut -f1))"
      done
    else
      echo "  ⚠ No tensorrt_models directory — run export_tensorrt.py first"
    fi
  else
    echo "  ⚠ TensorRT not installed — skipping engine verification"
  fi
  echo ""
fi

# ---------------------------------------------------------------------------
# Step 6: Summary
# ---------------------------------------------------------------------------

echo "[6/6] Validation summary..."
echo "============================================================"
echo "  GPU:        ${GPU_NAME}"
echo "  CUDA:       ${NVCC_VERSION}"
echo "  CUDA lib:   $([[ -f "${BUILD_DIR}/libtrajectory_kernels.so" ]] && echo "OK" || echo "MISSING")"
echo "  Tests:      $([[ ${TEST_EXIT:-0} -eq 0 ]] && echo "PASSED" || echo "FAILED")"
echo "============================================================"

if [[ ${TEST_EXIT:-0} -ne 0 ]]; then
  exit 1
fi

echo ""
echo "Jetson Orin target validation complete."
echo "Next: Deploy TensorRT engines and run calibration on target."
