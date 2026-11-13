# Q250-V3-Opti: 작업 분해 (TASKS)

## 작업 ID 체계
- **Phase 1**: 인프라 (T-01 ~ T-10)
- **Phase 2**: 음성인식 (T-11 ~ T-20)
- **Phase 3**: Non-GPS 융합 (T-21 ~ T-40)
- **Phase 4**: 다이브 어택 (T-41 ~ T-60)
- **Phase 5**: 기만 엔진 (T-61 ~ T-70)
- **Phase 6**: 위험/안전 (T-71 ~ T-85)
- **Phase 7**: 통합/검증 (T-86 ~ T-100)

---

## Phase 1: 기반 인프라 (T-01 ~ T-10)

### T-01: ROS2 워크스페이스 + 커스텀 메시지 정의
- **설명**: ROS2 Humble 워크스페이스 구성, 커스텀 메시지 패키지 생성
- **산출물**: `ros2_ws/src/q250_msgs/msg/*.msg`
- **의존성**: 없음
- **DoD**: `colcon build` 성공, 메시지 타입 생성 확인
- **예상**: 1일

### T-02: MAVLink 커스텀 메시지 생성 (mavgen)
- **설명**: XML 정의 → C/Python 헤더 생성 (메시지 ID 30000-30004, 30010-30012)
- **산출물**: `mavlink/q250_custom.xml`, 생성된 헤더
- **의존성**: T-01
- **DoD**: 
  - `mavgen.py` 실행 성공, PX4/MAVROS2에서 메시지 인식
  - 음성 제어 메시지 5종 (ID 30000-30004)
  - Silvus 연동 메시지 3종 (ID 30010-30012): LINK_STATUS, REOPT_STATUS, CHANNEL_CMD
- **예상**: 1일

### T-03: PX4 EKF2 외부 측정 인터페이스 검증
- **설명**: `VISION_POSITION_ESTIMATE`, `VISION_SPEED_ESTIMATE` 주입 테스트
- **산출물**: SITL에서 외부 측정값 주입 → EKF2 상태 수렴 확인
- **의존성**: PX4 SITL 실행 환경
- **DoD**: Gazebo SITL에서 비전 위치 주입 시 EKF2 위치 수렴 (오차 < 0.5m)
- **예상**: 2일

### T-04: MAVSDK + MAVROS2 듀얼 브릿지 구축
- **설명**: MAVSDK(미션) + MAVROS2(속도제어) 동시 실행 브릿지 + Silvus gRPC/REST 프록시
- **산출물**: `bridge/mavsdk_bridge.py`, `bridge/mavros2_bridge.py`, `bridge/coordinator.py`, `bridge/silvus_proxy.py`
- **의존성**: T-02, T-03
- **DoD**: 
  - MAVSDK: ARM/TAKEOFF/LAND/미션 업로드 작동
  - MAVROS2: `/mavros/setpoint_velocity/cmd_vel` 20Hz 제어 작동
  - 코디네이터: 선점/해제 로직 동작 (수동 > 음성 > 미션)
  - Silvus gRPC/REST 프록시: 링크 품질 수집, 채널 변경 명령 전달
- **예상**: 3일

### T-05: Gazebo SITL 환경 구성 (PX4 + 하이브리드 기체)
- **설명**: 고정익+FPV 하이브리드 기체 SDF 모델 + PX4 파라미터
- **산출물**: `simulation/models/q250_hybrid/`, `px4_params/q250_hybrid.params`
- **의존성**: T-03
- **DoD**: Gazebo에서 기체 이륙/비행/착륙 가능, 센서 데이터 정상 발행
- **예상**: 3일

### T-06: 시뮬레이션용 Non-GPS 센서 플러그인
- **설명**: Gazebo에서 VIO/Optical Flow/LiDAR 시뮬레이션
- **산출물**: `simulation/plugins/non_gps_sensors.cc`
- **의존성**: T-05
- **DoD**: 
  - VISION_POSITION_ESTIMATE 발행 (노이즈 포함)
  - OPTICAL_FLOW_RAD 발행
  - LIDAR 거리 데이터 발행
- **예상**: 3일

### T-07: 개발 환경 Docker 이미지
- **설명**: ROS2 + PX4 + Gazebo + ML 라이브러리 통합 이미지
- **산출물**: `Dockerfile.dev`, `docker-compose.dev.yml`
- **의존성**: T-05
- **DoD**: `docker-compose up`으로 전체 스택 기동, ROS2/MAVLink 통신 확인
- **예상**: 2일

### T-08: GitHub Actions CI 파이프라인
- **설명**: Lint/Test/Security/Docs/Docker/Release 파이프라인
- **산출물**: `.github/workflows/ci.yml`
- **의존성**: T-01
- **DoD**: PR 시 자동 실행, main 브랜치 보호 규칙 적용
- **예상**: 1일

