import asyncio
import time
from core_arbitrator import HardwareSpec, UnifiedCommand
from core.log_aggregator import LogSample

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from geometry_msgs.msg import Twist, TwistStamped
    from nav2_msgs.action import NavigateToPose
    from mavros_msgs.msg import State as MavrosState

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    Node = object

try:
    from mavsdk import System as MavsdkSystem

    MAVSDK_AVAILABLE = True
except ImportError:
    MAVSDK_AVAILABLE = False
    MavsdkSystem = None


class DroneHybridBridgeNode(Node):
    """
    드론 하이브리드 브릿지:
    - 고수준 미션(ARM, TAKEOFF, LAND, RTL, HOLD): MAVSDK-Python 비동기 제어
    - 연속 속도 제어(MOVE_VEL) 및 상태 감시: MAVROS2 토픽 제어
    - 로그 스트리밍: MAVLink/ROS2 → LogAggregator (10Hz)
    """

    def __init__(
        self, spec: HardwareSpec, mavsdk_uri: str = "udp://:14540", log_aggregator=None
    ):
        self.spec = spec
        self.mavsdk_uri = mavsdk_uri
        self.log_aggregator = log_aggregator
        self.drone = MavsdkSystem() if MAVSDK_AVAILABLE else None
        self.is_connected = (
            not MAVSDK_AVAILABLE
        )  # Mock 모드일 때는 기본 연결 상태로 간주
        self.last_heartbeat_time = time.monotonic()

        if ROS2_AVAILABLE:
            super().__init__(
                f"{spec.device_id}_bridge_node", namespace=f"/{spec.device_id}"
            )
            qos_ctrl = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10,
            )
            self.vel_pub = self.create_publisher(
                TwistStamped,
                f"/{spec.device_id}/mavros/setpoint_velocity/cmd_vel",
                qos_ctrl,
            )
            self.state_sub = self.create_subscription(
                MavrosState,
                f"/{spec.device_id}/mavros/state",
                self._mavros_state_cb,
                10,
            )

    def _log_info(self, msg: str) -> None:
        if ROS2_AVAILABLE:
            self.get_logger().info(msg)
        else:
            print(f"[INFO] {msg}")

    def _log_warn(self, msg: str) -> None:
        if ROS2_AVAILABLE:
            self.get_logger().warn(msg)
        else:
            print(f"[WARN] {msg}")

    def _mavros_state_cb(self, msg) -> None:
        if msg.connected:
            self.last_heartbeat_time = time.monotonic()
            self.is_connected = True

    async def connect_mavsdk(self) -> None:
        if not MAVSDK_AVAILABLE or self.drone is None:
            self._log_warn(
                f"[{self.spec.device_id}] MAVSDK 미설치 환경 -> 가상 시뮬레이션 모드로 동작합니다."
            )
            self.is_connected = True
            return

        self._log_info(
            f"[{self.spec.device_id}] MAVSDK 연결 대기 중: {self.mavsdk_uri}"
        )
        await self.drone.connect(system_address=self.mavsdk_uri)
        async for state in self.drone.core.connection_state():
            if state.is_connected:
                self.is_connected = True
                self.last_heartbeat_time = time.monotonic()
                self._log_info(f"[{self.spec.device_id}] MAVSDK 연결 완료!")
                break

    def publish_velocity(
        self, vx: float, vy: float, vz: float, yaw_rate: float
    ) -> None:
        self.last_heartbeat_time = time.monotonic()
        if ROS2_AVAILABLE:
            msg = TwistStamped()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = "base_link"
            msg.twist.linear.x = float(vx)
            msg.twist.linear.y = float(vy)
            msg.twist.linear.z = float(vz)
            msg.twist.angular.z = float(yaw_rate)
            self.vel_pub.publish(msg)

    async def execute_command(self, cmd: UnifiedCommand) -> None:
        self.last_heartbeat_time = time.monotonic()
        self._log_info(
            f"[{self.spec.device_id}] 드론 명령 실행: {cmd.action} (출처: {cmd.source})"
        )

        try:
            if cmd.action == "ESTOP":
                self.publish_velocity(0.0, 0.0, 0.0, 0.0)
                if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                    await self.drone.action.hold()
                    await self.drone.action.land()

            elif cmd.action == "ARM":
                if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                    await self.drone.action.arm()
                else:
                    await asyncio.sleep(0.3)

            elif cmd.action == "TAKEOFF":
                if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                    await self.drone.action.set_takeoff_altitude(cmd.z_m)
                    await self.drone.action.arm()
                    await self.drone.action.takeoff()
                else:
                    await asyncio.sleep(1.0)

            elif cmd.action == "LAND":
                if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                    await self.drone.action.land()
                else:
                    await asyncio.sleep(1.0)

            elif cmd.action == "HOLD":
                self.publish_velocity(0.0, 0.0, 0.0, 0.0)
                if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                    await self.drone.action.hold()

            elif cmd.action == "RTL":
                if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                    await self.drone.action.return_to_launch()
                else:
                    await asyncio.sleep(1.0)

            elif cmd.action == "MOVE_VEL":
                for _ in range(100):  # 20Hz 주기로 5초간 속도 유지
                    self.publish_velocity(
                        cmd.vx_mps, cmd.vy_mps, cmd.vz_mps, cmd.yaw_rate_radps
                    )
                    await asyncio.sleep(0.05)
                self.publish_velocity(0.0, 0.0, 0.0, 0.0)

            elif cmd.action == "SET_MODE":
                mode = cmd.params.get("mode", "CRUISE")
                self._log_info(f"[{self.spec.device_id}] 모드 변경: {mode}")
                # 모드 변경 로직 (실제로는 MAVLink로 전송)
                await asyncio.sleep(0.1)

            elif cmd.action == "DIVE_ATTACK":
                target_alt = cmd.params.get("target_alt", 100)
                angle = cmd.params.get("angle", 70)
                self._log_info(
                    f"[{self.spec.device_id}] 다이브 어택 시작: 목표 고도 {target_alt}m, 각도 {angle}도"
                )
                # 다이브 궤적 생성 및 실행 (trajectory_engine 필요)
                if hasattr(self, "trajectory_engine") and self.trajectory_engine:
                    start_pos = (0, 0, 500)  # 실제로는 현재 위치 사용
                    traj = await self.trajectory_engine.generate_dive_trajectory(
                        start_pos, target_alt, angle, self.spec.max_dive_speed_mps
                    )
                    # 궤적 따라 비행 (단순화)
                    for wp in traj.waypoints[:5]:  # 처음 몇 웨이포인트만
                        self.publish_velocity(50.0, 0.0, -30.0, 0.0)
                        await asyncio.sleep(0.1)
                await asyncio.sleep(0.5)

            elif cmd.action == "DECEPTION_START":
                pattern = cmd.params.get("pattern", "SINE_DIVE")
                duration = cmd.params.get("duration", 30.0)
                self._log_info(
                    f"[{self.spec.device_id}] 기만 모드 시작: {pattern}, 지속시간 {duration}초"
                )
                if hasattr(self, "deception_engine") and self.deception_engine:
                    from core.deception_engine import DeceptionPattern

                    pattern_enum = DeceptionPattern(pattern)
                    await self.deception_engine.start_deception(
                        pattern_enum, duration=duration
                    )

            elif cmd.action == "DECEPTION_STOP":
                self._log_info(f"[{self.spec.device_id}] 기만 모드 중지")
                if hasattr(self, "deception_engine") and self.deception_engine:
                    await self.deception_engine.stop_deception()

            elif cmd.action == "MOVE_VEL":
                for _ in range(100):  # 20Hz 주기로 5초간 속도 유지
                    self.publish_velocity(
                        cmd.vx_mps, cmd.vy_mps, cmd.vz_mps, cmd.yaw_rate_radps
                    )
                    await asyncio.sleep(0.05)
                self.publish_velocity(0.0, 0.0, 0.0, 0.0)

        except asyncio.CancelledError:
            self._log_warn(
                f"[{self.spec.device_id}] 드론 작업 선점 취소됨 -> 즉시 정지(Zero-Vel) 전환"
            )
            self.publish_velocity(0.0, 0.0, 0.0, 0.0)
            if MAVSDK_AVAILABLE and self.drone and self.is_connected:
                await self.drone.action.hold()
            raise

    # === 로그 스트리밍 파이프라인 (T-19) ===
    async def start_log_streaming(self):
        """텔레메트리 → 로그 어그리게이터 스트리밍 시작 (10Hz)"""
        if self.log_aggregator is None:
            self._log_warn(
                f"[{self.spec.device_id}] LogAggregator 없음 - 로그 스트리밍 비활성화"
            )
            return

        self._log_task = asyncio.create_task(self._log_stream_loop())
        self._log_info(f"[{self.spec.device_id}] 로그 스트리밍 시작 (10Hz)")

    async def _log_stream_loop(self):
        """텔레메트리 → LogAggregator 스트리밍 루프 (10Hz)"""
        while True:
            try:
                # MAVROS 상태
                if hasattr(self, "last_mavros_state") and self.last_mavros_state:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="FLIGHT_MODE",
                            data={
                                "mode": self.last_mavros_state.mode,
                                "armed": self.last_mavros_state.armed,
                                "connected": self.last_mavros_state.connected,
                            },
                        )
                    )

                # 배터리
                if hasattr(self, "last_battery") and self.last_battery:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="BATTERY",
                            data={
                                "voltage": self.last_battery.voltage,
                                "current": self.last_battery.current,
                                "remaining": self.last_battery.remaining_percent * 100,
                            },
                        )
                    )

                # 자세/IMU
                if hasattr(self, "last_attitude") and self.last_attitude:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="ATTITUDE",
                            data={
                                "roll": self.last_attitude.roll,
                                "pitch": self.last_attitude.pitch,
                                "yaw": self.last_attitude.yaw,
                            },
                        )
                    )

                # 모터/ESC
                if hasattr(self, "last_motor_status") and self.last_motor_status:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="MOTOR",
                            data={
                                "temps": self.last_motor_status.temperatures,
                                "rpms": self.last_motor_status.rpms,
                            },
                        )
                    )

                # GPS
                if hasattr(self, "last_gps") and self.last_gps:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="GPS",
                            data={
                                "fix_type": self.last_gps.fix_type,
                                "satellites": self.last_gps.satellites_visible,
                                "hdop": (
                                    self.last_gps.eph / 100.0
                                    if self.last_gps.eph
                                    else 99.0
                                ),
                            },
                        )
                    )

            except Exception as e:
                self._log_warn(f"[{self.spec.device_id}] 로그 스트리밍 에러: {e}")

            await asyncio.sleep(0.1)  # 10Hz

    def stop_log_streaming(self):
        """로그 스트리밍 중지"""
        if hasattr(self, "_log_task") and self._log_task:
            self._log_task.cancel()
            self._log_info(f"[{self.spec.device_id}] 로그 스트리밍 중지")


