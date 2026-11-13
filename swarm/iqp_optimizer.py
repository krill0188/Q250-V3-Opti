#!/usr/bin/env python3
"""
IQP 폐루프 최적화 엔진 (Prototype with PuLP)
실제 운영 시 CPLEX/Gurobi로 교체 가능
"""

import numpy as np
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
import json

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False
    print("Warning: PuLP not installed. Install with: pip install pulp")

from swarm.silvus_interface import SilvusInterface, LinkQuality, create_silvus_interface, OptimizationStatus

logger = logging.getLogger(__name__)


@dataclass
class UAVPosition:
    """UAV 위치 (이산 그리드)"""
    uav_id: int
    x: int  # 그리드 X
    y: int  # 그리드 Y
    z: int  # 고도 레벨
    
    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)
    
    def distance_to(self, other: 'UAVPosition') -> float:
        return np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)


@dataclass
class FrequencyAssignment:
    """주파수 할당"""
    uav_id: int
    channel_mhz: int
    bandwidth_mhz: int = 20
    power_dbm: float = 23.0


@dataclass
class OptimizationResult:
    """최적화 결과"""
    status: OptimizationStatus
    positions: Dict[int, UAVPosition]
    frequencies: Dict[int, FrequencyAssignment]
    objective_value: float
    coverage_score: float
    interference_score: float
    connectivity_score: float
    solve_time_sec: float
    iterations: int = 0
    timestamp: float = field(default_factory=time.time)


class GridMap:
    """이산 그리드 맵"""
    
    def __init__(self, x_range: Tuple[int, int], y_range: Tuple[int, int], z_range: Tuple[int, int], resolution: int = 10):
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.resolution = resolution
        self.valid_cells = self._generate_valid_cells()
    
    def _generate_valid_cells(self) -> List[Tuple[int, int, int]]:
        cells = []
        for x in range(self.x_range[0], self.x_range[1] + 1, self.resolution):
            for y in range(self.y_range[0], self.y_range[1] + 1, self.resolution):
                for z in range(self.z_range[0], self.z_range[1] + 1, self.resolution):
                    cells.append((x, y, z))
        return cells
    
    def is_valid(self, pos: UAVPosition) -> bool:
        return (self.x_range[0] <= pos.x <= self.x_range[1] and
                self.y_range[0] <= pos.y <= self.y_range[1] and
                self.z_range[0] <= pos.z <= self.z_range[1])
    
    def get_neighbors(self, pos: UAVPosition, radius: int = 1) -> List[UAVPosition]:
        neighbors = []
        for dx in range(-radius * self.resolution, (radius + 1) * self.resolution, self.resolution):
            for dy in range(-radius * self.resolution, (radius + 1) * self.resolution, self.resolution):
                for dz in range(-radius * self.resolution, (radius + 1) * self.resolution, self.resolution):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    new_pos = UAVPosition(
                        uav_id=0,  # 임시
                        x=pos.x + dx,
                        y=pos.y + dy,
                        z=pos.z + dz
                    )
                    if self.is_valid(new_pos):
                        neighbors.append(new_pos)
        return neighbors


