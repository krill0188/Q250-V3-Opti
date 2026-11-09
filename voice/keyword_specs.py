"""
Keyword Specifications - Single Source of Truth for Voice Commands
모든 음성 명령의 정의: 키워드, 자연어 문장, MAVLink 액션, 파라미터, 우선순위
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from enum import IntEnum
import json
from pathlib import Path


class CommandPriority(IntEnum):
    """명령 우선순위 (낮을수록 높음)"""
    FAILSAFE_ESTOP = 0      # 비상 정지/즉시 착륙
    MANUAL_SW = 1           # 수동 제어 스위치
    VOICE_KWS = 2           # KWS 음성 명령 (STT 우회)
    VOICE_NLU = 3           # STT+NLU 일반 음성 명령


@dataclass
class KeywordSpec:
    """단일 키워드 명령 스펙"""
    keyword: str                    # 모델 출력 라벨 (예: "emergency_stop")
    phrases: List[str]              # 사용자 자연어 발화 문장들
    mavlink_action: str             # MAVLink/MAVSDK 액션명
    params: Dict = field(default_factory=dict)  # 액션 파라미터
    priority: int = CommandPriority.VOICE_KWS
    target: str = "drone_1"         # 대상 기체
    description: str = ""           # 설명
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "KeywordSpec":
        return cls(**data)


# === 핵심 명령 스펙 정의 (이 파일이 단일 진실 소스) ===
KEYWORD_SPECS = [
    # ==========================================
    # 비상 명령 (Priority 0) - 최우선, 가장 민감하게
    # ==========================================
    KeywordSpec(
        keyword="emergency_stop",
        phrases=[
            "비상 정지", "긴급 정지", "즉시 정지", "올 스톱", "전부 정지",
            "비상정지", "긴급정지", "즉시정지", "다 멈춰", "당장 멈춰",
            "emergency stop", "stop now", "all stop", "abort"
        ],
        mavlink_action="ESTOP",
        params={},
        priority=CommandPriority.FAILSAFE_ESTOP,
        target="*",
        description="모든 기체 즉시 정지 (모터 차단)"
    ),
    KeywordSpec(
        keyword="land_now",
        phrases=[
            "즉시 착륙", "비상 착륙", "지금 착륙", "당장 내려", "강제 착륙",
            "emergency land", "land now", "land immediately", "force land"
        ],
        mavlink_action="LAND",
        params={},
        priority=CommandPriority.FAILSAFE_ESTOP,
        target="drone_1",
        description="즉시 강제 착륙"
    ),
    KeywordSpec(
        keyword="kill_switch",
        phrases=[
            "킬 스위치", "모터 차단", "전원 차단", "엔진 정지",
            "kill switch", "motor off", "engine stop"
        ],
        mavlink_action="ESTOP",
        params={},
        priority=CommandPriority.FAILSAFE_ESTOP,
        target="*",
        description="완전 모터 차단 (복구 불가)"
    ),
    
    # ==========================================
    # 기본 비행 제어 (Priority 2)
    # ==========================================
    KeywordSpec(
        keyword="takeoff",
        phrases=[
            "이륙", "이륙해", "뜨자", "올라가", "이륙 해", "이륙 하세요",
            "takeoff", "take off", "launch", "lift off"
        ],
        mavlink_action="TAKEOFF",
        params={"altitude": 3.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="이륙 (기본 고도 3m)"
    ),
    KeywordSpec(
        keyword="takeoff_high",
        phrases=[
            "높이 이륙", "10미터 이륙", "5미터 이륙", "고도 10미터",
            "takeoff high", "takeoff 10", "takeoff 5"
        ],
        mavlink_action="TAKEOFF",
        params={"altitude": 10.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="고고도 이륙 (10m)"
    ),
    KeywordSpec(
        keyword="land",
        phrases=[
            "착륙", "착륙해", "내려", "내려와", "착륙 해", "착륙 하세요",
            "land", "landing", "touchdown"
        ],
        mavlink_action="LAND",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="정상 착륙"
    ),
    KeywordSpec(
        keyword="return_home",
        phrases=[
            "복귀", "돌아와", "홈으로", "리턴", "복귀 해", "집으로",
            "return", "return home", "rtl", "home", "go home"
        ],
        mavlink_action="RTL",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="홈 위치로 복귀"
    ),
    KeywordSpec(
        keyword="hover",
        phrases=[
            "정지", "멈춰", "홀드", "대기", "제자리", "정지해", "멈춰라",
            "hover", "hold", "stop", "pause", "stay"
        ],
        mavlink_action="HOLD",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="현재 위치 호버링"
    ),
    KeywordSpec(
        keyword="arm",
        phrases=[
            "시동", "아밍", "모터 켜", "시동 걸어", "엔진 켜",
            "arm", "arming", "motor on"
        ],
        mavlink_action="ARM",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="모터 시동 (ARM)"
    ),
    KeywordSpec(
        keyword="disarm",
        phrases=[
            "시동 끄", "디스아밍", "모터 꺼", "시동 해제", "엔진 꺼",
            "disarm", "motor off"
        ],
        mavlink_action="DISARM",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="모터 시동 해제 (DISARM)"
    ),
    
    # ==========================================
    # 이동 제어 (Priority 2) - 속도 벡터
    # ==========================================
    KeywordSpec(
        keyword="move_forward",
        phrases=[
            "전진", "앞으로", "앞으로 가", "직진", "전진해", "앞으로 가세요",
            "forward", "go forward", "move forward", "go ahead"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 2.0, "vy": 0.0, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="전진 (2m/s)"
    ),
    KeywordSpec(
        keyword="move_forward_fast",
        phrases=[
            "빨리 전진", "전속 전진", "최대 전진", "달려",
            "forward fast", "full speed", "max forward"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 5.0, "vy": 0.0, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="전진 고속 (5m/s)"
    ),
    KeywordSpec(
        keyword="move_backward",
        phrases=[
            "후진", "뒤로", "뒤로 가", "후진해", "뒤로 가세요",
            "backward", "go back", "move back", "reverse"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": -2.0, "vy": 0.0, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="후진 (2m/s)"
    ),
    KeywordSpec(
        keyword="move_left",
        phrases=[
            "좌측", "왼쪽", "왼쪽으로", "좌측으로", "왼쪽 가", "왼쪽 이동",
            "left", "go left", "move left", "strafe left"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 2.0, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="좌측 이동 (2m/s)"
    ),
    KeywordSpec(
        keyword="move_right",
        phrases=[
            "우측", "오른쪽", "오른쪽으로", "우측으로", "오른쪽 가", "오른쪽 이동",
            "right", "go right", "move right", "strafe right"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": -2.0, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="우측 이동 (2m/s)"
    ),
    KeywordSpec(
        keyword="move_up",
        phrases=[
            "상승", "올라", "위로", "올라가", "높이", "올라가세요",
            "up", "go up", "ascend", "rise"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 0.0, "vz": 1.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="상승 (1m/s)"
    ),
    KeywordSpec(
        keyword="move_down",
        phrases=[
            "하강", "내려", "아래로", "내려가", "낮게", "내려가세요",
            "down", "go down", "descend", "lower"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 0.0, "vz": -1.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="하강 (1m/s)"
    ),
    KeywordSpec(
        keyword="turn_left",
        phrases=[
            "좌회전", "왼쪽 회전", "왼쪽으로 돌아", "좌측 회전", "왼쪽 돌아",
            "turn left", "rotate left", "yaw left"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_rate": 0.5},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="좌회전 (0.5 rad/s)"
    ),
    KeywordSpec(
        keyword="turn_right",
        phrases=[
            "우회전", "오른쪽 회전", "오른쪽으로 돌아", "우측 회전", "오른쪽 돌아",
            "turn right", "rotate right", "yaw right"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_rate": -0.5},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="우회전 (0.5 rad/s)"
    ),
    KeywordSpec(
        keyword="stop_move",
        phrases=[
            "이동 정지", "이동 멈춰", "이동 그만", "정지해",
            "stop move", "stop moving", "halt"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 0.0, "vz": 0.0, "yaw_rate": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="drone_1",
        description="모든 이동 정지 (호버링)"
    ),
    
    # ==========================================
    # 하이브리드 드론 전용 (Priority 2)
    # ==========================================
    KeywordSpec(
        keyword="dive_attack",
        phrases=[
            "다이브", "다이브 어택", "다이브 공격", "급강하", "다이브 해", "다이브 시작",
            "dive", "dive attack", "attack dive", "dive now"
        ],
        mavlink_action="DIVE_ATTACK",
        params={"target_alt": 100, "angle": 70},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="다이브 어택 (목표 고도 100m, 각도 70도)"
    ),
    KeywordSpec(
        keyword="dive_attack_steep",
        phrases=[
            "수직 다이브", "90도 다이브", "수직 급강하",
            "vertical dive", "steep dive", "90 degree dive"
        ],
        mavlink_action="DIVE_ATTACK",
        params={"target_alt": 100, "angle": 85},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="수직 다이브 (85도)"
    ),
    KeywordSpec(
        keyword="deceive_start",
        phrases=[
            "기만", "기만 모드", "기만 시작", "디셉션", "속이기", "기만해", "기만 켜",
            "deceive", "deception", "start deception", "deception on"
        ],
        mavlink_action="DECEPTION_START",
        params={"pattern": "AUTO", "duration": 30},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="기만 모드 자동 시작 (30초)"
    ),
    KeywordSpec(
        keyword="deceive_spiral",
        phrases=[
            "나선 기만", "스파이럴 기만", "나선형 기만",
            "spiral deception", "spiral dive deception"
        ],
        mavlink_action="DECEPTION_START",
        params={"pattern": "SPIRAL_DIVE", "duration": 30},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="나선형 기만 패턴"
    ),
    KeywordSpec(
        keyword="deceive_sine",
        phrases=[
            "사인 기만", "파동 기만", "사인파 기만",
            "sine deception", "sine wave deception"
        ],
        mavlink_action="DECEPTION_START",
        params={"pattern": "SINE_DIVE", "duration": 30},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="사인파 기만 패턴"
    ),
    KeywordSpec(
        keyword="deceive_jink",
        phrases=[
            "랜덤 기만", "진크 기만", "랜덤 진크",
            "random deception", "jink deception", "random jink"
        ],
        mavlink_action="DECEPTION_START",
        params={"pattern": "RANDOM_JINK", "duration": 30},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="랜덤 진크 기만 패턴"
    ),
    KeywordSpec(
        keyword="deceive_fake_crash",
        phrases=[
            "추락 기만", "페이크 크래시", "추락 위장", "가짜 추락",
            "fake crash", "crash deception"
        ],
        mavlink_action="DECEPTION_START",
        params={"pattern": "FAKE_CRASH", "duration": 30},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="추락 위장 기만 패턴"
    ),
    KeywordSpec(
        keyword="deceive_stop",
        phrases=[
            "기만 중지", "기만 끄", "기만 종료", "기만 해제", "디셉션 오프",
            "deceive stop", "deception off", "stop deception"
        ],
        mavlink_action="DECEPTION_STOP",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="기만 모드 중지"
    ),
    KeywordSpec(
        keyword="mode_cruise",
        phrases=[
            "순항", "순항 모드", "크루즈", "순항해", "크루즈 모드",
            "cruise", "cruise mode", "go cruise"
        ],
        mavlink_action="SET_MODE",
        params={"mode": "CRUISE"},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="순항 모드 (고정익)"
    ),
    KeywordSpec(
        keyword="mode_agile",
        phrases=[
            "기동", "기동 모드", "에프피브이", "FPV", "기동해", "FPV 모드",
            "agile", "agile mode", "fpv", "fpv mode", "go agile"
        ],
        mavlink_action="SET_MODE",
        params={"mode": "FPV_AGILE"},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="FPV 기동 모드 (멀티콥터)"
    ),
    KeywordSpec(
        keyword="transition_cruise",
        phrases=[
            "전환 순항", "고정익 전환", "순항으로 전환",
            "transition cruise", "to cruise", "switch to cruise"
        ],
        mavlink_action="TRANSITION_CRUISE_TO_FPV",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="FPV → 순항 모드 전환"
    ),
    KeywordSpec(
        keyword="transition_agile",
        phrases=[
            "전환 기동", "멀티콥터 전환", "기동으로 전환", "FPV 전환",
            "transition agile", "to agile", "switch to fpv"
        ],
        mavlink_action="TRANSITION_FPV_TO_CRUISE",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="hybrid_drone_1",
        description="순항 → FPV 기동 모드 전환"
    ),
    
    # ==========================================
    # 로봇 제어 (Priority 2)
    # ==========================================
    KeywordSpec(
        keyword="robot_forward",
        phrases=[
            "로봇 전진", "로봇 앞으로", "로봇 직진",
            "robot forward", "robot go forward"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 1.0, "vy": 0.0, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="robot_1",
        description="로봇 전진"
    ),
    KeywordSpec(
        keyword="robot_stop",
        phrases=[
            "로봇 정지", "로봇 멈춰", "로봇 홀드",
            "robot stop", "robot halt"
        ],
        mavlink_action="HOLD",
        params={},
        priority=CommandPriority.VOICE_KWS,
        target="robot_1",
        description="로봇 정지"
    ),
    KeywordSpec(
        keyword="robot_left",
        phrases=[
            "로봇 왼쪽", "로봇 좌회전", "로봇 좌측",
            "robot left", "robot turn left"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": 0.5, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="robot_1",
        description="로봇 좌측 이동"
    ),
    KeywordSpec(
        keyword="robot_right",
        phrases=[
            "로봇 오른쪽", "로봇 우회전", "로봇 우측",
            "robot right", "robot turn right"
        ],
        mavlink_action="MOVE_VEL",
        params={"vx": 0.0, "vy": -0.5, "vz": 0.0},
        priority=CommandPriority.VOICE_KWS,
        target="robot_1",
        description="로봇 우측 이동"
    ),
]


# === 유틸리티 함수 ===

def get_all_specs() -> List[KeywordSpec]:
    """모든 스펙 반환"""
    return KEYWORD_SPECS


def get_specs_by_priority(priority: CommandPriority) -> List[KeywordSpec]:
    """우선순위별 필터링"""
    return [s for s in KEYWORD_SPECS if s.priority == priority]


def get_specs_by_target(target: str) -> List[KeywordSpec]:
    """대상 기체별 필터링"""
    return [s for s in KEYWORD_SPECS if s.target == target or s.target == "*"]


def get_keywords_list() -> List[str]:
    """모델 학습용 키워드 리스트 (순서 중요: 인덱스 = 클래스 ID)"""
    return [s.keyword for s in KEYWORD_SPECS]


def get_phrases_for_keyword(keyword: str) -> List[str]:
    """키워드에 매핑된 자연어 문장들"""
    for s in KEYWORD_SPECS:
        if s.keyword == keyword:
            return s.phrases
    return []


def get_command_for_keyword(keyword: str) -> Optional[Dict]:
    """키워드 → 실행 명령 변환"""
    for s in KEYWORD_SPECS:
        if s.keyword == keyword:
            return {
                "keyword": s.keyword,
                "action": s.mavlink_action,
                "params": s.params,
                "priority": s.priority,
                "target": s.target,
            }
    return None


def export_for_training(output_dir: str = "~/data/kws_training"):
    """학습용 데이터 내보내기 (JSON)"""
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. 키워드 리스트 (labels.json)
    labels = {str(i): k for i, k in enumerate(get_keywords_list())}
    with open(output_path / "labels.json", 'w', encoding='utf-8') as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    
    # 2. 키워드별 문장 (phrases.json)
    phrases = {s.keyword: s.phrases for s in KEYWORD_SPECS}
    with open(output_path / "phrases.json", 'w', encoding='utf-8') as f:
        json.dump(phrases, f, ensure_ascii=False, indent=2)
    
    # 3. 명령 매핑 (commands.json)
    commands = {s.keyword: {
        "action": s.mavlink_action,
        "params": s.params,
        "priority": s.priority,
        "target": s.target,
    } for s in KEYWORD_SPECS}
    with open(output_path / "commands.json", 'w', encoding='utf-8') as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)
    
    # 4. 전체 스펙 (specs.json)
    specs = [s.to_dict() for s in KEYWORD_SPECS]
    with open(output_path / "specs.json", 'w', encoding='utf-8') as f:
        json.dump(specs, f, ensure_ascii=False, indent=2)
    
    print(f"학습용 파일 내보내기 완료: {output_path}")
    print(f"  - labels.json: {len(labels)}개 키워드")
    print(f"  - phrases.json: {sum(len(p) for p in phrases.values())}개 문장")
    print(f"  - commands.json: {len(commands)}개 명령")
    print(f"  - specs.json: {len(specs)}개 스펙")


def import_from_json(specs_file: str) -> List[KeywordSpec]:
    """JSON에서 스펙 로드"""
    with open(specs_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [KeywordSpec.from_dict(d) for d in data]


if __name__ == "__main__":
    import json
    
    # 학습용 파일 생성
    export_for_training()
    
    # 통계 출력
    print(f"\n=== 키워드 스펙 통계 ===")
    print(f"총 키워드: {len(KEYWORD_SPECS)}개")
    
    by_priority = {}
    for s in KEYWORD_SPECS:
        by_priority.setdefault(str(s.priority), 0)
        by_priority[str(s.priority)] += 1
    print(f"우선순위별: {by_priority}")
    
    by_target = {}
    for s in KEYWORD_SPECS:
        by_target.setdefault(s.target, 0)
        by_target[s.target] += 1
    print(f"대상별: {by_target}")
    
    print(f"\n키워드 리스트 (학습 순서):")
    for i, kw in enumerate(get_keywords_list()):
        spec = next(s for s in KEYWORD_SPECS if s.keyword == kw)
        print(f"  [{i:2d}] {kw} ({spec.mavlink_action})")