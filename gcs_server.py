import asyncio
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

import yaml
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from core_arbitrator import (
    CommandArbitrator,
    CommandPriority,
    DynamicSafetyValidator,
    HardwareSpec,
    UnifiedCommand,
)
from bridge.hardware_bridges import (
    ROS2_AVAILABLE,
    DroneHybridBridgeNode,
    RobotRos2BridgeNode,
)
from voice.voice_command_engine import VoiceIntentParser

if ROS2_AVAILABLE:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

SPEC_FILE_PATH = Path("config/hardware_profiles.yaml")

DEFAULT_SPECS: Dict[str, HardwareSpec] = {
    "drone_1": HardwareSpec(
        device_id="drone_1",
        device_type="drone",
        environment="sitl",
        max_altitude_m=30.0,
        min_altitude_m=1.0,
        max_linear_vel_mps=5.0,
        max_angular_vel_radps=1.5,
        min_battery_percent=20.0,
        capabilities=["ESTOP", "ARM", "TAKEOFF", "LAND", "HOLD", "MOVE_VEL", "RTL"],
    ),
    "robot_1": HardwareSpec(
        device_id="robot_1",
        device_type="robot",
        environment="sitl",
        max_altitude_m=0.0,
        min_altitude_m=0.0,
        max_linear_vel_mps=1.5,
        max_angular_vel_radps=1.2,
        min_battery_percent=15.0,
        capabilities=["ESTOP", "HOLD", "MOVE_VEL", "NAV_TO_POSE"],
    ),
    "hybrid_drone_1": HardwareSpec(
        device_id="hybrid_drone_1",
        device_type="hybrid_fixed_wing_fpv",
        environment="sitl",
        max_altitude_m=500.0,
        min_altitude_m=10.0,
        max_linear_vel_mps=80.0,
        max_angular_vel_radps=3.0,
        min_battery_percent=25.0,
        max_dive_angle_deg=80.0,
        max_dive_speed_mps=80.0,
        min_pullup_altitude_m=30.0,
        max_deception_duration_sec=60,
        deception_patterns=[
            "SPIRAL_DIVE",
            "SINE_DIVE",
            "RANDOM_JINK",
            "FAKE_CRASH",
            "MULTI_PULSE",
        ],
        capabilities=[
            "ESTOP",
            "ARM",
            "TAKEOFF",
            "LAND",
            "HOLD",
            "MOVE_VEL",
            "RTL",
            "SET_MODE",
            "DIVE_ATTACK",
            "DECEPTION_START",
            "DECEPTION_PATTERN",
            "DECEPTION_STOP",
            "TRANSITION_CRUISE_TO_FPV",
            "TRANSITION_FPV_TO_CRUISE",
        ],
    ),
}


def load_or_init_specs() -> Dict[str, HardwareSpec]:
    SPEC_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SPEC_FILE_PATH.exists():
        with open(SPEC_FILE_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
            return {k: HardwareSpec(**v) for k, v in raw.items()}
    save_specs_to_yaml(DEFAULT_SPECS)
    return DEFAULT_SPECS


def save_specs_to_yaml(specs: Dict[str, HardwareSpec]) -> None:
    SPEC_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEC_FILE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {k: v.model_dump() for k, v in specs.items()},
            f,
            allow_unicode=True,
            sort_keys=False,
        )


