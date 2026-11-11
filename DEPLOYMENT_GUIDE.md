# Q250-V3-Opti 타겟 PC 배포 및 실기체 검증 가이드

> **버전**: v1.1.0  
> **대상**: Windows 11 + WSL2 (Ubuntu 22.04) + ROS 2 Humble  
> **최종 업데이트**: 2024-11-10

---

## 1. 개요

이 문서는 Q250-V3-Opti 하이브리드 드론 시스템(고정익 + FPV, Non-GPS 네비게이션, 전술 음성 제어, 기만 기동)을 **타겟 PC(Windows 11 노트북 + Jetson Orin 탑재 실기체)**에 배포하고, **시뮬레이션 검증 → 실기체 단계별 테스트**를 수행하는 전 과정을 다룹니다.

### 1.1 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────┐
│                    타겟 노트북 (Windows 11 + WSL2)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  데이터셋   │  │  학습/검증  │  │  시뮬레이션 (Gazebo SITL) │ │
│  │  아카이브   │──│  파이프라인  │──│  + PX4 + ROS 2 브리지    │ │
│  └─────────────┘  └─────────────┘  └───────────┬─────────────┘ │
└─────────────────────────────────────────────────┼───────────────┘
                                                  │ WiFi/이더넷
                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    실기체 (Jetson Orin + PX4)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  음성 파이프 │  │  Non-GPS    │  │  기만 기동 실행기       │ │
│  │  라인 (3단계)│  │  네비게이션  │  │  (5가지 패턴)          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 하드웨어 요구사항

### 2.1 타겟 노트북 (개발/시뮬레이션용)

| 구성요소 | 최소 사양 | 권장 사양 |
|----------|-----------|-----------|
| **OS** | Windows 11 Pro 22H2+ | Windows 11 Pro 23H2+ |
| **CPU** | Intel 12세대 8코어 / AMD 7000 8코어 | Intel 14세대 HX 16코어 / AMD 7000 16코어 |
| **RAM** | 32 GB DDR5 | 64 GB+ DDR5 |
| **GPU** | RTX 3060 12GB | RTX 4080/4090 24GB |
| **Storage** | 1 TB NVMe Gen4 | 2 TB+ NVMe Gen4 |
| **네트워크** | WiFi 6 / 1Gbps 이더넷 | WiFi 6E / 2.5Gbps 이더넷 |

### 2.2 실기체 탑재 컴퓨터 (Jetson Orin)

| 구성요소 | 사양 |
|----------|------|
| **모듈** | Jetson AGX Orin 64GB 또는 Orin NX 16GB |
| **OS** | JetPack 6.0 (Ubuntu 22.04 + L4T R36.x) |
| **Storage** | 256 GB+ NVMe (외장 SSD 권장) |
| **주변장치** | 4ch MEMS 마이크 어레이, GPS, IMU, 광학 흐름 카메라, ToF/VIO 센서 |

### 2.3 드론 플랫폼 (Q250 하이브리드)

| 구성요소 | 사양 |
|----------|------|
| **프레임** | 고정익 + 쿼드 틸트로터 하이브리드 (윙스팬 ~2.5m) |
| **비행컨트롤러** | Pixhawk 6X / Cube Orange+ (PX4 v1.14+) |
| **추진** | 틸트 모터 4개 + 푸셔 모터 1개 |
| **센서** | IMU (ICM-42688), 기압계, GPS (M8N), 광학 흐름 (PMW3901), ToF/VIO |
| **통신** | 텔레메트리 (SIK 915MHz), LTE/5G 모뎀, WiFi 6 |

---

## 3. 소프트웨어 환경 구축

### 3.1 Windows 11 + WSL2 설정

