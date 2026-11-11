"""
정규화/스케일링 모듈
데이터 정규화, 스케일링, 역변환
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.base import BaseEstimator, TransformerMixin
import joblib
from pathlib import Path


class NormalizationMethod(Enum):
    """정규화 방법"""

    STANDARD = "standard"  # Z-score (mean=0, std=1)
    MINMAX = "minmax"  # [0, 1] 범위
    ROBUST = "robust"  # 중앙값/IQR 기반 (이상치 강건)
    NONE = "none"  # 정규화 안함


@dataclass
class ScalerParams:
    """스케일러 파라미터 저장"""

    method: str
    mean_: Optional[np.ndarray] = None
    std_: Optional[np.ndarray] = None
    min_: Optional[np.ndarray] = None
    max_: Optional[np.ndarray] = None
    center_: Optional[np.ndarray] = None
    scale_: Optional[np.ndarray] = None
    feature_names: List[str] = field(default_factory=list)
    n_features: int = 0


class SensorNormalizer:
    """센서별 정규화기 (센서별 독립적 스케일링)"""

    def __init__(
        self,
        method: str = "standard",
        feature_range: Tuple[float, float] = (0.0, 1.0),
        per_sensor: bool = True,
    ):
        """
        Args:
            method: "standard", "minmax", "robust", "none"
            feature_range: minmax 범위
            per_sensor: True면 센서별 독립 스케일링, False면 전체 통합
        """
        self.method = method
        self.feature_range = feature_range
        self.per_sensor = per_sensor
        self.scalers: Dict[str, Any] = {}
        self.scaler_params: Dict[str, ScalerParams] = {}
        self.is_fitted = False

    def _create_scaler(self, method: str):
        """스케일러 생성"""
        if method == "standard":
            return StandardScaler()
        elif method == "minmax":
            return MinMaxScaler(feature_range=self.feature_range)
        elif method == "robust":
            return RobustScaler()
        elif method == "none":
            return None
        else:
            raise ValueError(f"Unknown normalization method: {method}")

    def fit(
        self, sensor_data: Dict[str, np.ndarray], sensor_columns: Dict[str, List[str]]
    ) -> "SensorNormalizer":
        """
        스케일러 학습

        Args:
            sensor_data: {sensor_name: data_array (N, D)}
            sensor_columns: {sensor_name: column_names}
        """
        self.scalers = {}
        self.scaler_params = {}

        if self.per_sensor:
            # 센서별 독립적 스케일링
            for name, data in sensor_data.items():
                if data.size == 0:
                    continue

                scaler = self._create_scaler(self.method)
                if scaler is not None:
                    scaler.fit(data)
                    self.scalers[name] = scaler

                    # 파라미터 저장
                    params = ScalerParams(
                        method=self.method,
                        feature_names=sensor_columns.get(name, []),
                        n_features=data.shape[1],
                    )

                    if hasattr(scaler, "mean_"):
                        params.mean_ = scaler.mean_.copy()
                    if hasattr(scaler, "std_"):
                        params.std_ = scaler.std_.copy()
                    if hasattr(scaler, "min_"):
                        params.min_ = scaler.min_.copy()
                    if hasattr(scaler, "max_"):
                        params.max_ = scaler.max_.copy()
                    if hasattr(scaler, "center_"):
                        params.center_ = scaler.center_.copy()
                    if hasattr(scaler, "scale_"):
                        params.scale_ = scaler.scale_.copy()

                    self.scaler_params[name] = params
        else:
            # 전체 데이터 통합 스케일링
            all_data = np.vstack([d for d in sensor_data.values() if d.size > 0])
            if all_data.size > 0:
                scaler = self._create_scaler(self.method)
                if scaler is not None:
                    scaler.fit(all_data)
                    self.scalers["_global"] = scaler

                    params = ScalerParams(
                        method=self.method,
                        feature_names=[],
                        n_features=all_data.shape[1],
                    )
                    if hasattr(scaler, "mean_"):
                        params.mean_ = scaler.mean_.copy()
                    if hasattr(scaler, "std_"):
                        params.std_ = scaler.std_.copy()
                    if hasattr(scaler, "min_"):
                        params.min_ = scaler.min_.copy()
                    if hasattr(scaler, "max_"):
                        params.max_ = scaler.max_.copy()
                    if hasattr(scaler, "center_"):
                        params.center_ = scaler.center_.copy()
                    if hasattr(scaler, "scale_"):
                        params.scale_ = scaler.scale_.copy()

                    self.scaler_params["_global"] = params

        self.is_fitted = True
        return self

    def transform(self, sensor_data: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """정규화 적용"""
        if not self.is_fitted:
            raise ValueError("Normalizer not fitted. Call fit() first.")

        result = {}
        for name, data in sensor_data.items():
            if data.size == 0:
                result[name] = data
                continue

            if self.per_sensor and name in self.scalers:
                result[name] = self.scalers[name].transform(data)
            elif not self.per_sensor and "_global" in self.scalers:
                result[name] = self.scalers["_global"].transform(data)
            else:
                result[name] = data

        return result

    def inverse_transform(
        self, sensor_data: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """역변환 (정규화 -> 원본)"""
        if not self.is_fitted:
            raise ValueError("Normalizer not fitted")

        result = {}
        for name, data in sensor_data.items():
            if data.size == 0:
                result[name] = data
                continue

            if self.per_sensor and name in self.scalers:
                result[name] = self.scalers[name].inverse_transform(data)
            elif not self.per_sensor and "_global" in self.scalers:
                result[name] = self.scalers["_global"].inverse_transform(data)
            else:
                result[name] = data

        return result

    def save(self, path: Path) -> None:
        """스케일러 저장"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # 스케일러 저장
        for name, scaler in self.scalers.items():
            joblib.dump(scaler, path / f"scaler_{name}.pkl")

        # 파라미터 저장
        import json

        params_dict = {}
        for name, params in self.scaler_params.items():
            params_dict[name] = {
                "method": params.method,
                "feature_names": params.feature_names,
                "n_features": params.n_features,
                "mean_": params.mean_.tolist() if params.mean_ is not None else None,
                "std_": params.std_.tolist() if params.std_ is not None else None,
                "min_": params.min_.tolist() if params.min_ is not None else None,
                "max_": params.max_.tolist() if params.max_ is not None else None,
                "center_": (
                    params.center_.tolist() if params.center_ is not None else None
                ),
                "scale_": params.scale_.tolist() if params.scale_ is not None else None,
            }

        with open(path / "scaler_params.json", "w") as f:
            json.dump(params_dict, f, indent=2)

        # 설정 저장
        with open(path / "normalizer_config.json", "w") as f:
            json.dump(
                {
                    "method": self.method,
                    "feature_range": self.feature_range,
                    "per_sensor": self.per_sensor,
                    "is_fitted": self.is_fitted,
                },
                f,
                indent=2,
            )

    @classmethod
    def load(cls, path: Path) -> "SensorNormalizer":
        """스케일러 로드"""
        import json

        with open(path / "normalizer_config.json", "r") as f:
            config = json.load(f)

        normalizer = cls(
            method=config["method"],
            feature_range=tuple(config["feature_range"]),
            per_sensor=config["per_sensor"],
        )
        normalizer.is_fitted = config["is_fitted"]

        # 스케일러 로드
        for pkl_file in path.glob("scaler_*.pkl"):
            name = pkl_file.stem.replace("scaler_", "")
            normalizer.scalers[name] = joblib.load(pkl_file)

        # 파라미터 로드
        with open(path / "scaler_params.json", "r") as f:
            params_dict = json.load(f)

        for name, p in params_dict.items():
            params = ScalerParams(
                method=p["method"],
                feature_names=p["feature_names"],
                n_features=p["n_features"],
                mean_=np.array(p["mean_"]) if p["mean_"] is not None else None,
                std_=np.array(p["std_"]) if p["std_"] is not None else None,
                min_=np.array(p["min_"]) if p["min_"] is not None else None,
                max_=np.array(p["max_"]) if p["max_"] is not None else None,
                center_=np.array(p["center_"]) if p["center_"] is not None else None,
                scale_=np.array(p["scale_"]) if p["scale_"] is not None else None,
            )
            normalizer.scaler_params[name] = params

        return normalizer

    def get_feature_stats(self, sensor_name: str) -> Optional[Dict]:
        """특정 센서의 통계 정보 반환"""
        if sensor_name in self.scaler_params:
            params = self.scaler_params[sensor_name]
            return {
                "method": params.method,
                "n_features": params.n_features,
                "feature_names": params.feature_names,
                "mean": params.mean_.tolist() if params.mean_ is not None else None,
                "std": params.std_.tolist() if params.std_ is not None else None,
                "min": params.min_.tolist() if params.min_ is not None else None,
                "max": params.max_.tolist() if params.max_ is not None else None,
            }
        return None


