"""
Flight Log Adapter for PX4 ulog files.

Parses ulog format and extracts structured data for analysis.
Maintains provenance (SHA-256, source path, transform metadata).
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from pyulog import ULog

    PYULOG_AVAILABLE = True
except ImportError:
    PYULOG_AVAILABLE = False
    ULog = object  # type: ignore


@dataclass
class Provenance:
    """Provenance metadata for traceability."""

    source_path: str
    source_sha256: str
    transform_code_version: str  # Git commit hash
    transform_timestamp: str  # ISO 8601
    transform_params: Dict[str, Any]
    parser_version: str = "flightlog_adapter/0.1.0"


@dataclass
class FlightLogMetadata:
    """Top-level flight metadata."""

    log_id: str
    start_timestamp: int  # microseconds since epoch
    duration_s: float
    firmware_version: str
    vehicle_type: str
    autopilot_hw: str
    provenance: Provenance


@dataclass
class EstimatorStatus:
    """EKF2 estimator status snapshot."""

    timestamp: int
    nan_flags: int
    health_flags: int
    timeout_flags: int
    gps_check_fail_flags: int
    innovation_fault_flags: int
    mag_fault_flags: int
    solution_status: int


@dataclass
class EKF2Innovations:
    """EKF2 innovation (residual) data."""

    timestamp: int
    # Position innovations (m)
    pos_innov: List[float]  # [N, E, D]
    pos_innov_var: List[float]
    # Velocity innovations (m/s)
    vel_innov: List[float]
    vel_innov_var: List[float]
    # Angle innovations (rad)
    ang_innov: List[float]
    ang_innov_var: List[float]
    # External vision innovations
    ev_pos_innov: Optional[List[float]] = None
    ev_vel_innov: Optional[List[float]] = None
    ev_yaw_innov: Optional[float] = None


@dataclass
class VehicleLocalPosition:
    """Vehicle local position (NED)."""

    timestamp: int
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    ax: float
    ay: float
    az: float
    yaw: float
    yaw_rate: float
    xy_valid: bool
    z_valid: bool
    v_xy_valid: bool
    v_z_valid: bool


@dataclass
class VehicleGlobalPosition:
    """Vehicle global position (WGS84)."""

    timestamp: int
    lat: float
    lon: float
    alt: float  # MSL
    alt_ellipsoid: float
    eph: float  # Horizontal accuracy (m)
    epv: float  # Vertical accuracy (m)
    terrain_alt: float
    terrain_alt_valid: bool


@dataclass
class DistanceSensor:
    """Distance sensor (LiDAR/Range finder)."""

    timestamp: int
    sensor_id: int
    type: int
    orientation: int
    current_distance: float
    covariance: float
    signal_quality: int
    min_distance: float
    max_distance: float
    update_rate: float


@dataclass
class OpticalFlow:
    """Optical flow measurement."""

    timestamp: int
    sensor_id: int
    integration_timespan: int
    pixel_flow_x: float
    pixel_flow_y: float
    flow_comp_m_x: float
    flow_comp_m_y: float
    quality: int
    gyro_x_rate: float
    gyro_y_rate: float
    gyro_z_rate: float
    gyro_range: float
    ground_distance: float
    ground_distance_valid: bool


class FlightLogAdapter:
    """Adapter for parsing PX4 ulog files with provenance tracking."""

    # Message types we care about
    TOPICS_OF_INTEREST = {
        "estimator_status": EstimatorStatus,
        "ekf2_innovations": EKF2Innovations,
        "vehicle_local_position": VehicleLocalPosition,
        "vehicle_global_position": VehicleGlobalPosition,
        "distance_sensor": DistanceSensor,
        "optical_flow": OpticalFlow,
        # Add more as needed
    }

    def __init__(self, transform_code_version: Optional[str] = None):
        self.transform_code_version = transform_code_version or self._get_git_hash()

    @staticmethod
    def _get_git_hash() -> str:
        """Get current git commit hash."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )
            return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _compute_sha256(filepath: Path) -> str:
        """Compute SHA-256 hash of file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def parse(self, ulog_path: str) -> Dict[str, Any]:
        """
        Parse ulog file and return structured data with provenance.

        Returns:
            Dict with keys: metadata, estimator_status, innovations,
                           local_position, global_position, distance_sensor, optical_flow, provenance
        """
        if not PYULOG_AVAILABLE:
            raise RuntimeError("pyulog not installed. Run: pip install pyulog")

        path = Path(ulog_path)
        if not path.exists():
            raise FileNotFoundError(f"ULog file not found: {ulog_path}")

        # Compute provenance
        source_sha256 = self._compute_sha256(path)
        provenance = Provenance(
            source_path=str(path.absolute()),
            source_sha256=source_sha256,
            transform_code_version=self.transform_code_version,
            transform_timestamp=datetime.utcnow().isoformat() + "Z",
            transform_params={"parser": "pyulog", "topics": list(self.TOPICS_OF_INTEREST.keys())},
        )

        # Parse ulog
        ulog = ULog(ulog_path)

        # Extract metadata
        metadata = self._extract_metadata(ulog, provenance)

        # Extract time-series data
        data = {
            "metadata": metadata,
            "provenance": asdict(provenance),
        }

        for topic_name in self.TOPICS_OF_INTEREST:
            data[topic_name] = self._extract_topic(ulog, topic_name)

        return data

    def _extract_metadata(self, ulog: ULog, provenance: Provenance) -> FlightLogMetadata:
        """Extract flight metadata from ulog."""
        # Get start timestamp from first message
        start_ts = min(
            (
                msg.data["timestamp"][0]
                for msg in ulog.data_list
                if "timestamp" in msg.data and len(msg.data["timestamp"]) > 0
            ),
            default=0,
        )

        # Get duration from last message
        end_ts = max(
            (
                msg.data["timestamp"][-1]
                for msg in ulog.data_list
                if "timestamp" in msg.data and len(msg.data["timestamp"]) > 0
            ),
            default=start_ts,
        )

        # Firmware version from initial parameters
        firmware_version = "unknown"
        for key, val in ulog.initial_parameters.items():
            if key in ("SYS_AUTOSTART", "SYS_TYPE"):
                firmware_version = f"PX4_{val}"
                break

        return FlightLogMetadata(
            log_id=path.stem,
            start_timestamp=start_ts,
            duration_s=(end_ts - start_ts) / 1e6,
            firmware_version=firmware_version,
            vehicle_type="quadrotor",  # Could parse from SYS_AUTOSTART
            autopilot_hw="Pixhawk6C",
            provenance=provenance,
        )

    def _extract_topic(self, ulog: ULog, topic_name: str) -> List[Dict]:
        """Extract all messages for a topic."""
        messages = []
        for dataset in ulog.data_list:
            if dataset.name == topic_name:
                # Convert structured array to list of dicts
                for i in range(len(dataset.data["timestamp"])):
                    msg_dict = {"timestamp": int(dataset.data["timestamp"][i])}
                    for field in dataset.data.dtype.names:
                        if field != "timestamp":
                            val = dataset.data[field][i]
                            # Handle arrays
                            if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
                                msg_dict[field] = [float(x) for x in val]
                            else:
                                msg_dict[field] = (
                                    float(val) if isinstance(val, (int, float)) else val
                                )
                    messages.append(msg_dict)
        return messages

    def to_json(self, data: Dict, output_path: str) -> None:
        """Save parsed data to JSON with provenance."""
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def get_summary(self, data: Dict) -> Dict:
        """Generate summary statistics for quick assessment."""
        summary = {
            "log_id": data["metadata"].log_id,
            "duration_s": data["metadata"].duration_s,
            "message_counts": {},
            "ekf2_health": {},
        }

        for topic in self.TOPICS_OF_INTEREST:
            msgs = data.get(topic, [])
            summary["message_counts"][topic] = len(msgs)

        # EKF2 health summary
        est_status = data.get("estimator_status", [])
        if est_status:
            last = est_status[-1]
            summary["ekf2_health"] = {
                "solution_status": last.get("solution_status", 0),
                "health_flags": last.get("health_flags", 0),
                "innovation_faults": last.get("innovation_fault_flags", 0),
            }

        return summary


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse PX4 ulog with provenance")
    parser.add_argument("ulog_path", help="Path to .ulg file")
    parser.add_argument("-o", "--output", help="Output JSON path")
    parser.add_argument("--summary", action="store_true", help="Print summary only")

    args = parser.parse_args()

    adapter = FlightLogAdapter()
    data = adapter.parse(args.ulog_path)

    if args.summary:
        summary = adapter.get_summary(data)
        print(json.dumps(summary, indent=2))
    elif args.output:
        adapter.to_json(data, args.output)
        print(f"Saved to {args.output}")
    else:
        print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
