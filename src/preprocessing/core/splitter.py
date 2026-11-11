"""
데이터 분할 모듈
시계열 특성을 고려한 Train/Val/Test 분할
"""

from typing import Dict, List, Optional, Tuple, Any, Iterator
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from pathlib import Path
from abc import ABC, abstractmethod

from .base_loader import SensorData, MultiSensorData
from ..config import SplitConfig, DataSplit


class SplitStrategy(ABC):
    """분할 전략 기본 클래스"""

    @abstractmethod
    def split(
        self, multi_sensor: MultiSensorData, config: "SplitConfig"
    ) -> Dict[DataSplit, MultiSensorData]:
        pass


@dataclass
class TemporalSplitter(SplitStrategy):
    """시간 순서 보존 분할 (시계열 데이터용)"""

    def split(
        self, multi_sensor: MultiSensorData, config: "SplitConfig"
    ) -> Dict[DataSplit, MultiSensorData]:
        """시간 순서대로 Train/Val/Test 분할"""

        # 공통 시간 범위
        start_time, end_time = multi_sensor.get_common_time_range()
        total_duration = end_time - start_time

        if total_duration <= 0:
            raise ValueError("Invalid time range")

        # 분할 시점 계산
        train_end = start_time + total_duration * config.train_ratio
        val_end = train_end + total_duration * config.val_ratio

        splits = {}

        for split_name, (split_start, split_end) in [
            (DataSplit.TRAIN, (start_time, train_end)),
            (DataSplit.VAL, (train_end, val_end)),
            (DataSplit.TEST, (val_end, end_time)),
        ]:
            sensors = {}
            for name, sensor in multi_sensor.sensors.items():
                # 시간 마스크
                mask = (sensor.timestamp >= split_start) & (
                    sensor.timestamp < split_end
                )
                if not np.any(mask):
                    # 빈 분할인 경우 빈 센서 데이터 생성
                    sensors[name] = SensorData(
                        name=sensor.name,
                        timestamp=np.array([]),
                        data=np.empty((0, sensor.data.shape[1])),
                        columns=sensor.columns,
                        frequency_hz=sensor.frequency_hz,
                        coordinate_frame=sensor.coordinate_frame,
                        metadata=sensor.metadata.copy(),
                    )
                else:
                    sensors[name] = SensorData(
                        name=sensor.name,
                        timestamp=sensor.timestamp[mask] - split_start,
                        data=sensor.data[mask],
                        columns=sensor.columns,
                        frequency_hz=sensor.frequency_hz,
                        coordinate_frame=sensor.coordinate_frame,
                        metadata=sensor.metadata.copy(),
                    )

            splits[split_name] = MultiSensorData(
                sensors=sensors,
                reference_sensor=multi_sensor.reference_sensor,
                synchronized=multi_sensor.synchronized,
                metadata=multi_sensor.metadata.copy(),
            )

        return splits


@dataclass
class RandomSplitter(SplitStrategy):
    """랜덤 분할 (시계열 아닌 데이터용)"""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state

    def split(
        self, multi_sensor: MultiSensorData, config: "SplitConfig"
    ) -> Dict[DataSplit, MultiSensorData]:
        """랜덤 셔플 후 분할"""
        from sklearn.model_selection import train_test_split

        # 기준 센서 데이터로 인덱스 생성
        ref_sensor = multi_sensor.sensors[multi_sensor.reference_sensor]
        n_samples = len(ref_sensor)
        indices = np.arange(n_samples)

        # 분할
        train_idx, temp_idx = train_test_split(
            indices,
            train_size=config.train_ratio,
            random_state=self.random_state,
            shuffle=config.shuffle,
        )
        val_ratio = config.val_ratio / (config.val_ratio + config.test_ratio)
        val_idx, test_idx = train_test_split(
            temp_idx,
            train_size=val_ratio,
            random_state=self.random_state,
            shuffle=config.shuffle,
        )

        splits = {}
        for split_name, indices in [
            (DataSplit.TRAIN, train_idx),
            (DataSplit.VAL, val_idx),
            (DataSplit.TEST, test_idx),
        ]:
            sensors = {}
            for name, sensor in multi_sensor.sensors.items():
                sensors[name] = SensorData(
                    name=sensor.name,
                    timestamp=sensor.timestamp[indices],
                    data=sensor.data[indices],
                    columns=sensor.columns,
                    frequency_hz=sensor.frequency_hz,
                    coordinate_frame=sensor.coordinate_frame,
                    metadata=sensor.metadata.copy(),
                )
            splits[split_name] = MultiSensorData(
                sensors=sensors,
                reference_sensor=multi_sensor.reference_sensor,
                synchronized=multi_sensor.synchronized,
                metadata=multi_sensor.metadata.copy(),
            )

        return splits


