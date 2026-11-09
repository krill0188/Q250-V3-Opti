import asyncio
import pytest
from unittest.mock import MagicMock, patch

from core.deception_engine import DeceptionEngine, DeceptionPattern, ThreatProfile
from core.trajectory_engine import TrajectoryEngine
from core_arbitrator import HardwareSpec


@pytest.fixture
def hybrid_specs():
    return {
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
            capabilities=["DECEPTION_START", "DECEPTION_PATTERN", "DECEPTION_STOP"],
        ),
    }


@pytest.fixture
def trajectory_engine(hybrid_specs):
    return TrajectoryEngine(hybrid_specs)


@pytest.fixture
def deception_engine(hybrid_specs, trajectory_engine):
    return DeceptionEngine(hybrid_specs, trajectory_engine)


class TestDeceptionEnginePatterns:
    """기만 패턴별 실행 테스트"""

    @pytest.mark.asyncio
    async def test_spiral_dive_execution(self, deception_engine):
        """나선형 다이브 실행 테스트"""
        success = await deception_engine.start_deception(
            DeceptionPattern.SPIRAL_DIVE, duration=0.5
        )
        assert success is True
        assert deception_engine.is_active()
        assert deception_engine.get_active_pattern() == DeceptionPattern.SPIRAL_DIVE

        await asyncio.sleep(0.1)
        await deception_engine.stop_deception()
        assert not deception_engine.is_active()

    @pytest.mark.asyncio
    async def test_sine_dive_execution(self, deception_engine):
        """사인파 다이브 실행 테스트"""
        success = await deception_engine.start_deception(
            DeceptionPattern.SINE_DIVE, duration=0.5
        )
        assert success is True
        assert deception_engine.get_active_pattern() == DeceptionPattern.SINE_DIVE
        await deception_engine.stop_deception()

    @pytest.mark.asyncio
    async def test_random_jink_execution(self, deception_engine):
        """랜덤 진크 실행 테스트"""
        success = await deception_engine.start_deception(
            DeceptionPattern.RANDOM_JINK, duration=0.5
        )
        assert success is True
        assert deception_engine.get_active_pattern() == DeceptionPattern.RANDOM_JINK
        await deception_engine.stop_deception()

    @pytest.mark.asyncio
    async def test_fake_crash_execution(self, deception_engine):
        """추락 위장 실행 테스트"""
        success = await deception_engine.start_deception(
            DeceptionPattern.FAKE_CRASH, duration=0.5
        )
        assert success is True
        assert deception_engine.get_active_pattern() == DeceptionPattern.FAKE_CRASH
        await deception_engine.stop_deception()

    @pytest.mark.asyncio
    async def test_multi_pulse_execution(self, deception_engine):
        """다중 펄스 실행 테스트"""
        success = await deception_engine.start_deception(
            DeceptionPattern.MULTI_PULSE, duration=0.5
        )
        assert success is True
        assert deception_engine.get_active_pattern() == DeceptionPattern.MULTI_PULSE
        await deception_engine.stop_deception()


