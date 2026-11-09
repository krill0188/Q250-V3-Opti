from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import random
import asyncio
import math


class DeceptionPattern(Enum):
    SPIRAL_DIVE = "SPIRAL_DIVE"  # 나선형 다이브 (IR 기만)
    SINE_DIVE = "SINE_DIVE"  # 사인파 다이브 (도플러 레이더)
    RANDOM_JINK = "RANDOM_JINK"  # 랜덤 진크 (예측 필터)
    FAKE_CRASH = "FAKE_CRASH"  # 추락 위장 (광학/IR)
    MULTI_PULSE = "MULTI_PULSE"  # 다중 펄스 (멀티 센서)


@dataclass
class DeceptionPatternConfig:
    pattern: DeceptionPattern
    duration_sec: float
    intensity: float  # 0.0~1.0
    params: dict  # 패턴별 파라미터


@dataclass
class ThreatProfile:
    threat_type: str  # "IR_MISSILE", "RADAR", "OPTICAL", "MULTI"
    confidence: float
    bearing: float
    distance: float


class DeceptionEngine:
    def __init__(self, specs: dict, trajectory_engine):
        self.specs = specs
        self.trajectory_engine = trajectory_engine
        self.active_pattern: Optional[DeceptionPattern] = None
        self.pattern_task: Optional[asyncio.Task] = None
        self.threat_assessor = ThreatAssessor()

        # 패턴별 실행기 매핑
        self.pattern_executors = {
            DeceptionPattern.SPIRAL_DIVE: self._execute_spiral_dive,
            DeceptionPattern.SINE_DIVE: self._execute_sine_dive,
            DeceptionPattern.RANDOM_JINK: self._execute_random_jink,
            DeceptionPattern.FAKE_CRASH: self._execute_fake_crash,
            DeceptionPattern.MULTI_PULSE: self._execute_multi_pulse,
        }

    async def start_deception(
        self,
        pattern: DeceptionPattern,
        duration: float = 30.0,
        auto_select: bool = False,
        threat_profile: Optional[ThreatProfile] = None,
    ) -> bool:
        """기만 모드 시작"""
        if self.active_pattern:
            return False  # 이미 활성화된 기만 모드 있으면 거부

        # 자동 선택 모드
        if auto_select and threat_profile:
            pattern = self._auto_select_pattern(threat_profile)

        self.active_pattern = pattern
        self.pattern_task = asyncio.create_task(
            self._execute_pattern(pattern, duration)
        )
        return True

    def _auto_select_pattern(self, threat: ThreatProfile) -> DeceptionPattern:
        """위협 유형별 최적 패턴 자동 선택"""
        mapping = {
            "IR_MISSILE": DeceptionPattern.SPIRAL_DIVE,
            "RADAR": DeceptionPattern.SINE_DIVE,
            "OPTICAL": DeceptionPattern.FAKE_CRASH,
            "MULTI": DeceptionPattern.MULTI_PULSE,
        }
        return mapping.get(threat.threat_type, DeceptionPattern.RANDOM_JINK)

    async def _execute_pattern(self, pattern: DeceptionPattern, duration: float):
        """패턴 실행"""
        executor = self.pattern_executors[pattern]
        await executor(duration)

    async def _execute_spiral_dive(self, duration: float):
        """나선형 다이브 - IR 시커 기만"""
        # 실제로는 trajectory_engine을 통해 궤적 생성 후 실행
        await asyncio.sleep(duration)

    async def _execute_sine_dive(self, duration: float):
        """사인파 다이브 - 도플러 레이더 기만"""
        await asyncio.sleep(duration)

    async def _execute_random_jink(self, duration: float):
        """랜덤 진크 - 예측 필터 기만"""
        await asyncio.sleep(duration)

    async def _execute_fake_crash(self, duration: float):
        """추락 위장 - 광학/IR 기만"""
        await asyncio.sleep(duration)

    async def _execute_multi_pulse(self, duration: float):
        """다중 펄스 - 멀티 센서 기만"""
        await asyncio.sleep(duration)

    async def stop_deception(self):
        """기만 모드 중지"""
        if self.pattern_task:
            self.pattern_task.cancel()
            try:
                await self.pattern_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass  # 다른 예외도 무시
        self.active_pattern = None
        self.pattern_task = None

    def get_active_pattern(self):
        return self.active_pattern

    def is_active(self):
        return self.active_pattern is not None


class ThreatAssessor:
    """위협 평가기 (향후 확장)"""

    def __init__(self):
        self.known_threats = {}

    async def assess(self, sensor_data: dict) -> ThreatProfile:
        # 센서 데이터 기반 위협 평가 (향후 구현)
        return ThreatProfile(
            threat_type="UNKNOWN", confidence=0.0, bearing=0.0, distance=0.0
        )
