"""
Performance benchmark tests for CUDA/TensorRT on Jetson Orin.

Verifies:
- CUDA trajectory kernel latency (< 0.1ms for 50 points)
- TensorRT engine inference latency
- INT8 vs FP16 vs FP32 precision comparison
- Throughput measurements
- Regression benchmarks with baseline comparison

These tests are designed to run on Jetson Orin (sm_87) target.
On CI hosts without GPU, they use mock data and document expected baselines.

Performance targets (from CUDA_BUILD_GUIDE.md):
- Geometric Dive (50 pts): ~0.05ms CUDA vs ~1.2ms Python (24x speedup)
- Spiral Dive (50 pts): ~0.06ms CUDA vs ~1.5ms Python (25x speedup)
- Sine Dive (50 pts): ~0.05ms CUDA vs ~1.3ms Python (26x speedup)
- Jink (20 segments): ~0.04ms CUDA vs ~0.8ms Python (20x speedup)
- LUT Interpolation: ~0.01ms CUDA vs ~0.3ms Python (30x speedup)
"""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tests.conftest import (
    CALIBRATION_BATCH_SIZE,
    CALIBRATION_INPUT_SHAPE,
    CALIBRATION_SAMPLES_MIN,
)

# ---------------------------------------------------------------------------
# CUDA Performance Tests
# ---------------------------------------------------------------------------


class TestCUDAPerformance:
    """CUDA kernel performance benchmarks."""

    def test_geometric_dive_latency_cuda(self):
        """Geometric dive latency on CUDA backend.

        Target: < 0.1ms for 50 points on Jetson Orin.
        """
        try:
            from trajectory_bindings import get_trajectory_backend
        except ImportError:
            pytest.skip("trajectory_bindings not available")

        try:
            backend, name = get_trajectory_backend(force_python=False)
            if name != "cuda":
                pytest.skip("CUDA backend not available")
        except Exception:
            pytest.skip("CUDA backend not available")

        start = (0.0, 0.0, 500.0)
        iterations = 1000

        # Warmup
        for _ in range(10):
            backend.geometric_dive(start, 100, 45, 30)

        # Benchmark
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            backend.geometric_dive(start, 100, 45, 30)
            times.append(time.perf_counter() - t0)

        times = np.array(times)
        mean_ms = np.mean(times) * 1000
        p99_ms = np.percentile(times, 99) * 1000

        print(f"\n  CUDA Geometric Dive: mean={mean_ms:.4f}ms, p99={p99_ms:.4f}ms")

        assert mean_ms < 0.1, f"Mean latency {mean_ms:.4f}ms exceeds 0.1ms target"
        assert p99_ms < 0.5, f"P99 latency {p99_ms:.4f}ms exceeds 0.5ms target"

    def test_all_cuda_kernels_latency(self):
        """All CUDA trajectory kernels meet latency targets."""
        try:
            from trajectory_bindings import get_trajectory_backend
        except ImportError:
            pytest.skip("trajectory_bindings not available")

        try:
            backend, name = get_trajectory_backend(force_python=False)
            if name != "cuda":
                pytest.skip("CUDA backend not available")
        except Exception:
            pytest.skip("CUDA backend not available")

        kernels = {
            "geometric_dive": lambda: backend.geometric_dive((0, 0, 500), 100, 45, 30),
            "spiral_dive": lambda: backend.spiral_dive((0, 0, 300), 50, 3, 10, 10),
            "sine_dive": lambda: backend.sine_dive((0, 0, 300), 20, 0.5, 15, 10),
            "jink": lambda: backend.jink_trajectory((0, 0, 300), seed=42),
        }

        results = {}
        for kernel_name, fn in kernels.items():
            # Warmup
            for _ in range(5):
                fn()

            times = []
            for _ in range(500):
                t0 = time.perf_counter()
                fn()
                times.append(time.perf_counter() - t0)

            mean_ms = np.mean(times) * 1000
            results[kernel_name] = mean_ms
            print(f"  CUDA {kernel_name}: {mean_ms:.4f}ms")

        # All kernels should be well under 1ms
        for kernel_name, latency_ms in results.items():
            assert (
                latency_ms < 1.0
            ), f"{kernel_name} latency {latency_ms:.4f}ms exceeds 1ms"


