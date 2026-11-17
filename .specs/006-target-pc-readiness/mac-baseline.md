# Mac 기준선 — SpecKit/Hermes 및 Q250 준비 상태

- **기준 시각**: 2026-11-18 KST
- **저장소**: `Q250-V3-Opti`
- **저장소 HEAD**: `1e2ca47`
- **판정 원칙**: 이 문서는 Mac의 실측 기준선이며 타겟 PC 상태를 대신하지 않는다.

## 1. SpecKit/Hermes

| 항목 | Mac 결과 | 판정 |
|---|---|---|
| Hermes Agent | `/Users/amaster/.hermes/hermes-agent/.hermes/bin/hermes` | PASS |
| Hermes 버전 | `v0.22.6+481.gc314285` | PASS |
| 공식 Spec Kit CLI `specify` | command not found | BLOCKED |
| `uv` | `/Users/amaster/.local/bin/uv` | PASS |
| Python | `3.9.4` | MISMATCH — 공식 Spec Kit 기준 Python 3.11+ |
| `.specs/spec.md` | 존재 | PASS |
| `.specs/clarify.md` | 존재 | PASS |
| `.specs/plan.md` | 존재 | PASS |
| `.specs/tasks.md` | 존재 | PASS |
| `.specs/analyze.md` | 존재 | PASS |
| `CLAUDE.md` | 존재 | PASS |
| `AGENTS.md` | 없음 | GAP |
| 타겟 PC Hermes 접근 | 원격 확인 전 | NOT_CHECKED |

### 해석

현재 저장소는 SpecKit 스타일 산출물을 갖고 있지만 공식 Spec Kit CLI가 설치된 상태는 아니다. Hermes Agent와 공식 Spec Kit CLI는 별개다. 또한 현재 Mac Python 3.9.4는 최신 공식 Spec Kit 설치 기준인 Python 3.11+와 맞지 않는다.

## 2. Mac에서 확인된 주요 환경

| 영역 | 결과 | 판정 |
|---|---|---|
| OS | macOS 13.7.8 | 기준 전용 |
| CPU 아키텍처 | Intel x86_64 | 기준 전용 |
| ROS 2 | `ros2` 없음 | BLOCKED for ROS/SITL |
| colcon | 없음 | BLOCKED for ROS/SITL |
| Gazebo/gz | 없음 | BLOCKED for SITL |
| PX4 CLI | 없음 | BLOCKED for PX4 build |
| MAVLink Router | 없음 | BLOCKED for operation |
| MicroXRCEAgent | 없음 | BLOCKED for ROS/PX4 bridge |
| Docker CLI | 설치됨 | PARTIAL — daemon 확인 필요 |
| NVIDIA CUDA | 없음 | NOT_APPLICABLE on this Mac |
| QGroundControl CLI | 미확인 | NOT_CHECKED |

## 3. 데이터 기준선

Mac에 데이터셋과 처리본이 존재하지만, 타겟 PC의 준비 완료는 다음 재검증 후에만 판정한다.

- 필수 dataset train/val/test
- 각 split의 metadata.json
- NPZ shape/dtype/NaN/Inf
- normalizer/scaler 로드
- loader 1 batch
- 파일 수·바이트·SHA-256
- 체크포인트 및 모델 해시

대용량 `fpv_analog`는 기본 전송과 별도 관리한다.

## 4. 타겟 PC 비교 판정 규칙

타겟 PC에서 동일 점검 스크립트를 실행해 `target-baseline.md`와 JSON 결과를 만든다.

- Mac `PASS` + 타겟 `PASS`: 일치
- Mac `MISSING` + 타겟 `PASS`: 타겟 전용 제공 기능
- Mac `PASS` + 타겟 `MISSING`: 타겟 설치 누락
- 버전/OS/아키텍처 차이: `MISMATCH` 후 호환성 검증
- 타겟 미접속: `NOT_CHECKED`

실제 FC 검증 전 최고 판정은 `SIMULATION_READY`다.
