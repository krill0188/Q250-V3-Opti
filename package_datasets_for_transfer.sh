#!/bin/bash
# =============================================================================
# Q250-V3-Opti 데이터셋 타겟 PC 전송 패키징 스크립트
# 사용법: ./package_datasets_for_transfer.sh [대상디렉토리]
# =============================================================================

set -euo pipefail

# 색상
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERR]${NC} $*"; }

# 기본 경로
SOURCE_BASE="${HOME}/data/drone_datasets"
DEST_BASE="${1:-${HOME}/q250_transfer_package}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_DIR="${DEST_BASE}/q250_datasets_${TIMESTAMP}"

log_info "Q250-V3-Opti 데이터셋 패키징 시작"
log_info "소스: ${SOURCE_BASE}"
log_info "대상: ${PACKAGE_DIR}"

# 디렉토리 생성
mkdir -p "${PACKAGE_DIR}"

# =============================================================================
# 1. 처리된 데이터셋 (학습용) - 필수
# =============================================================================
log_info "1. 처리된 데이터셋 복사 중..."

# 드론 오디오 (필수 - 132M)
if [ -d "${SOURCE_BASE}/processed/drone_audio" ]; then
    mkdir -p "${PACKAGE_DIR}/processed/drone_audio"
    rsync -av --progress "${SOURCE_BASE}/processed/drone_audio/" "${PACKAGE_DIR}/processed/drone_audio/"
    log_ok "drone_audio 완료"
else
    log_warn "drone_audio 없음"
fi

# UZH-FPV (필수 - 1.2M)
if [ -d "${SOURCE_BASE}/processed/uzh_fpv" ]; then
    mkdir -p "${PACKAGE_DIR}/processed/uzh_fpv"
    rsync -av --progress "${SOURCE_BASE}/processed/uzh_fpv/" "${PACKAGE_DIR}/processed/uzh_fpv/"
    log_ok "uzh_fpv 완료"
else
    log_warn "uzh_fpv 없음"
fi

# IDF-DS (필수 - 87M)
if [ -d "${SOURCE_BASE}/processed/idf_ds" ]; then
    mkdir -p "${PACKAGE_DIR}/processed/idf_ds"
    rsync -av --progress "${SOURCE_BASE}/processed/idf_ds/" "${PACKAGE_DIR}/processed/idf_ds/"
    log_ok "idf_ds 완료"
else
    log_warn "idf_ds 없음"
fi

# IGN Fixed-wing (필수 - 68K)
if [ -d "${SOURCE_BASE}/processed/ign_fixed_wing" ]; then
    mkdir -p "${PACKAGE_DIR}/processed/ign_fixed_wing"
    rsync -av --progress "${SOURCE_BASE}/processed/ign_fixed_wing/" "${PACKAGE_DIR}/processed/ign_fixed_wing/"
    log_ok "ign_fixed_wing 완료"
else
    log_warn "ign_fixed_wing 없음"
fi

# Fixed-wing Attitude (필수 - 68M)
if [ -d "${SOURCE_BASE}/processed/fixed_wing_attitude" ]; then
    mkdir -p "${PACKAGE_DIR}/processed/fixed_wing_attitude"
    rsync -av --progress "${SOURCE_BASE}/processed/fixed_wing_attitude/" "${PACKAGE_DIR}/processed/fixed_wing_attitude/"
    log_ok "fixed_wing_attitude 완료"
else
    log_warn "fixed_wing_attitude 없음"
fi

# FPV Analog (선택 - 55G, 너무 커서 기본 제외)
if [ -d "${SOURCE_BASE}/processed/fpv_analog" ]; then
    log_warn "fpv_analog: 55GB - 너무 커서 기본 제외"
    log_info "필요시 수동 복사: rsync -av ${SOURCE_BASE}/processed/fpv_analog/ ${PACKAGE_DIR}/processed/fpv_analog/"
fi

# =============================================================================
# 2. 원본 데이터셋 (재처리용) - 선택
# =============================================================================
log_info "2. 원본 데이터셋 복사 중..."

# DroneAudioDataset 원본
if [ -d "${SOURCE_BASE}/04_special_verified/DroneAudioDataset" ]; then
    rsync -av --progress "${SOURCE_BASE}/04_special_verified/DroneAudioDataset/" "${PACKAGE_DIR}/raw/DroneAudioDataset/"
    log_ok "DroneAudioDataset 원본 완료"
fi

# UZH-FPV 원본
if [ -d "${SOURCE_BASE}/04_special_verified/uzh_fpv" ]; then
    rsync -av --progress "${SOURCE_BASE}/04_special_verified/uzh_fpv/" "${PACKAGE_DIR}/raw/uzh_fpv/"
    log_ok "UZH-FPV 원본 완료"
