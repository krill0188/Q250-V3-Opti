"""
Wake Word Detection Module using Porcupine (Picovoice)
Always-on "Hey Drone" / "드론아" detection
"""
import os
import struct
import threading
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional, List, Dict
from enum import Enum
from collections import deque

import pvporcupine
import pyaudio

logger = logging.getLogger(__name__)


class WakeWordState(Enum):
    """웨이크 워드 상태"""
    LISTENING = "listening"      # 대기 중
    DETECTED = "detected"        # 감지됨
    COOLDOWN = "cooldown"        # 쿨다운 중 (연속 감지 방지)
    DISABLED = "disabled"        # 비활성화


@dataclass
class WakeWordConfig:
    """웨이크 워드 설정"""
    # 내장 키워드: "porcupine", "hey google", "alexa", "hey siri", "computer", "jarvis", "bumblebee", "terminator"
    # 커스텀 키워드는 Picovoice Console에서 .ppn 파일 생성 필요
    keywords: List[str] = None
    keyword_paths: List[str] = None  # .ppn 파일 경로들
    sensitivities: List[float] = None  # 0.0 ~ 1.0
    library_path: Optional[str] = None
    model_path: Optional[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = ["porcupine"]  # 기본값
        if self.sensitivities is None:
            self.sensitivities = [0.5] * len(self.keywords)
        if len(self.sensitivities) != len(self.keywords):
            self.sensitivities = [0.5] * len(self.keywords)


@dataclass
class WakeWordEvent:
    """웨이크 워드 감지 이벤트"""
    keyword: str
    keyword_index: int
    timestamp: float
    confidence: float  # Porcupine은 confidence 미제공, 고정값


class WakeWordDetector:
    """
    Porcupine 기반 웨이크 워드 감지기
    - 상시 대기 (백그라운드 스레드)
    - 콜백 기반 이벤트 알림
    - 오디오 스트림 관리
    """

    def __init__(
        self,
        config: WakeWordConfig,
        on_detected: Optional[Callable[[WakeWordEvent], None]] = None,
        sample_rate: int = 16000,
        frame_length: int = 512,
    ):
        self.config = config
        self.on_detected = on_detected
        self.sample_rate = sample_rate
        self.frame_length = frame_length

        self._porcupine = None
        self._audio_stream = None
        self._pa = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._state = WakeWordState.DISABLED
        self._cooldown_until = 0.0
        self._cooldown_sec = 2.0  # 감지 후 2초 쿨다운

        # 통계
        self._stats = {
            "total_detections": 0,
            "last_detection_time": None,
            "keywords_detected": {},
        }

        self._init_porcupine()

    def _init_porcupine(self):
        """Porcupine 인스턴스 생성"""
        try:
            # 액세스 키 필요 (Picovoice Console에서 무료 발급)
            access_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if not access_key:
                logger.warning("PICOVOICE_ACCESS_KEY 환경변수 미설정 - 웨이크 워드 비활성화")
                return

            keyword_paths = self.config.keyword_paths or []
            keywords = self.config.keywords or []

            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=keyword_paths,
                keywords=keywords,
                sensitivities=self.config.sensitivities,
                library_path=self.config.library_path,
                model_path=self.config.model_path,
            )
            logger.info(f"Porcupine 초기화 완료: {len(self._porcupine.keywords)} 키워드")
            self._state = WakeWordState.LISTENING

        except pvporcupine.PorcupineInvalidArgumentError as e:
            logger.error(f"Porcupine 인수 오류: {e}")
        except pvporcupine.PorcupineActivationError as e:
            logger.error(f"Porcupine 액세스 키 오류: {e}")
        except Exception as e:
            logger.error(f"Porcupine 초기화 실패: {e}")

    def start(self):
        """감지 시작"""
        if self._running or not self._porcupine:
            return False

        try:
            self._pa = pyaudio.PyAudio()
            self._audio_stream = self._pa.open(
                rate=self.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.frame_length,
                stream_callback=None,  # 블로킹 모드
            )

            self._running = True
            self._thread = threading.Thread(target=self._detection_loop, daemon=True)
            self._thread.start()

            logger.info("웨이크 워드 감지 시작됨")
            return True

        except Exception as e:
            logger.error(f"오디오 스트림 시작 실패: {e}")
            self.stop()
            return False

    def stop(self):
        """감지 중지"""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._audio_stream:
            self._audio_stream.stop_stream()
            self._audio_stream.close()
            self._audio_stream = None

        if self._pa:
            self._pa.terminate()
            self._pa = None

        self._state = WakeWordState.DISABLED
        logger.info("웨이크 워드 감지 중지됨")

    def _detection_loop(self):
        """메인 감지 루프 (백그라운드 스레드)"""
        while self._running:
            try:
                # 오디오 프레임 읽기
                pcm_data = self._audio_stream.read(self.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.frame_length, pcm_data)

                # Porcupine 처리
                keyword_index = self._porcupine.process(pcm)

                if keyword_index >= 0:
                    self._handle_detection(keyword_index)

                # 쿨다운 체크
                if self._state == WakeWordState.COOLDOWN:
                    if time.time() > self._cooldown_until:
                        self._state = WakeWordState.LISTENING

            except Exception as e:
                logger.error(f"감지 루프 오류: {e}")
                time.sleep(0.1)

    def _handle_detection(self, keyword_index: int):
        """감지 처리"""
        if self._state != WakeWordState.LISTENING:
            return

        keyword = self._porcupine.keywords[keyword_index]
        timestamp = time.time()

        # 쿨다운 설정
        self._state = WakeWordState.COOLDOWN
        self._cooldown_until = timestamp + self._cooldown_sec

        # 통계 업데이트
        self._stats["total_detections"] += 1
        self._stats["last_detection_time"] = timestamp
        self._stats["keywords_detected"][keyword] = self._stats["keywords_detected"].get(keyword, 0) + 1

        # 이벤트 생성
        event = WakeWordEvent(
            keyword=keyword,
            keyword_index=keyword_index,
            timestamp=timestamp,
            confidence=1.0,  # Porcupine은 confidence 제공 안 함
        )

        logger.info(f"웨이크 워드 감지: {keyword} (index={keyword_index})")

        # 콜백 실행
        if self.on_detected:
            try:
                self.on_detected(event)
            except Exception as e:
                logger.error(f"웨이크 워드 콜백 오류: {e}")

    def get_state(self) -> WakeWordState:
        return self._state

    def get_stats(self) -> Dict:
        return self._stats.copy()

    def set_cooldown(self, seconds: float):
        self._cooldown_sec = max(0.5, seconds)

    def __del__(self):
        self.stop()
        if self._porcupine:
            self._porcupine.delete()


