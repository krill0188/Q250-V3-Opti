"""
군사 좌표계 처리 모듈 (MGRS / Mil / 극좌표)
- LLM은 좌표 '종류'와 '원본 문자열'만 추출
- 실제 WGS84 위경도 변환은 검증된 측지 라이브러리(mgrs, pyproj) 사용
- 병과별 비행/센서 프로파일 자동 분기
"""

import re
from typing import Dict, List, Tuple, Optional, NamedTuple, Literal
from dataclasses import dataclass, field
from enum import Enum
import math

try:
    import mgrs

    MGRS_AVAILABLE = True
except ImportError:
    MGRS_AVAILABLE = False
    mgrs = None

try:
    from pyproj import Transformer, CRS

    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False
    Transformer = None
    CRS = None


class CoordinateType(Enum):
    """좌표 유형 분류"""

    MGRS_10M = "mgrs_10m"  # 8자리 (10m 단위) 예: 52S DG 1234 5678
    MGRS_1M = "mgrs_1m"  # 10자리 (1m 단위) 예: 52S DG 12345 67890
    MGRS_ABBREV_6 = "mgrs_abbrev_6"  # 6자리 약식 (100km 생략) 예: DG 123 456
    MGRS_ABBREV_8 = "mgrs_abbrev_8"  # 8자리 약식 예: DG 1234 5678
    LATLON_DMS = "latlon_dms"  # 도분초 예: 38°12'34"N 127°45'21"E
    LATLON_DEC = "latlon_dec"  # 십진도 예: 38.209, 127.756
    MIL_POLAR = "mil_polar"  # 방위각 밀·거리 극좌표
    MIL_OFFSET = "mil_offset"  # 기준점 편이 예: 불스아이에서 좌 200밀, 전방 1500m
    BODY_FRD = "body_frd"  # 기체 기준 상대이동 예: 전방 50 좌측 20
    UTM = "utm"  # UTM 예: 52S 323456 4123456


class MilitaryBranch(Enum):
    """병과 분류"""

    INFANTRY = "infantry"  # 보병
    ARTILLERY = "artillery"  # 포병
    ENGINEER = "engineer"  # 공병
    AVIATION = "aviation"  # 항공
    ARMOR = "armor"  # 기갑
    SIGNAL = "signal"  # 통신
    RECON = "recon"  # 정찰
    SPECIAL = "special"  # 특수전
    AIR_DEFENSE = "air_defense"  # 방공
    CHEMICAL = "chemical"  # 화생방
    MEDICAL = "medical"  # 의무
    LOGISTICS = "logistics"  # 병참


@dataclass
class ParsedCoordinate:
    """파싱된 좌표 (원본 보존 + 유형 분류)"""

    raw_text: str  # 원본 음성 텍스트
    coord_type: CoordinateType  # 좌표 유형
    raw_value: str  # 정규화된 좌표 문자열
    confidence: float = 1.0  # 파싱 신뢰도

    # 변환 결과 (측지 라이브러리에서 채움)
    lat: Optional[float] = None  # 위도 (WGS84)
    lon: Optional[float] = None  # 경도 (WGS84)
    alt: Optional[float] = None  # 고도 (m, 선택적)

    # 로컬 NED 좌표 (미션 컴퓨터 프레임)
    north: Optional[float] = None  # 북쪽 거리 (m)
    east: Optional[float] = None  # 동쪽 거리 (m)
    down: Optional[float] = None  # 아래쪽 거리 (m)

    # 밀/극좌표 원본
    mil_azimuth: Optional[float] = None  # 방위각 (밀)
    mil_elevation: Optional[float] = None  # 고각 (밀)
    distance_m: Optional[float] = None  # 거리 (m)

    # 기준점 (MGRS/UTM)
    reference_point: Optional[str] = None  # 예: "BULLSEYE", "TARGET_1"

    # 기체 기준 상대이동 (BODY_FRD)
    forward_m: Optional[float] = None  # 전방 거리 (m)
    right_m: Optional[float] = None  # 우측 거리 (m)
    down_m: Optional[float] = None  # 하강 거리 (m, 음수=상승)

    # 부가 정보
    zone: Optional[str] = None  # UTM 존 (예: 52S)
    grid_letters: Optional[str] = None  # 100km 격자 (예: DG)


@dataclass
class BranchFlightProfile:
    """병과별 비행/센서 프로파일 (SOP 기반)"""

    branch: MilitaryBranch

    # 비행 파라미터
    default_altitude_agl: float = 100.0  # 기본 고도 (m, AGL)
    max_altitude_agl: float = 500.0  # 최대 고도 (m)
    default_speed_mps: float = 15.0  # 기본 속도 (m/s)
    max_speed_mps: float = 25.0  # 최대 속도 (m/s)
    loiter_radius_m: float = 200.0  # 선회 반경 (m)
    loiter_pattern: str = "circular"  # 선회 패턴: circular, figure8, racetrack

    # 센서/짐벌 파라미터
    gimbal_pitch_default: float = -45.0  # 기본 짐벌 피치 (도, -90=수직하향)
    gimbal_pitch_range: Tuple[float, float] = (-90.0, 10.0)  # 짐벌 피치 범위
    eo_zoom_default: float = 1.0  # EO 줌 배율
    ir_palette: str = "white_hot"  # IR 팔레트

    # 미션별 오버라이드
    mission_overrides: Dict[str, Dict] = field(default_factory=dict)

    # 안전/제한
    min_safe_altitude: float = 50.0  # 최소 안전 고도 (m)
    no_fly_zones: List[Dict] = field(default_factory=list)  # 비행금지구역
    max_endurance_min: float = 30.0  # 최대 체공 시간 (분)


