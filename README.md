# Q250-V3 Opti 자율비행 드론 운용 매뉴얼 프로젝트

## 📁 프로젝트 구조

```
Q250-V3-Opti/
├── README.md                    # 이 파일
├── .specs/
│   └── tasks.md                 # SpecKit 작업 명세 (Phase 1~8)
├── docs/                        # 문서 (마크다운 + 완성본)
│   ├── manual-draft.md          # 초안 (마크다운)
│   ├── manual-final.docx        # 완성본 (워드, 그림 포함)
│   ├── images/                  # 사진, 다이어그램 이미지
│   └── diagrams/                # 개념도 (Mermaid, PlantUML 소스)
├── config/                      # 설정 파일
│   ├── px4/                     # PX4 파라미터 파일
│   ├── jetson/                  # Jetson 설정 파일
│   ├── network/                 # 네트워크 설정
│   ├── ros2/                    # ROS 2 설정
│   └── silvus/                  # Silvus 설정
├── scripts/                     # 자동화 스크립트
│   ├── setup/                   # 설치 스크립트
│   ├── preflight/               # 비행 전 체크
│   ├── inflight/                # 비행 중 모니터링
│   └── postflight/              # 비행 후 처리
├── src/                         # 소스 코드
│   ├── bridge/                  # MAVSDK + MAVROS2 듀얼 브릿지
│   ├── collision_avoidance/     # APF+VO 충돌 회피 모듈
│   ├── deception/               # 기만 엔진
│   ├── deployment/              # TensorRT 배포
│   ├── nongps/                  # Non-GPS 내비게이션
│   ├── safety/                  # 위험 분석/안전 게이트
│   ├── swarm/                   # Silvus + IQP + 재최적화
│   ├── training/                # 모델 학습
│   └── voice/                   # 음성 파이프라인
├── generated/                   # 자동 생성 코드
│   └── mavlink/                 # MAVLink Python/C++ 바인딩
├── q250_msgs/                   # 커스텀 MAVLink 메시지
├── q250_msgs/voice_control.xml  # MAVLink 메시지 정의
├── ros2_ws/                     # ROS 2 워크스페이스
├── px4_params/                  # PX4 파라미터
├── flight_logs/                 # 비행 로그
├── simulation/                  # 시뮬레이션 환경
├── Dockerfile                   # 개발 환경 이미지
├── docker-compose.yml           # 멀티 컨테이너 오케스트레이션
├── docker-entrypoint.sh         # 컨테이너 진입점
├── check_env_q250.sh            # 환경 검증
├── package_datasets_for_transfer.sh  # 데이터셋 패키징
├── .github/workflows/ci.yml     # GitHub Actions CI
└── references/                  # 참조 자료
```

## 🎯 프로젝트 개요

**Q250-V3 Opti**는 재난 대응 및 군사 작전을 위한 자율비행 드론 시스템입니다. 음성 제어, Non-GPS 내비게이션, 다이브 어택, 기만 엔진, 실시간 통신 최적화, 안전 게이트, **실시간 충돌 회피(APF+VO)**를 통합한 완전 자율 비행 시스템입니다.

### 핵심 특징
- 🎤 **음성 제어**: faster-whisper + Silero VAD 실시간 한국어 인식
- 🛰️ **Non-GPS 내비게이션**: VIO, Optical Flow, LiDAR, EKF2 융합
- 🎯 **다이브 어택**: MPC/LUT/기하학적 궤적 + 실시간 충돌 회피(APF+VO)
- 🎭 **기만 엔진**: 위협 평가 + 자동 패턴 선택 + 효과 모델링
- 📡 **Silvus MANET + IQP 최적화**: 실시간 링크 품질 기반 주파수 재할당
- 🛡️ **안전 게이트**: LLM 위험 분석 + 위험 인식 중재자 + 비상 핸들러
- 🛑 **실시간 충돌 회피(APF+VO)**: 실시간 장애물/타 UAV 회피 (5ms 루프)

---

## 📋 Phase 개요 (Phase 1~8)

