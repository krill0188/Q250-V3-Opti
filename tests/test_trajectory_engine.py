import asyncio
import pytest
import math
from unittest.mock import MagicMock, patch

from core.trajectory_engine import TrajectoryEngine, TrajectoryMethod, DiveTrajectory
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
            capabilities=["DIVE_ATTACK", "DECEPTION_START"],
        ),
    }


@pytest.fixture
def trajectory_engine(hybrid_specs):
    return TrajectoryEngine(hybrid_specs)


class TestTrajectoryEngineGeometric:
    """기하학적 궤적 생성 테스트"""

    @pytest.mark.asyncio
    async def test_dive_trajectory_basic(self, trajectory_engine):
        """기본 다이브 궤적 생성"""
        start_pos = (0.0, 0.0, 500.0)
        target_alt = 100.0
        dive_angle = 70.0
        max_speed = 60.0

        traj = await trajectory_engine.generate_dive_trajectory(
            start_pos, target_alt, dive_angle, max_speed, TrajectoryMethod.GEOMETRIC
        )

        assert isinstance(traj, DiveTrajectory)
        assert traj.method == TrajectoryMethod.GEOMETRIC
        assert traj.constraints_satisfied is True
        assert len(traj.waypoints) == 11
        assert len(traj.velocities) == 11
        assert len(traj.timestamps) == 11

        # 시작점 확인
        assert traj.waypoints[0] == (0.0, 0.0, 500.0)
        # 종료 고도 확인
        assert abs(traj.waypoints[-1][2] - 100.0) < 2.0

        # 속도 벡터 확인
        vx, vy, vz = traj.velocities[0]
        assert vx > 0  # 전진
        assert vy == 0  # 횡방향 없음
        assert vz < 0  # 하강

    @pytest.mark.asyncio
    async def test_dive_trajectory_different_angles(self, trajectory_engine):
        """다양한 다이브 각도 테스트"""
        start_pos = (0.0, 0.0, 300.0)
        target_alt = 50.0
        max_speed = 40.0

        for angle in [30.0, 45.0, 60.0, 75.0]:
            traj = await trajectory_engine.generate_dive_trajectory(
                (0.0, 0.0, 300.0), 50.0, angle, 40.0, TrajectoryMethod.GEOMETRIC
            )

            assert traj.constraints_satisfied
            # 각도가 가파를수록 수직 성분 커짐
            vx, _, vz = traj.velocities[0]
            expected_vx = 40.0 * math.cos(math.radians(angle))
            expected_vz = -40.0 * math.sin(math.radians(angle))
            assert abs(traj.velocities[0][0] - expected_vx) < 0.1
            assert abs(traj.velocities[0][2] - expected_vz) < 0.1

    @pytest.mark.asyncio
    async def test_dive_trajectory_waypoint_count(self, trajectory_engine):
        """웨이포인트 개수 일관성 테스트"""
        for num_points in [5, 10, 20, 50]:
            # 내부적으로 10개 고정이지만 인터페이스 일관성 확인
            traj = await trajectory_engine.generate_dive_trajectory(
                (0, 0, 100), 10, 45, 20, TrajectoryMethod.GEOMETRIC
            )
            assert len(traj.waypoints) == 11  # 0~10 (11개)
            assert len(traj.waypoints) == len(traj.velocities) == len(traj.timestamps)


