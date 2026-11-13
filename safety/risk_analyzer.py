#!/usr/bin/env python3
"""
Local LLM 위험 분석기 with Silvus Integration
llama.cpp Function Calling을 사용한 실시간 위험 분석
Silvus 링크 품질 데이터 통합
"""

import asyncio
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class RiskCategory(Enum):
    COMMUNICATION = "COMMUNICATION"
    BATTERY = "BATTERY"
    COLLISION = "COLLISION"
    WEATHER = "WEATHER"
    NAVIGATION = "NAVIGATION"
    SYSTEM = "SYSTEM"
    MISSION = "MISSION"


class ActionType(Enum):
    RTL = "RTL"
    ESTOP = "ESTOP"
    HOLD = "HOLD"
    REOPTIMIZE_COMM = "REOPTIMIZE_COMM"
    CHANGE_ALTITUDE = "CHANGE_ALTITUDE"
    CHANGE_SPEED = "CHANGE_SPEED"
    ABORT_MISSION = "ABORT_MISSION"
    CONTINUE = "CONTINUE"
    WARNING = "WARNING"


@dataclass
class RiskAssessment:
    risk_level: RiskLevel
    category: RiskCategory
    confidence: float
    description: str
    recommended_action: ActionType
    action_params: Dict = field(default_factory=dict)
    auto_execute: bool = False
    timeout_ms: int = 200
    timestamp: float = field(default_factory=time.time)
    source_data: Dict = field(default_factory=dict)


@dataclass
class SilvusLinkMetrics:
    """Silvus 링크 품질 메트릭"""
    neighbor_mac: str
    snr_db: float
    per: float
    rssi_dbm: float
    etx: float
    hop_count: int
    channel_mhz: int
    tx_rate_mbps: float
    latency_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class UAVState:
    """UAV 상태"""
    uav_id: int
    position: np.ndarray  # [x, y, z]
    velocity: np.ndarray
    attitude: np.ndarray  # roll, pitch, yaw
    battery_percent: float
    mode: str
    armed: bool
    gps_fix: int
    satellites: int
    timestamp: float = field(default_factory=time.time)