class SystemContext:
    specs: Dict[str, HardwareSpec] = {}
    validator: DynamicSafetyValidator = None
    arbitrator = None
    voice_parser = None
    drone_node = None
    robot_node = None
    mode_manager = None
    trajectory_engine = None
    deception_engine = None
    log_aggregator = None
    risk_analyzer = None
    risk_arbitrator = None
    ros_executor = None
    ws_clients: List[WebSocket] = []
    event_logs: List[str] = []
    last_actions: Dict[str, str] = {
        "drone_1": "IDLE",
        "robot_1": "IDLE",
        "hybrid_drone_1": "IDLE",
    }

    @classmethod
    def log(cls, msg: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {msg}"
        print(entry)
        cls.event_logs.append(entry)
        if len(cls.event_logs) > 30:
            cls.event_logs.pop(0)


ctx = SystemContext()


async def dispatch_to_hardware(cmd: UnifiedCommand) -> None:
    ctx.last_actions[cmd.target_id] = f"{cmd.action} ({cmd.source})"
    ctx.log(
        f"[DISPATCH] {cmd.target_id} <- {cmd.action} (Prio:{cmd.priority.name}, Src:{cmd.source})"
    )
    try:
        if cmd.target_id == "drone_1" and ctx.drone_node:
            await ctx.drone_node.execute_command(cmd)
        elif cmd.target_id == "robot_1" and ctx.robot_node:
            await ctx.robot_node.execute_command(cmd)
        elif (
            cmd.target_id == "hybrid_drone_1"
            and hasattr(ctx, "hybrid_node")
            and ctx.hybrid_node
        ):
            await ctx.hybrid_node.execute_command(cmd)
        ctx.last_actions[cmd.target_id] = "IDLE (Completed)"
    except asyncio.CancelledError:
        ctx.last_actions[cmd.target_id] = "PREEMPTED (중단됨)"
        ctx.log(
            f"[PREEMPTED] {cmd.target_id} 기존 작업이 상위 명령에 의해 즉시 취소되었습니다."
        )
        raise
    except Exception as e:
        ctx.last_actions[cmd.target_id] = f"ERROR: {e}"
        ctx.log(f"[ERROR] {cmd.target_id} 실행 오류: {e}")


async def telemetry_and_watchdog_loop() -> None:
    while True:
        await asyncio.sleep(0.2)
        now = time.monotonic()

        # 드론 하트비트 체크
        drone_hb_age = (
            now - ctx.drone_node.last_heartbeat_time if ctx.drone_node else 999.0
        )
        drone_online = bool(
            ctx.drone_node and ctx.drone_node.is_connected and (drone_hb_age <= 5.0)
        )

        # 하이브리드 드론 하트비트 체크
        hybrid_hb_age = 999.0
        hybrid_online = False
        if hasattr(ctx, "hybrid_node") and ctx.hybrid_node:
            hybrid_hb_age = now - ctx.hybrid_node.last_heartbeat_time
            hybrid_online = bool(
                ctx.hybrid_node.is_connected and (hybrid_hb_age <= 5.0)
            )

        # 위험도 정보
        current_risk = None
        if ctx.risk_arbitrator:
            current_risk = ctx.risk_arbitrator.get_current_risk()

        # 모드 정보
        current_mode = "CRUISE"
        if hasattr(ctx, "mode_manager") and ctx.mode_manager:
            current_mode = ctx.mode_manager.get_current_mode().value

        telemetry_payload = {
            "timestamp": time.strftime("%H:%M:%S"),
            "mode": current_mode,
            "risk": (
                {
                    "level": current_risk.risk_level if current_risk else "UNKNOWN",
                    "categories": current_risk.risk_categories if current_risk else [],
                    "confidence": current_risk.confidence if current_risk else 0.0,
                    "reasoning": current_risk.reasoning if current_risk else "",
                }
                if current_risk
                else None
            ),
            "devices": {
                "drone_1": {
                    "environment": ctx.specs["drone_1"].environment,
                    "connected": drone_online,
                    "heartbeat_ms": (
                        round(drone_hb_age * 1000, 1) if drone_hb_age < 100 else -1
                    ),
                    "active_priority": ctx.arbitrator.active_priorities.get(
                        "drone_1", CommandPriority.VOICE_NLU
                    ).name,
                    "current_action": ctx.last_actions.get("drone_1", "IDLE"),
                    "limits": {
                        "max_alt": ctx.specs["drone_1"].max_altitude_m,
                        "max_vel": ctx.specs["drone_1"].max_linear_vel_mps,
                    },
                },
                "robot_1": {
                    "environment": ctx.specs["robot_1"].environment,
                    "connected": True,
                    "heartbeat_ms": 20.0,
                    "active_priority": ctx.arbitrator.active_priorities.get(
                        "robot_1", CommandPriority.VOICE_NLU
                    ).name,
                    "current_action": ctx.last_actions.get("robot_1", "IDLE"),
                    "limits": {
                        "max_vel": ctx.specs["robot_1"].max_linear_vel_mps,
                        "max_omega": ctx.specs["robot_1"].max_angular_vel_radps,
                    },
                },
            },
            "logs": ctx.event_logs[-12:],
        }

        if hasattr(ctx, "hybrid_node") and ctx.hybrid_node:
            hybrid_spec = ctx.specs.get("hybrid_drone_1")
            telemetry_payload["devices"]["hybrid_drone_1"] = {
                "environment": hybrid_spec.environment if hybrid_spec else "sitl",
                "connected": hybrid_online,
                "heartbeat_ms": (
                    round(hybrid_hb_age * 1000, 1) if hybrid_hb_age < 100 else -1
                ),
                "active_priority": ctx.arbitrator.active_priorities.get(
                    "hybrid_drone_1", CommandPriority.VOICE_NLU
                ).name,
                "current_action": ctx.last_actions.get("hybrid_drone_1", "IDLE"),
                "mode": current_mode,
                "limits": (
                    {
                        "max_alt": hybrid_spec.max_altitude_m if hybrid_spec else 500.0,
                        "max_vel": (
                            hybrid_spec.max_linear_vel_mps if hybrid_spec else 80.0
                        ),
                        "max_dive_speed": (
                            hybrid_spec.max_dive_speed_mps if hybrid_spec else 80.0
                        ),
                        "max_dive_angle": (
                            hybrid_spec.max_dive_angle_deg if hybrid_spec else 80.0
                        ),
                    }
                    if hybrid_spec
                    else {}
                ),
            }

        dead_clients = []
        for ws in ctx.ws_clients:
            try:
                await ws.send_json(telemetry_payload)
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            ctx.ws_clients.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ROS2_AVAILABLE:
        rclpy.init()

    ctx.specs = load_or_init_specs()
    ctx.validator = DynamicSafetyValidator(ctx.specs)
    ctx.arbitrator = CommandArbitrator(ctx.validator)
    ctx.voice_parser = VoiceIntentParser()

    # 로그 어그리게이터 & LLM 위험 분석기 초기화
    from core.log_aggregator import LogAggregator
    from core.llm_risk_analyzer import LocalLLMRiskAnalyzer
    from core.risk_aware_arbitrator import RiskAwareArbitrator
    from core.mode_manager import HybridModeManager
    from core.trajectory_engine import TrajectoryEngine
    from core.deception_engine import DeceptionEngine

    ctx.log_aggregator = LogAggregator()
    ctx.validator = DynamicSafetyValidator(ctx.specs)

    # LLM 위험 분석기 (모델 경로 확인)
    model_path = "~/models/llama-3.1-8b-q4_k_m.gguf"
    ctx.risk_analyzer = LocalLLMRiskAnalyzer(model_path=model_path)
    ctx.risk_arbitrator = RiskAwareArbitrator(
        ctx.validator, ctx.log_aggregator, ctx.risk_analyzer
    )
    ctx.arbitrator = ctx.risk_arbitrator  # 호환성

    ctx.voice_parser = VoiceIntentParser()

    ctx.mode_manager = HybridModeManager(ctx.specs, ctx.risk_arbitrator)
    ctx.trajectory_engine = TrajectoryEngine(ctx.specs)
    ctx.deception_engine = DeceptionEngine(ctx.specs, ctx.trajectory_engine)

    # 노드 초기화
    ctx.drone_node = DroneHybridBridgeNode(
        ctx.specs["drone_1"],
        mavsdk_uri="udp://:14540",
        log_aggregator=ctx.log_aggregator,
    )
    ctx.robot_node = RobotRos2BridgeNode(
        ctx.specs["robot_1"], log_aggregator=ctx.log_aggregator
    )

    # 하이브리드 드론 노드 (새로 추가)
    from bridge.hardware_bridges import DroneHybridBridgeNode

    ctx.hybrid_node = DroneHybridBridgeNode(
        ctx.specs["hybrid_drone_1"],
        mavsdk_uri="udp://:14540",
        log_aggregator=ctx.log_aggregator,
    )
    # trajectory_engine과 deception_engine 연결
    ctx.hybrid_node.trajectory_engine = ctx.trajectory_engine
    ctx.hybrid_node.deception_engine = ctx.deception_engine

    if ROS2_AVAILABLE:
        ctx.ros_executor = MultiThreadedExecutor(num_threads=4)
        ctx.ros_executor.add_node(ctx.drone_node)
        ctx.ros_executor.add_node(ctx.robot_node)
        if hasattr(ctx, "hybrid_node") and ctx.hybrid_node:
            ctx.ros_executor.add_node(ctx.hybrid_node)
        spin_thread = threading.Thread(target=ctx.ros_executor.spin, daemon=True)
        spin_thread.start()

    # 로그 스트리밍 시작
    if ctx.drone_node:
        await ctx.drone_node.start_log_streaming()
    if ctx.robot_node:
        await ctx.robot_node.start_log_streaming()
    if hasattr(ctx, "hybrid_node") and ctx.hybrid_node:
        await ctx.hybrid_node.start_log_streaming()

    # 위험 모니터링 시작
    await ctx.risk_arbitrator.start_risk_monitoring()

    # 텔레메트리/워치독 루프
    bg_task = asyncio.create_task(telemetry_and_watchdog_loop())
    ctx.log("하이브리드 제어 시스템(GCS + Arbitrator + Bridges + LLM Risk) 가동 완료.")

    yield

    bg_task.cancel()
    if ROS2_AVAILABLE and ctx.ros_executor:
        ctx.ros_executor.shutdown()
        rclpy.shutdown()


app = FastAPI(title="Drone & Robot Hybrid Control GCS", lifespan=lifespan)


class VoiceTextRequest(BaseModel):
    text: str
    confidence: float = 0.95
    active_target: str = "drone_1"


class HybridCommandRequest(BaseModel):
    target_id: str
    action: Literal[
        "SET_MODE",
        "DIVE_ATTACK",
        "DECEPTION_START",
        "DECEPTION_PATTERN",
        "DECEPTION_STOP",
        "TRANSITION_CRUISE_TO_FPV",
        "TRANSITION_FPV_TO_CRUISE",
    ]
    params: dict = {}


@app.post("/api/command")
async def send_manual_command(cmd: UnifiedCommand):
    try:
        accepted = await ctx.arbitrator.submit_command(cmd, dispatch_to_hardware)
        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="상위 우선순위 작업이 실행 중이어서 명령이 거부되었습니다.",
            )
        return {"status": "accepted", "command_id": cmd.command_id}
    except ValueError as e:
        ctx.log(f"[SAFETY REJECT] {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/hybrid/command")
