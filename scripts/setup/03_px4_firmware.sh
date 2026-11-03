#!/bin/bash
# 03_px4_firmware.sh - PX4 펌웨어 빌드/플래싱 (개발 PC에서 실행)
# 실행: ./03_px4_firmware.sh [build|flash|both]

set -e

ACTION=${1:-both}

echo "=========================================="
echo "PX4 Firmware Build/Flash for Q250-V3 Opti"
echo "Target: Holybro Pixhawk 6C mini (FMUv6C)"
echo "Branch: v1.15 (v1.16+ Optical-Flow 미지원)"
echo "=========================================="

# PX4 소스 준비
PX4_DIR=~/PX4-Autopilot

if [ ! -d "$PX4_DIR" ]; then
    echo "[1/4] Cloning PX4-Autopilot v1.15..."
    git clone https://github.com/PX4/PX4-Autopilot.git --branch v1.15 --recursive $PX4_DIR
else
    echo "[1/4] PX4-Autopilot already exists, updating..."
    cd $PX4_DIR
    git fetch origin
    git checkout v1.15
    git pull origin v1.15
    git submodule update --init --recursive
fi

cd $PX4_DIR

# 툴체인 설치
echo "[2/4] Installing toolchain..."
bash ./Tools/setup/ubuntu.sh

# 빌드
if [ "$ACTION" = "build" ] || [ "$ACTION" = "both" ]; then
    echo "[3/4] Building PX4 firmware for Pixhawk 6C mini..."
    make px4_fmu-v6c_default
    
    if [ $? -eq 0 ]; then
        echo "Build successful!"
        ls -la build/px4_fmu-v6c_default/*.px4 2>/dev/null || echo "Firmware file location may vary"
    else
        echo "Build failed!"
        exit 1
    fi
fi

# 플래싱
if [ "$ACTION" = "flash" ] || [ "$ACTION" = "both" ]; then
    echo "[4/4] Flashing firmware (connect FC via USB)..."
    echo "Ensure FC is in bootloader mode (safety switch pressed while connecting USB)"
    read -p "Press Enter when ready..."
    make px4_fmu-v6c_default upload
fi

echo ""
echo "=========================================="
echo "PX4 Firmware process complete!"
echo "=========================================="
echo ""
echo "Alternative: Use QGroundControl for flashing (recommended for beginners)"
echo "QGC → Gear icon → Firmware → Custom firmware file → Select .px4 file"