class GlobalNormalizer:
    """전체 데이터 통합 정규화 (단일 스케일러)"""

    def __init__(
        self, method: str = "standard", feature_range: Tuple[float, float] = (0.0, 1.0)
    ):
        self.method = method
        self.feature_range = feature_range
        self.scaler = None
        self.scaler_params: Optional[ScalerParams] = None
        self.is_fitted = False

    def fit(self, data: np.ndarray) -> "GlobalNormalizer":
        self.scaler = self._create_scaler(self.method)
        if self.scaler is not None:
            self.scaler.fit(data)
            self.scaler_params = ScalerParams(
                method=self.method,
                n_features=data.shape[1],
                mean_=(
                    self.scaler.mean_.copy() if hasattr(self.scaler, "mean_") else None
                ),
                std_=self.scaler.std_.copy() if hasattr(self.scaler, "std_") else None,
                min_=self.scaler.min_.copy() if hasattr(self.scaler, "min_") else None,
                max_=self.scaler.max_.copy() if hasattr(self.scaler, "max_") else None,
                center_=(
                    self.scaler.center_.copy()
                    if hasattr(self.scaler, "center_")
                    else None
                ),
                scale_=(
                    self.scaler.scale_.copy()
                    if hasattr(self.scaler, "scale_")
                    else None
                ),
            )
        self.is_fitted = True
        return self

    def _create_scaler(self, method: str):
        if method == "standard":
            return StandardScaler()
        elif method == "minmax":
            return MinMaxScaler(feature_range=self.feature_range)
        elif method == "robust":
            return RobustScaler()
        return None

    def transform(self, data: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.scaler is None:
            return data
        return self.scaler.transform(data)

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.scaler is None:
            return data
        return self.scaler.inverse_transform(data)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        if self.scaler:
            joblib.dump(self.scaler, path / "global_scaler.pkl")

    @classmethod
    def load(cls, path: Path) -> "GlobalNormalizer":
        normalizer = cls()
        scaler_path = path / "global_scaler.pkl"
        if scaler_path.exists():
            normalizer.scaler = joblib.load(scaler_path)
            normalizer.is_fitted = True
        return normalizer


def create_normalizer(
    method: str = "standard",
    feature_range: Tuple[float, float] = (0.0, 1.0),
    per_sensor: bool = True,
) -> SensorNormalizer:
    """정규화기 생성 팩토리"""
    return SensorNormalizer(
        method=method, feature_range=feature_range, per_sensor=per_sensor
    )
