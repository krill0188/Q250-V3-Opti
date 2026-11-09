import math
import re
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple, Callable, List, Dict, TYPE_CHECKING
from dataclasses import dataclass, field

import numpy as np
from pydantic import BaseModel, Field

from core_arbitrator import CommandPriority, UnifiedCommand

# TYPE_CHECKING으로 타입 힌트만 가져오고 런타임 import는 선택적으로 처리
if TYPE_CHECKING:
    from voice.speaker_adapter import (
        SpeakerAdapter,
        SpeakerProfile,
        AdaptiveWhisperModel,
    )
    from voice.wake_word_detector import (
        WakeWordDetector,
        WakeWordConfig,
        WakeWordEvent,
        WakeWordState,
        KoreanWakeWordDetector,
    )
    from voice.voice_enrollment import (
        VoiceEnrollmentManager,
        VoiceCommandMapping,
        CommandCategory,
        VoiceEnrollmentSession,
    )
    from voice.nlu_learning import NLUModelConfig, NLULearningPipeline
    from voice.ambiguous_quantification import (
        parse_korean_command,
        quantify_korean_ambiguity,
    )
    from voice.tactical_normalizer import TacticalNormalizer

# 런타임 선택적 import (가용성 플래그만 설정)
try:
    from faster_whisper import WhisperModel

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    WhisperModel = None  # type: ignore

# tactical_normalizer 지연 import
TACTICAL_NORMALIZER_AVAILABLE = False


def _check_tactical_normalizer() -> bool:
    global TACTICAL_NORMALIZER_AVAILABLE
    if not TACTICAL_NORMALIZER_AVAILABLE:
        try:
            from voice.tactical_normalizer import TacticalNormalizer

            TACTICAL_NORMALIZER_AVAILABLE = True
        except ImportError:
            pass
    return TACTICAL_NORMALIZER_AVAILABLE


# speaker_adapter, wake_word_detector, voice_enrollment, nlu_learning, ambiguous_quantification는 지연 import
# (torch, pvporcupine 등 무거운 의존성 회피)
SPEAKER_ADAPTER_AVAILABLE = False
WAKE_WORD_AVAILABLE = False
ENROLLMENT_AVAILABLE = False
NLU_LEARNING_AVAILABLE = False
AMBIGUOUS_QUANTIFICATION_AVAILABLE = False


def _check_speaker_adapter() -> bool:
    global SPEAKER_ADAPTER_AVAILABLE
    if not SPEAKER_ADAPTER_AVAILABLE:
        try:
            from voice.speaker_adapter import (
                SpeakerAdapter,
                SpeakerProfile,
                AdaptiveWhisperModel,
            )

            SPEAKER_ADAPTER_AVAILABLE = True
        except ImportError:
            pass
    return SPEAKER_ADAPTER_AVAILABLE


def _check_wake_word() -> bool:
    global WAKE_WORD_AVAILABLE
    if not WAKE_WORD_AVAILABLE:
        try:
            from voice.wake_word_detector import WakeWordDetector

            WAKE_WORD_AVAILABLE = True
        except ImportError:
            pass
    return WAKE_WORD_AVAILABLE


def _check_enrollment() -> bool:
    global ENROLLMENT_AVAILABLE
    if not ENROLLMENT_AVAILABLE:
        try:
            from voice.voice_enrollment import VoiceEnrollmentManager

            ENROLLMENT_AVAILABLE = True
        except ImportError:
            pass
    return ENROLLMENT_AVAILABLE


def _check_nlu_learning() -> bool:
    global NLU_LEARNING_AVAILABLE
    if not NLU_LEARNING_AVAILABLE:
        try:
            from voice.nlu_learning import NLULearningPipeline

            NLU_LEARNING_AVAILABLE = True
        except ImportError:
            pass
    return NLU_LEARNING_AVAILABLE


