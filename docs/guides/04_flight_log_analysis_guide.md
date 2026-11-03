# Q250-V3 Opti 실전 가이드: 비행 로그 분석 파이프라인 (Step-by-Step)

> **목적**: PX4 ulog + MAVLink PCAP + ROS 2 bag + Silvus 로그 → 멀티모달 DB → 자동 분석 리포트  
> **전제**: integration/ 어댑터 빌드 완료, flightlog DB 초기화 완료  
> **예상 소요**: 초기 설정 1일, 비행 후 분석 30분/회  
> **핵심**: **Provenance(SHA-256, Git hash, 타임스탬프) 완전 기록** → 재현 가능성 보장

---

## 📋 Phase 0: 환경 준비 및 DB 초기화

### 0.1 통합 어댑터 빌드 확인
```bash
cd /Users/amaster/projectm/Q250-V3-Opti

# integration 패키지 문법 검사
python3 -m py_compile integration/flightlog_adapter.py
python3 -m py_compile integration/mavlink_adapter.py
python3 -m py_compile integration/align.py
python3 -m py_compile integration/common.py

# 의존성 설치 (최초 1회)
pip install pyulog dpkt pymavlink scipy numpy
```

### 0.2 비행 로그 DB 초기화 (완료 확인)
```bash
# 이미 실행됐다면 스킵
python3 scripts/init_flightlog_db.py

# 출력 확인: 19개 테이블, 18개 인덱스 생성됨
# tables: flights, ekf2_innovations, vehicle_local_position, 
#         vehicle_global_position, distance_sensor, optical_flow,
#         vehicle_attitude, actuator_outputs, battery_status,
#         rc_channels, mavlink_messages, silvus_link_quality,
#         flight_events, analysis_results, time_sync_points,
#         time_transforms, sensor_specs
```

### 0.3 테스트 데이터로 파이프라인 검증
```bash
python3 scripts/test_flightlog_integration.py
# 출력: "✅ Demo complete! Database ready for real flight data."
```

---

## 📋 Phase 1: 비행 데이터 수집 및 파일 정리 (비행 직후)

### 1.1 비행 후 파일 수집 체크리스트
```bash
# 각 비행을 고유 폴더에 정리
mkdir -p /Users/amaster/projectm/Q250-V3-Opti/flight_logs/raw/FLIGHT_20261104_001

# 필수 파일들 복사:
# 1. PX4 ulog (SD 카드 또는 QGC 다운로드)
cp /path/to/log_001.ulg flight_logs/raw/FLIGHT_20261104_001/

# 2. MAVLink PCAP (Silvus 링크 품질용, Wireshark 캡처)
cp /path/to/mavlink_flight_001.pcap flight_logs/raw/FLIGHT_20261104_001/

# 3. MAVLink 텍스트 로그 (mavlink-router 또는 QGC 콘솔 로그)
cp /path/to/mavlink_flight_001.txt flight_logs/raw/FLIGHT_20261104_001/

# 4. ROS 2 bag (VIO, 플래너, 카메라 데이터)
cp -r /path/to/rosbag_flight_001 flight_logs/raw/FLIGHT_20261104_001/

# 5. Silvus 링크 품질 로그
cp /path/to/silvus_flight_001.csv flight_logs/raw/FLIGHT_20261104_001/

# 6. 비행 메타데이터 기록 (메모장 또는 YAML)
cat > flight_logs/raw/FLIGHT_20261104_001/meta.yaml << 'EOF'
flight_id: "FLIGHT_20261104_001"
date: "2026-11-04"
purpose: "VIO Integration Test - Mission/RTL"
location: "Indoor Lab"
vehicle: "Q250-V3-Opti-01"
pilot: "Test Pilot"
weather: "N/A (indoor)"
notes: "First fake GPS mission test. VIO drift observed after 5min."
config_git_hash: "abc1234"
px4_params_version: "v1.1-baseline+v2"
EOF
```

