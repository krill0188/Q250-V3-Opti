# EKF2 튜닝 가이드 (강좌 5편: 실내 자율비행 미션 기반)

## 실내 Position Mode 필수 파라미터 (config/px4/q250-v3-opti_v1.15_baseline.params 에 반영)

### Optical-Flow & LiDAR 활성화
```bash
# Optical-Flow
EKF2_OF_CTRL=1          # Optical Flow 융합 ON
SENS_FLOW_ROT=0         # 센서 회전 없음 (전방 장착)
EKF2_OF_POS_X=0.0       # Flow 센터 X 오프셋 (COG 기준, m)
EKF2_OF_POS_Y=0.0       # Flow 센터 Y 오프셋
EKF2_OF_POS_Z=-0.035    # Flow 센터 Z 오프셋 (아래로 -)

# LiDAR (Range Finder)
EKF2_RNG_CTRL=2         # Range height fusion (연속 모드)
EKF2_HGT_REF=2          # 고도 기준 = Range sensor
EKF2_RNG_POS_X=0.0      # LiDAR X 오프셋
EKF2_RNG_POS_Y=0.0      # LiDAR Y 오프셋
EKF2_RNG_POS_Z=-0.040   # LiDAR Z 오프셋
EKF2_RNG_NOISE=0.02     # LiDAR 노이즈 (m, 데이터시트 2% 반영)

# GPS/나침반 비활성화 (실내)
EKF2_GPS_CTRL=0         # GPS 완전 비활성화
EKF2_MAG_TYPE=5         # 나침반 비활성화 (실내 자기장 간섭 회피)
EKF2_AID_MASK=200       # Bit 3(OF)+6(EV yaw)+7(RNG) = 8+64+128
```

### EKF2 고급 튜닝 (시뮬 → 실기체 검증 후 조정)

#### Optical-Flow 품질/노이즈
```bash
EKF2_OF_QMIN=100        # 최소 품질 임계값 (0~255, 실내 조도 >100 Lux면 100~150)
EKF2_OF_NEIG_NR=3       # 노이즈 게이트 이웃 수
EKF2_OF_SCALE=1.0       # 스케일 팩터 (실측 후 조정)
```

#### LiDAR 노이즈/아웃라이어 처리
```bash
EKF2_RNG_NOISE=0.02     # 기본 0.02m (2cm), 실측 노이즈 보고 조정
EKF2_RNG_SFE=0.1        # 스케일 팩터 오차
EKF2_RNG_NOISE_SCALE=1.0
```

#### 높이 추정 모드
```bash
EKF2_HGT_REF=2          # 2 = Range sensor (LiDAR 기준)
EKF2_RNG_CTRL=2         # 2 = Continuous fusion
# 조건부 퓨전 원할 시:
# EKF2_RNG_CTRL=1       # Conditional (저속/저고도만)
```

#### 드래그/바이아스 추정
```bash
EKF2_DRAG_CTRL=3        # 드래그 모델 활성화 (XY)
EKF2_DRAG_NOISE=0.5
EKF2_BCN_CTRL=0         # 비콘 비활성화
EKF2_FUSE_BETA=1        # 합성 측면미끄럼각 융합
```

#### 그라운드 이펙트 (이착륙 시)
```bash
EKF2_GND_EFF_DZ=0.1     # 데드존
EKF2_GND_EFF_MAX_HGT=0.5
EKF2_GND_MAX_HGT=1.0
```

---

## 튜닝 절차 (시뮬 → 실기체)

### 1단계: 시뮬레이션에서 기본 검증
```bash
# Gazebo + PX4 SITL 실행
# QGC에서 실시간 EKF2 상태 모니터링:
# - EKF2 혁신(Innovation) 플롯 확인
# - Optical-Flow quality > 150 유지
# - LiDAR 거리 정확도 ±0.02m
# - XY 드리프트 < 0.05m (호버링 30초)
```

### 2단계: 실기체 벤치 테스트 (프롭 제거)
```bash
# QGC MAVLink Inspector로 센서 데이터 확인:
# - OPTICAL_FLOW_RAD: integrated_x/y 부호, quality > 150
# - DISTANCE_SENSOR: current_distance 정확도 ±0.02m
# - IMU: 바이어스 안정성
```

### 3단계: 실기체 실내 호버링 테스트
```bash
# Position Mode 호버링 30초
# 로그 다운로드 후 분석:
python3 scripts/postflight/analyze_log.py flight_log.ulg

# 합격 기준:
# - XY Position Std < 0.05m
# - Z Position Std < 0.03m
# - Flow Innovation RMS < 0.1 rad/s
# - Range Innovation RMS < 0.05m
```

### 4단계: 실패 시 튜닝 가이드

| 증상 | 원인 | 조정 파라미터 |
|------|------|---------------|
| **Position Mode 진입 안됨** | EKF2 수렴 실패 | EKF2_OF_CTRL=1, EKF2_RNG_CTRL=2, EKF2_HGT_REF=2 확인 |
| **이륙 후 XY 드리프트** | Flow 방향/오프셋 오류 | SENS_FLOW_ROT (90도 단위 테스트), EKF2_OF_POS_X/Y/Z |
| **고도 흔들림 (Z 지터)** | LiDAR 노이즈/장애물 | EKF2_RNG_NOISE ↑ (0.02→0.05), EKF2_RNG_CTRL=1(조건부) 시도 |
| **요(Yaw) 드리프트** | 자기장 간섭 | EKF2_MAG_TYPE=5 (나침반 OFF), EKF2_AID_MASK Bit 6(EV yaw) 활용 |
| **이륙 후 상승/하강 불안정** | 그라운드 이펙트 | EKF2_GND_EFF_DZ, EKF2_GND_MAX_HGT 조정 |

