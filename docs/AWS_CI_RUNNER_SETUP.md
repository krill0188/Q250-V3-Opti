# AWS g5.xlarge CI Runner Setup for Q250-V3-Opti

## Overview

This document describes how to provision an AWS g5.xlarge (A10G, sm_86) spot instance and configure it as a GitHub self-hosted CI runner for the `cuda-build` job. This enables Track A (Stage 1) Functional DoD validation for T-01~T-05 without requiring physical Jetson Orin hardware.

## Prerequisites (run on your LOCAL machine)

### 1. Configure AWS Credentials

Per user preference, AWS credentials must be input locally — never shared via chat.

```bash
aws configure
# AWS Access Key ID [None]: <YOUR_ACCESS_KEY>
# AWS Secret Access Key [None]: <YOUR_SECRET_KEY>
# Default region name [None]: us-east-1
# Default output format [None]: json

# Verify
aws sts get-caller-identity
```

### 2. Install Required Tools

```bash
# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# jq for JSON parsing
sudo apt install -y jq   # Ubuntu/Debian
# or: brew install jq    # macOS
```

### 3. Generate GitHub Personal Access Token

Create a PAT with `repo` scope at: https://github.com/settings/tokens/new

```bash
export GITHUB_PAT=<your_token>
export GITHUB_REPO_OWNER=<your-org-or-username>
```

## Step 1: Provision the g5.xlarge Spot Instance

```bash
chmod +x scripts/aws/provision_g5_instance.sh
./scripts/aws/provision_g5_instance.sh
```

This script will:
1. Find the latest Ubuntu 22.04 AMI
2. Create an EC2 key pair and security group
3. Request a g5.xlarge spot instance (A10G, sm_86)
4. Wait for the instance to be running
5. Output the instance ID and public IP

**SSH into the instance:**
```bash
ssh -i ~/.ssh/q250_g5_key.pem ubuntu@<PUBLIC_IP>
```

## Step 2: Verify CUDA and GPU on the Instance

The `user_data_g5.sh` cloud-init script runs on first boot and installs CUDA 12.2, TensorRT, and Python dependencies. Wait 3-5 minutes for it to complete, then verify:

```bash
ssh -i ~/.ssh/q250_g5_key.pem ubuntu@<PUBLIC_IP>

# Check GPU detection
nvidia-smi
# Expected: NVIDIA A10G, Compute Capability: 8.6

# Check CUDA toolkit
nvcc --version
# Expected: CUDA 12.x

# Check cloud-init completion
cat /home/ubuntu/.q250-g5-ready
```

## Step 3: Configure CI Self-Hosted Runner

```bash
# Export required environment variables
export GITHUB_PAT=<your_token>
export GITHUB_REPO_OWNER=<your-org-or-username>

# Run the CI runner setup
chmod +x scripts/aws/setup_ci_runner.sh
./scripts/aws/setup_ci_runner.sh
```

This script will:
1. Download and extract the GitHub Actions self-hosted runner
2. Install runner dependencies
3. Register the runner with labels: `self-hosted, cuda, g5`
4. Create a systemd service (`q250-ci-runner.service`) for persistence
5. Start the runner service

**Verify the runner is registered on GitHub:**
https://github.com/<OWNER>/Q250-V3-Opti/settings/actions/runners

## Step 4: Trigger CI Build

Push a commit or run the workflow manually:

```bash
# Trigger via git push
git add .
git commit -m "ci: configure g5.xlarge self-hosted runner for cuda-build"
git push origin main

# Or trigger via GitHub Actions UI: Actions → Q250-V3-Opti CI → Run workflow
```

The `cuda-build` job will now execute on the g5.xlarge instance with actual GPU (A10G, sm_86).

## CI Quality Gates (Track A)

The `cuda-build` CI job validates the following 5 gates:

| Gate | Description | Command |
|------|-------------|---------|
| 1 | CUDA multi-arch build | `./build_cuda.sh Release` |
| 2 | Python CUDA backend load | `trajectory_bindings.py` → backend: cuda |
| 3 | pytest non-CUDA tests | `python3 -m pytest tests/` |
| 4 | TensorRT INT8 GPU calibration | `export_tensorrt.py --int8` |
| 5 | Artifact cache roundtrip | SHA256 checksum verification |

Run all gates on the instance:
```bash
chmod +x scripts/aws/validate_functional_dod.sh
./scripts/aws/validate_functional_dod.sh
```

## Step 5: Clean Up (when done)

To avoid ongoing spot instance charges:

```bash
# Terminate the instance
aws ec2 terminate-instances --instance-ids <INSTANCE_ID> --region us-east-1

# Or stop it to resume later
aws ec2 stop-instances --instance-ids <INSTANCE_ID> --region us-east-1

# Remove the self-hosted runner from GitHub repo settings
# https://github.com/<OWNER>/Q250-V3-Opti/settings/actions/runners
```

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/aws/provision_g5_instance.sh` | Spot instance provisioning |
| `scripts/aws/user_data_g5.sh` | Cloud-init (CUDA, TensorRT, Python, build) |
| `scripts/aws/setup_ci_runner.sh` | GitHub self-hosted runner setup |
| `scripts/aws/ci_runner_service.template` | systemd service template |
| `scripts/aws/validate_functional_dod.sh` | Functional DoD validation + 5 CI gates |
| `.github/workflows/ci.yml` | CI workflow (cuda-build job → self-hosted runner) |

## Architecture

```
GitHub Actions (cloud)
    │
    ▼ (self-hosted, cuda, g5 labels)
AWS g5.xlarge (A10G, sm_86)
    ├── GitHub Self-Hosted Runner (systemd service)
    ├── CUDA 12.2 + TensorRT
    ├── Q250-V3-Opti project (built)
    └── nvidia-smi → A10G, Compute Cap 8.6
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Runner not showing on GitHub | Check `systemctl status q250-ci-runner.service` and `journalctl -u q250-ci-runner.service -f` |
| CUDA not detected | Ensure `user_data_g5.sh` completed; check `nvidia-smi` and `nvcc --version` |
| cuda-build job stuck pending | Verify runner labels match: `self-hosted, cuda, g5` |
| Spot instance not fulfilling | Increase `--spot-price` or try different region |
| Runner registration fails | Verify `GITHUB_PAT` has `repo` scope; check `GITHUB_REPO_OWNER` |
