# Q250-V3 Opti 용어집 (Glossary)

> **이 프로젝트에서 사용되는 전문 용어, 약어, 개념 정의** - 신규 팀원 온보딩 및 문서 독해용

---

## 📋 알파벳순 용어 정의

### A
| 용어 | 정의 |
|------|------|
| **ADR** | Architecture Decision Record. 아키텍처 결정 기록. 주요 기술 선택의 배경, 대안, 결과를 문서화 |
| **AID_MASK** | EKF2 에이딩 마스크. 어떤 센서를 융합할지 비트마스크로 제어 (GPS, Optical-Flow, External Vision, Range 등) |
| **AUTO 모드** | PX4 비행 모드. 업로드된 미션(웨이포인트)을 자동 실행 |
| **AES-256** | Advanced Encryption Standard 256-bit. Silvus 데이터링크 암호화 표준 |

### B
| 용어 | 정의 |
|------|------|
| **Bag (ROS 2 bag)** | ROS 2 토픽 데이터를 시계열로 저장한 파일 형식 (MCAP/SQLite). 재생/분석용 |
| **BEC** | Battery Eliminator Circuit. 배터리 전압을 5V/3.3V로 강압하여 FC/서보 전원 공급 |
| **Bitmask** | 비트 단위 플래그 조합. 여러 불리언 옵션을 하나의 정수로 표현 (예: EKF2_AID_MASK) |

### C
| 용어 | 정의 |
|------|------|
| **CAN** | Controller Area Network. 차량/드론 내부 통신 버스 (DShot 텔레메트리 등) |
| **CCW** | Counter-Clockwise. 반시계 방향 (모터 회전 방향) |
| **COG** | Center of Gravity. 무게 중심. 기체 설계/파라미터 기준점 |
| **COM_OBL_RC_ACT** | RC 링크 손실 시 행동 파라미터 (0=무시, 1=Hold, 2=Position, 3=RTL, 4=Land) |
| **COMPASS** | 나침반/자력계. 지구 자기장 측정으로 요(Yaw) 절대 기준 제공 |
| **Costmap** | 2D/3D 그리드 맵. 각 셀에 장애물 비용(0~255) 저장. 플래너가 경로 탐색 시 참조 |

### D
| 용어 | 정의 |
|------|------|
| **Datum** | 기준점. Fake GPS에서 로컬 ENU 좌표를 전역 LLA(위도/경도/고도)로 변환할 때 쓰는 원점 |
| **DDS** | Data Distribution Service. ROS 2 미들웨어 표준. Real-time publish/subscribe 통신 |
| **Dead Reckoning** | 항법 계산. 마지막 알려진 위치 + 속도 × 시간으로 현재 위치 추정 (드리프트 누적) |
| **Drift** | 드리프트. VIO/INS 등 상대 센서에서 시간이 지날수록 누적되는 위치/자세 오차 |
| **DShot** | Digital Shot. ESC 제어 디지털 프로토콜 (DShot300/600/1200). PWM 대체 |

### E
| 용어 | 정의 |
|------|------|
| **EKF2** | Extended Kalman Filter 2. PX4의 메인 상태 추정기. IMU, GPS, Optical-Flow, Vision, Range 등 다중 센서 융합 |
| **ENU** | East-North-Up. ROS 표준 좌표계. x=동, y=북, z=상 |
| **ESC** | Electronic Speed Controller. 모터 속도 제어기. DShot/PWM 입력 → 3상 AC 출력 |
| **EV** | External Vision. 외부 비전 시스템(VIO, 모션 캡처 등)이 제공하는 포즈 데이터 |
| **EV_CTRL** | EKF2 External Vision 컨트롤 비트마스크 (1=Pos, 2=Vel, 4=Yaw, 8=Horiz Pos, 16=Vert Pos) |

### F
| 용어 | 정의 |
|------|------|
| **FC** | Flight Controller. 비행 제어 컴퓨터 (Pixhawk 등). 실시간 자세/위치 제어 담당 |
| **FRD** | Forward-Right-Down. PX4/항공 표준 좌표계. x=전방, y=우측, z=하방 (NED와 동일) |
| **Fake GPS** | VIO 로컬 포즈를 GPS_INPUT MAVLink 메시지로 변환하여 PX4에 주입. Global Position 기능 활성화용 |
| **Fast-DDS** | eProsima 구현 DDS. ROS 2 기본 미들웨어. 실시간/대역폭 최적화 설정 가능 |
| **Failsafe** | 페일세이프. 이상 상황(링크 손실, 배터리 부족, 지오펜스 등) 시 자동 안전 동작 |
| **FOV** | Field of View. 시야각. 카메라/센서가 커버하는 각도 범위 |

