"""
기본 로더 추상 클래스
모든 데이터셋 로더의 공통 인터페이스 정의
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Any, Tuple
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
from datetime import datetime

from ..config import DatasetConfig, CoordinateFrame, DataSplit


@dataclass
class SensorData:
    """단일 센서 데이터 컨테이너"""

    name: str  # 센서 이름 (gps, imu, baro 등)
    timestamp: np.ndarray  # 타임스탬프 (초, float64)
    data: np.ndarray  # 센서 데이터 (N, D)
    columns: List[str]  # 컬럼 이름
    frequency_hz: float  # 샘플링 주파수
    coordinate_frame: str  # 좌표계
    metadata: dict = None  # 추가 메타데이터

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        # 타임스탬프 정렬 확인
        if not np.all(np.diff(self.timestamp) >= 0):
            sort_idx = np.argsort(self.timestamp)
            self.timestamp = self.timestamp[sort_idx]
            self.data = self.data[sort_idx]

    def __len__(self) -> int:
        return len(self.timestamp)

    def get_duration_sec(self) -> float:
        """데이터 지속 시간 (초)"""
        if len(self.timestamp) < 2:
            return 0.0
        return float(self.timestamp[-1] - self.timestamp[0])

    def resample(self, target_freq_hz: float, method: str = "linear") -> "SensorData":
        """리샘플링"""
        if abs(self.frequency_hz - target_freq_hz) < 1e-6:
            return self

        duration = self.get_duration_sec()
        new_timestamps = np.arange(
            self.timestamp[0], self.timestamp[-1], 1.0 / target_freq_hz
        )

        if method == "linear":
            interp_data = np.zeros(
                (len(new_timestamps), self.data.shape[1]), dtype=self.data.dtype
            )
            for i in range(self.data.shape[1]):
                interp_data[:, i] = np.interp(
                    new_timestamps, self.timestamp, self.data[:, i]
                )
        elif method == "nearest":
            interp_data = np.zeros(
                (len(new_timestamps), self.data.shape[1]), dtype=self.data.dtype
            )
            for i in range(self.data.shape[1]):
                interp_data[:, i] = np.interp(
                    new_timestamps, self.timestamp, self.data[:, i]
                )
        else:
            raise ValueError(f"Unsupported interpolation method: {method}")

        return SensorData(
            name=self.name,
            timestamp=new_timestamps,
            data=interp_data,
            columns=self.columns,
            frequency_hz=target_freq_hz,
            coordinate_frame=self.coordinate_frame,
            metadata=self.metadata.copy(),
        )

    def crop(self, start_sec: float, end_sec: float) -> "SensorData":
        """시간 구간 자르기"""
        start_ts = self.timestamp[0] + start_sec
        end_ts = self.timestamp[0] + end_sec
        mask = (self.timestamp >= start_ts) & (self.timestamp <= end_ts)

        return SensorData(
            name=self.name,
            timestamp=self.timestamp[mask] - self.timestamp[mask][0],
            data=self.data[mask],
            columns=self.columns,
            frequency_hz=self.frequency_hz,
            coordinate_frame=self.coordinate_frame,
            metadata=self.metadata.copy(),
        )


@dataclass
class MultiSensorData:
    """다중 센서 데이터 컨테이너 (동기화된)"""

    sensors: Dict[str, SensorData]  # 센서 이름 -> SensorData
    reference_sensor: str  # 기준 센서 (보통 GPS 또는 IMU)
    synchronized: bool = False
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def get_sensor(self, name: str) -> Optional["SensorData"]:
        return self.sensors.get(name)

    def get_duration_sec(self) -> float:
        """전체 데이터 지속 시간"""
        durations = [s.get_duration_sec() for s in self.sensors.values()]
        return max(durations) if durations else 0.0

    def get_common_time_range(self) -> Tuple[float, float]:
        """모든 센서 공통 시간 범위"""
        start_times = [s.timestamp[0] for s in self.sensors.values()]
        end_times = [s.timestamp[-1] for s in self.sensors.values()]
        return max(start_times), min(end_times)


class BaseLoader(ABC):
    """데이터셋 로더 기본 클래스"""

    def __init__(self, config: "DatasetConfig"):
        self.config = config
        self.raw_path = config.raw_data_path.expanduser()
        self.processed_path = config.processed_path.expanduser()
        self.processed_path.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def load_raw(self) -> MultiSensorData:
        """원시 데이터 로드 및 MultiSensorData 반환"""
        pass

    @abstractmethod
    def get_supported_sensors(self) -> List[str]:
        """지원하는 센서 목록"""
        pass

    def save_processed(self, data: MultiSensorData, split: str = "train") -> Path:
        """처리된 데이터 저장"""
        save_path = self.processed_path / split
        save_path.mkdir(parents=True, exist_ok=True)

        for name, sensor in data.sensors.items():
            # NPZ 형식으로 저장 (빠른 로드)
            np.savez_compressed(
                save_path / f"{name}.npz",
                timestamp=sensor.timestamp,
                data=sensor.data,
                columns=np.array(sensor.columns, dtype=object),
                frequency_hz=sensor.frequency_hz,
                coordinate_frame=sensor.coordinate_frame,
            )

        # 메타데이터 저장
        import json

        metadata = {
            "sensors": {
                name: {
                    "columns": s.columns,
                    "frequency_hz": s.frequency_hz,
                    "coordinate_frame": s.coordinate_frame,
                    "shape": s.data.shape,
                }
                for name, s in data.sensors.items()
            },
            "reference_sensor": data.reference_sensor,
            "synchronized": data.synchronized,
        }
        with open(save_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, cls=NumpyEncoder)

        return save_path

    def load_processed(self, split: str = "train") -> MultiSensorData:
        """처리된 데이터 로드"""
        import json

        load_path = self.processed_path / split
        metadata_path = load_path / "metadata.json"

        if not metadata_path.exists():
            raise FileNotFoundError(f"Processed data not found: {metadata_path}")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        sensors = {}
        for name, meta in metadata["sensors"].items():
            npz_path = load_path / f"{name}.npz"
            data = np.load(npz_path)
            sensors[name] = SensorData(
                name=name,
                timestamp=data["timestamp"],
                data=data["data"],
                columns=data["columns"].tolist(),
                frequency_hz=float(data["frequency_hz"]),
                coordinate_frame=str(data["coordinate_frame"]),
            )

        return MultiSensorData(
            sensors=sensors,
            reference_sensor=metadata["reference_sensor"],
            synchronized=metadata["synchronized"],
        )

    def get_column_mapping(self, sensor: str) -> Dict[str, str]:
        """센서별 컬럼 매핑 반환"""
        return self.config.column_mapping.get(sensor, {})

    def apply_column_mapping(self, df: pd.DataFrame, sensor: str) -> pd.DataFrame:
        """데이터프레임 컬럼명 표준화"""
        mapping = self.get_column_mapping(sensor)
        if mapping:
            df = df.rename(columns=mapping)
        return df


# JSON 직렬화를 위한 헬퍼
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)