def _check_ambiguous_quantification() -> bool:
    global AMBIGUOUS_QUANTIFICATION_AVAILABLE
    if not AMBIGUOUS_QUANTIFICATION_AVAILABLE:
        try:
            from voice.ambiguous_quantification import (
                parse_korean_command,
                quantify_korean_ambiguity,
            )

            AMBIGUOUS_QUANTIFICATION_AVAILABLE = True
        except ImportError:
            pass
    return AMBIGUOUS_QUANTIFICATION_AVAILABLE


logger = logging.getLogger(__name__)


class FastPathEmergencyMatcher:
    """초저지연 비상 명령어 매칭 (STT 신뢰도 무시)"""

    EMERGENCY_STOP_PATTERN = re.compile(
        r"(비상\s*정지|긴급\s*정지|즉시\s*정지|올\s*스톱|all\s*stop|임무\s*중지)",
        re.IGNORECASE,
    )
    RTL_PATTERN = re.compile(
        r"(긴급\s*복귀|즉시\s*복귀|복귀\s*명령|RTL)", re.IGNORECASE
    )
    EMCON_PATTERN = re.compile(r"(전파\s*침묵|엠콘|EMCON|무전\s*침묵)", re.IGNORECASE)
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

        if cls.RTL_PATTERN.search(clean_text):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="FAILSAFE",
                priority=CommandPriority.FAILSAFE_ESTOP,
                target_id="drone_1",
                action="RTL",
                confidence=1.0,
            )

        if cls.EMCON_PATTERN.search(clean_text):
            return UnifiedCommand(
                command_id=str(uuid.uuid4()),
                source="FAILSAFE",
                priority=CommandPriority.FAILSAFE_ESTOP,
                target_id=target,
                action="EMCON",
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
    """로컬 Whisper STT (화자 적응 지원 + 전술 프롬프트/정규화)"""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        speaker_adapter: Optional["SpeakerAdapter"] = None,
        tactical_normalizer: Optional["TacticalNormalizer"] = None,
        operation_area: str = "",
        callsigns: Optional[List[str]] = None,
        tactical_terms: Optional[List[str]] = None,
    ):
        if not WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper 패키지가 설치되어 있지 않습니다.")

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.speaker_adapter = speaker_adapter

        # 기본 모델
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

        # 화자별 어댑터 적용 모델 캐시
        self._adapted_models: Dict[str, "AdaptiveWhisperModel"] = {}

        # 전술 정규화기
        self.tactical_normalizer = tactical_normalizer
        self.operation_area = operation_area
        self.callsigns = callsigns or []
        self.tactical_terms = tactical_terms or []

        logger.info(f"Whisper STT 초기화: {model_size} ({device}, {compute_type})")

    def _get_model_for_speaker(self, speaker_id: Optional[str]) -> "WhisperModel":
        """화자별 어댑터 적용 모델 반환"""
        if not speaker_id or not self.speaker_adapter or not _check_speaker_adapter():
            return self.model

        profile = self.speaker_adapter.get_profile(speaker_id)
        if not profile or not profile.adapter_path:
            return self.model

        # 어댑터 모델 캐시 확인
        if speaker_id in self._adapted_models:
            return self._adapted_models[speaker_id].model

        # 어댑터 모델 생성 시도 (CT2 변환된 모델 경로 필요)
        if profile.adapter_path and Path(profile.adapter_path).exists():
            try:
                from voice.speaker_adapter import AdaptiveWhisperModel as AWM

                adapted = AWM(
                    model_size=profile.adapter_path,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                self._adapted_models[speaker_id] = adapted
                logger.info(f"화자별 어댑터 모델 로드: {speaker_id}")
                return adapted.model
            except Exception as e:
                logger.warning(f"어댑터 모델 로드 실패, 기본 모델 사용: {e}")

        return self.model

    def transcribe_audio(
        self,
        audio_np: np.ndarray,
        speaker_id: Optional[str] = None,
        language: str = "ko",
    ) -> Tuple[str, float]:
        """음성 인식 실행 (전술 프롬프트 적용)"""
        model = self._get_model_for_speaker(speaker_id)

        # 전술 프롬프트 동적 생성
        initial_prompt = "드론 1번, 로봇 1번, 하이브리드 1번, 이륙, 착륙, 정지, 앞으로 이동, 복귀, 고도, 미터, 다이브, 기만, 순항, 기동, 비상"
        if self.tactical_normalizer and _check_tactical_normalizer():
            initial_prompt = self.tactical_normalizer.generate_whisper_initial_prompt(
                operation_area=self.operation_area,
                callsigns=self.callsigns,
                tactical_terms=self.tactical_terms,
            )

        segments, _ = model.transcribe(
            audio_np,
            language=language,
            beam_size=3,
            vad_filter=True,
            initial_prompt=initial_prompt,
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
    target_id: str = Field(description="제어 대상 ID")
    action: str = Field(description="수행할 액션")
    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.0
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    vz_mps: float = 0.0
    yaw_rate_radps: float = 0.0


class VoiceIntentParser:
    """
    통합 음성 의도 파서
    - Fast-Path (비상/하이브리드)
    - 커스텀 명령어 매핑 (VoiceEnrollment)
    - LLM 폴백
    - 결정론적 폴백
    """

    SYSTEM_PROMPT = open(
        Path(__file__).parent.parent / "config" / "tactical_parser_prompt.md",
        encoding="utf-8",
    ).read()

    def __init__(
        self,
        llm_client=None,
        enrollment_manager: Optional["VoiceEnrollmentManager"] = None,
    ):
        self.llm_client = llm_client
        self.enrollment_manager = enrollment_manager

    async def parse_to_command(
        self,
        text: str,
        stt_confidence: float,
        active_target: str = "drone_1",
        speaker_id: Optional[str] = None,
        tactical_normalizer: Optional["TacticalNormalizer"] = None,
    ) -> UnifiedCommand:
        # 0) 전술 정규화 (STT 직후, 파싱 전)
        if tactical_normalizer and _check_tactical_normalizer():
            original_text = text
            text = tactical_normalizer.normalize(text)
            if text != original_text:
                logger.info(f"[TACTICAL-NORM] '{original_text}' -> '{text}'")
        fast_cmd = FastPathEmergencyMatcher.match(text, default_target=active_target)
        if fast_cmd is not None:
            logger.info(f"[FAST-PATH] '{text}' -> {fast_cmd.action}")
            return fast_cmd

        # 2) 하이브리드/다이브/기만 전용 Fast-Path
        hybrid_cmd = self._match_hybrid_commands(text, active_target)
        if hybrid_cmd:
            logger.info(f"[HYBRID-PATH] '{text}' -> {hybrid_cmd.action}")
            return hybrid_cmd

        # 3) 커스텀 명령어 매핑 확인 (VoiceEnrollment)
        if self.enrollment_manager and _check_enrollment():
            custom_mapping = self.enrollment_manager.resolve_command(
                recognized_text=text,
                speaker_id=speaker_id,
                stt_confidence=stt_confidence,
            )
            if custom_mapping:
                logger.info(f"[CUSTOM-MAPPING] '{text}' -> {custom_mapping.action}")
                return self._mapping_to_command(
                    custom_mapping, text, stt_confidence, active_target
                )

        # 4) LLM 구조화 파싱
        clarification_needed = False
        reason = ""
        if self.llm_client is not None:
            intent = await self._call_structured_llm(text, active_target)
        else:
            # 5) 결정론적 폴백 파서
            intent, clarification_needed, reason = self._deterministic_fallback_parser(
                text, active_target
            )

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
            clarification_needed=clarification_needed,
            reason=reason,
        )

    def _mapping_to_command(
        self,
        mapping: "VoiceCommandMapping",
        text: str,
        stt_confidence: float,
        active_target: str,
    ) -> UnifiedCommand:
        """VoiceCommandMapping을 UnifiedCommand로 변환"""
        target = mapping.target_device
        if target == "*":
            target = active_target

        # 파라미터에서 숫자 추출 (텍스트 기반 오버라이드)
        params = mapping.params.copy()
        self._extract_numbers_from_text(text, params)

        return UnifiedCommand(
            command_id=str(uuid.uuid4()),
            source="VOICE_NLU",
            priority=CommandPriority(mapping.priority),
            target_id=target,
            action=mapping.action,  # type: ignore[arg-type]
            params=params or {},
            confidence=stt_confidence,
        )

    def _extract_numbers_from_text(self, text: str, params: dict):
        """텍스트에서 숫자 추출하여 파라미터 업데이트"""
        numbers = re.findall(r"(\d+(?:\.\d+)?)", text)
        if not numbers:
            return

        vals = [float(n) for n in numbers]

        # 파라미터 키에 따라 매핑
        if "z_m" in params and "alt" not in params:
            params["z_m"] = vals[0]
        if "target_alt" in params:
            params["target_alt"] = vals[0]
        if "angle" in params and len(vals) > 1:
            params["angle"] = vals[1]
        if "duration" in params:
            params["duration"] = vals[0] if "duration" in params else vals[-1]
        if "vx_mps" in params:
            params["vx_mps"] = vals[0]

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
    ) -> tuple[ParsedVoiceIntent, bool, str]:
        """
        결정론적 폴백 파서
        Returns: (ParsedVoiceIntent, clarification_needed, reason)
        """
        target = (
            "drone_1"
            if "드론" in text
            else ("robot_1" if "로봇" in text else active_target)
        )
        if "하이브리드" in text:
            target = "hybrid_drone_1"

        # 모호한 표현 정량화 모듈 사용 시도
        if _check_ambiguous_quantification():
            try:
                from voice.ambiguous_quantification import parse_korean_command

                parsed = parse_korean_command(text)
                if parsed.get("clarification_needed"):
                    return (
                        ParsedVoiceIntent(
                            target_id=target,
                            action=parsed["action"],
                            x_m=parsed.get("forward_m", 0.0),
                            y_m=parsed.get("right_m", 0.0),
                            z_m=parsed.get("down_m", 0.0),
                            vx_mps=parsed.get("vx_mps", 0.0),
                            vy_mps=parsed.get("vy_mps", 0.0),
                            vz_mps=parsed.get("vz_mps", 0.0),
                            yaw_rate_radps=parsed.get("yaw_rate_radps", 0.0),
                        ),
                        True,
                        parsed.get("reason", "명령이 모호하여 명확화가 필요함"),
                    )
                else:
                    # 모호 표현이 정량화되었으면 해당 값 사용
                    action = parsed["action"]
                    # MOVE_BODY를 MOVE_VEL로 매핑 (UnifiedCommand 액션 리터럴에 맞춤)
                    if action == "MOVE_BODY":
                        action = "MOVE_VEL"
                    # 키 매핑: parse_korean_command는 forward_m/right_m/down_m/yaw_deg 사용
                    # ParsedVoiceIntent는 vx_mps/vy_mps/vz_mps/yaw_rate_radps 사용
                    return (
                        ParsedVoiceIntent(
                            target_id=target,
                            action=action,
                            x_m=parsed.get("forward_m", 0.0),
                            y_m=parsed.get("right_m", 0.0),
                            z_m=parsed.get("down_m", 0.0),
                            vx_mps=parsed.get("forward_m", 0.0),
                            vy_mps=parsed.get("right_m", 0.0),
                            vz_mps=parsed.get("down_m", 0.0),
                            yaw_rate_radps=parsed.get("yaw_deg", 0.0) * 3.14159 / 180.0,
                        ),
                        False,
                        parsed.get("reason", ""),
                    )
            except Exception:
                pass  # 폴백 파서로 진행

        num_match = re.search(r"(\d+(?:\.\d+)?)", text)
        val = float(num_match.group(1)) if num_match else 1.0

        if "이륙" in text:
            return (
                ParsedVoiceIntent(
                    target_id=target, action="TAKEOFF", z_m=val if num_match else 2.5
                ),
                False,
                "",
            )
        elif "착륙" in text:
            return ParsedVoiceIntent(target_id=target, action="LAND"), False, ""
        elif "복귀" in text or "돌아와" in text:
            return ParsedVoiceIntent(target_id=target, action="RTL"), False, ""
        elif "정지" in text or "멈춰" in text or "홀드" in text:
            return ParsedVoiceIntent(target_id=target, action="HOLD"), False, ""
        elif "앞으로" in text or "전진" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vx_mps=val),
                False,
                "",
            )
        elif "뒤로" in text or "후진" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vx_mps=-val),
                False,
                "",
            )
        elif "좌측" in text or "왼쪽" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vy_mps=-val),
                False,
                "",
            )
        elif "우측" in text or "오른쪽" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vy_mps=val),
                False,
                "",
            )
        elif "상승" in text or "올라" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vz_mps=val),
                False,
                "",
            )
        elif "하강" in text or "내려" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", vz_mps=-val),
                False,
                "",
            )
        elif "좌회전" in text:
            return (
                ParsedVoiceIntent(
                    target_id=target, action="MOVE_VEL", yaw_rate_radps=0.5
                ),
                False,
                "",
            )
        elif "우회전" in text:
            return (
                ParsedVoiceIntent(
                    target_id=target, action="MOVE_VEL", yaw_rate_radps=-0.5
                ),
                False,
                "",
            )
        elif "복귀" in text or "돌아와" in text:
            return ParsedVoiceIntent(target_id=target, action="RTL"), False, ""
        elif "고도" in text and "변경" in text:
            return (
                ParsedVoiceIntent(target_id=target, action="MOVE_VEL", z_m=val),
                False,
                "",
            )
        elif "좌표" in text or "이동" in text:
            return (
                ParsedVoiceIntent(
                    target_id=target, action="NAV_TO_POSE", x_m=val, y_m=0.0
                ),
                False,
                "",
            )

        return (
            ParsedVoiceIntent(target_id=target, action="HOLD"),
            True,
            f"해석할 수 없는 음성 명령입니다: '{text}'",
        )

    async def _call_structured_llm(
        self, text: str, active_target: str
    ) -> ParsedVoiceIntent:
        raw_json = await self.llm_client.generate_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"기본 타겟: {active_target} / 명령: {text}",
            response_model=ParsedVoiceIntent,
        )
        return ParsedVoiceIntent.model_validate_json(raw_json)


