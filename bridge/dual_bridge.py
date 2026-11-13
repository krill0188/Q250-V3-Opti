#!/usr/bin/env python3
"""
MAVSDK + MAVROS2 듀얼 브릿지 기초 구조
T-04 SpecKit 작업
"""

import asyncio
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
import threading
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum
import sys
import os

# MAVSDK
try:
    from mavsdk import System
    from mavsdk.mission import MissionItem, MissionPlan
    from mavsdk.offboard import OffboardError, VelocityBodyYawspeed
    from mavsdk.action import ActionError

    MAVSDK_AVAILABLE = True
except ImportError:
    MAVSDK_AVAILABLE = False
    print("Warning: mavsdk not installed. Run: pip install mavsdk")

# MAVROS2 메시지
try:
    from mavros_msgs.msg import State, CommandBool, SetMode
    from mavros_msgs.srv import CommandBool as CommandBoolSrv, SetMode as SetModeSrv
    from geometry_msgs.msg import PoseStamped, TwistStamped
    from sensor_msgs.msg import NavSatFix, Imu, BatteryState
    from std_msgs.msg import Header

    MAVROS2_AVAILABLE = True
except ImportError:
    MAVROS2_AVAILABLE = False
    print("Warning: mavros_msgs not available. Install ros-humble-mavros-msgs")

# 우리 커스텀 메시지
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "generated", "mavlink")
)
try:
    import python as mavlink_custom

    CUSTOM_MSGS_AVAILABLE = True
except ImportError:
    CUSTOM_MSGS_AVAILABLE = False
    print("Warning: Custom MAVLink messages not found. Run mavgen first.")


# =============================================================================
# MAVLink 직접 명령 헬퍼 (MAVSDK 부족 기능 보완)
# =============================================================================
class MAVLinkHelper:
    """MAVLink 직접 명령 전송 헬퍼 (MAVSDK 부족 기능 보완)"""

    def __init__(self, drone):
        self.drone = drone
        self.mav = drone._mavlink

    async def set_mode(self, mode: str) -> bool:
        """모드 변경 (PX4/ArduPilot 공통) - MAV_CMD_DO_SET_MODE (176)"""
        mode_map = {
            "GUIDED": 4,
            "AUTO": 3,
            "LOITER": 5,
            "RTL": 6,
            "LAND": 9,
            "TAKEOFF": 22,
            "OFFBOARD": 6,  # PX4 기준
            "MANUAL": 0,
            "STABILIZE": 1,
            "ACRO": 2,  # ArduPilot
        }
        custom_mode = mode_map.get(mode.upper(), 0)

        try:
            msg = self.mav.mav.command_long_encode(
                0,
                0,  # target system/component
                176,  # MAV_CMD_DO_SET_MODE
                0,  # confirmation
                1,  # base_mode: MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
                float(custom_mode),
                0,
                0,
                0,
                0,
                0,
            )
            await self.mav.send_message(msg)
            return True
        except Exception as e:
            print(f"MAVLinkHelper.set_mode failed: {e}")
            return False

    async def inject_voice_command(
        self, command_id: int, action: str, params: list, confidence: float
    ) -> bool:
        """음성 명령 주입 (테스트/시뮬레이션용)"""
        if not CUSTOM_MSGS_AVAILABLE:
            return False
        try:
            msg = mavlink_custom.MAVLink_voice_command_message(
                timestamp_ms=int(time.time() * 1000),
                command_text=f"injected:{action}".encode() + b"\x00",
                parsed_action=action.encode() + b"\x00",
                params=params + [0.0] * (10 - len(params)),
                param_count=min(len(params), 10),
                confidence=confidence,
                is_final=1,
                command_id=command_id,
            )
            buf = msg.pack(mavlink_custom.MAVLink("test"))
            for b in bytes(buf):
                self.mav.parse_char(b)
            return True
        except Exception as e:
            print(f"MAVLinkHelper.inject_voice_command failed: {e}")
            return False