### T-09: 개발 환경 문서화 (DEVELOPMENT_SETUP.md)
- **설명**: WSL2/Ubuntu/ROS2/PX4/Gazebo/Jetson 설정 가이드
- **산출물**: `DEVELOPMENT_SETUP.md`
- **의존성**: T-07
- **DoD**: 새 환경에서 문서대로 1시간 내 개발 환경 구축 가능
- **예상**: 1일

### T-10: 프로젝트 구조 정리 + 초기 커밋
- **설명**: 전체 디렉토리 구조 확정, .gitignore, README 업데이트
- **산출물**: 정리된 프로젝트 구조, 초기 커밋
- **의존성**: T-01 ~ T-09
- **DoD**: `git status` clean, 모든 Phase 1 산출물 커밋
- **예상**: 1일

---

## Phase 2: 음성인식 파이프라인 (T-11 ~ T-20)

### T-11: faster-whisper STT + VAD 통합
- **설명**: faster-whisper (CTranslate2) + Silero VAD 실시간 파이프라인
- **산출물**: `voice/stt/faster_whisper_stt.py`, `voice/stt/vad.py`, `voice/stt/audio_capture.py`
- **의존성**: T-01
- **DoD**: 
  - 실시간 오디오 → 텍스트 변환 (레이턴시 < 200ms)
  - 한국어/영어 인식 정확도 > 95%
  - VAD로 무음 구간 자동 분할
- **예상**: 3일

### T-12: llama.cpp NLU + 함수 호출 구현
- **설명**: 로컬 LLM (Nemotron-3.5-8B-GGUF) 함수 호출로 구조화된 명령 출력
- **산출물**: `voice/nlu/llama_nlu.py`, `voice/nlu/intent_parser.py`, `voice/nlu/functions.json`
- **의존성**: T-11, 모델 파일 (`~/models/nemotron-3.5-8b-q4_k_m.gguf`)
- **DoD**: 
  - 음성 텍스트 → 구조화된 명령 (action, params, confidence) 변환
  - 지원 액션: TAKEOFF, LAND, DIVE_ATTACK, DECEPTION_START, SET_MODE, MOVE_VEL, RTL, HOLD
  - 추론 시간 < 200ms (Jetson Orin Nano)
- **예상**: 3일

### T-13: Fast-Path 비상 명령 구현
- **설명**: "비상정지", "즉시 착륙" → LLM 우회 즉시 FAILSAFE_ESTOP
- **산출물**: `voice/nlu/fast_path.py`
- **의존성**: T-11
- **DoD**: 
  - "비상정지", "즉시 착륙", "이머전시" 키워드 즉시 감지
  - LLM 추론 없이 즉시 `FAILSAFE_ESTOP` 우선순위 명령 생성
  - 레이턴시 < 10ms
- **예상**: 1일

### T-14: Mission Planner + Commander 통합
- **설명**: 음성 명령 → 미션 시퀀싱 → 우선순위 중재기 연동
- **산출물**: `voice/commander.py`
- **의존성**: T-12, T-13
- **DoD**: 
  - 음성 명령 → 구조화된 미션 → 우선순위 중재기 제출
  - 미션 큐 관리 (우선순위/타임아웃/취소)
  - 음성 피드백 (TTS) 연동
- **예상**: 2일

### T-15: 음성→명령 E2E 테스트 (SITL)
- **설명**: Gazebo SITL에서 음성 명령 → 드론 제어 E2E 검증
- **산출물**: `tests/test_voice_e2e.py`
- **의존성**: T-14, T-05
- **DoD**: 
  - "드론 이륙" → TAKEOFF 실행 → 이륙 완료
  - "고도 50미터" → 고도 변경 → 목표 고도 ±1m 도달
  - "비상정지" → 즉시 ESTOP → 모터 정지
- **예상**: 2일

### T-16: 음성 피드백 (TTS) 연동
- **설명**: Edge-TTS 또는 pyttsx3로 음성 피드백
- **산출물**: `voice/audio_feedback.py`
- **의존성**: T-14
- **DoD**: 명령 수신 확인, 상태 알림, 위험 경고 음성 출력
- **예상**: 1일

### T-16: 오디오 캡처 최적화 (노이즈 억제)
- **설명**: 리샘플링, 노이즈 게이트, 에코 캔슬레이션
- **산출물**: `voice/stt/audio_processing.py`
- **의존성**: T-11
- **DoD**: 실외 프로펠러 소음 환경에서 STT 정확도 > 90%
- **예상**: 2일

### T-17: 다국어 지원 (한국어/영어)
- **설명**: 언어 자동 감지 + 다국어 모델 전환
- **산출물**: `voice/stt/multilingual.py`
- **의존성**: T-11
- **DoD**: 한국어/영어 혼용 명령 인식, 언어별 모델 자동 선택
- **예상**: 1일

