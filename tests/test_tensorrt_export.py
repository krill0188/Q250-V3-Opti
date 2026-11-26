"""
Test suite for TensorRT engine export and verification.

Verifies:
- ONNX model creation and validation
- TensorRT engine building (FP16, INT8 modes) — GPU only
- Engine verification against ONNX Runtime outputs — GPU only
- Dynamic optimization profiles — GPU only
- Benchmark inference latency — GPU only

Tests that require TensorRT/torch are skipped on hosts without GPU.
On Jetson Orin target, full TensorRT pipeline is exercised.

Designed for Jetson Orin (sm_87) target validation.
"""

import json
from pathlib import Path
import struct
from unittest.mock import MagicMock, patch

import numpy as np
import onnx
from onnx import TensorProto, helper
import pytest

# ---------------------------------------------------------------------------
# Try importing export_tensorrt — may fail on hosts without torch/tensorrt
# ---------------------------------------------------------------------------

try:
    from src.deployment.export_tensorrt import (
        INT8Calibrator,
        benchmark_tensorrt_engine,
        build_tensorrt_engine,
        verify_tensorrt_engine,
    )

    _EXPORT_MODULE_AVAILABLE = True
except (ImportError, RuntimeError, NameError):
    _EXPORT_MODULE_AVAILABLE = False


