"""
KWS Runtime - 키워드 스팟팅 실시간 추론 및 MAVLink 명령 변환
TFLite INT8 모델로 10ms 프레임 처리, <5ms 지연
"""
import numpy as np
import librosa
import tflite_runtime.interpreter as tflite
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from collections import deque

from voice.keyword_specs import (
    get_keywords_list,
    get_command_for_keyword,
    get_phrases_for_keyword,
    KEYWORD_SPECS,
    CommandPriority
)


@dataclass
class KWSResult:
    """KWS 추론 결과"""
    keyword: str
    confidence: float
    command: Optional[Dict]
    timestamp: float
    all_probs: Optional[Dict[str, float]] = None


class MFCCExtractor:
    """실시간 MFCC 특징 추출기 (스트리밍 최적화)"""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        n_mfcc: int = 13,
        n_fft: int = 480,
        hop_length: int = 160,
        n_frames: int = 200
    ):
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_frames = n_frames
        
        # 멜 필터뱅크 사전 계산
        self.mel_basis = librosa.filters.mel(
            sr=sample_rate, n_fft=n_fft, n_mels=40
        )
        
        # DCT 행렬 사전 계산 (MFCC용)
        self.dct_matrix = self._create_dct_matrix(n_mfcc, 40)
        
        # 윈도우 함수
        self.window = np.hanning(n_fft)
        
        # 링버퍼 (오디오)
        self.audio_buffer = np.zeros(n_fft, dtype=np.float32)
        self.buffer_pos = 0
        
        # MFCC 프레임 버퍼 (슬라이딩 윈도우)
        self.mfcc_buffer = np.zeros((n_frames, n_mfcc), dtype=np.float32)
        self.mfcc_count = 0
    
    def _create_dct_matrix(self, n_mfcc: int, n_mels: int) -> np.ndarray:
        """DCT-II 행렬 생성 (MFCC 계산용)"""
        n = np.arange(n_mels)
        k = np.arange(n_mfcc).reshape(-1, 1)
        dct = np.cos(np.pi / n_mels * (n + 0.5) * k)
        dct[0, :] *= np.sqrt(1.0 / n_mels)
        dct[1:, :] *= np.sqrt(2.0 / n_mels)
        return dct.astype(np.float32)
    
    def process_frame(self, audio_10ms: np.ndarray) -> np.ndarray:
        """
        10ms 오디오 프레임 → MFCC 1프레임 (13차원)
        전체 지연: ~0.5ms
        """
        # 1. 링버퍼에 오디오 추가
        frame_len = len(audio_10ms)
        if frame_len != self.hop_length:
            # 리샘플/패딩
            if frame_len < self.hop_length:
                audio_10ms = np.pad(audio_10ms, (0, self.hop_length - frame_len))
            else:
                audio_10ms = audio_10ms[:self.hop_length]
        
        # 링버퍼 업데이트
        end_pos = self.buffer_pos + frame_len
        if end_pos <= self.n_fft:
            self.audio_buffer[self.buffer_pos:end_pos] = audio_10ms
        else:
            # 순환
            first_part = self.n_fft - self.buffer_pos
            self.audio_buffer[self.buffer_pos:] = audio_10ms[:first_part]
            remaining = frame_len - first_part
            self.audio_buffer[:remaining] = audio_10ms[first_part:]
        
        self.buffer_pos = (self.buffer_pos + frame_len) % self.n_fft
        
        # 2. 충분한 데이터가 모였을 때만 MFCC 계산 (30ms 윈도우 필요)
        if self.mfcc_count < 3:  # 처음 3프레임은 0 패딩
            mfcc_frame = np.zeros(self.n_mfcc, dtype=np.float32)
        else:
            # 30ms 윈도우 추출 (마지막 n_fft 샘플)
            windowed = self._get_windowed_frame()
            
            # FFT → 멜 스펙트로그램 → 로그 → DCT
            stft = np.fft.rfft(windowed)
            power_spec = np.abs(stft) ** 2
            mel_spec = np.dot(self.mel_basis, power_spec)
            log_mel = np.log(mel_spec + 1e-10)
            mfcc_frame = np.dot(self.dct_matrix, log_mel).astype(np.float32)
        
        # 3. MFCC 버퍼 업데이트 (슬라이딩 윈도우)
        self.mfcc_buffer = np.roll(self.mfcc_buffer, shift=-1, axis=0)
        self.mfcc_buffer[-1] = mfcc_frame
        self.mfcc_count += 1
        
        return mfcc_frame
    
    def _get_windowed_frame(self) -> np.ndarray:
        """현재 위치에서 30ms 윈도우 추출"""
        start = (self.buffer_pos - self.n_fft) % self.n_fft
        if start + self.n_fft <= self.n_fft:
            frame = self.audio_buffer[start:start + self.n_fft].copy()
        else:
            frame = np.concatenate([
                self.audio_buffer[start:],
                self.audio_buffer[:self.n_fft - (self.n_fft - start)]
            ])
        return frame * self.window
    
    def get_input_tensor(self) -> np.ndarray:
        """모델 입력 텐서 생성 (1, 200, 13, 1)"""
        # MFCC 버퍼가 충분히 찼으면 그대로, 아니면 0 패딩
        if self.mfcc_count >= self.n_frames:
            tensor = self.mfcc_buffer.copy()
        else:
            tensor = np.zeros((self.n_frames, self.n_mfcc), dtype=np.float32)
            if self.mfcc_count > 0:
                tensor[-self.mfcc_count:] = self.mfcc_buffer[-self.mfcc_count:]
        
        # (1, 200, 13, 1) 형태로 리셰이프
        return tensor[np.newaxis, ..., np.newaxis].astype(np.float32)
    
    def reset(self):
        """버퍼 초기화"""
        self.audio_buffer.fill(0)
        self.buffer_pos = 0
        self.mfcc_buffer.fill(0)
        self.mfcc_count = 0