class SilvusRiskAnalyzer:
    """Silvus 링크 품질 기반 위험 분석기"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 임계값 설정
        self.thresholds = {
            'per_critical': self.config.get('per_critical', 0.15),
            'per_high': self.config.get('per_high', 0.10),
            'per_medium': self.config.get('per_medium', 0.05),
            'snr_critical': self.config.get('snr_critical', 5.0),
            'snr_high': self.config.get('snr_high', 10.0),
            'snr_medium': self.config.get('snr_medium', 15.0),
            'etx_critical': self.config.get('etx_critical', 5.0),
            'etx_high': self.config.get('etx_high', 3.0),
            'etx_medium': self.config.get('etx_medium', 2.0),
            'hop_critical': self.config.get('hop_critical', 5),
            'hop_high': self.config.get('hop_high', 4),
            'link_loss_timeout': self.config.get('link_loss_timeout', 3.0),
        }
        
        # 배터리 임계값
        self.battery_thresholds = {
            'critical': 15.0,
            'low': 25.0,
            'medium': 40.0,
        }
        
        # 슬라이딩 윈도우
        self.window_size = self.config.get('window_size', 10)
        self.link_history: Dict[str, deque] = {}
        
        logger.info("SilvusRiskAnalyzer initialized")
    
    def update_link_metrics(self, metrics: List[SilvusLinkMetrics]):
        """링크 메트릭 업데이트 및 히스토리 관리"""
        current_time = time.time()
        
        for metric in metrics:
            mac = metric.neighbor_mac
            if mac not in self.link_history:
                self.link_history[mac] = deque(maxlen=self.window_size)
            
            self.link_history[mac].append({
                'timestamp': metric.timestamp,
                'snr_db': metric.snr_db,
                'per': metric.per,
                'etx': metric.etx,
                'hop_count': metric.hop_count,
                'rssi_dbm': metric.rssi_dbm,
            })
            
            # 오래된 데이터 정리
            cutoff = current_time - 30.0  # 30초 윈도우
            while self.link_history[mac] and self.link_history[mac][0]['timestamp'] < cutoff:
                self.link_history[mac].popleft()
    
    def analyze_link_quality(self, metrics: List[SilvusLinkMetrics]) -> List[RiskAssessment]:
        """링크 품질 기반 위험 평가"""
        risks = []
        
        for metric in metrics:
            # PER 기반 위험도
            per_risk = self._assess_per_risk(metric.per, metric.neighbor_mac)
            if per_risk:
                risks.append(per_risk)
            
            # SNR 기반 위험도
            snr_risk = self._assess_snr_risk(metric.snr_db, metric.neighbor_mac)
            if snr_risk:
                risks.append(snr_risk)
            
            # ETX 기반 위험도
            etx_risk = self._assess_etx_risk(metric.etx, metric.neighbor_mac)
            if etx_risk:
                risks.append(etx_risk)
            
            # 홉 수 기반 위험도
            hop_risk = self._assess_hop_risk(metric.hop_count, metric.neighbor_mac)
            if hop_risk:
                risks.append(hop_risk)
            
            # 링크 손실 감지 (히스토리 기반)
            loss_risk = self._detect_link_loss(metric.neighbor_mac)
            if loss_risk:
                risks.append(loss_risk)
        
        return risks
    
    def _assess_per_risk(self, per: float, mac: str) -> Optional[RiskAssessment]:
        if per >= self.thresholds['per_critical']:
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                category=RiskCategory.COMMUNICATION,
                confidence=0.95,
                description=f"Critical PER {per:.1%} on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'per_critical', 'mac': mac, 'per': per},
                auto_execute=True,
                source_data={'per': per, 'threshold': self.thresholds['per_critical']}
            )
        elif per >= self.thresholds['per_high']:
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                category=RiskCategory.COMMUNICATION,
                confidence=0.85,
                description=f"High PER {per:.1%} on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'per_high', 'mac': mac, 'per': per},
                auto_execute=True,
                source_data={'per': per, 'threshold': self.thresholds['per_high']}
            )
        elif per >= self.thresholds['per_medium']:
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                category=RiskCategory.COMMUNICATION,
                confidence=0.7,
                description=f"Elevated PER {per:.1%} on link {mac}",
                recommended_action=ActionType.WARNING,
                action_params={'reason': 'per_medium', 'mac': mac, 'per': per},
                source_data={'per': per, 'threshold': self.thresholds['per_medium']}
            )
        return None
    
    def _assess_snr_risk(self, snr_db: float, mac: str) -> Optional[RiskAssessment]:
        if snr_db <= self.thresholds['snr_critical']:
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                category=RiskCategory.COMMUNICATION,
                confidence=0.9,
                description=f"Critical SNR {snr_db:.1f}dB on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'snr_critical', 'mac': mac, 'snr_db': snr_db},
                auto_execute=True,
                source_data={'snr_db': snr_db, 'threshold': self.thresholds['snr_critical']}
            )
        elif snr_db <= self.thresholds['snr_high']:
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                category=RiskCategory.COMMUNICATION,
                confidence=0.8,
                description=f"Low SNR {snr_db:.1f}dB on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'snr_high', 'mac': mac, 'snr_db': snr_db},
                auto_execute=True,
                source_data={'snr_db': snr_db, 'threshold': self.thresholds['snr_high']}
            )
        elif snr_db <= self.thresholds['snr_medium']:
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                category=RiskCategory.COMMUNICATION,
                confidence=0.7,
                description=f"Marginal SNR {snr_db:.1f}dB on link {mac}",
                recommended_action=ActionType.WARNING,
                action_params={'reason': 'snr_medium', 'mac': mac, 'snr_db': snr_db},
                source_data={'snr_db': snr_db, 'threshold': self.thresholds['snr_medium']}
            )
        return None
    
    def _assess_etx_risk(self, etx: float, mac: str) -> Optional[RiskAssessment]:
        if etx >= self.thresholds['etx_critical']:
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                category=RiskCategory.COMMUNICATION,
                confidence=0.9,
                description=f"Critical ETX {etx:.1f} on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'etx_critical', 'mac': mac, 'etx': etx},
                auto_execute=True,
                source_data={'etx': etx, 'threshold': self.thresholds['etx_critical']}
            )
        elif etx >= self.thresholds['etx_high']:
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                category=RiskCategory.COMMUNICATION,
                confidence=0.8,
                description=f"High ETX {etx:.1f} on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'etx_high', 'mac': mac, 'etx': etx},
                auto_execute=True,
                source_data={'etx': etx, 'threshold': self.thresholds['etx_high']}
            )
        return None
    
    def _assess_hop_risk(self, hop_count: int, mac: str) -> Optional[RiskAssessment]:
        if hop_count >= self.thresholds['hop_critical']:
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                category=RiskCategory.COMMUNICATION,
                confidence=0.85,
                description=f"Excessive hops ({hop_count}) on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'hop_critical', 'mac': mac, 'hops': hop_count},
                auto_execute=True,
                source_data={'hop_count': hop_count, 'threshold': self.thresholds['hop_critical']}
            )
        elif hop_count >= self.thresholds['hop_high']:
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                category=RiskCategory.COMMUNICATION,
                confidence=0.75,
                description=f"High hop count ({hop_count}) on link {mac}",
                recommended_action=ActionType.REOPTIMIZE_COMM,
                action_params={'reason': 'hop_high', 'mac': mac, 'hops': hop_count},
                auto_execute=True,
                source_data={'hop_count': hop_count, 'threshold': self.thresholds['hop_high']}
            )
        return None
    
    def _detect_link_loss(self, mac: str) -> Optional[RiskAssessment]:
        """링크 손실 감지 (히스토리 기반)"""
        if mac not in self.link_history:
            return None
        
        history = self.link_history[mac]
        if len(history) < 3:
            return None
        
        # 최근 3개 샘플에서 데이터가 없거나 너무 오래됨
        recent = list(history)[-3:]
        current_time = time.time()
        
        if current_time - recent[-1]['timestamp'] > self.thresholds['link_loss_timeout']:
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                category=RiskCategory.COMMUNICATION,
                confidence=0.95,
                description=f"Link lost to {mac} (timeout {self.thresholds['link_loss_timeout']}s)",
                recommended_action=ActionType.RTL,
                action_params={'reason': 'link_loss', 'mac': mac},
                auto_execute=True,
                source_data={'mac': mac, 'timeout': self.thresholds['link_loss_timeout']}
            )
        return None
    
    def analyze_battery(self, battery_percent: float, uav_id: int) -> Optional[RiskAssessment]:
        """배터리 위험 분석"""
        if battery_percent <= self.battery_thresholds['critical']:
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                category=RiskCategory.BATTERY,
                confidence=0.95,
                description=f"Critical battery {battery_percent:.1f}% on UAV {uav_id}",
                recommended_action=ActionType.RTL,
                action_params={'reason': 'battery_critical', 'battery': battery_percent},
                auto_execute=True,
                source_data={'battery_percent': battery_percent}
            )
        elif battery_percent <= self.battery_thresholds['low']:
            return RiskAssessment(
                risk_level=RiskLevel.HIGH,
                category=RiskCategory.BATTERY,
                confidence=0.9,
                description=f"Low battery {battery_percent:.1f}% on UAV {uav_id}",
                recommended_action=ActionType.RTL,
                action_params={'reason': 'battery_low', 'battery': battery_percent},
                auto_execute=True,
                source_data={'battery_percent': battery_percent}
            )
        return None
    
    def get_aggregated_risk(self, risks: List[RiskAssessment]) -> RiskAssessment:
        """여러 위험을 종합하여 최고 위험도 반환"""
        if not risks:
            return RiskAssessment(
                risk_level=RiskLevel.NONE,
                category=RiskCategory.SYSTEM,
                confidence=1.0,
                description="No risks detected",
                recommended_action=ActionType.CONTINUE
            )
        
        # 최고 위험도 찾기
        priority = {RiskLevel.CRITICAL: 4, RiskLevel.HIGH: 3, RiskLevel.MEDIUM: 2, RiskLevel.LOW: 1, RiskLevel.NONE: 0}
        max_risk = max(risks, key=lambda r: priority[r.risk_level])
        
        # 종합 설명 생성
        categories = set(r.category for r in risks)
        combined_desc = f"Multiple risks: {', '.join(c.value for c in categories)}"
        
        # 가장 긴급한 액션 선택
        action_priority = {ActionType.ESTOP: 5, ActionType.RTL: 4, ActionType.REOPTIMIZE_COMM: 3, 
                          ActionType.HOLD: 2, ActionType.WARNING: 1, ActionType.CONTINUE: 0}
        max_action = max(risks, key=lambda r: action_priority.get(r.recommended_action, 0))
        
        return RiskAssessment(
            risk_level=max_risk.risk_level,
            category=list(categories)[0],
            confidence=max(r.confidence for r in risks),
            description=combined_desc,
            recommended_action=max_action.recommended_action,
            action_params={'combined': True, 'risk_count': len(risks)},
            auto_execute=any(r.auto_execute for r in risks),
            source_data={'individual_risks': len(risks)}
        )


class RiskAnalyzer:
    """통합 위험 분석기 (LLM Function Calling + Silvus 연동)"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.silvus_analyzer = SilvusRiskAnalyzer(self.config.get('silvus', {}))
        
        # LLM 클라이언트 (실제로는 llama.cpp 연동)
        self.llm_enabled = config.get('llm_enabled', False)
        self.llm_timeout = config.get('llm_timeout_ms', 200)
        
        # 폴백 모드
        self.fallback_mode = not self.llm_enabled
        
        logger.info(f"RiskAnalyzer initialized (LLM: {'enabled' if self.llm_enabled else 'disabled (fallback)'})")
    
    def analyze(self, 
                uav_states: List[UAVState],
                silvus_metrics: List[SilvusLinkMetrics],
                battery_levels: Dict[int, float]) -> RiskAssessment:
        """통합 위험 분석 수행"""
        
        all_risks = []
        
        # 1. Silvus 링크 품질 분석
        comm_risks = self.silvus_analyzer.analyze_link_quality(silvus_metrics)
        
        # 2. 배터리 분석
        for uav in uav_states:
            battery_risk = self.silvus_analyzer.analyze_battery(
                battery_levels.get(uav.uav_id, 100), uav.uav_id
            )
            if battery_risk:
                all_risks.append(battery_risk)
        
        # 3. 통신 위험 추가
        all_risks.extend(comm_risks)
        
        # 4. 종합 위험도 계산
        aggregated = self.silvus_analyzer.get_aggregated_risk(all_risks)
        
        # 5. LLM 상세 분석 (활성화된 경우)
        if self.llm_enabled and not self.fallback_mode:
            try:
                llm_result = self._call_llm_analysis(uav_states, silvus_metrics, battery_levels)
                # LLM 결과와 폴백 결과 결합
                if llm_result.risk_level.value > aggregated.risk_level.value:
                    aggregated = llm_result
            except Exception as e:
                logger.warning(f"LLM analysis failed, using fallback: {e}")
        
        return aggregated
    
    def _call_llm_analysis(self, uav_states, silvus_metrics, battery_levels) -> RiskAssessment:
        """LLM Function Calling을 통한 상세 분석"""
        # 실제 구현에서는 llama.cpp Function Calling 사용
        # 여기서는 시뮬레이션
        logger.debug("LLM analysis called (simulated)")
        
        # 폴백 결과 반환
        return RiskAssessment(
            risk_level=RiskLevel.NONE,
            category=RiskCategory.SYSTEM,
            confidence=0.5,
            description="LLM analysis not implemented",
            recommended_action=ActionType.CONTINUE
        )
    
    def enable_llm(self, enabled: bool = True):
        """LLM 활성화/비활성화"""
        self.llm_enabled = enabled
        self.fallback_mode = not enabled
        logger.info(f"LLM {'enabled' if enabled else 'disabled'}")


