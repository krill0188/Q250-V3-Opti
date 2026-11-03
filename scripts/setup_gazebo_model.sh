#!/bin/bash
# setup_gazebo_model.sh - Gazebo 모델 경로 등록 및 PX4 연동

set -e

echo "=========================================="
echo "Gazebo Model Setup for Q250-V3 Opti"
echo "=========================================="

MODEL_DIR=~/projectm/Q250-V3-Opti/simulation/models/q250_v3_opti
PX4_DIR=~/PX4-Autopilot

# 1. GAZEBO_MODEL_PATH 환경변수 등록
if ! grep -q "GAZEBO_MODEL_PATH.*q250_v3_opti" ~/.bashrc; then
    echo 'export GAZEBO_MODEL_PATH=~/projectm/Q250-V3-Opti/simulation/models:$GAZEBO_MODEL_PATH' >> ~/.bashrc
    echo "Added GAZEBO_MODEL_PATH to ~/.bashrc"
fi

# 2. PX4에 모델 심볼릭 링크 (ROMFS 경로)
PX4_MODEL_DIR=$PX4_DIR/ROMFS/px4fmu_common/init.d-posix/airframes
if [ ! -f $PX4_MODEL_DIR/4001_q250_v3_opti ]; then
    echo "Creating PX4 airframe config..."
    sudo tee $PX4_MODEL_DIR/4001_q250_v3_opti > /dev/null << 'EOF'
#!/bin/sh
#
# Q250-V3 Opti
#
# @airframe Q250-V3 Opti
# @outputs MAIN1 MAIN2 MAIN3 MAIN4
# @board px4_fmu-v6c

. ${R}etc/init.d/rc.mc_defaults

# Motor order: FR, RL, FL, RR (PX4 standard)
# FR: AUX1 (CW), RL: AUX2 (CW), FL: AUX3 (CCW), RR: AUX4 (CCW)

param set-default CA_AIRFRAME 0
param set-default CA_ROTOR_COUNT 4

# Motor positions (FRD, COG origin)
param set-default CA_MOT_POS_X1 0.12
param set-default CA_MOT_POS_Y1 -0.12
param set-default CA_MOT_POS_Z1 -0.025
param set-default CA_MOT_DIR_CCW1 0

param set-default CA_MOT_POS_X2 -0.12
param set-default CA_MOT_POS_Y2 -0.12
param set-default CA_MOT_POS_Z2 -0.025
param set-default CA_MOT_DIR_CCW2 0

param set-default CA_MOT_POS_X3 0.12
param set-default CA_MOT_POS_Y3 0.12
param set-default CA_MOT_POS_Z3 -0.025
param set-default CA_MOT_DIR_CCW3 1

param set-default CA_MOT_POS_X4 -0.12
param set-default CA_MOT_POS_Y4 0.12
param set-default CA_MOT_POS_Z4 -0.025
param set-default CA_MOT_DIR_CCW4 1

# Optical-Flow & LiDAR
param set-default EKF2_OF_CTRL 1
param set-default EKF2_RNG_CTRL 2
param set-default EKF2_HGT_REF 2
param set-default SENS_FLOW_ROT 0
param set-default EKF2_OF_POS_Z -0.035
param set-default EKF2_RNG_POS_Z -0.040
param set-default EKF2_RNG_NOISE 0.02

# Indoor EKF2
param set-default EKF2_GPS_CTRL 0
param set-default EKF2_MAG_TYPE 5
param set-default EKF2_AID_MASK 352

# Optical-Flow UART4
param set-default MAV_1_CONFIG 4
param set-default MAV_1_MODE 1
param set-default SER_TEL4_BAUD 115200

# Companion Computer (uXRCE-DDS)
param set-default UXRCE_DDS_CFG 2
param set-default UXRCE_DDS_AG_IP 2130706433
param set-default UXRCE_DDS_PRT 8888
param set-default SER_TEL2_BAUD 921600

# Battery
param set-default BAT_V_DIV 54.5
param set-default BAT_A_PER_V 18.0
param set-default BAT_N_CELLS 4
param set-default BAT_CAPACITY 4000

# Indoor Safety
param set-default GF_ACTION 1
param set-default GF_MAX_HOR_DIST 10.0
param set-default GF_MAX_VER_DIST 2.5
param set-default COM_RC_LOSS_T 0.5
param set-default COM_RCL_ACT 2
EOF
    echo "Created PX4 airframe config: 4001_q250_v3_opti"
fi

# 3. 심볼릭 링크로 PX4 모델 디렉토리에 연결 (대안)
PX4_SITL_MODELS=$PX4_DIR/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models
if [ ! -L $PX4_SITL_MODELS/q250_v3_opti ]; then
    ln -sf ~/projectm/Q250-V3-Opti/simulation/models/q250_v3_opti $PX4_SITL_MODELS/q250_v3_opti
    echo "Linked model to PX4 SITL models directory"
fi

# 4. GAZEBO_MODEL_PATH 즉시 적용
export GAZEBO_MODEL_PATH=~/projectm/Q250-V3-Opti/simulation/models:$GAZEBO_MODEL_PATH

echo ""
echo "=========================================="
echo "Gazebo Model Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. source ~/.bashrc"
echo "2. Test model loading:"
echo "   gzserver --verbose --model q250_v3_opti"
echo ""
echo "3. Run PX4 SITL with custom model:"
echo "   cd ~/PX4-Autopilot"
echo "   PX4_SIM_MODEL=q250_v3_opti make px4_sitl gz_q250_v3_opti"
echo ""
echo "Or use the launch file:"
echo "   ros2 launch q250_v3_opti q250_v3_opti_sitl.launch.py"
