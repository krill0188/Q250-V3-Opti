"""
Tabular Dataset for FALCON, SkyMimic
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import (
    LabelEncoder,
    MinMaxScaler,
    RobustScaler,
    StandardScaler,
)


class TabularDataset:
    """표형 데이터셋 처리 클래스"""

    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.data_cfg = self.config["data"]
        self.preproc_cfg = self.config["preprocessing"]
        self.scaler = None
        self.label_encoder = None
        self.feature_selector = None
        self.selected_features = None

    def load_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """데이터 로드 및 타겟 분리"""
        df = pd.read_csv(self.data_cfg["raw_path"])

        # 타겟 컬럼 자동 감지 (마지막 컬럼이 기본)
        target_col = self.data_cfg.get("target_col")
        if target_col is None:
            target_col = df.columns[-1]

        y = df[target_col].copy()
        X = df.drop(columns=[target_col])

        # 드롭 컬럼 처리
        drop_cols = self.data_cfg.get("drop_cols", [])
        if drop_cols:
            X = X.drop(
                columns=[c for c in drop_cols if c in X.columns], errors="ignore"
            )

        return X, y

    def preprocess(
        self, X: pd.DataFrame, y: pd.Series, fit: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """전처리 파이프라인"""
        # 수치형/범주형 컬럼 분리
        cat_cols = self.data_cfg.get("categorical_cols", [])
        cat_cols = [c for c in cat_cols if c in X.columns]
        num_cols = [c for c in X.columns if c not in cat_cols]

        X_num = X[num_cols].copy()
        X_cat = X[cat_cols].copy() if cat_cols else pd.DataFrame(index=X.index)

        # 1. 수치형 결측치 처리
        X_num = self._handle_missing(X_num, fit)

        # 2. 범주형 인코딩
        if cat_cols:
            X_cat = self._encode_categorical(X_cat, fit)

        # 3. 피처 선택 (수치형만)
        X_num = self._select_features(X_num, y, fit)

        # 4. 스케일링 (수치형만)
        X_num = self._scale_features(X_num, fit)

        # 5. 결합
        if cat_cols:
            X_proc = pd.concat([X_num, X_cat], axis=1)
        else:
            X_proc = X_num

        # 6. 라벨 인코딩
        y_encoded = self._encode_labels(y, fit)

        return X_proc.values, y_encoded

    def _handle_missing(self, X: pd.DataFrame, fit: bool) -> pd.DataFrame:
        strategy = self.preproc_cfg.get("handle_missing", "median")
        if strategy == "drop":
            return X.dropna()

        if fit:
            self.imputer = SimpleImputer(strategy=strategy)
            X_imputed = pd.DataFrame(
                self.imputer.fit_transform(X), columns=X.columns, index=X.index
            )
        else:
            X_imputed = pd.DataFrame(
                self.imputer.transform(X), columns=X.columns, index=X.index
            )
        return X_imputed

    def _encode_categorical(self, X: pd.DataFrame, fit: bool) -> pd.DataFrame:
        """범주형 컬럼 인코딩 (X는 범주형 컬럼만 포함)"""
        X = X.copy()
        for col in X.columns:
            if fit:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
                if not hasattr(self, "label_encoders"):
                    self.label_encoders = {}
                self.label_encoders[col] = le
            else:
                le = self.label_encoders[col]
                # unseen label 처리
                known = set(le.classes_)
                X[col] = (
                    X[col]
                    .astype(str)
                    .apply(lambda x: x if x in known else le.classes_[0])
                )
                X[col] = le.transform(X[col])
        return X

    def _select_features(
        self, X: pd.DataFrame, y: pd.Series, fit: bool
    ) -> pd.DataFrame:
        method = self.preproc_cfg.get("feature_selection", {}).get("method", "none")
        if method == "none":
            return X

        k = self.preproc_cfg.get("feature_selection", {}).get("k", 50)
        k = min(k, X.shape[1])

        if fit:
            if method == "mutual_info":
                self.feature_selector = SelectKBest(mutual_info_classif, k=k)
            elif method == "f_classif":
                self.feature_selector = SelectKBest(f_classif, k=k)
            else:
                return X

            X_selected = self.feature_selector.fit_transform(X, y)
            self.selected_features = X.columns[
                self.feature_selector.get_support()
            ].tolist()
        else:
            if self.feature_selector is None:
                return X
            X_selected = self.feature_selector.transform(X)

        return pd.DataFrame(X_selected, columns=self.selected_features, index=X.index)

    def _scale_features(self, X: pd.DataFrame, fit: bool) -> pd.DataFrame:
        scaler_type = self.preproc_cfg.get("scaler", "standard")
        if scaler_type == "none":
            return X

        scalers = {
            "standard": StandardScaler(),
            "minmax": MinMaxScaler(),
            "robust": RobustScaler(),
        }

        if fit:
            self.scaler = scalers.get(scaler_type, StandardScaler())
            X_scaled = pd.DataFrame(
                self.scaler.fit_transform(X), columns=X.columns, index=X.index
            )
        else:
            if self.scaler is None:
                return X
            X_scaled = pd.DataFrame(
                self.scaler.transform(X), columns=X.columns, index=X.index
            )
        return X_scaled

    def _encode_labels(self, y: pd.Series, fit: bool) -> np.ndarray:
        if fit:
            self.label_encoder = LabelEncoder()
            return self.label_encoder.fit_transform(y)
        else:
            if self.label_encoder is None:
                return y.values
            return self.label_encoder.transform(y)

    def get_splits(
        self, X: np.ndarray, y: np.ndarray
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """Train/Val/Test 분할"""
        test_size = self.data_cfg.get("test_size", 0.15)
        val_size = self.data_cfg.get("val_size", 0.15)
        stratify = self.data_cfg.get("stratify", True)

        # Train + Val / Test
        stratify_arg = y if stratify else None
        X_trainval, X_test, y_trainval, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=self.config["seed"],
            stratify=stratify_arg,
        )

        # Train / Val
        val_size_adjusted = val_size / (1 - test_size)
        stratify_arg = y_trainval if stratify else None
        X_train, X_val, y_train, y_val = train_test_split(
            X_trainval,
            y_trainval,
            test_size=val_size_adjusted,
            random_state=self.config["seed"],
            stratify=stratify_arg,
        )

        return {
            "train": (X_train, y_train),
            "val": (X_val, y_val),
            "test": (X_test, y_test),
        }

    def inverse_transform_labels(self, y_encoded: np.ndarray) -> np.ndarray:
        if self.label_encoder is not None:
            return self.label_encoder.inverse_transform(y_encoded)
        return y_encoded


def load_falcon_data(config_path: str) -> Dict[str, Any]:
    """FALCON 데이터 로드 헬퍼"""
    dataset = TabularDataset(config_path)
    X, y = dataset.load_data()
    X_proc, y_proc = dataset.preprocess(X, y, fit=True)
    splits = dataset.get_splits(X_proc, y_proc)

    return {
        "dataset": dataset,
        "splits": splits,
        "feature_names": dataset.selected_features or list(X.columns),
        "class_names": (
            dataset.label_encoder.classes_ if dataset.label_encoder else None
        ),
        "input_dim": X_proc.shape[1],
        "num_classes": len(np.unique(y_proc)),
    }
