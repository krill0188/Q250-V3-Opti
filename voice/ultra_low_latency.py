"""
Ultra-Low Latency Voice Pipeline for Drone Control
Optimized for <500ms end-to-end latency
- Streaming STT (partial results)
- Model quantization (int4/int8)
- Parallel processing
- Command prediction/caching
- Edge-optimized models (Whisper.cpp, Silero VAD)
"""

import asyncio
import logging
import time
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any, Tuple
from collections import deque, defaultdict
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """파이프라인 단계 (프로파일링용)"""

    WAKE_WORD = "wake_word"
    VAD_START = "vad_start"
    VAD_END = "vad_end"
    STT_START = "stt_start"
    STT_PARTIAL = "stt_partial"
    STT_FINAL = "stt_final"
    NLU_START = "nlu_start"
    NLU_END = "nlu_end"
    ARBITRATE = "arbitrate"
    DISPATCH = "dispatch"
    EXECUTE = "execute"


@dataclass
class LatencyProfile:
    """단계별 지연 시간 프로파일"""

    timestamps: Dict[PipelineStage, float] = field(default_factory=dict)

    def mark(self, stage: PipelineStage):
        self.timestamps[stage] = time.perf_counter()

    def elapsed(self, start: PipelineStage, end: PipelineStage) -> float:
        if start in self.timestamps and end in self.timestamps:
            return (self.timestamps[end] - self.timestamps[start]) * 1000  # ms
        return -1

    def total_ms(self) -> float:
        if (
            PipelineStage.WAKE_WORD in self.timestamps
            and PipelineStage.EXECUTE in self.timestamps
        ):
            return (
                self.timestamps[PipelineStage.EXECUTE]
                - self.timestamps[PipelineStage.WAKE_WORD]
            ) * 1000
        return -1

    def summary(self) -> Dict[str, float]:
        stages = list(PipelineStage)
        result = {}
        for i in range(len(stages) - 1):
            result[f"{stages[i].value}->{stages[i+1].value}"] = self.elapsed(
                stages[i], stages[i + 1]
            )
        result["total"] = self.total_ms()
        return result


