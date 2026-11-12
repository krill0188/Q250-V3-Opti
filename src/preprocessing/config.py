"""
전처리 파이프라인 설정 모듈
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from enum import Enum


class CoordinateFrame(Enum):
    """좌표계 종류"""

    NED = "ned"  # North-East-Down
    ENU = "enu"  # East-North-Up
    WGS84 = "wgs84"  # GPS 위경도
    BODY = "body"  # 기체 기준


class DataSplit(Enum):
    """데이터 분할 종류"""

    TRAIN = "train"
    VAL = "val"
    TEST = "test"


@dataclass
class NormalizationConfig:
    """정규화 설정"""

    method: str = "standard"  # "standard", "minmax", "robust"
    feature_range: Tuple[float, float] = (0.0, 1.0)
    per_sensor: bool = True  # 센서별 별도 정규화


@dataclass
class SplitConfig:
    """데이터 분할 설정"""

    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    shuffle: bool = False  # 시계열 데이터는 False 권장
    stratified: bool = False
    temporal_split: bool = True  # 시계열 순서 보존


@dataclass
class SyncConfig:
    """시계열 동기화 설정"""

    target_freq_hz: float = 100.0  # 목표 주파수 (Hz)
    max_time_diff_sec: float = 0.01  # 최대 허용 시간 차이 (초)
    interp_method: str = "linear"  # "linear", "nearest", "cubic"
    extrapolate: bool = False


@dataclass
class DatasetConfig:
    """데이터셋별 설정"""

    name: str
    raw_data_path: Path
    processed_path: Path
    coordinate_frame: CoordinateFrame = CoordinateFrame.NED
    native_freq_hz: Optional[float] = None
    sensors: List[str] = field(default_factory=list)

    # 정규화/분할/동기화 설정
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)

    # 센서별 칼럼 매핑 (원시 데이터 -> 표준화된 이름)
    column_mapping: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # 결측치 처리
    max_gap_sec: float = 1.0  # 최대 허용 결측 구간 (초)
    fill_method: str = "interpolate"  # "interpolate", "forward", "backward", "zero"


# 데이터셋별 기본 설정
DATASET_CONFIGS = {
    "idf_ds": DatasetConfig(
        name="idf_ds",
        raw_data_path=Path(
            "~/data/drone_datasets/idf_ds/Speedybee DataSet"
        ).expanduser(),
        processed_path=Path("~/data/drone_datasets/processed/idf_ds").expanduser(),
        coordinate_frame=CoordinateFrame.NED,
        native_freq_hz=100.0,
        sensors=["gps", "imu", "baro", "wind", "actuator", "battery"],
        column_mapping={
            "gps": {
                "time": "timestamp",
                "lat": "lat_deg",
                "lon": "lon_deg",
                "alt": "alt_m",
                "vn": "vel_n_mps",
                "ve": "vel_e_mps",
                "vd": "vel_d_mps",
            },
            "imu": {
                "time": "timestamp",
                "ax": "acc_x_mps2",
                "ay": "acc_y_mps2",
                "az": "acc_z_mps2",
                "gx": "gyro_x_radps",
                "gy": "gyro_y_radps",
                "gz": "gyro_z_radps",
            },
            "baro": {"time": "timestamp", "alt": "alt_baro_m", "press": "press_pa"},
            "wind": {"time": "timestamp", "wn": "wind_n_mps", "we": "wind_e_mps"},
            "actuator": {
                "time": "timestamp",
                "ch1": "act_1",
                "ch2": "act_2",
                "ch3": "act_3",
                "ch4": "act_4",
            },
        },
        max_gap_sec=0.5,
    ),
    "fixed_wing_attitude": DatasetConfig(
        name="fixed_wing_attitude",
        raw_data_path=Path(
            "~/data/drone_datasets/fixed_wing_attitude/Fixed-Wing-UAV-Attitude-Dataset"
        ).expanduser(),
        processed_path=Path(
            "~/data/drone_datasets/processed/fixed_wing_attitude"
        ).expanduser(),
        coordinate_frame=CoordinateFrame.NED,
        native_freq_hz=50.0,
        sensors=["attitude", "gps", "imu", "airspeed"],
        column_mapping={
            "attitude": {
                "time": "timestamp",
                "roll": "roll_rad",
                "pitch": "pitch_rad",
                "yaw": "yaw_rad",
            },
        },
        max_gap_sec=1.0,
    ),
    "ign_fixed_wing": DatasetConfig(
        name="ign_fixed_wing",
        raw_data_path=Path("~/data/drone_datasets/ign_fixed_wing").expanduser(),
        processed_path=Path(
            "~/data/drone_datasets/processed/ign_fixed_wing"
        ).expanduser(),
        coordinate_frame=CoordinateFrame.NED,
        native_freq_hz=100.0,
        sensors=["gps", "imu", "camera", "gnss"],
        max_gap_sec=0.5,
    ),
    "uzh_fpv": DatasetConfig(
        name="uzh_fpv",
        raw_data_path=Path("~/data/drone_datasets/uzh_fpv").expanduser(),
        processed_path=Path("~/data/drone_datasets/processed/uzh_fpv").expanduser(),
        coordinate_frame=CoordinateFrame.NED,
        native_freq_hz=200.0,
        sensors=["imu", "event_camera", "davis", "snapdragon"],
        max_gap_sec=0.01,
    ),
    "fpv_analog": DatasetConfig(
        name="fpv_analog",
        raw_data_path=Path("~/data/drone_datasets/fpv_analog").expanduser(),
        processed_path=Path("~/data/drone_datasets/processed/fpv_analog").expanduser(),
        coordinate_frame=CoordinateFrame.BODY,
        native_freq_hz=16000.0,
        sensors=["audio"],
        column_mapping={},
        max_gap_sec=0.0,
    ),
    "drone_audio": DatasetConfig(
        name="drone_audio",
        raw_data_path=Path(
            "~/projectm/drone_datasets/04_special_direct/ew_acoustic_air2air/DroneAudioDataset"
        ).expanduser(),
        processed_path=Path("~/data/drone_datasets/processed/drone_audio").expanduser(),
        coordinate_frame=CoordinateFrame.BODY,
        native_freq_hz=16000.0,
        sensors=["audio_binary", "audio_multiclass"],
        column_mapping={},
        max_gap_sec=0.0,
    ),
}
