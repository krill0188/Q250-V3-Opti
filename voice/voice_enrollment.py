"""
Voice Enrollment Module - Custom Command Mapping per User
사용자별 커스텀 음성 명령어 매핑 등록/관리
"""
import os
import json
import logging
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """명령어 카테고리"""
    NAVIGATION = "navigation"       # 이동/내비게이션
    FLIGHT_MODE = "flight_mode"     # 비행 모드
    EMERGENCY = "emergency"         # 비상
    CAMERA = "camera"               # 카메라/짐벌
    PAYLOAD = "payload"             # 페이로드
    CUSTOM = "custom"               # 사용자 정의


@dataclass
class VoiceCommandMapping:
    """음성 명령어 매핑"""
    phrase: str                     # 음성 구문: "내 드론 이륙"
    target_device: str              # 대상 기기: "drone_1", "hybrid_drone_1"
    action: str                     # UnifiedCommand action: "TAKEOFF", "DIVE_ATTACK"
    params: Dict = field(default_factory=dict)  # 추가 파라미터
    category: CommandCategory = CommandCategory.CUSTOM
    priority: int = 2               # 우선순위 (0=FAILSAFE, 1=MANUAL, 2=VOICE)
    confidence_threshold: float = 0.85
    enabled: bool = True
    speaker_id: Optional[str] = None  # 특정 화자만 적용 (None=전체)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    usage_count: int = 0
    last_used: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "phrase": self.phrase,
            "target_device": self.target_device,
            "action": self.action,
            "params": self.params,
            "category": self.category.value,
            "priority": self.priority,
            "confidence_threshold": self.confidence_threshold,
            "enabled": self.enabled,
            "speaker_id": self.speaker_id,
            "created_at": self.created_at,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VoiceCommandMapping":
        data = data.copy()
        data["category"] = CommandCategory(data.get("category", "custom"))
        return cls(**data)