fi

# =============================================================================
# 3. 체크포인트 및 모델 (학습 결과) - 필수
# =============================================================================
log_info "3. 체크포인트 및 모델 복사 중..."

CHECKPOINT_DIRS=(
    "${HOME}/projectm/Q250-V3-Opti/checkpoints"
    "/Users/amaster/projectm/Q250-V3-Opti/checkpoints"
    "${HOME}/Q250-V3-Opti/checkpoints"
)

for dir in "${CHECKPOINT_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        rsync -av --progress "$dir/" "${PACKAGE_DIR}/checkpoints/"
        log_ok "체크포인트 완료: $dir"
        break
    fi
done

# =============================================================================
# 4. 설정 및 메타데이터
# =============================================================================
log_info "4. 설정 파일 복사 중..."

cp -r "${HOME}/projectm/Q250-V3-Opti/src/preprocessing/config.py" "${PACKAGE_DIR}/config/" 2>/dev/null || true
cp -r "${HOME}/projectm/Q250-V3-Opti/src/preprocessing/core/" "${PACKAGE_DIR}/config/core/" 2>/dev/null || true

# 메타데이터 생성
cat > "${PACKAGE_DIR}/DATASET_INFO.txt" <<EOF
Q250-V3-Opti Dataset Transfer Package
Generated: $(date)
Source: ${SOURCE_BASE}

=== 포함된 데이터셋 ===
1. drone_audio (processed) - 132M
   - Binary: train/val/test features.npz
   - Multiclass: train/val/test features.npz
   - MFCC 40-dim, 157 timesteps

2. uzh_fpv (processed) - 1.2M
   - indoor_forward_3/5/6 sequences
   - IMU (1000Hz) + Images (30Hz) + GT (200Hz)

3. idf_ds (processed) - 87M

4. fixed_wing_attitude (processed) - 68M

5. ign_fixed_wing (processed) - 68K

=== 제외된 데이터셋 (용량 과다) ===
- fpv_analog (processed) - 55GB
  필요시 별도 전송 필요

=== 원본 데이터셋 ===
- DroneAudioDataset (raw)
- UZH-FPV (raw)

=== 체크포인트 ===
- Binary/Multiclass classifier checkpoints
- Best model .pth files

=== 타겟 PC 경로 ===
압축 해제 후: ~/data/drone_datasets/processed/ 에 복사
EOF

# =============================================================================
# 5. 압축 (선택)
# =============================================================================
log_info "5. 압축 생성 중..."

cd "${DEST_BASE}"
PACKAGE_NAME="q250_datasets_${TIMESTAMP}.tar.gz"

# 필수만 압축 (fpv_analog 제외)
tar -czf "${PACKAGE_NAME}" -C "${PACKAGE_DIR}" .

PACKAGE_SIZE=$(du -h "${PACKAGE_NAME}" | cut -f1)
log_ok "압축 완료: ${PACKAGE_NAME} (${PACKAGE_SIZE})"

# =============================================================================
# 6. 체크섬
# =============================================================================
log_info "6. 체크섬 생성 중..."
sha256sum "${PACKAGE_NAME}" > "${PACKAGE_NAME}.sha256"
log_ok "SHA256: $(cat ${PACKAGE_NAME}.sha256 | cut -d' ' -f1)"

# =============================================================================
# 완료
# =============================================================================
echo ""
echo "=========================================="
echo -e "${GREEN}패키징 완료!${NC}"
echo "=========================================="
echo "패키지: ${DEST_BASE}/${PACKAGE_NAME}"
echo "크기: ${PACKAGE_SIZE}"
echo "체크섬: ${PACKAGE_NAME}.sha256"
echo ""
echo "전송 방법:"
echo "  1. USB 드라이브에 복사"
echo "  2. 타겟 PC에서 압축 해제:"
echo "     tar -xzf q250_datasets_${TIMESTAMP}.tar.gz -C ~/data/drone_datasets/"
echo "  3. 체크섬 검증:"
echo "     sha256sum -c ${PACKAGE_NAME}.sha256"
echo ""
echo "타겟 PC 경로 구조:"
echo "  ~/data/drone_datasets/processed/drone_audio/"
echo "  ~/data/drone_datasets/processed/uzh_fpv/"
echo "  ~/data/drone_datasets/processed/idf_ds/"
echo "  ~/data/drone_datasets/processed/fixed_wing_attitude/"
echo "  ~/data/drone_datasets/processed/ign_fixed_wing/"
echo "  ~/checkpoints/ (또는 ~/Q250-V3-Opti/checkpoints/)"