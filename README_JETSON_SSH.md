# Q250-V3-Opti: Jetson Orin SSH Automation Pipeline

Complete SSH automation for Jetson Orin on-device validation (Tier 2 of the hybrid validation strategy).

## Overview

This automation implements the **Tier 2 Jetson Orin On-Device Validation** from the Agora decision (motion `t_f0894c80`):

> "Tier 2 Jetson Orin On-Device for final DoD validation (CUDA kernel execution, TensorRT INT8 calibration/engine generation, benchmarks)"

## Pipeline Stages

| Stage | Description | DoD Verification |
|-------|-------------|------------------|
| **Deploy** | Transfer source, checkpoints, calibration data to Jetson | Files present on target |
| **Build** | Compile CUDA kernels for sm_87 (Jetson Orin) | `libtrajectory_kernels.so` + CUDA backend active |
| **Calibrate** | TensorRT INT8 calibration (entropy + percentile) | Two `.engine` files with benchmarks |
| **DLA** | Test Deep Learning Accelerator execution | DLA layer analysis + benchmark |
| **Benchmark** | Full performance suite (CUDA + TensorRT) | Latency/FPS targets met |
| **Package** | Create signed deploy package | `q250-v3-opti-gpu-YYYYMMDD.tar.gz` + SHA256 |

## Quick Start

### 1. Configure SSH Access

```bash
# Generate dedicated SSH key for Jetson access
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_q250 -C "q250-jetson"

# Copy public key to Jetson
ssh-copy-id -i ~/.ssh/id_ed25519_q250.pub jetson@jetson.local

# Test connection
ssh -i ~/.ssh/id_ed25519_q250 jetson@jetson.local "echo 'OK'"
```

### 2. Configure Environment

```bash
# Copy and edit configuration
cp config/jetson.env.example ~/.config/q250/jetson.env
# Edit: JETSON_HOST, JETSON_USER, JETSON_KEY, paths
source ~/.config/q250/jetson.env
```

### 3. Run Full Pipeline

```bash
# From project root
./scripts/ssh_jetson_setup.sh
```

### 4. Run Specific Stage

```bash
# Only build CUDA kernels
./scripts/ssh_jetson_setup.sh --stage build

# Only calibration (files already on Jetson)
./scripts/ssh_jetson_setup.sh --stage calibrate --skip-deploy

# Full pipeline with custom host
./scripts/ssh_jetson_setup.sh --host 192.168.1.100 --user nvidia
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Development Machine                          │
│  ┌─────────────────┐    ┌──────────────────────────────────┐   │
│  │ ssh_jetson_     │───▶│ SSH/SCP                           │   │
│  │ setup.sh        │    │ • Deploy source & data            │   │
│  │ (Orchestrator)  │    │ • Invoke remote pipeline          │   │
│  └─────────────────┘    │ • Download deploy package         │   │
│                         └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │ SSH
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Jetson Orin (Target)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ jetson_pipeline.sh                                       │  │
│  │ • Build CUDA kernels (sm_87)                             │  │
│  │ • TensorRT INT8: entropy + percentile calibration        │  │
│  │ • DLA execution test                                     │  │
│  │ • CUDA kernel benchmarks                                 │  │
│  │ • TensorRT inference benchmarks                          │  │
│  │ • Create deploy package + manifest + SHA256              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Scripts

| Script | Purpose | Runs On |
|--------|---------|---------|
| `ssh_jetson_setup.sh` | Main orchestrator (deploy → invoke remote → download) | Dev machine |
| `jetson_pipeline.sh` | On-device validation pipeline | Jetson Orin |
| `jetson_verify.sh` | Quick validation (pre-existing) | Jetson Orin |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JETSON_HOST` | `jetson.local` | Jetson hostname/IP |
| `JETSON_USER` | `jetson` | SSH username |
| `JETSON_PORT` | `22` | SSH port |
| `JETSON_KEY` | `~/.ssh/id_ed25519` | SSH private key |
| `JETSON_PROJECT_DIR` | `~/Q250-V3-Opti` | Remote project path |
| `JETSON_CALIB_DIR` | `~/data/drone_datasets/processed/drone_audio` | Calibration data |
| `JETSON_CHECKPOINT_DIR` | `~/checkpoints` | Model checkpoints |
| `CALIB_METHODS` | `entropy,percentile` | Calibration methods |
| `CALIB_PERCENTILE` | `99.9` | Percentile for MinMax calibrator |
| `STAGE` | `all` | Pipeline stage |

### GitHub Actions Secrets

For CI/CD integration, add these repository secrets:

| Secret | Description |
|--------|-------------|
| `JETSON_HOST` | Jetson hostname/IP |
| `JETSON_USER` | SSH username |
| `JETSON_PORT` | SSH port |
| `JETSON_KEY_BASE64` | `base64 -w 0 < ~/.ssh/id_ed25519_q250` |
| `JETSON_CALIB_DIR` | Remote calibration data path |
| `JETSON_CHECKPOINT_DIR` | Remote checkpoint path |

## GitHub Actions Workflow

The workflow `.github/workflows/jetson-validation.yml` provides:

- **Manual dispatch** with stage selection
- **Weekly scheduled** regression testing (Mondays 2 AM UTC)
- **Tag-triggered** release package publishing
- **Quick validation** on every push to main

