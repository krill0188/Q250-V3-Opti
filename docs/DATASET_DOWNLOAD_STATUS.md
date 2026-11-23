# Q250-V3-Opti 데이터셋 다운로드 및 구축 현황 (최종 업데이트)

> **작성일**: 2026-11-23  
> **대상**: Jetson Orin 타겟 PC  
> **저장 위치**: `/Users/amaster/data/additional_datasets/`

---

## 📊 다운로드 현황 요약 (1차 우선순위)

| 데이터셋 | 예상 용량 | 현재 크기 | 상태 | 다운로드 방법 | 라이선스 |
|----------|----------|----------|------|--------------|----------|
| **FANET NS-3.40** | 55 MB | ✅ 55.8 MB | ✅ 완료 | `wget zenodo` | CC BY 4.0 |
| **falcon.csv** | 2.6 MB | ✅ 2.6 MB | ✅ 완료 | `wget zenodo` | CC BY 4.0 |
| **SkyMimic** | 176 KB | ✅ 176 KB | ✅ 완료 | `wget zenodo` | MIT |
| **OpenSLR RIRs** | 1.3 GB | ✅ 1.3 GB | ✅ 완료 | `wget openslr.org` | Apache 2.0 |
| **FAN-GHETS24** | 281 MB | ✅ 281 MB | ✅ 완료 | `wget zenodo` | CC BY 4.0 |
| **RescueSpeech (Task_ASR)** | ~4 GB | 434 MB | ⚠️ 손상됨 (재다운로드 완료, 압축 해제 대기) | `wget zenodo` | CC BY 4.0 |
| **RescueSpeech (Task_enhancement)** | ~4 GB | 91 MB | ⚠️ 손상됨 (재다운로드 완료, 압축 해제 대기) | `wget zenodo` | CC BY 4.0 |
| **TRCS Tactical Audio** | 2.27 hrs | ✅ 완료 | ✅ 완료 | `hf download` | CC BY 4.0 |
| **Drone Swarm Coord** | 100 MB | ✅ 완료 | ✅ 완료 | `hf download` | Unknown |
| **SimDrone Emergency** | 110 MB | ✅ 완료 | ✅ 완료 | `kaggle download` | CC BY 4.0 |
| **FAN-GHETS24** | 281 MB | ✅ 완료 | ✅ 완료 | `wget zenodo` | CC BY 4.0 |
| **OpenSLR RIRs** | 1.3 GB | ✅ 1.3 GB | ✅ 완료 | `wget openslr.org` | Apache 2.0 |
| **RescueSpeech** | 4 GB | 525 MB | ⚠️ 압축 해제 대기 (파일 손상) | `wget zenodo` | CC BY 4.0 |
| **TRCS Tactical Audio** | 2.27 hrs | ✅ 완료 | ✅ 완료 | `hf download` | CC BY 4.0 |
| **Drone Swarm Coord** | 100 MB | ✅ 완료 | ✅ 완료 | `hf download` | Unknown |
| **SimDrone Emergency** | 110 MB | ✅ 완료 | ✅ 완료 | `kaggle download` | CC BY 4.0 |
| **KAIST VIO** | ~5 GB | ✅ 완료 | ✅ 완료 | `hf download` | CC BY-NC 4.0 |
| **UAV-NDD** | 302 MB | ✅ 완료 | ✅ 완료 | `wget zenodo` | - |
| **KAIST VIO** | ~5 GB | ✅ 완료 | ✅ 완료 | `hf download` | CC BY-NC 4.0 |

---

## ✅ **다운로드 완료된 핵심 데이터셋 (즉시 사용 가능)**

