# Q250-V3-Opti 타겟 PC(Jetson Orin) 즉시 실행 가이드

> **작성일**: 2026-11-22  
> **대상**: Jetson Orin (AGX/NX) + JetPack 6.x + Hermes Agent + Speckit 스킬  
> **저장소**: https://github.com/krill0188/Q250-V3-Opti (main 브랜치)  
> **핵심**: 타겟 PC에서 `./build_cuda.sh Release` 한 번 실행 → 즉시 GPU 가속 적용

---

## 0. 사전 확인 (타겟 PC에서 실행)

```bash
# 1) JetPack/CUDA 확인
nvcc --version
# 예: Cuda compilation tools, release 12.2, V12.2.140

# 2) GPU 아키텍처 확인 (Orin = 87)
nvidia-smi --query-gpu=compute_cap --format=csv

# 3) Python/pycuda 확인
python3 -c "import pycuda.driver; print(pycuda.driver.get_version())"

# 4) Hermes Agent + Speckit 확인
hermes --version
speckit --version
```

**모두 정상이면 다음 단계 진행.**

---

## 1. 저장소 클론 및 빌드 (한 번만)

```bash
# 1) 저장소 클론 (main 브랜치)
cd ~
git clone https://github.com/krill0188/Q250-V3-Opti.git
cd Q250-V3-Opti

# 2) 빌드 스크립트 실행 (Jetson Orin sm_87 자동 감지)
chmod +x build_cuda.sh
./build_cuda.sh Release

# 3) 빌드 성공 확인
cd build
python3 ../src/cuda/trajectory_bindings.py
```

### ✅ 성공 시 출력 예시

```
============================================================
Q250-V3-Opti Trajectory CUDA Kernels Build
============================================================
Build type: Release
Target CUDA architectures: 87
Configuring with CMake...
Building...
Build SUCCESS!
Library: /home/jetson/Q250-V3-Opti/build/libtrajectory_kernels.so
Size: 245K

Testing trajectory backend selection...
Selected backend: cuda
Testing CUDA geometric dive...
Generated 11 points
First: TrajectoryPoint(pos=(0.00, 0.00, 100.00), vel=(17.68, 0.00, -17.68), t=0.000)
```

> **핵심**: `Selected backend: cuda` 가 나와야 함. `python_fallback`이면 빌드 실패.

---

## 2. TensorRT INT8 엔진 생성 (타겟에서만 가능)

```bash
cd ~/Q250-V3-Opti

# 1) 캘리브레이션 데이터 준비 (최초 1회)
mkdir -p data/calibration
# data/calibration/ 아래에 .npy 또는 오디오 파일 배치 (최소 100개)

# 2) INT8 엔진 생성 + 벤치마크
python3 src/deployment/export_tensorrt.py \
    --model_path checkpoints/multiclass/best_model.pth \
    --int8 --calib_data data/calibration \
    --output_dir tensorrt_models \
    --benchmark
```

### ✅ 성공 시 출력 예시

```
Exporting checkpoints/multiclass/best_model.pth -> TensorRT (FP16=True, INT8=True)
Preparing INT8 calibration data...
Prepared calibration data: (400, 1, 157, 40)
Building TensorRT engine... (this may take a few minutes)
TensorRT engine saved to: tensorrt_models/audio_classifier.engine
Max absolute difference: 0.000123
✓ TensorRT engine matches ONNX Runtime!

Benchmarking...
Results: {'mean_ms': 0.83, 'std_ms': 0.02, 'min_ms': 0.79, 'max_ms': 0.91, 'fps': 1204.8}
```

> **결과물**: `tensorrt_models/audio_classifier.engine` (배포용 INT8 엔진)

---

## 3. 전체 시스템 검증

