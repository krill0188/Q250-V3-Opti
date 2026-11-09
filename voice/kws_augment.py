"""
KWS Data Augmentation - 학습 데이터 증강
원본 오디오 → 다양한 변형으로 데이터 N배 확대
"""
import numpy as np
import librosa
import soundfile as sf
import random
from pathlib import Path
from typing import List, Optional, Tuple
import json
from dataclasses import dataclass, asdict
import shutil


@dataclass
class AugmentConfig:
    """증강 설정"""
    # 시간 스트레칭
    time_stretch_range: Tuple[float, float] = (0.9, 1.1)
    time_stretch_prob: float = 0.5
    
    # 피치 시프트
    pitch_shift_range: Tuple[float, float] = (-2.0, 2.0)  # 반음 단위
    pitch_shift_prob: float = 0.5
    
    # 배경 노이즈
    noise_snr_range: Tuple[float, float] = (10.0, 30.0)  # dB
    noise_prob: float = 0.7
    noise_types: List[str] = None  # white, pink, brown, babble
    
    # 볼륨 조절
    volume_range: Tuple[float, float] = (0.5, 1.5)
    volume_prob: float = 0.5
    
    # 시간 시프트
    time_shift_max_sec: float = 0.2
    time_shift_prob: float = 0.3
    
    # 리버브 (실내/실외 시뮬레이션)
    reverb_prob: float = 0.2
    reverb_room_size: Tuple[float, float] = (0.1, 0.8)
    reverb_damping: Tuple[float, float] = (0.2, 0.8)
    
    # 출력 설정
    target_sample_rate: int = 16000
    target_duration: float = 2.0  # 초
    n_augment: int = 10  # 원본 1개당 생성할 증강 수
    
    def __post_init__(self):
        if self.noise_types is None:
            self.noise_types = ['white', 'pink']


