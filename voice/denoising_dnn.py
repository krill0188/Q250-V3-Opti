"""
3단계: DNN 기반 노이즈 제거 (딥러닝 기반 실시간 노이즈 억제)
- TCN/CRN 기반 실시간 노이즈 억제 모델 인터페이스
- DeepFilterNet3 지원 (48kHz, ERB 스케일 특징)
- ONNX Runtime / TensorRT / TensorFlow Lite 지원
- 실시간 스트리밍 추론 최적화
"""

import numpy as np
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod
import warnings
import struct

try:
    import onnxruntime as ort

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None

# torch는 지연 import (모듈 레벨에서 import 시 numpy 호환성 문제 발생)
TORCH_AVAILABLE = False
torch = None


def _check_torch() -> bool:
    global TORCH_AVAILABLE, torch
    if not TORCH_AVAILABLE:
        try:
            import torch as _torch

            TORCH_AVAILABLE = True
            torch = _torch
        except ImportError:
            pass
    return TORCH_AVAILABLE


@dataclass
class DNNModelConfig:
    """DNN 노이즈 제거 모델 설정"""

    model_path: str
    sample_rate: int = 16000
    frame_size: int = 512  # 프레임 크기 (샘플)
    hop_size: int = 256  # 홉 크기 (샘플)
    n_fft: int = 512  # FFT 크기
    input_channels: int = 1  # 입력 채널 (모노)
    output_channels: int = 1  # 출력 채널 (모노)

    # 모델 아키텍처 파라미터
    model_type: str = "tcn"  # "tcn", "crn", "dprnn", "demucs", "deepfilternet3"
    hidden_size: int = 256
    num_layers: int = 4

    # 런타임 설정
    use_onnx: bool = True  # ONNX Runtime 사용
    providers: list = None  # ONNX 프로바이더 우선순위
    intra_op_threads: int = 1  # 연산자 내 스레드 수
    inter_op_threads: int = 1  # 연산자 간 스레드 수

    # DeepFilterNet3 특화 설정
    erb_bands: int = 32  # ERB 밴드 수
    df_bins: int = 96  # DeepFilter 주파수 빈 수
    df_order: int = 5  # DeepFilter 차수
    conv_lookahead: int = 2  # 컨볼루션 룩어헤드
    df_lookahead: int = 2  # DeepFilter 룩어헤드
    norm_tau: float = 1.0  # 정규화 타우
    normalization_alpha: float = 0.99  # 정규화 알파

    def __post_init__(self):
        if self.providers is None:
            self.providers = ["CPUExecutionProvider"]


class BaseDenoiser(ABC):
    """노이즈 제거기 베이스 클래스"""

    @abstractmethod
    def process(self, audio: np.ndarray) -> np.ndarray:
        """단일 채널 오디오 노이즈 제거"""
        pass

    @abstractmethod
    def process_stream(self, audio_frame: np.ndarray) -> np.ndarray:
        """스트리밍 프레임 단위 처리"""
        pass

    @abstractmethod
    def reset_state(self):
        """내부 상태 초기화"""
        pass

    @property
    @abstractmethod
    def algorithmic_latency(self) -> int:
        """알고리즘 지연 (샘플 수)"""
        pass


