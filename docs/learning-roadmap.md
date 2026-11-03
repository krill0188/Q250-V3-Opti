# Q250-V3 Opti 자율비행 드론 학습 로드맵

> `jetson-px4-ros2-autonomous-drone/docs/00-learning-guide-ko.md`를 기반으로 Q250-V3-Opti 실기체 운용 프로젝트에 맞춰 재구성했습니다.

---

## 0. 시작 전 체크리스트

| 항목 | 상태 | 비고 |
|------|------|------|
| 기체 조립 완료 (Pixhawk 6C Mini + Jetson Nano + Silvus) | ☐ | HW 체크리스트 별도 |
| PX4 v1.15 펌웨어 빌드/플래싱 완료 | ☐ | `scripts/setup/03_px4_firmware.sh` |
| Jetson JetPack 6 + ROS 2 Humble 설치 | ☐ | `scripts/setup/01_jetson_base.sh`, `02_ros2_humble.sh` |
| MAVLink Router / uXRCE-DDS Agent 설정 | ☐ | `scripts/setup/04_mavlink_router.sh`, `05_uxrce_dds_agent.sh` |
| Silvus 데이터링크 벤치 테스트 통과 | ☐ | `config/silvus_checklist.md` |
| 개발 PC (WSL2 Ubuntu 22.04) 환경 동기화 | ☐ | `references/development_environment.md` |

---

## 1단계: 하드웨어 기초 이해 (1주)

### 1.1 핵심 하드웨어 역할
| 구성요소 | 역할 | Q250-V3-Opti 사양 |
|----------|------|-------------------|
| **Pixhawk 6C Mini** | 실시간 비행 제어, 센서 융합, Failsafe | FMUv6C, IMU×2, Baro×2, Mag×1 |
| **Jetson Nano** | 비전 처리, VIO, AI 추론, 고수준 플래너 | 4GB, JetPack 6, ROS 2 Humble |
| **Silvus Air Unit** | 장거리/저지연 데이터링크 (MN-MIMO) | 80~120 Mbps, 3~8ms RTT, AES-256 |
| **Optical-Flow (PMW3901)** | 실내 속도/위치 추정 (EKF2 융합) | UART4/TELEM4, 100Hz |
| **LiDAR (TF-Luna)** | 고도/장애물 거리 측정 (EKF2 융합) | UART4/TELEM4, 100Hz, 0.02~11m |
| **RealSense D435i** (선택) | VIO/Depth/장애물 인식 | USB 3.0, IMU 내장 |

### 1.2 학습 자료
- `docs/diagrams/system_architecture.mmd` - 시스템 전체 구조도
- `docs/diagrams/fc_portmap.mmd` - FC 포트맵 및 배선도
- `docs/diagrams/power_system.mmd` - 전원 시스템도
- `config/px4/q250-v3-opti_v1.15_baseline.params` - PX4 파라미터 (주석 참조)

### 1.3 실습
- [ ] 기체 육안 점검 (프레임, 모터, ESC, 배선, 마운트)
- [ ] QGroundControl 연결 → 펌웨어 버전 확인 → 센서 캘리브레이션
- [ ] 벤치에서 모터 스핀 테스트 (프로펠러 제거, DShot 확인)
- [ ] Silvus 웹 UI 접속 → 링크 품질/RSSI/토폴로지 확인

---

## 2단계: 소프트웨어 설치 및 환경 구축 (1주)

### 2.1 개발 PC (WSL2)
```bash
# references/development_environment.md 순서대로
./scripts/setup/00_wsl2_dev_pc.sh
# VS Code Remote-WSL 연결, Docker 컨테이너 빌드 테스트
```

### 2.2 Jetson 타겟
```bash
# 순서대로 실행 (각각 30~60분 소요)
./scripts/setup/01_jetson_base.sh      # JetPack, 시스템 설정
./scripts/setup/02_ros2_humble.sh      # ROS 2 Humble
./scripts/setup/03_px4_firmware.sh     # PX4 빌드 (개발 PC에서)
./scripts/setup/04_mavlink_router.sh   # MAVLink Router
./scripts/setup/05_uxrce_dds_agent.sh  # uXRCE-DDS Agent
./scripts/setup/apply_configs.sh       # 설정 파일 동기화
```

### 2.3 검증
```bash
# 개발 PC
ros2 --version
colcon version-check
gz sim --version
px4-build  # alias 테스트

# Jetson (SSH 접속 후)
ros2 --version
MicroXRCEAgent --help
journalctl -fu mavlink-router
journalctl -fu uxrce-dds-agent
```

---

## 3단계: PX4 기초 및 파라미터 튜닝 (1~2주)