```bash
cd ~/Q250-V3-Opti/build

python3 -c "
import sys
sys.path.insert(0, '..')
from core.trajectory_engine import TrajectoryEngine, TrajectoryMethod
import asyncio

# 테스트 스펙
class Spec:
    max_dive_speed_mps = 50.0
    max_dive_angle_deg = 80.0

engine = TrajectoryEngine(specs={'q250': Spec()})

# GPU 백엔드 확인
print(f'GPU Backend: {engine.gpu_engine.backend_name if engine.gpu_engine else \"CPU\"}')

# 궤적 생성 테스트
traj = asyncio.run(engine.generate_dive_trajectory(
    start_pos=(0.0, 0.0, 100.0),
    target_alt=50.0,
    dive_angle=45.0,
    max_speed=25.0,
    method=TrajectoryMethod.MPC
))
print(f'Waypoints: {len(traj.waypoints)}')
print(f'Method: {traj.method}')
print(f'Constraints OK: {traj.constraints_satisfied}')
print(f'First WP: {traj.waypoints[0]}')
print(f'Last WP: {traj.waypoints[-1]}')
"
```

### ✅ 성공 시 출력

```
GPU Backend: cuda
Waypoints: 51
Method: TrajectoryMethod.GEOMETRIC
Constraints OK: True
First WP: (0.0, 0.0, 100.0)
Last WP: (50.0, 0.0, 50.0)
```

---

## 4. Hermes Agent + Speckit 연동 (타겟에서)

타겟 PC에 **Hermes Agent + Speckit 스킬**이 설치되어 있다면:

```bash
# 1) 스킬 로드 확인
hermes skill load cuda-kernel-development

# 2) Speckit 워크플로 실행 (자동 빌드/검증)
speckit run q250-trajectory-gpu

# 3) Hermes에서 직접 실행
hermes run "
from core.trajectory_engine import TrajectoryEngine
engine = TrajectoryEngine(specs={...})
import asyncio
traj = asyncio.run(engine.generate_dive_trajectory(...))
print(f'Backend: {engine.gpu_engine.backend_name}')
"
```

---

## 5. 배포용 파일 패키징 (최종 산출물)

```bash
cd ~/Q250-V3-Opti

# 배포 패키지 생성
mkdir -p deploy_package
cp build/libtrajectory_kernels.so deploy_package/
cp tensorrt_models/audio_classifier.engine deploy_package/
cp src/cuda/trajectory_bindings.py deploy_package/
cp -r src/cuda/trajectory_kernels.cuh deploy_package/

# 버전 태그
cd deploy_package
tar -czf ../q250-v3-opti-gpu-$(date +%Y%m%d).tar.gz .
```

### 최종 배포 패키지 구성

```
q250-v3-opti-gpu-20261122.tar.gz
├── libtrajectory_kernels.so          # CUDA 공유 라이브러리 (sm_87)
├── audio_classifier.engine           # TensorRT INT8 엔진
├── trajectory_bindings.py            # Python 바인딩
└── trajectory_kernels.cuh            # 헤더 (참조용)
```

---

## 6. 런타임 환경 변수 (서비스 등록 시)

```bash
# /etc/systemd/system/q250-trajectory.service
[Service]
Environment=PYTHONPATH=/opt/q250/lib
Environment=LD_LIBRARY_PATH=/opt/q250/lib:/usr/local/cuda/lib64
Environment=CUDA_VISIBLE_DEVICES=0
ExecStart=/usr/bin/python3 -m q250.trajectory_service
```

---

## 7. 문제 해결 (Troubleshooting)

| 증상 | 원인 | 해결 |
|------|------|------|
| `Selected backend: python_fallback` | CUDA 라이브러리 미빌드/미발견 | `./build_cuda.sh Release` 재실행, `ls build/libtrajectory_kernels.so` 확인 |
| `nvcc not found` | CUDA 툴킷 미설치 | `sudo apt install nvidia-cuda-toolkit-12-2` 또는 JetPack 재설치 |
| `pycuda version mismatch` | CUDA/pycuda 버전 불일치 | `pip install pycuda==2023.1` (CUDA 12.x용) |
| `TensorRT engine build failed` | 캘리브레이션 데이터 부족 | `data/calibration/`에 최소 100개 샘플 확보 |
| `CUDA error: invalid device ordinal` | GPU 인식 안됨 | `nvidia-smi` 확인, `CUDA_VISIBLE_DEVICES=0` 설정 |

