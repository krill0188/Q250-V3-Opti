#!/usr/bin/env python3
"""
LLM Mission Planner Node for Q250-V3-Opti

Converts natural language mission descriptions to structured waypoint/constraint JSON
for PX4 autopilot. Integrates with LLM providers (OpenAI, Anthropic, local) and
includes safety validation pipeline.

Architecture: Decision Layer (LLM) → Validation → PX4 OFFBOARD/Mission
"""

import json
import os
import time
import uuid
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.parameter import Parameter
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState
from mavros_msgs.msg import State as MavrosState
from mavros_msgs.srv import CommandBool, SetMode
from px4_msgs.msg import VehicleStatus, VehicleLocalPosition, VehicleGlobalPosition

# Optional LLM imports
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from jinja2 import Environment, FileSystemLoader

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


class MissionType(Enum):
    PATROL = "patrol"
    SURVEY = "survey"
    INSPECTION = "inspection"
    DELIVERY = "delivery"
    CUSTOM = "custom"


class ActionType(Enum):
    NONE = "none"
    TAKEOFF = "takeoff"
    LAND = "land"
    LOITER = "loiter"
    PHOTO = "photo"
    SCAN = "scan"


@dataclass
class Waypoint:
    seq: int
    lat: float
    lon: float
    alt: float
    speed: float = 3.0
    heading: float = 0.0
    hold_time: float = 0.0
    action: str = "none"
    params: Dict = field(default_factory=dict)


@dataclass
class Constraints:
    max_altitude: float = 50.0
    min_altitude: float = 0.5
    max_speed: float = 5.0
    geofence: List[Dict[str, float]] = field(default_factory=list)
    no_fly_zones: List = field(default_factory=list)
    max_waypoint_distance: float = 500.0
    min_obstacle_clearance: float = 2.0


@dataclass
class Failsafe:
    on_comm_loss: str = "rtl"
    on_battery_low: str = "rtl"
    on_geofence_breach: str = "rtl"
    on_obstacle_critical: str = "hover"


@dataclass
class MissionPlan:
    mission_id: str
    mission_type: str
    priority: str
    waypoints: List[Waypoint]
    constraints: Constraints
    failsafe: Failsafe
    metadata: Dict = field(default_factory=dict)


class LLMProvider:
    """Abstract LLM provider interface"""

    def __init__(self, config: Dict):
        self.config = config

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def validate_response(self, response: str) -> Tuple[bool, Optional[Dict]]:
        """Validate and parse JSON response"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            return True, parsed
        except json.JSONDecodeError as e:
            return False, {"error": f"JSON parse error: {e}", "raw": response[:500]}


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider"""

    def __init__(self, config: Dict):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai package not installed")

        api_key = os.getenv("OPENAI_API_KEY") or config.get("api_key")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = config.get("llm_model", "gpt-4o")
        self.temperature = config.get("llm_temperature", 0.1)
        self.max_tokens = config.get("llm_max_tokens", 2048)
        self.timeout = config.get("llm_timeout", 30.0)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = await asyncio.wait_for(
            self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ),
            timeout=self.timeout,
        )
        return response.choices[0].message.content


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider"""

    def __init__(self, config: Dict):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package not installed")

        api_key = os.getenv("ANTHROPIC_API_KEY") or config.get("api_key")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = config.get("llm_model", "claude-3-5-sonnet-20241022")
        self.temperature = config.get("llm_temperature", 0.1)
        self.max_tokens = config.get("llm_max_tokens", 2048)
        self.timeout = config.get("llm_timeout", 30.0)

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = await asyncio.wait_for(
            self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ),
            timeout=self.timeout,
        )
        return response.content[0].text


class LocalLLMProvider(LLMProvider):
    """Local LLM provider (Ollama, vLLM, etc.)"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = config.get("local_llm_url", "http://localhost:11434/v1")
        self.model = config.get("llm_model", "llama3.1:8b")
        self.temperature = config.get("llm_temperature", 0.1)
        self.max_tokens = config.get("llm_max_tokens", 2048)
        self.timeout = config.get("llm_timeout", 60.0)

        import aiohttp

        self.session = aiohttp.ClientSession()

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        import aiohttp

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as response:
            result = await response.json()
            return result["choices"][0]["message"]["content"]

    async def close(self):
        await self.session.close()


