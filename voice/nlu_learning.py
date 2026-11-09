"""
Natural Language Understanding Learning Pipeline
- NLU 파싱 결과 + 사용자 피드백 수집
- Few-shot 프롬프트 구성 (학습 데이터 → 프롬프트 예시)
- NLU 모델 파인튜닝 (LLM LoRA / 분류기)
- 온라인/증분 학습 지원
- 활성 학습(Active Learning): 불확실한 샘플 우선 라벨링
"""

import os
import json
import logging
import uuid
import asyncio
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """사용자 피드백 유형"""

    CORRECT = "correct"  # 파싱 맞음
    INCORRECT = "incorrect"  # 파싱 틀림 (정답 제공)
    AMBIGUOUS = "ambiguous"  # 애매함
    PARTIAL = "partial"  # 부분적으로 맞음


class NLUModelType(Enum):
    """NLU 모델 타입"""

    RULE_BASED = "rule_based"  # 현재 규칙 기반
    LLM_FEWSHOT = "llm_fewshot"  # LLM + Few-shot 프롬프트
    LLM_LORA = "llm_lora"  # LLM LoRA 파인튜닝
    CLASSIFIER = "classifier"  # 경량 분류기 (DistilBERT 등)


@dataclass
class NLUTrainingSample:
    """NLU 학습 샘플"""

    sample_id: str
    utterance: str  # 사용자 발화
    stt_confidence: float  # STT 신뢰도
    parsed_intent: Dict  # 파싱된 의도 (UnifiedCommand dict)
    ground_truth_intent: Optional[Dict] = None  # 정답 의도 (피드백 시)
    feedback_type: Optional[FeedbackType] = None
    feedback_text: str = ""  # 사용자 수정 텍스트
    context: Dict = field(default_factory=dict)  # 컨텍스트 (활성 타겟, 이전 명령 등)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model_version: str = "1.0"  # 파싱에 사용된 모델 버전
    is_training: bool = False  # 학습 데이터로 사용 여부

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NLUTrainingSample":
        return cls(**data)


@dataclass
class NLUModelConfig:
    """NLU 모델 설정"""

    model_type: NLUModelType = NLUModelType.LLM_FEWSHOT
    base_model: str = "microsoft/Phi-3-mini-4k-instruct"  # 또는 Llama-3.1-8B
    lora_rank: int = 16
    lora_alpha: int = 32
    max_examples_in_prompt: int = 10
    confidence_threshold: float = 0.7  # 이하이면 active learning 대상
    min_training_samples: int = 50  # 파인튜닝 최소 샘플 수

    # 분류기용 (경량 모델)
    classifier_model: str = "distilbert-base-multilingual-cased"
    classifier_max_length: int = 128

    # 저장 경로
    data_dir: str = "~/models/nlu_learning"
    model_dir: str = "~/models/nlu_models"

    def __post_init__(self):
        self.data_dir = str(Path(self.data_dir).expanduser())
        self.model_dir = str(Path(self.model_dir).expanduser())
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.model_dir).mkdir(parents=True, exist_ok=True)


