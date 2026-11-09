#!/usr/bin/env python3
"""
Obstacle Distance Publisher for Q250-V3-Opti

Converts LiDAR / distance sensor data to MAVLink OBSTACLE_DISTANCE message
for PX4 collision prevention.

Subscribes: mavros_msgs/DistanceSensor (or sensor_msgs/Range)
Publishes:  mavros_msgs/ObstacleDistance (to MAVROS -> PX4)

Based on docs/12-obstacle-avoidance-pipeline.md
"""

import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from mavros_msgs.msg import ObstacleDistance
from sensor_msgs.msg import Range
from mavros_msgs.msg import DistanceSensor
from std_msgs.msg import Header


class ObstacleDistancePublisher(Node):
    """Publishes obstacle distances to MAVROS for PX4 collision prevention."""

    def __init__(self):
        super().__init__("obstacle_distance_pub")

        # Parameters
        self.declare_parameter("lidar_topic", "/mavros/distance_sensor/lidar")
        self.declare_parameter(
            "mavros_obstacle_topic", "/mavros/obstacle_distance/send"
        )
        self.declare_parameter("num_sectors", 72)  # 5-degree sectors (360/5=72)
        self.declare_parameter("max_distance", 10.0)
        self.declare_parameter("min_distance", 0.1)
        self.declare_parameter("frame_id", "base_link")
        self.declare_parameter("sensor_orientation", 0)  # MAV_SENSOR_ORIENTATION

        self.lidar_topic = self.get_parameter("lidar_topic").value
        self.obstacle_topic = self.get_parameter("mavros_obstacle_topic").value
        self.num_sectors = self.get_parameter("num_sectors").value
        self.max_distance = self.get_parameter("max_distance").value
        self.min_distance = self.get_parameter("min_distance").value
        self.frame_id = self.get_parameter("frame_id").value
        self.sensor_orientation = self.get_parameter("sensor_orientation").value

        # Sector angle width
        self.sector_angle = 360.0 / self.num_sectors

        # Latest distance reading (single LiDAR forward)
        self.latest_distance = None
        self.latest_timestamp = None

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
        )

        # Subscriber: LiDAR distance sensor (from MAVROS)
        self.lidar_sub = self.create_subscription(
            DistanceSensor, self.lidar_topic, self.lidar_callback, qos
        )

        # Also support sensor_msgs/Range
        self.range_sub = self.create_subscription(
            Range,
            self.lidar_topic.replace("distance_sensor", "range"),
            self.range_callback,
            qos,
        )

        # Publisher: MAVROS ObstacleDistance
        self.obstacle_pub = self.create_publisher(
            ObstacleDistance, self.obstacle_topic, qos
        )

        # Timer: publish at 10Hz (PX4 expects regular updates)
        self.timer = self.create_timer(0.1, self.publish_obstacle_distance)

        self.get_logger().info(
            f"Obstacle Distance Publisher initialized:\n"
            f"  LiDAR topic: {self.lidar_topic}\n"
            f"  Output topic: {self.obstacle_topic}\n"
            f"  Sectors: {self.num_sectors} ({self.sector_angle:.1f} deg each)\n"
            f"  Range: {self.min_distance}-{self.max_distance}m"
        )

    def lidar_callback(self, msg: DistanceSensor):
        """Handle MAVROS DistanceSensor message."""
        # Only use forward-facing sensor (orientation 0 = forward)
        if msg.orientation == 0 or msg.orientation == 255:  # 255 = unknown/default
            self.latest_distance = msg.current_distance
            self.latest_timestamp = self.get_clock().now()

    def range_callback(self, msg: Range):
        """Handle sensor_msgs/Range message."""
        self.latest_distance = msg.range
        self.latest_timestamp = self.get_clock().now()

    def publish_obstacle_distance(self):
        """Publish OBSTACLE_DISTANCE message to MAVROS."""
        if self.latest_distance is None:
            return

        # Clamp distance
        dist = max(self.min_distance, min(self.max_distance, self.latest_distance))

        # Convert to cm (MAVLink OBSTACLE_DISTANCE uses cm)
        dist_cm = int(dist * 100)
        max_dist_cm = int(self.max_distance * 100)
        min_dist_cm = int(self.min_distance * 100)

        # Create message
        msg = ObstacleDistance()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id

        # Time in microseconds since boot (approximate)
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)

        # Single LiDAR forward: populate only forward sector (index 0 = North/Forward)
        # Sector 0 = 0 deg (North/Forward), increasing clockwise
        msg.distances = [max_dist_cm] * self.num_sectors
        msg.distances[0] = dist_cm  # Forward

        # If we have a 360-degree LiDAR, this would fill all sectors
        # For single forward LiDAR, we can infer some side sectors as unknown (max)
        # PX4 will treat max_dist_cm as "no obstacle detected"

        msg.increment = int(self.sector_angle * 100)  # degrees * 100
        msg.min_distance = min_dist_cm
        msg.max_distance = max_dist_cm
        msg.angle_offset = 0  # Sector 0 aligned with forward
        msg.frame = 0  # MAV_FRAME_BODY_FRD (0) or MAV_FRAME_LOCAL_NED (1)
        # Use body frame so sector 0 = forward

        self.obstacle_pub.publish(msg)

        if (
            self.get_clock().now().nanoseconds % 10_000_000_000 < 100_000_000
        ):  # ~1Hz log
            self.get_logger().debug(
                f"Published obstacle distance: {dist:.2f}m ({dist_cm}cm)"
            )


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleDistancePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