class MissionValidator:
    """Validates mission plans for safety and correctness"""

    def __init__(self, config: Dict):
        self.config = config
        self.max_altitude = config.get("max_altitude", 50.0)
        self.min_altitude = config.get("min_altitude", 0.5)
        self.max_speed = config.get("max_speed", 5.0)
        self.max_waypoint_distance = config.get("max_waypoint_distance", 500.0)
        self.safety_margin = config.get("safety_margin", 2.0)
        self.geofence = config.get("geofence_polygon", [])

    def validate(self, mission: MissionPlan) -> Dict:
        errors = []
        warnings = []
        suggestions = []

        # 1. Coordinate validity
        for i, wp in enumerate(mission.waypoints):
            if not (-90 <= wp.lat <= 90):
                errors.append(
                    {
                        "code": "INVALID_LATITUDE",
                        "message": f"Waypoint {i}: latitude {wp.lat} out of range [-90, 90]",
                        "severity": "critical",
                        "waypoint_index": i,
                    }
                )
            if not (-180 <= wp.lon <= 180):
                errors.append(
                    {
                        "code": "INVALID_LONGITUDE",
                        "message": f"Waypoint {i}: longitude {wp.lon} out of range [-180, 180]",
                        "severity": "critical",
                        "waypoint_index": i,
                    }
                )
            if not (self.min_altitude <= wp.alt <= self.max_altitude):
                errors.append(
                    {
                        "code": "INVALID_ALTITUDE",
                        "message": f"Waypoint {i}: altitude {wp.alt}m out of range [{self.min_altitude}, {self.max_altitude}]",
                        "severity": "critical",
                        "waypoint_index": i,
                    }
                )
            if not (0.1 <= wp.speed <= self.max_speed):
                errors.append(
                    {
                        "code": "INVALID_SPEED",
                        "message": f"Waypoint {i}: speed {wp.speed}m/s out of range [0.1, {self.max_speed}]",
                        "severity": "critical",
                        "waypoint_index": i,
                    }
                )
            if wp.hold_time < 0:
                errors.append(
                    {
                        "code": "INVALID_HOLD_TIME",
                        "message": f"Waypoint {i}: hold_time {wp.hold_time}s must be >= 0",
                        "severity": "critical",
                        "waypoint_index": i,
                    }
                )
            if wp.action not in [a.value for a in ActionType]:
                errors.append(
                    {
                        "code": "INVALID_ACTION",
                        "message": f"Waypoint {i}: action '{wp.action}' not valid",
                        "severity": "critical",
                        "waypoint_index": i,
                    }
                )

        # 2. Geofence compliance
        if self.geofence and len(self.geofence) >= 3:
            for i, wp in enumerate(mission.waypoints):
                if not self._point_in_polygon(wp.lat, wp.lon, self.geofence):
                    errors.append(
                        {
                            "code": "OUTSIDE_GEOFENCE",
                            "message": f"Waypoint {i}: outside geofence boundary",
                            "severity": "critical",
                            "waypoint_index": i,
                        }
                    )
                else:
                    # Check margin
                    margin = self._distance_to_polygon_edge(
                        wp.lat, wp.lon, self.geofence
                    )
                    if margin < self.safety_margin:
                        warnings.append(
                            {
                                "code": "GEOFENCE_MARGIN",
                                "message": f"Waypoint {i}: only {margin:.1f}m from geofence edge (min {self.safety_margin}m)",
                                "waypoint_index": i,
                            }
                        )

        # 3. Waypoint spacing
        for i in range(1, len(mission.waypoints)):
            dist = self._haversine_distance(
                mission.waypoints[i - 1].lat,
                mission.waypoints[i - 1].lon,
                mission.waypoints[i].lat,
                mission.waypoints[i].lon,
            )
            if dist > self.max_waypoint_distance:
                warnings.append(
                    {
                        "code": "WAYPOINT_SPACING",
                        "message": f"Waypoints {i-1}-{i}: distance {dist:.1f}m exceeds max {self.max_waypoint_distance}m",
                        "waypoint_index": i,
                    }
                )

        # 4. Altitude changes
        for i in range(1, len(mission.waypoints)):
            alt_change = abs(mission.waypoints[i].alt - mission.waypoints[i - 1].alt)
            if alt_change > 10.0:
                warnings.append(
                    {
                        "code": "ALTITUDE_CHANGE",
                        "message": f"Waypoints {i-1}-{i}: altitude change {alt_change:.1f}m > 10m",
                        "waypoint_index": i,
                    }
                )

        # 5. Action sequence
        if mission.waypoints:
            if mission.waypoints[0].action != "takeoff":
                warnings.append(
                    {
                        "code": "MISSING_TAKEOFF",
                        "message": "First waypoint should have action 'takeoff'",
                        "waypoint_index": 0,
                    }
                )
            if mission.waypoints[-1].action != "land":
                warnings.append(
                    {
                        "code": "MISSING_LAND",
                        "message": "Last waypoint should have action 'land'",
                        "waypoint_index": len(mission.waypoints) - 1,
                    }
                )

        # 6. Failsafe defaults
        if not mission.failsafe.on_comm_loss:
            mission.failsafe.on_comm_loss = "rtl"
        if not mission.failsafe.on_battery_low:
            mission.failsafe.on_battery_low = "rtl"
        if not mission.failsafe.on_geofence_breach:
            mission.failsafe.on_geofence_breach = "rtl"
        if not mission.failsafe.on_obstacle_critical:
            mission.failsafe.on_obstacle_critical = "hover"

        # 10. Suggestions
        if len(mission.waypoints) > 20:
            suggestions.append("Consider splitting long mission into multiple segments")
        if mission.constraints.max_altitude > 30:
            suggestions.append(
                "High altitude mission: verify VIO/fake GPS accuracy at altitude"
            )

        valid = len(errors) == 0
        score = 1.0 - (len(errors) * 0.2 + len(warnings) * 0.05)
        score = max(0.0, min(1.0, score))

        return {
            "valid": valid,
            "score": round(score, 2),
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "auto_fix_applied": False,
            "fixed_mission_json": {},
        }

    def _point_in_polygon(self, lat: float, lon: float, polygon: List[Dict]) -> bool:
        """Ray casting algorithm for point-in-polygon test"""
        x, y = lon, lat
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]["lon"], polygon[0]["lat"]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]["lon"], polygon[i % n]["lat"]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def _distance_to_polygon_edge(
        self, lat: float, lon: float, polygon: List[Dict]
    ) -> float:
        """Minimum distance from point to polygon edges"""
        min_dist = float("inf")
        for i in range(len(polygon)):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % len(polygon)]
            dist = self._point_to_segment_distance(
                lat, lon, p1["lat"], p1["lon"], p2["lat"], p2["lon"]
            )
            min_dist = min(min_dist, dist)
        return min_dist

    def _point_to_segment_distance(
        self, lat: float, lon: float, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Distance from point to line segment (approximate for small distances)"""
        # Convert to local ENU approximation
        R = 6378137.0
        x = (lon - lon1) * R * math.cos(math.radians(lat1))
        y = (lat - lat1) * R
        x1, y1 = 0, 0
        x2 = (lon2 - lon1) * R * math.cos(math.radians(lat1))
        y2 = (lat2 - lat1) * R

        # Point to segment distance
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(x, y)
        t = max(0, min(1, (x * dx + y * dy) / (dx * dx + dy * dy)))
        px, py = x1 + t * dx, y1 + t * dy
        return math.hypot(x - px, y - py)

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Haversine distance in meters"""
        import math

        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(a))


