# Q250-V3 Opti 군집 통신 가이드 (Swarm Communication Guide)

> **목적**: Silvus Mesh + Fast-DDS 실시간 위치 브로드캐스트 + 충돌 방지 + 편대 비행  
> **전제**: 단일 기체 자율 비행 완성 (VIO→EKF2, Fake GPS, 회피 파이프라인)  
> **위치**: `ros2_ws/src/swarm_comm/`  
> **기반**: `docs/architecture.md` - Silvus MN-MIMO + Fast-DDS + 충돌 방지

---

## 📋 Phase 0: 아키텍처 이해

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Swarm Communication Architecture                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Drone 1 (Leader)          Drone 2           Drone 3           Drone 4 │
│  ┌─────────────┐          ┌─────────────┐    ┌─────────────┐           │
│  │ Pos Broadcaster ──────▶│ Pos Broadcaster ◀───│ Pos Broadcaster│           │
│  │ Collision Avoid  ◀────│ Collision Avoid ────▶│ Collision Avoid│           │
│  │ Swarm Coordinator    │ Swarm Coordinator    │ Swarm Coordinator│           │
│  └──────┬────────┘          └────────┬────────┘    └────────┬────────┘           │
│         │                            │                      │                    │
│         └────────────────────────────┼──────────────────────┘                    │
│                                      ▼                                           │
│                          Silvus MN-MIMO Mesh Network                             │
│                    (80-120 Mbps, 3-8ms RTT, Self-healing, 20-50km)              │
│                                      │                                           │
│                                      ▼                                           │
│                          Ground Station (GCS/QGC)                                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 핵심 구성요소

| 노드 | 역할 | 주기 | 토픽 |
|------|------|------|------|
| **Position Broadcaster** | 내 위치/속도/자세/배터리/모드 브로드캐스트 | 20 Hz | `/swarm/position` |
| **Collision Avoidance** | 이웃 드론 감지 → 회피 속도 계산 → PX4 전송 | 20 Hz | `/mavros/setpoint_velocity/cmd_vel` |
| **Swarm Coordinator** | 편대 비행 리더/팔로워, 태스크 할당 | 10 Hz | `/swarm/formation_cmd` |

### 통신 스택
| 계층 | 기술 | 설정 |
|------|------|------|
| **Physical** | Silvus StreamCaster MN-MIMO | 80-120 Mbps, 3-8ms RTT, AES-256 |
| **Network** | MAVLink Router + UDP | 멀티엔드포인트 라우팅 |
| **Middleware** | Fast-DDS (ROS 2) | Best-effort, depth=1, deadline=50ms |
| **Application** | ROS 2 Topics + JSON | 위치/속도/자세/배터리/모드/VIO품질 |

---

## 📋 Phase 1: 패키지 빌드 및 설정 (30분)

### 1.1 빌드
```bash
cd /Users/amaster/projectm/Q250-V3-Opti/ros2_ws
colcon build --symlink-install --packages-select swarm_comm
source install/setup.bash
```

### 1.2 설정 파일 확인
```bash
cat ros2_ws/src/swarm_comm/config/swarm_comm.yaml
```

**핵심 파라미터**:
```yaml
drone_id: "drone_01"           # 고유 드론 ID
swarm_id: "swarm_alpha"        # 군집 ID
broadcast_rate: 20.0           # Hz (위치 브로드캐스트)
ca_algorithm: "potential_field" # potential_field, velocity_obstacle, mpc
safety_radius: 2.0             # m (최소 분리 거리)
warning_radius: 5.0            # m (경고 구역)
formation_enabled: false       # 편대 비행 활성화
formation_shape: "line"        # line, wedge, diamond, circle
formation_spacing: 3.0         # m (편대 간격)
leader_id: ""                  # 리더 드론 ID (비우면 없음)
silvus_link_loss_threshold: 0.1  # 10% 패킷 로스
silvus_rtt_threshold: 50.0     # ms RTT 임계값
```