def merge_state(mavsdk_state: DroneState, mavros2_state: DroneState) -> DroneState:
    """우선순위 기반 상태 병합 (MAVSDK > MAVROS2 for 고수준, MAVROS2 > MAVSDK for 센서)"""
    merged = DroneState()

    # 연결 상태: OR 연산
    merged.connected = mavsdk_state.connected or mavros2_state.connected

    # 무장/비행: MAVSDK 우선 (고수준 상태)
    merged.armed = mavsdk_state.armed if mavsdk_state.connected else mavros2_state.armed
    merged.in_air = (
        mavsdk_state.in_air if mavsdk_state.connected else mavros2_state.in_air
    )

    # 모드: MAVSDK 우선, 없으면 MAVROS2
    merged.mode = (
        mavsdk_state.mode if mavsdk_state.mode != "UNKNOWN" else mavros2_state.mode
    )

    # 위치: MAVSDK (글로벌) 우선
    merged.latitude = (
        mavsdk_state.latitude if mavsdk_state.latitude != 0 else mavros2_state.latitude
    )
    merged.longitude = (
        mavsdk_state.longitude
        if mavsdk_state.longitude != 0
        else mavros2_state.longitude
    )
    merged.altitude_amsl = mavsdk_state.altitude_amsl or mavros2_state.altitude_amsl
    merged.altitude_rel = mavsdk_state.altitude_rel or mavros2_state.altitude_rel

    # 배터리/GPS: MAVROS2 (전용 토픽) 우선
    merged.battery_percent = (
        mavros2_state.battery_percent or mavsdk_state.battery_percent
    )
    merged.gps_fix_type = mavros2_state.gps_fix_type or mavsdk_state.gps_fix_type
    merged.satellites = mavros2_state.satellites or mavsdk_state.satellites

    # 기타
    merged.heading = mavsdk_state.heading or mavros2_state.heading
    merged.velocity_ned = (
        mavsdk_state.velocity_ned
        if mavsdk_state.velocity_ned != (0.0, 0.0, 0.0)
        else mavros2_state.velocity_ned
    )

    # 타임스탬프: 최신값
    merged.last_update = max(mavsdk_state.last_update, mavros2_state.last_update)

    return merged


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ARMED = "armed"
    IN_AIR = "in_air"
    ERROR = "error"


@dataclass
class DroneState:
    """통합 드론 상태"""

    connected: bool = False
    armed: bool = False
    in_air: bool = False
    mode: str = "UNKNOWN"
    battery_percent: float = 0.0
    gps_fix_type: int = 0
    satellites: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_amsl: float = 0.0
    altitude_rel: float = 0.0
    heading: float = 0.0
    velocity_ned: tuple = (0.0, 0.0, 0.0)
    last_update: float = 0.0


