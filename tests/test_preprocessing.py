#!/usr/bin/env python3
"""
전처리 파이프라인 테스트 스크립트
"""

import sys
from pathlib import Path
import tempfile
import shutil

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from src.preprocessing import (
    DATASET_CONFIGS,
    create_pipeline,
    SensorData,
    MultiSensorData,
    TimeSynchronizer,
    SensorNormalizer,
    DataSplitter,
    DataValidator,
    create_synchronizer,
    create_normalizer,
    create_splitter,
    create_validator,
)


def create_test_data():
    """테스트용 더미 데이터 생성"""
    # GPS 데이터
    n = 1000
    timestamps = np.linspace(0, 10, n)
    gps_data = np.column_stack(
        [
            37.123456 + np.cumsum(np.random.randn(n) * 1e-6),  # lat
            127.123456 + np.cumsum(np.random.randn(n) * 1e-6),  # lon
            100 + np.cumsum(np.random.randn(n) * 0.1),  # alt
            np.random.randn(n) * 0.5,  # vn
            np.random.randn(n) * 0.5,  # ve
            np.random.randn(n) * 0.1,  # vd
        ]
    )

    # IMU 데이터
    imu_data = np.column_stack(
        [
            np.random.randn(n) * 0.5,  # acc_x
            np.random.randn(n) * 0.5,  # acc_y
            -9.81 + np.random.randn(n) * 0.2,  # acc_z (중력 포함)
            np.random.randn(n) * 0.01,  # gyro_x
            np.random.randn(n) * 0.01,  # gyro_y
            np.random.randn(n) * 0.01,  # gyro_z
        ]
    )

    return {
        "gps": SensorData(
            name="gps",
            timestamp=np.linspace(0, 10, n),
            data=gps_data,
            columns=["lat", "lon", "alt", "vn", "ve", "vd"],
            frequency_hz=100.0,
            coordinate_frame="NED",
        ),
        "imu": SensorData(
            name="imu",
            timestamp=np.linspace(0, 10, n),
            data=imu_data,
            columns=["acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"],
            frequency_hz=100.0,
            coordinate_frame="BODY",
        ),
    }


def test_sensor_data():
    """SensorData 클래스 테스트"""
    print("Testing SensorData...")
    data = create_test_data()
    gps = data["gps"]
    imu = data["imu"]

    assert len(gps) == 1000
    assert len(imu) == 1000
    assert gps.frequency_hz == 100.0
    assert imu.coordinate_frame == "BODY"

    # 리샘플링 테스트
    imu_resampled = imu.resample(50.0)
    assert imu_resampled.frequency_hz == 50.0
    assert len(imu_resampled) == 500  # 10초 * 50Hz

    # 크롭 테스트
    gps_cropped = gps.crop(2.0, 8.0)
    assert abs(gps_cropped.get_duration_sec() - 6.0) < 0.1

    print("  SensorData tests passed!")


def test_multi_sensor_data():
    """MultiSensorData 테스트"""
    print("Testing MultiSensorData...")
    data = create_test_data()
    multi = MultiSensorData(
        sensors=data,
        reference_sensor="gps",
    )

    assert len(multi.sensors) == 2
    assert multi.reference_sensor == "gps"
    assert multi.get_duration_sec() == 10.0

    start, end = multi.get_common_time_range()
    assert abs(start - 0.0) < 0.01
    assert abs(end - 10.0) < 0.01

    print("  MultiSensorData tests passed!")


def test_synchronizer():
    """TimeSynchronizer 테스트"""
    print("Testing TimeSynchronizer...")
    from src.preprocessing import TimeSynchronizer, create_synchronizer

    data = create_test_data()
    multi = MultiSensorData(sensors=data, reference_sensor="gps")

    sync = create_synchronizer(target_freq_hz=50.0)
    result = sync.synchronize(multi)

    assert len(result.synchronized_data) == 2
    assert "gps" in result.synchronized_data
    assert "imu" in result.synchronized_data

    # 주파수 확인
    assert abs(result.synchronized_data["gps"].frequency_hz - 50.0) < 0.1
    assert abs(result.synchronized_data["imu"].frequency_hz - 50.0) < 0.1

    print("  TimeSynchronizer tests passed!")