### T-18: 음성 명령 이력 + 로깅
- **설명**: 인식 결과/신뢰도/실행 결과 구조화 로깅
- **산출물**: `voice/logger.py`
- **의존성**: T-14
- **DoD**: SQLite/JSONL 저장, 재학습용 데이터셋 추출 가능
- **예상**: 1일

### T-19: 웨이크 워드 감지
- **설명**: "헤이 드론" 등 웨이크 워드로 STT 활성화
- **산출물**: `voice/stt/wake_word.py` (Porcupine/PV)
- **의존성**: T-11
- **DoD**: 상시 대기 모드에서 웨이크 워드 감지 시 STT 활성화, 오탐 < 1회/시간
- **예상**: 1일

### T-20: 음성 파이프라인 통합 + 문서화
- **설명**: 전체 파이프라인 통합 테스트 + API 문서
- **산출물**: `voice/__init__.py`, `docs/voice_pipeline.md`
- **의존성**: T-11 ~ T-19
- **DoD**: 전체 파이프라인 E2E 통과, API 문서 완성
- **예상**: 1일

---

## Phase 3: Non-GPS 융합 (T-21 ~ T-40)

### T-21: VIO 파이프라인 선택 (ORB-SLAM3 vs OpenVINS vs MASt3R-SLAM)
- **설명**: ORB-SLAM3 vs OpenVINS vs **MASt3R-SLAM** 3파전 비교 평가 + 선택
- **산출물**: `nongps/vio/orb_slam3_wrapper.py` 또는 `openvins_wrapper.py` 또는 `mast3r_slam_wrapper.py`
- **의존성**: T-05, T-06
- **DoD**:
  - 실내/실외에서 위치 추적 드리프트 < 1% 거리
  - 루프 클로저 작동 확인
  - 실시간 30fps 처리
  - **단일 카메라 지원 여부**
  - **IMU 융합 용이성 (별도 레이어 필요성 평가)**
  - **불확도/공분산 출력 지원 여부 (EKF2 주입용)**
  - **Jetson Orin Nano 배포 가능성 (INT8 양자화)**
- **예상**: 3일

### T-22: VIO 파이프라인 구현 (선택된 것)
- **설명**: 선택된 VIO 알고리즘 Python 바인딩 + ROS2 노드화
- **산출물**: `nongps/vio/*.py`, ROS2 노드 (`vio_node.py`)
- **의존성**: T-21
- **DoD**: 
  - `/nongps/vio/pose` 토픽 발행 (10Hz)
  - `/nongps/vio/status` 품질 지표 발행
  - 루프 클로저 시 자세 보정 확인
- **예상**: 3일

### T-23: Optical Flow 속도 추정 (OpenCV)
- **설명**: 하향 카메라 Optical Flow → 속도 벡터 추정
- **산출물**: `nongps/optical_flow/flow_processor.py`, `velocity_estimator.py`
- **의존성**: T-06 (Gazebo 플러그인)
- **DoD**: 
  - Farneback/Lucas-Kanade 구현
  - 픽셀 흐름 → m/s 변환 (초점거리/고도 보정)
  - 품질 임계값 기반 유효성 검사
  - 50Hz 처리, 지터 < 0.1m/s
- **예상**: 2일

### T-24: LiDAR 드라이버 (TF-Luna + TFmini-S)
- **설명**: UART/I2C 드라이버 + 장애물 맵핑
- **산출물**: `nongps/lidar/tf_luna_driver.py`, `tf_mini_driver.py`, `obstacle_mapper.py`
- **의존성**: 하드웨어 연결 (UART/I2C)
- **DoD**: 
  - TF-Luna (전방): 20Hz 거리 데이터, ±2cm 정확도
  - TFmini-S (하향): 100Hz 고도 데이터, ±5cm 정확도
  - 장애물 맵 그리드 발행 (`/nongps/lidar/obstacle_map`)
- **예상**: 2일

### T-25: EKF2 외부 측정 인터페이스 구현
- **설명**: PX4 EKF2에 VIO/Optical Flow/LiDAR/Silvus OLSR 측정값 주입
- **산출물**: `nongps/fusion/ekf2_interface.py`, `external_measurement.py`
- **의존성**: T-03, T-22, T-23, T-24, T-71 (Silvus 인터페이스)
- **DoD**: 
  - `VISION_POSITION_ESTIMATE` (10Hz) 주입 → EKF2 위치 수렴
  - `VISION_SPEED_ESTIMATE` (10Hz) 주입 → EKF2 속도 수렴
  - `DISTANCE_SENSOR` (하향 라이다) → EKF2 고도 보정
  - Silvus OLSR 상대 위치/링크 품질 → EKF2 보조 측정값 주입
  - 공분산 행렬 적절히 설정 (대각성분 기반)
- **예상**: 3일

