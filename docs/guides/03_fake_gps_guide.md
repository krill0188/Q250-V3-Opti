# Q250-V3 Opti 실전 가이드: Fake GPS 구현 및 검증 (Step-by-Step)

> **목적**: VIO Local Position → GPS_INPUT MAVLink → PX4 Global Position으로 Mission/RTL/Geofence 활성화  
> **전제**: VIO→EKF2 연동 완료, Position 모드 안정 비행 가능  
> **예상 소요**: 2~3일 (노드 빌드 0.5일, 벤치 테스트 1일, 실내 비행 1일)  
> **핵심**: **원점(Datum) 고정 필수** - 비행 중 원점 변경 시 위치 점프 발생

---

## 📋 Phase 0: 사전 이해 및 아키텍처

### 0.1 왜 Fake GPS가 필요한가?

| 기능 | Global Position 필요? | Local Position만으로 가능? |
|------|----------------------|---------------------------|
| Position 모드 호버 | ❌ | ✅ |
| OFFBOARD 속도/위치 제어 | ❌ | ✅ |
| **Mission (웨이포인트 비행)** | ✅ | ❌ |
| **RTL (Return to Launch)** | ✅ | ❌ |
| **Geofence (GF_ACTION)** | ✅ | ❌ |

### 0.2 시스템 아키텍처

```
VIO Estimator (ROS 2)
      │
      ▼ (local pose: x, y, z, q in ENU)
fake_gps_node
      │
      ├─ Datum 설정 (lat₀, lon₀, alt₀)  ← 고정 또는 초기 자동 저장
      ├─ ENU → LLA 변환 (평탄 지구 근사)
      ├─ 품질 필드 생성 (fix_type=3, sats=10, accuracy=VIO cov 기반)
      └─ 타임스탬프 동기화 (PX4 시간 기준 us)
      │
      ▼ (GPS_INPUT MAVLink)
MAVROS /mavros/gps_input/input
      │
      ▼
PX4 GPS Module → EKF2 (GPS fusion 활성화)
      │
      ▼
Global Position Valid → Mission/RTL/Geofence 활성화
```

### 0.3 좌표 변환 공식 (ENU → LLA)

```python
# 평탄 지구 근사 (소규모 실내/실외 < 1km)
R = 6378137.0  # 지구 반경 (m)

def enu_to_lla(x_enu, y_enu, z_enu, lat0, lon0, alt0):
    dlat = y_enu / R * 180.0 / math.pi
    dlon = x_enu / (R * math.cos(math.radians(lat0))) * 180.0 / math.pi
    lat = lat0 + dlat
    lon = lon0 + dlon
    alt = alt0 + z_enu  # ENU z = Up, MSL 고도
    return lat, lon, alt
```

> **주의**: 정확한 변환이 필요하면 `pyproj` 또는 `GeographicLib` 사용 권장

---

## 📋 Phase 1: fake_gps 패키지 빌드 및 설정 (Day 1 오전)

### 1.1 패키지 빌드
```bash
cd /Users/amaster/projectm/Q250-V3-Opti/ros2_ws
colcon build --symlink-install --packages-select fake_gps
source install/setup.bash
```

### 1.2 설정 파일 확인 및 수정
```bash
# 설정 파일 위치
cat /Users/amaster/projectm/Q250-V3-Opti/ros2_ws/src/fake_gps/config/fake_gps.yaml

# 핵심 파라미터 (실제 이륙 위치로 변경 필수!):
# datum_lat: 37.5665    # 위도 (예: 서울시청)
# datum_lon: 126.9780   # 경도
# datum_alt: 28.0       # MSL 고도 (m)
# fix_type: 3           # 3=3D Fix, 5=RTK 시뮬레이션
# satellites_visible: 10
```

### 1.3 실전: 이륙 위치 원점 설정 방법 2가지

#### 방법 A: 고정 원점 (실내 테스트용)
```bash
# 실내 테스트장의 알려진 좌표 사용
# 예: 실내 비행장 중심점 GPS 좌표 미리 측정해 둠
datum_lat: 37.123456
datum_lon: 127.123456
datum_alt: 50.0  # MSL 고도
```

#### 방법 B: 동적 원점 저장 (실외→실내 전환 시 권장)
```bash
# 1. 실외에서 GPS 정상 수신 상태에서 이륙
# 2. MAVLink SET_GPS_GLOBAL_ORIGIN 자동 전송 구현
# 3. 실내 진입 시 해당 원점 기준으로 fake GPS 생성
# → 코드 수정 필요 (fake_gps_node에 origin 자동 저장 로직 추가)
```

---

## 📋 Phase 2: 벤치 테스트 (Day 1 오후)

