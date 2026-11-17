# Q250-V3-Opti 타 PC 준비도 점검 작업표

상태: `TODO` / `IN_PROGRESS` / `PASS` / `PARTIAL` / `BLOCKED` / `NOT_CHECKED`

## Phase 0 — Hermes·SpecKit 운영 진입점

- [ ] TPC-000 Hermes 설치 상태 확인: `hermes --version`
- [ ] TPC-000A Hermes 진단 실행: `hermes doctor` 결과 보관(비밀값 제외)
- [ ] TPC-000B 타겟 PC의 Q250 저장소를 Hermes 작업 디렉터리로 등록
- [ ] TPC-000C `AGENTS.md`와 `.specs/` 문서를 Hermes 세션에서 읽기 확인
- [ ] TPC-000D Hermes가 `.specs/tasks.md`를 단일 작업 기준으로 사용하는지 확인
- [ ] TPC-000E SpecKit CLI/확장 기능 필요 여부와 설치 상태를 Hermes와 별도로 판정
- [ ] TPC-000F 실제 환경 변경 전 `TPC-*` 작업 ID와 DoD 지정
- [ ] TPC-000G Hermes 로그에서 API 키·토큰·SSH 키·비밀번호 노출 여부 확인
- [ ] TPC-000H 공식 Spec Kit CLI `specify` 설치 경로 결정(uv/pipx/pip)
- [ ] TPC-000I Python 3.11+ 실행 환경 준비 후 `specify version` 확인
- [ ] TPC-000J Q250 프로젝트에 Spec Kit integration/commands 적용 여부 결정
- [ ] TPC-000K Mac 기준선과 타겟 PC 점검 결과 비교표 작성

## Phase A — 기준선과 점검 도구

- [ ] TPC-001 `spec.md`, `plan.md`, 저장소 commit/tag 기록
- [ ] TPC-002 Mac host inventory JSON 생성
- [ ] TPC-003 Mac Python import/version inventory 생성
- [ ] TPC-004 Mac dataset manifest 생성
- [ ] TPC-005 Mac checkpoint/model SHA-256 manifest 생성
- [ ] TPC-006 타 PC 점검 스크립트 작성: OS/CPU/RAM/GPU/disk/network
- [ ] TPC-007 타 PC 도구 버전 점검 스크립트 작성
- [ ] TPC-008 타 PC Python import/버전 점검 스크립트 작성
- [ ] TPC-009 점검 결과 JSON schema 정의

## Phase B — 타 PC OS·하드웨어

- [ ] TPC-010 Windows 11/WSL2 또는 native Ubuntu 22.04 확인
- [ ] TPC-011 WSL2 systemd 및 Ubuntu release 확인
- [ ] TPC-012 CPU architecture, RAM, disk 여유 확인
- [ ] TPC-013 NVIDIA GPU, driver, CUDA 확인
- [ ] TPC-014 NVIDIA Container Toolkit 확인
- [ ] TPC-015 Docker daemon 및 Compose 확인
- [ ] TPC-016 USB/IP, serial, `dialout` 권한 확인
- [ ] TPC-017 방화벽/DNS/필수 UDP 포트 확인

## Phase C — 운용·개발 필수 SW

- [ ] TPC-020 Git, compiler, CMake, Ninja, ccache 설치·버전 확인
- [ ] TPC-021 Python venv/pip/개발 헤더 확인
- [ ] TPC-022 ROS 2 Humble 설치 및 environment source 확인
- [ ] TPC-023 rosdep/colcon/vcstool 설치 및 동작 확인
- [ ] TPC-024 Gazebo Harmonic 설치 및 headless launch 확인
- [ ] TPC-025 PX4 v1.15 source recursive checkout 확인
- [ ] TPC-026 PX4 build toolchain 및 `px4_fmu-v6c_default` build 확인
- [ ] TPC-027 MAVLink Router 설치·설정·read-only status 확인
- [ ] TPC-028 Micro-XRCE-DDS-Agent v2.4.3 설치·버전 확인
- [ ] TPC-029 MAVSDK/Pymavlink/MAVROS2 설치·import 확인
- [ ] TPC-030 QGroundControl 설치 버전 확인
- [ ] TPC-031 VS Code/Remote WSL/CMake/Python/Docker extensions 확인

## Phase D — 프로젝트 통합

