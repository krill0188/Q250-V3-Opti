# Q250-V3-Opti: 상세 구현 계획 (PLAN)

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Q250-V3-Opti 통합 시스템                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │  Voice STT  │    │   Voice NLU │    │ Voice Fast  │                │
│  │ (faster-    │───▶│  (llama.cpp)│───▶│  Path       │                │
│  │  whisper)   │    │             │    │ (Emergency) │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│       │                │                │                             │
│       ▼                ▼                ▼                             │
│  ┌─────────────────────────────────────────────────────┐             │
│  │              Mission Planner / Commander              │             │
│  │  (음성→명령 변환, 우선순위 관리, 미션 시퀀싱)          │             │
│  └─────────────────────────────────────────────────────┘             │
│                           │                                          │
│          ┌────────────────┼────────────────┐                        │
│          ▼                ▼                ▼                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ ModeManager │  │RiskAwareArb │  │NonGPSFusion │                 │
│  │ (FSM 5-state)│  │ (Priority+  │  │ (EKF2+VIO/  │                 │
│  │ CRUISE/     │  │  Risk Gate) │  │ OpticalFlow)│                 │
│  │ FPV/DIVE/   │  │             │  │             │                 │
│  │ DECEPTION)  │  │             │  │             │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │               │               │                            │
│         ▼               ▼               ▼                            │
│  ┌─────────────────────────────────────────────────────┐             │
│  │              Hardware Bridge Layer                    │             │
│  │  MAVSDK (Mission) + MAVROS2 (Velocity) + MAVLink    │             │
│  └─────────────────────────────────────────────────────┘             │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────┐             │
│  │  PX4 Firmware + Sensors (Pixhawk 6C + Jetson Orin)    │             │
│  └─────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

## 모듈 상세 설계

### 1. Voice Command Engine (`voice/`)
```
voice/
├── stt/
│   ├── faster_whisper_stt.py     # faster-whisper 래퍼
│   ├── audio_capture.py          # 실시간 오디오 캡처 (PyAudio)
│   └── vad.py                    # 음성 활동 감지 (Silero VAD)
├── nlu/
│   ├── llama_nlu.py              # llama.cpp 함수 호출 NLU
│   ├── intent_parser.py          # 의도 파싱 및 검증
│   └── fast_path.py              # 비상/즉시착륙 Fast-Path
├── commander.py                  # 미션 플래너 통합
└── audio_feedback.py             # TTS 피드백 (Edge-TTS)
```

### 2. Non-GPS Fusion (`nongps/`)
```
nongps/
├── vio/
│   ├── orb_slam3_wrapper.py      # ORB-SLAM3 Python 바인딩
│   ├── feature_tracker.py        # ORB 특징점 추적
│   └── pose_estimator.py         # 자세 추정 (PnP)
├── optical_flow/
│   ├── flow_processor.py         # OpenCV Farneback/Lucas-Kanade
│   ├── velocity_estimator.py     # 속도 추정 (픽셀→m/s)
│   └── quality_monitor.py        # 흐름 품질 평가
├── lidar/
│   ├── tf_luna_driver.py         # TF-Luna UART 드라이버
│   ├── tf_mini_driver.py         # TFmini-S I2C 드라이버
│   └── obstacle_mapper.py        # 장애물 맵 생성
├── fusion/
│   ├── ekf2_interface.py         # PX4 EKF2 MAVLink 인터페이스
│   ├── external_measurement.py   # 외부 측정값 주입 (비전/라이더)
│   ├── covariance_manager.py     # 공분산 행렬 관리
│   └── health_monitor.py         # 센서 건강도 모니터링
└── state_estimator.py            # 통합 상태 추정기 (위치/속도/자세)
```

### 3. Dive Attack System (`dive/`)
```
dive/
├── trajectory/
│   ├── mpc_optimizer.py          # MPC 궤적 최적화 (CVXPY)
│   ├── lut_generator.py          # LUT 사전 계산 및 캐시
│   ├── geometric_fallback.py     # 기하학적 폴백 궤적
│   └── constraint_checker.py     # 제약조건 검증 (속도/각도/고도)
├── patterns/
│   ├── spiral_dive.py            # SPIRAL_DIVE (IR 기만)
│   ├── sine_dive.py              # SINE_DIVE (도플러 레이더)
│   ├── random_jink.py            # RANDOM_JINK (예측 필터)
│   ├── fake_crash.py             # FAKE_CRASH (광학/IR)
│   └── multi_pulse.py            # MULTI_PULSE (멀티 센서)
├── pullup/
│   ├── terrain_aware.py          # 지형 인식 풀업 (DEM 활용)
│   ├── altitude_trigger.py       # 고도 트리거 (라이다/GPS)
│   └── auto_recovery.py          # 자동 회복 궤적
└── dive_controller.py            # 다이브 상태 머신 + 실행기
```