class TestDeceptionEngineAutoSelect:
    """자동 패턴 선택 테스트"""

    @pytest.mark.asyncio
    async def test_ir_missile_threat_selects_spiral(self, deception_engine):
        """IR 미사일 위협 -> SPIRAL_DIVE 선택"""
        threat = ThreatProfile(
            threat_type="IR_MISSILE", confidence=0.9, bearing=45.0, distance=2000.0
        )
        pattern = deception_engine._auto_select_pattern(threat)
        assert pattern == DeceptionPattern.SPIRAL_DIVE

    @pytest.mark.asyncio
    async def test_radar_threat_selects_sine(self, deception_engine):
        """레이더 위협 -> SINE_DIVE 선택"""
        threat = ThreatProfile(
            threat_type="RADAR", confidence=0.8, bearing=180.0, distance=5000.0
        )
        pattern = deception_engine._auto_select_pattern(threat)
        assert pattern == DeceptionPattern.SINE_DIVE

    @pytest.mark.asyncio
    async def test_optical_threat_selects_fake_crash(self, deception_engine):
        """광학 위협 -> FAKE_CRASH 선택"""
        threat = ThreatProfile(
            threat_type="OPTICAL", confidence=0.95, bearing=0.0, distance=1000.0
        )
        pattern = deception_engine._auto_select_pattern(threat)
        assert pattern == DeceptionPattern.FAKE_CRASH

    @pytest.mark.asyncio
    async def test_multi_sensor_threat_selects_multi_pulse(self, deception_engine):
        """멀티 센서 위협 -> MULTI_PULSE 선택"""
        threat = ThreatProfile(
            threat_type="MULTI", confidence=0.85, bearing=90.0, distance=3000.0
        )
        pattern = deception_engine._auto_select_pattern(threat)
        assert pattern == DeceptionPattern.MULTI_PULSE

    @pytest.mark.asyncio
    async def test_unknown_threat_defaults_to_random_jink(self, deception_engine):
        """알 수 없는 위협 -> RANDOM_JINK 기본 선택"""
        threat = ThreatProfile(
            threat_type="UNKNOWN_THREAT", confidence=0.5, bearing=0.0, distance=1000.0
        )
        pattern = deception_engine._auto_select_pattern(threat)
        assert pattern == DeceptionPattern.RANDOM_JINK

    @pytest.mark.asyncio
    async def test_auto_select_start_deception(self, deception_engine):
        """자동 선택으로 기만 시작"""
        threat = ThreatProfile(
            threat_type="IR_MISSILE", confidence=0.9, bearing=0.0, distance=1000.0
        )

        success = await deception_engine.start_deception(
            pattern=DeceptionPattern.SPIRAL_DIVE,  # 무시됨 (auto_select=True)
            duration=0.5,
            auto_select=True,
            threat_profile=ThreatProfile(
                threat_type="RADAR", confidence=0.8, bearing=0.0, distance=2000.0
            ),
        )
        assert success is True
        # 자동 선택된 패턴이 실행되어야 함 (RADAR -> SINE_DIVE)
        assert deception_engine.get_active_pattern() == DeceptionPattern.SINE_DIVE
        await deception_engine.stop_deception()


class TestDeceptionEngineConcurrency:
    """동시성/경합 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_start_rejected(self, deception_engine):
        """동시 기만 시작 거부 테스트"""
        # 첫 번째 기만 시작
        success1 = await deception_engine.start_deception(
            DeceptionPattern.SPIRAL_DIVE, duration=1.0
        )
        assert success1 is True

        # 두 번째 기만 시작 시도 (거부되어야 함)
        success2 = await deception_engine.start_deception(
            DeceptionPattern.SINE_DIVE, duration=1.0
        )
        assert success2 is False  # 이미 활성화된 기만 모드 있음

    @pytest.mark.asyncio
    async def test_stop_then_restart(self, deception_engine):
        """중지 후 재시작 가능 테스트"""
        await deception_engine.start_deception(
            DeceptionPattern.SPIRAL_DIVE, duration=1.0
        )
        await deception_engine.stop_deception()

        # 중지 후 재시작 가능
        success = await deception_engine.start_deception(
            DeceptionPattern.SINE_DIVE, duration=0.5
        )
        assert success is True
        await deception_engine.stop_deception()

    @pytest.mark.asyncio
    async def test_cancel_during_execution(self, deception_engine):
        """실행 중 취소 테스트"""
        task = asyncio.create_task(
            deception_engine.start_deception(DeceptionPattern.SPIRAL_DIVE, duration=5.0)
        )

        await asyncio.sleep(0.1)  # 실행 시작 대기
        await deception_engine.stop_deception()  # 강제 중지

        # 태스크가 취소되어야 함
        try:
            await task
        except asyncio.CancelledError:
            pass  # 정상 취소됨

        assert not deception_engine.is_active()


class TestDeceptionEngineEdgeCases:
    """예외 상황 테스트"""

    @pytest.mark.asyncio
    async def test_stop_when_not_active(self, deception_engine):
        """비활성 상태에서 stop 호출"""
        # 예외 없이 정상 종료되어야 함
        await deception_engine.stop_deception()
        assert not deception_engine.is_active()

    @pytest.mark.asyncio
    async def test_get_active_when_inactive(self, deception_engine):
        """비활성 상태에서 활성 패턴 조회"""
        pattern = deception_engine.get_active_pattern()
        assert pattern is None

    @pytest.mark.asyncio
    async def test_multiple_stop_calls(self, deception_engine):
        """연속 stop 호출 안전성"""
        await deception_engine.start_deception(
            DeceptionPattern.SPIRAL_DIVE, duration=1.0
        )
        await deception_engine.stop_deception()
        await deception_engine.stop_deception()  # 두 번 호출
        await deception_engine.stop_deception()  # 세 번 호출
        assert not deception_engine.is_active()
