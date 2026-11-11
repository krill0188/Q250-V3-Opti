#!/bin/bash
# =====================================================================
# Q250-V3-Opti: 전체 데이터셋 일괄 다운로드 스크립트
# Non-GPS 고정익, FPV 다이브, 이기종 드론 데이터셋 통합
# =====================================================================

set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 기본 경로
DATA_ROOT="${HOME}/data/drone_datasets"
LOG_FILE="${DATA_ROOT}/download_$(date +%Y%m%d_%H%M%S).log"

# 디렉토리 생성
mkdir -p "${DATA_ROOT}"/{idf_ds,fixed_wing_attitude,uzh_fpv,fpv_analog,forvis,ign_fixed_wing,navigation_datasets}
mkdir -p "${DATA_ROOT}/scripts"

# 로그 함수
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*" | tee -a "${LOG_FILE}"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "${LOG_FILE}"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "${LOG_FILE}"
}

# 진행률 표시
show_progress() {
    local current=$1
    local total=$2
    local name=$3
    local percent=$((current * 100 / total))
    echo -ne "${BLUE}[${current}/${total}]${NC} ${name} ... ${percent}%\r"
}

# 크기 확인
check_disk_space() {
    local available=$(df -h "${DATA_ROOT}" | awk 'NR==2 {print $4}')
    log "사용 가능한 디스크 공간: ${available}"
    local available_kb=$(df "${DATA_ROOT}" | awk 'NR==2 {print $4}')
    if [ "${available_kb}" -lt 104857600 ]; then  # 100GB 미만
        warn "디스크 공간이 100GB 미만입니다. 정리 후 진행하세요."
    fi
}

# =====================================================================
# 1. IDF-DS (Non-GPS 고정익, Zenodo) - 가장 중요
# =====================================================================
download_idf_ds() {
    log "=== [1/7] IDF-DS 다운로드 (Non-GPS 고정익, ~30GB) ==="
    cd "${DATA_ROOT}/idf_ds"
    
    if command -v zenodo-get &> /dev/null; then
        zenodo-get 16992975 2>&1 | tee -a "${LOG_FILE}"
    else
        warn "zenodo-get 미설치. 설치 중..."
        pip install zenodo-get 2>&1 | tee -a "${LOG_FILE}"
        zenodo-get 16992975 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    log "IDF-DS 다운로드 완료"
}

# =====================================================================
# 2. Fixed-Wing UAV Attitude Dataset (GitHub LFS)
# =====================================================================
download_fixed_wing_attitude() {
    log "=== [2/7] Fixed-Wing UAV Attitude Dataset (GitHub LFS, ~5GB) ==="
    cd "${DATA_ROOT}/fixed_wing_attitude"
    
    if [ ! -d "Fixed-Wing-UAV-Attitude-Dataset" ]; then
        git lfs install
        git clone https://github.com/LiWentao0316/Fixed-Wing-UAV-Attitude-Dataset.git 2>&1 | tee -a "${LOG_FILE}"
    else
        cd Fixed-Wing-UAV-Attitude-Dataset
        git lfs pull 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    log "Fixed-Wing Attitude Dataset 다운로드 완료"
}

# =====================================================================
# 3. UZH-FPV Drone Racing (공식 사이트)
# =====================================================================
download_uzh_fpv() {
    log "=== [3/7] UZH-FPV Drone Racing (공식, ~20GB) ==="
    cd "${DATA_ROOT}/uzh_fpv"
    
    # 공식 사이트에서 다운로드 (wget 미러링)
    if [ ! -f ".downloaded" ]; then
        wget -r -np -nH --cut-dirs=2 -R "index.html*" \
             --reject "index.html*" \
             --wait=1 --random-wait \
             --limit-rate=5m \
             https://fpv.ifi.uzh.ch/datasets/ 2>&1 | tee -a "${LOG_FILE}"
        touch .downloaded
    else
        log "이미 다운로드됨 (스킵). 강제 재다운로드: rm .downloaded"
    fi
    
    log "UZH-FPV 다운로드 완료"
}