### 1.2 SHA-256 해시 계산 및 기록 (Provenance 핵심)
```bash
cd /Users/amaster/projectm/Q250-V3-Opti/flight_logs/raw/FLIGHT_20261104_001

# 모든 원본 파일 해시 계산
sha256sum *.ulg *.pcap *.txt *.csv *.bag > SHA256SUMS.txt
cat SHA256SUMS.txt
# 출력 예:
# a1b2c3d4e5f6...  log_001.ulg
# f6e5d4c3b2a1...  mavlink_flight_001.pcap
# ...

# meta.yaml에 해시 추가
# (나중 파이프라인이 자동으로 읽음)
```

---

## 📋 Phase 2: 자동 파싱 및 DB 적재 (스크립트 실행)

### 2.1 통합 파싱 스크립트 생성
```bash
cat > /Users/amaster/projectm/Q250-V3-Opti/scripts/parse_flight.py << 'PYEOF'
#!/usr/bin/env python3
"""
비행 로그 자동 파싱 및 DB 적재
Usage: python3 parse_flight.py FLIGHT_20261104_001
"""

import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from integration import (
    FlightLogAdapter,
    MAVLinkAdapter,
    TimeAligner,
    compute_sha256,
    get_git_hash,
    utc_now_iso,
)

DB_PATH = '/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db/flightlog.db'
RAW_BASE = '/Users/amaster/projectm/Q250-V3-Opti/flight_logs/raw'


def parse_flight(flight_id: str):
    flight_dir = Path(RAW_BASE) / flight_id
    if not flight_dir.exists():
        raise FileNotFoundError(f"Flight directory not found: {flight_dir}")

    # 메타데이터 로드
    meta_file = flight_dir / 'meta.yaml'
    meta = {}
    if meta_file.exists():
        with open(meta_file) as f:
            meta = yaml.safe_load(f)

    print(f"=" * 60)
    print(f"Parsing flight: {flight_id}")
    print(f"=" * 60)

    # 1. PX4 ulog 파싱
    ulog_files = list(flight_dir.glob('*.ulg'))
    ulog_data = None
    if ulog_files:
        print(f"\n[1/5] Parsing ulog: {ulog_files[0]}")
        adapter = FlightLogAdapter()
        ulog_data = adapter.parse(str(ulog_files[0]))
        print(f"    Topics: {list(ulog_data.keys())}")
        print(f"    EKF2 innovations: {len(ulog_data.get('ekf2_innovations', []))}")
        print(f"    Local positions: {len(ulog_data.get('vehicle_local_position', []))}")
    else:
        print("\n[1/5] No ulog file found")

    # 2. MAVLink PCAP 파싱
    pcap_files = list(flight_dir.glob('*.pcap')) + list(flight_dir.glob('*.pcapng'))
    mavlink_data = None
    if pcap_files:
        print(f"\n[2/5] Parsing PCAP: {pcap_files[0]}")
        adapter = MAVLinkAdapter()
        mavlink_data = adapter.parse_pcap(str(pcap_files[0]), 
                                          filter_types=['GLOBAL_POSITION_INT', 'LOCAL_POSITION_NED', 
                                                        'ATTITUDE', 'GPS_RAW_INT', 'TIMESYNC',
                                                        'DISTANCE_SENSOR', 'OPTICAL_FLOW_RAD',
                                                        'VISION_POSITION_ESTIMATE', 'ODOMETRY',
                                                        'ESTIMATOR_STATUS', 'EKF2_INNOVATIONS',
                                                        'BATTERY_STATUS', 'RC_CHANNELS',
                                                        'HEARTBEAT', 'SYS_STATUS'])
        print(f"    Message types: {len(mavlink_data.get('messages', {}))}")
        for k, v in mavlink_data.get('message_counts', {}).items():
            print(f"    {k}: {v}")
    else:
        print("\n[2/5] No PCAP file found")

    # 3. MAVLink 텍스트 로그 파싱 (보조)
    txt_files = list(flight_dir.glob('*.txt')) + list(flight_dir.glob('*.log'))
    if txt_files:
        print(f"\n[3/5] Parsing text log: {txt_files[0]}")
        adapter = MAVLinkAdapter()
        txt_data = adapter.parse_text_log(str(txt_files[0]),
                                          filter_types=['GLOBAL_POSITION_INT', 'LOCAL_POSITION_NED',
                                                        'ATTITUDE', 'GPS_RAW_INT', 'TIMESYNC',
                                                        'DISTANCE_SENSOR', 'OPTICAL_FLOW_RAD',
                                                        'VISION_POSITION_ESTIMATE', 'ODOMETRY',
                                                        'ESTIMATOR_STATUS', 'EKF2_INNOVATIONS'])
        print(f"    Message types: {len(txt_data.get('messages', {}))}")
    else:
        print("\n[3/5] No text log file found")

    # 4. Silvus 로그 파싱 (CSV)
    silvus_files = list(flight_dir.glob('*silvus*.csv'))
    if silvus_files:
        print(f"\n[4/5] Parsing Silvus log: {silvus_files[0]}")
        # CSV 파싱 후 DB에 직접 저장 (별도 구현 필요)
        print(f"    Silvus log found: {silvus_files[0]}")
    else:
        print("\n[4/5] No Silvus log found")

    # 5. ROS 2 bag 파싱 (별도 구현 필요)
    bag_dirs = [d for d in flight_dir.iterdir() if d.is_dir() and 'bag' in d.name.lower()]
    if bag_dirs:
        print(f"\n[5/5] ROS 2 bag found: {bag_dirs[0]}")
        print(f"    (bag parsing not yet implemented)")
    else:
        print("\n[5/5] No ROS 2 bag found")

    print(f"\n✅ Parsing complete for {flight_id}")
    print(f"Next: Run DB insertion script")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 parse_flight.py FLIGHT_ID")
        print("Example: python3 parse_flight.py FLIGHT_20261104_001")
        sys.exit(1)
    parse_flight(sys.argv[1])
PYEOF

chmod +x /Users/amaster/projectm/Q250-V3-Opti/scripts/parse_flight.py
```