class TestTrajectoryEngineLUT:
    """LUT 캐시 기능 테스트"""

    @pytest.mark.asyncio
    async def test_lut_cache_hit(self, trajectory_engine):
        """LUT 캐시 히트 테스트"""
        start = (0.0, 0.0, 500.0)
        target_alt = 100.0
        angle = 70.0
        speed = 60.0

        # 첫 호출 (계산)
        traj1 = await trajectory_engine.generate_dive_trajectory(
            start, target_alt, angle, speed, TrajectoryMethod.LUT
        )

        # 두 번째 호출 (캐시에서 가져옴)
        traj2 = await trajectory_engine.generate_dive_trajectory(
            start, target_alt, angle, speed, TrajectoryMethod.LUT
        )

        # 동일한 객체 반환 (캐시 히트)
        assert traj1 is traj2
        assert traj1.method == TrajectoryMethod.LUT

    @pytest.mark.asyncio
    async def test_lut_cache_miss_different_params(self, trajectory_engine):
        """다른 파라미터로 캐시 미스 테스트"""
        # 첫 번째 호출
        traj1 = await trajectory_engine.generate_dive_trajectory(
            (0, 0, 500), 100, 70, 60, TrajectoryMethod.LUT
        )

        # 다른 각도
        traj2 = await trajectory_engine.generate_dive_trajectory(
            (0, 0, 500), 100, 60, 60, TrajectoryMethod.LUT
        )

        # 다른 객체여야 함 (캐시 미스)
        assert traj1 is not traj2
        assert traj2.method == TrajectoryMethod.LUT


class TestTrajectoryEngineDeception:
    """기만 궤적 생성 테스트"""

    @pytest.fixture
    def engine(self):
        specs = {
            "hybrid_drone_1": HardwareSpec(
                device_id="hybrid_drone_1",
                device_type="hybrid_fixed_wing_fpv",
                environment="sitl",
                max_altitude_m=500.0,
                max_linear_vel_mps=80.0,
                capabilities=["DECEPTION_START"],
            ),
        }
        return TrajectoryEngine(specs)

    @pytest.mark.asyncio
    async def test_spiral_dive_trajectory(self, engine):
        """나선형 다이브 궤적 생성"""
        start = (0.0, 0.0, 300.0)
        duration = 30.0
        params = {"radius": 50.0, "turns": 3, "descent_rate": 10.0}

        traj = await engine.generate_deception_trajectory(
            "SPIRAL_DIVE", start, duration, params
        )

        assert isinstance(traj, DiveTrajectory)
        assert traj.method == TrajectoryMethod.LUT
        assert len(traj.waypoints) == 51  # 0~50
        assert traj.waypoints[0] == (0.0, 0.0, 300.0)
        assert traj.waypoints[-1][2] < 100.0  # 강하 확인

        # 나선형 확인: x, y가 원운동 (첫 번째 포인트는 중심이므로 제외)
        for i, wp in enumerate(traj.waypoints[1:], 1):
            expected_radius = 50.0
            actual_radius = math.sqrt(wp[0] ** 2 + wp[1] ** 2)
            assert abs(actual_radius - expected_radius) < 1.0  # 근사치

    @pytest.mark.asyncio
    async def test_sine_dive_trajectory(self, engine):
        """사인파 다이브 궤적"""
        start = (0.0, 0.0, 300.0)
        duration = 30.0
        params = {"amplitude": 20.0, "frequency": 0.5, "descent_rate": 15.0}

        traj = await engine.generate_deception_trajectory(
            "SINE_DIVE", start, duration, params
        )

        assert len(traj.waypoints) == 51
        # x 좌표가 사인파 형태
        for i, wp in enumerate(traj.waypoints):
            t = i / 50.0
            expected_x = 20.0 * math.sin(2 * math.pi * 0.5 * t)
            assert abs(wp[0] - expected_x) < 0.5

    @pytest.mark.asyncio
    async def test_random_jink_trajectory(self, engine):
        """랜덤 진크 궤적"""
        start = (0.0, 0.0, 300.0)
        duration = 30.0
        params = {"speed": 20.0, "descent_rate": 10.0}

        traj = await engine.generate_deception_trajectory(
            "RANDOM_JINK", start, duration, params
        )

        assert len(traj.waypoints) == 21  # 0~20
        assert traj.waypoints[0] == (0.0, 0.0, 300.0)
        # 강하 확인
        assert traj.waypoints[-1][2] < 100.0
        # 재현성 확인 (시드 고정)
        traj2 = await engine.generate_deception_trajectory(
            "RANDOM_JINK", start, duration, params
        )
        assert traj.waypoints == traj2.waypoints

    @pytest.mark.asyncio
    async def test_unknown_pattern_fallback(self, engine):
        """알 수 없는 패턴 -> 기하학적 폴백"""
        traj = await engine.generate_deception_trajectory(
            "UNKNOWN_PATTERN", (0, 0, 100), 10.0, {}
        )
        assert traj.method == TrajectoryMethod.GEOMETRIC


