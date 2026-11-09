import asyncio
import pytest

from core_arbitrator import (
    CommandArbitrator,
    CommandPriority,
    DynamicSafetyValidator,
    HardwareSpec,
    UnifiedCommand,
)
from voice.voice_command_engine import VoiceIntentParser


@pytest.fixture
def sample_specs():
    return {
        "drone_1": HardwareSpec(
            device_id="drone_1",
            device_type="drone",
            environment="sitl",
            max_altitude_m=20.0,
            min_altitude_m=1.0,
            max_linear_vel_mps=3.0,
            max_angular_vel_radps=1.0,
            capabilities=["ESTOP", "ARM", "TAKEOFF", "LAND", "HOLD", "MOVE_VEL", "RTL"],
        ),
        "robot_1": HardwareSpec(
            device_id="robot_1",
            device_type="robot",
            environment="sitl",
            max_linear_vel_mps=1.5,
            max_angular_vel_radps=1.2,
            capabilities=["ESTOP", "HOLD", "MOVE_VEL", "NAV_TO_POSE"],
        ),
    }


def test_altitude_validation_and_velocity_clamping(sample_specs):
    """허용 고도 초과 시 차단 및 최대 속도 초과 시 자동 Clamping 검증"""
    validator = DynamicSafetyValidator(sample_specs)

    unsafe_takeoff = UnifiedCommand(
        command_id="cmd-1",
        source="VOICE_NLU",
        priority=CommandPriority.VOICE_NLU,
        target_id="drone_1",
        action="TAKEOFF",
        z_m=50.0,
        confidence=0.95,
    )
    with pytest.raises(ValueError, match="이륙 고도"):
        validator.validate_and_clamp(unsafe_takeoff)

    over_speed_cmd = UnifiedCommand(
        command_id="cmd-2",
        source="VOICE_NLU",
        priority=CommandPriority.VOICE_NLU,
        target_id="drone_1",
        action="MOVE_VEL",
        vx_mps=10.0,
        vy_mps=-8.0,
        confidence=0.95,
    )
    clamped = validator.validate_and_clamp(over_speed_cmd)
    assert clamped.vx_mps == 3.0
    assert clamped.vy_mps == -3.0


def test_low_confidence_voice_rejection(sample_specs):
    """음성 인식 신뢰도(Confidence)가 0.85 미만일 때 명령 차단 검증"""
    validator = DynamicSafetyValidator(sample_specs)
    low_conf_cmd = UnifiedCommand(
        command_id="cmd-3",
        source="VOICE_NLU",
        priority=CommandPriority.VOICE_NLU,
        target_id="drone_1",
        action="TAKEOFF",
        z_m=3.0,
        confidence=0.60,
    )
    with pytest.raises(ValueError, match="신뢰도 부족"):
        validator.validate_and_clamp(low_conf_cmd)


@pytest.mark.asyncio
async def test_manual_control_preempts_voice_command(sample_specs):
    """음성 명령 실행 중 기본 제어 SW(수동 조작) 개입 시 즉시 선점 취소(Preemption) 검증"""
    validator = DynamicSafetyValidator(sample_specs)
    arbitrator = CommandArbitrator(validator)

    events = []

    async def mock_hardware_dispatch(cmd: UnifiedCommand):
        events.append(f"START:{cmd.source}:{cmd.action}")
        try:
            await asyncio.sleep(5.0)
            events.append(f"DONE:{cmd.source}:{cmd.action}")
        except asyncio.CancelledError:
            events.append(f"PREEMPTED:{cmd.source}:{cmd.action}")
            raise

    voice_cmd = UnifiedCommand(
        command_id="v-1",
        source="VOICE_NLU",
        priority=CommandPriority.VOICE_NLU,
        target_id="drone_1",
        action="MOVE_VEL",
        vx_mps=2.0,
        confidence=0.95,
    )
    accepted_v = await arbitrator.submit_command(voice_cmd, mock_hardware_dispatch)
    assert accepted_v is True
    await asyncio.sleep(0.05)

    manual_cmd = UnifiedCommand(
        command_id="m-1",
        source="MANUAL_SW",
        priority=CommandPriority.MANUAL_SW,
        target_id="drone_1",
        action="HOLD",
    )
    accepted_m = await arbitrator.submit_command(manual_cmd, mock_hardware_dispatch)
    assert accepted_m is True
    await asyncio.sleep(0.05)

    accepted_v2 = await arbitrator.submit_command(voice_cmd, mock_hardware_dispatch)
    assert accepted_v2 is False

    assert "START:VOICE_NLU:MOVE_VEL" in events
    assert "PREEMPTED:VOICE_NLU:MOVE_VEL" in events
    assert "START:MANUAL_SW:HOLD" in events


@pytest.mark.asyncio
async def test_fast_path_emergency_matcher():
    """비상 정지 및 즉시 착륙 음성 명령이 LLM 없이 최상위 우선순위로 변환되는지 검증"""
    from voice.voice_command_engine import VoiceIntentParser

    parser = VoiceIntentParser(llm_client=None)

    estop_cmd = await parser.parse_to_command(
        "드론 비상 정지", stt_confidence=0.50, active_target="drone_1"
    )
    assert estop_cmd.action == "ESTOP"
    assert estop_cmd.priority == CommandPriority.FAILSAFE_ESTOP
    assert estop_cmd.source == "FAILSAFE"

    land_cmd = await parser.parse_to_command(
        "즉시 착륙", stt_confidence=0.70, active_target="drone_1"
    )
    assert land_cmd.action == "LAND"
    assert land_cmd.priority == CommandPriority.FAILSAFE_ESTOP
    assert land_cmd.source == "FAILSAFE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