def test_normalizer():
    """SensorNormalizer 테스트"""
    print("Testing SensorNormalizer...")
    from src.preprocessing import create_normalizer

    data = create_test_data()

    normalizer = SensorNormalizer(method="standard", per_sensor=True)
    normalizer.fit(
        {k: v.data for k, v in data.items()}, {k: v.columns for k, v in data.items()}
    )

    # 변환 테스트
    normalized = normalizer.transform({k: v.data for k, v in data.items()})

    # 평균 0, 표준편차 1 근처인지 확인
    for name, data_arr in normalized.items():
        mean = np.mean(data_arr, axis=0)
        std = np.std(data_arr, axis=0)
        assert np.allclose(mean, 0, atol=0.1), f"Mean not zero for {name}"
        assert np.allclose(std, 1, atol=0.1), f"Std not one for {name}"

    # 역변환 테스트
    denormalized = normalizer.inverse_transform(normalized)
    for name in data:
        np.testing.assert_allclose(data[name].data, denormalized[name], rtol=1e-5)

    print("  SensorNormalizer tests passed!")


def test_splitter():
    """DataSplitter 테스트"""
    print("Testing DataSplitter...")
    from src.preprocessing import create_splitter, MultiSensorData
    from src.preprocessing.config import DataSplit

    data = create_test_data()
    multi = MultiSensorData(sensors=data, reference_sensor="gps")

    splitter = create_splitter("temporal")
    from types import SimpleNamespace

    config = SimpleNamespace(
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15,
        shuffle=False,
    )
    splits = splitter.split(multi, config=config)

    assert DataSplit.TRAIN in splits
    assert DataSplit.VAL in splits
    assert DataSplit.TEST in splits

    # 시간 순서 확인 (각 분할의 시작 시간은 0으로 리셋됨)
    # 대신 전체 시간 범위가 올바르게 분할되었는지 확인
    train_data = splits[DataSplit.TRAIN].sensors["gps"]
    val_data = splits[DataSplit.VAL].sensors["gps"]
    test_data = splits[DataSplit.TEST].sensors["gps"]

    assert len(train_data) > 0
    assert len(val_data) > 0
    assert len(test_data) > 0

    # 전체 샘플 수 확인
    total_samples = len(train_data) + len(val_data) + len(test_data)
    assert total_samples <= 1000  # 원본 데이터 수

    print("  DataSplitter tests passed!")


def test_validator():
    """DataValidator 테스트"""
    print("Testing DataValidator...")
    from src.preprocessing import create_validator, SensorData

    # 정상 데이터
    good_data = SensorData(
        name="test",
        timestamp=np.linspace(0, 10, 100),
        data=np.random.randn(100, 3),
        columns=["x", "y", "z"],
        frequency_hz=10.0,
        coordinate_frame="NED",
    )

    validator = DataValidator()
    report = validator.validate_sensor(good_data, "test")

    assert not report.has_errors
    print("  Normal data validation passed!")

    # NaN 데이터
    bad_data = SensorData(
        name="bad",
        timestamp=np.linspace(0, 10, 100),
        data=np.array([[1, np.nan, 3]] * 100),
        columns=["x", "y", "z"],
        frequency_hz=10.0,
        coordinate_frame="NED",
    )

    report = validator.validate_sensor(bad_data, "bad")
    assert report.has_errors
    assert any(i.check == "no_nan_values" for i in report.issues)

    # Inf 데이터
    inf_data = SensorData(
        name="inf",
        timestamp=np.linspace(0, 10, 100),
        data=np.array([[1, np.inf, 3]] * 100),
        columns=["x", "y", "z"],
        frequency_hz=10.0,
        coordinate_frame="NED",
    )

    report = validator.validate_sensor(inf_data, "inf")
    assert report.has_errors

    print("  DataValidator tests passed!")


def test_pipeline_config():
    """파이프라인 설정 테스트"""
    print("Testing pipeline configs...")
    from src.preprocessing.config import DATASET_CONFIGS

    # 모든 데이터셋 설정 확인
    expected = [
        "idf_ds",
        "fixed_wing_attitude",
        "ign_fixed_wing",
        "uzh_fpv",
        "fpv_analog",
    ]
    for name in expected:
        assert name in DATASET_CONFIGS
        config = DATASET_CONFIGS[name]
        assert config.name == name
        assert config.raw_data_path is not None
        assert config.processed_path is not None

    print("  Pipeline configs passed!")


def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 60)
    print("Running Preprocessing Pipeline Tests")
    print("=" * 60)

    test_sensor_data()
    test_multi_sensor_data()
    test_synchronizer()
    test_normalizer()
    test_splitter()
    test_validator()
    test_pipeline_config()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
