#!/usr/bin/env python3
"""
Collision Avoidance for Q250-V3-Opti Swarm

Real-time collision avoidance using potential fields / velocity obstacles.
Subscribes to swarm position broadcasts and computes avoidance velocities.
"""

import json
import math
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.parameter import Parameter

from std_msgs.msg import String
from geometry_msgs.msg import Twist, Vector3, PoseStamped
from nav_msgs.msg import Odometry
from px4_msgs.msg import VehicleLocalPosition, VehicleVelocitySetpoint
from std_msgs.msg import Header
from builtin_interfaces.msg import Time as BuiltinTime


class CAAlgorithm(Enum):
    POTENTIAL_FIELD = "potential_field"
    VELOCITY_OBSTACLE = "velocity_obstacle"
    MPC = "mpc"


@dataclass
class DroneState:
    drone_id: str
    position: Tuple[float, float, float]  # ENU
    velocity: Tuple[float, float, float]
    attitude: Tuple[float, float, float, float]  # quaternion
    timestamp: float
    mode: str = "UNKNOWN"
    battery: float = 100.0
    vio_healthy: bool = True


class CollisionAvoidance(Node):
    """Real-time collision avoidance for swarm"""

    def __init__(self):
        super().__init__("collision_avoidance")

        # Declare parameters
        self.declare_parameters(
            namespace="",
            parameters=[
                ("drone_id", "drone_01"),
                ("ca_algorithm", "potential_field"),
                ("safety_radius", 2.0),
                ("warning_radius", 5.0),
                ("max_avoidance_accel", 2.0),
                ("prediction_horizon", 2.0),
                ("min_approach_angle", 30.0),
                ("repulsive_gain", 1.0),
                "attractive_gain",
                0.5,
                "max_repulsive_force",
                5.0,
                "cut_off_distance",
                10.0,
                "vo_time_horizon",
                3.0,
                "vo_safety_margin",
                1.0,
                ("position_topic", "/swarm/position"),
                ("cmd_vel_topic", "/mavros/setpoint_velocity/cmd_vel"),
                ("odom_topic", "/mavros/local_position/odom"),
                ("max_position_age", 1.0),
                ("min_neighbors_for_ca", 1),
                ("log_collision_events", True),
            ],
        )

        # Load config
        self.config = {
            param: self.get_parameter(param).value
            for param in [
                "drone_id",
                "ca_algorithm",
                "safety_radius",
                "warning_radius",
                "max_avoidance_accel",
                "prediction_horizon",
                "min_approach_angle",
                "repulsive_gain",
                "attractive_gain",
                "max_repulsive_force",
                "cut_off_distance",
                "vo_time_horizon",
                "vo_safety_margin",
                "position_topic",
                "cmd_vel_topic",
                "odom_topic",
                "max_position_age",
                "min_neighbors_for_ca",
                "log_collision_events",
            ]
        }

        self.drone_id = self.config["drone_id"]
        self.algorithm = CAAlgorithm(self.config["ca_algorithm"])

        # State
        self.neighbors: Dict[str, Dict] = {}
        self.own_state: Optional[Dict] = None
        self.avoidance_active = False
        self.last_avoidance_time = 0

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
        )

        # Subscribers
        self.position_sub = self.create_subscription(
            String, self.config["position_topic"], self.position_callback, 10
        )
        self.odom_sub = self.create_subscription(
            Odometry, self.config["odom_topic"], self.odom_callback, 10
        )

        # Publisher
        self.cmd_vel_pub = self.create_publisher(
            Twist, self.config["cmd_vel_topic"], 10
        )

        # Timer for CA loop
        self.ca_timer = self.create_timer(0.05, self.ca_loop)  # 20 Hz

        self.get_logger().info(
            f"Collision Avoidance initialized: {self.drone_id} ({self.algorithm.value})"
        )

    def position_callback(self, msg: String):
        """Handle incoming swarm position broadcasts"""
        try:
            data = json.loads(msg.data)
            drone_id = data.get("drone_id")

            if drone_id == self.drone_id:
                return  # Ignore own broadcast

            # Check timestamp freshness
            age = time.time() - data.get("timestamp", 0)
            if age > self.get_parameter("max_position_age").value:
                return

            # Update neighbor state
            self.neighbors[drone_id] = {
                "position": data["position"],
                "velocity": data.get("velocity", {"vx": 0, "vy": 0, "vz": 0}),
                "attitude": data.get("attitude"),
                "mode": data.get("mode", "UNKNOWN"),
                "battery": data.get("battery", 100),
                "vio_healthy": data.get("vio_quality", {}).get("healthy", True),
                "timestamp": data["timestamp"],
                "link_quality": data.get("link_quality", {}),
            }

        except Exception as e:
            self.get_logger().debug(f"Position callback error: {e}")

    def odom_callback(self, msg: Odometry):
        """Update own state from odometry"""
        self.own_state = {
            "position": (
                msg.pose.pose.position.x,
                msg.pose.pose.position.y,
                msg.pose.pose.position.z,
            ),
            "velocity": (
                msg.twist.twist.linear.x,
                msg.twist.twist.linear.y,
                msg.twist.twist.linear.z,
            ),
            "attitude": (
                msg.pose.pose.orientation.x,
                msg.pose.pose.orientation.y,
                msg.pose.pose.orientation.z,
                msg.pose.pose.orientation.w,
            ),
            "timestamp": time.time(),
        }

    def ca_loop(self):
        """Main collision avoidance loop (20 Hz)"""
        if self.own_state is None:
            return

        # Filter valid neighbors
        valid_neighbors = {}
        now = time.time()
        for drone_id, state in self.neighbors.items():
            age = now - state["timestamp"]
            if age <= self.get_parameter("max_position_age").value:
                valid_neighbors[drone_id] = state

        self.neighbors = valid_neighbors

        # Check if we have enough neighbors for CA
        if len(valid_neighbors) < self.get_parameter("min_neighbors_for_ca").value:
            self.avoidance_active = False
            return

        # Compute avoidance velocity
        avoidance_vel = self.compute_avoidance_velocity()

        if avoidance_vel is not None:
            self.avoidance_active = True
            self.last_avoidance_time = time.time()

            # Publish avoidance velocity
            cmd = Twist()
            cmd.linear.x = avoidance_vel[0]
            cmd.linear.y = avoidance_vel[1]
            cmd.linear.z = avoidance_vel[2]
            self.cmd_vel_pub.publish(cmd)

            if self.get_parameter("log_collision_events").value:
                self.get_logger().warn(
                    f"CA ACTIVE: avoidance_vel=({avoidance_vel[0]:.2f}, {avoidance_vel[1]:.2f}, {avoidance_vel[2]:.2f})"
                )
        else:
            if self.avoidance_active:
                self.avoidance_active = False
                self.get_logger().info("CA deactivated - no threats")

    def compute_avoidance_velocity(self) -> Optional[Tuple[float, float, float]]:
        """Compute avoidance velocity based on algorithm"""
        if self.algorithm == CAAlgorithm.POTENTIAL_FIELD:
            return self._potential_field_avoidance()
        elif self.algorithm == CAAlgorithm.VELOCITY_OBSTACLE:
            return self._velocity_obstacle_avoidance()
        else:
            return self._potential_field_avoidance()

    def _potential_field_avoidance(self) -> Optional[Tuple[float, float, float]]:
        """Potential field based collision avoidance"""
        own_pos = self.own_state["position"]
        own_vel = self.own_state["velocity"]

        total_force = [0.0, 0.0, 0.0]
        threat_detected = False

        safety_radius = self.get_parameter("safety_radius").value
        warning_radius = self.get_parameter("warning_radius").value
        repulsive_gain = self.get_parameter("repulsive_gain").value
        max_force = self.get_parameter("max_repulsive_force").value
        cutoff = self.get_parameter("cut_off_distance").value

        for drone_id, neighbor in self.neighbors.items():
            n_pos = neighbor["position"]
            n_vel = neighbor.get("velocity", {"vx": 0, "vy": 0, "vz": 0})

            # Relative position
            dx = own_pos[0] - n_pos["x"]
            dy = own_pos[1] - n_pos["y"]
            dz = own_pos[2] - n_pos["z"]

            distance = math.sqrt(dx * dx + dy * dy + dz * dz)

            if distance > cutoff or distance < 0.1:
                continue

            threat_detected = True

            # Repulsive force (inverse square law)
            if distance < safety_radius:
                # Strong repulsion within safety radius
                force_mag = repulsive_gain * (safety_radius / distance) ** 2
            elif distance < warning_radius:
                # Weaker repulsion in warning zone
                force_mag = repulsive_gain * (warning_radius / distance) * 0.5
            else:
                continue

            # Cap force
            force_mag = min(force_mag, max_force)

            # Direction away from neighbor
            total_force[0] += force_mag * dx / distance
            total_force[1] += force_mag * dy / distance
            total_force[2] += force_mag * dz / distance

        if not threat_detected:
            return None

        # Convert force to velocity (simple proportional control)
        kp = 1.0
        avoidance_vel = (total_force[0] * kp, total_force[1] * kp, total_force[2] * kp)

        # Limit to max avoidance acceleration
        max_accel = self.get_parameter("max_avoidance_accel").value
        vel_mag = math.sqrt(
            avoidance_vel[0] ** 2 + avoidance_vel[1] ** 2 + avoidance_vel[2] ** 2
        )
        if vel_mag > max_accel:
            scale = max_accel / vel_mag
            avoidance_vel = (
                avoidance_vel[0] * scale,
                avoidance_vel[1] * scale,
                avoidance_vel[2] * scale,
            )

        return avoidance_vel

    def _velocity_obstacle_avoidance(self) -> Optional[Tuple[float, float, float]]:
        """Velocity Obstacle based collision avoidance"""
        # Simplified VO implementation
        own_pos = self.own_state["position"]
        own_vel = self.own_state["velocity"]

        time_horizon = self.get_parameter("vo_time_horizon").value
        safety_margin = self.get_parameter("vo_safety_margin").value

        best_vel = list(self.own_state.get("velocity", (0, 0, 0)))
        min_cost = float("inf")

        # Sample candidate velocities
        for vx in [-2, -1, 0, 1, 2]:
            for vy in [-2, -1, 0, 1, 2]:
                for vz in [-1, 0, 1]:
                    cand_vel = (vx, vy, vz)
                    cost = 0
                    collision = False

                    for drone_id, neighbor in self.neighbors.items():
                        n_pos = neighbor["position"]
                        n_vel = neighbor.get("velocity", {"vx": 0, "vy": 0, "vz": 0})

                        # Relative position and velocity
                        rx = n_pos["x"] - own_pos[0]
                        ry = n_pos["y"] - own_pos[1]
                        rz = n_pos["z"] - own_pos[2]
                        rvx = n_vel["vx"] - cand_vel[0]
                        rvy = n_vel["vy"] - cand_vel[1]
                        rvz = n_vel["vz"] - cand_vel[2]

                        # Check collision within time horizon
                        # Simplified: check if relative position + relative velocity * t < safety_radius
                        for t in [time_horizon * 0.5, time_horizon]:
                            fx = rx + rvx * t
                            fy = ry + rvy * t
                            fz = rz + rvz * t
                            dist = math.sqrt(fx * fx + fy * fy + fz * fz)
                            if (
                                dist
                                < self.get_parameter("safety_radius").value
                                + safety_margin
                            ):
                                collision = True
                                break

                    if collision:
                        continue

                    # Cost: prefer current velocity, penalize deviation
                    cost = (
                        (cand_vel[0] - own_vel[0]) ** 2
                        + (cand_vel[1] - own_vel[1]) ** 2
                        + (cand_vel[2] - own_vel[2]) ** 2
                    )

                    if cost < min_cost:
                        min_cost = cost
                        best_vel = list(cand_vel)

        if min_cost == float("inf"):
            return None

        # Return velocity change (delta)
        return (
            best_vel[0] - own_vel[0],
            best_vel[1] - own_vel[1],
            best_vel[2] - own_vel[2],
        )


def main(args=None):
    rclpy.init(args=args)
    node = CollisionAvoidance()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
