# Q250-V3 Opti LLM 고수준 미션 플래너 가이드

> **목적**: 자연어 미션 명령(예: "창고 3구역 순찰") → 웨이포인트/제약조건 JSON → PX4 실행  
> **전제**: VIO→EKF2 연동 완료, fake GPS 작동, 회피 파이프라인 작동  
> **위치**: `ros2_ws/src/llm_mission_planner/`  
> **기반**: `docs/architecture.md` - LLM은 판단 계층(3번)에만 개입

---

## 📋 Phase 0: 아키텍처 이해

```
자연어 입력 → LLM Mission Planner → 검증(Validator) → PX4 Mission/Offboard
                    ↓                    ↓              ↓
              시스템 프롬프트         안전 검증      Mission/RTL/Geofence
              미션 프롬프트           좌표 검증       활성화
              검증 프롬프트           지오펜스 체크
```

### 핵심 원칙 (아키텍처 문서 기반)
| 원칙 | 설명 |
|------|------|
| **LLM은 판단 계층만** | 모터 제어·자세 안정화·Failsafe는 PX4(결정론적 계층) 전담 |
| **출력 검증 필수** | LLM 출력은 반드시 Validator 통과 후 PX4 전달 |
| **좌표계 변환** | LLM은 ENU 출력 → 내부에서 NED 변환 → PX4 전달 |
| **Datum 고정** | 비행 중 원점(Datum) 변경 금지 → 위치 점프 방지 |
| **Failsafe 기본값** | 통신두절/배터리/지오펜스/충돌 시 기본 RTL/Hover |

---

## 📋 Phase 1: 패키지 빌드 및 설정 (30분)

### 1.1 빌드
```bash
cd /Users/amaster/projectm/Q250-V3-Opti/ros2_ws
colcon build --symlink-install --packages-select llm_mission_planner
source install/setup.bash
```

### 1.2 LLM API 키 설정 (필수)
```bash
# OpenAI 사용 시
export OPENAI_API_KEY="sk-..."

# Anthropic 사용 시
export ANTHROPIC_API_KEY="sk-ant-..."

# 로컬 LLM(Ollama) 사용 시
# ollama pull llama3.1:8b
# export LLM_PROVIDER=local
```

### 1.3 설정 파일 확인
```bash
cat ros2_ws/src/llm_mission_planner/config/mission_planner.yaml
```

**핵심 파라미터**:
```yaml
llm_provider: "openai"        # openai, anthropic, local
llm_model: "gpt-4o"           # 모델명
llm_temperature: 0.1          # 결정론적 출력 위해 낮게
llm_max_tokens: 2048
llm_timeout: 30.0             # 초

default_altitude: 10.0        # 기본 고도 (m)
max_altitude: 50.0            # 최대 고도
min_altitude: 0.5             # 최소 고도
default_speed: 3.0            # 기본 속도 (m/s)
max_speed: 5.0                # 최대 속도
safety_margin: 2.0            # 지오펜스 여유 (m)
geofence_polygon: []          # [[lat, lon], ...] 비어있으면 기본값
validate_waypoints: true      # 검증 활성화
max_retries: 3                # 검증 실패 시 재시도
```

---

## 📋 Phase 2: 프롬프트 이해 및 커스터마이징 (1시간)

### 2.1 시스템 프롬프트 (`config/prompts/system_prompt.j2`)
- **역할 정의**: "당신은 Q250-V3-Opti 전문 미션 플래너입니다"
- **출력 스키마**: 엄격한 JSON (mission_id, waypoints[], constraints{}, failsafe{}, metadata{})
- **좌표계**: 출력 WGS84(lat/lon/alt MSL), 내부 ENU↔NED 변환
- **액션 타입**: none, takeoff, land, loiter, photo, scan
- **미션 타입**: patrol, survey, inspection, delivery, custom

### 2.2 미션 프롬프트 (`config/prompts/mission_prompt.j2`)
- **컨텍스트 주입**: 현재 위치, 배터리, 모드, VIO 상태, Silvus 링크, 지오펜스, 장애물
- **제약조건**: config에서 주입 (고도/속도/지오펜스/웨이포인트 간격)

### 2.3 검증 프롬프트 (`config/prompts/validation_prompt.j2`)
- **10가지 검증 기준**: 좌표 유효성, 지오펜스 준수, 웨이포인트 간격, 고도 안전, 속도 제한, 액션 유효성, Failsafe 설정, 배터리 실행가능성, VIO 드리프트 고려, Silvus 링크 품질
- **심각도**: critical(비행 불가), warning(비행 가능하나 수정 권장), info(선택적 제안)

