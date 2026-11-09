"""
Common utilities and shared data structures for flight intelligence integration.

Provides base classes, SQL schema, and shared constants used by all adapters.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum


class SourceType(Enum):
    """Types of data sources."""

    ULOG = "ulog"  # PX4 binary flight log
    MAVLINK_PCAP = "mavlink_pcap"  # MAVLink over PCAP
    MAVLINK_TEXT = "mavlink_text"  # MAVLink text log (QGC/mavlink-router)
    ROS2_BAG = "ros2_bag"  # ROS 2 bag (MCAP/SQLite)
    VIDEO = "video"  # Video file (MP4/MOV)
    SILVUS_LOG = "silvus_log"  # Silvus link quality log
    CUSTOM = "custom"


class CoordinateFrame(Enum):
    """Coordinate frames used in flight data."""

    NED = "ned"  # North-East-Down (PX4 native)
    ENU = "enu"  # East-North-Up (ROS standard)
    FRD = "frd"  # Forward-Right-Down (body frame)
    FLU = "flu"  # Forward-Left-Up (camera frame)
    LLA = "lla"  # Lat-Long-Alt (WGS84)
    ECEF = "ecef"  # Earth-Centered Earth-Fixed


@dataclass
class Provenance:
    """Standard provenance record for all derived data."""

    source_type: SourceType
    source_path: str
    source_sha256: str
    source_size_bytes: int
    transform_code_version: str  # Git commit hash of transform code
    transform_timestamp: str  # ISO 8601 UTC
    transform_params: Dict[str, Any]
    parser_version: str  # Adapter version

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["source_type"] = self.source_type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "Provenance":
        d = d.copy()
        d["source_type"] = SourceType(d["source_type"])
        return cls(**d)


@dataclass
class FlightMetadata:
    """High-level flight metadata common to all sources."""

    flight_id: str  # Unique flight identifier
    start_time_utc: str  # ISO 8601
    end_time_utc: str  # ISO 8601
    duration_s: float
    vehicle_id: str  # e.g., "Q250-V3-Opti-01"
    firmware_version: str  # PX4 version
    autopilot_hardware: str  # e.g., "Pixhawk6C"
    location: Optional[str] = None  # Human-readable location
    purpose: Optional[str] = None  # e.g., "VIO test", "Mission flight"
    weather: Optional[str] = None  # Weather conditions
    pilot: Optional[str] = None  # Pilot name
    notes: Optional[str] = None


@dataclass
class SensorSpec:
    """Sensor specification for provenance."""

    sensor_id: str
    sensor_type: str  # imu, baro, mag, gps, optical_flow, lidar, camera, etc.
    model: str
    firmware_version: str
    mount_position: Dict[str, float]  # x, y, z in body frame (m)
    mount_orientation: Dict[str, float]  # roll, pitch, yaw (rad)
    update_rate_hz: float
    noise_params: Dict[str, float]  # Sensor-specific noise parameters


# PX4 ulog message IDs we care about (subset)
PX4_KEY_MESSAGES = {
    # Estimator
    "estimator_status",
    "estimator_status_flags",
    "ekf2_innovations",
    "ekf2_innovation_variances",
    "ekf2_timestamps",
    "ekf2_replay",
    # Position/Velocity
    "vehicle_local_position",
    "vehicle_global_position",
    "vehicle_local_position_setpoint",
    # Attitude
    "vehicle_attitude",
    "vehicle_attitude_setpoint",
    "vehicle_angular_velocity",
    "vehicle_angular_acceleration",
    # Sensors
    "sensor_accel",
    "sensor_gyro",
    "sensor_mag",
    "sensor_baro",
    "sensor_gps",
    "sensor_gps2",
    "distance_sensor",
    "optical_flow",
    "airspeed",
    "vehicle_air_data",
    # Control
    "actuator_outputs",
    "actuator_controls",
    "actuator_controls_status",
    "vehicle_rates_setpoint",
    "vehicle_attitude_setpoint",
    "vehicle_thrust_setpoint",
    "vehicle_torque_setpoint",
    "manual_control_setpoint",
    "offboard_control_setpoint",
    # Status
    "vehicle_status",
    "vehicle_status_flags",
    "vehicle_land_detected",
    "vehicle_command",
    "vehicle_command_ack",
    "battery_status",
    "power_button_state",
    "rc_channels",
    "input_rc",
    # Communication
    "mavlink_log",
    "uorb_latency",
    "system_power",
    # Mission
    "mission",
    "mission_result",
    "geofence_result",
    # EKF2 internal
    "ekf2_state",
    "ekf2_covariance",
    "ekf2_innovation_filtered",
    # External vision
    "vehicle_visual_odometry",
    "vehicle_odometry",
    "estimator_visual_odometry_aligned",
    # Wind
    "wind",
    "wind_estimate",
    # ESC
    "esc_status",
    "esc_telemetry",
}


# MAVLink message IDs (common subset)
MAVLINK_KEY_MESSAGES = {
    0: "HEARTBEAT",
    1: "SYS_STATUS",
    2: "SYSTEM_TIME",
    4: "PING",
    5: "CHANGE_OPERATOR_CONTROL",
    6: "CHANGE_OPERATOR_CONTROL_ACK",
    11: "SET_MODE",
    20: "PARAM_REQUEST_READ",
    21: "PARAM_REQUEST_LIST",
    22: "PARAM_VALUE",
    23: "PARAM_SET",
    24: "GPS_RAW_INT",
    25: "GPS_STATUS",
    26: "SCALED_IMU",
    27: "RAW_IMU",
    28: "RAW_PRESSURE",
    29: "SCALED_PRESSURE",
    30: "ATTITUDE",
    31: "ATTITUDE_QUATERNION",
    32: "LOCAL_POSITION_NED",
    33: "GLOBAL_POSITION_INT",
    34: "RC_CHANNELS_RAW",
    35: "RC_CHANNELS",
    36: "RAW_CONTROLLER",
    37: "REQUEST_DATA_STREAM",
    38: "DATA_STREAM",
    39: "MANUAL_CONTROL",
    40: "RC_CHANNELS_OVERRIDE",
    41: "MISSION_ITEM",
    42: "MISSION_REQUEST",
    43: "MISSION_SET_CURRENT",
    44: "MISSION_CURRENT",
    45: "MISSION_REQUEST_LIST",
    46: "MISSION_COUNT",
    47: "MISSION_CLEAR_ALL",
    48: "MISSION_ACK",
    50: "SAFETY_ALLOWED_AREA",
    51: "SAFETY_ALLOWED_AREA",
    54: "GPS_RAW",
    55: "GPS_RTK",
    57: "COMMAND_LONG",
    58: "COMMAND_ACK",
    59: "COMMAND_CANCEL",
    60: "MANUAL_SETPOINT",
    61: "SET_ATTITUDE_TARGET",
    62: "SET_POSITION_TARGET_LOCAL_NED",
    63: "SET_POSITION_TARGET_GLOBAL_INT",
    65: "SET_ACTUATOR_CONTROL_TARGET",
    66: "SET_ACTUATOR_OUTPUT_TARGET",
    67: "HIL_STATE",
    68: "HIL_CONTROLS",
    69: "HIL_RC_INPUTS_RAW",
    70: "HIL_ACTUATOR_CONTROLS",
    71: "OPTICAL_FLOW",
    72: "GLOBAL_VISION_POSITION_ESTIMATE",
    73: "VISION_POSITION_ESTIMATE",
    74: "VISION_SPEED_ESTIMATE",
    75: "VICON_POSITION_ESTIMATE",
    76: "HIGHRES_IMU",
    77: "OPTICAL_FLOW_RAD",
    78: "HIL_STATE_QUATERNION",
    79: "HIL_GPS",
    80: "SIM_STATE",
    81: "RADIO_STATUS",
    82: "FILE_TRANSFER_PROTOCOL",
    83: "TIMESYNC",
    84: "CAMERA_TRIGGER",
    85: "HIL_ACTUATOR_CONTROLS",
    86: "HIL_OPTICAL_FLOW",
    87: "HIL_STATE_QUATERNION",
    89: "GLOBAL_POSITION_INT_COV",
    90: "LOCAL_POSITION_NED_COV",
    91: "ATTITUDE_QUATERNION_COV",
    92: "SET_ACTUATOR_CONTROL_TARGET",
    93: "ACTUATOR_OUTPUT_STATUS",
    94: "ACTUATOR_OUTPUT",
    101: "TRAJECTORY_REPRESENTATION_WAYPOINTS",
    102: "TRAJECTORY_REPRESENTATION_BEZIER",
    103: "GIMBAL_REPORT",
    104: "GIMBAL_CONTROL",
    105: "GIMBAL_DEVICE_INFORMATION",
    106: "GIMBAL_DEVICE_SET_ATTITUDE",
    107: "GIMBAL_MANAGER_INFORMATION",
    108: "GIMBAL_MANAGER_SET_MANUAL_CONTROL",
    109: "GIMBAL_MANAGER_SET_ATTITUDE",
    110: "GIMBAL_MANAGER_SET_MANUAL_CONTROL",
    111: "RTCM_DATA",
    114: "WIND_COV",
    115: "GPS_INPUT",
    116: "GPS_RTCM_DATA",
    117: "HIGH_LATENCY",
    118: "HIGH_LATENCY2",
    119: "VIBRATION",
    120: "HOME_POSITION",
    121: "SET_HOME_POSITION",
    122: "MAVLINK_LOG_ENTRY",
    123: "MAVLINK_LOG_DATA",
    124: "GPS_GLOBAL_ORIGIN",
    125: "GPS_GLOBAL_ORIGIN_ACK",
    126: "LOG_ENTRY",
    127: "LOG_DATA",
    128: "LOG_ERASE",
    129: "LOG_REQUEST_LIST",
    130: "LOG_REQUEST_DATA",
    131: "LOG_REQUEST_END",
    132: "GPS_INJECT_DATA",
    133: "GPS2_RAW",
    134: "POWER_STATUS",
    135: "SERIAL_CONTROL",
    136: "GPS_RTK",
    137: "GPS2_RTK",
    138: "SCALED_IMU2",
    139: "SCALED_IMU3",
    140: "DATA_TRANSMISSION_HANDSHAKE",
    141: "ENCAPSULATED_DATA",
    142: "DISTANCE_SENSOR",
    143: "TERRAIN_REQUEST",
    144: "TERRAIN_DATA",
    145: "TERRAIN_CHECK",
    146: "TERRAIN_REPORT",
    147: "SCALED_IMU3",
    148: "FOLLOW_TARGET",
    149: "CONTROL_SYSTEM_STATE",
    150: "TRACK_RECT",
    151: "PROGRESS",
    152: "BATTERY_STATUS",
    153: "AUTOPILOT_VERSION",
    154: "LANDING_TARGET",
    155: "ESTIMATOR_STATUS",
    156: "WIND",
    157: "DATA64",
    158: "DATA96",
    159: "DATA128",
    160: "DATA160",
    161: "DATA192",
    162: "DATA224",
    163: "DATA256",
    164: "DATA288",
    165: "DATA320",
    166: "DATA352",
    167: "DATA384",
    168: "DATA416",
    169: "DATA448",
    170: "DATA480",
    171: "DATA512",
    172: "DATA544",
    173: "DATA576",
    174: "DATA608",
    175: "DATA640",
    176: "DATA672",
    177: "DATA704",
    178: "DATA736",
    179: "DATA768",
    180: "DATA800",
    181: "DATA832",
    182: "DATA864",
    183: "DATA896",
    184: "DATA928",
    185: "DATA960",
    186: "DATA992",
    187: "DATA1024",
    188: "OBSTACLE_DISTANCE",
    189: "ODOMETRY",
    190: "TRAJECTORY_CHANGEPOINT",
    191: "MOUNT_ORIENTATION",
    192: "LOGGING_DATA",
    193: "LOGGING_DATA_ACK",
    194: "LOGGING_ACK",
    195: "VIDEO_STREAM_INFORMATION",
    196: "VIDEO_STREAM_STATUS",
    197: "SET_CAMERA_MODE",
    198: "CAMERA_CAPTURE_STATUS",
    199: "CAMERA_IMAGE_CAPTURED",
    200: "FLIGHT_INFORMATION",
    201: "MOUNT_CONTROL",
    202: "WIND",
    203: "DATA64",
    204: "DATA96",
    205: "DATA128",
    206: "DATA160",
    207: "DATA192",
    208: "DATA224",
    209: "DATA256",
    210: "DATA256",
    211: "DATA288",
    212: "DATA320",
    213: "DATA352",
    214: "DATA384",
    215: "DATA416",
    216: "DATA448",
    217: "DATA480",
    218: "DATA512",
    219: "DATA544",
    220: "DATA576",
    221: "DATA608",
    222: "DATA640",
    223: "DATA672",
    224: "DATA704",
    225: "DATA736",
    226: "DATA768",
    227: "DATA800",
    228: "DATA832",
    229: "DATA864",
    230: "DATA896",
    231: "DATA928",
    232: "DATA960",
    233: "DATA992",
    234: "DATA1024",
    235: "LOGGING_DATA",
    236: "LOGGING_DATA_ACK",
    237: "LOGGING_ACK",
    238: "VIDEO_STREAM_INFORMATION",
    239: "VIDEO_STREAM_STATUS",
    240: "SET_CAMERA_MODE",
    241: "CAMERA_CAPTURE_STATUS",
    242: "CAMERA_IMAGE_CAPTURED",
    243: "FLIGHT_INFORMATION",
    244: "MOUNT_ORIENTATION",
    245: "WIND_COV",
    246: "GPS_INPUT",
    247: "GPS_RTCM_DATA",
    248: "HIGH_LATENCY",
    249: "HIGH_LATENCY2",
    250: "VIBRATION",
    251: "HOME_POSITION",
    252: "SET_HOME_POSITION",
    253: "SET_GPS_GLOBAL_ORIGIN",
    254: "PARAM_EXT_REQUEST_READ",
    255: "PARAM_EXT_REQUEST_LIST",
    256: "PARAM_EXT_VALUE",
    257: "PARAM_EXT_SET",
    258: "PARAM_EXT_ACK",
    259: "GIMBAL_DEVICE_ATTITUDE_STATUS",
    260: "FENCE_FETCH_POINT",
    261: "FENCE_POINT",
    262: "RALLY_FETCH_POINT",
    263: "RALLY_POINT",
    264: "COMPONENT_INFORMATION",
    265: "LIMB_STATE",
    266: "ESC_STATUS",
    267: "ESC_TELEMETRY_1_TO_4",
    268: "ESC_TELEMETRY_5_TO_8",
    269: "ESC_TELEMETRY_9_TO_12",
    270: "ESC_TELEMETRY_13_TO_16",
    271: "SET_GPS_GLOBAL_ORIGIN",
    272: "TERRAIN_REPORT",
    273: "SCALED_IMU3",
    274: "DATA_TRANSMISSION_HANDSHAKE",
    275: "ENCAPSULATED_DATA",
    276: "DISTANCE_SENSOR",
    277: "TERRAIN_REQUEST",
    278: "TERRAIN_DATA",
    279: "TERRAIN_CHECK",
    280: "SCALED_IMU3",
    281: "FOLLOW_TARGET",
    282: "CONTROL_SYSTEM_STATE",
    283: "TRACK_RECT",
    284: "PROGRESS",
    285: "BATTERY_STATUS",
    286: "AUTOPILOT_VERSION",
    287: "LANDING_TARGET",
    288: "ESTIMATOR_STATUS",
    289: "WIND",
    290: "DATA64",
    291: "DATA96",
    292: "DATA128",
    293: "DATA160",
    294: "DATA192",
    295: "DATA224",
    296: "DATA256",
    297: "DATA256",
    298: "DATA288",
    299: "DATA320",
    300: "DATA352",
    301: "DATA384",
    302: "DATA416",
    303: "DATA448",
    304: "DATA480",
    305: "DATA512",
    306: "DATA544",
    307: "DATA576",
    308: "DATA608",
    309: "DATA640",
    310: "DATA672",
    311: "DATA704",
    312: "DATA736",
    313: "DATA768",
    314: "DATA800",
    315: "DATA832",
    316: "DATA864",
    317: "DATA896",
    318: "DATA928",
    319: "DATA960",
    320: "DATA992",
    321: "DATA1024",
    322: "OBSTACLE_DISTANCE",
    323: "ODOMETRY",
    324: "TRAJECTORY_CHANGEPOINT",
    325: "MOUNT_ORIENTATION",
    326: "LOGGING_DATA",
    327: "LOGGING_DATA_ACK",
    328: "LOGGING_ACK",
    329: "VIDEO_STREAM_INFORMATION",
    330: "VIDEO_STREAM_STATUS",
    331: "SET_CAMERA_MODE",
    332: "CAMERA_CAPTURE_STATUS",
    333: "CAMERA_IMAGE_CAPTURED",
    334: "FLIGHT_INFORMATION",
    335: "MOUNT_ORIENTATION",
    336: "WIND_COV",
    337: "GPS_INPUT",
    338: "GPS_RTCM_DATA",
    339: "HIGH_LATENCY",
    340: "HIGH_LATENCY2",
    341: "VIBRATION",
    342: "HOME_POSITION",
    343: "SET_HOME_POSITION",
    344: "SET_GPS_GLOBAL_ORIGIN",
    345: "PARAM_EXT_REQUEST_READ",
    346: "PARAM_EXT_REQUEST_LIST",
    347: "PARAM_EXT_VALUE",
    348: "PARAM_EXT_SET",
    349: "PARAM_EXT_ACK",
    350: "GIMBAL_DEVICE_ATTITUDE_STATUS",
    351: "FENCE_FETCH_POINT",
    352: "FENCE_POINT",
    353: "RALLY_FETCH_POINT",
    354: "RALLY_POINT",
    355: "COMPONENT_INFORMATION",
    356: "LIMB_STATE",
    357: "ESC_STATUS",
    358: "ESC_TELEMETRY_1_TO_4",
    359: "ESC_TELEMETRY_5_TO_8",
    360: "ESC_TELEMETRY_9_TO_12",
    361: "ESC_TELEMETRY_13_TO_16",
    362: "SET_GPS_GLOBAL_ORIGIN",
    363: "TERRAIN_REPORT",
    364: "SCALED_IMU3",
    365: "DATA_TRANSMISSION_HANDSHAKE",
    366: "ENCAPSULATED_DATA",
    367: "DISTANCE_SENSOR",
    368: "TERRAIN_REQUEST",
    369: "TERRAIN_DATA",
    370: "TERRAIN_CHECK",
    371: "SCALED_IMU3",
    372: "FOLLOW_TARGET",
    373: "CONTROL_SYSTEM_STATE",
    374: "TRACK_RECT",
    375: "PROGRESS",
    376: "BATTERY_STATUS",
    377: "AUTOPILOT_VERSION",
    378: "LANDING_TARGET",
    379: "ESTIMATOR_STATUS",
    380: "WIND",
    381: "DATA64",
    382: "DATA96",
    383: "DATA128",
    384: "DATA160",
    385: "DATA192",
    386: "DATA224",
    387: "DATA256",
    388: "DATA256",
    389: "DATA288",
    390: "DATA320",
    391: "DATA352",
    392: "DATA384",
    393: "DATA416",
    394: "DATA448",
    395: "DATA480",
    396: "DATA512",
    397: "DATA544",
    398: "DATA576",
    399: "DATA608",
    400: "DATA640",
    401: "DATA672",
    402: "DATA704",
    403: "DATA736",
    404: "DATA768",
    405: "DATA800",
    406: "DATA832",
    407: "DATA864",
    408: "DATA896",
    409: "DATA928",
    410: "DATA960",
    411: "DATA992",
    412: "DATA1024",
    413: "OBSTACLE_DISTANCE",
    414: "ODOMETRY",
    415: "TRAJECTORY_CHANGEPOINT",
    416: "MOUNT_ORIENTATION",
    417: "LOGGING_DATA",
    418: "LOGGING_DATA_ACK",
    419: "LOGGING_ACK",
    420: "VIDEO_STREAM_INFORMATION",
    421: "VIDEO_STREAM_STATUS",
    422: "SET_CAMERA_MODE",
    423: "CAMERA_CAPTURE_STATUS",
    424: "CAMERA_IMAGE_CAPTURED",
    425: "FLIGHT_INFORMATION",
    426: "MOUNT_ORIENTATION",
    427: "WIND_COV",
    428: "GPS_INPUT",
    429: "GPS_RTCM_DATA",
    430: "HIGH_LATENCY",
    431: "HIGH_LATENCY2",
    432: "VIBRATION",
    433: "HOME_POSITION",
    434: "SET_HOME_POSITION",
    435: "SET_GPS_GLOBAL_ORIGIN",
    436: "PARAM_EXT_REQUEST_READ",
    437: "PARAM_EXT_REQUEST_LIST",
    438: "PARAM_EXT_VALUE",
    439: "PARAM_EXT_SET",
    440: "PARAM_EXT_ACK",
    441: "GIMBAL_DEVICE_ATTITUDE_STATUS",
    442: "FENCE_FETCH_POINT",
    443: "FENCE_POINT",
    444: "RALLY_FETCH_POINT",
    445: "RALLY_POINT",
    446: "COMPONENT_INFORMATION",
    447: "LIMB_STATE",
    448: "ESC_STATUS",
    449: "ESC_TELEMETRY_1_TO_4",
    450: "ESC_TELEMETRY_5_TO_8",
    451: "ESC_TELEMETRY_9_TO_12",
    452: "ESC_TELEMETRY_13_TO_16",
}


# SQL Schema for multi-modal flight log database
FLIGHTLOG_SQL_SCHEMA = """
-- Flight log database schema
-- Supports multi-modal data: ulog, mavlink, rosbag, video, silvus
-- All tables include provenance (SHA-256, version, timestamp)

