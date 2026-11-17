# Q250-V3-Opti 타 PC 운용 준비도 점검 명세

- **문서 유형**: SpecKit Feature Specification
- **대상**: 타 PC(운용·개발·데이터 처리 PC)와 현재 Mac의 동등성 비교
- **기준 저장소**: `Q250-V3-Opti`
- **기준 커밋**: `1e2ca47`
- **기준 태그**: `v0.5.0`
- **기준일**: 2026-11-18 KST
- **안전 등급**: 실제 FC 연결·ARM·비행 명령 없이 환경과 데이터만 점검

## 1. 목적

타 PC에서 Q250-V3-Opti를 재현 가능한 상태로 구축한다. 다음을 하나의 추적 가능한 준비도 판정으로 관리한다.

1. 운용 필수 소프트웨어와 개발 도구
2. PX4·ROS 2·Gazebo·MAVLink·uXRCE-DDS 통신 계층
3. ML·음성·비전·데이터 전처리 Python 환경
4. 데이터셋 원본·처리본·메타데이터·체크섬·체크포인트
5. ROS 2 워크스페이스와 프로젝트 설정
6. SITL·Mock·Hardware를 구분한 검증 증거
7. 현재 Mac과 타 PC의 차이 및 차이 해소 작업

## 2. 범위

### 포함

- 타 PC 운영체제/커널/GPU/CUDA/드라이버/디스크/메모리
- WSL2와 Ubuntu 22.04 또는 동등한 Linux 실행 계층
- ROS 2 Humble, Gazebo Harmonic, PX4 v1.15
- MAVLink Router, Micro-XRCE-DDS-Agent, MAVSDK, MAVROS2
- Docker/Compose 및 NVIDIA Container Toolkit
- Python 의존성, C/C++ 빌드 도구, VS Code 도구
- 음성·VIO·Optical Flow·LiDAR·EKF2 개발 도구
- 데이터셋 전송·복원·무결성 검증·전처리·학습 입력 검증
- QGroundControl은 운용·펌웨어 플래시 도구로 별도 확인

### 제외

- 실제 FC에 대한 ARM, TAKEOFF, LAND, PARAM_SET, MISSION 실행
- 실제 비행 승인 또는 Hardware PASS 판정
- 비밀값·토큰·SSH 개인키·API 키의 수집 및 문서화
- `Q250-V3-Opti`와 별도인 `Swarm OpS GCS` 프로젝트 상태

## 3. 준비도 상태 규칙

- `PASS`: 명령 실행 증거와 기대 결과가 모두 기록됨
- `PARTIAL`: 일부 기능만 확인됨. 운용 가능 판정에는 사용하지 않음
- `BLOCKED`: 필수 의존성이 없어 후속 검증 불가
- `MISMATCH`: Mac 기준과 타 PC 기준이 다르고 해결책이 필요함
- `NOT_CHECKED`: 타 PC에서 아직 점검하지 않음
- `NOT_APPLICABLE`: 해당 프로파일에서 사용하지 않음

전체 판정은 다음 조건을 모두 만족해야 `READY`다.

- 운용 필수 소프트웨어 `PASS`
- ROS 2/PX4/SITL 통신 스모크 테스트 `PASS`
- 데이터셋 필수 묶음의 체크섬 검증 `PASS`
- 처리본 train/val/test와 metadata 검증 `PASS`
- 체크포인트·모델 파일 존재 및 해시 기록 `PASS`
- 실제 FC 검증이 없으면 전체 상태는 `SIMULATION_READY`까지만 허용

## 4. Hermes Agent·SpecKit 운영 전제

타겟 PC에는 Hermes Agent가 이미 설치되어 있다는 사용자 확인이 있다. 따라서 타겟 PC 점검에서 Hermes 자체를 신규 설치 대상으로 보지 않고, 다음 두 항목을 분리해 확인한다.

1. **Hermes Agent 설치 상태**: `hermes --version`, `hermes doctor`, 실제 실행 및 프로젝트 경로 접근
2. **SpecKit 운영 상태**: 저장소의 `.specs/` 문서와 `AGENTS.md`를 Hermes가 읽고 작업 기준으로 적용하는지 확인

Hermes 설치와 SpecKit 설치는 같은 것이 아니다. Hermes가 설치되어 있어도 SpecKit CLI/템플릿/확장 기능의 설치 여부는 별도 확인한다. 이 프로젝트의 최소 SpecKit 운영 기준은 저장소에 다음 문서가 존재하고 Hermes 작업 컨텍스트에서 우선 읽히는 것이다.