class AudioAugmenter:
    """오디오 데이터 증강기"""
    
    def __init__(self, config: Optional[AugmentConfig] = None):
        self.config = config or AugmentConfig()
        self.sr = self.config.target_sample_rate
        self.target_samples = int(self.sr * self.config.target_duration)
        
        # 노이즈 캐시
        self._noise_cache = {}
    
    def _generate_noise(self, noise_type: str, length: int) -> np.ndarray:
        """각종 노이즈 생성"""
        cache_key = f"{noise_type}_{length}"
        if cache_key in self._noise_cache:
            return self._noise_cache[cache_key]
        
        if noise_type == 'white':
            noise = np.random.randn(length)
        elif noise_type == 'pink':
            # 핑크 노이즈 (1/f 스펙트럼)
            white = np.random.randn(length)
            # 간단한 핑크 노이즈 근사
            b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
            a = [1, -2.494956002, 2.017265875, -0.522189400]
            from scipy import signal
            noise = signal.lfilter(b, a, white)
        elif noise_type == 'brown':
            # 브라운 노이즈 (랜덤 워크)
            noise = np.cumsum(np.random.randn(length))
            noise = noise / np.max(np.abs(noise))
        else:
            noise = np.random.randn(length)
        
        # 정규화
        noise = noise / (np.std(noise) + 1e-10)
        self._noise_cache[cache_key] = noise
        return noise
    
    def add_noise(self, audio: np.ndarray, snr_db: float, noise_type: str = 'white') -> np.ndarray:
        """SNR 기준으로 노이즈 추가"""
        noise = self._generate_noise(noise_type, len(audio))
        
        # 신호 파워
        signal_power = np.mean(audio ** 2)
        noise_power = np.mean(noise ** 2)
        
        # 원하는 SNR 달성하도록 노이즈 스케일링
        target_noise_power = signal_power / (10 ** (snr_db / 10))
        scale = np.sqrt(target_noise_power / (noise_power + 1e-10))
        
        return audio + noise * scale
    
    def time_stretch(self, audio: np.ndarray, rate: float) -> np.ndarray:
        """시간 스트레칭 (피치 보존)"""
        return librosa.effects.time_stretch(audio, rate=rate)
    
    def pitch_shift(self, audio: np.ndarray, n_steps: float) -> np.ndarray:
        """피치 시프트 (시간 보존)"""
        return librosa.effects.pitch_shift(audio, sr=self.sr, n_steps=n_steps)
    
    def volume_adjust(self, audio: np.ndarray, gain: float) -> np.ndarray:
        """볼륨 조절"""
        return audio * gain
    
    def time_shift(self, audio: np.ndarray, shift_sec: float) -> np.ndarray:
        """시간 시프트 (순환)"""
        shift_samples = int(shift_sec * self.sr)
        return np.roll(audio, shift_samples)
    
    def add_reverb(self, audio: np.ndarray, room_size: float, damping: float) -> np.ndarray:
        """간단한 리버브 (지연선 기반)"""
        delay_samples = int(0.05 * self.sr * room_size)  # 50ms * room_size
        decay = 1.0 - damping
        
        # 간단한 지연선 리버브
        reverb = np.zeros_like(audio)
        for i in range(3):  # 3개 반사
            delay = delay_samples * (i + 1)
            gain = decay ** (i + 1) * 0.3
            if delay < len(audio):
                reverb[delay:] += audio[:-delay] * gain
        
        # 원본 + 리버브 믹스 (드라이/웻 7:3)
        return 0.7 * audio + 0.3 * reverb
    
    def normalize_length(self, audio: np.ndarray) -> np.ndarray:
        """길이 정규화 (자르기/패딩)"""
        if len(audio) > self.target_samples:
            return audio[:self.target_samples]
        elif len(audio) < self.target_samples:
            return np.pad(audio, (0, self.target_samples - len(audio)))
        return audio
    
    def augment(self, audio: np.ndarray, n_augment: int = None) -> List[np.ndarray]:
        """단일 오디오 → N개 증강 버전 생성"""
        if n_augment is None:
            n_augment = self.config.n_augment
        
        results = [audio.copy()]  # 원본 포함
        
        for _ in range(n_augment - 1):
            aug = audio.copy()
            
            # 1. 시간 스트레칭
            if random.random() < self.config.time_stretch_prob:
                rate = random.uniform(*self.config.time_stretch_range)
                aug = self.time_stretch(aug, rate)
            
            # 2. 피치 시프트
            if random.random() < self.config.pitch_shift_prob:
                n_steps = random.uniform(*self.config.pitch_shift_range)
                aug = self.pitch_shift(aug, n_steps)
            
            # 3. 볼륨 조절
            if random.random() < self.config.volume_prob:
                gain = random.uniform(*self.config.volume_range)
                aug = self.volume_adjust(aug, gain)
            
            # 4. 시간 시프트
            if random.random() < self.config.time_shift_prob:
                shift = random.uniform(-self.config.time_shift_max_sec, self.config.time_shift_max_sec)
                aug = self.time_shift(aug, shift)
            
            # 5. 배경 노이즈
            if random.random() < self.config.noise_prob:
                snr = random.uniform(*self.config.noise_snr_range)
                noise_type = random.choice(self.config.noise_types)
                aug = self.add_noise(aug, snr, noise_type)
            
            # 6. 리버브
            if random.random() < self.config.reverb_prob:
                room_size = random.uniform(*self.config.reverb_room_size)
                damping = random.uniform(*self.config.reverb_damping)
                aug = self.add_reverb(aug, room_size, damping)
            
            # 길이 정규화
            aug = self.normalize_length(aug)
            results.append(aug)
        
        return results
    
    def process_file(self, input_path: str, output_dir: str, n_augment: int = None) -> List[str]:
        """단일 파일 증강 → 저장"""
        audio, _ = librosa.load(input_path, sr=self.sr)
        augmented = self.augment(audio, n_augment)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        input_stem = Path(input_path).stem
        saved_files = []
        
        for i, aug_audio in enumerate(augmented):
            if i == 0:
                out_name = f"{input_stem}.wav"
            else:
                out_name = f"{input_stem}_aug{i}.wav"
            
            out_file = output_path / out_name
            sf.write(out_file, aug_audio, self.sr)
            saved_files.append(str(out_file))
        
        return saved_files
    
    def process_directory(
        self,
        input_dir: str,
        output_dir: str,
        metadata_file: str = None,
        n_augment: int = None
    ) -> List[dict]:
        """디렉토리 전체 증강 (+ 메타데이터 생성)"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        all_metadata = []
        
        # 메타데이터 로드 (있는 경우)
        meta_map = {}
        if metadata_file and Path(metadata_file).exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                for line in f:
                    meta = json.loads(line.strip())
                    meta_map[meta['file']] = meta
        
        wav_files = list(input_path.glob("*.wav"))
        print(f"증강 시작: {len(wav_files)}개 파일 → 각각 {self.config.n_augment}배")
        
        for wav_file in wav_files:
            # 원본 메타데이터
            orig_meta = meta_map.get(wav_file.name, {})
            
            saved = self.process_file(str(wav_file), output_dir, n_augment)
            
            for i, saved_file in enumerate(saved):
                rel_path = Path(saved_file).relative_to(output_path)
                meta = orig_meta.copy()
                meta['file'] = str(rel_path)
                if i > 0:
                    meta['augmented'] = True
                    meta['aug_index'] = i
                else:
                    meta['augmented'] = False
                all_metadata.append(meta)
        
        # 메타데이터 저장
        if metadata_file:
            output_meta = Path(metadata_file)
            output_meta.parent.mkdir(parents=True, exist_ok=True)
            with open(output_meta, 'w', encoding='utf-8') as f:
                for meta in all_metadata:
                    f.write(json.dumps(meta, ensure_ascii=False) + '\n')
        
        print(f"증강 완료: {len(all_metadata)}개 샘플 → {output_dir}")
        return all_metadata


def create_augmenter(
    n_augment: int = 10,
    noise_prob: float = 0.7,
    time_stretch_prob: float = 0.5,
    pitch_shift_prob: float = 0.5,
    **kwargs
) -> AudioAugmenter:
    """편의 함수: 증강기 생성"""
    config = AugmentConfig(
        n_augment=n_augment,
        noise_prob=noise_prob,
        time_stretch_prob=time_stretch_prob,
        pitch_shift_prob=pitch_shift_prob,
        **kwargs
    )
    return AudioAugmenter(config)


def quick_augment(
    input_dir: str,
    output_dir: str,
    n_augment: int = 10,
    metadata_file: str = None
):
    """빠른 증강 실행"""
    augmenter = create_augmenter(n_augment=n_augment)
    augmenter.process_directory(input_dir, output_dir, metadata_file, n_augment)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="KWS 데이터 증강")
    parser.add_argument("--input", required=True, help="입력 디렉토리")
    parser.add_argument("--output", required=True, help="출력 디렉토리")
    parser.add_argument("--metadata", help="메타데이터 파일 (JSONL)")
    parser.add_argument("--n-augment", type=int, default=10, help="증강 배수")
    parser.add_argument("--noise-prob", type=float, default=0.7)
    parser.add_argument("--stretch-prob", type=float, default=0.5)
    parser.add_argument("--pitch-prob", type=float, default=0.5)
    
    args = parser.parse_args()
    
    augmenter = create_augmenter(
        n_augment=args.n_augment,
        noise_prob=args.noise_prob,
        time_stretch_prob=args.stretch_prob,
        pitch_shift_prob=args.pitch_prob
    )
    
    augmenter.process_directory(args.input, args.output, args.metadata, args.n_augment)