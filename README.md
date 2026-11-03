# Q250-V3 Opti 자율비행 드론 운용 매뉴얼 프로젝트

## 📁 프로젝트 구조

```
Q250-V3-Opti/
├── README.md                    # 이 파일
├── docs/                        # 문서 (마크다운 + 완성본)
│   ├── manual-draft.md          # 초안 (마크다운)
│   ├── manual-final.docx        # 완성본 (워드, 그림 포함)
│   ├── images/                  # 사진, 다이어그램 이미지
│   └── diagrams/                # 개념도 (Mermaid, PlantUML 소스)
├── config/                      # 설정 파일
│   ├── px4/                     # PX4 파라미터 파일
│   ├── jetson/                  # Jetson 설정 파일
│   ├── network/                 # 네트워크 설정
│   └── ros2/                    # ROS 2 설정
├── scripts/                     # 자동화 스크립트
│   ├── setup/                   # 설치 스크립트
│   ├── preflight/               # 비행 전 체크
│   ├── inflight/                # 비행 중 모니터링
│   └── postflight/              # 비행 후 처리
├── ros2_ws/                     # ROS 2 워크스페이스 소스
│   └── src/
├── px4_params/                  # PX4 파라미터 백업/버전관리
├── flight_logs/                 # 비행 로그 아카이브
├── simulation/                  # 시뮬레이션 환경
└── references/                  # 참조 자료 링크/아카이브
```

## 🎯 문서 작성 순서 (HW → SW 설치 → SW 설정 → SW 운용 융합)

### 1단계: 하드웨어 설정 (HW Setup)
- 기체 조립 및 점검
- FC 포트맵 및 배선
- 컴패니언 컴퓨터 장착 및 전원
- RC 수신기 연결
- 네트워크 토폴로지 구성

### 2단계: 소프트웨어 설치 (SW Installation)
- PX4 펌웨어 빌드/플래싱
- Jetson OS (JetPack) 설치
- ROS 2 Humble 설치
- QGroundControl 설치
- 필수 드라이버/라이브러리

### 3단계: 소프트웨어 설정 (SW Configuration)
- PX4 파라미터 설정 (QGC)
- MAVLink Router 설정
- uXRCE-DDS Agent 설정
- ROS 2 워크스페이스 빌드
- 네트워크/방화벽/보안 설정

### 4단계: 운용 융합 (Operation Integration)
- 비행 전 체크리스트
- 비행 모드별 운용 절차
- 비상 절차
- 로그 분석 및 튜닝
- 군집비행 확장

---

## 🚀 빠른 시작

```bash
# 1. 저장소 클론 (이 폴더에서 작업)
cd /Users/amaster/projectm/Q250-V3-Opti

# 2. 설치 스크립트 실행 (순서대로)
./scripts/setup/01_jetson_base.sh
./scripts/setup/02_ros2_humble.sh
./scripts/setup/03_px4_firmware.sh
./scripts/setup/04_mavlink_router.sh
./scripts/setup/05_uxrce_dds_agent.sh

# 3. 설정 적용
./scripts/setup/apply_configs.sh

# 4. 비행 전 체크
./scripts/preflight/check_all.sh
```

---

## 📋 문서 버전 관리

| 버전 | 날짜 | 작성자 | 주요 변경사항 |
|------|------|--------|---------------|
| 0.1 (초안) | 2026-11-02 | Hermes Agent | 전체 구조 및 내용 초안 작성 |
| 1.0 (완성) | - | - | 그림/사진/개념도 포함 완성본 |

---

## 🔗 핵심 참조 링크

- **Q250-V3 Opti 공식**: https://quad-drone-lab.gitbook.io/quad-drone-start/q250/q250-v3-opti
- **PX4 공식 문서**: https://docs.px4.io/main/en/
- **ROS 2 PX4 가이드**: https://docs.px4.io/main/en/ros2/user_guide
- **쿼드 드론연구소**: https://quad-drone-lab.co.kr/

---

## 📄 완성본 생성 방법 (manual-final.docx)

### 필요 도구 설치
```bash
# Python 패키지
pip install python-docx markdown2 beautifulsoup4 pillow

# Mermaid CLI (다이어그램 렌더링용)
npm install -g @mermaid-js/mermaid-cli

# 또는 Docker 사용
docker run --rm -v $(pwd)/docs/diagrams:/data -v $(pwd)/docs/images:/output minlag/mermaid-cli -i /data/*.mmd -o /output
```

### 변환 실행
```bash
cd /Users/amaster/projectm/Q250-V3-Opti
python3 scripts/convert_to_docx.py
```

### 수동 변환 대안 (Pandoc)
```bash
# Pandoc 설치 후
pandoc docs/manual-draft.md -o docs/manual-final.docx \
    --from markdown+mermaid \
    --to docx \
    --resource-path=docs/images \
    --pdf-engine=weasyprint
```

### 이미지/다이어그램 추가 가이드
1. `docs/images/` 폴더에 실제 기체 사진 배치:
   - `q250-v3-opti-top.jpg` (기체 상단 뷰)
   - `q250-v3-opti-side.jpg` (측면 뷰)
   - `pixhawk6c-mini-ports.jpg` (FC 포트 클로즈업)
   - `jetson-nano-mount.jpg` (Jetson 장착)
   - `wiring-t2-telem2.jpg` (TELEM2 배선)
   - `wiring-uart4-oflidar.jpg` (Optical-Flow/LiDAR 배선)
   - `rc-receiver-connection.jpg` (RC 수신기 연결)
   - `battery-ubec-mount.jpg` (배터리/UBEC 마운트)

2. Mermaid 다이어그램 자동 렌더링 시 `docs/images/`에 PNG 생성됨

3. 초안의 `[[IMAGE:...]]` 플레이스홀더가 실제 이미지로 치환됨


## 📡 실버스(StreamCaster) 데이터링크 통합

### 보유 자산
- **GDT (Ground Data Terminal)**: 1대 — 지상국 게이트웨이
- **Air Unit**: 4대 — 기체 4대 장착 (예비 1대)
- **웨이브폼**: **MN-MIMO** (군용급 MANET, TDMA/OFDMA, AES-256)

### 핵심 성능
| 지표 | 값 |
|------|-----|
| 단일 홉 처리량 | 80~120 Mbps |
| 지연 (1홉) | 3~8 ms (RTT) |
| 최대 홉 수 | 5~8 홉 |
| 거리 (LOS) | 20~50 km |
| 암호화 | AES-256 + TRANSEC |

### 관련 파일
- `config/mavlink-router/main_silvus.conf` — MAVLink 라우팅 설정
- `config/jetson/fastdds_silvus_config.xml` — ROS2 DDS 설정
- `scripts/silvus_monitor.py` — 링크 상태 모니터링 ROS2 노드
- `config/silvus_checklist.md` — 초기 설정 체크리스트

### 빠른 시작
```bash
# 1. 펌웨어 통일 (5대 모두 동일 버전)
# 2. 웹 UI에서 주파수/파워/암호화 키 설정
# 3. 벤치 테스트: 5대 연결 → 웹 UI 토폴로지 확인
# 4. 기체 1대 통합 → MAVLink/ROS2 트래픽 검증
# 5. 실내 비행 테스트 → 2~4대 순차 확장
```
