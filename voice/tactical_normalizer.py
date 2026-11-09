"""
군사 특화 STT 전술 정규화기 (Deterministic Tactical Normalizer)
- STT 출력 직후 LLM 전달 전, 군사 용어/음가/포네틱을 표준 표기로 결정론적 변환
- Regex + 사전 기반, 확률적 추론 없음 (파싱 오류율 0% 목표)
"""

import re
from typing import Dict, List, Tuple, Optional, Pattern
from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class TacticalNormalizerConfig:
    """전술 정규화기 설정"""

    custom_dict_path: Optional[str] = None

    convert_phonetic_numbers: bool = True
    convert_nato_phonetic: bool = True
    correct_tactical_terms: bool = True
    normalize_grid_coords: bool = True
    normalize_callsigns: bool = True
    preserve_original: bool = False

    custom_phonetic_numbers: Dict[str, str] = field(default_factory=dict)
    custom_nato_phonetic: Dict[str, str] = field(default_factory=dict)
    custom_tactical_terms: Dict[str, str] = field(default_factory=dict)


class TacticalNormalizer:
    """
    결정론적 전술 정규화기
    - 군사 음가 숫자, NATO 포네틱, 전술 용어, 격자 좌표, 호출부호를 표준 표기로 변환
    - 모든 변환은 규칙 기반(Regex + 사전), LLM 추론 없음
    """

    # ===== 기본 사전 =====

    DEFAULT_PHONETIC_NUMBERS: Dict[str, str] = {
        "공": "0",
        "영": "0",
        "제로": "0",
        "일": "1",
        "하나": "1",
        "이": "2",
        "둘": "2",
        "삼": "3",
        "셋": "3",
        "사": "4",
        "넷": "4",
        "오": "5",
        "다섯": "5",
        "육": "6",
        "여섯": "6",
        "륙": "6",
        "칠": "7",
        "일곱": "7",
        "팔": "8",
        "여덟": "8",
        "구": "9",
        "아홉": "9",
        # 한자어 숫자 (백, 천, 만 등) - 단독 사용 시
        "백": "00",
        "천": "000",
        "만": "0000",
    }

    DEFAULT_NATO_PHONETIC: Dict[str, str] = {
        "알파": "A",
        "브라보": "B",
        "찰리": "C",
        "델타": "D",
        "에코": "E",
        "폭스트롯": "F",
        "골프": "G",
        "호텔": "H",
        "인디아": "I",
        "줄리엣": "J",
        "킬로": "K",
        "리마": "L",
        "마이크": "M",
        "노벰버": "N",
        "오스카": "O",
        "파파": "P",
        "퀘벡": "Q",
        "로미오": "R",
        "시에라": "S",
        "탱고": "T",
        "유니폼": "U",
        "빅터": "V",
        "위스키": "W",
        "엑스레이": "X",
        "양키": "Y",
        "줄루": "Z",
        "엑스": "X",
        "와이": "Y",
        "지드": "Z",
        "지드라": "Z",
    }

    DEFAULT_TACTICAL_TERMS: Dict[str, str] = {
        "접촉": "접적",
        "적접": "접적",
        "전적": "접적",
        "사각": "사각",
        "사각형": "사각",
        "사각지대": "사각",
        "차폐": "차폐",
        "차량폐기": "차폐",
        "차량 폐기": "차폐",
        "차량폐기물": "차폐",
        "엄폐": "엄폐",
        "엄폐물": "엄폐",
        "엄호": "엄폐",
        "집결": "집결",
        "집결지": "집결지",
        "집결장소": "집결지",
        "진출": "진출",
        "진출선": "진출선",
        "진출로": "진출선",
        "탄착": "탄착",
        "탄착관측": "탄착관측",
        "탄착점": "탄착점",
        "관측": "관측",
        "관측소": "관측소",
        "관측병": "관측병",
        "방위": "방위",
        "방위각": "방위각",
        "방위각도": "방위각",
        "거리": "거리",
        "거리측정": "거리측정",
        "고도": "고도",
        "고도계": "고도계",
        "방향": "방향",
        "방향타": "방향타",
        "사격": "사격",
        "사격명령": "사격명령",
        "사격중지": "사격중지",
        "장전": "장전",
        "실탄": "실탄",
        "공포탄": "공포탄",
        "탄약": "탄약",
        "탄창": "탄창",
        "탄피": "탄피",
        "무전": "무전",
        "교신": "교신",
        "응답": "응답",
        "수신": "수신",
        "호출": "호출",
        "호출부호": "호출부호",
        "콜사인": "호출부호",
        "확인": "확인",
        "확인바람": "확인바람",
        "이해": "이해",
        "반복": "반복",
        "다시한번": "반복",
        "말씀": "말씀",
        "소대": "소대",
        "중대": "중대",
        "대대": "대대",
        "연대": "연대",
        "사단": "사단",
        "군단": "군단",
        "작전지역": "작전지역",
        "책임지역": "책임지역",
        "경계지역": "경계지역",
    }

    GRID_PATTERN: Pattern = re.compile(
        r"(?:격자\s*)?([가-힣]{2,3})\s*([가-힣]{2,3})\s*(\d{3,5})\s*(\d{3,5})"
    )

    def __init__(self, config: Optional[TacticalNormalizerConfig] = None):
        self.config = config or TacticalNormalizerConfig()

        self.phonetic_numbers = {
            **self.DEFAULT_PHONETIC_NUMBERS,
            **self.config.custom_phonetic_numbers,
        }
        self.nato_phonetic = {
            **self.DEFAULT_NATO_PHONETIC,
            **self.config.custom_nato_phonetic,
        }
        self.tactical_terms = {
            **self.DEFAULT_TACTICAL_TERMS,
            **self.config.custom_tactical_terms,
        }

        if self.config.custom_dict_path:
            self._load_custom_dict(self.config.custom_dict_path)

        self._compile_patterns()

    def _load_custom_dict(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "phonetic_numbers" in data:
                self.phonetic_numbers.update(data["phonetic_numbers"])
            if "nato_phonetic" in data:
                self.nato_phonetic.update(data["nato_phonetic"])
            if "tactical_terms" in data:
                self.tactical_terms.update(data["tactical_terms"])
        except Exception as e:
            print(f"사용자 정의 사전 로드 실패: {e}")

    def _compile_patterns(self):
        """정규식 컴파일 - 단어 경계(\\b) 필수 적용"""
        # NATO 포네틱: 단어 경계로 완전 매칭만
        nato_keys = sorted(self.nato_phonetic.keys(), key=len, reverse=True)
        self._nato_pattern = re.compile(
            r"\b(?:" + "|".join(map(re.escape, nato_keys)) + r")\b"
        )

        # 전술 용어: 단어 경계로 완전 매칭만
        term_keys = sorted(self.tactical_terms.keys(), key=len, reverse=True)
        self._tactical_term_pattern = re.compile(
            r"\b(?:" + "|".join(map(re.escape, term_keys)) + r")\b"
        )

        # 숫자 음가: 독립된 단어로만 매칭 (한글 단어 경계)
        # 주의: "사각"의 "사"가 매칭되지 않도록 단어 경계 필수
        num_keys = sorted(self.phonetic_numbers.keys(), key=len, reverse=True)
        self._phonetic_num_word_pattern = re.compile(
            r"\b(?:" + "|".join(map(re.escape, num_keys)) + r")\b"
        )

        # 연속 숫자 음가 (띄어쓰기 없는 경우): "하나둘셋" → "123"
        # 이 패턴은 전술 용어/NATO 변환 후에만 적용
        self._phonetic_num_seq_pattern = re.compile(
            r"(?:" + "|".join(map(re.escape, num_keys)) + r"){2,}"
        )

    def normalize(self, text: str) -> str:
        """메인 정규화 파이프라인 - 순서 중요!"""
        if not text or not text.strip():
            return text

        original = text
        result = text

        # 1. 격자 좌표 (가장 구체적)
        if self.config.normalize_grid_coords:
            result = self._normalize_grid_coords(result)

        # 2. 호출부호
        if self.config.normalize_callsigns:
            result = self._normalize_callsigns(result)

        # 3. NATO 포네틱 (단어 단위)
        if self.config.convert_nato_phonetic:
            result = self._convert_nato_phonetic(result)

        # 4. 전술 용어 정정 (숫자 음가 변환보다 먼저!)
        if self.config.correct_tactical_terms:
            result = self._correct_tactical_terms(result)

        # 5. 군사 숫자 음가 (단어 단위 + 연속열)
        if self.config.convert_phonetic_numbers:
            result = self._convert_phonetic_numbers(result)

        # 6. 공백 정리
        result = self._cleanup_whitespace(result)

        if self.config.preserve_original:
            return {"original": original, "normalized": result}
        return result

    def _normalize_grid_coords(self, text: str) -> str:
        def replace_grid(match):
            first = self.nato_phonetic.get(match.group(1), match.group(1).upper()[:1])
            second = self.nato_phonetic.get(match.group(2), match.group(2).upper()[:1])
            return f"{first}{second} {match.group(3)} {match.group(4)}"

        return self.GRID_PATTERN.sub(replace_grid, text)

    def _normalize_callsigns(self, text: str) -> str:
        unit_map = {
            "타이거": "TIGER",
            "이글": "EAGLE",
            "팰컨": "FALCON",
            "울프": "WOLF",
            "라이온": "LION",
            "샤크": "SHARK",
            "레드": "RED",
            "블루": "BLUE",
            "그린": "GREEN",
            "화이트": "WHITE",
            "알파팀": "ALPHA",
            "브라보팀": "BRAVO",
            "찰리팀": "CHARLIE",
            "델타팀": "DELTA",
        }

        def replace_callsign(match):
            unit = unit_map.get(match.group(1), match.group(1).upper())
            return f"{unit} {match.group(2)}-{match.group(3)}"

        pattern = re.compile(r"\b([가-힣]+)\s*(\d+)[\-\.](\d+)\b")
        return pattern.sub(replace_callsign, text)

    def _convert_nato_phonetic(self, text: str) -> str:
        def replace_nato(match: re.Match) -> str:
            return self.nato_phonetic.get(match.group(0), match.group(0))

        return self._nato_pattern.sub(replace_nato, text)

    def _correct_tactical_terms(self, text: str) -> str:
        def replace_term(match: re.Match) -> str:
            return self.tactical_terms.get(match.group(0), match.group(0))

        return self._tactical_term_pattern.sub(replace_term, text)

    def _convert_phonetic_numbers(self, text: str) -> str:
        """숫자 음가 변환: 1) 독립 단어 2) 연속열 (순서 중요)"""

        # 1. 독립된 단어 단위 변환 ("사" → "4", "일" → "1" 등)
        def replace_num_word(match):
            return self.phonetic_numbers.get(match.group(0), match.group(0))

        result = self._phonetic_num_word_pattern.sub(replace_num_word, text)

        # 2. 연속 열 변환 ("하나둘셋" → "123")
        # 주의: 이미 변환된 숫자(아라비아 숫자)는 건너뜀
        def replace_num_seq(match):
            seq = match.group(0)
            # 이미 아라비아 숫자가 포함된 경우 건너뜀
            if any(c.isdigit() for c in seq):
                return seq

            result_parts = []
            i = 0
            keys = sorted(self.phonetic_numbers.keys(), key=len, reverse=True)
            while i < len(seq):
                matched = False
                for key in keys:
                    if seq.startswith(key, i):
                        result_parts.append(self.phonetic_numbers[key])
                        i += len(key)
                        matched = True
                        break
                if not matched:
                    result_parts.append(seq[i])
                    i += 1
            return "".join(result_parts)

        return self._phonetic_num_seq_pattern.sub(replace_num_seq, result)

    def _cleanup_whitespace(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        # 인접한 영문 대문자 단일 글자 병합 (예: "D G" -> "DG")
        text = re.sub(r"\b([A-Z])\s+([A-Z])\b", r"\1\2", text)
        text = re.sub(r"\s([,.!?:;])", r"\1", text)
        text = re.sub(r"([,.!?:;])\s", r"\1 ", text)
        return text.strip()

    def get_changes(self, original: str, normalized: str) -> List[Dict]:
        changes = []
        orig_words = original.split()
        norm_words = normalized.split()

        for i, (o, n) in enumerate(zip(orig_words, norm_words)):
            if o != n:
                changes.append(
                    {
                        "position": i,
                        "original": o,
                        "normalized": n,
                        "type": self._classify_change(o, n),
                    }
                )
        return changes

    def _classify_change(self, original: str, normalized: str) -> str:
        if (
            original in self.phonetic_numbers
            and normalized == self.phonetic_numbers[original]
        ):
            return "phonetic_number"
        if (
            original in self.nato_phonetic
            and normalized == self.nato_phonetic[original]
        ):
            return "nato_phonetic"
        if (
            original in self.tactical_terms
            and normalized == self.tactical_terms[original]
        ):
            return "tactical_term"
        if re.match(r"^[A-Z]{2}\s\d{3,5}\s\d{3,5}$", normalized):
            return "grid_coord"
        if re.match(r"^[A-Z]+\s\d+-\d+$", normalized):
            return "callsign"
        return "other"

    def generate_whisper_initial_prompt(
        self,
        operation_area: str = "",
        callsigns: List[str] = None,
        tactical_terms: List[str] = None,
        max_length: int = 200,
    ) -> str:
        parts = []

        if operation_area:
            parts.append(f"작전지역 {operation_area}")

        if callsigns:
            cs_str = ", ".join(callsigns[:5])
            parts.append(f"호출부호 {cs_str}")

        if tactical_terms:
            terms_str = ", ".join(tactical_terms[:10])
            parts.append(f"전술용어 {terms_str}")

        base = "다음은 군사 무전 교신 녹음입니다. 군사 용어, 호출부호, 격자 좌표, 숫자 음가를 정확히 인식하세요."

        prompt = base
        if parts:
            prompt += " " + ". ".join(parts) + "."

        if len(prompt) > max_length:
            prompt = prompt[: max_length - 3] + "..."

        return prompt


def create_tactical_normalizer(
    custom_dict_path: Optional[str] = None, **kwargs
) -> TacticalNormalizer:
    config = TacticalNormalizerConfig(custom_dict_path=custom_dict_path, **kwargs)
    return TacticalNormalizer(config)


def normalize_tactical_text(text: str, **kwargs) -> str:
    normalizer = create_tactical_normalizer(**kwargs)
    return normalizer.normalize(text)


if __name__ == "__main__":
    test_cases = [
        "타이거 1-3 델타 골프 하나둘셋넷 오여섯칠팔 접촉 사각 차폐",
        "이글 알파 브라보 찰리 1234 5678 진출선 탄착관측 확인바람",
        "레드 이글 2-1 알파 브라보 3456 7890 엄폐 집결지 사격명령",
        "공일이삼사 오육칠팔구 접촉 사각형 차량폐기 엄폐물",
        "사각 지대에서 접촉 발생, 델타 골프 1234 5678로 진출선 형성",
    ]

    normalizer = create_tactical_normalizer()

    print("=== 전술 정규화기 테스트 ===\n")
    for i, text in enumerate(test_cases, 1):
        result = normalizer.normalize(text)
        changes = normalizer.get_changes(text, result)
        print(f"[테스트 {i}]")
        print(f"  원본: {text}")
        print(f"  정규화: {result}")
        if changes:
            print(f"  변경사항: {changes}")
        print()

    print("=== Whisper initial_prompt 생성 ===")
    prompt = normalizer.generate_whisper_initial_prompt(
        operation_area="철원",
        callsigns=["TIGER 1-3", "EAGLE ALPHA", "RED 2-1"],
        tactical_terms=["접적", "진출선", "탄착관측", "사격명령", "집결지"],
    )
    print(f"프롬프트: {prompt}")