### 4. Deception Engine (`deception/`)
```
deception/
├── pattern_selector.py           # 위협 유형→패턴 매핑 + 점수 기반 선택
├── threat_assessor.py            # 센서 기반 위협 평가 (IR/Radar/Optical)
├── effect_model.py               # 기만 효과 시뮬레이션 (확률적)
├── executor.py                   # 패턴 실행기 (타이밍/시퀀싱)
└── coordinator.py                # 다중 기만 시퀀스 조정
```

### 5. Risk & Safety (`safety/`)
```
safety/
├── risk_analyzer.py              # Local LLM 위험 분석 (llama.cpp)
├── risk_arbitrator.py            # 위험 게이트 + 우선순위 중재
├── safety_validator.py           # 동적 안전 검증 (고도/속도/배터리)
├── emergency_handler.py          # 비상 상황 핸들러 (ESTOP/RTL)
└── watchdog.py                   # 통신/센서 워치독 (3초 타임아웃)
```

### 5. Hardware Bridge (`bridge/`)
```
bridge/
├── mavsdk_bridge.py              # MAVSDK 고수준 미션 제어
├── mavros2_bridge.py             # MAVROS2 속도/자세 제어
├── mavlink_custom.py             # 커스텀 MAVLink 메시지 (30000-30004)
├── sensor_bridge.py              # 센서 데이터 브릿지 (ROS2 ↔ MAVLink)
└── bridge_coordinator.py         # 듀얼 제어 조정기 (선점/해제)
```

### 6. Mode Manager (`mode/`)
```
mode/
├── fsm.py                        # 5-state FSM (CRUISE/FPV/DIVE/DECEPTION/TRANSITION)
├── transition_guard.py           # 전환 조건 가드 (자동/수동/비상)
├── auto_transition.py            # 자동 전환 조건 평가
└── mode_executor.py              # 모드별 실행기 연동
```

---

## 데이터 플로우

### 음성 명령 플로우
```
Audio (16kHz) → VAD → faster-whisper → 텍스트
                                    ↓
                            Fast-Path? (비상/착륙)
                                    ↓ Yes          No
                            FAILSAFE_ESTOP      llama.cpp NLU
                                    ↓                   ↓
                            즉시 실행          구조화된 명령
                                                      ↓
                                              Mission Planner
                                                      ↓
                                              RiskAwareArbitrator
                                                      ↓
                                              Hardware Bridge
```

### Non-GPS 융합 플로우
```
IMU (100Hz) ──▶ EKF2 예측
                      │
Camera (30Hz) ──▶ VIO ──▶ 위치/자세 측정 ──▶ EKF2 업데이트
                      │
Optical Flow (50Hz) ──▶ 속도 측정 ──────────▶ EKF2 업데이트
                      │
LiDAR (20Hz) ───────▶ 고도/장애물 ─────────▶ EKF2 업데이트
                      │
GPS (5Hz) ──────────▶ 절대 위치 ───────────▶ EKF2 업데이트 (가용시)
                      │
                      ▼
            통합 상태 추정 (위치/속도/자세 + 공분산)
                      │
                      ▼
            PX4 EKF2 외부 측정값 주입 (MAVLink VISION_POSITION_ESTIMATE)
```

### 다이브 어택 플로우
```
DIVE_ATTACK 명령
      │
      ▼
ModeManager: DIVE_ATTACK 모드 전환
      │
      ▼
TrajectoryEngine.generate_dive_trajectory()
  ├─ MPC (실시간 최적화)
  ├─ LUT (캐시 히트시 즉시)
  └─ Geometric (폴백)
      │
      ▼
DiveController 실행
  ├─ MAVSDK: 미션 업로드
  ├─ MAVROS2: 속도/자세 제어
  ├─ 풀업 트리거 모니터링 (라이다/고도)
      │
      ▼
풀업 트리거 발생
      │
      ▼
AutoPullup 실행 → CRUISE 모드 복귀
```

---

## 모듈 간 인터페이스 (ROS2 토픽 / MAVLink)

### ROS2 토픽
| 토픽 | 타입 | 발행자 | 구독자 | 주기 |
|------|------|--------|--------|------|
| `/voice/stt_result` | `std_msgs/String` | STT | NLU | 이벤트 |
| `/voice/command` | `custom_msgs/VoiceCommand` | NLU | Commander | 이벤트 |
| `/nongps/state` | `custom_msgs/NonGPSState` | Fusion | ModeManager/Controller | 10Hz |
| `/dive/trajectory` | `custom_msgs/DiveTrajectory` | TrajectoryEng | DiveController | 이벤트 |
| `/deception/cmd` | `custom_msgs/DeceptionCmd` | Commander | DeceptionEng | 이벤트 |
| `/risk/assessment` | `custom_msgs/RiskAssessment` | RiskAnalyzer | RiskArbitrator | 2Hz |
| `/mode/current` | `std_msgs/String` | ModeManager | All | 이벤트 |
| `/bridge/mavlink_tx` | `mavros_msgs/Mavlink` | Bridge | MAVROS2 | 50Hz |
| `/bridge/mavlink_rx` | `mavros_msgs/Mavlink` | MAVROS2 | Bridge | 50Hz |

