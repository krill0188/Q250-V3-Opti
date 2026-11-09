#!/usr/bin/env python3
"""
Test Flight Log Integration

Demonstrates parsing ulog/MAVLink and storing in the flightlog database
with full provenance tracking.
"""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import sys

# Add integration to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration import (
    FlightLogAdapter,
    MAVLinkAdapter,
    TimeAligner,
    compute_sha256,
    get_git_hash,
    utc_now_iso,
    FLIGHTLOG_SQL_SCHEMA,
)

DB_PATH = "/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db/flightlog.db"


def insert_flight_record(conn, flight_data: dict) -> str:
    """Insert flight metadata and return flight_id."""
    cursor = conn.cursor()

    flight_id = flight_data.get(
        "flight_id", f"flight_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    cursor.execute(
        """
        INSERT OR REPLACE INTO flights (
            flight_id, source_type, source_path, source_sha256, source_size_bytes,
            start_time_utc, end_time_utc, duration_s,
            vehicle_id, firmware_version, autopilot_hardware,
            location, purpose, weather, pilot, notes,
            transform_code_version, transform_timestamp, transform_params, parser_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            flight_id,
            flight_data["source_type"],
            flight_data["source_path"],
            flight_data["source_sha256"],
            flight_data.get("source_size_bytes", 0),
            flight_data.get("start_time_utc", utc_now_iso()),
            flight_data.get("end_time_utc", utc_now_iso()),
            flight_data.get("duration_s", 0.0),
            flight_data.get("vehicle_id", "Q250-V3-Opti"),
            flight_data.get("firmware_version", "PX4 v1.15"),
            flight_data.get("autopilot_hardware", "Pixhawk6C"),
            flight_data.get("location", "Indoor Test"),
            flight_data.get("purpose", "VIO Integration Test"),
            flight_data.get("weather", "N/A"),
            flight_data.get("pilot", "Test Pilot"),
            flight_data.get("notes", ""),
            flight_data.get("transform_code_version", get_git_hash()),
            flight_data.get("transform_timestamp", utc_now_iso()),
            flight_data.get("transform_params", "{}"),
            flight_data.get("parser_version", "integration/0.1.0"),
        ),
    )
    conn.commit()
    return flight_id


def store_ekf2_innovations(
    conn, flight_id: str, innovations: list, provenance: str
) -> int:
    """Store EKF2 innovations data."""
    cursor = conn.cursor()
    count = 0

    for innov in innovations:
        cursor.execute(
            """
            INSERT INTO ekf2_innovations (
                flight_id, timestamp, timestamp_original, timebase,
                pos_innov_n, pos_innov_e, pos_innov_d,
                pos_innov_var_n, pos_innov_var_e, pos_innov_var_d,
                vel_innov_n, vel_innov_e, vel_innov_d,
                vel_innov_var_n, vel_innov_var_e, vel_innov_var_d,
                ang_innov_x, ang_innov_y, ang_innov_z,
                ang_innov_var_x, ang_innov_var_y, ang_innov_var_z,
                ev_pos_innov_n, ev_pos_innov_e, ev_pos_innov_d,
                ev_vel_innov_n, ev_vel_innov_e, ev_vel_innov_d,
                ev_yaw_innov,
                provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                flight_id,
                innov.get("timestamp", 0),
                innov.get("timestamp_original"),
                innov.get("timebase", "ulog"),
                innov.get("pos_innov", [None] * 3)[0],
                innov.get("pos_innov", [None] * 3)[1],
                innov.get("pos_innov", [None] * 3)[2],
                innov.get("pos_innov_var", [None] * 3)[0],
                innov.get("pos_innov_var", [None] * 3)[1],
                innov.get("pos_innov_var", [None] * 3)[2],
                innov.get("vel_innov", [None] * 3)[0],
                innov.get("vel_innov", [None] * 3)[1],
                innov.get("vel_innov", [None] * 3)[2],
                innov.get("vel_innov_var", [None] * 3)[0],
                innov.get("vel_innov_var", [None] * 3)[1],
                innov.get("vel_innov_var", [None] * 3)[2],
                innov.get("ang_innov", [None] * 3)[0],
                innov.get("ang_innov", [None] * 3)[1],
                innov.get("ang_innov", [None] * 3)[2],
                innov.get("ang_innov_var", [None] * 3)[0],
                innov.get("ang_innov_var", [None] * 3)[1],
                innov.get("ang_innov_var", [None] * 3)[2],
                (
                    innov.get("ev_pos_innov", [None] * 3)[0]
                    if innov.get("ev_pos_innov")
                    else None
                ),
                (
                    innov.get("ev_pos_innov", [None] * 3)[1]
                    if innov.get("ev_pos_innov")
                    else None
                ),
                (
                    innov.get("ev_pos_innov", [None] * 3)[2]
                    if innov.get("ev_pos_innov")
                    else None
                ),
                (
                    innov.get("ev_vel_innov", [None] * 3)[0]
                    if innov.get("ev_vel_innov")
                    else None
                ),
                (
                    innov.get("ev_vel_innov", [None] * 3)[1]
                    if innov.get("ev_vel_innov")
                    else None
                ),
                (
                    innov.get("ev_vel_innov", [None] * 3)[2]
                    if innov.get("ev_vel_innov")
                    else None
                ),
                innov.get("ev_yaw_innov"),
                provenance,
            ),
        )
        count += 1

    conn.commit()
    return count