# ===== 병과별 기본 프로파일 (한국군 SOP 기반) =====

DEFAULT_BRANCH_PROFILES: Dict[MilitaryBranch, BranchFlightProfile] = {
    MilitaryBranch.INFANTRY: BranchFlightProfile(
        branch=MilitaryBranch.INFANTRY,
        default_altitude_agl=100.0,
        max_altitude_agl=300.0,
        default_speed_mps=10.0,
        max_speed_mps=20.0,
        loiter_radius_m=150.0,
        loiter_pattern="circular",
        gimbal_pitch_default=-60.0,
        gimbal_pitch_range=(-80.0, 0.0),
        eo_zoom_default=2.0,
        ir_palette="white_hot",
        mission_overrides={
            "recon": {"altitude_agl": 80, "speed_mps": 8, "gimbal_pitch": -70},
            "overwatch": {"altitude_agl": 150, "speed_mps": 5, "gimbal_pitch": -45},
            "cas_support": {"altitude_agl": 200, "speed_mps": 15, "gimbal_pitch": -30},
        },
        min_safe_altitude=30.0,
        max_endurance_min=25.0,
    ),
    MilitaryBranch.ARTILLERY: BranchFlightProfile(
        branch=MilitaryBranch.ARTILLERY,
        default_altitude_agl=200.0,
        max_altitude_agl=500.0,
        default_speed_mps=15.0,
        max_speed_mps=25.0,
        loiter_radius_m=300.0,
        loiter_pattern="figure8",
        gimbal_pitch_default=-30.0,
        gimbal_pitch_range=(-60.0, 10.0),
        eo_zoom_default=4.0,
        ir_palette="black_hot",
        mission_overrides={
            "target_acquisition": {
                "altitude_agl": 300,
                "speed_mps": 10,
                "gimbal_pitch": -20,
            },
            "fall_of_shot": {"altitude_agl": 150, "speed_mps": 5, "gimbal_pitch": -45},
            "adjust_fire": {"altitude_agl": 200, "speed_mps": 8, "gimbal_pitch": -35},
        },
        min_safe_altitude=50.0,
        max_endurance_min=30.0,
    ),
    MilitaryBranch.ENGINEER: BranchFlightProfile(
        branch=MilitaryBranch.ENGINEER,
        default_altitude_agl=80.0,
        max_altitude_agl=200.0,
        default_speed_mps=8.0,
        max_speed_mps=15.0,
        loiter_radius_m=100.0,
        loiter_pattern="racetrack",
        gimbal_pitch_default=-75.0,
        gimbal_pitch_range=(-90.0, -30.0),
        eo_zoom_default=1.5,
        ir_palette="white_hot",
        mission_overrides={
            "route_clearance": {
                "altitude_agl": 50,
                "speed_mps": 5,
                "gimbal_pitch": -90,
            },
            "obstacle_recon": {
                "altitude_agl": 100,
                "speed_mps": 8,
                "gimbal_pitch": -60,
            },
            "bridge_recon": {"altitude_agl": 80, "speed_mps": 6, "gimbal_pitch": -70},
        },
        min_safe_altitude=20.0,
        max_endurance_min=20.0,
    ),
    MilitaryBranch.AVIATION: BranchFlightProfile(
        branch=MilitaryBranch.AVIATION,
        default_altitude_agl=300.0,
        max_altitude_agl=1000.0,
        default_speed_mps=25.0,
        max_speed_mps=40.0,
        loiter_radius_m=500.0,
        loiter_pattern="circular",
        gimbal_pitch_default=-20.0,
        gimbal_pitch_range=(-60.0, 20.0),
        eo_zoom_default=8.0,
        ir_palette="white_hot",
        mission_overrides={
            "aerial_recon": {"altitude_agl": 500, "speed_mps": 30, "gimbal_pitch": -15},
            "target_designation": {
                "altitude_agl": 300,
                "speed_mps": 20,
                "gimbal_pitch": -30,
            },
            "bda": {"altitude_agl": 400, "speed_mps": 15, "gimbal_pitch": -25},
        },
        min_safe_altitude=100.0,
        max_endurance_min=40.0,
    ),
    MilitaryBranch.ARMOR: BranchFlightProfile(
        branch=MilitaryBranch.ARMOR,
        default_altitude_agl=150.0,
        max_altitude_agl=400.0,
        default_speed_mps=20.0,
        max_speed_mps=30.0,
        loiter_radius_m=250.0,
        loiter_pattern="circular",
        gimbal_pitch_default=-40.0,
        gimbal_pitch_range=(-70.0, 10.0),
        eo_zoom_default=3.0,
        ir_palette="white_hot",
        mission_overrides={
            "flank_security": {
                "altitude_agl": 120,
                "speed_mps": 12,
                "gimbal_pitch": -50,
            },
            "advance_guard": {
                "altitude_agl": 180,
                "speed_mps": 18,
                "gimbal_pitch": -35,
            },
        },
        min_safe_altitude=40.0,
        max_endurance_min=30.0,
    ),
    MilitaryBranch.RECON: BranchFlightProfile(
        branch=MilitaryBranch.RECON,
        default_altitude_agl=120.0,
        max_altitude_agl=400.0,
        default_speed_mps=12.0,
        max_speed_mps=25.0,
        loiter_radius_m=200.0,
        loiter_pattern="figure8",
        gimbal_pitch_default=-50.0,
        gimbal_pitch_range=(-80.0, 0.0),
        eo_zoom_default=5.0,
        ir_palette="white_hot",
        mission_overrides={
            "deep_recon": {"altitude_agl": 200, "speed_mps": 15, "gimbal_pitch": -40},
            "route_recon": {"altitude_agl": 100, "speed_mps": 10, "gimbal_pitch": -60},
            "zone_recon": {"altitude_agl": 150, "speed_mps": 12, "gimbal_pitch": -50},
        },
        min_safe_altitude=30.0,
        max_endurance_min=35.0,
    ),
    MilitaryBranch.SIGNAL: BranchFlightProfile(
        branch=MilitaryBranch.SIGNAL,
        default_altitude_agl=200.0,
        max_altitude_agl=500.0,
        default_speed_mps=10.0,
        max_speed_mps=20.0,
        loiter_radius_m=300.0,
        loiter_pattern="circular",
        gimbal_pitch_default=-30.0,
        gimbal_pitch_range=(-60.0, 10.0),
        eo_zoom_default=1.0,
        ir_palette="white_hot",
        mission_overrides={
            "relay": {"altitude_agl": 300, "speed_mps": 5, "gimbal_pitch": -10},
            "comms_recon": {"altitude_agl": 250, "speed_mps": 8, "gimbal_pitch": -20},
        },
        min_safe_altitude=100.0,
        max_endurance_min=45.0,
    ),
    MilitaryBranch.AIR_DEFENSE: BranchFlightProfile(
        branch=MilitaryBranch.AIR_DEFENSE,
        default_altitude_agl=250.0,
        max_altitude_agl=800.0,
        default_speed_mps=20.0,
        max_speed_mps=35.0,
        loiter_radius_m=400.0,
        loiter_pattern="circular",
        gimbal_pitch_default=10.0,
        gimbal_pitch_range=(-30.0, 60.0),
        eo_zoom_default=10.0,
        ir_palette="black_hot",
        mission_overrides={
            "air_surveillance": {
                "altitude_agl": 500,
                "speed_mps": 15,
                "gimbal_pitch": 20,
            },
            "target_tracking": {
                "altitude_agl": 300,
                "speed_mps": 20,
                "gimbal_pitch": 0,
            },
        },
        min_safe_altitude=150.0,
        max_endurance_min=30.0,
    ),
}