@dataclass
class VoicePipelineConfig:
    """음성 파이프라인 설정"""

    # STT
    whisper_model_size: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # 화자 적응
    enable_speaker_adaptation: bool = False
    speaker_profiles_dir: str = "~/models/speaker_profiles"

    # 웨이크 워드
    enable_wake_word: bool = False
    wake_word_keywords: List[str] = field(default_factory=list)
    wake_word_keyword_paths: List[str] = field(default_factory=list)
    wake_word_sensitivities: List[float] = field(default_factory=list)
    picovoice_access_key: str = ""

    # 음성 등록
    enable_enrollment: bool = False
    enrollment_storage_dir: str = "~/models/voice_enrollment"

    # NLU 학습 (자연어 이해 지속적 개선)
    enable_nlu_learning: bool = False
    nlu_learning_config: Optional["NLUModelConfig"] = None
    nlu_model_type: str = "fewshot"  # "fewshot", "lora", "classifier"
    auto_retrain_threshold: int = 50  # 이만큼 피드백 쌓이면 자동 재학습

    # VAD
    vad_aggressiveness: int = 2  # 0-3
    silence_timeout_sec: float = 2.0
    min_audio_length_sec: float = 0.5


class VoiceCommandPipeline:
    """
    완전한 음성 명령 파이프라인
    - 웨이크 워드 대기 → VAD → STT → NLU → 명령 실행
    - 화자 적응, 커스텀 명령어 지원
    """

    def __init__(
        self,
        config: "VoicePipelineConfig",
        on_command: Optional[Callable[["UnifiedCommand"], None]] = None,
        on_wake_word: Optional[Callable[["WakeWordEvent"], None]] = None,
        on_transcription: Optional[Callable[[str, float], None]] = None,
    ):
        self.config = config
        self.on_command = on_command
        self.on_wake_word = on_wake_word
        self.on_transcription = on_transcription

        # 컴포넌트 초기화
        self._init_components()

        # 상태
        self._running = False
        self._wake_word_detected = False
        self._recording = False
        self._audio_buffer: List[np.ndarray] = []
        self.active_target = "drone_1"  # 현재 제어 대상 (음성/명령으로 변경 가능)

    def _init_components(self):
        # 화자 적응
        self.speaker_adapter = None
        if self.config.enable_speaker_adaptation and _check_speaker_adapter():
            from voice.speaker_adapter import SpeakerAdapter as SA

            self.speaker_adapter = SA(self.config.speaker_profiles_dir)
            self.active_speaker_id = self.speaker_adapter.active_profile_id
        else:
            self.active_speaker_id = None

        # STT
        self.stt = LocalWhisperSTT(
            model_size=self.config.whisper_model_size,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type,
            speaker_adapter=self.speaker_adapter,
        )

        # 음성 등록
        self.enrollment_manager = None
        if self.config.enable_enrollment and _check_enrollment():
            from voice.voice_enrollment import VoiceEnrollmentManager as VEM

            self.enrollment_manager = VEM(self.config.enrollment_storage_dir)

        # NLU 학습 파이프라인
        self.nlu_learning = None
        if self.config.enable_nlu_learning and _check_nlu_learning():
            from voice.nlu_learning import (
                NLUModelConfig,
                NLULearningPipeline,
                LearningVoiceIntentParser,
                NLUModelType,
            )

            nlu_config = self.config.nlu_learning_config or NLUModelConfig()
            # 모델 타입 설정
            if self.config.nlu_model_type == "lora":
                nlu_config.model_type = NLUModelType.LLM_LORA
            elif self.config.nlu_model_type == "classifier":
                nlu_config.model_type = NLUModelType.CLASSIFIER
            else:
                nlu_config.model_type = NLUModelType.LLM_FEWSHOT

            self.nlu_learning = NLULearningPipeline(nlu_config)
            # 기본 파서를 학습 래퍼로 감싸기
            base_parser = VoiceIntentParser(
                llm_client=None,
                enrollment_manager=self.enrollment_manager,
            )
            self.parser = LearningVoiceIntentParser(base_parser, self.nlu_learning)
        else:
            # 기본 파서
            self.parser = VoiceIntentParser(
                llm_client=None,
                enrollment_manager=self.enrollment_manager,
            )

        # 웨이크 워드
        self.wake_word_detector = None
        if self.config.enable_wake_word and _check_wake_word():
            from voice.wake_word_detector import (
                KoreanWakeWordDetector,
                WakeWordDetector,
                WakeWordConfig,
            )

            if self.config.wake_word_keyword_paths:
                self.wake_word_detector = KoreanWakeWordDetector(
                    keyword_paths=self.config.wake_word_keyword_paths,
                    on_detected=self._handle_wake_word,
                )
            elif self.config.wake_word_keywords:
                self.wake_word_detector = WakeWordDetector(
                    WakeWordConfig(
                        keywords=self.config.wake_word_keywords,
                        sensitivities=self.config.wake_word_sensitivities,
                    ),
                    on_detected=self._handle_wake_word,
                )

    def _handle_wake_word(self, event: "WakeWordEvent"):
        """웨이크 워드 감지 콜백"""
        logger.info(f"웨이크 워드 감지: {event.keyword}")
        self._wake_word_detected = True
        if self.on_wake_word:
            self.on_wake_word(event)

    def start(self):
        """파이프라인 시작"""
        if self._running:
            return

        self._running = True

        # 웨이크 워드 감지 시작
        if self.wake_word_detector:
            self.wake_word_detector.start()
            logger.info("웨이크 워드 대기 모드 시작")
        else:
            logger.info("웨이크 워드 없이 직접 STT 모드 시작")

    def stop(self):
        """파이프라인 중지"""
        self._running = False

        if self.wake_word_detector:
            self.wake_word_detector.stop()

        logger.info("음성 파이프라인 중지")

    def process_audio_chunk(self, audio_np: np.ndarray) -> Optional[UnifiedCommand]:
        """
        오디오 청크 처리 (실시간 스트리밍용)
        웨이크 워드 감지 후 VAD로 음성 구간 추출 → STT → NLU
        """
        if not self._running:
            return None

        # 웨이크 워드 모드에서 감지 대기
        if self.wake_word_detector and not self._wake_word_detected:
            return None

        # 간단한 VAD (에너지 기반)
        energy = np.mean(np.abs(audio_np))
        is_speech = energy > 0.01  # 임계값 조정 필요

        if is_speech:
            self._audio_buffer.append(audio_np)
            self._recording = True
        elif self._recording:
            # 무음 감지 → 세그먼트 완료
            return self._process_recorded_audio()

        return None

    def _process_recorded_audio(self) -> Optional[UnifiedCommand]:
        """녹음된 오디오 처리"""
        if not self._audio_buffer:
            self._recording = False
            self._wake_word_detected = False  # 웨이크 워드 모드면 리셋
            return None

        # 오디오 연결
        full_audio = np.concatenate(self._audio_buffer)
        self._audio_buffer = []
        self._recording = False

        # 최소 길이 체크
        if len(full_audio) < self.config.min_audio_length_sec * 16000:
            logger.debug("오디오 너무 짧음, 무시")
            self._wake_word_detected = False
            return None

        # STT 실행
        try:
            text, confidence = self.stt.transcribe_audio(
                full_audio,
                speaker_id=self.active_speaker_id,
            )

            if not text:
                logger.debug("STT 결과 없음")
                self._wake_word_detected = False
                return None

            logger.info(f"STT: '{text}' (conf={confidence:.2f})")

            if self.on_transcription:
                self.on_transcription(text, confidence)

            # 신뢰도 체크
            if confidence < 0.5:
                logger.warning(f"STT 신뢰도 낮음: {confidence:.2f}")
                self._wake_word_detected = False
                return None

            # NLU 파싱 (비동기 실행 필요)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            command = loop.run_until_complete(
                self.parser.parse_to_command(
                    text=text,
                    stt_confidence=confidence,
                    active_target=self.active_target,
                    speaker_id=self.active_speaker_id or "",
                )
            )

            # 웨이크 워드 모드면 리셋
            self._wake_word_detected = False

            if self.on_command:
                self.on_command(command)

            return command

        except Exception as e:
            logger.error(f"오디오 처리 오류: {e}")
            self._wake_word_detected = False
            return None

    def set_active_speaker(self, speaker_id: str):
        """활성 화자 변경"""
        if self.speaker_adapter:
            self.speaker_adapter.set_active(speaker_id)
            self.active_speaker_id = speaker_id
            logger.info(f"활성 화자 변경: {speaker_id}")

    def add_custom_command(
        self,
        phrase: str,
        target_device: str,
        action: str,
        params: dict = None,
        speaker_id: str = None,
        **kwargs,
    ):
        """커스텀 명령어 추가"""
        if self.enrollment_manager:
            sid = speaker_id or self.active_speaker_id
            self.enrollment_manager.add_mapping(
                phrase=phrase,
                target_device=target_device,
                action=action,
                params=params or {},
                speaker_id=sid,
                **kwargs,
            )

    def get_stats(self) -> dict:
        """파이프라인 통계"""
        stats = {
            "running": self._running,
            "wake_word_enabled": self.wake_word_detector is not None,
            "speaker_adaptation": self.speaker_adapter is not None,
            "enrollment": self.enrollment_manager is not None,
            "nlu_learning": self.nlu_learning is not None,
            "active_speaker": self.active_speaker_id,
            "active_target": self.active_target,
        }

        if self.wake_word_detector:
            stats["wake_word"] = self.wake_word_detector.get_stats()

        if self.speaker_adapter:
            stats["profiles"] = len(self.speaker_adapter.profiles)

        if self.enrollment_manager:
            stats["custom_mappings"] = len(self.enrollment_manager.mappings)

        if self.nlu_learning:
            stats["nlu_learning"] = self.nlu_learning.get_pipeline_status()

        return stats

    def set_active_target(self, target_id: str):
        """활성 제어 대상 변경 (drone_1, robot_1, hybrid_drone_1 등)"""
        self.active_target = target_id
        logger.info(f"활성 타겟 변경: {target_id}")

    def submit_nlu_feedback(
        self, sample_id: str, is_correct: bool, correct_text: str = ""
    ) -> bool:
        """NLU 파싱 결과에 대한 사용자 피드백 제출"""
        if self.nlu_learning and hasattr(self.parser, "submit_feedback"):
            return self.parser.submit_feedback(sample_id, is_correct, correct_text)
        logger.warning("NLU 학습이 활성화되지 않음")
        return False

    def get_active_learning_tasks(self, count: int = 10) -> List[Dict]:
        """Active Learning: 라벨링이 필요한 샘플 목록 반환"""
        if self.nlu_learning:
            return self.nlu_learning.get_active_learning_tasks(count)
        return []


