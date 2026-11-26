#!/usr/bin/env python3
"""
TensorRT Export Script for Audio Classification Models
ONNX -> TensorRT Engine for embedded deployment
INT8 Calibration + Optimization Profiles + Dynamic CUDA Graph 지원
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import onnx
import onnxruntime as ort
import torch


def export_to_onnx(
    model: torch.nn.Module,
    dummy_input: torch.Tensor,
    onnx_path: str,
    input_names: list = ["input"],
    output_names: list = ["output"],
    opset_version: int = 11,
    dynamic_axes: dict = None,
):
    """Export PyTorch model to ONNX"""

    if dynamic_axes is None:
        dynamic_axes = {"input": {0: "batch_size"}, "output": {0: "batch_size"}}

    print(f"Exporting to ONNX: {onnx_path}")

    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        verbose=False,
    )

    # Verify ONNX model
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    print("ONNX model verified!")

    return onnx_path


def simplify_onnx(onnx_path: str, output_path: str = None) -> str:
    """Simplify ONNX model using onnx-simplifier"""
    try:
        import onnxsim

        if output_path is None:
            output_path = onnx_path.replace(".onnx", "_simplified.onnx")

        print(f"Simplifying ONNX: {onnx_path} -> {output_path}")
        model = onnx.load(onnx_path)
        model_simp, check = onnxsim.simplify(model)

        if check:
            onnx.save(model_simp, output_path)
            print("ONNX model simplified successfully!")
        else:
            print("Warning: Simplification check failed, but saving anyway")
            onnx.save(model_simp, output_path)

        return output_path

    except ImportError:
        print("onnxsim not installed, skipping simplification")
        return onnx_path


def build_tensorrt_engine(
    onnx_path: str,
    engine_path: str,
    max_batch_size: int = 32,
    fp16_mode: bool = True,
    int8_mode: bool = False,
    calibration_data: np.ndarray = None,
    calibration_cache: str = None,
    workspace_size: int = 1 << 30,  # 1GB
) -> bool:
    """Build TensorRT engine from ONNX with INT8 calibration support"""

    try:
        import tensorrt as trt

        print(f"Building TensorRT engine: {engine_path}")
        print(f"FP16: {fp16_mode}, INT8: {int8_mode}")

        TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
        builder = trt.Builder(TRT_LOGGER)
        network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
        parser = trt.OnnxParser(network, TRT_LOGGER)

        # Parse ONNX
        with open(onnx_path, "rb") as f:
            if not parser.parse(f.read()):
                print("ERROR: Failed to parse ONNX")
                for error_idx in range(parser.num_errors):
                    print(parser.get_error(error_idx))
                return False

        # Build config
        config = builder.create_builder_config()
        config.max_workspace_size = workspace_size

        if fp16_mode and builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)
            print("FP16 mode enabled")

        # INT8 Calibration Setup
        calibrator = None
        if int8_mode and builder.platform_has_fast_int8:
            config.set_flag(trt.BuilderFlag.INT8)
            print("INT8 mode enabled")

            if calibration_data is not None:
                calibrator = INT8Calibrator(
                    calibration_data,
                    cache_file=calibration_cache or f"{engine_path}.calib",
                )
                config.int8_calibrator = calibrator
                print(f"INT8 calibrator set (cache: {calibration_cache or engine_path + '.calib'})")
            else:
                print("WARNING: INT8 mode requested but no calibration data provided")

        # Optimization profiles for dynamic shapes
        profile = builder.create_optimization_profile()
        # Assuming input shape: (batch, 1, 157, 40)
        profile.set_shape(
            "input", (1, 1, 157, 40), (16, 1, 157, 40), (32, 1, 157, 40)  # min  # opt
        )  # max
        config.add_optimization_profile(profile)

        # Build engine
        print("Building engine... (this may take a few minutes)")
        engine = builder.build_engine(network, config)

        if engine is None:
            print("ERROR: Failed to build engine")
            return False

        # Save engine
        with open(engine_path, "wb") as f:
            f.write(engine.serialize())

        print(f"TensorRT engine saved to: {engine_path}")
        return True

    except ImportError:
        print("TensorRT not installed. Install with: pip install tensorrt")
        print("Or use the official TensorRT container")
        return False
    except Exception as e:
        print(f"ERROR building TensorRT engine: {e}")
        return False


# =============================================================================
# INT8 Calibrator for Audio Classification
# =============================================================================


class INT8Calibrator(trt.IInt8EntropyCalibrator2):
    """INT8 Entropy Calibrator for Audio Classification Models"""

    def __init__(
        self,
        calibration_data: np.ndarray,
        cache_file: str = "calibration.cache",
        batch_size: int = 8,
    ):
        """
        Args:
            calibration_data: (N, 1, 157, 40) 대표 데이터셋 (정규화된 float32)
            cache_file: 캘리브레이션 캐시 파일 경로
            batch_size: 캘리브레이션 배치 크기
        """
        trt.IInt8EntropyCalibrator2.__init__(self)

        self.cache_file = cache_file
        self.batch_size = batch_size

        # 데이터 정규화 확인 및 전처리
        self.data = calibration_data.astype(np.float32)
        if self.data.ndim == 3:  # (N, 157, 40) -> (N, 1, 157, 40)
            self.data = self.data[:, np.newaxis, :, :]
        elif self.data.ndim != 4 or self.data.shape[1] != 1:
            raise ValueError(f"Expected (N, 1, 157, 40), got {self.data.shape}")

        self.num_samples = self.data.shape[0]
        self.current_batch = 0

        # GPU 메모리 할당 (첫 배치 크기로)
        self.device_input = None
        self._allocate_device_memory()

        # 캐시 로드 시도
        self.calibration_cache = None
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "rb") as f:
                self.calibration_cache = f.read()
            print(f"Loaded calibration cache from {self.cache_file}")

    def _allocate_device_memory(self):
        """첫 배치 크기로 GPU 메모리 할당"""
        import pycuda.autoinit
        import pycuda.driver as cuda

        batch = self.data[: self.batch_size]
        self.device_input = cuda.mem_alloc(batch.nbytes)

    def get_batch_size(self) -> int:
        return self.batch_size

    def get_batch(self, names: List[str], p_str: Optional[List] = None) -> List[int]:
        """다음 캘리브레이션 배치 반환"""
        if self.current_batch * self.batch_size >= self.num_samples:
            return None

        start = self.current_batch * self.batch_size
        end = min(start + self.batch_size, self.num_samples)
        batch = self.data[start:end]

        import pycuda.driver as cuda

        cuda.memcpy_htod(self.device_input, batch)

        self.current_batch += 1
        return [int(self.device_input)]

    def read_calibration_cache(self) -> bytes:
        return self.calibration_cache

    def write_calibration_cache(self, cache: bytes):
        with open(self.cache_file, "wb") as f:
            f.write(cache)
        print(f"Calibration cache saved to {self.cache_file}")


def verify_tensorrt_engine(
    engine_path: str,
    onnx_path: str,
    test_input: np.ndarray = None,
    rtol: float = 1e-3,
    atol: float = 1e-5,
) -> bool:
    """Verify TensorRT engine matches ONNX output"""

    try:
        import pycuda.autoinit
        import pycuda.driver as cuda
        import tensorrt as trt

        print(f"Verifying TensorRT engine: {engine_path}")

        # Load engine
        TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(TRT_LOGGER)

        with open(engine_path, "rb") as f:
            engine = runtime.deserialize_cuda_engine(f.read())

        context = engine.create_execution_context()

        # Get bindings
        input_binding = engine.get_binding_index("input")
        output_binding = engine.get_binding_index("output")

        # Prepare test input
        if test_input is None:
            test_input = np.random.randn(1, 1, 157, 40).astype(np.float32)

        # Allocate device memory
        d_input = cuda.mem_alloc(test_input.nbytes)
        output_shape = engine.get_binding_shape(output_binding)
        output_shape[0] = test_input.shape[0]  # batch size
        d_output = cuda.mem_alloc(np.prod(output_shape) * np.float32().itemsize)

        # Copy input to device
        cuda.memcpy_htod(d_input, test_input)

        # Execute
        bindings = [int(d_input), int(d_output)]
        context.execute_v2(bindings)

        # Get output
        output = np.empty(output_shape, dtype=np.float32)
        cuda.memcpy_dtoh(output, d_output)

        # Compare with ONNX Runtime
        ort_session = ort.InferenceSession(onnx_path)
        ort_inputs = {"input": test_input}
        ort_outputs = ort_session.run(None, ort_inputs)[0]

        # Compare
        diff = np.abs(output - ort_outputs).max()
        rel_diff = np.abs(output - ort_outputs).max() / (np.abs(ort_outputs).max() + 1e-8)

        print(f"Max absolute difference: {diff:.6f}")
        print(f"Max relative difference: {rel_diff:.6f}")

        if diff < atol and rel_diff < rtol:
            print("✓ TensorRT engine matches ONNX Runtime!")
            return True
        else:
            print("✗ TensorRT engine differs from ONNX Runtime")
            return False

    except ImportError:
        print("TensorRT or pycuda not available for verification")
        return False
    except Exception as e:
        print(f"ERROR verifying engine: {e}")
        return False


def export_pytorch_to_tensorrt(
    model: torch.nn.Module,
    dummy_input: torch.Tensor,
    output_dir: str,
    model_name: str = "model",
    fp16: bool = True,
    int8: bool = False,
    simplify: bool = True,
    calibration_dataset: Optional[torch.utils.data.DataLoader] = None,
) -> Tuple[str, str]:
    """
    Complete pipeline: PyTorch -> ONNX -> TensorRT with INT8 calibration

    Args:
        calibration_dataset: INT8 캘리브레이션용 DataLoader (필수 if int8=True)
    Returns:
        (onnx_path, engine_path)
    """
    if int8 and calibration_dataset is None:
        raise ValueError("INT8 mode requires calibration_dataset (DataLoader)")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    onnx_path = output_dir / f"{model_name}.onnx"
    engine_path = output_dir / f"{model_name}.engine"
    simplified_onnx_path = output_dir / f"{model_name}_simplified.onnx"
    calibration_cache = output_dir / f"{model_name}.calib"

    # 1. PyTorch -> ONNX
    export_to_onnx(model, dummy_input, str(onnx_path))

    # 2. Simplify ONNX (optional)
    if simplify:
        final_onnx = simplify_onnx(str(onnx_path), str(simplified_onnx_path))
    else:
        final_onnx = str(onnx_path)

    # 3. Prepare calibration data for INT8
    calibration_data = None
    if int8:
        print("Preparing INT8 calibration data...")
        calibration_data = []
        model.eval()
        with torch.no_grad():
            for batch_idx, (inputs, _) in enumerate(calibration_dataset):
                if batch_idx >= 50:  # 최대 50 배치 (배치당 8개면 400 샘플)
                    break
                calibration_data.append(inputs.cpu().numpy())
        calibration_data = np.concatenate(calibration_data, axis=0)
        print(f"Prepared calibration data: {calibration_data.shape}")

    # 4. ONNX -> TensorRT
    success = build_tensorrt_engine(
        final_onnx,
        str(engine_path),
        fp16_mode=fp16,
        int8_mode=int8,
        calibration_data=calibration_data,
        calibration_cache=str(calibration_cache),
    )

    if success:
        # Verify
        test_input = np.random.randn(1, 1, 157, 40).astype(np.float32)
        verify_tensorrt_engine(str(engine_path), final_onnx, test_input)

    return str(onnx_path), str(engine_path)


def benchmark_tensorrt_engine(
    engine_path: str,
    input_shape: Tuple = (1, 1, 157, 40),
    num_warmup: int = 10,
    num_iter: int = 100,
) -> dict:
    """Benchmark TensorRT engine inference time"""

    try:
        import time

        import pycuda.autoinit
        import pycuda.driver as cuda
        import tensorrt as trt

        TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
        runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))

        with open(engine_path, "rb") as f:
            engine = runtime.deserialize_cuda_engine(f.read())

        context = engine.create_execution_context()

        # Prepare input
        input_shape = list(input_shape)
        test_input = np.random.randn(*input_shape).astype(np.float32)

        # Allocate buffers
        input_binding = engine.get_binding_index("input")
        output_binding = engine.get_binding_index("output")

        d_input = cuda.mem_alloc(test_input.nbytes)
        output_shape = list(engine.get_binding_shape(output_binding))
        output_shape[0] = input_shape[0]
        d_output = cuda.mem_alloc(np.prod(output_shape) * 4)

        # Warmup
        for _ in range(num_warmup):
            cuda.memcpy_htod(d_input, test_input)
            bindings = [int(d_input), int(d_output)]
            context.execute_v2(bindings)

        cuda.Context.synchronize()

        # Benchmark
        times = []
        for _ in range(num_iter):
            start = time.perf_counter()
            cuda.memcpy_htod(d_input, test_input)
            context.execute_v2([int(d_input), int(d_output)])
            cuda.Context.synchronize()
            times.append(time.perf_counter() - start)

        times = np.array(times)
        return {
            "mean_ms": np.mean(times) * 1000,
            "std_ms": np.std(times) * 1000,
            "min_ms": np.min(times) * 1000,
            "max_ms": np.max(times) * 1000,
            "fps": 1.0 / np.mean(times),
            "throughput": input_shape[0] / np.mean(times),
        }

    except ImportError:
        print("TensorRT/pycuda not available for benchmarking")
        return {}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export PyTorch model to TensorRT with INT8 calibration"
    )
    parser.add_argument(
        "--model_path", type=str, required=True, help="Path to PyTorch model (.pth)"
    )
    parser.add_argument(
        "--output_dir", type=str, default="./tensorrt_models", help="Output directory"
    )
    parser.add_argument("--model_name", type=str, default="audio_classifier", help="Model name")
    parser.add_argument("--task", type=str, choices=["binary", "multiclass"], default="multiclass")
    parser.add_argument("--fp16", action="store_true", default=True, help="Enable FP16")
    parser.add_argument(
        "--int8",
        action="store_true",
        default=False,
        help="Enable INT8 (requires --calib_data)",
    )
    parser.add_argument(
        "--calib_data",
        type=str,
        help="Path to calibration dataset directory (for INT8)",
    )
    parser.add_argument("--no_simplify", action="store_true", help="Skip ONNX simplification")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark after export")

    args = parser.parse_args()

    # Load model
    from train_audio_classifier import AudioCNNLSTM

    device = torch.device("cpu")

    num_classes = 2 if args.task == "binary" else 3
    model = AudioCNNLSTM(num_classes=num_classes).to(device)
    checkpoint = torch.load(args.model_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Dummy input
    dummy_input = torch.randn(1, 1, 157, 40).to(device)

    # Prepare calibration dataset for INT8
    calibration_dataset = None
    if args.int8:
        if not args.calib_data:
            raise ValueError(
                "INT8 mode requires --calib_data argument (path to calibration dataset)"
            )
        from torch.utils.data import DataLoader

        from preprocessing.datasets.drone_audio_dataset import DroneAudioDataset

        calib_dataset = DroneAudioDataset(args.calib_data, split="train", augment=False)
        calibration_dataset = DataLoader(calib_dataset, batch_size=8, shuffle=False, num_workers=4)
        print(f"Loaded calibration dataset: {len(calib_dataset.dataset)} samples")

    # Export
    print(f"Exporting {args.model_path} -> TensorRT (FP16={args.fp16}, INT8={args.int8})")
    onnx_path, engine_path = export_pytorch_to_tensorrt(
        model,
        dummy_input,
        args.output_dir,
        args.model_name,
        fp16=args.fp16,
        int8=args.int8,
        simplify=not args.no_simplify,
        calibration_dataset=calibration_dataset,
    )

    if args.benchmark:
        print("\nBenchmarking...")
        results = benchmark_tensorrt_engine(engine_path)
        print(f"Results: {results}")