### 1.3 드론별 ID 설정 (각 드론에서)
```bash
# 드론 1 (리더)
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_01 swarm_id:=swarm_alpha leader_id:=drone_01 formation_enabled:=true

# 드론 2
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_02 swarm_id:=swarm_alpha leader_id:=drone_01 formation_enabled:=true

# 드론 3
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_03 swarm_id:=swarm_alpha leader_id:=drone_01 formation_enabled:=true

# 드론 4
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_04 swarm_id:=swarm_alpha leader_id:=drone_01 formation_enabled:=true
```

---

## 📋 Phase 2: Silvus 네트워크 설정 (필수, 1시간)

### 2.1 Silvus 웹 UI 접속
```
브라우저 → http://192.168.10.11 (Air Unit) 또는 http://192.168.10.10 (GDT)
```

### 2.2 필수 설정
| 설정 | 권장값 | 설명 |
|------|--------|------|
| **주파수** | 2.4GHz 또는 5GHz | 간섭 적은 채널 선택 |
| **대역폭** | 20MHz/40MHz | 거리/속도 트레이드오프 |
| **출력 파워** | 최대 (5W) | 최대 거리 확보 |
| **암호화** | AES-256 + TRANSEC | 보안 필수 |
| **MIMO 모드** | MN-MIMO | 다중 홉 지원 |
| **TDMA 슬롯** | 자동 | 충돌 방지 |

### 2.3 네트워크 토폴로지 확인
```bash
# Silvus 모니터링 실행
python3 scripts/silvus_monitor.py --air-unit-ip 192.168.10.11

# 출력 예시:
# RSSI: -62 dBm | SNR: 18 dB | Loss: 0.8% | RTT: 4.2ms | Hops: 1 | Topology: Star
```

**정상 범위**:
- RSSI > -70 dBm
- 패킷 로스 < 1%
- RTT < 10ms
- Hop ≤ 3 (메시 네트워크)

### 2.4 MAVLink Router 설정
```bash
# /etc/mavlink-router/main.conf (Jetson)
[UartEndpoint pixhawk]
Device = /dev/ttyTHS1
Baud = 921600

[UdpEndpoint gcs]
Address = 192.168.10.10
Port = 14550

[UdpEndpoint silvus]
Address = 192.168.10.11
Port = 14540

[UdpEndpoint swarm]
Address = 239.255.0.1
Port = 7400
Multicast = true
```

---

## 📋 Phase 3: Fast-DDS 설정 (30분)

### 3.1 QoS 프로파일 (`config/swarm_comm.yaml`)
```yaml
qos_profiles:
  swarm_realtime:
    reliability: "best_effort"
    history: "keep_last"
    depth: 1
    durability: "volatile"
    deadline_ms: 50
    lifespan_ms: 100
```

### 3.2 Fast-DDS 설정 파일 (`fastdds_silvus_config.xml`)
```xml
<profiles>
  <participant profile_name="swarm_participant">
    <rtps>
      <builtin>
        <domainId>0</domainId>
        <partition>swarm_alpha</partition>
      </builtin>
      <port>
        <portBase>7400</portBase>
      </rtps>
    </participant>
  </profiles>
</profiles>
```

### 3.3 환경변수 설정 (Jetson + 개발 PC)
```bash
# ~/.bashrc 또는 launch 파일에서
export FASTRTPS_DEFAULT_PROFILES_FILE=~/fastdds_config.xml
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DOMAIN_ID=0
```

---

## 📋 Phase 4: 단일 기체 테스트 → 군집 확장 (2일)

### 4.1 단일 기체 브로드캐스트 테스트 (Day 1 오전)
```bash
# 드론 1에서 실행
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_01

# 별도 터미널에서 확인
ros2 topic echo /swarm/position
ros2 topic hz /swarm/position
# 출력: average rate: 20.0 Hz
```

**확인 사항**:
- [ ] `/swarm/position` 20Hz 발행
- [ ] JSON 메시지에 position, velocity, attitude, battery, mode 포함
- [ ] Silvus 링크 품질 실시간 반영 (link_quality 필드)