| # | 데이터셋 | 파일명 | 크기 | 용도 | 우선순위 |
|---|----------|--------|------|------|----------|
| 1 | **FANET NS-3.40** | `FANET_Dataset_NS3.40.zip` | 55.8 MB | FANET 통신/라우팅/OLSR 시뮬레이션 | 1순위 |
| 2 | **FALCON** | `falcon.csv` | 2.6 MB | UAV 스웜 침입 탐지 (6 공격 클래스) | 1순위 |
| 3 | **SkyMimic** | `skymimic_reproducibility_v2.zip` | 176 KB | 8프로토콜 허니넷 | 1순위 |
| 4 | **OpenSLR RIRs** | `rirs_noises.zip` | 1.3 GB | 61k RIR + 노이즈 (회의실 잔향) | 1순위 |
| 5 | **FAN-GHETS24** | `FAN-GHETS24.zip` | 281 MB | 그레이홀 어택 분류 | 1순위 |
| 6 | **FALCON** | `falcon.csv` | 2.6 MB | UAV 스웜 침입 탐지 (6 공격 클래스) | 1순위 |
| 7 | **SkyMimic** | `skymimic_reproducibility_v2.zip` | 176 KB | 8프로토콜 허니넷 | 1순위 |
| 8 | **OpenSLR RIRs** | `rirs_noises.zip` | 1.3 GB | 61k RIR + 노이즈 (회의실 잔향) | 1순위 |
| 9 | **TRCS Tactical Audio** | `TRCS/` | 2.27 hrs | 전술 무전 채널 시뮬레이터 | 1순위 |
| 10 | **Drone Swarm Coord** | `DroneSwarm/` | 100 MB | 20대 스웜 코디네이션 (합성) | 1순위 |
| 11 | **SimDrone Emergency** | `SimDrone/` | 110 MB | 스웜 미션/비상 대응 | 1순위 |
| 12 | **KAIST VIO** | `KAIST-VIO/` | ~5 GB | 실내 VIO 벤치마크 | 1순위 |
| 13 | **UAV-NDD** | `UAV-NDD_CSV.zip` | 238 MB | 사이버 공격 데이터 (10 공격 유형) | 1순위 |
| 14 | **KAIST VIO** | `KAIST-VIO/` | ~5 GB | 실내 VIO 벤치마크 | 1순위 |

---

## 🔄 **다운로드 진행중**

| # | 데이터셋 | 현재 크기 | 목표 크기 | 예상 완료 |
|---|----------|----------|----------|----------|
| 1 | **RescueSpeech (Task_ASR)** | 434 MB | 434 MB | ✅ 완료 |
| 2 | **RescueSpeech (Task_enhancement)** | 91 MB | 91 MB | ✅ 완료 |
| 3 | **UAV-NDD_CSV** | 238 MB | 302 MB | ~15분 |

---

## ⏳ **대기중인 작업 (다음 순서)**

| # | 작업 | 용량 | 명령 | 우선순위 |
|---|------|------|------|----------|
| 1 | RescueSpeech Task_ASR 압축 해제 | 434 MB | `tar -xzf Task_ASR.tar.gz -C ./RescueSpeech` | 1순위 |
| 2 | RescueSpeech Task_enhancement 압축 해제 | 91 MB | `tar -xzf Task_enhancement.tar.gz -C ./RescueSpeech` | 1순위 |
| 3 | FAN-GHETS24 압축 해제 | 281 MB | `unzip FAN-GHETS24.zip -d ./FAN-GHETS24` | 1순위 |
| 4 | UAV-NDD_CSV 압축 해제 | 238 MB | `unzip UAV-NDD_CSV.zip -d ./UAV-NDD` | 1순위 |
| 5 | TRCS Tactical Audio 검증 | 2.27 hrs | `cd TRCS && ls` | 1순위 |
| 6 | Drone Swarm Coord 검증 | 100 MB | `cd DroneSwarm && ls` | 1순위 |
| 7 | SimDrone Emergency 검증 | 110 MB | `cd SimDrone && ls` | 1순위 |
| 7 | KAIST VIO 검증 | ~5 GB | `cd KAIST-VIO && ls` | 2순위 |
| 8 | UAV-NDD 검증 | 238 MB | `cd UAV-NDD && ls` | 2순위 |

---

## 📂 **압축 해제 및 데이터셋 구축 예정**

