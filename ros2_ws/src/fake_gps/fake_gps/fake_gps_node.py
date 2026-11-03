#!/usr/bin/env python3
"""
Fake GPS Node for Q250-V3-Opti

Converts VIO local pose (ENU frame) to MAVLink GPS_INPUT messages
for PX4 global position estimation (Mission/RTL/Geofence support).

Subscribes: geometry_msgs/PoseWithCovarianceStamped (VIO pose in ENU)
Publishes:  mavros_msgs/GPSINPUT (to MAVROS -> PX4)

Author: Hermes Agent
Based on: docs/13-fake-gps-implementation.md
"""

import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.time import Time

from geometry_msgs.msg import PoseWithCovarianceStamped
from mavros_msgs.msg import GPSINPUT
from std_msgs.msg import Header
from builtin_interfaces.msg import Time as BuiltinTime


class FakeGPSNode(Node):
    """Converts VIO pose to fake GPS for PX4 global position."""

    # GPS_INPUT ignore flags (MAVLink spec)
    IGNORE_FLAG_VEL = 1
    IGNORE_FLAG_YAW = 2
    IGNORE_FLAG_ALT = 4
    IGNORE_FLAG_HDOP = 8
    IGNORE_FLAG_VDOP = 16
    IGNORE_FLAG_SATS = 32

    def __init__(self):
        super().__init__("fake_gps_node")

        # Declare parameters with defaults
        self.declare_parameter("datum_lat", 37.5665)
        self.declare_parameter("datum_lon", 126.9780)
        self.declare_parameter("datum_alt", 28.0)
        self.declare_parameter("fix_type", 3)
        self.declare_parameter("satellites_visible", 10)
        self.declare_parameter("horiz_accuracy", 0.5)
        self.declare_parameter("vert_accuracy", 0.5)
        self.declare_parameter("vio_pose_topic", "/ov_msckf/pose")
        self.declare_parameter("gps_input_topic", "/mavros/gps_input/input")
        self.declare_parameter("input_frame", "enu")
        self.declare_parameter("ignore_velocity", True)
        self.declare_parameter("ignore_yaw", True)
        self.declare_parameter("max_rate_hz", 10.0)
        self.declare_parameter("debug_logging", False)

        # Get parameters
        self.datum_lat = self.get_parameter("datum_lat").value
        self.datum_lon = self.get_parameter("datum_lon").value
        self.datum_alt = self.get_parameter("datum_alt").value
        self.fix_type = self.get_parameter("fix_type").value
        self.satellites_visible = self.get_parameter("satellites_visible").value
        self.min_horiz_acc = self.get_parameter("horiz_accuracy").value
        self.min_vert_acc = self.get_parameter("vert_accuracy").value
        self.vio_pose_topic = self.get_parameter("vio_pose_topic").value
        self.gps_input_topic = self.get_parameter("gps_input_topic").value
        self.input_frame = self.get_parameter("input_frame").value.lower()
        self.ignore_velocity = self.get_parameter("ignore_velocity").value
        self.ignore_yaw = self.get_parameter("ignore_yaw").value
        self.max_rate_hz = self.get_parameter("max_rate_hz").value
        self.debug_logging = self.get_parameter("debug_logging").value

        # Earth radius for ENU->LLA conversion (WGS84 semi-major axis)
        self.R_EARTH = 6378137.0

        # Rate limiting
        self.min_interval = 1.0 / self.max_rate_hz if self.max_rate_hz > 0 else 0.0
        self.last_publish_time = 0.0

        # QoS for sensor data (best effort, keep last)
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
        )

        # Subscriber: VIO pose (ENU)
        self.vio_sub = self.create_subscription(
            PoseWithCovarianceStamped, self.vio_pose_topic, self.vio_pose_callback, qos
        )

        # Publisher: MAVROS GPS_INPUT
        self.gps_pub = self.create_publisher(GPSINPUT, self.gps_input_topic, qos)

        # Stats
        self.msg_count = 0
        self.last_log_time = self.get_clock().now()

        self.get_logger().info(
            f"Fake GPS Node initialized:\n"
            f"  Datum: lat={self.datum_lat:.6f}, lon={self.datum_lon:.6f}, alt={self.datum_alt:.1f}m\n"
            f"  Fix type: {self.fix_type}, Sats: {self.satellites_visible}\n"
            f"  Input: {self.vio_pose_topic} ({self.input_frame.upper()})\n"
            f"  Output: {self.gps_input_topic}\n"
            f"  Ignore vel: {self.ignore_velocity}, yaw: {self.ignore_yaw}\n"
            f"  Max rate: {self.max_rate_hz} Hz"
        )

    def vio_pose_callback(self, msg: PoseWithCovarianceStamped):
        """Process VIO pose and publish GPS_INPUT."""
        now = self.get_clock().now()
        now_sec = now.nanoseconds / 1e9

        # Rate limiting
        if self.min_interval > 0 and (now_sec - self.last_publish_time) < self.min_interval:
            return
        self.last_publish_time = now_sec

        # Extract position (ENU frame from VIO)
        x_enu = msg.pose.pose.position.x
        y_enu = msg.pose.pose.position.y
        z_enu = msg.pose.pose.position.z

        # Convert ENU -> LLA (WGS84)
        lat, lon, alt = self.enu_to_lla(x_enu, y_enu, z_enu)

        # Extract covariance for accuracy estimation
        cov = msg.pose.covariance  # 6x6 row-major: [x, y, z, rot_x, rot_y, rot_z]
        # Position covariance diagonal
        var_x = cov[0] if cov[0] > 0 else 0.0
        var_y = cov[7] if cov[7] > 0 else 0.0
        var_z = cov[14] if cov[14] > 0 else 0.0

        horiz_acc = max(math.sqrt(max(var_x, var_y)), self.min_horiz_acc)
        vert_acc = max(math.sqrt(var_z), self.min_vert_acc)

        # Build ignore flags
        ignore_flags = 0
        if self.ignore_velocity:
            ignore_flags |= self.IGNORE_FLAG_VEL
        if self.ignore_yaw:
            ignore_flags |= self.IGNORE_FLAG_YAW
        # Don't ignore altitude - we have baro/LiDAR for that

        # Create GPSINPUT message
        gps_msg = GPSINPUT()
        gps_msg.header = Header()
        gps_msg.header.stamp = now.to_msg()
        gps_msg.header.frame_id = "gps"

        # Time in microseconds (PX4 expects UNIX time in us)
        gps_msg.time_usec = int(now.nanoseconds / 1000)

        gps_msg.gps_id = 0  # Primary GPS
        gps_msg.ignore_flags = ignore_flags
        gps_msg.fix_type = self.fix_type
        gps_msg.lat = int(lat * 1e7)  # deg * 1e7
        gps_msg.lon = int(lon * 1e7)  # deg * 1e7
        gps_msg.alt = int(alt * 1000)  # mm (MSL)
        gps_msg.hdop = 1.0
        gps_msg.vdop = 1.0
        gps_msg.satellites_visible = self.satellites_visible

        # Velocity (set to 0 if ignored)
        if not self.ignore_velocity:
            # Would need velocity from VIO - not implemented yet
            gps_msg.vn = 0.0
            gps_msg.ve = 0.0
            gps_msg.vd = 0.0
        else:
            gps_msg.vn = 0.0
            gps_msg.ve = 0.0
            gps_msg.vd = 0.0

        gps_msg.speed_accuracy = 0.1
        gps_msg.horiz_accuracy = horiz_acc
        gps_msg.vert_accuracy = vert_acc

        # Yaw (set to 0 if ignored)
        if not self.ignore_yaw:
            # Would need yaw from VIO - not implemented yet
            gps_msg.yaw = 0
            gps_msg.yaw_accuracy = 0.0
        else:
            gps_msg.yaw = 0
            gps_msg.yaw_accuracy = 0.0

        # Publish
        self.gps_pub.publish(gps_msg)
        self.msg_count += 1

        # Periodic logging
        if self.debug_logging or (now.nanoseconds - self.last_log_time.nanoseconds) > 5e9:
            self.get_logger().info(
                f"Fake GPS #{self.msg_count}: lat={lat:.6f}, lon={lon:.6f}, alt={alt:.2f}m, "
                f"horiz_acc={horiz_acc:.2f}m, vert_acc={vert_acc:.2f}m"
            )
            self.last_log_time = now

    def enu_to_lla(self, x_enu: float, y_enu: float, z_enu: float) -> tuple:
        """
        Convert local ENU coordinates to LLA (WGS84).
        Uses flat-earth approximation valid for small areas (< 10km).
        """
        # ENU to LLA: datum is the origin
        # x_enu = East, y_enu = North, z_enu = Up
        dlat = y_enu / self.R_EARTH * 180.0 / math.pi
        dlon = x_enu / (self.R_EARTH * math.cos(math.radians(self.datum_lat))) * 180.0 / math.pi

        lat = self.datum_lat + dlat
        lon = self.datum_lon + dlon
        alt = self.datum_alt + z_enu  # ENU z = Up, MSL altitude

        return lat, lon, alt


def main(args=None):
    rclpy.init(args=args)
    node = FakeGPSNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info(f"Fake GPS Node shutting down. Total messages: {node.msg_count}")
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
