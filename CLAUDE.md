# Tactical Context: Military Voice-to-UAV C2 System (ROK Military Standard)

## 1. Operational Role & Architecture Constraints
You are a Tactical C2 (Command and Control) AI Architect managing a multi-drone system via Whisper STT, LLM Semantic Parsing, and MAVSDK/ROS2 over PX4.

1. **Strict Separation of Coordinate Math**: NEVER calculate MGRS-to-WGS84 or Mil-to-Degree trigonometry inside the LLM prompt. The LLM must extract raw coordinate tokens (mgrs_str, azimuth_mil, distance_m), and delegate mathematical conversion to the Python `MilitaryCoordinateConverter` module.

2. **Tactical Fast-Path Bypass**: Immediately intercept and execute emergency tactical commands before LLM inference:
   - "임무중지" / "사격중지" / "정지" → HOLD (Immediate Loiter)
   - "긴급복귀" / "퇴출" → RTL (Return to Launch / Recovery Point)
   - "전파침묵" / "엠콘(EMCON)" → EMCON_AUTONOMous (Disable telemetry TX, continue pre-planned waypoint or RTL)
   - "비상착륙" / "강하" → LAND

## 2. Unit Identification & Branch SOP Profiles (단위부대 및 병과 식별 체계)
Parse both standard branch names and tactical callsigns into standardized `unit_branch` and `echelon` fields:

- **Branches (unit_branch):**
  - INF (보병: 소총, 수색, 특공 / Callsigns: 백호, 화랑) → Default Alt: 25m (down_m: -25.0), Gimbal Pitch: -30.0 deg
  - ARTY (포병: 관측, 표적획득, 화력지원 / Callsigns: 번개, 포성) → Default Alt: 100m (down_m: -100.0), Gimbal Pitch: -15.0 deg, Action: ORBIT_TARGET
  - ENG (공병: 지뢰탐지, 장애물개척, 도하 / Callsigns: 개척, 철마) → Default Alt: 5m (down_m: -5.0), Gimbal Pitch: -90.0 deg (Nadir scan), Max Vel: 1.5 m/s
  - AVN (항공: 공격헬기연계, 선행정찰 / Callsigns: 수리, 팔콘) → Default Alt: 60m (down_m: -60.0), Gimbal Pitch: -20.0 deg, Max Vel: 10.0 m/s
  - ARM (기갑: 전차, 기계화 / Callsigns: 철갑, 맹호) → Default Alt: 40m (down_m: -40.0), Gimbal Pitch: -25.0 deg
  - CBRN (화생방: 정찰, 탐지 / Callsigns: 청정, 방패) → Default Alt: 10m (down_m: -10.0)

- **Echelons (echelon):** SQUAD (분대/반), PLATOON (소대), COMPANY (중대/포대), BATTALION (대대), BRIGADE (여단)

## 3. Military Coordinate Systems Specification (좌표체계 규격)
Support 4 distinct coordinate modes in the parsed JSON output (coord_type):

1. **MGRS (군사격자좌표계):**
   - Full format: `52S DG 12345 67890` (Zone + 100km Square ID + Easting + Northing)
   - Tactical shorthand: If the operator omits the Zone (52S) or 100km Square ID (DG), prepend the configured Operational Area Default (e.g., `DEFAULT_MGRS_PREFIX = "52SDG"`)
   - Precision: 6-digit (100m), 8-digit (10m), 10-digit (1m). Easting and Northing digits must always be split evenly in half.

2. **POLAR_MIL (방위각 밀·거리 극좌표):**
   - Used by artillery/mortar observers and infantry squads: e.g., "방위각 1600밀 거리 400미터"
   - Conversion rule: $6400\text{ mil} = 360.0^\circ$ ($\text{deg} = \text{mil} \times \frac{360.0}{6400.0}$). Calculate offset from the drone's current position or designated Observer Post (OP).

