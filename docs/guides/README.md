# Q250-V3 Opti 실전 가이드 마스터 인덱스

> **이 문서부터 읽으세요** - 전체 가이드맵과 실행 순서, 의존성 관계를 한눈에 파악할 수 있습니다.

---

## 🎯 Q250-V3 Opti 프로젝트 전체 로드맵

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Q250-V3 Opti 자율비행 완성 로드맵                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 0: 환경 구축 (1회)                                                   │
│  ├─ 05_dev_environment_setup_guide.md  ← 개발 PC + Jetson 완전 설정        │
│  │   └─ WSL2, ROS 2, PX4, Docker, VS Code, SSH, 네트워크                  │
│  │                                                                           │
│  Phase 1: 하드웨어 및 기초 통신 (1주)                                       │
│  ├─ 기체 조립, 배선, 센서 장착 (Pixhawk 6C Mini, Jetson Nano, Silvus)     │
│  ├─ PX4 v1.15 펌웨어 빌드/플래싱                                           │
│  ├─ MAVLink Router, uXRCE-DDS Agent 설정                                   │
│  └─ Silvus 데이터링크 벤치 테스트                                          │
│                                                                             │
│  Phase 2: PX4 기초 및 실내 EKF2 튜닝 (1~2주)                               │
│  ├─ EKF2 이해: 센서 융합, Aid Mask, Innovation 모니터링                    │
│  ├─ 실내 모드 파라미터 적용 (GPS/Mag OFF, OF/Range ON)                     │
│  └─ SITL/벤치에서 기본 비행 모드 검증                                      │
│                                                                             │
│  Phase 3: VIO → EKF2 연동 (핵심, 2~3주)  ← ★★★ 최우선                      │
│  ├─ 01_vio_ekf2_integration_guide.md  ← 단계별 실전 가이드                │
│  │   ├─ Phase 1: RealSense 드라이버/토픽 검증                             │
│  │   ├─ Phase 2: VIO 노드(OpenVINS) 설치 및 포즈 출력 검증                │
│  │   ├─ Phase 3: 좌표계 검증 (TF 트리, ENU↔NED, 카메라 마운트 실측)       │
│  │   ├─ Phase 4: 통신 경로 선택 (MAVROS vs px4_ros_com)                   │
│  │   ├─ Phase 5: EKF2 파라미터 적용 및 혁신 모니터링 (핵심!)              │
│  │   ├─ Phase 6: Position 모드 진입 테스트 (무프로펠러→실내 비행)         │
│  │   └─ Phase 7: non-GPS 비행 모드 및 fake GPS 연계                       │
│  │                                                                           │
│  Phase 4: Fake GPS 구현 (Mission/RTL/Geofence 활성화, 2~3일)              │
│  ├─ 03_fake_gps_guide.md  ← fake GPS 완전 구현 가이드                     │
│  │   ├─ Phase 1: 패키지 빌드 및 설정 (원점 Datum 설정 중요!)              │
│  │   ├─ Phase 2: 벤치 테스트 (MAVROS GPS_INPUT, QGC Map 확인)            │
│  │   ├─ Phase 3: PX4 파라미터 설정 (EKF2_GPS_CTRL=7)                     │
│  │   ├─ Phase 4: Mission/RTL/Geofence 테스트 (SITL→실기체)              │
│  │   └─ Phase 5: 실내 비행 검증 (드리프트 모니터링 포함)                 │
│  │                                                                           │
│  Phase 5: 자율 회피 파이프라인 (2~3주)                                     │
│  ├─ 02_obstacle_avoidance_guide.md  ← 회피 파이프라인 가이드            │
│  │   ├─ Phase 1: 센서 파이프라인 검증 (Depth, PointCloud, LiDAR, TF)     │
│  │   ├─ Phase 2: Costmap/장애물 표현 검증 (Inflation, 블라인드 스팟)      │
│  │   ├─ Phase 3: TEB 플래너 단독 테스트 (가상 목표/장애물 시나리오)       │
│  │   ├─ Phase 4: PX4 OFFBOARD 연동 (무프로펠러 벤치 테스트)              │
│  │   ├─ Phase 5: 실내 비행 테스트 (8단계 시나리오, 안전 최우선)         │
│  │   └─ Phase 6: 지속적 개선 (파라미터 튜닝, 실패 케이스 문서화)         │
│  │                                                                           │
│  Phase 6: 비행 로그 분석 및 지속적 개선 (상시)                            │
│  ├─ 04_flight_log_analysis_guide.md  ← 멀티모달 로그 분석 파이프라인    │
│  │   ├─ Phase 1: 비행 후 데이터 수집 및 SHA-256 Provenance 기록          │
│  │   ├─ Phase 2: 자동 파싱 (ulog, MAVLink PCAP, 텍스트, Silvus, ROS bag) │
│  │   ├─ Phase 3: DB 적재 및 시간 정렬 (TimeAligner)                      │
│  │   ├─ Phase 4: 자동 분석 리포트 생성 (EKF2, VIO, GPS, 회피, Silvus)   │
│  │   ├─ Phase 5: 트렌드 분석 및 파라미터 튜닝 피드백 루프                │
│  │   └─ Phase 6: 아카이브 및 문서화                                      │
│  │                                                                           │
│  Phase 7: Silvus 데이터링크 고도화 & 군집 비행 (2주+)                     │
│  ├─ Silvus MN-MIMO 특성 이해 및 링크 품질 모니터링                        │
│  ├─ MAVLink Router 멀티엔드포인트 라우팅                                  │
│  ├─ Fast-DDS 튜닝 (대역폭/지연 최적화)                                   │
│  ├─ 링크 품질 → 비행 파라미터 동적 연동 (planner 속도 자동 감속)         │
│  └─ 군집 비행 아키텍처 (리더-팔로워, 컨센서스)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 가이드별 의존성 및 실행 순서