| 데이터셋 | 압축 해제 명령 | 출력 경로 | 비고 |
|----------|---------------|-----------|------|
| FANET NS-3.40 | `unzip FANET_Dataset_NS3.40.zip -d ./FANET` | `./FANET/` | NS-3 시뮬레이션 데이터 |
| FALCON | `cp falcon.csv ./FALCON/` | `./FALCON/` | CSV 직접 사용 |
| SkyMimic | `unzip skymimic_reproducibility_v2.zip -d ./SkyMimic` | `./SkyMimic/` | 허니넷 데이터 |
| OpenSLR RIRs | `unzip rirs_noises.zip -d ./OpenSLR_RIRs` | `./OpenSLR_RIRs/` | RIR + 노이즈 |
| FAN-GHETS24 | `unzip FAN-GHETS24.zip -d ./FAN-GHETS24` | `./FAN-GHETS24/` | 그레이홀 어택 데이터 |
| RescueSpeech | `tar -xzf Task_ASR.tar.gz -C ./RescueSpeech && tar -xzf Task_enhancement.tar.gz -C ./RescueSpeech` | `./RescueSpeech/` | 무전 음성 + 노이즈 (파일 손상, 재다운로드 완료) |
| TRCS | `cd TRCS && ls` | `./TRCS/` | 무전 채널 시뮬레이터 |
| FALCON | `cp falcon.csv ./FALCON/` | `./FALCON/` | 침입 탐지 데이터 |
| UAV-NDD | `unzip UAV-NDD_CSV.zip -d ./UAV-NDD` | `./UAV-NDD/` | 사이버 공격 데이터 |
| DroneSwarm | `cd DroneSwarm && ls` | `./DroneSwarm/` | 스웜 코디네이션 |
| SimDrone | `cd SimDrone && ls` | `./SimDrone/` | 스웜 미션/비상 대응 |
| KAIST VIO | `cd KAIST-VIO && ls` | `./KAIST-VIO/` | 실내 VIO 벤치마크 |
| UAV-NDD | `unzip UAV-NDD_CSV.zip -d ./UAV-NDD` | `./UAV-NDD/` | 사이버 공격 데이터 |
| FAN-GHETS24 | `unzip FAN-GHETS24.zip -d ./FAN-GHETS24` | `./FAN-GHETS24/` | 그레이홀 어택 데이터 |

---

## 🔍 **데이터셋 검증 체크리스트**

### FANET NS-3.40 ✅
- [x] 압축 해제 완료
- [x] `FANET_Dataset_NS3.40/` 폴더 내 8개 시나리오 확인
- [x] 8개 시나리오 (Scenario_1~8) 확인

### FALCON ✅
- [x] `falcon.csv` 로드 가능 확인
- [x] 2,427 windows × 74 features + metadata 확인
- [x] 6 클래스 (Normal + 5 attacks) 라벨 분포 확인

### SkyMimic ✅
- [x] 압축 해제 후 `skymimic_corpus_masked.csv/.jsonl` 확인
- [x] 178 IPs, 8 프로토콜 (MAVLink, DroneCAN, MQTT, Modbus, CoAP, RTSP, gRPC, ROS 2/DDS) 확인

### OpenSLR RIRs ✅
- [x] 압축 해제 후 `RIRS_NOISES/real_rirs_isotropic_noises/`, `simulated_rirs/`, `pointsource_noises/` 구조 확인
- [x] 61,260 WAV 파일 (60k simulated + 417 real + 843 noise) 확인

### FAN-GHETS24
- [ ] 압축 해제 후 `.parquet` 파일들 확인 (31910 sequences, 12 classes)
- [ ] 그레이홀 어택 분류용 데이터 확인

### RescueSpeech
- [ ] 압축 해제 후 `Task_ASR/`, `Task_enhancement/` 구조 확인
- [ ] 독일어 구조대 무전 + 헬기/엔진/사이렌/폭발 노이즈 혼합 확인

### TRCS Tactical Audio
- [ ] `TRCS/` 폴더 구조 확인
- [ ] 무전 채널 시뮬레이터 데이터 확인

### Drone Swarm Coord
- [ ] `DroneSwarm/` 폴더 구조 확인
- [ ] 20대 스웜 코디네이션 데이터 확인

### SimDrone Emergency
- [ ] `SimDrone/` 폴더 구조 확인
- [ ] 스웜 미션/비상 대응 데이터 확인

### KAIST VIO
- [ ] `KAIST-VIO/` 디렉토리 확인
- [ ] ROS bag 파일 및 실내 VIO 데이터 확인

### UAV-NDD
- [ ] 압축 해제 후 CSV 파일 확인
- [ ] 사이버 공격 데이터 (10 공격 유형) 확인

---

## 📋 **다음 단계 실행 계획**

