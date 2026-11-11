"""
IGN Fixed-Wing Dataset 로더
고정익 드론: 고정밀 GPS(RINEX) + 카메라 + GCP
Non-GPS 네비게이션 검증용 Ground Truth
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from tqdm import tqdm
import re
from datetime import datetime

from ..core.base_loader import BaseLoader, SensorData, MultiSensorData
from ..config import DatasetConfig


class IGNFixedWingLoader(BaseLoader):
    """IGN Fixed-Wing 데이터셋 로더"""

    def __init__(self, config: DatasetConfig):
        super().__init__(config)
        self.data_root = self.raw_path / "Open_data" / "01_Observations"

    def get_supported_sensors(self) -> List[str]:
        return [
            "camera",
            "gcp_wgs84",
            "gcp_image",
            "rinex_rover",
            "rinex_master",
            "rinex_vrs",
        ]

    def load_raw(self) -> MultiSensorData:
        """데이터셋 전체 로드"""
        sensors = {}

        # 1. 카메라 이미지 메타데이터
        camera_sensor = self._load_camera_images()
        if camera_sensor:
            sensors["camera"] = camera_sensor

        # 2. GCP WGS84 좌표
        gcp_wgs84 = self._load_gcp_wgs84()
        if gcp_wgs84 is not None:
            sensors["gcp_wgs84"] = gcp_wgs84

        # 3. GCP 이미지 좌표
        gcp_img = self._load_gcp_image_coords()
        if gcp_img is not None:
            sensors["gcp_image"] = gcp_img

        # 4. RINEX 헤더 정보 (선택적)
        # 실제 관측 데이터는 별도 처리 필요 (RTKLIB)

        if not sensors:
            raise ValueError("No data loaded")

        # 공통 타임스탬프 (이미지 인덱스 기준)
        ref_sensor = list(sensors.values())[0]
        timestamps = np.arange(len(ref_sensor), dtype=np.float64)

        return MultiSensorData(
            sensors=sensors,
            reference_sensor=(
                "camera" if "camera" in sensors else list(sensors.keys())[0]
            ),
            metadata={
                "source": "IGN_Fixed_Wing",
                "description": "High-precision GPS + Camera + GCP dataset for Non-GPS navigation validation",
                "note": "RINEX observation files require RTKLIB post-processing for cm-level rover trajectory",
            },
        )

    def _load_camera_images(self) -> Optional[SensorData]:
        """카메라 이미지 메타데이터 로드"""
        img_dir = self.data_root / "Camera" / "Data" / "Images"
        if not img_dir.exists():
            return None

        img_files = sorted(img_dir.glob("*.tif"))
        if not img_files:
            img_files = sorted(img_dir.glob("*.tiff"))

        if not img_files:
            return None

        # 이미지 ID 추출 (파일명에서)
        img_ids = []
        for f in img_files:
            try:
                img_id = int(f.stem)
                img_ids.append(img_id)
            except ValueError:
                continue

        if not img_ids:
            return None

        # 타임스탬프: 이미지 순서 기반 (실제로는 EXIF나 별도 파일에 있음)
        n_images = len(img_ids)
        timestamps = np.arange(n_images, dtype=np.float64)

        # 메타데이터 구성
        data = np.column_stack(
            [
                np.array(img_ids, dtype=np.int32),
                np.arange(n_images, dtype=np.int32),  # 인덱스
            ]
        )

        return SensorData(
            name="camera",
            timestamp=timestamps,
            data=data.astype(np.float64),
            columns=["image_id", "frame_index"],
            frequency_hz=1.0,  # 순차적 프레임
            coordinate_frame="IMAGE",
            metadata={
                "num_images": n_images,
                "img_dir": str(img_dir),
                "format": "TIFF",
            },
        )

    def _load_gcp_wgs84(self) -> Optional[SensorData]:
        """GCP WGS84 좌표 로드"""
        gcp_file = self.data_root / "Camera" / "Data" / "GCPs" / "WGS84.txt"
        if not gcp_file.exists():
            return None

        # 파싱: id, lat, lon, height
        rows = []
        with open(gcp_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(";"):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        gcp_id = int(parts[0])
                        # DMS to Decimal
                        lat_dms = parts[1:4]  # DD MM SS.sssss
                        lon_dms = parts[4:7]
                        height = float(parts[7])

                        lat = self._dms_to_decimal(lat_dms[0], lat_dms[1], lat_dms[2])
                        lon = self._dms_to_decimal(lon_dms[0], lon_dms[1], lon_dms[2])

                        rows.append([gcp_id, lat, lon, height])
                    except (ValueError, IndexError):
                        continue

        if not rows:
            return None

        data = np.array(rows, dtype=np.float64)
        n = len(data)

        return SensorData(
            name="gcp_wgs84",
            timestamp=np.arange(n, dtype=np.float64),
            data=data,
            columns=["gcp_id", "latitude", "longitude", "height"],
            frequency_hz=1.0,
            coordinate_frame="WGS84",
            metadata={"num_gcps": n, "datum": "WGS84"},
        )

    def _load_gcp_image_coords(self) -> Optional[SensorData]:
        """GCP 이미지 좌표 로드"""
        gcp_file = (
            self.data_root / "Camera" / "Data" / "GCPs" / "GCPs_img_coordinates.txt"
        )
        if not gcp_file.exists():
            return None

        rows = []
        with open(gcp_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) >= 4:
                    try:
                        img_id = int(parts[0])
                        gcp_id = int(parts[1])
                        x = float(parts[2])
                        y = float(parts[3])
                        rows.append([img_id, gcp_id, x, y])
                    except ValueError:
                        continue

        if not rows:
            return None

        data = np.array(rows, dtype=np.float64)
        n = len(data)

        return SensorData(
            name="gcp_image",
            timestamp=np.arange(n, dtype=np.float64),
            data=data,
            columns=["image_id", "gcp_id", "x_pixel", "y_pixel"],
            frequency_hz=1.0,
            coordinate_frame="PIXEL",
            metadata={"num_observations": n},
        )

    def _dms_to_decimal(self, deg: str, min_: str, sec: str) -> float:
        """DMS (도/분/초) -> 10진도 변환"""
        d = float(deg)
        m = float(min_)
        s = float(sec)
        return d + m / 60.0 + s / 3600.0

    def parse_rinex_header(self, rinex_file: Path) -> Dict:
        """RINEX 헤더 파싱 (메타데이터용)"""
        header = {}
        with open(rinex_file, "r") as f:
            for line in f:
                if "END OF HEADER" in line:
                    break
                if len(line) >= 60:
                    label = line[60:].strip()
                    value = line[:60].strip()
                    if label:
                        header[label] = value
        return header

    def get_rinex_files(self) -> Dict[str, List[Path]]:
        """RINEX 파일 목록 반환"""
        gps_dir = self.data_root / "GPS" / "Data"
        files = {
            "rover": list((gps_dir / "Rover").glob("*.18o")),
            "master": list((gps_dir / "Master").glob("*.18o")),
            "vrs": list((gps_dir / "Vrs").glob("*.18o")),
        }
        return files


def create_ign_fixed_wing_loader(config: DatasetConfig) -> IGNFixedWingLoader:
    return IGNFixedWingLoader(config)
