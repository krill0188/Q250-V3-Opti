#!/usr/bin/env bash
# =============================================================================
# Q250-V3-Opti: AWS g5.xlarge (A10G, sm_86) Spot Instance Provisioning
# Stage 1: Functional DoD Validation on Cloud GPU
# =============================================================================
set -euo pipefail

# --- Configuration -----------------------------------------------------------
INSTANCE_TYPE="g5.xlarge"
GPU_ARCH="86"          # A10G = sm_86
AMI_OWNER="amazon"
AMI_NAME_FILTER="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
KEY_NAME="${KEY_NAME:-q250-g5-key}"
SECURITY_GROUP_NAME="${SECURITY_GROUP_NAME:-q250-g5-sg}"
INSTANCE_NAME="q250-g5-functional-dod"
SUBNET_ID="${SUBNET_ID:-}"
SPOT_PRICE="${SPOT_PRICE:-0.50}"    # max spot price USD/hour
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
KEY_MATERIAL_FILE="${HOME}/.ssh/q250_g5_key.pem"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()   { echo -e "${RED}[ERR]${NC}  $*"; }

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Provision AWS g5.xlarge (A10G, sm_86) spot instance for Q250-V3-Opti
Stage 1 Functional DoD validation.

OPTIONS:
    --region REGION       AWS region (default: us-east-1 or AWS_DEFAULT_REGION)
    --key-name NAME       EC2 key pair name (default: q250-g5-key)
    --spot-price PRICE    Max spot price USD/hour (default: 0.50)
    --instance-name NAME  EC2 instance Name tag (default: q250-g5-functional-dod)
    --dry-run             Validate config without provisioning
    -h, --help            Show this help

ENV VARS:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY  AWS credentials (required)
    AWS_DEFAULT_REGION                        AWS region
    KEY_NAME, SECURITY_GROUP_NAME, SUBNET_ID  Override defaults

EXAMPLES:
    $0                                        # Provision with defaults
    $0 --region us-west-2 --spot-price 0.75   # Custom region/price
    $0 --dry-run                              # Validate only

EOF
}

# --- Argument parsing --------------------------------------------------------
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --region) REGION="$2"; shift 2 ;;
        --key-name) KEY_NAME="$2"; shift 2 ;;
        --spot-price) SPOT_PRICE="$2"; shift 2 ;;
        --instance-name) INSTANCE_NAME="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) log_err "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# --- Pre-flight checks -------------------------------------------------------
log_info "Q250-V3-Opti g5.xlarge Provisioning"
log_info "Region: ${REGION}"
log_info "Instance type: ${INSTANCE_TYPE} (A10G, sm_${GPU_ARCH})"
log_info "Spot max price: \$${SPOT_PRICE}/hr"
log_info "Dry run: ${DRY_RUN}"

# Check AWS CLI
if ! command -v aws &>/dev/null; then
    log_err "AWS CLI not found. Install: https://aws.amazon.com/cli/"
    exit 1
fi

# Check credentials
if ! aws sts get-caller-identity --region "${REGION}" &>/dev/null; then
    log_err "AWS credentials not configured or invalid."
    log_err "  Run: aws configure"
    log_err "  Or set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION"
    exit 1
fi
log_ok "AWS credentials valid"

# Check jq for JSON parsing
if ! command -v jq &>/dev/null; then
    log_err "jq not found. Install: https://jqlang.github.io/jq/"
    exit 1
fi