class StreamingVAD:
    """
    초저지연 스트리밍 VAD (Silero VAD 기반)
    - 10ms 프레임 단위 처리
    - 음성 시작/끝 즉시 감지
    - 온디맨드 모델 로드
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 10,
        threshold: float = 0.5,
        min_speech_ms: int = 100,
        min_silence_ms: int = 300,
        padding_ms: int = 100,
    ):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_ms / 1000)  # 160 samples @ 16kHz
        self.threshold = threshold
        self.min_speech_frames = min_speech_ms // frame_ms
        self.min_silence_frames = min_silence_ms // frame_ms
        self.padding_frames = padding_ms // frame_ms

        self._model = None
        self._init_model()

        # 상태
        self._speech_frames = 0
        self._silence_frames = 0
        self._triggered = False
        self._buffer = deque(maxlen=self.padding_frames)
        self._speech_buffer = []

    def _init_model(self):
        """Silero VAD 모델 지연 로드"""
        try:
            import torch

            self._model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self._model.eval()
            logger.info("Silero VAD 모델 로드 완료")
        except Exception as e:
            logger.warning(f"Silero VAD 로드 실패, 에너지 기반 폴백: {e}")
            self._model = None

    def process_frame(
        self, audio_frame: np.ndarray
    ) -> Tuple[bool, bool, Optional[np.ndarray]]:
        """
        단일 프레임 처리
        Returns: (is_speech, segment_ended, completed_segment_audio)
        """
        if len(audio_frame) != self.frame_size:
            # 리샘플/패딩
            if len(audio_frame) < self.frame_size:
                audio_frame = np.pad(
                    audio_frame, (0, self.frame_size - len(audio_frame))
                )
            else:
                audio_frame = audio_frame[: self.frame_size]

        # VAD 추론
        if self._model is not None:
            import torch

            with torch.no_grad():
                tensor = torch.from_numpy(audio_frame).float().unsqueeze(0)
                prob = self._model(tensor, self.sample_rate).item()
            is_speech = prob > self.threshold
        else:
            # 폴백: 에너지 기반
            energy = np.mean(np.abs(audio_frame))
            is_speech = energy > 0.01

        # 상태 머신
        self._buffer.append(audio_frame.copy())

        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
            self._speech_buffer.append(audio_frame)

            if not self._triggered and self._speech_frames >= self.min_speech_frames:
                self._triggered = True
                # 패딩 포함해서 반환
                segment = np.concatenate(list(self._buffer) + self._speech_buffer)
                return True, False, segment

            if self._triggered:
                return True, False, None
        else:
            self._silence_frames += 1
            if self._triggered:
                self._speech_buffer.append(audio_frame)
                if self._silence_frames >= self.min_silence_frames:
                    # 세그먼트 완료
                    segment = np.concatenate(self._speech_buffer)
                    self._reset()
                    return False, True, segment

        return self._triggered, False, None

    def _reset(self):
        self._triggered = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._speech_buffer = []

    def flush(self) -> Optional[np.ndarray]:
        """버퍼에 남은 음성 반환"""
        if self._speech_buffer:
            segment = np.concatenate(self._speech_buffer)
            self._reset()
            return segment
        return None


class FastWhisperSTT:
    """
    초고속 Whisper STT
    - whisper.cpp (C++ 구현) 사용
    - int4/int8 양자화
    - 스트리밍/부분 결과 지원
    - 모델 크기: tiny(39M) > base(74M) > small(244M)
    """

    def __init__(
        self,
        model_size: str = "tiny",  # tiny, base, small
        device: str = "cpu",
        compute_type: str = "int8",  # int8, int4, float16
        num_workers: int = 2,
        beam_size: int = 1,  # 빔 서치 1로 속도 우선
        vad_filter: bool = True,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.num_workers = num_workers
        self.beam_size = beam_size
        self.vad_filter = vad_filter

        self._model = None
        self._init_model()

        # 스트리밍 상태
        self._audio_buffer = np.array([], dtype=np.float32)
        self._last_partial = ""
        self._partial_callback: Optional[Callable[[str], None]] = None

    def _init_model(self):
        """faster-whisper (whisper.cpp 기반) 초기화"""
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                num_workers=self.num_workers,
            )
            logger.info(
                f"Fast Whisper 로드: {self.model_size} ({self.device}, {self.compute_type})"
            )
        except Exception as e:
            logger.error(f"Fast Whisper 초기화 실패: {e}")
            raise

    def set_partial_callback(self, callback: Callable[[str], None]):
        """부분 결과 콜백 설정 (실시간 자막용)"""
        self._partial_callback = callback

    def transcribe_streaming(
        self,
        audio_chunk: np.ndarray,
        is_final: bool = False,
    ) -> Tuple[str, bool, float]:
        """
        스트리밍 전사
        Returns: (text, is_final, confidence)
        """
        # 오디오 버퍼에 추가
        self._audio_buffer = np.concatenate(
            [self._audio_buffer, audio_chunk.astype(np.float32)]
        )

        # 최소 길이 체크 (0.5초)
        min_samples = 16000 * 0.5
        if len(self._audio_buffer) < min_samples and not is_final:
            return "", False, 0.0

        # 추론 실행
        start = time.perf_counter()
        segments, info = self._model.transcribe(
            self._audio_buffer,
            language="ko",
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
            word_timestamps=False,
            condition_on_previous_text=False,
        )

        texts = []
        probs = []
        for seg in segments:
            texts.append(seg.text.strip())
            probs.append(np.exp(seg.avg_logprob))

        full_text = " ".join(texts)
        avg_conf = sum(probs) / len(probs) if probs else 0.0

        inference_ms = (time.perf_counter() - start) * 1000

        # 부분 결과 콜백
        if full_text != self._last_partial and self._partial_callback:
            self._partial_callback(full_text)
            self._last_partial = full_text

        # 최종이면 버퍼 초기화
        if is_final:
            self._audio_buffer = np.array([], dtype=np.float32)
            self._last_partial = ""
            return full_text, True, min(1.0, avg_conf)

        return full_text, False, min(1.0, avg_conf)

    def transcribe_batch(self, audio: np.ndarray) -> Tuple[str, float]:
        """배치 전사 (기존 호환)"""
        segments, _ = self._model.transcribe(
            audio,
            language="ko",
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
        )
        texts = [seg.text.strip() for seg in segments]
        probs = [np.exp(seg.avg_logprob) for seg in segments]
        return " ".join(texts), min(1.0, sum(probs) / len(probs)) if probs else 0.0


class CommandCache:
    """
    명령어 캐시 - 자주 쓰는 명령 즉시 매핑
    - STT/NLU 완전 우회
    - 웨이크 워드 + 키워드만으로 즉시 실행
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._build_default_cache()

    def _build_default_cache(self):
        """기본 비상/자주 쓰는 명령 캐싱"""
        self._cache = {
            # 비상 (최우선)
            "비상정지": {"action": "ESTOP", "priority": 0, "target": "*", "params": {}},
            "긴급정지": {"action": "ESTOP", "priority": 0, "target": "*", "params": {}},
            "즉시정지": {"action": "ESTOP", "priority": 0, "target": "*", "params": {}},
            "올스톱": {"action": "ESTOP", "priority": 0, "target": "*", "params": {}},
            "비상착륙": {
                "action": "LAND",
                "priority": 0,
                "target": "drone_1",
                "params": {},
            },
            "즉시착륙": {
                "action": "LAND",
                "priority": 0,
                "target": "drone_1",
                "params": {},
            },
            # 기본 제어
            "이륙": {
                "action": "TAKEOFF",
                "priority": 2,
                "target": "drone_1",
                "params": {"z_m": 3.0},
            },
            "착륙": {
                "action": "LAND",
                "priority": 2,
                "target": "drone_1",
                "params": {},
            },
            "복귀": {"action": "RTL", "priority": 2, "target": "drone_1", "params": {}},
            "홀드": {"action": "HOLD", "priority": 2, "target": "*", "params": {}},
            "정지": {"action": "HOLD", "priority": 2, "target": "*", "params": {}},
            "멈춰": {"action": "HOLD", "priority": 2, "target": "*", "params": {}},
            # 이동
            "전진": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vx_mps": 2.0},
            },
            "앞으로": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vx_mps": 2.0},
            },
            "후진": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vx_mps": -2.0},
            },
            "뒤로": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vx_mps": -2.0},
            },
            "좌측": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vy_mps": 2.0},
            },
            "왼쪽": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vy_mps": 2.0},
            },
            "우측": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vy_mps": -2.0},
            },
            "오른쪽": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vy_mps": -2.0},
            },
            "상승": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vz_mps": 1.0},
            },
            "올라": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vz_mps": 1.0},
            },
            "하강": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vz_mps": -1.0},
            },
            "내려": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"vz_mps": -1.0},
            },
            "좌회전": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"yaw_rate_radps": 0.5},
            },
            "우회전": {
                "action": "MOVE_VEL",
                "priority": 2,
                "target": "drone_1",
                "params": {"yaw_rate_radps": -0.5},
            },
            # 하이브리드
            "다이브": {
                "action": "DIVE_ATTACK",
                "priority": 2,
                "target": "hybrid_drone_1",
                "params": {"target_alt": 100, "angle": 70},
            },
            "기만": {
                "action": "DECEPTION_START",
                "priority": 2,
                "target": "hybrid_drone_1",
                "params": {"pattern": "AUTO", "duration": 30},
            },
            "순항": {
                "action": "SET_MODE",
                "priority": 2,
                "target": "hybrid_drone_1",
                "params": {"mode": "CRUISE"},
            },
            "기동": {
                "action": "SET_MODE",
                "priority": 2,
                "target": "hybrid_drone_1",
                "params": {"mode": "FPV_AGILE"},
            },
        }

    def match(self, text: str) -> Optional[Dict]:
        """캐시 매칭 (부분 매칭 포함)"""
        text = text.strip()

        # 완전 매칭
        if text in self._cache:
            return self._cache[text]

        # 부분 매칭 (키워드 포함)
        for keyword, cmd in self._cache.items():
            if keyword in text:
                return cmd

        return None

    def add(
        self, phrase: str, action: str, target: str, params: Dict, priority: int = 2
    ):
        self._cache[phrase] = {
            "action": action,
            "priority": priority,
            "target": target,
            "params": params,
        }