### 4.2 충돌 방지 단독 테스트 (Day 1 오후)
```bash
# 가상 이웃 시뮬레이션 (별도 터미널)
ros2 topic pub /swarm/position std_msgs/String "data: '{\"drone_id\":\"drone_02\",\"position\":{\"x\":2.0,\"y\":0.0,\"z\":-1.0},\"velocity\":{\"vx\":-1.0,\"vy\":0.0,\"vz\":0.0},\"mode\":\"OFFBOARD\"}'"

# 충돌 방지 노드 확인
ros2 topic echo /mavros/setpoint_velocity/cmd_vel
# 출력: 회피 속도 벡터 출력 확인
```

**검증 시나리오**:
| 시나리오 | 입력 | 기대 출력 |
|----------|------|-----------|
| 전방 드론 접근 | drone_02가 전방 1m 접근 | 회피 속도 후진/측면 |
| 측면 드론 통과 | drone_02가 측면 0.5m 통과 | 측면 회피 벡터 |
| 다중 드론 | 3개 드론 근접 | 종합 회피 벡터 |

### 4.3 Silvus 링크 품질 연동 테스트 (Day 2 오전)
```bash
# Silvus 링크 열화 시뮬레이션
# Silvus 웹 UI에서 출력 파워 낮추기 또는 안테나 방향 변경

# 자동 브로드캐스트 레이트 감소 확인
ros2 topic hz /swarm/position
# 패킷 로스 > 10% 또는 RTT > 50ms → 20Hz → 10Hz 자동 감소
```

**확인 사항**:
- [ ] 패킷 로스 > 10% → 브로드캐스트 레이트 50% 감소
- [ ] RTT > 50ms → 브로드캐스트 레이트 50% 감소
- [ ] 링크 복구 시 → 20Hz 자동 복구

---

## 📋 Phase 5: 다중 기체 군집 테스트 (Day 2-3)

### 5.1 2기체 기본 통신 (Day 2 오후)
```bash
# 드론 1 (리더)
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_01 swarm_id:=swarm_alpha leader_id:=drone_01

# 드론 2 (팔로워)
ros2 launch swarm_comm swarm_comm.launch.py drone_id:=drone_02 swarm_id:=swarm_alpha leader_id:=drone_01
```

**확인 사항**:
- [ ] 양쪽에서 `/swarm/position` 수신
- [ ] 서로의 위치/속도/모드 실시간 표시
- [ ] Silvus 토폴로지에 양쪽 표시 (Hop=1)

### 5.2 충돌 방지 통합 테스트 (Day 3 오전)
```bash
# 2기체 접근 테스트
# 드론 1: 위치 고정 (호버)
# 드론 2: 드론 1 방향으로 전진

# 기대: 드론 2가 safety_radius(2m) 진입 전 회피 기동
# 로그 확인: "CA ACTIVE: avoidance_vel=(-0.5, 0.0, 0.0)"
```

### 5.3 편대 비행 테스트 (Day 3 오후)
```bash
# 편대 활성화
ros2 launch swarm_comm swarm_comm.launch.py formation_enabled:=true formation_shape:=line formation_spacing:=3.0 leader_id:=drone_01

# 리더 이동 → 팔로워 자동 추종 확인
# 편대 형태: line, wedge, diamond, circle 변경 테스트
```

**편대 형태별 오프셋**:
| 형태 | 드론 1 (리더) | 드론 2 | 드론 3 | 드론 4 |
|------|--------------|--------|--------|--------|
| line | (0, 0) | (0, -3) | (0, 3) | (0, 6) |
| wedge | (0, 0) | (-2.1, -2.1) | (-2.1, 2.1) | (-4.2, 0) |
| diamond | (0, 0) | (-3, 0) | (0, 3) | (0, -3) |
| circle | (0, 0) | (1.9, 0) | (0, 1.9) | (-1.9, 0) |