### 2.1 MAVROS 실행 및 GPS_INPUT 토픽 확인
```bash
# 1. MAVROS 실행 (이미 실행 중이면 생략)
ros2 launch mavros px4.launch.py fcu_url:=/dev/ttyUSB0:921600

# 2. fake_gps 노드 실행
ros2 launch fake_gps fake_gps.launch.py \
  datum_lat:=37.123456 \
  datum_lon:=127.123456 \
  datum_alt:=50.0 \
  vio_pose_topic:=/ov_msckf/pose

# 3. GPS_INPUT 발행 확인 (별도 터미널)
ros2 topic hz /mavros/gps_input/input
# 출력 예: average rate: 10.0 Hz

ros2 topic echo /mavros/gps_input/input --once
# 출력 예:
# header: {frame_id: "gps", stamp: {sec: 1234567890}}
# time_usec: 1234567890123
# fix_type: 3
# lat: 3712345600  (deg * 1e7)
# lon: 12712345600
# alt: 50000       (mm)
# horiz_accuracy: 0.5
# vert_accuracy: 0.5
# satellites_visible: 10
```

### 2.2 QGroundControl에서 GPS 상태 확인
```bash
# QGC 열기 → Fly View → GPS 위젯 확인:
# □ GPS: 3D Fix (초록색)
# □ 위성 수: 10개
# □ HDOP: ~1.0
# □ 위도/경도/고도: datum 값과 일치
# □ Map 탭: 기체 아이콘이 datum 위치에 표시
```

### 2.3 PX4 EKF2 혁신 모니터링
```bash
# MAVLink Console에서:
ekf2 innovation

# GPS 혁신 확인:
# gps_innov[0~2]: Position innovation (m)
# gps_innov[3~5]: Velocity innovation (m/s)
# 모두 ±3σ 내 유지되어야 함

# Estimator Status 확인:
# gps_pos, gps_vel, gps_hgt 플래그 모두 SET
```

**✅ Phase 2 완료 기준**:
- GPS_INPUT 10Hz 안정 발행
- QGC에서 GPS 3D Fix, Map에 기체 표시
- EKF2 GPS 혁신 ±3σ, GPS 플래그 모두 SET

---

## 📋 Phase 3: PX4 파라미터 설정 (Day 2 오전)

### 3.1 Fake GPS용 EKF2 파라미터
```bash
# QGC Parameters에서 설정 후 Write → Reboot

# GPS 융합 활성화 (fake GPS를 주 위치 소스로)
EKF2_GPS_CTRL   7       # 비트 0,1,2 = Pos+Vel+Hgt 모두 융합
EKF2_GPS_CHECK  31      # 품질 체크 완화 (비트 0~4)
EKF2_GPS_P_NOISE 0.5    # GPS 위치 노이즈 (m)
EKF2_GPS_V_NOISE 0.5    # GPS 속도 노이즈 (m/s)

# External Vision은 보조로 유지
EKF2_EV_CTRL    15
EKF2_AID_MASK   352     # OF + Range + EV Yaw + GPS

# Mag 비활성화 (실내)
EKF2_MAG_TYPE   5
```

### 3.2 파라미터 적용 확인
```bash
# 재부팅 후 QGC에서:
# □ EKF2_GPS_CTRL = 7
# □ GPS 탭: 위성 10, HDOP 1.0, 3D Fix
# □ Estimator Status: gps_pos, gps_vel, gps_hgt 모두 초록
```

---

## 📋 Phase 4: Mission/RTL/Geofence 테스트 (Day 2 오후)

### 4.1 SITL 시뮬레이션 먼저 (권장)
```bash
# 개발 PC에서 SITL로 먼저 테스트
cd ~/PX4-Autopilot
make px4_sitl gz_q250_v3_opti

# 별도 터미널에서 fake_gps + MAVROS 실행 후
# QGC에서 Mission 생성 → AUTO 모드 테스트
```

### 4.2 실기체 Mission 테스트 (무프로펠러 → 프로펠러)

#### Step 1: 무프로펠러 Position 모드에서 Global Position 확인
```bash
# 1. 프로펠러 제거
# 2. Position 모드 진입
# 3. QGC Map에서 기체 위치가 VIO 궤적과 일치하는지 확인
# 4. 수동 조종으로 이동 → Map 궤적 실시간 추적 확인
```

#### Step 2: Mission 업로드 및 실행
```bash
# QGC Plan 탭:
# 1. 웨이포인트 3~4개 생성 (이륙점 반경 2~3m 내)
# 2. 고도: 1.0m (실내 안전 고도)
# 3. Upload → 기체에 미션 전송

# Flight 탭:
# 1. AUTO 모드 전환
# 2. Mission 시작 → 자동 비행
# 3. 웨이포인트 통과 확인
```

#### Step 3: RTL 테스트
```bash
# 1. Mission 중이거나 Position 모드에서
# 2. RC에서 RTL 스위치 또는 QGC RTL 버튼
# 3. 기체가 datum 원점(이륙점)으로 복귀 → 착륙 확인
# 4. 복귀 궤적 Map에서 확인
```