# --- Find AMI ----------------------------------------------------------------
log_info "Looking up Ubuntu 22.04 AMI in ${REGION}..."
AMI_ID=$(aws ec2 describe-images \
    --region "${REGION}" \
    --owners "${AMI_OWNER}" \
    --filters "Name=name,Values=${AMI_NAME_FILTER}" "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text 2>/dev/null)

if [[ -z "${AMI_ID}" || "${AMI_ID}" == "None" ]]; then
    log_err "Could not find Ubuntu 22.04 AMI in ${REGION}"
    exit 1
fi
log_ok "AMI: ${AMI_ID}"

# --- Create or import key pair -----------------------------------------------
if ! aws ec2 describe-key-pairs --region "${REGION}" --key-names "${KEY_NAME}" &>/dev/null; then
    log_info "Creating key pair: ${KEY_NAME}"
    mkdir -p "$(dirname "${KEY_MATERIAL_FILE}")"
    aws ec2 create-key-pair \
        --region "${REGION}" \
        --key-name "${KEY_NAME}" \
        --key-type rsa \
        --query 'KeyMaterial' --output text > "${KEY_MATERIAL_FILE}"
    chmod 600 "${KEY_MATERIAL_FILE}"
    log_ok "Key pair created: ${KEY_MATERIAL_FILE}"
else
    log_ok "Key pair already exists: ${KEY_NAME}"
fi

# --- Create security group ---------------------------------------------------
SG_ID=$(aws ec2 describe-security-groups \
    --region "${REGION}" \
    --filters "Name=group-name,Values=${SECURITY_GROUP_NAME}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || true)

if [[ -z "${SG_ID}" || "${SG_ID}" == "None" ]]; then
    log_info "Creating security group: ${SECURITY_GROUP_NAME}"
    SG_ID=$(aws ec2 create-security-group \
        --region "${REGION}" \
        --group-name "${SECURITY_GROUP_NAME}" \
        --description "Q250-V3-Opti g5.xlarge Functional DoD" \
        --query 'GroupId' --output text)

    # Allow SSH
    aws ec2 authorize-security-group-ingress \
        --region "${REGION}" \
        --group-id "${SG_ID}" \
        --protocol tcp --port 22 --cidr 0.0.0.0/0 &>/dev/null || true

    # Allow all traffic for flexibility (restrict in production)
    aws ec2 authorize-security-group-ingress \
        --region "${REGION}" \
        --group-id "${SG_ID}" \
        --protocol -1 --cidr 0.0.0.0/0 &>/dev/null || true

    log_ok "Security group created: ${SG_ID}"
else
    log_ok "Security group already exists: ${SG_ID}"
fi

# --- Read user data ----------------------------------------------------------
USER_DATA_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/user_data_g5.sh"
if [[ ! -f "${USER_DATA_FILE}" ]]; then
    log_err "User data script not found: ${USER_DATA_FILE}"
    exit 1
fi
USER_DATA_B64=$(base64 -w0 < "${USER_DATA_FILE}")

if [[ "${DRY_RUN}" == true ]]; then
    log_info "=== DRY RUN - Configuration validated ==="
    log_info "AMI: ${AMI_ID}"
    log_info "Instance type: ${INSTANCE_TYPE}"
    log_info "Key pair: ${KEY_NAME}"
    log_info "Security group: ${SG_ID}"
    log_info "User data: ${USER_DATA_FILE}"
    log_info "Would provision spot instance now."
    exit 0
fi

# --- Request spot instance ---------------------------------------------------
log_info "Requesting g5.xlarge spot instance..."
RUN_INSTANCES_JSON=$(aws ec2 run-instances \
    --region "${REGION}" \
    --image-id "${AMI_ID}" \
    --instance-type "${INSTANCE_TYPE}" \
    --key-name "${KEY_NAME}" \
    --security-group-ids "${SG_ID}" \
    --instance-market-options '{"MarketType": "spot", "SpotOptions": {"MaxPrice": "'"${SPOT_PRICE}"'", "SpotInstanceType": "one-time"}}' \
    --user-data "${USER_DATA_B64}" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}},{Key=Project,Value=Q250-V3-Opti},{Key=Purpose,Value=Functional-DoD},{Key=GPU,Value=A10G},{Key=Arch,Value=sm_86}]" \
    --count 1 \
    ${SUBNET_ID:+"--subnet-id ${SUBNET_ID}"} \
    --query 'Instances[0]' \
    --output json 2>/dev/null)

if [[ -z "${RUN_INSTANCES_JSON}" ]]; then
    log_err "Failed to request spot instance"
    exit 1
fi

INSTANCE_ID=$(echo "${RUN_INSTANCES_JSON}" | jq -r '.InstanceId')
SPOT_REQUEST_ID=$(echo "${RUN_INSTANCES_JSON}" | jq -r '.InstanceLifecycle // "spot"')

log_info "Instance requested: ${INSTANCE_ID} (spot: ${SPOT_REQUEST_ID})"

# --- Wait for running state --------------------------------------------------
log_info "Waiting for instance to be running (this may take 2-5 minutes)..."
aws ec2 wait instance-running --region "${REGION}" --instance-ids "${INSTANCE_ID}"
log_ok "Instance is running: ${INSTANCE_ID}"

# --- Get public IP -----------------------------------------------------------
PUBLIC_IP=$(aws ec2 describe-instances \
    --region "${REGION}" \
    --instance-ids "${INSTANCE_ID}" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

log_info "Public IP: ${PUBLIC_IP}"

# --- Wait for SSH readiness --------------------------------------------------
log_info "Waiting for SSH to be ready (cloud-init may take 3-5 minutes)..."
for i in $(seq 1 30); do
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        -i "${KEY_MATERIAL_FILE}" ubuntu@"${PUBLIC_IP}" "echo 'SSH ready'" &>/dev/null; then
        log_ok "SSH is ready on ${PUBLIC_IP}"
        break
    fi
    if [[ $i -eq 30 ]]; then
        log_err "SSH not ready after 30 attempts"
        exit 1
    fi
    sleep 10
done

# --- Summary -----------------------------------------------------------------
echo ""
echo "============================================================"
echo "  g5.xlarge Spot Instance Provisioned Successfully"
echo "============================================================"
echo "  Instance ID:  ${INSTANCE_ID}"
echo "  Instance Type: ${INSTANCE_TYPE} (A10G, sm_${GPU_ARCH})"
echo "  Public IP:    ${PUBLIC_IP}"
echo "  SSH:          ssh -i ${KEY_MATERIAL_FILE} ubuntu@${PUBLIC_IP}"
echo "  Region:       ${REGION}"
echo "  Spot Max:     \$${SPOT_PRICE}/hr"
echo ""
echo "  Next steps:"
echo "  1. SSH in: ssh -i ${KEY_MATERIAL_FILE} ubuntu@${PUBLIC_IP}"
echo "  2. Verify GPU: nvidia-smi"
echo "  3. Run Functional DoD: ./scripts/aws/validate_functional_dod.sh"
echo "============================================================"

# Save instance info for downstream tasks
cat > "/tmp/q250_g5_instance_info.sh" <<EOF
export Q250_G5_INSTANCE_ID="${INSTANCE_ID}"
export Q250_G5_PUBLIC_IP="${PUBLIC_IP}"
export Q250_G5_KEY_FILE="${KEY_MATERIAL_FILE}"
export Q250_G5_REGION="${REGION}"
export Q250_G5_INSTANCE_TYPE="${INSTANCE_TYPE}"
EOF
log_ok "Instance info saved to /tmp/q250_g5_instance_info.sh"