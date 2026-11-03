# 13. fake GPS 구현 가이드 (Global Position 연동용)

> `jetson-px4-ros2-autonomous-drone/docs/13-fake-gps.md`를 Q250-V3-Opti 실기체 환경에 맞춰 재구성했습니다.

---

## 13.1 fake GPS가 필요한 이유

VIO/External Vision만으로는 **local position (NED, 원점 기준)**만 제공됩니다. 하지만 PX4의 다음 기능들은 **global position (위도/경도/고도)**을 요구합니다:

| 기능 | Global Position 필요 여부 |
|------|---------------------------|
| Mission (웨이포인트 비행) | ✅ 필수 |
| RTL (Return to Launch) | ✅ 필수 |
| Geofence (GF_ACTION) | ✅ 필수 |
| Position 모드 (실내) | ❌ Local만으로 가능 |
| OFFBOARD (setpoint) | ❌ Local만으로 가능 |

**fake GPS** = VIO local pose → **위도/경도/고도 변환** → `GPS_INPUT` MAVLink 메시지 → PX4 GPS 입력

---

## 13.2 아키텍처

```
VIO Estimator (ROS 2)
      │
      ▼ (local pose: x, y, z, q in ENU)
fake_gps Node
      │
      ├─ Datum/Origin 설정 (위도₀, 경도₀, 고도₀)
      ├─ 좌표 변환: ENU → LLA (WGS84)
      ├─ 품질 필드 생성 (fix_type, satellites, accuracy)
      └─ 타임스탬프 동기화
      │
      ▼ (GPS_INPUT MAVLink)
MAVROS / px4_ros_com
      │
      ▼
PX4 GPS Module → EKF2 (GPS fusion)
      │
      ▼
Global Position Valid → Mission/RTL/Geofence 활성화
```

---

## 13.3 필수 구성 요소

### 13.3.1 기준 원점 (Datum/Origin) 설정
```yaml
# config/fake_gps.yaml 예시
fake_gps:
  datum:
    latitude:  37.5665   # 서울시청 예시 (실제 이륙 지점)
    longitude: 126.9780
    altitude:  28.0      # MSL 고도 (m)
  # 또는 MAVLink SET_GPS_GLOBAL_ORIGIN으로 동적 설정
```

> **중요**: 원점은 **비행 전 고정**하거나, **초기 GPS 수신 시 자동 저장**해야 함. 중간에 바꾸면 위치 점프 발생.

### 13.3.2 좌표 변환 (ENU → LLA)
```python
# 대략적 변환 (소규모 지역, 평탄 지구 가정)
# 정확하려면 pyproj 또는 GeographicLib 사용 권장

import math

def enu_to_lla(x_enu, y_enu, z_enu, lat0, lon0, alt0):
    # 지구 반경 근사
    R = 6378137.0  # m
    
    dlat = x_enu / R * 180.0 / math.pi
    dlon = y_enu / (R * math.cos(math.radians(lat0))) * 180.0 / math.pi
    
    lat = lat0 + dlat
    lon = lon0 + dlon
    alt = alt0 + z_enu  # ENU z = Up, LLA alt = MSL
    
    return lat, lon, alt
```

### 13.3.3 GPS_INPUT 메시지 필드 (MAVLink)
```python
# MAVLink GPS_INPUT 필수 필드
msg = GPS_INPUT(
    time_usec=now_usec,           # 마이크로초 타임스탬프 (PX4 시간 기준)
    gps_id=0,                     # GPS ID (0=primary)
    ignore_flags=0,               # 무시할 필드 비트마스크
    time_week_ms=0,               # GPS 주 밀리초 (fake: 0)
    time_week=0,                  # GPS 주 (fake: 0)
    fix_type=3,                   # 3=3D fix, 4=DGPS, 5=RTK
    lat=int(lat * 1e7),           # 위도 × 1e7 (degE7)
    lon=int(lon * 1e7),           # 경도 × 1e7 (degE7)
    alt=int(alt * 1000),          # 고도 mm (MSL)
    hdop=1.0,                     # 수평 정밀도 저하도
    vdop=1.0,                     # 수직 정밀도 저하도
    vn=0, ve=0, vd=0,             # 속도 NED (m/s, fake: 0)
    speed_accuracy=0.1,           # 속도 정확도 (m/s)
    horiz_accuracy=0.5,           # 수평 정확도 (m)
    vert_accuracy=0.5,            # 수직 정확도 (m)
    satellites_visible=10,        # 위성 수 (fake: 10)
    yaw=0,                        # Yaw (deg, fake: 0)
    yaw_accuracy=0.0              # Yaw 정확도
)
```