#### Step 4: Geofence 테스트
```bash
# QGC에서 Geofence 설정:
# 1. 원점 반경 5m 원형 펜스 생성
# 2. GF_ACTION = 1 (RTL)
# 3. 비행 중 펜스 밖으로 유도 → 자동 RTL 동작 확인
```

---

## 📋 Phase 5: 실내 비행 검증 (Day 3)

### 5.1 안전 준비
- [ ] 네트/패딩 설치
- [ ] 비상정지 버튼 작동 확인
- [ ] 배터리 100%
- [ ] 관측자 배치 (RC 수동 오버라이드)

### 5.2 비행 시나리오

| 단계 | 시나리오 | 성공 기준 |
|------|----------|-----------|
| 5.1 | 이륙 → 1m 호버 (Position) | Global Position Valid, Map 궤적 일치 |
| 5.2 | Mission 업로드 → AUTO 실행 | 웨이포인트 3개 모두 통과, ±0.5m 정확도 |
| 5.3 | RTL 버튼 테스트 | 원점 복귀 ±0.5m, 자동 착륙 |
| 5.4 | Geofence 위반 유도 | 경계 이탈 시 즉시 RTL 모드 전환 |
| 5.5 | VIO 드리프트 시 Global Position 영향 확인 | 드리프트 < 0.5m/분 시 수용 가능 |

### 5.3 드리프트 모니터링 및 대응
```bash
# fake GPS는 VIO 드리프트를 그대로 Global Position에 반영
# 장시간 비행 시 드리프트 누적 → Mission 정확도 저하

# 대응 방안:
# 1. 주기적 원점 재보정 (알려진 랜드마크에서 SET_GPS_GLOBAL_ORIGIN 재전송)
# 2. VIO 루프 클로저 구현 (RTAB-Map 등)
# 3. drift > 임계값(2m) 시 fake GPS 중단 경고

# fake_gps_node에 drift 감지 로직 추가 권장:
# if position_change_rate > 0.1 m/s for 30s:
#     publish warning, reduce fix_type to 2 (2D)
```

---

## 🚨 트러블슈팅 퀵 레퍼런스

| 증상 | 원인 | 해결 |
|------|------|------|
| GPS: No Fix | `fix_type` 미설정, 토픽 미발행 | `fix_type=3`, 토픽 10Hz 확인 |
| Global Position 안 뜸 | `EKF2_GPS_CTRL=0`, 위성 수 부족 | `EKF2_GPS_CTRL=7`, `satellites_visible>=5` |
| Mission 시작 안 함 | Global Position Valid 안 뜸 | GPS 혁신 ±3σ, 플래그 확인 |
| 위치 점프 | Datum 변경, 변환 오류 | Datum 고정, 변환 공식 검증 |
| EKF2 GPS 거부 | `horiz_accuracy` 너무 큼 | VIO cov 기반 accuracy 계산, `EKF2_GPS_CHECK` 완화 |
| RTL 시 엉뚱한 곳 감 | 원점 ≠ 실제 이륙점 | 이륙 시 `SET_GPS_GLOBAL_ORIGIN` 자동 전송 구현 |

---

## 📝 운영 체크리스트 (비행 전 필수)

```bash
# Pre-flight Fake GPS Checklist
□ datum_lat/lon/alt 실제 이륙 위치와 일치
□ VIO 포즈 토픽 (/ov_msckf/pose) 30Hz 안정
□ fake_gps_node 실행 중, /mavros/gps_input/input 10Hz 발행
□ QGC: GPS 3D Fix, 위성 10, HDOP ~1.0
□ QGC Map: 기체 아이콘 올바른 위치
□ EKF2: GPS 혁신 ±3σ, gps_pos/vel/hgt 플래그 SET
□ EKF2_GPS_CTRL=7, EKF2_GPS_CHECK=31
□ Mission 웨이포인트 datum 반경 5m 내 생성
□ Geofence 반경 10m, GF_ACTION=1 (RTL)
□ 비상시: RC 수동 모드 즉시 전환 가능
```

---

## 📚 참고 문서 및 코드

| 항목 | 위치 |
|------|------|
| Fake GPS 상세 설계 | `docs/13-fake-gps-implementation.md` |
| ROS 2 노드 코드 | `ros2_ws/src/fake_gps/fake_gps/fake_gps_node.py` |
| Launch 파일 | `ros2_ws/src/fake_gps/launch/fake_gps.launch.py` |
| 설정 파일 | `ros2_ws/src/fake_gps/config/fake_gps.yaml` |
| VIO→EKF2 연동 (선행) | `docs/guides/01_vio_ekf2_integration_guide.md` |
| 학습 로드맵 | `docs/learning-roadmap.md` (6단계) |

---

*작성: 2026-11-04 | 기반: docs/13-fake-gps-implementation.md*