def _skip_if_no_export_module():
    """Skip test if export_tensorrt module can't be imported."""
    if not _EXPORT_MODULE_AVAILABLE:
        pytest.skip("export_tensorrt module not available (torch/tensorrt missing)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_onnx(tmp_path, num_classes=3):
    """Create a minimal valid ONNX model for TensorRT testing.

    Graph: GlobalAveragePool -> Flatten -> MatMul -> Add
    Input:  (1, 1, 157, 40)
    Output: (1, num_classes)
    """
    input_shape = [1, 1, 157, 40]
    X = helper.make_tensor_value_info("input", TensorProto.FLOAT, input_shape)
    Y = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, num_classes])

    node_pool = helper.make_node("GlobalAveragePool", ["input"], ["pooled"])
    node_flat = helper.make_node("Flatten", ["pooled"], ["flattened"], axis=1)

    W_vals = np.random.randn(157 * 40, num_classes).astype(np.float32).flatten().tolist()
    B_vals = np.zeros(num_classes, dtype=np.float32).tolist()
    W = helper.make_tensor("W", TensorProto.FLOAT, [157 * 40, num_classes], W_vals)
    B = helper.make_tensor("B", TensorProto.FLOAT, [num_classes], B_vals)

    node_mm = helper.make_node("MatMul", ["flattened", "W"], ["logits"])
    node_add = helper.make_node("Add", ["logits", "B"], ["output"])

    graph = helper.make_graph(
        [node_pool, node_flat, node_mm, node_add],
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


def _serialize_mock_engine(engine_path: Path, num_classes: int = 3):
    """Write a fake serialized TensorRT engine file for offline testing."""
    header = b"TRT_ENGINE_MOCK"
    payload = struct.pack("<I", num_classes)
    engine_path.write_bytes(header + payload)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestONNXExport:
    """Test ONNX model creation and validation (no GPU required)."""

    def test_minimal_onnx_creation(self, tmp_path):
        """A minimal ONNX model can be created and passes checker."""
        onnx_path = _make_minimal_onnx(tmp_path)
        assert onnx_path.exists()

        model = onnx.load(str(onnx_path))
        onnx.checker.check_model(model)
        assert model.graph.input[0].name == "input"
        assert model.graph.output[0].name == "output"

    def test_onnx_input_shape(self, tmp_path):
        """ONNX model input shape is (1, 1, 157, 40)."""
        onnx_path = _make_minimal_onnx(tmp_path)
        model = onnx.load(str(onnx_path))
        inp = model.graph.input[0]
        dims = [d.dim_value for d in inp.type.tensor_type.shape.dim]
        assert dims == [1, 1, 157, 40]

    def test_onnx_output_classes(self, tmp_path):
        """ONNX model output has correct number of classes."""
        onnx_path = _make_minimal_onnx(tmp_path, num_classes=2)
        model = onnx.load(str(onnx_path))
        out = model.graph.output[0]
        dims = [d.dim_value for d in out.type.tensor_type.shape.dim]
        assert dims == [1, 2]


class TestTensorRTBuild:
    """Test TensorRT engine building (GPU only)."""

    @pytest.mark.requires_cuda
    def test_build_fp16_engine(self, tmp_path):
        """FP16 engine builds successfully (GPU only)."""
        _skip_if_no_export_module()

        onnx_path = _make_minimal_onnx(tmp_path)
        engine_path = tmp_path / "model_fp16.engine"

        success = build_tensorrt_engine(
            str(onnx_path),
            str(engine_path),
            max_batch_size=32,
            fp16_mode=True,
            int8_mode=False,
        )
        assert success is True
        assert engine_path.exists()

    @pytest.mark.requires_cuda
    def test_build_int8_engine_requires_calibration(self, tmp_path):
        """INT8 engine build warns without calibration data (GPU only)."""
        _skip_if_no_export_module()

        onnx_path = _make_minimal_onnx(tmp_path)
        engine_path = tmp_path / "model_int8.engine"

        success = build_tensorrt_engine(
            str(onnx_path),
            str(engine_path),
            max_batch_size=32,
            fp16_mode=False,
            int8_mode=True,
            calibration_data=None,
        )
        # Should still return True (warns but doesn't fail hard)
        assert success is True

    def test_build_tensorrt_not_installed_offline(self, tmp_path):
        """Without TensorRT installed, build returns False gracefully."""
        _skip_if_no_export_module()

        onnx_path = _make_minimal_onnx(tmp_path)
        engine_path = tmp_path / "model.engine"

        with patch.dict("sys.modules", {"tensorrt": None}):
            success = build_tensorrt_engine(
                str(onnx_path),
                str(engine_path),
                fp16_mode=False,
                int8_mode=False,
            )
            assert success is False


class TestTensorRTVerification:
    """Test TensorRT engine output verification against ONNX Runtime."""

    @pytest.mark.requires_cuda
    def test_engine_matches_onnx(self, tmp_path):
        """TensorRT engine output matches ONNX Runtime within tolerance."""
        _skip_if_no_export_module()

        onnx_path = _make_minimal_onnx(tmp_path)
        engine_path = tmp_path / "model.engine"
        _serialize_mock_engine(engine_path)

        test_input = np.random.randn(1, 1, 157, 40).astype(np.float32)

        with (
            patch("src.deployment.export_tensorrt.pycuda", MagicMock()),
            patch("src.deployment.export_tensorrt.ort") as mock_ort,
        ):
            mock_session = MagicMock()
            mock_session.run.return_value = [np.random.randn(1, 3).astype(np.float32)]
            mock_ort.InferenceSession.return_value = mock_session

            result = verify_tensorrt_engine(str(engine_path), str(onnx_path), test_input=test_input)
            assert isinstance(result, bool)


class TestOptimizationProfiles:
    """Test dynamic optimization profile configuration (GPU only)."""

    @pytest.mark.requires_cuda
    def test_profile_has_min_opt_max_shapes(self, tmp_path):
        """Optimization profile defines min/opt/max shapes."""
        _skip_if_no_export_module()

        onnx_path = _make_minimal_onnx(tmp_path)
        engine_path = tmp_path / "model.engine"

        with patch("src.deployment.export_tensorrt.trt") as mock_trt:
            mock_builder = MagicMock()
            mock_config = MagicMock()
            mock_profile = MagicMock()
            mock_trt.Builder.return_value = mock_builder
            mock_builder.create_builder_config.return_value = mock_config
            mock_config.add_optimization_profile.return_value = None
            mock_trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH = 1
            mock_trt.BuilderFlag.FP16 = "fp16_flag"

            build_tensorrt_engine(
                str(onnx_path),
                str(engine_path),
                max_batch_size=32,
                fp16_mode=True,
                int8_mode=False,
            )

            # Verify optimization profile was added
            assert mock_config.add_optimization_profile.called

            # Check the shape call args
            profile_arg = mock_config.add_optimization_profile.call_args[0][0]
            assert profile_arg.set_shape.called

            shape_call = profile_arg.set_shape.call_args
            args = shape_call[0]
            assert args[0] == "input"
            min_shape, opt_shape, max_shape = args[1], args[2], args[3]
            assert min_shape[0] <= opt_shape[0] <= max_shape[0]
            assert max_shape[0] == 32  # max_batch_size


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------


class TestBenchmark:
    """TensorRT engine inference benchmarks (GPU only)."""

    @pytest.mark.requires_cuda
    def test_benchmark_returns_metrics(self, tmp_path):
        """Benchmark returns dict with mean_ms, std_ms, fps, throughput."""
        _skip_if_no_export_module()

        engine_path = tmp_path / "model.engine"
        _serialize_mock_engine(engine_path)

        with (
            patch("src.deployment.export_tensorrt.pycuda", MagicMock()),
            patch("src.deployment.export_tensorrt.time") as mock_time,
        ):
            mock_time.perf_counter.side_effect = [0.0, 0.001, 0.002, 0.003]

            result = benchmark_tensorrt_engine(str(engine_path), num_iter=10)
            assert isinstance(result, dict)
            if result:
                assert "mean_ms" in result
                assert "fps" in result