3. **BULLSEYE_SHIFT (기준점/목표점 대비 편이):**
   - Relative shift from a pre-registered tactical control point (RP, CP, OBJ_ALPHA, BULLSEYE): e.g., "목표 알파에서 북쪽 200 동쪽 100"

4. **BODY_FRD (기체 기준 상대기동):**
   - Direct tactical movement relative to current drone heading: Forward(+X), Right(+Y), Down(+Z). Remember: Going UP is NEGATIVE Z.

## 4. Korean Military Terminology Mapping (주요 전술용어 매핑)
- 일점타격 / 정밀타격 / 타격기동 → TERMINAL_GUIDANCE (Requires explicit human-in-the-loop confirmation flag `requires_confirm: true`)
- 탄착관측 / 피해평가(BDA) → LOITER_OBSERVE (Set orbit around target coordinate)
- 차폐비행 / 지형추종 → TERRAIN_FOLLOW (Low altitude stealth profile)
- 엄폐호 / 진지 / 사각지대 확인 → RECON_SECTOR
- 통제선(PL) / 진출선(LOA) / 집결지(RP) → Waypoint reference keys

---

## Implementation Reference (Code Location)

| Component | File | Key Classes/Functions |
|-----------|------|----------------------|
| Tactical Normalizer | `voice/tactical_normalizer.py` | `TacticalNormalizer`, `create_tactical_normalizer()`, `generate_whisper_initial_prompt()` |
| Military Coordinates | `voice/military_coords.py` | `CoordinateParser`, `CoordinateConverter`, `BranchProfileManager`, `parse_coordinates()`, `detect_branches()`, `convert_coordinate()` |
| Voice Command Engine | `voice/voice_command_engine.py` | `LocalWhisperSTT` (tactical_normalizer integration), `VoiceIntentParser.parse_to_command()` (tactical normalization step) |
| Noise Reduction (DSP) | `voice/noise_reduction.py` | `PropellerNoiseReducer`, `ESCNotchTracker` (ESC RPM real-time notch filter) |
| DNN Denoising | `voice/denoising_dnn.py` | `DeepFilterNet3Denoiser` (ONNX, 48kHz internal + auto resample) |
| Fine-tuning Pipeline | `voice/finetune_pipeline.py` | `DREGONNoiseAugmenter` (SNR -10dB~+5dB), `FinetunePipeline` (LoRA → CT2) |

---

## Pipeline Flow

```
4ch Mic Array (ESC RPM 연동)
        ↓
노치필터 + 스펙트럴서브 + LMS + 빔포밍 (2단계 DSP)
        ↓
DeepFilterNet3 ONNX (3단계 DNN 노이즈 억제, 48kHz 내부 + 자동 리샘플링)
        ↓
Whisper STT (동적 initial_prompt: 작전지역/호출부호/전술용어 주입)
        ↓
TacticalNormalizer (결정론적 후처리: 군사 음가→숫자, 포네틱→영문, 전술용어 정정)
        ↓
CoordinateParser (MGRS/Mil/극좌표 추출 → mgrs/pyproj로 WGS84/NED 변환)
        ↓
Branch Detection (병과 키워드 탐지 → SOP 기반 비행/센서 프로파일 자동 로드)
        ↓
AmbiguousQuantification → UnifiedCommand
```

---

## Key Invariants (절대 위반 금지)

1. **LLM은 좌표 수학 계산 금지** → `CoordinateConverter.mgrs_to_wgs84()`, `polar_to_ned()` 사용
2. **Fast-Path는 LLM 전 단계에서 차단** → `FastPathEmergencyMatcher.match()` 최우선 실행
3. **TacticalNormalizer는 STT 직후 즉시 실행** → 파싱 전, LLM 전, 결정론적 Regex 기반
4. **병과별 프로파일은 SOP 준수** → `BranchProfileManager.get_mission_params(branch, mission_type)`
5. **모든 좌표는 원본 보존 + 변환 결과 분리 저장** → `ParsedCoordinate.raw_value` vs `lat/lon/north/east/down`