"""
2단계: 프로펠러 소음 제거를 위한 신호처리(DSP) 파이프라인
- 적응형 노이즈 캔슬링 (LMS/RLS)
- 스펙트럴 서브트랙션
- 프로펠러 BPF 주파수 노치 필터
- 4채널 빔포밍 (지연합/최대 SNR)
"""
import numpy as np
import scipy.signal as signal
from typing import Optional, Tuple
from dataclasses import dataclass
from collections import deque


@dataclass
class PropellerNoiseConfig:
    """프로펠러 노이즈 리덕션 설정"""
    sample_rate: int = 16000
    n_fft: int = 512
    hop_length: int = 160  # 10ms @ 16kHz
    n_channels: int = 4
    
    # 프로펠러 주파수 대역 (BPF + 고조파)
    prop_base_freq: float = 80.0    # 기본 주파수 (Hz) - 일반적인 멀티콥터
    prop_harmonics: int = 10        # 고려할 고조파 수
    notch_bandwidth: float = 5.0    # 노치 필터 대역폭 (Hz)
    
    # 스펙트럴 서브트랙션
    spectral_floor: float = 0.02    # 스펙트럴 플로어 (최소 게인)
    over_subtraction: float = 1.5   # 과감제 계수
    
    # 적응형 필터 (LMS)
    lms_filter_len: int = 256       # 필터 길이 (16ms @ 16kHz)
    lms_mu: float = 0.01            # 스텝 크기
    lms_leakage: float = 0.999      # 누설 계수
    
    # 빔포밍
    beamforming_type: str = "mvdr"  # "delay_sum", "mvdr", "max_snr"
    mic_spacing: float = 0.05       # 마이크 간격 (m)
    sound_speed: float = 343.0      # 음속 (m/s)


class NotchFilterBank:
    """프로펠러 주파수 + 고조파 노치 필터 뱅크"""
    
    def __init__(self, config: PropellerNoiseConfig):
        self.config = config
        self.filters = []
        self._design_filters()
    
    def _design_filters(self):
        """프로펠러 기본주파수 + 고조파에 대한 IIR 노치 필터 설계"""
        self.filters = []
        for h in range(1, self.config.prop_harmonics + 1):
            freq = self.config.prop_base_freq * h
            if freq < self.config.sample_rate / 2:
                # 2차 IIR 노치 필터 설계
                w0 = freq / (self.config.sample_rate / 2)
                bw = self.config.notch_bandwidth / (self.config.sample_rate / 2)
                # scipy.signal.iirnotch 사용
                b, a = signal.iirnotch(w0, 1.0 / bw)
                self.filters.append((b, a))
    
    def apply(self, audio: np.ndarray) -> np.ndarray:
        """오디오에 모든 노치 필터 순차 적용"""
        result = audio.copy()
        for b, a in self.filters:
            result = signal.lfilter(b, a, result)
        return result