# =====================================================================
# 4. FPV Analog Video Signal (HuggingFace)
# =====================================================================
download_fpv_analog() {
    log "=== [4/7] FPV Analog Video Signal (HuggingFace, ~3GB) ==="
    cd "${DATA_ROOT}/fpv_analog"
    
    if command -v hf &> /dev/null; then
        hf download lll-a-p/fpv-drone-detection-snapshot --repo-type dataset --local-dir . 2>&1 | tee -a "${LOG_FILE}"
    else
        warn "huggingface-cli (hf) 미설치. 설치: pip install huggingface_hub[cli]"
        pip install huggingface_hub[cli] 2>&1 | tee -a "${LOG_FILE}"
        hf download lll-a-p/fpv-drone-detection-snapshot --repo-type dataset --local-dir . 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    # 압축 해제
    for zip in *.zip; do
        if [ -f "$zip" ]; then
            unzip -n "$zip" -d "${zip%.zip}" 2>&1 | tee -a "${LOG_FILE}"
        fi
    done
    
    log "FPV Analog 다운로드 완료"
}

# =====================================================================
# 5. ForVis (Forest Vision) - Google Drive
# =====================================================================
download_forvis() {
    log "=== [5/7] ForVis Forest Vision (Google Drive, ~10GB) ==="
    cd "${DATA_ROOT}/forvis"
    
    if command -v gdown &> /dev/null; then
        # ForVis Google Drive 폴더 ID: 1T3nJRqQwyy-msXUD_-oBVeV6XnQXUZ76
        gdown --folder "https://drive.google.com/drive/folders/1T3nJRqQwyy-msXUD_-oBVeV6XnQXUZ76" 2>&1 | tee -a "${LOG_FILE}"
    else:
        warn "gdown 미설치. 설치: pip install gdown"
        pip install gdown 2>&1 | tee -a "${LOG_FILE}"
        gdown --folder "https://drive.google.com/drive/folders/1T3nJRqQwyy-msXUD_-oBVeV6XnQXUZ76" 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    log "ForVis 다운로드 완료"
}

# =====================================================================
# 6. IGN Fixed-Wing Micro UAV (Zenodo)
# =====================================================================
download_ign_fixed_wing() {
    log "=== [6/7] IGN Fixed-Wing Micro UAV (Zenodo, ~6GB) ==="
    cd "${DATA_ROOT}/ign_fixed_wing"
    
    if command -v zenodo-get &> /dev/null; then
        zenodo-get 4476489 2>&1 | tee -a "${LOG_FILE}"
    else:
        pip install zenodo-get 2>&1 | tee -a "${LOG_FILE}"
        zenodo-get 4476489 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    log "IGN Fixed-Wing 다운로드 완료"
}

# =====================================================================
# 7. Navigation Datasets (GitHub)
# =====================================================================
download_navigation_datasets() {
    log "=== [7/7] Navigation Datasets (GitHub, 메타데이터만) ==="
    cd "${DATA_ROOT}/navigation_datasets"
    
    # Navigation-Dataset 메타데이터
    if [ ! -d "Navigation-Dataset" ]; then
        git clone https://github.com/xk19o3/Navigation-Dataset.git 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    # Awesome Aerial Localization Datasets
    if [ ! -d "awesome-aerial-localization-datasets" ]; then
        git clone https://github.com/michaelschleiss/awesome-aerial-localization-datasets.git 2>&1 | tee -a "${LOG_FILE}"
    fi
    
    log "Navigation Datasets 메타데이터 다운로드 완료"
}

# =====================================================================
# 메인 실행
# =====================================================================
main() {
    log "========================================"
    log "Q250-V3-Opti 전체 데이터셋 다운로드 시작"
    log "대상 경로: ${DATA_ROOT}"
    log "예상 총 용량: 70-100GB"
    log "예상 소요 시간: 2-6시간 (네트워크/디스크 속도 의존)"
    log "========================================"
    
    check_disk_space
    
    # 필수 도구 설치
    log "필수 도구 확인/설치 중..."
    pip install --quiet zenodo-get gdown huggingface_hub[cli] git-lfs 2>&1 | tail -5
    git lfs install
    
    # 순차 실행 (병렬 실행 시 네트워크/디스크 병목 방지)
    download_idf_ds
    download_fixed_wing_attitude
    download_uzh_fpv
    download_fpv_analog
    download_forvis
    download_ign_fixed_wing
    download_navigation_datasets
    
    # 요약
    log "========================================"
    log "모든 다운로드 완료!"
    log "데이터 위치: ${DATA_ROOT}"
    du -sh "${DATA_ROOT}"/* 2>/dev/null | sort -hr
    log "로그 파일: ${LOG_FILE}"
    log "========================================"
}

# 실행
main "$@"