### MAVLink 커스텀 메시지 (30000-30004)
| ID | 메시지 | 필드 | 방향 |
|----|--------|------|------|
| 30000 | VOICE_COMMAND | action, params, confidence, target | GCS→Drone |
| 30001 | NON_GPS_STATE | pos, vel, att, cov, source | Drone→GCS |
| 30002 | DIVE_TRAJECTORY | waypoints, velocities, timestamps | GCS→Drone |
| 30003 | DECEPTION_CMD | pattern, duration, params | GCS→Drone |
| 30004 | RISK_ASSESSMENT | level, categories, actions, auto_exec | Drone→GCS |

---

## 개발 우선순위 및 의존성

```
Phase 1: 기반 인프라 (1-2주)
├── 1.1 ROS2 워크스페이스 설정 + 커스텀 메시지
├── 1.2 MAVLink 커스텀 메시지 생성 (mavgen)
├── 1.3 PX4 EKF2 외부 측정 인터페이스 검증
├── 1.4 MAVSDK + MAVROS2 듀얼 브릿지 구축
└── 1.5 시뮬레이션 환경 (Gazebo + PX4 SITL)

Phase 2: 음성인식 파이프라인 (2주)
├── 2.1 faster-whisper STT + VAD 통합
├── 2.2 llama.cpp NLU + 함수 호출 구현
├── 2.3 Fast-Path 비상 명령 구현
├── 2.4 Mission Planner + Commander 통합
└── 2.5 음성→명령 E2E 테스트 (SITL)

Phase 3: Non-GPS 융합 (3-4주)
├── 3.1 VIO 파이프라인 (ORB-SLAM3 / OpenVINS)
├── 3.2 Optical Flow 속도 추정 (OpenCV)
├── 3.3 LiDAR 드라이버 + 장애물 맵핑
├── 3.4 EKF2 외부 측정 인터페이스 구현
├── 3.5 센서 융합 + 공분산 관리
└── 3.6 Non-GPS 상태 추정 검증 (실내/실외)

Phase 4: 다이브 어택 시스템 (3주)
├── 4.1 궤적 엔진 (MPC/LUT/Geometric)
├── 4.2 5종 기만 패턴 구현
├── 4.3 풀업 트리거 + 자동 회복
├── 4.4 다이브 상태 머신 + 실행기
└── 4.7 다이브 E2E 테스트 (SITL)

Phase 5: 기만 엔진 (2주)
├── 5.1 위협 평가기 (IR/Radar/Optical)
├── 5.2 패턴 선택기 (자동/수동)
├── 5.3 기만 효과 모델링
└── 5.4 기만 실행기 + 시퀀서

Phase 6: 위험 분석 + 안전 게이트 (2주)
├── 6.1 Local LLM 위험 분석 (llama.cpp Function Calling)
├── 6.2 위험 게이트 + 우선순위 중재
├── 6.3 동적 안전 검증기
├── 6.4 비상 핸들러 + 워치독
└── 6.5 안전 게이트 E2E 테스트

Phase 7: 통합 및 검증 (2주)
├── 7.1 전체 시스템 통합 (SITL)
├── 7.2 안전 게이트 종합 테스트
├── 7.3 실하드웨어 검증 (Pixhawk 6C + Jetson)
└── 7.4 문서화 + 릴리즈 v1.0
```

---

## 리소스 추정

| 리소스 | 예상 필요량 |
|--------|-------------|
| **개발 기간** | 약 14-16주 |
| **Jetson Orin Nano** | 1대 (개발용) + 1대 (탑재용) |
| **Pixhawk 6C** | 2대 (SITL용 + 실기용) |
| **Gazebo 시뮬레이션** | 1대 (고사양 GPU 서버) |
| **테스트 비행** | 실내 10회 + 실외 20회 |
| **데이터셋** | 실내 VIO 50분 + 실외 VIO 100분 |

---

## 위험 요소 및 대응

| 위험 | 확률 | 영향 | 대응 방안 |
|------|------|------|-----------|
| VIO 드리프트 실외에서 심함 | 높음 | 높음 | GPS 보정 + LiDAR 보조 + 다중 EKF |
| Jetson 발열로 쓰로틀링 | 중간 | 높음 | 히트싱크 + 팬 + 추론 간격 조절 |
| MAVSDK/MAVROS2 동시 제어 충돌 | 중간 | 높음 | 브릿지 코디네이터로 선점 관리 |
| Non-GPS 실내→실외 전환 불안정 | 높음 | 높음 | 센서 품질 기반 가중치 동적 조정 |
| 다이브 풀업 실패 | 낮음 | 치명적 | 다중 풀업 트리거 + 하드웨어 ESTOP |

---

## 다음 단계

**CLARIFY 완료** → **PLAN 수립 완료** → 다음은 **TASKS (작업 분해)** 진행