### Manual Trigger

```bash
# Via GitHub CLI
gh workflow run jetson-validation.yml \
  -f stage=all \
  -f jetson_host=192.168.1.100

# Or via GitHub UI: Actions → Jetson Orin Validation → Run workflow
```

## Deploy Package

The final artifact `q250-v3-opti-gpu-YYYYMMDD.tar.gz` contains:

```
q250-v3-opti-gpu-20261127.tar.gz
├── libtrajectory_kernels.so          # CUDA kernels (sm_87)
├── audio_classifier.engine           # TensorRT INT8 (entropy)
├── audio_classifier_percentile.engine # TensorRT INT8 (percentile 99.9)
├── trajectory_bindings.py            # Python ctypes bindings
├── trajectory_kernels.cuh            # Kernel headers
├── *.calib                           # Calibration caches
└── MANIFEST.txt                      # File list + SHA256
```

### Deployment on Target

```bash
# On target Jetson (or any arm64 + CUDA 12.x device)
tar -xzf q250-v3-opti-gpu-20261127.tar.gz
export LD_LIBRARY_PATH=$PWD:$LD_LIBRARY_PATH
export PYTHONPATH=$PWD:$PYTHONPATH

# Verify
python3 -c "
from trajectory_bindings import get_trajectory_backend
backend, name = get_trajectory_backend()
print(f'Backend: {name}')  # Should be 'cuda'
pts = backend.geometric_dive((0,0,100), 50, 45, 25, 30, 60, 50)
print(f'Generated {len(pts)} waypoints')
"
```

## Calibration Methods Comparison

| Method | Class | Use Case | Typical Result |
|--------|-------|----------|----------------|
| **Entropy** | `IInt8EntropyCalibrator2` | General purpose, default | Good for most distributions |
| **Percentile** | `IInt8MinMaxCalibrator` | Long-tailed activations (audio) | Tighter range, often better accuracy |

The pipeline runs **both** and produces separate engines for comparison.

## DLA Testing

Jetson Orin has 2x DLA cores. The pipeline:

1. Detects DLA availability via `builder.num_DLA_cores`
2. Analyzes layer precision compatibility (INT8/FP16 layers)
3. Runs inference benchmark with DLA execution context
4. Reports latency/FPS for DLA vs GPU

## Benchmarks Targets

| Component | Target | Notes |
|-----------|--------|-------|
| CUDA Geometric Dive (50 pts) | < 0.1 ms | 24x speedup vs Python |
| CUDA Spiral Dive (50 pts) | < 0.1 ms | 25x speedup vs Python |
| TensorRT INT8 Inference | < 1 ms | 1200+ FPS on Orin |
| DLA INT8 Inference | < 2 ms | Lower power, dedicated HW |

## Troubleshooting

### SSH Connection Failed
```bash
# Test manually
ssh -i ~/.ssh/id_ed25519_q250 -p 22 jetson@jetson.local "nvidia-smi"

# Check firewall on Jetson
sudo ufw status
sudo ufw allow 22/tcp
```

### CUDA Build Fails
```bash
# On Jetson, check CUDA
nvcc --version
nvidia-smi

# Rebuild manually
cd ~/Q250-V3-Opti && ./build_cuda.sh Release
```

### TensorRT Not Found
```bash
# JetPack 6.x includes TensorRT
# Verify:
python3 -c "import tensorrt; print(tensorrt.__version__)"

# If missing, install via JetPack SDK Manager
```

### Calibration Data Missing
```bash
# Ensure calibration data exists on Jetson
ls ~/data/drone_datasets/processed/drone_audio/

# Or specify custom path
./scripts/ssh_jetson_setup.sh --stage calibrate \
  # (edit script to pass --calib-data)
```

### DLA Not Available
- DLA requires specific layer types (INT8/FP16 convolutions)
- Some layers may fall back to GPU
- Check `/tmp/dla_test.log` for layer analysis

## Integration with Tier 1 Cloud CI

This Tier 2 pipeline complements the Tier 1 Cloud CI (`.github/workflows/ci.yml`):

| Tier | Environment | Purpose |
|------|-------------|---------|
| **Tier 1** | GitHub Actions `ubuntu-latest` + CUDA toolkit | CUDA build verification, multi-arch (sm_86/89), unit tests |
| **Tier 2** | Jetson Orin (physical) | Final DoD: kernel execution, INT8 calibration, DLA, benchmarks |

## Files Created

```
scripts/
├── ssh_jetson_setup.sh      # Main orchestrator (dev machine)
├── jetson_pipeline.sh       # On-device pipeline (Jetson)
└── jetson_verify.sh         # Quick validation (pre-existing)

config/
└── jetson.env.example       # Configuration template

.github/workflows/
└── jetson-validation.yml    # GitHub Actions workflow
```

## References

- Agora Motion: `t_f0894c80` (hybrid 2-tier validation strategy)
- CUDA Build Guide: `CUDA_BUILD_GUIDE.md`
- Target PC Guide: `TARGET_PC_실행가이드.md`
- TensorRT Export: `src/deployment/export_tensorrt.py`
- Parent task: `t_399a17df` (this automation)
- Child task: `t_1a08bfce` (INT8 calibration strategy validation)