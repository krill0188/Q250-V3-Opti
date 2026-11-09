#!/bin/bash
# DREGON 드론 노이즈 데이터셋 다운로드 스크립트
# 공식 INRIA 사이트에서 In-Flight Noise-Only Recordings만 다운로드

set -e

DATA_DIR="${HOME}/data/dregon_noise"
mkdir -p "${DATA_DIR}"
cd "${DATA_DIR}"

BASE_URL="https://dregon.inria.fr/datasets/dregon"

# Noise-only recordings (프로펠러 소음만 있는 파일들)
FILES=(
    "DREGON_free-flight_nosource_room1.zip"
    "DREGON_free-flight_nosource_room2.zip"
    "DREGON_hovering_nosource_room2.zip"
    "DREGON_updown_nosource_room2.zip"
    "DREGON_rectangle_nosource_room2.zip"
    "DREGON_spinning_nosource_room2.zip"
)

echo "=== DREGON Noise-Only Recordings 다운로드 시작 ==="
echo "대상 디렉토리: ${DATA_DIR}"
echo "파일 수: ${#FILES[@]}"
echo ""

for FILE in "${FILES[@]}"; do
    URL="${BASE_URL}/${FILE}"
    echo "다운로드: ${FILE}"
    
    if [ -f "${FILE}" ]; then
        echo "  → 이미 존재함, 건너뜀"
    else
        # wget으로 다운로드 (재시도 3회, 진행률 표시)
        wget -c --tries=3 --timeout=30 --show-progress "${URL}" || {
            echo "  ⚠️  다운로드 실패: ${FILE}"
            echo "     수동 다운로드: ${URL}"
            continue
        }
    fi
    
    # 압축 해제
    if [ -f "${FILE}" ]; then
        echo "  압축 해제 중..."
        unzip -o -q "${FILE}" -d "${FILE%.zip}" || {
            echo "  ⚠️  압축 해제 실패: ${FILE}"
        }
        
        # .wav 파일만 상위로 이동 (선택적)
        find "${FILE%.zip}" -name "*.wav" -exec mv {} "${DATA_DIR}/" \;
    fi
done

echo ""
echo "=== 다운로드 완료 ==="
echo "확인: ls -la ${DATA_DIR}/*.wav"
echo ""

# 파일 크기 확인
echo "다운로드된 WAV 파일:"
ls -lh "${DATA_DIR}"/*.wav 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || echo "  (WAV 파일 없음 - 압축 해제 확인 필요)"

# 전체 크기
TOTAL=$(du -sh "${DATA_DIR}" 2>/dev/null | cut -f1)
echo "전체 크기: ${TOTAL}"