### G
| 용어 | 정의 |
|------|------|
| **GCS** | Ground Control Station. 지상국 소프트웨어 (QGroundControl, Mission Planner 등) |
| **Geofence** | 지오펜스. 가상 경계 울타리. 이탈 시 자동 RTL/Land/Terminate 동작 |
| **GF_ACTION** | Geofence 위반 시 행동 (1=RTL, 2=Land, 3=Terminate) |
| **GPS_INPUT** | MAVLink 메시지 ID 123. 외부 소스(VIO, Fake GPS)가 PX4에 GPS 데이터 주입용 |
| **GPS_RAW_INT** | MAVLink 메시지 ID 24. GPS 원시 데이터 (위도/경도/고도/속도/정확도) |
| **GPS_GLOBAL_ORIGIN** | MAVLink 메시지 ID 124. 로컬 좌표계 원점(위도/경도/고도) 설정/동기화 |

### H
| 용어 | 정의 |
|------|------|
| **HIL** | Hardware-In-the-Loop. 실제 하드웨어(FC) + 시뮬레이션 센서/환경 결합 테스트 |
| **HDOP** | Horizontal Dilution of Precision. GPS 수평 정밀도 저하도. 낮을수록 정확 (1.0~2.0 양호) |
| **HITL** | Hardware-In-the-Loop (HIL과 동일) |

### I
| 용어 | 정의 |
|------|------|
| **IMU** | Inertial Measurement Unit. 관성 측정 장치. 가속도계 + 자이로스코프 (일부 자력계 포함) |
| **Innovation** | 혁신/잔차. EKF2에서 예측값과 실측값의 차이. 센서 융합 품질 지표 |
| **INS** | Inertial Navigation System. 관성 항법. IMU 적분으로 위치/속도/자세 추정 |
| **I2C** | Inter-Integrated Circuit. 저속 직렬 통신 버스 (센서, EEPROM 등) |

### J
| 용어 | 정의 |
|------|------|
| **JetPack** | NVIDIA Jetson용 SDK. OS, CUDA, TensorRT, cuDNN, 비전 라이브러리 포함 |
| **Jupyter** | 웹 기반 인터랙티브 노트북. 데이터 분석/시각화용 |

### K
| 용어 | 정의 |
|------|------|
| **KV** | RPM per Volt. 모터 상수. 1V당 무부하 회전수 (RPM/V). 높을수록 고속/저토크 |

### L
| 용어 | 정의 |
|------|------|
| **LLA** | Latitude-Longitude-Altitude. 위도-경도-고도 (WGS84 지구 타원체 기준) |
| **LiDAR** | Light Detection and Ranging. 레이저 펄스 비행 시간으로 거리 측정 |
| **Local Position** | 로컬 위치. 이륙점/원점 기준 상대 좌표 (NED/FRD, 미터 단위) |
| **Loop Closure** | 루프 클로저. SLAM에서 이전에 방문한 장소 재인식으로 드리프트 보정 |

### M
| 용어 | 정의 |
|------|------|
| **MAVLink** | Micro Air Vehicle Link. 드론 통신 표준 프로토콜 (메시지 ID, 페이로드, CRC 정의) |
| **MAVROS** | MAVLink + ROS/ROS 2 브리지. MAVLink 메시지를 ROS 토픽/서비스로 변환 |
| **MCAP** | Message Capture. ROS 2 bag 기본 저장 형식. 빠른 기록/재생/압축 지원 |
| **MN-MIMO** | Mobile Networked MIMO. Silvus 독자 MANET 웨이브폼. TDMA/OFDMA, 다중 홉 |
| **MSCKF** | Multi-State Constraint Kalman Filter. VIO 알고리즘 일종. 특징점 기반 상태 추정 |
| **Mission** | 미션. 웨이포인트 리스트 + 명령(이륙, 웨이포인트, 착륙 등). AUTO 모드에서 실행 |

### N
| 용어 | 정의 |
|------|------|
| **NED** | North-East-Down. 항공/항법 표준 좌표계. x=북, y=동, z=하방 (FRD와 동일) |
| **NTP** | Network Time Protocol. 네트워크 시간 동기화 (밀리초 단위) |
| **NVMe** | Non-Volatile Memory Express. 고속 SSD 인터페이스 (Jetson 저장장치) |