---

## 📋 Phase 3: 실행 및 테스트 (2시간)

### 3.1 노드 실행
```bash
# 터미널 1: 미션 플래너 노드
ros2 launch llm_mission_planner mission_planner.launch.py \
  llm_provider:=openai \
  llm_model:=gpt-4o \
  geofence_polygon:='[[37.5660,126.9770],[37.5670,126.9770],[37.5670,126.9790],[37.5660,126.9790]]'

# 터미널 2: 검증 노드 (별도 실행 가능)
ros2 run llm_mission_planner mission_validator_node
```

### 3.2 미션 요청 테스트
```bash
# 토픽으로 요청
ros2 topic pub /llm_mission/request std_msgs/String "data: '창고 3구역을 10m 고도에서 순찰해줘'"

# 서비스 호출 (비동기)
ros2 service call /llm_mission/plan std_msgs/String "data: '태양광 패널 10개 점검, 각 패널 앞 30초 호버링'"

# 검증 서비스
ros2 service call /llm_mission/validate std_msgs/String "data: '{\"mission_id\":\"test\",\"waypoints\":[{\"lat\":37.5665,\"lon\":126.978,\"alt\":10}],\"constraints\":{},\"failsafe\":{}}'"
```

### 3.3 응답 확인
```bash
# 미션 응답
ros2 topic echo /llm_mission/response

# 검증 결과
ros2 topic echo /llm_mission/validated

# 웨이포인트 (PX4 전송용)
ros2 topic echo /llm_mission/waypoints
```

---

## 📋 Phase 4: 실전 미션 예시

### 4.1 순찰 미션 (Patrol)
```bash
입력: "창고 3구역을 10m 고도에서 순찰해줘, 4개 코너 돌고 돌아와"

출력 예시:
{
  "mission_id": "patrol_warehouse_3_20260101_001",
  "mission_type": "patrol",
  "priority": "normal",
  "waypoints": [
    {"seq": 0, "lat": 37.5665, "lon": 126.9780, "alt": 10.0, "speed": 3.0, "action": "takeoff"},
    {"seq": 1, "lat": 37.5660, "lon": 126.9775, "alt": 10.0, "speed": 3.0, "action": "none"},
    {"seq": 2, "lat": 37.5660, "lon": 126.9785, "alt": 10.0, "speed": 3.0, "action": "photo"},
    {"seq": 3, "lat": 37.5670, "lon": 126.9785, "alt": 10.0, "speed": 3.0, "action": "photo"},
    {"seq": 4, "lat": 37.5670, "lon": 126.9775, "alt": 10.0, "speed": 3.0, "action": "photo"},
    {"seq": 5, "lat": 37.5665, "lon": 126.9780, "alt": 10.0, "speed": 2.0, "action": "land"}
  ],
  "constraints": {"geofence": [[37.5660,126.9770],[37.5670,126.9770],[37.5670,126.9790],[37.5660,126.9790]], "max_altitude": 15, "min_altitude": 5, "max_speed": 5, "safety_margin": 2},
  "failsafe": {"on_comm_loss": "rtl", "on_battery_low": "rtl", "on_geofence_breach": "rtl", "on_obstacle_critical": "hover"},
  "metadata": {"source_text": "창고 3구역을 10m 고도에서 순찰해줘", "llm_model": "gpt-4o"}
}
```

### 4.2 점검 미션 (Inspection)
```bash
입력: "태양광 패널 10개 점검해줘, 각 패널 앞에서 30초 호버링하며 사진 찍어"

출력: inspection 타입, 10개 웨이포인트, 각 hold_time: 30, action: "photo"
```

### 4.3 배달 미션 (Delivery)
```bash
입력: "A지점에서 B지점으로 패키지 배달해줘, 정밀 착륙 필요"

출력: delivery 타입, takeoff → waypoint A → waypoint B → precision land (RTK 필요시 fake GPS RTK 모드)
```

---

## 📋 Phase 5: 검증 파이프라인 이해

### 5.1 자동 검증 흐름
```
LLM 응답 → JSON 파싱 → MissionPlan 변환 → Validator.validate() → 
  ┌─ valid=true  → 발행 (/llm_mission/validated, /llm_mission/waypoints)
  └─ valid=false → 재시도 (최대 3회) → 실패 시 에러 발행
```