class CoordinateParser:
    """음성 텍스트에서 군사 좌표 추출 및 유형 분류"""

    # MGRS 패턴 (다양한 형식)
    MGRS_PATTERNS = [
        # 전체 MGRS: 52S DG 1234 5678 (10m) 또는 52S DG 12345 56789 (1m)
        (
            CoordinateType.MGRS_10M,
            re.compile(
                r"\b(\d{1,2}[A-HJ-NP-Z])\s*([A-HJ-NP-Z]{2})\s*(\d{4})\s*(\d{4})\b",
                re.IGNORECASE,
            ),
        ),
        (
            CoordinateType.MGRS_1M,
            re.compile(
                r"\b(\d{1,2}[A-HJ-NP-Z])\s*([A-HJ-NP-Z]{2})\s*(\d{5})\s*(\d{5})\b",
                re.IGNORECASE,
            ),
        ),
        # 전체 MGRS (공백 없는): 52SDG12345678
        (
            CoordinateType.MGRS_10M,
            re.compile(
                r"\b(\d{1,2}[A-HJ-NP-Z])([A-HJ-NP-Z]{2})(\d{4})(\d{4})\b", re.IGNORECASE
            ),
        ),
        (
            CoordinateType.MGRS_1M,
            re.compile(
                r"\b(\d{1,2}[A-HJ-NP-Z])([A-HJ-NP-Z]{2})(\d{5})(\d{5})\b", re.IGNORECASE
            ),
        ),
        # 약식 MGRS (100km 격자 생략): DG 1234 5678 또는 DG 123 456
        (
            CoordinateType.MGRS_ABBREV_8,
            re.compile(r"\b([A-HJ-NP-Z]{2})\s*(\d{4})\s*(\d{4})\b", re.IGNORECASE),
        ),
        (
            CoordinateType.MGRS_ABBREV_6,
            re.compile(r"\b([A-HJ-NP-Z]{2})\s*(\d{3})\s*(\d{3})\b", re.IGNORECASE),
        ),
        # 약식 MGRS (공백 없는): DG12345678
        (
            CoordinateType.MGRS_ABBREV_8,
            re.compile(r"\b([A-HJ-NP-Z]{2})(\d{4})(\d{4})\b", re.IGNORECASE),
        ),
        (
            CoordinateType.MGRS_ABBREV_6,
            re.compile(r"\b([A-HJ-NP-Z]{2})(\d{3})(\d{3})\b", re.IGNORECASE),
        ),
    ]

    # 위경도 패턴
    LATLON_DMS_PATTERN = re.compile(
        r"(\d{1,2})[°도]\s*(\d{1,2})[′분]\s*(\d{1,2}(?:\.\d+)?)[″초]\s*([NS])\s*"
        r"(\d{1,3})[°도]\s*(\d{1,2})[′분]\s*(\d{1,2}(?:\.\d+)?)[″초]\s*([EW])",
        re.IGNORECASE,
    )
    # 단순화된 DMS 패턴 (한국어 구분자)
    LATLON_DMS_SIMPLE_PATTERN = re.compile(
        r"위도\s*(\d{1,2})\s*도\s*(\d{1,2})\s*분\s*(\d{1,2}(?:\.\d+)?)\s*초\s*([북남])\s*"
        r"경도\s*(\d{1,3})\s*도\s*(\d{1,2})\s*분\s*(\d{1,2}(?:\.\d+)?)\s*초\s*([동서])",
        re.IGNORECASE,
    )
    LATLON_DEC_PATTERN = re.compile(r"(\d{1,2}\.\d+)\s*[,/]\s*(\d{2,3}\.\d+)")

    # 밀 극좌표 패턴
    MIL_POLAR_PATTERN = re.compile(
        r"(?:방위|방위각)\s*(\d{1,4})\s*(?:밀|mil)\s*(?:거리|범위)\s*(\d+(?:\.\d+)?)\s*(?:m|미터|km|킬로)",
        re.IGNORECASE,
    )
    MIL_OFFSET_PATTERN = re.compile(
        r"(?:불스아이|불즈아이|기준점|타겟|목표점)\s*(?:에서|로부터)?\s*"
        r"(?:좌|우|전방|후방|북|남|동|서)쪽?\s*(\d{1,4})\s*(?:밀|mil)?\s*"
        r"(?:전방|후방|좌|우|북|남|동|서)쪽?\s*(\d+(?:\.\d+)?)\s*(?:m|미터|km|킬로|이동)?",
        re.IGNORECASE,
    )
    # 기체 기준 상대이동 (BODY_FRD)
    BODY_FRD_PATTERN = re.compile(
        r"(?:전방|앞)\s*(\d+(?:\.\d+)?)\s*(?:m|미터)?\s*(?:좌측|좌|왼쪽)\s*(\d+(?:\.\d+)?)\s*(?:m|미터)?",
        re.IGNORECASE,
    )

    # UTM 패턴
    UTM_PATTERN = re.compile(
        r"\b(\d{1,2}[A-HJ-NP-Z])\s*(\d{6})\s*(\d{7})\b", re.IGNORECASE
    )

    # 병과 키워드
    BRANCH_KEYWORDS = {
        MilitaryBranch.INFANTRY: ["보병", "소총", "기계화보병", "기보"],
        MilitaryBranch.ARTILLERY: ["포병", "박격포", "자주포", "다연장", "관측반"],
        MilitaryBranch.ENGINEER: ["공병", "전투공병", "도하", "장애물", "지뢰"],
        MilitaryBranch.AVIATION: [
            "항공",
            "헬기",
            "공격헬기",
            "기동헬기",
            "무인기",
            "UAV",
        ],
        MilitaryBranch.ARMOR: ["기갑", "전차", "장갑차", "기계화"],
        MilitaryBranch.SIGNAL: ["통신", "신호", "중계", "전파"],
        MilitaryBranch.RECON: ["정찰", "수색", "관측", "감시"],
        MilitaryBranch.SPECIAL: ["특수전", "특전", "UDT", "해군특수전"],
        MilitaryBranch.AIR_DEFENSE: ["방공", "대공", "지대공", "휴대용방공"],
        MilitaryBranch.CHEMICAL: ["화생방", "제독", "탐지"],
        MilitaryBranch.MEDICAL: ["의무", "후송", "구급"],
        MilitaryBranch.LOGISTICS: ["병참", "보급", "수송", "정비"],
    }

    def __init__(self):
        pass

    def parse_coordinate(self, text: str) -> List[ParsedCoordinate]:
        """텍스트에서 모든 좌표 추출"""
        results = []

        # 1. MGRS (전체 + 약식)
        for coord_type, pattern in self.MGRS_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(0)
                coord = self._parse_mgrs_match(match, coord_type, raw)
                if coord:
                    results.append(coord)

        # 2. 위경도 (DMS 표준)
        for match in self.LATLON_DMS_PATTERN.finditer(text):
            coord = self._parse_latlon_dms(match, match.group(0))
            if coord:
                results.append(coord)

        # 3. 위경도 (DMS 한국어)
        for match in self.LATLON_DMS_SIMPLE_PATTERN.finditer(text):
            coord = self._parse_latlon_dms_simple(match, match.group(0))
            if coord:
                results.append(coord)

        # 4. 위경도 (십진도)
        for match in self.LATLON_DEC_PATTERN.finditer(text):
            coord = self._parse_latlon_dec(match, match.group(0))
            if coord:
                results.append(coord)

        # 5. 밀 극좌표
        for match in self.MIL_POLAR_PATTERN.finditer(text):
            coord = self._parse_mil_polar(match, match.group(0))
            if coord:
                results.append(coord)

        # 6. 밀 편이 좌표
        for match in self.MIL_OFFSET_PATTERN.finditer(text):
            coord = self._parse_mil_offset(match, match.group(0))
            if coord:
                results.append(coord)

        # 7. 기체 기준 상대이동 (BODY_FRD)
        for match in self.BODY_FRD_PATTERN.finditer(text):
            coord = self._parse_body_frd(match, match.group(0))
            if coord:
                results.append(coord)

        # 8. UTM
        for match in self.UTM_PATTERN.finditer(text):
            coord = self._parse_utm(match, match.group(0))
            if coord:
                results.append(coord)

        return results

    def _parse_mgrs_match(
        self, match: re.Match, coord_type: CoordinateType, raw: str
    ) -> Optional[ParsedCoordinate]:
        try:
            if coord_type in (CoordinateType.MGRS_10M, CoordinateType.MGRS_1M):
                zone = match.group(1).upper()
                grid = match.group(2).upper()
                easting = match.group(3)
                northing = match.group(4)
            else:  # 약식
                zone = None
                grid = match.group(1).upper()
                easting = match.group(2)
                northing = match.group(3)

            # 10m → 1m 패딩 (필요시)
            if coord_type == CoordinateType.MGRS_ABBREV_6:
                easting = easting.ljust(4, "0")
                northing = northing.ljust(4, "0")

            raw_value = (
                f"{zone + ' ' if zone else ''}{grid} {easting} {northing}".strip()
            )

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=coord_type,
                raw_value=raw_value,
                zone=zone,
                grid_letters=grid,
            )
        except Exception:
            return None

    def _parse_latlon_dms_simple(
        self, match: re.Match, raw: str
    ) -> Optional[ParsedCoordinate]:
        """한국어 DMS 형식 파싱: 위도 38도 12분 34초 북 경도 127도 45분 21초 동"""
        try:
            lat_deg = int(match.group(1))
            lat_min = int(match.group(2))
            lat_sec = float(match.group(3))
            lat_hem = match.group(4)
            lon_deg = int(match.group(5))
            lon_min = int(match.group(6))
            lon_sec = float(match.group(7))
            lon_hem = match.group(8)

            lat = lat_deg + lat_min / 60 + lat_sec / 3600
            lon = lon_deg + lon_min / 60 + lon_sec / 3600
            if lat_hem in ("남", "S", "s"):
                lat = -lat
            if lon_hem in ("서", "W", "w"):
                lon = -lon

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=CoordinateType.LATLON_DMS,
                raw_value=f"{lat:.6f}, {lon:.6f}",
                lat=lat,
                lon=lon,
            )
        except Exception:
            return None

    def _parse_latlon_dms(
        self, match: re.Match, raw: str
    ) -> Optional[ParsedCoordinate]:
        try:
            lat_deg = int(match.group(1))
            lat_min = int(match.group(2))
            lat_sec = float(match.group(3))
            lat_hem = match.group(4).upper()
            lon_deg = int(match.group(5))
            lon_min = int(match.group(6))
            lon_sec = float(match.group(7))
            lon_hem = match.group(8).upper()

            lat = lat_deg + lat_min / 60 + lat_sec / 3600
            lon = lon_deg + lon_min / 60 + lon_sec / 3600
            if lat_hem == "S":
                lat = -lat
            if lon_hem == "W":
                lon = -lon

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=CoordinateType.LATLON_DMS,
                raw_value=f"{lat:.6f}, {lon:.6f}",
                lat=lat,
                lon=lon,
            )
        except Exception:
            return None

    def _parse_latlon_dec(
        self, match: re.Match, raw: str
    ) -> Optional[ParsedCoordinate]:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            # 한국 위도 범위 대략 33-43, 경도 124-132
            if 30 <= lat <= 45 and 120 <= lon <= 135:
                return ParsedCoordinate(
                    raw_text=raw,
                    coord_type=CoordinateType.LATLON_DEC,
                    raw_value=f"{lat:.6f}, {lon:.6f}",
                    lat=lat,
                    lon=lon,
                )
        except Exception:
            pass
        return None

    def _parse_mil_polar(self, match: re.Match, raw: str) -> Optional[ParsedCoordinate]:
        try:
            mil_az = float(match.group(1))
            dist = float(match.group(2))
            if match.group(0).lower().find("km") >= 0:
                dist *= 1000

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=CoordinateType.MIL_POLAR,
                raw_value=f"방위 {mil_az}밀 거리 {dist}m",
                mil_azimuth=mil_az,
                distance_m=dist,
            )
        except Exception:
            return None

    def _parse_mil_offset(
        self, match: re.Match, raw: str
    ) -> Optional[ParsedCoordinate]:
        try:
            mil_offset = float(match.group(1))
            dist = float(match.group(2)) if match.group(2) else 0
            if "km" in match.group(0).lower():
                dist *= 1000

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=CoordinateType.MIL_OFFSET,
                raw_value=f"기준점에서 {mil_offset}밀 {dist}m",
                mil_azimuth=mil_offset,
                distance_m=dist,
                reference_point="BULLSEYE",
            )
        except Exception:
            return None

    def _parse_body_frd(self, match: re.Match, raw: str) -> Optional[ParsedCoordinate]:
        try:
            forward = float(match.group(1))
            right = float(match.group(2))

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=CoordinateType.BODY_FRD,
                raw_value=f"전방 {forward}m 좌측 {right}m",
                forward_m=forward,
                right_m=right,
                down_m=0.0,
            )
        except Exception:
            return None

    def _parse_utm(self, match: re.Match, raw: str) -> Optional[ParsedCoordinate]:
        try:
            zone = match.group(1).upper()
            easting = match.group(2)
            northing = match.group(3)

            return ParsedCoordinate(
                raw_text=raw,
                coord_type=CoordinateType.UTM,
                raw_value=f"{zone} {easting} {northing}",
                zone=zone,
            )
        except Exception:
            return None

    def detect_branch(self, text: str) -> List[Tuple[MilitaryBranch, float]]:
        """텍스트에서 병과 키워드 탐지 (신뢰도 포함)"""
        detected = []
        text_lower = text.lower()

        for branch, keywords in self.BRANCH_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    # 키워드 길이 가중치
                    confidence = min(1.0, len(kw) / 10.0 + 0.3)
                    detected.append((branch, confidence))
                    break

        # 중복 제거 (높은 신뢰도 우선)
        unique = {}
        for branch, conf in detected:
            if branch not in unique or conf > unique[branch]:
                unique[branch] = conf

        return sorted(unique.items(), key=lambda x: x[1], reverse=True)


