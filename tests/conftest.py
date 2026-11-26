"""Pytest fixtures for CUDA/TensorRT verification test suite.

Provides fixtures for:
- CUDA kernel testing (with mock fallback for non-GPU CI)
- TensorRT engine building/verification (with mock fallback)
- INT8 calibration data generation (entropy + percentile)
- Calibration cache version checking
- Performance benchmark configuration

These fixtures are designed to run on Jetson Orin (sm_87) target hardware,
with graceful degradation to mock-based testing on CI machines without GPU.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JETSON_ORIN_ARCH = "87"  # sm_87
CALIBRATION_SAMPLES_MIN = 1000
CALIBRATION_BATCH_SIZE = 32
CALIBRATION_INPUT_SHAPE = (
    1,
    157,
    40,
)  # (channels, time, mels) for audio classification
NETWORK_HASH_ALGO = "sha256"

# Cache version format: v{calib_method}_{batch_size}_{num_samples}_{network_hash_short}
CACHE_VERSION_PREFIX = "trt_calib_v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_network_hash(model_bytes: bytes) -> str:
    """Compute SHA-256 hash of model bytes for cache versioning."""
    return hashlib.sha256(model_bytes).hexdigest()[:16]


def _compute_cache_version(
    calib_method: str,
    batch_size: int,
    num_samples: int,
    network_hash: str,
) -> str:
    """Build a deterministic cache version string.

    Format: trt_calib_v1|{method}|{batch_size}|{samples}|{network_hash}
    """
    return f"{CACHE_VERSION_PREFIX}|{calib_method}|{batch_size}|{num_samples}|{network_hash}"


def _is_cuda_available() -> bool:
    """Check if CUDA is available on this machine."""
    try:
        import pycuda.driver as cuda  # noqa: F401
        import tensorrt as trt  # noqa: F401

        return True
    except ImportError:
        return False


def _is_tensorrt_available() -> bool:
    """Check if TensorRT is available on this machine."""
    try:
        import tensorrt as trt  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Fixtures: Environment detection
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cuda_available() -> bool:
    """Whether CUDA (pycuda + tensorrt) is available on this host."""
    return _is_cuda_available()


@pytest.fixture(scope="session")
def tensorrt_available() -> bool:
    """Whether TensorRT is available on this host."""
    return _is_tensorrt_available()


@pytest.fixture(scope="session")
def jetson_orin_target() -> bool:
    """Whether this host is a Jetson Orin target (sm_87).

    Detected via nvidia-smi or environment variable.
    """
    env_val = os.environ.get("Q250_JETSON_ORIN", "").lower()
    if env_val in ("1", "true", "yes"):
        return True
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            gpu_name = result.stdout.strip().lower()
            if "orin" in gpu_name or "t234" in gpu_name:
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Fixtures: Calibration data
# ---------------------------------------------------------------------------


@pytest.fixture
def calibration_samples_1000() -> np.ndarray:
    """Generate 1000+ calibration samples matching model input shape.

    Shape: (1000, 1, 157, 40) — normalized float32 audio features.
    Deterministic via fixed seed for reproducibility.
    """
    rng = np.random.RandomState(42)
    samples = rng.randn(CALIBRATION_SAMPLES_MIN, *CALIBRATION_INPUT_SHAPE).astype(np.float32)
    # Normalize to [-1, 1] range typical of log-mel features
    samples = np.clip(samples, -1.0, 1.0)
    return samples


@pytest.fixture
def calibration_samples_500() -> np.ndarray:
    """Generate 500 calibration samples (below minimum for boundary testing)."""
    rng = np.random.RandomState(42)
    return rng.randn(500, *CALIBRATION_INPUT_SHAPE).astype(np.float32)


@pytest.fixture
def calibration_batch() -> np.ndarray:
    """Single calibration batch of size CALIBRATION_BATCH_SIZE."""
    rng = np.random.RandomState(7)
    return rng.randn(CALIBRATION_BATCH_SIZE, *CALIBRATION_INPUT_SHAPE).astype(np.float32)


# ---------------------------------------------------------------------------
# Fixtures: Model artifacts
# ---------------------------------------------------------------------------


@pytest.fixture
def dummy_onnx_model(tmp_path) -> Path:
    """Create a minimal ONNX model for TensorRT testing.

    Simple linear model: input (1, 1, 157, 40) -> output (1, num_classes)
    """
    import onnx
    from onnx import TensorProto, helper

    num_classes = 3
    input_shape = [1, 1, 157, 40]

    X = helper.make_tensor_value_info("input", TensorProto.FLOAT, input_shape)
    Y = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, num_classes])

    # Simple gemm-like node (flatten + linear) — minimal valid ONNX
    node_def = helper.make_node("GlobalAveragePool", inputs=["input"], outputs=["pooled"])
    node_flatten = helper.make_node("Flatten", inputs=["pooled"], outputs=["flattened"], axis=1)
    # MatMul + Add for classification head
    W = helper.make_tensor(
        "W",
        TensorProto.FLOAT,
        [157 * 40, num_classes],
        vals=np.random.randn(157 * 40, num_classes).astype(np.float32).flatten().tolist(),
    )
    B = helper.make_tensor(
        "B",
        TensorProto.FLOAT,
        [num_classes],
        vals=np.zeros(num_classes, dtype=np.float32).tolist(),
    )
    node_matmul = helper.make_node("MatMul", ["flattened", "W"], ["logits"])
    node_add = helper.make_node("Add", ["logits", "B"], ["output"])

    graph = helper.make_graph(
        [node_def, node_flatten, node_matmul, node_add],
        "test_model",
        [X],
        [Y],
        initializer=[W, B],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 11)])
    onnx.checker.check_model(model)

    onnx_path = tmp_path / "test_model.onnx"
    onnx.save(model, str(onnx_path))
    return onnx_path


@pytest.fixture
def dummy_model_bytes(dummy_onnx_model) -> bytes:
    """Raw bytes of the dummy ONNX model (for hash computation)."""
    return dummy_onnx_model.read_bytes()


@pytest.fixture
def network_hash(dummy_model_bytes) -> str:
    """SHA-256-based short hash of the dummy model."""
    return _compute_network_hash(dummy_model_bytes)


# ---------------------------------------------------------------------------
# Fixtures: Cache versioning
# ---------------------------------------------------------------------------


@pytest.fixture
def cache_version_entropy(network_hash) -> str:
    """Expected cache version for entropy calibrator."""
    return _compute_cache_version(
        "entropy", CALIBRATION_BATCH_SIZE, CALIBRATION_SAMPLES_MIN, network_hash
    )


@pytest.fixture
def cache_version_percentile(network_hash) -> str:
    """Expected cache version for percentile calibrator."""
    return _compute_cache_version(
        "percentile", CALIBRATION_BATCH_SIZE, CALIBRATION_SAMPLES_MIN, network_hash
    )


# ---------------------------------------------------------------------------
# Fixtures: Temporary directories
# ---------------------------------------------------------------------------


@pytest.fixture
def tensorrt_workspace(tmp_path) -> Path:
    """Temporary workspace for TensorRT engine artifacts."""
    ws = tmp_path / "tensorrt_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture
def calibration_cache_file(tensorrt_workspace) -> Path:
    """Path to a calibration cache file."""
    return tensorrt_workspace / "calibration.cache"


# ---------------------------------------------------------------------------
# Fixtures: Mock TensorRT (for CI without GPU)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tensorrt():
    """Mock TensorRT module for testing without GPU/TensorRT installed."""
    with patch.dict("sys.modules", {"tensorrt": MagicMock()}):
        trt = MagicMock()
        trt.Logger = MagicMock
        trt.Builder = MagicMock
        trt.Runtime = MagicMock
        trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH = 1
        trt.BuilderFlag.FP16 = "fp16"
        trt.BuilderFlag.INT8 = "int8"
        trt.IInt8EntropyCalibrator2 = MagicMock
        yield trt


# ---------------------------------------------------------------------------
# Pytest configuration: skip markers
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom skip markers."""
    config.addinivalue_line(
        "markers",
        "requires_cuda: skip if CUDA/TensorRT not available",
    )
    config.addinivalue_line(
        "markers",
        "requires_jetson_orin: skip if not running on Jetson Orin target",
    )
    config.addinivalue_line(
        "markers",
        "target_validation: test designed for Jetson Orin target execution",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip CUDA/TensorRT tests when hardware is unavailable."""
    requires_cuda = pytest.mark.skip(reason="CUDA/TensorRT not available on this host")
    requires_jetson = pytest.mark.skip(reason="Not running on Jetson Orin target")

    for item in items:
        if item.get_closest_marker("requires_cuda") and not _is_cuda_available():
            item.add_marker(requires_cuda)
        if item.get_closest_marker("requires_jetson_orin") and not _is_jetson_orin():
            item.add_marker(requires_jetson)


def _is_jetson_orin() -> bool:
    """Lightweight Jetson Orin detection (no subprocess in collection)."""
    return os.environ.get("Q250_JETSON_ORIN", "").lower() in ("1", "true", "yes")