class ONNXDenoiser(BaseDenoiser):
    """ONNX Runtime 기반 노이즈 제거기 (범용 TCN/CRN 등)"""

    def __init__(self, config: DNNModelConfig):
        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX Runtime이 설치되지 않음: pip install onnxruntime")

        self.config = config
        self.session = None
        self.input_name = None
        self.output_name = None
        self._init_session()

        # 스트리밍용 상태
        self._overlap_buffer = np.zeros(
            config.n_fft - config.hop_size, dtype=np.float32
        )
        self._window = np.hanning(config.n_fft).astype(np.float32)

    def _init_session(self):
        """ONNX 세션 초기화"""
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self.config.intra_op_threads
        sess_options.inter_op_num_threads = self.config.inter_op_threads
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        self.session = ort.InferenceSession(
            self.config.model_path,
            sess_options=sess_options,
            providers=self.config.providers,
        )

        # 입출력 이름 확인
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        # 입력 형태 확인
        input_shape = self.session.get_inputs()[0].shape
        print(f"ONNX 모델 로드: {self.config.model_path}")
        print(f"  입력 형태: {input_shape}")
        print(f"  출력 형태: {[o.shape for o in self.session.get_outputs()]}")

    def _stft(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """STFT 변환"""
        # 윈도우 적용
        windowed = audio * self._window

        # STFT
        stft = np.fft.rfft(windowed, n=self.config.n_fft)
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        return magnitude, phase

    def _istft(self, magnitude: np.ndarray, phase: np.ndarray) -> np.ndarray:
        """ISTFT 역변환"""
        # 복소 스펙트럼 복원
        stft = magnitude * np.exp(1j * phase)

        # IRFFT
        audio = np.fft.irfft(stft, n=self.config.n_fft)

        # 윈도우 보정
        audio = audio * self._window

        return audio

    def process(self, audio: np.ndarray) -> np.ndarray:
        """전체 오디오 프레임 단위 처리 (배치 모드)"""
        # 프레임 단위로 분할하여 처리
        frame_size = self.config.frame_size
        hop_size = self.config.hop_size
        n_frames = (len(audio) - self.config.frame_size) // hop_size + 1

        output = np.zeros_like(audio)

        for i in range(n_frames):
            start = i * hop_size
            end = start + self.config.frame_size
            frame = audio[start:end]

            # 패딩 필요 시
            if len(frame) < self.config.frame_size:
                frame = np.pad(frame, (0, self.config.frame_size - len(frame)))

            processed_frame = self.process_stream(frame)
            output[start:end] += processed_frame[:hop_size]

        return output

    def process_stream(self, audio_frame: np.ndarray) -> np.ndarray:
        """단일 프레임 스트리밍 처리"""
        # 프레임 크기 검증
        if len(audio_frame) != self.config.frame_size:
            if len(audio_frame) < self.config.frame_size:
                audio_frame = np.pad(
                    audio_frame, (0, self.config.frame_size - len(audio_frame))
                )
            else:
                audio_frame = audio_frame[: self.config.frame_size]

        # STFT
        magnitude, phase = self._stft(audio_frame)

        # 모델 입력 준비 (magnitude만 입력으로 사용하거나 complex 스펙트럼 사용)
        # 모델 입력 형태: (1, F, T) 또는 (1, 2, F, T) - magnitude/phase 또는 real/imag
        input_data = magnitude.astype(np.float32)[
            np.newaxis, np.newaxis, :
        ]  # (1, 1, F)

        # ONNX 추론
        output = self.session.run([self.output_name], {self.input_name: input_data})[
            0
        ]  # (1, 1, F) 또는 (1, 2, F)

        # 출력 파싱
        if output.shape[1] == 2:
            # Real/Imag 출력
            out_magnitude = np.sqrt(output[0, 0] ** 2 + output[0, 1] ** 2)
            out_phase = np.arctan2(output[0, 1], output[0, 0])
        else:
            # Magnitude만 출력 (위상은 원본 사용)
            out_magnitude = output[0, 0]
            out_phase = phase

        # ISTFT
        clean_frame = self._istft(out_magnitude, out_phase)

        return clean_frame[: self.config.hop_size]  # 홉 크기만큼만 반환

    def reset_state(self):
        """내부 상태 초기화"""
        self._overlap_buffer.fill(0)

    @property
    def algorithmic_latency(self) -> int:
        return self.config.n_fft - self.config.hop_size


class DeepFilterNet3Denoiser(BaseDenoiser):
    """
    DeepFilterNet3 ONNX 모델 전용 노이즈 제거기
    - 48kHz 샘플링 레이트 필요
    - ERB 스케일 스펙트럴 특징 사용
    - 실시간 스트리밍 지원 (상태 유지)
    """

    def __init__(self, config: DNNModelConfig):
        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX Runtime이 설치되지 않음: pip install onnxruntime")

        self.config = config
        self.session = None
        self.input_names = {}
        self.output_names = {}

        # DeepFilterNet3 설정 (config에서 가져오거나 기본값)
        # DeepFilterNet3는 내부적으로 48kHz 고정
        self.sample_rate = 48000
        self.fft_size = getattr(config, "n_fft", 960)
        self.hop_size = getattr(config, "hop_size", 480)
        self.erb_bands = getattr(config, "erb_bands", 32)
        self.df_bins = getattr(config, "df_bins", 96)
        self.df_order = getattr(config, "df_order", 5)
        self.conv_lookahead = getattr(config, "conv_lookahead", 2)
        self.df_lookahead = getattr(config, "df_lookahead", 2)
        self.norm_tau = getattr(config, "norm_tau", 1.0)
        self.normalization_alpha = getattr(config, "normalization_alpha", 0.99)

        # 입력/출력 샘플링 레이트 (리샘플링용)
        self.input_sample_rate = config.sample_rate

        # 보조 데이터 로드 (ERB 매트릭스, Vorbis 윈도우)
        self._load_auxiliary_data()

        # 스트리밍 상태
        self._init_streaming_state()

        # 세션 초기화
        self._init_session()

    def _load_auxiliary_data(self):
        """보조 데이터 로드 (ERB 매트릭스, Vorbis 윈도우)"""
        aux_path = Path(self.config.model_path).parent / "deepfilter-auxiliary.bin"
        if aux_path.exists():
            with open(aux_path, "rb") as f:
                data = f.read()
            # 간단한 파싱 (실제 포맷에 따라 조정 필요)
            # 여기서는 기본값 생성
            self._erb_fb = self._create_erb_filterbank()
            self._vorbis_window = self._create_vorbis_window()
        else:
            self._erb_fb = self._create_erb_filterbank()
            self._vorbis_window = self._create_vorbis_window()

    def _create_erb_filterbank(self) -> np.ndarray:
        """ERB 필터뱅크 생성 (주파수 → ERB 스케일 변환)"""
        # ERB 중심 주파수
        erb_freqs = np.linspace(0, self.sample_rate / 2, self.erb_bands + 2)[1:-1]
        # FFT 빈: 0 ~ sample_rate/2, fft_size//2 + 1 개
        fft_freqs = np.linspace(0, self.sample_rate / 2, self.fft_size // 2 + 1)

        # 삼각 필터뱅크
        erb_fb = np.zeros((self.erb_bands, len(fft_freqs)), dtype=np.float32)
        for i, cf in enumerate(erb_freqs):
            # ERB 대역폭 계산
            bw = 24.7 * (4.37 * cf / 1000 + 1)  # ERB 공식
            lower = cf - bw / 2
            upper = cf + bw / 2

            # 삼각 필터
            mask = (fft_freqs >= lower) & (fft_freqs <= upper)
            erb_fb[i, mask] = 1.0 - np.abs(fft_freqs[mask] - cf) / (bw / 2)

        # 정규화
        erb_fb = erb_fb / (erb_fb.sum(axis=1, keepdims=True) + 1e-8)
        return erb_fb.astype(np.float32)

    def _create_vorbis_window(self) -> np.ndarray:
        """Vorbis 윈도우 생성"""
        n = self.fft_size
        window = np.sin(np.pi / 2 * np.sin(np.pi * (np.arange(n) + 0.5) / n) ** 2)
        return window.astype(np.float32)

    def _init_session(self):
        """ONNX 세션 초기화"""
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self.config.intra_op_threads
        sess_options.inter_op_num_threads = self.config.inter_op_threads
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        self.session = ort.InferenceSession(
            self.config.model_path,
            sess_options=sess_options,
            providers=self.config.providers,
        )

        # 입출력 이름 매핑
        for inp in self.session.get_inputs():
            self.input_names[inp.name] = inp.shape
        for out in self.session.get_outputs():
            self.output_names[out.name] = out.shape

        print(f"DeepFilterNet3 ONNX 모델 로드: {self.config.model_path}")
        print(f"  입력: {self.input_names}")
        print(f"  출력: {self.output_names}")

    def _init_streaming_state(self):
        """스트리밍 상태 초기화"""
        # 오버랩-애드 버퍼
        self._overlap_buffer = np.zeros(self.fft_size - self.hop_size, dtype=np.float32)

        # 프레임 버퍼 (룩어헤드용)
        self._frame_buffer = np.zeros(
            (self.conv_lookahead + self.df_lookahead + 1, self.fft_size),
            dtype=np.float32,
        )
        self._frame_idx = 0

        # 노이즈 추정 상태
        self._noise_est = None
        self._noise_alpha = self.normalization_alpha

        # DeepFilter 상태 (DF 차수만큼 이전 프레임 저장)
        self._df_states = np.zeros((self.df_order, self.df_bins), dtype=np.complex64)

    def _stft(self, audio: np.ndarray) -> np.ndarray:
        """STFT 변환 (Vorbis 윈도우 사용)"""
        # 프레임 크기 맞추기
        if len(audio) != self.fft_size:
            if len(audio) < self.fft_size:
                audio = np.pad(audio, (0, self.fft_size - len(audio)))
            else:
                audio = audio[: self.fft_size]

        # Vorbis 윈도우 적용
        windowed = audio * self._vorbis_window

        # STFT
        stft = np.fft.rfft(windowed, n=self.fft_size)
        return stft

    def _istft(self, stft: np.ndarray) -> np.ndarray:
        """ISTFT 역변환 (Vorbis 윈도우 사용)"""
        # IRFFT
        audio = np.fft.irfft(stft, n=self.fft_size)

        # Vorbis 윈도우 적용 (완전 재구성을 위해)
        audio = audio * self._vorbis_window

        return audio

    def _compute_erb_features(self, magnitude: np.ndarray) -> np.ndarray:
        """주파수 스펙트럼을 ERB 특징으로 변환"""
        # ERB 필터뱅크 적용
        erb_features = self._erb_fb @ magnitude  # (erb_bands,)
        return erb_features.astype(np.float32)

    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """특징 정규화 (지수 이동 평균 기반)"""
        if self._noise_est is None:
            self._noise_est = features.copy()

        # 노이즈 추정 업데이트
        self._noise_est = (
            self._noise_alpha * self._noise_est + (1 - self._noise_alpha) * features
        )

        # 정규화: 특징 / (노이즈 추정 + tau)
        normalized = features / (self._noise_est + self.norm_tau)
        return normalized.astype(np.float32)

    def _prepare_model_input(
        self, stft: np.ndarray
    ) -> Tuple[Dict[str, np.ndarray], np.ndarray, np.ndarray]:
        """모델 입력 준비 (DeepFilterNet3 형식: feat_erb, feat_spec)"""
        magnitude = np.abs(stft)
        phase = np.angle(stft)

        # ERB 특징 추출 (32 밴드)
        erb_features = self._compute_erb_features(magnitude)  # (32,)

        # 정규화
        norm_erb = self._normalize_features(erb_features)  # (32,)

        # Spectral 특징 (96 빈, real/imag)
        # 모델은 96 빈의 복소 스펙트럼을 기대 (feat_spec: [1, 2, frames, 96])
        spec_real = magnitude[: self.df_bins].astype(np.float32)  # (96,)
        spec_imag = np.zeros_like(spec_real)  # 위상에서 계산 가능하지만 일단 0

        # 입력 형태: (batch=1, channels, frames=1, features)
        inputs = {
            "feat_erb": norm_erb[
                np.newaxis, np.newaxis, np.newaxis, :
            ],  # (1, 1, 1, 32)
            "feat_spec": np.stack([spec_real, spec_imag], axis=0)[
                np.newaxis, :, np.newaxis, :
            ],  # (1, 2, 1, 96)
        }

        return inputs, magnitude, phase

    def _parse_model_output(
        self,
        outputs: Dict[str, np.ndarray],
        original_magnitude: np.ndarray,
        original_phase: np.ndarray,
    ) -> np.ndarray:
        """모델 출력 파싱 (erb_mask, df_coefs)"""
        # ERB 마스크 출력: [1, 1, frames=2, 32]
        if "erb_mask" in outputs:
            erb_mask = outputs["erb_mask"][0, 0, 0]  # (32,) - 첫 번째 프레임
            # ERB 마스크를 주파수 마스크로 보간
            freq_mask = self._erb_fb.T @ erb_mask  # (fft_bins,)
            freq_mask = np.clip(freq_mask, 0, 2)  # 클리핑

            # 마스크 적용
            clean_magnitude = original_magnitude * freq_mask
            clean_phase = original_phase

        # DeepFilter 계수 출력: [1, 5, frames=2, 96, 2]
        elif "df_coefs" in outputs:
            # df_coefs: (1, 5, 2, 96, 2) -> 첫 번째 프레임
            df_coefs = outputs["df_coefs"][0, :, 0]  # (5, 96, 2)
            # 복소 계수로 변환
            df_complex = df_coefs[..., 0] + 1j * df_coefs[..., 1]  # (5, 96)

            # DeepFilter 적용 (단순화: 첫 번째 계수만 사용)
            filter_response = np.mean(df_complex, axis=0)  # (96,)
            filter_response = filter_response[: len(original_magnitude)]
            if len(filter_response) < len(original_magnitude):
                filter_response = np.pad(
                    filter_response, (0, len(original_magnitude) - len(filter_response))
                )

            clean_magnitude = original_magnitude * np.abs(filter_response)
            clean_phase = original_phase + np.angle(filter_response)

        else:
            # 기본: 첫 번째 출력 사용
            out = list(outputs.values())[0]
            if out.shape[-1] == 2:
                clean_magnitude = np.sqrt(out[0, 0] ** 2 + out[0, 1] ** 2)
                clean_phase = np.arctan2(out[0, 1], out[0, 0])
            else:
                clean_magnitude = out[0, 0]
                clean_phase = original_phase

        # 복소 스펙트럼 복원
        clean_stft = clean_magnitude * np.exp(1j * clean_phase)
        return clean_stft

    def process(self, audio: np.ndarray) -> np.ndarray:
        """전체 오디오 배치 처리"""
        # 리샘플링 필요시 (입력 SR → 48kHz)
        if self.input_sample_rate != self.sample_rate:
            from scipy.signal import resample

            audio = resample(
                audio, int(len(audio) * self.sample_rate / self.input_sample_rate)
            )

        # 프레임 단위 처리
        n_frames = (len(audio) - self.fft_size) // self.hop_size + 1
        output = np.zeros(len(audio), dtype=np.float32)

        for i in range(n_frames):
            start = i * self.hop_size
            end = start + self.fft_size
            frame = audio[start:end]

            processed_frame = self.process_stream(frame)
            output[start : start + self.hop_size] += processed_frame[: self.hop_size]

        # 리샘플링 복구 (48kHz → 입력 SR)
        if self.input_sample_rate != self.sample_rate:
            from scipy.signal import resample

            output = resample(
                output, int(len(output) * self.input_sample_rate / self.sample_rate)
            )

        return output

    def process_stream(self, audio_frame: np.ndarray) -> np.ndarray:
        """단일 프레임 스트리밍 처리 (48kHz, 960 samples)"""
        # 프레임 크기 검증
        if len(audio_frame) != self.fft_size:
            if len(audio_frame) < self.fft_size:
                audio_frame = np.pad(audio_frame, (0, self.fft_size - len(audio_frame)))
            else:
                audio_frame = audio_frame[: self.fft_size]

        # STFT
        stft = self._stft(audio_frame)

        # 모델 입력 준비
        inputs, magnitude, phase = self._prepare_model_input(stft)

        # ONNX 추론
        outputs = self.session.run(None, inputs)
        output_dict = {
            name: out for name, out in zip(self.output_names.keys(), outputs)
        }

        # 출력 파싱
        clean_stft = self._parse_model_output(output_dict, magnitude, phase)

        # ISTFT
        clean_frame = self._istft(clean_stft)

        # 오버랩-애드
        output_frame = np.zeros(self.fft_size, dtype=np.float32)
        output_frame[: self.fft_size - self.hop_size] += self._overlap_buffer
        output_frame[self.hop_size :] += clean_frame[self.hop_size :]
        self._overlap_buffer = clean_frame[: self.fft_size - self.hop_size].copy()

        return output_frame[
            self.hop_size : self.hop_size + self.hop_size
        ]  # 홉 크기만큼 반환

    def reset_state(self):
        """내부 상태 초기화"""
        self._overlap_buffer.fill(0)
        self._frame_buffer.fill(0)
        self._frame_idx = 0
        self._noise_est = None
        self._df_states.fill(0)

    @property
    def algorithmic_latency(self) -> int:
        return self.fft_size - self.hop_size


class TorchDenoiser(BaseDenoiser):
    """PyTorch 기반 노이즈 제거기 (학습/파인튜닝용)"""

    def __init__(self, config: DNNModelConfig):
        if not _check_torch():
            raise RuntimeError("PyTorch가 설치되지 않음: pip install torch")

        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self._load_model()

    def _load_model(self):
        """모델 로드 (구현 필요)"""
        # 예: TCN, CRN, DPRNN 등 아키텍처별 구현
        raise NotImplementedError("모델 아키텍처별 구현 필요")

    def process(self, audio: np.ndarray) -> np.ndarray:
        raise NotImplementedError()

    def process_stream(self, audio_frame: np.ndarray) -> np.ndarray:
        raise NotImplementedError()

    def reset_state(self):
        pass

    @property
    def algorithmic_latency(self) -> int:
        return self.config.n_fft - self.config.hop_size


class DNNNoiseSuppression:
    """
    DNN 기반 노이즈 억제 통합 인터페이스
    - ONNX Runtime (추론 최적화)
    - PyTorch (학습/파인튜닝)
    - DeepFilterNet3 (전용 처리)
    - 스트리밍/배치 모드 지원
    """

    def __init__(
        self,
        model_path: str,
        config: Optional[DNNModelConfig] = None,
        backend: str = "onnx",  # "onnx", "torch", "deepfilternet3"
    ):
        self.config = config or DNNModelConfig(model_path=model_path)
        self.backend = backend
        self.denoiser = None
        self._init_denoiser()

    def _init_denoiser(self):
        """백엔드별 디노이저 초기화"""
        if self.backend == "onnx":
            if not ONNX_AVAILABLE:
                raise RuntimeError("ONNX Runtime 필요: pip install onnxruntime")
            self.denoiser = ONNXDenoiser(self.config)
        elif self.backend == "torch":
            if not _check_torch():
                raise RuntimeError("PyTorch 필요: pip install torch")
            self.denoiser = TorchDenoiser(self.config)
        elif self.backend == "deepfilternet3":
            if not ONNX_AVAILABLE:
                raise RuntimeError("ONNX Runtime 필요: pip install onnxruntime")
            self.denoiser = DeepFilterNet3Denoiser(self.config)
        else:
            raise ValueError(f"지원하지 않는 백엔드: {self.backend}")

    def process(self, audio: np.ndarray) -> np.ndarray:
        """배치 모드 처리"""
        if self.denoiser is None:
            raise RuntimeError("디노이저가 초기화되지 않음")
        return self.denoiser.process(audio)

    def process_stream(self, audio_frame: np.ndarray) -> np.ndarray:
        """스트리밍 프레임 단위 처리"""
        if self.denoiser is None:
            raise RuntimeError("디노이저가 초기화되지 않음")
        return self.denoiser.process_stream(audio_frame)

    def reset_state(self):
        if self.denoiser:
            self.denoiser.reset_state()

    @property
    def algorithmic_latency(self) -> int:
        if self.denoiser:
            return self.denoiser.algorithmic_latency
        return 0


# 편의 함수
def create_denoiser(
    model_path: str,
    backend: str = "onnx",
    sample_rate: int = 16000,
    frame_size: int = 512,
    hop_size: int = 256,
    **kwargs,
) -> DNNNoiseSuppression:
    """DNN 노이즈 억제기 생성 편의 함수"""
    config = DNNModelConfig(
        model_path=model_path,
        sample_rate=sample_rate,
        frame_size=frame_size,
        hop_size=hop_size,
        **kwargs,
    )
    return DNNNoiseSuppression(model_path, config, backend)


# DeepFilterNet3 전용 편의 함수
def create_deepfilternet3_denoiser(
    model_dir: str,
    sample_rate: int = 16000,  # 입력 샘플링 레이트 (자동 리샘플링)
    **kwargs,
) -> DNNNoiseSuppression:
    """DeepFilterNet3 노이즈 억제기 생성 (48kHz 내부 처리, 자동 리샘플링)"""
    model_path = str(Path(model_dir) / "deepfilter.onnx")
    config = DNNModelConfig(
        model_path=model_path,
        sample_rate=sample_rate,
        model_type="deepfilternet3",
        **kwargs,
    )
    return DNNNoiseSuppression(model_path, config, "deepfilternet3")


# 모델 변환 유틸리티
def export_pytorch_to_onnx(
    pytorch_model,
    output_path: str,
    sample_rate: int = 16000,
    frame_size: int = 512,
    opset_version: int = 14,
):
    """PyTorch 모델을 ONNX로 변환"""
    import torch

    dummy_input = torch.randn(1, 1, frame_size // 2 + 1)  # (B, C, F)

    torch.onnx.export(
        pytorch_model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["magnitude"],
        output_names=["output_magnitude"],
        dynamic_axes={
            "magnitude": {0: "batch", 2: "frames"},
            "output_magnitude": {0: "batch", 2: "frames"},
        },
    )
    print(f"ONNX 모델 저장: {output_path}")


# 추천 사전학습 모델 정보
PRETRAINED_MODELS = {
    "dns64": {
        "description": "Microsoft DNS Challenge 2020 베이스라인 모델",
        "url": "https://github.com/microsoft/DNS-Challenge",
        "sample_rate": 16000,
        "model_type": "tcn",
    },
    "dprnn": {
        "description": "Dual-Path RNN 음성 분리/노이즈 제거",
        "url": "https://github.com/JusperLee/Dual-Path-RNN",
        "sample_rate": 16000,
        "model_type": "dprnn",
    },
    "crn": {
        "description": "Convolutional Recurrent Network",
        "url": "https://github.com/XiaoMi/CRN",
        "sample_rate": 16000,
        "model_type": "crn",
    },
    "demucs": {
        "description": "Facebook Demucs 음성 분리/노이즈 제거",
        "url": "https://github.com/facebookresearch/demucs",
        "sample_rate": 16000,
        "model_type": "demucs",
    },
    "deepfilternet3": {
        "description": "DeepFilterNet3 실시간 노이즈 제거 (48kHz, ERB 특징)",
        "url": "https://huggingface.co/soniqo/DeepFilterNet3-ONNX",
        "sample_rate": 48000,
        "model_type": "deepfilternet3",
    },
}


if __name__ == "__main__":
    # 사용 예시
    print("DNN 노이즈 제거 모듈")
    print(
        f"사용 가능한 백엔드: ONNX={'ONNX' if ONNX_AVAILABLE else 'None'} | PyTorch={'PyTorch' if TORCH_AVAILABLE else 'None'}"
    )
    print("\n추천 사전학습 모델:")
    for name, info in PRETRAINED_MODELS.items():
        print(
            f"  {name}: {info['description']} ({info['model_type']}, {info['sample_rate']}Hz)"
        )

    # DeepFilterNet3 테스트 (모델이 있는 경우)
    import os

    model_dir = "~/projectm/Q250-V3-Opti/models/denoising"
    if os.path.exists(os.path.expanduser(model_dir + "/deepfilter.onnx")):
        print(f"\nDeepFilterNet3 모델 발견: {model_dir}")
        try:
            denoiser = create_deepfilternet3_denoiser(model_dir)
            print("DeepFilterNet3 디노이저 생성 성공")
        except Exception as e:
            print(f"DeepFilterNet3 로드 실패: {e}")
