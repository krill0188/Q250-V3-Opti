#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti: GitHub Self-Hosted CI Runner Setup for AWS g5.xlarge (A10G, sm_86)
# Run this ON the g5.xlarge instance after provisioning and CUDA setup.
#
# This script:
#   1. Installs the GitHub Actions self-hosted runner application
#   2. Registers the runner with the Q250-V3-Opti repository
#   3. Configures runner labels: self-hosted, cuda, g5
#   4. Sets up a systemd service for runner persistence across reboots
#
# Prerequisites (run on your LOCAL machine first):
#   - AWS credentials configured (aws configure)
#   - g5.xlarge instance provisioned (./scripts/aws/provision_g5_instance.sh)
#   - GitHub PAT with repo scope: export GITHUB_PAT=<your_token>
#
# Usage:
#   chmod +x scripts/aws/setup_ci_runner.sh
#   ./scripts/aws/setup_ci_runner.sh
# =============================================================================
set -euo pipefail

# --- Configuration -----------------------------------------------------------
RUNNER_NAME="q250-g5-runner"
RUNNER_LABELS="self-hosted,cuda,g5"
RUNNER_WORK_DIR="/home/ubuntu/actions-runner/_work"
RUNNER_VERSION="2.320.0"
RUNNER_ARCH="x64"
RUNNER_OS="linux"
RUNNER_DIR="/home/ubuntu/actions-runner"
REPO_OWNER="${GITHUB_REPO_OWNER:-}"
REPO_NAME="${GITHUB_REPO_NAME:-Q250-V3-Opti}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()   { echo -e "${RED}[ERR]${NC}  $*"; }

# --- Validate prerequisites --------------------------------------------------
log_info "Q250-V3-Opti CI Runner Setup for g5.xlarge (A10G, sm_86)"

# Check running on the instance (should be ubuntu user)
if [[ "$(whoami)" != "ubuntu" ]]; then
    log_warn "Not running as ubuntu user. This script is intended to run on the g5.xlarge instance."
fi

# Check GitHub PAT
if [[ -z "${GITHUB_PAT:-}" ]]; then
    log_err "GITHUB_PAT environment variable not set."
    log_err "  Generate a Personal Access Token with 'repo' scope at:"
    log_err "  https://github.com/settings/tokens/new"
    log_err "  Then: export GITHUB_PAT=<your_token>"
    exit 1
fi

# Check repo owner/name
if [[ -z "${REPO_OWNER}" ]]; then
    log_err "GITHUB_REPO_OWNER environment variable not set."
    log_err "  Example: export GITHUB_REPO_OWNER=your-org"
    exit 1
fi

# Verify CUDA is available
if ! command -v nvidia-smi &>/dev/null; then
    log_warn "nvidia-smi not found. CUDA may not be fully installed yet."
    log_warn "  Ensure user_data_g5.sh has completed before running this script."
fi

if ! command -v nvcc &>/dev/null; then
    log_warn "nvcc not found. CUDA toolkit may not be installed."
fi

# Verify jq
if ! command -v jq &>/dev/null; then
    log_err "jq not found. Install: sudo apt install -y jq"
    exit 1
fi

# --- Create runner directory -------------------------------------------------
log_info "Creating runner directory at ${RUNNER_DIR}..."
mkdir -p "${RUNNER_DIR}"
cd "${RUNNER_DIR}"

# --- Download GitHub Actions runner ------------------------------------------
RUNNER_PACKAGE="actions-runner-${RUNNER_OS}-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_PACKAGE}"

if [[ ! -f "${RUNNER_PACKAGE}" ]]; then
    log_info "Downloading GitHub Actions runner v${RUNNER_VERSION}..."
    curl -o "${RUNNER_PACKAGE}" -L "${RUNNER_URL}" \
        || log_err "Failed to download runner package"
    log_ok "Runner package downloaded"
else
    log_ok "Runner package already present"
fi

# Extract runner
log_info "Extracting runner package..."
tar xzf "${RUNNER_PACKAGE}"
log_ok "Runner extracted"

# --- Install runner dependencies ---------------------------------------------
log_info "Installing runner dependencies..."
chmod +x "${RUNNER_DIR}/bin/installdependencies.sh"
"${RUNNER_DIR}/bin/installdependencies.sh" 2>&1 || log_warn "Some dependencies may already be installed"
log_ok "Runner dependencies installed"

# --- Configure runner --------------------------------------------------------
log_info "Configuring GitHub self-hosted runner..."

# Remove existing runner config if present
if [[ -f "${RUNNER_DIR}/.runner" ]]; then
    log_info "Removing existing runner configuration..."
    if [[ -f "${RUNNER_DIR}/config.sh" ]]; then
        "./config.sh" remove --token "${GITHUB_PAT}" 2>/dev/null || true
    fi
    rm -rf "${RUNNER_DIR:?}/.credentials" "${RUNNER_DIR:?}/.runner" "${RUNNER_DIR:?}/.credentials_rsaparams"
fi

# Configure the runner
./config.sh \
    --url "https://github.com/${REPO_OWNER}/${REPO_NAME}" \
    --token "${GITHUB_PAT}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --work "${RUNNER_WORK_DIR}" \
    --ephemeral \
    --unattended \
    --replace

log_ok "Runner configured: ${RUNNER_NAME} with labels [${RUNNER_LABELS}]"

# --- Create systemd service --------------------------------------------------
log_info "Creating systemd service for runner persistence..."

SERVICE_FILE="/etc/systemd/system/q250-ci-runner.service"
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=Q250-V3-Opti GitHub Self-Hosted CI Runner (g5.xlarge, A10G)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${RUNNER_DIR}
ExecStart=${RUNNER_DIR}/run.sh
Restart=always
RestartSec=10
Environment=RUNNER_NAME=${RUNNER_NAME}
Environment=RUNNER_LABELS=${RUNNER_LABELS}

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable q250-ci-runner.service

log_ok "Systemd service created: q250-ci-runner.service"

# --- Start the runner --------------------------------------------------------
log_info "Starting CI runner service..."
systemctl start q250-ci-runner.service

# Wait for runner to register
sleep 5

# Verify runner is active
if systemctl is-active --quiet q250-ci-runner.service; then
    log_ok "CI runner service is active"
else
    log_warn "CI runner service may not be running. Check status with:"
    log_warn "  systemctl status q250-ci-runner.service"
    log_warn "  journalctl -u q250-ci-runner.service -f"
fi

# --- Summary -----------------------------------------------------------------
echo ""
echo "============================================================"
echo "  CI Runner Setup Complete"
echo "============================================================"
echo "  Runner name:   ${RUNNER_NAME}"
echo "  Runner labels: ${RUNNER_LABELS}"
echo "  Runner dir:    ${RUNNER_DIR}"
echo "  Repo:          https://github.com/${REPO_OWNER}/${REPO_NAME}"
echo "  Service:       q250-ci-runner.service"
echo ""
echo "  Check runner status:  systemctl status q250-ci-runner.service"
echo "  View runner logs:     journalctl -u q250-ci-runner.service -f"
echo "  Verify on GitHub:     https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/actions/runners"
echo ""
echo "  Next: Push a commit to trigger the cuda-build CI job on this runner."
echo "============================================================"