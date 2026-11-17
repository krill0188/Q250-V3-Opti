# Q250-V3-Opti 타 PC 준비도 점검 계획

## 0. Hermes를 통한 SpecKit 운영

타겟 PC에는 Hermes Agent가 이미 설치되어 있으므로, 타겟 PC의 모든 Q250 작업은 Hermes를 진입점으로 사용한다.

1. Hermes에서 Q250 저장소를 프로젝트 작업 디렉터리로 연다.
2. 첫 작업에서 `AGENTS.md`, `.specs/spec.md`, `.specs/plan.md`, `.specs/tasks.md`를 읽는다.
3. 현재 작업에 해당하는 feature spec을 찾는다.
4. 작업 시작 전 `TPC-*` 또는 기존 `T-*` 작업 ID를 선택한다.
5. Hermes에게 환경 변경을 요청할 때 작업 ID와 DoD를 함께 지정한다.
6. Hermes가 실행한 명령·결과·변경 파일을 작업 항목에 기록한다.
7. 테스트와 수용 기준이 통과하기 전 `PASS`로 변경하지 않는다.

### 타겟 PC에서 최초 실행할 점검

```bash
cd ~/Q250-V3-Opti
hermes --version
hermes doctor
hermes chat -q "이 저장소의 AGENTS.md, .specs/spec.md, .specs/plan.md, .specs/tasks.md를 읽고 TPC-001~TPC-017 기준으로 타겟 PC 환경 점검 계획과 누락 항목만 보고해라. 파일 수정과 실제 FC 명령은 하지 마라."
```

위 명령의 API 출력·로그에는 비밀값이 포함되지 않도록 확인한다. `hermes chat -q`가 프로젝트 컨텍스트를 자동으로 읽지 않는 경우에도, Hermes 세션에서 해당 파일을 먼저 열도록 명시한다.

## 1. 구현 전략

타 PC를 직접 추정하지 않고 다음 순서로 증거를 수집한다.

1. 저장소 기준점 고정
2. 타 PC host inventory 수집
3. OS/드라이버/GPU/CUDA/Docker 계층 확인
4. Python·ROS 2·PX4·Gazebo·MAVLink 도구 확인
5. 프로젝트 checkout 및 설정 검증
6. 데이터셋·모델 전송 패키지 생성
7. 타 PC 복원 후 무결성 검증
8. 처리본 구조·metadata·loader smoke test
9. Docker GPU smoke test
10. ROS 2 build와 PX4 SITL smoke test
11. 결과를 Mac 대조표에 반영
12. SIMULATION_READY 또는 BLOCKED 판정

## 2. 권장 프로파일 분리

### A. 개발/SITL PC

- Windows 11 + WSL2 Ubuntu 22.04 또는 native Ubuntu 22.04
- RTX GPU와 NVIDIA driver/CUDA
- ROS 2 Humble + Gazebo Harmonic
- PX4 v1.15 build 가능
- Docker GPU 가능
- 데이터셋 및 체크포인트 저장 공간: 필수 전송본보다 충분히 큰 여유 공간

### B. Jetson 운용 PC

- JetPack/Ubuntu 호환성 별도 확인
- serial `dialout` 권한
- mavlink-router
- Micro-XRCE-DDS-Agent
- ROS 2 runtime
- FastDDS 설정
- 실제 센서/FC 연결은 read-only preflight부터 시작

두 프로파일을 한 대의 PC에 억지로 동일하게 설치하지 않는다. 개발 PC와 Jetson 운용 장치의 증거를 별도 기록한다.

## 3. 데이터 전송 정책

### 3.1 기본 전송

`package_datasets_for_transfer.sh`의 필수 목록을 기준으로 한다.

- processed/drone_audio
- processed/uzh_fpv
- processed/idf_ds
- processed/ign_fixed_wing
- processed/fixed_wing_attitude
- checkpoints
- preprocessing 설정·metadata

### 3.2 별도 전송

- processed/fpv_analog: 약 55GB, 용량·시간 확인 후 별도 전송
- raw: 재처리 필요 시에만 전송
- navigation_datasets: 사용하는 pipeline이 확정된 경우 전송
- 로컬 LLM: 라이선스와 해시 확인 후 별도 전송

### 3.3 전송 규칙

- Mac 원본은 삭제하지 않는다.
- tar 또는 tar.zst 생성 후 SHA-256 생성
- 타 PC에서 SHA-256 검증 후 압축 해제
- 압축 해제 후 dataset manifest 재생성
- dataset별 파일 수/바이트/metadata/샘플 shape 비교
- 실패 시 학습·SITL 준비 판정 금지

