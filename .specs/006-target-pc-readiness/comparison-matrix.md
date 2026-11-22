# Q250-V3-Opti Mac ↔ 타 PC 준비도 비교 매트릭스

판정: `PASS` / `PARTIAL` / `MISMATCH` / `BLOCKED` / `NOT_CHECKED`

## A. 호스트·가상화

| 항목 | Mac 기준(실측) | 타 PC 기준 | 판정 | 증거/조치 |
|---|---|---|---|---|
| OS | macOS 13.7.8 | Linux/WSL2, `DESKTOP-IAOM8VS` | MISMATCH | WSL2 Ubuntu release/systemd 추가 확인 |
| CPU/arch | Intel x86_64 | Linux x86_64 | PARTIAL | CPU/RAM 상세 추가 확인 |
| Python | 3.9.4 | 시스템 3.10.12; Specify 3.11.18 | PARTIAL | Spec Kit은 3.11.18로 해결; Q250 런타임은 별도 venv 필요 |
| Docker CLI | 설치됨 | Windows Docker Desktop 경로 | PARTIAL | `docker info`, Compose, GPU 확인 |
| Docker daemon | 응답 없음 | 미점검 | NOT_CHECKED | 타겟에서 daemon 확인 필요 |
| GPU/CUDA | NVIDIA CUDA 없음 | 미점검 | NOT_CHECKED | `nvidia-smi`, WSL CUDA 확인 |
| 디스크 | root 약 3% 사용 | 미점검 | NOT_CHECKED | 데이터+컨테이너 여유 확인 |
| 네트워크 | Mac 기준 미점검 | 미점검 | NOT_CHECKED | UDP 14540/14550/5760 |
| USB/serial | Mac 후보 포트에서 heartbeat 없음 | 미점검 | NOT_CHECKED | 실제 FC 전 read-only |

## B. 운용·개발 소프트웨어

| 항목 | Mac 기준(실측/저장소) | 타 PC 기준 | 필수 |
|---|---|---|---|
| Git | 설치, 저장소 clean 기준 확인 | `/usr/bin/git` | PASS |
| CMake | brew 설치 확인 | `/usr/bin/cmake` | PASS |
| Ninja | brew 설치 확인 | 미확인 | GAP |
| ccache | brew 설치 확인 | 미확인 | OPTIONAL/PERFORMANCE |
| ROS 2 Humble | `ros2` 없음 | `/opt/ros/humble/bin/ros2` | PASS |
| colcon/rosdep | 없음 또는 미확인 | `/usr/bin/colcon`; rosdep 미확인 | PARTIAL |
| Gazebo Harmonic | `gz` 없음 | `/usr/bin/gz` | PASS, version 추가 확인 |
| PX4 v1.15 | CLI 없음; 소스 checkout은 별도 확인 필요 | 미확인 | NOT_CHECKED |
| MAVLink Router | 없음 | 미확인 | GAP |
| MicroXRCEAgent | 없음 | 미확인 | GAP |
| MAVSDK/pymavlink | Python import 확인 | 미확인 | NOT_CHECKED |
| MAVROS2 | ROS 계층 부재 | 미확인 | NOT_CHECKED |
| QGroundControl | CLI 미확인 | 미확인 | GAP |
| VS Code/Remote WSL | 미점검 | 미점검 | 개발 PC 권장 |

## C. Python/ML/음성/비전

| 항목 | Mac 기준(실측) | 타 PC 기준 | 조치 |
|---|---|---|---|
| numpy | 2.0.2 | 미점검 | Torch ABI 경고가 있어 고정 필요 |
| pandas | 2.3.3 | 미점검 | requirements와 비교 |
| scipy | 1.13.1 | 미점검 | requirements와 비교 |
| scikit-learn | 1.6.1 | 미점검 | requirements와 비교 |
| torch | 2.2.2 | 미점검 | CUDA 12.1 이미지 기준 검증 |
| torchvision | 0.17.2 | 미점검 | torch와 pair 확인 |
| OpenCV | 4.11.0 | 미점검 | headless/GUI 차이 기록 |
| MAVSDK | import됨 | 미점검 | 버전 출력 필요 |
| pymavlink | 2.4.49 | 미점검 | dialect 확인 |
| faster-whisper | 1.2.1 | 미점검 | ctranslate2 pair 확인 |
| librosa | import 실패 | 미점검 | 타 PC 필수 설치 |
| soundfile | 0.13.1 | 미점검 | audio smoke |
| transformers | 4.57.6 | 미점검 | NLU 사용 시 확인 |
| ONNX Runtime | 1.19.2 | 미점검 | GPU provider 확인 |
| CUDA torch | Mac 미지원 | 미점검 | `torch.cuda.is_available()` |