### T-26: 공분산 행렬 관리 + 센서 건강도 모니터링
- **설명**: 측정 공분산 동적 조정 + 센서 품질 평가
- **산출물**: `nongps/fusion/covariance_manager.py`, `health_monitor.py`
- **의존성**: T-25
- **DoD**: 
  - 센서별 품질 점수 (0-1) 실시간 계산
  - 품질 저하 시 공분산 자동 증가 (가중치 감소)
  - 센서 장애 감지 시 자동 제외 + 경고
- **예상**: 2일

### T-26: 통합 상태 추정기 (NonGPSStateEstimator)
- **설명**: 위치/속도/자세 + 공분산 통합 출력
- **산출물**: `nongps/state_estimator.py`
- **의존성**: T-22 ~ T-25
- **DoD**: 
  - `/nongps/state` 토픽 발행 (10Hz): 위치/속도/자세 + 6x6 공분산
  - 실내 드리프트 < 1m/분, 실외 GPS 보정 시 < 0.5m
  - 센서 장애 시 Graceful degradation
- **예상**: 2일

### T-27: Non-GPS SITL 검증 (실내)
- **설명**: Gazebo 실내 환경에서 Non-GPS 자율 비행
- **산출물**: `tests/test_nongps_indoor.py`
- **의존성**: T-26, T-05
- **DoD**: 
  - GPS 없이 이륙 → 웨이포인트 비행 → 착륙
  - 위치 오차 < 1m (실내 10x10m)
  - 센서 장애 시나리오 (카메라 가림) 대응 확인
- **예상**: 2일

### T-28: Non-GPS SITL 검증 (실외)
- **설명**: Gazebo 실외 환경에서 GPS+Non-GPS 하이브리드
- **산출물**: `tests/test_nongps_outdoor.py`
- **의존성**: T-27
- **DoD**: 
  - GPS 가용 시: GPS 주导航, Non-GPS 보조
  - GPS 차단 시: Non-GPS 단독 자율 비행 지속
  - 전환 시 위치 점프 < 2m
- **예상**: 2일

### T-28: Non-GPS 실하드웨어 검증 (Pixhawk + Jetson)
- **설명**: 실기체에서 Non-GPS 자율 비행 테스트
- **산출물**: `docs/nongps_hardware_test_report.md`
- **의존성**: T-28
- **DoD**: 
  - 실내: VIO + Optical Flow 단독 비행 5분
  - 실외: GPS 차단 후 Non-GPS 단독 3분
  - 드리프트 측정 및 보고서 작성
- **예상**: 3일

### T-29: Non-GPS 문서화 + 튜닝 가이드
- **설명**: 파라미터 튜닝 가이드 + 트러블슈팅
- **산출물**: `docs/nongps_tuning_guide.md`
- **의존성**: T-28
- **DoD**: 주요 파라미터 설명, 일반적인 문제/해결책, 로그 분석 방법
- **예상**: 1일

### T-30: Non-GPS 파이프라인 통합 + 회귀 테스트
- **설명**: 전체 Non-GPS 파이프라인 통합 + CI 회귀 테스트
- **산출물**: `nongps/__init__.py`, `tests/test_nongps_regression.py`
- **의존성**: T-21 ~ T-29
- **DoD**: CI에서 회귀 테스트 통과, 성능 벤치마크 기준선 설정
- **예상**: 1일

---

## Phase 4: 다이브 어택 시스템 (T-41 ~ T-60)

### T-41: 궤적 엔진 핵심 (MPC/LUT/Geometric)
- **설명**: MPC 실시간 최적화 + LUT 캐시 + 기하학적 폴백
- **산출물**: `dive/trajectory/mpc_optimizer.py`, `lut_generator.py`, `geometric_fallback.py`
- **의존성**: T-04, T-10
- **DoD**: 
  - MPC: CVXPY 기반, 제약조건 만족, 50ms 내 해 계산
  - LUT: (고도, 각도, 속도) 키로 캐시, 히트율 > 80%
  - Geometric: 제약조건 클램핑 내장, 폴백 보장
- **예상**: 4일

### T-42: 5종 기만 패턴 궤적 생성
- **설명**: SPIRAL/SINE/JINK/FAKE_CRASH/MULTI_PULSE 궤적
- **산출물**: `dive/patterns/*.py`
- **의존성**: T-41
- **DoD**: 
  - 각 패턴별 고유 궤적 특성 구현
  - 파라미터화 (반경/턴/진폭/주파수/하강률)
  - 궤적 연속성/미분가능성 보장
- **예상**: 3일

### T-43: 풀업 트리거 + 자동 회복
- **설명**: 라이다/고도 기반 풀업 트리거 + 자동 회복 궤적
- **산출물**: `dive/pullup/terrain_aware.py`, `altitude_trigger.py`, `auto_recovery.py`
- **의존성**: T-41, T-24
- **DoD**: 
  - 최소 풀업 고도 30m 보장
  - 지형 인식 풀업 (DEM 연동 시)
  - 자동 회복 후 CRUISE 모드 복귀
