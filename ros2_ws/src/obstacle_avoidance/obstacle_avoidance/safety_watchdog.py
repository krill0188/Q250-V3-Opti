#!/usr/bin/env python3
"""
Safety Watchdog for Q250-V3-Opti

Monitors planner health and Silvus link quality, adjusts PX4 parameters
and triggers failsafe modes when anomalies detected.

Based on docs/12-obstacle-avoidance-pipeline.md Section 12.9
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.parameter import Parameter

from geometry_msgs.msg import Twist
from std_msgs.msg import Float32MultiArray
from mavros_msgs.srv import ParamSet
from mavros_msgs.msg import ParamValue


class SafetyWatchdog(Node):
    """Monitors system health and triggers safety actions."""

    def __init__(self):
        super().__init__("safety_watchdog")

        # Parameters
        self.declare_parameter("planner_topic", "/mavros/setpoint_velocity/cmd_vel")
        self.declare_parameter("silvus_topic", "/silvus/link_quality")
        self.declare_parameter("watchdog_timeout", 0.5)  # seconds
        self.declare_parameter("silvus_loss_threshold", 0.1)  # 10% packet loss
        self.declare_parameter("silvus_rtt_threshold", 50.0)  # ms
        self.declare_parameter("silvus_rssi_threshold", -85.0)  # dBm

        self.planner_topic = self.get_parameter("planner_topic").value
        self.silvus_topic = self.get_parameter("silvus_topic").value
        self.watchdog_timeout = self.get_parameter("watchdog_timeout").value
        self.loss_threshold = self.get_parameter("silvus_loss_threshold").value
        self.rtt_threshold = self.get_parameter("silvus_rtt_threshold").value
        self.rssi_threshold = self.get_parameter("silvus_rssi_threshold").value

        # State
        self.last_planner_time = None
        self.planner_active = False
        self.silvus_healthy = True
        self.current_max_vel = 2.0  # Nominal
        self.current_inflation = 0.8  # Nominal

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
        )

        # Subscriber: Planner output (Twist)
        self.planner_sub = self.create_subscription(
            Twist, self.planner_topic, self.planner_callback, qos
        )

        # Subscriber: Silvus link quality
        self.silvus_sub = self.create_subscription(
            Float32MultiArray, self.silvus_topic, self.silvus_callback, qos
        )

        # Client: MAVROS param set
        self.param_client = self.create_client(ParamSet, "/mavros/param/set")

        # Timers
        self.watchdog_timer = self.create_timer(0.1, self.watchdog_check)  # 10Hz
        self.silvus_timer = self.create_timer(1.0, self.silvus_check)  # 1Hz

        self.get_logger().info(
            f"Safety Watchdog initialized:\n"
            f"  Planner topic: {self.planner_topic}\n"
            f"  Silvus topic: {self.silvus_topic}\n"
            f"  Watchdog timeout: {self.watchdog_timeout}s\n"
            f"  Silvus thresholds: loss>{self.loss_threshold*100:.0f}%, "
            f"RTT>{self.rtt_threshold}ms, RSSI<{self.rssi_threshold}dBm"
        )

    def planner_callback(self, msg: Twist):
        """Track planner heartbeat."""
        self.last_planner_time = self.get_clock().now()
        self.planner_active = True

    def silvus_callback(self, msg: Float32MultiArray):
        """Process Silvus link quality: [rssi_dbm, snr_db, packet_loss_pct, rtt_ms, hop_count]"""
        if len(msg.data) >= 4:
            rssi = msg.data[0]
            snr = msg.data[1]
            loss = msg.data[2]
            rtt = msg.data[3]

            # Evaluate health
            was_healthy = self.silvus_healthy
            self.silvus_healthy = (
                loss <= self.loss_threshold
                and rtt <= self.rtt_threshold
                and rssi >= self.rssi_threshold
            )

            # Log state changes
            if was_healthy != self.silvus_healthy:
                if self.silvus_healthy:
                    self.get_logger().info(
                        f"Silvus link RECOVERED: RSSI={rssi:.1f}dBm, "
                        f"Loss={loss*100:.1f}%, RTT={rtt:.1f}ms"
                    )
                    self.recover_nominal_params()
                else:
                    self.get_logger().warn(
                        f"Silvus link DEGRADED: RSSI={rssi:.1f}dBm, "
                        f"Loss={loss*100:.1f}%, RTT={rtt:.1f}ms"
                    )
                    self.degrade_safety_params(loss, rtt)

    def watchdog_check(self):
        """Check planner heartbeat and trigger failsafe if needed."""
        if self.last_planner_time is None:
            return

        now = self.get_clock().now()
        elapsed = (now - self.last_planner_time).nanoseconds / 1e9

        if elapsed > self.watchdog_timeout and self.planner_active:
            self.get_logger().error(
                f"PLANNER WATCHDOG TRIGGERED: No cmd_vel for {elapsed:.2f}s "
                f"(timeout={self.watchdog_timeout}s)"
            )
            self.trigger_failsafe()
            self.planner_active = False  # Prevent repeated triggers

    def silvus_check(self):
        """Periodic Silvus health check (in case topic stops publishing)."""
        # Could add staleness check here
        pass

    def degrade_safety_params(self, loss: float, rtt: float):
        """Reduce speed and increase safety margins when link degrades."""
        # Scale based on severity
        severity = max(loss / self.loss_threshold, rtt / self.rtt_threshold)
        severity = min(max(severity, 1.0), 3.0)  # Clamp 1.0-3.0

        new_max_vel = 2.0 / severity
        new_inflation = 0.8 * severity

        self.current_max_vel = max(new_max_vel, 0.3)  # Floor at 0.3 m/s
        self.current_inflation = min(new_inflation, 3.0)  # Cap at 3.0m

        self.get_logger().warn(
            f"DEGRADING safety params: max_vel={self.current_max_vel:.2f}m/s, "
            f"inflation={self.current_inflation:.2f}m (severity={severity:.1f}x)"
        )

        # Note: Actual parameter updates would require:
        # 1. TEB planner dynamic reconfigure (not implemented here)
        # 2. PX4 COM_OF_LOSS_T adjustment via MAVROS
        self.update_px4_param("COM_OF_LOSS_T", max(0.5 / severity, 0.2))

    def recover_nominal_params(self):
        """Restore nominal parameters when link recovers."""
        self.current_max_vel = 2.0
        self.current_inflation = 0.8

        self.get_logger().info(
            f"RECOVERED nominal params: max_vel={self.current_max_vel:.2f}m/s, "
            f"inflation={self.current_inflation:.2f}m"
        )

        self.update_px4_param("COM_OF_LOSS_T", 1.0)

    def trigger_failsafe(self):
        """Trigger emergency failsafe: hover/land via PX4."""
        self.get_logger().error("TRIGGERING FAILSAFE: Planner watchdog timeout!")

        # Option 1: Set PX4 to Position mode (hover)
        # Option 2: Set PX4 to Land mode
        # Option 3: Publish zero velocity setpoint
        # For now, log the event - actual implementation needs MAVROS mode service

        self.update_px4_param("COM_OBL_RC_ACT", 2)  # Position mode on RC loss
        self.update_px4_param("COM_OF_LOSS_T", 0.5)  # Fast OFFBOARD exit

    def update_px4_param(self, param_name: str, value: float):
        """Update PX4 parameter via MAVROS."""
        if not self.param_client.service_is_ready():
            self.get_logger().debug(
                f"MAVROS param service not ready, skipping {param_name}"
            )
            return

        request = ParamSet.Request()
        request.param_id = param_name
        request.value = ParamValue()
        request.value.real = float(value)
        request.value.integer = 0

        future = self.param_client.call_async(request)
        future.add_done_callback(
            lambda f: self.get_logger().debug(
                f'Param {param_name}={value} set: {f.result().success if f.result() else "failed"}'
            )
        )


def main(args=None):
    rclpy.init(args=args)
    node = SafetyWatchdog()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
