# Q250-V3-Opti 개발 환경 가이드

## 🖥️ 대상 환경
- **OS**: Ubuntu 22.04 LTS (WSL2 권장)
- **GPU**: NVIDIA RTX 5070 8GB VRAM
- **CUDA**: 12.1+
- **드라이버**: 550+
- **ROS 2**: Humble Hawksbill
- **Python**: 3.11+

---

## 🐳 Docker 개발 환경 (권장)

### 빠른 시작
```bash
# 1. 저장소 클론
git clone https://github.com/krill0188/Q250-V3-Opti.git
cd Q250-V3-Opti

# 2. Docker 이미지 빌드 (최초 1회, ~10분)
docker compose build q250-dev

# 3. 개발 컨테이너 실행
docker compose up -d q250-dev

# 4. 컨테이너 접속
docker exec -it q250-dev bash
```

### 프로파일별 실행
```bash
# 기본 개발 환경 (Jupyter, TensorBoard 포함)
docker compose --profile dev up -d

# 시뮬레이션 환경 (PX4 SITL + Gazebo)
docker compose --profile simulation up -d

# MAVROS2 브릿지
docker compose --profile bridge up -d

# 전체 스택
docker compose --profile dev --profile simulation --profile bridge up -d
```

### 컨테이너 내부 유용한 명령어
```bash
# 빌드/테스트
colcon-build          # 전체 워크스페이스 빌드
colcon-test           # 테스트 실행
pytest-voice          # 음성 파이프라인 테스트
pytest-bridge         # 브릿지 테스트
bridge-test           # 브릿지 구조 검증

# 음성 파이프라인
asr-test              # 실시간 ASR 테스트 (마이크 필요)
asr-test-small        # 설정 확인만

# MAVLink 메시지 확인
mavlink-check         # 커스텀 메시지 ID/클래스 확인

# Git/개발
ll, la, .., ...       # 탐색 단축키
```

---

## 🛠️ 수동 설치 (Docker 미사용 시)

### 1. 시스템 패키지
```bash
sudo apt update && sudo apt install -y \
    build-essential cmake ninja-build pkg-config \
    python3 python3-pip python3-venv python3-dev \
    git curl wget vim tmux htop \
    portaudio19-dev libasound2-dev \
    lsb-release gnupg2 software-properties-common
```

### 2. ROS 2 Humble
```bash
# ROS 2 저장소 추가
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    | sudo gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/ros2.list

sudo apt update && sudo apt install -y \
    ros-humble-ros-base \
    ros-humble-mavros \
    ros-humble-mavros-msgs \
    ros-humble-mavros-extras \
    ros-humble-tf-transformations \
    python3-colcon-common-extensions \
    python3-rosdep

sudo rosdep init && rosdep update
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
```

### 3. NVIDIA 드라이버/CUDA
```bash
# 드라이버 550+ 확인
nvidia-smi

# CUDA 12.1 툴킷 (이미 설치되어 있다면 스킵)
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update && sudo apt install -y cuda-toolkit-12-1

# 환경 변수
echo 'export PATH=/usr/local/cuda-12.1/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
```

### 4. Python 패키지
```bash
# 가상환경 생성
python3 -m venv ~/q250-venv
source ~/q250-venv/bin/activate

# PyTorch (CUDA 12.1)
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# ML/오디오
pip install faster-whisper ctranslate2 onnx onnxruntime-gpu onnxsim \
    librosa soundfile scikit-learn scipy numpy pandas \
    opencv-python-headless tensorboard pydantic pyyaml tqdm sounddevice

# MAVSDK/MAVROS2
pip install mavsdk==1.0.0 pymavlink
```

