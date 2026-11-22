# Q250-V3-Opti Gazebo Sim 변환 스캐폴드

## 목적

`../q250_v3_opti/model.sdf` 원본을 수정하지 않고 PX4 v1.15.4 + Gazebo Sim용 변환을 시작하기 위한 별도 모델이다.

현재 스캐폴드는 다음을 보장한다.

- 원본 모델 보존
- Gazebo Classic 플러그인 미사용
- PX4 v1.15.4 공식 `gz-sim-multicopter-motor-model-system` 형식 사용
- XML well-formed 검증 가능
- 실제 mesh가 없으므로 primitive geometry 사용
- 센서 정의와 ROS bridge는 아직 별도 검증 대상

현재 스캐폴드만으로 `Q250_SITL_PASS`를 선언하지 않는다.

## 원본과 변환본

- 원본: `simulation/models/q250_v3_opti/`
- 변환본: `simulation/models/q250_v3_opti_gz/`
- 원본의 `model.sdf`, `sensors/*.sdf`, launch 파일은 수정하지 않는다.

## 타겟 PC 검증 절차

타겟 PC에서 저장소를 갱신한 뒤 PX4 트리에 복사한다. PX4 저장소를 직접 정리하거나 `git clean`하지 않는다.

```bash
cd ~/Q250-V3-Opti
xmllint --noout simulation/models/q250_v3_opti_gz/model.sdf
xmllint --noout simulation/models/q250_v3_opti_gz/model.config

cd ~/PX4-Autopilot-v1.15.4
mkdir -p Tools/simulation/gz/models
cp -a ~/Q250-V3-Opti/simulation/models/q250_v3_opti_gz \
  Tools/simulation/gz/models/
```

Q250 모델을 PX4 시작 스크립트로 연결하기 전, 먼저 Gazebo가 모델 SDF를 읽는지 확인한다.

```bash
cd ~/PX4-Autopilot-v1.15.4
GZ_SIM_RESOURCE_PATH="$PWD/Tools/simulation/gz/models:${GZ_SIM_RESOURCE_PATH:-}" \
  gz sdf -k Tools/simulation/gz/models/q250_v3_opti_gz/model.sdf
```

## PX4 airframe 연결

PX4의 airframe 파일은 PX4 저장소에 별도 변경으로 추가해야 한다. 모델 SDF 검증이 통과한 뒤에만 추가한다.

권장 ID는 프로젝트에서 아직 사용하지 않는지 먼저 확인한 후 결정한다.

```bash
grep -RIn '4001_q250\|q250_v3_opti' \
  ROMFS/px4fmu_common/init.d-posix/airframes \
  Tools/simulation/gz 2>/dev/null || true
```

airframe 추가 후에는 최소한 다음 방식으로 연결 여부를 시험한다.

```bash
PX4_SYS_AUTOSTART=<확정한_ID> \
PX4_SIM_MODEL=q250_v3_opti_gz \
GZ_SIM_RESOURCE_PATH="$PWD/Tools/simulation/gz/models:${GZ_SIM_RESOURCE_PATH:-}" \
  ./build/px4_sitl_default/bin/px4
```

모델 이름과 airframe ID가 공식 PX4 시작 스크립트의 검색 규칙과 일치하는지 확인하기 전에는 `make px4_sitl gz_q250_v3_opti`를 사용하지 않는다. 이 모델은 현재 공식 Make target이 아니다.

## 남은 검증

- 실제 Q250 mesh 파일 복원 또는 primitive 유지 결정
- 모터 joint 방향과 thrust 계수 검증
- Gazebo Sim 센서 topic 확인
- `ros_gz_bridge.yaml`의 실제 Gazebo topic과 대조
- uXRCE-DDS Agent와 `/fmu/out/*` 연결
- PX4 heartbeat 및 SITL telemetry
- 데이터·실제 FC 검증은 이 모델 스캐폴드와 별도 판정
