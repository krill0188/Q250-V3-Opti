# Q250-V3-Opti: 테스트 매트릭스 및 안전 게이트 (ANALYZE)

## 테스트 전략 개요

| 테스트 레벨 | 범위 | 도구 | 자동화 | 게이트 |
|-------------|------|------|--------|--------|
| **Unit** | 모듈 단위 함수/클래스 | pytest + mock | CI 필수 | 100% 통과 |
| **Integration** | 모듈 간 인터페이스 | pytest + ROS2 launch | CI 필수 | 100% 통과 |
| **SITL** | Gazebo + PX4 시뮬레이션 | pytest + ros2 launch | 야간 빌드 | 핵심 시나리오 100% |
| **Hardware** | 실기체 (Pixhawk + Jetson) | 수동 + 반자동 | 주 1회 | 핵심 시나리오 100% |
| **Flight** | 실외 비행 테스트 | 수동 | 마일스톤 | 비행 승인 후 |

---

## 안전 게이트 (Safety Gates) - 필수 통과

모든 PR/릴리즈는 다음 게이트 **전체 통과** 필수:

| 게이트 ID | 이름 | 설명 | 통과 기준 | 자동화 |
|-----------|------|------|-----------|--------|
| **SG-01** | 고도/속도 제한 | 명령이 하드웨어 한계 초과 시 클램핑/차단 | 100% 차단/클램핑 | Unit + SITL |
| **SG-02** | 저신뢰도 음성 차단 | STT confidence < 0.85 시 명령 거부 | 100% 거부 | Unit + SITL |
| **SG-03** | 수동 조작 선점 | MANUAL_SW 활성 시 음성/자동 명령 즉시 취소 | 100% 선점 | SITL |
| **SG-04** | 비상 패스트패스 | "비상정지"/"즉시착륙" → LLM 우회 즉시 ESTOP | 레이턴시 < 10ms | Unit + SITL |
| **SG-05** | 배터리 임계치 보호 | 배터리 < 25% 시 강제 RTL | 100% 실행 | SITL + HW |
| **SG-06** | 통신 두절 보호 | MAVLink 하트비트 3초 타임아웃 → 자동 RTL/HOLD | 100% 감지 | SITL + HW |
| **SG-07** | CRITICAL 위험 차단 | RiskAnalyzer CRITICAL → 음성 차단 + 자동 RTL/ESTOP | 100% 차단/실행 | SITL |
| **SG-08** | 풀업 고도 보장 | 다이브 풀업 트리거 고도 ≥ 30m 보장 | 100% 준수 | SITL + HW |
| **SG-09** | 기만 동시 실행 방지 | 이미 활성 기만 시 새 기만 거부 | 100% 거부 | Unit + SITL |
| **SG-10** | 센서 장애 Graceful Degradation | 센서 장애 시 백업 센서 전환 + 경고 | 100% 감지/전환 | SITL + HW |

---

## 테스트 매트릭스 (모듈별)

### 1. 음성인식 파이프라인 (Phase 2)

