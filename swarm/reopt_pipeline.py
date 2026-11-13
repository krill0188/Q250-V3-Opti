#!/usr/bin/env python3
"""
실시간 재최적화 파이프라인
링크 품질 저하 감지 → IQP 재실행 → Silvus 채널 변경 자동화
"""

import asyncio
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from collections import deque
import numpy as np

from swarm.silvus_interface import SilvusInterface, create_silvus_interface
from swarm.iqp_optimizer import IQPOptimizer, OptimizationResult, create_optimizer, IncrementalOptimizer, OptimizationStatus

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    PER_HIGH = "PER_HIGH"
    SNR_LOW = "SNR_LOW"
    ETX_HIGH = "ETX_HIGH"
    HOP_COUNT_INCREASE = "HOP_COUNT_INCREASE"
    LINK_LOST = "LINK_LOST"
    MANUAL = "MANUAL"
    PERIODIC = "PERIODIC"


@dataclass
class TriggerEvent:
    trigger_type: TriggerType
    source_mac: str
    metric_value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


@dataclass
class ReoptCycle:
    """재최적화 사이클 기록"""
    cycle_id: int
    trigger: TriggerEvent
    start_time: float
    end_time: Optional[float] = None
    status: str = "RUNNING"
    previous_obj: float = 0.0
    new_obj: float = 0.0
    freq_changes: Dict[int, Tuple[int, int]] = field(default_factory=dict)  # uav_id -> (old, new)
    error: Optional[str] = None


class TriggerMonitor:
    """트리거 조건 모니터링"""
    
    def __init__(self, 
                 per_threshold: float = 0.1,
                 snr_threshold_db: float = 10.0,
                 etx_threshold: float = 3.0,
                 hop_threshold: int = 4,
                 check_interval: float = 1.0):
        
        self.per_threshold = per_threshold
        self.snr_threshold = snr_threshold_db
        self.etx_threshold = etx_threshold
        self.hop_threshold = hop_threshold
        self.check_interval = check_interval
        
        # 히스테리시스 (진동 방지)
        self.per_hysteresis = 0.02
        self.snr_hysteresis = 2.0
        
        # 상태 추적
        self.prev_metrics: Dict[str, Dict] = {}
        self.trigger_history: deque = deque(maxlen=100)
    
    def check(self, silvus: 'SilvusInterface') -> List[TriggerEvent]:
        """트리거 조건 체크"""
        events = []
        neighbors = silvus.get_neighbors()
        
        for link in neighbors:
            mac = link.neighbor_mac
            prev = self.prev_metrics.get(mac, {})
            
            # PER 체크
            if link.per > self.per_threshold:
                if prev.get('per', 0) <= self.per_threshold + self.per_hysteresis:
                    events.append(TriggerEvent(
                        trigger_type=TriggerType.PER_HIGH,
                        source_mac=mac,
                        metric_value=link.per,
                        threshold=self.per_threshold,
                        metadata={'prev_per': prev.get('per', 0)}
                    ))
            
            # SNR 체크
            if link.snr_db < self.snr_threshold:
                if prev.get('snr_db', 100) >= self.snr_threshold + self.snr_hysteresis:
                    events.append(TriggerEvent(
                        trigger_type=TriggerType.SNR_LOW,
                        source_mac=mac,
                        metric_value=link.snr_db,
                        threshold=self.snr_threshold,
                        metadata={'prev_snr': prev.get('snr_db', 100)}
                    ))
            
            # ETX 체크
            if link.etx > self.etx_threshold:
                events.append(TriggerEvent(
                    trigger_type=TriggerType.ETX_HIGH,
                    source_mac=mac,
                    metric_value=link.etx,
                    threshold=self.etx_threshold
                ))
            
            # 홉 수 체크
            if link.hop_count >= self.hop_threshold:
                events.append(TriggerEvent(
                    trigger_type=TriggerType.HOP_COUNT_INCREASE,
                    source_mac=mac,
                    metric_value=link.hop_count,
                    threshold=self.hop_threshold
                ))
            
            # 현재 메트릭 저장
            self.prev_metrics[mac] = {
                'per': link.per,
                'snr_db': link.snr_db,
                'etx': link.etx,
                'hop_count': link.hop_count
            }
        
        # 링크 손실 감지
        current_macs = {n.neighbor_mac for n in neighbors}
        for mac in self.prev_metrics:
            if mac not in current_macs:
                events.append(TriggerEvent(
                    trigger_type=TriggerType.LINK_LOST,
                    source_mac=mac,
                    metric_value=0,
                    threshold=0,
                    metadata={'last_seen': self.prev_metrics[mac]}
                ))
        
        # 이벤트 기록
        for event in events:
            self.trigger_history.append(event)
            logger.warning(f"Trigger: {event.trigger_type.value} from {event.source_mac} "
                          f"(value={event.metric_value:.2f}, threshold={event.threshold:.2f})")
        
        return events


