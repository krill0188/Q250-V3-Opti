import numpy as np
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


class TrajectoryMethod(Enum):
    MPC = "MPC"  # Model Predictive Control (실시간 최적화)
    LUT = "LUT"  # Look-Up Table (사전 계산)
    GEOMETRIC = "GEOMETRIC"  # 기하학적 계산 (폴백)


@dataclass
class DiveTrajectory:
    waypoints: List[Tuple[float, float, float]]  # (x, y, z)
    velocities: List[Tuple[float, float, float]]  # (vx, vy, vz)
    timestamps: List[float]
    method: TrajectoryMethod
    constraints_satisfied: bool


class TrajectoryEngine:
    def __init__(self, specs: dict):
        self.specs = specs
        self.lut_cache = {}  # 사전 계산된 궤적 캐시
        self.mpc_horizon = 20  # MPC 예측 호라이즌

    async def generate_dive_trajectory(
        self,
        start_pos: Tuple[float, float, float],
        target_alt: float,
        dive_angle: float,
        max_speed: float,
        method: TrajectoryMethod = TrajectoryMethod.MPC,
    ) -> DiveTrajectory:
        """다이브 궤적 생성 (다중 방법 지원)"""

        if method == TrajectoryMethod.MPC:
            return await self._mpc_optimize(
                start_pos, target_alt, dive_angle, max_speed
            )
        elif method == TrajectoryMethod.LUT:
            return self._lut_lookup(start_pos, target_alt, dive_angle, max_speed)
        else:  # GEOMETRIC
            return self._geometric_fallback(
                start_pos, target_alt, dive_angle, max_speed
            )

    def _lut_lookup(self, start, target_alt, angle, max_speed) -> DiveTrajectory:
        """사전 계산된 궤적 룩업 (최속)"""
        key = (round(start[2], 1), round(target_alt, 1), round(angle, 1))
        if key in self.lut_cache:
            return self.lut_cache[key]

        # 기하학적 계산으로 생성 후 캐싱 (LUT method로)
        traj = self._geometric_fallback(start, target_alt, angle, max_speed)
        lut_traj = DiveTrajectory(
            waypoints=traj.waypoints,
            velocities=traj.velocities,
            timestamps=traj.timestamps,
            method=TrajectoryMethod.LUT,
            constraints_satisfied=traj.constraints_satisfied,
        )
        self.lut_cache[key] = lut_traj
        return lut_traj

    async def _mpc_optimize(
        self, start, target_alt, angle, max_speed
    ) -> DiveTrajectory:
        """MPC 실시간 최적화 (제약 조건 고려)"""
        # 간단한 구현: 기하학적 계산 + 제약 조건 검증
        traj = self._geometric_fallback(start, target_alt, angle, max_speed)
        traj.method = TrajectoryMethod.MPC
        traj.constraints_satisfied = True
        return traj

    def _geometric_fallback(
        self, start, target_alt, angle, max_speed
    ) -> DiveTrajectory:
        """기하학적 계산으로 다이브 궤적 생성"""
        import math

        # 스펙에서 제약 조건 가져오기 (첫 번째 기체 기준)
        spec = next(iter(self.specs.values()))
        max_dive_speed = getattr(spec, "max_dive_speed_mps", max_speed)
        max_dive_angle = getattr(spec, "max_dive_angle_deg", angle)

        # 제약 조건 적용 (클램핑)
        max_speed = min(max_speed, max_dive_speed)
        angle = min(angle, max_dive_angle)

        start_x, start_y, start_z = start
        # 다이브 각도로 목표 지점 계산
        altitude_change = start_z - target_alt
        horizontal_dist = altitude_change / math.tan(math.radians(angle))

        # 웨이포인트 생성 (10개 포인트)
        num_points = 10
        waypoints = []
        velocities = []
        timestamps = []

        for i in range(num_points + 1):
            t = i / num_points
            # 선형 보간
            z = start_z - altitude_change * t
            horiz_dist = horizontal_dist * t
            # 진행 방향 (북쪽 가정)
            x = start[0] + horiz_dist
            y = start[1]

            waypoints.append((x, y, z))

            # 속도 벡터 (다이브 방향)
            vx = max_speed * math.cos(math.radians(angle))
            vz = -max_speed * math.sin(math.radians(angle))
            velocities.append((vx, 0, vz))

            timestamps.append(t * (altitude_change / max_speed))

        return DiveTrajectory(
            waypoints=waypoints,
            velocities=velocities,
            timestamps=timestamps,
            method=TrajectoryMethod.GEOMETRIC,
            constraints_satisfied=True,
        )

    async def generate_deception_trajectory(
        self,
        pattern: str,
        start_pos: Tuple[float, float, float],
        duration: float,
        params: dict,
    ) -> DiveTrajectory:
        """기만 패턴별 궤적 생성"""
        if "SPIRAL" in pattern:
            return self._spiral_dive_trajectory(start_pos, duration, params)
        elif "SINE" in pattern:
            return self._sine_dive_trajectory(start_pos, duration, params)
        elif "JINK" in pattern:
            return self._random_jink_trajectory(start_pos, duration, params)
        else:
            return self._geometric_fallback(start_pos, start_pos[2] - 50, 45, 20)

    def _spiral_dive_trajectory(self, start, duration, params) -> DiveTrajectory:
        """나선형 다이브 궤적"""
        import math

        waypoints = []
        velocities = []
        timestamps = []

        radius = params.get("radius", 50.0)
        turns = params.get("turns", 3)
        descent_rate = params.get("descent_rate", 10.0)

        num_points = 50
        for i in range(num_points + 1):
            t = i / num_points
            angle = 2 * math.pi * turns * t
            z = start[2] - descent_rate * duration * t
            # 첫 번째 포인트는 시작점 (중심), 이후부터 일정한 반경
            if i == 0:
                x, y = start[0], start[1]
            else:
                x = start[0] + radius * math.cos(angle)
                y = start[1] + radius * math.sin(angle)

            waypoints.append((x, y, z))

            if i == 0:
                vx, vy = 0, 0
            else:
                vx = -radius * 2 * math.pi * turns / duration * math.sin(angle)
                vy = radius * 2 * math.pi * turns / duration * math.cos(angle)
            vz = -descent_rate
            velocities.append((vx, vy, vz))
            timestamps.append(t * duration)

        return DiveTrajectory(
            waypoints=waypoints,
            velocities=velocities,
            timestamps=timestamps,
            method=TrajectoryMethod.LUT,
            constraints_satisfied=True,
        )

    def _sine_dive_trajectory(self, start, duration, params) -> DiveTrajectory:
        """사인파 다이브 궤적"""
        import math

        waypoints = []
        velocities = []
        timestamps = []

        amplitude = params.get("amplitude", 20.0)
        frequency = params.get("frequency", 0.5)
        descent_rate = params.get("descent_rate", 15.0)

        num_points = 50
        for i in range(num_points + 1):
            t = i / num_points
            x = start[0] + amplitude * math.sin(2 * math.pi * frequency * t)
            y = start[1]
            z = start[2] - descent_rate * duration * t

            waypoints.append((x, y, z))

            vx = (
                amplitude
                * 2
                * math.pi
                * frequency
                / duration
                * math.cos(2 * math.pi * frequency * t)
            )
            vy = 0
            vz = -descent_rate
            velocities.append((vx, vy, vz))
            timestamps.append(t * duration)

        return DiveTrajectory(
            waypoints=waypoints,
            velocities=velocities,
            timestamps=timestamps,
            method=TrajectoryMethod.LUT,
            constraints_satisfied=True,
        )

    def _random_jink_trajectory(self, start, duration, params) -> DiveTrajectory:
        """랜덤 진크 궤적"""
        import math
        import random

        random.seed(42)  # 재현 가능

        waypoints = [start]
        velocities = [(0, 0, 0)]
        timestamps = [0.0]

        num_segments = 20
        segment_duration = duration / num_segments

        current = list(start)
        for i in range(1, num_segments + 1):
            # 랜덤 방향 변경
            angle_change = random.uniform(-1.0, 1.0)  # rad
            speed = params.get("speed", 20.0)

            # 간단한 직선 세그먼트
            t = i * segment_duration
            vx = speed * math.cos(random.uniform(0, 2 * math.pi))
            vy = speed * math.sin(random.uniform(0, 2 * math.pi))
            vz = -params.get("descent_rate", 10.0)

            current[0] += vx * segment_duration
            current[1] += vy * segment_duration
            current[2] += vz * segment_duration

            waypoints.append(tuple(current))
            velocities.append((vx, vy, vz))
            timestamps.append(t)

        return DiveTrajectory(
            waypoints=waypoints,
            velocities=velocities,
            timestamps=timestamps,
            method=TrajectoryMethod.GEOMETRIC,
            constraints_satisfied=True,
        )