-- Flights table: one row per flight
CREATE TABLE IF NOT EXISTS flights (
    flight_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,           -- ulog, mavlink_pcap, ros2_bag, etc.
    source_path TEXT NOT NULL,           -- Original file path
    source_sha256 TEXT NOT NULL,         -- SHA-256 of source file
    source_size_bytes INTEGER,
    start_time_utc TEXT NOT NULL,        -- ISO 8601
    end_time_utc TEXT NOT NULL,          -- ISO 8601
    duration_s REAL,
    vehicle_id TEXT,
    firmware_version TEXT,
    autopilot_hardware TEXT,
    location TEXT,
    purpose TEXT,
    weather TEXT,
    pilot TEXT,
    notes TEXT,
    transform_code_version TEXT,         -- Git commit of parser
    transform_timestamp TEXT,            -- ISO 8601 when parsed
    transform_params TEXT,               -- JSON
    parser_version TEXT,                 -- Adapter version
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_sha256, source_type)
);

-- Time sync points between sources
CREATE TABLE IF NOT EXISTS time_sync_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    source_a TEXT NOT NULL,              -- e.g., 'ulog', 'mavlink', 'rosbag'
    source_b TEXT NOT NULL,
    timestamp_a REAL NOT NULL,           -- Unix seconds in source A timebase
    timestamp_b REAL NOT NULL,           -- Unix seconds in source B timebase
    confidence REAL NOT NULL,            -- 0.0-1.0
    method TEXT NOT NULL,                -- mavlink_timesync, gps_pps, ntp, manual
    provenance_a TEXT,                   -- SHA-256 of source A
    provenance_b TEXT,                   -- SHA-256 of source B
    transform_code_version TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);