class MissionPlannerNode(Node):
    """LLM Mission Planner Node"""

    def __init__(self):
        super().__init__("mission_planner_node")

        # Declare parameters
        self.declare_parameters(
            namespace="",
            parameters=[
                ("llm_provider", "openai"),
                ("llm_model", "gpt-4o"),
                ("llm_temperature", 0.1),
                ("llm_max_tokens", 2048),
                ("llm_timeout", 30.0),
                ("default_altitude", 10.0),
                ("max_altitude", 50.0),
                ("min_altitude", 0.5),
                ("default_speed", 3.0),
                ("max_speed", 5.0),
                ("safety_margin", 2.0),
                ("max_waypoints", 50),
                ("max_waypoint_distance", 500.0),
                ("geofence_polygon", []),
                ("validate_waypoints", True),
                ("max_retries", 3),
                ("system_prompt_file", "config/prompts/system_prompt.j2"),
                ("mission_prompt_file", "config/prompts/mission_prompt.j2"),
                ("log_llm_requests", True),
                ("log_llm_responses", True),
            ],
        )

        # Load config
        self.config = {
            param: self.get_parameter(param).value
            for param in [
                "llm_provider",
                "llm_model",
                "llm_temperature",
                "llm_max_tokens",
                "llm_timeout",
                "default_altitude",
                "max_altitude",
                "min_altitude",
                "default_speed",
                "max_speed",
                "safety_margin",
                "max_waypoints",
                "max_waypoint_distance",
                "geofence_polygon",
                "validate_waypoints",
                "max_retries",
                "system_prompt_file",
                "mission_prompt_file",
                "log_llm_requests",
                "log_llm_responses",
            ]
        }

        # Initialize LLM provider
        self.llm_provider = self._create_llm_provider()

        # Initialize validator
        self.validator = MissionValidator(self.config)

        # Jinja2 environment for prompts
        if JINJA2_AVAILABLE:
            prompt_dir = os.path.join(os.path.dirname(__file__), "config", "prompts")
            self.jinja_env = Environment(loader=FileSystemLoader(prompt_dir))
        else:
            self.jinja_env = None

        # State
        self.current_position = None
        self.current_battery = 100.0
        self.current_mode = "UNKNOWN"
        self.vio_status = "UNKNOWN"
        self.silvus_status = "UNKNOWN"

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE,
        )

        # Subscribers
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            "/mavros/local_position/pose",
            self.pose_callback,
            qos,
        )
        self.battery_sub = self.create_subscription(
            BatteryState, "/mavros/battery", self.battery_callback, qos
        )
        self.state_sub = self.create_subscription(
            MavrosState, "/mavros/state", self.state_callback, qos
        )

        # Publishers
        self.mission_pub = self.create_publisher(String, "/llm_mission/response", qos)
        self.validated_pub = self.create_publisher(
            String, "/llm_mission/validated", qos
        )
        self.waypoints_pub = self.create_publisher(
            String, "/llm_mission/waypoints", qos
        )

        # Services
        self.plan_srv = self.create_service(
            String, "/llm_mission/plan", self.plan_mission_callback
        )
        self.validate_srv = self.create_service(
            String, "/llm_mission/validate", self.validate_mission_callback
        )

        # Subscription for mission requests
        self.request_sub = self.create_subscription(
            String, "/llm_mission/request", self.mission_request_callback, qos
        )

        self.get_logger().info("LLM Mission Planner Node initialized")
        self.get_logger().info(
            f'LLM Provider: {self.config["llm_provider"]}, Model: {self.config["llm_model"]}'
        )

    def _create_llm_provider(self) -> LLMProvider:
        provider_name = self.config["llm_provider"].lower()
        if provider_name == "openai":
            return OpenAIProvider(self.config)
        elif provider_name == "anthropic":
            return AnthropicProvider(self.config)
        elif provider_name == "local":
            return LocalLLMProvider(self.config)
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")

    def pose_callback(self, msg: PoseWithCovarianceStamped):
        self.current_position = {
            "x": msg.pose.pose.position.x,
            "y": msg.pose.pose.position.y,
            "z": msg.pose.pose.position.z,
        }

    def battery_callback(self, msg: BatteryState):
        if msg.capacity > 0:
            self.current_battery = (msg.charge / msg.capacity) * 100.0
        else:
            self.current_battery = (
                msg.percentage * 100.0 if msg.percentage >= 0 else 100.0
            )

    def state_callback(self, msg: MavrosState):
        self.current_mode = msg.mode

    def mission_request_callback(self, msg: String):
        """Handle incoming mission requests"""
        self.get_logger().info(f"Received mission request: {msg.data[:100]}...")
        # Process asynchronously
        self.create_task(self.process_mission_request(msg.data))

    async def process_mission_request(self, user_input: str):
        """Process natural language mission request"""
        try:
            # Load prompts
            system_prompt = self._load_prompt("system_prompt.j2")
            mission_prompt = self._render_prompt(
                "mission_prompt.j2",
                {
                    "user_input": user_input,
                    "current_position_lat": 37.5665,  # Default datum
                    "current_position_lon": 126.9780,
                    "current_position_alt": 28.0,
                    "battery_percent": self.current_battery,
                    "flight_mode": self.current_mode,
                    "vio_status": self.vio_status,
                    "silvus_status": self.silvus_status,
                    "geofence": self.config.get("geofence_polygon", []),
                    "no_fly_zones": [],
                    "obstacles": [],
                    "weather_info": "Indoor",
                    **{
                        k: self.config[k]
                        for k in [
                            "default_altitude",
                            "max_altitude",
                            "min_altitude",
                            "default_speed",
                            "max_speed",
                            "safety_margin",
                            "max_waypoints",
                            "max_waypoint_distance",
                        ]
                    },
                },
            )

            # Generate mission plan
            for attempt in range(self.config["max_retries"]):
                self.get_logger().info(
                    f'LLM attempt {attempt + 1}/{self.config["max_retries"]}'
                )

                response = await self.llm_provider.generate(
                    system_prompt, mission_prompt
                )

                if self.config["log_llm_responses"]:
                    self.get_logger().info(f"LLM Response: {response[:200]}...")

                # Validate response
                valid, parsed = self.llm_provider.validate_response(response)
                if not valid:
                    self.get_logger().warn(f"LLM response invalid: {parsed}")
                    continue

                # Convert to MissionPlan
                mission = self._parse_mission(parsed)

                # Validate mission
                validation = self.validator.validate(mission)

                if validation["valid"]:
                    # Success!
                    await self._publish_mission(mission, validation)
                    return
                else:
                    self.get_logger().warn(f'Validation failed: {validation["errors"]}')
                    if not self.config.get("retry_on_validation_error", True):
                        break

            # All attempts failed
            self.get_logger().error("All LLM attempts failed or validation failed")
            await self._publish_error(
                user_input, "Failed to generate valid mission plan"
            )

        except Exception as e:
            self.get_logger().error(f"Mission planning error: {e}")
            await self._publish_error(user_input, str(e))

    def _load_prompt(self, filename: str) -> str:
        if self.jinja_env:
            return self.jinja_env.get_template(filename).render()
        else:
            # Fallback: read raw file
            path = os.path.join(
                os.path.dirname(__file__), "config", "prompts", filename
            )
            with open(path, "r") as f:
                return f.read()

    def _render_prompt(self, filename: str, context: Dict) -> str:
        if self.jinja_env:
            return self.jinja_env.get_template(filename).render(**context)
        else:
            # Simple string replacement fallback
            path = os.path.join(
                os.path.dirname(__file__), "config", "prompts", filename
            )
            with open(path, "r") as f:
                template = f.read()
            for key, value in context.items():
                template = template.replace(f"{{{{ {key} }}}}", str(value))
            return template

    def _parse_mission(self, parsed: Dict) -> MissionPlan:
        """Convert parsed JSON to MissionPlan dataclass"""
        waypoints = []
        for wp_data in parsed.get("waypoints", []):
            wp = Waypoint(
                seq=wp_data.get("seq", 0),
                lat=wp_data.get("lat", 0.0),
                lon=wp_data.get("lon", 0.0),
                alt=wp_data.get("alt", self.config["default_altitude"]),
                speed=wp_data.get("speed", self.config["default_speed"]),
                heading=wp_data.get("heading", 0.0),
                hold_time=wp_data.get("hold_time", 0.0),
                action=wp_data.get("action", "none"),
                params=wp_data.get("params", {}),
            )
            waypoints.append(wp)

        constraints = Constraints(
            max_altitude=parsed.get("constraints", {}).get(
                "max_altitude", self.config["max_altitude"]
            ),
            min_altitude=parsed.get("constraints", {}).get(
                "min_altitude", self.config["min_altitude"]
            ),
            max_speed=parsed.get("constraints", {}).get(
                "max_speed", self.config["max_speed"]
            ),
            geofence=parsed.get("constraints", {}).get(
                "geofence", self.config.get("geofence_polygon", [])
            ),
            no_fly_zones=parsed.get("constraints", {}).get("no_fly_zones", []),
            max_waypoint_distance=parsed.get("constraints", {}).get(
                "max_waypoint_distance", self.config["max_waypoint_distance"]
            ),
            min_obstacle_clearance=parsed.get("constraints", {}).get(
                "min_obstacle_clearance", self.config["safety_margin"]
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
            mission_id=parsed.get("mission_id", str(uuid.uuid4())),
            mission_type=parsed.get("mission_type", "custom"),
            priority=parsed.get("priority", "normal"),
            waypoints=waypoints,
            constraints=constraints,
            failsafe=failsafe,
            metadata=parsed.get("metadata", {}),
        )

    async def _publish_mission(self, mission: MissionPlan, validation: Dict):
        """Publish validated mission"""
        # Publish full mission response
        mission_msg = String()
        mission_msg.data = json.dumps(
            {
                "mission_id": mission.mission_id,
                "mission_type": mission.mission_type,
                "priority": mission.priority,
                "waypoints": [asdict(wp) for wp in mission.waypoints],
                "constraints": asdict(mission.constraints),
                "failsafe": asdict(mission.failsafe),
                "metadata": mission.metadata,
            },
            indent=2,
        )
        self.mission_pub.publish(mission_msg)

        # Publish validated mission
        val_msg = String()
        val_msg.data = json.dumps(validation, indent=2)
        self.validated_pub.publish(val_msg)

        # Publish waypoints for PX4
        wp_msg = String()
        wp_msg.data = json.dumps([asdict(wp) for wp in mission.waypoints], indent=2)
        self.waypoints_pub.publish(wp_msg)

        self.get_logger().info(f"Mission {mission.mission_id} published successfully")

    async def _publish_error(self, user_input: str, error: str):
        error_msg = String()
        error_msg.data = json.dumps(
            {"error": error, "user_input": user_input, "timestamp": time.time()}
        )
        self.mission_pub.publish(error_msg)

    def plan_mission_callback(self, request: String, response: String):
        """Service callback for mission planning"""
        self.create_task(self.process_mission_request(request.data))
        response.data = json.dumps(
            {"status": "accepted", "message": "Mission planning started"}
        )
        return response

    def validate_mission_callback(self, request: String, response: String):
        """Service callback for mission validation"""
        try:
            parsed = json.loads(request.data)
            mission = self._parse_mission(parsed)
            validation = self.validator.validate(mission)
            response.data = json.dumps(validation)
        except Exception as e:
            response.data = json.dumps(
                {
                    "valid": False,
                    "score": 0.0,
                    "errors": [
                        {
                            "code": "PARSE_ERROR",
                            "message": str(e),
                            "severity": "critical",
                        }
                    ],
                }
            )
        return response

    def create_task(self, coro):
        """Create asyncio task in ROS executor"""
        asyncio.create_task(coro)


def main(args=None):
    rclpy.init(args=args)

    # Use MultiThreadedExecutor for async support
    executor = MultiThreadedExecutor()
    node = MissionPlannerNode()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