### 5.2 검증 기준 (코드 기준)
| 검사 | 임계값 | 심각도 |
|------|--------|--------|
| 위도/경도 범위 | -90~90, -180~180 | critical |
| 고도 범위 | min_altitude ~ max_altitude | critical |
| 지오펜스 내부 | 폴리곤 내부 + safety_margin | critical |
| 웨이포인트 간격 | ≤ max_waypoint_distance | warning |
| 고도 급변 | ≤ 10m/waypoint | warning |
| 속도 범위 | 0.1 ~ max_speed | critical |
| 액션 시퀀스 | 첫 takeoff, 마지막 land | warning |
| Failsafe 기본값 | 자동 채움 | info |

### 5.3 자동 수정 (auto_fix)
- 고도/속도 클램핑
- 중복 웨이포인트 제거
- takeoff/land 자동 추가
- 지오펜스 경계 스냅
- Failsafe 기본값 채움

---

## 📋 Phase 6: PX4 연동 및 실행

### 6.1 웨이포인트 → PX4 Mission 업로드
```bash
# 생성된 waypoints 토픽을 MAVROS mission upload로 변환
# /llm_mission/waypoints → mavros/mission/push
```

### 6.2 실행 모드 선택
| 미션 타입 | 실행 모드 | 비고 |
|----------|-----------|------|
| patrol/survey | AUTO (Mission) | 웨이포인트 순차 실행 |
| inspection | AUTO + loiter | hold_time 활용 |
| delivery | AUTO + precision land | RTK/fake GPS RTK 필요 |
| custom | OFFBOARD | 실시간 제어 필요 시 |

### 6.3 실시간 모니터링
```bash
# 미션 진행 상황
ros2 topic echo /mavros/mission/reached

# GPS 상태 (fake GPS 포함)
ros2 topic echo /mavros/global_position/global

# 배터리/링크
ros2 topic echo /mavros/battery
ros2 topic echo /silvus/link_quality
```

---

## 📋 Phase 7: 프롬프트 엔지니어링 팁

### 7.1 좋은 프롬프트 작성법
| 잘된 예 | 나쁜 예 |
|---------|---------|
| "창고 3구역을 10m 고도에서 시계방향으로 순찰, 각 코너에서 10초 호버링" | "창고 돌고 와" |
| "태양광 패널 A1~A10 순서대로 점검, 각 30초 호버링, 카메라 각도 45도 아래로" | "태양광 패널 찍어와" |
| "A(37.5665,126.9780)에서 B(37.5670,126.9790)로 배달, 착륙 반경 0.5m 이내" | "A에서 B로 가져다 줘" |

### 7.2 프롬프트에 포함하면 좋은 정보
- 목표 고도/속도/정밀도
- 지오펜스/금지구역 참조
- 배터리/시간 제약
- 특정 액션(photo, scan, loiter) 및 파라미터
- 비상시 대처 방안 (RTL 조건 등)

---

## 🚨 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| LLM 응답 JSON 파싱 실패 | 마크다운 코드 블록 포함 | 시스템 프롬프트에 "JSON only" 강조, 파싱 로직에서 ```json 제거 |
| 검증 실패 반복 | 프롬프트에 제약조건 누락 | mission_prompt.j2에 config 제약조건 모두 주입 확인 |
| 좌표계 오류 (ENU/NED) | 프롬프트에 좌표계 명시 안 함 | 시스템 프롬프트에 "출력 WGS84, 내부 ENU↔NED 변환" 명시 |
| LLM 타임아웃 | 모델 응답 느림 | llm_timeout 증가, max_tokens 감소, temperature=0.1 |
| 검증 무한 루프 | max_retries 초과 | max_retries 증가, retry_on_validation_error=false로 비활성화 |
| 지오펜스 위반 | LLM이 폴리곤 외부 좌표 생성 | 프롬프트에 geofence_polygon 주입 확인, auto_fix 활성화 |

---

## 🔗 관련 문서

| 문서 | 위치 |
|------|------|
| 시스템 아키텍처 | `docs/architecture.md` (LLM 역할 분리 10계명) |
| VIO→EKF2 연동 | `docs/guides/01_vio_ekf2_integration_guide.md` |
| Fake GPS | `docs/guides/03_fake_gps_guide.md` |
| 회피 파이프라인 | `docs/guides/02_obstacle_avoidance_guide.md` |
| 비행 로그 분석 | `docs/guides/04_flight_log_analysis_guide.md` |
| 개발 환경 | `docs/guides/05_dev_environment_setup_guide.md` |
| 빠른 참조 | `docs/QUICK_REFERENCE.md` |

---

*작성: 2026-11-04 | 기반: llm_mission_planner 패키지 + docs/architecture.md*