class CoordinateConverter:
    """좌표계 변환 (측지 라이브러리 사용)"""

    def __init__(
        self,
        origin_lat: float = 37.5665,
        origin_lon: float = 126.9780,
        default_zone: str = "52S",  # 한반도 중동부 표준 (52S), 서부는 51S
        default_square: str = "DG",  # 작전지역 기본 100km 격자 (예: DG, CH 등)
    ):
        """기준점 설정 (기본: 서울시청)"""
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self.default_zone = default_zone
        self.default_square = default_square
        self._mgrs_converter = None
        self._transformer_wgs_to_utm = None
        self._transformer_utm_to_wgs = None
        self._init_converters()

    def _init_converters(self):
        if MGRS_AVAILABLE:
            self._mgrs_converter = mgrs.MGRS()

        if PYPROJ_AVAILABLE:
            # WGS84 -> UTM-K (EPSG:5179) 변환기
            self._wgs84 = CRS.from_epsg(4326)
            self._utm_k = CRS.from_epsg(5179)
            self._transformer_wgs_to_utm = Transformer.from_crs(
                self._wgs84, self._utm_k, always_xy=True
            )
            self._transformer_utm_to_wgs = Transformer.from_crs(
                self._utm_k, self._wgs84, always_xy=True
            )

    def mgrs_to_wgs84(self, mgrs_str: str) -> Tuple[float, float]:
        """MGRS → 위경도 (WGS84)

        지원 형식:
        - 전체 MGRS: "52S DG 1234 5678" 또는 "52SDG12345678"
        - 약식 (Zone 생략): "DG 1234 5678" 또는 "DG12345678" → 기본 Zone(52S) 자동 추가
        """
        if not self._mgrs_converter:
            raise RuntimeError("mgrs 라이브러리가 필요합니다: pip install mgrs")

        # 모든 공백 제거 후 대문자화
        clean = re.sub(r"\s+", "", mgrs_str.upper())

        # 약식 MGRS 감지 및 기본 Zone/Square 자동 추가
        # 패턴 1: 숫자만 6/8/10자리 (예: 12345678) → Zone + Square + 숫자
        # 패턴 2: 영문 2자리 + 숫자 6/8/10자리 (예: DG12345678) → Zone + 영문 + 숫자
        # 패턴 3: 이미 전체 MGRS (예: 52SDG12345678) → 그대로 사용

        if re.fullmatch(r"\d{6}|\d{8}|\d{10}", clean):
            # 숫자만: 52S + DG + 숫자
            clean = f"{self.default_zone}{self.default_square}{clean}"
        elif re.fullmatch(r"[A-HJ-NP-Z]{2}(\d{6}|\d{8}|\d{10})", clean):
            # 영문 2자리 + 숫자: 52S + 영문 + 숫자
            clean = f"{self.default_zone}{clean}"
        # else: 이미 전체 MGRS 형식 (52SDG...) → 그대로 사용

        lat, lon = self._mgrs_converter.toLatLon(clean.encode("utf-8"))
        return lat, lon

    def wgs84_to_mgrs(self, lat: float, lon: float, precision: int = 5) -> str:
        """위경도 → MGRS"""
        if not self._mgrs_converter:
            raise RuntimeError("mgrs 라이브러리가 필요합니다")

        mgrs_bytes = self._mgrs_converter.toMGRS(lat, lon, precision)
        mgrs_str = mgrs_bytes.decode("utf-8")
        # 가독성을 위해 공백 삽입
        return self._format_mgrs(mgrs_str)

    def _format_mgrs(self, mgrs_str: str) -> str:
        # 52SDG12345678 → 52S DG 1234 5678
        if len(mgrs_str) >= 7:
            zone = mgrs_str[:3]
            grid = mgrs_str[3:5]
            coords = mgrs_str[5:]
            half = len(coords) // 2
            easting = coords[:half]
            northing = coords[half:]
            return f"{zone} {grid} {easting} {northing}"
        return mgrs_str

    def wgs84_to_ned(
        self, lat: float, lon: float, alt: float = 0
    ) -> Tuple[float, float, float]:
        """위경도 → 로컬 NED (기준점 대비)"""
        if not PYPROJ_AVAILABLE or not self._transformer_wgs_to_utm:
            # 간단한 평탄 지구 근사 (단거리용)
            lat_rad = math.radians(self.origin_lat)
            dlat = lat - self.origin_lat
            dlon = lon - self.origin_lon
            north = dlat * 111320.0  # 1도 ≈ 111.32km
            east = dlon * 111320.0 * math.cos(lat_rad)
            down = -alt
            return north, east, down

        # 정확한 변환: WGS84 -> UTM-K -> 로컬 NED
        x, y = self._transformer_wgs_to_utm.transform(lon, lat)
        # 기준점도 UTM으로 변환
        ox, oy = self._transformer_wgs_to_utm.transform(
            self.origin_lon, self.origin_lat
        )
        north = y - oy
        east = x - ox
        down = -alt
        return north, east, down

    def mil_to_degrees(self, mil: float) -> float:
        """밀 → 도 변환 (6400밀 = 360도)"""
        return mil * 360.0 / 6400.0

    def degrees_to_mil(self, deg: float) -> float:
        """도 → 밀 변환"""
        return deg * 6400.0 / 360.0

    def polar_to_ned(
        self, mil_azimuth: float, distance_m: float, mil_elevation: float = 0
    ) -> Tuple[float, float, float]:
        """밀 극좌표 → NED"""
        az_deg = self.mil_to_degrees(mil_azimuth)
        az_rad = math.radians(az_deg)
        el_rad = math.radians(self.mil_to_degrees(mil_elevation))

        # 수평 거리
        horizontal_dist = distance_m * math.cos(el_rad)
        north = horizontal_dist * math.cos(az_rad)
        east = horizontal_dist * math.sin(az_rad)
        down = -distance_m * math.sin(el_rad)

        return north, east, down


