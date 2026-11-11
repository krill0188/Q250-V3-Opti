"""
Fixed-Wing UAV Attitude Dataset 로더
고정익 다이브/기만 궤적 학습용 데이터
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from tqdm import tqdm

from ..core.base_loader import BaseLoader, SensorData, MultiSensorData
from ..config import DatasetConfig


class FixedWingAttitudeLoader(BaseLoader):
    """Fixed-Wing Attitude 데이터셋 로더"""

    # 센서별 컬럼 그룹 정의
    SENSOR_GROUPS = {
        "gps": [
            "gpsDataNew_pos_x",
            "gpsDataNew_pos_y",
            "gpsDataNew_alt",
            "gpsDataNew_pos_vx",
            "gpsDataNew_pos_vy",
            "gpsDataNew_pos_vz",
            "gpsDatasatnum",
            "gpsstatuspos",
            "gpsstatusheading",
            "current_lat",
            "current_lng",
            "current_alt",
        ],
        "imu": [
            "gyro_raw_x",
            "gyro_raw_y",
            "gyro_raw_z",
            "acc_raw_x",
            "acc_raw_y",
            "acc_raw_z",
            "wx_deg_s",
            "wy_deg_s",
            "wz_deg_s",
            "extern_gyro_raw_x",
            "extern_gyro_raw_y",
            "extern_gyro_raw_z",
        ],
        "attitude": [
            "roll_deg",
            "pitch_deg",
            "yaw_deg",
            "roll_dem_deg",
            "pitch_dem_deg",
            "yaw_dem_deg",
            "local_phi_rad",
            "rtk_yaw",
        ],
        "motor": [
            "motor_out1",
            "motor_out2",
            "motor_out3",
            "motor_out4",
            "motor_out7",
            "throttle_control_in",
            "throttle",
        ],
        "actuator": [
            "aileron",
            "elevator",
            "rudder",
        ],
        "airspeed": [
            "indicated_airspeed_cms",
            "spdCompFilt_TAS_cms",
            "ekf_TAS_cms",
            "extern_diff_press",
            "extern_airspeed_temp",
            "extern_airspeed_ms",
            "tasDataNew_tas",
            "sensor_east2_tas",
        ],
        "baro": [
            "filteredBaro",
            "baro_alt_meter",
            "gpsDelayedhgt",
            "ekfRtkRefHgt",
        ],
        "battery": [
            "battery_volt",
        ],
        "wind": [
            "wind_ekf_x",
            "wind_ekf_y",
        ],
        "ekf": [
            "pos_x",
            "pos_y",
            "pos_z",
            "vel_x",
            "vel_y",
            "vel_z",
            "accel_z_ef_mss",
            "accel_z_target",
        ],
        "tecs": [
            "tecs_hgt_dem_adj",
            "tecs_TAS_dem_adj",
            "L1_cross_error",
        ],
        "tracking": [
            "Tracking_x_dist_err",
            "Tracking_y_dist_err",
            "Tracking_z_dist_err",
            "tracking_pos_cm_x",
            "tracking_pos_cm_y",
            "tracking_pos_cm_z",
            "tracking_set_cm_x",
            "tracking_set_cm_y",
            "tracking_set_cm_z",
        ],
    }

    TIMESTAMP_COL = "sd_timestamp"

    def __init__(self, config: DatasetConfig):
        super().__init__(config)

    def get_supported_sensors(self) -> List[str]:
        return list(self.SENSOR_GROUPS.keys()) + ["timestamp_meta"]

    def _find_all_files(self) -> List[Path]:
        """모든 Parquet 파일 찾기 (TSV 변환본 우선)"""
        files = []
        for date_dir in sorted(self.raw_path.glob("2025*")):
            if date_dir.is_dir():
                # Parquet 파일 우선
                for pq_file in sorted(date_dir.glob("UART_*.parquet")):
                    files.append(pq_file)
                # Parquet 없으면 TXT fallback
                if not any(date_dir.glob("UART_*.parquet")):
                    for txt_file in sorted(date_dir.glob("UART_*.TXT")):
                        files.append(txt_file)
        return files

    def load_raw(self) -> MultiSensorData:
        """전체 파일 로드 및 병합"""
        files = self._find_all_files()

        if not files:
            raise FileNotFoundError(f"No data files found in {self.raw_path}")

        print(f"Loading {len(files)} files...")

        all_dfs = []

        for f in tqdm(files, desc="Reading files"):
            try:
                if f.suffix == ".parquet":
                    df = pd.read_parquet(f)
                else:
                    # TSV fallback
                    df = pd.read_csv(f, sep="\t", low_memory=False)

                if len(df) > 0:
                    all_dfs.append(df)
            except Exception as e:
                print(f"Error reading {f}: {e}")

        if not all_dfs:
            raise ValueError("No valid data loaded")

        # 병합 및 정렬
        merged = pd.concat(all_dfs, ignore_index=True)
        merged = merged.sort_values(self.TIMESTAMP_COL).reset_index(drop=True)

        # 타임스탬프 변환 (마이크로초 -> 초)
        timestamps = merged[self.TIMESTAMP_COL].values.astype(np.float64) / 1e6

        # 센서별 데이터 추출
        sensors = {}

        for sensor_name, cols in self.SENSOR_GROUPS.items():
            available = [c for c in cols if c in merged.columns]
            if not available:
                continue

            data = merged[available].values.astype(np.float64)

            # 주파수 추정
            if len(timestamps) > 1:
                dt = np.median(np.diff(timestamps))
                freq = 1.0 / dt if dt > 0 else 50.0
            else:
                freq = 50.0

            sensors[sensor_name] = SensorData(
                name=sensor_name,
                timestamp=timestamps,
                data=data,
                columns=available,
                frequency_hz=freq,
                coordinate_frame=(
                    "NED" if sensor_name in ["gps", "ekf", "wind"] else "BODY"
                ),
                metadata={"source": "FixedWingAttitude", "num_files": len(files)},
            )

        # 메타데이터용 타임스탬프 센서
        meta_cols = [
            "sd_start",
            "flight_mode",
            "rc_switch1_state",
            "transition_state",
            "mission_index",
        ]
        meta_available = [c for c in meta_cols if c in merged.columns]
        if meta_available:
            sensors["timestamp_meta"] = SensorData(
                name="timestamp_meta",
                timestamp=timestamps,
                data=merged[meta_available].values.astype(np.float64),
                columns=meta_available,
                frequency_hz=freq,
                coordinate_frame="NONE",
                metadata={"source": "FixedWingAttitude"},
            )

        print(f"Loaded sensors: {list(sensors.keys())}")
        for name, s in sensors.items():
            print(
                f"  {name}: {len(s)} samples @ {s.frequency_hz:.1f}Hz, cols={len(s.columns)}"
            )

        return MultiSensorData(
            sensors=sensors,
            reference_sensor="imu" if "imu" in sensors else list(sensors.keys())[0],
            metadata={
                "source": "FixedWingAttitude",
                "total_files": len(files),
                "total_samples": len(merged),
            },
        )


def create_fixed_wing_attitude_loader(config: DatasetConfig) -> FixedWingAttitudeLoader:
    return FixedWingAttitudeLoader(config)