class ReoptimizationPipeline:
    """
    실시간 재최적화 파이프라인
    트리거 감지 → IQP 재실행 → 채널 변경 → 검증 → 완료/롤백
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 컴포넌트 초기화
        self.silvus = create_silvus_interface(config.get("silvus", {"mock_mode": True}))
        self.optimizer = create_optimizer(config.get("optimizer", {}))
        self.trigger_monitor = TriggerMonitor(
            per_threshold=config.get("per_threshold", 0.1),
            snr_threshold_db=config.get("snr_threshold_db", 10.0),
            etx_threshold=config.get("etx_threshold", 3.0),
            hop_threshold=config.get("hop_threshold", 4),
            check_interval=config.get("check_interval", 1.0)
        )
        
        # 파이프라인 상태
        self.running = False
        self.cycle_count = 0
        self.cycle_history: deque = deque(maxlen=50)
        self.last_cycle: Optional[ReoptCycle] = None
        
        # 콜백
        self.on_cycle_start: Optional[Callable[[ReoptCycle], None]] = None
        self.on_cycle_complete: Optional[Callable[[ReoptCycle], None]] = None
        self.on_rollback: Optional[Callable[[ReoptCycle], None]] = None
        
        # 스레드
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 설정
        self.min_cycle_interval = config.get("min_cycle_interval", 2.0)
        self.max_solve_time = config.get("max_solve_time", 5.0)
        self.rollback_on_degradation = config.get("rollback_on_degradation", True)
        self.degradation_threshold = config.get("degradation_threshold", 0.1)  # 10% 악화 시 롤백
        
        # 이전 주파수 계획 (롤백용)
        self.last_freq_plan: Dict[str, int] = {}
    
    def start(self):
        """파이프라인 시작"""
        if self.running:
            logger.warning("Pipeline already running")
            return
        
        self.silvus.initialize()
        self.running = True
        self._stop_event.clear()
        
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Reoptimization pipeline started")
    
    def stop(self):
        """파이프라인 중지"""
        self.running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Reoptimization pipeline stopped")
    
    def _monitor_loop(self):
        """모니터링 루프"""
        while not self._stop_event.is_set():
            try:
                # 트리거 체크
                events = self.trigger_monitor.check(self.silvus)
                
                for event in events:
                    # 최소 간격 체크
                    if self.last_cycle and time.time() - self.last_cycle.start_time < self.min_cycle_interval:
                        logger.debug(f"Skipping trigger {event.trigger_type.value}: min interval not elapsed")
                        continue
                    
                    # 재최적화 실행
                    asyncio.run(self._execute_reopt_cycle(event))
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            time.sleep(self.trigger_monitor.check_interval)
    
    async def _execute_reopt_cycle(self, trigger: TriggerEvent):
        """재최적화 사이클 실행"""
        self.cycle_count += 1
        cycle = ReoptCycle(
            cycle_id=self.cycle_count,
            trigger=trigger,
            start_time=time.time()
        )
        self.last_cycle = cycle
        
        if self.on_cycle_start:
            self.on_cycle_start(cycle)
        
        logger.info(f"Starting reopt cycle {cycle.cycle_id}: {trigger.trigger_type.value} from {trigger.source_mac}")
        
        try:
            # 1. 현재 주파수 계획 백업 (롤백용)
            self._backup_current_plan()
            
            # 2. IQP 재최적화 실행 (비동기)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: self.optimizer.solve(self.silvus)
            )
            
            cycle.end_time = time.time()
            cycle.previous_obj = self.last_cycle.new_obj if self.last_cycle else 0
            cycle.new_obj = result.objective_value
            
            # 주파수 변경 사항 기록
            cycle.freq_changes = self._compute_freq_changes(result)
            
            if result.status in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
                # 3. 품질 검증
                if self._validate_result(result):
                    # 4. 주파수 계획 적용
                    self._apply_frequency_plan(result)
                    cycle.status = "SUCCESS"
                    logger.info(f"Cycle {cycle.cycle_id} SUCCESS: obj {cycle.previous_obj:.2f} -> {cycle.new_obj:.2f}")
                else:
                    # 품질 저하 시 롤백
                    if self.rollback_on_degradation:
                        self._rollback()
                        cycle.status = "ROLLED_BACK"
                        logger.warning(f"Cycle {cycle.cycle_id} ROLLED BACK: quality degradation")
                    else:
                        cycle.status = "DEGRADED"
                        logger.warning(f"Cycle {cycle.cycle_id} DEGRADED but rollback disabled")
            else:
                cycle.status = f"FAILED: {result.status.value}"
                cycle.error = f"Optimization failed with status {result.status.value}"
                logger.error(f"Cycle {cycle.cycle_id} FAILED: {result.status.value}")
                
        except Exception as e:
            cycle.end_time = time.time()
            cycle.status = f"ERROR: {str(e)}"
            cycle.error = str(e)
            logger.error(f"Cycle {cycle.cycle_id} ERROR: {e}")
        
        finally:
            self.cycle_history.append(cycle)
            if self.on_cycle_complete:
                self.on_cycle_complete(cycle)
    
    def _backup_current_plan(self):
        """현재 주파수 계획 백업"""
        self.last_freq_plan = {}
        neighbors = self.silvus.get_neighbors()
        for link in neighbors:
            # 실제로는 Silvus에서 현재 채널 조회
            self.last_freq_plan[link.neighbor_mac] = link.channel_mhz
    
    def _compute_freq_changes(self, result: OptimizationResult) -> Dict[int, Tuple[int, int]]:
        """주파수 변경 사항 계산"""
        changes = {}
        for uav_id, freq in result.frequencies.items():
            old = self.last_freq_plan.get(f"uav_{uav_id}", freq.channel_mhz)
            if old != freq.channel_mhz:
                changes[uav_id] = (old, freq.channel_mhz)
        return changes
    
    def _validate_result(self, result: OptimizationResult) -> bool:
        """결과 품질 검증"""
        if not self.last_cycle:
            return True  # 첫 사이클은 무조건 통과
        
        # 목적함수 향상 또는 유지 확인
        improvement = (result.objective_value - self.last_cycle.new_obj) / abs(self.last_cycle.new_obj) if self.last_cycle.new_obj != 0 else 0
        
        if improvement < -self.degradation_threshold:
            logger.warning(f"Objective degraded by {improvement:.1%} (threshold: {self.degradation_threshold:.1%})")
            return False
        
        # 연결성 확인
        if result.connectivity_score > 5.0:  # ETX 임계값
            logger.warning(f"Connectivity degraded: ETX={result.connectivity_score:.2f}")
            return False
        
        return True
    
    def _apply_frequency_plan(self, result: OptimizationResult):
        """주파수 계획 Silvus에 적용"""
        freq_plan = {}
        for uav_id, freq in result.frequencies.items():
            # UAV ID를 MAC으로 매핑 (실제로는 매핑 테이블 필요)
            mac = f"aa:bb:cc:dd:ee:{uav_id:02x}"
            freq_plan[mac] = freq.channel_mhz
        
        self.silvus.push_frequency_plan(freq_plan)
        self.last_freq_plan = freq_plan
        logger.info(f"Applied frequency plan: {freq_plan}")
    
    def _rollback(self):
        """이전 주파수 계획으로 롤백"""
        if self.last_freq_plan:
            logger.warning("Rolling back to previous frequency plan")
            self.silvus.push_frequency_plan(self.last_freq_plan)
            if self.on_rollback and self.last_cycle:
                self.on_rollback(self.last_cycle)
    
    def trigger_manual_reopt(self, reason: str = "Manual trigger"):
            """수동 재최적화 트리거"""
            event = TriggerEvent(
                trigger_type=TriggerType.MANUAL,
                source_mac="manual",
                metric_value=0,
                threshold=0,
                metadata={"reason": reason}
            )
            asyncio.run(self._execute_reopt_cycle(event))
    
    def get_status(self) -> Dict:
        """파이프라인 상태 조회"""
        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "last_cycle": {
                "id": self.last_cycle.cycle_id if self.last_cycle else None,
                "status": self.last_cycle.status if self.last_cycle else None,
                "trigger": self.last_cycle.trigger.trigger_type.value if self.last_cycle else None,
                "duration_sec": (self.last_cycle.end_time - self.last_cycle.start_time) if self.last_cycle and self.last_cycle.end_time else None,
                "objective_improvement": (self.last_cycle.new_obj - self.last_cycle.previous_obj) if self.last_cycle else None
            },
            "recent_cycles": [
                {
                    "id": c.cycle_id,
                    "status": c.status,
                    "trigger": c.trigger.trigger_type.value,
                    "duration": c.end_time - c.start_time if c.end_time else None
                }
                for c in list(self.cycle_history)[-10:]
            ],
            "silvus_status": {
                "neighbors": len(self.silvus.get_neighbors()),
                "alerts": len(self.silvus.get_alerts())
            }
        }
    
    def get_cycle_history(self) -> List[ReoptCycle]:
        return list(self.cycle_history)


class PeriodicReoptScheduler:
    """주기적 재최적화 스케줄러"""
    
    def __init__(self, pipeline: ReoptimizationPipeline, interval_sec: float = 30.0):
        self.pipeline = pipeline
        self.interval = interval_sec
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self):
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
    
    def _run(self):
        while not self._stop_event.is_set():
            time.sleep(self.interval)
            if self.running and not self._stop_event.is_set():
                logger.info("Periodic reoptimization trigger")
                self.pipeline.trigger_manual_reopt("Periodic scheduled reoptimization")


def create_pipeline(config: Dict[str, Any]) -> ReoptimizationPipeline:
    """팩토리 함수"""
    return ReoptimizationPipeline(config)


# 콜백 예시
def on_cycle_start(cycle: ReoptCycle):
    print(f"[CYCLE START] #{cycle.cycle_id}: {cycle.trigger.trigger_type.value}")


def on_cycle_complete(cycle: ReoptCycle):
    duration = cycle.end_time - cycle.start_time if cycle.end_time else 0
    print(f"[CYCLE END] #{cycle.cycle_id}: {cycle.status} in {duration:.2f}s")


def on_rollback(cycle: ReoptCycle):
    print(f"[ROLLBACK] Cycle {cycle.cycle_id} rolled back")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("=== Reoptimization Pipeline Test ===")
    
    config = {
        "silvus": {"mock_mode": True},
        "optimizer": {
            "grid": {
                "x_range": (0, 1000),
                "y_range": (0, 1000),
                "z_range": (50, 200),
                "resolution": 100
            },
            "uav_ids": [1, 2, 3, 4],
            "time_limit_sec": 10.0
        },
        "per_threshold": 0.1,
        "snr_threshold_db": 10.0,
        "etx_threshold": 3.0,
        "check_interval": 2.0,
        "min_cycle_interval": 5.0
    }
    
    # 파이프라인 생성
    pipeline = create_pipeline(config)
    pipeline.on_cycle_start = on_cycle_start
    pipeline.on_cycle_complete = on_cycle_complete
    pipeline.on_rollback = on_rollback
    
    # 시작
    pipeline.start()
    
    # 잠시 대기하며 트리거 발생 대기
    print("\nPipeline running. Waiting for triggers...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # 주기적 스케줄러도 시작
        scheduler = PeriodicReoptScheduler(pipeline, interval_sec=10.0)
        scheduler.start()
        
        # 30초간 실행
        for i in range(30):
            time.sleep(1)
            if i % 5 == 0:
                status = pipeline.get_status()
                print(f"Status: cycles={status['cycle_count']}, last={status['last_cycle']['status'] if status['last_cycle'] else 'None'}")
        
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        pipeline.stop()
        print("Pipeline stopped")