### 2.2 파싱 실행
```bash
cd /Users/amaster/projectm/Q250-V3-Opti
python3 scripts/parse_flight.py FLIGHT_20261104_001

# 출력 예:
# ============================================================
# Parsing flight: FLIGHT_20261104_001
# ============================================================
# 
# [1/5] Parsing ulog: .../log_001.ulg
#     Topics: ['metadata', 'estimator_status', 'ekf2_innovations', ...]
#     EKF2 innovations: 1250
#     Local positions: 1250
# 
# [2/5] Parsing PCAP: .../mavlink_flight_001.pcap
#     Message types: 15
#     GLOBAL_POSITION_INT: 500
#     LOCAL_POSITION_NED: 500
#     ...
# 
# ✅ Parsing complete for FLIGHT_20261104_001
```

---

## 📋 Phase 3: DB 적재 및 시간 정렬 (자동화)

### 3.1 DB 적재 스크립트 (기존 test_flightlog_integration.py 확장)
```bash
cat > /Users/amaster/projectm/Q250-V3-Opti/scripts/ingest_flight.py << 'PYEOF'
#!/usr/bin/env python3
"""
파싱된 데이터를 flightlog DB에 적재 (Provenance 포함)
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from integration import (
    FlightLogAdapter,
    MAVLinkAdapter,
    compute_sha256,
    get_git_hash,
    utc_now_iso,
)


DB_PATH = '/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db/flightlog.db'
RAW_BASE = '/Users/amaster/projectm/Q250-V3-Opti/flight_logs/raw'


def insert_flight_record(conn, flight_id: str, meta: dict, ulog_sha256: str = None) -> str:
    """flights 테이블에 비행 메타데이터 기록"""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO flights (
            flight_id, source_type, source_path, source_sha256, source_size_bytes,
            start_time_utc, end_time_utc, duration_s,
            vehicle_id, firmware_version, autopilot_hardware,
            location, purpose, weather, pilot, notes,
            transform_code_version, transform_timestamp, transform_params, parser_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        flight_id,
        'ulog',
        str(RAW_BASE / flight_id / f'{flight_id}.ulg'),
        ulog_sha256 or 'unknown',
        meta.get('source_size_bytes', 0),
        meta.get('start_time_utc', utc_now_iso()),
        meta.get('end_time_utc', utc_now_iso()),
        meta.get('duration_s', 0.0),
        meta.get('vehicle_id', 'Q250-V3-Opti'),
        meta.get('firmware_version', 'PX4 v1.15'),
        meta.get('autopilot_hardware', 'Pixhawk6C'),
        meta.get('location', 'Indoor Lab'),
        meta.get('purpose', 'Test Flight'),
        meta.get('weather', 'N/A'),
        meta.get('pilot', 'Test Pilot'),
        meta.get('notes', ''),
        get_git_hash(),
        utc_now_iso(),
        json.dumps({'parser': 'pyulog'}),
        'flightlog_adapter/0.1.0'
    ))
    conn.commit()
    return flight_id


def ingest_ulog(conn, flight_id: str, ulog_path: Path):
    """ulog 파싱 후 핵심 테이블에 적재"""
    adapter = FlightLogAdapter()
    data = adapter.parse(str(ulog_path))
    provenance = f"sha256:{compute_sha256(ulog_path)}|flightlog_adapter/0.1.0|{utc_now_iso()}"
    
    # EKF2 innovations
    count = 0
    cursor = conn.cursor()
    for innov in data.get('ekf2_innovations', []):
        cursor.execute("""
            INSERT INTO ekf2_innovations (
                flight_id, timestamp, timestamp_original, timebase,
                pos_innov_n, pos_innov_e, pos_innov_d,
                pos_innov_var_n, pos_innov_var_e, pos_innov_var_d,
                vel_innov_n, vel_innov_e, vel_innov_d,
                vel_innov_var_n, vel_innov_var_e, vel_innov_var_d,
                ang_innov_x, ang_innov_y, ang_innov_z,
                ang_innov_var_x, ang_innov_var_y, ang_innov_var_z,
                provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            flight_id,
            innov.get('timestamp', 0) / 1e6,  # us -> s
            innov.get('timestamp', 0) / 1e6,
            'ulog',
            innov.get('pos_innov', [None]*3)[0],
            innov.get('pos_innov', [None]*3)[1],
            innov.get('pos_innov', [None]*3)[2],
            innov.get('pos_innov_var', [None]*3)[0],
            innov.get('pos_innov_var', [None]*3)[1],
            innov.get('pos_innov_var', [None]*3)[2],
            innov.get('vel_innov', [None]*3)[0],
            innov.get('vel_innov', [None]*3)[1],
            innov.get('vel_innov', [None]*3)[2],
            innov.get('vel_innov_var', [None]*3)[0],
            innov.get('vel_innov_var', [None]*3)[1],
            innov.get('vel_innov_var', [None]*3)[2],
            innov.get('ang_innov', [None]*3)[0],
            innov.get('ang_innov', [None]*3)[1],
            innov.get('ang_innov', [None]*3)[2],
            innov.get('ang_innov_var', [None]*3)[0],
            innov.get('ang_innov_var', [None]*3)[1],
            innov.get('ang_innov_var', [None]*3)[2],
            provenance
        ))
        count += 1
    conn.commit()
    print(f"  Inserted {count} EKF2 innovation records")
    
    # Vehicle local position
    count = 0
    for pos in data.get('vehicle_local_position', []):
        cursor.execute("""
            INSERT INTO vehicle_local_position (
                flight_id, timestamp, timestamp_original, timebase,
                x, y, z, vx, vy, vz, ax, ay, az, yaw, yaw_rate,
                xy_valid, z_valid, v_xy_valid, v_z_valid, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            flight_id,
            pos.get('timestamp', 0) / 1e6,
            pos.get('timestamp', 0) / 1e6,
            'ulog',
            pos.get('x'), pos.get('y'), pos.get('z'),
            pos.get('vx'), pos.get('vy'), pos.get('vz'),
            pos.get('ax'), pos.get('ay'), pos.get('az'),
            pos.get('yaw'), pos.get('yaw_rate'),
            pos.get('xy_valid'), pos.get('z_valid'),
            pos.get('v_xy_valid'), pos.get('v_z_valid'),
            provenance
        ))
        count += 1
    conn.commit()
    print(f"  Inserted {count} local position records")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ingest_flight.py FLIGHT_ID")
        sys.exit(1)
    
    flight_id = sys.argv[1]
    flight_dir = Path('/Users/amaster/projectm/Q250-V3-Opti/flight_logs/raw') / flight_id
    
    if not flight_dir.exists():
        print(f"Flight directory not found: {flight_dir}")
        sys.exit(1)
    
    # 메타데이터 로드
    meta = {}
    meta_file = flight_dir / 'meta.yaml'
    if meta_file.exists():
        import yaml
        with open(meta_file) as f:
            meta = yaml.safe_load(f)
    
    # ulog 파일 찾기
    ulog_files = list(flight_dir.glob('*.ulg'))
    if not ulog_files:
        print("No ulog file found")
        sys.exit(1)
    ulog_path = ulog_files[0]
    
    # SHA-256 계산
    from integration import compute_sha256
    ulog_sha256 = compute_sha256(ulog_path)
    
    # DB 연결
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        print(f"Ingesting flight: {flight_id}")
        
        # 1. Flight record
        insert_flight_record(conn, flight_id, meta, compute_sha256(ulog_path))
        print(f"  Flight record inserted")
        
        # 2. Ulog data
        ingest_ulog(conn, flight_id, ulog_path)
        
        print(f"✅ Ingestion complete for {flight_id}")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
PYEOF

chmod +x /Users/amaster/projectm/Q250-V3-Opti/scripts/ingest_flight.py
```

