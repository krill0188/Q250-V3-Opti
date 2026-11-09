"""
3단계: DNN 기반 노이즈 제거 (딥러닝 기반 실시간 노이즈 억제)
- TCN/CRN 기반 실시간 노이즈 억제 모델 인터페이스
- ONNX Runtime / TensorRT / TensorFlow Lite 지원
- 실시간 스트리밍 추론 최적화
"""
import numpy as np
from typing import Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod
import warnings

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
    frame_size: int = 512       # 프레임 크기 (샘플)
    hop_size: int = 256         # 홉 크기 (샘플)
    n_fft: int = 512            # FFT 크기
    input_channels: int = 1     # 입력 채널 (모노)
    output_channels: int = 1    # 출력 채널 (모노)
    
    # 모델 아키텍처 파라미터
    model_type: str = "tcn"     # "tcn", "crn", "dprnn", "demucs"
    hidden_size: int = 256
    num_layers: int = 4
    
    # 런타임 설정
    use_onnx: bool = True       # ONNX Runtime 사용
    providers: list = None      # ONNX 프로바이더 우선순위
    intra_op_threads: int = 1   # 연산자 내 스레드 수
    inter_op_threads: int = 1   # 연산자 간 스레드 수
    
    def __post_init__(self):
        if self.providers is None:
            self.providers = ['CPUExecutionProvider']


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
    """ONNX Runtime 기반 노이즈 제거기"""
    
    def __init__(self, config: DNNModelConfig):
        if not ONNX_AVAILABLE:
            raise RuntimeError("ONNX Runtime이 설치되지 않음: pip install onnxruntime")
        
        self.config = config
        self.session = None
        self.input_name = None
        self.output_name = None
        self._init_session()
        
        # 스트리밍용 상태
        self._overlap_buffer = np.zeros(config.n_fft - config.hop_size, dtype=np.float32)
        self._window = np.hanning(config.n_fft).astype(np.float32)
        
    def _init_session(self):
        """ONNX 세션 초기화"""
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = self.config.intra_op_threads
        sess_options.inter_op_num_threads = self.config.inter_op_threads
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self.session = ort.InferenceSession(
            self.config.model_path,
            sess_options=sess_options,
            providers=self.config.providers
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
                audio_frame = np.pad(audio_frame, (0, self.config.frame_size - len(audio_frame)))
            else:
                audio_frame = audio_frame[:self.config.frame_size]
        
        # STFT
        magnitude, phase = self._stft(audio_frame)
        
        # 모델 입력 준비 (magnitude만 입력으로 사용하거나 complex 스펙트럼 사용)
        # 모델 입력 형태: (1, F, T) 또는 (1, 2, F, T) - magnitude/phase 또는 real/imag
        input_data = magnitude.astype(np.float32)[np.newaxis, np.newaxis, :]  # (1, 1, F)
        
        # ONNX 추론
        output = self.session.run(
            [self.output_name],
            {self.input_name: input_data}
        )[0]  # (1, 1, F) 또는 (1, 2, F)
        
        # 출력 파싱
        if output.shape[1] == 2:
            # Real/Imag 출력
            out_magnitude = np.sqrt(output[0, 0]**2 + output[0, 1]**2)
            out_phase = np.arctan2(output[0, 1], output[0, 0])
        else:
            # Magnitude만 출력 (위상은 원본 사용)
            out_magnitude = output[0, 0]
            out_phase = phase
        
        # ISTFT
        clean_frame = self._istft(out_magnitude, out_phase)
        
        return clean_frame[:self.config.hop_size]  # 홉 크기만큼만 반환
    
    def reset_state(self):
        """내부 상태 초기화"""
        self._overlap_buffer.fill(0)
    
    @property
    def algorithmic_latency(self) -> int:
        return self.config.n_fft - self.config.hop_size


class TorchDenoiser(BaseDenoiser):
    """PyTorch 기반 노이즈 제거기 (학습/파인튜닝용)"""
    
    def __init__(self, config: DNNModelConfig):
        if not _check_torch():
            raise RuntimeError("PyTorch가 설치되지 않음: pip install torch")
        
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
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
    - 스트리밍/배치 모드 지원
    """
    
    def __init__(
        self,
        model_path: str,
        config: Optional[DNNModelConfig] = None,
        backend: str = "onnx"  # "onnx" or "torch"
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
    **kwargs
) -> DNNNoiseSuppression:
    """DNN 노이즈 억제기 생성 편의 함수"""
    config = DNNModelConfig(
        model_path=model_path,
        sample_rate=sample_rate,
        frame_size=frame_size,
        hop_size=hop_size,
        **kwargs
    )
    return DNNNoiseSuppression(model_path, config, backend)


# 모델 변환 유틸리티
def export_pytorch_to_onnx(
    pytorch_model,
    output_path: str,
    sample_rate: int = 16000,
    frame_size: int = 512,
    opset_version: int = 14
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
        input_names=['magnitude'],
        output_names=['output_magnitude'],
        dynamic_axes={
            'magnitude': {0: 'batch', 2: 'frames'},
            'output_magnitude': {0: 'batch', 2: 'frames'}
        }
    )
    print(f"ONNX 모델 저장: {output_path}")


# 추천 사전학습 모델 정보
PRETRAINED_MODELS = {
    "dns64": {
        "description": "Microsoft DNS Challenge 2020 베이스라인 모델",
        "url": "https://github.com/microsoft/DNS-Challenge",
        "sample_rate": 16000,
        "model_type": "tcn"
    },
    "dprnn": {
        "description": "Dual-Path RNN 음성 분리/노이즈 제거",
        "url": "https://github.com/JusperLee/Dual-Path-RNN",
        "sample_rate": 16000,
        "model_type": "dprnn"
    },
    "crn": {
        "description": "Convolutional Recurrent Network",
        "url": "https://github.com/XiaoMi/CRN",
        "sample_rate": 16000,
        "model_type": "crn"
    },
    "demucs": {
        "description": "Facebook Demucs 음성 분리/노이즈 제거",
        "url": "https://github.com/facebookresearch/demucs",
        "sample_rate": 16000,
        "model_type": "demucs"
    }
}


if __name__ == "__main__":
    # 사용 예시
    print("DNN 노이즈 제거 모듈")
    print("사용 가능한 백엔드:", "ONNX" if ONNX_AVAILABLE else "None", "| PyTorch" if TORCH_AVAILABLE else "None")
    print("\n추천 사전학습 모델:")
    for name, info in PRETRAINED_MODELS.items():
        print(f"  {name}: {info['description']} ({info['model_type']})")