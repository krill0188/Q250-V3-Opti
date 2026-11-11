"""
파이프라인 기본 클래스
데이터셋별 전처리 파이프라인 오케스트레이션
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

from ..core.base_loader import BaseLoader, MultiSensorData, SensorData
from ..core.synchronizer import TimeSynchronizer, SyncResult
from ..core.normalizer import SensorNormalizer, create_normalizer
from ..core.splitter import DataSplitter, create_splitter
from ..core.validator import DataValidator, ValidationReport, create_validator
from ..config import DatasetConfig, SplitConfig, SyncConfig, NormalizationConfig


@dataclass
class PipelineResult:
    """파이프라인 실행 결과"""

    dataset_name: str
    raw_data: any = None
    synchronized_data: any = None
    normalized_data: any = None
    splits: Dict[str, any] = None
    validation_reports: Dict[str, any] = None
    metadata: dict = None
    success: bool = True
    error: str = ""


class BasePipeline(ABC):
    """전처리 파이프라인 기본 클래스"""

    def __init__(self, config: "DatasetConfig"):
        self.config = config
        self.validator = None
        self.normalizer = None
        self.splitter = None
        self.synchronizer = None

    @abstractmethod
    def create_loader(self):
        """데이터셋 로더 생성"""
        pass

    def initialize_components(self):
        """컴포넌트 초기화"""
        # 검증기
        self.validator = self.create_validator()

        # 정규화기
        norm_config = self.config.normalization
        self.normalizer = create_normalizer(
            method=norm_config.method,
            feature_range=norm_config.feature_range,
            per_sensor=norm_config.per_sensor,
        )

        # 분할기
        self.splitter = create_splitter("temporal")  # 시계열은 temporal

        # 동기화기
        self.synchronizer = TimeSynchronizer(
            SyncConfig(target_freq_hz=100.0, max_time_diff_sec=0.01)
        )

    @abstractmethod
    def create_validator(self):
        """검증기 생성"""
        pass

    def run(self, splits: List[str] = None) -> dict:
        """전체 파이프라인 실행"""
        if splits is None:
            splits = ["train", "val", "test"]

        results = {}

        # 1. 로더 생성
        loader = self.create_loader()

        # 2. 원시 데이터 로드
        print(f"[{self.config.name}] Loading raw data...")
        raw_data = loader.load_raw()
        print(f"  Loaded {len(raw_data.sensors)} sensors")

        # 3. 검증
        print(f"[{self.config.name}] Validating raw data...")
        validation_reports = self.validator.validate_multi_sensor(raw_data)
        self._print_validation_summary(raw_data)

        # 4. 동기화
        print(f"[{self.config.name}] Synchronizing sensors...")
        sync_result = self.synchronizer.synchronize(raw_data)
        print(f"  Synchronized {len(sync_result.synchronized_data)} sensors")
        print(f"  Time offsets: {sync_result.time_offsets}")
        print(f"  Quality scores: {sync_result.quality_scores}")

        # 5. 정규화 (Train 데이터로 스케일러 학습)
        print(f"[{self.config.name}] Normalizing data...")
        # 먼저 Train 데이터만으로 스케일러 학습

        # 6. 분할
        print(f"[{self.config.name}] Splitting data...")

        return {}

    def _print_validation_summary(self, multi_sensor):
        """검증 결과 요약 출력"""
        reports = self.validator.validate_multi_sensor(self.current_raw_data)
        for name, report in reports.items():
            status = (
                "FAIL"
                if report.has_errors
                else ("WARN" if report.has_warnings else "OK")
            )
            print(f"  {name}: {status} - {report.summary()}")


# =====================================================================
# 데이터셋별 파이프라인
# =====================================================================


class IDF_DSPipeline:
    """IDF-DS 파이프라인 (Non-GPS 고정익 네비게이션)"""

    def __init__(self, config):
        self.config = config
        self._init_components()

    def _init_components(self):
        from .validator import create_validator
        from .normalizer import create_normalizer
        from .splitter import create_splitter
        from .synchronizer import TimeSynchronizer

        self.validator = create_validator()
        self.normalizer = create_normalizer(
            method="standard", feature_range=(0.0, 1.0), per_sensor=True
        )
        self.splitter = create_splitter("temporal")
        self.synchronizer = None  # IDF-DS는 별도 동기화 로직

    def run(self):
        """IDF-DS 파이프라인 실행"""
        pass


class FixedWingPipeline:
    """고정익 파이프라인 (다이브/기만 궤적)"""

    def __init__(self, config):
        self.config = config

    def run(self):
        pass


class IGNPipeline:
    """IGN 고정익 파이프라인"""

    def __init__(self, config):
        self.config = config

    def run(self):
        pass


class UZHFPVPipeline:
    """UZH-FPV 파이프라인 (고속 FPV)"""

    def __init__(self, config):
        self.config = config

    def run(self):
        pass


class FPVAnalogPipeline:
    """FPV 아날로그 오디오 파이프라인"""

    def __init__(self, config):
        self.config = config

    def run(self):
        from preprocessing.loaders import get_loader
        from pathlib import Path

        loader = get_loader("fpv_analog", self.config)
        loader.load_raw()

        output_dir = Path(self.config.processed_path).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        result = loader.process_and_save(output_dir)
        return result


# =====================================================================
# 파이프라인 팩토리
# =====================================================================

PIPELINES = {
    "idf_ds": IDF_DSPipeline,
    "fixed_wing_attitude": FixedWingPipeline,
    "ign_fixed_wing": IGNPipeline,
    "uzh_fpv": UZHFPVPipeline,
    "fpv_analog": FPVAnalogPipeline,
}


def create_pipeline(dataset_name: str, config: "DatasetConfig"):
    """파이프라인 생성 팩토리"""
    if dataset_name not in PIPELINES:
        raise ValueError(f"Unknown pipeline: {dataset_name}")
    return PIPELINES[dataset_name](config)


def run_all_pipelines(configs: Dict[str, any]) -> Dict[str, any]:
    """모든 파이프라인 순차 실행"""
    results = {}
    for name, config in configs.items():
        print(f"\n=== Running pipeline: {name} ===")
        pipeline = create_pipeline(name, config)
        result = pipeline.run()
        results[name] = result
    return results