- `.specs/spec.md`
- `.specs/plan.md`
- `.specs/tasks.md`
- `.specs/006-target-pc-readiness/spec.md`
- `.specs/006-target-pc-readiness/plan.md`
- `.specs/006-target-pc-readiness/tasks.md`
- `AGENTS.md` 또는 프로젝트 운영 규칙 파일

Hermes 설정·인증정보는 타겟 PC의 기존 설정을 보존한다. API 키, 토큰, 비밀번호, SSH 개인키는 점검 결과에 기록하지 않는다.

### Hermes 수용 기준

- `hermes --version` 실행 성공
- `hermes doctor` 결과를 비밀값 없이 보관
- Hermes가 Q250 저장소를 현재 작업 디렉터리로 열 수 있음
- Hermes가 `.specs/tasks.md`를 단일 작업 기준으로 읽음
- Hermes 작업 요청에 대해 먼저 관련 `spec.md`와 `plan.md`를 참조함
- 실제 코드·환경 변경 전 SpecKit 작업 ID를 지정함
- 작업 후 테스트 결과와 변경 파일을 작업 항목에 연결함

## 5. 환경 프로파일

### 4.1 타 PC 권장 프로파일

- Windows 11 + WSL2
- WSL 배포판: Ubuntu 22.04
- NVIDIA GPU: RTX 5070 8GB 이상 권장
- CUDA: 12.1 계열
- ROS 2: Humble
- Gazebo: Harmonic
- PX4: v1.15
- Python: 프로젝트의 고정 가상환경 또는 Docker 이미지 사용
- Docker Desktop/Engine + NVIDIA Container Toolkit
- USB/IP: FC·Jetson·Silvus·모뎀 연결 시 `usbipd`

### 4.2 현재 Mac 관찰 프로파일

- macOS 13.7.8, Intel x86_64
- Python 3.9.4
- Git/Node/npm/Docker CLI 설치
- ROS 2, colcon, Gazebo, PX4 CLI, MAVLink Router, MicroXRCEAgent, QGroundControl CLI 미확인
- Docker 서버 응답 없음: Docker Desktop/daemon 실행 증거 없음
- Python 패키지 일부 설치
- NVIDIA CUDA 환경 없음
- 데이터셋과 일부 체크포인트는 Mac 로컬에 존재

Mac은 데이터·소스 준비 기준으로 사용하고, Linux/WSL2 타 PC를 운용·SITL 기준으로 사용한다. Mac에서 도구가 없다는 사실만으로 프로젝트 결함으로 판정하지 않는다.

## 5. 기능 요구사항

### FR-001 환경 식별
타 PC 점검기는 OS, 커널, 아키텍처, CPU, RAM, GPU, GPU 드라이버, CUDA, 디스크, 네트워크, 사용자를 기록해야 한다.

### FR-002 핵심 도구 확인
다음 실행 파일과 버전을 확인해야 한다.

- `git`, `python3`, `pip`, `cmake`, `ninja`, `ccache`
- `docker`, `docker compose`
- `ros2`, `colcon`, `rosdep`
- `gz`/Gazebo, `make`, `ninja`
- `mavlink-routerd`, `MicroXRCEAgent`
- `QGroundControl` 설치 상태
- `cuda`/`nvidia-smi`/NVIDIA Container Toolkit

### FR-003 Python 환경 확인
`requirements.txt`, `requirements-finetune.txt`, `bridge/requirements.txt`를 기준으로 설치·import·버전을 확인한다. CPU/Mac용 패키지와 CUDA용 패키지를 같은 환경에 무분별하게 섞지 않는다.

필수 영역:

- NumPy, pandas, SciPy, scikit-learn
- PyTorch, torchvision, torchaudio
- OpenCV
- MAVSDK, pymavlink
- faster-whisper, ctranslate2
- librosa, soundfile, sounddevice
- ONNX/ONNX Runtime GPU
- transformers, PyYAML, pydantic, tqdm

### FR-004 ROS 2/PX4 계층 확인
다음 버전과 빌드를 확인한다.

- ROS 2 Humble 환경 source
- `ros2 doctor` 실행
- `rosdep update` 상태
- `ros2_ws`의 Q250 패키지 build
- `px4_msgs` v1.15 호환
- `px4_ros_com` 및 Micro-XRCE-DDS-Agent v2.4.3
- PX4-Autopilot v1.15 recursive checkout
- `q250_v3_opti` 모델·파라미터·custom MAVLink dialect

### FR-005 통신 계층 확인
실제 FC 명령 없이 다음을 확인한다.

- MAVLink Router 프로세스/설정 파일
- uXRCE-DDS Agent 프로세스/포트
- ROS 2 `/fmu/out/*` discovery 또는 SITL 토픽
- UDP 포트 충돌 여부: 14540, 14550, 5760
- ROS_DOMAIN_ID와 RMW 구현
- 네트워크 방화벽/WSL2 포트 전달