### 3.1 학습 순서
1. **PX4 아키텍처**: 모듈(uORB), Estimator(EKF2), Controller, Mixer
2. **비행 모드**: Manual → Altitude → Position → Mission → Offboard
3. **파라미터 시스템**: QGC에서 저장/불러오기, 버전 관리
4. **EKF2 이해**: 센서 융합, Aid Mask, Innovation 모니터링

### 3.2 핵심 문서
- `docs/diagrams/ekf2_sensor_fusion.mmd` - EKF2 블록 다이어그램 (실내 모드)
- `config/px4/q250-v3-opti_v1.15_baseline.params` - 베이스라인 파라미터
- `docs/07-vio-ekf2-integration.md` - VIO→EKF2 연동 (실내 자율비행 핵심)

### 3.3 실습 체크리스트
- [ ] QGC에서 파라미터 전체 백업 (`px4_params/backup_YYYYMMDD.params`)
- [ ] 실내 모드 파라미터 적용 (`EKF2_GPS_CTRL=0`, `EKF2_AID_MASK=352`)
- [ ] Optical-Flow/LiDAR 벤치 테스트 (정지/이동 시 품질 확인)
- [ ] EKF2 혁신 모니터링 (QGC MAVLink Console: `ekf2 innovation`)
- [ ] SITL에서 기본 비행 모드 테스트 (`px4-sitl`)

---

## 4단계: ROS 2 기초 및 통신 (1주)

### 4.1 학습 순서
1. **ROS 2 핵심**: Node, Topic, Service, Action, Parameter, TF2
2. **QoS 설정**: Reliability, Durability, History, Deadline
3. **px4_msgs / px4_ros_com**: PX4 uORB ↔ ROS 2 직접 연결
3. **MAVROS**: MAVLink ↔ ROS 2 브리지 (호환성 경로)
4. **시뮬레이션 연동**: Gazebo + PX4 SITL + ROS 2

### 4.2 핵심 문서
- `references/development_environment.md` - 환경 변수, alias, VS Code 설정
- `docs/07-vio-ekf2-integration.md` 섹션 7.4 Step 4 - 통신 경로 선택 (MAVROS vs px4_ros_com)
- `launch/q250_v3_opti_sitl.launch.py` - SITL launch 파일

### 4.3 실습 체크리스트
- [ ] `ros2 topic list`로 PX4 토픽(`/fmu/out/*`, `/fmu/in/*`) 확인
- [ ] `ros2 topic echo /fmu/out/vehicle_status`로 상태 모니터링
- [ ] `ros2 topic pub /fmu/in/vehicle_command`로 간단 명령 전송 테스트
- [ ] SITL + ROS 2 브리지 실행 → RViz2에서 기체 자세 확인
- [ ] `ros2 bag record`로 비행 데이터 녹화/재생 연습

---

## 5단계: VIO → EKF2 연동 (실내 자율비행 핵심, 2~3주)

### 5.1 학습 순서
1. **VIO 원리**: Visual-Inertial Odometry, 특징점 추적, IMU 프리인테그레이션
2. **RealSense D435i 설정**: 펌웨어, 캘리브레이션, IMU 동기화
3. **VIO 노드 선택/설치**: `ov_msckf`, `vio_ros`, `rtabmap_ros` 중 택1
4. **좌표계 검증**: ROS ENU ↔ PX4 NED/FRD 변환, TF 트리
5. **PX4 External Vision 연동**: MAVROS vision_pose 또는 px4_ros_com
6. **EKF2 파라미터 튜닝**: `EKF2_EV_CTRL`, `EKF2_EV_DELAY`, `EKF2_EV_POS_X/Y/Z`

### 5.2 핵심 문서
- `docs/07-vio-ekf2-integration.md` - 전체 연동 가이드 (필독)
- `docs/11-vio-non-gps-flight.md` - non-GPS 비행 모드 (별도 문서)
- `docs/13-fake-gps-implementation.md` - fake GPS (Mission/RTL용)

### 5.3 단계별 마일스톤
| 마일스톤 | 성공 기준 | 예상 기간 |
|----------|-----------|-----------|
| M5.1 카메라 드라이버 | `/camera/imu`, `/camera/depth/image_rect_raw` 30Hz 안정 | 2일 |
| M5.2 VIO pose 출력 | `/vio/pose` 발행, 정지 시 drift < 1cm/s | 3일 |
| M5.3 좌표계 검증 | TF 트리 완전, ENU→NED 변환 정확 | 2일 |
| M5.4 PX4 수신 확인 | QGC에서 `VEHICLE_VISUAL_ODOMETRY` 수신, EKF2 혁신 ±3σ | 3일 |
| M5.5 Position 모드 진입 | 프로펠러 제거 상태에서 Position 모드 호버 유지 | 2일 |
| M5.6 실내 비행 테스트 | 저고도 수동/Position 비행 5분 이상, 로그 분석 통과 | 1주 |

---