## D. 데이터셋

| 데이터셋 | Mac 상태 | 타 PC 상태 | 필수 판정 |
|---|---|---|---|
| drone_audio processed | metadata/경로 확인 | 미점검 | train/val/test + binary/multiclass |
| uzh_fpv processed | train/val/test 확인 | 미점검 | image/IMU/GT |
| idf_ds processed | train/val/test 확인 | 미점검 | sensor schema |
| ign_fixed_wing processed | train/val/test 확인 | 미점검 | camera/GCP |
| fixed_wing_attitude processed | train/val/test 확인 | 미점검 | sensor schema |
| fpv_analog processed | 대용량 약 55GB급 | 미점검 | 별도 전송 또는 제외 명시 |
| navigation_datasets | 존재 | 미점검 | 사용하는 경우 필수 |
| raw datasets | 일부 원본 존재 | 미점검 | 재처리 필요 시만 |
| metadata | 다수 `metadata.json` 확인 | 미점검 | JSON parse/shape 비교 |
| checksums | 일부 원본 checksum 확인 | 미점검 | 통합 manifest 생성 필요 |

## E. 체크포인트·모델

| 파일 | Mac SHA-256 | 타 PC SHA-256 | 판정 |
|---|---|---|---|
| `checkpoints/binary/best_model.pth` | `840c683b3264806bca834d4e47b56795b389b302ce285e4fb1b3f4d68e34e126` | 미점검 | NOT_CHECKED |
| `checkpoints/multiclass/best_model.pth` | `6978c5ce500dc733cbc701705681db49b9f4829599a2435756c74b8e0b405d92` | 미점검 | NOT_CHECKED |
| `models/denoising/deepfilter.onnx` | `e1157049059434ae0d5857e32c812abea227b975e946b2eb64d001abbce156d3` | 미점검 | NOT_CHECKED |
| `models/denoising/deepfilter-auxiliary.bin` | `47e84480f823ab95bee69d9f8a2344074e3d8e7dbb4370d44785b91698a4dca1` | 미점검 | NOT_CHECKED |
| `generated/mavlink/python.py` | `ca2299bf2d5090b0bed940dc5735143334d4083c11cf5916feb551a165bae538` | 미점검 | NOT_CHECKED |

## F. 통합 검증

| 검증 | Mac | 타 PC | 완료 조건 |
|---|---|---|---|
| Python tests | 미실행 in this check | 미점검 | 저장소 테스트 통과 |
| preprocessing loader | 데이터 존재 | 미점검 | 1 batch 성공 |
| Docker build | daemon 없음 | 미점검 | image build |
| Docker GPU | 불가 | 미점검 | CUDA healthcheck |
| ROS 2 build | 불가 | 미점검 | colcon success |
| PX4 SITL | 불가 | 미점검 | Q250 model launch |
| MAVLink heartbeat | 실제 FC 미검증 | 미점검 | SITL/FC 별도 기록 |
| Hardware preflight | Mac 후보 포트에서 heartbeat 없음 | 미점검 | read-only only |
| Hardware ARM | 실행 안 함 | 실행 금지 | 별도 승인·증거 필요 |

## 현재 결론

- Mac은 **데이터셋·소스·일부 Python/모델 준비 기준**이다.
- Mac은 현재 **ROS 2/PX4/Gazebo/Docker GPU 운용 기준을 충족한다고 볼 수 없다**.
- 타 PC는 접속·명령 실행 전이므로 모든 항목이 `NOT_CHECKED`다.
- 타 PC에서 먼저 `host inventory → tool inventory → dataset restore/checksum → Python/ROS build → SITL` 순서로 점검해야 한다.
- 실제 FC가 확인되기 전 최종 상한 판정은 `SIMULATION_READY`다.
