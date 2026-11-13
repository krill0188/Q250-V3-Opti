#!/usr/bin/env python3
"""
Silvus StreamCaster Mock Interface for Development/Testing
실제 Silvus SDK 없이 개발/테스트 가능하도록 Mock 데이터 제공
"""

import numpy as np
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LinkStatus(Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    LOST = "LOST"


class OptimizationStatus(Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class LinkQuality:
    neighbor_mac: str
    snr_db: float
    per: float
    rssi_dbm: float
    tx_rate_mbps: float
    latency_ms: float
    hop_count: int
    channel_mhz: int
    bandwidth_mhz: int
    etx: float
    status: LinkStatus = LinkStatus.GOOD
    timestamp: float = field(default_factory=time.time)


@dataclass
class SilvusLinkMetrics:
    """Silvus 링크 품질 메트릭 (위험 분석용)"""
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
class RadioHealth:
    temperature_c: float
    tx_power_dbm: float
    cpu_usage_pct: float
    memory_usage_pct: float
    uptime_seconds: float


class SilvusInterface:
    """
    Silvus StreamCaster 인터페이스 (Mock 구현)
    실제 환경에서는 Silvus SDK (REST/gRPC/SNMP)로 교체
    """
    
    def __init__(self, radio_ip: str = "192.168.1.100", mock_mode: bool = True):
        self.radio_ip = radio_ip
        self.mock_mode = mock_mode
        self._neighbors: Dict[str, LinkQuality] = {}
        self._radio_health: Optional[RadioHealth] = None
        self._initialized = False
        
        if mock_mode:
            self._init_mock_data()
    
    def _init_mock_data(self):
        """개발/테스트용 Mock 데이터 초기화"""
        # 4대 UAV 메쉬 네트워크 시뮬레이션
        macs = [
            "aa:bb:cc:dd:ee:01",
            "aa:bb:cc:dd:ee:02", 
            "aa:bb:cc:dd:ee:03",
            "aa:bb:cc:dd:ee:04"
        ]
        
        for i, mac in enumerate(macs):
            # 거리에 따른 품질 차이 시뮬레이션
            base_snr = 25 - i * 4  # 25, 21, 17, 13 dB
            base_per = 0.01 + i * 0.03  # 1%, 4%, 7%, 10%
            
            self._neighbors[mac] = LinkQuality(
                neighbor_mac=mac,
                snr_db=base_snr + random.uniform(-2, 2),
                per=max(0, min(0.5, base_per + random.uniform(-0.01, 0.01))),
                rssi_dbm=-60 - i * 5 + random.uniform(-3, 3),
                tx_rate_mbps=50 - i * 8 + random.uniform(-5, 5),
                latency_ms=10 + i * 5 + random.uniform(-2, 2),
                hop_count=1 + (i // 2),
                channel_mhz=5745 + (i % 3) * 20,
                bandwidth_mhz=20,
                etx=1.0 / (1 - max(0.001, 0.01 + i * 0.03)),
                status=self._snr_to_status(base_snr)
            )
        
        self._radio_health = RadioHealth(
            temperature_c=42.0 + random.uniform(-3, 3),
            tx_power_dbm=23.0,
            cpu_usage_pct=34.0 + random.uniform(-5, 5),
            memory_usage_pct=45.0 + random.uniform(-5, 5),
            uptime_seconds=3600.0
        )
        self._initialized = True
        logger.info(f"Mock Silvus initialized with {len(self._neighbors)} neighbors")
    
    def _snr_to_status(self, snr: float) -> LinkStatus:
        if snr >= 20: return LinkStatus.EXCELLENT
        elif snr >= 15: return LinkStatus.GOOD
        elif snr >= 10: return LinkStatus.FAIR
        elif snr >= 5: return LinkStatus.POOR
        return LinkStatus.LOST
    
    def initialize(self) -> bool:
        """인터페이스 초기화"""
        if self.mock_mode:
            return self._initialized
        # 실제 구현: Silvus SDK 연결
        logger.warning("Real Silvus SDK not implemented in mock mode")
        return False
    
    def get_neighbors(self) -> List[LinkQuality]:
        """이웃 노드 링크 품질 목록 반환"""
        # Mock: 시간 경과에 따른 품질 변화 시뮬레이션
        for mac, link in self._neighbors.items():
            link.snr_db += random.uniform(-0.5, 0.5)
            link.per = max(0, min(0.5, link.per + random.uniform(-0.005, 0.005)))
            link.etx = 1.0 / (1 - max(0.001, link.per))
            link.timestamp = time.time()
        return list(self._neighbors.values())
    
    def get_link_matrix(self) -> np.ndarray:
        """N×N 링크 품질 행렬 반환 (ETX 기반 비용)"""
        neighbors = self.get_neighbors()
        n = len(neighbors)
        etx_matrix = np.full((n, n), np.inf)
        macs = [n.neighbor_mac for n in neighbors]
        
        for i, mac_i in enumerate(macs):
            etx_matrix[i, i] = 0
            for j, mac_j in enumerate(macs):
                if i != j:
                    # 실제로는 라우팅 테이블에서 조회
                    etx_matrix[i, j] = self._get_etx_between(mac_i, mac_j)
        return etx_matrix
    
    def _get_etx_between(self, mac1: str, mac2: str) -> float:
        """두 노드 간 ETX 추정"""
        link1 = self._neighbors.get(mac1)
        link2 = self._neighbors.get(mac2)
        if link1 and link2:
            return (link1.etx + link2.etx) / 2
        return np.inf
    
    def get_interference_vector(self) -> np.ndarray:
        """각 노드별 간섭 레벨 (PER 기반)"""
        neighbors = self.get_neighbors()
        return np.array([n.per for n in neighbors])
    
    def get_snr_vector(self) -> np.ndarray:
        """각 노드별 SNR 벡터"""
        neighbors = self.get_neighbors()
        return np.array([n.snr_db for n in neighbors])
    
    def get_radio_health(self) -> Optional[RadioHealth]:
        """라디오 건강 상태"""
        if self._radio_health:
            self._radio_health.temperature_c += random.uniform(-0.5, 0.5)
            self._radio_health.cpu_usage_pct = max(0, min(100, 
                self._radio_health.cpu_usage_pct + random.uniform(-2, 2)))
        return self._radio_health
    
    def trigger_reoptimization(self) -> bool:
        """링크 품질 저하 시 재최적화 필요 여부"""
        neighbors = self.get_neighbors()
        for link in neighbors:
            if link.per > 0.1 or link.snr_db < 10 or link.etx > 3:
                logger.warning(f"Reoptimization triggered by {link.neighbor_mac}: PER={link.per:.3f}, SNR={link.snr_db:.1f}dB")
                return True
        return False
    
    def push_frequency_plan(self, freq_assignments: Dict[str, int]) -> bool:
        """최적화 결과 주파수 할당 푸시"""
        logger.info(f"Pushing frequency plan: {freq_assignments}")
        for mac, freq in freq_assignments.items():
            logger.info(f"  {mac} -> {freq} MHz")
        return True
    
    def set_channel(self, mac: str, channel_mhz: int) -> bool:
        """개별 노드 채널 변경"""
        logger.info(f"Setting {mac} to {channel_mhz} MHz")
        return True
    
    def get_alerts(self) -> List[Dict]:
        """알림 목록"""
        alerts = []
        for link in self.get_neighbors():
            if link.per > 0.15:
                alerts.append({"severity": "CRITICAL", "source": link.neighbor_mac, "message": f"PER critical: {link.per:.2%}"})
            elif link.per > 0.1:
                alerts.append({"severity": "WARNING", "source": link.neighbor_mac, "message": f"PER high: {link.per:.2%}"})
            if link.snr_db < 5:
                alerts.append({"severity": "CRITICAL", "source": link.neighbor_mac, "message": f"SNR critical: {link.snr_db:.1f}dB"})
        return alerts
    
    def shutdown(self):
        """종료"""
        logger.info("Silvus interface shutdown")
        self._initialized = False


def create_silvus_interface(config: Optional[Dict] = None) -> SilvusInterface:
    """팩토리 함수"""
    config = config or {}
    return SilvusInterface(
        radio_ip=config.get("radio_ip", "192.168.1.100"),
        mock_mode=config.get("mock_mode", True)
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 테스트 실행
    silvus = create_silvus_interface({"mock_mode": True})
    
    print("=== Silvus Mock Interface Test ===")
    
    # 이웃 조회
    neighbors = silvus.get_neighbors()
    print(f"\nNeighbors ({len(neighbors)}):")
    for n in neighbors:
        print(f"  {n.neighbor_mac}: SNR={n.snr_db:.1f}dB, PER={n.per:.2%}, ETX={n.etx:.2f}, Status={n.status.value}")
    
    # 링크 매트릭스
    print("\nLink Matrix (ETX):")
    matrix = silvus.get_link_matrix()
    print(matrix)
    
    # 간섭 벡터
    interference = silvus.get_interference_vector()
    print(f"\nInterference (PER): {interference}")
    
    # 재최적화 트리거 확인
    triggered = silvus.trigger_reoptimization()
    print(f"\nReoptimization triggered: {triggered}")
    
    # 주파수 계획 푸시 테스트
    plan = {"aa:bb:cc:dd:ee:01": 5745, "aa:bb:cc:dd:ee:02": 5765, 
            "aa:bb:cc:dd:ee:03": 5785, "aa:bb:cc:dd:ee:04": 5805}
    silvus.push_frequency_plan(plan)
    
    # 알림 확인
    alerts = silvus.get_alerts()
    print(f"\nAlerts: {len(alerts)}")
    for a in alerts:
        print(f"  [{a['severity']}] {a['source']}: {a['message']}")
    
    print("\n=== Test Complete ===")