-- Time transforms (linear: t_ref = scale * t_src + offset)
CREATE TABLE IF NOT EXISTS time_transforms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    source_name TEXT NOT NULL,           -- Source being transformed
    reference_source TEXT NOT NULL,      -- Reference timebase (e.g., 'ulog')
    scale REAL NOT NULL DEFAULT 1.0,
    offset REAL NOT NULL DEFAULT 0.0,
    r_squared REAL,
    sync_points_used INTEGER,
    provenance TEXT,                     -- JSON of source->SHA256
    transform_code_version TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id),
    UNIQUE(flight_id, source_name)
);

-- Sensor specifications
CREATE TABLE IF NOT EXISTS sensor_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    sensor_type TEXT NOT NULL,
    model TEXT,
    firmware_version TEXT,
    mount_x REAL, mount_y REAL, mount_z REAL,  -- Body frame (m)
    mount_roll REAL, mount_pitch REAL, mount_yaw REAL,  -- Body frame (rad)
    update_rate_hz REAL,
    noise_params TEXT,                   -- JSON
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);

-- EKF2 innovations (residuals) - key for estimator health
CREATE TABLE IF NOT EXISTS ekf2_innovations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,             -- Aligned to reference timebase (seconds)
    timestamp_original REAL,             -- Original timestamp
    timebase TEXT,                       -- Original timebase name
    
    -- Position innovations (NED, meters)
    pos_innov_n REAL, pos_innov_e REAL, pos_innov_d REAL,
    pos_innov_var_n REAL, pos_innov_var_e REAL, pos_innov_var_d REAL,
    
    -- Velocity innovations (NED, m/s)
    vel_innov_n REAL, vel_innov_e REAL, vel_innov_d REAL,
    vel_innov_var_n REAL, vel_innov_var_e REAL, vel_innov_var_d REAL,
    
    -- Angle innovations (rad)
    ang_innov_x REAL, ang_innov_y REAL, ang_innov_z REAL,
    ang_innov_var_x REAL, ang_innov_var_y REAL, ang_innov_var_z REAL,
    
    -- External vision (if available)
    ev_pos_innov_n REAL, ev_pos_innov_e REAL, ev_pos_innov_d REAL,
    ev_vel_innov_n REAL, ev_vel_innov_e REAL, ev_vel_innov_d REAL,
    ev_yaw_innov REAL,
    
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_ekf2_innovations_flight_time ON ekf2_innovations(flight_id, timestamp);