class PredictiveCommander:
    """
    예측적 명령 실행
    - 컨텍스트 기반 다음 명령 예측
    - 프리페치/프리워밍
    """

    def __init__(self):
        self._transition_probs: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._last_command: Optional[str] = None
        self._command_history: List[str] = []

    def record_command(self, action: str):
        """명령 기록 및 전이 확률 업데이트"""
        if self._last_command:
            self._transition_probs[self._last_command][action] += 1
        self._last_command = action
        self._command_history.append(action)

        # 최근 50개만 유지
        if len(self._command_history) > 50:
            self._command_history.pop(0)

    def predict_next(self, top_k: int = 3) -> List[Tuple[str, float]]:
        """다음 명령 예측"""
        if not self._last_command:
            # 전체 빈도 기반
            freq = defaultdict(int)
            for a in self._command_history:
                freq[a] += 1
            total = sum(freq.values())
            return [
                (a, c / total)
                for a, c in sorted(freq.items(), key=lambda x: -x[1])[:top_k]
            ]

        probs = self._transition_probs[self._last_command]
        total = sum(probs.values())
        if total == 0:
            return []
        return [
            (a, c / total)
            for a, c in sorted(probs.items(), key=lambda x: -x[1])[:top_k]
        ]

    def prewarm(self, action: str):
        """예측된 명령 프리워밍 (모델 캐시, 연결 풀 등)"""
        # TODO: MAVSDK 연결 미리 확인, 모델 워밍업 등
        pass


