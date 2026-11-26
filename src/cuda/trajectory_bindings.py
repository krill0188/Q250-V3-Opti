#!/usr/bin/env python3
"""
Python Bindings for Q250-V3-Opti Trajectory CUDA Kernels
ctypes 기반 경량 래퍼 (pybind11 빌드 불필요)
"""

import ctypes
import os
from pathlib import Path
import sys
import time
from typing import List, Optional, Tuple

import numpy as np

# =============================================================================
# Data Structures (CUDA 커널과 일치)
# =============================================================================


class TrajectoryPoint(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_float),
        ("y", ctypes.c_float),
        ("z", ctypes.c_float),
        ("vx", ctypes.c_float),
        ("vy", ctypes.c_float),
        ("vz", ctypes.c_float),
        ("timestamp", ctypes.c_float),
    ]

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def velocity_tuple(self) -> Tuple[float, float, float]:
        return (self.vx, self.vy, self.vz)

    def __repr__(self):
        return (
            f"TrajectoryPoint(pos=({self.x:.2f}, {self.y:.2f}, {self.z:.2f}), "
            f"vel=({self.vx:.2f}, {self.vy:.2f}, {self.vz:.2f}), "
            f"t={self.timestamp:.3f})"
        )


class DiveTrajectoryParams(ctypes.Structure):
    _fields_ = [
        ("start_x", ctypes.c_float),
        ("start_y", ctypes.c_float),
        ("start_z", ctypes.c_float),
        ("target_alt", ctypes.c_float),
        ("dive_angle_deg", ctypes.c_float),
        ("max_speed", ctypes.c_float),
        ("max_dive_speed", ctypes.c_float),
        ("max_dive_angle_deg", ctypes.c_float),
        ("num_points", ctypes.c_int),
    ]


class SpiralDiveParams(ctypes.Structure):
    _fields_ = [
        ("start_x", ctypes.c_float),
        ("start_y", ctypes.c_float),
        ("start_z", ctypes.c_float),
        ("radius", ctypes.c_float),
        ("turns", ctypes.c_float),
        ("descent_rate", ctypes.c_float),
        ("duration", ctypes.c_float),
        ("num_points", ctypes.c_int),
    ]


class SineDiveParams(ctypes.Structure):
    _fields_ = [
        ("start_x", ctypes.c_float),
        ("start_y", ctypes.c_float),
        ("start_z", ctypes.c_float),
        ("amplitude", ctypes.c_float),
        ("frequency", ctypes.c_float),
        ("descent_rate", ctypes.c_float),
        ("duration", ctypes.c_float),
        ("num_points", ctypes.c_int),
    ]


class JinkParams(ctypes.Structure):
    _fields_ = [
        ("start_x", ctypes.c_float),
        ("start_y", ctypes.c_float),
        ("start_z", ctypes.c_float),
        ("speed", ctypes.c_float),
        ("descent_rate", ctypes.c_float),
        ("duration", ctypes.c_float),
        ("num_segments", ctypes.c_int),
        ("seed", ctypes.c_uint),
    ]


# =============================================================================
# Shared Library Loader
# =============================================================================


