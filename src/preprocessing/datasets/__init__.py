"""
PyTorch Dataset 클래스들
전처리된 데이터를 PyTorch 학습용으로 제공
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path
from abc import ABC, abstractmethod
import numpy as np

# torch는 완전 지연 import (numpy 2.x 충돌 방지)
_TORCH_LOADED = False
_torch = None
_DataLoader = None
_F = None


def _load_torch():
    """torch를 실제로 필요할 때만 import"""
    global _TORCH_LOADED, _torch, _DataLoader, _F
    if _TORCH_LOADED:
        return
    try:
        import torch as t
        from torch.utils.data import DataLoader as DL
        import torch.nn.functional as F

        _torch = t
        _DataLoader = DL
        _F = F
        _TORCH_LOADED = True
    except ImportError:
        pass


# 베이스 클래스 해결을 위한 메타클래스
class _LazyDatasetMeta(type):
    """Dataset 베이스 클래스를 torch 로드 시점에 동적으로 결정"""

    def __new__(mcs, name, bases, namespace):
        # object를 Dataset으로 치환
        new_bases = tuple(
            _torch.utils.data.Dataset if b is object and _torch is not None else b
            for b in bases
        )
        return super().__new__(mcs, name, new_bases, namespace)


# 베이스 클래스로 object 사용 (나중에 메타클래스가 치환)
_DatasetBase = object

from ..core.base_loader import SensorData, MultiSensorData
from ..config import DatasetConfig, DataSplit


@dataclass
class SequenceSample:
    """시계열 시퀀스 샘플"""

    sequence: torch.Tensor  # (seq_len, n_features)
    target: Optional[torch.Tensor]  # (target_len, n_targets) 또는 스칼라
    metadata: Dict = None  # 타임스탬프, 센서 정보 등
    sensor_name: str = ""  # 센서 이름

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseSequenceDataset(_DatasetBase, metaclass=_LazyDatasetMeta):
    """시계열 시퀀스 데이터셋 기본 클래스"""

    def __init__(
        self,
        data_dir: Path,
        split: str = "train",
        seq_len: int = 100,
        stride: int = 1,
        target_len: int = 1,
        target_features: Optional[List[str]] = None,
        feature_columns: Optional[List[str]] = None,
        normalize: bool = True,
        scaler_path: Optional[str] = None,
    ):
        """
        Args:
            data_dir: 처리된 데이터 디렉토리
            split: "train", "val", "test"
            seq_len: 입력 시퀀스 길이
            stride: 슬라이딩 윈도우 스트라이드
            target_len: 타겟 시퀀스 길이
            target_features: 타겟으로 사용할 피처 이름들
            feature_columns: 입력으로 사용할 피처 이름들
            normalize: 정규화 여부
            scaler_path: 스케일러 경로
        """
        _load_torch()
        if _torch is None:
            raise ImportError("PyTorch is required for BaseSequenceDataset")
        self.data_dir = Path(data_dir)
        self.split = split
        self.seq_len = seq_len
        self.stride = stride
        self.target_len = target_len
        self.target_features = target_features
        self.feature_columns = feature_columns
        self.normalize = normalize

        self.data_dir = Path(data_dir)
        self.split_dir = self.data_dir / split

        # 메타데이터 로드
        import json

        metadata_path = self.split_dir / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")

        with open(metadata_path, "r") as f:
            self.metadata = json.load(f)

        # 데이터 로드
        self._load_data()
        self._create_windows()

    def _load_data(self):
        """NPZ 파일 로드 (청크 파일 지원)"""
        self.sensor_data = {}
        for sensor_name, meta in self.metadata["sensors"].items():
            # 청크 파일들 찾기 (.chunk_*.npz)
            chunk_files = sorted(self.split_dir.glob(f".chunk_*.npz"))
            if chunk_files:
                # 청크 파일들에서 해당 센서 데이터 추출하여 결합
                self._load_from_chunks(sensor_name, chunk_files)
            else:
                # 단일 파일 방식 (기존)
                npz_path = self.split_dir / f"{sensor_name}.npz"
                if not npz_path.exists():
                    raise FileNotFoundError(f"Data file not found: {npz_path}")
                data = np.load(npz_path)
                self._raw_data[sensor_name] = {
                    "timestamp": data["timestamp"],
                    "data": data["data"],
                    "columns": data["columns"].tolist(),
                    "frequency_hz": float(data["frequency_hz"]),
                    "coordinate_frame": str(data["coordinate_frame"]),
                }

    def _load_from_chunks(self, sensor_name: str, chunk_files: List[Path]):
        """청크 파일들에서 센서 데이터 로드 및 결합"""
        all_timestamps = []
        all_data = []
        columns = None
        frequency_hz = None
        coordinate_frame = None

        for cf in chunk_files:
            data = np.load(cf)
            if sensor_name == "audio":
                all_data.append(data["audio"])
            elif sensor_name == "label":
                all_data.append(data["label"])
            else:
                # 다른 센서는 chunk 파일에 없을 수 있음
                continue
            all_timestamps.append(data["timestamp"])

        if not all_data:
            raise ValueError(f"No data found for sensor {sensor_name} in chunk files")

        combined_data = np.vstack(all_data)
        combined_timestamps = np.concatenate(all_timestamps)

        self._raw_data[sensor_name] = {
            "timestamp": combined_timestamps,
            "data": combined_data,
            "columns": (
                [f"sample_{i}" for i in range(combined_data.shape[1])]
                if sensor_name == "audio"
                else ["label"]
            ),
            "frequency_hz": 16000.0 if sensor_name == "audio" else 1.0,
            "coordinate_frame": "TIME" if sensor_name == "audio" else "NONE",
        }

    def _create_windows(self):
        """슬라이딩 윈도우 생성"""
        self.windows = []

        # 센서별 윈도우 생성
        for sensor_name, data_dict in self._raw_data.items():
            data = data_dict["data"]
            timestamps = data_dict["timestamp"]
            n_samples = len(data)

            if n_samples < self.seq_len + self.target_len:
                continue

            # 슬라이딩 윈도우
            for i in range(
                0, n_samples - self.seq_len - self.target_len + 1, self.stride
            ):
                seq_start = i
                seq_end = i + self.seq_len
                target_end = i + self.seq_len + self.target_len

                self.windows.append(
                    {
                        "sensor": sensor_name,
                        "seq_start": seq_start,
                        "seq_end": seq_end,
                        "target_end": target_end,
                    }
                )

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        window = self.windows[idx]
        sensor_name = window["sensor"]
        data_dict = self._raw_data[sensor_name]

        data = data_dict["data"]
        seq_start = window["seq_start"]
        seq_end = window["seq_end"]
        target_end = window["target_end"]

        # 입력 시퀀스
        x = data[seq_start:seq_end].astype(np.float32)

        # 타겟 (기본: 다음 스텝 예측)
        y = data[seq_end:target_end].astype(np.float32)

        return torch.from_numpy(x), torch.from_numpy(y)


class MultiSensorDataset(_DatasetBase, metaclass=_LazyDatasetMeta):
    """멀티센서 동기화 데이터셋"""

    def __init__(
        self,
        data_dir: Path,
        split: str = "train",
        seq_len: int = 100,
        stride: int = 1,
        target_len: int = 1,
        reference_sensor: str = "gps",
        target_sensor: Optional[str] = None,
        sync_tolerance_sec: float = 0.01,
    ):
        """
        멀티센서 동기화 데이터셋

        Args:
            data_dir: 데이터 디렉토리
            split: "train", "val", "test"
            seq_len: 입력 시퀀스 길이
            stride: 스트라이드
            target_len: 타겟 길이
            reference_sensor: 기준 센서
            target_sensor: 타겟 센서 (None이면 reference_sensor와 동일)
        """
        _load_torch()
        if _torch is None:
            raise ImportError("PyTorch is required for MultiSensorDataset")
        self.data_dir = Path(data_dir)
        self.split = split
        self.seq_len = seq_len
        self.stride = stride
        self.target_len = target_len
        self.reference_sensor = reference_sensor
        self.target_sensor = target_sensor or reference_sensor

        self.data_dir = Path(data_dir)
        self.split_dir = self.data_dir / split

        # 메타데이터 로드
        import json

        with open(self.split_dir / "metadata.json", "r") as f:
            self.metadata = json.load(f)

        # 데이터 로드 및 동기화
        self._load_and_sync()
        self._create_windows()

    def _load_and_sync(self):
        """데이터 로드 및 동기화 (청크 파일 지원)"""
        self.sensor_data = {}
        for sensor_name, meta in self.metadata["sensors"].items():
            # 청크 파일들 찾기
            chunk_files = sorted(self.split_dir.glob(f".chunk_*.npz"))
            if chunk_files:
                self._load_sensor_from_chunks(sensor_name, chunk_files)
            else:
                # 단일 파일 방식 (기존)
                npz_path = self.split_dir / f"{sensor_name}.npz"
                if not npz_path.exists():
                    raise FileNotFoundError(f"Data file not found: {npz_path}")
                data = np.load(npz_path)
                self._raw_data[sensor_name] = {
                    "timestamp": data["timestamp"],
                    "data": data["data"],
                    "columns": data["columns"].tolist(),
                    "frequency_hz": float(data["frequency_hz"]),
                    "coordinate_frame": str(data["coordinate_frame"]),
                }

    def _load_sensor_from_chunks(self, sensor_name: str, chunk_files: List[Path]):
        """청크 파일들에서 센서 데이터 로드"""
        all_timestamps = []
        all_data = []

        for cf in chunk_files:
            data = np.load(cf)
            if sensor_name == "audio":
                all_data.append(data["audio"])
            elif sensor_name == "label":
                all_data.append(data["label"])
            else:
                continue
            all_timestamps.append(data["timestamp"])

        if not all_data:
            raise ValueError(f"No data found for sensor {sensor_name} in chunk files")

        combined_data = np.vstack(all_data)
        combined_timestamps = np.concatenate(all_timestamps)

        self._raw_data[sensor_name] = {
            "timestamp": combined_timestamps,
            "data": combined_data,
            "columns": (
                [f"sample_{i}" for i in range(combined_data.shape[1])]
                if sensor_name == "audio"
                else ["label"]
            ),
            "frequency_hz": 16000.0 if sensor_name == "audio" else 1.0,
            "coordinate_frame": "TIME" if sensor_name == "audio" else "NONE",
        }

        # 기준 센서 타임스탬프 기준 동기화
        ref_data = self._raw_data[self.reference_sensor]
        ref_time = ref_data["timestamp"]

        self.synced_data = {}
        for name, data_dict in self._raw_data.items():
            if name == self.reference_sensor:
                self.synced_data[name] = {
                    "timestamp": ref_time,
                    "data": data_dict["data"],
                    "columns": data_dict["columns"],
                    "frequency_hz": float(data_dict["frequency_hz"]),
                }
                continue

            # 타임스탬프 정렬 (선형 보간)
            src_time = data_dict["timestamp"]
            src_data = data_dict["data"]

            # 타겟 시간축에 맞춰 보간
            interp_data = np.zeros(
                (
                    len(self._raw_data[self.reference_sensor]["timestamp"]),
                    src_data.shape[1],
                )
            )
            for i in range(src_data.shape[1]):
                interp_func = np.interp(
                    self._raw_data[self.reference_sensor]["timestamp"],
                    src_time,
                    src_data[:, i],
                )
                interp_data[:, i] = interp_func

            self.synced_data[name] = {
                "timestamp": ref_time,
                "data": interp_data,
                "columns": data_dict["columns"],
                "frequency_hz": float(data_dict["frequency_hz"]),
            }

    def _create_windows(self):
        """슬라이딩 윈도우 생성"""
        self.windows = []

        ref_data = self.synced_data[self.reference_sensor]
        n_samples = len(ref_data["timestamp"])

        if n_samples < self.seq_len + 1:
            return

        for i in range(0, n_samples - self.seq_len, self.stride):
            self.windows.append(
                {
                    "start": i,
                    "end": i + self.seq_len,
                }
            )

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        window = self.windows[idx]
        start = window["start"]
        end = window["end"]

        # 멀티센서 입력 생성
        inputs = {}
        for name, data_dict in self.synced_data.items():
            inputs[name] = torch.from_numpy(
                data_dict["data"][start:end].astype(np.float32)
            )

        # 타겟 (기본: reference sensor의 다음 스텝)
        target_data = self.synced_data[self.reference_sensor]["data"]
        target = torch.from_numpy(target_data[start:end].astype(np.float32))

        return {
            "inputs": inputs,
            "target": target,
            "timestamps": torch.from_numpy(
                self.synced_data[self.reference_sensor]["timestamp"][start:end]
            ),
        }


class MultimodalDataset(_DatasetBase, metaclass=_LazyDatasetMeta):
    """멀티모달 데이터셋 (이미지 + IMU + GPS + 오디오 등)"""

    def __init__(
        self,
        data_dir: Path,
        split: str = "train",
        modalities: List[str] = None,
        seq_len: int = 100,
        sync_method: str = "interpolate",
    ):
        """
        Args:
            modalities: ["image", "imu", "gps", "audio", "event"]
        """
        _load_torch()
        if _torch is None:
            raise ImportError("PyTorch is required for MultimodalDataset")
        self.data_dir = Path(data_dir)
        self.split = split
        self.modalities = modalities or ["image", "imu", "gps"]
        self.seq_len = seq_len
        self.sync_method = sync_method

        # 각 모달리티별 데이터셋 생성
        self.modality_datasets = {}
        for mod in self.modalities:
            if mod == "image":
                self.modality_datasets[mod] = ImageSequenceDataset(
                    self.data_dir / split / "images", seq_len
                )
            elif mod == "imu":
                self.modality_datasets[mod] = IMUDataset(
                    self.data_dir / split / "imu", seq_len
                )
            # ... 기타 모달리티

        # 공통 길이 계산
        self.length = min(len(ds) for ds in self.modality_datasets.values())

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        sample = {}
        for mod, ds in self.modality_datasets.items():
            sample[mod] = ds[idx]
        return sample


class ImageSequenceDataset(_DatasetBase, metaclass=_LazyDatasetMeta):
    """이미지 시퀀스 데이터셋"""

    def __init__(self, data_dir: Path, seq_len: int = 16):
        _load_torch()
        if _torch is None:
            raise ImportError("PyTorch is required for ImageSequenceDataset")
        self.data_dir = Path(data_dir)
        self.seq_len = seq_len
        self.image_paths = sorted(self.data_dir.glob("*.jpg")) + sorted(
            self.data_dir.glob("*.png")
        )

        if len(self.image_paths) < seq_len:
            raise ValueError(f"Not enough images: {len(self.image_paths)} < {seq_len}")

    def __len__(self):
        return len(self.image_paths) - self.seq_len + 1

    def __getitem__(self, idx):
        # 시퀀스 로드
        frames = []
        for i in range(self.seq_len):
            img_path = self.image_paths[idx + i]
            # 이미지 로드 및 전처리
            import cv2

            img = cv2.imread(str(self.image_paths[idx + i]))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (224, 224))
            img = img.astype(np.float32) / 255.0
            frames.append(img)

        # (seq_len, C, H, W)
        return torch.from_numpy(np.stack(frames)).permute(0, 3, 1, 2)


class IMUDataset(_DatasetBase, metaclass=_LazyDatasetMeta):
    """IMU 데이터셋"""

    def __init__(self, data_dir: Path, seq_len: int = 100):
        _load_torch()
        if _torch is None:
            raise ImportError("PyTorch is required for IMUDataset")
        self.data_dir = Path(data_dir)
        self.seq_len = seq_len

        # NPZ 파일 로드
        npz_files = list(self.data_dir.glob("*.npz"))
        if not npz_files:
            raise ValueError(f"No NPZ files found in {data_dir}")

        # 첫 번째 파일 로드 (확장 필요)
        data = np.load(npz_files[0])
        self.data = data["data"]
        self.timestamps = data["timestamp"]
        self.columns = data["columns"].tolist()

        if len(self.data) < seq_len:
            raise ValueError(f"Not enough data: {len(self.data)} < {seq_len}")

    def __len__(self):
        return len(self.data) - self.seq_len + 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.seq_len]
        return _torch.from_numpy(x.astype(np.float32))


def create_dataloader(
    dataset: _DatasetBase,
    batch_size: int = 32,
    shuffle: bool = True,
    num_workers: int = 4,
    pin_memory: bool = True,
) -> _DataLoader:
    """DataLoader 생성 헬퍼"""
    _load_torch()
    if _DataLoader is None:
        raise ImportError("PyTorch is required for create_dataloader")
    return _DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=pin_memory,
        persistent_workers=num_workers > 0,
    )


def get_dataset_info(dataset: Dataset) -> dict:
    """데이터셋 정보 요약"""
    return {
        "length": len(dataset),
        "sample_shape": (
            dataset[0].shape if hasattr(dataset[0], "shape") else str(type(dataset[0]))
        ),
        "num_classes": getattr(dataset, "num_classes", None),
    }
