import asyncio
from enum import IntEnum
from typing import Any, Callable, Coroutine, Dict, List, Literal
from pydantic import BaseModel, Field


class CommandPriority(IntEnum):
    FAILSAFE_ESTOP = 0  # 긴급 정지 및 워치독 페일세이프 (최상위)
    MANUAL_SW = 1  # 기본 제어 SW 수동 조작
    VOICE_NLU = 2  # 음성 인식 AI 파서 명령 (하위)


class HardwareSpec(BaseModel):
    device_id: str
    device_type: Literal["drone", "robot", "hybrid_fixed_wing_fpv"]
    environment: Literal["sitl", "real"] = "sitl"
    max_altitude_m: float = 30.0
    min_altitude_m: float = 0.5
    max_linear_vel_mps: float = 5.0
    max_angular_vel_radps: float = 1.5
    min_battery_percent: float = 20.0
    max_dive_angle_deg: float = 80.0
    max_dive_speed_mps: float = 80.0
    min_pullup_altitude_m: float = 30.0
    max_deception_duration_sec: float = 60.0
    deception_patterns: List[str] = []
    capabilities: List[str]


class UnifiedCommand(BaseModel):
    command_id: str
    source: Literal["FAILSAFE", "MANUAL_SW", "VOICE_NLU"]
    priority: CommandPriority
    target_id: str
    action: Literal[
        "ESTOP",
        "ARM",
        "TAKEOFF",
        "LAND",
        "HOLD",
        "MOVE_VEL",
        "GOTO_REL",
        "NAV_TO_POSE",
        "RTL",
        "SET_MODE",
        "DIVE_ATTACK",
        "DECEPTION_START",
        "DECEPTION_PATTERN",
        "DECEPTION_STOP",
        "TRANSITION_CRUISE_TO_FPV",
        "TRANSITION_FPV_TO_CRUISE",
        "GET_RISK_STATUS",
        # 전술 임무 액션
        "RECON_AREA",
        "BDA_OBSERVE",
        "MINEFIELD_RECON",
        "ROUTE_SECURITY",
        "TERRAIN_FOLLOW",
        "EMCON",
    ]
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    vz_mps: float = 0.0
    yaw_rate_radps: float = 0.0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    params: Dict[str, Any] = {}
    clarification_needed: bool = False
    reason: str = ""


class DynamicSafetyValidator:
    def __init__(self, specs: Dict[str, HardwareSpec]):
        self.specs = specs

    def update_spec(self, device_id: str, new_spec: HardwareSpec) -> None:
        """실장비 연결 또는 UI 스펙 변경 시 실시간 업데이트"""
        self.specs[device_id] = new_spec

    def validate_and_clamp(self, cmd: UnifiedCommand) -> UnifiedCommand:
        if cmd.target_id not in self.specs:
            raise ValueError(f"등록되지 않은 기체 ID: {cmd.target_id}")

        spec = self.specs[cmd.target_id]

        # 긴급 정지는 모든 검증을 우회하여 즉시 통과
        if cmd.action == "ESTOP" or cmd.priority == 0:  # FAILSAFE_ESTOP
            return cmd

        # 1) 음성 명령 신뢰도 검사 (0.85 미만 차단)
        if cmd.source == "VOICE_NLU" and cmd.confidence < 0.85:
            raise ValueError(f"음성 인식 신뢰도 부족 ({cmd.confidence:.2f} < 0.85)")

        # 2) 기체 지원 기능(Capability) 검사
        if cmd.action not in spec.capabilities:
            raise ValueError(f"{cmd.target_id} 기체가 지원하지 않는 명령: {cmd.action}")

        # 3) 드론 이륙 고도 한계 검증
        if spec.device_type == "drone" and cmd.action == "TAKEOFF":
            if not (spec.min_altitude_m <= cmd.z_m <= spec.max_altitude_m):
                raise ValueError(
                    f"이륙 고도({cmd.z_m}m)가 안전 범위({spec.min_altitude_m}~{spec.max_altitude_m}m)를 벗어났습니다."
                )

        # 4) 속도 제한 Clamping (스펙 상한선 강제 적용)
        max_v = spec.max_linear_vel_mps
        max_w = spec.max_angular_vel_radps
        cmd.vx_mps = max(-max_v, min(max_v, cmd.vx_mps))
        cmd.vy_mps = max(-max_v, min(max_v, cmd.vy_mps))
        cmd.vz_mps = max(-max_v, min(max_v, cmd.vz_mps))
        cmd.yaw_rate_radps = max(-max_w, min(max_w, cmd.yaw_rate_radps))

        return cmd


class CommandArbitrator:
    def __init__(self, validator: DynamicSafetyValidator):
        self.validator = validator
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.active_priorities: Dict[str, CommandPriority] = {}

    async def submit_command(
        self,
        raw_cmd: UnifiedCommand,
        dispatch_callback: Callable[[UnifiedCommand], Coroutine],
    ) -> bool:
        target = raw_cmd.target_id
        current_prio = self.active_priorities.get(target, CommandPriority.VOICE_NLU)

        # 현재 실행 중인 명령보다 우선순위가 낮으면 거부 (수동 조작 중 음성 명령 차단)
        if target in self.active_tasks and not self.active_tasks[target].done():
            if raw_cmd.priority > current_prio:
                print(
                    f"[REJECT] {target}: 상위 우선순위({current_prio.name}) 제어 중이므로 "
                    f"{raw_cmd.source} 명령 거부"
                )
                return False
            else:
                print(
                    f"[PREEMPT] {target}: {raw_cmd.source} 명령으로 기존 작업 즉시 중단"
                )
                self.active_tasks[target].cancel()

        # 안전 검증 및 속도 Clamping 수행
        safe_cmd = self.validator.validate_and_clamp(raw_cmd)
        self.active_priorities[target] = safe_cmd.priority

        # 하드웨어 브릿지로 비동기 디스패치
        task = asyncio.create_task(dispatch_callback(safe_cmd))
        self.active_tasks[target] = task
        return True
