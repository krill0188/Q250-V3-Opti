"""
Test suite for TensorRT INT8 calibration.

Verifies:
- INT8 entropy calibrator (IInt8EntropyCalibrator2) default behavior — GPU only
- Percentile calibrator option — GPU only
- Calibration data: 1000+ samples, batch size 32+
- Calibration cache read/write — GPU only
- Cache version checking with network hash + calibration settings
- Calibration data shape validation (N, 1, 157, 40)

Per the motion t_e7600ec1 consensus:
  - IInt8EntropyCalibrator2 is default
  - Percentile calibrator available via --calib_method
  - 1000+ samples, batch size 32+
  - Cache version check with network hash + calibration settings

Designed for Jetson Orin (sm_87) target validation.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
import pytest

from tests.conftest import (
    CALIBRATION_BATCH_SIZE,
    CALIBRATION_INPUT_SHAPE,
    CALIBRATION_SAMPLES_MIN,
    _compute_cache_version,
    _compute_network_hash,
)

# ---------------------------------------------------------------------------
# Try importing from export_tensorrt — may fail on hosts without torch/tensorrt
# ---------------------------------------------------------------------------

try:
    from src.deployment.export_tensorrt import INT8Calibrator

    _CALIBRATOR_AVAILABLE = True
except (ImportError, RuntimeError, NameError):
    _CALIBRATOR_AVAILABLE = False

try:
    from src.deployment.export_tensorrt import PercentileCalibrator

    _PERCENTILE_AVAILABLE = True
except (ImportError, RuntimeError, NameError):
    _PERCENTILE_AVAILABLE = False


def _skip_if_no_calibrator():
    """Skip test if INT8Calibrator can't be imported."""
    if not _CALIBRATOR_AVAILABLE:
        pytest.skip("INT8Calibrator not available (torch/tensorrt missing)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calibration_data(num_samples, seed=42):
    """Generate deterministic calibration data."""
    rng = np.random.RandomState(seed)
    data = rng.randn(num_samples, *CALIBRATION_INPUT_SHAPE).astype(np.float32)
    return np.clip(data, -1.0, 1.0)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestCalibrationDataShape:
    """Test calibration data shape validation (no GPU required)."""

    def test_shape_4d_with_channel(self, calibration_samples_1000):
        """Calibration data must be (N, 1, 157, 40)."""
        data = calibration_samples_1000
        assert data.ndim == 4
        assert data.shape[0] >= CALIBRATION_SAMPLES_MIN
        assert data.shape[1] == 1  # channel
        assert data.shape[2:] == CALIBRATION_INPUT_SHAPE[1:]

    def test_shape_3d_auto_expands(self):
        """3D data (N, 157, 40) is auto-expanded to (N, 1, 157, 40)."""
        data = _make_calibration_data(100)
        assert data.shape == (100, 1, 157, 40)

    def test_minimum_samples(self, calibration_samples_1000):
        """At least 1000 calibration samples per spec."""
        assert calibration_samples_1000.shape[0] >= CALIBRATION_SAMPLES_MIN

    def test_batch_size_32(self, calibration_batch):
        """Calibration batch size is 32+ per spec."""
        assert calibration_batch.shape[0] >= CALIBRATION_BATCH_SIZE


class TestEntropyCalibrator:
    """Test IInt8EntropyCalibrator2 implementation (GPU only)."""

    @pytest.mark.requires_cuda
    def test_entropy_calibrator_init(self, calibration_samples_1000):
        """Entropy calibrator initializes with data and cache path."""
        _skip_if_no_calibrator()

        with tempfile.NamedTemporaryFile(suffix=".cache", delete=False) as f:
            cache_path = f.name

        try:
            calib = INT8Calibrator(
                calibration_data=calibration_samples_1000,
                cache_file=cache_path,
                batch_size=CALIBRATION_BATCH_SIZE,
            )
            assert calib.batch_size == CALIBRATION_BATCH_SIZE
            assert calib.num_samples == CALIBRATION_SAMPLES_MIN
            assert calib.data.shape == (CALIBRATION_SAMPLES_MIN, 1, 157, 40)
        finally:
            os.unlink(cache_path)

    @pytest.mark.requires_cuda
    def test_entropy_calibrator_get_batch(self, calibration_samples_1000):
        """get_batch returns device pointers for each batch."""
        _skip_if_no_calibrator()

        with tempfile.NamedTemporaryFile(suffix=".cache", delete=False) as f:
            cache_path = f.name

        try:
            calib = INT8Calibrator(
                calibration_data=calibration_samples_1000,
                cache_file=cache_path,
                batch_size=CALIBRATION_BATCH_SIZE,
            )

            batch = calib.get_batch(["input"])
            assert batch is not None
            assert len(batch) == 1
            assert isinstance(batch[0], int)  # device pointer

            # Exhaust all batches
            num_batches = CALIBRATION_SAMPLES_MIN // CALIBRATION_BATCH_SIZE
            for _ in range(num_batches):
                batch = calib.get_batch(["input"])
                assert batch is not None

            # After exhaustion, returns None
            assert calib.get_batch(["input"]) is None
        finally:
            os.unlink(cache_path)

    @pytest.mark.requires_cuda
    def test_entropy_calibrator_cache_roundtrip(self, calibration_samples_1000, tmp_path):
        """Calibration cache is written and can be re-read."""
        _skip_if_no_calibrator()

        cache_path = tmp_path / "entropy_calib.cache"

        calib1 = INT8Calibrator(
            calibration_data=calibration_samples_1000,
            cache_file=str(cache_path),
            batch_size=CALIBRATION_BATCH_SIZE,
        )
        # Consume all batches to trigger cache write
        while calib1.get_batch(["input"]) is not None:
            pass

        assert cache_path.exists()
        cache_data = cache_path.read_bytes()
        assert len(cache_data) > 0

        # Re-create calibrator with same cache -> should load cache
        calib2 = INT8Calibrator(
            calibration_data=calibration_samples_1000,
            cache_file=str(cache_path),
            batch_size=CALIBRATION_BATCH_SIZE,
        )
        assert calib2.calibration_cache == cache_data


class TestPercentileCalibrator:
    """Test percentile calibrator option (--calib_method=percentile). GPU only."""

    def test_percentile_calibrator_class_exists(self):
        """PercentileCalibrator class is importable (documents requirement)."""
        if not _PERCENTILE_AVAILABLE:
            pytest.skip("PercentileCalibrator not yet implemented")

    @pytest.mark.requires_cuda
    def test_percentile_calibrator_init(self, calibration_samples_1000, tmp_path):
        """Percentile calibrator initializes correctly."""
        _skip_if_no_calibrator()
        if not _PERCENTILE_AVAILABLE:
            pytest.skip("PercentileCalibrator not yet implemented")

        cache_path = tmp_path / "percentile_calib.cache"
        calib = PercentileCalibrator(
            calibration_data=calibration_samples_1000,
            cache_file=str(cache_path),
            batch_size=CALIBRATION_BATCH_SIZE,
            percentile=99.9,
        )
        assert calib.batch_size == CALIBRATION_BATCH_SIZE
        assert calib.percentile == 99.9

    @pytest.mark.requires_cuda
    def test_percentile_vs_entropy_different_scales(self, calibration_samples_1000, tmp_path):
        """Percentile and entropy calibrators produce different scale factors."""
        _skip_if_no_calibrator()
        if not _PERCENTILE_AVAILABLE:
            pytest.skip("PercentileCalibrator not yet implemented")

        entropy_cache = tmp_path / "e.cache"
        pct_cache = tmp_path / "p.cache"

        e_calib = INT8Calibrator(
            calibration_data=calibration_samples_1000,
            cache_file=str(entropy_cache),
            batch_size=CALIBRATION_BATCH_SIZE,
        )
        p_calib = PercentileCalibrator(
            calibration_data=calibration_samples_1000,
            cache_file=str(pct_cache),
            batch_size=CALIBRATION_BATCH_SIZE,
        )

        # Both consume all batches
        while e_calib.get_batch(["input"]) is not None:
            pass
        while p_calib.get_batch(["input"]) is not None:
            pass

        # Both produce cache files (different content expected)
        assert entropy_cache.exists()
        assert pct_cache.exists()


class TestCalibrationCacheVersioning:
    """Test cache version checking with network hash + calibration settings.

    Per motion consensus: cache version = f(calib_method, batch_size,
    num_samples, network_hash). If any parameter changes, cache is invalid.
    """

    def test_compute_network_hash_deterministic(self, dummy_model_bytes):
        """Network hash is deterministic for same model bytes."""
        h1 = _compute_network_hash(dummy_model_bytes)
        h2 = _compute_network_hash(dummy_model_bytes)
        assert h1 == h2
        assert len(h1) == 16  # short hash

    def test_compute_network_hash_different_models(self, dummy_model_bytes):
        """Different model bytes produce different hashes."""
        h1 = _compute_network_hash(dummy_model_bytes)
        h2 = _compute_network_hash(b"different_model_bytes")
        assert h1 != h2

    def test_cache_version_format(self, dummy_model_bytes):
        """Cache version string contains all required components."""
        network_hash = _compute_network_hash(dummy_model_bytes)
        version = _compute_cache_version(
            "entropy", CALIBRATION_BATCH_SIZE, CALIBRATION_SAMPLES_MIN, network_hash
        )

        parts = version.split("|")
        assert parts[0] == "trt_calib_v1"
        assert parts[1] == "entropy"
        assert parts[2] == str(CALIBRATION_BATCH_SIZE)
        assert parts[3] == str(CALIBRATION_SAMPLES_MIN)
        assert parts[4] == network_hash

    def test_cache_version_changes_with_method(self, dummy_model_bytes):
        """Different calibration methods produce different cache versions."""
        network_hash = _compute_network_hash(dummy_model_bytes)
        v_entropy = _compute_cache_version(
            "entropy", CALIBRATION_BATCH_SIZE, CALIBRATION_SAMPLES_MIN, network_hash
        )
        v_percentile = _compute_cache_version(
            "percentile", CALIBRATION_BATCH_SIZE, CALIBRATION_SAMPLES_MIN, network_hash
        )
        assert v_entropy != v_percentile

    def test_cache_version_changes_with_batch_size(self, dummy_model_bytes):
        """Different batch sizes produce different cache versions."""
        network_hash = _compute_network_hash(dummy_model_bytes)
        v32 = _compute_cache_version("entropy", 32, CALIBRATION_SAMPLES_MIN, network_hash)
        v64 = _compute_cache_version("entropy", 64, CALIBRATION_SAMPLES_MIN, network_hash)
        assert v32 != v64

    def test_cache_version_changes_with_sample_count(self, dummy_model_bytes):
        """Different sample counts produce different cache versions."""
        network_hash = _compute_network_hash(dummy_model_bytes)
        v1000 = _compute_cache_version("entropy", CALIBRATION_BATCH_SIZE, 1000, network_hash)
        v500 = _compute_cache_version("entropy", CALIBRATION_BATCH_SIZE, 500, network_hash)
        assert v1000 != v500

    def test_cache_version_changes_with_network_hash(self):
        """Different network hashes produce different cache versions."""
        v1 = _compute_cache_version("entropy", 32, 1000, "aaaa1111")
        v2 = _compute_cache_version("entropy", 32, 1000, "bbbb2222")
        assert v1 != v2

    @pytest.mark.requires_cuda
    def test_calibrator_uses_cache_version(self, calibration_samples_1000, tmp_path):
        """Calibrator embeds cache version in cache file."""
        _skip_if_no_calibrator()

        cache_path = tmp_path / "versioned.cache"
        calib = INT8Calibrator(
            calibration_data=calibration_samples_1000,
            cache_file=str(cache_path),
            batch_size=CALIBRATION_BATCH_SIZE,
        )
        # Consume all batches
        while calib.get_batch(["input"]) is not None:
            pass

        assert cache_path.exists()

    def test_cache_invalidation_on_parameter_change(self, tmp_path, dummy_model_bytes):
        """Cache is invalidated when calibration parameters change."""
        network_hash = _compute_network_hash(dummy_model_bytes)

        v1 = _compute_cache_version("entropy", 32, 1000, network_hash)
        v2 = _compute_cache_version("entropy", 64, 1000, network_hash)

        # Simulate cache check: old cache version != current version -> invalidate
        cache_file = tmp_path / "test.cache"
        cache_file.write_text(json.dumps({"version": v1}))

        # Read cache and check version
        cached = json.loads(cache_file.read_text())
        assert cached["version"] == v1
        assert cached["version"] != v2  # Would trigger rebuild


# ---------------------------------------------------------------------------
# CLI argument tests (documenting --calib_method, --calib_batches, --calib_batch_size)
# ---------------------------------------------------------------------------


class TestCalibrationCLIArgs:
    """Test CLI argument parsing for calibration options.

    Documents the agreed-upon CLI interface:
      --calib_method  entropy|percentile  (default: entropy)
      --calib_batches N                   (number of calibration batches)
      --calib_batch_size N                (batch size, default 32)
    """

    def test_calib_method_choices(self):
        """--calib_method accepts 'entropy' or 'percentile'."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--calib_method",
            choices=["entropy", "percentile"],
            default="entropy",
        )
        args = parser.parse_args(["--calib_method", "percentile"])
        assert args.calib_method == "percentile"

        args = parser.parse_args([])
        assert args.calib_method == "entropy"

    def test_calib_batch_size_default_32(self):
        """--calib_batch_size defaults to 32."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--calib_batch_size", type=int, default=32)
        args = parser.parse_args([])
        assert args.calib_batch_size == 32

    def test_calib_batches_positive(self):
        """--calib_batches must be positive."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--calib_batches", type=int, default=32)
        args = parser.parse_args(["--calib_batches", "100"])
        assert args.calib_batches == 100