### 5. 우리 코드 설정
```bash
# 작업 디렉토리
cd ~/Q250-V3-Opti

# MAVLink 커스텀 메시지 생성
mkdir -p generated/mavlink
python -m pymavlink.tools.mavgen \
    --lang=Python --wire-protocol=2.0 \
    --output=generated/mavlink/python \
    q250_msgs/voice_control.xml

# C++ 도 생성 (필요시)
python -m pymavlink.tools.mavgen \
    --lang=C++11 --wire-protocol=2.0 \
    --output=generated/mavlink/cpp \
    q250_msgs/voice_control.xml

# PYTHONPATH 설정
echo 'export PYTHONPATH=~/Q250-V3-Opti:$PYTHONPATH' >> ~/.bashrc
echo 'export MAVLINK_DIALECT=voice_control' >> ~/.bashrc
source ~/.bashrc
```

---

## ✅ 환경 검증

### 자동 검증 스크립트
```bash
# 타겟 PC 전용 환경 체크
bash check_env_q250.sh
```

### 수동 확인
```bash
# 1. GPU/CUDA
nvidia-smi
python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0))"

# 2. ROS 2
source /opt/ros/humble/setup.bash
ros2 doctor

# 3. MAVSDK
python -c "import mavsdk; print('MAVSDK:', mavsdk.__version__)"

# 4. MAVROS2
ros2 pkg list | grep mavros

# 5. 우리 패키지
python -c "
import sys
sys.path.insert(0, 'generated/mavlink')
import python as m
print('VOICE messages:', [k for k in dir(m) if 'VOICE' in k])
"

# 6. 음성 파이프라인 (모델 다운로드 시간 소요)
cd ~/Q250-V3-Opti
OMP_NUM_THREADS=1 python voice/realtime_asr_pipeline.py
# "Listening..." 뜨면 마이크 테스트, Ctrl+C로 종료
```

---

## 📁 프로젝트 구조
```
Q250-V3-Opti/
├── Dockerfile                 # 개발 환경 이미지
├── docker-compose.yml         # 멀티 컨테이너 오케스트레이션
├── docker-entrypoint.sh       # 컨테이너 진입점
├── check_env_q250.sh          # 타겟 PC 환경 검증
├── .github/workflows/ci.yml   # GitHub Actions CI
├── bridge/                    # MAVSDK + MAVROS2 듀얼 브릿지
│   ├── dual_bridge.py         # 메인 브릿지 클래스
│   ├── requirements.txt       # 의존성
│   └── test_bridge.py         # 구조 검증 테스트
├── voice/                     # 음성 파이프라인
│   ├── realtime_asr_pipeline.py  # faster-whisper + VAD
│   └── voice_command_engine.py   # 명령 파싱 (기존)
├── q250_msgs/                 # MAVLink 커스텀 메시지
│   └── voice_control.xml      # 5개 메시지 정의
├── generated/mavlink/         # mavgen 생성 코드
│   ├── python.py              # Python 모듈 (전체 MAVLink + 커스텀)
│   └── cpp/                   # C++ 헤더/구현
└── src/                       # ROS 2 패키지 (향후)
```

---

## 🔧 트러블슈팅

| 문제 | 해결 |
|------|------|
| `nvidia-smi` 실패 | 드라이버 재설치: `sudo apt install nvidia-driver-550` |
| CUDA 버전 불일치 | `nvcc --version` 확인, PyTorch는 cu121 버전 설치 |
| ROS 2 통신 안됨 | `ROS_DOMAIN_ID` 동일하게 설정, 방화벽 확인 |
| MAVLink 메시지 import 실패 | `PYTHONPATH`에 `generated/mavlink` 추가 |
| faster-whisper 로드 실패 | `OMP_NUM_THREADS=1` 설정, CPU면 `int8` 사용 |
| Docker GPU 안됨 | `docker run --gpus all` 또는 `runtime: nvidia` 확인 |
| 음성 권한 없음 | macOS: 시스템설정 > 보안 > 마이크 허용, Linux: `usermod -a -G audio $USER` |

---

## 📚 참고 링크
- [MAVSDK Python 문서](https://mavsdk.mavlink.io/main/en/python/)
- [MAVROS2 문서](https://docs.px4.io/main/en/ros/mavros_installation.html)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [PX4 SITL 시뮬레이션](https://docs.px4.io/main/en/simulation/)
- [ROS 2 Humble 설치](https://docs.ros.org/en/humble/Installation.html)