### FR-006 데이터셋 준비 확인
데이터셋은 원본과 처리본을 구분하고, 각 처리본에 train/val/test 및 metadata가 있어야 한다.

필수 처리본:

- `drone_audio` binary/multiclass
- `uzh_fpv`
- `idf_ds`
- `ign_fixed_wing`
- `fixed_wing_attitude`

선택/대용량:

- `fpv_analog`: 약 55GB급으로 기본 전송에서 제외 가능하나 별도 상태 기록 필수
- `navigation_datasets`
- 원본 데이터셋: 재처리 목적일 때만 전송

### FR-007 데이터 무결성
전송 묶음에는 다음이 있어야 한다.

- 파일 목록
- 생성 시각
- 소스 경로
- 데이터셋별 크기
- SHA-256 통합 파일
- 처리본 metadata
- 체크포인트·모델 해시

압축 해제 후 타 PC에서 `sha256sum -c` 및 파일 수/바이트 수 비교를 수행한다.

### FR-008 모델·체크포인트 확인
다음 파일을 타 PC에 명시적으로 배치하고 해시를 비교한다.

- `checkpoints/binary/best_model.pth`
- `checkpoints/multiclass/best_model.pth`
- `models/denoising/deepfilter.onnx`
- `models/denoising/deepfilter-auxiliary.bin`
- 필요 시 로컬 LLM GGUF: 문서의 모델 경로·라이선스·해시를 별도 등록

### FR-009 재현 가능한 검증
환경 점검 결과는 사람이 읽는 Markdown과 기계 판독 가능한 JSON으로 저장한다. 검증 결과에는 명령, exit code, timestamp, host identity, 결과, 비고를 포함한다.

### FR-010 안전 경계
환경 점검과 SITL 검증은 실제 FC 운용 증거와 분리한다. HEARTBEAT 또는 SITL 통신 확인만으로 Hardware PASS를 만들지 않는다.

## 6. 수용 기준

- AC-001 타 PC 환경 인벤토리의 필수 항목 누락 없음
- AC-002 모든 필수 도구가 버전과 함께 PASS 또는 명시적 BLOCKED로 기록됨
- AC-003 Docker GPU 컨테이너에서 `torch.cuda.is_available()`가 기대값과 일치
- AC-004 ROS 2 workspace가 `colcon build --symlink-install`을 통과
- AC-005 PX4 v1.15 SITL과 Gazebo가 기동되고 Q250 모델이 로드됨
- AC-006 MAVLink/ROS 2 bridge의 토픽 또는 heartbeat가 제한 시간 안에 확인됨
- AC-007 필수 처리 데이터셋의 train/val/test와 metadata가 모두 존재
- AC-008 전송 후 SHA-256 및 파일 수/크기가 Mac 기록과 일치
- AC-009 체크포인트·모델 해시가 Mac 기록과 일치
- AC-010 실제 FC 조작 없이 SIMULATION_READY 판정을 낼 수 있음
- AC-011 Hardware READY는 실제 FC preflight 및 별도 승인 없이는 발행하지 않음

## 7. 현재 확인된 Mac 기준 증거

- 데이터셋 루트: `~/data/drone_datasets`
- 원본/처리본 전체 파일 크기: 약 59.5GB processed 포함, 원본별 별도 존재
- 확인된 주요 원본: fixed_wing_attitude, fpv_analog, idf_ds, ign_fixed_wing, navigation_datasets, uzh_fpv
- 처리본 metadata와 train/val/test가 확인된 주요 데이터셋: fixed_wing_attitude, fpv_analog, idf_ds, ign_fixed_wing, uzh_fpv 및 drone_audio 경로
- 체크포인트·denoising 모델 해시는 별도 비교표에 기록
- Mac Python 환경에서 NumPy 2.0.2와 Torch 2.2.2 import 시 NumPy ABI 경고가 발생
- Mac 환경에서 `librosa` import 실패
- 현재 Mac은 ROS 2/SITL/Hardware 운용 준비 완료로 판정하지 않음

## 8. 비기능 요구사항

- 비밀값을 보고서·로그·패키지에 포함하지 않는다.
- 원본 데이터셋은 이동 전에 보존하고 복사 후 검증한다.
- 전송 중 원본 삭제 금지.
- 프로젝트 경로는 타 PC에서 환경변수로 지정하고 사용자명 하드코딩을 피한다.
- Linux 기준 스크립트는 macOS에서 성공했다고 Linux 운용 가능으로 해석하지 않는다.
- 모든 판정은 명령 출력 또는 파일 해시 증거를 남긴다.