---

## 📋 Phase 6: 실전 운용 및 모니터링

### 6.1 실시간 모니터링 대시보드
```bash
# 종합 상태 확인
ros2 topic echo /swarm/status
ros2 topic echo /swarm/position
ros2 topic hz /swarm/position

# Silvus 링크 품질
python3 scripts/silvus_monitor.py --air-unit-ip 192.168.10.11

# 충돌 방지 이벤트
ros2 topic echo /swarm/collision_avoidance
```

### 6.2 로그 분석
```bash
# 비행 후 분석
python3 scripts/postflight/analyze_log.py log_XXX.ulg

# 군집 특화 분석
python3 scripts/analyze_swarm.py log_XXX.ulg
# 출력: 편대 유지율, 충돌 회피 횟수, 통신 품질, 편대 간격 편차
```

### 6.3 성능 지표 (KPI)
| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| **브로드캐스트 레이트** | ≥ 18 Hz (목표 20Hz) | `ros2 topic hz /swarm/position` |
| **위치 데이터 지연** | < 50ms | 타임스탬프 차이 |
| **충돌 회피 성공률** | 100% | 회피 이벤트 / 위협 상황 |
| **편대 유지율** | > 95% | 편대 내 드론 비율 |
| **통신 패킷 로스** | < 1% | Silvus 모니터 |
| **RTT** | < 10ms | Silvus 모니터 |

---

## 🚨 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| **위치 브로드캐스트 안 나옴** | MAVROS 토픽 없음 | `/mavros/local_position/pose` 확인, MAVROS 재시작 |
| **충돌 방지 작동 안 함** | 이웃 데이터 없음 | `/swarm/position` 수신 확인, Silvus 링크 확인 |
| **편대 유지 안 됨** | 리더 ID 불일치 | `leader_id` 파라미터 확인, 리더 기체에서만 formation_enabled=true |
| **Silvus 패킷 로스 높음** | 안테나/채널/출력 | 안테나 방향, 채널 변경, 출력 파워 최대 |
| **Fast-DDS 통신 안 됨** | 도메인/파티션 불일치 | `ROS_DOMAIN_ID`, `fastdds_silvus_config.xml` partition 확인 |
| **편대 간격 벌어짐** | 리더 속도 과함 | 리더 속도 제한, `formation_spacing` 증가 |

---

## 📋 Phase 7: 고급 기능 확장

### 7.1 태스크 할당 (Task Allocation)
```python
# 향후 확장: 시장 기반 태스크 할당 (Market-based Task Allocation)
# 각 드론이 태스크 입찰 → 최적 할당
```

### 7.2 합의 알고리즘 (Consensus)
```python
# 향후 확장: Raft/합의 알고리즘으로 리더 선출 자동화
# 리더 장애 시 자동 페일오버
```

### 7.3 이기종 드론 지원
```python
# 드론 기종/능력 차이 고려한 태스크 할당
# 능력 메타데이터 공유 (카메라 유무, 배터리 용량, 센서 종류)
```

---

## 📚 관련 문서

| 문서 | 위치 |
|------|------|
| 시스템 아키텍처 | `docs/architecture.md` (Silvus + Fast-DDS + CA) |
| VIO→EKF2 연동 | `docs/guides/01_vio_ekf2_integration_guide.md` |
| 회피 파이프라인 | `docs/guides/02_obstacle_avoidance_guide.md` |
| LLM 미션 플래너 | `docs/guides/06_llm_mission_planner_guide.md` |
| 비행 로그 분석 | `docs/guides/04_flight_log_analysis_guide.md` |
| 개발 환경 | `docs/guides/05_dev_environment_setup_guide.md` |
| 빠른 참조 | `docs/QUICK_REFERENCE.md` |
| 안전 체크리스트 | `docs/SAFETY_CHECKLIST.md` |

---

*작성: 2026-11-04 | 기반: swarm_comm 패키지 + docs/architecture.md + PDF 문서(군집 통신 섹션)*