| 순서 | 가이드 | 선행 조건 | 산출물 | 예상 기간 |
|------|--------|-----------|--------|-----------|
| **1** | `05_dev_environment_setup_guide.md` | 없음 | 개발 PC + Jetson 완전 동기화 환경 | 2~3시간 |
| **2** | 하드웨어 조립 & 펌웨어 | 가이드 1 완료 | 비행 가능 기체 | 1주 |
| **3** | PX4 기초 & 실내 EKF2 | 가이드 2 완료 | 실내 Position 모드 안정 비행 | 1~2주 |
| **4** | `01_vio_ekf2_integration_guide.md` | PX4 실내 모드 안정 | **VIO→EKF2 융합, Position 모드 자율 비행** | **2~3주** |
| **5** | `03_fake_gps_guide.md` | VIO→EKF2 완료 | Mission/RTL/Geofence 활성화 | 2~3일 |
| **6** | `02_obstacle_avoidance_guide.md` | VIO→EKF2 완료 | 자율 회피 비행 | 2~3주 |
| **7** | `04_flight_log_analysis_guide.md` | 비행 데이터 존재 | 자동 분석 리포트, 튜닝 피드백 | 상시 |
| **8** | Silvus/군집 비행 | 단일 기체 완전 자율 | 다중 기체 자율 협업 | 2주+ |

> **💡 핵심 경로**: 1 → 2 → 3 → **4** → (5, 6 병렬 가능) → 7 → 8
> - **Phase 4(VIO→EKF2)가 모든 자율 비행의 전제조건**임
> - Phase 5(fake GPS)와 Phase 6(회피)는 Phase 4 완료 후 **병렬 진행 가능**

---

## 📁 생성된 전체 문서 구조