```powershell
# PowerShell 관리자 실행
# 1. WSL2 설치
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
wsl --update

# 2. GPU 드라이버 확인 (NVIDIA GPU 필요)
# https://developer.nvidia.com/cuda/wsl 에서 최신 드라이버 설치

# 3. WSL2 메모리/CPU 제한 설정 (.wslconfig)
# %UserProfile%\.wslconfig 생성:
```
[wsl2]
memory=48GB          # 물리 RAM의 75% 이하
processors=12        # 물리 코어 수 이하
swap=8GB
localhostForwarding=true
kernelCommandLine=isolcpus=0
```

```powershell
# 4. WSL 재시작
wsl --shutdown
wsl -d Ubuntu-22.04
```

### 3.2 Ubuntu 22.04 (WSL2) 내부 환경

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 필수 패키지 설치
sudo apt install -y \
    python3.10 python3.10-venv python3-pip \
    git git-lfs build-essential cmake ninja-build \
    libsndfile1 libportaudio2 libopenblas-dev \
    ros-humble-desktop \
    python3-colcon-common-extensions python3-rosdep \
    libeigen3-dev libyaml-cpp-dev nlohmann-json3-dev \
    wget curl unzip zstd

# ROS 2 Humble 설정
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
sudo rosdep init && rosdep update

# Git LFS 초기화
git lfs install
```

### 3.3 Python 가상환경 및 의존성

```bash
# 프로젝트 클론
cd ~
git clone https://github.com/krill0188/Q250-V3-Opti.git
cd Q250-V3-Opti

# Python 3.10 가상환경
python3.10 -m venv .venv
source .venv/bin/activate

# pip 업그레이드
pip install --upgrade pip setuptools wheel

# 핵심 ML/데이터 라이브러리
pip install numpy==1.26.4 scipy pandas tqdm pyyaml
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 오디오 처리 (soundfile 필수!)
pip install soundfile librosa

# 드론/로봇 통신
pip install mavsdk==0.57.0 transforms3d

# 로컬 패키지 설치 (전처리 파이프라인 등)
pip install -e .

# 음성 파이프라인
pip install faster-whisper onnxruntime pvporcupine
pip install huggingface_hub

# 개발 도구
pip install pytest pytest-asyncio black isort mypy tensorboard
```

### 3.4 데이터셋 복원 및 검증

```bash
# 아카이브 다운로드 (rsync/스크래치 디스크 권장)
mkdir -p ~/data/drone_datasets
cd ~/data/drone_datasets

# 체크섬 검증 후 압축 해제
for f in ~/q250_*.tar.zst; do
    sha256sum -c "$f.sha256" && tar -I zstd -xf "$f"
done

# 데이터셋 로드 테스트
cd ~/Q250-V3-Opti
source .venv/bin/activate
python3 -c "
from src.preprocessing.datasets import MultiSensorDataset
from pathlib import Path

for ds in ['idf_ds', 'ign_fixed_wing', 'uzh_fpv', 'fpv_analog', 'fixed_wing_attitude']:
    p = Path(f'~/data/drone_datasets/{ds}/processed').expanduser()
    if p.exists():
        for split in ['train', 'val', 'test']:
            try:
                ds_obj = MultiSensorDataset(p / split)
                print(f'✅ {ds}/{split}: {len(ds_obj)} samples, sensors={list(ds_obj.sensor_data.keys())}')
            except Exception as e:
                print(f'❌ {ds}/{split}: {e}')
"
```

---

## 4. ROS 2 워크스페이스 빌드

### 4.1 PX4-Autopilot 서브모듈 동기화

```bash
cd ~/Q250-V3-Opti
git submodule update --init --recursive
```

### 4.2 ROS 2 워크스페이스 빌드

```bash
cd ~/Q250-V3-Opti/ros2_ws
colcon build --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --packages-select q250_msgs q250_bridge q250_nongps q250_dive q250_deception

source install/setup.bash
echo "source ~/Q250-V3-Opti/ros2_ws/install/setup.bash" >> ~/.bashrc
```

### 4.3 커스텀 메시지 확인

```bash
ros2 interface show q250_msgs/msg/VoiceCommand
ros2 interface show q250_msgs/msg/NonGPSState
ros2 interface show q250_msgs/msg/DiveTrajectory
ros2 interface show q250_msgs/msg/DeceptionCmd
ros2 interface show q250_msgs/msg/RiskAssessment
ros2 interface show q250_msgs/msg/ModeState
```

---

## 5. 시뮬레이션 환경 (Gazebo SITL + PX4)

### 5.1 PX4 SITL 빌드