class KoreanWakeWordDetector(WakeWordDetector):
    """
    한국어 웨이크 워드 전용 감지기
    기본 키워드: "드론아", "헤이 드론", "시작", "비상"
    커스텀 .ppn 파일 필요 (Picovoice Console에서 생성)
    """

    DEFAULT_KEYWORDS = [
        "드론아",
        "헤이 드론",
        "시작",
        "비상",
        "정지",
    ]

    def __init__(
        self,
        custom_keyword_paths: List[str] = None,
        sensitivities: List[float] = None,
        on_detected: Optional[Callable[[WakeWordEvent], None]] = None,
    ):
        # 커스텀 키워드 경로가 없으면 기본 키워드 사용 (내장 키워드엔 한국어 없음)
        # 실제로는 .ppn 파일 필수
        keyword_paths = custom_keyword_paths or []

        config = WakeWordConfig(
            keyword_paths=keyword_paths,
            keywords=self.DEFAULT_KEYWORDS if not keyword_paths else [],
            sensitivities=sensitivities or [0.6] * len(self.DEFAULT_KEYWORDS),
        )

        super().__init__(config, on_detected)

        if not keyword_paths:
            logger.warning(
                "한국어 웨이크 워드용 .ppn 파일이 필요합니다. "
                "Picovoice Console(console.picovoice.ai)에서 생성 후 keyword_paths에 전달하세요."
            )


# 편의 함수
def create_wake_word_detector(
    keywords: List[str] = None,
    keyword_paths: List[str] = None,
    sensitivities: List[float] = None,
    on_detected: Optional[Callable[[WakeWordEvent], None]] = None,
) -> WakeWordDetector:
    """웨이크 워드 감지기 생성"""
    config = WakeWordConfig(
        keywords=keywords,
        keyword_paths=keyword_paths,
        sensitivities=sensitivities,
    )
    return WakeWordDetector(config, on_detected)


def create_korean_wake_word_detector(
    keyword_paths: List[str] = None,
    on_detected: Optional[Callable[[WakeWordEvent], None]] = None,
) -> KoreanWakeWordDetector:
    """한국어 웨이크 워드 감지기 생성"""
    return KoreanWakeWordDetector(keyword_paths, on_detected=on_detected)


# 사용 예시
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_wake_word(event: WakeWordEvent):
        print(f"[WAKE WORD] {event.keyword} 감지됨!")

    # 환경변수 PICOVOICE_ACCESS_KEY 설정 필요
    detector = create_wake_word_detector(
        keywords=["porcupine", "jarvis"],
        sensitivities=[0.5, 0.6],
        on_detected=on_wake_word,
    )

    if detector.start():
        print("웨이크 워드 대기 중... (Ctrl+C로 종료)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n종료")
        finally:
            detector.stop()