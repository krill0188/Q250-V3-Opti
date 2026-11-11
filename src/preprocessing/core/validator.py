"""
데이터 품질 검증 모듈
데이터 무결성, 완전성, 일관성 검증
"""

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Callable, Any

from .base_loader import SensorData, MultiSensorData
from ..config import DatasetConfig


class Severity(Enum):
    """심각도 레벨"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """검증 이슈"""

    severity: str
    sensor: str
    check: str
    message: str
    details: dict = field(default_factory=dict)

    def __str__(self):
        return f"[{self.severity.upper()}] {self.sensor}: {self.check} - {self.message}"


@dataclass
class ValidationReport:
    """검증 리포트"""

    sensor: str
    total_samples: int
    duration_sec: float
    frequency_hz: float
    issues: List[Any] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(i.severity in ["error", "critical"] for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def summary(self) -> str:
        errors = sum(1 for i in self.issues if i.severity in ["error", "critical"])
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        infos = sum(1 for i in self.issues if i.severity == "info")
        return f"Errors: {errors}, Warnings: {warnings}, Infos: {infos}"


class DataValidator:
    """데이터 품질 검증기"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.checks = []
        self._register_default_checks()

    def _register_default_checks(self):
        """기본 검증 규칙 등록"""
        self.add_check(
            "timestamp_monotonic", self._check_timestamp_monotonic, "critical"
        )
        self.add_check("no_nan_values", self._check_no_nan, "error")
        self.add_check("no_inf_values", self._check_no_inf, "error")
        self.add_check("frequency_consistency", self._check_frequency, "warning")
        self.add_check("timestamp_gaps", self._check_timestamp_gaps, "warning")
        self.add_check("outlier_detection", self._check_outliers, "info")
        self.add_check("constant_values", self._check_constant, "info")
        self.add_check("sensor_range", self._check_sensor_range, "warning")

    def add_check(self, name: str, func: callable, severity: str = "warning"):
        """검증 규칙 추가"""
        self.checks.append({"name": name, "func": func, "severity": severity})

    def validate_sensor(
        self, sensor_data: "SensorData", sensor_name: str
    ) -> "ValidationReport":
        """단일 센서 데이터 검증"""
        from .base_loader import SensorData

        report = ValidationReport(
            sensor="", total_samples=0, duration_sec=0.0, frequency_hz=0.0
        )

        report.sensor = sensor_data.name
        report.total_samples = len(sensor_data)
        report.duration_sec = sensor_data.get_duration_sec()
        report.frequency_hz = sensor_data.frequency_hz

        # 기본 통계
        if len(sensor_data.data) > 0:
            report.stats = {
                "mean": np.mean(sensor_data.data, axis=0).tolist(),
                "std": np.std(sensor_data.data, axis=0).tolist(),
                "min": np.min(sensor_data.data, axis=0).tolist(),
                "max": np.max(sensor_data.data, axis=0).tolist(),
            }

        # 각 검증 실행
        for check in self.checks:
            try:
                issues = check["func"](sensor_data)
                for issue in issues:
                    issue.severity = check["severity"]
                    issue.sensor = sensor_data.name
                    report.issues.append(issue)
            except Exception as e:
                report.issues.append(
                    ValidationIssue(
                        severity="error",
                        sensor=sensor_data.name,
                        check=check["name"],
                        message=f"Check failed: {str(e)}",
                    )
                )

        return report

    def validate_multi_sensor(
        self, multi_sensor: "MultiSensorData"
    ) -> Dict[str, "ValidationReport"]:
        """다중 센서 검증"""
        reports = {}
        for name, sensor in multi_sensor.sensors.items():
            reports[sensor.name] = self.validate_sensor(sensor, sensor.name)
        return reports

    # === 기본 검증 함수들 ===

    def _check_timestamp_monotonic(self, sensor: "SensorData") -> List:
        """타임스탬프 단조 증가 확인"""
        issues = []
        if len(sensor.timestamp) < 2:
            return issues

        diffs = np.diff(sensor.timestamp)
        non_monotonic = np.where(diffs <= 0)[0]

        if len(non_monotonic) > 0:
            issues.append(
                ValidationIssue(
                    severity="critical",
                    sensor="",
                    check="timestamp_monotonic",
                    message=f"Timestamp not monotonic at {len(non_monotonic)} positions",
                    details={"indices": non_monotonic.tolist()[:10]},
                )
            )
        return issues

    def _check_no_nan(self, sensor: "SensorData") -> List:
        """NaN 값 확인"""
        issues = []
        nan_mask = np.isnan(sensor.data)
        if np.any(nan_mask):
            nan_count = np.sum(nan_mask)
            issues.append(
                ValidationIssue(
                    severity="error",
                    sensor="",
                    check="no_nan_values",
                    message=f"Found {nan_count} NaN values",
                    details={"nan_ratio": float(nan_count / sensor.data.size)},
                )
            )
        return issues

    def _check_no_inf(self, sensor: "SensorData") -> List:
        """Inf 값 확인"""
        issues = []
        inf_mask = np.isinf(sensor.data)
        if np.any(inf_mask):
            inf_count = np.sum(inf_mask)
            issues.append(
                ValidationIssue(
                    severity="error",
                    sensor="",
                    check="no_inf_values",
                    message=f"Found {inf_count} Inf values",
                    details={"inf_ratio": float(inf_count / sensor.data.size)},
                )
            )
        return issues

    def _check_frequency(self, sensor: "SensorData") -> List:
        """샘플링 주파수 일관성 확인"""
        issues = []
        if len(sensor.timestamp) < 2:
            return issues

        diffs = np.diff(sensor.timestamp)
        expected_interval = 1.0 / sensor.frequency_hz
        actual_intervals = diffs

        # 주파수 편차 확인
        deviation = np.abs(actual_intervals - expected_interval) / expected_interval
        max_deviation = np.max(deviation)
        mean_deviation = np.mean(deviation)

        if max_deviation > 0.1:  # 10% 이상 편차
            issues.append(
                ValidationIssue(
                    severity="warning",
                    sensor="",
                    check="frequency_consistency",
                    message=f"Frequency deviation: max={max_deviation:.2%}, mean={mean_deviation:.2%}",
                    details={
                        "max_deviation": float(max_deviation),
                        "mean_deviation": float(mean_deviation),
                    },
                )
            )
        return issues

    def _check_timestamp_gaps(self, sensor: "SensorData") -> List:
        """타임스탬프 갭 확인"""
        issues = []
        if len(sensor.timestamp) < 2:
            return issues

        diffs = np.diff(sensor.timestamp)
        expected_interval = 1.0 / sensor.frequency_hz
        gap_threshold = expected_interval * 5  # 5배 이상이면 갭으로 간주

        large_gaps = np.where(diffs > gap_threshold)[0]
        if len(large_gaps) > 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    sensor="",
                    check="timestamp_gaps",
                    message=f"Found {len(large_gaps)} timestamp gaps (>5x expected interval)",
                    details={
                        "gap_indices": large_gaps.tolist()[:10],
                        "max_gap_sec": float(np.max(diffs)),
                    },
                )
            )
        return issues

    def _check_outliers(self, sensor: "SensorData") -> List:
        """이상치 탐지 (IQR 방법)"""
        issues = []
        if len(sensor.data) < 10:
            return issues

        for i, col_name in enumerate(sensor.columns):
            col_data = sensor.data[:, i]
            Q1 = np.percentile(col_data, 25)
            Q3 = np.percentile(col_data, 75)
            IQR = Q3 - Q1

            if IQR == 0:
                continue

            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            outliers = np.where(
                (sensor.data[:, i] < lower_bound) | (sensor.data[:, i] > upper_bound)
            )[0]
            outlier_ratio = len(outliers) / len(col_data)

            if outlier_ratio > 0.05:  # 5% 이상이면 경고
                issues.append(
                    ValidationIssue(
                        severity="info",
                        sensor="",
                        check="outlier_detection",
                        message=f"Column '{col_name}': {len(outliers)} outliers ({outlier_ratio:.2%})",
                        details={
                            "column": col_name,
                            "outlier_count": int(len(outliers)),
                            "ratio": float(outlier_ratio),
                        },
                    )
                )
        return issues

    def _check_constant(self, sensor: "SensorData") -> List:
        """상수 값 확인 (변화 없는 센서)"""
        issues = []
        if len(sensor.data) < 2:
            return issues

        for i, col_name in enumerate(sensor.columns):
            col_data = sensor.data[:, i]
            if np.all(col_data == col_data[0]):
                issues.append(
                    ValidationIssue(
                        severity="info",
                        sensor="",
                        check="constant_values",
                        message=f"Column '{col_name}' is constant (value: {col_data[0]})",
                        details={"column": col_name, "value": float(col_data[0])},
                    )
                )
        return issues

    def _check_sensor_range(self, sensor: "SensorData") -> List:
        """센서별 예상 범위 확인"""
        issues = []
        # 센서별 예상 범위 (예시)
        expected_ranges = {
            "gps": {"lat": (-90, 90), "lon": (-180, 180), "alt": (-1000, 20000)},
            "imu": {"acc": (-50, 50), "gyro": (-20, 20)},  # m/s2, rad/s
            "baro": {"alt": (-1000, 20000), "press": (30000, 110000)},
            "battery": {"voltage": (0, 30), "current": (-100, 100)},
        }

        sensor_type = None
        for key in expected_ranges:
            if key in sensor.name.lower():
                sensor_type = key
                break

        if sensor_type and sensor_type in expected_ranges:
            ranges = expected_ranges[sensor_type]
            for i, col_name in enumerate(sensor.columns):
                for range_key, (min_val, max_val) in ranges.items():
                    if range_key in col_name.lower():
                        col_data = sensor.data[:, i]
                        out_of_range = np.sum(
                            (col_data < min_val) | (col_data > max_val)
                        )
                        if out_of_range > 0:
                            issues.append(
                                ValidationIssue(
                                    severity="warning",
                                    sensor="",
                                    check="sensor_range",
                                    message=f"Column '{col_name}': {out_of_range} values out of expected range [{min_val}, {max_val}]",
                                    details={
                                        "column": col_name,
                                        "out_of_range": int(out_of_range),
                                        "expected_range": [min_val, max_val],
                                    },
                                )
                            )
        return issues