- **예상**: 2일

### T-44: 다이브 상태 머신 + 실행기
- **설명**: 다이브 진입/실행/풀업/회복 상태 머신
- **산출물**: `dive/dive_controller.py`, `dive/fsm.py`
- **의존성**: T-41 ~ T-43
- **DoD**: 
  - 상태: IDLE → DIVE_ENTRY → DIVE_EXECUTE → PULLUP → RECOVERY → CRUISE
  - MAVSDK 미션 업로드 + MAVROS2 실시간 제어
  - 비상 시 즉시 중단 + 풀업 실행
- **예상**: 3일

### T-45: 다이브 SITL 테스트 (기본)
- **설명**: Gazebo에서 다이브 어택 기본 궤적 실행
- **산출물**: `tests/test_dive_basic.py`
- **의존성**: T-44, T-05
- **DoD**: 500m 고도에서 70도 다이브 → 100m 풀업 → 순항 복귀
- **예상**: 2일

### T-46: 다이브 SITL 테스트 (기만 패턴 결합)
- **설명**: 다이브 중 기만 패턴 실행 테스트
- **산출물**: `tests/test_dive_deception.py`
- **의존성**: T-44, T-51
- **DoD**: 다이브 중 SPIRAL_DIVE 실행 → 풀업 → 복귀
- **예상**: 2일

### T-46: 다이브 제약조건 검증
- **설명**: 속도/각도/고도/풀업 제약조건 자동 검증
- **산출물**: `dive/trajectory/constraint_checker.py`, `tests/test_dive_constraints.py`
- **의존성**: T-41
- **DoD**: 
  - 최대 속도 80m/s 클램핑
  - 최대 각도 80도 클램핑
  - 최소 풀업 30m 보장
  - 웨이포인트 타임스탬프 단조 증가
- **예상**: 1일

### T-47: 다이브 실하드웨어 검증
- **설명**: 실기체에서 다이브 어택 테스트 (고도 제한)
- **산출물**: `docs/dive_hardware_test_report.md`
- **의존성**: T-45, T-28
- **DoD**: 100m 고도에서 45도 다이브 → 50m 풀업 성공 5회
- **예상**: 3일

### T-47: 다이브 문서화 + 튜닝 가이드
- **산출물**: `docs/dive_tuning_guide.md`
- **예상**: 1일

---

## Phase 5: 기만 엔진 (T-61 ~ T-70)

### T-61: 위협 평가기 (ThreatAssessor)
- **산출물**: `deception/threat_assessor.py`
- **DoD**: IR/Radar/Optical/Multi 센서 기반 위협 유형/신뢰도/방위/거리 추정
- **예상**: 2일

### T-62: 자동 패턴 선택기
- **산출물**: `deception/pattern_selector.py`
- **DoD**: 위협 유형 매핑 + 점수 기반 선택 (A+B 혼합)
- **예상**: 2일

### T-63: 기만 효과 모델링
- **산출물**: `deception/effect_model.py`
- **DoD**: 기만 성공 확률 시뮬레이션 (센서/거리/각도 기반)
- **예상**: 2일

### T-64: 기만 실행기 (Executor)
- **산출물**: `deception/executor.py`
- **DoD**: 패턴별 시퀀스 실행, 타이밍 제어, 중단/재개 지원
- **예상**: 2일

### T-65: 기만 코디네이터 (시퀀서)
- **산출물**: `deception/coordinator.py`
- **DoD**: 다중 기만 순차/병렬 실행, 위협 변화 시 패턴 전환
- **예상**: 1일

### T-66: 기만 SITL 테스트
- **산출물**: `tests/test_deception_e2e.py`
- **DoD**: 각 패턴 실행 → 효과 시뮬레이션 → 중단/재개 검증
- **예상**: 2일

### T-67: 기만 실하드웨어 검증
- **산출물**: `docs/deception_hardware_test.md`
- **예상**: 2일

### T-68: 기만 문서화
- **산출물**: `docs/deception_guide.md`
- **예상**: 1일

### T-69: 기만 파이프라인 통합
- **산출물**: `deception/__init__.py`
- **예상**: 1일

### T-70: 기만 회귀 테스트
- **산출물**: `tests/test_deception_regression.py`
- **예상**: 1일

### T-71: Silvus MANET 백본 연동 (신규)
- **설명**: Silvus StreamCaster SDK 연동, 실시간 링크 품질 수집, MAVLink 브릿지
- **산출물**: `swarm/silvus_interface.py`, `swarm/mavlink_bridge.py`, `config/silvus.yaml`
- **의존성**: T-02, T-04, T-07
- **DoD**:
  - Silvus REST/gRPC/SNMP 인터페이스 구현
  - 실시간 링크 품질 (SNR, PER, ETX, RSSI) 10Hz 수집
  - MAVLink `SILVUS_LINK_STATUS` (ID 30010) 발행
  - 주파수/채널 변경 명령 수신 및 Silvus 설정 적용
  - 4대 Silvus 메쉬 형성 → 이동 중 링크 품질 로깅
