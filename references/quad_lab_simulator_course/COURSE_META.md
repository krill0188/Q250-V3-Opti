# QUAD 드론 연구소 - 드론 시뮬레이터 만들기 강좌 참조

## 기본 정보
- **채널**: QUAD 드론 연구소 (제조사/교육기관 공식 채널)
- **강좌명**: [🥇드론 시뮬레이터 만들기] 시리즈
- **1편 URL**: https://youtu.be/zXIm_meNF3k
- **대상 기체**: Q250-V3 Opti (Pixhawk 6C mini + Jetson Nano)
- **목적**: 시뮬레이터 구축 → 실기체 검증 → 자율비행 개발 전체 워크플로우

## 플레이리스트 추정 (채널 강좌 구조 기반)
| 편 | 예상 제목 | 핵심 내용 | 프로젝트 적용도 |
|-----|-----------|-----------|-----------------|
| 1 | 강좌 소개 ✨ | 전체 로드맵, 필요 하드웨어/소프트웨어 | 낮음 (개요) |
| 2 | **개발 환경 구축** | Ubuntu, ROS2, Gazebo, PX4, QGC 설치 | **최고** |
| 3 | **기체 모델링 & 센서** | SDF/URDF, 질량/관성, Optical-Flow, LiDAR, 카메라 | **최고** |
| 4 | **ROS2 연동 & Offboard** | uXRCE-DDS, px4_msgs, TrajectorySetpoint | **최고** |
| 5 | **실내 자율비행 미션** | Optical-Flow/LiDAR Position Mode, 웨이포인트 | **최고** |
| 6 | **HITL (Hardware-in-the-loop)** | 실 FC 연결, 실버스 데이터링크 연동 | **높음** |
| 7+ | 고급 주제 | 군집, VIO, SLAM, 강화학습 등 | 중/높음 |

## 시청 우선순위 (시간 절약)
1. **2편~5편 필수 정주행** (핵심 워크플로우 완성)
2. 6편 이후 필요 시 선별 시청
3. 1편은 2배속으로 개요만 확인

---

## 핵심 기술 스택 (강좌 기준)
| 분류 | 기술 | 버전 (추정) | 비고 |
|------|------|-------------|------|
| OS | Ubuntu | 20.04 / 22.04 | Jetson: 20.04 (JP 4.6) |
| ROS | ROS 2 | Humble / Iron | Jetson: Humble |
| Simulator | Gazebo | Classic / Harmonic | 강좌 확인 필요 |
| FC Firmware | PX4 | v1.14 / v1.15 | **v1.15 고정** (OF 지원) |
| Middleware | uXRCE-DDS | 최신 | Micro-XRCE-DDS Agent |
| GCS | QGroundControl | 최신 Stable | |
| Language | Python 3.10 / C++17 | | ROS2 Humble 기준 |

---

## 프로젝트 매핑 (강좌 → 우리 폴더)
| 강좌 단계 | 우리 프로젝트 파일/폴더 | 상태 |
|-----------|------------------------|------|
| 2편: 환경 구축 | `scripts/setup/01_jetson_base.sh`, `02_ros2_humble.sh` | ✅ 완료 |
| 2편: PX4 빌드 | `scripts/setup/03_px4_firmware.sh` | ✅ 완료 |
| 2편: MAVLink/uXRCE | `scripts/setup/04_mavlink_router.sh`, `05_uxrce_dds_agent.sh` | ✅ 완료 |
| 3편: 기체 모델링 | `simulation/models/q250_v3_opti/` | 🔄 생성 필요 |
| 3편: 센서 플러그인 | `simulation/models/q250_v3_opti/sensors/` | 🔄 생성 필요 |
| 4편: ROS2 연동 | `ros2_ws/src/`, `scripts/silvus_monitor.py` | ✅ 기반 완료 |
| 4편: Offboard 제어 | `scripts/` (예제 노드 필요) | 🔄 예제 추가 필요 |
| 5편: 실내 자율비행 | `config/px4/` (EKF2 파라미터) | ✅ 파라미터 완료 |
| 6편: HITL/실버스 | `config/mavlink-router/main_silvus.conf`, `scripts/silvus_monitor.py` | ✅ 완료 |

---

## 다음 액션 아이템 (강좌 시청하면서 수행)
1. **2편 시청** → `scripts/setup/` 스크립트 검증/보완
2. **3편 시청** → `simulation/models/q250_v3_opti/` SDF/URDF 생성
3. **4편 시청** → `ros2_ws/src/offboard_control/` 예제 노드 작성
4. **5편 시청** → `config/px4/` EKF2 파라미터 실기체값으로 튜닝
5. **전편 공통** → Gazebo 런치 파일, 월드 파일, 파라미터 브리지 설정