```
/Users/amaster/projectm/Q250-V3-Opti/
├── docs/
│   ├── guides/                    # ★★★ 실전 단계별 가이드 (여기서 시작하세요)
│   │   ├── 01_vio_ekf2_integration_guide.md      # VIO→EKF2 연동 (핵심)
│   │   ├── 02_obstacle_avoidance_guide.md        # 자율 회피 파이프라인
│   │   ├── 03_fake_gps_guide.md                  # Fake GPS 구현
│   │   ├── 04_flight_log_analysis_guide.md       # 비행 로그 분석 파이프라인
│   │   └── 05_dev_environment_setup_guide.md     # 개발 환경 설정 (첫 시작)
│   │
│   ├── 07-vio-ekf2-integration.md                # VIO→EKF2 상세 기술 문서
│   ├── 12-obstacle-avoidance-pipeline.md         # 회피 파이프라인 상세
│   ├── 13-fake-gps-implementation.md             # Fake GPS 상세 구현
│   ├── learning-roadmap.md                       # 10단계 학습 로드맵
│   ├── architecture.md                           # 시스템 아키텍처 + AI/LLM 원칙
│   ├── manual-draft.md                           # 운용 매뉴얼 초안
│   └── diagrams/                                 # Mermaid 다이어그램들
│
├── ros2_ws/src/
│   ├── fake_gps/                                 # Fake GPS ROS 2 패키지
│   │   ├── fake_gps/fake_gps_node.py             # 메인 노드 (ENU→LLA 변환)
│   │   ├── launch/fake_gps.launch.py             # Launch 파일
│   │   └── config/fake_gps.yaml                  # 설정 파일
│   │
│   └── obstacle_avoidance/                       # 회피 파이프라인 패키지
│       ├── obstacle_avoidance/obstacle_distance_pub.py  # LiDAR→OBSTACLE_DISTANCE
│       ├── obstacle_avoidance/safety_watchdog.py        # 플래너 워치독 + Silvus 연동
│       ├── launch/obstacle_avoidance.launch.py          # 통합 Launch
│       └── config/ (teb_params.yaml, costmap_params.yaml)
│
├── integration/                                  # 비행 로그 분석 어댑터
│   ├── flightlog_adapter.py      # PX4 ulog 파싱 + Provenance
│   ├── mavlink_adapter.py        # MAVLink PCAP/텍스트 파싱
│   ├── align.py                  # 멀티소스 시간 정렬
│   ├── common.py                 # 공통 타입, SQL 스키마, 좌표변환
│   └── __init__.py
│
├── scripts/
│   ├── setup/                    # 환경 설정 자동화
│   │   ├── 00_wsl2_dev_pc.sh
│   │   ├── 01_jetson_base.sh
│   │   ├── 02_ros2_humble.sh
│   │   ├── 03_px4_firmware.sh
│   │   ├── 04_mavlink_router.sh
│   │   ├── 05_uxrce_dds_agent.sh
│   │   └── apply_configs.sh
│   ├── preflight/check_all.sh    # 사전 비행 체크
│   ├── postflight/analyze_log.py # 자동 분석 리포트
│   ├── init_flightlog_db.py      # DB 초기화
│   ├── parse_flight.py           # 비행 로그 파싱
│   ├── ingest_flight.py          # DB 적재
│   └── silvus_monitor.py         # Silvus 링크 모니터링
│
├── flight_logs/db/flightlog.db   # SQLite DB (19개 테이블, Provenance 포함)
├── references/flightlog-schema.sql
└── config/px4/q250-v3-opti_v1.15_baseline.params  # PX4 파라미터 (VIO/EV 주석 추가)
```

---

## 🚀 지금 당장 시작하기 (Quick Start)

### 1단계: 개발 환경 구축 (오늘 당장)
```bash
# 1. 저장소 클론 (이미 되어 있다면 스킵)
cd /Users/amaster/projectm/Q250-V3-Opti

# 2. 개발 환경 설정 가이드 읽기 (필수!)
cat docs/guides/05_dev_environment_setup_guide.md

# 3. 자동 설정 스크립트 실행 (WSL2 터미널에서)
./scripts/setup/00_wsl2_dev_pc.sh

# 4. Jetson 설정 (별도 터미널에서)
scp scripts/setup/01_jetson_base.sh jetson@192.168.10.11:~/
ssh jetson@192.168.10.11 "chmod +x ~/01_jetson_base.sh && ~/01_jetson_base.sh"
```

### 2단계: PX4 펌웨어 빌드/플래싱 (이번 주 내)
```bash
# 개발 PC에서
./scripts/setup/03_px4_firmware.sh both  # 빌드 + 플래싱
```

### 3단계: VIO→EKF2 연동 시작 (핵심, 다음 주부터)
```bash
# 실전 가이드 읽기 (필독!)
cat docs/guides/01_vio_ekf2_integration_guide.md

# Phase 1부터 순차 진행:
# 1. RealSense 드라이버 실행 및 토픽 확인
# 2. OpenVINS 설치 및 VIO 포즈 검증
# 3. TF 트리 및 카메라 마운트 실측
# 4. MAVROS vision_pose 경로로 PX4 연동
# 5. EKF2 파라미터 적용 및 혁신 모니터링 (핵심!)
# 6. Position 모드 진입 테스트
```

