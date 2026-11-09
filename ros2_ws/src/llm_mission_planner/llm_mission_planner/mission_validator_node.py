#!/usr/bin/env python3
"""
Mission Validator Node for Q250-V3-Opti

Standalone validator for mission plans. Can be used independently or as part
of the mission planning pipeline.
"""

import json
import os
from typing import Dict, List, Any

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from std_msgs.msg import String

from .mission_planner_node import (
    MissionValidator,
    MissionPlan,
    Waypoint,
    Constraints,
    Failsafe,
    ActionType,
)


class MissionValidatorNode(Node):
    """Standalone mission validation node"""

    def __init__(self):
        super().__init__("mission_validator_node")

        # Declare parameters
        self.declare_parameters(
            namespace="",
            parameters=[
                ("max_altitude", 50.0),
                ("min_altitude", 0.5),
                ("max_speed", 5.0),
                ("safety_margin", 2.0),
                ("max_waypoint_distance", 500.0),
                ("geofence_polygon", []),
                ("min_obstacle_clearance", 2.0),
            ],
        )

        # Load config
        self.config = {
            param: self.get_parameter(param).value
            for param in [
                "max_altitude",
                "min_altitude",
                "max_speed",
                "safety_margin",
                "max_waypoint_distance",
                "geofence_polygon",
                "min_obstacle_clearance",
            ]
        }

        # Initialize validator
        self.validator = MissionValidator(self.config)

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
        )

        # Subscriber for mission validation requests
        self.validation_sub = self.create_subscription(
            String, "/llm_mission/validate_request", self.validate_callback, qos
        )

        # Publisher for validation results
        self.result_pub = self.create_publisher(
            String, "/llm_mission/validation_result", qos
        )

        self.get_logger().info("Mission Validator Node initialized")

    def validate_callback(self, msg: String):
        """Handle validation request"""
        try:
            # Parse mission JSON
            parsed = json.loads(msg.data)

            # Convert to MissionPlan
            mission = self._parse_mission(parsed)

            # Validate
            validation = self.validator.validate(mission)

            # Publish result
            result_msg = String()
            result_msg.data = json.dumps(validation, indent=2)
            self.result_pub.publish(result_msg)

            if validation["valid"]:
                self.get_logger().info(
                    f'Mission validation PASSED (score: {validation["score"]})'
                )
            else:
                self.get_logger().warn(
                    f'Mission validation FAILED: {len(validation["errors"])} errors'
                )

        except Exception as e:
            self.get_logger().error(f"Validation error: {e}")
            error_result = {
                "valid": False,
                "score": 0.0,
                "errors": [
                    {"code": "PARSE_ERROR", "message": str(e), "severity": "critical"}
                ],
                "warnings": [],
                "suggestions": [],
            }
            result_msg = String()
            result_msg.data = json.dumps(error_result, indent=2)
            self.result_pub.publish(result_msg)

    def _parse_mission(self, parsed: Dict) -> "MissionPlan":
        """Parse JSON to MissionPlan"""
        from .mission_planner_node import MissionPlan, Waypoint, Constraints, Failsafe

        waypoints = []
        for wp_data in parsed.get("waypoints", []):
            wp = Waypoint(
                seq=wp_data.get("seq", 0),
                lat=wp_data.get("lat", 0.0),
                lon=wp_data.get("lon", 0.0),
                alt=wp_data.get("alt", 10.0),
                speed=wp_data.get("speed", 3.0),
                heading=wp_data.get("heading", 0.0),
                hold_time=wp_data.get("hold_time", 0.0),
                action=wp_data.get("action", "none"),
                params=wp_data.get("params", {}),
            )
            waypoints.append(wp)

        constraints = Constraints(
            max_altitude=parsed.get("constraints", {}).get("max_altitude", 50.0),
            min_altitude=parsed.get("constraints", {}).get("min_altitude", 0.5),
            max_speed=parsed.get("constraints", {}).get("max_speed", 5.0),
            geofence=parsed.get("constraints", {}).get("geofence", []),
            no_fly_zones=parsed.get("constraints", {}).get("no_fly_zones", []),
            max_waypoint_distance=parsed.get("constraints", {}).get(
                "max_waypoint_distance", 500.0
            ),
            min_obstacle_clearance=parsed.get("constraints", {}).get(
                "min_obstacle_clearance", 2.0
            ),
        )

        failsafe_data = parsed.get("failsafe", {})
        failsafe = Failsafe(
            on_comm_loss=failsafe_data.get("on_comm_loss", "rtl"),
            on_battery_low=failsafe_data.get("on_battery_low", "rtl"),
            on_geofence_breach=failsafe_data.get("on_geofence_breach", "rtl"),
            on_obstacle_critical=failsafe_data.get("on_obstacle_critical", "hover"),
        )

        return MissionPlan(
            mission_id=parsed.get("mission_id", "unknown"),
            mission_type=parsed.get("mission_type", "custom"),
            priority=parsed.get("priority", "normal"),
            waypoints=waypoints,
            constraints=Constraints(
                max_altitude=parsed.get("constraints", {}).get("max_altitude", 50.0),
                min_altitude=parsed.get("constraints", {}).get("min_altitude", 0.5),
                max_speed=parsed.get("constraints", {}).get("max_speed", 5.0),
                geofence=parsed.get("constraints", {}).get("geofence", []),
                no_fly_zones=parsed.get("constraints", {}).get("no_fly_zones", []),
                max_waypoint_distance=parsed.get("constraints", {}).get(
                    "max_waypoint_distance", 500.0
                ),
                min_obstacle_clearance=parsed.get("constraints", {}).get(
                    "min_obstacle_clearance", 2.0
                ),
            ),
            failsafe=Failsafe(
                on_comm_loss=parsed.get("failsafe", {}).get("on_comm_loss", "rtl"),
                on_battery_low=parsed.get("failsafe", {}).get("on_battery_low", "rtl"),
                on_geofence_breach=parsed.get("failsafe", {}).get(
                    "on_geofence_breach", "rtl"
                ),
                on_obstacle_critical=parsed.get("failsafe", {}).get(
                    "on_obstacle_critical", "hover"
                ),
            ),
            metadata=parsed.get("metadata", {}),
        )


def main(args=None):
    rclpy.init(args=args)
    node = MissionValidatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