class RiskAwareArbitrator:
    """위험 인식 중재자"""
    
    def __init__(self, risk_analyzer: RiskAnalyzer, config: Dict = None):
        self.risk_analyzer = risk_analyzer
        self.config = config or {}
        self.last_assessment: Optional[RiskAssessment] = None
        self.action_history: deque = deque(maxlen=100)
    
    def assess_and_arbitrate(self, 
                             uav_states: List[UAVState],
                             silvus_metrics: List[SilvusLinkMetrics],
                             battery_levels: Dict[int, float],
                             pending_commands: List[Dict]) -> Dict[str, Any]:
        """위험 평가 및 중재"""
        
        # 위험 평가
        assessment = self.risk_analyzer.analyze(uav_states, silvus_metrics, battery_levels)
        self.last_assessment = assessment
        
        # 중재 결정
        decision = self._make_decision(assessment, pending_commands)
        
        # 기록
        self.action_history.append({
            'timestamp': time.time(),
            'assessment': assessment,
            'decision': decision
        })
        
        return decision
    
    def _make_decision(self, assessment: RiskAssessment, pending_commands: List[Dict]) -> Dict[str, Any]:
        """중재 결정"""
        decision = {
            'allow_commands': True,
            'blocked_commands': [],
            'forced_actions': [],
            'warnings': [],
            'risk_level': assessment.risk_level.value,
            'auto_execute': assessment.auto_execute
        }
        
        if assessment.risk_level == RiskLevel.CRITICAL:
            decision['allow_commands'] = False
            decision['forced_actions'].append({
                'action': assessment.recommended_action.value,
                'params': assessment.action_params,
                'reason': assessment.description
            })
            decision['blocked_commands'] = [c.get('id') for c in pending_commands]
            
        elif assessment.risk_level == RiskLevel.HIGH:
            # 속도/고도 제한
            decision['warnings'].append(f"HIGH risk: {assessment.description}")
            for cmd in pending_commands:
                if cmd.get('type') in ['velocity', 'altitude']:
                    decision['blocked_commands'].append(cmd.get('id'))
                    
        elif assessment.risk_level == RiskLevel.MEDIUM:
            decision['warnings'].append(f"MEDIUM risk: {assessment.description}")
            
        return decision
    
    def get_status(self) -> Dict:
        return {
            'last_assessment': self.last_assessment.__dict__ if self.last_assessment else None,
            'action_history_len': len(self.action_history)
        }