### 3.2 적재 실행
```bash
python3 scripts/ingest_flight.py FLIGHT_20261104_001

# 출력:
# Ingesting flight: FLIGHT_20261104_001
#   Flight record inserted
#   Inserted 1250 EKF2 innovation records
#   Inserted 1250 local position records
# ✅ Ingestion complete for FLIGHT_20261104_001
```

### 3.3 시간 정렬 (멀티소스 데이터 있는 경우)
```bash
python3 << 'EOF'
from integration import TimeAligner, compute_sha256
from pathlib import Path

flight_id = "FLIGHT_20261104_001"
base = Path('/Users/amaster/projectm/Q250-V3-Opti/flight_logs/raw') / flight_id

# TimeAligner 초기화 (ulog를 reference로)
aligner = TimeAligner(reference_source='ulog')
aligner.add_source('ulog', str(base / f'{flight_id}.ulg'))
aligner.add_source('mavlink', str(base / 'mavlink_flight_001.pcap'))

# TIMESYNC 메시지로 동기화 포인트 추출
# (MAVLinkAdapter로 TIMESYNC 파싱 후 add_mavlink_timesync 호출)
# aligner.add_mavlink_timesync('ulog', 'mavlink', timesync_ulog, timesync_mavlink)

# 변환 계산
transforms = aligner.compute_transforms()
for src, tf in transforms.items():
    print(f"{src} -> ulog: scale={tf.scale:.6f}, offset={tf.offset:.6f}s, R²={tf.r_squared:.6f}")

# Provenance 저장
aligner.save_provenance(str(Path('/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db') / f'{flight_id}_alignment.json'))
EOF
```