class SpectralSubtraction:
    """스펙트럴 서브트랙션 기반 노이즈 제거"""
    
    def __init__(self, config: PropellerNoiseConfig):
        self.config = config
        self.noise_psd = None
        self.alpha = 0.98  # 노이즈 PSD 업데이트 계수
        self.first_frame = True
        
    def _stft(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """STFT 변환"""
        f, t, Zxx = signal.stft(
            audio, fs=self.config.sample_rate,
            nperseg=self.config.n_fft,
            noverlap=self.config.n_fft - self.config.hop_length,
            window='hann'
        )
        return Zxx, f
    
    def _istft(self, Zxx: np.ndarray) -> np.ndarray:
        """ISTFT 역변환"""
        _, audio = signal.istft(
            Zxx, fs=self.config.sample_rate,
            nperseg=self.config.n_fft,
            noverlap=self.config.n_fft - self.config.hop_length,
            window='hann'
        )
        return audio
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """스펙트럴 서브트랙션 적용"""
        # STFT
        Zxx, freqs = self._stft(audio)
        magnitude = np.abs(Zxx)
        phase = np.angle(Zxx)
        psd = magnitude ** 2
        
        # 노이즈 PSD 추정 (첫 프레임 또는 무음 구간)
        if self.first_frame:
            self.noise_psd = psd.copy()
            self.first_frame = False
        else:
            # 노이즈만 있는 구간 감지 (간단: 에너지 임계값)
            frame_energy = np.mean(psd)
            if frame_energy < 1e-6:  # 무음에 가까움
                self.noise_psd = self.alpha * self.noise_psd + (1 - self.alpha) * psd
        
        # 스펙트럴 서브트랙션
        if self.noise_psd is not None:
            # 과감제 + 스펙트럴 플로어
            clean_psd = magnitude ** 2 - self.config.over_subtraction * self.noise_psd
            clean_psd = np.maximum(clean_psd, self.config.spectral_floor * self.noise_psd)
            clean_magnitude = np.sqrt(clean_psd)
        else:
            clean_magnitude = magnitude
        
        # 복원
        clean_Zxx = clean_magnitude * np.exp(1j * phase)
        clean_audio = self._istft(clean_Zxx)
        
        return clean_audio[:len(audio)]  # 길이 맞추기


class AdaptiveLMSFilter:
    """적응형 LMS 필터 (참조 신호 기반 노이즈 캔슬링)"""
    
    def __init__(self, config: PropellerNoiseConfig, reference_channel: int = 0):
        self.config = config
        self.reference_channel = reference_channel
        self.filter_len = config.lms_filter_len
        self.mu = config.lms_mu
        self.leakage = config.lms_leakage
        
        # 필터 계수 초기화
        self.weights = np.zeros(self.filter_len, dtype=np.float32)
        self.buffer = np.zeros(self.filter_len, dtype=np.float32)
        
    def process(self, primary: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """
        Primary: 주 신호 (음성 + 노이즈)
        Reference: 참조 신호 (노이즈만 포함된 채널 또는 프로펠러 RPM 동기 신호)
        """
        output = np.zeros_like(primary)
        error = np.zeros_like(primary)
        
        for i in range(len(primary)):
            # 버퍼 업데이트
            self.buffer = np.roll(self.buffer, 1)
            self.buffer[0] = reference[i]
            
            # 필터 출력 (노이즈 추정)
            y = np.dot(self.weights, self.buffer)
            
            # 에러 계산 (목표: 음성만 남김)
            error[i] = primary[i] - y
            
            # LMS 가중치 업데이트
            self.weights = self.leakage * self.weights + self.mu * error[i] * self.buffer
            
        return error


class Beamformer:
    """4채널 빔포밍 (Delay-and-Sum, MVDR, Max-SNR)"""
    
    def __init__(self, config: PropellerNoiseConfig):
        self.config = config
        self.mic_positions = self._get_mic_positions()
        
    def _get_mic_positions(self) -> np.ndarray:
        """4채널 정사각형 배치 위치 (m)"""
        d = self.config.mic_spacing
        return np.array([
            [-d/2, -d/2, 0],  # Ch0: 전방-좌측
            [ d/2, -d/2, 0],  # Ch1: 전방-우측
            [ d/2,  d/2, 0],  # Ch2: 후방-우측
            [-d/2,  d/2, 0],  # Ch3: 후방-좌측
        ])
    
    def _steering_vector(self, freq: float, azimuth: float, elevation: float = 0) -> np.ndarray:
        """지향 벡터 계산"""
        k = 2 * np.pi * freq / self.config.sound_speed
        dir_vec = np.array([
            np.cos(elevation) * np.cos(azimuth),
            np.cos(elevation) * np.sin(azimuth),
            np.sin(elevation)
        ])
        delays = np.dot(self.mic_positions, dir_vec)
        return np.exp(-1j * k * delays)
    
    def delay_and_sum(self, audio_4ch: np.ndarray, azimuth: float = 0, elevation: float = 0) -> np.ndarray:
        """
        Delay-and-Sum 빔포밍
        audio_4ch: (4, N) shape
        """
        n_channels, n_samples = audio_4ch.shape
        output = np.zeros(n_samples, dtype=np.float32)
        
        # 주파수 도메인에서 처리 (효율성)
        for ch in range(n_channels):
            output += audio_4ch[ch]  # 단순 합 (지연 보상 생략 - 단순화)
        
        return output / n_channels
    
    def mvdr(self, audio_4ch: np.ndarray, azimuth: float = 0, elevation: float = 0) -> np.ndarray:
        """
        MVDR (Minimum Variance Distortionless Response) 빔포밍
        주파수 도메인에서 공분산 행렬 기반 가중치 계산
        """
        # STFT
        n_channels, n_samples = audio_4ch.shape
        stft_data = []
        f = None
        for ch in range(n_channels):
            f_ch, t, Zxx = signal.stft(
                audio_4ch[ch], fs=self.config.sample_rate,
                nperseg=512, noverlap=256
            )
            stft_data.append(Zxx)
            if f is None:
                f = f_ch
        
        # f가 None이면 기본 주파수 배열 생성
        if f is None:
            f = np.linspace(0, self.config.sample_rate / 2, 257)
        
        stft_data = np.array(stft_data)  # (4, F, T)
        n_freq, n_frames = stft_data.shape[1], stft_data.shape[2]
        output_stft = np.zeros((n_freq, n_frames), dtype=np.complex64)
        
        for fi in range(n_freq):
            freq = f[fi]
            # 지향 벡터
            d = self._steering_vector(freq, azimuth, elevation)
            
            # 공분산 행렬 추정 (시간 평균)
            R = np.zeros((4, 4), dtype=np.complex64)
            for ti in range(n_frames):
                x = stft_data[:, fi, ti]
                R += np.outer(x, x.conj())
            R /= n_frames
            
            # 정규화
            R += 1e-6 * np.eye(4)
            
            # MVDR 가중치: w = R^-1 * d / (d^H * R^-1 * d)
            try:
                Rinv = np.linalg.inv(R)
                w = Rinv @ d
                w = w / (d.conj() @ Rinv @ d)
                
                # 적용
                for ti in range(n_frames):
                    x = stft_data[:, fi, ti]
                    output_stft[fi, ti] = w.conj() @ x
            except np.linalg.LinAlgError:
                # 특이 행렬이면 D&S로 폴백
                output_stft[fi, :] = np.mean(stft_data[:, fi, :], axis=0)
        
        # ISTFT
        _, output = signal.istft(output_stft, fs=self.config.sample_rate)
        return output[:n_samples]


class PropellerNoiseReducer:
    """
    프로펠러 노이즈 통합 리듀서
    파이프라인: 노치 필터 → 스펙트럴 서브트랙션 → 적응형 LMS → 빔포밍
    """
    
    def __init__(self, config: Optional[PropellerNoiseConfig] = None):
        self.config = config or PropellerNoiseConfig()
        
        # 각 단계 초기화
        self.notch_filter = NotchFilterBank(self.config)
        self.spectral_sub = SpectralSubtraction(self.config)
        self.lms_filters = [
            AdaptiveLMSFilter(self.config, ref_ch) 
            for ref_ch in range(self.config.n_channels)
        ]
        self.beamformer = Beamformer(self.config)
        
        # 통계
        self.stats = {
            "notch_applied": 0,
            "spectral_frames": 0,
            "lms_updates": 0,
            "beamformed_frames": 0
        }
    
    def process(self, audio_4ch: np.ndarray, reference_rpm: Optional[np.ndarray] = None) -> np.ndarray:
        """
        4채널 오디오 입력 → 단일 채널 클린 오디오 출력
        
        Args:
            audio_4ch: (4, N) shape, 4채널 원시 오디오
            reference_rpm: 프로펠러 RPM 신호 (선택적, LMS 참조용)
        
        Returns:
            clean_audio: (N,) shape, 단일 채널 클린 오디오
        """
        n_channels, n_samples = audio_4ch.shape
        assert n_channels == self.config.n_channels
        
        # 1단계: 노치 필터 (프로펠러 주파수 + 고조파 제거)
        filtered = np.zeros_like(audio_4ch)
        for ch in range(self.config.n_channels):
            filtered[ch] = self.notch_filter.apply(audio_4ch[ch])
        self.stats["notch_applied"] += 1
        
        # 2단계: 스펙트럴 서브트랙션 (채널별 독립 적용)
        spectral_clean = np.zeros_like(filtered)
        for ch in range(self.config.n_channels):
            spectral_clean[ch] = self.spectral_sub.process(filtered[ch])
        self.stats["spectral_frames"] += 1
        
        # 3단계: 적응형 LMS 노이즈 캔슬링 (참조 신호가 있는 경우)
        if reference_rpm is not None:
            lms_clean = np.zeros_like(spectral_clean)
            for ch in range(self.config.n_channels):
                lms_clean[ch] = self.lms_filters[ch].process(
                    spectral_clean[ch], reference_rpm
                )
            self.stats["lms_updates"] += 1
            enhanced = lms_clean
        else:
            enhanced = spectral_clean
        
        # 4단계: 빔포밍 (전방 음성 강조)
        # 전방(azimuth=0) 방향 우선
        clean_audio = self.beamformer.delay_and_sum(enhanced, azimuth=0.0)
        self.stats["beamformed_frames"] += 1
        
        return clean_audio
    
    def get_stats(self) -> dict:
        return self.stats.copy()
    
    def reset(self):
        self.stats = {k: 0 for k in self.stats}
        self.spectral_sub.noise_psd = None
        self.spectral_sub.first_frame = True
        for lms in self.lms_filters:
            lms.weights.fill(0)
            lms.buffer.fill(0)


# 편의 함수
def create_noise_reducer(
    sample_rate: int = 16000,
    n_channels: int = 4,
    prop_freq: float = 80.0
) -> PropellerNoiseReducer:
    """기본 설정으로 노이즈 리듀서 생성"""
    config = PropellerNoiseConfig(
        sample_rate=sample_rate,
        n_channels=n_channels,
        prop_base_freq=prop_freq
    )
    return PropellerNoiseReducer(config)


# 테스트/데모
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    
    # 테스트용 합성 신호 생성
    sr = 16000
    duration = 2.0
    t = np.arange(int(sr * duration)) / sr
    
    # 합성 음성 (100-4000Hz 대역)
    speech = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 880 * t)
    speech += 0.2 * np.random.randn(len(t))
    
    # 프로펠러 소음 (80Hz 기본 + 고조파)
    prop_noise = np.zeros_like(t)
    for h in range(1, 11):
        prop_noise += 0.1/h * np.sin(2 * np.pi * 80 * h * t)
    
    # 4채널 시뮬레이션 (지연 차이만)
    audio_4ch = np.zeros((4, len(t)))
    for ch in range(4):
        delay = ch * 10  # 샘플 단위 지연
        if delay > 0:
            audio_4ch[ch, delay:] = speech[:-delay] + 0.5 * prop_noise[:-delay]
        else:
            audio_4ch[ch] = speech + 0.5 * prop_noise
    
    # 노이즈 리듀서 적용
    reducer = create_noise_reducer(sample_rate=16000, n_channels=4, prop_freq=80)
    clean = reducer.process(audio_4ch)
    
    # 결과 확인
    print(f"입력 shape: {audio_4ch.shape}")
    print(f"출력 shape: {clean.shape}")
    print(f"통계: {reducer.get_stats()}")
    
    # SNR 계산
    def snr(signal, noise):
        return 10 * np.log10(np.sum(signal**2) / np.sum(noise**2))
    
    input_snr = snr(speech, audio_4ch[0] - speech)
    output_snr = snr(speech[:len(clean)], clean - speech[:len(clean)])
    print(f"입력 SNR: {input_snr:.1f} dB")
    print(f"출력 SNR: {output_snr:.1f} dB")
    print(f"개선: {output_snr - input_snr:.1f} dB")