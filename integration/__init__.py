"""
Flight Intelligence Integration Package

Provides adapters for parsing and aligning multi-modal flight data:
- PX4 ulog (flightlog_adapter)
- MAVLink PCAP/text (mavlink_adapter)
- Multi-source time alignment (align)
- Shared utilities and SQL schema (common)

All adapters maintain full provenance (SHA-256, version, timestamps) for traceability.
"""

from .align import (
    AlignedDataset,
    ProvenanceRecord,
    TimeAligner,
    TimeSyncPoint,
    TimeTransform,
    find_common_time_range,
    resample_to_common_grid,
)
from .common import (
    FLIGHTLOG_SQL_SCHEMA,
    MAVLINK_KEY_MESSAGES,
    PX4_KEY_MESSAGES,
    CoordinateFrame,
    FlightMetadata,
    Provenance,
    SensorSpec,
    SourceType,
    compute_sha256,
    ecef_to_lla,
    enu_to_ned,
    euler_to_quat,
    get_git_hash,
    lla_to_ecef,
    ned_to_enu,
    quat_to_euler,
    utc_now_iso,
)
from .flightlog_adapter import (
    DistanceSensor,
    EKF2Innovations,
    EstimatorStatus,
    FlightLogAdapter,
    FlightLogMetadata,
    OpticalFlow,
)
from .flightlog_adapter import Provenance as FLProvenance
from .flightlog_adapter import VehicleGlobalPosition, VehicleLocalPosition
from .mavlink_adapter import MAVLinkAdapter, MAVLinkMessage
from .mavlink_adapter import Provenance as MLProvenance

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
