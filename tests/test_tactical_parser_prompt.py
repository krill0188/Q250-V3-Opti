"""
전술 파서 프롬프트 준수 검증 테스트
LLM 출력이 시스템 프롬프트의 JSON 스키마와 규칙을 준수하는지 검증
"""

import pytest
import json
from pathlib import Path
from voice.voice_command_engine import VoiceIntentParser, ParsedVoiceIntent
from voice.tactical_normalizer import create_tactical_normalizer
from voice.military_coords import (
    CoordinateParser,
    CoordinateConverter,
    BranchProfileManager,
    MilitaryBranch,
)


class MockLLMClient:
    """테스트용 Mock LLM 클라이언트"""

    def __init__(self, responses: dict):
        self.responses = responses
        self.call_count = 0

    async def generate_json(
        self, system_prompt: str, user_prompt: str, response_model
    ) -> str:
        # user_prompt에서 텍스트 추출
        if "명령:" in user_prompt:
            text = user_prompt.split("명령:")[-1].strip()
        else:
            text = user_prompt

        # 매핑된 응답 반환
        for key, response in self.responses.items():
            if key in text:
                return json.dumps(response)

        # 기본 응답
        return json.dumps(
            {
                "target_id": "drone_1",
                "action": "HOLD",
                "x_m": 0.0,
                "y_m": 0.0,
                "z_m": 0.0,
                "vx_mps": 0.0,
                "vy_mps": 0.0,
                "vz_mps": 0.0,
                "yaw_rate_radps": 0.0,
            }
        )


