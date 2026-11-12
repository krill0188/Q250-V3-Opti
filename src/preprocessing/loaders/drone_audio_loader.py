"""
DroneAudioDataset Loader
Binary and multiclass drone audio detection dataset.
"""

import os
import numpy as np
import librosa
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from tqdm import tqdm
import json

from ..core.base_loader import BaseLoader, SensorData, MultiSensorData
from ..config import DatasetConfig


@dataclass
class AudioConfig:
    """Audio processing configuration"""

    sample_rate: int = 16000
    n_mfcc: int = 40
    n_fft: int = 1024
    hop_length: int = 512
    n_mels: int = 128
    max_duration: float = 5.0  # seconds
    feature_type: str = "mfcc"  # "mfcc", "mel", "mel_mfcc"


class DroneAudioLoader(BaseLoader):
    """DroneAudioDataset Loader for binary and multiclass classification"""

    def __init__(self, config: DatasetConfig, audio_config: AudioConfig = None):
        super().__init__(config)
        self.audio_config = audio_config or AudioConfig()
        self.binary_classes = ["unknown", "yes_drone"]
        self.multiclass_classes = ["unknown", "bebop_1", "membo_1"]

    def get_supported_sensors(self) -> List[str]:
        return ["audio_binary", "audio_multiclass"]

    def _find_audio_files(
        self, root_dir: Path, class_dirs: List[str]
    ) -> Dict[str, List[Path]]:
        """Find all audio files organized by class"""
        files_by_class = {}
        for class_name in class_dirs:
            class_dir = Path(root_dir) / class_name
            if class_dir.exists():
                files = list(class_dir.glob("*.wav"))
                if files:
                    files_by_class[class_name] = files
                    print(f"  {class_name}: {len(files)} files")
        return files_by_class

    def _load_audio_file(self, file_path: Path) -> Tuple[np.ndarray, int]:
        """Load audio file and resample if needed"""
        try:
            audio, sr = librosa.load(
                file_path, sr=self.audio_config.sample_rate, mono=True
            )

            # Trim or pad to max_duration
            max_samples = int(
                self.audio_config.max_duration * self.audio_config.sample_rate
            )
            if len(audio) > max_samples:
                audio = audio[:max_samples]
            elif len(audio) < max_samples:
                audio = np.pad(audio, (0, max_samples - len(audio)), mode="constant")

            return audio, sr
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None, None

    def _extract_features(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract features from audio"""
        if self.audio_config.feature_type == "mfcc":
            mfcc = librosa.feature.mfcc(
                y=audio,
                sr=sr,
                n_mfcc=self.audio_config.n_mfcc,
                n_fft=self.audio_config.n_fft,
                hop_length=self.audio_config.hop_length,
            )
            return mfcc.T  # (time, n_mfcc)
        elif self.audio_config.feature_type == "mel":
            mel = librosa.feature.melspectrogram(
                y=audio,
                sr=sr,
                n_mels=self.audio_config.n_mels,
                n_fft=self.audio_config.n_fft,
                hop_length=self.audio_config.hop_length,
            )
            mel_db = librosa.power_to_db(mel, ref=np.max)
            return mel_db.T  # (time, n_mels)
        elif self.audio_config.feature_type == "mel_mfcc":
            mel = librosa.feature.melspectrogram(
                y=audio,
                sr=sr,
                n_mels=self.audio_config.n_mels,
                n_fft=self.audio_config.n_fft,
                hop_length=self.audio_config.hop_length,
            )
            mel_db = librosa.power_to_db(mel, ref=np.max)
            mfcc = librosa.feature.mfcc(S=mel_db, n_mfcc=self.audio_config.n_mfcc)
            # Concatenate mel and mfcc
            combined = np.vstack([mel_db, mfcc]).T
            return combined
        else:
            raise ValueError(f"Unknown feature type: {self.audio_config.feature_type}")

    def _process_class_files(
        self, files_by_class: Dict[str, List[Path]], class_names: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Process files for given classes"""
        all_features = []
        all_labels = []

        for class_idx, class_name in enumerate(class_names):
            if class_name not in files_by_class:
                continue
            files = files_by_class[class_name]
            print(f"Loading {class_name}: {len(files)} files")

            for file_path in tqdm(files, desc=f"Processing {class_name}"):
                audio, sr = self._load_audio_file(file_path)
                if audio is None:
                    continue
                features = self._extract_features(audio, sr)
                all_features.append(features)
                all_labels.append(class_idx)

        if not all_features:
            raise ValueError("No audio files loaded")

        # Pad sequences to same length
        max_len = max(f.shape[0] for f in all_features)
        feature_dim = all_features[0].shape[1]

        padded_features = np.zeros((len(all_features), max_len, feature_dim))
        for i, feat in enumerate(all_features):
            padded_features[i, : feat.shape[0]] = feat

        labels = np.array(all_labels)
        return padded_features, labels

    def load_binary(self) -> Tuple[np.ndarray, np.ndarray]:
        """Load binary classification dataset (unknown vs yes_drone)"""
        binary_root = Path(self.raw_path) / "Binary_Drone_Audio"
        files_by_class = self._find_audio_files(binary_root, self.binary_classes)
        return self._process_class_files(files_by_class, self.binary_classes)

    def load_multiclass(self) -> Tuple[np.ndarray, np.ndarray]:
        """Load multiclass dataset (unknown, bebop_1, membo_1)"""
        multiclass_root = Path(self.raw_path) / "Multiclass_Drone_Audio"
        files_by_class = self._find_audio_files(
            multiclass_root, self.multiclass_classes
        )
        return self._process_class_files(files_by_class, self.multiclass_classes)

    def load_raw(self):
        """Load both binary and multiclass datasets"""
        print("Loading binary dataset...")
        bin_features, bin_labels = self.load_binary()

        print("Loading multiclass dataset...")
        mc_features, mc_labels = self.load_multiclass()

        # Store feature dimensions for metadata
        self._bin_feat_dim = (
            bin_features.shape[1] * bin_features.shape[2]
        )  # time * features
        self._mc_feat_dim = mc_features.shape[1] * mc_features.shape[2]

        # Create metadata for each
        bin_metadata = {
            "task": "binary",
            "classes": self.binary_classes,
            "feature_shape": [bin_features.shape[1], bin_features.shape[2]],
            "num_samples": len(bin_features),
        }

        mc_metadata = {
            "task": "multiclass",
            "classes": self.multiclass_classes,
            "feature_shape": [mc_features.shape[1], mc_features.shape[2]],
            "num_samples": len(mc_features),
        }

        # We'll return the raw features and labels, let the pipeline handle the rest
        return {
            "binary": {
                "features": bin_features,
                "labels": bin_labels,
                "metadata": bin_metadata,
            },
            "multiclass": {
                "features": mc_features,
                "labels": mc_labels,
                "metadata": mc_metadata,
            },
        }


def create_drone_audio_loader(
    config: DatasetConfig, audio_config: AudioConfig = None
) -> DroneAudioLoader:
    return DroneAudioLoader(config, audio_config)
