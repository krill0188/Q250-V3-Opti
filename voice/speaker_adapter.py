"""
Speaker Adaptation Module for Whisper Fine-tuning
Uses faster-whisper with LoRA adapters for personalization
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import torch
import torchaudio
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


@dataclass
class SpeakerProfile:
    """화자 프로필 - 음성 특징 + 커스텀 명령어"""

    speaker_id: str
    name: str
    language: str = "ko"
    # LoRA 어댑터 경로 (fine-tuning 후 저장)
    adapter_path: Optional[str] = None
    # 커스텀 명령어 매핑: "내 드론" -> "drone_1"
    custom_commands: Dict[str, str] = field(default_factory=dict)
    # 웨이크 워드 감도 (0.0~1.0)
    wake_word_sensitivity: float = 0.5
    # 등록된 음성 샘플 메타데이터
    enrolled_samples: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "name": self.name,
            "language": self.language,
            "adapter_path": self.adapter_path,
            "custom_commands": self.custom_commands,
            "wake_word_sensitivity": self.wake_word_sensitivity,
            "enrolled_samples": self.enrolled_samples,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerProfile":
        return cls(**data)


class SpeakerAdapter:
    """
    화자 적응 관리자
    - 프로필 저장/로드
    - 음성 샘플 등록
    - LoRA 파인튜닝 트리거
    - 추론 시 어댑터 적용
    """

    def __init__(self, profiles_dir: str = "~/models/speaker_profiles"):
        self.profiles_dir = Path(profiles_dir).expanduser()
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, SpeakerProfile] = {}
        self.active_profile_id: Optional[str] = None
        self._load_all_profiles()

    def _load_all_profiles(self):
        """모든 프로필 로드"""
        for profile_file in self.profiles_dir.glob("*.json"):
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    profile = SpeakerProfile.from_dict(data)
                    self.profiles[profile.speaker_id] = profile
                    logger.info(
                        f"화자 프로필 로드: {profile.name} ({profile.speaker_id})"
                    )
            except Exception as e:
                logger.error(f"프로필 로드 실패 {profile_file}: {e}")

    def create_profile(
        self, speaker_id: str, name: str, language: str = "ko"
    ) -> SpeakerProfile:
        """새 화자 프로필 생성"""
        if speaker_id in self.profiles:
            raise ValueError(f"이미 존재하는 speaker_id: {speaker_id}")

        profile = SpeakerProfile(
            speaker_id=speaker_id,
            name=name,
            language=language,
        )
        self.profiles[speaker_id] = profile
        self._save_profile(profile)
        return profile

    def get_profile(self, speaker_id: str) -> Optional[SpeakerProfile]:
        return self.profiles.get(speaker_id)

    def set_active(self, speaker_id: str):
        if speaker_id not in self.profiles:
            raise ValueError(f"존재하지 않는 프로필: {speaker_id}")
        self.active_profile_id = speaker_id
        logger.info(f"활성 화자 변경: {self.profiles[speaker_id].name}")

    def get_active(self) -> Optional[SpeakerProfile]:
        if self.active_profile_id:
            return self.profiles.get(self.active_profile_id)
        return None

    def _save_profile(self, profile: SpeakerProfile):
        profile.updated_at = datetime.now().isoformat()
        profile_file = self.profiles_dir / f"{profile.speaker_id}.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    def add_custom_command(self, speaker_id: str, phrase: str, target: str):
        """커스텀 명령어 매핑 추가: "내 드론" -> "drone_1" """
        profile = self.get_profile(speaker_id)
        if not profile:
            raise ValueError(f"프로필 없음: {speaker_id}")
        profile.custom_commands[phrase] = target
        self._save_profile(profile)

    def enroll_audio_sample(
        self, speaker_id: str, audio_path: str, transcript: str = ""
    ) -> bool:
        """음성 샘플 등록 (파인튜닝용 데이터셋 구성)"""
        profile = self.get_profile(speaker_id)
        if not profile:
            raise ValueError(f"프로필 없음: {speaker_id}")

        sample_info = {
            "audio_path": audio_path,
            "transcript": transcript,
            "duration_sec": self._get_audio_duration(audio_path),
            "enrolled_at": datetime.now().isoformat(),
        }
        profile.enrolled_samples.append(sample_info)
        self._save_profile(profile)
        logger.info(f"음성 샘플 등록: {speaker_id} - {audio_path}")
        return True

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            info = torchaudio.info(audio_path)
            return info.num_frames / info.sample_rate
        except Exception:
            return 0.0

    def prepare_finetuning_dataset(self, speaker_id: str, output_dir: str) -> int:
        """파인튜닝용 데이터셋 준비 (Whisper fine-tuning 형식)"""
        profile = self.get_profile(speaker_id)
        if not profile:
            raise ValueError(f"프로필 없음: {speaker_id}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Whisper fine-tuning용 JSONL 형식
        dataset_file = output_path / "train.jsonl"
        count = 0

        with open(dataset_file, "w", encoding="utf-8") as f:
            for sample in profile.enrolled_samples:
                if sample.get("transcript"):
                    entry = {
                        "audio": sample["audio_path"],
                        "text": sample["transcript"],
                        "language": profile.language,
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1

        logger.info(f"파인튜닝 데이터셋 준비: {dataset_file} ({count} 샘플)")
        return count


class LoRAFineTuner:
    """
    Whisper LoRA 파인튜닝 (faster-whisper 호환)
    참고: faster-whisper는 CTranslate2 기반이라 직접 LoRA 학습은 제한적
    실제로는 transformers + peft로 학습 후 CTranslate2 변환 필요
    """

    def __init__(self, base_model: str = "large-v3", device: str = "auto"):
        self.base_model = base_model
        self.device = (
            device
            if device != "auto"
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        logger.info(f"LoRA 파인튜너 초기화: {base_model} on {self.device}")

    def train_lora(
        self,
        dataset_path: str,
        output_dir: str,
        speaker_id: str,
        epochs: int = 3,
        learning_rate: float = 1e-4,
        lora_rank: int = 16,
        lora_alpha: int = 32,
    ) -> str:
        """
        LoRA 학습 실행 (transformers + peft 사용)
        실제 구현시 별도 스크립트 권장 (GPU 메모리 많이 필요)
        """
        logger.warning("LoRA 파인튜닝은 별도 GPU 환경에서 실행 권장")
        logger.info(f"데이터셋: {dataset_path}, 출력: {output_dir}")

        # 실제 구현 예시 (주석처리 - 별도 실행 필요)
        """
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        from peft import LoraConfig, get_peft_model, TaskType
        import torch

        # 모델 로드
        model = WhisperForConditionalGeneration.from_pretrained(
            f"openai/whisper-{self.base_model}", torch_dtype=torch.float16
        ).to(self.device)
        processor = WhisperProcessor.from_pretrained(f"openai/whisper-{self.base_model}")

        # LoRA 설정
        lora_config = LoraConfig(
            r=lora_rank,
            lora_alpha=lora_alpha,
            target_modules=["q_proj", "v_proj", "k_proj", "out_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type=TaskType.SEQ_2_SEQ_LM,
        )
        model = get_peft_model(model, lora_config)

        # 데이터셋 로드 및 학습...
        # trainer = Trainer(...)
        # trainer.train()

        # 어댑터 저장
        model.save_pretrained(output_dir)
        processor.save_pretrained(output_dir)
        """

        adapter_path = str(Path(output_dir) / f"lora_{speaker_id}")
        Path(adapter_path).mkdir(parents=True, exist_ok=True)

        # 플레이스홀더 파일 생성
        (Path(adapter_path) / "adapter_config.json").write_text(
            json.dumps(
                {
                    "base_model": f"openai/whisper-{self.base_model}",
                    "lora_rank": lora_rank,
                    "lora_alpha": lora_alpha,
                    "target_modules": ["q_proj", "v_proj", "k_proj", "out_proj"],
                }
            )
        )

        logger.info(f"어댑터 경로 생성됨 (학습 필요): {adapter_path}")
        return adapter_path


class AdaptiveWhisperModel:
    """
    어댑터 적용된 Whisper 모델 래퍼
    faster-whisper는 CTranslate2 모델만 지원하므로
    어댑터 적용된 모델은 별도 변환 후 사용
    """

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "float16",
        adapter_path: Optional[str] = None,
    ):
        self.model_size = model_size
        self.adapter_path = adapter_path
        self.device = (
            device
            if device != "auto"
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.compute_type = compute_type

        # 기본 모델 로드
        self.model = WhisperModel(
            model_size, device=self.device, compute_type=compute_type
        )
        logger.info(f"Whisper 모델 로드: {model_size} ({self.device}, {compute_type})")

        # 어댑터가 있으면 로드 시도 (CT2 변환된 모델 필요)
        if adapter_path and Path(adapter_path).exists():
            logger.info(f"어댑터 경로 발견: {adapter_path}")
            # 실제로는 ct2 변환된 모델 경로를 model_size로 전달해야 함
            # self.model = WhisperModel(adapter_path, ...)

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        vad_filter: bool = True,
        **kwargs,
    ) -> Tuple[List, dict]:
        """음성 인식 실행"""
        segments, info = self.model.transcribe(
            audio_path, language=language, vad_filter=vad_filter, **kwargs
        )
        return list(segments), info._asdict()

    def transcribe_streaming(
        self,
        audio_chunks: List[bytes],
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ):
        """스트리밍 음성 인식 (실시간용)"""
        # faster-whisper는 스트리밍 직접 지원 안 함
        # 구현시 별도 버퍼링 로직 필요
        raise NotImplementedError("스트리밍은 별도 구현 필요")


# 편의 함수
def create_speaker_adapter(
    profiles_dir: str = "~/models/speaker_profiles",
) -> SpeakerAdapter:
    return SpeakerAdapter(profiles_dir)


def create_lora_finetuner(base_model: str = "large-v3") -> LoRAFineTuner:
    return LoRAFineTuner(base_model)
