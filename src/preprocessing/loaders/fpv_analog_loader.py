"""
FPV Analog 오디오 데이터셋 로더 - 전체 디코딩 후 분할 저장
대용량 오디오 데이터를 순차 디코딩 후 메모리 효율적으로 분할 저장
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import io
import soundfile as sf

from ..core.base_loader import BaseLoader, SensorData, MultiSensorData
from ..config import DatasetConfig


# 모듈 레벨 함수 (multiprocessing pickle용 - macOS spawn 호환)
def _decode_wav_bytes_sf(
    wav_bytes: bytes, target_sr: int = 16000, max_duration: float = 10.0
):
    """단일 WAV 바이트 디코딩 (soundfile 사용 - 고속)"""
    try:
        audio_data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")

        if sr != target_sr:
            return None

        # 모노 변환
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # 정규화
        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0

        max_samples = int(max_duration * target_sr)
        if len(audio_data) > max_samples:
            audio_data = audio_data[:max_samples]
        elif len(audio_data) < max_samples:
            audio_data = np.pad(audio_data, (0, max_samples - len(audio_data)))

        return audio_data.astype(np.float32)
    except Exception:
        return None


class FPVAnalogLoader(BaseLoader):
    """FPV Analog 오디오 데이터셋 로더 (전체 디코딩 후 분할 저장)"""

    def __init__(self, config: DatasetConfig):
        super().__init__(config)
        self.target_sr = 16000
        self.max_duration = 10.0

    def get_supported_sensors(self) -> List[str]:
        return ["audio", "label"]

    def load_raw(self) -> MultiSensorData:
        """메타데이터만 로드 (실제 오디오는 process_and_save에서 처리)"""
        data_dir = self.raw_path / "data"
        parquet_files = sorted(data_dir.glob("train-*.parquet"))

        if not parquet_files:
            raise FileNotFoundError(f"No parquet files in {data_dir}")

        total_samples = 0
        for pf in parquet_files:
            df = pd.read_parquet(pf, columns=["label"])
            total_samples += len(df)

        timestamps = np.arange(total_samples, dtype=np.float64)
        dummy_audio = np.zeros(
            (total_samples, int(self.max_duration * self.target_sr)), dtype=np.float32
        )
        dummy_labels = np.zeros((total_samples, 1), dtype=np.int64)

        sensors = {
            "audio": SensorData(
                name="audio",
                timestamp=timestamps,
                data=dummy_audio,
                columns=[f"sample_{i}" for i in range(dummy_audio.shape[1])],
                frequency_hz=float(self.target_sr),
                coordinate_frame="TIME",
                metadata={
                    "max_duration": self.max_duration,
                    "num_files": len(parquet_files),
                    "lazy": True,
                },
            ),
            "label": SensorData(
                name="label",
                timestamp=timestamps,
                data=dummy_labels,
                columns=["label"],
                frequency_hz=1.0,
                coordinate_frame="NONE",
                metadata={"classes": {0: "no_drone", 1: "drone"}, "lazy": True},
            ),
        }

        self._parquet_files = parquet_files

        return MultiSensorData(
            sensors=sensors,
            reference_sensor="audio",
            metadata={
                "source": "FPV-Analog",
                "total_samples": total_samples,
                "lazy": True,
            },
        )

    def process_and_save(
        self, output_dir: Path, split_ratios: tuple = (0.7, 0.15, 0.15)
    ) -> Dict:
        """전체 파일 순차 디코딩 후 메모리 효율적으로 분할 저장"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        train_ratio, val_ratio, test_ratio = split_ratios

        split_dirs = {}
        for split_name in ["train", "val", "test"]:
            d = output_dir / split_name
            d.mkdir(parents=True, exist_ok=True)
            split_dirs[split_name] = d

        # split별 데이터 누적 (리스트로)
        split_audio = {"train": [], "val": [], "test": []}
        split_labels = {"train": [], "val": [], "test": []}
        split_counts = {"train": 0, "val": 0, "test": 0}

        # 결정론적 split 할당을 위한 시드
        np.random.seed(42)

        print("Processing parquet files...")
        for pf in self._parquet_files:
            print(f"  Processing {pf.name}...")
            df = pd.read_parquet(pf)
            n_samples = len(df)

            wav_bytes_list = [row["audio"]["bytes"] for _, row in df.iterrows()]
            labels = df["label"].values

            # 순차 디코딩 (빠름: ~18초/4624샘플)
            print(f"  Decoding {n_samples} samples...")
            for wb, label in zip(wav_bytes_list, labels):
                audio = _decode_wav_bytes_sf(wb, self.target_sr, self.max_duration)
                if audio is not None:
                    r = np.random.random()
                    if r < train_ratio:
                        split_audio["train"].append(audio)
                        split_labels["train"].append(label)
                    elif r < train_ratio + val_ratio:
                        split_audio["val"].append(audio)
                        split_labels["val"].append(label)
                    else:
                        split_audio["test"].append(audio)
                        split_labels["test"].append(label)

            # 주기적 저장으로 메모리 관리 (매 500샘플마다)
            for split_name in ["train", "val", "test"]:
                if len(split_audio[split_name]) >= 500:
                    print(
                        f"    Saving {split_name} split ({len(split_audio[split_name])} samples)..."
                    )
                    self._save_split_incremental(
                        split_name,
                        split_dirs[split_name],
                        split_audio[split_name],
                        split_labels[split_name],
                        split_counts,
                    )
                    print(f"    Saved {split_name}")
                    # 메모리 해제
                    split_audio[split_name].clear()
                    split_labels[split_name].clear()

        # 파일 처리 완료 후 남은 데이터 플러시
        for split_name in ["train", "val", "test"]:
            if split_audio[split_name]:
                print(
                    f"    Flushing {split_name} split ({len(split_audio[split_name])} samples)..."
                )
                self._save_split_incremental(
                    split_name,
                    split_dirs[split_name],
                    split_audio[split_name],
                    split_labels[split_name],
                    split_counts,
                )
                print(f"    Flushed {split_name}")
                split_audio[split_name].clear()
                split_labels[split_name].clear()

        print(
            f"Split counts - train: {split_counts['train']}, val: {split_counts['val']}, test: {split_counts['test']}"
        )

        # 각 split별 메타데이터 저장
        for split_name in ["train", "val", "test"]:
            split_dir = split_dirs[split_name]
            chunk_files = sorted(split_dir.glob(".chunk_*.npz"))

            if not chunk_files:
                print(f"  {split_name}: SKIPPED (empty)")
                continue

            # 메타데이터 저장
            first_chunk = np.load(chunk_files[0])
            audio_shape = (split_counts[split_name], first_chunk["audio"].shape[1])
            label_shape = (split_counts[split_name], 1)

            import json

            metadata = {
                "sensors": {
                    "audio": {
                        "columns": [f"sample_{i}" for i in range(audio_shape[1])],
                        "frequency_hz": float(self.target_sr),
                        "coordinate_frame": "TIME",
                        "shape": list(audio_shape),
                    },
                    "label": {
                        "columns": ["label"],
                        "frequency_hz": 1.0,
                        "coordinate_frame": "NONE",
                        "shape": list(label_shape),
                    },
                },
                "reference_sensor": "audio",
                "synchronized": False,
            }
            meta_path = split_dir / "metadata.json"
            temp_path = split_dir / f"metadata.json.tmp"
            with open(temp_path, "w") as f:
                json.dump(metadata, f, indent=2, default=str)
                f.flush()
                import os

                os.fsync(f.fileno())
            temp_path.replace(meta_path)

            print(
                f"  {split_name}: {split_counts[split_name]} samples, metadata.json written"
            )

        return {
            "train": split_counts["train"],
            "val": split_counts["val"],
            "test": split_counts["test"],
        }

    def _save_split_incremental(
        self, split_name, split_dir, audio_list, label_list, split_counts
    ):
        """분할 데이터를 청크 파일로 증분 저장"""
        print(f"      _save_split_incremental: stacking {len(audio_list)} arrays...")
        chunk_audio = np.stack(audio_list)
        print(f"      stacked: {chunk_audio.shape}")
        chunk_labels = np.array(label_list, dtype=np.int64).reshape(-1, 1)
        n = len(chunk_audio)

        chunk_timestamps = np.arange(
            split_counts[split_name], split_counts[split_name] + n, dtype=np.float64
        )
        split_counts[split_name] += n

        chunk_idx = len(list(split_dir.glob(".chunk_*.npz")))
        chunk_file = split_dir / f".chunk_{chunk_idx:06d}.npz"
        print(f"      saving to {chunk_file}...")
        # Use uncompressed for speed, compression can be done later if needed
        np.savez(
            chunk_file,
            timestamp=chunk_timestamps,
            audio=chunk_audio,
            label=chunk_labels,
        )
        print(f"      saved")


def create_fpv_analog_loader(config: DatasetConfig) -> FPVAnalogLoader:
    return FPVAnalogLoader(config)