| 테스트 ID | 시나리오 | 입력 | 기대 출력 | 우선순위 | 자동화 |
|-----------|----------|------|-----------|----------|--------|
| **VOICE-01** | 한국어 STT 정확도 | "드론 이륙해" | "드론 이륙해" (CER < 5%) | P0 | Unit |
| **VOICE-02** | 영어 STT 정확도 | "Take off drone" | "Take off drone" (WER < 5%) | P1 | Unit |
| **VOICE-03** | 노이즈 환경 STT | 프로펠러 소음 + 명령 | 정확한 텍스트 (CER < 10%) | P0 | SITL |
| **VOICE-04** | VAD 분할 | 연속 발화 "이륙해 고도 100" | 두 개 세그먼트 분할 | P1 | Unit |
| **VOICE-05** | NLU 명령 파싱 | "고도 100미터로 올라가" | `{"action":"MOVE_VEL","params":{"vz":1},"confidence":0.95}` | P0 | Unit |
| **VOICE-06** | NLU 파라미터 추출 | "다이브 각도 70도 속도 60" | `{"angle":70,"speed":60}` | P0 | Unit |
| **VOICE-07** | Fast-Path 비상정지 | "비상정지" (confidence 0.5) | `FAILSAFE_ESTOP` 즉시, LLM 미호출 | P0 | Unit+SITL |
| **VOICE-08** | Fast-Path 즉시착륙 | "즉시 착륙해" (confidence 0.6) | `FAILSAFE_ESTOP` + LAND | P0 | Unit+SITL |
| **VOICE-09** | 저신뢰도 차단 | "이륙" (confidence 0.6) | 거부 + "인식 신뢰도 부족" | P0 | Unit+SITL |
| **VOICE-10** | 다중 명령 시퀀스 | "이륙해, 고도 50, 다이브 시작" | 순차 미션 큐 등록 | P1 | SITL |
| **VOICE-10** | 웨이크 워드 감지 | "헤이 드론" + 명령 | STT 활성화 → 명령 처리 | P1 | SITL |
| **VOICE-11** | TTS 피드백 | 명령 수신 시 | "명령 받았습니다. 이륙합니다." 음성 출력 | P1 | SITL |
| **VOICE-12** | 노이즈 게이트 | 프로펠러 소음만 | STT 미실행 (무음 판정) | P1 | SITL |

### 2. Non-GPS 융합 (Phase 3)

| 테스트 ID | 시나리오 | 입력 | 기대 출력 | 우선순위 | 자동화 |
|-----------|----------|------|-----------|----------|--------|
| **NGPS-01** | VIO 실내 위치 추적 | 실내 비행 5분 | 드리프트 < 1m/분 | P0 | SITL |
| **NGPS-02** | VIO 실외 위치 추적 | 실외 비행 10분 | 드리프트 < 3m/분 (GPS 보정 시 < 0.5m) | P0 | SITL |
| **NGPS-03** | VIO 루프 클로저 | 루프 비행 후 복귀 | 자세/위치 보정 확인 | P1 | SITL |
| **NGPS-04** | Optical Flow 속도 | 저고도 호버링 | 속도 오차 < 0.1m/s | P0 | SITL |
| **NGPS-05** | Optical Flow 전진 비행 | 5m/s 전진 | 속도 벡터 오차 < 0.2m/s | P0 | SITL |
| **NGPS-06** | LiDAR 고도 정확도 | TFmini-S 하향 | 고도 오차 ±5cm | P0 | HW |
| **NGPS-07** | LiDAR 전방 거리 | TF-Luna 전방 | 거리 오차 ±2cm | P0 | HW |
| **NGPS-08** | EKF2 비전 위치 주입 | VISION_POSITION_ESTIMATE 10Hz | EKF2 위치 수렴 (<0.5m) | P0 | SITL |
| **NGPS-09** | EKF2 비전 속도 주입 | VISION_SPEED_ESTIMATE 10Hz | EKF2 속도 수렴 | P0 | SITL |
| **NGPS-10** | EKF2 라이다 고도 보정 | DISTANCE_SENSOR (하향) | EKF2 고도 보정 | P0 | SITL |
| **NGPS-11** | 센서 장애 - 카메라 가림 | VIO 중단 | Optical Flow + LiDAR로 전환, 드리프트 < 2m/분 | P0 | SITL |
| **NGPS-12** | 센서 장애 - Optical Flow 중단 | 저고도에서 플로우 중단 | VIO + LiDAR로 전환 | P0 | SITL |
| **NGPS-13** | GPS 차단 시뮬레이션 | GPS 신호 차단 | Non-GPS 단독 3분 자율 비행 | P0 | SITL |
| **NGPS-14** | GPS 복구 시 전환 | GPS 복구 후 | 매끄러운 전환 (점프 < 2m) | P1 | SITL |
| **NGPS-15** | 실내 자율 비행 E2E | GPS 없음, 10x10m | 이륙→웨이포인트 4개→착륙 성공 | P0 | SITL |
| **NGPS-16** | 실외 하이브리드 E2E | GPS+Non-GPS | GPS→Non-GPS→GPS 전환 무중단 | P0 | SITL+HW |

### 3. 다이브 어택 시스템 (Phase 4)