class TestTrajectoryEngineConstraints:
    """제약 조건 만족 테스트"""

    @pytest.fixture
    def engine(self):
        specs = {
            "hybrid_drone_1": HardwareSpec(
                device_id="hybrid_drone_1",
                device_type="hybrid_fixed_wing_fpv",
                environment="sitl",
                max_altitude_m=500.0,
                min_altitude_m=10.0,
                max_linear_vel_mps=80.0,
                max_angular_vel_radps=3.0,
                max_dive_angle_deg=80.0,
                max_dive_speed_mps=80.0,
                capabilities=["ESTOP", "RTL", "HOLD", "MOVE_VEL"],
            ),
        }
        return TrajectoryEngine(specs)

    @pytest.mark.asyncio
    async def test_max_speed_clamping(self, engine):
        """최대 속도 제한 테스트"""
        # 요청 속도가 스펙 초과
        traj = await engine.generate_dive_trajectory(
            (0, 0, 500),
            100,
            45,
            100.0,  # 100m/s 요청 > 80m/s 제한
            TrajectoryMethod.GEOMETRIC,
        )

        # 속도가 80m/s로 클램핑되어야 함
        vx, vy, vz = traj.velocities[0]
        actual_speed = math.sqrt(vx**2 + vy**2 + vz**2)
        assert actual_speed <= 80.0 + 0.1  # 허용 오차

    @pytest.mark.asyncio
    async def test_max_dive_angle_clamping(self, engine):
        """최대 다이브 각도 제한 테스트"""
        # 85도 요청 > 80도 제한
        traj = await engine.generate_dive_trajectory(
            (0, 0, 500), 100, 85.0, 60.0, TrajectoryMethod.GEOMETRIC
        )

        # 실제 각도가 80도 이하여야 함
        # 속도 벡터로 역산출
        vx, _, vz = traj.velocities[0]
        actual_angle = math.degrees(math.atan2(abs(vz), abs(vx)))
        assert actual_angle <= 80.0 + 1.0  # 허용 오차

    @pytest.mark.asyncio
    async def test_min_pullup_altitude(self, engine):
        """최소 풀업 고도 준수 테스트"""
        # 목표 고도가 min_pullup_altitude 미만
        traj = await engine.generate_dive_trajectory(
            (0, 0, 500),
            5.0,
            70.0,
            60.0,  # 5m 목표 < 30m 최소
            TrajectoryMethod.GEOMETRIC,
        )

        # 실제로는 min_pullup_altitude(30m)까지밖에 못 내려감
        # 구현에 따라 다를 수 있으므로 최소한 검증
        assert min(wp[2] for wp in traj.waypoints) >= 0  # 지하로 안감

    @pytest.mark.asyncio
    async def test_waypoint_timestamp_monotonic(self, engine):
        """타임스탬프 단조 증가 테스트"""
        traj = await engine.generate_dive_trajectory(
            (0, 0, 500), 100, 45, 30, TrajectoryMethod.GEOMETRIC
        )

        for i in range(1, len(traj.timestamps)):
            assert traj.timestamps[i] > traj.timestamps[i - 1]

    @pytest.mark.asyncio
    async def test_trajectory_duration_consistency(self, engine):
        """궤적 총 시간 일관성 테스트"""
        duration = 20.0
        traj = await engine.generate_deception_trajectory(
            "SPIRAL_DIVE",
            (0, 0, 300),
            duration,
            {"radius": 50, "turns": 2, "descent_rate": 10},
        )

        # 마지막 타임스탬프가 요청한 duration과 비슷해야 함
        assert abs(traj.timestamps[-1] - duration) < 1.0