-- Estimator status
CREATE TABLE IF NOT EXISTS estimator_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    nan_flags INTEGER,
    health_flags INTEGER,
    timeout_flags INTEGER,
    gps_check_fail_flags INTEGER,
    innovation_fault_flags INTEGER,
    mag_fault_flags INTEGER,
    solution_status INTEGER,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_estimator_status_flight_time ON estimator_status(flight_id, timestamp);

-- Vehicle local position (NED)
CREATE TABLE IF NOT EXISTS vehicle_local_position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    x REAL, y REAL, z REAL,              -- Position (m)
    vx REAL, vy REAL, vz REAL,           -- Velocity (m/s)
    ax REAL, ay REAL, az REAL,           -- Acceleration (m/s^2)
    yaw REAL, yaw_rate REAL,             -- Yaw (rad), yaw rate (rad/s)
    xy_valid INTEGER, z_valid INTEGER,
    v_xy_valid INTEGER, v_z_valid INTEGER,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_vehicle_local_pos_flight_time ON vehicle_local_position(flight_id, timestamp);

-- Vehicle global position (LLA)
CREATE TABLE IF NOT EXISTS vehicle_global_position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    lat REAL, lon REAL, alt REAL,        -- WGS84 (deg, deg, m MSL)
    alt_ellipsoid REAL,
    eph REAL, epv REAL,                  -- Horizontal/vertical accuracy (m)
    terrain_alt REAL, terrain_alt_valid INTEGER,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_vehicle_global_pos_flight_time ON vehicle_global_position(flight_id, timestamp);