class IQPOptimizer:
    """
    IQP 폐루프 최적화 엔진
    목적: Coverage - λ₁·Interference - λ₂·ETX_Cost 최대화
    """
    
    def __init__(self, 
                 grid_map: GridMap,
                 uav_ids: List[int],
                 silvus: SilvusInterface,
                 solver: str = "PULP_CBC_CMD",
                 time_limit_sec: float = 5.0):
        
        self.grid_map = grid_map
        self.uav_ids = uav_ids
        self.silvus = silvus
        self.solver_name = solver
        self.time_limit = time_limit_sec
        
        # 가중치
        self.lambda_coverage = 1.0
        self.lambda_interference = 0.5
        self.lambda_connectivity = 0.3
        
        # 제약 파라미터
        self.max_hops = 3
        self.min_snr_db = 10.0
        self.max_per = 0.1
        self.max_etx = 3.0
        
        # 사용 가능 채널 (5GHz UNII 대역)
        self.available_channels = [5745, 5765, 5785, 5805, 5825]  # MHz
        
        # 이전 해 (warm start용)
        self.previous_solution: Optional[OptimizationResult] = None
        
        logger.info(f"IQP Optimizer initialized for {len(uav_ids)} UAVs")
    
    def set_weights(self, coverage: float, interference: float, connectivity: float):
        """가중치 설정"""
        self.lambda_coverage = coverage
        self.lambda_interference = interference
        self.lambda_connectivity = connectivity
    
    def set_constraints(self, max_hops: int = 3, min_snr: float = 10.0, 
                       max_per: float = 0.1, max_etx: float = 3.0):
        """제약 조건 설정"""
        self.max_hops = max_hops
        self.min_snr_db = min_snr
        self.max_per = max_per
        self.max_etx = max_etx
    
    def solve(self, silvus: SilvusInterface) -> OptimizationResult:
        """최적화 실행"""
        start_time = time.time()
        
        if not PULP_AVAILABLE:
            return self._fallback_solve(silvus)
        
        try:
            # Silvus에서 실측 데이터 가져오기
            neighbors = silvus.get_neighbors()
            etx_matrix = silvus.get_link_matrix()
            per_vector = silvus.get_interference_vector()
            snr_vector = silvus.get_snr_vector()
            
            # 문제 정의
            prob = pulp.LpProblem("UAV_FANET_Optimization", pulp.LpMaximize)
            
            # 결정 변수
            # 위치 변수: x_uav_cell = 1 if UAV at cell
            pos_vars = {}
            for uav_id in self.uav_ids:
                for cell in self.grid_map.valid_cells:
                    var_name = f"pos_{uav_id}_{cell[0]}_{cell[1]}_{cell[2]}"
                    pos_vars[(uav_id, cell)] = pulp.LpVariable(var_name, cat='Binary')
            
            # 주파수 할당 변수
            freq_vars = {}
            for uav_id in self.uav_ids:
                for ch_idx, channel in enumerate(self.available_channels):
                    var_name = f"freq_{uav_id}_{ch_idx}"
                    freq_vars[(uav_id, ch_idx)] = pulp.LpVariable(var_name, cat='Binary')
            
            # 제약 1: 각 UAV는 정확히 하나의 위치에 배치
            for uav_id in self.uav_ids:
                prob += pulp.lpSum(pos_vars[(uav_id, cell)] for cell in self.grid_map.valid_cells) == 1
            
            # 제약 2: 각 UAV는 정확히 하나의 주파수 채널 사용
            for uav_id in self.uav_ids:
                prob += pulp.lpSum(freq_vars[(uav_id, ch_idx)] for ch_idx in range(len(self.available_channels))) == 1
            
            # 제약 3: 같은 채널 사용 시 거리 제약 (간섭 방지)
            for i, uav_i in enumerate(self.uav_ids):
                for j, uav_j in enumerate(self.uav_ids):
                    if i >= j:
                        continue
                    for ch_idx in range(len(self.available_channels)):
                        # 같은 채널 사용 시 최소 거리 보장
                        for cell_i in self.grid_map.valid_cells:
                            for cell_j in self.grid_map.valid_cells:
                                dist = np.sqrt(sum((a - b)**2 for a, b in zip(cell_i, cell_j)))
                                if dist < 50:  # 50m 미만이면 같은 채널 금지
                                    prob += (freq_vars[(uav_i, ch_idx)] + freq_vars[(uav_j, ch_idx)] +
                                             pos_vars[(uav_i, cell_i)] + pos_vars[(uav_j, cell_j)]) <= 3
            
            # 목적 함수 구성
            # 1. 커버리지 점수 (그리드 커버리지 근사)
            coverage_expr = 0
            for uav_id in self.uav_ids:
                for cell in self.grid_map.valid_cells:
                    # 커버리지 반경 내 가중치
                    coverage_expr += pos_vars[(uav_id, cell)] * 1.0
            
            # 2. 간섭 비용 (PER 기반)
            interference_expr = 0
            if hasattr(self.silvus, 'get_interference_vector'):
                per_vector = self.silvus.get_interference_vector()
                for uav_id in self.uav_ids:
                    if uav_id - 1 < len(per_vector):
                        interference_expr += per_vector[uav_id - 1] * 10
            
            # 3. 연결성 비용 (ETX 기반)
            connectivity_expr = 0
            if hasattr(self.silvus, 'get_link_matrix'):
                etx_matrix = self.silvus.get_link_matrix()
                for i in range(len(self.uav_ids)):
                    for j in range(len(self.uav_ids)):
                        if i != j and i < len(etx_matrix) and j < len(etx_matrix[i]):
                            connectivity_expr += etx_matrix[i][j]
            
            # 목적 함수
            prob += (self.lambda_coverage * coverage_expr 
                    - self.lambda_interference * interference_expr 
                    - self.lambda_connectivity * connectivity_expr)
            
            # 솔버 설정
            if self.solver_name == "PULP_CBC_CMD":
                solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=self.time_limit)
            else:
                solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=self.time_limit)
            
            # Warm start (이전 해 활용)
            if self.previous_solution:
                self._apply_warm_start(prob, pos_vars, freq_vars)
            
            # 해결
            prob.solve(solver)
            
            # 결과 파싱
            solve_time = time.time() - start_time
            status = OptimizationStatus.OPTIMAL if pulp.LpStatus[prob.status] == 'Optimal' else OptimizationStatus.FEASIBLE
            
            # 결과 추출
            positions = {}
            frequencies = {}
            
            for uav_id in self.uav_ids:
                # 위치 찾기
                for cell in self.grid_map.valid_cells:
                    if pulp.value(pos_vars[(uav_id, cell)]) > 0.5:
                        positions[uav_id] = UAVPosition(uav_id, cell[0], cell[1], cell[2])
                        break
                
                # 주파수 찾기
                for ch_idx, channel in enumerate(self.available_channels):
                    if pulp.value(freq_vars[(uav_id, ch_idx)]) > 0.5:
                        frequencies[uav_id] = FrequencyAssignment(uav_id, channel)
                        break
            
            # 점수 계산
            coverage_score = self._compute_coverage_score(positions)
            interference_score = self._compute_interference_score(silvus)
            connectivity_score = self._compute_connectivity_score(silvus)
            objective = pulp.value(prob.objective) if prob.objective else 0
            
            result = OptimizationResult(
                status=status,
                positions=positions,
                frequencies=frequencies,
                objective_value=objective,
                coverage_score=coverage_score,
                interference_score=interference_score,
                connectivity_score=connectivity_score,
                solve_time_sec=solve_time
            )
            
            # Warm start용 저장
            self.previous_solution = result
            
            logger.info(f"Optimization completed: {status.value}, obj={objective:.2f}, time={solve_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            return self._fallback_solve(silvus)
    
    def _compute_coverage_score(self, positions: Dict[int, UAVPosition]) -> float:
        """커버리지 점수 계산"""
        # 간단한 근사: UAV 수 * 커버리지 반경
        return len(positions) * 100.0
    
    def _compute_interference_score(self, silvus: SilvusInterface) -> float:
        """간섭 점수 계산"""
        per_vector = silvus.get_interference_vector()
        return float(np.sum(per_vector)) if len(per_vector) > 0 else 0.0
    
    def _compute_connectivity_score(self, silvus: SilvusInterface) -> float:
        """연결성 점수 계산"""
        etx_matrix = silvus.get_link_matrix()
        if etx_matrix.size > 0:
            finite_etx = etx_matrix[np.isfinite(etx_matrix)]
            return float(np.mean(finite_etx)) if len(finite_etx) > 0 else 0.0
        return 0.0
    
    def _apply_warm_start(self, prob, pos_vars, freq_vars):
        """이전 해를 warm start로 적용"""
        if not self.previous_solution:
            return
        
        prev = self.previous_solution
        for uav_id, pos in prev.positions.items():
            cell = (pos.x, pos.y, pos.z)
            if (uav_id, cell) in pos_vars:
                pos_vars[(uav_id, cell)].setInitialValue(1)
        
        for uav_id, freq in prev.frequencies.items():
            ch_idx = self.available_channels.index(freq.channel_mhz) if freq.channel_mhz in self.available_channels else 0
            if (uav_id, ch_idx) in freq_vars:
                freq_vars[(uav_id, ch_idx)].setInitialValue(1)
    
    def _fallback_solve(self, silvus: SilvusInterface) -> OptimizationResult:
        """폴백: 휴리스틱 기반 빠른 해결"""
        logger.warning("Using fallback heuristic solver")
        start_time = time.time()
        
        # 그리드에서 간격 있게 배치
        positions = {}
        frequencies = {}
        cells = self.grid_map.valid_cells
        n_cells = len(cells)
        n_uavs = len(self.uav_ids)
        
        for i, uav_id in enumerate(self.uav_ids):
            idx = int(i * n_cells / n_uavs)
            cell = cells[min(idx, n_cells - 1)]
            positions[uav_id] = UAVPosition(uav_id, cell[0], cell[1], cell[2])
            frequencies[uav_id] = FrequencyAssignment(uav_id, self.available_channels[i % len(self.available_channels)])
        
        solve_time = time.time() - start_time
        return OptimizationResult(
            status=OptimizationStatus.FEASIBLE,
            positions=positions,
            frequencies=frequencies,
            objective_value=0.0,
            coverage_score=len(positions) * 100,
            interference_score=0.0,
            connectivity_score=0.0,
            solve_time_sec=solve_time
        )


class IncrementalOptimizer:
    """증분 재최적화 (이전 해 warm start 활용)"""
    
    def __init__(self, optimizer: IQPOptimizer):
        self.optimizer = optimizer
        self.last_trigger_time = 0
        self.min_interval = 2.0  # 최소 재최적화 간격 (초)
    
    def should_reoptimize(self, silvus: SilvusInterface) -> Tuple[bool, str]:
        """재최적화 필요 여부 판단"""
        # 최소 간격 체크
        if time.time() - self.last_trigger_time < self.min_interval:
            return False, "Minimum interval not elapsed"
        
        # 트리거 조건 확인
        if silvus.trigger_reoptimization():
            self.last_trigger_time = time.time()
            return True, "Link quality degradation detected"
        
        return False, "No trigger"
    
    def reoptimize(self, silvus: SilvusInterface) -> OptimizationResult:
        """증분 재최적화 실행"""
        logger.info("Starting incremental reoptimization...")
        result = self.optimizer.solve(silvus)
        logger.info(f"Reoptimization completed: {result.status.value}")
        return result


def create_optimizer(config: Dict[str, Any]) -> IQPOptimizer:
    """팩토리 함수"""
    # 그리드 맵 생성
    grammar = config.get("grid", {
        "x_range": (0, 1000),
        "y_range": (0, 1000),
        "z_range": (50, 200),
        "resolution": 50
    })
    grid_map = GridMap(
        tuple(grammar["x_range"]),
        tuple(grammar["y_range"]),
        tuple(grammar["z_range"]),
        grammar["resolution"]
    )
    
    # Silvus 인터페이스
    silvus = create_silvus_interface(config.get("silvus", {"mock_mode": True}))
    
    # UAV IDs
    uav_ids = config.get("uav_ids", [1, 2, 3, 4])
    
    return IQPOptimizer(
        grid_map=grid_map,
        uav_ids=uav_ids,
        silvus=create_silvus_interface(config.get("silvus", {"mock_mode": True})),
        solver=config.get("solver", "PULP_CBC_CMD"),
        time_limit_sec=config.get("time_limit_sec", 5.0)
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== IQP Optimizer Test ===")
    
    # 설정
    config = {
        "grid": {
            "x_range": (0, 1000),
            "y_range": (0, 1000),
            "z_range": (50, 200),
            "resolution": 100
        },
        "uav_ids": [1, 2, 3, 4],
        "silvus": {"mock_mode": True},
        "time_limit_sec": 10.0
    }
    
    # 옵티마이저 생성
    optimizer = create_optimizer(config)
    optimizer.set_weights(coverage=1.0, interference=0.5, connectivity=0.3)
    
    # Silvus 인터페이스
    silvus = create_silvus_interface({"mock_mode": True})
    silvus.initialize()
    
    # 최적화 실행
    print("Running optimization...")
    result = optimizer.solve(silvus)
    
    print(f"\n=== Optimization Result ===")
    print(f"Status: {result.status.value}")
    print(f"Objective: {result.objective_value:.2f}")
    print(f"Coverage: {result.coverage_score:.1f}")
    print(f"Interference: {result.interference_score:.2f}")
    print(f"Connectivity: {result.connectivity_score:.2f}")
    print(f"Solve Time: {result.solve_time_sec:.2f}s")
    
    print("\nPositions:")
    for uav_id, pos in result.positions.items():
        print(f"  UAV {uav_id}: ({pos.x}, {pos.y}, {pos.z})")
    
    print("\nFrequencies:")
    for uav_id, freq in result.frequencies.items():
        print(f"  UAV {uav_id}: {freq.channel_mhz} MHz")
    
    # 증분 재최적화 테스트
    print("\n=== Incremental Reoptimization Test ===")
    inc_optimizer = IncrementalOptimizer(optimizer)
    should, reason = inc_optimizer.should_reoptimize(silvus)
    print(f"Should reoptimize: {should} ({reason})")
    
    if should:
        result2 = inc_optimizer.reoptimize(silvus)
        print(f"Reoptimization result: {result2.status.value}, obj={result2.objective_value:.2f}")
    
    print("\n=== Test Complete ===")