---

## 📋 Phase 4: 자동 분석 리포트 생성

### 4.1 분석 스크립트 실행
```bash
python3 scripts/postflight/analyze_log.py flight_logs/db/flightlog.db FLIGHT_20261104_001

# 출력 예:
# ============================================================
# Flight Analysis Report: FLIGHT_20261104_001
# ============================================================
# Duration: 452.3s (7.5 min)
# Vehicle: Q250-V3-Opti-01
# 
# --- EKF2 Health ---
# Solution Status: 3 (All sensors fused)
# Position Innovation (NED): mean=[0.01, -0.02, 0.00], std=[0.05, 0.06, 0.03] m
# Velocity Innovation: mean=[0.00, 0.00, 0.00], std=[0.02, 0.02, 0.01] m/s
# Yaw Innovation: mean=0.001, std=0.005 rad
# Innovation 3-sigma violation rate: 1.2% (target < 5%)
# 
# --- VIO Quality ---
# External Vision fusion: ACTIVE (ev_pos, ev_vel, ev_yaw flags SET)
# EV Position Innovation: mean=0.02m, max=0.15m
# EV Delay estimate: 12ms (EKF2_EV_DELAY=10, consider increasing)
# 
# --- Fake GPS ---
# GPS Fusion: ACTIVE (gps_pos, gps_vel, gps_hgt flags SET)
# GPS Innovation: mean=0.03m, within 3-sigma
# Global Position Valid: YES (Mission/RTL capable)
# 
# --- Flight Modes ---
# Position: 320s (71%)
# Offboard: 85s (19%)
# Auto (Mission): 47s (10%)
# 
# --- Silvus Link Quality ---
# Avg RSSI: -62 dBm
# Avg Packet Loss: 0.8%
# Avg RTT: 4.2 ms
# Degradation events: 0
# 
# --- Obstacle Avoidance ---
# Planner cycles: 4200
# Avg cycle time: 67ms (max: 145ms)
# Avoidance triggers: 3 (all successful stops)
# Min obstacle distance: 0.72m (threshold: 0.5m)
# 
# --- Battery ---
# Start: 16.2V, End: 14.8V
# Min voltage: 14.5V
# Current avg: 12.3A
# 
# --- Events ---
# [00:12] Takeoff
# [03:45] Mode: Position -> Offboard
# [04:12] Mission started
# [07:30] RTL triggered
# [07:55] Landing
# 
# ============================================================
# Overall Assessment: PASS
# Recommendations:
#   - Consider increasing EKF2_EV_DELAY to 15ms (innovation min at 12ms)
#   - VIO drift after 5min: implement periodic origin reset
# ============================================================
```