class BranchProfileManager:
    """병과별 프로파일 관리"""

    def __init__(
        self,
        custom_profiles: Optional[Dict[MilitaryBranch, BranchFlightProfile]] = None,
    ):
        self.profiles = {**DEFAULT_BRANCH_PROFILES}
        if custom_profiles:
            self.profiles.update(custom_profiles)

    def get_profile(self, branch: MilitaryBranch) -> BranchFlightProfile:
        return self.profiles.get(
            branch, DEFAULT_BRANCH_PROFILES[MilitaryBranch.INFANTRY]
        )

    def get_mission_params(self, branch: MilitaryBranch, mission_type: str) -> Dict:
        """미션 타입별 파라미터 병합"""
        # 문자열 입력이면 Enum으로 변환
        if isinstance(branch, str):
            branch = MilitaryBranch[branch]
        profile = self.get_profile(branch)
        base = {
            "altitude_agl": profile.default_altitude_agl,
            "speed_mps": profile.default_speed_mps,
            "loiter_radius_m": profile.loiter_radius_m,
            "loiter_pattern": profile.loiter_pattern,
            "gimbal_pitch": profile.gimbal_pitch_default,
            "eo_zoom": profile.eo_zoom_default,
            "ir_palette": profile.ir_palette,
        }

        if mission_type in profile.mission_overrides:
            base.update(profile.mission_overrides[mission_type])

        # 안전 제한 적용
        base["altitude_agl"] = max(base["altitude_agl"], profile.min_safe_altitude)
        base["altitude_agl"] = min(base["altitude_agl"], profile.max_altitude_agl)
        base["speed_mps"] = min(base["speed_mps"], profile.max_speed_mps)

        return base

    def update_profile(self, branch: MilitaryBranch, **kwargs):
        """프로파일 동적 업데이트"""
        profile = self.get_profile(branch)
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)