- [ ] TPC-040 Q250 repository clone/checkout 및 clean status 확인
- [ ] TPC-041 `ros2_ws` dependency resolve
- [ ] TPC-042 `colcon build --symlink-install` 성공
- [ ] TPC-043 custom MAVLink dialect/generated files 확인
- [ ] TPC-044 config/px4 baseline parameter 파일 확인
- [ ] TPC-045 Docker image build 성공
- [ ] TPC-046 Docker GPU healthcheck에서 `torch.cuda.is_available()` 확인
- [ ] TPC-047 Docker Compose YAML config validation
- [ ] TPC-048 environment variables 및 path hardcoding 검사

## Phase E — 데이터셋 전송

- [ ] TPC-050 Mac processed dataset 목록·크기·파일 수 기준선 확정
- [ ] TPC-051 필수 데이터셋 package 생성
- [ ] TPC-052 package SHA-256 생성
- [ ] TPC-053 checkpoints/models package 및 SHA-256 생성
- [ ] TPC-054 선택 데이터셋 `fpv_analog` 별도 package 여부 결정
- [ ] TPC-055 raw dataset 전송 필요성 결정
- [ ] TPC-056 타 PC 저장 공간과 전송 공간 확인
- [ ] TPC-057 타 PC에서 package SHA-256 검증
- [ ] TPC-058 타 PC에서 압축 해제 및 경로 정합성 확인
- [ ] TPC-059 타 PC dataset manifest 재생성
- [ ] TPC-060 Mac manifest와 파일 수/바이트/해시 비교

## Phase F — 데이터 준비상태

- [ ] TPC-070 모든 필수 dataset train/val/test 존재
- [ ] TPC-071 모든 split metadata JSON parse
- [ ] TPC-072 NPZ shape/dtype 검사
- [ ] TPC-073 NaN/Inf/empty array 검사
- [ ] TPC-074 normalizer/scaler 파일 로드 검사
- [ ] TPC-075 preprocessing loader 1 batch smoke test
- [ ] TPC-076 drone_audio binary/multiclass label/feature 검사
- [ ] TPC-077 UZH-FPV image/IMU/groundtruth 검사
- [ ] TPC-078 IDF-DS sensor schema 검사
- [ ] TPC-079 IGN fixed-wing camera/GCP schema 검사
- [ ] TPC-080 fixed-wing attitude sensor schema 검사
- [ ] TPC-081 fpv_analog 대용량 상태 및 재처리 계획 기록
- [ ] TPC-082 checkpoint/model hash 비교

## Phase G — SITL 및 통신 검증

- [ ] TPC-090 PX4 SITL build
- [ ] TPC-091 Gazebo Q250 model load
- [ ] TPC-092 SITL heartbeat 확인
- [ ] TPC-093 MAVLink UDP 포트 확인
- [ ] TPC-094 uXRCE-DDS Agent 연결 확인
- [ ] TPC-095 `/fmu/out/vehicle_status` 확인
- [ ] TPC-096 `/fmu/out/vehicle_local_position` 확인
- [ ] TPC-097 `/fmu/out/sensor_combined` 확인
- [ ] TPC-098 ROS 2 custom messages discovery 확인
- [ ] TPC-099 MAVSDK/MAVROS2 bridge smoke test
- [ ] TPC-100 SITL log와 테스트 결과 보관

## Phase H — 운용 전 안전 검증

- [ ] TPC-110 Hardware preflight는 HEARTBEAT read-only로 수행
- [ ] TPC-111 실제 FC port/sysid/compid/firmware/baud 기록
- [ ] TPC-112 ARM 전 안전 조건·승인 문서 확인
- [ ] TPC-113 실제 FC 검증 전 `HARDWARE_PASS` 금지 확인
- [ ] TPC-114 장애 시나리오와 복구 절차 확인
- [ ] TPC-115 최종 판정: `SIMULATION_READY`, `DATA_READY_ONLY`, `BLOCKED` 중 하나

## Phase I — 비교 보고서와 릴리즈

- [ ] TPC-120 Mac vs 타 PC 비교 매트릭스 작성
- [ ] TPC-121 미설치·버전차·ABI차·GPU차 분류
- [ ] TPC-122 재현 실패 원인과 조치 기록
- [ ] TPC-123 증거 파일 경로와 SHA-256 기록
- [ ] TPC-124 README/사용가이드에 타 PC 절차 링크
- [ ] TPC-125 SpecKit traceability 갱신
- [ ] TPC-126 변경사항 테스트 및 `git diff --check`
- [ ] TPC-127 커밋·릴리즈 여부를 사용자 승인 후 결정