### O
| 용어 | 정의 |
|------|------|
| **OBSTACLE_DISTANCE** | MAVLink 메시지 ID 330. 360도 섹터별 장애물 거리 (cm 단위) |
| **ODOMETRY** | MAVLink 메시지 ID 331. 오도메트리 데이터 (포즈 + 속도 + 공분산) |
| **OFFBOARD** | PX4 비행 모드. 외부 컴퓨터(ROS 2, GCS)가 실시간 setpoint(위치/속도/자세) 전송 |
| **Optical-Flow** | 광학 흐름. 카메라 영상 연속 프레임 간 픽셀 이동으로 상대 속도/이동량 추정 |
| **Origin** | 원점. 좌표계 기준점. Local: 이륙점, Global: GPS datum |

### P
| 용어 | 정의 |
|------|------|
| **PCAP** | Packet Capture. 네트워크 패킷 저장 파일 형식 (Wireshark 분석용) |
| **PID** | Proportional-Integral-Derivative. 피드백 제어 알고리즘 (PX4 컨트롤러 기반) |
| **Pixhawk** | PX4 하드웨어 표준. FMU(비행 관리 유닛) + IO(액추에이터 인터페이스) |
| **PNP** | Perspective-n-Point. 3D-2D 점 대응으로 카메라 포즈 추정 (VIO 초기화용) |
| **Position Mode** | PX4 비행 모드. 스틱 입력을 위치 제어 명령으로 변환 (GPS/VIO 필요) |
| **Provenance** | 출처/이력. 데이터의 출처 파일, SHA-256, 변환 코드 버전, 타임스탬프 등 추적 정보 |
| **PWM** | Pulse Width Modulation. 펄스 폭 변조. 아날로그 신호 모사 (서보, ESC 레거시) |
| **PX4** | Professional X(Experimental) 4. 오픈소스 비행 제어 소프트웨어/펌웨어 |

### Q
| 용어 | 정의 |
|------|------|
| **QGC / QGroundControl** | PX4 공식 지상국 소프트웨어. 펌웨어, 파라미터, 캘리브레이션, 미션, 로그 관리 |
| **Quaternion** | 사원수. 4원소(q0,q1,q2,q3)로 3D 회전 표현. 짐벌 락 없음, 보간 용이 |

### R
| 용어 | 정의 |
|------|------|
| **RC** | Radio Control. 무선 조종기/수신기. 조종 스틱 → 채널 값(1000~2000us) |
| **ROS 2** | Robot Operating System 2. DDS 기반 분산 로봇 미들웨어 (Humble/Iron/Rolling) |
| **RTL** | Return to Launch. 이륙점/원점으로 자동 복귀 후 착륙 |
| **RTP** | Real-time Transport Protocol. 오디오/비디오 스트리밍 표준 |
| **RTPS** | Real-Time Publish-Subscribe. DDS 와이어 프로토콜 (UDP/IP 위) |

### S
| 용어 | 정의 |
|------|------|
| **SBUS** | Serial Bus. Futaba/FrSky 디지털 RC 프로토콜 (100kbps, 16채널) |
| **SDK** | Software Development Kit. 개발 도구/라이브러리 모음 (JetPack, RealSense SDK 등) |
| **Setpoint** | 설정점. 제어 목표값 (위치, 속도, 자세, 추력 등). OFFBOARD에서 외부 전송 |
| **SHA-256** | Secure Hash Algorithm 256-bit. 파일 무결성 검증용 암호학적 해시 |
| **SITL** | Software-In-the-Loop. 소프트웨어만으로 PX4 + 시뮬레이터(Gazebo) 실행 테스트 |
| **SLAM** | Simultaneous Localization and Mapping. 동시 위치 추정 및 지도 작성 |
| **SNR** | Signal-to-Noise Ratio. 신호 대 잡음 비 (dB). 높을수록 링크 품질 양호 |
| **SPI** | Serial Peripheral Interface. 고속 동기 직렬 버스 (센서, 플래시 메모리) |
| **SRTM** | Shuttle Radar Topography Mission. NASA 고도 데이터 (지형 고도 보정용) |