class KWSRuntime:
    """
    KWS 실시간 추론 런타임
    - 10ms마다 MFCC 추출 + TFLite 추론
    - 시간 평활화로 안정성 확보
    - 명령 즉시 변환
    """
    
    def __init__(
        self,
        model_path: str,
        labels_path: str,
        specs_path: Optional[str] = None,
        threshold_override: Optional[Dict[str, float]] = None,
        smoothing_frames: int = 3
    ):
        # TFLite 인터프리터
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # 입력/출력 양자화 파라미터
        self.input_quant = self.input_details[0].get('quantization', (1.0, 0))
        self.output_quant = self.output_details[0].get('quantization', (1.0, 0))
        
        # 라벨
        with open(labels_path, 'r', encoding='utf-8') as f:
            self.idx_to_label = json.load(f)
        
        # 명령 스펙
        if specs_path and Path(specs_path).exists():
            with open(specs_path, 'r', encoding='utf-8') as f:
                self.specs = json.load(f)
        else:
            self.specs = [s.to_dict() for s in KEYWORD_SPECS]
        
        self.command_map = {s['keyword']: s for s in self.specs}
        
        # 컴포넌트
        self.mfcc_extractor = MFCCExtractor()
        
        # 임계값 (키워드별 조정)
        self.thresholds = {cmd: 0.85 for cmd in self.command_map}
        self.thresholds.update({
            'emergency_stop': 0.75,
            'land_now': 0.75,
            'kill_switch': 0.70,
        })
        if threshold_override:
            self.thresholds.update(threshold_override)
        
        # 시간 평활화 버퍼
        self.smoothing_frames = smoothing_frames
        self.prob_buffer = deque(maxlen=smoothing_frames)
        
        # 상태
        self.last_detection_time = 0
        self.detection_cooldown = 0.5  # 500ms 쿨다운
        
        # 통계
        self.stats = {
            "total_inferences": 0,
            "detections": 0,
            "by_keyword": {},
            "avg_inference_ms": 0.0
        }
        
        print(f"KWS 런타임 초기화 완료:")
        print(f"  모델: {model_path}")
        print(f"  클래스: {len(self.idx_to_label)}개")
        print(f"  입력 양자화: {self.input_quant}")
        print(f"  출력 양자화: {self.output_quant}")
        print(f"  평활화: {smoothing_frames}프레임")
    
    def process_audio_frame(self, audio_10ms: np.ndarray) -> Optional[KWSResult]:
        """
        10ms 오디오 프레임 처리 → KWS 결과
        전체 지연: MFCC 0.5ms + 추론 1-2ms + 후처리 0.5ms = ~2-3ms
        """
        import time
        start_time = time.perf_counter()
        
        # 1. MFCC 추출
        self.mfcc_extractor.process_frame(audio_10ms)
        
        # 2. 입력 텐서 준비
        input_tensor = self.mfcc_extractor.get_input_tensor()
        
        # 3. 입력 양자화 (INT8 모델인 경우)
        if self.input_details[0]['dtype'] == np.int8:
            scale, zero_point = self._get_quant_params(self.input_quant)
            input_tensor = (input_tensor / scale + zero_point).astype(np.int8)
        
        # 3. TFLite 추론
        self.interpreter.set_tensor(self.input_details[0]['index'], input_tensor)
        self.interpreter.invoke()
        
        # 4. 출력 디퀀타이즈
        output = self.interpreter.get_tensor(self.output_details[0]['index'])
        if self.output_details[0]['dtype'] == np.int8:
            scale, zero_point = self._get_quant_params(self.output_quant)
            output = (output.astype(np.float32) - zero_point) * scale
        
        logits = output[0]
        probs = self._softmax(logits)
        
        # 5. 시간 평활화
        self.prob_buffer.append(probs)
        avg_probs = np.mean(self.prob_buffer, axis=0)
        
        # 6. 최대 확률 클래스
        max_idx = np.argmax(avg_probs)
        confidence = avg_probs[max_idx]
        keyword = self.idx_to_label.get(str(max_idx), "unknown")
        
        # 6. 임계값 체크
        threshold = self.thresholds.get(keyword, 0.85)
        
        # 쿨다운 체크
        current_time = time.time()
        in_cooldown = (current_time - self.last_detection_time) < self.detection_cooldown
        
        result = None
        if confidence >= threshold and not in_cooldown:
            command = self.command_map.get(keyword)
            if command:
                result = KWSResult(
                    keyword=keyword,
                    confidence=float(confidence),
                    command={
                        "keyword": keyword,
                        "action": command['mavlink_action'],
                        "params": command['params'],
                        "priority": command['priority'],
                        "target": command['target'],
                    },
                    timestamp=time.time(),
                    all_probs={self.idx_to_label.get(str(i), f"cls_{i}"): float(p) 
                              for i, p in enumerate(avg_probs)}
                )
                
                # 상태 업데이트
                self.last_detection_time = current_time
                self.stats["detections"] += 1
                self.stats["by_keyword"][keyword] = self.stats["by_keyword"].get(keyword, 0) + 1
        
        # 통계
        inference_ms = (time.perf_counter() - start_time) * 1000
        self.stats["total_inferences"] += 1
        self.stats["avg_inference_ms"] = (
            (self.stats["avg_inference_ms"] * (self.stats["total_inferences"] - 1) + inference_ms) 
            / self.stats["total_inferences"]
        )
        
        return result
    
    def _get_quant_params(self, quant) -> Tuple[float, int]:
        """양자화 파라미터 안전하게 추출"""
        if isinstance(quant, tuple) and len(quant) == 2:
            return quant
        return 1.0, 0
    
    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x))
        return e / e.sum()
    
    def process_audio_stream(
        self,
        audio_generator,
        callback: Optional[callable] = None
    ):
        """
        오디오 스트림 연속 처리 (제너레이터 기반)
        """
        for audio_frame in audio_generator:
            result = self.process_audio_frame(audio_frame)
            if result and callback:
                callback(result)
            if result:
                print(f"[KWS] {result.keyword} ({result.confidence:.3f}) → {result.command['action']}")
    
    def get_stats(self) -> Dict:
        return self.stats.copy()
    
    def reset(self):
        self.mfcc_extractor.reset()
        self.prob_buffer.clear()
        self.last_detection_time = 0