```bash
cd ~/Q250-V3-Opti/PX4-Autopilot
# 하이브리드 기체 설정 필요 (Q250 하이브리드용)
make px4_sitl gz_x500
# 또는 커스텀 기체: make px4_sitl gz_q250_hybrid
```

### 5.2 MicroXRCE-DDS Agent (PX4 ↔ ROS 2 브리지)

```bash
# 별도 터미널에서 실행
MicroXRCEAgent udp4 -p 8888
```

### 5.3 데이터셋 브리지 노드 실행

```bash
# 터미널 1: PX4 SITL + Gazebo
cd ~/Q250-V3-Opti/PX4-Autopilot
make px4_sitl gz_x500

# 터미널 2: MicroXRCE-DDS Agent
MicroXRCEAgent udp4 -p 8888

# 터미널 3: ROS 2 데이터셋 브리지 + 시뮬레이션 노드
cd ~/Q250-V3-Opti
source .venv/bin/activate
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash

# UZH-FPV 데이터셋으로 Non-GPS 시뮬레이션
python3 src/simulation/dataset_bridge.py \
    ~/data/drone_datasets/uzh_fpv/processed train \
    --rate 100

# 별도 터미널: Non-GPS 네비게이션 노드
ros2 run q250_nongps nongps_navigator \
    --vio_topic /camera/vio/pose \
    --flow_topic /camera/optical_flow \
    --imu_topic /fmu/imu/out
```

---

## 6. 음성 파이프라인 실행 (3단계)

### 6.1 하드웨어 마이크 어레이 연결

```
4ch MEMS 마이크 (MSM261S4030H0 또는 ICS-43434)
├── 20cm 마스트 중앙 장착
├── 5cm 반경 원형 배치 (0°, 90°, 180°, 270°)
├── 진동 격리 마운트 (고무/실리콘)
├── 이중 윈드실드 (폼 + 퍼)
└── USB/I2S → Jetson Orin 연결
```

### 6.2 음성 데몬 실행

```bash
# 실기체 Jetson에서 실행
cd ~/Q250-V3-Opti
source .venv/bin/activate

python3 -m voice.voice_daemon \
    --config config/hardware_profiles.yaml \
    --model models/whisper_tiny_int8.ct2 \
    --kws models/kws_ds_cnn_int8.tflite \
    --denoiser models/deepfilternet3.onnx \
    --ros_topic /q250/voice_command \
    --log_level INFO
```

### 6.3 음성 명령 테스트

```bash
# 기본 명령
"이륙" / "착륙" / "호버링" / "전진 2미터" / "좌회전 90도"

# 전술 명령 (한국군 좌표계)
"알파 브라보 1234 5678 이동"
"델타 골프 5678 1234 공격"
"우리 편 300미터 북쪽 정찰"

# 긴급 명령 (KWS <5ms)
"비상정지" / "즉시복귀" / "강제착륙"
```

---

## 7. Non-GPS 네비게이션 검증

### 7.1 학습 파이프라인

```bash
cd ~/Q250-V3-Opti
source .venv/bin/activate

# 1차 학습 (UZH-FPV 데이터셋)
python3 src/training/train_nongps.py \
    --data_dir ~/data/drone_datasets/uzh_fpv/processed \
    --epochs 100 --batch_size 32 --lr 1e-3 \
    --seq_len 100 --hidden 256 \
    --output_dir ~/q250_checkpoints/nongps \
    --val_split 0.15 --test_split 0.15

# TensorBoard 모니터링
tensorboard --logdir ~/q250_checkpoints/nongps/logs
```

### 7.2 모델 평가

```bash
# 실내 VICON 환경에서 평가
ros2 run q250_nongps vio_evaluator \
    --gt_topic /vicon/q250/pose \
    --est_topic /q250/nongps/pose \
    --duration 300 \
    --output ~/flight_logs/vio_eval.csv
```

---

## 8. 실기체 단계별 검증 체크리스트