---

## ⚠️ 자주 하는 실수 & 체크포인트

| 실수 | 결과 | 방지 방법 |
|------|------|-----------|
| **VIO→EKF2 전에 회피/ fake GPS 시도** | 시간 낭비, 디버깅 지옥 | **순서 엄수**: Phase 4 완료 후 Phase 5,6 진행 |
| **EKF2 혁신 모니터링 안 함** | 원인 모를 드리프트/이탈 | **매 비행 후** `ekf2 innovation` 필수 확인 |
| **카메라 마운트 위치 안 재고 파라미터 입력** | Yaw/Position 오차 누적 | **실측 후** `EKF2_EV_POS_X/Y/Z` 입력 |
| **Datum(원점) 비행 중 변경** | 위치 점프, Mission 실패 | **비행 전 고정** 또는 이륙 시 자동 저장 구현 |
| **프로펠러 달고 첫 테스트** | 기체 파손, 안전 사고 | **무프로펠러 벤치 테스트 완료 후** 프로펠러 장착 |
| **Silvus 링크 품질 모니터링 안 함** | 링크 열화 시 제어 불능 | `scripts/silvus_monitor.py` 상시 실행 |
| **로그 분석 안 하고 다음 비행** | 같은 실수 반복 | **매 비행 후** `analyze_log.py` 실행 |

---

## 📞 문제 발생 시 참고할 곳

| 문제 유형 | 1차 참고 문서 | 2차 상세 문서 |
|-----------|---------------|---------------|
| VIO 포즈 안 나옴 | `01_vio_ekf2_integration_guide.md` Phase 1~2 | `07-vio-ekf2-integration.md` |
| EKF2 혁신 ±3σ 초과 | `01_vio_ekf2_integration_guide.md` Phase 5 | `07-vio-ekf2-integration.md` 섹션 7.5 |
| Position 모드 진입 실패 | `01_vio_ekf2_integration_guide.md` Phase 6 | `docs/learning-roadmap.md` 5단계 |
| fake GPS Mission 안 됨 | `03_fake_gps_guide.md` Phase 4 | `13-fake-gps-implementation.md` |
| 회피 안 됨/충돌 | `02_obstacle_avoidance_guide.md` Phase 3~5 | `12-obstacle-avoidance-pipeline.md` |
| 로그 분석 방법 | `04_flight_log_analysis_guide.md` | `integration/` 어댑터 코드 |
| 환경 설정 꼬임 | `05_dev_environment_setup_guide.md` | `references/development_environment.md` |

---

## 🎓 학습 로드맵 요약 (10단계)

```
1주차:  HW 이해 + 환경 구축     → 05_dev_environment_setup_guide.md
2주차:  PX4 기초 + 실내 EKF2    → learning-roadmap.md 3단계
3~5주차: VIO→EKF2 연동 (핵심)    → 01_vio_ekf2_integration_guide.md ★★★
6주차:  fake GPS + Mission/RTL  → 03_fake_gps_guide.md
7~9주차: 자율 회피 파이프라인    → 02_obstacle_avoidance_guide.md
10주차+: Silvus/군집/로그 분석   → 04_flight_log_analysis_guide.md
```

---

## 💡 핵심 원칙 (항상 기억)

> **결정론적 계층(PX4)이 최종 권한**을 가진다. 보조 계층(VIO, Planner, LLM)은 제안만 한다.
> 
> **실시간 루프(400Hz~10Hz)와 비실시간 계층(LLM 등)은 엄격히 분리**한다.
> 
> **모든 센서/추정/제어 데이터는 Provenance(SHA-256, Git hash, 타임스탬프)와 함께 저장**한다.
> 
> **Failsafe는 하드웨어/펌웨어 레벨에서 다중 계층으로** 구현한다.
> 
> **EKF2 혁신은 ±3σ 내 유지** - 벗어나면 즉시 원인 분석 후 비행 중단.
> 
> **모든 아키텍처 변경은 ADR로 기록**하고, 비행 테스트 검증 후 병합한다.

---

*마스터 인덱스 버전: 1.0 | 작성: 2026-11-04 | 기반: 전체 가이드 문서 통합*