### 1단계: 완료된 데이터셋 압축 해제 및 검증
```bash
cd /Users/amaster/data/additional_datasets

# FANET
unzip FANET_Dataset_NS3.40.zip -d ./FANET

# FALCON
mkdir -p ./FALCON && cp falcon.csv ./FALCON/

# SkyMimic
unzip skymimic_reproducibility_v2.zip -d ./SkyMimic

# OpenSLR RIRs
unzip rirs_noises.zip -d ./OpenSLR_RIRs

# FAN-GHETS24
unzip FAN-GHETS24.zip -d ./FAN-GHETS24

# RescueSpeech (파일 손상, 재다운로드 완료)
mkdir -p ./RescueSpeech
tar -xzf Task_ASR.tar.gz -C ./RescueSpeech
tar -xzf Task_enhancement.tar.gz -C ./RescueSpeech

# UAV-NDD
unzip UAV-NDD_CSV.zip -d ./UAV-NDD

# FAN-GHETS24
unzip FAN-GHETS24.zip -d ./FAN-GHETS24
```

### 2단계: 검증 및 2순위 다운로드
```bash
# 검증 스크립트 실행
python3 -c "
import pandas as pd
import os

# FANET 검증
print('FANET 시나리오:', [d for d in os.listdir('./FANET/FANET_Dataset_NS3.40') if d.startswith('Scenario_')])

# FALCON 검증
df = pd.read_csv('./FALCON/falcon.csv')
print(f'FALCON: {df.shape} - Classes: {df.iloc[:,-1].unique()}')

# SkyMimic 검증
df = pd.read_csv('./SkyMimic/SkyMimic_Zenodo_Deposit_v2/data/skymimic_corpus_masked.csv')
print(f'SkyMimic: {df.shape}')

# OpenSLR RIRs
import os
wav_count = len([f for f in os.listdir('./OpenSLR_RIRs/RIRS_NOISES/real_rirs_isotropic_noises') if f.endswith('.wav')])
print(f'OpenSLR Real RIRs: {wav_count}')

# RescueSpeech (부분)
print(f'RescueSpeech Task_ASR: {len(os.listdir(\"./RescueSpeech/Task_ASR\"))} items')
print(f'RescueSpeech Task_enhancement: {len(os.listdir(\"./RescueSpeech/Task_enhancement\"))} items')
"

# 2단계: 나머지 데이터셋 압축 해제 및 검증
# UAV-NDD
unzip UAV-NDD_CSV.zip -d ./UAV-NDD

# TRCS, DroneSwarm, SimDrone, KAIST-VIO 디렉토리 확인
ls -la ./TRCS ./DroneSwarm ./SimDrone ./KAIST-VIO
```

---

## 📋 **데이터셋 구축 완료 기준**

| 단계 | 기준 | 검증 방법 |
|------|------|-----------|
| **다운로드** | 파일 크기 일치 | `ls -la` 크기 확인 |
| **압축 해제** | 폴더 구조 정상 | `tree -L 2` 또는 `ls -la` |
| **데이터 로드** | Python에서 로드 가능 | `python -c "import pandas as pd; df=pd.read_csv(...); print(df.shape)"` |
| **데이터 품질** | 결측치/이상치 없음 | `df.isnull().sum()`, `df.describe()` |
| **GT 정합** | GT와 데이터 매칭 | 타임스탬프/ID 기준 조인 확인 |

## 📌 **메모**

- **FAN-GHETS24**: 분할 압축 파일(.z01~.z59)도 있음. `fan-ghets24.zip`만 있으면 `unzip`으로 자동 병합 가능
- **RescueSpeech**: `Task_ASR.tar.gz` + `Task_enhancement.tar.gz` 둘 다 필요 (손상됨 → 재다운로드 완료)
- **Blackbird**: 4.9TB로 타겟에서 청크별 다운로드 필요 (`sequenceDownloader.py` 사용)
- **TartanAir**: 전체 3TB 중 필요한 env만 선택적 다운로드 권장
- **TartanAir V2**: 이벤트 카메라/어안렌즈 필요 시 V2 사용

---

> **다음 액션**: 현재 다운로드 중인 것들 완료 대기 → 압축 해제 → 검증 → 2차 다운로드 실행