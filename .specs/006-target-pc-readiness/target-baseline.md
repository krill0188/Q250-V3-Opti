# 타겟 PC 기준선 — SpecKit/Hermes 및 Q250 준비 상태

- **수집 시각**: 2026-11-17 23:02:44 UTC
- **호스트**: `DESKTOP-IAOM8VS`
- **경로**: `/home/user/Q250-V3-Opti`
- **OS 계층**: Linux, x86_64, WSL2 Windows 경로 Docker CLI 확인
- **안전**: `commands_sent_to_fc=0`, `hardware_status=NOT_CHECKED`

## 1. SpecKit/Hermes

| 항목 | 타겟 PC 결과 | 판정 |
|---|---|---|
| Hermes Agent | `/home/user/.local/bin/hermes` | PASS |
| Hermes 버전 | `v0.23.1` | PASS |
| 공식 Spec Kit CLI `specify` | `1.4.2`, Python `3.11.18` | PASS |
| `uv` | 미표시 | NOT_CHECKED — Specify는 이미 실행됨 | 
| Python | 시스템 `3.10.12`; Specify 실행 환경 `3.11.18` | PASS for Spec Kit |
| `AGENTS.md` | 없음 | GAP |
| `CLAUDE.md` | 존재 | PASS |
| 기존 `.specs` 문서 | 모두 존재 | PASS |
| 타겟 readiness 문서 | 모두 존재 | PASS |
| Hermes integration | `hermes`, default/installed | PASS |
| Hermes integration manifest | `.specify/integrations/hermes.manifest.json` | PASS |

### 판정

타겟 PC에는 Hermes Agent와 공식 Spec Kit CLI `1.4.2`가 설치되어 있다. 공식 Spec Kit은 Python `3.11.18` 환경에서 실행되며, 시스템 Python `3.10.12`와 분리되어 있다. `.specify/`가 공식 프로젝트 구조로 초기화되었고 Hermes integration이 기본 integration으로 전환되었다.

Q250 기존 `.specs/` 문서는 모두 보존되어 있다. 따라서 공식 `.specify/`는 템플릿·스크립트·integration 관리 영역으로 사용하고, Q250 도메인 명세는 `.specs/`에서 계속 관리한다. `uv` 실행 여부 자체는 이번 출력에 없으므로 별도 확인 항목으로 남긴다.

## 2. Robotics 도구

| 항목 | 결과 | 판정 |
|---|---|---|
| ROS 2 | `/opt/ros/humble/bin/ros2` | PASS |
| ROS 2 배포판 | Humble 경로 | PASS, 버전 명령 추가 확인 필요 |
| colcon | `/usr/bin/colcon` | PASS |
| Gazebo CLI | `/usr/bin/gz` | PASS, `gz sim --version` 추가 확인 필요 |
| legacy `gazebo` | 미확인 | NOT_REQUIRED if Gazebo Harmonic/gz sim 사용 |
| Docker | Windows Docker Desktop 경로 | PARTIAL, daemon/Compose/GPU 확인 필요 |
| Git | `/usr/bin/git` | PASS |
| CMake | `/usr/bin/cmake` | PASS |
| Ninja | 미확인 | GAP |
| ccache | 미확인 | OPTIONAL/PERFORMANCE |
| MAVLink Router | 미확인 | GAP for operation |
| Micro-XRCE-DDS-Agent | 미확인 | GAP for PX4↔ROS 2 bridge |
| QGroundControl | 미확인 | GAP for FC operation/firmware |

## 3. 아직 확인하지 않은 필수 항목

다음 항목은 이번 inventory에 포함되지 않아 설치 완료 또는 운용 가능으로 판정하지 않는다.

- Ubuntu release와 WSL2 systemd
- CPU/RAM/디스크 여유
- NVIDIA GPU, Windows driver, WSL CUDA, `nvidia-smi`
- Docker daemon: `docker info`
- Docker Compose: `docker compose version`
- Docker GPU passthrough
- ROS 2 environment source와 `ros2 doctor`
- Gazebo 실제 버전과 headless 실행
- PX4-Autopilot v1.15 source/recursive submodules
- PX4 SITL build
- `px4_msgs` v1.15
- Micro-XRCE-DDS-Agent 연결
- `/fmu/out/*` topics
- Python venv 및 프로젝트 의존성
- 데이터셋·체크포인트·모델 복원 및 SHA-256
- 실제 FC preflight

## 4. 현재 준비도

- SpecKit 문서 동기화: `PASS`
- Hermes 설치: `PASS`
- 공식 Spec Kit CLI: `BLOCKED`
- ROS 2/colcon/gz 기본 도구: `PASS`
- Docker: `PARTIAL`
- PX4/ROS 2 bridge: `BLOCKED or NOT_CHECKED`
- 데이터 준비: `NOT_CHECKED`
- Hardware: `NOT_CHECKED`
- 전체: `BLOCKED — SpecKit prerequisite and runtime inventory incomplete`

실제 FC 검증 전 최고 허용 판정은 `SIMULATION_READY`다.
