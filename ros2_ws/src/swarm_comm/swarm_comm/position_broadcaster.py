#!/usr/bin/env python3
"""
Position Broadcaster for Q250-V3-Opti Swarm

Broadcasts real-time position, velocity, attitude, and status to swarm via Fast-DDS.
Integrates with Silvus link quality monitoring for adaptive broadcast rates.
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile,
    ReliabilityPolicy,
    HistoryPolicy,
    DurabilityPolicy,
    QoSDuration,
)
from rclpy.parameter import Parameter
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String, Header
from geometry_msgs.msg import (
    PoseStamped,
    PoseWithCovarianceStamped,
    TwistStamped,
    Vector3,
)
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState
from mavros_msgs.msg import State as MavrosState
from px4_msgs.msg import (
    VehicleStatus,
    VehicleLocalPosition,
    VehicleGlobalPosition,
    VehicleAttitude,
    BatteryStatus,
)
from builtin_interfaces.msg import Time as BuiltinTime

from .swarm_messages import SwarmPosition, SwarmStatus, DroneState


class PositionBroadcaster(Node):
    """Broadcasts drone position and state to swarm via Fast-DDS"""

    def __init__(self):
        super().__init__("position_broadcaster")

        # Declare parameters
        self.declare_parameters(
            namespace="",
            parameters=[
                ("drone_id", "drone_01"),
                ("swarm_id", "swarm_alpha"),
                ("broadcast_rate", 20.0),
                ("position_topic", "/swarm/position"),
                ("status_topic", "/swarm/status"),
                ("use_reliable_qos", False),
                ("history_depth", 1),
                ("include_velocity", True),
                ("include_attitude", True),
                ("include_battery", True),
                ("include_mode", True),
                ("include_vio_quality", True),
                ("silvus_monitor_topic", "/silvus/link_quality"),
                ("silvus_link_loss_threshold", 0.1),
                ("silvus_rtt_threshold", 50.0),
                ("link_loss_reduce_rate", 0.5),
                ("vio_quality_topic", "/vio/quality"),
                ("vio_drift_threshold", 0.5),
                ("vio_loss_timeout", 2.0),
                ("max_position_age", 1.0),
                ("position_timeout_action", "hover"),
                ("log_broadcast_stats", True),
                ("log_stats_interval", 10.0),
            ],
        )

        # Load config
        self.config = {
            param: self.get_parameter(param).value
            for param in [
                "drone_id",
                "swarm_id",
                "broadcast_rate",
                "position_topic",
                "status_topic",
                "use_reliable_qos",
                "history_depth",
                "include_velocity",
                "include_attitude",
                "include_battery",
                "include_mode",
                "include_vio_quality",
                "silvus_monitor_topic",
                "silvus_link_loss_threshold",
                "silvus_rtt_threshold",
                "link_loss_reduce_rate",
                "vio_quality_topic",
                "vio_drift_threshold",
                "vio_loss_timeout",
                "max_position_age",
                "position_timeout_action",
                "log_broadcast_stats",
                "log_stats_interval",
            ]
        }

        # State
        self.drone_id = self.config["drone_id"]
        self.swarm_id = self.config["swarm_id"]

        # Current state
        self.current_position = None  # dict with x, y, z (ENU)
        self.current_velocity = None  # dict with vx, vy, vz
        self.current_attitude = None  # quaternion
        self.current_battery = 100.0
        self.current_mode = "UNKNOWN"
        self.silvus_quality = {"rssi": -50, "loss": 0.0, "rtt": 10.0}
        self.vio_quality = {"drift": 0.0, "healthy": True, "last_update": time.time()}

        # Broadcast rate adaptation
        self.current_broadcast_rate = self.config["broadcast_rate"]
        self.base_broadcast_rate = self.config["broadcast_rate"]
        self.link_degraded = False

        # Stats
        self.broadcast_count = 0
        self.last_stats_time = time.time()

        # QoS Profiles
        if self.config["use_reliable_qos"]:
            qos = QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=self.config["history_depth"],
                durability=DurabilityPolicy.VOLATILE,
            )
        else:
            qos = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=self.config["history_depth"],
                durability=DurabilityPolicy.VOLATILE,
            )

        # Subscribers
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            "/mavros/local_position/pose",
            self.pose_callback,
            10,
        )
        self.velocity_sub = self.create_subscription(
            TwistStamped, "/mavros/local_position/velocity", self.velocity_callback, 10
        )
        self.attitude_sub = self.create_subscription(
            PoseStamped, "/mavros/attitude", self.attitude_callback, 10
        )
        self.battery_sub = self.create_subscription(
            BatteryState, "/mavros/battery", self.battery_callback, 10
        )
        self.state_sub = self.create_subscription(
            State, "/mavros/state", self.state_callback, 10
        )

        # Silvus link quality
        self.silvus_sub = self.create_subscription(
            String, self.config["silvus_monitor_topic"], self.silvus_callback, 10
        )

        # VIO quality
        self.vio_sub = self.create_subscription(
            String, self.config["vio_quality_topic"], self.vio_callback, 10
        )

        # Publishers
        self.position_pub = self.create_publisher(
            String, self.config["position_topic"], 10
        )
        self.status_pub = self.create_publisher(String, self.config["status_topic"], 10)

        # Timer for broadcasting
        self.broadcast_timer = self.create_timer(
            1.0 / self.current_broadcast_rate, self.broadcast_callback
        )

        # Stats timer
        self.stats_timer = self.create_timer(
            self.config.get("log_stats_interval", 10.0), self.stats_callback
        )

        self.get_logger().info(
            f"Position Broadcaster initialized: {self.drone_id} in {self.swarm_id} "
            f"at {self.current_broadcast_rate} Hz"
        )

    def pose_callback(self, msg: PoseWithCovarianceStamped):
        self.current_position = {
            "x": msg.pose.pose.position.x,
            "y": msg.pose.pose.position.y,
            "z": msg.pose.pose.position.z,
            "timestamp": time.time(),
        }

    def velocity_callback(self, msg: TwistStamped):
        if self.config["include_velocity"]:
            self.current_velocity = {
                "vx": msg.twist.linear.x,
                "vy": msg.twist.linear.y,
                "vz": msg.twist.linear.z,
                "timestamp": time.time(),
            }

    def attitude_callback(self, msg: PoseStamped):
        if self.config["include_attitude"]:
            self.current_attitude = {
                "qx": msg.pose.orientation.x,
                "qy": msg.pose.orientation.y,
                "qz": msg.pose.orientation.z,
                "qw": msg.pose.orientation.w,
                "timestamp": time.time(),
            }

    def battery_callback(self, msg):
        if self.config["include_battery"]:
            if msg.capacity > 0:
                self.current_battery = (msg.charge / msg.capacity) * 100.0
            else:
                self.current_battery = (
                    msg.percentage * 100.0 if msg.percentage >= 0 else 100.0
                )

    def state_callback(self, msg):
        if self.config["include_mode"]:
            self.current_mode = msg.mode

    def silvus_callback(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.silvus_quality = {
                "rssi": data.get("rssi", -50),
                "loss": data.get("packet_loss", 0.0),
                "rtt": data.get("rtt", 10.0),
                "timestamp": time.time(),
            }

            # Check for link degradation
            loss = data.get("packet_loss", 0.0)
            rtt = data.get("rtt", 10.0)

            was_degraded = self.link_degraded
            self.link_degraded = (
                loss > self.get_parameter("silvus_link_loss_threshold").value
                or rtt > self.get_parameter("silvus_rtt_threshold").value
            )

            if self.link_degraded != was_degraded:
                if self.link_degraded:
                    self.get_logger().warn(
                        f"Silvus link degraded: loss={loss*100:.1f}%, RTT={rtt:.1f}ms"
                    )
                    # Reduce broadcast rate
                    self.current_broadcast_rate = (
                        self.base_broadcast_rate
                        * self.get_parameter("link_loss_reduce_rate").value
                    )
                else:
                    self.get_logger().info("Silvus link recovered")
                    self.current_broadcast_rate = self.base_broadcast_rate

                # Update timer
                self.broadcast_timer.cancel()
                self.broadcast_timer = self.create_timer(
                    1.0 / self.current_broadcast_rate, self.broadcast_callback
                )

        except Exception as e:
            self.get_logger().debug(f"Silvus callback error: {e}")

    def vio_callback(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.vio_quality = {
                "drift": data.get("drift_rate", 0.0),
                "healthy": data.get("healthy", True),
                "last_update": time.time(),
            }
        except Exception as e:
            self.get_logger().debug(f"VIO callback error: {e}")

    def broadcast_callback(self):
        """Broadcast position and status to swarm"""
        if self.current_position is None:
            return

        # Check position freshness
        age = time.time() - self.current_position["timestamp"]
        if age > self.get_parameter("max_position_age").value:
            self.get_logger().warn(f"Position data stale: {age:.1f}s old")
            # Could trigger position_timeout_action here
            return

        # Build position message
        position_msg = {
            "drone_id": self.drone_id,
            "swarm_id": self.swarm_id,
            "timestamp": time.time(),
            "position": {
                "x": self.current_position["x"],
                "y": self.current_position["y"],
                "z": self.current_position["z"],
            },
        }

        if self.config["include_velocity"] and self.current_velocity:
            position_msg["velocity"] = {
                "vx": self.current_velocity["vx"],
                "vy": self.current_velocity["vy"],
                "vz": self.current_velocity["vz"],
            }

        if self.config["include_attitude"] and self.current_attitude:
            position_msg["attitude"] = {
                "qx": self.current_attitude["qx"],
                "qy": self.current_attitude["qy"],
                "qz": self.current_attitude["qz"],
                "qw": self.current_attitude["qw"],
            }

        if self.config["include_battery"]:
            position_msg["battery"] = self.current_battery

        if self.config["include_mode"]:
            position_msg["mode"] = self.current_mode

        if self.config["include_vio_quality"]:
            position_msg["vio_quality"] = self.vio_quality

        # Add Silvus link quality
        position_msg["link_quality"] = self.silvus_quality

        # Publish
        msg = String()
        msg.data = json.dumps(position_msg)
        self.position_pub.publish(msg)

        self.broadcast_count += 1

    def stats_callback(self):
        """Log broadcast statistics"""
        if not self.get_parameter("log_broadcast_stats").value:
            return

        now = time.time()
        elapsed = now - self.last_stats_time
        rate = self.broadcast_count / elapsed if elapsed > 0 else 0

        self.get_logger().info(
            f"Swarm broadcast stats: {self.broadcast_count} msgs in {elapsed:.1f}s "
            f"({rate:.1f} Hz), link_degraded={self.link_degraded}, "
            f"current_rate={self.current_broadcast_rate:.1f} Hz"
        )

        self.broadcast_count = 0
        self.last_stats_time = now


def main(args=None):
    rclpy.init(args=args)
    node = PositionBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