| Phase | 환경 | 검증 항목 | 도구/명령 | 합격 기준 |
|-------|------|-----------|-----------|-----------|
| **1. 벤치** | 실내, 프로펠러 제거 | 센서 100Hz 동기화, 음성 파이프라인 지연 | `ros2 topic hz /fmu/imu/out /fmu/gps/out`<br>`python3 -m voice.latency_test` | 센서 동기화 ±5ms<br>음성 e2e < 500ms (KWS < 5ms) |
| **2. 실내 비행** | 모션캡처/VICON | VIO 위치 RMSE, 음성 명령 성공률 | `ros2 run q250_nongps vio_evaluator`<br>`scripts/voice_command_tester.py` | VIO RMSE < 0.5m (300초)<br>명령 성공률 > 95% |
| **3. 야외 GPS** | 안전고도 50m+ | EKF2 융합 정확도, 다이빙 궤적 추적 | `ros2 run q250_nongps ekf2_validator`<br>`ros2 run q250_dive trajectory_tracker` | EKF2 위치 오차 < 1.0m<br>다이빙 추적 < 2.0m |
| **4. 기만 기동** | 위협 시뮬레이션 | 5패턴 안전제한 준수, 지속시간 | `ros2 run q250_deception deception_executor` | 고도≥50m, 강하각≤80°<br>속도≤80m/s, 시간<60s |

### 8.1 Phase 1: 벤치 테스트 스크립트

```bash
#!/bin/bash
# scripts/bench_test.sh

echo "=== Phase 1: 벤치 테스트 ==="

# 1. 센서 bringup
ros2 launch q250_bringup sensor_bringup.launch.py hardware_profile:=hybrid_drone_1 &
sleep 5

# 2. 센서 주파수 확인
echo "센서 주파수:"
ros2 topic hz /fmu/imu/out /fmu/gps/out /fmu/magnetometer/out /fmu/velocity/out

# 3. 전처리 파이프라인 테스트
python3 -c "
from src.preprocessing.core.normalizer import SensorNormalizer
from src.preprocessing.datasets import MultiSensorDataset
ds = MultiSensorDataset('~/data/flight_logs/test_flight')
print('Sensors:', ds.sensor_names)
print('Sample keys:', ds[0].keys())
"

# 4. 음성 파이프라인 지연 측정
python3 -c "
from voice.voice_command_engine import VoiceCommandEngine
import numpy as np, time
engine = VoiceCommandEngine('config/hardware_profiles.yaml')
audio = np.random.randn(16000).astype(np.float32)
t0 = time.perf_counter()
result = engine.process_audio_array(audio)
print(f'Latency: {(time.perf_counter()-t0)*1000:.1f}ms')
print(f'Result: {result}')
"
```

### 8.2 Phase 2: 실내 비행 테스트

```bash
#!/bin/bash
# scripts/indoor_test.sh

echo "=== Phase 2: 실내 비행 (VICON) ==="

# VIO 평가 (300초)
ros2 run q250_nongps vio_evaluator \
    --gt_topic /vicon/q250/pose \
    --est_topic /q250/nongps/pose \
    --duration 300 \
    --output ~/flight_logs/vio_eval.csv

# 음성 명령 테스트
python3 scripts/voice_command_tester.py --commands commands.yaml
```

### 8.3 Phase 3: 야외 GPS 비행

```bash
#!/bin/bash
# scripts/outdoor_test.sh

echo "=== Phase 3: 야외 GPS 비행 ==="

# EKF2 융합 검증
ros2 run q250_nongps ekf2_validator \
    --gps_topic /fmu/gps/out \
    --vio_topic /q250/nongps/pose \
    --output ~/flight_logs/ekf2_validation.csv

# 다이빙 궤적 테스트 (시뮬레이션 검증 후)
ros2 run q250_dive trajectory_tracker \
    --pattern SPIRAL_DIVE \
    --start_alt 100 --max_angle 60 \
    --log ~/flight_logs/dive_spiral.csv
```

### 8.4 Phase 4: 기만 기동 실기체 검증

```bash
#!/bin/bash
# scripts/deception_test.sh

echo "=== Phase 4: 기만 기동 검증 ==="

for pattern in SPIRAL_DIVE SINE_DIVE RANDOM_JINK FAKE_CRASH MULTI_PULSE; do
    for run in 1 2 3; do
        echo "Testing $pattern run $run..."
        ros2 run q250_deception deception_executor \
            --pattern $pattern \
            --threat_simulated \
            --log_dir ~/flight_logs/deception_${pattern}_run${run}
        sleep 30  # 쿨다운
    done
done
```

