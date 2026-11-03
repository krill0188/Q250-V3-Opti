-- Flight log database schema for multi-modal flight data
-- Supports: PX4 ulog, MAVLink (PCAP/text), ROS 2 bag, Silvus logs, Video
-- All tables include provenance (SHA-256, version, timestamp) for traceability

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