class RobotRos2BridgeNode(Node):
    """
    지상 로봇 ROS2 브릿지:
    - 속도 제어: /<robot_id>/cmd_vel (geometry_msgs/Twist)
    - 자율 주행: /<robot_id>/navigate_to_pose (nav2_msgs/action/NavigateToPose)
    - 로그 스트리밍: 로봇 상태 → LogAggregator
    """

    def __init__(self, spec: HardwareSpec, log_aggregator=None):
        self.spec = spec
        self.log_aggregator = log_aggregator
        self._current_goal_handle = None
        self._log_task = None

        if ROS2_AVAILABLE:
            super().__init__(
                f"{spec.device_id}_bridge_node", namespace=f"/{spec.device_id}"
            )
            self.cmd_vel_pub = self.create_publisher(
                Twist, f"/{spec.device_id}/cmd_vel", 10
            )
            self.nav_client = ActionClient(
                self, NavigateToPose, f"/{spec.device_id}/navigate_to_pose"
            )

    def _log_info(self, msg: str) -> None:
        if ROS2_AVAILABLE:
            self.get_logger().info(msg)
        else:
            print(f"[INFO] {msg}")

    def _log_warn(self, msg: str) -> None:
        if ROS2_AVAILABLE:
            self.get_logger().warn(msg)
        else:
            print(f"[WARN] {msg}")

    def stop_immediately(self) -> None:
        if ROS2_AVAILABLE:
            stop_msg = Twist()
            self.cmd_vel_pub.publish(stop_msg)
        if self._current_goal_handle is not None:
            self._log_warn(
                f"[{self.spec.device_id}] 진행 중인 Nav2 자율주행 목표 취소 요청"
            )
            self._current_goal_handle.cancel_goal_async()
            self._current_goal_handle = None

    async def execute_command(self, cmd: UnifiedCommand) -> None:
        self._log_info(
            f"[{self.spec.device_id}] 로봇 명령 실행: {cmd.action} (출처: {cmd.source})"
        )

        try:
            if cmd.action in ("ESTOP", "HOLD"):
                self.stop_immediately()

            elif cmd.action == "MOVE_VEL":
                for _ in range(60):  # 20Hz로 3초간 주행 유지
                    if ROS2_AVAILABLE:
                        msg = Twist()
                        msg.linear.x = float(cmd.vx_mps)
                        msg.linear.y = float(cmd.vy_mps)
                        msg.angular.z = float(cmd.yaw_rate_radps)
                        self.cmd_vel_pub.publish(msg)
                    await asyncio.sleep(0.05)
                self.stop_immediately()

            elif cmd.action == "NAV_TO_POSE":
                if not ROS2_AVAILABLE:
                    await asyncio.sleep(2.0)
                    return

                if not self.nav_client.wait_for_server(timeout_sec=2.0):
                    raise RuntimeError(
                        f"[{self.spec.device_id}] Nav2 액션 서버가 응답하지 않습니다."
                    )

                goal_msg = NavigateToPose.Goal()
                goal_msg.pose.header.frame_id = "map"
                goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
                goal_msg.pose.pose.position.x = float(cmd.x_m)
                goal_msg.pose.pose.position.y = float(cmd.y_m)
                goal_msg.pose.pose.orientation.w = 1.0

                send_goal_future = self.nav_client.send_goal_async(goal_msg)
                while not send_goal_future.done():
                    await asyncio.sleep(0.05)

                goal_handle = send_goal_future.result()
                if not goal_handle.accepted:
                    raise RuntimeError(
                        f"[{self.spec.device_id}] Nav2 목표 지점이 거부되었습니다."
                    )

                self._current_goal_handle = goal_handle
                result_future = goal_handle.get_result_async()
                while not result_future.done():
                    await asyncio.sleep(0.1)

                self._current_goal_handle = None
                self._log_info(f"[{self.spec.device_id}] Nav2 목적지 도착 완료")

        except asyncio.CancelledError:
            self._log_warn(
                f"[{self.spec.device_id}] 로봇 작업 선점 취소됨 -> 비상 정지 수행"
            )
            self.stop_immediately()
            raise

    # === 로그 스트리밍 파이프라인 (T-19) ===
    async def start_log_streaming(self):
        """로봇 상태 → 로그 어그리게이터 스트리밍 시작"""
        if self.log_aggregator is None:
            return

        self._log_task = asyncio.create_task(self._log_stream_loop())

    async def _log_stream_loop(self):
        """로봇 상태 → LogAggregator 스트리밍 (10Hz)"""
        while True:
            try:
                # 배터리 (예시 - 실제로는 토픽 구독 필요)
                if hasattr(self, "last_battery") and self.last_battery:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="BATTERY",
                            data={
                                "voltage": self.last_battery.voltage,
                                "current": self.last_battery.current,
                                "remaining": self.last_battery.remaining_percent * 100,
                            },
                        )
                    )

                # 자세 (IMU)
                if hasattr(self, "last_attitude") and self.last_attitude:
                    await self.log_aggregator.ingest(
                        LogSample(
                            timestamp=time.time(),
                            device_id=self.spec.device_id,
                            log_type="ATTITUDE",
                            data={
                                "roll": self.last_attitude.roll,
                                "pitch": self.last_attitude.pitch,
                                "yaw": self.last_attitude.yaw,
                            },
                        )
                    )

            except Exception as e:
                self._log_warn(f"[{self.spec.device_id}] 로그 스트리밍 에러: {e}")

            await asyncio.sleep(0.1)

    def stop_log_streaming(self):
        if hasattr(self, "_log_task") and self._log_task:
            self._log_task.cancel()