---

## 9. 문제 해결 가이드

| 증상 | 원인 | 해결 |
|------|------|------|
| `torch` import 시 NumPy 경고 | NumPy 2.x + 구버전 PyTorch | `pip install numpy==1.26.4` 또는 PyTorch 재빌드 |
| `soundfile` import 실패 | libsndfile 미설치 | `sudo apt install libsndfile1` |
| ROS 2 토픽 미발행 | MicroXRCE-DDS Agent 미실행 | `MicroXRCEAgent udp4 -p 8888` 실행 확인 |
| 데이터셋 로드 시 메모리 부족 | 청크 파일 미사용 | `MultiSensorDataset` 자동 청크 병합 확인 |
| 음성 지연 > 500ms | KWS 미사용, Whisper base 모델 | `tiny.int8` 모델 + KWS 활성화 |
| Gazebo 실행 불가 | GPU 드라이버/WLSg 미설정 | NVIDIA WSL 드라이버 재설치 |
| PX4 빌드 실패 | 서브모듈 미동기화 | `git submodule update --init --recursive` |

---

## 10. CI/CD 파이프라인

```yaml
# .github/workflows/hardware_validation.yml
on:
  schedule:
    - cron: '0 2 * * 0'  # 주간
  workflow_dispatch:

jobs:
  bench-test:
    runs-on: [self-hosted, jetson-orin]
    steps:
      - uses: actions/checkout@v4
      - name: Build ROS 2 workspace
        run: |
          source /opt/ros/humble/setup.bash
          colcon build --symlink-install
      - name: Run bench tests
        run: python3 -m pytest tests/hardware/ -v
      
  simulation-test:
    runs-on: ubuntu-latest
    container: px4io/px4-dev-simulation:latest
    steps:
      - uses: actions/checkout@v4
      - name: Gazebo SITL + dataset bridge
        run: |
          make px4_sitl gz_x500 &
          sleep 30
          python3 src/simulation/dataset_bridge.py ~/data/uzh_fpv/processed train
      
  flight-test:
    runs-on: [self-hosted, q250-drone]
    if: github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4
      - name: Pre-flight checklist
        run: python3 scripts/preflight_check.py
      - name: Execute flight test plan
        run: python3 scripts/flight_test_runner.py --plan flight_plan.yaml
```

---

## 11. 타겟 PC 이전 시 필수 체크리스트

| 항목 | 확인 명령 | 예상 결과 |
|------|-----------|-----------|
| Python + PyTorch CUDA | `python -c "import torch; print(torch.cuda.is_available())"` | `True` |
| ROS 2 + 커스텀 메시지 | `ros2 interface show q250_msgs/msg/VoiceCommand` | 메시지 정의 출력 |
| 데이터셋 무결성 | `sha256sum ~/data/drone_datasets/*/processed/**/*.npz` | 원본과 일치 |
| 음성 모델 파일 | `ls ~/Q250-V3-Opti/models/` | whisper, kws, denoiser 존재 |
| 하드웨어 프로파일 | `cat config/hardware_profiles.yaml` | hybrid_drone_1 정의 |
| PX4 펌웨어 빌드 | `cd PX4-Autopilot && make px4_sitl gz_x500` | 빌드 성공 |

---

## 12. 참고 자료

- **Q250-V3-Opti GitHub**: https://github.com/krill0188/Q250-V3-Opti
- **PX4 문서**: https://docs.px4.io/main/en/
- **ROS 2 Humble 문서**: https://docs.ros.org/en/humble/
- **Gazebo Harmonic**: https://gazebosim.org/docs/harmonic
- **Jetson Orin 개발자 가이드**: https://developer.nvidia.com/embedded/jetson-orin
- **faster-whisper**: https://github.com/guillaumekln/faster-whisper
- **DeepFilterNet3**: https://github.com/Rikorose/DeepFilterNet

---

> **작성자**: Q250-V3-Opti 개발팀  
> **문의**: GitHub Issues 또는 프로젝트 Slack 채널