- **예상**: 3일

### T-72: IQP 폐루프 최적화 엔진 (신규)
- **설명**: Silvus 실측 데이터 주입 → CPLEX/Gurobi 실시간 재최적화
- **산출물**: `swarm/iqp_optimizer.py`, `swarm/frequency_planner.py`
- **의존성**: T-71, T-25, T-74 (위험 분석기)
- **DoD**:
  - 목적함수: Coverage - λ₁·Interference - λ₂·ETX_Cost
  - 변수: UAV 위치(이산 그리드), 주파수 채널, 안테나 빔
  - 제약: 연결성(ETX 기반), 최대 홉 수, 주파수 충돌 방지
  - CPLEX Python API 연동, 해결 시간 < 5초 (20 UAV)
  - Silvus 링크 품질 변화 시 증분 재최적화 트리거
  - 주파수 재할당 → Silvus 채널 변경 API 호출
- **예상**: 4일

### T-73: 실시간 재최적화 파이프라인 (신규)
- **설명**: 링크 품질 저하 감지 → IQP 재실행 → Silvus 채널 변경 자동화
- **산출물**: `swarm/reopt_pipeline.py`, `swarm/trigger_monitor.py`
- **의존성**: T-71, T-72
- **DoD**:
  - 트리거: PER > 0.1, SNR < 10dB, ETX > 3, 홉 수 증가
  - 증분 최적화 (이전 해 warm-start)
  - 주파수 변경 완료까지 < 2초
  - 롤백 메커니즘 (품질 악화 시 이전 채널 복구)
  - MAVLink `SILVUS_REOPT_STATUS` (ID 30011) 발행
- **예상**: 2일

---

## Phase 6: 위험 분석 + 안전 게이트 (T-71 ~ T-85)

### T-74: Local LLM 위험 분석기 (llama.cpp Function Calling)
- **산출물**: `safety/risk_analyzer.py`
- **DoD**: 
  - 입력: 슬라이딩 윈도우 로그 (배터리/자세/모드/센서, **Silvus 링크 품질: SNR, PER, ETX, 홉 수**)
  - 출력: 위험도(CRITICAL/HIGH/MEDIUM/LOW), 카테고리, 권장액션, 자동실행
  - Function Calling 스키마 준수
  - 타임아웃 200ms 내 응답 (폴백 포함)
  - **Silvus 링크 품질 저하(PER>0.1, SNR<10dB) → 통신 위험도 상승 → 자동 재최적화/RTL 권고**
- **예상**: 3일

### T-72: 위험 인식 중재자 (RiskAwareArbitrator)
- **산출물**: `safety/risk_arbitrator.py`
- **DoD**: 
  - 주기적 위험 평가 (2Hz)
  - CRITICAL: 하위 명령 차단 + RTL/ESTOP 자동 실행
  - HIGH: 경고 + 속도/고도 제한
  - 위험 해제 시 자동 해제
- **예상**: 2일

### T-73: 동적 안전 검증기
- **산출물**: `safety/safety_validator.py`
- **DoD**: 
  - 고도/속도/배터리/자세 실시간 검증
  - 명령 클램핑 (속도/고도 제한)
  - 저신뢰도 음성 차단 (confidence < 0.85)
- **예상**: 2일

### T-74: 비상 핸들러 (ESTOP/RTL/HOLD)
- **산출물**: `safety/emergency_handler.py`
- **DoD**: 
  - ESTOP: 즉시 모터 정지 + 착륙
  - RTL: 복귀 경로 생성 + 자동 복귀
  - HOLD: 현재 위치 유지
  - FAILSAFE 우선순위 (0) 보장
- **예상**: 2일

### T-75: 워치독 (통신/센서/시스템)
- **산출물**: `safety/watchdog.py`
- **DoD**: 
  - MAVLink 하트비트 3초 타임아웃 → 자동 RTL
  - 센서 데이터 1초 무수신 → 경고 + 백업 센서 전환
  - CPU/메모리/온도 임계값 감시
- **예상**: 1일

### T-76: 안전 게이트 종합 테스트
- **산출물**: `tests/test_safety_gates.py`
- **DoD**: 
  - 고도/속도 초과 차단
  - 저신뢰도 음성 차단
  - 수동 선점 테스트
  - CRITICAL 위험 시 자동 RTL/ESTOP
- **예상**: 2일

### T-77: 안전 문서화 + 안전 사례
- **산출물**: `docs/safety_case.md`, `docs/safety_guide.md`
- **예상**: 1일