## 6단계: non-GPS 비행 모드 & fake GPS (1~2주)

### 6.1 학습 순서
1. **Local Position만으로 가능한 것**: Position 모드, Offboard, 호버, 기본 기동
2. **Global Position 필요한 것**: Mission, RTL, Geofence
3. **fake GPS 구현**: VIO local pose → LLA 변환 → `GPS_INPUT` MAVLink
4. **원점(Datum) 관리**: 고정 원점 vs 동적 원점 (`SET_GPS_GLOBAL_ORIGIN`)
5. **품질 필드 튜닝**: `fix_type`, `satellites_visible`, `horiz_accuracy`

### 6.2 핵심 문서
- `docs/11-vio-non-gps-flight.md` - non-GPS 비행 모드 상세
- `docs/13-fake-gps-implementation.md` - fake GPS 구현 가이드 (코드 포함)

### 6.3 마일스톤
| 마일스톤 | 성공 기준 |
|----------|-----------|
| M6.1 fake GPS 노드 동작 | `/mavros/gps_input/input` 발행, QGC에서 GPS 3D Fix 표시 |
| M6.2 Global Position Valid | QGC Map에 기체 위치 표시, EKF2 GPS 혁신 ±3σ |
| M6.3 Mission 업로드/실행 | QGC에서 웨이포인트 Mission 업로드 → AUTO 모드 실행 |
| M6.4 RTL 동작 확인 | RTL 모드 전환 → 원점 복귀 → 착륙 |
| M6.5 Geofence 테스트 | 경계 이탈 시 `GF_ACTION=1` (RTL) 동작 |

---

## 7단계: 자율 회피 파이프라인 (2~3주)

### 7.1 학습 순서
1. **센서 파이프라인**: Depth → PointCloud → Voxel Grid → Costmap
2. **로컬 플래너**: TEB / DWA / 커스텀, 비용함수 튜닝
3. **PX4 인터페이스**: MAVROS `cmd_vel` 또는 `px4_ros_com` VehicleVelocitySetpoint
4. **안전/페일세이프**: 센서 끊김, 플래너 크래시, RC 비상복귀, Geofence
5. **단계별 테스트**: 정지 → 시뮬 → 무프로펠러 → 실내 비행

### 7.2 핵심 문서
- `docs/12-obstacle-avoidance-pipeline.md` - 전체 파이프라인 & 테스트 시나리오 (필독)

### 7.3 마일스톤
| 마일스톤 | 성공 기준 |
|----------|-----------|
| M7.1 Costmap 생성 | `/local_costmap/costmap` 5Hz, 장애물 팽창 확인 |
| M7.2 플래너 단독 테스트 | 가상 장애물에서 회피 벡터 출력, 정지/우회 동작 |
| M7.3 OFFBOARD 연동 | 플래너 → MAVROS/px4_ros_com → PX4 속도 제어 확인 |
| M7.4 통합 무프로펠러 | 전방 장애물에서 정지, 측면 회피, 플래너 크래시 시 안전 전환 |
| M7.5 실내 비행 테스트 | 5.5~5.8 모든 시나리오 통과, 로그 분석 완료 |

---

## 8단계: Silvus 데이터링크 고도화 & 군집 비행 (2주+)

### 8.1 학습 순서
1. **Silvus MN-MIMO 특성**: TDMA/OFDMA, 홉, 토폴로지, 암호화
2. **MAVLink Router 멀티엔드포인트**: 다중 기체/지상국 라우팅
3. **Fast-DDS 튜닝**: Silvus 대역폭/지연 최적화 (`fastdds_silvus_config.xml`)
4. **링크 품질 모니터링**: `scripts/silvus_monitor.py` → ROS 2 토픽
5. **군집 비행 아키텍처**: 리더-팔로워, 컨센서스, 태스크 할당

### 8.2 핵심 문서
- `config/silvus_checklist.md` - 초기 설정 체크리스트
- `config/mavlink-router/main_silvus.conf` - 라우팅 설정
- `config/jetson/fastdds_silvus_config.xml` - DDS QoS 최적화
- `scripts/silvus_monitor.py` - 링크 상태 모니터링 노드
- `docs/diagrams/network_topology.mmd` - 네트워크 토폴로지도

### 8.3 마일스톤
| 마일스톤 | 성공 기준 |
|----------|-----------|
| M8.1 단일 기체 링크 검증 | 500m 거리에서 80+ Mbps, RTT < 10ms, 패킷로스 < 1% |
| M8.2 다중 기체 (2~4대) 동시 접속 | 토폴로지 자동 형성, 전체 트래픽 정상 |
| M8.3 링크 품질 → 파라미터 연동 | 패킷로스/지연 임계값 초과 시 플래너 속도 자동 감속 |
| M8.4 군집 기본 기동 | 리더-팔로워 편대 비행 (간격 유지, 회전 동기) |

