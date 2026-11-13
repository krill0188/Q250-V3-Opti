#!/usr/bin/env python3
"""
faster-whisper + Silero VAD 실시간 음성인식 파이프라인
T-11 SpecKit 작업 구현
"""

import asyncio
import numpy as np
import torch
import logging
from typing import Optional, Callable, AsyncGenerator
from dataclasses import dataclass
from collections import deque
import time

logger = logging.getLogger(__name__)


@dataclass
class ASRConfig:
    """ASR 파이프라인 설정"""

    model_size: str = "base"  # tiny < base < small < medium < large-v3
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type: str = "float16" if torch.cuda.is_available() else "int8"
    language: str = "ko"
    beam_size: int = 5
    vad_threshold: float = 0.5
    min_silence_ms: int = 500
    max_segment_sec: float = 30.0
    sample_rate: int = 16000
    chunk_ms: int = 100  # 100ms 청크


@dataclass
class TranscriptionResult:
    """전사 결과"""

    text: str
    start_time: float
    end_time: float
    confidence: float
    language: str
    is_final: bool


class SileroVAD:
    """Silero VAD 래퍼"""

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            # torch hub에서 Silero VAD 로드
            self.model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self.get_speech_timestamps = utils[0]
            logger.info("Silero VAD loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            self.model = None

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """음성 구간 감지"""
        if self.model is None:
            return True  # VAD 없으면 모두 음성으로 처리

        try:
            # 텐서 변환
            tensor = torch.from_numpy(audio_chunk).float()
            if len(tensor.shape) == 1:
                tensor = tensor.unsqueeze(0)

            # 음성 확률 계산
            speech_prob = self.model(tensor, 16000).item()
            return speech_prob > 0.5
        except Exception:
            return True


class FasterWhisperASR:
    """faster-whisper 기반 실시간 ASR"""

    def __init__(self, config: ASRConfig):
        self.config = config
        self.model = None
        self.vad = SileroVAD(config.vad_threshold, config.sample_rate)
        self._load_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel

            logger.info(
                f"Loading model: {self.config.model_size} on {self.config.device} with {self.config.compute_type}"
            )

            # float16 실패 시 float32로 폴백
            compute_type = self.config.compute_type
            for ct in [compute_type, "float32", "int8"]:
                try:
                    self.model = WhisperModel(
                        self.config.model_size,
                        device=self.config.device,
                        compute_type=ct,
                        download_root=None,
                    )
                    logger.info(
                        f"faster-whisper loaded: {self.config.model_size} on {self.config.device} ({ct})"
                    )
                    break
                except Exception as e:
                    logger.warning(f"Compute type {ct} failed: {e}, trying next...")
                    continue
            else:
                raise RuntimeError("All compute types failed")
        except ImportError:
            logger.error(
                "faster-whisper not installed. Run: pip install faster-whisper"
            )
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load faster-whisper: {e}")
            self.model = None

    def transcribe_chunk(self, audio: np.ndarray) -> list[TranscriptionResult]:
        """오디오 청크 전사"""
        if self.model is None:
            return []

        try:
            # VAD로 음성 구간만 추출
            speech_chunks = self.vad.get_speech_timestamps(
                audio, self.vad.model, sampling_rate=16000
            )

            results = []
            for chunk in speech_chunks:
                start = chunk["start"] / 16000
                end = chunk["end"] / 16000
                segment = audio[chunk["start"] : chunk["end"]]

                if len(segment) < 1600:  # 0.1초 미만 무시
                    continue

                segments, info = self.model.transcribe(
                    segment,
                    language=self.config.language,
                    beam_size=self.config.beam_size,
                    vad_filter=False,  # 이미 VAD 적용함
                    word_timestamps=True,
                )

                for seg in segments:
                    results.append(
                        TranscriptionResult(
                            text=seg.text.strip(),
                            start_time=start + seg.start,
                            end_time=start + seg.end,
                            confidence=seg.avg_logprob,
                            language=info.language,
                            is_final=True,
                        )
                    )

            return results
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return []


class StreamingASRPipeline:
    """실시간 스트리밍 ASR 파이프라인"""

    def __init__(self, config: ASRConfig):
        self.config = config
        self.asr = FasterWhisperASR(config)
        self.audio_buffer = deque(maxlen=int(config.max_segment_sec * 16000))
        self.silence_buffer = deque(maxlen=int(config.min_silence_ms * 16))
        self.is_speaking = False
        self.last_speech_time = 0
        self.callback: Optional[Callable[[TranscriptionResult], None]] = None

    def set_callback(self, callback: Callable[[TranscriptionResult], None]):
        self.callback = callback

    def process_audio(self, audio_chunk: np.ndarray) -> list[TranscriptionResult]:
        """오디오 청크 처리 (100ms 단위 권장)"""
        # 버퍼에 추가
        self.audio_buffer.extend(audio_chunk)

        # VAD로 음성 감지
        is_speech = self.asr.vad.is_speech(audio_chunk)
        current_time = time.time()

        results = []

        if is_speech:
            self.is_speaking = True
            self.last_speech_time = current_time
            self.silence_buffer.clear()
        else:
            self.silence_buffer.extend(audio_chunk)

            # 무음 지속 시간 체크
            silence_duration = len(self.silence_buffer) / 16000
            if self.is_speaking and silence_duration >= (
                self.config.min_silence_ms / 1000
            ):
                # 발화 종료 - 버퍼 전체 전사
                audio_data = np.array(self.audio_buffer)
                if len(audio_data) > 1600:
                    results = self.asr.transcribe_chunk(audio_data)
                    if results and self.callback:
                        for r in results:
                            self.callback(r)

                # 버퍼 초기화
                self.audio_buffer.clear()
                self.silence_buffer.clear()
                self.is_speaking = False

        # 최대 세그먼트 길이 체크
        if len(self.audio_buffer) >= self.config.max_segment_sec * 16000:
            audio_data = np.array(self.audio_buffer)
            results = self.asr.transcribe_chunk(audio_data)
            if results and self.callback:
                for r in results:
                    self.callback(r)
            self.audio_buffer.clear()
            self.is_speaking = False

        return results

    async def run_stream(
        self, audio_queue: asyncio.Queue
    ) -> AsyncGenerator[TranscriptionResult, None]:
        """비동기 스트림 처리"""
        while True:
            try:
                audio_chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.1)
                results = self.process_audio(audio_chunk)
                for r in results:
                    yield r
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Stream error: {e}")


