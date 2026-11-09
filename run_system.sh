#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN} [SpecKit Hybrid System] 드론(MAVSDK/MAVROS2) & 로봇(ROS2) & 하이브리드 통합 기동 ${NC}"
echo -e "${GREEN}=================================================================${NC}"

# 파라미터 파싱
MODE="sitl"
FCU_URL="udp://:14540@127.0.0.1:14557"
WITH_LLM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --fcu-url)
            FCU_URL="$2"
            shift 2
            ;;
        --with-llm)
            WITH_LLM=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

cleanup() {
    echo -e "\n${YELLOW}[SHUTDOWN] 전체 브릿지 노드 및 GCS 서버를 안전하게 종료합니다...${NC}"
    if [ ! -z "$LLM_PID" ]; then
        kill -INT "$LLM_PID" 2>/dev/null || true
    fi
    if [ ! -z "$LAUNCH_PID" ]; then
        kill -INT "$LAUNCH_PID" 2>/dev/null || true
    fi
    if [ ! -z "$GCS_PID" ]; then
        kill -INT "$GCS_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

echo -e "\n${YELLOW}[Step 1/5] 코어 안전 검증기 및 우선순위 중재기 무결성 테스트(pytest) 실행...${NC}"
if command -v pytest &> /dev/null; then
    pytest tests/test_safety_core.py tests/test_risk_analyzer.py -v
    echo -e "${GREEN}[PASS] 모든 안전 가드레일 테스트를 통과했습니다.${NC}"
else
    echo -e "${RED}[WARN] pytest가 설치되어 있지 않습니다. (pip install -r requirements.txt 권장)${NC}"
fi

echo -e "\n${YELLOW}[Step 2/5] ROS2 미들웨어 환경 로드...${NC}"
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
    echo -e "${GREEN}ROS2 Jazzy 환경 로드 완료.${NC}"
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
    echo -e "${GREEN}ROS2 Humble 환경 로드 완료.${NC}"
else
    echo -e "${YELLOW}[INFO] 표준 /opt/ros 경로에서 ROS2를 찾지 못했습니다. 현재 셸 환경을 유지합니다.${NC}"
fi

# LLM 서버 시작 (옵션)
if [ "$WITH_LLM" = true ]; then
    echo -e "\n${YELLOW}[Step 3/5] 로컬 LLM 서버 (Llama.cpp) 시작...${NC}"
    MODEL_PATH=~/models/llama-3.1-8b-q4_k_m.gguf
    if [ -f "$MODEL_PATH" ]; then
        docker run --rm -d --name llm-server \
            --gpus all \
            -p 8080:8080 \
            -v ~/models:/models \
            ghcr.io/ggerganov/llama.cpp:server-cuda \
            -m /models/llama-3.1-8b-q4_k_m.gguf \
            -c 4096 --host 0.0.0.0 --port 8080 \
            --n-gpu-layers -1 --parallel 4 &
        LLM_PID=$!
        sleep 5
        echo -e "${GREEN}[OK] LLM 서버 시작됨 (http://localhost:8080)${NC}"
    else
        echo -e "${YELLOW}[WARN] LLM 모델 없음: $MODEL_PATH${NC}"
        echo -e "  다운로드: huggingface-cli download bartowski/Llama-3.1-8B-Instruct-GGUF llama-3.1-8b-q4_k_m.gguf --local-dir ~/models"
    fi
fi

echo -e "\n${YELLOW}[Step 4/5] ROS2 Bringup Launch 실행 (Mode: ${MODE}, FCU: ${FCU_URL})...${NC}"
if command -v ros2 &> /dev/null && [ -f "launch/bringup.launch.py" ]; then
    USE_SIM="true"
    if [ "$MODE" == "real" ]; then
        USE_SIM="false"
    fi
    ros2 launch launch/bringup.launch.py use_sim_time:=$USE_SIM fcu_url:=$FCU_URL &
    LAUNCH_PID=$!
    sleep 2
else
    echo -e "${YELLOW}[INFO] ros2 launch 실행을 생략하고 단독 브릿지 모드로 진입합니다.${NC}"
fi

echo -e "\n${YELLOW}[Step 5/5] 통합 제어 서버(GCS Dashboard + Arbitrator + Voice Engine + LLM Risk) 가동...${NC}"
echo -e "${GREEN}>>> 웹 브라우저에서 http://localhost:8000 에 접속하세요 <<<${NC}"
uvicorn gcs_server:app --host 0.0.0.0 --port 8000 &
GCS_PID=$!

wait $GCS_PID