-- Distance sensor (LiDAR, range finder)
CREATE TABLE IF NOT EXISTS distance_sensor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    sensor_id INTEGER,
    sensor_type INTEGER,                 -- MAVLink distance sensor type
    orientation INTEGER,
    current_distance REAL,               -- Meters
    covariance REAL,
    signal_quality INTEGER,
    min_distance REAL, max_distance REAL,
    update_rate REAL,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_distance_sensor_flight_time ON distance_sensor(flight_id, timestamp);

-- Optical flow
CREATE TABLE IF NOT EXISTS optical_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    sensor_id INTEGER,
    integration_timespan INTEGER,        -- Microseconds
    pixel_flow_x REAL, pixel_flow_y REAL,
    flow_comp_m_x REAL, flow_comp_m_y REAL,  -- Flow in m/s
    quality INTEGER,
    gyro_x_rate REAL, gyro_y_rate REAL, gyro_z_rate REAL,
    gyro_range REAL,
    ground_distance REAL,
    ground_distance_valid INTEGER,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_optical_flow_flight_time ON optical_flow(flight_id, timestamp);

-- Attitude
CREATE TABLE IF NOT EXISTS vehicle_attitude (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    q0 REAL, q1 REAL, q2 REAL, q3 REAL,  -- Quaternion
    roll REAL, pitch REAL, yaw REAL,     -- Euler (rad)
    rollspeed REAL, pitchspeed REAL, yawspeed REAL,  -- Body rates (rad/s)
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_vehicle_attitude_flight_time ON vehicle_attitude(flight_id, timestamp);

-- Actuator outputs
CREATE TABLE IF NOT EXISTS actuator_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    output_0 REAL, output_1 REAL, output_2 REAL, output_3 REAL,
    output_4 REAL, output_5 REAL, output_6 REAL, output_7 REAL,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_actuator_outputs_flight_time ON actuator_outputs(flight_id, timestamp);

-- Battery status
CREATE TABLE IF NOT EXISTS battery_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    voltage_v REAL, current_a REAL,
    remaining_percent REAL,
    capacity_mah REAL,
    temperature_c REAL,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_battery_status_flight_time ON battery_status(flight_id, timestamp);

-- RC channels
CREATE TABLE IF NOT EXISTS rc_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    chan1_raw INTEGER, chan2_raw INTEGER, chan3_raw INTEGER, chan4_raw INTEGER,
    chan5_raw INTEGER, chan6_raw INTEGER, chan7_raw INTEGER, chan8_raw INTEGER,
    chan9_raw INTEGER, chan10_raw INTEGER, chan11_raw INTEGER, chan12_raw INTEGER,
    chan13_raw INTEGER, chan14_raw INTEGER, chan15_raw INTEGER, chan16_raw INTEGER,
    rssi INTEGER, rssi_max INTEGER,
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_rc_channels_flight_time ON rc_channels(flight_id, timestamp);

-- MAVLink raw messages (for messages not covered by specific tables)
CREATE TABLE IF NOT EXISTS mavlink_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    msg_type TEXT NOT NULL,              -- e.g., 'GLOBAL_POSITION_INT'
    msg_id INTEGER NOT NULL,
    system_id INTEGER, component_id INTEGER,
    payload TEXT,                        -- JSON
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_mavlink_flight_time ON mavlink_messages(flight_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_mavlink_flight_type ON mavlink_messages(flight_id, msg_type);

-- Silvus link quality
CREATE TABLE IF NOT EXISTS silvus_link_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    timestamp_original REAL,
    timebase TEXT,
    air_unit_id TEXT,                    -- e.g., 'air_01', 'gdt'
    rssi_dbm REAL,
    snr_db REAL,
    packet_loss_pct REAL,
    rtt_ms REAL,
    hop_count INTEGER,
    topology_json TEXT,                  -- Full topology snapshot
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_silvus_flight_time ON silvus_link_quality(flight_id, timestamp);

-- Events/annotations (human or auto-detected)
CREATE TABLE IF NOT EXISTS flight_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,            -- takeoff, landing, mode_change, failsafe, anomaly, etc.
    severity TEXT,                       -- info, warning, critical
    description TEXT,
    source TEXT,                         -- manual, auto_ekf2, auto_silvus, etc.
    related_data TEXT,                   -- JSON with context
    provenance TEXT,
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_flight_events_flight_time ON flight_events(flight_id, timestamp);

-- Analysis results (derived metrics)
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    analysis_type TEXT NOT NULL,         -- ekf2_health, vio_quality, link_quality, etc.
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_unit TEXT,
    time_window_start REAL,
    time_window_end REAL,
    details TEXT,                        -- JSON
    provenance TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(flight_id) REFERENCES flights(flight_id)
);
CREATE INDEX IF NOT EXISTS idx_analysis_flight_type ON analysis_results(flight_id, analysis_type);
"""


def compute_sha256(filepath: Union[str, Path]) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_git_hash(repo_path: Optional[Path] = None) -> str:
    """Get current git commit hash."""
    import subprocess

    cwd = repo_path or Path(__file__).parent.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=cwd
        )
        return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.utcnow().isoformat() + "Z"


# Coordinate frame transformations
def ned_to_enu(north: float, east: float, down: float) -> Tuple[float, float, float]:
    """NED to ENU: x_enu = east, y_enu = north, z_enu = -down"""
    return east, north, -down


def enu_to_ned(east: float, north: float, up: float) -> Tuple[float, float, float]:
    """ENU to NED: x_ned = north, y_ned = east, z_ned = -up"""
    return north, east, -up


def lla_to_ecef(lat: float, lon: float, alt: float) -> Tuple[float, float, float]:
    """LLA (WGS84) to ECEF. lat/lon in degrees, alt in meters."""
    import math

    # WGS84 ellipsoid
    a = 6378137.0  # Semi-major axis (m)
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f  # Eccentricity squared

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    N = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)

    x = (N + alt) * math.cos(lat_rad) * math.cos(lon_rad)
    y = (N + alt) * math.cos(lat_rad) * math.sin(lon_rad)
    z = (N * (1 - e2) + alt) * math.sin(lat_rad)

    return x, y, z


def ecef_to_lla(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """ECEF to LLA (WGS84). Returns lat, lon in degrees, alt in meters."""
    import math

    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f
    b = a * (1 - f)
    ep2 = (a * a - b * b) / (b * b)

    p = math.sqrt(x * x + y * y)
    th = math.atan2(z * a, p * b)

    lat = math.atan2(z + ep2 * b * math.sin(th) ** 3, p - e2 * a * math.cos(th) ** 3)
    lon = math.atan2(y, x)
    N = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - N

    return math.degrees(lat), math.degrees(lon), alt


def quat_to_euler(
    q0: float, q1: float, q2: float, q3: float
) -> Tuple[float, float, float]:
    """Quaternion to Euler angles (roll, pitch, yaw) in radians. ZYX convention."""
    import math

    # Roll (x-axis rotation)
    sinr_cosp = 2 * (q0 * q1 + q2 * q3)
    cosr_cosp = 1 - 2 * (q1 * q1 + q2 * q2)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2 * (q0 * q2 - q3 * q1)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2 * (q0 * q3 + q1 * q2)
    cosy_cosp = 1 - 2 * (q2 * q2 + q3 * q3)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def euler_to_quat(
    roll: float, pitch: float, yaw: float
) -> Tuple[float, float, float, float]:
    """Euler angles (roll, pitch, yaw) in radians to quaternion. ZYX convention."""
    import math

    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)

    q0 = cr * cp * cy + sr * sp * sy
    q1 = sr * cp * cy - cr * sp * sy
    q2 = cr * sp * cy + sr * cp * sy
    q3 = cr * cp * sy - sr * sp * cy

    return q0, q1, q2, q3