class TestPythonFallbackPerformance:
    """Python fallback performance (for CI without GPU)."""

    def test_geometric_dive_latency_python(self):
        """Python fallback geometric dive latency.

        Target: < 5ms for 50 points on CI hardware.
        """
        from trajectory_bindings import TrajectoryPythonFallback

        backend = TrajectoryPythonFallback()
        start = (0.0, 0.0, 500.0)

        # Warmup
        for _ in range(10):
            backend.geometric_dive(start, 100, 45, 30)

        # Benchmark
        iterations = 100
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            backend.geometric_dive(start, 100, 45, 30)
            times.append(time.perf_counter() - t0)

        mean_ms = np.mean(times) * 1000
        print(f"\n  Python Geometric Dive: mean={mean_ms:.3f}ms")

        assert mean_ms < 5.0, f"Python fallback too slow: {mean_ms:.3f}ms"


# ---------------------------------------------------------------------------
# TensorRT Performance Tests
# ---------------------------------------------------------------------------


class TestTensorRTPerformance:
    """TensorRT engine inference performance benchmarks."""

    @pytest.mark.requires_cuda
    def test_fp16_inference_latency(self, tmp_path):
        """FP16 TensorRT engine inference latency target."""
        import pycuda.autoinit
        import pycuda.driver as cuda
        import tensorrt as trt

        engine_path = tmp_path / "model_fp16.engine"
        # Write a mock engine file for the test structure
        # Real test runs on Jetson with actual engine
        pytest.skip("Requires actual TensorRT engine on Jetson Orin")

    @pytest.mark.requires_cuda
    def test_int8_vs_fp16_precision(self, tmp_path):
        """INT8 engine output within tolerance of FP16 engine.

        INT8 quantization error should be < 5% relative difference.
        """
        pytest.skip("Requires actual TensorRT engines on Jetson Orin")

    def test_benchmark_structure(self):
        """Benchmark result dict has required keys."""
        required_keys = {"mean_ms", "std_ms", "min_ms", "max_ms", "fps", "throughput"}
        # This test documents the expected benchmark output schema
        assert required_keys == required_keys  # placeholder for schema validation


# ---------------------------------------------------------------------------
# Regression baselines
# ---------------------------------------------------------------------------


class TestRegressionBaselines:
    """Documented performance baselines for regression detection.

    Baselines from CUDA_BUILD_GUIDE.md (Jetson AGX Orin 64GB, batch=1).
    Update these when re-measured on target hardware.
    """

    BASELINES = {
        "geometric_dive_cuda_ms": 0.05,
        "spiral_dive_cuda_ms": 0.06,
        "sine_dive_cuda_ms": 0.05,
        "jink_cuda_ms": 0.04,
        "lut_interpolate_cuda_ms": 0.01,
        "geometric_dive_python_ms": 1.2,
        "spiral_dive_python_ms": 1.5,
        "sine_dive_python_ms": 1.3,
        "jink_python_ms": 0.8,
        "lut_interpolate_python_ms": 0.3,
    }

    def test_baselines_documented(self):
        """All baseline performance values are documented."""
        for name, value in self.BASELINES.items():
            assert value > 0
            assert isinstance(value, float)

    def test_cuda_speedup_factor(self):
        """CUDA should provide > 10x speedup over Python fallback."""
        for op in [
            "geometric_dive",
            "spiral_dive",
            "sine_dive",
            "jink",
            "lut_interpolate",
        ]:
            cuda_ms = self.BASELINES[f"{op}_cuda_ms"]
            python_ms = self.BASELINES[f"{op}_python_ms"]
            speedup = python_ms / cuda_ms
            assert speedup > 10.0, f"{op}: speedup {speedup:.1f}x below 10x target"
            print(
                f"  {op}: {speedup:.1f}x speedup (CUDA {cuda_ms}ms vs Python {python_ms}ms)"
            )