def store_vehicle_local_position(
    conn, flight_id: str, positions: list, provenance: str
) -> int:
    """Store vehicle local position data."""
    cursor = conn.cursor()
    count = 0

    for pos in positions:
        cursor.execute(
            """
            INSERT INTO vehicle_local_position (
                flight_id, timestamp, timestamp_original, timebase,
                x, y, z, vx, vy, vz, ax, ay, az, yaw, yaw_rate,
                xy_valid, z_valid, v_xy_valid, v_z_valid,
                provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                flight_id,
                pos.get("timestamp", 0),
                pos.get("timestamp_original"),
                pos.get("timebase", "ulog"),
                pos.get("x"),
                pos.get("y"),
                pos.get("z"),
                pos.get("vx"),
                pos.get("vy"),
                pos.get("vz"),
                pos.get("ax"),
                pos.get("ay"),
                pos.get("az"),
                pos.get("yaw"),
                pos.get("yaw_rate"),
                pos.get("xy_valid"),
                pos.get("z_valid"),
                pos.get("v_xy_valid"),
                pos.get("v_z_valid"),
                provenance,
            ),
        )
        count += 1

    conn.commit()
    return count


def demo_with_sample_data():
    """Demonstrate with sample data since we don't have real ulog files yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("=" * 60)
    print("Flight Log Integration Demo")
    print("=" * 60)

    # Simulate a flight record
    flight_data = {
        "flight_id": "test_flight_20261103_001",
        "source_type": "ulog",
        "source_path": "/path/to/test_flight.ulg",
        "source_sha256": "a" * 64,  # dummy hash
        "source_size_bytes": 1024000,
        "start_time_utc": "2026-11-03T10:00:00Z",
        "end_time_utc": "2026-11-03T10:15:00Z",
        "duration_s": 900.0,
        "vehicle_id": "Q250-V3-Opti-01",
        "firmware_version": "PX4 v1.15",
        "autopilot_hardware": "Pixhawk6C",
        "location": "Indoor Lab",
        "purpose": "VIO-EKF2 Integration Test",
        "weather": "N/A (indoor)",
        "pilot": "Test Pilot",
        "notes": "First VIO integration test with fake GPS",
        "transform_code_version": get_git_hash(),
        "transform_timestamp": utc_now_iso(),
        "transform_params": '{"parser": "pyulog", "topics": ["ekf2_innovations", "vehicle_local_position"]}',
        "parser_version": "flightlog_adapter/0.1.0",
    }

    # Insert flight
    flight_id = insert_flight_record(conn, flight_data)
    print(f"\n✓ Inserted flight: {flight_id}")

    # Sample EKF2 innovations (simulated)
    sample_innovations = [
        {
            "timestamp": 1000000 + i * 10000,  # 10ms intervals
            "timestamp_original": 1000000 + i * 10000,
            "timebase": "ulog",
            "pos_innov": [0.01, -0.02, 0.005],
            "pos_innov_var": [0.01, 0.01, 0.02],
            "vel_innov": [0.005, -0.01, 0.001],
            "vel_innov_var": [0.005, 0.005, 0.01],
            "ang_innov": [0.001, -0.002, 0.003],
            "ang_innov_var": [0.001, 0.001, 0.002],
        }
        for i in range(100)  # 1 second of data at 100Hz
    ]

    prov = "sha256:" + "a" * 64 + "|flightlog_adapter/0.1.0|" + utc_now_iso()
    count = store_ekf2_innovations(conn, flight_id, sample_innovations, prov)
    print(f"✓ Stored {count} EKF2 innovation records")

    # Sample vehicle local position
    sample_positions = [
        {
            "timestamp": 1000000 + i * 10000,
            "timestamp_original": 1000000 + i * 10000,
            "timebase": "ulog",
            "x": i * 0.01,  # Moving forward 0.01m per step
            "y": 0.0,
            "z": -1.0,
            "vx": 0.1,
            "vy": 0.0,
            "vz": 0.0,
            "ax": 0.0,
            "ay": 0.0,
            "az": 0.0,
            "yaw": 0.0,
            "yaw_rate": 0.0,
            "xy_valid": True,
            "z_valid": True,
            "v_xy_valid": True,
            "v_z_valid": True,
        }
        for i in range(100)
    ]

    count = store_vehicle_local_position(conn, flight_id, sample_positions, prov)
    print(f"✓ Stored {count} vehicle local position records")

    # Verify
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM ekf2_innovations WHERE flight_id = ?", (flight_id,)
    )
    print(f"\nEKF2 innovations in DB: {cursor.fetchone()[0]}")

    cursor.execute(
        "SELECT COUNT(*) FROM vehicle_local_position WHERE flight_id = ?", (flight_id,)
    )
    print(f"Vehicle local positions in DB: {cursor.fetchone()[0]}")

    cursor.execute("SELECT * FROM flights WHERE flight_id = ?", (flight_id,))
    flight = cursor.fetchone()
    print(f"\nFlight record: {flight[0]} - {flight[10]} - {flight[11]}")

    conn.close()
    print("\n✅ Demo complete! Database ready for real flight data.")


def main():
    print("Flight Log Integration Test")
    print(f"Database: {DB_PATH}")

    if not Path(DB_PATH).exists():
        print("Database not found. Run init_flightlog_db.py first.")
        return

    demo_with_sample_data()


if __name__ == "__main__":
    main()