---

## 9단계: 비행 로그 분석 & 지속적 개선 (상시)

### 9.1 분석 도구 연계
- `integration/flightlog_adapter.py` - PX4 ulog 파싱
- `integration/mavlink_adapter.py` - MAVLink/PCAP 파싱
- `integration/align.py` - 멀티소스 시간 정렬 (provenance/SHA-256)
- `scripts/postflight/analyze_log.py` - 자동 분석 리포트

### 9.2 분석 항목
| 항목 | 도구 | 주기 |
|------|------|------|
| EKF2 혁신/추정기 상태 | ulog + analyze_log.py | 매 비행 |
| VIO drift/품질 | rosbag + 커스텀 스크립트 | 매 비행 |
| Silvus 링크 품질 | silvus_monitor.py 로그 | 매 비행 |
| 플래너 성능 (주기, 회피 성공률) | rosbag + 커스텀 | 주간 |
| 배터리/온도/모터 건강도 | ulog | 월간 |

### 9.3 문서화
- `flight_logs/` - 원본 로그 아카이브 (날짜별 폴더)
- `docs/manual-draft.md` - 운용 매뉴얼에 검증 결과 반영
- `px4_params/` - 파라미터 버전 관리 (Git 태그)

---

## 10단계: 문서화 & 지식 전수 (지속)

| 문서 | 위치 | 업데이트 주기 |
|------|------|---------------|
| 운용 매뉴얼 초안 | `docs/manual-draft.md` | 주요 마일스톤마다 |
| 완성본 (Word) | `docs/manual-final.docx` | 분기별 |
| 파라미터 변경 이력 | `px4_params/CHANGELOG.md` | 파라미터 변경 시 |
| 문제 해결 가이드 | `docs/troubleshooting.md` | 이슈 발생 시 |
| 아키텍처 결정 기록 (ADR) | `docs/adr/` | 주요 설계 변경 시 |

---

## 📋 전체 타임라인 요약 (예상)

| 단계 | 내용 | 예상 기간 | 누적 |
|------|------|-----------|------|
| 1 | HW 기초 이해 | 1주 | 1주 |
| 2 | SW 설치/환경 | 1주 | 2주 |
| 3 | PX4 기초/파라미터 | 1~2주 | 3~4주 |
| 4 | ROS 2 기초/통신 | 1주 | 4~5주 |
| 5 | **VIO→EKF2 연동** | **2~3주** | **6~8주** |
| 6 | non-GPS/fake GPS | 1~2주 | 7~10주 |
| 7 | **자율 회피 파이프라인** | **2~3주** | **9~13주** |
| 8 | Silvus/군집 비행 | 2주+ | 11~15주+ |
| 9 | 로그 분석/개선 | 상시 | - |
| 10 | 문서화/전수 | 지속 | - |

> **핵심 경로**: 5단계(VIO→EKF2) → 6단계(fake GPS) → 7단계(회피) 순차 의존성이 강함. 병렬화 가능: 8단계(Silvus)는 3단계 이후 독립 진행 가능.

---

## 🎯 우선순위 매트릭스 (리소스 제한 시)

| 우선순위 | 작업 | 이유 |
|----------|------|------|
| **P0 (필수)** | VIO→EKF2 연동 검증 | 실내 자율비행의 전제조건 |
| **P0 (필수)** | 자율 회피 파이프라인 | 안전 비행 필수 |
| **P1 (중요)** | fake GPS 구현 | Mission/RTL/Geofence 활성화 |
| **P1 (중요)** | Silvus 링크 품질 모니터링 | 장거리/군집 비행 신뢰성 |
| **P2 (선택)** | AI 객체 인식 회피 | 특정 물체 구분 필요 시 |
| **P2 (선택)** | 군집 컨센서스 알고리즘 | 다중 기체 자율 협업 시 |

---

## 📚 참고 레포지토리

| 레포 | 용도 |
|------|------|
| `krill0188/jetson-px4-ros2-autonomous-drone` | 학습 가이드, VIO/회피/fake GPS 상세 절차 |
| `krill0188/flight-intelligence-mvp` | 비행로그 분석 파이프라인 (비공개) |
| `krill0188/ardupilot-log-analyzer` | ArduPilot 로그 분석 (참조용) |
| `krill0188/mavlink-analyzer` | MAVLink/PCAP 분석 (참조용) |
| `PX4/PX4-Autopilot` v1.15 | 펌웨어 소스, 파라미터 레퍼런스 |
| `PX4/px4_ros_com` release/1.15 | ROS 2 직접 통신 |
| `mavros/mavros` ROS 2 | MAVLink 브리지 |

---

*최종 업데이트: 2026-11-03 | 작성: Hermes Agent | 기반: jetson-px4-ros2-autonomous-drone/docs/00-learning-guide-ko.md*