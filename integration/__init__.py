"""
Flight Intelligence Integration Package

Provides adapters for parsing and aligning multi-modal flight data:
- PX4 ulog (flightlog_adapter)
- MAVLink PCAP/text (mavlink_adapter)
- Multi-source time alignment (align)
- Shared utilities and SQL schema (common)

All adapters maintain full provenance (SHA-256, version, timestamps) for traceability.
"""

from .common import (
    SourceType,
    CoordinateFrame,
    Provenance,
    FlightMetadata,
    SensorSpec,
    PX4_KEY_MESSAGES,
    MAVLINK_KEY_MESSAGES,
    FLIGHTLOG_SQL_SCHEMA,
    compute_sha256,
    get_git_hash,
    utc_now_iso,
    ned_to_enu,
    enu_to_ned,
    lla_to_ecef,
    ecef_to_lla,
    quat_to_euler,
    euler_to_quat,
)

from .flightlog_adapter import (
    FlightLogAdapter,
    Provenance as FLProvenance,
    FlightLogMetadata,
    EstimatorStatus,
    EKF2Innovations,
    VehicleLocalPosition,
    VehicleGlobalPosition,
    DistanceSensor,
    OpticalFlow,
)

from .mavlink_adapter import (
    MAVLinkAdapter,
    Provenance as MLProvenance,
    MAVLinkMessage,
)

from .align import (
    TimeAligner,
    TimeSyncPoint,
    TimeTransform,
    AlignedDataset,
    ProvenanceRecord,
    find_common_time_range,
    resample_to_common_grid,
)

__all__ = [
    # Common types
    "SourceType",
    "CoordinateFrame",
    "Provenance",
    "FlightMetadata",
    "SensorSpec",
    "PX4_KEY_MESSAGES",
    "MAVLINK_KEY_MESSAGES",
    "FLIGHTLOG_SQL_SCHEMA",
    "compute_sha256",
    "get_git_hash",
    "utc_now_iso",
    "ned_to_enu",
    "enu_to_ned",
    "lla_to_ecef",
    "ecef_to_lla",
    "quat_to_euler",
    "euler_to_quat",
    # Flight log adapter
    "FlightLogAdapter",
    "FLProvenance",
    "FlightLogMetadata",
    "EstimatorStatus",
    "EKF2Innovations",
    "VehicleLocalPosition",
    "VehicleGlobalPosition",
    "DistanceSensor",
    "OpticalFlow",
    # MAVLink adapter
    "MAVLinkAdapter",
    "MLProvenance",
    "MAVLinkMessage",
    # Time alignment
    "TimeAligner",
    "TimeSyncPoint",
    "TimeTransform",
    "AlignedDataset",
    "ProvenanceRecord",
    "find_common_time_range",
    "resample_to_common_grid",
]

__version__ = "0.1.0"