async def send_hybrid_command(cmd: HybridCommandRequest):
    try:
        # HybridCommandRequest를 UnifiedCommand로 변환
        cmd_map = {
            "SET_MODE": ("SET_MODE", {"mode": cmd.params.get("mode")}),
            "DIVE_ATTACK": (
                "DIVE_ATTACK",
                {
                    "target_alt": cmd.params.get("target_alt", 100),
                    "angle": cmd.params.get("angle", 70),
                },
            ),
            "DECEPTION_START": (
                "DECEPTION_START",
                {
                    "pattern": cmd.params.get("pattern", "SINE_DIVE"),
                    "duration": cmd.params.get("duration", 30),
                },
            ),
            "DECEPTION_PATTERN": (
                "DECEPTION_PATTERN",
                {"pattern": cmd.params.get("pattern")},
            ),
            "DECEPTION_STOP": ("DECEPTION_STOP", {}),
            "TRANSITION_CRUISE_TO_FPV": ("SET_MODE", {"mode": "FPV_AGILE"}),
            "TRANSITION_FPV_TO_CRUISE": ("SET_MODE", {"mode": "CRUISE"}),
        }

        action, params = cmd_map.get(cmd.action, (cmd.action, cmd.params))

        cmd_obj = UnifiedCommand(
            command_id=str(uuid.uuid4()),
            source="MANUAL_SW",
            priority=CommandPriority.MANUAL_SW,
            target_id=cmd.target_id,
            action=action,
            **params,
        )

        accepted = await ctx.arbitrator.submit_command(cmd_obj, dispatch_to_hardware)
        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="상위 우선순위 작업이 실행 중이어서 명령이 거부되었습니다.",
            )
        return {"status": "accepted", "command_id": cmd_obj.command_id}
    except ValueError as e:
        ctx.log(f"[SAFETY REJECT] {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/voice")