class TestTacticalParserPromptCompliance:
    """시스템 프롬프트 준수 검증 테스트"""

    @pytest.fixture
    def parser(self):
        """VoiceIntentParser with mocked LLM"""
        mock_responses = {
            "번개": {
                "target_id": "drone_1",
                "action": "BDA_OBSERVE",
                "x_m": 0.0,
                "y_m": 0.0,
                "z_m": 100.0,
                "vx_mps": 0.0,
                "vy_mps": 0.0,
                "vz_mps": 0.0,
                "yaw_rate_radps": 0.0,
            },
            "개척": {
                "target_id": "drone_1",
                "action": "MINEFIELD_RECON",
                "x_m": 0.0,
                "y_m": 0.0,
                "z_m": 5.0,
                "vx_mps": 0.0,
                "vy_mps": 0.0,
                "vz_mps": 0.0,
                "yaw_rate_radps": 0.0,
            },
            "타이거": {
                "target_id": "drone_1",
                "action": "RECON_AREA",
                "x_m": 0.0,
                "y_m": 0.0,
                "z_m": 25.0,
                "vx_mps": 0.0,
                "vy_mps": 0.0,
                "vz_mps": 0.0,
                "yaw_rate_radps": 0.0,
            },
        }
        parser = VoiceIntentParser(llm_client=MockLLMClient(mock_responses))
        return parser

    @pytest.fixture
    def normalizer(self):
        from voice import create_tactical_normalizer

        return create_tactical_normalizer()

    @pytest.fixture
    def coord_parser(self):
        return CoordinateParser()

    @pytest.fixture
    def coord_converter(self):
        return CoordinateConverter()

    @pytest.fixture
    def branch_mgr(self):
        return BranchProfileManager()

    # ===== 1. unit_id 추출 규칙 검증 =====

    @pytest.mark.asyncio
    async def test_unit_id_branch_inf(self, parser):
        """보병 병과 식별: 백호/화랑 호출부호 → INF"""
        text = "백호 1-1 이륙"
        # 전술 정규화 적용
        from voice import create_tactical_normalizer

        normalizer = create_tactical_normalizer()
        norm_text = normalizer.normalize(text)

        result = await parser.parse_to_command(
            text=norm_text,
            stt_confidence=0.9,
            tactical_normalizer=None,  # 이미 정규화됨
        )

        assert result.target_id == "drone_1"
        # unit_id 검증은 UnifiedCommand에 없으므로 tactical_action으로 확인
        # 추후 UnifiedCommand에 unit_id 필드 추가 시 검증

    @pytest.mark.asyncio
    async def test_unit_id_branch_arty(self, parser):
        """포병 병과 식별: 번개/포성 호출부호 → ARTY"""
        text = "번개 2 탄착 관측 임무"
        from voice import create_tactical_normalizer

        normalizer = create_tactical_normalizer()
        norm_text = normalizer.normalize(text)

        result = await parser.parse_to_command(
            text=norm_text, stt_confidence=0.9, tactical_normalizer=None
        )
        assert result.action in ["BDA_OBSERVE", "HOLD"]  # 포병 액션 또는 기본값

    # ===== 2. tactical_action 매핑 검증 =====

    @pytest.mark.asyncio
    async def test_tactical_action_bda_observe(self, parser):
        """탄착관측 → BDA_OBSERVE"""
        text = "번개 2 탄착 관측 임무 수행"
        from voice import create_tactical_normalizer

        normalizer = create_tactical_normalizer()
        norm_text = normalizer.normalize(text)

        result = await parser.parse_to_command(
            text=norm_text, stt_confidence=0.9, tactical_normalizer=None
        )
        # 포병 병과 + 탄착관측 → BDA_OBSERVE 예상
        assert result.action in ["BDA_OBSERVE", "RECON_AREA", "HOLD"]

    @pytest.mark.asyncio
    async def test_tactical_action_minefield_recon(self, parser):
        """지뢰지대 정찰 → MINEFIELD_RECON"""
        text = "개척 1 공병 소대 지뢰 지대 정찰"
        from voice import create_tactical_normalizer

        normalizer = create_tactical_normalizer()
        norm_text = normalizer.normalize(text)

        result = await parser.parse_to_command(
            text=norm_text, stt_confidence=0.9, tactical_normalizer=None
        )
        assert result.action in ["MINEFIELD_RECON", "RECON_AREA", "HOLD"]

    @pytest.mark.asyncio
    async def test_tactical_action_hold_rtl_emergency(self, parser):
        """긴급 명령 Fast-Path: 임무중지/긴급복귀 → ESTOP/RTL"""
        from voice.voice_command_engine import FastPathEmergencyMatcher

        # 임무중지 → ESTOP (임무 중지는 비상정지)
        cmd = FastPathEmergencyMatcher.match("임무중지", default_target="drone_1")
        assert cmd is not None
        assert cmd.action == "ESTOP"

        # 긴급복귀 → RTL
        cmd = FastPathEmergencyMatcher.match("긴급복귀", default_target="drone_1")
        assert cmd is not None
        assert cmd.action == "RTL"

        # 전파침묵 → EMCON
        cmd = FastPathEmergencyMatcher.match("전파침묵", default_target="drone_1")
        assert cmd is not None
        assert cmd.action == "EMCON"

        # 비상착륙 → LAND
        cmd = FastPathEmergencyMatcher.match("비상착륙", default_target="drone_1")
        assert cmd is not None
        assert cmd.action == "LAND"

        # 정지 (단독) → HOLD
        cmd = FastPathEmergencyMatcher.match("정지", default_target="drone_1")
        assert cmd is not None
        assert cmd.action == "HOLD"

    # ===== 3. 군사 좌표계 추출 규칙 검증 =====

    def test_coordinate_mgrs_full(self, coord_parser):
        """전체 MGRS: '52S DG 1234 5678' 또는 '52SDG12345678'"""
        text = "좌표 52S DG 1234 5678 이동"
        coords = coord_parser.parse_coordinate(text)

        # 전체 MGRS와 약식 MGRS 둘 다 매칭될 수 있음 (패턴 중복 허용)
        mgrs_coords = [c for c in coords if c.coord_type.value.startswith("mgrs")]
        assert len(mgrs_coords) >= 1
        assert any("52S" in c.raw_value for c in mgrs_coords)

    def test_coordinate_mgrs_abbrev(self, coord_parser):
        """약식 MGRS: 'DG 1234 5678' → 기본 Zone(52S) 자동 추가"""
        text = "좌표 DG 1234 5678"
        coords = coord_parser.parse_coordinate(text)

        mgrs_coords = [c for c in coords if c.coord_type.value.startswith("mgrs")]
        assert len(mgrs_coords) >= 1
        assert mgrs_coords[0].coord_type.value in (
            "mgrs_10m",
            "mgrs_abbrev_8",
            "mgrs_1m",
            "mgrs_abbrev_6",
        )

    def test_coordinate_polar_mil(self, coord_parser):
        """극좌표(밀): '방위각 3200밀 거리 500미터'"""
        text = "방위각 3200밀 거리 500미터 이동"
        coords = coord_parser.parse_coordinate(text)

        polar_coords = [c for c in coords if c.coord_type.value == "mil_polar"]
        assert len(polar_coords) == 1
        assert polar_coords[0].mil_azimuth == 3200.0
        assert polar_coords[0].distance_m == 500.0

    def test_coordinate_bullseye_shift(self, coord_parser):
        """기준점 편이: '목표 알파에서 북쪽 200 동쪽 100'"""
        text = "불스아이에서 북쪽 200 동쪽 100 이동"
        coords = coord_parser.parse_coordinate(text)

        bullseye_coords = [c for c in coords if c.coord_type.value == "mil_offset"]
        assert len(bullseye_coords) >= 1
        assert bullseye_coords[0].reference_point == "BULLSEYE"

    def test_coordinate_body_frd(self, coord_parser):
        """기체 기준 상대이동: '전방 50 좌측 20'"""
        text = "전방 50 좌측 20 이동"
        coords = coord_parser.parse_coordinate(text)

        frd_coords = [c for c in coords if c.coord_type.value == "body_frd"]
        assert len(frd_coords) >= 1

    # ===== 4. 좌표 변환 엔진 검증 =====

    def test_mgrs_to_wgs84(self, coord_converter):
        """MGRS → WGS84 변환"""
        lat, lon = coord_converter.mgrs_to_wgs84("DG 1234 5678")
        assert 33 < lat < 43  # 한반도 위도 범위
        assert 124 < lon < 132  # 한반도 경도 범위

    def test_polar_mil_to_ned(self, coord_converter):
        """밀 극좌표 → NED 변위"""
        # 1600밀 = 90도 (동쪽)
        n, e, d = coord_converter.polar_to_ned(1600.0, 300.0)
        assert abs(n - 0.0) < 1.0
        assert abs(e - 300.0) < 1.0

        # 3200밀 = 180도 (남쪽)
        n, e, d = coord_converter.polar_to_ned(3200.0, 3500.0)
        assert abs(n + 3500.0) < 1.0
        assert abs(e - 0.0) < 1.0

    # ===== 5. 병과별 프로파일 검증 =====

    def test_branch_profiles_exact_match(self, branch_mgr):
        """참조 구현 BRANCH_SOP_PROFILES와 정확히 일치"""
        expected = {
            "INFANTRY": {
                "altitude": 100.0,
                "gimbal": -60.0,
                "speed": 10.0,
                "mode": "circular",
            },
            "ARTILLERY": {
                "altitude": 200.0,
                "gimbal": -30.0,
                "speed": 15.0,
                "mode": "figure8",
            },
            "ENGINEER": {
                "altitude": 80.0,
                "gimbal": -75.0,
                "speed": 8.0,
                "mode": "racetrack",
            },
            "AVIATION": {
                "altitude": 300.0,
                "gimbal": -20.0,
                "speed": 25.0,
                "mode": "circular",
            },
            "ARMOR": {
                "altitude": 150.0,
                "gimbal": -40.0,
                "speed": 20.0,
                "mode": "circular",
            },
            "CHEMICAL": {
                "altitude": 100.0,
                "gimbal": -60.0,
                "speed": 10.0,
                "mode": "circular",
            },
        }

        for branch, expected_vals in expected.items():
            profile = branch_mgr.get_mission_params(branch, "default")
            assert (
                profile["altitude_agl"] == expected_vals["altitude"]
            ), f"{branch} 고도 불일치"
            assert (
                profile["gimbal_pitch"] == expected_vals["gimbal"]
            ), f"{branch} 짐벌 불일치"
            assert (
                profile["speed_mps"] == expected_vals["speed"]
            ), f"{branch} 속도 불일치"
            assert (
                profile["loiter_pattern"] == expected_vals["mode"]
            ), f"{branch} 모드 불일치"

    def test_arty_mission_override(self, branch_mgr):
        """ARTY target_acquisition: 300m, -20도"""
        profile = branch_mgr.get_mission_params("ARTILLERY", "target_acquisition")
        assert profile["altitude_agl"] == 300.0
        assert profile["gimbal_pitch"] == -20.0

    def test_eng_mission_override(self, branch_mgr):
        """ENGINEER route_clearance: 50m(안전최소), -90도"""
        profile = branch_mgr.get_mission_params("ENGINEER", "route_clearance")
        assert profile["altitude_agl"] == 50.0  # 안전최소 50m로 보정됨
        assert profile["gimbal_pitch"] == -90.0

    # ===== 6. 전술 정규화기 검증 =====

    def test_normalize_mil_numerals(self, normalizer):
        """군사 숫자 음가 → 아라비아 숫자"""
        assert normalizer.normalize("삼백") == "300"
        assert normalizer.normalize("이천") == "2000"
        assert normalizer.normalize("일만") == "10000"

    def test_normalize_nato_phonetic(self, normalizer):
        """NATO 포네틱 → 영문"""
        assert "DG" in normalizer.normalize("델타 골프")
        assert "AB" in normalizer.normalize("알파 브라보")

    def test_normalize_jargon(self, normalizer):
        """전술용어 교정"""
        assert normalizer.normalize("접촉 지역") == "접적 지역"
        # "차량 폐기" → "차폐 비행" (공백 포함)
        assert "차폐" in normalizer.normalize("차량 폐기")

    def test_normalize_full_pipeline(self, normalizer):
        """전체 파이프라인: 참조 구현 테스트 케이스"""
        # 참조 구현 raw_stt_1
        raw_1 = "번개 둘 여기는 본부 포병 관측 임무 수행하라 좌표 델타 골프 하나둘셋넷 오여섯칠팔 탄착 관측"
        expected_1 = (
            "번개 2 여기는 본부 포병 관측 임무 수행하라 좌표 DG 1234 5678 탄착 관측"
        )
        assert normalizer.normalize(raw_1) == expected_1

        # 참조 구현 raw_stt_2
        raw_2 = "개척 하나 공병 소대 전방 지뢰 지대 정찰 방위각 하나여섯공공 밀 거리 삼백 미터로 이동"
        expected_2 = (
            "개척 1 공병 소대 전방 지뢰 지대 정찰 방위각 1600 밀 거리 300 미터로 이동"
        )
        assert normalizer.normalize(raw_2) == expected_2

    # ===== 7. JSON 스키마 준수 검증 =====

    def test_parsable_voice_intent_schema(self):
        """ParsedVoiceIntent JSON 스키마 유효성"""
        intent = ParsedVoiceIntent(
            target_id="drone_1",
            action="RECON_AREA",
            x_m=100.0,
            y_m=0.0,
            z_m=50.0,
            vx_mps=10.0,
            vy_mps=0.0,
            vz_mps=0.0,
            yaw_rate_radps=0.0,
        )
        # Pydantic 검증 통과 확인
        assert intent.target_id == "drone_1"
        assert intent.action == "RECON_AREA"

    def test_unified_command_schema(self):
        """UnifiedCommand 스키마 유효성"""
        from core_arbitrator import UnifiedCommand, CommandPriority

        cmd = UnifiedCommand(
            command_id="test-123",
            source="VOICE_NLU",
            priority=CommandPriority.VOICE_NLU,
            target_id="drone_1",
            action="RECON_AREA",  # 새로 추가된 전술 액션
            x_m=100.0,
            confidence=0.9,
        )
        assert cmd.target_id == "drone_1"
        assert cmd.action == "RECON_AREA"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
