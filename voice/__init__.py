"""
Voice Package - 음성 제어 모듈
선택적 의존성(faster-whisper, pvporcupine, torch 등)이 없을 때도 import 가능하도록 지연 로딩 사용
"""
from typing import TYPE_CHECKING

# 항상 사용 가능한 것들 (voice_command_engine만)
from voice.voice_command_engine import (
    FastPathEmergencyMatcher,
    LocalWhisperSTT,
    ParsedVoiceIntent,
    VoiceIntentParser,
    VoicePipelineConfig,
    VoiceCommandPipeline,
    create_voice_pipeline,
)

# 선택적 의존성이 필요한 모듈들은 지연 로딩
# import 시점에 실패하지 않도록 __getattr__ 사용

__all__ = [
    # voice_command_engine (핵심)
    "FastPathEmergencyMatcher",
    "LocalWhisperSTT",
    "ParsedVoiceIntent",
    "VoiceIntentParser",
    "VoicePipelineConfig",
    "VoiceCommandPipeline",
    "create_voice_pipeline",
    # speaker_adapter (faster-whisper, torch 필요)
    "SpeakerAdapter",
    "SpeakerProfile",
    "LoRAFineTuner",
    "AdaptiveWhisperModel",
    "create_speaker_adapter",
    "create_lora_finetuner",
    # wake_word_detector (pvporcupine, pyaudio 필요)
    "WakeWordDetector",
    "WakeWordConfig",
    "WakeWordEvent",
    "WakeWordState",
    "KoreanWakeWordDetector",
    "create_wake_word_detector",
    "create_korean_wake_word_detector",
    # voice_enrollment (독립적)
    "VoiceEnrollmentManager",
    "VoiceCommandMapping",
    "CommandCategory",
    "VoiceEnrollmentSession",
    "create_enrollment_manager",
    # finetune_pipeline (torch, transformers, peft, datasets, jiwer 필요)
    "FinetuneConfig",
    "STTLogCollector",
    "WhisperFinetuner",
    "CTranslate2Converter",
    "FinetunePipeline",
    "create_finetune_pipeline",
    "quick_finetune",
    # labeling_tool (datasets 필요)
    "STTLabelingTool",
    # nlu_learning (torch, transformers, peft 필요)
    "NLUModelConfig",
    "NLUModelType",
    "FeedbackType",
    "NLUTrainingSample",
    "NLUDataCollector",
    "FewShotPromptBuilder",
    "NLULearningPipeline",
    "LearningVoiceIntentParser",
    "create_nlu_learning_pipeline",
    # ultra_low_latency (faster-whisper, pvporcupine, torch 필요)
    "StreamingVAD",
    "FastWhisperSTT",
    "CommandCache",
    "PredictiveCommander",
    "UltraLowLatencyPipeline",
    "LatencyProfile",
    "PipelineStage",
    "create_ultra_low_latency_pipeline",
    # keyword_specs (독립적 - 핵심 스펙 정의)
    "KeywordSpec",
    "CommandPriority",
    "KEYWORD_SPECS",
    "get_all_specs",
    "get_specs_by_priority",
    "get_specs_by_target",
    "get_keywords_list",
    "get_phrases_for_keyword",
    "get_command_for_keyword",
    "export_for_training",
    # kws_data_collector (pyaudio 필요)
    "CollectionConfig",
    "SampleMetadata",
    "KWSDataCollector",
    "MultiSpeakerCollector",
    "quick_collect",
    # kws_augment (librosa, scipy 필요)
    "AugmentConfig",
    "AudioAugmenter",
    "create_augmenter",
    "quick_augment",
    # kws_train (torch, librosa, sklearn 필요)
    "train_kws",
    "evaluate_tflite",
    "test_tflite_inference_speed",
    "prepare_dataset",
    "build_ds_cnn_model",
    # kws_runtime (tflite_runtime, librosa 필요)
    "MFCCExtractor",
    "KWSRuntime",
    "KWSResult",
    "create_kws_runtime",
    "test_kws_runtime",
]

