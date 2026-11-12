#!/usr/bin/env python3
"""
DroneAudioDataset 전처리 파이프라인
Binary 및 Multiclass 드론 오디오 분류 데이터셋 전처리
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from pathlib import Path
from tqdm import tqdm

from src.preprocessing.loaders import get_loader
from src.preprocessing.config import DATASET_CONFIGS, SplitConfig, DatasetConfig
from src.preprocessing.core.synchronizer import TimeSynchronizer, SyncConfig
from src.preprocessing.core.normalizer import SensorNormalizer, create_normalizer
from src.preprocessing.core.splitter import create_splitter
from src.preprocessing.core.base_loader import MultiSensorData, SensorData

import numpy as np
import json


def process_drone_audio():
    """DroneAudioDataset 전처리 메인 함수"""

    config_name = "drone_audio"
    config = DATASET_CONFIGS["drone_audio"]

    print(f"=== Processing {config.name} ===")
    print(f"Raw data path: {config.raw_data_path}")
    print(f"Processed path: {config.processed_path}")

    # Create output directories
    output_dir = Path(config.processed_path).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create loader with custom audio config
    from src.preprocessing.loaders.drone_audio_loader import (
        DroneAudioLoader,
        AudioConfig,
    )
    from src.preprocessing.config import DatasetConfig

    audio_config = AudioConfig(
        sample_rate=16000,
        n_mfcc=40,
        n_fft=1024,
        hop_length=512,
        n_mels=128,
        max_duration=5.0,
        feature_type="mfcc",
    )

    # Create a new config with the raw path expanded
    config_dict = {k: v for k, v in config.__dict__.items()}
    config_dict["raw_data_path"] = Path(config.raw_data_path).expanduser()
    config_dict["processed_path"] = Path(config.processed_path).expanduser()
    config = DatasetConfig(**config_dict)

    loader = DroneAudioLoader(
        config,
        AudioConfig(
            sample_rate=16000,
            n_mfcc=40,
            n_fft=1024,
            hop_length=512,
            n_mels=128,
            max_duration=5.0,
            feature_type="mfcc",
        ),
    )

    # Load binary dataset
    print("\n=== Loading Binary Dataset ===")
    bin_features, bin_labels = loader.load_binary()
    print(f"Binary features shape: {bin_features.shape}")
    print(f"Binary labels shape: {bin_labels.shape}")
    print(f"Class distribution: {np.bincount(bin_labels)}")

    # Load multiclass dataset
    print("\n=== Loading Multiclass Dataset ===")
    mc_features, mc_labels = loader.load_multiclass()
    print(f"Multiclass features shape: {mc_features.shape}")
    print(f"Multiclass labels shape: {mc_labels.shape}")
    print(f"Class distribution: {np.bincount(mc_labels)}")

    # Create normalized features for binary
    print("\n=== Normalizing Binary Features ===")
    bin_normalizer = SensorNormalizer(
        method="standard", feature_range=(0.0, 1.0), per_sensor=True
    )
    bin_features_flat = bin_features.reshape(bin_features.shape[0], -1)
    bin_normalizer.fit(
        {0: bin_features_flat},
        {0: [f"feat_{i}" for i in range(bin_features_flat.shape[1])]},
    )
    bin_features_norm = bin_normalizer.transform({0: bin_features_flat})[0]
    bin_features_norm = bin_features_norm.reshape(bin_features.shape)

    # Create normalized multiclass features
    print("\n=== Normalizing Multiclass Features ===")
    mc_normalizer = SensorNormalizer(
        method="standard", feature_range=(0.0, 1.0), per_sensor=True
    )
    mc_features_flat = mc_features.reshape(mc_features.shape[0], -1)
    mc_normalizer.fit(
        {0: mc_features_flat},
        {0: [f"feat_{i}" for i in range(mc_features_flat.shape[1])]},
    )
    mc_features_norm = mc_normalizer.transform({0: mc_features_flat})[0]
    mc_features_norm = mc_features_norm.reshape(mc_features.shape)

    # Create SensorData objects for splitting
    print("\n=== Creating SensorData Objects ===")

    # Binary sensor data
    bin_flat = bin_features.reshape(bin_features.shape[0], -1)
    bin_sensor_labeled = SensorData(
        name="audio_binary",
        timestamp=np.arange(len(bin_labels)),
        data=np.column_stack(
            [bin_features.reshape(len(bin_features), -1), bin_labels.reshape(-1, 1)]
        ),
        columns=[
            f"feat_{i}" for i in range(bin_features.shape[1] * bin_features.shape[2])
        ]
        + ["label"],
        frequency_hz=16000.0,
        coordinate_frame="AUDIO",
        metadata={"task": "binary", "classes": ["unknown", "yes_drone"]},
    )

    mc_sensor_labeled = SensorData(
        name="audio_multiclass",
        timestamp=np.arange(len(mc_labels)),
        data=np.column_stack(
            [mc_features.reshape(len(mc_features), -1), mc_labels.reshape(-1, 1)]
        ),
        columns=[
            f"feat_{i}" for i in range(mc_features.shape[1] * mc_features.shape[2])
        ]
        + ["label"],
        frequency_hz=16000.0,
        coordinate_frame="AUDIO",
        metadata={"task": "multiclass", "classes": ["unknown", "bebop_1", "membo_1"]},
    )

    bin_multi = MultiSensorData(
        sensors={"audio_binary": bin_sensor_labeled}, reference_sensor="audio_binary"
    )

    mc_multi = MultiSensorData(
        sensors={"audio_multiclass": mc_sensor_labeled},
        reference_sensor="audio_multiclass",
    )

    # Split using SplitConfig
    split_config = SplitConfig(
        train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, temporal_split=False
    )
    splitter = create_splitter("stratified", label_column="label")

    print("\n=== Splitting Binary Dataset ===")
    bin_splits = splitter.split(
        bin_multi,
        config=SplitConfig(
            train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, temporal_split=False
        ),
    )

    print("Binary splits:")
    for split_enum, split_data in bin_splits.items():
        print(
            f"  {split_enum.value}: {len(list(split_data.sensors.values())[0])} samples"
        )

    print("\n=== Splitting Multiclass Dataset ===")
    mc_splits = splitter.split(
        mc_multi,
        config=SplitConfig(
            train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, temporal_split=False
        ),
    )
    print("Multiclass splits:")
    for split_enum, split_data in mc_splits.items():
        print(
            f"  {split_enum.value}: {len(list(split_data.sensors.values())[0])} samples"
        )

    # Save results
    output_dir = Path("~/data/drone_datasets/processed/drone_audio").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save binary splits
    for split_enum, split_data in bin_splits.items():
        split_name = split_enum.value
        split_dir = (
            Path("~/data/drone_datasets/processed/drone_audio").expanduser()
            / "binary"
            / split_name
        )
        split_dir.mkdir(parents=True, exist_ok=True)

        sensor_data = list(split_data.sensors.values())[0]
        data = sensor_data.data
        features = data[:, :-1]
        labels = data[:, -1].astype(int)

        np.savez_compressed(
            Path("~/data/drone_datasets/processed/drone_audio").expanduser()
            / "binary"
            / split_name
            / "features.npz",
            features=features,
            labels=labels,
        )

        metadata = {
            "num_samples": len(labels),
            "feature_shape": features.shape[1:],
            "classes": ["unknown", "yes_drone"],
            "task": "binary",
            "source": "DroneAudioDataset",
        }
        with open(
            Path("~/data/drone_datasets/processed/drone_audio").expanduser()
            / "binary"
            / split_name
            / "metadata.json",
            "w",
        ) as f:
            json.dump(metadata, f, indent=2)

    # Save multiclass splits
    for split_enum, split_data in mc_splits.items():
        split_name = split_enum.value
        split_dir = (
            Path("~/data/drone_datasets/processed/drone_audio").expanduser()
            / "multiclass"
            / split_name
        )
        split_dir.mkdir(parents=True, exist_ok=True)

        sensor_data = list(split_data.sensors.values())[0]
        data = sensor_data.data
        features = data[:, :-1]
        labels = data[:, -1].astype(int)

        np.savez_compressed(
            Path("~/data/drone_datasets/processed/drone_audio").expanduser()
            / "multiclass"
            / split_name
            / "features.npz",
            features=features,
            labels=labels,
        )

        metadata = {
            "num_samples": len(labels),
            "feature_shape": features.shape[1:],
            "classes": ["unknown", "bebop_1", "membo_1"],
            "task": "multiclass",
            "source": "DroneAudioDataset",
        }
        with open(
            Path("~/data/drone_datasets/processed/drone_audio").expanduser()
            / "multiclass"
            / split_name
            / "metadata.json",
            "w",
        ) as f:
            json.dump(metadata, f, indent=2)

    print("\n=== All done! ===")
    print(f"Results saved to: {output_dir}")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import numpy as np
    from pathlib import Path
    from tqdm import tqdm

    from src.preprocessing.loaders import get_loader
    from src.preprocessing.config import DATASET_CONFIGS, SplitConfig, DatasetConfig
    from src.preprocessing.core.synchronizer import TimeSynchronizer, SyncConfig
    from src.preprocessing.core.normalizer import SensorNormalizer, create_normalizer
    from src.preprocessing.core.splitter import create_splitter
    from src.preprocessing.core.base_loader import MultiSensorData, SensorData
    from src.preprocessing.loaders.drone_audio_loader import (
        DroneAudioLoader,
        AudioConfig,
    )

    process_drone_audio()
