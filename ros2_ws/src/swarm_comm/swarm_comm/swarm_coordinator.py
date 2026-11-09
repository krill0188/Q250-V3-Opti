#!/usr/bin/env python3
"""
Swarm Coordinator for Q250-V3-Opti

High-level swarm coordination: formation flight, task allocation, mission coordination.
"""

import json
import time
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.parameter import Parameter

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped, Twist, Point
from nav_msgs.msg import Odometry


class FormationShape(Enum):
    LINE = "line"
    WEDGE = "wedge"
    DIAMOND = "diamond"
    CIRCLE = "circle"


@dataclass
class FormationPosition:
    drone_id: str
    offset_x: float
    offset_y: float
    offset_z: float


class SwarmCoordinator(Node):
    """High-level swarm coordination"""

    def __init__(self):
        super().__init__("swarm_coordinator")

        # Declare parameters
        self.declare_parameters(
            namespace="",
            parameters=[
                ("drone_id", "drone_01"),
                ("swarm_id", "swarm_alpha"),
                ("formation_enabled", False),
                ("formation_shape", "line"),
                ("formation_spacing", 3.0),
                ("leader_id", ""),
                ("position_topic", "/swarm/position"),
                ("formation_cmd_topic", "/swarm/formation_cmd"),
                ("max_swarm_size", 10),
                ("formation_spacing", 3.0),
            ],
        )

        # Load config
        self.config = {
            param: self.get_parameter(param).value
            for param in [
                "drone_id",
                "swarm_id",
                "formation_enabled",
                "formation_shape",
                "formation_spacing",
                "leader_id",
                "position_topic",
                "formation_cmd_topic",
                "max_swarm_size",
            ]
        }

        self.drone_id = self.config["drone_id"]
        self.swarm_id = self.config["swarm_id"]
        self.is_leader = self.drone_id == self.config["leader_id"]

        # State
        self.neighbors: Dict[str, Dict] = {}
        self.formation_positions: List[Tuple[float, float, float]] = []
        self.formation_active = False

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

        # Publisher
        self.formation_pub = self.create_publisher(
            String, self.config["formation_cmd_topic"], 10
        )

        # Timer
        self.coord_timer = self.create_timer(0.1, self.coordination_loop)  # 10 Hz

        self.get_logger().info(
            f"Swarm Coordinator initialized: {self.drone_id} (leader={self.is_leader})"
        )

    def position_callback(self, msg: String):
        """Handle incoming swarm position broadcasts"""
        try:
            data = json.loads(msg.data)
            drone_id = data.get("drone_id")

            if drone_id == self.drone_id:
                return

            self.neighbors[drone_id] = {
                "position": data["position"],
                "velocity": data.get("velocity", {"vx": 0, "vy": 0, "vz": 0}),
                "mode": data.get("mode", "UNKNOWN"),
                "battery": data.get("battery", 100),
                "timestamp": data.get("timestamp", time.time()),
            }

        except Exception as e:
            self.get_logger().debug(f"Position callback error: {e}")

    def coordination_loop(self):
        """Main coordination loop"""
        if not self.config["formation_enabled"]:
            return

        if self.is_leader:
            self._leader_coordination()
        else:
            self._follower_coordination()

    def _leader_coordination(self):
        """Leader computes formation positions and broadcasts commands"""
        # Compute formation offsets
        shape = self.config["formation_shape"]
        spacing = self.config["formation_spacing"]
        max_size = self.config["max_swarm_size"]

        # Get active neighbors
        active_drones = [
            d
            for d in self.neighbors.keys()
            if time.time() - self.neighbors[d]["timestamp"] < 1.0
        ]

        # Compute formation positions
        self.formation_positions = self._compute_formation(
            shape, spacing, len(active_drones) + 1
        )

        # Broadcast formation command
        cmd = {
            "command": "formation",
            "shape": shape,
            "spacing": spacing,
            "leader_id": self.drone_id,
            "positions": {
                drone_id: {"offset_x": pos[0], "offset_y": pos[1], "offset_z": pos[2]}
                for drone_id, pos in zip(
                    [self.drone_id] + list(active_drones), self.formation_positions
                )
            },
            "timestamp": time.time(),
        }

        msg = String()
        msg.data = json.dumps(cmd)
        self.formation_pub.publish(msg)

    def _follower_coordination(self):
        """Follower maintains formation position relative to leader"""
        # Check for formation commands
        # This would be implemented with a subscription to formation_cmd_topic
        pass

    def _compute_formation(
        self, shape: str, spacing: float, num_drones: int
    ) -> List[Tuple[float, float, float]]:
        """Compute formation offsets for given shape and number of drones"""
        positions = []

        if shape == "line":
            # Line formation: drones side by side
            for i in range(num_drones):
                x = 0
                y = (i - (num_drones - 1) / 2) * spacing
                z = 0
                positions.append((x, y, z))

        elif shape == "wedge":
            # Wedge formation: V-shape
            for i in range(num_drones):
                if i == 0:
                    positions.append((0, 0, 0))  # Leader at tip
                else:
                    row = (i + 1) // 2
                    side = 1 if i % 2 == 1 else -1
                    x = -row * spacing * 0.7
                    y = side * row * spacing * 0.7
                    z = 0
                    positions.append((x, y, z))

        elif shape == "diamond":
            # Diamond formation
            for i in range(num_drones):
                if i == 0:
                    positions.append((0, 0, 0))
                elif i == 1:
                    positions.append((-spacing, 0, 0))
                elif i == 2:
                    positions.append((0, spacing, 0))
                elif i == 3:
                    positions.append((0, -spacing, 0))
                else:
                    # Additional drones in outer ring
                    angle = 2 * math.pi * (i - 4) / max(1, num_drones - 4)
                    r = 2 * spacing
                    positions.append((r * math.cos(angle), r * math.sin(angle), 0))

        elif shape == "circle":
            # Circle formation
            for i in range(num_drones):
                angle = 2 * math.pi * i / num_drones
                r = spacing * num_drones / (2 * math.pi)
                positions.append((r * math.cos(angle), r * math.sin(angle), 0))

        return positions


def main(args=None):
    rclpy.init(args=args)
    node = SwarmCoordinator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