# 지연 로딩을 위한 모듈 매핑
_OPTIONAL_MODULES = {
    "speaker_adapter": [
        "SpeakerAdapter",
        "SpeakerProfile",
        "LoRAFineTuner",
        "AdaptiveWhisperModel",
        "create_speaker_adapter",
        "create_lora_finetuner",
    ],
    "wake_word_detector": [
        "WakeWordDetector",
        "WakeWordConfig",
        "WakeWordEvent",
        "WakeWordState",
        "KoreanWakeWordDetector",
        "create_wake_word_detector",
        "create_korean_wake_word_detector",
    ],
    "voice_enrollment": [
        "VoiceEnrollmentManager",
        "VoiceCommandMapping",
        "CommandCategory",
        "VoiceEnrollmentSession",
        "create_enrollment_manager",
    ],
    "finetune_pipeline": [
        "FinetuneConfig",
        "STTLogCollector",
        "WhisperFinetuner",
        "CTranslate2Converter",
        "FinetunePipeline",
        "create_finetune_pipeline",
        "quick_finetune",
    ],
    "labeling_tool": [
        "STTLabelingTool",
    ],
    "nlu_learning": [
        "NLUModelConfig",
        "NLUModelType",
        "FeedbackType",
        "NLUTrainingSample",
        "NLUDataCollector",
        "FewShotPromptBuilder",
        "NLULearningPipeline",
        "LearningVoiceIntentParser",
        "create_nlu_learning_pipeline",
    ],
    "ultra_low_latency": [
        "StreamingVAD",
        "FastWhisperSTT",
        "CommandCache",
        "PredictiveCommander",
        "UltraLowLatencyPipeline",
        "LatencyProfile",
        "PipelineStage",
        "create_ultra_low_latency_pipeline",
    ],
    "keyword_specs": [
        "KeywordSpec",
        "CommandPriority",
        "KEYWORD_SPECS",
        "get_all_specs",
        "get_specs_by_priority",
        "get_specs_by_target",
        "get_keywords_list",
        "get_phrases_for_keyword",
        "get_command_for_keyword",
        "export_for_training",
    ],
    "kws_data_collector": [
        "CollectionConfig",
        "SampleMetadata",
        "KWSDataCollector",
        "MultiSpeakerCollector",
        "quick_collect",
    ],
    "kws_augment": [
        "AugmentConfig",
        "AudioAugmenter",
        "create_augmenter",
        "quick_augment",
    ],
    "kws_train": [
        "train_kws",
        "evaluate_tflite",
        "test_tflite_inference_speed",
        "prepare_dataset",
        "build_ds_cnn_model",
    ],
    "kws_runtime": [
        "MFCCExtractor",
        "KWSRuntime",
        "KWSResult",
        "create_kws_runtime",
        "test_kws_runtime",
    ],
}

# 타입 체커용 (실제 import는 런타임에만)
if TYPE_CHECKING:
    from voice.speaker_adapter import (
        SpeakerAdapter,
        SpeakerProfile,
        LoRAFineTuner,
        AdaptiveWhisperModel,
        create_speaker_adapter,
        create_lora_finetuner,
    )
    from voice.wake_word_detector import (
        WakeWordDetector,
        WakeWordConfig,
        WakeWordEvent,
        WakeWordState,
        KoreanWakeWordDetector,
        create_wake_word_detector,
        create_korean_wake_word_detector,
    )
    from voice.voice_enrollment import (
        VoiceEnrollmentManager,
        VoiceCommandMapping,
        CommandCategory,
        VoiceEnrollmentSession,
        create_enrollment_manager,
    )
    from voice.finetune_pipeline import (
        FinetuneConfig,
        STTLogCollector,
        WhisperFinetuner,
        CTranslate2Converter,
        FinetunePipeline,
        create_finetune_pipeline,
        quick_finetune,
    )
    from voice.labeling_tool import STTLabelingTool
    from voice.nlu_learning import (
        NLUModelConfig,
        NLUModelType,
        FeedbackType,
        NLUTrainingSample,
        NLUDataCollector,
        FewShotPromptBuilder,
        NLULearningPipeline,
        LearningVoiceIntentParser,
        create_nlu_learning_pipeline,
    )
    from voice.ultra_low_latency import (
        StreamingVAD,
        FastWhisperSTT,
        CommandCache,
        PredictiveCommander,
        UltraLowLatencyPipeline,
        LatencyProfile,
        PipelineStage,
        create_ultra_low_latency_pipeline,
    )
    from voice.keyword_specs import (
        KeywordSpec,
        CommandPriority,
        KEYWORD_SPECS,
        get_all_specs,
        get_specs_by_priority,
        get_specs_by_target,
        get_keywords_list,
        get_phrases_for_keyword,
        get_command_for_keyword,
        export_for_training,
    )
    from voice.kws_data_collector import (
        CollectionConfig,
        SampleMetadata,
        KWSDataCollector,
        MultiSpeakerCollector,
        quick_collect,
    )
    from voice.kws_augment import (
        AugmentConfig,
        AudioAugmenter,
        create_augmenter,
        quick_augment,
    )
    from voice.kws_train import (
        train_kws,
        evaluate_tflite,
        test_tflite_inference_speed,
        prepare_dataset,
        build_ds_cnn_model,
    )
    from voice.kws_runtime import (
        MFCCExtractor,
        KWSRuntime,
        KWSResult,
        create_kws_runtime,
        test_kws_runtime,
    )


def __getattr__(name: str):
    """지연 로딩: 처음 접근할 때 모듈 import 시도"""
    for module_name, symbols in _OPTIONAL_MODULES.items():
        if name in symbols:
            try:
                module = __import__(f"voice.{module_name}", fromlist=[name])
                return getattr(module, name)
            except ImportError as e:
                raise AttributeError(
                    f"'{name}'을 사용하려면 선택적 의존성이 필요합니다: {e}"
                ) from e

    raise AttributeError(f"module 'voice' has no attribute '{name}'")


def __dir__():
    return __all__