**품질 필드 설정 원칙**:
- `fix_type=3` (3D fix) 최소, RTK 시뮬레이션 시 `5`
- `satellites_visible=8~12` (실제처럼 보이게)
- `horiz_accuracy`, `vert_accuracy` = VIO 공분산에서 유도
- `ignore_flags`로 미제공 필드 명시 (예: 속도 미제공 시 `GPS_INPUT_IGNORE_FLAG_VEL` 설정)

---

## 13.4 구현 예시 (ROS 2 노드)

### fake_gps_node.py (스켈레톤)
```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from mavros_msgs.msg import GPSINPUT
from std_msgs.msg import Header
import math

class FakeGPSNode(Node):
    def __init__(self):
        super().__init__('fake_gps_node')
        
        # 파라미터
        self.declare_parameter('datum_lat', 37.5665)
        self.declare_parameter('datum_lon', 126.9780)
        self.declare_parameter('datum_alt', 28.0)
        self.declare_parameter('fix_type', 3)
        self.declare_parameter('satellites_visible', 10)
        self.declare_parameter('horiz_accuracy', 0.5)
        self.declare_parameter('vert_accuracy', 0.5)
        
        self.datum_lat = self.get_parameter('datum_lat').value
        self.datum_lon = self.get_parameter('datum_lon').value
        self.datum_alt = self.get_parameter('datum_alt').value
        
        # 구독: VIO pose (ENU)
        self.sub = self.create_subscription(
            PoseWithCovarianceStamped,
            '/vio/pose',  # VIO 노드 출력 토픽
            self.pose_callback,
            10)
        
        # 발행: MAVROS GPS_INPUT
        self.pub = self.create_publisher(
            GPSINPUT,
            '/mavros/gps_input/input',
            10)
        
        self.get_logger().info(f'Fake GPS initialized: datum=({self.datum_lat}, {self.datum_lon}, {self.datum_alt})')
    
    def pose_callback(self, msg: PoseWithCovarianceStamped):
        # ENU → LLA 변환
        x_enu = msg.pose.pose.position.x
        y_enu = msg.pose.pose.position.y
        z_enu = msg.pose.pose.position.z
        
        lat, lon, alt = self.enu_to_lla(x_enu, y_enu, z_enu)
        
        # 공분산에서 정확도 추출
        cov = msg.pose.covariance
        horiz_acc = math.sqrt(max(cov[0], cov[7]))  # x, y 분산
        vert_acc = math.sqrt(cov[14])               # z 분산
        
        # GPS_INPUT 메시지 구성
        gps_msg = GPSINPUT()
        gps_msg.header = Header()
        gps_msg.header.stamp = self.get_clock().now().to_msg()
        gps_msg.header.frame_id = 'gps'
        
        gps_msg.time_usec = int(self.get_clock().now().nanoseconds / 1000)
        gps_msg.gps_id = 0
        gps_msg.ignore_flags = GPSINPUT.IGNORE_FLAG_VEL | GPSINPUT.IGNORE_FLAG_YAW
        gps_msg.fix_type = self.get_parameter('fix_type').value
        gps_msg.lat = int(lat * 1e7)
        gps_msg.lon = int(lon * 1e7)
        gps_msg.alt = int(alt * 1000)
        gps_msg.hdop = 1.0
        gps_msg.vdop = 1.0
        gps_msg.satellites_visible = self.get_parameter('satellites_visible').value
        gps_msg.horiz_accuracy = max(horiz_acc, self.get_parameter('horiz_accuracy').value)
        gps_msg.vert_accuracy = max(vert_acc, self.get_parameter('vert_accuracy').value)
        
        self.pub.publish(gps_msg)
    
    def enu_to_lla(self, x, y, z):
        R = 6378137.0
        dlat = x / R * 180.0 / math.pi
        dlon = y / (R * math.cos(math.radians(self.datum_lat))) * 180.0 / math.pi
        return self.datum_lat + dlat, self.datum_lon + dlon, self.datum_alt + z

def main():
    rclpy.init()
    node = FakeGPSNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### Launch 파일
```xml
<!-- launch/fake_gps.launch.py -->
<launch>
  <node pkg="fake_gps" exec="fake_gps_node" name="fake_gps_node" output="screen">
    <param name="datum_lat" value="37.5665"/>
    <param name="datum_lon" value="126.9780"/>
    <param name="datum_alt" value="28.0"/>
    <param name="fix_type" value="3"/>
    <param name="satellites_visible" value="10"/>
    <param name="horiz_accuracy" value="0.5"/>
    <param name="vert_accuracy" value="0.5"/>
    <remap from="/vio/pose" to="/ov_msckf/pose"/>
  </node>
