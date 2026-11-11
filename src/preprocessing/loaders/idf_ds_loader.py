"""
IDF-DS (Speedybee) 데이터셋 로더
Non-GPS 네비게이션용 고정익 비행 데이터
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from tqdm import tqdm

from ..core.base_loader import BaseLoader, SensorData, MultiSensorData
from ..config import DatasetConfig


class IDF_DSLoader(BaseLoader):
    """IDF-DS (Speedybee) 데이터셋 로더"""

    # GPS 컬럼 매핑 (원시 → 표준)
    GPS_COLUMN_MAP = {
        "time (us)": "timestamp",
        "GPS_coord[0]": "lat",
        "GPS_coord[1]": "lon",
        "GPS_altitude": "alt",
        "GPS_speed (m/s)": "speed",
        "GPS_ground_course": "course",
        "GPS_velned[0]": "vn",
        "GPS_velned[1]": "ve",
        "GPS_velned[2]": "vd",
        "GPS_fixType": "fix_type",
        "GPS_numSat": "num_sat",
        "GPS_hdop": "hdop",
        "GPS_eph": "eph",
        "GPS_epv": "epv",
    }

    # Telemetry 컬럼 매핑
    TLM_COLUMN_MAP = {
        "time (us)": "timestamp",
        "gyroADC[0]": "gyro_x",
        "gyroADC[1]": "gyro_y",
        "gyroADC[2]": "gyro_z",
        "accSmooth[0]": "acc_x",
        "accSmooth[1]": "acc_y",
        "accSmooth[2]": "acc_z",
        "attitude[0]": "roll",
        "attitude[1]": "pitch",
        "attitude[2]": "yaw",
        "BaroAlt": "baro_alt_cm",
        "magADC[0]": "mag_x",
        "magADC[1]": "mag_y",
        "magADC[2]": "mag_z",
        "vbat (V)": "voltage",
        "amperage (A)": "current",
        "rcCommand[0]": "rc_roll",
        "rcCommand[1]": "rc_pitch",
        "rcCommand[2]": "rc_yaw",
        "rcCommand[3]": "rc_throttle",
        "motor[0]": "motor",
        "servo[0]": "servo_0",
        "escRPM": "esc_rpm",
        "navPos[0]": "nav_lat",
        "navPos[1]": "nav_lon",
        "navPos[2]": "nav_alt",
        "navVel[0]": "nav_vn",
        "navVel[1]": "nav_ve",
        "navVel[2]": "nav_vd",
    }

    def __init__(self, config: DatasetConfig):
        super().__init__(config)
        self.laps = []  # (gps_path, tlm_path) 리스트

    def get_supported_sensors(self) -> List[str]:
        return ["gps", "imu", "baro", "mag", "battery", "rc", "motor", "nav"]

    def _discover_laps(self) -> List[tuple]:
        """GPS와 Telemetry 파일 쌍 찾기"""
        gps_dir = self.raw_path / "processed" / "GPS"
        tlm_dir = self.raw_path / "processed" / "telemetry"

        if not gps_dir.exists() or not tlm_dir.exists():
            raise FileNotFoundError(f"IDF-DS data not found at {self.raw_path}")

        gps_files = sorted(gps_dir.glob("Lap*_gps.csv"))
        laps = []

        for gps_file in gps_files:
            # Lap 번호 추출
            lap_num = gps_file.stem.split("_")[0]  # "Lap001"
            tlm_file = tlm_dir / f"{lap_num}.csv"

            if tlm_file.exists():
                laps.append((gps_file, tlm_file))
            else:
                print(f"Warning: No telemetry for {lap_num}")

        return laps

    def load_raw(self) -> MultiSensorData:
        """전체 랩 데이터 로드 및 병합"""
        self.laps = self._discover_laps()

        if not self.laps:
            raise ValueError("No valid lap pairs found")

        print(f"Loading {len(self.laps)} laps...")

        # 전체 데이터 누적용 리스트
        all_gps = []
        all_tlm = []

        for gps_path, tlm_path in tqdm(self.laps, desc="Loading laps"):
            # GPS 로드
            gps_df = pd.read_csv(gps_path)
            gps_df = self._standardize_gps(gps_df)
            all_gps.append(gps_df)

            # Telemetry 로드
            tlm_df = pd.read_csv(tlm_path, low_memory=False)
            tlm_df = self._standardize_telemetry(tlm_df)
            all_tlm.append(tlm_df)

        # 병합
        gps_merged = (
            pd.concat(all_gps, ignore_index=True) if all_gps else pd.DataFrame()
        )
        tlm_merged = (
            pd.concat(all_tlm, ignore_index=True) if all_tlm else pd.DataFrame()
        )

        # 시간 정렬 (마이크로초 → 초)
        if not gps_merged.empty:
            gps_merged = gps_merged.sort_values("timestamp").reset_index(drop=True)
            gps_merged["timestamp"] = gps_merged["timestamp"] / 1e6

        if not tlm_merged.empty:
            tlm_merged = tlm_merged.sort_values("timestamp").reset_index(drop=True)
            tlm_merged["timestamp"] = tlm_merged["timestamp"] / 1e6

        # SensorData 객체 생성
        sensors = {}

        if not gps_merged.empty:
            sensors["gps"] = self._create_gps_sensor(gps_merged)

        if not tlm_merged.empty:
            tlm_sensors = self._create_telemetry_sensors(tlm_merged)
            sensors.update(tlm_sensors)

        return MultiSensorData(
            sensors=sensors,
            reference_sensor="gps" if "gps" in sensors else list(sensors.keys())[0],
            metadata={"source": "IDF-DS", "num_laps": len(self.laps)},
        )

    def _standardize_gps(self, df: pd.DataFrame) -> pd.DataFrame:
        """GPS 컬럼명 표준화"""
        # 필요한 컬럼만 선택
        available = [c for c in self.GPS_COLUMN_MAP.keys() if c in df.columns]
        df = df[available].copy()
        df = df.rename(columns={c: self.GPS_COLUMN_MAP[c] for c in available})
        return df

    def _standardize_telemetry(self, df: pd.DataFrame) -> pd.DataFrame:
        """Telemetry 컬럼명 표준화"""
        available = [c for c in self.TLM_COLUMN_MAP.keys() if c in df.columns]
        df = df[available].copy()
        df = df.rename(columns={c: self.TLM_COLUMN_MAP[c] for c in available})
        return df

    def _create_gps_sensor(self, df: pd.DataFrame) -> SensorData:
        """GPS SensorData 생성"""
        # 컬럼 순서 고정
        cols = [
            "lat",
            "lon",
            "alt",
            "vn",
            "ve",
            "vd",
            "speed",
            "course",
            "fix_type",
            "num_sat",
            "hdop",
            "eph",
            "epv",
        ]
        available_cols = [c for c in cols if c in df.columns]

        data = df[available_cols].values.astype(np.float64)

        # 주파수 추정
        if len(df) > 1:
            dt = np.median(np.diff(df["timestamp"].values))
            freq = 1.0 / dt if dt > 0 else 100.0
        else:
            freq = 100.0

        return SensorData(
            name="gps",
            timestamp=df["timestamp"].values.astype(np.float64),
            data=data,
            columns=available_cols,
            frequency_hz=freq,
            coordinate_frame="WGS84",
            metadata={"source": "GPS", "num_laps": len(self.laps)},
        )

    def _create_telemetry_sensors(self, df: pd.DataFrame) -> Dict[str, SensorData]:
        """Telemetry에서 여러 센서 분리"""
        sensors = {}

        # 주파수 추정
        if len(df) > 1:
            dt = np.median(np.diff(df["timestamp"].values))
            freq = 1.0 / dt if dt > 0 else 100.0
        else:
            freq = 100.0

        # IMU: gyro + acc + attitude
        imu_cols = [
            "gyro_x",
            "gyro_y",
            "gyro_z",
            "acc_x",
            "acc_y",
            "acc_z",
            "roll",
            "pitch",
            "yaw",
        ]
        imu_avail = [c for c in imu_cols if c in df.columns]
        if imu_avail:
            sensors["imu"] = SensorData(
                name="imu",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=df[imu_avail].values.astype(np.float64),
                columns=imu_avail,
                frequency_hz=freq,
                coordinate_frame="BODY",
                metadata={"source": "telemetry"},
            )

        # Barometer
        if "baro_alt_cm" in df.columns:
            sensors["baro"] = SensorData(
                name="baro",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=(df["baro_alt_cm"].values / 100.0)
                .reshape(-1, 1)
                .astype(np.float64),  # cm → m
                columns=["alt"],
                frequency_hz=freq,
                coordinate_frame="NED",
                metadata={"source": "telemetry"},
            )

        # Magnetometer
        mag_cols = ["mag_x", "mag_y", "mag_z"]
        mag_avail = [c for c in mag_cols if c in df.columns]
        if mag_avail:
            sensors["mag"] = SensorData(
                name="mag",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=df[mag_avail].values.astype(np.float64),
                columns=mag_avail,
                frequency_hz=freq,
                coordinate_frame="BODY",
                metadata={"source": "telemetry"},
            )

        # Battery
        bat_cols = ["voltage", "current"]
        bat_avail = [c for c in bat_cols if c in df.columns]
        if bat_avail:
            sensors["battery"] = SensorData(
                name="battery",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=df[bat_avail].values.astype(np.float64),
                columns=bat_avail,
                frequency_hz=freq,
                coordinate_frame="NONE",
                metadata={"source": "telemetry"},
            )

        # RC Commands
        rc_cols = ["rc_roll", "rc_pitch", "rc_yaw", "rc_throttle"]
        rc_avail = [c for c in rc_cols if c in df.columns]
        if rc_avail:
            sensors["rc"] = SensorData(
                name="rc",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=df[rc_avail].values.astype(np.float64),
                columns=rc_avail,
                frequency_hz=freq,
                coordinate_frame="NONE",
                metadata={"source": "telemetry"},
            )

        # Motor
        mot_cols = ["motor", "servo_0"]
        mot_avail = [c for c in mot_cols if c in df.columns]
        if mot_avail:
            sensors["motor"] = SensorData(
                name="motor",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=df[mot_avail].values.astype(np.float64),
                columns=mot_avail,
                frequency_hz=freq,
                coordinate_frame="NONE",
                metadata={"source": "telemetry"},
            )

        # Navigation (EKF 추정 상태)
        nav_cols = ["nav_lat", "nav_lon", "nav_alt", "nav_vn", "nav_ve", "nav_vd"]
        nav_avail = [c for c in nav_cols if c in df.columns]
        if nav_avail:
            sensors["nav"] = SensorData(
                name="nav",
                timestamp=df["timestamp"].values.astype(np.float64),
                data=df[nav_avail].values.astype(np.float64),
                columns=nav_avail,
                frequency_hz=freq,
                coordinate_frame="NED",
                metadata={"source": "telemetry", "note": "EKF estimated"},
            )

        return sensors


def create_idf_ds_loader(config: DatasetConfig) -> IDF_DSLoader:
    """IDF-DS 로더 생성 팩토리"""
    return IDF_DSLoader(config)