# 편의 함수
def create_voice_pipeline(
    config: "VoicePipelineConfig" = None,
    on_command: Callable[["UnifiedCommand"], None] = None,
    on_wake_word: Callable[["WakeWordEvent"], None] = None,
    on_transcription: Callable[[str, float], None] = None,
) -> "VoiceCommandPipeline":
    """음성 파이프라인 생성"""
    if config is None:
        config = VoicePipelineConfig()
    return VoiceCommandPipeline(config, on_command, on_wake_word, on_transcription)


# 사용 예시
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    config = VoicePipelineConfig(
        whisper_model_size="base",
        enable_wake_word=False,  # PICOVOICE_ACCESS_KEY 필요
        enable_enrollment=True,
        enable_speaker_adaptation=False,  # 어댑터 모델 필요
    )

    def on_cmd(cmd: UnifiedCommand):
        print(f"[명령 실행] {cmd.action} -> {cmd.target_id}")

    def on_wake(event):
        print(f"[웨이크 워드] {event.keyword}")

    def on_trans(text: str, conf: float):
        print(f"[인식] {text} ({conf:.2f})")

    pipeline = create_voice_pipeline(config, on_cmd, on_wake, on_trans)

    # 커스텀 명령어 등록
    pipeline.add_custom_command(
        phrase="내 드론 이륙",
        target_device="drone_1",
        action="TAKEOFF",
        params={"z_m": 5.0},
    )

    pipeline.start()
    print("파이프라인 시작됨 (테스트용 - 실제 오디오 입력 필요)")

    # 테스트용 직접 텍스트 처리
    import asyncio

    async def test():
        cmd = await pipeline.parser.parse_to_command("내 드론 이륙", 0.95, "drone_1")
        print(f"파싱 결과: {cmd.action} {cmd.params}")

    asyncio.run(test())
    pipeline.stop()