class AudioCapture:
    """마이크 오디오 캡처"""

    def __init__(self, sample_rate: int = 16000, chunk_ms: int = 100):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_ms / 1000)
        self.stream = None
        self.running = False
        self.audio_queue = asyncio.Queue()
        self._loop = None

    def start(self):
        import sounddevice as sd

        self._loop = asyncio.get_event_loop()
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_size,
            callback=self._callback,
        )
        self.stream.start()
        self.running = True
        logger.info("Audio capture started")

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.running = False
            logger.info("Audio capture stopped")

    def _callback(self, indata, frames, time, status):
        if status:
            logger.warning(f"Audio status: {status}")
        # 오디오 데이터를 비동기 큐에 넣기
        if self._loop and self.running:
            audio_data = indata[:, 0].copy()  # 모노 채널
            self._loop.call_soon_threadsafe(self.audio_queue.put_nowait, audio_data)

    async def get_audio_chunk(self) -> np.ndarray:
        """오디오 청크 가져오기"""
        return await self.audio_queue.get()


# 사용 예시
async def main():
    logging.basicConfig(level=logging.INFO)

    # 설정 (테스트용 base 모델 사용)
    config = ASRConfig(
        model_size="base",
        device="cuda" if torch.cuda.is_available() else "cpu",
        compute_type="float16" if torch.cuda.is_available() else "int8",
        language="ko",
        vad_threshold=0.5,
    )

    # 파이프라인 생성
    pipeline = StreamingASRPipeline(config)

    # 결과 콜백
    def on_transcription(result: TranscriptionResult):
        print(
            f"[{result.start_time:.1f}-{result.end_time:.1f}] {result.text} (conf: {result.confidence:.2f})"
        )

    pipeline.set_callback(on_transcription)

    # 오디오 캡처
    capture = AudioCapture(chunk_ms=100)
    capture.start()

    try:
        print("Listening... (Ctrl+C to stop)", flush=True)
        while True:
            audio_chunk = await capture.get_audio_chunk()
            pipeline.process_audio(audio_chunk)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        capture.stop()


if __name__ == "__main__":
    asyncio.run(main())