---

## 로그 분석 자동화 (scripts/postflight/analyze_log.py 활용)

```bash
# 비행 후 자동 분석
python3 scripts/postflight/analyze_log.py ~/flight_logs/20261102_143000/flight_log.ulg

# 출력 예시:
# === Position Stability ===
# X Std: 0.023 m
# Y Std: 0.018 m
# Z Std: 0.012 m
# === Optical Flow Innovation RMS: 0.045 rad/s ===
# === Range Finder Innovation RMS: 0.021 m ===
# === Motor Balance (hover avg) ===
# Motor 1: 0.452
# Motor 2: 0.448
# Motor 3: 0.455
# Motor 4: 0.450
# === Pass/Fail Criteria ===
# ✓ XY Position Std < 0.05m: PASS
# ✓ Z Position Std < 0.03m: PASS
# ✓ Motor Balance < 5%: PASS
```

---

## 실내 비행 환경 체크리스트 (강좌 5편 환경)

| 항목 | 기준 | 확인 방법 |
|------|------|-----------|
| **조도** | > 100 Lux (권장 > 300 Lux) | 룩스 미터 / 스마트폰 앱 |
| **바닥 텍스처** | 패턴 있음 (단색/반사면 금지) | 육안 확인, Optical-Flow quality > 150 |
| **바닥 평탄도** | 평평, 장애물 없음 | 육안 확인 |
| **공간 크기** | 최소 3m × 3m × 2.5m | 줄자 측정 |
| **기류** | 에어컨/선풍기 끄기 | 풍속계 또는 티슈 테스트 |
| **조명 균일성** | 그림자/플리커 없음 | 육안 확인 |
| **전파 환경** | 2.4GHz/5GHz 간섭 최소화 | WiFi 분석기 앱 |

---

## 실버스 데이터링크 연동 시 추가 고려사항

```bash
# 실버스 매쉬 지연 고려 (1홉 3-8ms, 2홉 8-15ms)
# EKF2 측정 지연 보정:
EKF2_OF_DELAY=5      # Optical-Flow 측정 지연 (ms)
EKF2_RNG_DELAY=5     # LiDAR 측정 지연 (ms)
EKF2_IMU_DELAY=2     # IMU 측정 지연 (ms)

# 실버스 패킷 손실 시 EKF2 예측 모드 유지 시간
EKF2_TIMEOUT=5000    # ms (5초간 측정 없으면 예측만)
```

---

## 다음 단계: 실외 GPS 비행으로 확장 시

```bash
# GPS 활성화
EKF2_GPS_CTRL=7       # GPS 수평/속도/고도 모두 사용
EKF2_MAG_TYPE=1       # 나침반 자동
EKF2_AID_MASK=328     # GPS + OF + RNG + EV yaw (필요시)

# RTK 사용 시
EKF2_GPS_CTRL=15      # RTK 고정도 모드
GPS_RTK_MODE=1
```

---

## 참고: EKF2_AID_MASK 비트맵 완전 해설

| 비트 | 값 | 의미 | 실내 기본 |
|------|-----|------|-----------|
| 0 | 1 | GPS 수평 위치 | 0 |
| 1 | 2 | GPS 속도 | 0 |
| 2 | 4 | GPS 고도 | 0 |
| 3 | 8 | **Optical Flow** | **1** |
| 4 | 16 | External Vision 위치 | 0 |
| 5 | 32 | External Vision 속도 | 0 |
| 6 | 64 | **External Vision Yaw** | **1** (EV 있거나 나침반 대체) |
| 7 | 128 | **Range Finder 고도** | **1** |
| 8 | 258 | 합성 측면미끄럼각 | 1 |
| 9 | 512 | 고정익 대기속도 | 0 |
| 10 | 1024 | 멀티콥터 드래그 | 1 |
| 11 | 2048 | External Vision 헤딩 | 0 |

**실내 기본 마스크**: 8 + 64 + 128 + 256 = **352** (EV yaw 없을 시 8+128=136)
※ 위 가이드의 200은 Bit 6 제외 버전. EV yaw 사용 시 352 권장.

---

## 강좌 5편 시청하면서 채울 튜닝 로그

| 테스트 | 날짜 | 파라미터 변경 | 결과 | 비고 |
|--------|------|---------------|------|------|
| 시뮬 호버링 |  |  |  |  |
| 벤치 테스트 |  |  |  |  |
| 실내 1차 비행 |  |  |  |  |
| 튜닝 1회 |  |  |  |  |
| 실내 2차 비행 |  |  |  |  |
| 튜닝 2회 |  |  |  |  |
| 실내 3차 비행 |  |  |  |  |

---
*최종 업데이트: 2026-11-02 (강좌 5편 기준)*
