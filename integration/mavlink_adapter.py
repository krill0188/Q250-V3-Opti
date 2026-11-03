"""
MAVLink Adapter for PCAP and text log files.

Parses MAVLink messages from PCAP captures or text logs.
Maintains provenance (SHA-256, source path, transform metadata).
"""

import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, List, Optional, Any, BinaryIO
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict

try:
    import dpkt

    DPKT_AVAILABLE = True
except ImportError:
    DPKT_AVAILABLE = False

try:
    from pymavlink import mavutil

    MAVUTIL_AVAILABLE = True
except ImportError:
    MAVUTIL_AVAILABLE = False


@dataclass
class Provenance:
    """Provenance metadata for traceability."""

    source_path: str
    source_sha256: str
    transform_code_version: str
    transform_timestamp: str
    transform_params: Dict[str, Any]
    parser_version: str = "mavlink_adapter/0.1.0"


@dataclass
class MAVLinkMessage:
    """Generic MAVLink message container."""

    timestamp: float  # Unix timestamp (seconds)
    msg_type: str  # Message name (e.g., 'GLOBAL_POSITION_INT')
    msg_id: int  # MAVLink message ID
    system_id: int
    component_id: int
    payload: Dict[str, Any]  # Decoded fields
    raw_bytes: Optional[bytes] = None
    provenance: Optional[Provenance] = None