| Phase | 작업 수 | 기간 | 핵심 내용 |
|-------|---------|------|-----------|
| **Phase 1** | 10 | 2주 | 인프라 (ROS2, MAVLink, Docker, CI/CD) |
| **Phase 2** | 10 | 3주 | 음성인식 (faster-whisper + VAD) |
| **Phase 3** | 10 | 4주 | Non-GPS 융합 (VIO, Optical Flow, EKF2) |
| **Phase 4** | 7 | 3주 | 다이브 어택 (MPC, 기만 패턴, 풀업) |
| **Phase 5** | 13 | 4주 | 기만 엔진 + Silvus 통신 백본 |
| **Phase 6** | 8 | 2주 | 위험 분석 + 안전 게이트 |
| **Phase 7** | 15 | 3주 | 통합/검증 (SITL, 실외 비행) |
| **Phase 8** | 6 | 3주 | **충돌 회피 (APF+VO)** |

**총계: 79개 작업, 약 24주 (병렬화 시 ~19주)**

---

## 🚀 빠른 시작

```bash
# 1. 저장소 클론
cd /Users/amaster/projectm/Q250-V3-Opti

# 2. Docker 개발 환경 실행
docker compose build q250-dev
docker compose up -d q250-dev
docker exec -it q250-dev bash

# 3. 환경 검증
bash check_env_q250.sh

# 4. 설치 스크립트 실행 (컨테이너 내부)
./scripts/setup/01_jetson_base.sh
./scripts/setup/02_ros2_humble.sh
./scripts/setup/03_px4_firmware.sh
./scripts/setup/04_mavlink_router.sh
./scripts/setup/05_uxrce_dds_agent.sh
./scripts/setup/apply_configs.sh

# 5. 비행 전 체크
./scripts/preflight/check_all.sh
```

---

## 📡 실버스(StreamCaster) 데이터링크 통합

### 보유 자산
- **GDT (Ground Data Terminal)**: 1대 — 지상국 게이트웨이
- **Air Unit**: 4대 — 기체 4대 장착 (예비 1대)
- **웨이브폼**: **MN-MIMO** (군용급 MANET, TDMA/OFDMA, AES-256)

### 핵심 성능

| 지표 | 값 |
|------|-----|
| 단일 홉 처리량 | 80~120 Mbps |
| 지연 (1홉) | 3~8 ms (RTT) |
| 최대 홉 수 | 5~8 홉 |
| 거리 (LOS) | 20~50 km |
| 암호화 | AES-256 + TRANSEC |

### 관련 파일
- `config/silvus/silvus.yaml` — Silvus 설정
- `config/mavlink-router/main_silvus.conf` — MAVLink 라우팅
- `config/jetson/fastdds_silvus_config.xml` — ROS2 DDS 설정
- `scripts/silvus_monitor.py` — 링크 상태 모니터링 ROS2 노드

---

## 🛑 실시간 충돌 회피 (APF+VO) - Phase 8

### 핵심 개념
- **APF (Artificial Potential Field)**: 목표 인력 + 장애물 척력 → 선호 속도 생성
- **VO (Velocity Obstacle)**: 충돌 유발 속도 공간 식별 → 안전 후보 필터링
- **하이브리드 선택**: 선호 속도와 가장 가까운 안전 속도 선택

### 핵심 성능
| 지표 | 목표 |
|------|------|
| 연산 주기 | ≤ 5ms (200Hz) |
| VO 구성 시간 | < 1ms (이웃 10개) |
| 후보 필터링 | < 2ms (후보 50개) |
| 최종 선택 | < 0.5ms |
| **전체 루프** | **< 5ms** (200Hz) |

### 주요 파일
- `src/collision_avoidance/apf_vo_core.py` — 핵심 엔진
- `src/collision_avoidance/velocity_obstacle.py` — VO 계산
- `src/collision_avoidance/heterogeneous_params.py` — 이기종 파라미터
- `src/dive/apf_vo_integration.py` — 다이브 어택 연동
- `src/swarm/formation_apf_vo.py` — 편대 비행 연동
- `src/safety/collision_safety_gate.py` — 안전 게이트 연동
- `tests/test_apf_vo_sitl.py` — SITL 검증

---

## 📡 MAVLink 커스텀 메시지 (8종)

| ID | 메시지 | 방향 | 설명 |
|----|--------|------|------|
| 30000 | VOICE_COMMAND | GCS → Drone | 음성 명령 (TAKEOFF, LAND, GOTO 등) |
| 30001 | VOICE_STATUS | Drone → GCS | 음성 시스템 상태 |
| 30002 | VOICE_FEEDBACK | Drone → GCS | 명령 실행 피드백 |
| 30003 | VOICE_WAYPOINT | GCS ↔ Drone | 음성 정의 웨이포인트 |
| 30004 | VOICE_EMERGENCY | GCS → Drone | 긴급 명령 |
| **30010** | **SILVUS_LINK_STATUS** | **Drone → GCS** | **링크 품질 (SNR, PER, ETX 등)** |
| **30011** | **SILVUS_REOPT_STATUS** | **Drone → GCS** | **재최적화 상태** |
| **30012** | **SILVUS_CHANNEL_CMD** | **GCS → Drone** | **채널 변경 명령** |

