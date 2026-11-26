"""
Sequence Dataset for FAN-GHETS24, FANET
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
from sklearn.feature_selection import VarianceThreshold
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import (
    LabelEncoder,
    MinMaxScaler,
    RobustScaler,
    StandardScaler,
)
import torch
from torch.utils.data import DataLoader, Dataset
import yaml

warnings.filterwarnings("ignore")


class SequenceDataset(Dataset):
    """시퀀스 데이터셋 (가변 길이 시퀀스 패딩/트렁케이션)"""

    def __init__(
        self,
        sequences: List[np.ndarray],
        labels: np.ndarray,
        max_len: int = 2048,
        pad_value: float = 0.0,
    ):
        """
        Args:
            sequences: List of (seq_len, n_features) arrays
            labels: (n_samples,) array
            max_len: 최대 시퀀스 길이
            pad_value: 패딩 값
        """
        self.sequences = sequences
        self.labels = labels
        self.max_len = max_len
        self.pad_value = pad_value

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        seq = self.sequences[idx]
        label = self.labels[idx]

        # 시퀀스 길이 조정
        seq_len = seq.shape[0]
        if seq_len > self.max_len:
            # 랜덤 크롭 또는 앞부분만 사용
            start = np.random.randint(0, seq_len - self.max_len + 1)
            seq = seq[start : start + self.max_len]
            actual_len = self.max_len
        else:
            actual_len = seq_len

        # 패딩
        if seq_len < self.max_len:
            pad_width = ((0, self.max_len - seq_len), (0, 0))
            seq = np.pad(seq, pad_width, mode="constant", constant_values=self.pad_value)

        return {
            "sequence": torch.FloatTensor(seq),
            "label": torch.LongTensor([label])[0],
            "length": torch.LongTensor([actual_len])[0],
        }


class FANGHETSDataset:
    """FAN-GHETS24 데이터셋 로드 및 전처리"""

    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.data_cfg = self.config["data"]
        self.preproc_cfg = self.config["preprocessing"]
        self.max_seq_len = self.data_cfg.get("max_seq_len", 2048)

        self.scaler = None
        self.label_encoder = None
        self.feature_selector = None
        self.selected_features = None

    def load_data(self) -> Tuple[List[np.ndarray], np.ndarray]:
        """파일에서 시퀀스와 라벨 로드"""
        raw_dir = self.data_cfg["raw_dir"]
        label_col = self.data_cfg["label_col"]
        intensity_col = self.data_cfg["intensity_col"]
        drop_cols = self.data_cfg.get("drop_cols", [])

        parquet_files = [f for f in os.listdir(raw_dir) if f.endswith(".parquet")]

        sequences = []
        labels = []
        corrupted = 0

        for f in parquet_files:
            try:
                df = pd.read_parquet(os.path.join(raw_dir, f))

                # 라벨 추출 (파일당 단일 라벨)
                label = df[label_col].iloc[0]
                labels.append(label)

                # 피처 추출 (라벨 컬럼 제외)
                feature_cols = [c for c in df.columns if c not in drop_cols]
                seq = df[feature_cols].values.astype(np.float32)
                sequences.append(seq)

            except Exception as e:
                corrupted += 1
                continue

        print(f"Loaded {len(sequences)} sequences, {corrupted} corrupted")
        return sequences, np.array(labels)

    def preprocess(
        self, sequences: List[np.ndarray], labels: np.ndarray, fit: bool = True
    ) -> Tuple[List[np.ndarray], np.ndarray]:
        """전처리: 스케일링, 라벨 인코딩"""

        # 라벨 인코딩
        if fit:
            self.label_encoder = LabelEncoder()
            labels_encoded = self.label_encoder.fit_transform(labels)
        else:
            if self.label_encoder is None:
                raise ValueError("Label encoder not fitted")
            labels_encoded = self.label_encoder.transform(labels)

        # 시퀀스 스케일링 (전체 시퀀스를 합쳐서 fit)
        if fit:
            self.scaler = self._get_scaler()
            # 전체 데이터 합쳐서 fit
            all_data = np.vstack(sequences)
            self.scaler.fit(all_data)

        # 각 시퀀스 변환
        scaled_sequences = []
        for seq in sequences:
            scaled_seq = self.scaler.transform(seq)
            scaled_sequences.append(scaled_seq.astype(np.float32))

        return scaled_sequences, labels_encoded

    def _get_scaler(self):
        scaler_type = self.preproc_cfg.get("scaler", "standard")
        scalers = {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
        }
        return scalers.get(scaler_type, StandardScaler())

    def get_splits(self, sequences: List[np.ndarray], labels: np.ndarray) -> Dict:
        """Train/Val/Test 분할 (Stratified)"""
        test_size = self.data_cfg.get("test_size", 0.15)
        val_size = self.data_cfg.get("val_size", 0.15)
        stratify = self.data_cfg.get("stratify", True)
        seed = self.config["seed"]

        # 인덱스로 분할
        indices = np.arange(len(sequences))
        stratify_arg = labels if stratify else None

        # Train+Val / Test
        idx_trainval, idx_test = train_test_split(
            indices, test_size=test_size, random_state=seed, stratify=stratify_arg
        )

        # Train / Val
        val_size_adjusted = val_size / (1 - test_size)
        stratify_arg = labels[idx_trainval] if stratify else None
        idx_train, idx_val = train_test_split(
            idx_trainval,
            test_size=val_size_adjusted,
            random_state=seed,
            stratify=stratify_arg,
        )

        def get_split(idxs):
            return [sequences[i] for i in idxs], labels[idxs]

        return {
            "train": get_split(idx_train),
            "val": get_split(idx_val),
            "test": get_split(idx_test),
        }

    def create_dataloaders(
        self, splits: Dict, batch_size: int = 32, num_workers: int = 0
    ) -> Dict[str, DataLoader]:
        """DataLoader 생성"""
        loaders = {}
        for split_name, (seqs, labels) in splits.items():
            dataset = SequenceDataset(seqs, labels, max_len=self.max_seq_len)
            shuffle = split_name == "train"
            loaders[split_name] = DataLoader(
                dataset,
                batch_size=batch_size,
                shuffle=shuffle,
                num_workers=num_workers,
                pin_memory=True,
                collate_fn=self._collate_fn,
            )
        return loaders

    def _collate_fn(self, batch):
        """배치 콜레이트 함수"""
        sequences = torch.stack([item["sequence"] for item in batch])
        labels = torch.stack([item["label"] for item in batch])
        lengths = torch.stack([item["length"] for item in batch])
        return {"sequence": sequences, "label": labels, "length": lengths}

    def inverse_transform_labels(self, labels_encoded: np.ndarray) -> np.ndarray:
        if self.label_encoder is not None:
            return self.label_encoder.inverse_transform(labels_encoded)
        return labels_encoded


def load_fanghets_data(config_path: str) -> Dict[str, Any]:
    """FAN-GHETS24 데이터 로드 헬퍼"""
    dataset = FANGHETSDataset(config_path)

    print("Loading FAN-GHETS24 sequences...")
    sequences, labels = dataset.load_data()

    print("Preprocessing...")
    sequences_proc, labels_proc = dataset.preprocess(sequences, labels, fit=True)

    print("Creating splits...")
    splits = dataset.get_splits(sequences_proc, labels_proc)

    print(
        f"Train: {len(splits['train'][0])}, Val: {len(splits['val'][0])}, Test: {len(splits['test'][0])}"
    )
    print(f"Classes: {dataset.label_encoder.classes_}")
    print(f"Input dim: {sequences_proc[0].shape[1]}")
    print(f"Num classes: {len(dataset.label_encoder.classes_)}")

    return {
        "dataset": dataset,
        "splits": splits,
        "class_names": dataset.label_encoder.classes_,
        "input_dim": sequences_proc[0].shape[1],
        "num_classes": len(dataset.label_encoder.classes_),
    }