| 테스트 ID | 시나리오 | 입력 | 기대 출력 | 우선순위 | 자동화 |
|-----------|----------|------|-----------|----------|--------|
| **DIVE-01** | 기하학적 다이브 궤적 | 500m→100m, 70도, 60m/s | 11개 웨이포인트, 제약 만족 | P0 | Unit |
| **DIVE-02** | MPC 다이브 궤적 | 동일 조건 + 장애물 | 제약 만족 + 장애물 회피 | P0 | SITL |
| **DIVE-03** | LUT 캐시 히트 | 동일 파라미터 2회 호출 | 동일 객체 반환 (캐시 히트) | P1 | Unit |
| **DIVE-04** | SPIRAL_DIVE 궤적 | 50m 반경, 3턴, 10m/s 하강 | 51개 웨이포인트, 나선형 | P0 | Unit |
| **DIVE-05** | SINE_DIVE 궤적 | 20m 진폭, 0.5Hz, 15m/s 하강 | 사인파 궤적, 51개 웨이포인트 | P0 | Unit |
| **DIVE-06** | RANDOM_JINK 궤적 | 20m/s, 10m/s 하강 | 21개 웨이포인트, 랜덤 지그재그 | P0 | Unit |
| **DIVE-07** | FAKE_CRASH 궤적 | 급하강 + 수평 | 추락 위장 궤적 | P0 | Unit |
| **DIVE-07** | MULTI_PULSE 궤적 | 다중 펄스 패턴 | 복합 기만 궤적 | P0 | Unit |
| **DIVE-08** | 속도 클램핑 | 요청 100m/s > 제한 80m/s | 80m/s로 클램핑 | P0 | Unit |
| **DIVE-08** | 각도 클램핑 | 요청 85도 > 제한 80도 | 80도로 클램핑 | P0 | Unit |
| **DIVE-09** | 최소 풀업 고도 | 풀업 트리거 25m < 30m | 30m에서 강제 풀업 | P0 | SITL |
| **DIVE-09** | 풀업 트리거 - 라이다 | 라이다 고도 30m 도달 | 자동 풀업 궤적 실행 | P0 | SITL+HW |
| **DIVE-10** | 풀업 트리거 - 기압계 | 기압 고도 30m 도달 | 자동 풀업 궤적 실행 | P0 | SITL+HW |
| **DIVE-11** | 자동 풀업 실행 | 트리거 발생 | 풀업 궤적 → CRUISE 복귀 | P0 | SITL |
| **DIVE-12** | 다이브 상태 머신 | IDLE→ENTRY→EXECUTE→PULLUP→RECOVERY | 올바른 전이 | P0 | SITL |
| **DIVE-13** | 다이브 중 기만 실행 | 다이브 중 SPIRAL_DIVE 명령 | 동시 실행 → 풀업 후 복귀 | P1 | SITL |
| **DIVE-14** | 다이브 중 비상 중단 | 풀업 전 ESTOP 명령 | 즉시 중단 + 풀업 | P0 | SITL |
| **DIVE-15** | 다이브 실하드웨어 | 100m 고도, 45도 다이브 | 50m 풀업 성공 5회 | P0 | HW |

### 4. 기만 엔진 (Phase 5)

| 테스트 ID | 시나리오 | 입력 | 기대 출력 | 우선순위 | 자동화 |
|-----------|----------|------|-----------|----------|--------|
| **DECP-01** | IR 미사일 위협 → SPIRAL | IR 위협, 고신뢰도 | SPIRAL_DIVE 선택 | P0 | Unit |
| **DECP-02** | 레이더 위협 → SINE | 레이더 위협, 고신뢰도 | SINE_DIVE 선택 | P0 | Unit |
| **DECP-03** | 광학 위협 → FAKE_CRASH | 광학 위협, 고신뢰도 | FAKE_CRASH 선택 | P0 | Unit |
| **DECP-04** | 멀티 센서 → MULTI_PULSE | IR+레이더+광학 | MULTI_PULSE 선택 | P0 | Unit |
| **DECP-05** | 알 수 없는 위협 → RANDOM_JINK | 미분류 위협 | RANDOM_JINK 선택 | P1 | Unit |
| **DECP-06** | 자동 패턴 실행 | DECEPTION_START SPIRAL | 30초 실행 후 자동 중단 | P0 | SITL |
| **DECP-07** | 기만 중 중단 | 실행 중 DECEPTION_STOP | 즉시 중단 | P0 | SITL |
| **DECP-08** | 동시 실행 방지 | SPIRAL 실행 중 SINE 시도 | 거부 + 경고 | P0 | Unit |
| **DECP-08** | 위협 변화 시 전환 | SPIRAL 실행 중 레이더 위협 추가 | SINE로 전환 | P1 | SITL |
| **DECP-09** | 기만 효과 시뮬레이션 | 거리 500m, IR 미사일 | 성공 확률 > 70% | P1 | Unit |
| **DECP-10** | 기만 실행 로그 | 실행/중단/전환 이벤트 | 구조화된 로그 저장 | P1 | SITL |

