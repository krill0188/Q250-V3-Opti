"""
데이터셋별 로더 팩토리
"""

from .idf_ds_loader import IDF_DSLoader, create_idf_ds_loader
from .fpv_analog_loader import FPVAnalogLoader, create_fpv_analog_loader
from .fixed_wing_attitude_loader import (
    FixedWingAttitudeLoader,
    create_fixed_wing_attitude_loader,
)
from .ign_fixed_wing_loader import IGNFixedWingLoader, create_ign_fixed_wing_loader
from .uzh_fpv_loader import UZHFPVLoader, create_uzh_fpv_loader

# 로더 레지스트리
LOADERS = {
    "idf_ds": create_idf_ds_loader,
    "fpv_analog": create_fpv_analog_loader,
    "fixed_wing_attitude": create_fixed_wing_attitude_loader,
    "ign_fixed_wing": create_ign_fixed_wing_loader,
    "uzh_fpv": create_uzh_fpv_loader,
}


def get_loader(dataset_name: str, config):
    """데이터셋 이름으로 로더 생성"""
    if dataset_name not in LOADERS:
        raise ValueError(
            f"Unknown dataset: {dataset_name}. Available: {list(LOADERS.keys())}"
        )
    return LOADERS[dataset_name](config)


def list_available_loaders() -> list:
    """사용 가능한 로더 목록"""
    return list(LOADERS.keys())