## 4. 검증 단계와 산출물

### 단계 0: 기준선

산출물:

- `readiness-baseline-mac.json`
- `dataset-manifest-mac.json`
- `model-checksums-mac.sha256`
- 저장소 commit/tag

### 단계 1: 타 PC 기본 환경

확인:

- `uname -a`, OS release, architecture
- CPU/RAM/disk
- GPU/driver/CUDA
- Docker daemon 및 NVIDIA runtime
- 네트워크/DNS/USB 권한

산출물:

- `readiness-target-host.json`
- `host-inventory.txt`

### 단계 2: 도구 체인

확인:

- compiler/build: gcc/g++, cmake, ninja, ccache, make
- source: git, curl, wget, jq, rsync, tar, zstd
- runtime: Python, venv, pip
- robotics: ROS 2, colcon, rosdep, Gazebo
- flight: PX4, QGroundControl, pymavlink, MAVSDK
- transport: mavlink-router, Micro-XRCE-DDS-Agent
- developer: VS Code/Remote WSL, Docker Compose

산출물:

- `tool-versions.json`
- missing tool list

### 단계 3: Python

1. 프로젝트 전용 venv 또는 Docker 선택
2. `requirements.txt`, `requirements-finetune.txt`, `bridge/requirements.txt` 설치
3. 각 import와 버전 수집
4. torch CUDA 확인
5. audio/vision/MAVLink smoke test

Mac에서 확인된 경고인 NumPy 2.x/Torch ABI 문제는 타 PC 기준 환경에 복사하지 않고, 타 PC에서 새로 검증한다.

### 단계 4: ROS/PX4

1. ROS 2 Humble source
2. rosdep 초기화·update
3. `ros2_ws/src` dependency resolve
4. `colcon build --symlink-install`
5. PX4 v1.15 recursive checkout
6. Q250 model/params/custom message 확인
7. SITL build

### 단계 5: SITL/통신

1. Gazebo headless 기동
2. PX4 SITL 기동
3. MAVLink heartbeat 확인
4. uXRCE-DDS Agent 기동
5. `/fmu/out/*` topic 확인
6. ROS 2 node discovery 확인
7. 필요 시 MAVSDK/MAVROS2 bridge smoke

ARM/TAKEOFF는 SITL에서도 별도 명령 승인 단계로 관리하고, 환경점검 완료와 혼동하지 않는다.

### 단계 6: 데이터

1. 패키지 SHA-256 검증
2. dataset manifest 비교
3. metadata JSON parse
4. train/val/test 파일 존재 검사
5. NPZ shape/dtype/NaN/Inf 검사
6. loader 1 batch 검사
7. normalizer/scaler pickle 로드 검사
8. checkpoint/model 파일 해시 비교

### 단계 7: 판정

- 모든 필수 단계 PASS: `SIMULATION_READY`
- 데이터만 PASS, robotics tool missing: `DATA_READY_ONLY`
- host/container GPU missing: `CPU_OR_BLOCKED`
- 실제 FC 미확인: `HARDWARE_NOT_VALIDATED`를 반드시 병기

## 5. 위험과 대응

| 위험 | 대응 |
|---|---|
| macOS에서 Linux 스크립트가 실행됨 | 타 PC Linux/WSL2에서만 기준 실행 |
| Python ABI 충돌 | 프로젝트 venv 또는 Docker 고정 |
| CUDA/torch 조합 불일치 | 컨테이너 기준으로 먼저 검증 |
| ROS/PX4 브랜치 불일치 | v1.15와 px4_msgs branch 고정 |
| 55GB fpv_analog 전송 실패 | 기본 package와 분리 |
| 압축 후 파일 누락 | SHA-256 + manifest + shape 검사 |
| WSL2 USB/UDP 문제 | usbipd·방화벽·포트 사전 확인 |
| 실제 FC를 잘못된 포트로 조작 | read-only preflight, 포트 확인 전 명령 금지 |
| QGroundControl 버전 불일치 | 설치 버전과 펌웨어 파일 hash 기록 |
| 문서 경로의 사용자명 하드코딩 | `$HOME`, `$Q250_ROOT` 사용 |

## 6. 완료 조건

- SpecKit 명세의 AC-001~AC-011 증거가 표에 모두 채워짐
- 타 PC에서 재현 명령이 모두 기록됨
- Mac과 타 PC의 차이가 `PASS`, `MISMATCH`, `BLOCKED` 중 하나로 분류됨
- 데이터 전송 후 원본·처리본·모델의 무결성이 검증됨
- 테스트 결과와 Hardware 미검증 한계가 함께 기록됨