### 5. 위험 분석 + 안전 게이트 (Phase 6)

| 테스트 ID | 시나리오 | 입력 | 기대 출력 | 우선순위 | 자동화 |
|-----------|----------|------|-----------|----------|--------|
| **RISK-01** | CRITICAL - 배터리 3% | 배터리 3%, 다이브 모드 | CRITICAL, BATTERY_CRITICAL, RTL auto | P0 | Unit+SITL |
| **RISK-02** | CRITICAL - 모터 과열 | 모터 85도, 다이브 중 | CRITICAL, MOTOR_OVERHEAT, ESTOP auto | P0 | Unit+SITL |
| **RISK-02** | CRITICAL - 자세 제어 상실 | 롤 50도 유지 | CRITICAL, ATTITUDE_LOSS, ESTOP auto | P0 | SITL |
| **RISK-03** | HIGH - 배터리 15% | 배터리 15%, 순항 | HIGH, BATTERY_LOW, 속도 제한 | P0 | Unit |
| **RISK-04** | HIGH - 모터 70도 | 모터 70도, 순항 | HIGH, MOTOR_OVERHEAT, 속도 제한 | P0 | Unit |
| **RISK-05** | HIGH - GPS 상실 + 비상모드 미진입 | GPS 로스트, RTL 미진입 | HIGH, GPS_LOST, 경고 | P0 | SITL |
| **RISK-06** | MEDIUM - 배터리 30% | 배터리 30% | MEDIUM, BATTERY_MEDIUM, 모니터링 | P1 | Unit |
| **RISK-07** | LOW - 정상 상태 | 모든 센서 정상 | LOW, 빈 카테고리, CONTINUE | P1 | Unit |
| **RISK-08** | LLM 타임아웃 폴백 | 추론 200ms 초과 | LOW, LLM_FALLBACK, 규칙 기반 | P0 | Unit |
| **RISK-09** | LLM 에러 폴백 | llama.cpp 예외 발생 | LOW, LLM_FALLBACK, 규칙 기반 | P0 | Unit |
| **RISK-09** | 데이터 없음 폴백 | 로그 버퍼 비어있음 | LOW, NO_DATA, confidence 1.0 | P1 | Unit |

### 안전 게이트 통합 테스트

| 게이트 | 테스트 시나리오 | 통과 기준 | 자동화 |
|--------|----------------|-----------|--------|
| **SG-01** | MOVE_VEL 100m/s 요청 (제한 80) | 80m/s로 클램핑 | Unit |
| **SG-02** | STT 0.6 confidence "이륙" | 명령 거부 + 로그 | Unit+SITL |
| **SG-03** | MANUAL_SW HOLD 중 음성 "전진" | 음성 명령 취소 + HOLD 유지 | SITL |
| **SG-04** | "비상정지" 0.5 confidence | 즉시 ESTOP, LLM 미호출 | Unit+SITL |
| **SG-05** | 배터리 20% 강제 RTL | RTL 미션 자동 업로드 + 실행 | SITL+HW |
| **SG-06** | MAVLink 4초 무수신 | 자동 RTL/HOLD | SITL+HW |
| **SG-07** | CRITICAL 위험 → 음성 "전진" | 차단 + "위험 상황으로 명령 차단" TTS | SITL |
| **SG-08** | 다이브 25m에서 풀업 트리거 | 30m에서 강제 풀업 | SITL+HW |
| **SG-09** | SPIRAL 실행 중 SINE 요청 | 거부 + "기만 모드 활성화 중" | Unit+SITL |
| **SG-10** | 카메라 가림 → VIO 중단 | Optical Flow 전환 + "비전 센서 장애" 경고 | SITL |

