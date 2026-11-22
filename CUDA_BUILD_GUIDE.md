# Q250-V3-Opti CUDA 커널 빌드 가이드

## 사전 요구사항

### Jetson Orin (타겟 디바이스)
```bash
# JetPack 6.x 설치 시 CUDA 포함됨
# 확인:
nvcc --version
# 출력 예: Cuda compilation tools, release 12.2, V12.2.140
```

### 데스크톱 (개발 머신)
```bash
# Ubuntu 22.04
sudo apt update && sudo apt install -y nvidia-cuda-toolkit-12-2
# 또는 NVIDIA 공식 runfile 설치
# https://developer.nvidia.com/cuda-downloads

# 확인:
nvcc --version
```

### Python 의존성
```bash
pip install pycuda ctypes numpy
# pycuda는 CUDA 툴킷과 버전 매칭 필요
```

---

## 빌드 절차

### 1. 자동 빌드 (권장)
```bash
cd /path/to/Q250-V3-Opti
chmod +x build_cuda.sh
./build_cuda.sh Release
```

### 2. 수동 빌드 (상세 제어)
```bash
mkdir -p build && cd build

# CUDA 아키텍처 지정 (Jetson Orin = 87)
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES="87" \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc

# 빌드
cmake --build . --config Release -j$(nproc)
```

### 3. 크로스 컴파일 (데스크톱 → Jetson)
```bash
# Jetson 타겟용 크로스 컴파일
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES="87" \
    -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
    -DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++ \
    -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc
```

---

## 빌드 산출물

```
build/
├── libtrajectory_kernels.so          # 공유 라이브러리 (메인)
├── trajectory_bindings.py             # Python 바인딩 (자동 복사)
└── test_trajectory_kernels            # 테스트 실행 파일 (옵션)
```

---

## 설치 및 검증

### 1. 라이브러리 설치 (시스템 전체)
```bash
sudo cp build/libtrajectory_kernels.so /usr/local/lib/
sudo ldconfig
```

### 2. Python 바인딩 테스트
```bash
cd build
python3 ../src/cuda/trajectory_bindings.py
```

**예상 출력 (CUDA 사용 시):**
```
Testing trajectory backend selection...
Selected backend: cuda
Testing CUDA geometric dive...
Generated 11 points
First: TrajectoryPoint(pos=(0.00, 0.00, 100.00), vel=(17.68, 0.00, -17.68), t=0.000)
Last: TrajectoryPoint(pos=(50.00, 0.00, 50.00), vel=(17.68, 0.00, -17.68), t=2.828)
```

**예상 출력 (CUDA 없을 때):**
```
Testing trajectory backend selection...
[Trajectory] CUDA backend unavailable: CUDA library not found...
[Trajectory] Falling back to Python implementation
Selected backend: python_fallback
Testing Python fallback...
Generated 11 points
First: (0.0, 0.0, 100.0)
Last: (50.0, 0.0, 50.0)
```

---

## Python에서 사용하기

### 1. 자동 백엔드 선택 (권장)
```python
from src.cuda.trajectory_bindings import get_trajectory_backend, TrajectoryEngineGPU

# 자동 선택 (CUDA 있으면 GPU, 없으면 Python)
backend, name = get_trajectory_backend()
print(f"Backend: {name}")

# 다이브 궤적 생성
points = backend.geometric_dive(
    start_pos=(0, 0, 100),
    target_alt=50,
    dive_angle=45,
    max_speed=25,
    max_dive_speed=30,
    max_dive_angle=60,
    num_points=50
)

for p in points[:3]:
    print(f"  {p}")
```

### 2. TrajectoryEngineGPU 사용 (기존 코드 호환)
```python
from core.trajectory_engine import TrajectoryEngine, TrajectoryMethod

# 기존 코드와 동일하게 사용 - 자동으로 GPU 가속 적용
engine = TrajectoryEngine(specs={"drone1": DroneSpec(...)})

# GPU 가속 자동 적용
traj = await engine.generate_dive_trajectory(
    start_pos=(0, 0, 100),
    target_alt=50,
    dive_angle=45,
    max_speed=25,
    method=TrajectoryMethod.MPC
)
```

### 3. 강제 Python 모드 (디버깅용)
```python
from src.cuda.trajectory_bindings import get_trajectory_backend

backend, name = get_trajectory_backend(force_python=True)
# name == "python_fallback"
```

---

## 성능 비교 (예상)

| 연산 | Python (CPU) | CUDA (GPU) | 속도 향상 |
|------|-------------|------------|-----------|
| Geometric Dive (50 pts) | ~1.2 ms | ~0.05 ms | **24x** |
| Spiral Dive (50 pts) | ~1.5 ms | ~0.06 ms | **25x** |
| Sine Dive (50 pts) | ~1.3 ms | ~0.05 ms | **26x** |
| Jink (20 segments) | ~0.8 ms | ~0.04 ms | **20x** |
| LUT Interpolation | ~0.3 ms | ~0.01 ms | **30x** |

*Jetson AGX Orin 64GB 기준, 배치 크기 1 기준*

---

## 문제 해결

### 1. `nvcc not found`
```bash
# CUDA 툴킷 설치 확인
ls /usr/local/cuda/bin/nvcc

# PATH 추가
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
```

### 2. `CUDA library not found`
```bash
# 라이브러리 경로 확인
ls -la build/libtrajectory_kernels.so

# Python 경로에 추가
export PYTHONPATH=/path/to/Q250-V3-Opti/build:$PYTHONPATH
```

### 3. `pycuda` 버전 불일치
```bash
# CUDA 버전 확인
nvcc --version

# 일치하는 pycuda 설치
pip uninstall pycuda
pip install pycuda==2023.1  # CUDA 12.x용
```

### 4. 아키텍처 불일치 (sm_XX)
```bash
# 현재 GPU 아키텍처 확인
nvidia-smi --query-gpu=compute_cap --format=csv

# CMakeLists.txt에서 아키텍처 수정
# Jetson Orin: 87
# RTX 30/40: 86, 89
# RTX 4090: 89
```

---

## 배포 체크리스트

Jetson 타겟에 배포 전 확인:

- [ ] `libtrajectory_kernels.so` 타겟 아키텍처(arm64, sm_87)로 빌드됨
- [ ] `trajectory_bindings.py`가 Python 경로에 있음
- [ ] `pycuda`가 타겟 CUDA 버전과 일치함
- [ ] `python3 -c "from trajectory_bindings import get_trajectory_backend; print(get_trajectory_backend()[1])"` 출력: `cuda`
- [ ] 궤적 생성 지연 < 0.1ms (50포인트 기준)

---

## 지원 및 문의

빌드 관련 이슈: 프로젝트 GitHub Issues 참고
CUDA 커널 최적화 요청: `src/cuda/trajectory_kernels.cu` 수정 후 재빌드