### T-78: 안전 파이프라인 통합 + 회귀 테스트
- **산출물**: `safety/__init__.py`, `tests/test_safety_regression.py`
- **예상**: 1일

---

## Phase 7: 통합 및 검증 (T-86 ~ T-100)

### T-89: 전체 시스템 통합 (SITL)
- **산출물**: `tests/test_full_integration_sitl.py`
- **DoD**: 음성→Non-GPS→다이브→기만→위험분석 전체 파이프라인 SITL 통과, **Silvus 4대 + UAV 4대 메쉬 형성 → 음성 명령 배치 → IQP 최적화 → 이동 중 실시간 재최적화 시연**
- **예상**: 3일

### T-87: 안전 게이트 종합 테스트
- **산출물**: `tests/test_safety_integration.py`
- **예상**: 2일

### T-88: 실하드웨어 통합 검증 (Pixhawk 6C + Jetson)
- **산출물**: `docs/hardware_integration_report.md`
- **예상**: 5일

### T-89: 실외 비행 테스트 (승인 후)
- **산출물**: `docs/flight_test_report.md`
- **예상**: 10일 (승인 대기 포함)

### T-90: 성능 벤치마크 + 최적화
- **산출물**: `docs/performance_benchmark.md`
- **예상**: 2일

### T-91: 문서화 완성 (README/CHANGELOG/가이드)
- **산출물**: README.md, CHANGELOG.md, 각 모듈 가이드
- **예상**: 2일

### T-92: v1.0 릴리즈 준비
- **산출물**: `gh release create v1.0.0`
- **예상**: 1일

### T-93: CI/CD 파이프라인 최종 검증
- **산출물**: CI 파이프라인 그린 확인
- **예상**: 1일

### T-94: 코드 리뷰 + 정리
- **산출물**: 리팩토링 + 주석 보완
- **예상**: 2일

### T-95: 배포 자동화 (Docker 이미지 + 배포 스크립트)
- **산출물**: `deploy/`, `docker-compose.prod.yml`
- **예상**: 2일

### T-96: 운영 매뉴얼 + 트러블슈팅 가이드
- **산출물**: `docs/operations_manual.md`, `docs/troubleshooting.md`
- **예상**: 2일

### T-97: 백업/복구 절차 문서화
- **산출물**: `docs/backup_recovery.md`
- **예상**: 1일

### T-98: 보안 감사 + 시크릿 관리 검증
- **산출물**: `docs/security_audit.md`
- **예상**: 1일

### T-99: 최종 회귀 테스트 스위트 실행
- **산출물**: 전체 테스트 스위트 그린
- **예상**: 2일

### T-100: 프로젝트 완료 보고 + 인수인계
- **산출물**: `PROJECT_COMPLETION_REPORT.md`
- **예상**: 1일

---

## Phase 8: 실시간 충돌 회피 모듈 (APF+VO) (T-81 ~ T-86)

### T-81: APF+VO 핵심 엔진 구현
- **설명**: APF 선호 속도 생성 + VO 필터링 + 안전 후보 선택 엔진
- **산출물**: `collision_avoidance/apf_vo_core.py`, `collision_avoidance/velocity_obstacle.py`
- **의존성**: T-03, T-04, T-25
- **DoD**:
  - APF: 목표 인력(역제곱) + 장애물 척력(가우시안/역제곱)
  - VO: 원뿔형 VO 구성 (이종 UAV 반경/속도 반영)
  - 후보 필터링: VO 외부 + Clearance > 임계값 + TTC > 임계값
  - 선택: ||V_pref - V_cand|| 최소 + Clearance 가중치 + TTC 가중치
  - 연산 시간 < 5ms (100Hz 루프 가능)
- **예상**: 3일

### T-82: 이기종 UAV 지원 확장
- **설명**: 기체 반경/최대속도/회전반경 이기종 파라미터 반영
- **산출물**: `collision_avoidance/heterogeneous_params.py`
- **의존성**: T-81
- **DoD**: UAV 타입별 파라미터 테이블, VO 크기/형상 동적 조정
- **예상**: 2일

### T-83: 다이브 어택 연동
- **설명**: 다이브 어택 궤적에 실시간 충돌 회피 오버레이
- **산출물**: `dive/apf_vo_integration.py`
- **의존성**: T-81, T-44
- **DoD**: 다이브 중 장애물 감지 시 MPC 궤적 + APF+VO 보정 합성, 풀업 시에도 회피 유지
- **예상**: 2일

### T-84: 스웜 편대 비행 연동
- **설명**: 편대 유지 인력 + 상호 충돌 회피 VO 통합
- **산출물**: `swarm/formation_apf_vo.py`
- **의존성**: T-81, T-65
- **DoD**: 편대 형상 인력(APF) + 편대원 간 VO(척력) 동시 적용
- **예상**: 3일

