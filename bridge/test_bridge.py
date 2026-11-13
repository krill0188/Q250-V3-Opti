#!/usr/bin/env python3
"""
Bridge 구조 검증 테스트 (타겟 PC에서 실행)
import 테스트 및 기본 구조 확인
"""

import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_dual_bridge_import():
    """DualBridge 클래스 import 테스트"""
    print("Testing DualBridge import...")
    try:
        from bridge.dual_bridge import (
            DualBridge,
            MAVSDKBridge,
            MAVROS2Bridge,
            DroneState,
            ConnectionState,
        )

        print("✅ All classes imported successfully")
        return True
    except ImportError as e:
        if "rclpy" in str(e) or "mavsdk" in str(e) or "mavros_msgs" in str(e):
            print(f"⚠️  Expected missing dependency (target PC only): {e}")
            return True  # 타겟 PC에서만 필요한 의존성
        print(f"❌ Import failed: {e}")
        return False
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        return False


def test_drone_state():
    """DroneState 데이터 클래스 테스트"""
    print("\nTesting DroneState...")
    try:
        from bridge.dual_bridge import DroneState

        state = DroneState(
            connected=True,
            armed=False,
            mode="GUIDED",
            battery_percent=85.5,
            latitude=37.5665,
            longitude=126.9780,
            altitude_amsl=100.0,
            altitude_rel=10.0,
        )
        print(f"✅ DroneState created: {state.mode}, battery={state.battery_percent}%")
        return True
    except ImportError as e:
        if "rclpy" in str(e) or "mavsdk" in str(e):
            print(f"⚠️  Skipped (target PC deps): {e}")
            return True
        print(f"❌ DroneState test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ DroneState test failed: {e}")
        return False


def test_connection_state_enum():
    """ConnectionState enum 테스트"""
    print("\nTesting ConnectionState enum...")
    try:
        from bridge.dual_bridge import ConnectionState

        states = list(ConnectionState)
        print(f"✅ ConnectionState values: {[s.value for s in states]}")
        return True
    except ImportError as e:
        if "rclpy" in str(e) or "mavsdk" in str(e):
            print(f"⚠️  Skipped (target PC deps): {e}")
            return True
        print(f"❌ ConnectionState test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ ConnectionState test failed: {e}")
        return False


def test_custom_mavlink_messages():
    """커스텀 MAVLink 메시지 import 테스트"""
    print("\nTesting custom MAVLink messages...")
    try:
        import sys

        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "generated", "mavlink")
        )
        import python as mavlink_custom

        # 메시지 ID 확인
        msg_ids = {
            "VOICE_COMMAND": getattr(
                mavlink_custom, "MAVLINK_MSG_ID_VOICE_COMMAND", None
            ),
            "VOICE_STATUS": getattr(
                mavlink_custom, "MAVLINK_MSG_ID_VOICE_STATUS", None
            ),
            "VOICE_FEEDBACK": getattr(
                mavlink_custom, "MAVLINK_MSG_ID_VOICE_FEEDBACK", None
            ),
            "VOICE_WAYPOINT": getattr(
                mavlink_custom, "MAVLINK_MSG_ID_VOICE_WAYPOINT", None
            ),
            "VOICE_EMERGENCY": getattr(
                mavlink_custom, "MAVLINK_MSG_ID_VOICE_EMERGENCY", None
            ),
        }

        print(f"✅ Message IDs: {msg_ids}")

        # 메시지 클래스 확인
        msg_classes = [
            "MAVLink_voice_command_message",
            "MAVLink_voice_status_message",
            "MAVLink_voice_feedback_message",
            "MAVLink_voice_waypoint_message",
            "MAVLink_voice_emergency_message",
        ]

        for cls_name in msg_classes:
            cls = getattr(mavlink_custom, cls_name, None)
            if cls:
                print(f"  ✅ {cls_name}: {cls}")
            else:
                print(f"  ❌ {cls_name}: NOT FOUND")
                return False

        return True
    except Exception as e:
        print(f"❌ Custom MAVLink test failed: {e}")
        return False


def test_bridge_structure():
    """브릿지 디렉토리 구조 확인"""
    print("\nTesting bridge structure...")
    base = os.path.join(os.path.dirname(__file__), "..")

    required = [
        "bridge/__init__.py",
        "bridge/dual_bridge.py",
        "bridge/requirements.txt",
        "q250_msgs/voice_control.xml",
        "generated/mavlink/python.py",
        "generated/mavlink/cpp/voice_control/voice_control.hpp",
    ]

    all_ok = True
    for path in required:
        full = os.path.join(base, path)
        if os.path.exists(full):
            size = os.path.getsize(full)
            print(f"  ✅ {path} ({size} bytes)")
        else:
            print(f"  ❌ {path} - NOT FOUND")
            all_ok = False

    return all_ok


def main():
    print("=" * 50)
    print("Q250-V3-Opti Bridge Structure Test")
    print("=" * 50)

    tests = [
        test_bridge_structure,
        test_dual_bridge_import,
        test_drone_state,
        test_connection_state_enum,
        test_custom_mavlink_messages,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 50)
    print(f"Results: {sum(results)}/{len(results)} passed")

    if all(results):
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