---

## 8. 성능 검증 체크리스트 (런타임)

```bash
# 1) 궤적 생성 지연 측정
python3 -c "
import time
from src.cuda.trajectory_bindings import get_trajectory_backend
backend, _ = get_trajectory_backend()
start = time.perf_counter()
for _ in range(100):
    pts = backend.geometric_dive((0,0,100), 50, 45, 25, 30, 60, 50)
print(f'Avg: {(time.perf_counter()-start)/100*1000:.2f} ms')
"
# 목표: < 0.1 ms (Python fallback은 ~1.2 ms)

# 2) TensorRT 추론 지연
python3 -c "
import tensorrt as trt, pycuda.driver as cuda, numpy as np, time
runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
with open('tensorrt_models/audio_classifier.engine','rb') as f:
    engine = runtime.deserialize_cuda_engine(f.read())
ctx = engine.create_execution_context()
inp = np.random.randn(1,1,157,40).astype(np.float32)
d_inp = cuda.mem_alloc(inp.nbytes)
out = np.empty((1,3), dtype=np.float32)
d_out = cuda.mem_alloc(out.nbytes)
for _ in range(10): ctx.execute_v2([int(d_inp), int(d_out)])  # warmup
t0 = time.perf_counter()
for _ in range(100):
    cuda.memcpy_htod(d_inp, inp)
    ctx.execute_v2([int(d_inp), int(d_out)])
cuda.Context.synchronize()
print(f'Avg: {(time.perf_counter()-t0)/100*1000:.2f} ms')
"
# 목표: < 1 ms (INT8)
```

---

## 9. 한 줄 요약: 타겟 PC에서 실행할 명령어 3줄

```bash
# 1) 빌드
cd ~/Q250-V3-Opti && ./build_cuda.sh Release

# 2) INT8 엔진 생성
python3 src/deployment/export_tensorrt.py --model_path checkpoints/multiclass/best_model.pth --int8 --calib_data data/calibration --output_dir tensorrt_models --benchmark

# 3) 검증
cd build && python3 -c "
from core.trajectory_engine import TrajectoryEngine
import asyncio
engine = TrajectoryEngine(specs={'q250': type('S',(),{'max_dive_speed_mps':50,'max_dive_angle_deg':80})()})
traj = asyncio.run(engine.generate_dive_trajectory((0,0,100),50,45,25))
print(f'Backend: {engine.gpu_engine.backend_name}')
"
```

---

## 10. 파일 위치 요약

| 파일 | 위치 | 용도 |
|------|------|------|
| `build_cuda.sh` | 루트 | 자동 빌드 스크립트 (sm_87 자동 감지) |
| `src/cuda/trajectory_kernels.cu/.h` | src/cuda/ | CUDA 커널 5종 + 헤더 |
| `src/cuda/trajectory_bindings.py` | src/cuda/ | ctypes 바인딩 + 자동 fallback |
| `core/trajectory_engine.py` | core/ | GPU 백엔드 자동 적용 |
| `src/deployment/export_tensorrt.py` | src/deployment/ | TensorRT INT8 내보내기 |
| `CUDA_BUILD_GUIDE.md` | 루트 | 상세 빌드 가이드 |
| `CMakeLists.txt` | 루트 | CMake 빌드 시스템 |

---

> **작성 완료**: 2026-11-22  
> **저장소**: https://github.com/krill0188/Q250-V3-Opti (main, commit e887ecf)  
> **타겟**: Jetson Orin + JetPack 6.x + Hermes Agent + Speckit  
> **핵심**: 타겟에서 `./build_cuda.sh Release` 한 번 → 끝