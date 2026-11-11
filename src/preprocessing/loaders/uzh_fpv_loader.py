"""
UZH-FPV Dataset 로더
고속 FPV 레이싱 드론 데이터 (Event camera + IMU + Ground truth)
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from tqdm import tqdm
import re

from ..core.base_loader import BaseLoader, SensorData, MultiSensorData
from ..config import DatasetConfig


class UZHFPVLoader(BaseLoader):
    """UZH-FPV 데이터셋 로더"""

    def __init__(self, config: DatasetConfig):
        super().__init__(config)
        # raw_path가 uzh_fpv 디렉토리 자체를 가리킴
        self.data_root = self.raw_path

    def get_supported_sensors(self) -> List[str]:
        return ["groundtruth", "imu", "images", "events"]

    def _find_sequences(self) -> List[Path]:
        """데이터 시퀀스 디렉토리 찾기"""
        sequences = []
        for item in self.data_root.iterdir():
            if item.is_dir() and (item / "groundtruth.txt").exists():
                sequences.append(item)
        return sequences

    def load_raw(self) -> MultiSensorData:
        """전체 시퀀스 로드 및 병합"""
        sequences = self._find_sequences()

        if not sequences:
            # 단일 파일들이 루트에 있는 경우
            if (self.data_root / "groundtruth.txt").exists():
                sequences = [self.data_root]

        if not sequences:
            raise FileNotFoundError(f"No UZH-FPV sequences found in {self.data_root}")

        print(f"Loading {len(sequences)} sequences...")

        all_gt = []
        all_imu = []
        all_images = []
        all_events = []

        for seq_dir in sequences:
            print(f"  Loading {seq_dir.name}...")
            gt = self._load_groundtruth(seq_dir / "groundtruth.txt")
            imu = self._load_imu(seq_dir / "imu.txt")
            images = self._load_images(seq_dir / "images.txt")
            events = self._load_events(seq_dir / "events.txt")

            if gt is not None:
                all_gt.append(gt)
            if imu is not None:
                all_imu.append(imu)
            if images is not None:
                all_images.append(images)
            if events is not None:
                all_events.append(events)

        # 병합
        sensors = {}

        if all_gt:
            gt_data = np.vstack([g.data for g in all_gt])
            gt_ts = np.concatenate([g.timestamp for g in all_gt])
            sensors["groundtruth"] = SensorData(
                name="groundtruth",
                timestamp=gt_ts,
                data=gt_data,
                columns=["tx", "ty", "tz", "qx", "qy", "qz", "qw"],
                frequency_hz=200.0,  # ~5ms interval
                coordinate_frame="WORLD",
                metadata={"source": "UZH-FPV", "num_sequences": len(sequences)},
            )

        if all_imu:
            imu_data = np.vstack([i.data for i in all_imu])
            imu_ts = np.concatenate([i.timestamp for i in all_imu])
            sensors["imu"] = SensorData(
                name="imu",
                timestamp=imu_ts,
                data=imu_data,
                columns=[
                    "ang_vel_x",
                    "ang_vel_y",
                    "ang_vel_z",
                    "lin_acc_x",
                    "lin_acc_y",
                    "lin_acc_z",
                ],
                frequency_hz=1000.0,  # ~1ms interval
                coordinate_frame="BODY",
                metadata={"source": "UZH-FPV"},
            )

        if all_images:
            img_data = np.vstack([im.data for im in all_images])
            img_ts = np.concatenate([im.timestamp for im in all_images])
            sensors["images"] = SensorData(
                name="images",
                timestamp=img_ts,
                data=img_data,
                columns=["image_id", "frame_index"],
                frequency_hz=30.0,  # ~33ms interval
                coordinate_frame="IMAGE",
                metadata={"source": "UZH-FPV"},
            )

        if all_events:
            # 이벤트는 별도 처리 (희소 데이터)
            sensors["events"] = all_events[0]  # 첫 번째 시퀀스만
            sensors["events"].metadata["num_sequences"] = len(all_events)

        if not sensors:
            raise ValueError("No valid data loaded")

        # 기준 센서 결정
        ref_sensor = "groundtruth" if "groundtruth" in sensors else "imu"

        print(f"Loaded sensors: {list(sensors.keys())}")
        for name, s in sensors.items():
            if hasattr(s, "data"):
                print(
                    f"  {name}: {len(s)} samples @ {s.frequency_hz:.1f}Hz, shape={s.data.shape}"
                )

        return MultiSensorData(
            sensors=sensors,
            reference_sensor=ref_sensor,
            metadata={"source": "UZH-FPV", "num_sequences": len(sequences)},
        )

    def _load_groundtruth(self, filepath: Path) -> Optional[SensorData]:
        """Ground truth 로드: timestamp, tx, ty, tz, qx, qy, qz, qw"""
        if not filepath.exists():
            return None

        # 주석 라인 건너뛰기
        df = pd.read_csv(
            filepath,
            sep=" ",
            comment="#",
            header=None,
            names=["timestamp", "tx", "ty", "tz", "qx", "qy", "qz", "qw"],
        )

        if len(df) == 0:
            return None

        timestamps = df["timestamp"].values.astype(np.float64)
        # 절대 시간(Unix) -> 상대 시간(첫 타임스탬프 기준)
        timestamps = timestamps - timestamps[0]
        data = df[["tx", "ty", "tz", "qx", "qy", "qz", "qw"]].values.astype(np.float64)

        # 주파수 추정
        if len(timestamps) > 1:
            dt = np.median(np.diff(timestamps))
            freq = 1.0 / dt if dt > 0 else 200.0
        else:
            freq = 200.0

        return SensorData(
            name="groundtruth",
            timestamp=timestamps,
            data=data,
            columns=["tx", "ty", "tz", "qx", "qy", "qz", "qw"],
            frequency_hz=freq,
            coordinate_frame="WORLD",
            metadata={"source": "UZH-FPV groundtruth"},
        )

    def _load_imu(self, filepath: Path) -> Optional[SensorData]:
        """IMU 로드: timestamp, ang_vel_x, ang_vel_y, ang_vel_z, lin_acc_x, lin_acc_y, lin_acc_z"""
        if not filepath.exists():
            return None

        df = pd.read_csv(
            filepath,
            sep=" ",
            comment="#",
            header=None,
            names=[
                "timestamp",
                "ang_vel_x",
                "ang_vel_y",
                "ang_vel_z",
                "lin_acc_x",
                "lin_acc_y",
                "lin_acc_z",
            ],
        )

        if len(df) == 0:
            return None

        timestamps = df["timestamp"].values.astype(np.float64)
        # 절대 시간 -> 상대 시간
        timestamps = timestamps - timestamps[0]
        data = df[
            [
                "ang_vel_x",
                "ang_vel_y",
                "ang_vel_z",
                "lin_acc_x",
                "lin_acc_y",
                "lin_acc_z",
            ]
        ].values.astype(np.float64)

        if len(timestamps) > 1:
            dt = np.median(np.diff(timestamps))
            freq = 1.0 / dt if dt > 0 else 1000.0
        else:
            freq = 1000.0

        return SensorData(
            name="imu",
            timestamp=timestamps,
            data=data,
            columns=[
                "ang_vel_x",
                "ang_vel_y",
                "ang_vel_z",
                "lin_acc_x",
                "lin_acc_y",
                "lin_acc_z",
            ],
            frequency_hz=freq,
            coordinate_frame="BODY",
            metadata={"source": "UZH-FPV IMU"},
        )

    def _load_images(self, filepath: Path) -> Optional[SensorData]:
        """이미지 리스트 로드: id, timestamp, image_name"""
        if not filepath.exists():
            return None

        # 첫 줄(헤더) 읽어서 컬럼 수 확인
        with open(filepath, "r") as f:
            first_line = f.readline().strip()

        # 공백으로 분할하되 이미지 경로의 공백 처리
        df = pd.read_csv(
            filepath,
            sep=r"\s+",
            comment="#",
            header=None,
            names=["image_id", "timestamp", "image_name"],
            engine="python",
        )

        if len(df) == 0:
            return None

        # timestamp 컬럼이 이미지 경로인 경우 교정
        if df["timestamp"].dtype == "object":
            # image_name이 timestamp에 들어간 경우 교정
            mask = df["timestamp"].str.contains(r"\.png|\.jpg", na=False)
            if mask.any():
                df.loc[mask, "image_name"] = df.loc[mask, "timestamp"]
                df.loc[mask, "timestamp"] = df.loc[mask, "image_id"]
                df.loc[mask, "image_id"] = np.arange(mask.sum())

        # 타입 변환
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

        if len(df) == 0:
            return None

        timestamps = df["timestamp"].values.astype(np.float64)
        # 절대 시간 -> 상대 시간
        timestamps = timestamps - timestamps[0]
        image_ids = df["image_id"].values.astype(np.int32)
        frame_indices = np.arange(len(df), dtype=np.int32)

        data = np.column_stack([image_ids, frame_indices])

        if len(timestamps) > 1:
            dt = np.median(np.diff(timestamps))
            freq = 1.0 / dt if dt > 0 else 30.0
        else:
            freq = 30.0

        return SensorData(
            name="images",
            timestamp=timestamps,
            data=data.astype(np.float64),
            columns=["image_id", "frame_index"],
            frequency_hz=freq,
            coordinate_frame="IMAGE",
            metadata={
                "source": "UZH-FPV images",
                "image_dir": str(filepath.parent / "img"),
            },
        )

    def _load_events(self, filepath: Path) -> Optional[SensorData]:
        """DVS 이벤트 로드 (희소 데이터)"""
        if not filepath.exists():
            return None

        # 이벤트 파일은 보통 매우 큼 (수백 MB) - 필요시 로드
        # 여기서는 메타데이터만
        return SensorData(
            name="events",
            timestamp=np.array([0.0]),
            data=np.array([[0, 0, 0, 0]], dtype=np.float64),
            columns=["timestamp", "x", "y", "polarity"],
            frequency_hz=0.0,
            coordinate_frame="EVENT",
            metadata={
                "source": "UZH-FPV DVS events",
                "file": str(filepath),
                "lazy": True,
            },
        )


def create_uzh_fpv_loader(config: DatasetConfig) -> UZHFPVLoader:
    return UZHFPVLoader(config)
