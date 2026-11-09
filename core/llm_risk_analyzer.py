import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from llama_cpp import Llama

from core.log_aggregator import LogAggregator


@dataclass
class RiskAssessment:
    risk_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    risk_categories: List[str]
    confidence: float
    reasoning: str
    recommended_actions: List[Dict]
    auto_execute: List[str]
    inference_ms: float


# 시스템 프롬프트 (위험 분석용)
RISK_ANALYSIS_SYSTEM_PROMPT = """
당신은 드론/로봇 실시간 위험 분석 전문가입니다.
실시간 텔레메트리 로그를 분석하여 위험도를 4단계(CRITICAL/HIGH/MEDIUM/LOW)로 분류하세요.

## 입력 형식 (JSON 슬라이딩 윈도우)
{
  "window_ms": 2000,
  "samples": [
    {"t": 1234567890, "device": "drone_1", "type": "BATTERY", "voltage": 14.2, "current": 15.3, "remaining": 45},
    {"t": 1234567891, "device": "drone_1", "type": "ATTITUDE", "roll": 0.1, "pitch": -0.05, "yaw": 1.2},
    {"t": 1234567892, "device": "drone_1", "type": "GPS", "fix": 3, "sats": 8, "hdop": 1.2},
    {"t": 1234567893, "device": "drone_1", "type": "MOTOR", "temps": [45, 48, 52, 47], "rpms": [5200, 5180, 5210, 5190]},
    {"t": 1234567894, "device": "drone_1", "type": "FLIGHT_MODE", "mode": "DIVE_ATTACK", "armed": true}
  ]
}

## 출력 형식 (JSON만)
{
  "risk_level": "CRITICAL|HIGH|MEDIUM|LOW",
  "risk_categories": ["BATTERY_CRITICAL", "MOTOR_OVERHEAT"],
  "confidence": 0.92,
  "reasoning": "배터리 15% 미만 + 모터 2번 55도 초과 + 다이브 모드 중 = 즉시 착륙 필요",
  "recommended_actions": [
    {"action": "RTL", "priority": "IMMEDIATE", "reason": "배터리 임계치 도달"},
    {"action": "REDUCE_DIVE_ANGLE", "priority": "HIGH", "reason": "구조 하중 감소"}
  ],
  "auto_execute": ["RTL"]
}

## 위험 판단 기준
### CRITICAL (즉시 개입)
- 배터리 < 15% 또는 전압 셀 < 3.3V
- 모터 온도 > 70°C 또는 급상승 (>5°C/s)
- 자세 제어 상실 (롤/피치 > 45도 유지)
- GPS 상실 + 비상 모드 미진입
- 제어 링크 완전 두절 (>3초)

### HIGH (긴급 조치)
- 배터리 15-25% 또는 전압 셀 3.3-3.5V
- 모터 온도 60-70°C
- GPS RTK 상실 / HDOP > 5
- 통신 링크 품질 < 30%
- 미션 웨이포인트 대폭 이탈 (>50m)

### MEDIUM (경고 및 모니터링)
- 배터리 25-40%
- 모터 온도 50-60°C
- 풍속 > 10m/s (기체 한계 80%)
- 센서 드리프트 감지 (IMU/GPS 불일치 > 2σ)
- 통신 지터 > 100ms

### LOW (관찰)
- 정상 범위 내 미세 변동
- 센서 노이즈 플로어 수준
"""

RISK_ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
        "risk_categories": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"},
        "recommended_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["IMMEDIATE", "HIGH", "NORMAL", "LOW"],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["action", "priority", "reason"],
            },
        },
        "auto_execute": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "risk_level",
        "risk_categories",
        "confidence",
        "reasoning",
        "recommended_actions",
        "auto_execute",
    ],
}


@dataclass
class RiskAssessment:
    risk_level: str
    risk_categories: List[str]
    confidence: float
    reasoning: str
    recommended_actions: List[Dict]
    auto_execute: List[str]
    inference_ms: float


