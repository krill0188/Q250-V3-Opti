# Q250-V3-Opti: 음성인식 + Non-GPS + 다이브 통합 시스템

## 프로젝트 개요
Q250-V3-Opti 플랫폼에 **음성인식 + Non-GPS 내비게이션 + 고정익/FPV 다이브 어택** 기능을 통합한 자율비행 시스템 구축

## 핵심 요구사항

### 1. 음성인식 파이프라인 (Voice Recognition)
- **STT**: faster-whisper (로컬, 실시간)
- **NLU**: 로컬 LLM (llama.cpp) + 함수 호출
- **Fast-Path**: 비상정지/즉시착륙 즉시 처리 (LLM 우회)
- **다국어**: 한국어/영어 지원

### 2. Non-GPS 내비게이션 (Non-GPS Navigation)
- **Visual-Inertial Odometry (VIO)**: 카메라 + IMU 융합
- **Optical Flow**: 하향 카메라 기반 속도/자세 추정
- **LiDAR/Depth**: 장애물 회피 및 고도 유지
- **Sensor Fusion**: EKF 기반 다중 센서 융합

### 3. 다이브 어택 (Dive Attack) - 고정익 + FPV 하이브리드
- **모드**: CRUISE(고정익) ↔ FPV_AGILE(멀티콥터) ↔ DIVE_ATTACK
- **다이브 파라미터**: 80m/s, 80도, 최소 풀업 30m
- **기만 패턴**: SPIRAL_DIVE, SINE_DIVE, RANDOM_JINK, FAKE_CRASH, MULTI_PULSE
- **자동 풀업**: 지형/고도 기반 자동 회복

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Q250-V3-Opti 통합 시스템                    │
├─────────────────────────────────────────────────────────────┤
│  Voice Command Engine ←→ Mission Planner                    │
├─────────────────────────────────────────────────────────────┤
│  ModeManager (CRUISE/FPV_AGILE/DIVE_ATTACK/DECEPTION)       │
├──────────────┬──────────────────┬───────────────────────────┤
│ TrajectoryEng │ NonGPSNav        │  DeceptionEngine         │
│ (MPC/LUT/Geo) │ (VIO/OpticalFlow)│  (5 Patterns)            │
├──────────────┴──────────────────┴───────────────────────────┤
│         LocalLLMRiskAnalyzer (llama.cpp)                     │
├─────────────────────────────────────────────────────────────┤
│  Hardware Bridge: MAVSDK + MAVROS2 (Dual Control)           │
├─────────────────────────────────────────────────────────────┤
│  PX4 + Gazebo SITL / Real Hardware (Pixhawk 6C + Jetson)   │
└─────────────────────────────────────────────────────────────┘
```

## 하드웨어 스펙 (Q250-V3-Opti)

| 구성요소 | 사양 |
|---------|------|
| **FC** | Pixhawk 6C (STM32H7) |
| **Companion** | Jetson Orin Nano / Xavier NX |
| **Camera** | IMX219 (전방) + IMX219 (하향 Optical Flow) |
| **IMU** | ICM-42688-D (FC) + ICM-20948 (Companion) |
| **GPS** | u-blox F9P (RTK) + Non-GPS 백업 |
| **LiDAR** | TF-Luna (전방) + TFmini-S (하향) |
| **Motor** | T-Motor MN501-S KV300 (고정익) + MN4014 KV300 (FPV) |
| **ESC** | BLHeli_32 50A (DShot600) |
| **Battery** | 6S 22.2V 10000mAh (고정익) + 6S 5000mAh (FPV) |

## 안전 제약조건

| 제약 | 값 | 비고 |
|------|-----|------|
| 최대 다이브 속도 | 80 m/s | 구조 한계 |
| 최대 다이브 각도 | 80° | 구조 하중 고려 |
| 최소 풀업 고도 | 30 m | 지형 여유도 |
| 최대 기만 지속시간 | 60초 | 배터리/열 관리 |
| 최소 배터리 | 25% | RTL 강제 트리거 |
| 통신 두절 타임아웃 | 3초 | 자동 RTL/HOLD |

## 인터페이스 정의

### 음성 명령 인터페이스
```python
VoiceCommand:
  action: str          # TAKEOFF, LAND, DIVE_ATTACK, DECEPTION_START, SET_MODE
  params: dict         # target_alt, angle, pattern, duration
  confidence: float    # STT 신뢰도 (0.85 이상)
  target_id: str       # drone_1, drone_2
```

### Non-GPS 상태 인터페이스
```python
NonGPSState:
  position: Vector3    # x, y, z (로컬 NED)
  velocity: Vector3    # vx, vy, vz
  attitude: Quaternion # roll, pitch, yaw
  covariance: Matrix6x6 # 추정 불확실성
  source: str          # VIO, OPTICAL_FLOW, LIDAR, FUSED
```

### 다이브 궤적 인터페이스
```python
DiveTrajectory:
  waypoints: List[Vector3]
  velocities: List[Vector3]
  timestamps: List[float]
  method: Enum[MPC, LUT, GEOMETRIC]
  constraints_satisfied: bool
  pullup_trigger: float  # 고도 트리거
```

## 검증 기준 (Definition of Done)

| 모듈 | 검증 항목 | 통과 기준 |
|------|-----------|-----------|
| 음성인식 | STT 정확도 | > 95% (한국어) |
| 음성인식 | NLU 정확도 | > 90% (명령 매핑) |
| Non-GPS | 위치 오차 | < 1m (실내), < 3m (실외) |
| Non-GPS | 드리프트 | < 0.5m/min |
| 다이브 | 궤적 추종 | < 2m RMS 오차 |
| 다이브 | 풀업 정확도 | ±2m 목표 고도 |
| 기만 | 패턴 실행 | 100% 명령 수신 시 실행 |
| 안전 | 풀업 트리거 | 100% 고도 트리거 작동 |
| 통합 | E2E 레이턴시 | < 100ms (명령→실행) |

## 개발 단계 (SpecKit 7단계)

1. **SPECIFY** ✅ - 본 문서
2. **CLARIFY** - 모호성 해결 (다음 단계)
3. **PLAN** - 상세 아키텍처 및 모듈 설계
4. **TASKS** - 작업 분해 및 의존성
4. **ANALYZE** - 테스트 매트릭스 및 안전 게이트
5. **IMPLEMENT** - 모듈별 구현
6. **VERIFY** - 통합 테스트 및 안전 검증