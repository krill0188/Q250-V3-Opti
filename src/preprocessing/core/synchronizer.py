"""
시계열 동기화 모듈
GPS, IMU, 카메라, 오디오 등 다중 센서 데이터의 시간 동기화
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import signal, interpolate

from .base_loader import SensorData, MultiSensorData
from ..config import SyncConfig, CoordinateFrame


@dataclass
class SyncResult:
    """동기화 결과"""

    synchronized_data: Dict[str, "SensorData"]
    reference_sensor: str
    time_offsets: Dict[str, float]  # 각 센서의 시간 오프셋 (초)
    quality_scores: Dict[str, float]  # 동기화 품질 점수 (0-1)
    common_time_range: Tuple[float, float]  # 공통 시간 범위 (시작, 끝)


class TimeSynchronizer:
    """다중 센서 시계열 동기화"""

    def __init__(self, config: Optional[SyncConfig] = None):
        self.config = config or SyncConfig()

    def synchronize(
        self, multi_sensor: MultiSensorData, reference_sensor: Optional[str] = None
    ) -> SyncResult:
        """
        다중 센서 데이터 동기화

        Args:
            multi_sensor: 동기화할 다중 센서 데이터
            reference_sensor: 기준 센서 이름 (None이면 첫 번째 센서)

        Returns:
            SyncResult: 동기화 결과
        """
        if not multi_sensor.sensors:
            raise ValueError("No sensors to synchronize")

        # 기준 센서 결정
        if reference_sensor is None:
            reference_sensor = multi_sensor.reference_sensor
        if reference_sensor not in multi_sensor.sensors:
            reference_sensor = list(multi_sensor.sensors.keys())[0]

        ref_sensor = multi_sensor.sensors[reference_sensor]
        ref_time = ref_sensor.timestamp

        # 공통 시간 범위 계산
        common_start, common_end = multi_sensor.get_common_time_range()
        if common_start >= common_end:
            raise ValueError("No common time range among sensors")

        # 각 센서 동기화
        synchronized = {}
        time_offsets = {}
        quality_scores = {}

        for name, sensor in multi_sensor.sensors.items():
            if name == reference_sensor:
                # 기준 센서는 타겟 주파수로 리샘플링만
                if abs(sensor.frequency_hz - self.config.target_freq_hz) > 1e-6:
                    synced = sensor.resample(self.config.target_freq_hz)
                else:
                    synced = sensor
                time_offsets[name] = 0.0
                quality_scores[name] = 1.0
            else:
                # 다른 센서: 시간 오프셋 추정 + 리샘플링
                offset, quality = self._estimate_time_offset(sensor, ref_sensor)
                time_offsets[name] = offset
                quality_scores[name] = quality

                # 시간 오프셋 적용
                corrected_time = sensor.timestamp + offset

                # 공통 시간 범위로 자르기
                mask = (corrected_time >= common_start) & (corrected_time <= common_end)
                if not np.any(mask):
                    raise ValueError(f"No overlapping time range for sensor {name}")

                synced = SensorData(
                    name=sensor.name,
                    timestamp=corrected_time[mask] - common_start,  # 0부터 시작
                    data=sensor.data[mask],
                    columns=sensor.columns,
                    frequency_hz=sensor.frequency_hz,
                    coordinate_frame=sensor.coordinate_frame,
                    metadata=sensor.metadata.copy(),
                )

                # 목표 주파수로 리샘플링
                if abs(synced.frequency_hz - self.config.target_freq_hz) > 1e-6:
                    synced = synced.resample(self.config.target_freq_hz)

            synchronized[name] = synced

        return SyncResult(
            synchronized_data=synchronized,
            reference_sensor=reference_sensor,
            time_offsets=time_offsets,
            quality_scores=quality_scores,
            common_time_range=(0.0, common_end - common_start),
        )

    def _estimate_time_offset(
        self, sensor: "SensorData", ref_sensor: "SensorData"
    ) -> Tuple[float, float]:
        """
        두 센서 간 시간 오프셋 추정 (상호상관 기반)

        Returns:
            (offset_sec, quality_score)
        """
        # 공통 특성이 있는 채널 선택 (예: 진동, 가속도 등)
        # 여기서는 첫 번째 차원 사용 (일반적으로 진동/가속도)
        if sensor.data.shape[1] == 0 or ref_sensor.data.shape[1] == 0:
            return 0.0, 0.0

        # 공통 시간 범위 내 데이터 추출
        common_start = max(sensor.timestamp[0], ref_sensor.timestamp[0])
        common_end = min(sensor.timestamp[-1], ref_sensor.timestamp[-1])

        if common_start >= common_end:
            return 0.0, 0.0

        # 리샘플링하여 동일 시간축에서 비교
        target_freq = min(sensor.frequency_hz, ref_sensor.frequency_hz)
        target_freq = min(target_freq, self.config.target_freq_hz)

        sensor_sync = sensor.resample(target_freq)
        ref_sync = ref_sensor.resample(target_freq)

        # 공통 시간 범위에서 데이터 추출
        mask_sensor = (sensor_sync.timestamp >= common_start) & (
            sensor_sync.timestamp <= common_end
        )
        mask_ref = (ref_sync.timestamp >= common_start) & (
            ref_sync.timestamp <= common_end
        )

        if not np.any(mask_sensor) or not np.any(mask_ref):
            return 0.0, 0.0

        sig1 = sensor_sync.data[mask_sensor, 0]  # 첫 번째 채널
        sig2 = ref_sync.data[mask_ref, 0]

        # 길이 맞추기
        min_len = min(len(sig1), len(sig2))
        sig1 = sig1[:min_len]
        sig2 = sig2[:min_len]

        if min_len < 10:
            return 0.0, 0.0

        # 상호상관으로 시간 오프셋 추정
        correlation = signal.correlate(sig1, sig2, mode="full")
        lags = signal.correlation_lags(len(sig1), len(sig2), mode="full")
        max_corr_idx = np.argmax(np.abs(correlation))
        max_corr = correlation[max_corr_idx]
        lag = lags[max_corr_idx]

        # 시간 오프셋 (초)
        offset_sec = lag / target_freq

        # 품질 점수 (정규화된 최대 상관계수)
        quality = abs(max_corr) / (np.std(sig1) * np.std(sig2) * min_len + 1e-10)
        quality = min(max(quality, 0.0), 1.0)

        return offset_sec, quality

    def estimate_offset_from_gps(
        self, sensor: "SensorData", gps_sensor: "SensorData"
    ) -> Tuple[float, float]:
        """GPS 데이터를 이용한 시간 오프셋 추정 (더 정확)"""
        # GPS 시간과 센서 시간의 차이 분석
        # GPS는 보통 절대 시간(UTC)을 가짐
        if "time" not in gps_sensor.columns and "timestamp" not in gps_sensor.columns:
            return 0.0, 0.0

        # GPS 시간 컬럼 찾기
        time_col = "time" if "time" in gps_sensor.columns else "timestamp"
        gps_time = gps_sensor.data[:, gps_sensor.columns.index(time_col)]

        # 센서 시간과 GPS 시간의 선형 회귀로 오프셋 추정
        # 센서의 첫/마지막 타임스탬프와 GPS 시간 매칭
        pass  # 구현 생략 - 기본 동기화로 대체

        return 0.0, 0.0


class InterpolationSync:
    """보간 기반 동기화 (정확한 시간 동기화가 어려울 때)"""

    def __init__(self, target_freq_hz: float = 100.0):
        self.target_freq_hz = target_freq_hz

    def sync_by_interpolation(
        self, multi_sensor: MultiSensorData, reference_sensor: str
    ) -> MultiSensorData:
        """보간을 이용한 동기화"""
        ref_sensor = multi_sensor.sensors[reference_sensor]

        # 목표 시간축 생성 (기준 센서 기준)
        target_time = ref_sensor.timestamp

        synchronized = {}
        for name, sensor in multi_sensor.sensors.items():
            if name == reference_sensor:
                synchronized[name] = sensor
                continue

            # 각 채널별 보간
            interp_data = np.zeros((len(target_time), sensor.data.shape[1]))
            for i in range(sensor.data.shape[1]):
                interp_func = interpolate.interp1d(
                    sensor.timestamp,
                    sensor.data[:, i],
                    kind="linear",
                    bounds_error=False,
                    fill_value="extrapolate",
                )
                interp_data[:, i] = interp_func(target_time)

            synchronized[name] = SensorData(
                name=sensor.name,
                timestamp=target_time,
                data=interp_data,
                columns=sensor.columns,
                frequency_hz=self.target_freq_hz,
                coordinate_frame=sensor.coordinate_frame,
                metadata=sensor.metadata.copy(),
            )

        return MultiSensorData(
            sensors=synchronized, reference_sensor=reference_sensor, synchronized=True
        )


def create_synchronizer(
    target_freq_hz: float = 100.0,
    max_time_diff_sec: float = 0.01,
    interp_method: str = "linear",
) -> TimeSynchronizer:
    """동기화기 생성 팩토리"""
    config = SyncConfig(
        target_freq_hz=target_freq_hz,
        max_time_diff_sec=max_time_diff_sec,
        interp_method=interp_method,
    )
    return TimeSynchronizer(config)