async def send_voice_command(req: VoiceTextRequest):
    try:
        ctx.log(f"[VOICE INPUT] '{req.text}' (신뢰도: {req.confidence:.2f})")
        cmd = await ctx.voice_parser.parse_to_command(
            text=req.text,
            stt_confidence=req.confidence,
            active_target=req.active_target,
        )
        accepted = await ctx.arbitrator.submit_command(cmd, dispatch_to_hardware)
        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="수동 제어(상위 우선순위) 중이므로 음성 명령이 차단되었습니다.",
            )
        return {"status": "accepted", "parsed_command": cmd.model_dump()}
    except ValueError as e:
        ctx.log(f"[VOICE REJECT] {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/specs")
async def get_all_specs():
    return {k: v.model_dump() for k, v in ctx.specs.items()}


@app.put("/api/specs/{device_id}")
async def update_device_spec(device_id: str, new_spec: HardwareSpec):
    ctx.specs[device_id] = new_spec
    ctx.validator.update_spec(device_id, new_spec)
    save_specs_to_yaml(ctx.specs)
    ctx.log(
        f"[SPEC HOT-RELOAD] {device_id} 스펙 갱신 완료 "
        f"(환경:{new_spec.environment}, 최대속도:{new_spec.max_linear_vel_mps}m/s)"
    )
    return {"status": "updated", "spec": new_spec.model_dump()}