class MAVSDKBridge:
    """MAVSDK 브릿지 - 고수준 미션/오프보드 제어용"""

    def __init__(self, system_address: str = "udp://:14540"):
        self.system_address = system_address
        self.drone: Optional[System] = None
        self.state = DroneState()
        self.connected = False
        self._state_callbacks: list[Callable[[DroneState], None]] = []
        _running = False

    async def connect(self) -> bool:
        """드론 연결"""
        if not MAVSDK_AVAILABLE:
            raise RuntimeError("MAVSDK not installed")

        self.drone = System()
        try:
            await self.drone.connect(system_address=self.system_address)

            # 연결 대기
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    self.connected = True
                    print(f"MAVSDK: Connected to drone at {self.system_address}")
                    break

            # 상태 모니터링 시작
            self._running = True
            asyncio.create_task(self._monitor_state())
            return True

        except Exception as e:
            print(f"MAVSDK connection failed: {e}")
            return False

    async def _monitor_state(self):
        """상태 모니터링 루프"""
        try:
            async for state in self.drone.telemetry.position():
                if not self._running:
                    break
                self.state.latitude = state.latitude_deg
                self.state.longitude = state.longitude_deg
                self.state.altitude_amsl = state.absolute_altitude_m
                self.state.altitude_rel = state.relative_altitude_m
                self.state.last_update = time.time()
                self._notify_state_change()
        except Exception as e:
            print(f"MAVSDK position monitor error: {e}")

        try:
            async for battery in self.drone.telemetry.battery():
                if not self._running:
                    break
                self.state.battery_percent = battery.remaining_percent * 100
        except Exception:
            pass

        try:
            async for gps in self.drone.telemetry.gps_info():
                if not self._running:
                    break
                self.state.gps_fix_type = gps.fix_type
                self.state.satellites = gps.num_satellites
        except Exception:
            pass

        try:
            async for flight_mode in self.drone.telemetry.flight_mode():
                if not self._running:
                    break
                self.state.mode = str(flight_mode)
        except Exception:
            pass

        try:
            async for armed in self.drone.telemetry.armed():
                if not self._running:
                    break
                self.state.armed = armed
        except Exception:
            pass

        try:
            async for in_air in self.drone.telemetry.in_air():
                if not self._running:
                    break
                self.state.in_air = in_air
        except Exception:
            pass

    def add_state_callback(self, callback: Callable[[DroneState], None]):
        self._state_callbacks.append(callback)

    def _notify_state_change(self):
        for cb in self._state_callbacks:
            try:
                cb(self.state)
            except Exception:
                pass

    # --- 고수준 액션 ---
    async def arm(self) -> bool:
        try:
            await self.drone.action.arm()
            return True
        except ActionError as e:
            print(f"Arm failed: {e}")
            return False

    async def disarm(self) -> bool:
        try:
            await self.drone.action.disarm()
            return True
        except ActionError as e:
            print(f"Disarm failed: {e}")
            return False

    async def takeoff(self) -> bool:
        try:
            await self.drone.action.takeoff()
            return True
        except ActionError as e:
            print(f"Takeoff failed: {e}")
            return False

    async def land(self) -> bool:
        try:
            await self.drone.action.land()
            return True
        except ActionError as e:
            print(f"Land failed: {e}")
            return False

    async def return_to_launch(self) -> bool:
        try:
            await self.drone.action.return_to_launch()
            return True
        except ActionError as e:
            print(f"RTL failed: {e}")
            return False

    # --- 미션 ---
    async def upload_mission(self, mission_items: list[MissionItem]) -> bool:
        try:
            mission_plan = MissionPlan(mission_items)
            await self.drone.mission.upload_mission(mission_plan)
            return True
        except Exception as e:
            print(f"Mission upload failed: {e}")
            return False

    async def start_mission(self) -> bool:
        try:
            await self.drone.mission.start_mission()
            return True
        except Exception as e:
            print(f"Mission start failed: {e}")
            return False

    # --- 오프보드 ---
    async def set_offboard_velocity(
        self, vx: float, vy: float, vz: float, yaw_rate: float
    ):
        """Body 프레임 속도 명령"""
        try:
            await self.drone.offboard.set_velocity_body(
                VelocityBodyYawspeed(vx, vy, vz, yaw_rate)
            )
        except OffboardError as e:
            print(f"Offboard velocity failed: {e}")

    async def start_offboard(self) -> bool:
        try:
            await self.drone.offboard.start()
            return True
        except OffboardError as e:
            print(f"Offboard start failed: {e}")
            return False

    async def stop_offboard(self) -> bool:
        try:
            await self.drone.offboard.stop()
            return True
        except OffboardError as e:
            print(f"Offboard stop failed: {e}")
            return False

    async def disconnect(self):
        self._running = False
        if self.drone:
            # MAVSDK는 별도 disconnect 없음
            pass


