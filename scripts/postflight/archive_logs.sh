#!/bin/bash
# archive_logs.sh - 비행 후 로그 아카이브
# 실행: ./archive_logs.sh

set -e

DATE=$(date +%Y%m%d_%H%M%S)
LOG_DIR=~/flight_logs/$DATE
mkdir -p $LOG_DIR

echo "Archiving flight logs to $LOG_DIR"

# 1. QGC에서 다운로드한 .ulg 복사 (수동 다운로드 후)
# cp ~/Downloads/*.ulg $LOG_DIR/

# 2. Jetson 서비스 로그 아카이브 (최근 2시간)
journalctl -u uxrce-dds-agent --since "2 hours ago" > $LOG_DIR/dds_agent.log 2>/dev/null || true
journalctl -u mavlink-router --since "2 hours ago" > $LOG_DIR/mavlink_router.log 2>/dev/null || true

# 3. 파라미터 스냅샷
if [ -f ~/px4_params/q250-v3-opti_latest.params ]; then
    cp ~/px4_params/q250-v3-opti_latest.params $LOG_DIR/params_backup.params
fi

# 4. 현재 파라미터도 백업 (QGC에서 다운로드 권장)
# ros2 param dump /px4 > $LOG_DIR/px4_params.yaml 2>/dev/null || true

# 5. 비행 메모 템플릿 생성
cat > $LOG_DIR/flight_note.md << EOF
# Flight Log: $DATE
- Duration: ___ min
- Mode: Position / Offboard / Mission
- Purpose: ________________
- Weather: Indoor, Lux: ___, Temp: ___°C
- Battery: ID ___, Start: ___V, End: ___V
- Issues: ________________
- Observations: ________________
- Next Action: ________________
EOF

# 6. Git 커밋 (flight_logs 폴더가 git repo인 경우)
cd ~/flight_logs
if [ -d .git ]; then
    git add $DATE
    git commit -m "Flight log $DATE" 2>/dev/null || true
fi

echo "Archive complete: $LOG_DIR"
echo ""
echo "Next steps:"
echo "1. Download .ulg from QGC (Analyze → Download Logs)"
echo "2. Copy to $LOG_DIR/"
echo "3. Fill in flight_note.md"
echo "4. Run analysis: python3 ~/scripts/postflight/analyze_log.py $LOG_DIR/*.ulg"