class NLUDataCollector:
    """
    NLU 학습 데이터 수집기
    - 모든 파싱 요청/결과 로깅
    - 사용자 피드백 수집 API
    - Active Learning: 불확실한 샘플 선별
    """

    def __init__(self, config: NLUModelConfig):
        self.config = config
        self.samples_file = Path(config.data_dir) / "nlu_samples.jsonl"
        self.feedback_file = Path(config.data_dir) / "nlu_feedback.jsonl"
        self.stats_file = Path(config.data_dir) / "nlu_stats.json"
        self._load_stats()

    def _load_stats(self):
        self.stats = {
            "total_parsed": 0,
            "total_feedback": 0,
            "correct_feedback": 0,
            "incorrect_feedback": 0,
            "by_action": defaultdict(int),
            "by_feedback_type": defaultdict(int),
        }
        if self.stats_file.exists():
            with open(self.stats_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self.stats.update(loaded)
                # defaultdict 복원
                self.stats["by_action"] = defaultdict(int, loaded.get("by_action", {}))
                self.stats["by_feedback_type"] = defaultdict(
                    int, loaded.get("by_feedback_type", {})
                )

    def _save_stats(self):
        save_data = dict(self.stats)
        save_data["by_action"] = dict(self.stats["by_action"])
        save_data["by_feedback_type"] = dict(self.stats["by_feedback_type"])
        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

    def log_parsing(
        self,
        utterance: str,
        stt_confidence: float,
        parsed_intent: Dict,
        context: Dict = None,
        model_version: str = "1.0",
    ) -> str:
        """파싱 결과 로깅 (자동 수집)"""
        sample = NLUTrainingSample(
            sample_id=str(uuid.uuid4())[:8],
            utterance=utterance,
            stt_confidence=stt_confidence,
            parsed_intent=parsed_intent,
            context=context or {},
            model_version=model_version,
        )

        with open(self.samples_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample.to_dict(), ensure_ascii=False) + "\n")

        self.stats["total_parsed"] += 1
        action = parsed_intent.get("action", "UNKNOWN")
        self.stats["by_action"][action] += 1
        self._save_stats()

        return sample.sample_id

    def add_feedback(
        self,
        sample_id: str,
        feedback_type: FeedbackType,
        ground_truth_intent: Dict = None,
        feedback_text: str = "",
    ) -> bool:
        """사용자 피드백 추가"""
        # 원본 샘플 찾기
        sample = self._find_sample(sample_id)
        if not sample:
            logger.warning(f"샘플을 찾을 수 없음: {sample_id}")
            return False

        # 피드백 기록
        sample.feedback_type = feedback_type
        sample.feedback_text = feedback_text
        if ground_truth_intent:
            sample.ground_truth_intent = ground_truth_intent
            sample.is_training = True  # 학습 데이터로 사용

        feedback_entry = {
            "sample_id": sample_id,
            "feedback_type": feedback_type.value,
            "ground_truth_intent": ground_truth_intent,
            "feedback_text": feedback_text,
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")

        # 원본 샘플 파일에 is_training 업데이트 (재기록 필요)
        self._update_sample_training_flag(sample_id, True)

        self.stats["total_feedback"] += 1
        self.stats["by_feedback_type"][feedback_type.value] += 1
        if feedback_type == FeedbackType.CORRECT:
            self.stats["correct_feedback"] += 1
        elif feedback_type == FeedbackType.INCORRECT:
            self.stats["incorrect_feedback"] += 1
        self._save_stats()

        logger.info(f"피드백 기록: {sample_id} - {feedback_type.value}")
        return True

    def _find_sample(self, sample_id: str) -> Optional[NLUTrainingSample]:
        if not self.samples_file.exists():
            return None
        with open(self.samples_file, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                if data.get("sample_id") == sample_id:
                    return NLUTrainingSample.from_dict(data)
        return None

    def _update_sample_training_flag(self, sample_id: str, flag: bool):
        """샘플 파일의 is_training 플래그 업데이트 (전체 재기록)"""
        samples = []
        if self.samples_file.exists():
            with open(self.samples_file, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line.strip())
                    if data.get("sample_id") == sample_id:
                        data["is_training"] = flag
                    samples.append(data)

        with open(self.samples_file, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

    def get_training_data(self, min_confidence: float = 0.0) -> List[NLUTrainingSample]:
        """학습용 데이터 로드 (피드백으로 검증된 것들)"""
        training_data = []
        if not self.samples_file.exists():
            return training_data

        with open(self.samples_file, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                if data.get("is_training", False) and data.get("ground_truth_intent"):
                    if data.get("stt_confidence", 1.0) >= min_confidence:
                        training_data.append(NLUTrainingSample.from_dict(data))

        logger.info(f"학습 데이터 로드: {len(training_data)}개")
        return training_data

    def get_active_learning_candidates(
        self,
        count: int = 20,
        confidence_threshold: float = None,
    ) -> List[NLUTrainingSample]:
        """Active Learning: 불확실한 샘플 선별 (라벨링 우선순위)"""
        if confidence_threshold is None:
            confidence_threshold = self.config.confidence_threshold

        candidates = []
        if not self.samples_file.exists():
            return candidates

        with open(self.samples_file, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                # 피드백 없음 + 낮은 신뢰도 + 학습 데이터 아님
                if (
                    not data.get("feedback_type")
                    and not data.get("is_training", False)
                    and data.get("stt_confidence", 1.0) < confidence_threshold
                ):
                    candidates.append(NLUTrainingSample.from_dict(data))

        # 신뢰도 낮은 순 정렬
        candidates.sort(key=lambda x: x.stt_confidence)
        return candidates[:count]

    def get_stats(self) -> Dict:
        return dict(self.stats)


class FewShotPromptBuilder:
    """
    Few-shot 프롬프트 구성기
    - 학습 데이터에서 다양하고 품질 좋은 예시 선별
    - 동작별, 컨텍스트별 균형 있게 선택
    - 프롬프트 템플릿 관리
    """

    SYSTEM_PROMPT = """당신은 드론/로봇/하이브리드 제어용 NLU 파서입니다.
사용자의 한국어 음성 텍스트를 분석하여 지정된 JSON 스키마로만 응답하십시오.

[액션 목록]
- ESTOP: 비상 정지 (최우선)
- ARM: 시동
- TAKEOFF: 이륙 (z_m: 고도)
- LAND: 착륙
- HOLD: 정지/호버링
- MOVE_VEL: 속도 제어 (vx_mps, vy_mps, vz_mps, yaw_rate_radps)
- RTL: 복귀
- SET_MODE: 모드 전환 (params.mode: CRUISE/FPV_AGILE/DIVE_ATTACK/DECEPTION)
- DIVE_ATTACK: 다이브 어택 (params.target_alt, params.angle)
- DECEPTION_START: 기만 시작 (params.pattern, params.duration)
- DECEPTION_STOP: 기만 중지
- NAV_TO_POSE: 좌표 이동 (x_m, y_m)

[파라미터 추출 규칙]
- 숫자는 미터/초/도 단위로 추출
- "전진/앞으로" → vx_mps 양수
- "후진/뒤로" → vx_mps 음수
- "좌측/왼쪽" → vy_mps 양수  
- "우측/오른쪽" → vy_mps 음수
- "상승/올라" → vz_mps 양수
- "하강/내려" → vz_mps 음수
- "좌회전" → yaw_rate_radps 양수
- "우회전" → yaw_rate_radps 음수

응답은 반드시 JSON만 출력하십시오."""

    def __init__(self, config: NLUModelConfig):
        self.config = config
        self.examples: List[NLUTrainingSample] = []

    def update_examples(self, samples: List[NLUTrainingSample]):
        """학습 예시 업데이트 (다양성 확보)"""
        # 액션별로 그룹화
        by_action = defaultdict(list)
        for s in samples:
            if s.ground_truth_intent:
                action = s.ground_truth_intent.get("action", "UNKNOWN")
                by_action[action].append(s)

        # 각 액션당 최대 N개씩 선택 (다양성)
        max_per_action = max(
            1, self.config.max_examples_in_prompt // max(len(by_action), 1)
        )
        selected = []

        for action, action_samples in by_action.items():
            # 신뢰도 높은 순 정렬
            action_samples.sort(key=lambda x: x.stt_confidence, reverse=True)
            selected.extend(action_samples[:max_per_action])

        # 전체 개수 제한
        if len(selected) > self.config.max_examples_in_prompt:
            selected = selected[: self.config.max_examples_in_prompt]

        self.examples = selected
        logger.info(
            f"Few-shot 예시 업데이트: {len(self.examples)}개 (액션 {len(by_action)}종류)"
        )

    def build_prompt(self, user_utterance: str, active_target: str = "drone_1") -> str:
        """Few-shot 프롬프트 생성"""
        prompt_parts = [self.SYSTEM_PROMPT, "\n\n[예시]\n"]

        for i, ex in enumerate(self.examples, 1):
            gt = ex.ground_truth_intent
            prompt_parts.append(f"예시 {i}:")
            prompt_parts.append(f'  입력: "{ex.utterance}"')
            prompt_parts.append(f"  출력: {json.dumps(gt, ensure_ascii=False)}")
            prompt_parts.append("")

        prompt_parts.append(f"[실제 입력]")
        prompt_parts.append(f"기본 타겟: {active_target}")
        prompt_parts.append(f'명령: "{user_utterance}"')
        prompt_parts.append("\n출력:")

        return "\n".join(prompt_parts)

    def get_example_count(self) -> int:
        return len(self.examples)


class NLULearningPipeline:
    """
    NLU 지속적 학습 파이프라인
    - 데이터 수집 → Few-shot 업데이트 → 주기적 파인튜닝 → 배포
    """

    def __init__(self, config: NLUModelConfig = None):
        self.config = config or NLUModelConfig()
        self.collector = NLUDataCollector(self.config)
        self.prompt_builder = FewShotPromptBuilder(self.config)
        self.current_model_version = "1.0"
        self.last_training_time = None
        self.training_in_progress = False

    def on_parsing_result(
        self,
        utterance: str,
        stt_confidence: float,
        parsed_intent: Dict,
        context: Dict = None,
    ) -> str:
        """파싱 결과 콜백 (자동 데이터 수집)"""
        return self.collector.log_parsing(
            utterance=utterance,
            stt_confidence=stt_confidence,
            parsed_intent=parsed_intent,
            context=context,
            model_version=self.current_model_version,
        )

    def on_user_feedback(
        self,
        sample_id: str,
        is_correct: bool,
        correct_intent: Dict = None,
        feedback_text: str = "",
    ) -> bool:
        """사용자 피드백 콜백"""
        if is_correct:
            return self.collector.add_feedback(
                sample_id=sample_id,
                feedback_type=FeedbackType.CORRECT,
                ground_truth_intent=correct_intent,
                feedback_text=feedback_text,
            )
        else:
            return self.collector.add_feedback(
                sample_id=sample_id,
                feedback_type=FeedbackType.INCORRECT,
                ground_truth_intent=correct_intent,
                feedback_text=feedback_text,
            )

    def update_fewshot_prompt(self):
        """Few-shot 프롬프트 예시 업데이트"""
        training_data = self.collector.get_training_data()
        self.prompt_builder.update_examples(training_data)

    def get_fewshot_prompt(self, utterance: str, active_target: str = "drone_1") -> str:
        """현재 Few-shot 프롬프트 반환"""
        return self.prompt_builder.build_prompt(utterance, active_target)

    def should_retrain(self) -> bool:
        """파인튜닝 필요 여부 판단"""
        training_data = self.collector.get_training_data()
        return len(training_data) >= self.config.min_training_samples

    async def finetune_nlu_model(self) -> Optional[str]:
        """NLU 모델 파인튜닝 실행 (LLM LoRA)"""
        if self.training_in_progress:
            logger.warning("이미 학습 진행 중")
            return None

        if not self.should_retrain():
            logger.info(
                f"학습 데이터 부족: {len(self.collector.get_training_data())} < {self.config.min_training_samples}"
            )
            return None

        self.training_in_progress = True
        logger.info("NLU 모델 파인튜닝 시작...")

        try:
            # 실제 구현: transformers + peft로 LLM LoRA 학습
            # 여기서는 경로만 반환 (실제 학습은 별도 스크립트 권장)
            model_path = await self._run_lora_training()

            if model_path:
                self.current_model_version = (
                    f"v{datetime.now().strftime('%Y%m%d_%H%M')}"
                )
                self.last_training_time = datetime.now().isoformat()
                logger.info(
                    f"NLU 모델 학습 완료: {model_path} (버전: {self.current_model_version})"
                )
                return model_path

        except Exception as e:
            logger.error(f"NLU 학습 실패: {e}")
        finally:
            self.training_in_progress = False

        return None

    async def _run_lora_training(self) -> Optional[str]:
        """LoRA 학습 실행 (실제로는 별도 프로세스 권장)"""
        training_data = self.collector.get_training_data()

        # 학습 데이터 JSONL 형식으로 저장
        train_file = (
            Path(self.config.data_dir) / f"nlu_train_{self.current_model_version}.jsonl"
        )
        with open(train_file, "w", encoding="utf-8") as f:
            for sample in training_data:
                # 채팅 형식으로 변환
                messages = [
                    {"role": "system", "content": self.prompt_builder.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"기본 타겟: {sample.context.get('active_target', 'drone_1')}\n명령: \"{sample.utterance}\"",
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            sample.ground_truth_intent, ensure_ascii=False
                        ),
                    },
                ]
                f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")

        logger.info(f"학습 데이터 저장: {train_file} ({len(training_data)}개)")

        # 실제 학습 명령 (주석 - 별도 실행 권장)
        """
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model
        from trl import SFTTrainer
        
        model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        tokenizer = AutoTokenizer.from_pretrained(self.config.base_model)
        tokenizer.pad_token = tokenizer.eos_token
        
        lora_config = LoraConfig(
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            lora_dropout=0.1,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        
        trainer = SFTTrainer(
            model=model,
            train_dataset=load_dataset("json", data_files=str(train_file))["train"],
            tokenizer=tokenizer,
            max_seq_length=512,
            args=TrainingArguments(
                output_dir=f"{self.config.model_dir}/nlu_lora_{self.current_model_version}",
                num_train_epochs=3,
                per_device_train_batch_size=2,
                learning_rate=2e-4,
                fp16=True,
            ),
        )
        trainer.train()
        model.save_pretrained(f"{self.config.model_dir}/nlu_lora_{self.current_model_version}")
        """

        # 플레이스홀더: 학습된 모델 경로 반환
        model_path = f"{self.config.model_dir}/nlu_lora_{self.current_model_version}"
        Path(model_path).mkdir(parents=True, exist_ok=True)
        (Path(model_path) / "adapter_config.json").write_text(
            json.dumps(
                {
                    "base_model": self.config.base_model,
                    "lora_rank": self.config.lora_rank,
                    "lora_alpha": self.config.lora_alpha,
                }
            )
        )

        return model_path

    def get_active_learning_tasks(self, count: int = 10) -> List[Dict]:
        """Active Learning: 라벨링이 필요한 샘플 반환"""
        candidates = self.collector.get_active_learning_candidates(count=count)
        return [
            {
                "sample_id": s.sample_id,
                "utterance": s.utterance,
                "stt_confidence": s.stt_confidence,
                "current_parsing": s.parsed_intent,
                "context": s.context,
            }
            for s in candidates
        ]

    def get_pipeline_status(self) -> Dict:
        return {
            "model_version": self.current_model_version,
            "model_type": self.config.model_type.value,
            "fewshot_examples": self.prompt_builder.get_example_count(),
            "training_in_progress": self.training_in_progress,
            "last_training": self.last_training_time,
            "should_retrain": self.should_retrain(),
            "collector_stats": self.collector.get_stats(),
        }


# 편의 함수
def create_nlu_learning_pipeline(config: NLUModelConfig = None) -> NLULearningPipeline:
    return NLULearningPipeline(config)


# VoiceIntentParser와 연동용 어댑터
class LearningVoiceIntentParser:
    """
    학습 기능이 통합된 VoiceIntentParser 래퍼
    - 파싱 시마다 데이터 수집
    - Few-shot 프롬프트 사용
    - 피드백 API 제공
    """

    def __init__(
        self,
        base_parser,  # 기존 VoiceIntentParser 인스턴스
        learning_pipeline: NLULearningPipeline,
    ):
        self.base_parser = base_parser
        self.learning = learning_pipeline
        self.pending_samples: Dict[str, Dict] = {}  # sample_id -> {utterance, context}

    async def parse_to_command(
        self,
        text: str,
        stt_confidence: float,
        active_target: str = "drone_1",
        speaker_id: str = None,
    ):
        # 1. 기본 파싱 수행
        context = {"active_target": active_target, "speaker_id": speaker_id}
        command = await self.base_parser.parse_to_command(
            text, stt_confidence, active_target, speaker_id
        )

        # 2. 학습 데이터 수집
        sample_id = self.learning.on_parsing_result(
            utterance=text,
            stt_confidence=stt_confidence,
            parsed_intent=command.model_dump(),
            context=context,
        )

        # 3. Few-shot 프롬프트로 재파싱 (LLM 모드일 때)
        if self.learning.config.model_type in [
            NLUModelType.LLM_FEWSHOT,
            NLUModelType.LLM_LORA,
        ]:
            fewshot_prompt = self.learning.get_fewshot_prompt(text, active_target)
            # LLM 클라이언트가 있으면 few-shot으로 재시도
            if self.base_parser.llm_client:
                try:
                    # TODO: few-shot 프롬프트로 LLM 호출
                    pass
                except Exception as e:
                    logger.warning(f"Few-shot 파싱 실패, 기본 결과 사용: {e}")

        # sample_id를 command에 저장 (피드백용)
        command.sample_id = sample_id
        self.pending_samples[sample_id] = {
            "utterance": text,
            "command": command,
            "context": context,
        }

        return command

    def submit_feedback(self, sample_id: str, is_correct: bool, correct_text: str = ""):
        """사용자 피드백 제출"""
        if sample_id in self.pending_samples:
            pending = self.pending_samples[sample_id]
            correct_intent = None

            if not is_correct and correct_text:
                # 정답 텍스트로 의도 파싱 시도 (또는 수동 입력)
                # 여기서는 간단히 처리
                pass

            success = self.learning.on_user_feedback(
                sample_id=sample_id,
                is_correct=is_correct,
                correct_intent=correct_intent,
                feedback_text=correct_text,
            )

            if success:
                # Few-shot 프롬프트 업데이트
                self.learning.update_fewshot_prompt()
                del self.pending_samples[sample_id]

            return success
        return False

    def get_learning_status(self) -> Dict:
        return self.learning.get_pipeline_status()


# 사용 예시
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 설정
    config = NLUModelConfig(
        model_type=NLUModelType.LLM_FEWSHOT,
        base_model="microsoft/Phi-3-mini-4k-instruct",
        max_examples_in_prompt=8,
        min_training_samples=30,
    )

    # 파이프라인 생성
    pipeline = create_nlu_learning_pipeline(config)

    # 시뮬레이션: 파싱 결과 수집
    sample_id = pipeline.on_parsing_result(
        utterance="드론 5미터 이륙해",
        stt_confidence=0.95,
        parsed_intent={"action": "TAKEOFF", "target_id": "drone_1", "z_m": 5.0},
        context={"active_target": "drone_1"},
    )
    print(f"수집된 샘플: {sample_id}")

    # 사용자 피드백 (정답)
    pipeline.on_user_feedback(sample_id, is_correct=True)
    print("피드백: 올바름")

    # 오파싱 시뮬레이션
    sample_id2 = pipeline.on_parsing_result(
        utterance="하이브리드 드론 다이브 어택 100미터",
        stt_confidence=0.85,
        parsed_intent={
            "action": "DIVE_ATTACK",
            "target_id": "drone_1",
            "params": {"target_alt": 100},
        },
        context={"active_target": "hybrid_drone_1"},
    )

    # 사용자 수정 피드백
    pipeline.on_user_feedback(
        sample_id2,
        is_correct=False,
        correct_intent={
            "action": "DIVE_ATTACK",
            "target_id": "hybrid_drone_1",
            "params": {"target_alt": 100, "angle": 70},
        },
        feedback_text="타겟이 하이브리드 드론이고 각도 70도 추가",
    )
    print("피드백: 수정됨")

    # Few-shot 프롬프트 확인
    pipeline.learning.update_fewshot_prompt()
    prompt = pipeline.learning.get_fewshot_prompt("드론 앞으로 2미터", "drone_1")
    print(f"\nFew-shot 프롬프트 예시:\n{prompt[:500]}...")

    # 상태 확인
    print(f"\n파이프라인 상태: {pipeline.get_pipeline_status()}")