---

## 하드웨어 테스트 체크리스트 (HW)

### 필수 하드웨어 구성
| 구성요소 | 수량 | 검증 항목 |
|----------|------|-----------|
| Pixhawk 6C | 2 | 펌웨어 업로드, MAVLink 통신, 센서 캘리브레이션 |
| Jetson Orin Nano | 1 | 모델 추론 속도, 열 관리, GPIO 제어 |
| IMX219 카메라 | 2 (전방/하향) | VIO, Optical Flow 이미지 품질 |
| TF-Luna | 1 | 전방 거리 정확도 ±2cm |
| TFmini-S | 1 | 하향 고도 ±5cm |
| u-blox F9P RTK | 1 | GPS RTK 고정, 정확도 < 2cm |
| T-Motor MN501-S | 2+ | 모터/ESC 캘리브레이션, 추력 테스트 |
| 6S LiPo 10000mAh | 2 | 용량/전압/방전율 모니터링 |

### 하드웨어 검증 시나리오
| 테스트 ID | 시나리오 | 통과 기준 |
|-----------|----------|-----------|
| **HW-01** | Pixhawk 6C 펌웨어 업로드 | 부팅 → MAVLink 하트비트 수신 |
| **HW-02** | MAVSDK 연결 | UDP 14540 연결 → 하트비트 수신 |
| **HW-03** | MAVROS2 연결 | ROS2 토픽 `/mavros/state` 수신 |
| **HW-04** | 카메라 캘리브레이션 | 체스보드 20장 → 내/외부 파라미터 추출 |
| **HW-05** | VIO 파이프라인 | 실내에서 궤적 추적 드리프트 < 1% |
| **HW-05** | Optical Flow | 저고도 호버링 속도 오차 < 0.1m/s |
| **HW-06** | LiDAR 거리/고도 | TF-Luna ±2cm, TFmini-S ±5cm |
| **HW-06** | IMU 캘리브레이션 | 가속도계/자이로 바이어스 < 임계값 |
| **HW-07** | 모터/ESC 캘리브레이션 | DShot600, 스로틀 선형성 확인 |
| **HW-08** | 배터리 모니터링 | 전압/전류/용량 정확도 ±2% |
| **HW-09** | 열 스트레스 테스트 | 30분 연속 추론 → 쓰로틀링 없음 |
| **HW-10** | 전원 시스템 | 6S 배터리 → 5V/12V 레귤레이터 안정성 |

---

## CI/CD 파이프라인 품질 게이트

```yaml
# .github/workflows/ci.yml 에서 강제 적용
quality_gates:
  lint:
    ruff: error
    mypy: error
  test:
    unit: "100% pass"
    integration: "100% pass"
    coverage: "> 80%"
  security:
    trufflehog: "no secrets"
    pip-audit: "no critical vulns"
  safety_gates:  # 커스텀 게이트
    sg-01: "altitude_velocity_clamp"
    sg-02: "low_confidence_rejection"
    sg-03: "manual_preemption"
    sg-04: "fast_path_emergency"
    sg-05: "battery_rtl"
    sg-06: "link_loss_rtl"
    sg-07: "critical_risk_block"
    sg-08: "pullup_altitude"
    sg-09: "deception_concurrency"
    sg-10: "sensor_degradation"
```

---

## 테스트 실행 명령어