### 4.2 분석 결과 DB 저장
```bash
# analyze_log.py가 자동으로 analysis_results 테이블에 저장
# 확인:
sqlite3 flight_logs/db/flightlog.db "SELECT * FROM analysis_results WHERE flight_id='FLIGHT_20261104_001';"
```

---

## 📋 Phase 5: 트렌드 분석 및 파라미터 튜닝 피드백

### 5.1 다중 비행 비교 분석
```bash
python3 << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db/flightlog.db')

# EKF2 혁신 트렌드 (최근 10회 비행)
query = """
SELECT f.flight_id, f.start_time_utc,
       AVG(ABS(pos_innov_n)) as avg_pos_innov_n,
       AVG(ABS(pos_innov_e)) as avg_pos_innov_e,
       AVG(ABS(pos_innov_d)) as avg_pos_innov_d,
       MAX(ABS(pos_innov_n)) as max_pos_innov_n,
       MAX(ABS(pos_innov_e)) as max_pos_innov_e,
       MAX(ABS(pos_innov_d)) as max_pos_innov_d
FROM ekf2_innovations e
JOIN flights f ON e.flight_id = f.flight_id
WHERE f.start_time_utc > date('now', '-30 days')
GROUP BY f.flight_id
ORDER BY f.start_time_utc DESC
LIMIT 10
"""

df = pd.read_sql_query(query, conn)
print(df.to_string(index=False))

# 트렌드: 혁신 값이 증가하면 센서 열화 또는 파라미터 재튜닝 필요
conn.close()
EOF
```

