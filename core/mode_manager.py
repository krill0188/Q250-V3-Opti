from enum import Enum
from dataclasses import dataclass
from typing import Optional
import asyncio


class HybridMode(Enum):
    CRUISE = "CRUISE"  # 고정익 순항
    FPV_AGILE = "FPV_AGILE"  # FPV 기동
    DIVE_ATTACK = "DIVE_ATTACK"  # 다이브 어택
    DECEPTION = "DECEPTION"  # 기만 모드
    TRANSITION = "TRANSITION"  # 전환 중


@dataclass
class ModeTransition:
    from_mode: HybridMode
    to_mode: HybridMode
    trigger: str  # AUTO, MANUAL, EMERGENCY
    conditions_met: bool


class HybridModeManager:
    def __init__(self, specs: dict, arbitrator):
        self.specs = specs
        self.arbitrator = arbitrator
        self.current_mode = HybridMode.CRUISE
        self.transition_history = []
        self.auto_transition_enabled = True

    async def request_transition(
        self, target_mode: HybridMode, trigger: str = "MANUAL"
    ) -> bool:
        """모드 전환 요청 (자동/수동)"""
        if not self._validate_transition(target_mode):
            return False

        transition = ModeTransition(
            from_mode=self.current_mode,
            to_mode=target_mode,
            trigger=trigger,
            conditions_met=self._check_conditions(target_mode),
        )

        if not transition.conditions_met and trigger == "AUTO":
            return False

        await self._execute_transition(transition)
        return True

    def _validate_transition(self, target_mode: HybridMode) -> bool:
        """전환 유효성 검사"""
        # 동일 모드면 무시
        if target_mode == self.current_mode:
            return False
        return True

    def _check_conditions(self, target_mode: HybridMode) -> bool:
        """자동 전환 조건 체크"""
        # 첫 번째 기체의 스펙 가져오기
        spec = next(iter(self.specs.values()))

        if target_mode == HybridMode.DIVE_ATTACK:
            # 다이브 어택: 최소 고도 50m, 최소 속도 20m/s, 배터리 30% 이상 필요
            # 현재 상태는 시뮬레이션으로 기본값 사용 (실제로는 텔레메트리에서 가져옴)
            current_alt = getattr(self, "_current_altitude", 100.0)
            current_speed = getattr(self, "_current_speed", 30.0)
            current_battery = getattr(self, "_current_battery", 50.0)

            return (
                current_alt >= 50.0
                and current_speed >= 20.0
                and current_battery >= 30.0
            )

        elif target_mode == HybridMode.FPV_AGILE:
            # FPV 모드: 저고도에서 가능
            current_alt = getattr(self, "_current_altitude", 100.0)
            return current_alt <= 100.0

        elif target_mode == HybridMode.DECEPTION:
            # 기만 모드: 위협 감지 시에만 가능
            return getattr(self, "_threat_detected", False)

        return True

    async def _execute_transition(self, transition: ModeTransition):
        """실제 전환 실행"""
        self.current_mode = transition.to_mode
        self.transition_history.append(transition)
        # 하드웨어 브릿지에 모드 변경 알림 (향후 구현)

    def get_current_mode(self):
        return self.current_mode

    def get_mode_history(self, limit: int = 10):
        return self.transition_history[-limit:]