@dataclass
class VoiceEnrollmentSession:
    """음성 등록 세션"""
    session_id: str
    speaker_id: str
    phrase: str
    target_device: str
    action: str
    params: Dict
    audio_samples: List[str] = field(default_factory=list)  # 녹음된 파일 경로들
    status: str = "recording"  # recording, verifying, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class VoiceEnrollmentManager:
    """
    음성 명령어 등록 관리자
    - 사용자별 커스텀 명령어 매핑 CRUD
    - 등록 세션 관리 (녹음 → 검증 → 저장)
    - VoiceIntentParser와 연동
    """

    def __init__(self, storage_dir: str = "~/models/voice_enrollment"):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.mappings_file = self.storage_dir / "command_mappings.json"
        self.sessions_file = self.storage_dir / "enrollment_sessions.json"

        self.mappings: Dict[str, VoiceCommandMapping] = {}  # phrase -> mapping
        self.sessions: Dict[str, VoiceEnrollmentSession] = {}
        self.speaker_mappings: Dict[str, List[str]] = {}  # speaker_id -> phrase list

        self._load_mappings()
        self._load_sessions()

        # 기본 내장 매핑 (시스템 기본값)
        self._register_default_mappings()

    def _register_default_mappings(self):
        """시스템 기본 명령어 매핑 (모든 화자 공통)"""
        defaults = [
            # 비상 (최우선)
            VoiceCommandMapping(
                phrase="비상 정지",
                target_device="*",
                action="ESTOP",
                category=CommandCategory.EMERGENCY,
                priority=0,
                confidence_threshold=0.5,
                speaker_id=None,
            ),
            VoiceCommandMapping(
                phrase="즉시 착륙",
                target_device="*",
                action="LAND",
                category=CommandCategory.EMERGENCY,
                priority=0,
                confidence_threshold=0.7,
                speaker_id=None,
            ),
            # 기본 비행
            VoiceCommandMapping(
                phrase="이륙",
                target_device="drone_1",
                action="TAKEOFF",
                params={"z_m": 3.0},
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="착륙",
                target_device="drone_1",
                action="LAND",
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="복귀",
                target_device="drone_1",
                action="RTL",
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="일시정지",
                target_device="drone_1",
                action="HOLD",
                category=CommandCategory.FLIGHT_MODE,
            ),
            # 이동
            VoiceCommandMapping(
                phrase="전진",
                target_device="drone_1",
                action="MOVE_VEL",
                params={"vx_mps": 2.0},
                category=CommandCategory.NAVIGATION,
            ),
            VoiceCommandMapping(
                phrase="후진",
                target_device="drone_1",
                action="MOVE_VEL",
                params={"vx_mps": -2.0},
                category=CommandCategory.NAVIGATION,
            ),
            VoiceCommandMapping(
                phrase="좌회전",
                target_device="drone_1",
                action="MOVE_VEL",
                params={"yaw_rate_radps": 0.5},
                category=CommandCategory.NAVIGATION,
            ),
            VoiceCommandMapping(
                phrase="우회전",
                target_device="drone_1",
                action="MOVE_VEL",
                params={"yaw_rate_radps": -0.5},
                category=CommandCategory.NAVIGATION,
            ),
            # 하이브리드 드론 전용
            VoiceCommandMapping(
                phrase="다이브",
                target_device="hybrid_drone_1",
                action="DIVE_ATTACK",
                params={"target_alt": 100, "angle": 70},
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="기만 모드",
                target_device="hybrid_drone_1",
                action="DECEPTION_START",
                params={"pattern": "AUTO", "duration": 30},
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="기만 중지",
                target_device="hybrid_drone_1",
                action="DECEPTION_STOP",
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="순항 모드",
                target_device="hybrid_drone_1",
                action="SET_MODE",
                params={"mode": "CRUISE"},
                category=CommandCategory.FLIGHT_MODE,
            ),
            VoiceCommandMapping(
                phrase="FPV 모드",
                target_device="hybrid_drone_1",
                action="SET_MODE",
                params={"mode": "FPV_AGILE"},
                category=CommandCategory.FLIGHT_MODE,
            ),
        ]

        for mapping in defaults:
            key = self._make_key(mapping.phrase, mapping.speaker_id)
            if key not in self.mappings:
                self.mappings[key] = mapping

        self._save_mappings()

    def _make_key(self, phrase: str, speaker_id: Optional[str]) -> str:
        """매핑 키 생성 (화자별 구분)"""
        if speaker_id:
            return f"{speaker_id}:{phrase}"
        return f"global:{phrase}"

    def _load_mappings(self):
        if self.mappings_file.exists():
            try:
                with open(self.mappings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for key, mapping_data in data.items():
                        self.mappings[key] = VoiceCommandMapping.from_dict(mapping_data)
                        # 화자별 인덱스 구성
                        speaker = mapping_data.get("speaker_id")
                        if speaker:
                            self.speaker_mappings.setdefault(speaker, []).append(key)
                logger.info(f"명령어 매핑 로드: {len(self.mappings)}개")
            except Exception as e:
                logger.error(f"매핑 로드 실패: {e}")

    def _save_mappings(self):
        try:
            data = {k: v.to_dict() for k, v in self.mappings.items()}
            with open(self.mappings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"매핑 저장 실패: {e}")

    def _load_sessions(self):
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for session_data in data:
                        session = VoiceEnrollmentSession(**session_data)
                        self.sessions[session.session_id] = session
            except Exception as e:
                logger.error(f"세션 로드 실패: {e}")

    def _save_sessions(self):
        try:
            data = [s.__dict__ for s in self.sessions.values()]
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"세션 저장 실패: {e}")

    # === 매핑 CRUD ===

    def add_mapping(
        self,
        phrase: str,
        target_device: str,
        action: str,
        params: Dict = None,
        category: CommandCategory = CommandCategory.CUSTOM,
        priority: int = 2,
        confidence_threshold: float = 0.85,
        speaker_id: Optional[str] = None,
    ) -> VoiceCommandMapping:
        """커스텀 명령어 매핑 추가"""
        mapping = VoiceCommandMapping(
            phrase=phrase,
            target_device=target_device,
            action=action,
            params=params or {},
            category=category,
            priority=priority,
            confidence_threshold=confidence_threshold,
            speaker_id=speaker_id,
        )

        key = self._make_key(phrase, speaker_id)
        self.mappings[key] = mapping

        if speaker_id:
            self.speaker_mappings.setdefault(speaker_id, []).append(key)

        self._save_mappings()
        logger.info(f"명령어 매핑 추가: {phrase} -> {action} ({speaker_id or 'global'})")
        return mapping

    def remove_mapping(self, phrase: str, speaker_id: Optional[str] = None) -> bool:
        """매핑 삭제"""
        key = self._make_key(phrase, speaker_id)
        if key in self.mappings:
            del self.mappings[key]
            if speaker_id and speaker_id in self.speaker_mappings:
                self.speaker_mappings[speaker_id] = [
                    k for k in self.speaker_mappings[speaker_id] if k != key
                ]
            self._save_mappings()
            logger.info(f"명령어 매핑 삭제: {phrase} ({speaker_id or 'global'})")
            return True
        return False

    def get_mapping(self, phrase: str, speaker_id: Optional[str] = None) -> Optional[VoiceCommandMapping]:
        """매핑 조회 (화자별 우선, 없으면 글로벌)"""
        # 화자별 매핑 우선
        if speaker_id:
            key = self._make_key(phrase, speaker_id)
            if key in self.mappings:
                return self.mappings[key]

        # 글로벌 매핑
        key = self._make_key(phrase, None)
        return self.mappings.get(key)

    def get_all_mappings(self, speaker_id: Optional[str] = None) -> List[VoiceCommandMapping]:
        """모든 매핑 조회 (화자별 + 글로벌)"""
        result = []

        # 글로벌 매핑
        for key, mapping in self.mappings.items():
            if mapping.speaker_id is None:
                result.append(mapping)

        # 화자별 매핑
        if speaker_id and speaker_id in self.speaker_mappings:
            for key in self.speaker_mappings[speaker_id]:
                if key in self.mappings:
                    result.append(self.mappings[key])

        return result

    def get_mappings_by_category(
        self,
        category: CommandCategory,
        speaker_id: Optional[str] = None
    ) -> List[VoiceCommandMapping]:
        """카테고리별 매핑 조회"""
        all_mappings = self.get_all_mappings(speaker_id)
        return [m for m in all_mappings if m.category == category]

    def enable_mapping(self, phrase: str, speaker_id: Optional[str] = None, enabled: bool = True):
        """매핑 활성화/비활성화"""
        mapping = self.get_mapping(phrase, speaker_id)
        if mapping:
            mapping.enabled = enabled
            self._save_mappings()

    # === 등록 세션 관리 ===

    def start_enrollment_session(
        self,
        speaker_id: str,
        phrase: str,
        target_device: str,
        action: str,
        params: Dict = None,
    ) -> VoiceEnrollmentSession:
        """음성 등록 세션 시작"""
        session = VoiceEnrollmentSession(
            session_id=str(uuid.uuid4())[:8],
            speaker_id=speaker_id,
            phrase=phrase,
            target_device=target_device,
            action=action,
            params=params or {},
        )
        self.sessions[session.session_id] = session
        self._save_sessions()
        logger.info(f"등록 세션 시작: {session.session_id} - {phrase}")
        return session

    def add_audio_sample(self, session_id: str, audio_path: str) -> bool:
        """세션에 음성 샘플 추가"""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.audio_samples.append(audio_path)
        self._save_sessions()
        return True

    def complete_enrollment(
        self,
        session_id: str,
        confidence_threshold: float = 0.85,
        category: CommandCategory = CommandCategory.CUSTOM,
        priority: int = 2,
    ) -> Optional[VoiceCommandMapping]:
        """등록 완료 → 매핑 저장"""
        session = self.sessions.get(session_id)
        if not session or session.status != "recording":
            return None

        # 매핑 생성
        mapping = self.add_mapping(
            phrase=session.phrase,
            target_device=session.target_device,
            action=session.action,
            params=session.params,
            category=category,
            priority=priority,
            confidence_threshold=confidence_threshold,
            speaker_id=session.speaker_id,
        )

        session.status = "completed"
        self._save_sessions()
        logger.info(f"등록 완료: {session_id} -> {mapping.phrase}")
        return mapping

    def cancel_enrollment(self, session_id: str) -> bool:
        """등록 취소"""
        session = self.sessions.get(session_id)
        if session:
            session.status = "cancelled"
            self._save_sessions()
            return True
        return False

    # === VoiceIntentParser 연동 ===

    def resolve_command(
        self,
        recognized_text: str,
        speaker_id: Optional[str] = None,
        stt_confidence: float = 0.95,
    ) -> Optional[VoiceCommandMapping]:
        """
        인식된 텍스트를 명령어 매핑으로 변환
        VoiceIntentParser에서 호출하여 커스텀 매핑 우선 적용
        """
        # 1. 완전 일치 검색 (화자별 우선)
        mapping = self.get_mapping(recognized_text, speaker_id)
        if mapping and mapping.enabled:
            if stt_confidence >= mapping.confidence_threshold:
                mapping.usage_count += 1
                mapping.last_used = datetime.now().isoformat()
                self._save_mappings()
                return mapping

        # 2. 부분 일치 검색 (키워드 포함)
        all_mappings = self.get_all_mappings(speaker_id)
        for m in all_mappings:
            if m.enabled and m.phrase in recognized_text:
                if stt_confidence >= m.confidence_threshold:
                    m.usage_count += 1
                    m.last_used = datetime.now().isoformat()
                    self._save_mappings()
                    return m

        return None


# 편의 함수
def create_enrollment_manager(storage_dir: str = "~/models/voice_enrollment") -> VoiceEnrollmentManager:
    return VoiceEnrollmentManager(storage_dir)


# 사용 예시
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = create_enrollment_manager()

    # 커스텀 명령어 추가
    manager.add_mapping(
        phrase="내 드론 이륙",
        target_device="drone_1",
        action="TAKEOFF",
        params={"z_m": 5.0},
        speaker_id="user_001",
    )

    manager.add_mapping(
        phrase="전투 모드",
        target_device="hybrid_drone_1",
        action="SET_MODE",
        params={"mode": "DIVE_ATTACK"},
        category=CommandCategory.FLIGHT_MODE,
        speaker_id="user_001",
    )

    # 조회
    mappings = manager.get_all_mappings("user_001")
    for m in mappings:
        print(f"  {m.phrase} -> {m.action} ({m.category.value})")

    # 텍스트로 명령어 해석
    result = manager.resolve_command("내 드론 이륙해", speaker_id="user_001")
    if result:
        print(f"해석됨: {result.action} with {result.params}")