### 5.2 파라미터 튜닝 피드백 루프
```bash
# 분석 결과 기반 파라미터 변경 권장사항 자동 생성
python3 << 'EOF'
# px4_params/CHANGELOG.md 자동 업데이트 예시
changelog_entry = """
## 2026-11-04: Post-flight Analysis - FLIGHT_20261104_001

### EKF2 Tuning
- EKF2_EV_DELAY: 10 → 15ms (innovation minimum at 12ms measured)
- EKF2_EVP_NOISE: 0.1 → 0.15 (VIO covariance underestimated)

### VIO Drift Mitigation
- Added periodic origin reset trigger (drift > 2m or 5min)
- Fake GPS fix_type reduced to 2 (2D) when drift detected

### Obstacle Avoidance
- TEB weight_obstacle: 50 → 80 (more aggressive avoidance)
- Inflation distance: 0.8 → 1.0m (larger safety margin)

### Silvus Link Quality
- Packet loss threshold: 10% → 5% (earlier degradation detection)
- COM_OF_LOSS_T: 1.0 → 0.5s (faster OFFBOARD exit on link loss)

### Test Results
- Flight: FLIGHT_20261104_001 (7.5 min indoor)
- EKF2 innovation 3-sigma violation: 1.2% (target < 5%) ✅
- VIO drift: 0.8m over 5min (acceptable with origin reset)
- Mission/RTL: 100% success (3 waypoints, RTL accuracy 0.3m)
- Obstacle avoidance: 3/3 successful stops
"""

print(changelog_entry)
EOF
```

---

## 📋 Phase 6: 아카이브 및 문서화

### 6.1 비행 로그 아카이브 구조
```
/Users/amaster/projectm/Q250-V3-Opti/flight_logs/
├── raw/                    # 원본 파일 (immutable, SHA-256 기록)
│   └── FLIGHT_YYYYMMDD_XXX/
│       ├── meta.yaml
│       ├── SHA256SUMS.txt
│       ├── *.ulg
│       ├── *.pcap
│       ├── *.txt
│       ├── *.csv
│       └── rosbag_*/
├── db/                     # SQLite DB (파싱된 구조화 데이터)
│   ├── flightlog.db
│   └── FLIGHT_XXX_alignment.json
├── processed/              # 파싱 중간 결과 (JSON, CSV)
│   └── FLIGHT_XXX/
└── reports/                # 분석 리포트 (HTML/Markdown)
    └── FLIGHT_XXX_report.md
```

### 6.2 정기 백업 및 정리
```bash
# 주간 백업 (자동화 권장)
tar -czf flight_logs_backup_$(date +%Y%m%d).tar.gz flight_logs/

# 월간 정리: 90일 이상 된 raw 데이터는 cold storage로 이동
find flight_logs/raw -type d -mtime +90 -exec mv {} /archive/cold_storage/ \;
```

---

## 🚨 트러블슈팅

| 문제 | 원인 | 해결 |
|------|------|------|
| ulog 파싱 실패 | pyulog 버전 불일치 | `pip install --upgrade pyulog` |
| MAVLink PCAP 파싱 안 됨 | dpkt/pymavlink 버전 | `pip install --upgrade dpkt pymavlink` |
| 시간 정렬 안 됨 | TIMESYNC 메시지 없음 | MAVLink 텍스트 로그에서 수동 동기화 포인트 추가 |
| DB 용량 과다 | 인덱스 과다, 오래된 데이터 | `VACUUM`, 파티셔닝, 90일 이상 아카이브 |
| 분석 리포트 생성 느림 | 대용량 데이터 풀스캔 | 인덱스 확인, 시간 범위 제한 쿼리 사용 |

---

## 📚 참고 문서

| 문서 | 위치 |
|------|------|
| 통합 어댑터 API | `integration/__init__.py` |
| Flight Log Adapter | `integration/flightlog_adapter.py` |
| MAVLink Adapter | `integration/mavlink_adapter.py` |
| Time Aligner | `integration/align.py` |
| SQL 스키마 | `references/flightlog-schema.sql` |
| DB 초기화 | `scripts/init_flightlog_db.py` |
| 분석 스크립트 | `scripts/postflight/analyze_log.py` |
| 학습 로드맵 | `docs/learning-roadmap.md` (9단계) |

---

*작성: 2026-11-04 | 기반: integration/ 어댑터, references/flightlog-schema.sql*