### T-85: 안전 게이트 연동 (T-74 연계)
- **설명**: 충돌 임박 시 안전 게이트 즉시 개입
- **산출물**: `safety/collision_safety_gate.py`
- **의존성**: T-81, T-74
- **DoD**: TTC < 2s 시 ESTOP/HOLD 자동 발동, 회피 속도 강제 주입
- **예상**: 2일

### T-86: 실시간 검증 (SITL)
- **산출물**: `tests/test_apf_vo_sitl.py`
- **의존성**: T-81, T-05
- **DoD**: Gazebo에서 동적 장애물 10개 + UAV 4대 실시간 회피 검증
- **예상**: 3일

---

## 작업 의존성 그래프 (핵심 경로)

```
T-01 → T-02 → T-03 → T-04 → T-05 → T-06 → T-07 → T-08 → T-09 → T-10
                                                    │
                                                    ▼
T-11 → T-12 → T-13 → T-14 → T-15 → T-16 → T-17 → T-18 → T-19 → T-20
                                                    │
                                                    ▼
T-21 → T-22 → T-23 → T-24 → T-25 → T-26 → T-27 → T-28 → T-29 → T-30
                                                    │
                                                    ▼
T-41 → T-42 → T-43 → T-44 → T-45 → T-46 → T-47
                                                    │
                                                    ▼
T-61 → T-62 → T-63 → T-64 → T-65 → T-66 → T-67 → T-68 → T-69 → T-73
                                                    │
                                                    ▼
T-74 → T-75 → T-76 → T-77 → T-78 → T-79 → T-80 → T-81
                                                    │
                                                    ▼
T-89 → T-90 → T-91 → T-92 → T-93 → T-94 → T-95 → T-96 → T-97 → T-98 → T-99 → T-100 → T-101 → T-102 → T-103 → T-104 → T-105 → T-106
```

---

## 병렬화 가능 그룹

| 그룹 | 작업 | 비고 |
|------|------|------|
| **Group A** | T-11~T-20 (음성), T-21~T-30 (Non-GPS) | Phase 2, 3 병렬 가능 |
| **Group B** | T-41~T-47 (다이브), T-61~T-73 (기만+통신) | Phase 4, 5 병렬 가능 |
| **Group C** | T-74~T-81 (안전+통신), T-41~T-47 (다이브) | 일부 병렬 가능 |
| **Group D** | T-82~T-86 (충돌 회피), T-89~T-106 (통합) | 일부 병렬 가능 |

---

## 총 예상 소요 기간

| Phase | 작업 수 | 예상 기간 | 비고 |
|-------|---------|-----------|------|
| Phase 1 | 10 | 2주 | 기반 인프라 |
| Phase 2 | 10 | 3주 | 음성인식 |
| Phase 3 | 10 | 4주 | Non-GPS 융합 |
| Phase 4 | 7 | 3주 | 다이브 어택 |
| Phase 5 | 13 | 4주 | 기만 엔진 + 통신 백본 |
| Phase 6 | 8 | 2주 | 위험/안전 |
| Phase 7 | 15 | 3주 | 통합/검증 |
| **Phase 8** | **6** | **3주** | **충돌 회피 (APF+VO)** |
| **총계** | **79** | **약 24주** | 병렬화 시 약 19주 |

---

## 마일스톤

| 마일스톤 | 목표 일자 | 완료 기준 |
|----------|-----------|-----------|
| M1: 인프라 완료 | Week 2 | T-10 완료, SITL 기본 비행 가능 |
| M2: 음성 파이프라인 | Week 5 | T-20 완료, SITL 음성 제어 가능 |
| M3: Non-GPS 융합 | Week 9 | T-30 완료, GPS 없이 자율 비행 가능 |
| M4: 다이브/기만/통신 | Week 13 | T-47, T-73 완료, SITL 다이브+기만+재최적화 시연 |
| M5: 안전 게이트 | Week 15 | T-81 완료, 안전 게이트 종합 테스트 통과 |
| **M6: 충돌 회피 (APF+VO)** | **Week 18** | **T-86 완료, SITL 실시간 충돌 회피 시연** |
| M7: 통합/릴리즈 | Week 24 | T-106 완료, v1.0 릴리즈 |

---

## 리소스 할당 권장

| 역할 | 인원 | 담당 Phase |
|------|------|------------|
| ROS2/MAVLink 엔지니어 | 1 | Phase 1, 3, 4, 5 |
| ML/음성 엔지니어 | 1 | Phase 2 |
| 컴퓨터비전/센서융합 엔지니어 | 1 | Phase 3 |
| 제어/궤적 엔지니어 | 1 | Phase 4, 5 |
| 안전/임베디드 엔지니어 | 1 | Phase 6 |
| **충돌 회피/제어 엔지니어 (신규)** | **1** | **Phase 8 (APF+VO)** |
| 통합/테스트 엔지니어 | 1 | Phase 7 |
| **총계** | **7명** | **병렬 최적화 시 19주** |