class MAVLinkAdapter:
    """Adapter for parsing MAVLink from PCAP or text logs with provenance tracking."""

    # Key message types for flight analysis
    KEY_MESSAGE_TYPES = {
        "GLOBAL_POSITION_INT",
        "LOCAL_POSITION_NED",
        "ATTITUDE",
        "ATTITUDE_QUATERNION",
        "VELOCITY_NED",
        "GPS_RAW_INT",
        "GPS2_RAW",
        "VFR_HUD",
        "SYS_STATUS",
        "BATTERY_STATUS",
        "RC_CHANNELS",
        "RC_CHANNELS_RAW",
        "COMMAND_ACK",
        "MISSION_ITEM",
        "MISSION_REQUEST",
        "STATUSTEXT",
        "HEARTBEAT",
        "SYSTEM_TIME",
        "TIMESYNC",
        "OBSTACLE_DISTANCE",
        "DISTANCE_SENSOR",
        "OPTICAL_FLOW_RAD",
        "VISION_POSITION_ESTIMATE",
        "VISION_SPEED_ESTIMATE",
        "ODOMETRY",
        "ESC_STATUS",
        "ESC_TELEMETRY_1_TO_4",
        "ACTUATOR_OUTPUT_STATUS",
        "ACTUATOR_CONTROL_TARGET",
        "VEHICLE_STATUS",
        "VEHICLE_STATUS_FLAGS",
        "VEHICLE_COMMAND",
        "VEHICLE_COMMAND_ACK",
        "ESTIMATOR_STATUS",
        "EKF2_INNOVATIONS",
        "WIND",
        "WIND_COV",
    }

    def __init__(self, transform_code_version: Optional[str] = None):
        self.transform_code_version = transform_code_version or self._get_git_hash()

    @staticmethod
    def _get_git_hash() -> str:
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
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def parse_pcap(
        self,
        pcap_path: str,
        filter_types: Optional[List[str]] = None,
        max_messages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Parse MAVLink messages from PCAP file.

        Args:
            pcap_path: Path to .pcap or .pcapng file
            filter_types: List of message types to keep (None = all)
            max_messages: Maximum messages to parse (None = all)

        Returns:
            Dict with provenance and messages grouped by type
        """
        if not DPKT_AVAILABLE:
            raise RuntimeError("dpkt not installed. Run: pip install dpkt")

        path = Path(pcap_path)
        if not path.exists():
            raise FileNotFoundError(f"PCAP file not found: {pcap_path}")

        source_sha256 = self._compute_sha256(path)
        provenance = Provenance(
            source_path=str(path.absolute()),
            source_sha256=source_sha256,
            transform_code_version=self.transform_code_version,
            transform_timestamp=datetime.utcnow().isoformat() + "Z",
            transform_params={
                "parser": "dpkt",
                "filter_types": filter_types,
                "max_messages": max_messages,
            },
        )

        messages_by_type = defaultdict(list)
        total_parsed = 0

        with open(path, "rb") as f:
            pcap = dpkt.pcap.Reader(f)
            for ts, buf in pcap:
                if max_messages and total_parsed >= max_messages:
                    break

                # Parse UDP payload for MAVLink
                try:
                    eth = dpkt.ethernet.Ethernet(buf)
                    if eth.type != dpkt.ethernet.ETH_TYPE_IP:
                        continue
                    ip = eth.data
                    if ip.p != dpkt.ip.IP_PROTO_UDP:
                        continue
                    udp = ip.data
                    payload = bytes(udp.data)

                    # Try to parse as MAVLink v2
                    msgs = self._parse_mavlink_bytes(payload, ts, provenance)
                    for msg in msgs:
                        if filter_types is None or msg.msg_type in filter_types:
                            messages_by_type[msg.msg_type].append(msg)
                            total_parsed += 1
                except Exception:
                    continue

        return {
            "provenance": asdict(provenance),
            "message_counts": {k: len(v) for k, v in messages_by_type.items()},
            "total_messages": total_parsed,
            "messages": {k: [asdict(m) for m in v] for k, v in messages_by_type.items()},
        }

    def parse_text_log(
        self,
        log_path: str,
        filter_types: Optional[List[str]] = None,
        max_messages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Parse MAVLink from text log (QGroundControl format or mavlink-router text).
        """
        if not MAVUTIL_AVAILABLE:
            raise RuntimeError("pymavlink not installed. Run: pip install pymavlink")

        path = Path(log_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")

        source_sha256 = self._compute_sha256(path)
        provenance = Provenance(
            source_path=str(path.absolute()),
            source_sha256=source_sha256,
            transform_code_version=self.transform_code_version,
            transform_timestamp=datetime.utcnow().isoformat() + "Z",
            transform_params={
                "parser": "pymavlink.mavutil",
                "filter_types": filter_types,
                "max_messages": max_messages,
            },
        )

        messages_by_type = defaultdict(list)
        total_parsed = 0

        mlog = mavutil.mavlink_connection(str(path), robust_parsing=True)

        while True:
            if max_messages and total_parsed >= max_messages:
                break

            msg = mlog.recv_match(blocking=False)
            if msg is None:
                break

            msg_type = msg.get_type()
            if filter_types is None or msg_type in filter_types:
                mavlink_msg = MAVLinkMessage(
                    timestamp=msg._timestamp if hasattr(msg, "_timestamp") else 0,
                    msg_type=msg_type,
                    msg_id=msg.get_msgId(),
                    system_id=msg.get_srcSystem(),
                    component_id=msg.get_srcComponent(),
                    payload=msg.to_dict(),
                    provenance=provenance,
                )
                messages_by_type[msg_type].append(mavlink_msg)
                total_parsed += 1

        return {
            "provenance": asdict(provenance),
            "message_counts": {k: len(v) for k, v in messages_by_type.items()},
            "total_messages": total_parsed,
            "messages": {k: [asdict(m) for m in v] for k, v in messages_by_type.items()},
        }

    def _parse_mavlink_bytes(
        self, data: bytes, timestamp: float, provenance: Provenance
    ) -> List[MAVLinkMessage]:
        """Parse raw bytes for MAVLink v2 frames."""
        messages = []

        if not MAVUTIL_AVAILABLE:
            return messages

        # MAVLink v2 frame: STX(0xFD) + len + seq + sysid + compid + msgid(3bytes) + payload + CRC(2bytes)
        i = 0
        while i < len(data):
            if data[i] == 0xFD:  # MAVLink v2 STX
                if i + 10 > len(data):
                    break
                plen = data[i + 1]
                if i + 12 + plen > len(data):
                    break

                frame = data[i : i + 12 + plen]
                try:
                    msg = mavutil.mavlink.MAVLink(None).parse_char(frame)
                    if msg:
                        messages.append(
                            MAVLinkMessage(
                                timestamp=timestamp,
                                msg_type=msg.get_type(),
                                msg_id=msg.get_msgId(),
                                system_id=msg.get_srcSystem(),
                                component_id=msg.get_srcComponent(),
                                payload=msg.to_dict(),
                                raw_bytes=frame,
                                provenance=provenance,
                            )
                        )
                except Exception:
                    pass
                i += 12 + plen
            else:
                i += 1

        return messages

    def to_json(self, data: Dict, output_path: str) -> None:
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def extract_time_series(self, data: Dict, msg_type: str, fields: List[str]) -> Dict[str, List]:
        """Extract specific fields as time series for plotting/analysis."""
        messages = data.get("messages", {}).get(msg_type, [])
        result = {field: [] for field in fields}
        result["timestamp"] = []

        for msg in messages:
            result["timestamp"].append(msg.get("timestamp", 0))
            payload = msg.get("payload", {})
            for field in fields:
                result[field].append(payload.get(field, None))

        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Parse MAVLink from PCAP or text log")
    parser.add_argument("input_path", help="Path to .pcap, .pcapng, or text log file")
    parser.add_argument("-o", "--output", help="Output JSON path")
    parser.add_argument("--types", nargs="+", help="Filter message types")
    parser.add_argument("--max", type=int, help="Max messages to parse")
    parser.add_argument("--summary", action="store_true", help="Print summary only")

    args = parser.parse_args()

    adapter = MAVLinkAdapter()

    if args.input_path.endswith((".pcap", ".pcapng")):
        data = adapter.parse_pcap(args.input_path, args.types, args.max)
    else:
        data = adapter.parse_text_log(args.input_path, args.types, args.max)

    if args.summary:
        print(
            json.dumps(
                {
                    "total_messages": data["total_messages"],
                    "message_counts": data["message_counts"],
                },
                indent=2,
            )
        )
    elif args.output:
        adapter.to_json(data, args.output)
        print(f"Saved to {args.output}")
    else:
        print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