@dataclass
class StratifiedSplitter(SplitStrategy):
    """계층화 분할 (라벨 있는 데이터용)"""

    def __init__(self, label_column: str = "label", random_state: int = 42):
        self.label_column = label_column
        self.random_state = random_state

    def split(
        self, multi_sensor: MultiSensorData, config: "SplitConfig"
    ) -> Dict[DataSplit, MultiSensorData]:
        """라벨 기반 계층화 분할"""
        # 라벨 센서가 필요함
        if self.label_column not in [
            c for s in multi_sensor.sensors.values() for c in s.columns
        ]:
            raise ValueError(f"Label column '{self.label_column}' not found")

        from sklearn.model_selection import StratifiedShuffleSplit

        # 라벨 추출
        label_sensor = multi_sensor.sensors[multi_sensor.reference_sensor]
        labels = label_sensor.data[:, label_sensor.columns.index(self.label_column)]

        sss = StratifiedShuffleSplit(
            n_splits=1,
            test_size=(config.val_ratio + config.test_ratio),
            random_state=self.random_state,
        )

        indices = np.arange(len(labels))
        train_idx, temp_idx = next(sss.split(indices, labels))

        # Val/Test 다시 분할
        val_ratio = config.val_ratio / (config.val_ratio + config.test_ratio)
        sss2 = StratifiedShuffleSplit(
            n_splits=1, test_size=val_ratio, random_state=self.random_state
        )
        val_idx, test_idx = next(sss2.split(temp_idx, labels[temp_idx]))

        splits = {}
        for split_name, indices in [
            (DataSplit.TRAIN, train_idx),
            (DataSplit.VAL, val_idx),
            (DataSplit.TEST, test_idx),
        ]:
            sensors = {}
            for name, sensor in multi_sensor.sensors.items():
                sensors[name] = SensorData(
                    name=sensor.name,
                    timestamp=sensor.timestamp[indices],
                    data=sensor.data[indices],
                    columns=sensor.columns,
                    frequency_hz=sensor.frequency_hz,
                    coordinate_frame=sensor.coordinate_frame,
                    metadata=sensor.metadata.copy(),
                )
            splits[split_name] = MultiSensorData(
                sensors=sensors,
                reference_sensor=multi_sensor.reference_sensor,
                synchronized=multi_sensor.synchronized,
                metadata=multi_sensor.metadata.copy(),
            )

        return splits


class DataSplitter:
    """데이터 분할기 팩토리"""

    STRATEGIES = {
        "temporal": TemporalSplitter,
        "random": RandomSplitter,
        "stratified": StratifiedSplitter,
    }

    def __init__(self, strategy: str = "temporal", **kwargs):
        if strategy not in self.STRATEGIES:
            raise ValueError(
                f"Unknown strategy: {strategy}. Available: {list(self.STRATEGIES.keys())}"
            )
        self.strategy = self.STRATEGIES[strategy](**kwargs)

    def split(
        self, multi_sensor: MultiSensorData, config: "SplitConfig"
    ) -> Dict[DataSplit, MultiSensorData]:
        """데이터 분할 실행"""
        return self.strategy.split(multi_sensor, config)

    def save_splits(
        self,
        splits: Dict[DataSplit, MultiSensorData],
        output_dir: Path,
        base_loader: Any = None,
    ) -> Dict[str, Path]:
        """분할 데이터 저장"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = {}
        for split_name, split_data in splits.items():
            split_dir = output_dir / split_name.value
            # NPZ 저장 로직은 BaseLoader.save_processed 활용 권장
            paths[split_name.value] = split_dir

        return paths


def create_splitter(strategy: str = "temporal", **kwargs) -> DataSplitter:
    """분할기 생성 팩토리"""
    return DataSplitter(strategy, **kwargs)