# === Risk API 엔드포인트 ===
@app.get("/api/risk/status")
async def get_risk_status():
    risk = ctx.risk_arbitrator.get_current_risk() if ctx.risk_arbitrator else None
    if not risk:
        return {"status": "NO_RISK_DATA"}

    return {
        "risk_level": risk.risk_level,
        "risk_categories": risk.risk_categories,
        "confidence": risk.confidence,
        "reasoning": risk.reasoning,
        "recommended_actions": risk.recommended_actions,
        "auto_execute": risk.auto_execute,
        "inference_ms": risk.inference_ms,
        "timestamp": time.time(),
    }


@app.get("/api/risk/history")
async def get_risk_history():
    # 최근 위험도 이력 반환 (구현 필요)
    return {"history": []}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(ws: WebSocket):
    await ws.accept()
    ctx.ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in ctx.ws_clients:
            ctx.ws_clients.remove(ws)


# === 대시보드 HTML (Risk Dashboard 포함) ===
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>Drone & Robot Hybrid GCS</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 16px; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px; }
    .estop-btn { background: #dc2626; color: white; font-size: 18px; font-weight: bold; border: 2px solid #f87171; padding: 12px 28px; border-radius: 8px; cursor: pointer; }
    .estop-btn:hover { background: #b91c1c; }
    .grid { display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 16px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }
    h3 { margin-top: 0; color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 8px; }
    .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    button { background: #2563eb; color: white; border: none; padding: 10px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; }
    button:hover { background: #1d4ed8; }
    button.secondary { background: #475569; }
    input, select { background: #0f172a; color: white; border: 1px solid #475569; padding: 8px; border-radius: 6px; width: 100%; box-sizing: border-box; margin-bottom: 8px; }
    .log-box { background: #020617; font-family: monospace; font-size: 12px; height: 220px; overflow-y: auto; padding: 10px; border-radius: 6px; border: 1px solid #334155; }
    .badge { padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; background: #334155; }
    .risk-critical { background: #dc2626 !important; }
    .risk-high { background: #ea580c !important; }
    .risk-medium { background: #ca8a04 !important; }
    .risk-low { background: #16a34a !important; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h2 style="margin:0;">드론(MAVSDK/MAVROS2) & 로봇(ROS2) & 하이브리드 드론 통합 관제 시스템</h2>
      <small style="color:#94a3b8;">SpecKit Architecture: FAILSAFE(P0) > MANUAL_SW(P1) > VOICE_NLU(P2) | LLM Risk Analysis</small>
    </div>
    <button class="estop-btn" onclick="triggerEStop()">긴급 정지 (ALL E-STOP / Priority 0)</button>
  </div>

  <div class="grid">
    <div class="card">
      <h3>1. 실시간 상태 & 우선순위 모니터</h3>
      <div id="telemetry-view">연결 대기 중...</div>
      <h4 style="margin-top:16px; margin-bottom:6px; color:#94a3b8;">중재기(Arbitrator) 실시간 로그</h4>
      <div id="log-box" class="log-box"></div>
    </div>

    <div class="card">
      <h3>2. 수동 제어 SW (Priority 1) & 음성 인식 (Priority 2) & 하이브리드 제어</h3>
      <label>제어 대상 기체 선택 (Active Target)</label>
      <select id="target-select">
        <option value="drone_1">drone_1 (MAVSDK + MAVROS2 Hybrid)</option>
        <option value="robot_1">robot_1 (ROS2 Twist + Nav2)</option>
        <option value="hybrid_drone_1">hybrid_drone_1 (Hybrid Fixed-wing + FPV)</option>
      </select>

      <h4>[기본 제어 SW] 수동 조작 (음성 미션 즉시 선점/취소)</h4>
      <div class="btn-group">
        <button onclick="sendManual('ARM')">시동 (ARM)</button>
        <button onclick="sendManual('TAKEOFF', {z_m: 3.0})">이륙 (3m)</button>
        <button onclick="sendManual('HOLD')">일시정지 (HOLD)</button>
        <button onclick="sendManual('LAND')">착륙 (LAND)</button>
        <button onclick="sendManual('RTL')">복귀 (RTL)</button>
      </div>
      <div class="btn-group">
        <button onclick="sendManual('MOVE_VEL', {vx_mps: 1.5})">전진 (+1.5m/s)</button>
        <button onclick="sendManual('MOVE_VEL', {vx_mps: -1.5})">후진 (-1.5m/s)</button>
        <button onclick="sendManual('MOVE_VEL', {yaw_rate_radps: 0.5})">좌회전</button>
        <button onclick="sendManual('MOVE_VEL', {yaw_rate_radps: -0.5})">우회전</button>
      </div>

      <hr style="border-color:#334155; margin: 16px 0;">
      <h4>[하이브리드 드론 제어]</h4>
      <div class="btn-group">
        <button onclick="setHybridMode('CRUISE')" id="mode-cruise">✈️ 순항</button>
        <button onclick="setHybridMode('FPV_AGILE')" id="mode-fpv">🏎️ FPV 기동</button>
        <button onclick="setHybridMode('DIVE_ATTACK')" id="mode-dive">💥 다이브</button>
        <button onclick="setHybridMode('DECEPTION')" id="mode-deception">🎭 기만</button>
      </div>
      <div id="dive-params" style="display:none; margin-top:8px;">
        <input type="number" id="dive-alt" placeholder="시작 고도(m)" value="500" style="width:80px;">
        <input type="number" id="dive-angle" placeholder="다이브 각도(°)" value="70" style="width:80px;">
        <button onclick="startDive()">다이브 시작</button>
      </div>
      <div id="deception-params" style="display:none; margin-top:8px;">
        <select id="deception-pattern">
          <option value="AUTO">자동 (위협 분석)</option>
          <option value="SPIRAL_DIVE">나선형 다이브 (IR)</option>
          <option value="SINE_DIVE">사인파 다이브 (레이더)</option>
          <option value="RANDOM_JINK">랜덤 진크 (예측필터)</option>
          <option value="FAKE_CRASH">추락 위장 (광학)</option>
          <option value="MULTI_PULSE">다중 펄스 (멀티센서)</option>
        </select>
        <input type="number" id="deception-duration" placeholder="지속시간(초)" value="30" style="width:80px;">
        <button onclick="startDeception()">기만 시작</button>
        <button onclick="stopDeception()" class="secondary">기만 종료</button>
      </div>

      <hr style="border-color:#334155; margin: 16px 0;">
      <h4>[음성 명령 엔진] Push-to-Talk & 자연어 입력</h4>
      <input type="text" id="voice-input" placeholder="예: 드론 1번 5미터 이륙해 / 로봇 앞으로 1.2 속도로 전진 / 하이브리드 드론 다이브 어택 / 기만 모드 사인파 다이브 / 비상정지 / 위험 상태">
      <div class="btn-group">
        <button onclick="sendVoiceText()">음성 텍스트 전송 (STT->NLU 실행)</button>
        <button class="secondary" onclick="startWebSpeech()">마이크 음성 인식 (Push-to-Talk)</button>
      </div>
    </div>

    <div class="card">
      <h3>3. 실시간 위험 분석 (Local LLM)</h3>
      <div class="status-row">
        <div>위험도: <span class="badge" id="risk-level">대기 중</span></div>
        <div>신뢰도: <span id="risk-confidence">-</span></div>
        <div>추론 시간: <span id="inference-ms">-</span>ms</div>
      </div>
      <div style="margin-top:8px;">
        <strong>판단 근거:</strong>
        <div id="risk-reasoning" style="font-size:12px; color:#94a3b8;">대기 중...</div>
      </div>
      <div style="margin-top:8px;">
        <strong>권장 조치:</strong>
        <div id="risk-actions" style="font-size:12px;"></div>
      </div>
      <div style="margin-top:8px;">
        <strong>자동 실행:</strong>
        <div id="risk-auto" style="font-size:12px;"></div>
      </div>
    </div>

    <div class="card">
      <h3>4. 하드웨어 스펙 실시간 입력/수정 (HAL)</h3>
      <label>대상 기체</label>
      <select id="spec-device" onchange="loadSpecForm()">
        <option value="drone_1">drone_1</option>
        <option value="robot_1">robot_1</option>
        <option value="hybrid_drone_1">hybrid_drone_1</option>
      </select>
      <label>구동 환경 (SITL 시뮬레이션 vs 실제 장비)</label>
      <select id="spec-env">
        <option value="sitl">sitl (PX4/ArduPilot Gazebo 시뮬레이터)</option>
        <option value="real">real (실제 드론 FC / 실물 ROS2 로봇)</option>
      </select>
      <label>최대 허용 고도 (m, 드론/하이브리드 전용)</label>
      <input type="number" step="0.5" id="spec-max-alt" value="30.0">
      <label>최대 선속도 상한선 (m/s)</label>
      <input type="number" step="0.1" id="spec-max-vel" value="5.0">
      <label>최대 각속도 상한선 (rad/s)</label>
      <input type="number" step="0.1" id="spec-max-omega" value="1.5">
      <label>최소 배터리 임계치 (%)</label>
      <input type="number" step="1" id="spec-min-bat" value="20.0">
      <label>최대 다이브 각도 (°, 하이브리드 전용)</label>
      <input type="number" step="1" id="spec-max-dive-angle" value="80.0">
      <label>최대 다이브 속도 (m/s, 하이브리드 전용)</label>
      <input type="number" step="1" id="spec-max-dive-speed" value="80.0">
      <label>최소 풀업 고도 (m, 하이브리드 전용)</label>
      <input type="number" step="1" id="spec-min-pullup" value="30.0">
      <label>최대 기만 지속시간 (초, 하이브리드 전용)</label>
      <input type="number" step="1" id="spec-max-deception" value="60.0">
      <button style="width:100%; margin-top:8px; background:#059669;" onclick="updateSpec()">
        스펙 즉시 적용 및 YAML 저장 (Hot-Reload)
      </button>
    </div>
  </div>

  <script>
    let cachedSpecs = {};

    const ws = new WebSocket(`ws://${location.host}/ws/telemetry`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      let html = "";
      for (const [id, dev] of Object.entries(data.devices)) {
        html += `<div style="margin-bottom:10px; padding:10px; background:#0f172a; border-radius:6px;">
          <strong>${id.toUpperCase()}</strong> <span class="badge">${dev.environment?.toUpperCase() || "UNKNOWN"}</span>
          <div>연결 상태: ${dev.connected ? "ONLINE" : "WAITING/OFFLINE"} (HB: ${dev.heartbeat_ms}ms)</div>
          <div>현재 제어권: <strong>${dev.active_priority}</strong></div>
          <div>실행 상태: <span style="color:#38bdf8;">${dev.current_action}</span></div>
          <div style="font-size:12px; color:#94a3b8;">안전 한계: 최대속도 ${dev.limits?.max_vel || dev.limits?.max_vel}m/s</div>
        </div>`;
      }
      document.getElementById("telemetry-view").innerHTML = html;
      const logBox = document.getElementById("log-box");
      logBox.innerHTML = data.logs.join("<br>");
      logBox.scrollTop = logBox.scrollHeight;

      // 위험도 업데이트
      if (data.risk) {
        const level = data.risk.level;
        document.getElementById('risk-level').textContent = level;
        document.getElementById('risk-level').className = 'badge risk-' + level.toLowerCase();
        document.getElementById('risk-confidence').textContent = (data.risk.confidence * 100).toFixed(0) + '%';
        document.getElementById('inference-ms').textContent = data.risk.inference_ms ? data.risk.inference_ms.toFixed(0) : '-';
        document.getElementById('risk-reasoning').textContent = data.risk.reasoning || '-';
        document.getElementById('risk-actions').innerHTML = (data.risk.recommended_actions || []).map(a =>
          `<span class="badge" style="background:${a.priority==='IMMEDIATE'?'#dc2626':a.priority==='HIGH'?'#ea580c':'#3b82f6'}">${a.action} (${a.priority})</span>`).join(' ');
        document.getElementById('risk-auto').textContent = data.risk.auto_execute ? data.risk.auto_execute.join(', ') : '없음';
      }
    };

    async function sendManual(action, params = {}) {
      const target = document.getElementById("target-select").value;
      const payload = {
        command_id: crypto.randomUUID(),
        source: "MANUAL_SW",
        priority: 1,
        target_id: target,
        action: action,
        ...params
      };

      const res = await fetch("/api/command", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      if (!res.ok) alert(await res.text());
    }

    async function triggerEStop() {
      for (const target of ["drone_1", "robot_1", "hybrid_drone_1"]) {
        await fetch("/api/command", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            command_id: crypto.randomUUID(),
            source: "FAILSAFE",
            priority: 0,
            target_id: target,
            action: "ESTOP"
          })
        });
      }
    }

    async function sendVoiceText() {
      const text = document.getElementById("voice-input").value;
      const target = document.getElementById("target-select").value;
      if (!text) return;
      const res = await fetch("/api/voice", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: text, confidence: 0.95, active_target: target})
      });
      if (!res.ok) alert(await res.text());
    }

    function setHybridMode(mode) {
      document.getElementById("dive-params").style.display = mode === "DIVE_ATTACK" ? "block" : "none";
      document.getElementById("deception-params").style.display = mode === "DECEPTION" ? "block" : "none";
      fetch("/api/hybrid/mode", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode, trigger: "MANUAL"})
      });
    }

    function startDive() {
      const alt = parseFloat(document.getElementById('dive-alt').value);
      const angle = parseFloat(document.getElementById('dive-angle').value);
      sendHybridCmd('DIVE_ATTACK', {target_alt: alt, angle: angle});
    }

    function startDeception() {
      const pattern = document.getElementById('deception-pattern').value;
      const duration = parseFloat(document.getElementById('deception-duration').value);
      sendHybridCmd('DECEPTION_START', {pattern, duration});
    }

    function stopDeception() {
      sendHybridCmd('DECEPTION_STOP', {});
    }

    async function sendHybridCmd(action, params) {
      const target = document.getElementById("target-select").value;
      const res = await fetch("/api/hybrid/command", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({target_id: target, action, params})
      });
      if (!res.ok) alert(await res.text());
    }

    async function sendVoiceText() {
      const text = document.getElementById("voice-input").value;
      const target = document.getElementById("target-select").value;
      if (!text) return;
      const res = await fetch("/api/voice", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: text, confidence: 0.95, active_target: target})
      });
      if (!res.ok) alert(await res.text());
    }

    async function startWebSpeech() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return alert("브라우저가 Web Speech API를 지원하지 않습니다. 텍스트 입력창을 사용해 주세요.");
      const rec = new SpeechRecognition();
      rec.lang = "ko-KR";
      rec.onresult = (e) => {
        document.getElementById("voice-input").value = e.results[0][0].transcript;
        sendVoiceText();
      };
      rec.start();
    }

    async function fetchSpecs() {
      const res = await fetch("/api/specs");
      cachedSpecs = await res.json();
      loadSpecForm();
    }

    function loadSpecForm() {
      const id = document.getElementById("spec-device").value;
      const s = cachedSpecs[id];
      if (!s) return;
      document.getElementById("spec-env").value = s.environment;
      document.getElementById("spec-max-alt").value = s.max_altitude_m || 0;
      document.getElementById("spec-max-vel").value = s.max_linear_vel_mps || 0;
      document.getElementById("spec-max-omega").value = s.max_angular_vel_radps || 0;
      document.getElementById("spec-min-bat").value = s.min_battery_percent || 0;
      document.getElementById("spec-max-dive-angle").value = s.max_dive_angle_deg || 0;
      document.getElementById("spec-max-dive-speed").value = s.max_dive_speed_mps || 0;
      document.getElementById("spec-min-pullup").value = s.min_pullup_altitude_m || 0;
      document.getElementById("spec-max-deception").value = s.max_deception_duration_sec || 0;
    }

    async function updateSpec() {
      const id = document.getElementById("spec-device").value;
      const current = cachedSpecs[id];
      const updated = {
        ...current,
        environment: document.getElementById("spec-env").value,
        max_altitude_m: parseFloat(document.getElementById("spec-max-alt").value),
        max_linear_vel_mps: parseFloat(document.getElementById("spec-max-vel").value),
        max_angular_vel_radps: parseFloat(document.getElementById("spec-max-omega").value),
        min_battery_percent: parseFloat(document.getElementById("spec-min-bat").value),
        max_dive_angle_deg: parseFloat(document.getElementById("spec-max-dive-angle").value),
        max_dive_speed_mps: parseFloat(document.getElementById("spec-max-dive-speed").value),
        min_pullup_altitude_m: parseFloat(document.getElementById("spec-min-pullup").value),
        max_deception_duration_sec: parseFloat(document.getElementById("spec-max-deception").value)
      };

      const res = await fetch(`/api/specs/${id}`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(updated)
      });
      if (res.ok) fetchSpecs();
    }

    fetchSpecs();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return DASHBOARD_HTML
