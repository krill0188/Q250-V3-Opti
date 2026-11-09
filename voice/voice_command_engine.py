import math
import re
import uuid
from typing import Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from core_arbitrator import CommandPriority, UnifiedCommand

try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperModel = None


class FastPathEmergencyMatcher:
    EMERGENCY_STOP_PATTERN = re.compile(
        r"(비상\s*정지|긴급\s*정지|즉시\s*정지|올\s*스톱|all\s*stop)", re.IGNORECASE
    )
    HOLD_PATTERN = re.compile(r"^(멈춰|정지|스톱|홀드|잠깐|대기)$", re.IGNORECASE)
    LAND_PATTERN = re.compile(r"(비상\s*착륙|즉시\s*착륙)", re.IGNORECASE)

    @classmethod
    def match(cls, text: str, default_target: str) -> Optional[UnifiedCommand]:
        clean_text = text.strip()

        target = default_target
        if "드론" in clean_text:
            target = "drone_1"
        elif "로봇" in clean_text:
            target = "robot_1"
        elif "하이브리드" in clean_text:
            target = "hybrid_drone_1"

        if cls.EMERGENCY_STOP_PATTERN.search(clean_text):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="FAILSAFE",
                priority=CommandPriority.FAILSAFE_ESTOP,
                target_id=target,
                action="ESTOP",
                confidence=1.0,
            )

        if cls.LAND_PATTERN.search(clean_text):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="FAILSAFE",
                priority=CommandPriority.FAILSAFE_ESTOP,
                target_id="drone_1",
                action="LAND",
                confidence=1.0,
            )

        if cls.HOLD_PATTERN.search(clean_text):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.MANUAL_SW,
                target_id=target,
                action="HOLD",
                confidence=1.0,
            )

        return None


class LocalWhisperSTT:
    def __init__(
        self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"
    ):
        if not WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper 패키지가 설치되어 있지 않습니다.")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe_audio(self, audio_np: np.ndarray) -> Tuple[str, float]:
        segments, _ = self.model.transcribe(
            audio_np,
            language="ko",
            beam_size=3,
            vad_filter=True,
            initial_prompt="드론 1번, 로봇 1번, 하이브리드 1번, 이륙, 착륙, 정지, 앞으로 이동, 복귀, 고도, 미터, 다이브, 기만, 순항, 기동",
        )
        texts = []
        probs = []
        for seg in segments:
            texts.append(seg.text.strip())
            probs.append(math.exp(seg.avg_logprob))

        if not texts:
            return "", 0.0

        full_text = " ".join(texts)
        avg_confidence = sum(probs) / len(probs)
        return full_text, min(1.0, max(0.0, avg_confidence))


class ParsedVoiceIntent(BaseModel):
    target_id: str = Field(
        description="제어 대상 ID (예: drone_1, robot_1, hybrid_drone_1)"
    )
    action: str = Field(
        description="ARM, TAKEOFF, LAND, HOLD, MOVE_VEL, NAV_TO_POSE, RTL, SET_MODE, DIVE_ATTACK, DECEPTION_START, DECEPTION_PATTERN, DECEPTION_STOP 중 하나"
    )
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    vz_mps: float = 0.0
    yaw_rate_radps: float = 0.0