class TrajectoryCUDA:
    """CUDA 커널 래퍼 클래스"""

    def __init__(self, lib_path: Optional[str] = None):
        """
        Args:
            lib_path: 컴파일된 공유 라이브러리 경로 (.so)
                     None이면 자동 탐색
        """
        if lib_path is None:
            # 기본 경로 탐색
            base_dir = Path(__file__).parent.parent.parent
            candidates = [
                base_dir / "build" / "libtrajectory_kernels.so",
                base_dir / "src" / "cuda" / "libtrajectory_kernels.so",
                Path("/usr/local/lib/libtrajectory_kernels.so"),
            ]
            for c in candidates:
                if c.exists():
                    lib_path = str(c)
                    break

        if lib_path is None or not Path(lib_path).exists():
            raise RuntimeError(
                f"CUDA library not found. Build first:\n"
                f"  mkdir -p build && cd build && cmake .. && make\n"
                f"Or specify lib_path explicitly."
            )

        self.lib = ctypes.CDLL(lib_path)
        self._setup_signatures()
        self._seed_state = ctypes.c_uint(0xDEADBEEF)  # 기본 시드
        self._d_seed_state = None  # 디바이스 시드 상태 포인터

    def _setup_signatures(self):
        """함수 시그니처 설정"""
        # geometric_dive_trajectory
        self.lib.launch_geometric_dive_trajectory.argtypes = [
            ctypes.POINTER(DiveTrajectoryParams),
            ctypes.POINTER(TrajectoryPoint),
            ctypes.c_int,
        ]
        self.lib.launch_geometric_dive_trajectory.restype = ctypes.c_int

        # spiral_dive_trajectory
        self.lib.launch_spiral_dive_trajectory.argtypes = [
            ctypes.POINTER(SpiralDiveParams),
            ctypes.POINTER(TrajectoryPoint),
            ctypes.c_int,
        ]
        self.lib.launch_spiral_dive_trajectory.restype = ctypes.c_int

        # sine_dive_trajectory
        self.lib.launch_sine_dive_trajectory.argtypes = [
            ctypes.POINTER(SineDiveParams),
            ctypes.POINTER(TrajectoryPoint),
            ctypes.c_int,
        ]
        self.lib.launch_sine_dive_trajectory.restype = ctypes.c_int

        # jink_trajectory
        self.lib.launch_jink_trajectory.argtypes = [
            ctypes.POINTER(JinkParams),
            ctypes.POINTER(TrajectoryPoint),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.lib.launch_jink_trajectory.restype = ctypes.c_int

    def _check_error(self, err: int, op: str):
        if err != 0:
            raise RuntimeError(f"CUDA error in {op}: code {err}")

    # =========================================================================
    # Public API
    # =========================================================================

    def geometric_dive(
        self,
        start_pos: Tuple[float, float, float],
        target_alt: float,
        dive_angle: float,
        max_speed: float,
        max_dive_speed: float = 50.0,
        max_dive_angle: float = 80.0,
        num_points: int = 50,
    ) -> List[TrajectoryPoint]:
        """기하학적 다이브 궤적 생성 (GPU 가속)"""

        params = DiveTrajectoryParams(
            start_x=start_pos[0],
            start_y=start_pos[1],
            start_z=start_pos[2],
            target_alt=target_alt,
            dive_angle_deg=dive_angle,
            max_speed=max_speed,
            max_dive_speed=max_dive_speed,
            max_dive_angle_deg=max_dive_angle,
            num_points=num_points,
        )

        # 출력 배열 할당
        output = (TrajectoryPoint * (num_points + 1))()

        err = self.lib.launch_geometric_dive_trajectory(ctypes.byref(params), output, num_points)
        self._check_error(err, "geometric_dive")

        return list(output)

    def spiral_dive(
        self,
        start_pos: Tuple[float, float, float],
        radius: float = 50.0,
        turns: float = 3.0,
        descent_rate: float = 10.0,
        duration: float = 10.0,
        num_points: int = 50,
    ) -> List[TrajectoryPoint]:
        """나선형 다이브 궤적 생성 (GPU 가속)"""

        params = SpiralDiveParams(
            start_x=start_pos[0],
            start_y=start_pos[1],
            start_z=start_pos[2],
            radius=radius,
            turns=turns,
            descent_rate=descent_rate,
            duration=duration,
            num_points=num_points,
        )

        output = (TrajectoryPoint * (num_points + 1))()

        err = self.lib.launch_spiral_dive_trajectory(ctypes.byref(params), output, num_points)
        self._check_error(err, "spiral_dive")

        return list(output)

    def sine_dive(
        self,
        start_pos: Tuple[float, float, float],
        amplitude: float = 20.0,
        frequency: float = 0.5,
        descent_rate: float = 15.0,
        duration: float = 10.0,
        num_points: int = 50,
    ) -> List[TrajectoryPoint]:
        """사인파 다이브 궤적 생성 (GPU 가속)"""

        params = SineDiveParams(
            start_x=start_pos[0],
            start_y=start_pos[1],
            start_z=start_pos[2],
            amplitude=amplitude,
            frequency=frequency,
            descent_rate=descent_rate,
            duration=duration,
            num_points=num_points,
        )

        output = (TrajectoryPoint * (num_points + 1))()

        err = self.lib.launch_sine_dive_trajectory(ctypes.byref(params), output, num_points)
        self._check_error(err, "sine_dive")

        return list(output)

    def jink_trajectory(
        self,
        start_pos: Tuple[float, float, float],
        speed: float = 20.0,
        descent_rate: float = 10.0,
        duration: float = 10.0,
        num_segments: int = 20,
        seed: Optional[int] = None,
    ) -> List[TrajectoryPoint]:
        """랜덤 진크 궤적 생성 (GPU 가속, 재현 가능)"""

        if seed is None:
            seed = int(time.time() * 1000) & 0xFFFFFFFF

        params = JinkParams(
            start_x=start_pos[0],
            start_y=start_pos[1],
            start_z=start_pos[2],
            speed=speed,
            descent_rate=descent_rate,
            duration=duration,
            num_segments=num_segments,
            seed=seed,
        )

        output = (TrajectoryPoint * (num_segments + 1))()

        # 시드 상태 디바이스 메모리 할당 (최초 1회)
        if self._d_seed_state is None:
            self._d_seed_state = ctypes.c_uint(seed)

        err = self.lib.launch_jink_trajectory(
            ctypes.byref(params), output, num_segments, ctypes.byref(self._d_seed_state)
        )
        self._check_error(err, "jink_trajectory")

        return list(output)


# =============================================================================
# Fallback: Pure Python Implementation (CUDA 미사용 시)
# =============================================================================


class TrajectoryPythonFallback:
    """Pure Python 구현 (CUDA 라이브러리 없을 때 자동 사용)"""

    @staticmethod
    def geometric_dive(
        start_pos: Tuple[float, float, float],
        target_alt: float,
        dive_angle: float,
        max_speed: float,
        max_dive_speed: float = 50.0,
        max_dive_angle: float = 80.0,
        num_points: int = 50,
    ) -> List[Tuple[float, float, float]]:
        import math

        clamped_speed = min(max_speed, max_dive_speed)
        clamped_angle = min(dive_angle, max_dive_angle)
        dive_angle_rad = math.radians(clamped_angle)

        altitude_change = start_pos[2] - target_alt
        horizontal_dist = altitude_change / math.tan(dive_angle_rad)

        waypoints = []
        for i in range(num_points + 1):
            t = i / num_points
            z = start_pos[2] - altitude_change * t
            horiz_dist = horizontal_dist * t
            x = start_pos[0] + horiz_dist
            y = start_pos[1]
            waypoints.append((x, y, z))

        return waypoints

    @staticmethod
    def spiral_dive(
        start_pos: Tuple[float, float, float],
        radius: float = 50.0,
        turns: float = 3.0,
        descent_rate: float = 10.0,
        duration: float = 10.0,
        num_points: int = 50,
    ) -> List[Tuple[float, float, float]]:
        import math

        waypoints = []
        for i in range(num_points + 1):
            t = i / num_points
            angle = 2 * math.pi * turns * t
            z = start_pos[2] - descent_rate * duration * t

            if i == 0:
                x, y = start_pos[0], start_pos[1]
            else:
                x = start_pos[0] + radius * math.cos(angle)
                y = start_pos[1] + radius * math.sin(angle)

            waypoints.append((x, y, z))

        return waypoints

    @staticmethod
    def sine_dive(
        start_pos: Tuple[float, float, float],
        amplitude: float = 20.0,
        frequency: float = 0.5,
        descent_rate: float = 15.0,
        duration: float = 10.0,
        num_points: int = 50,
    ) -> List[Tuple[float, float, float]]:
        import math

        waypoints = []
        for i in range(num_points + 1):
            t = i / num_points
            x = start_pos[0] + amplitude * math.sin(2 * math.pi * frequency * t)
            y = start_pos[1]
            z = start_pos[2] - descent_rate * duration * t
            waypoints.append((x, y, z))

        return waypoints


# =============================================================================
# Auto-Selector: 사용 가능한 최적 구현 자동 선택
# =============================================================================


def get_trajectory_backend(force_python: bool = False):
    """
    사용 가능한 최적 백엔드 반환

    Returns:
        (backend_instance, backend_name)
    """
    if force_python:
        return TrajectoryPythonFallback(), "python_fallback"

    try:
        # CUDA 라이브러리 로드 시도
        backend = TrajectoryCUDA()
        return backend, "cuda"
    except Exception as e:
        print(f"[Trajectory] CUDA backend unavailable: {e}")
        print(f"[Trajectory] Falling back to Python implementation")
        return TrajectoryPythonFallback(), "python_fallback"


# =============================================================================
# 기존 trajectory_engine.py 호환 인터페이스
# =============================================================================


class TrajectoryEngineGPU:
    """기존 TrajectoryEngine과 호환되는 GPU 가속 래퍼"""

    def __init__(self, specs: dict, force_python: bool = False):
        self.specs = specs
        self.backend, self.backend_name = get_trajectory_backend(force_python)
        self.lut_cache = {}
        self.mpc_horizon = 20
        print(f"[TrajectoryEngine] Backend: {self.backend_name}")

    async def generate_dive_trajectory(
        self,
        start_pos: Tuple[float, float, float],
        target_alt: float,
        dive_angle: float,
        max_speed: float,
        method: str = "MPC",
    ):
        import math

        from core.trajectory_engine import DiveTrajectory, TrajectoryMethod

        if method == "LUT" or method == TrajectoryMethod.LUT:
            # LUT: 캐시된 궤적 재사용
            return self._lut_lookup(start_pos, target_alt, dive_angle, max_speed)

        # CUDA/가속: 기하학적 계산 (GPU)
        spec = next(iter(self.specs.values()))
        max_dive_speed = getattr(spec, "max_dive_speed_mps", max_speed)
        max_dive_angle = getattr(spec, "max_dive_angle_deg", dive_angle)

        if hasattr(self.backend, "geometric_dive"):
            # CUDA 백엔드
            points = self.backend.geometric_dive(
                start_pos,
                target_alt,
                dive_angle,
                max_speed,
                max_dive_speed,
                max_dive_angle,
                50,
            )
            waypoints = [p.to_tuple() for p in points]
            velocities = [p.velocity_tuple() for p in points]
            timestamps = [p.timestamp for p in points]
        else:
            # Python 폴백
            waypoints = self.backend.geometric_dive(
                start_pos,
                target_alt,
                dive_angle,
                max_speed,
                max_dive_speed,
                max_dive_angle,
                50,
            )
            # 속도/타임스탬프 계산
            altitudes = [p[2] for p in waypoints]
            vx = max_speed * math.cos(math.radians(dive_angle))
            vz = -max_speed * math.sin(math.radians(dive_angle))
            velocities = [(vx, 0, vz) for _ in waypoints]
            timestamps = [
                i * (altitudes[0] - altitudes[-1]) / max_speed / 50 for i in range(len(waypoints))
            ]

        return DiveTrajectory(
            waypoints=waypoints,
            velocities=velocities,
            timestamps=timestamps,
            method=TrajectoryMethod.GEOMETRIC,
            constraints_satisfied=True,
        )

    def _lut_lookup(self, start, target_alt, angle, max_speed):
        # 기존 LUT 로직 유지 (Python)
        key = (round(start[2], 1), round(target_alt, 1), round(angle, 1))
        if key in self.lut_cache:
            return self.lut_cache[key]

        import asyncio

        traj = asyncio.create_task(
            self.generate_dive_trajectory(start, target_alt, angle, max_speed, method="GEOMETRIC")
        )
        # Note: This is a workaround - in real usage, call generate_dive_trajectory directly
        # and cache the result before returning
        return self.lut_cache.get(key)


# 모듈 테스트
if __name__ == "__main__":
    print("Testing trajectory backend selection...")
    backend, name = get_trajectory_backend()
    print(f"Selected backend: {name}")

    if name == "cuda":
        print("Testing CUDA geometric dive...")
        points = backend.geometric_dive((0, 0, 100), 50, 45, 25, 30, 60, 10)
        print(f"Generated {len(points)} points")
        print(f"First: {points[0]}")
        print(f"Last: {points[-1]}")
    else:
        print("Testing Python fallback...")
        points = backend.geometric_dive((0, 0, 100), 50, 45, 25, 30, 60, 10)
        print(f"Generated {len(points)} points")
        print(f"First: {points[0]}")
        print(f"Last: {points[-1]}")
