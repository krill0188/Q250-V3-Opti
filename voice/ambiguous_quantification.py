"""
모호한 한국어 표현 정량화 매핑 테이블
LLM/파서가 한국어의 모호한 부사와 방향 표현을 정량화된 수치로 변환하는 기준
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class QuantificationRule:
    """정량화 규칙"""

    korean_patterns: list[str]  # 매칭할 한국어 패턴들
    value: float  # 변환될 수치
    unit: str  # 단위 (m, deg, m/s 등)
    description: str  # 설명


# === 거리/이동 모호 표현 ===
DISTANCE_AMBIGUOUS = {
    "조금": QuantificationRule(
        ["조금", "살짝", "약간", "미세하게", "미세"], 1.0, "m", "미세 이동"
    ),
    "적당히": QuantificationRule(["적당히", "적당량"], 2.0, "m", "적당 이동"),
    "많이": QuantificationRule(["많이", "크게", "크게 많이"], 5.0, "m", "대폭 이동"),
    "최대로": QuantificationRule(["최대로", "맥시멈", "맥스"], 20.0, "m", "최대 이동"),
    "기본": QuantificationRule(["", "그냥", "그냥 가"], 2.0, "m", "기본 이동"),
}

# === 회전/방향 모호 표현 ===
ROTATION_AMBIGUOUS = {
    "조금_회전": QuantificationRule(
        ["조금만 돌아", "살짝 돌아", "약간 회전"], 15.0, "deg", "미세 회전"
    ),
    "90도_우회전": QuantificationRule(
        ["우회전", "오른쪽 돌아", "우향우", "오른쪽으로 돌아"],
        90.0,
        "deg",
        "90도 우회전",
    ),
    "90도_좌회전": QuantificationRule(
        ["좌회전", "왼쪽 돌아", "좌향좌", "왼쪽으로 돌아"], -90.0, "deg", "90도 좌회전"
    ),
    "180도_회전": QuantificationRule(
        ["뒤로 돌아", "반대 방향", "반바퀴"], 180.0, "deg", "180도 회전"
    ),
    "기본_회전": QuantificationRule(
        ["돌아", "회전해", "방향 바꿔"], 45.0, "deg", "기본 회전"
    ),
}

# === 속도 모호 표현 ===
SPEED_AMBIGUOUS = {
    "천천히": QuantificationRule(["천천히", "천천히 가", "서서히"], 1.0, "m/s", "저속"),
    "적당히": QuantificationRule(["적당히 가", "적당 속도"], 2.0, "m/s", "적당 속도"),
    "빠르게": QuantificationRule(["빨리", "빨리 가", "최대 속도"], 5.0, "m/s", "고속"),
}

# === 고도 모호 표현 ===
ALTITUDE_AMBIGUOUS = {
    "조금_올려": QuantificationRule(
        ["조금만 올려", "살짝 올려", "약간 높여", "조금만 높여", "살짝 높여"],
        -1.0,
        "m",
        "미세 상승",
    ),
    "많이_올려": QuantificationRule(
        ["많이 올려", "크게 높여", "높게", "많이 높여"], -5.0, "m", "대폭 상승"
    ),
    "조금_내려": QuantificationRule(
        ["조금만 내려", "살짝 내려"], 1.0, "m", "미세 하강"
    ),
    "많이_내려": QuantificationRule(
        ["많이 내려", "확 내려", "바닥까지"], 10.0, "m", "대폭 하강"
    ),
    "기본_고도": QuantificationRule(
        ["고도 맞춰", "고도 유지", "이 높이"], 0.0, "m", "현재 고도 유지"
    ),
}

# === 방향 키워드 매핑 (한국어 → yaw_deg) ===
DIRECTION_KEYWORDS = {
    # 전진/후진
    "forward": ["앞으로", "전진", "직진", "앞으로 가", "전진해"],
    "backward": ["뒤로", "후진", "뒤로 가", "뒤로 가세요"],
    # 좌/우 이동
    "left": ["좌측", "왼쪽", "왼쪽으로", "좌측으로", "왼쪽 가", "왼쪽 이동", "좌로"],
    "right": [
        "우측",
        "오른쪽",
        "오른쪽으로",
        "우측으로",
        "오른쪽 가",
        "오른쪽 이동",
        "우로",
    ],
    # 상승/하강
    "up": ["상승", "올라", "위로", "올라가", "높이", "올라가세요"],
    "down": ["하강", "내려", "아래로", "내려가", "낮게", "내려가세요"],
    # 회전 (작은 각도만 - 큰 각도는 ROTATION_AMBIGUOUS에서 처리)
    "turn_left": ["좌측으로 조금 돌아", "약간 좌회전"],
    "turn_right": ["우측으로 조금 돌아", "약간 우회전"],
    "turn_around": ["뒤로 돌아", "반대 방향", "반바퀴", "턴", "돌아"],
}

# === 액션 키워드 매핑 ===
ACTION_KEYWORDS = {
    "TAKEOFF": [
        "이륙",
        "이륙해",
        "뜨자",
        "올라가",
        "이륙 해",
        "이륙 하세요",
        "takeoff",
        "take off",
    ],
    "LAND": ["착륙", "착륙해", "내려", "내려와", "착륙 해", "착륙 하세요", "land"],
    "RTL": [
        "복귀",
        "돌아와",
        "홈으로",
        "리턴",
        "복귀 해",
        "집으로",
        "return",
        "rtl",
        "home",
    ],
    "HOLD": [
        "정지",
        "멈춰",
        "홀드",
        "대기",
        "제자리",
        "정지해",
        "멈춰라",
        "hold",
        "stop",
    ],
    "ARM": ["시동", "아밍", "모터 켜", "시동 걸어", "엔진 켜", "arm"],
    "DISARM": ["시동 끄", "디스아밍", "모터 꺼", "시동 해제", "엔진 꺼", "disarm"],
}

# 전체 모호 표현 사전 (우선순위 순)
ALL_AMBIGUOUS = {
    **DISTANCE_AMBIGUOUS,
    **ROTATION_AMBIGUOUS,
    **SPEED_AMBIGUOUS,
    **ALTITUDE_AMBIGUOUS,
}


def quantify_korean_ambiguity(text: str, context: str = "distance") -> Optional[float]:
    """
    한국어 모호 표현을 수치로 변환

    Args:
        text: 입력 텍스트
        context: "distance", "rotation", "speed", "altitude" 중 하나

    Returns:
        변환된 수치 (없으면 None)
    """
    text = text.strip()

    # 컨텍스트별 사전 선택
    if context == "rotation":
        lookup = ROTATION_AMBIGUOUS
    elif context == "speed":
        lookup = SPEED_AMBIGUOUS
    elif context == "altitude":
        lookup = ALTITUDE_AMBIGUOUS
    else:  # distance
        lookup = DISTANCE_AMBIGUOUS

    # 정확 매칭 우선
    for key, rule in lookup.items():
        for pattern in rule.korean_patterns:
            if pattern in text:
                return rule.value

    # 부분 매칭
    for key, rule in lookup.items():
        for pattern in rule.korean_patterns:
            if pattern in text:
                return rule.value

    return None


def get_direction_vector(text: str) -> Optional[Dict[str, float]]:
    """
    한국어 방향 표현을 forward/right/up 벡터로 변환
    """
    text = text.strip()

    for direction, keywords in DIRECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                if direction == "forward":
                    return {"forward_m": 1.0, "right_m": 0.0, "down_m": 0.0}
                elif direction == "backward":
                    return {"forward_m": -1.0, "right_m": 0.0, "down_m": 0.0}
                elif direction == "left":
                    return {"forward_m": 0.0, "right_m": 1.0, "down_m": 0.0}
                elif direction == "right":
                    return {"forward_m": 0.0, "right_m": -1.0, "down_m": 0.0}
                elif direction == "up":
                    return {"forward_m": 0.0, "right_m": 0.0, "down_m": -1.0}
                elif direction == "down":
                    return {"forward_m": 0.0, "right_m": 0.0, "down_m": 1.0}
                elif direction == "turn_left":
                    return {"yaw_deg": 15.0}  # 기본 15도
                elif direction == "turn_right":
                    return {"yaw_deg": -15.0}
                elif direction == "turn_around":
                    return {"yaw_deg": 180.0}

    return None


def extract_numbers(text: str) -> list[float]:
    """텍스트에서 모든 숫자 추출"""
    import re

    return [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)", text)]


def parse_korean_command(text: str) -> Dict:
    """
    한국어 명령어를 파싱하여 정량화된 파라미터 추출
    """
    import re

    result = {
        "action": "MOVE_VEL",
        "forward_m": 0.0,
        "right_m": 0.0,
        "down_m": 0.0,
        "yaw_deg": 0.0,
        "clarification_needed": False,
        "reason": "",
    }

    # 액션 키워드 검사
    for action, keywords in ACTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                result["action"] = action
                break

    # 숫자 추출
    numbers = extract_numbers(text)

    # 방향 벡터 추출
    direction = get_direction_vector(text)
    if direction:
        for k, v in direction.items():
            if k in result:
                result[k] = v

    # 모호 표현 정량화
    if not numbers:
        # 거리에 숫자가 없으면 모호 표현으로 정량화
        dist_val = quantify_korean_ambiguity(text, "distance")
        if dist_val is not None:
            # 방향이 정해져 있으면 해당 축에 적용
            if result["forward_m"] != 0.0:
                result["forward_m"] *= dist_val
            elif result["right_m"] != 0.0:
                result["right_m"] *= dist_val
            elif result["down_m"] != 0.0:
                result["down_m"] *= dist_val
            else:
                result["forward_m"] = dist_val  # 기본 전진
    else:
        # 숫자가 있으면 첫 번째 숫자를 기본 거리로 사용
        # 방향이 이미 정해져 있으면 숫자 적용
        if (
            result["forward_m"] != 0.0
            or result["right_m"] != 0.0
            or result["down_m"] != 0.0
        ):
            # 방향이 정해져 있으면 해당 축에 숫자 적용
            val = numbers[0]
            if result["forward_m"] != 0.0:
                result["forward_m"] *= val
            elif result["right_m"] != 0.0:
                result["right_m"] *= val
            elif result["down_m"] != 0.0:
                result["down_m"] *= val
            else:
                # 방향이 정해지지 않았지만 숫자가 있으면 전진으로 간주
                result["forward_m"] = numbers[0]
        else:
            # 방향도 없고 숫자도 없으면 기본값
            result["forward_m"] = numbers[0] if numbers else 2.0

    # 회전 모호 표현
    rot_val = quantify_korean_ambiguity(text, "rotation")
    if rot_val is not None and result["yaw_deg"] == 0.0:
        result["yaw_deg"] = rot_val

    # 고도 모호 표현
    alt_val = quantify_korean_ambiguity(text, "altitude")
    if alt_val is not None and result["down_m"] == 0.0:
        result["down_m"] = alt_val

    # 모호함 판단: 방향이 불명확하거나 대상이 모호한 경우
    ambiguous_keywords = [
        "저기",
        "거기",
        "이리",
        "그쪽",
        "어디",
        "어디로",
        "옆으로",
        "근처",
        "가까이",
    ]
    if any(kw in text for kw in ambiguous_keywords) and not numbers:
        result["clarification_needed"] = True
        result["reason"] = "대상 위치가 불명확합니다 (거리/방향 미지정)"

    # 안전 클램핑 (20m 제한)
    for key in ["forward_m", "right_m", "down_m"]:
        if key in result:
            result[key] = max(-20.0, min(20.0, result[key]))

    result["yaw_deg"] = max(-180.0, min(180.0, result["yaw_deg"]))

    return result


# === 편의 함수 ===
def create_ambiguous_quantifier() -> Dict:
    """정량화 규칙 사전 생성"""
    return {
        "distance": DISTANCE_AMBIGUOUS,
        "rotation": ROTATION_AMBIGUOUS,
        "speed": SPEED_AMBIGUOUS,
        "altitude": ALTITUDE_AMBIGUOUS,
        "direction": DIRECTION_KEYWORDS,
        "action": ACTION_KEYWORDS,
    }


if __name__ == "__main__":
    # 테스트
    test_cases = [
        "앞으로 조금만 가",
        "왼쪽으로 4미터 이동하고 고도 조금만 높여봐",
        "우회전해",
        "고도 10미터로 올려",
        "살짝 오른쪽으로 이동",
        "최대로 빨리 가",
    ]

    for tc in test_cases:
        parsed = parse_korean_command(tc)
        print(f"입력: '{tc}'")
        print(f"결과: {parsed}\n")