class UltraLowLatencyPipeline:
    """
    초저지연 음성 명령 파이프라인 (<500ms 목표)
    - 웨이크워드 → VAD → 스트리밍 STT → 캐시/NLU → 중재 → 실행
    - 병렬 처리: STT 중간 결과로 NLU 시작
    - 프로파일링 내장
    """

    def __init__(
        self,
        whisper_model: str = "tiny",
        whisper_device: str = "cpu",
        whisper_compute: str = "int8",
        enable_wake_word: bool = True,
        wake_word_keywords: List[str] = None,
        on_command: Optional[Callable] = None,
        on_partial: Optional[Callable[[str], None]] = None,
        on_timing: Optional[Callable[[Dict], None]] = None,
    ):
        self.on_command = on_command
        self.on_partial = on_partial
        self.on_timing = on_timing

        # 프로파일러
        self.profile = LatencyProfile()
        self._profile_lock = threading.Lock()

        # 컴포넌트 초기화 (지연 로드)
        self._vad: Optional[StreamingVAD] = None
        self._stt: Optional[FastWhisperSTT] = None
        self._cache = CommandCache()
        self._predictor = PredictiveCommander()

        # 설정
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device
        self.whisper_compute = whisper_compute
        self.enable_wake_word = enable_wake_word

        # 웨이크워드
        self._wake_detector = None
        if enable_wake_word:
            self._init_wake_word(wake_word_keywords or ["porcupine"])

        # 상태
        self._running = False
        self._wake_detected = False
        self._vad_active = False
        self._current_segment = np.array([], dtype=np.float32)
        self._active_target = "drone_1"

        # 비동기 루프
        self._loop = None
        self._executor = None

    def _init_wake_word(self, keywords: List[str]):
        try:
            import pvporcupine
            import pyaudio
            import os

            access_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if not access_key:
                logger.warning("PICOVOICE_ACCESS_KEY 없음, 웨이크워드 비활성화")
                self.enable_wake_word = False
                return

            self._wake_detector = pvporcupine.create(
                access_key=access_key,
                keywords=keywords,
                sensitivities=[0.5] * len(keywords),
            )
            self._pa = pyaudio.PyAudio()
            self._wake_stream = self._pa.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._wake_detector.frame_length,
            )
            logger.info(f"웨이크워드 감지기 시작: {keywords}")
        except Exception as e:
            logger.error(f"웨이크워드 초기화 실패: {e}")
            self.enable_wake_word = False

    def start(self):
        """파이프라인 시작"""
        if self._running:
            return

        self._running = True
        self._vad = StreamingVAD()

        # STT 모델 로드 (백그라운드)
        def load_stt():
            self._stt = FastWhisperSTT(
                model_size=self.whisper_model,
                device=self.whisper_device,
                compute_type=self.whisper_compute,
            )
            self._stt.set_partial_callback(self._on_stt_partial)

        threading.Thread(target=load_stt, daemon=True).start()

        logger.info("초저지연 파이프라인 시작됨")

    def stop(self):
        self._running = False
        if self.enable_wake_word and self._wake_detector:
            self._wake_stream.stop_stream()
            self._wake_stream.close()
            self._pa.terminate()
            self._wake_detector.delete()
        logger.info("파이프라인 중지됨")

    def _on_stt_partial(self, text: str):
        """STT 부분 결과 콜백 (실시간 자막 + 예측적 NLU)"""
        if self.on_partial:
            self.on_partial(text)

        # 부분 결과로 캐시 매칭 시도 (빠른 경로)
        if len(text) > 2:
            cached = self._cache.match(text)
            if cached and cached["priority"] == 0:  # 비상 명령
                self._execute_cached(cached, text, 1.0, is_emergency=True)

    def process_audio(self, audio_chunk: np.ndarray) -> Optional[Dict]:
        """
        오디오 청크 처리 (메인 루프에서 호출)
        Returns: 실행된 명령 정보 또는 None
        """
        if not self._running:
            return None

        # 웨이크워드 처리
        if self.enable_wake_word and self._wake_detector and not self._wake_detected:
            try:
                pcm = self._wake_stream.read(
                    self._wake_detector.frame_length, exception_on_overflow=False
                )
                pcm = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
                keyword_idx = self._wake_detector.process(pcm)
                if keyword_idx >= 0:
                    self._wake_detected = True
                    self.profile.mark(PipelineStage.WAKE_WORD)
                    self._vad_active = True
                    logger.info("웨이크워드 감지!")
            except Exception:
                pass
            return None

        if not self._wake_detected and self.enable_wake_word:
            return None

        # VAD 처리
        if self._vad_active:
            is_speech, segment_ended, segment_audio = self._vad.process_frame(
                audio_chunk
            )

            if is_speech and not segment_ended:
                # 음성 진행 중 - STT 스트리밍
                if self._stt:
                    self.profile.mark(PipelineStage.STT_START)
                    text, is_final, conf = self._stt.transcribe_streaming(
                        audio_chunk, is_final=False
                    )
                    if is_final:
                        self.profile.mark(PipelineStage.STT_FINAL)

            if segment_ended and segment_audio is not None:
                # 발화 완료 - 최종 STT + NLU
                self.profile.mark(PipelineStage.VAD_END)
                return self._process_final_utterance(segment_audio)

        return None

    def _process_final_utterance(self, audio: np.ndarray) -> Dict:
        """최종 발화 처리 (STT + NLU + 실행)"""
        self.profile.mark(PipelineStage.STT_START)

        # STT 최종 결과
        if self._stt:
            text, _, confidence = self._stt.transcribe_streaming(audio, is_final=True)
        else:
            text, confidence = "", 0.0

        self.profile.mark(PipelineStage.STT_FINAL)

        if not text or confidence < 0.3:
            self._reset_utterance()
            return {"status": "low_confidence", "text": text}

        self.profile.mark(PipelineStage.NLU_START)

        # 1. 캐시 매칭 (최우선, <5ms)
        cached = self._cache.match(text)
        if cached:
            self.profile.mark(PipelineStage.NLU_END)
            self._execute_cached(cached, text, confidence)
            return {"status": "cached", "text": text, "command": cached}

        # 2. 규칙 기반 NLU (빠른 경로, <10ms)
        rule_cmd = self._rule_based_nlu(text)
        if rule_cmd:
            self.profile.mark(PipelineStage.NLU_END)
            self._execute_command(rule_cmd, text, confidence)
            return {"status": "rule", "text": text, "command": rule_cmd}

        # 3. LLM NLU (필요시만)
        # self.profile.mark(PipelineStage.NLU_END)
        # llm_cmd = await self._llm_nlu(text)
        # self._execute_command(llm_cmd, text, confidence)

        self.profile.mark(PipelineStage.NLU_END)
        self._reset_utterance()
        return {"status": "unrecognized", "text": text}

    def _rule_based_nlu(self, text: str) -> Optional[Dict]:
        """규칙 기반 빠른 NLU (키워드 + 숫자 추출)"""
        import re

        text = text.strip()

        # 타겟 결정
        target = self._active_target
        if "하이브리드" in text:
            target = "hybrid_drone_1"
        elif "드론" in text:
            target = "drone_1"
        elif "로봇" in text:
            target = "robot_1"

        # 숫자 추출
        nums = re.findall(r"(\d+(?:\.\d+)?)", text)
        vals = [float(n) for n in nums] if nums else []

        # 패턴 매칭
        if "이륙" in text:
            return {
                "action": "TAKEOFF",
                "target": target,
                "params": {"z_m": vals[0] if vals else 3.0},
            }
        if "착륙" in text and "비상" not in text and "즉시" not in text:
            return {"action": "LAND", "target": target, "params": {}}
        if "복귀" in text or "돌아와" in text:
            return {"action": "RTL", "target": target, "params": {}}
        if "홀드" in text or "정지" in text or "멈춰" in text:
            return {"action": "HOLD", "target": target, "params": {}}
        if "전진" in text or "앞으로" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"vx_mps": vals[0] if vals else 2.0},
            }
        if "후진" in text or "뒤로" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"vx_mps": -(vals[0] if vals else 2.0)},
            }
        if "좌측" in text or "왼쪽" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"vy_mps": vals[0] if vals else 1.0},
            }
        if "우측" in text or "오른쪽" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"vy_mps": -(vals[0] if vals else 1.0)},
            }
        if "상승" in text or "올라" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"vz_mps": vals[0] if vals else 1.0},
            }
        if "하강" in text or "내려" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"vz_mps": -(vals[0] if vals else 1.0)},
            }
        if "좌회전" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"yaw_rate_radps": 0.5},
            }
        if "우회전" in text:
            return {
                "action": "MOVE_VEL",
                "target": target,
                "params": {"yaw_rate_radps": -0.5},
            }

        # 하이브리드 전용
        if target == "hybrid_drone_1":
            if "다이브" in text and (
                "어택" in text or "공격" in text or "시작" in text
            ):
                return {
                    "action": "DIVE_ATTACK",
                    "target": target,
                    "params": {
                        "target_alt": vals[0] if vals else 100,
                        "angle": vals[1] if len(vals) > 1 else 70,
                    },
                }
            if "기만" in text and ("시작" in text or "켜" in text):
                pattern = "AUTO"
                if "나선" in text:
                    pattern = "SPIRAL_DIVE"
                elif "사인" in text:
                    pattern = "SINE_DIVE"
                elif "랜덤" in text:
                    pattern = "RANDOM_JINK"
                elif "추락" in text:
                    pattern = "FAKE_CRASH"
                elif "멀티" in text:
                    pattern = "MULTI_PULSE"
                return {
                    "action": "DECEPTION_START",
                    "target": target,
                    "params": {"pattern": pattern, "duration": vals[0] if vals else 30},
                }
            if "순항" in text:
                return {
                    "action": "SET_MODE",
                    "target": target,
                    "params": {"mode": "CRUISE"},
                }
            if "기동" in text or "FPV" in text:
                return {
                    "action": "SET_MODE",
                    "target": target,
                    "params": {"mode": "FPV_AGILE"},
                }

        return None

    def _execute_cached(
        self, cached: Dict, text: str, confidence: float, is_emergency: bool = False
    ):
        """캐시된 명령 즉시 실행"""
        self.profile.mark(PipelineStage.ARBITRATE)
        self.profile.mark(PipelineStage.DISPATCH)

        cmd = {
            "action": cached["action"],
            "target": (
                cached["target"] if cached["target"] != "*" else self._active_target
            ),
            "params": cached["params"],
            "priority": cached["priority"],
            "source": "FAILSAFE" if is_emergency else "VOICE_NLU",
            "text": text,
            "confidence": confidence,
        }

        self._predictor.record_command(cached["action"])

        self.profile.mark(PipelineStage.EXECUTE)

        if self.on_command:
            self.on_command(cmd)

        self._emit_timing()
        self._reset_utterance()

    def _execute_command(self, cmd: Dict, text: str, confidence: float):
        self.profile.mark(PipelineStage.ARBITRATE)
        self.profile.mark(PipelineStage.DISPATCH)

        full_cmd = {
            "action": cmd["action"],
            "target": cmd["target"],
            "params": cmd["params"],
            "priority": 2,
            "source": "VOICE_NLU",
            "text": text,
            "confidence": confidence,
        }

        self._predictor.record_command(cmd["action"])

        self.profile.mark(PipelineStage.EXECUTE)

        if self.on_command:
            self.on_command(full_cmd)

        self._emit_timing()
        self._reset_utterance()

    def _reset_utterance(self):
        self._wake_detected = False
        self._vad_active = False
        if self._vad:
            self._vad._reset()
        if self._stt:
            self._stt._audio_buffer = np.array([], dtype=np.float32)
            self._stt._last_partial = ""
        self.profile = LatencyProfile()

    def _emit_timing(self):
        if self.on_timing:
            self.on_timing(self.profile.summary())

        # 로그 출력
        summary = self.profile.summary()
        logger.info(
            f"지연시간: {summary.get('total', 0):.1f}ms "
            f"(VAD: {summary.get('vad_start->vad_end', 0):.1f}ms, "
            f"STT: {summary.get('stt_start->stt_final', 0):.1f}ms, "
            f"NLU: {summary.get('nlu_start->nlu_end', 0):.1f}ms, "
            f"실행: {summary.get('dispatch->execute', 0):.1f}ms)"
        )

    def set_active_target(self, target: str):
        self._active_target = target

    def add_custom_command(
        self, phrase: str, action: str, target: str, params: Dict, priority: int = 2
    ):
        self._cache.add(phrase, action, target, params, priority)

    def get_stats(self) -> Dict:
        return {
            "running": self._running,
            "wake_word": self.enable_wake_word,
            "stt_loaded": self._stt is not None,
            "model": self.whisper_model,
            "cache_size": len(self._cache._cache),
        }


