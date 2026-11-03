# Q250-V3 Opti 안전 체크리스트 (Safety Checklist Card)

> **라미네이트해서 현장에 비치** - A5 크기 양면 인쇄, 펀칭 후 바인더링 권장
> **비행 전 필수 확인** - 모든 항목 체크 후 서명

---

## 🚁 비행 전 체크리스트 (PRE-FLIGHT)

### 하드웨어
- [ ] 프로펠러 방향/고정 (CW/CCW 확인)
- [ ] 배터리 100% 충전, 커넥터 체결, 전압 확인 (16.8V/4S)
- [ ] Silvus Air Unit 4대 연결, 웹 UI 접속 확인
- [ ] RealSense D435i USB 3.0 연결, 토픽 발행 확인
- [ ] LiDAR(TF-Luna) / Optical-Flow 토픽 발행 확인
- [ ] RC 수신기 바인딩, 페일세이프 설정 (RTL/Position)
- [ ] 비상정지(킬 스위치) 작동 확인

### 소프트웨어 (개발 PC + Jetson)
- [ ] MAVLink Router 실행 (journalctl 확인)
- [ ] uXRCE-DDS Agent 실행 (Client connected)
- [ ] ROS 2 토픽: `/camera/depth`, `/mavros/*`, `/fmu/out/*` 활성
- [ ] EKF2 파라미터: 실내 모드 적용 확인 (GPS/Mag OFF)
- [ ] VIO 포즈: `/ov_msckf/pose` 30Hz, 드리프트 < 1cm/s
- [ ] Fake GPS: `/mavros/gps_input/input` 10Hz (Mission 시)
- [ ] Silvus 모니터: `scripts/silvus_monitor.py` 실행 중

### 통신/링크
- [ ] Silvus RSSI > -70dBm 전 기체
- [ ] 패킷 로스 < 1%, RTT < 10ms
- [ ] MAVLink 양방향 통신 (GCS ↔ 기체)
- [ ] uXRCE-DDS 세션 활성 (Heartbeat 수신)

### 안전/환경
- [ ] 비행 구역 네트/패딩 설치
- [ ] 관측자 1명 배치 (RC 수동 오버라이드 준비)
- [ ] 비상정지 버튼/킬 스위치 손에 쥐고 있음
- [ ] 소화기, 구급상자 비치 확인
- [ ] 배터리 예비 1개, 충전기 준비
- [ ] 날씨/풍속 확인 (실내: 환기, 조명 충분)

---

## ✈️ 비행 중 모니터링 (IN-FLIGHT)

| 항목 | 정상 범위 | 경고 | 즉시 조치 |
|------|-----------|------|-----------|
| **EKF2 혁신 (Pos)** | ±0.1m | ±0.3m | >0.5m → Manual |
| **EKF2 혁신 (Vel)** | ±0.05m/s | ±0.15m/s | >0.3m/s → Manual |
| **EKF2 혁신 (Yaw)** | ±0.02rad | ±0.05rad | >0.1rad → Manual |
| **VIO 드리프트** | <0.5m/5min | 1m/5min | >2m → Origin Reset |
| **Silvus RSSI** | >-70dBm | -70~-85dBm | <-85dBm → RTL |
| **패킷 로스** | <1% | 1~10% | >10% → RTL |
| **RTT** | <10ms | 10~50ms | >50ms → 속도 50% 감속 |
| **OFFBOARD 유지율** | >95% | 90~95% | <90% → Position |
| **배터리 전압** | >15.5V | 15.0~15.5V | <14.8V → Land |
| **모터 온도** | <60°C | 60~75°C | >80°C → Land |

---

## 🚨 비상 절차 (EMERGENCY PROCEDURES)

| 상황 | 즉시 행동 (3초 내) | 후속 조치 |
|------|-------------------|-----------|
| **제어 상실/이상 동작** | 1. 킬 스위치 2. Manual 모드 3. 착륙 유도 | 로그 다운로드, 원인 분석 |
| **배터리 저전압 (<14.8V)** | 1. RTL 스위치 2. 착륙 확인 | 배터리 교체, 비행 중단 |
| **Silvus 링크 끊김** | 1. Position 모드 확인 2. 수동 조종 준비 | 링크 복구 대기, 강제 RTL |
| **VIO/EKF2 발산** | 1. Position→Manual 즉시 2. 킬 스위치 | 로그 분석, 파라미터 재튜닝 |
| **충돌/임박** | 1. 킬 스위치 2. 프로펠러 정지 확인 | 안전 거리 확보, 손상 점검 |
| **지오펜스 이탈** | 1. 자동 RTL 확인 2. 수동 개입 준비 | 원인 분석, 펜스 재설정 |
| **OFFBOARD 이탈** | 1. Position 모드 확인 2. 플래너 재시작 | 플래너 로그 분석 |

---

## 📝 비행 후 필수 (POST-FLIGHT)

- [ ] 로그 다운로드: QGC → Log Download → `log_XXX.ulg`
- [ ] SHA-256 기록: `sha256sum log_XXX.ulg > SHA256SUMS.txt`
- [ ] 자동 분석: `python3 scripts/postflight/analyze_log.py log_XXX.ulg`
- [ ] 핵심 확인:
  - [ ] EKF2 혁신 3σ 위반율 < 5%
  - [ ] VIO 드리프트 < 0.5m/분
  - [ ] OFFBOARD 유지율 > 95%
  - [ ] 최소 장애물 거리 > 0.5m
  - [ ] Silvus 패킷 로스 < 1%
- [ ] CHANGELOG 기록: `px4_params/CHANGELOG.md`
- [ ] 배터리 충전/보관 (3.8V/storage)
- [ ] 하드웨어 점검: 프로펠러, 마운트, 커넥터
- [ ] 이슈/개선사항 메모: `docs/troubleshooting.md`

---

## ✍️ 서명란 (SIGNATURES)

| 역할 | 이름 | 서명 | 일시 |
|------|------|------|------|
| **파일럿 (PIC)** | | | |
| **관측자 (VO)** | | | |
| **안전관리자** | | | |
| **기술리드** | | | |

---

## 📞 비상 연락처

| 역할 | 이름 | 전화 | 무전 채널 |
|------|------|------|-----------|
| 안전관리자 | | | Ch 1 |
| 기술리드 | | | Ch 2 |
| 의료/소방 | 119 | - | - |
| 경찰 | 112 | - | - |

---

*체크리스트 v1.0 | 2026-11-04 | A5 양면 라미네이트 | 비행마다 신규 출력*