# ===== 편의 함수 =====


def parse_coordinates(text: str) -> List[ParsedCoordinate]:
    """텍스트에서 좌표 파싱"""
    parser = CoordinateParser()
    return parser.parse_coordinate(text)


def detect_branches(text: str) -> List[Tuple[MilitaryBranch, float]]:
    """텍스트에서 병과 탐지"""
    parser = CoordinateParser()
    return parser.detect_branch(text)


def convert_coordinate(
    coord: ParsedCoordinate, converter: CoordinateConverter
) -> ParsedCoordinate:
    """파싱된 좌표를 WGS84/NED로 변환"""
    try:
        if coord.coord_type in (
            CoordinateType.MGRS_10M,
            CoordinateType.MGRS_1M,
            CoordinateType.MGRS_ABBREV_6,
            CoordinateType.MGRS_ABBREV_8,
        ):
            lat, lon = converter.mgrs_to_wgs84(coord.raw_value)
            coord.lat, coord.lon = lat, lon
            coord.north, coord.east, coord.down = converter.wgs84_to_ned(lat, lon)

        elif coord.coord_type in (CoordinateType.LATLON_DMS, CoordinateType.LATLON_DEC):
            if coord.lat is not None and coord.lon is not None:
                coord.north, coord.east, coord.down = converter.wgs84_to_ned(
                    coord.lat, coord.lon
                )

        elif coord.coord_type == CoordinateType.MIL_POLAR:
            if coord.mil_azimuth is not None and coord.distance_m is not None:
                coord.north, coord.east, coord.down = converter.polar_to_ned(
                    coord.mil_azimuth, coord.distance_m, coord.mil_elevation or 0
                )

        elif coord.coord_type == CoordinateType.MIL_OFFSET:
            if coord.mil_azimuth is not None and coord.distance_m is not None:
                coord.north, coord.east, coord.down = converter.polar_to_ned(
                    coord.mil_azimuth, coord.distance_m, 0
                )
                # 기준점 보정 필요 (별도 처리)

        elif coord.coord_type == CoordinateType.UTM:
            if PYPROJ_AVAILABLE and converter._transformer_utm_to_wgs:
                # UTM -> WGS84 (구현 필요)
                pass

    except Exception as e:
        print(f"좌표 변환 오류: {e}")

    return coord