# 편의 함수
def create_ultra_low_latency_pipeline(
    model: str = "tiny", device: str = "cpu", compute: str = "int8", **kwargs
) -> UltraLowLatencyPipeline:
    return UltraLowLatencyPipeline(
        whisper_model=model, whisper_device=device, whisper_compute=compute, **kwargs
    )


# 사용 예시
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_cmd(cmd):
        print(f"[실행] {cmd['action']} -> {cmd['target']} | params: {cmd['params']}")

    def on_partial(text):
        print(f"[부분인식] {text}")

    def on_timing(timing):
        print(f"[타이밍] 총 {timing.get('total', 0):.1f}ms")

    pipeline = create_ultra_low_latency_pipeline(
        model="tiny",  # 가장 빠름 (39MB)
        device="cpu",
        compute="int8",
        enable_wake_word=False,  # 키 필요
        on_command=on_cmd,
        on_partial=on_partial,
        on_timing=on_timing,
    )

    # 커스텀 명령 추가
    pipeline.add_custom_command("내드론이륙", "TAKEOFF", "drone_1", {"z_m": 5.0})

    pipeline.start()
    print("파이프라인 시작 (테스트용 - 실제 오디오 입력 필요)")

    # 시뮬레이션: 1초 무음 + "이륙" + 1초 무음
    import numpy as np

    silence = np.zeros(16000, dtype=np.float32)  # 1초
    speech = np.random.randn(16000).astype(np.float32) * 0.1  # 가짜 음성

    for chunk in [silence, speech, silence]:
        for i in range(0, len(chunk), 160):  # 10ms 프레임
            result = pipeline.process_audio(chunk[i : i + 160])
            if result:
                print(f"결과: {result}")

    pipeline.stop()
