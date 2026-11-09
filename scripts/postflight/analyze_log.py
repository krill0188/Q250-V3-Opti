#!/usr/bin/env python3
# analyze_log.py - 비행 로그 분석
# 사용: python3 analyze_log.py <flight_log.ulg>

import sys

import numpy as np
import pandas as pd


def analyze_flight_log(ulg_file):
    try:
        import pyulog
    except ImportError:
        print("Installing pyulog...")
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyulog"])
        import pyulog

    print(f"Analyzing: {ulg_file}")
    ulog = pyulog.ULog(ulg_file)

    # CSV로 변환 (메모리에서)
    data = {}
    for d in ulog.data_list:
        if d.name in [
            "vehicle_local_position",
            "estimator_status",
            "actuator_outputs",
            "battery_status",
            "vehicle_status",
        ]:
            data[d.name] = pd.DataFrame(d.data)

    # 1. 위치 정확도
    if "vehicle_local_position" in data:
        pos = data["vehicle_local_position"]
        print("\n=== Position Stability ===")
        print(f"X Std: {pos['x'].std():.4f} m")
        print(f"Y Std: {pos['y'].std():.4f} m")
        print(f"Z Std: {pos['z'].std():.4f} m")

    # 2. EKF2 혁신 분석
    if "estimator_status" in data:
        est = data["estimator_status"]
        of_cols = [c for c in est.columns if "flow" in c.lower()]
        rng_cols = [c for c in est.columns if "hagl" in c.lower() or "rng" in c.lower()]

        if of_cols:
            of_innov = est[of_cols].values
            print(
                f"\n=== Optical Flow Innovation RMS: {np.sqrt(np.mean(of_innov**2)):.4f} ==="
            )
        if rng_cols:
            rng_innov = est[rng_cols].values
            print(
                f"=== Range Finder Innovation RMS: {np.sqrt(np.mean(rng_innov**2)):.4f} ==="
            )

    # 3. 모터 출력 균형
    if "actuator_outputs" in data:
        act = data["actuator_outputs"]
        motor_cols = [
            c for c in act.columns if c.startswith("output[") and c.endswith("]")
        ]
        if len(motor_cols) >= 4:
            motors = act[motor_cols[:4]].values
            hover_motors = motors[motors.mean(axis=1) > 0.2]
            print(f"\n=== Motor Balance (hover avg) ===")
            for i in range(4):
                print(f"Motor {i+1}: {hover_motors[:,i].mean():.3f}")
            print(f"Max Deviation: {np.max(np.std(hover_motors, axis=1)):.3f}")

    # 4. 배터리 소비
    if "battery_status" in data:
        bat = data["battery_status"]
        if "voltage" in bat.columns and "current" in bat.columns:
            print(f"\n=== Battery ===")
            print(f"Start Voltage: {bat['voltage'].iloc[0]:.2f} V")
            print(f"End Voltage: {bat['voltage'].iloc[-1]:.2f} V")
            print(f"Avg Current: {bat['current'].mean():.2f} A")
            dt = (bat["timestamp"].iloc[-1] - bat["timestamp"].iloc[0]) / 1e6 / 3600
            print(f"Capacity Used: {(bat['current'].mean() * dt):.3f} Ah")

    # 5. 합격/불합격 판정
    print("\n=== Pass/Fail Criteria ===")
    passed = 0
    total = 0

    if "vehicle_local_position" in data:
        total += 1
        if max(pos["x"].std(), pos["y"].std()) < 0.05:
            print("✓ XY Position Std < 0.05m: PASS")
            passed += 1
        else:
            print("✗ XY Position Std < 0.05m: FAIL")

        total += 1
        if pos["z"].std() < 0.03:
            print("✓ Z Position Std < 0.03m: PASS")
            passed += 1
        else:
            print("✗ Z Position Std < 0.03m: FAIL")

    if "actuator_outputs" in data and len(motor_cols) >= 4:
        total += 1
        if np.max(np.std(hover_motors, axis=1)) < 0.05:
            print("✓ Motor Balance < 5%: PASS")
            passed += 1
        else:
            print("✗ Motor Balance < 5%: FAIL")

    print(f"\nOverall: {passed}/{total} checks passed")
    return passed == total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_log.py <flight_log.ulg>")
        sys.exit(1)

    success = analyze_flight_log(sys.argv[1])
    sys.exit(0 if success else 1)