생성된 코드: `generated/mavlink/python.py`, `generated/mavlink/cpp/voice_control/`

---

## 🔧 개발 환경

```bash
# Docker 개발 환경
docker compose build q250-dev
docker compose up -d q250-dev
docker exec -it q250-dev bash

# 환경 검증
bash check_env_q250.sh

# 유용한 별칭 (컨테이너 내부)
colcon-build      # 전체 빌드
colcon-test       # 테스트 실행
pytest-voice      # 음성 파이프라인 테스트
pytest-bridge     # 브릿지 테스트
bridge-test       # 브릿지 구조 검증
asr-test          # 실시간 ASR 테스트
mavlink-check     # 커스텀 메시지 확인
```

---

## 📋 작업 현황 (SpecKit Phase 1~8)

| Phase | 작업 수 | 상태 | 비고 |
|-------|---------|------|------|
| Phase 1: 인프라 | 10 | ✅ 완료 | Docker, CI/CD, MAVLink, 브릿지 |
| Phase 2: 음성 | 10 | ✅ 완료 | faster-whisper + VAD 검증됨 |
| Phase 3: Non-GPS | 10 | 🔄 설계 완료 | MASt3R-SLAM 후보 추가 |
| Phase 4: 다이브 | 7 | 🔄 설계 완료 | MPC, 기만 패턴, 풀업 |
| Phase 5: 기만+통신 | 13 | 🔄 설계 완료 | Silvus + IQP + 재최적화 |
| Phase 6: 안전 | 8 | 🔄 설계 완료 | LLM 위험 분석 + 중재자 |
| Phase 7: 통합 | 15 | 🔄 설계 완료 | SITL, 실외 비행 |
| **Phase 8: 충돌 회피** | **6** | **🔄 설계 완료** | **APF+VO** |

---

## 📦 데이터셋 패키징 (타겟 PC 전송용)

```bash
# Mac에서 패키징
./package_datasets_for_transfer.sh ~/q250_transfer_package

# 생성 파일
q250_datasets_YYYYMMDD_HHMMSS.tar.gz      (289MB)
q250_datasets_YYYYMMDD_HHMMSS.tar.gz.sha256

# 포함 데이터셋
- drone_audio (processed) — 132MB (Binary/Multiclass)
- uzh_fpv (processed) — 1.2MB (IMU+Images+GT)
- idf_ds (processed) — 87MB
- fixed_wing_attitude — 68MB
- ign_fixed_wing — 68KB
- checkpoints — 20MB (Binary/Multiclass best_model.pth)

# 제외 (용량 과다)
- fpv_analog (processed) — 55GB (별도 전송 필요)
```

### 타겟 PC(WSL2)에서 복원
```bash
cd ~/data/drone_datasets/
tar -xzf q250_datasets_*.tar.gz
sha256sum -c *.sha256
```

---

## 🚀 릴리즈 정보

### v0.4.0 (2026-11-13)
- **Phase 1-2 완료**: 인프라, 음성 파이프라인
- **Phase 3-5 설계 완료**: Non-GPS, 다이브, 기만+통신
- **Phase 8 추가**: APF+VO 충돌 회피 모듈

### GitHub Release
- Tag: `v0.4.0`
- URL: https://github.com/krill0188/Q250-V3-Opti/releases/tag/v0.4.0

---

## 📚 참고 자료

- **Q250-V3 Opti 공식**: https://quad-drone-lab.gitbook.io/quad-drone-start/q250/q250-v3-opti
- **PX4 공식 문서**: https://docs.px4.io/main/en/
- **ROS 2 PX4 가이드**: https://docs.px4.io/main/en/ros2/user_guide
- **쿼드 드론연구소**: https://quad-drone-lab.co.kr/
- **SpecKit 명세**: `.specs/tasks.md` (Phase 1~8, T-01~T-106)

---

## 📄 라이선스
이 프로젝트는 쿼드 드론연구소 내부 프로젝트입니다. 무단 배포를 금합니다.

---

*Last updated: 2026-11-13 | Q250-V3-Opti Team*