def get_branch_flight_params(
    branch: MilitaryBranch, mission_type: str = "default"
) -> Dict:
    """병과+미션별 비행 파라미터 조회"""
    manager = BranchProfileManager()
    return manager.get_mission_params(branch, mission_type)


# ===== CLI 테스트 =====

if __name__ == "__main__":
    # 좌표 파싱 테스트
    test_texts = [
        "타이거 1-3 델타 골프 1234 5678 접적 발생",
        "방위 3200밀 거리 3500미터 탄착 관측",
        "불스아이에서 좌 200밀 전방 1500미터 사격 요청",
        "위도 38도 12분 34초 북 경도 127도 45분 21초 동",
        "포병 관측반 불즈아이 DG 1234 5678에서 북 300밀",
        "정찰드론 철원 52S DG 12345 56789 전방 정찰",
    ]

    parser = CoordinateParser()
    converter = CoordinateConverter()
    branch_mgr = BranchProfileManager()

    print("=== 좌표 파싱 테스트 ===\n")
    for text in test_texts:
        print(f"입력: {text}")
        coords = parser.parse_coordinate(text)
        branches = parser.detect_branch(text)

        for coord in coords:
            converted = convert_coordinate(coord, converter)
            print(f"  좌표: {converted.coord_type.value} = {converted.raw_value}")
            if converted.lat is not None:
                print(f"    WGS84: ({converted.lat:.6f}, {converted.lon:.6f})")
            if converted.north is not None:
                print(
                    f"    NED: N={converted.north:.1f}m E={converted.east:.1f}m D={converted.down:.1f}m"
                )
            if converted.mil_azimuth is not None:
                print(
                    f"    밀: 방위 {converted.mil_azimuth}밀, 거리 {converted.distance_m}m"
                )

        if branches:
            print(
                f"  탐지된 병과: {', '.join(f'{b.value}({c:.1f})' for b, c in branches)}"
            )
            for branch, _ in branches:
                params = branch_mgr.get_mission_params(branch, "recon")
                print(
                    f"    {branch.value} 정찰 프로파일: 고도 {params['altitude_agl']}m, 속도 {params['speed_mps']}m/s, 짐벌 {params['gimbal_pitch']}도"
                )
        print()