# === 편의 함수 ===

def create_kws_runtime(
    model_dir: str = "~/models/kws",
    threshold_override: Optional[Dict[str, float]] = None
) -> KWSRuntime:
    """KWS 런타임 생성 (기본 경로 사용)"""
    model_dir = Path(model_dir).expanduser()
    
    model_path = model_dir / "kws_model_int8.tflite"
    labels_path = model_dir / "labels.json"
    specs_path = model_dir / "specs.json"
    
    if not model_path.exists():
        raise FileNotFoundError(f"모델 파일 없음: {model_path}")
    
    return KWSRuntime(
        model_path=str(model_path),
        labels_path=str(labels_path),
        specs_path=str(specs_path) if specs_path.exists() else None,
        threshold_override=threshold_override
    )


def test_kws_runtime():
    """테스트용 더미 오디오로 추론 속도 측정"""
    runtime = create_kws_runtime()
    
    print("KWS 런타임 테스트 시작...")
    
    # 더미 오디오 생성 (10ms * 100 = 1초)
    for i in range(100):
        # 실제로는 마이크에서 읽음
        dummy_audio = np.random.randn(160).astype(np.float32) * 0.01
        
        result = runtime.process_audio_frame(dummy_audio)
        
        if result:
            print(f"감지: {result.keyword} ({result.confidence:.3f})")
    
    stats = runtime.get_stats()
    print(f"\n통계: {stats}")


if __name__ == "__main__":
    import json
    import time
    
    test_kws_runtime()