class MAVROS2Bridge(Node):
    """MAVROS2 브릿지 - ROS2 토픽/서비스 통신용"""

    def __init__(self, namespace: str = "/mavros"):
        super().__init__("mavros2_bridge")
        self.namespace = namespace
        self.state = DroneState()
        self._state_callbacks: list[Callable[[DroneState], None]] = []
        self._connected = False

        # QoS 설정
        from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # 구독자
        self.state_sub = self.create_subscription(
            State, f"{namespace}/state", self._state_cb, qos
        )
        self.pose_sub = self.create_subscription(
            PoseStamped, f"{namespace}/local_position/pose", self._pose_cb, qos
        )
        self.gps_sub = self.create_subscription(
            NavSatFix, f"{namespace}/global_position/global", self._gps_cb, qos
        )
        self.battery_sub = self.create_subscription(
            BatteryState, f"{namespace}/battery", self._battery_cb, qos
        )
        self.velocity_sub = self.create_subscription(
            TwistStamped,
            f"{namespace}/local_position/velocity_local",
            self._velocity_cb,
            qos,
        )

        # 서비스 클라이언트
        self.arm_client = self.create_client(CommandBoolSrv, f"{namespace}/cmd/arming")
        self.mode_client = self.create_client(SetModeSrv, f"{namespace}/set_mode")

        # 퍼블리셔 (명령용)
        self.setpoint_pub = self.create_publisher(
            PoseStamped, f"{namespace}/setpoint_position/local", qos
        )
        self.velocity_pub = self.create_publisher(
            TwistStamped, f"{namespace}/setpoint_velocity/cmd_vel", qos
        )

        # 커스텀 메시지 퍼블리셔 (음성 제어용)
        if CUSTOM_MSGS_AVAILABLE:
            self.voice_cmd_pub = self.create_publisher(
                bytes, f"{namespace}/voice_command", 10  # raw MAVLink bytes
            )

        self.get_logger().info(f"MAVROS2 Bridge initialized on {namespace}")

    def _state_cb(self, msg: State):
        self.state.connected = msg.connected
        self.state.armed = msg.armed
        self.state.mode = msg.mode
        self._connected = msg.connected
        self.state.last_update = time.time()
        self._notify_state_change()

    def _pose_cb(self, msg: PoseStamped):
        self.state.latitude = 0  # local position
        self.state.longitude = 0
        self.state.altitude_rel = msg.pose.position.z
        # yaw 추출
        from tf_transformations import euler_from_quaternion

        q = msg.pose.orientation
        _, _, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])
        self.state.heading = yaw

    def _gps_cb(self, msg: NavSatFix):
        self.state.latitude = msg.latitude
        self.state.longitude = msg.longitude
        self.state.altitude_amsl = msg.altitude
        self.state.gps_fix_type = msg.status.status

    def _battery_cb(self, msg: BatteryState):
        if msg.percentage > 0:
            self.state.battery_percent = msg.percentage * 100

    def _velocity_cb(self, msg: TwistStamped):
        self.state.velocity_ned = (
            msg.twist.linear.x,
            msg.twist.linear.y,
            msg.twist.linear.z,
        )

    def add_state_callback(self, callback: Callable[[DroneState], None]):
        self._state_callbacks.append(callback)

    def _notify_state_change(self):
        for cb in self._state_callbacks:
            try:
                cb(self.state)
            except Exception:
                pass

    # --- 서비스 호출 ---
    async def arm(self, arm: bool = True) -> bool:
        if not self.arm_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("Arming service not available")
            return False

        req = CommandBoolSrv.Request()
        req.value = arm
        future = self.arm_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() and future.result().success:
            return True
        return False

    async def set_mode(self, mode: str) -> bool:
        if not self.mode_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("Set mode service not available")
            return False

        req = SetModeSrv.Request()
        req.custom_mode = mode
        future = self.mode_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() and future.result().mode_sent:
            return True
        return False

    # --- 퍼블리시 ---
    def publish_position_setpoint(self, x: float, y: float, z: float, yaw: float = 0.0):
        msg = PoseStamped()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = z
        # yaw를 quaternion으로 변환
        from tf_transformations import quaternion_from_euler

        q = quaternion_from_euler(0, 0, yaw)
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]
        self.setpoint_pub.publish(msg)

    def publish_velocity_setpoint(
        self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0
    ):
        msg = TwistStamped()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = vx
        msg.twist.linear.y = vy
        msg.twist.linear.z = vz
        msg.twist.angular.z = yaw_rate
        self.velocity_pub.publish(msg)

    def send_voice_command(
        self,
        command_text: str,
        parsed_action: str,
        params: list[float],
        confidence: float,
        command_id: int,
    ):
        """음성 명령 MAVLink 메시지 전송"""
        if not CUSTOM_MSGS_AVAILABLE:
            return

        # MAVLink 메시지 생성
        msg = mavlink_custom.MAVLink_voice_command_message(
            timestamp_ms=int(time.time() * 1000),
            command_text=command_text.encode("utf-8") + b"\x00",
            parsed_action=parsed_action.encode("utf-8") + b"\x00",
            params=params + [0.0] * (10 - len(params)),
            param_count=min(len(params), 10),
            confidence=confidence,
            is_final=1,
            command_id=command_id,
        )

        # 직렬화
        mav = mavlink_custom.MAVLink("bridge")
        buf = msg.pack(mav)
        self.voice_cmd_pub.publish(bytes(buf))

    def shutdown(self):
        self.destroy_node()


