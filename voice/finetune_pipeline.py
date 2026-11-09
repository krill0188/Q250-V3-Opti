"""
Whisper Fine-tuning Pipeline for Drone Voice Control
1. Dataset preparation from STT logs + ground truth
2. Whisper fine-tuning with LoRA (PEFT)
3. Convert to CTranslate2 format for faster-whisper
4. Deploy model path update
"""
import os
import json
import logging
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import defaultdict

import torch
import torchaudio
from datasets import Dataset, Audio
from transformers import (
    WhisperForConditionalGeneration,
    WhisperProcessor,
    WhisperFeatureExtractor,
    WhisperTokenizer,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)
from peft import LoraConfig, get_peft_model, TaskType, PeftModel

logger = logging.getLogger(__name__)


@dataclass
class FinetuneConfig:
    """파인튜닝 설정"""
    # 기본 모델
    base_model: str = "openai/whisper-large-v3"  # or medium, small, base, tiny
    language: str = "korean"
    task: str = "transcribe"

    # LoRA 설정
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    target_modules: List[str] = field(default_factory=lambda: ["q_proj", "v_proj", "k_proj", "out_proj"])

    # 학습 설정
    output_dir: str = "~/models/whisper-finetuned"
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation: int = 2
    learning_rate: float = 1e-4
    warmup_steps: int = 100
    max_steps: int = -1  # -1 = epoch 기반
    fp16: bool = True
    gradient_checkpointing: bool = True

    # 데이터 설정
    train_split: float = 0.9
    max_audio_length: float = 30.0  # 초
    sampling_rate: int = 16000

    # CTranslate2 변환 설정
    ct2_output_dir: str = "~/models/whisper-finetuned-ct2"
    ct2_quantization: str = "int8"  # int8, float16, int8_float16

    # 로깅
    logging_steps: int = 10
    save_steps: int = 500
    eval_steps: int = 500

    def __post_init__(self):
        self.output_dir = str(Path(self.output_dir).expanduser())
        self.ct2_output_dir = str(Path(self.ct2_output_dir).expanduser())
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.ct2_output_dir).mkdir(parents=True, exist_ok=True)