### T
| 용어 | 정의 |
|------|------|
| **TDOA** | Time Difference of Arrival. 도달 시간 차이로 위치 추정 (Silvus 위치 측정) |
| **TEB** | Timed Elastic Band. 로컬 플래너 알고리즘. 시간 최적화 + 장애물 회피 탄성 밴드 |
| **TF / TF2** | Transform Frame. ROS 좌표계 변환 라이브러리. 프레임 간 상대 위치/자세 관리 |
| **Throttle** | 스로틀. 추력 조절 입력 (0~100%, 채널 3) |
| **Timesync** | MAVLink 메시지 ID 111. 시스템 간 시간 동기화 (tc1=로컬, ts1=원격) |

### U
| 용어 | 정의 |
|------|------|
| **uORB** | Micro Object Request Broker. PX4 내부 발행/구독 메시지 버스 (모듈 간 통신) |
| **uXRCE-DDS** | Micro XRCE-DDS. PX4 uORB ↔ ROS 2 DDS 브리지. 에이전트(PC/Jetson) + 클라이언트(FC) |
| **ULog** | PX4 비행 로그 바이너리 형식. 구조화된 메시지 스트림 + 메타데이터 + 압축 |

### V
| 용어 | 정의 |
|------|------|
| **VIO** | Visual-Inertial Odometry. 카메라 영상 특징점 + IMU 관성 데이터로 6DOF 포즈 추정 |
| **VFR_HUD** | MAVLink 메시지 ID 74. 가상 HUD 데이터 (고도, 속도, 자세, 스로틀 등) |
| **VTOL** | Vertical Take-Off and Landing. 수직 이착륙기 (쿼드플레인, 틸트로터 등) |

### W
| 용어 | 정의 |
|------|------|
| **Watchdog** | 워치독. 프로세스/스레드 생존 감시. 타임아웃 시 리셋/페일세이프 트리거 |
| **WGS84** | World Geodetic System 1984. 지구 타원체 표준 (GPS 좌표계 기준) |
| **WLS** | Weighted Least Squares. 가중 최소자승법. 센서 융합/캘리브레이션 최적화 |

### X/Y/Z
| 용어 | 정의 |
|------|------|
| **XRCE** | eXtensible Remote Communication Entity. DDS 원격 엔티티 (uXRCE-DDS의 XRCE) |
| **Yaw** | 요(Yaw). 수직축(Z) 회전. 방위각. NED에서 시계방향 양수 |
| **YPR** | Yaw-Pitch-Roll. 오일러 각 순서 (Z-Y-X). 자세 표현 방식 |

---

## 🔤 약어 치트시트 (Acronym Cheatsheet)