class DualBridge:
    """MAVSDK + MAVROS2 통합 브릿지"""

    def __init__(
        self, mavsdk_address: str = "udp://:14540", mavros_namespace: str = "/mavros"
    ):
        self.mavsdk = MAVSDKBridge(mavsdk_address)
        self.mavros2 = None  # ROS2 컨텍스트에서 생성
        self.mavros_namespace = mavros_namespace
        self._unified_state = DroneState()
        self._state_callbacks: list[Callable[[DroneState], None]] = []
        self._ros_spin_thread: Optional[threading.Thread] = None
        self._ros_executor: Optional[MultiThreadedExecutor] = None

    def _init_ros2(self):
        """ROS2 초기화 (별도 스레드에서)"""
        if not MAVROS2_AVAILABLE:
            self.get_logger().warning("MAVROS2 not available, running MAVSDK only")
            return

        rclpy.init()
        self.mavros2 = MAVROS2Bridge(self.mavros_namespace)
        self.mavros2.add_state_callback(self._on_mavros2_state)
        self.mavsdk.add_state_callback(self._on_mavsdk_state)

        self._ros_executor = MultiThreadedExecutor()
        self._ros_executor.add_node(self.mavros2)

        self._ros_spin_thread = threading.Thread(target=self._ros_spin, daemon=True)
        self._ros_spin_thread.start()

    def _ros_spin(self):
        try:
            self._ros_executor.spin()
        except Exception as e:
            print(f"ROS2 spin error: {e}")

    def _on_mavsdk_state(self, state: DroneState):
        # MAVSDK 상태를 통합 상태로 병합 (merge_state 사용)
        self._unified_state = merge_state(state, self._unified_state)
        self._notify_state_change()

    def _on_mavros2_state(self, state: DroneState):
        # MAVROS2 상태를 통합 상태로 병합 (merge_state 사용)
        self._unified_state = merge_state(self._unified_state, state)
        self._notify_state_change()

    def add_state_callback(self, callback: Callable[[DroneState], None]):
        self._state_callbacks.append(callback)

    def _notify_state_change(self):
        for cb in self._state_callbacks:
            try:
                cb(self._unified_state)
            except Exception:
                pass

    @property
    def state(self) -> DroneState:
        return self._unified_state

    async def connect(self) -> bool:
        """양쪽 브릿지 연결"""
        # ROS2 초기화
        self._init_ros2()

        # MAVSDK 연결
        mavsdk_ok = await self.mavsdk.connect()

        # MAVROS2는 비동기 연결 대기
        await asyncio.sleep(2.0)

        return mavsdk_ok

    # --- 통합 API (MAVSDK 우선, 폴백: MAVROS2) ---
    async def arm(self) -> bool:
        if self.mavsdk.connected:
            return await self.mavsdk.arm()
        elif self.mavros2:
            return await self.mavros2.arm(True)
        return False

    async def disarm(self) -> bool:
        if self.mavsdk.connected:
            return await self.mavsdk.disarm()
        elif self.mavros2:
            return await self.mavros2.arm(False)
        return False

    async def takeoff(self) -> bool:
        if self.mavsdk.connected:
            return await self.mavsdk.takeoff()
        elif self.mavros2:
            return await self.mavros2.set_mode("AUTO.TAKEOFF")
        return False

    async def land(self) -> bool:
        if self.mavsdk.connected:
            return await self.mavsdk.land()
        elif self.mavros2:
            return await self.mavros2.set_mode("AUTO.LAND")
        return False

    async def return_to_launch(self) -> bool:
        if self.mavsdk.connected:
            return await self.mavsdk.return_to_launch()
        elif self.mavros2:
            return await self.mavros2.set_mode("AUTO.RTL")
        return False

    async def set_mode(self, mode: str) -> bool:
        if self.mavros2:
            return await self.mavros2.set_mode(mode)
        return False

    # --- 오프보드/미션 (MAVSDK 전용) ---
    async def start_offboard(self) -> bool:
        return await self.mavsdk.start_offboard()

    async def set_offboard_velocity(
        self, vx: float, vy: float, vz: float, yaw_rate: float
    ):
        await self.mavsdk.set_offboard_velocity(vx, vy, vz, yaw_rate)

    async def upload_mission(self, items: list) -> bool:
        return await self.mavsdk.upload_mission(items)

    # --- 음성 명령 전송 (MAVROS2 토픽) ---
    def send_voice_command(
        self,
        command_text: str,
        parsed_action: str,
        params: list[float],
        confidence: float,
        command_id: int,
    ):
        if self.mavros2:
            self.mavros2.send_voice_command(
                command_text, parsed_action, params, confidence, command_id
            )

    async def disconnect(self):
        await self.mavsdk.disconnect()
        if self.mavros2:
            self.mavros2.shutdown()
        if self._ros_executor:
            self._ros_executor.shutdown()
        if rclpy.ok():
            rclpy.shutdown()


# 사용 예시
async def main():
    bridge = DualBridge(mavsdk_address="udp://:14540", mavros_namespace="/mavros")

    def on_state(state: DroneState):
        print(
            f"State: connected={state.connected}, armed={state.armed}, "
            f"mode={state.mode}, battery={state.battery_percent:.1f}%"
        )

    bridge.add_state_callback(on_state)

    print("Connecting...")
    if await bridge.connect():
        print("Connected!")

        # 상태 모니터링
        for _ in range(30):
            await asyncio.sleep(1)

        # 음성 명령 테스트
        bridge.send_voice_command(
            command_text="이륙해줘",
            parsed_action="TAKEOFF",
            params=[],
            confidence=0.95,
            command_id=1,
        )
        print("Voice command sent")

        await asyncio.sleep(2)

    await bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
