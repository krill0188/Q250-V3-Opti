"""
Drone Data Preprocessing Loaders Package
"""

from .idf_ds_loader import IDF_DSLoader
from .ign_fixed_wing_loader import IGNFixedWingLoader
from .uzh_fpv_loader import UZHFPVLoader
from .fpv_analog_loader import FPVAnalogLoader
from .fixed_wing_attitude_loader import FixedWingAttitudeLoader
from .drone_audio_loader import DroneAudioLoader, AudioConfig, create_drone_audio_loader

from ..config import DatasetConfig

__all__ = [
    "IDF_DSLoader",
    "IGNFixedWingLoader",
    "UZHFPVLoader",
    "FPVAnalogLoader",
    "FixedWingAttitudeLoader",
    "DroneAudioLoader",
    "AudioConfig",
    "create_drone_audio_loader",
]


def get_loader(dataset_name: str, config: DatasetConfig):
    """Factory function to get appropriate loader instance"""
    loaders = {
        "idf_ds": lambda c: IDF_DSLoader(c),
        "ign_fixed_wing": lambda c: IGNFixedWingLoader(c),
        "uzh_fpv": lambda c: UZHFPVLoader(c),
        "fpv_analog": lambda c: FPVAnalogLoader(c),
        "fixed_wing_attitude": lambda c: FixedWingAttitudeLoader(c),
        "drone_audio": lambda c: DroneAudioLoader(c, AudioConfig()),
    }

    if dataset_name not in loaders:
        raise ValueError(
            f"Unknown dataset: {dataset_name}. Available: {list(loaders.keys())}"
        )

    return loaders[dataset_name](config)