class LocalLLMRiskAnalyzer:
    def __init__(
        self,
        model_path: str = "~/models/llama-3.1-8b-q4_k_m.gguf",
        n_gpu_layers: int = -1,
        n_ctx: int = 4096,
        n_batch: int = 512,
        inference_timeout_ms: int = 200,
        llm_instance=None,  # 테스트용 주입 가능
    ):
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.n_batch = n_batch
        self.inference_timeout_ms = inference_timeout_ms
        self._llm = llm_instance  # 주입된 인스턴스 사용 (지연 초기화)
        self._llm_initialized = llm_instance is not None

        self.system_prompt = RISK_ANALYSIS_SYSTEM_PROMPT
        self.json_schema = {
            "type": "object",
            "properties": {
                "risk_level": {
                    "type": "string",
                    "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                },
                "risk_categories": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning": {"type": "string"},
                "recommended_actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": ["IMMEDIATE", "HIGH", "NORMAL", "LOW"],
                            },
                            "reason": {"type": "string"},
                        },
                        "required": ["action", "priority", "reason"],
                    },
                },
                "auto_execute": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "risk_level",
                "risk_categories",
                "confidence",
                "reasoning",
                "recommended_actions",
                "auto_execute",
            ],
        }

        self._inference_semaphore = asyncio.Semaphore(2)

    def _ensure_llm_initialized(self):
        """Llama 인스턴스 지연 초기화"""
        if not self._llm_initialized:
            self._llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=self.n_gpu_layers,
                n_ctx=self.n_ctx,
                n_batch=self.n_batch,
                verbose=False,
                chat_format="functionary",
            )
            self._llm_initialized = True

    async def analyze_window(self, log_aggregator, device_id: str):
        """슬라이딩 윈도우 로그 분석 → 위험 평가"""

        # 1. 슬라이딩 윈도우 데이터 수집
        window = log_aggregator.get_window(device_id, 2.0)
        if not window:
            return self._default_low_risk()

        # 2. LLM 입력 포맷 구성
        input_json = self._format_window_for_llm(window)

        # 3. 비동기 추론 (타임아웃 보호)
        start = time.time()
        try:
            async with self._inference_semaphore:
                result = await asyncio.wait_for(
                    self._call_llm(input_json), timeout=self.inference_timeout_ms / 1000
                )
        except asyncio.TimeoutError:
            print(f"[LLM WARNING] Inference timeout ({self.inference_timeout_ms}ms)")
            return self._fallback_rule_based(window)
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return self._fallback_rule_based(window)

        inference_ms = (time.time() - start) * 1000

        # 3. 결과 파싱 및 검증
        try:
            result_data = json.loads(result)
            assessment = RiskAssessment(inference_ms=inference_ms, **result_data)
            return self._validate_assessment(assessment)
        except Exception as e:
            print(f"[LLM PARSE ERROR] {e}")
            return self._fallback_rule_based(window)

    def _format_window_for_llm(self, samples) -> str:
        return json.dumps(
            {
                "window_ms": 2000,
                "samples": [
                    {
                        "t": int(s.timestamp * 1000),
                        "device": s.device_id,
                        "type": s.log_type,
                        **s.data,
                    }
                    for s in samples[-50:]
                ],
            },
            separators=(",", ":"),
        )

    async def _call_llm(self, input_json: str) -> str:
        """Llama.cpp 구조화 출력 호출 (sync/async 모두 지원)"""
        self._ensure_llm_initialized()
        # Function schema 정의
        risk_assessment_function = {
            "name": "risk_assessment",
            "description": "드론 위험도 평가 결과",
            "parameters": {
                "type": "object",
                "properties": {
                    "risk_level": {
                        "type": "string",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    },
                    "risk_categories": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"},
                    "recommended_actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "priority": {
                                    "type": "string",
                                    "enum": ["IMMEDIATE", "HIGH", "NORMAL", "LOW"],
                                },
                                "reason": {"type": "string"},
                            },
                            "required": ["action", "priority", "reason"],
                        },
                    },
                    "auto_execute": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "risk_level",
                    "risk_categories",
                    "confidence",
                    "reasoning",
                    "recommended_actions",
                    "auto_execute",
                ],
            },
        }

        # sync/async 둘 다 지원
        import asyncio

        func = self._llm.create_chat_completion
        if asyncio.iscoroutinefunction(func):
            response = await func(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": input_json},
                ],
                functions=[risk_assessment_function],
                function_call={"name": "risk_assessment"},
                temperature=0.1,
                max_tokens=1024,
            )
        else:
            # 동기 함수를 스레드 풀에서 실행
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: func(
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": input_json},
                    ],
                    functions=[risk_assessment_function],
                    function_call={"name": "risk_assessment"},
                    temperature=0.1,
                    max_tokens=1024,
                ),
            )
        return response["choices"][0]["message"]["function_call"]["arguments"]

    def _validate_assessment(self, assessment):
        assessment.confidence = max(0.0, min(1.0, assessment.confidence))

        min_conf = {"CRITICAL": 0.9, "HIGH": 0.7, "MEDIUM": 0.5, "LOW": 0.3}
        if assessment.confidence < min_conf.get(assessment.risk_level, 0.5):
            assessment.confidence = min_conf[assessment.risk_level]

        if assessment.risk_level != "CRITICAL":
            assessment.auto_execute = []

        return assessment

    def _fallback_rule_based(self, window):
        return RiskAssessment(
            risk_level="LOW",
            risk_categories=["LLM_FALLBACK"],
            confidence=0.5,
            reasoning="LLM 추론 실패로 규칙 기반 폴백 적용",
            recommended_actions=[],
            auto_execute=[],
            inference_ms=0,
        )

    def _default_low_risk(self):
        return RiskAssessment(
            risk_level="LOW",
            risk_categories=["NO_DATA"],
            confidence=1.0,
            reasoning="분석할 로그 데이터 없음",
            recommended_actions=[],
            auto_execute=[],
            inference_ms=0,
        )