</launch>
```

---

## 13.5 PX4 파라미터 설정

```bash
# fake GPS 활성화 시
EKF2_GPS_CTRL   7       # GPS 위치+속도+고도 모두 융합 (비트 0,1,2)
EKF2_GPS_CHECK  31      # GPS 품질 체크 완화 (비트 0~4)
EKF2_GPS_P_NOISE 0.5    # GPS 위치 노이즈 (m)
EKF2_GPS_V_NOISE 0.5    # GPS 속도 노이즈 (m/s)

# External Vision은 그대로 유지 (보조)
EKF2_EV_CTRL    15
EKF2_AID_MASK   352     # OF + Range + EV Yaw + GPS

# Mag은 실내에서 비활성화
EKF2_MAG_TYPE   5
```

> **주의**: `EKF2_GPS_CTRL=7`로 하면 fake GPS가 **주 위치 소스**가 됩니다. VIO drift가 누적되면 global position도 같이 드리프트합니다. 주기적 원점 재설정 또는 루프 클로저 필요.

---

## 13.6 검증 절차

### 13.6.1 벤치 테스트 (프로펠러 제거)
```bash
# 1. fake_gps_node 실행
ros2 launch fake_gps fake_gps.launch.py

# 2. MAVROS GPS_INPUT 발행 확인
ros2 topic echo /mavros/gps_input/input

# 3. QGroundControl에서 GPS 상태 확인
# - GPS: 3D Fix, 위성 10개, HDOP ~1.0
# - Global Position: 위도/경도/고도 표시됨
# - Map에 기체 위치 표시됨

# 4. PX4 EKF2 혁신 확인
# MAVLink Console: ekf2 innovation monitor
# gps_innov[0~2]가 ±3 sigma 내
```

### 13.6.2 Mission/RTL 테스트 (SITL 먼저)
```bash
# SITL에서 Mission 업로드 → RTL → Geofence 테스트
# fake GPS로 global position valid가 되면 Mission 실행 가능해짐
```

### 13.6.3 실내 비행 테스트
```bash
# 1. 무프로펠러 Position 모드 → GPS 상태 확인
# 2. 저고도 수동 비행 → Global position 궤적 기록
# 3. Mission 업로드 → 자동 비행 → RTL 동작 확인
# 4. Geofence 위반 시 GF_ACTION(1=RTL) 동작 확인
```

---

## 13.7 실패 모드 및 대응

| 증상 | 원인 | 대응 |
|------|------|------|
| GPS status: No Fix | `fix_type` 미설정 / 메시지 미도달 | 토픽 확인, MAVROS 연결 확인 |
| Global position 점프 | 원점(datum) 변경 / 좌표변환 오류 | 원점 고정, 변환 공식 검증 |
| EKF2가 GPS 거부 | `horiz_accuracy` 너무 큼 / 혁신 초과 | 정확도 값 낮추기, `EKF2_GPS_CHECK` 완화 |
| Mission 시작 안 함 | Global position valid 안 뜸 | GPS fix_type=3 이상, 위성 수 5개 이상 |
| RTL 시 엉뚱한 곳 감 | 원점과 실제 이륙 지점 불일치 | 이륙 시 `SET_GPS_GLOBAL_ORIGIN` 자동 전송 구현 |

---

## 13.8 운영 권장사항

1. **원점 자동 저장**: 첫 GPS 수신(실외) 또는 첫 VIO pose(실내) 시 `SET_GPS_GLOBAL_ORIGIN` 전송
2. **주기적 품질 모니터링**: `horiz_accuracy` > 2m 시 경고, > 5m 시 fake GPS 중단
3. **VIO drift 보정**: 루프 클로저 또는 알려진 랜드마크에서 원점 재보정
4. **실외 전환 시**: fake GPS → 실제 GPS 자동 전환 로직 구현 (fix_type 비교)

---

## 13.9 다음 단계

1. **fake_gps ROS 2 패키지** 생성 → `ros2_ws/src/fake_gps/`
2. **launch 파일** 및 **파라미터 yaml** 추가
3. **SITL에서 Mission/RTL 테스트** 후 실기체 적용
5. **VIO drift 모니터링** 노드와 연계 (drift > 임계값 시 경고)