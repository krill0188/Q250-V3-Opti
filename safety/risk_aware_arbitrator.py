import asyncio
import time
from typing import Optional
from core_arbitrator import CommandArbitrator, CommandPriority, UnifiedCommand
from core.llm_risk_analyzer import LocalLLMRiskAnalyzer, RiskAssessment
from core.log_aggregator import LogAggregator


class RiskAwareArbitrator(CommandArbitrator):
    """LLM 위험 분석 결과를 고려하는 확장 중재기"""

    def __init__(
        self,
        validator,
        log_aggregator: LogAggregator,
        risk_analyzer: LocalLLMRiskAnalyzer,
        risk_check_interval: float = 0.5,  # 2Hz 위험 평가
    ):
        super().__init__(validator)
        self.log_aggregator = log_aggregator
        self.risk_analyzer = risk_analyzer
        self.risk_check_interval = risk_check_interval
        self.current_risk: Optional[RiskAssessment] = None
        self._risk_task: Optional[asyncio.Task] = None
        self._block_lower_priority = False

    async def start_risk_monitoring(self):
        """주기적 위험 평가 태스크 시작"""
        self._risk_task = asyncio.create_task(self._risk_monitor_loop())

    async def _risk_monitor_loop(self):
        """주기적 위험 평가 루프"""
        while True:
            try:
                # 모든 기체 대상 위험 평가
                for device_id in list(self.log_aggregator.buffers.keys()):
                    risk = await self.risk_analyzer.analyze_window(
                        self.log_aggregator, device_id
                    )
                    self.current_risk = risk

                    # CRITICAL 위험 시 즉시 개입
                    if risk.risk_level == "CRITICAL":
                        await self._handle_critical_risk(risk)

                    # HIGH 위험 시 경고 + 모드 제한
                    elif risk.risk_level == "HIGH":
                        await self._handle_high_risk(risk)

            except Exception as e:
                print(f"[RISK MONITOR ERROR] {e}")

            await asyncio.sleep(self.risk_check_interval)

    async def _handle_critical_risk(self, risk: RiskAssessment, dispatch_callback=None):
        """CRITICAL 위험 즉시 대응"""
        print(f"[CRITICAL RISK] {risk.reasoning}")

        if dispatch_callback is None:
            dispatch_callback = self._dummy_dispatch

        # 1. auto_execute 액션 즉시 아비트레이터 제출
        for action_name in risk.auto_execute:
            if action_name == "ESTOP":
                action = "ESTOP"
            elif action_name == "RTL":
                action = "RTL"
            elif action_name == "HOLD":
                action = "HOLD"
            else:
                action = action_name

            estop_cmd = UnifiedCommand(
                command_id=f"risk-{int(time.time()*1000)}",
                source="FAILSAFE",
                priority=CommandPriority.FAILSAFE_ESTOP,
                target_id="drone_1",
                action=action,
                confidence=1.0,
            )
            await self.submit_command(estop_cmd, dispatch_callback)

        # 2. 모든 음성/수동 명령 일시 차단 (CRITICAL 해제까지)
        self._block_lower_priority = True

    async def _handle_high_risk(self, risk: RiskAssessment):
        """HIGH 위험 경고 및 모드 제한"""
        print(f"[HIGH RISK] {risk.reasoning}")
        # GCS 경고 알림은 WebSocket으로 전송
        # 음성 명령 우선순위 일시 낮춤
        # 최대 속도/고도 제한 강화

    def get_current_risk(self):
        return self.current_risk

    def is_blocked(self) -> bool:
        return self._block_lower_priority

    def clear_block(self):
        self._block_lower_priority = False

    async def submit_command(self, raw_cmd, dispatch_callback):
        """위험 차단 확인 후 명령 제출"""
        if (
            self._block_lower_priority
            and raw_cmd.priority > CommandPriority.FAILSAFE_ESTOP
        ):
            print(f"[BLOCKED] {raw_cmd.source} 명령 차단됨 (CRITICAL 위험 활성)")
            return False
        return await super().submit_command(raw_cmd, dispatch_callback)

    async def _dummy_dispatch(self, cmd):
        pass