class CrossSensorValidator:
    """센서 간 교차 검증"""

    def __init__(self):
        self.checks = []

    def validate_consistency(self, multi_sensor: "MultiSensorData") -> List:
        """센서 간 일관성 검증"""
        issues = []

        # GPS와 기압계 고도 비교
        if "gps" in multi_sensor.sensors and "baro" in multi_sensor.sensors:
            issues.extend(self._check_gps_baro_altitude(multi_sensor))

        # IMU와 GPS 속도 비교
        if "imu" in multi_sensor.sensors and "gps" in multi_sensor.sensors:
            issues.extend(self._check_imu_gps_velocity(multi_sensor))

        return issues

    def _check_gps_baro_altitude(self, multi_sensor: "MultiSensorData") -> List:
        """GPS 고도와 기압계 고도 비교"""
        issues = []
        gps_sensor = multi_sensor.sensors.get("gps")
        baro_sensor = multi_sensor.sensors.get("baro")

        if not gps_sensor or not baro_sensor:
            return issues

        # 공통 시간 범위에서 비교
        common_start, common_end = multi_sensor.get_common_time_range()
        if common_start >= common_end:
            return issues

        # 리샘플링 후 비교 (간단한 버전)
        # 실제로는 시간 동기화 후 비교 필요
        return issues

    def _check_imu_gps_velocity(self, multi_sensor: "MultiSensorData") -> List:
        """IMU 적분 속도와 GPS 속도 비교"""
        issues = []
        # 구현 생략
        return issues


def create_validator(config: Optional[dict] = None) -> "DataValidator":
    """검증기 생성 팩토리"""
    return DataValidator(config)


def create_cross_validator() -> "CrossSensorValidator":
    """교차 검증기 생성"""
    return CrossSensorValidator()