| 약어 | 풀네임 | 분야 |
|------|--------|------|
| **AHRS** | Attitude and Heading Reference System | 자세/방위 기준 시스템 |
| **CAN** | Controller Area Network | 통신 버스 |
| **CCW** | Counter-Clockwise | 모터 방향 |
| **COG** | Center of Gravity | 무게중심 |
| **CPU** | Central Processing Unit | 프로세서 |
| **CRC** | Cyclic Redundancy Check | 오류 검출 |
| **CW** | Clockwise | 모터 방향 |
| **DOF** | Degrees of Freedom | 자유도 |
| **DPS** | Degrees Per Second | 각속도 단위 |
| **DShot** | Digital Shot | ESC 프로토콜 |
| **ECEF** | Earth-Centered Earth-Fixed | 지구 중심 좌표계 |
| **EKF** | Extended Kalman Filter | 확장 칼만 필터 |
| **ESC** | Electronic Speed Controller | 변속기 |
| **FDM** | Flight Dynamics Model | 비행 역학 모델 |
| **FOV** | Field of View | 시야각 |
| **FPS** | Frames Per Second | 프레임율 |
| **GCS** | Ground Control Station | 지상국 |
| **GNSS** | Global Navigation Satellite System | 위성 항법 (GPS+GLONASS+Galileo) |
| **GPU** | Graphics Processing Unit | 그래픽 처리 |
| **GPS** | Global Positioning System | 전지구 위치 결정 |
| **HIL** | Hardware-In-the-Loop | 하드웨어 인 더 루프 |
| **HUD** | Heads-Up Display | 헤드업 디스플레이 |
| **IMU** | Inertial Measurement Unit | 관성 측정 장치 |
| **I/O** | Input/Output | 입출력 |
| **KV** | RPM per Volt | 모터 상수 |
| **LIDAR** | Light Detection and Ranging | 라이다 |
| **LOS** | Line of Sight | 가시선 |
| **MAV** | Micro Air Vehicle | 소형 항공기 |
| **MIMO** | Multiple Input Multiple Output | 다중 입출력 |
| **MSCKF** | Multi-State Constraint Kalman Filter | 다중 상태 제약 칼만 필터 |
| **NED** | North-East-Down | 북-동-하 좌표계 |
| **PID** | Proportional-Integral-Derivative | 비례-적분-미분 제어 |
| **PPM** | Pulse Position Modulation | 펄스 위치 변조 |
| **PWM** | Pulse Width Modulation | 펄스 폭 변조 |
| **QGC** | QGroundControl | 지상국 SW |
| **RC** | Radio Control | 무선 조종 |
| **RPM** | Revolutions Per Minute | 분당 회전수 |
| **RSSI** | Received Signal Strength Indicator | 수신 신호 강도 |
| **RTL** | Return to Launch | 귀환 착륙 |
| **RTP** | Real-time Transport Protocol | 실시간 전송 프로토콜 |
| **RTPS** | Real-Time Publish-Subscribe | 실시간 발행-구독 |
| **SBUS** | Serial Bus | 직렬 버스 (RC) |
| **SITL** | Software-In-the-Loop | 소프트웨어 인 더 루프 |
| **SLAM** | Simultaneous Localization and Mapping | 동시 위치 추정 및 지도 작성 |
| **SNR** | Signal-to-Noise Ratio | 신호 대 잡음비 |
| **SOC** | System on Chip | 시스템 온 칩 |
| **TCP** | Transmission Control Protocol | 전송 제어 프로토콜 |
| **TF** | Transform Frame | 좌표계 변환 |
| **TDOA** | Time Difference of Arrival | 도달 시간 차이 |
| **TEB** | Timed Elastic Band | 시탄성 밴드 플래너 |
| **UART** | Universal Asynchronous Receiver-Transmitter | 범용 비동기 수신송신 |
| **UDP** | User Datagram Protocol | 사용자 데이터그램 프로토콜 |
| **uORB** | Micro Object Request Broker | PX4 내부 메시지 버스 |
| **USB** | Universal Serial Bus | 범용 직렬 버스 |
| **VIO** | Visual-Inertial Odometry | 시각-관성 오도메트리 |
| **VTOL** | Vertical Take-Off and Landing | 수직 이착륙 |
| **WGS84** | World Geodetic System 1984 | 세계 지odetic 시스템 1984 |

---

## 📐 좌표계 변환 요약 (Coordinate Frame Cheatsheet)

| 변환 | 공식 | 비고 |
|------|------|------|
| **ENU → NED** | `x_ned = y_enu`, `y_ned = x_enu`, `z_ned = -z_enu` | ROS ↔ PX4 |
| **NED → ENU** | `x_enu = y_ned`, `y_enu = x_ned`, `z_enu = -z_ned` | PX4 ↔ ROS |
| **Body → NED** | 회전행렬 `R_body_to_ned(q)` | 자세 q로 변환 |
| **Camera → Body** | 고정 오프셋 `t_cb`, 회전 `R_cb` | 캘리브레이션 결과 |
| **ENU → LLA** | 평탄 지구 근사 (소규모) | Fake GPS용 |
| **LLA → ECEF** | WGS84 타원체 공식 | 정밀 변환 |

---

## 📏 단위계 요약 (Units Summary)

| 물리량 | PX4/MAVLink | ROS 2 | 비고 |
|--------|-------------|-------|------|
| **위치** | meter (m) | meter (m) | 동일 |
| **속도** | m/s | m/s | 동일 |
| **가속도** | m/s² | m/s² | 동일 |
| **각도** | radian (rad) | radian (rad) | 동일 |
| **각속도** | rad/s | rad/s | 동일 |
| **자세** | Quaternion / Euler (rad) | Quaternion / Euler (rad) | 동일 |
| **시간** | microsecond (µs) | nanosecond (ns) | **단위 다름!** |
| **거리(MAVLink)** | centimeter (cm) | meter (m) | **단위 다름!** |
| **자력계** | Gauss / mG | Tesla (T) | 1 Gauss = 100 µT |
| **기압** | hPa / mbar | Pa | 1 hPa = 100 Pa |

> ⚠️ **시간/거리 단위 변환 필수** - MAVLink ↔ ROS 2 브리지에서 자동 처리되나 직접 파싱 시 주의

---

*Glossary v1.0 | 2026-11-04 | 신규 팀원 필독*