class VoiceIntentParser:
    SYSTEM_PROMPT = """
    당신은 드론/로봇/하이브리드 제어용 NLU 파서입니다.
    사용자의 음성 텍스트를 분석하여 반드시 지정된 JSON 스키마로만 응답하십시오.
    - 전진/앞으로: vx_mps 양수(+), 후진/뒤로: vx_mps 음수(-)
    - 좌측 이동: vy_mps 양수(+), 우측 이동: vy_mps 음수(-)
    - 상승: vz_mps 양수(+), 하강: vz_mps 음수(-)
    - 이륙 고도 지정 시 z_m에 미터 단위로 기록하십시오.
    - 모드 전환: SET_MODE 액션, params에 mode 필드
    - 다이브: DIVE_ATTACK 액션, params에 target_alt, angle
    - 기만: DECEPTION_START 액션, params에 pattern, duration, auto
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def parse_to_command(
        self,
        text: str,
        stt_confidence: float,
        active_target: str = "drone_1",
    ) -> UnifiedCommand:
        # 1) 초저지연 Fast-Path 긴급 명령어 먼저 검사
        fast_cmd = FastPathEmergencyMatcher.match(text, default_target=active_target)
        if fast_cmd is not None:
            print(f"[FAST-PATH 매칭 완료] '{text}' -> {fast_cmd.action}")
            return fast_cmd

        # 2) 하이브리드/다이브/기만 전용 키워드 매칭 (Fast-Path 확장)
        hybrid_cmd = self._match_hybrid_commands(text, active_target)
        if hybrid_cmd:
            print(f"[HYBRID-PATH 매칭 완료] '{text}' -> {hybrid_cmd.action}")
            return hybrid_cmd

        # 3) 일반 명령어 파싱
        if self.llm_client is not None:
            intent = await self._call_structured_llm(text, active_target)
        else:
            intent = self._deterministic_fallback_parser(text, active_target)

        return UnifiedCommand(
            command_id=str(uuid.uuid4()),
            source="VOICE_NLU",
            priority=CommandPriority.VOICE_NLU,
            target_id=intent.target_id,
            action=intent.action,
            x_m=intent.x_m,
            y_m=intent.y_m,
            z_m=intent.z_m,
            vx_mps=intent.vx_mps,
            vy_mps=intent.vy_mps,
            vz_mps=intent.vz_mps,
            yaw_rate_radps=intent.yaw_rate_radps,
            confidence=stt_confidence,
        )

    def _match_hybrid_commands(
        self, text: str, default_target: str
    ) -> Optional[UnifiedCommand]:
        """하이브리드/다이브/기만 전용 Fast-Path 매칭"""
        clean_text = text.strip()
        target = default_target

        if "하이브리드" in clean_text or "하이브리드 드론" in clean_text:
            target = "hybrid_drone_1"
        elif "드론" in clean_text:
            target = "drone_1"
        elif "로봇" in clean_text:
            target = "robot_1"

        # 모드 전환
        if "순항" in clean_text or "크루즈" in clean_text:
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.VOICE_NLU,
                target_id=target,
                action="SET_MODE",
                params={"mode": "CRUISE"},
                confidence=0.95,
            )
        elif "기동" in clean_text or "에프피브이" in clean_text or "FPV" in clean_text:
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.VOICE_NLU,
                target_id=target,
                action="SET_MODE",
                params={"mode": "FPV_AGILE"},
                confidence=0.95,
            )
        elif "다이브" in clean_text and (
            "어택" in clean_text or "공격" in clean_text or "시작" in clean_text
        ):
            # 다이브 파라미터 추출
            num_match = re.search(r"(\d+(?:\.\d+)?)", clean_text)
            alt = float(num_match.group(1)) if num_match else 500.0
            angle_match = re.search(r"각도\s*(\d+)", clean_text)
            angle = float(angle_match.group(1)) if angle_match else 70.0

            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.VOICE_NLU,
                target_id=target,
                action="DIVE_ATTACK",
                params={"target_alt": alt, "angle": angle},
                confidence=0.95,
            )
        elif "기만" in clean_text and (
            "시작" in clean_text or "켜" in clean_text or "실행" in clean_text
        ):
            # 기만 패턴 추출
            pattern = "AUTO"
            if "나선" in clean_text or "스파이럴" in clean_text:
                pattern = "SPIRAL_DIVE"
            elif "사인" in clean_text or "파동" in clean_text:
                pattern = "SINE_DIVE"
            elif "랜덤" in clean_text or "진크" in clean_text:
                pattern = "RANDOM_JINK"
            elif "추락" in clean_text or "페이크" in clean_text:
                pattern = "FAKE_CRASH"
            elif "멀티" in clean_text or "펄스" in clean_text:
                pattern = "MULTI_PULSE"

            # 지속시간 추출
            duration_match = re.search(r"(\d+)\s*초", clean_text)
            duration = float(duration_match.group(1)) if duration_match else 30.0

            auto = "자동" in clean_text or "오토" in clean_text

            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.VOICE_NLU,
                target_id=target,
                action="DECEPTION_START",
                params={"pattern": pattern, "duration": duration, "auto": auto},
                confidence=0.95,
            )
        elif "기만" in clean_text and (
            "중지" in clean_text or "종료" in clean_text or "꺼" in clean_text
        ):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.VOICE_NLU,
                target_id=target,
                action="DECEPTION_STOP",
                confidence=0.95,
            )
        elif "위험" in clean_text and (
            "상태" in clean_text or "분석" in clean_text or "어떠" in clean_text
        ):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="VOICE_NLU",
                priority=CommandPriority.VOICE_NLU,
                target_id=target,
                action="GET_RISK_STATUS",
                confidence=0.95,
            )

        return None

    def _deterministic_fallback_parser(
        self, text: str, active_target: str
    ) -> ParsedVoiceIntent:
        target = (
            "drone_1"
            if "드론" in text
            else ("robot_1" if "로봇" in text else active_target)
        )
        if "하이브리드" in text:
            target = "hybrid_drone_1"

        num_match = re.search(r"(\d+(?:\.\d+)?)", text)
        val = float(num_match.group(1)) if num_match else 1.0

        if "이륙" in text:
            return ParsedVoiceIntent(
                target_id=target, action="TAKEOFF", z_m=val if num_match else 2.5
            )
        elif "착륙" in text:
            return ParsedVoiceIntent(target_id=target, action="LAND")
        elif "복귀" in text or "돌아와" in text:
            return ParsedVoiceIntent(target_id=target, action="RTL")
        elif "정지" in text or "멈춰" in text or "홀드" in text:
            return ParsedVoiceIntent(target_id=target, action="HOLD")
        elif "앞으로" in text or "전진" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vx_mps=val)
        elif "뒤로" in text or "후진" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vx_mps=-val)
        elif "좌측" in text or "왼쪽" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vy_mps=-val)
        elif "우측" in text or "오른쪽" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vy_mps=val)
        elif "상승" in text or "올라" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vz_mps=val)
        elif "하강" in text or "내려" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vz_mps=-val)
        elif "좌회전" in text:
            return ParsedVoiceIntent(
                target_id=target, action="MOVE_VEL", yaw_rate_radps=0.5
            )
        elif "우회전" in text:
            return ParsedVoiceIntent(
                target_id=target, action="MOVE_VEL", yaw_rate_radps=-0.5
            )
        elif "복귀" in text or "돌아와" in text:
            return ParsedVoiceIntent(target_id=target, action="RTL")
        elif "고도" in text and "변경" in text:
            return ParsedVoiceIntent(target_id=target, action="MOVE_VEL", z_m=val)
        elif "좌표" in text or "이동" in text:
            return ParsedVoiceIntent(
                target_id=target, action="NAV_TO_POSE", x_m=val, y_m=0.0
            )

        raise ValueError(f"해석할 수 없는 음성 명령입니다: '{text}'")

    async def _call_structured_llm(
        self, text: str, active_target: str
    ) -> ParsedVoiceIntent:
        raw_json = await self.llm_client.generate_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"기본 타겟: {active_target} / 명령: {text}",
            response_model=ParsedVoiceIntent,
        )
        return ParsedVoiceIntent.model_validate_json(raw_json)