class STTLogCollector:
    """
    STT 로그 + 정답 텍스트 쌍 수집기
    - GCS 서버의 텔레메트리 로그에서 추출
    - 수동 라벨링 도구 연동
    """

    def __init__(self, log_dir: str = "~/models/stt_logs"):
        self.log_dir = Path(log_dir).expanduser()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pairs_file = self.log_dir / "stt_pairs.jsonl"
        self.pending_file = self.log_dir / "pending_review.jsonl"

    def add_pair(self, audio_path: str, stt_text: str, ground_truth: str, confidence: float, metadata: dict = None):
        """STT 결과와 정답 쌍 저장"""
        entry = {
            "audio_path": audio_path,
            "stt_text": stt_text,
            "ground_truth": ground_truth,
            "confidence": confidence,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "reviewed": False,
        }
        with open(self.pairs_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"STT 쌍 저장: {audio_path} | STT: '{stt_text}' | GT: '{ground_truth}'")

    def add_pending_review(self, audio_path: str, stt_text: str, confidence: float, metadata: dict = None):
        """검토 대기 항목 추가 (정답 텍스트 미확정)"""
        entry = {
            "audio_path": audio_path,
            "stt_text": stt_text,
            "confidence": confidence,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "status": "pending",  # pending, approved, rejected, corrected
        }
        with open(self.pending_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_training_data(self, min_confidence: float = 0.7) -> List[Dict]:
        """학습용 데이터 로드 (신뢰도 필터링 + 검토 완료만)"""
        data = []
        if self.pairs_file.exists():
            with open(self.pairs_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get("confidence", 0) >= min_confidence and entry.get("reviewed", False):
                        data.append({
                            "audio": entry["audio_path"],
                            "text": entry["ground_truth"],
                            "language": self._detect_language(entry["ground_truth"]),
                        })
        logger.info(f"학습 데이터 로드: {len(data)}개 (신뢰도 >= {min_confidence})")
        return data

    def load_pending_review(self) -> List[Dict]:
        """검토 대기 목록 로드"""
        pending = []
        if self.pending_file.exists():
            with open(self.pending_file, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get("status") == "pending":
                        pending.append(entry)
        return pending

    def approve_pending(self, index: int, ground_truth: str):
        """검토 완료 및 학습 데이터로 이동"""
        lines = []
        with open(self.pending_file, "r", encoding="utf-8") as f:
            lines = [json.loads(l.strip()) for l in f]

        if 0 <= index < len(lines):
            entry = lines[index]
            entry["status"] = "approved"
            entry["ground_truth"] = ground_truth
            entry["reviewed"] = True

            # 학습 데이터로 이동
            self.add_pair(
                entry["audio_path"],
                entry["stt_text"],
                ground_truth,
                entry["confidence"],
                entry["metadata"]
            )

            # 대기 목록에서 제거
            lines.pop(index)
            with open(self.pending_file, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(json.dumps(l, ensure_ascii=False) + "\n")

    def _detect_language(self, text: str) -> str:
        """간단한 언어 감지"""
        korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        return "korean" if korean_chars > english_chars else "english"


class WhisperFinetuner:
    """
    Whisper LoRA 파인튜닝
    - Hugging Face Transformers + PEFT 사용
    - CTranslate2 변환용 체크포인트 저장
    """

    def __init__(self, config: FinetuneConfig):
        self.config = config
        self.processor = None
        self.model = None
        self.trainer = None

    def prepare_model(self):
        """모델 및 프로세서 준비"""
        logger.info(f"베이스 모델 로드: {self.config.base_model}")

        self.processor = WhisperProcessor.from_pretrained(
            self.config.base_model,
            language=self.config.language,
            task=self.config.task,
        )

        self.model = WhisperForConditionalGeneration.from_pretrained(
            self.config.base_model,
            torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )

        # LoRA 설정
        lora_config = LoraConfig(
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=self.config.target_modules,
            bias="none",
            task_type=TaskType.SEQ_2_SEQ_LM,
        )

        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

        # 강제 디코더 ID 설정 (언어/태스크 토큰)
        self.model.config.forced_decoder_ids = self.processor.get_decoder_prompt_ids(
            language=self.config.language, task=self.config.task
        )
        self.model.config.suppress_tokens = []

    def prepare_dataset(self, train_data: List[Dict], eval_data: List[Dict] = None):
        """데이터셋 준비 및 전처리"""
        def preprocess_function(batch):
            # 오디오 로드 및 리샘플링
            audio_arrays = []
            for audio_path in batch["audio"]:
                waveform, sr = torchaudio.load(audio_path)
                if sr != self.config.sampling_rate:
                    resampler = torchaudio.transforms.Resample(sr, self.config.sampling_rate)
                    waveform = resampler(waveform)
                # 모노 채널로 변환
                if waveform.shape[0] > 1:
                    waveform = waveform.mean(dim=0, keepdim=True)
                audio_arrays.append(waveform.squeeze().numpy())

            # 특징 추출
            inputs = self.processor.feature_extractor(
                audio_arrays,
                sampling_rate=self.config.sampling_rate,
                return_tensors="pt",
                padding=True,
            )

            # 텍스트 토크나이징
            labels = self.processor.tokenizer(
                batch["text"],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=448,
            ).input_ids

            # 패딩 토큰을 -100으로 (loss 무시)
            labels[labels == self.processor.tokenizer.pad_token_id] = -100

            inputs["labels"] = labels
            return inputs

        train_dataset = Dataset.from_list(train_data).cast_column("audio", Audio(sampling_rate=self.config.sampling_rate))
        train_dataset = train_dataset.map(
            preprocess_function,
            batched=True,
            remove_columns=train_dataset.column_names,
            num_proc=1,
        )

        if eval_data:
            eval_dataset = Dataset.from_list(eval_data).cast_column("audio", Audio(sampling_rate=self.config.sampling_rate))
            eval_dataset = eval_dataset.map(
                preprocess_function,
                batched=True,
                remove_columns=eval_dataset.column_names,
                num_proc=1,
            )
        else:
            eval_dataset = None

        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset

        logger.info(f"데이터셋 준비 완료: Train={len(train_dataset)}, Eval={len(eval_dataset) if eval_dataset else 0}")

    def train(self):
        """학습 실행"""
        training_args = Seq2SeqTrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation,
            learning_rate=self.config.learning_rate,
            warmup_steps=self.config.warmup_steps,
            max_steps=self.config.max_steps,
            fp16=self.config.fp16,
            gradient_checkpointing=self.config.gradient_checkpointing,
            evaluation_strategy="steps" if self.eval_dataset else "no",
            eval_steps=self.config.eval_steps,
            save_steps=self.config.save_steps,
            logging_steps=self.config.logging_steps,
            save_total_limit=3,
            load_best_model_at_end=True if self.eval_dataset else False,
            metric_for_best_model="wer" if self.eval_dataset else None,
            greater_is_better=False,
            report_to="none",  # wandb 등 비활성화
            dataloader_num_workers=0,
            remove_unused_columns=False,
        )

        def compute_metrics(pred):
            from jiwer import wer
            pred_ids = pred.predictions
            label_ids = pred.label_ids
            label_ids[label_ids == -100] = self.processor.tokenizer.pad_token_id
            pred_str = self.processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
            label_str = self.processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
            return {"wer": wer(label_str, pred_str)}

        self.trainer = Seq2SeqTrainer(
            model=self.model,
            args=training_args,
            train_dataset=self.train_dataset,
            eval_dataset=self.eval_dataset,
            tokenizer=self.processor.feature_extractor,
            compute_metrics=compute_metrics if self.eval_dataset else None,
        )

        logger.info("파인튜닝 시작...")
        self.trainer.train()

        # 최종 모델 저장 (PEFT 어댑터만)
        self.model.save_pretrained(self.config.output_dir)
        self.processor.save_pretrained(self.config.output_dir)
        logger.info(f"어댑터 저장 완료: {self.config.output_dir}")

        return self.config.output_dir

    def merge_and_save_full_model(self, output_path: str = None):
        """LoRA 어댑터를 베이스 모델에 병합하여 전체 모델 저장"""
        if output_path is None:
            output_path = str(Path(self.config.output_dir) / "merged")

        logger.info(f"모델 병합 및 저장: {output_path}")

        # 베이스 모델 다시 로드
        base_model = WhisperForConditionalGeneration.from_pretrained(
            self.config.base_model,
            torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
        )

        # PEFT 어댑터 로드 및 병합
        peft_model = PeftModel.from_pretrained(base_model, self.config.output_dir)
        merged_model = peft_model.merge_and_unload()

        # 저장
        merged_model.save_pretrained(output_path)
        self.processor.save_pretrained(output_path)

        logger.info(f"병합된 모델 저장 완료: {output_path}")
        return output_path


class CTranslate2Converter:
    """
    Hugging Face 모델을 CTranslate2 형식으로 변환 (faster-whisper 호환)
    """

    def __init__(self, config: FinetuneConfig):
        self.config = config

    def convert(self, model_path: str = None, output_path: str = None) -> str:
        """ct2 변환 실행"""
        if model_path is None:
            model_path = str(Path(self.config.output_dir) / "merged")
        if output_path is None:
            output_path = self.config.ct2_output_dir

        model_path = Path(model_path).expanduser()
        output_path = Path(output_path).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"CTranslate2 변환: {model_path} -> {output_path}")

        # ct2 변환 명령 실행
        cmd = [
            "ct2-transformers-converter",
            "--model", str(model_path),
            "--output_dir", str(output_path),
            "--quantization", self.config.ct2_quantization,
            "--force",
        ]

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("CTranslate2 변환 성공")
            logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"CTranslate2 변환 실패: {e.stderr}")
            raise RuntimeError(f"ct2 변환 실패: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError("ct2-transformers-converter를 찾을 수 없습니다. `pip install ctranslate2` 실행 필요")

        # 변환 검증
        if not (output_path / "model.bin").exists():
            raise RuntimeError("변환된 모델 파일(model.bin)을 찾을 수 없습니다")

        logger.info(f"변환 완료: {output_path}")
        return str(output_path)

    def verify_model(self, model_path: str = None) -> bool:
        """변환된 모델 검증 (빠른 추론 테스트)"""
        if model_path is None:
            model_path = self.config.ct2_output_dir

        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(model_path, device="cpu", compute_type="int8")
            # 더미 오디오로 테스트
            import numpy as np
            dummy_audio = np.zeros(16000, dtype=np.float32)  # 1초 무음
            segments, _ = model.transcribe(dummy_audio, language="ko", beam_size=1)
            list(segments)  # 소비
            logger.info("모델 검증 성공")
            return True
        except Exception as e:
            logger.error(f"모델 검증 실패: {e}")
            return False


class FinetunePipeline:
    """
    전체 파인튜닝 파이프라인 오케스트레이터
    """

    def __init__(self, config: FinetuneConfig = None):
        self.config = config or FinetuneConfig()
        self.collector = STTLogCollector()
        self.finetuner = WhisperFinetuner(self.config)
        self.converter = CTranslate2Converter(self.config)

    def run_full_pipeline(
        self,
        min_confidence: float = 0.7,
        test_size: float = 0.1,
    ) -> str:
        """전체 파이프라인 실행"""
        logger.info("=" * 50)
        logger.info("Whisper 파인튜닝 파이프라인 시작")
        logger.info("=" * 50)

        # 1. 데이터 준비
        logger.info("1단계: 학습 데이터 준비")
        data = self.collector.load_training_data(min_confidence=min_confidence)
        if len(data) < 10:
            raise ValueError(f"학습 데이터 부족: {len(data)}개 (최소 10개 필요)")

        # Train/Eval 분할
        split_idx = int(len(data) * (1 - test_size))
        train_data = data[:split_idx]
        eval_data = data[split_idx:] if test_size > 0 else None

        logger.info(f"  Train: {len(train_data)}개, Eval: {len(eval_data) if eval_data else 0}개")

        # 2. 모델 준비
        logger.info("2단계: 모델 및 LoRA 준비")
        self.finetuner.prepare_model()

        # 3. 데이터셋 준비
        logger.info("3단계: 데이터셋 전처리")
        self.finetuner.prepare_dataset(train_data, eval_data)

        # 4. 학습 실행
        logger.info("4단계: LoRA 파인튜닝 실행")
        adapter_path = self.finetuner.train()

        # 5. 모델 병합
        logger.info("5단계: 어댑터 병합 (전체 모델 생성)")
        merged_path = self.finetuner.merge_and_save_full_model()

        # 6. CTranslate2 변환
        logger.info("6단계: CTranslate2 변환 (faster-whisper 호환)")
        ct2_path = self.converter.convert(merged_path)

        # 7. 검증
        logger.info("7단계: 변환된 모델 검증")
        if not self.converter.verify_model(ct2_path):
            raise RuntimeError("모델 검증 실패")

        logger.info("=" * 50)
        logger.info(f"파이프라인 완료! 최종 모델: {ct2_path}")
        logger.info("=" * 50)

        return ct2_path

    def deploy_model(self, ct2_path: str, target: str = "speaker_adapter"):
        """
        학습된 모델을 배포 위치에 연결
        - speaker_adapter: 화자별 어댑터 경로로 등록
        - voice_pipeline: 기본 STT 모델로 교체
        """
        if target == "speaker_adapter":
            # SpeakerAdapter 프로필에 어댑터 경로 업데이트
            from voice.speaker_adapter import SpeakerAdapter
            adapter = SpeakerAdapter()
            # 활성 화자 프로필에 어댑터 경로 설정
            if adapter.active_profile_id:
                profile = adapter.get_profile(adapter.active_profile_id)
                if profile:
                    profile.adapter_path = ct2_path
                    adapter._save_profile(profile)
                    logger.info(f"화자 프로필 어댑터 업데이트: {adapter.active_profile_id} -> {ct2_path}")

        elif target == "voice_pipeline":
            # VoicePipelineConfig 기본 모델 경로 업데이트
            # (실제로는 설정 파일이나 환경변수로 관리)
            import os
            os.environ["WHISPER_FINETUNED_MODEL"] = ct2_path
            logger.info(f"환경변수 설정: WHISPER_FINETUNED_MODEL={ct2_path}")

        logger.info(f"모델 배포 완료: {target}")


# 편의 함수
def create_finetune_pipeline(config: FinetuneConfig = None) -> FinetunePipeline:
    return FinetunePipeline(config)


def quick_finetune(
    audio_text_pairs: List[Tuple[str, str]],
    output_dir: str = "~/models/whisper-finetuned-quick",
    base_model: str = "openai/whisper-base",
    epochs: int = 2,
) -> str:
    """
    빠른 파인튜닝 (간단한 리스트 입력)
    audio_text_pairs: [(audio_path, ground_truth_text), ...]
    """
    config = FinetuneConfig(
        base_model=base_model,
        output_dir=output_dir,
        num_epochs=epochs,
        batch_size=2,
    )

    pipeline = FinetunePipeline(config)

    # 임시 데이터 저장
    for i, (audio_path, text) in enumerate(audio_text_pairs):
        pipeline.collector.add_pair(
            audio_path=audio_path,
            stt_text="",  # 빈 STT
            ground_truth=text,
            confidence=1.0,
            metadata={"source": "quick_finetune", "index": i}
        )

    return pipeline.run_full_pipeline(min_confidence=0.5, test_size=0.0)


# CLI 엔트리포인트
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Whisper Fine-tuning Pipeline for Drone Voice Control")
    parser.add_argument("--base-model", default="openai/whisper-large-v3", help="Base model name")
    parser.add_argument("--output-dir", default="~/models/whisper-finetuned", help="Output directory")
    parser.add_argument("--ct2-dir", default="~/models/whisper-finetuned-ct2", help="CTranslate2 output")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Min confidence for training data")
    parser.add_argument("--quantization", default="int8", choices=["int8", "float16", "int8_float16"], help="CT2 quantization")
    parser.add_argument("--skip-train", action="store_true", help="Skip training, only convert existing model")
    parser.add_argument("--model-path", help="Existing model path to convert (for --skip-train)")

    args = parser.parse_args()

    config = FinetuneConfig(
        base_model=args.base_model,
        output_dir=args.output_dir,
        ct2_output_dir=args.ct2_dir,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        lora_rank=args.lora_rank,
        ct2_quantization=args.quantization,
    )

    pipeline = FinetunePipeline(config)

    if args.skip_train and args.model_path:
        logger.info("학습 건너뛰기, 변환만 수행")
        merged_path = pipeline.finetuner.merge_and_save_full_model()
        ct2_path = pipeline.converter.convert(merged_path)
        pipeline.converter.verify_model(ct2_path)
        pipeline.deploy_model(ct2_path)
    else:
        ct2_path = pipeline.run_full_pipeline(min_confidence=args.min_confidence)
        pipeline.deploy_model(ct2_path)

    print(f"\n완료! faster-whisper 모델 경로: {ct2_path}")
    print(f"사용 예시: WhisperModel('{ct2_path}', device='cuda', compute_type='int8')")