def create_risk_analyzer(config: Dict = None) -> RiskAnalyzer:
    """팩토리 함수"""
    return RiskAnalyzer(config or {})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== Risk Analyzer Test ===")
    
    # 설정
    config = {
        'silvus': {
            'per_critical': 0.15,
            'per_high': 0.10,
            'snr_critical': 5.0,
            'snr_high': 10.0,
            'etx_critical': 5.0,
            'etx_high': 3.0,
        },
        'llm_enabled': False
    }
    
    # 분석기 생성
    analyzer = create_risk_analyzer(config)
    silvus_analyzer = analyzer.silvus_analyzer
    
    # 테스트 데이터
    from swarm.silvus_interface import SilvusLinkMetrics
    
    metrics = [
        SilvusLinkMetrics("aa:bb:cc:dd:ee:01", 20.0, 0.02, -60, 1.2, 1, 5745, 50, 10),
        SilvusLinkMetrics("aa:bb:cc:dd:ee:02", 8.0, 0.12, -85, 3.5, 2, 5765, 30, 25),
        SilvusLinkMetrics("aa:bb:cc:dd:ee:03", 3.0, 0.25, -92, 8.0, 3, 5785, 15, 40),
    ]
    
    uav_states = []  # 빈 리스트로 테스트
    battery_levels = {1: 85, 2: 90, 3: 15, 4: 70}
    
    # Silvus 위험 분석
    print("=== Silvus Link Quality Analysis ===")
    silvus_analyzer.update_link_metrics(metrics)
    risks = silvus_analyzer.analyze_link_quality(metrics)
    
    for risk in risks:
        print(f"  [{risk.risk_level.value}] {risk.category.value}: {risk.description}")
        print(f"    Action: {risk.recommended_action.value} (auto={risk.auto_execute})")
    
    # 배터리 분석
    print("\n=== Battery Analysis ===")
    for uav_id, battery in battery_levels.items():
        risk = silvus_analyzer.analyze_battery(battery, uav_id)
        if risk:
            print(f"  UAV {uav_id}: [{risk.risk_level.value}] {risk.description}")
    
    # 종합 위험도
    print("\n=== Aggregated Risk ===")
    all_risks = []
    for uav_id, battery in battery_levels.items():
        risk = silvus_analyzer.analyze_battery(battery, uav_id)
        if risk:
            all_risks.append(risk)
    all_risks.extend(risks)
    
    aggregated = silvus_analyzer.get_aggregated_risk(all_risks)
    print(f"Overall: [{aggregated.risk_level.value}] {aggregated.description}")
    print(f"Action: {aggregated.recommended_action.value} (auto={aggregated.auto_execute})")
    
    # 전체 위험 분석기 테스트
    print("\n=== Full Risk Analyzer ===")
    analyzer = RiskAnalyzer({'silvus': {'per_critical': 0.15}, 'llm_enabled': False})
    assessment = analyzer.analyze([], metrics, battery_levels)
    print(f"Overall Assessment: [{assessment.risk_level.value}] {assessment.description}")
    print(f"Action: {assessment.recommended_action.value}")
    
    # 중재자 테스트
    print("\n=== Risk Arbitrator ===")
    arbitrator = RiskAwareArbitrator(analyzer)
    decision = arbitrator.assess_and_arbitrate([], metrics, battery_levels, [])
    print(f"Decision: allow={decision['allow_commands']}, forced={decision['forced_actions']}")
    
    print("\n=== Test Complete ===")