```bash
# 전체 테스트 스위트
PYTHONPATH=. pytest tests/ -v --tb=short

# 개별 모듈
PYTHONPATH=. pytest tests/test_voice/ -v        # 음성인식
PYTHONPATH=. pytest tests/test_nongps/ -v       # Non-GPS
PYTHONPATH=. pytest tests/test_dive/ -v         # 다이브
PYTHONPATH=. pytest tests/test_deception/ -v    # 기만
PYTHONPATH=. pytest tests/test_safety/ -v       # 안전 게이트
PYTHONPATH=. pytest tests/test_integration/ -v  # 통합

# SITL 테스트 (Gazebo + PX4 실행 필요)
PYTHONPATH=. pytest tests/test_sitl/ -v -k "sitl"

# 하드웨어 테스트 (실기체 연결 필요)
PYTHONPATH=. pytest tests/test_hardware/ -v -k "hardware"

# 안전 게이트만
PYTHONPATH=. pytest tests/test_safety_gates.py -v

# 커버리지 리포트
PYTHONPATH=. pytest tests/ --cov=core --cov=voice --cov=nongps --cov=dive --cov=deception --cov=safety --cov=bridge --cov-report=html
```

---

## 테스트 데이터 관리

| 데이터셋 | 용도 | 크기 | 저장 위치 |
|----------|------|------|-----------|
| **음성 데이터** | STT 학습/검증 | 10시간 (한국어/영어) | `data/voice/` |
| **실내 VIO** | VIO 학습/검증 | 50분 (루프 포함) | `data/nongps/indoor/` |
| **실외 VIO+GPS** | 하이브리드 검증 | 100분 | `data/nongps/outdoor/` |
| **다이브 궤적** | 궤적 엔진 검증 | 1000개 궤적 | `data/dive/trajectories/` |
| **기만 시뮬레이션** | 효과 모델 검증 | 10000 시뮬레이션 | `data/deception/sim/` |
| **위험 로그** | 위험 분석기 학습 | 5000 샘플 | `data/safety/logs/` |

---

## 회귀 테스트 기준선 (Baseline)

| 지표 | 기준선 (v0.1.0) | 허용 편차 | 측정 주기 |
|------|-----------------|-----------|-----------|
| STT CER (한국어) | 3.2% | < 5% | 매 커밋 |
| STT CER (영어) | 4.1% | < 5% | 매 커밋 |
| NLU 정확도 | 94.5% | > 90% | 매 커밋 |
| VIO 드리프트 (실내) | 0.8%/분 | < 1%/분 | 일일 |
| VIO 드리프트 (실외) | 2.1%/분 | < 3%/분 | 일일 |
| Optical Flow 속도 오차 | 0.08m/s | < 0.1m/s | 일일 |
| 다이브 궤적 생성 시간 | 45ms (MPC) | < 50ms | 일일 |
| LLM 추론 시간 | 180ms | < 200ms | 일일 |
| 안전 게이트 레이턴시 | 2ms | < 5ms | 일일 |
| 전체 테스트 스위트 시간 | 45초 | < 60초 | 매 PR |

---

## 결함 관리

| 심각도 | 정의 | 대응 기한 | 예시 |
|--------|------|-----------|------|
| **Critical** | 안전 게이트 실패, 충돌 위험 | 즉시 (릴리즈 블록) | SG-01~10 실패, 충돌 발생 |
| **High** | 핵심 기능 실패, 성능 심각 저하 | 24시간 내 | 주요 기능 미작동, 성능 50% 저하 |
| **Medium** | 부가 기능 실패, UX 저하 | 1주일 내 | 부가 기능 버그, UI 문제 |
| **Low** | 코스메틱, 문서, 경고 | 다음 스프린트 | 오타, 로그 메시지 개선 |

---

## 테스트 리포트 템플릿

```markdown
# 테스트 리포트: [모듈명] - [날짜]

## 요약
- 전체: X개 / 통과: Y개 / 실패: Z개 / 스킵: W개
- 안전 게이트: 통과/실패
- 커버리지: XX%

## 실패 상세
| 테스트 ID | 실패 사유 | 심각도 | 담당자 | 조치 계획 |
|-----------|-----------|--------|--------|-----------|

## 성능 지표
| 지표 | 현재 | 기준선 | 편차 | 상태 |
|------|------|--------|------|------|

## 위험 평가
- Critical: 0개
- High: X개
- Medium: Y개
- Low: Z개

## 승인
- 테스트 엔지니어: ___________
- 안전 엔지니어: ___________ (안전 게이트 필수)
- 프로젝트 리드: ___________
```