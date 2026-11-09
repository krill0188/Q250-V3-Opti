#!/usr/bin/env python3
"""
PDF → 비디오 변환기 (TTS 내레이션 포함)
Fast prototype: 10분 / High quality: Manim + 합성
"""

import fitz  # pymupdf
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from gtts import gTTS
import os

PDF_PATH = "/tmp/drone_doc.pdf"
OUTPUT_DIR = "/tmp/drone_video_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def pdf_to_images(pdf_path, dpi=192):
    """PDF 페이지를 이미지로 변환"""
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_path = f"{OUTPUT_DIR}/page_{i+1:02d}.png"
        pix.save(img_path)
        images.append(img_path)
    doc.close()
    return images


def generate_narration(text, lang="ko", output_path=None):
    """TTS로 내레이션 생성"""
    if output_path is None:
        output_path = f"{OUTPUT_DIR}/narration.mp3"
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(output_path)
    return output_path


def create_video_from_pages(
    images, narrations=None, output_path="/tmp/drone_video.mp4", fps=24
):
    """이미지 + 오디오로 비디오 생성"""
    clips = []

    for i, img_path in enumerate(images):
        duration = 5.0  # 기본 5초/페이지

        # 오디오가 있으면 길이 맞춤
        if narrations and i < len(narrations) and os.path.exists(narrations[i]):
            audio = AudioFileClip(narrations[i])
            duration = max(duration, audio.duration)

        clip = ImageClip(img_path).with_duration(duration).with_fps(fps)

        if narrations and i < len(narrations) and os.path.exists(narrations[i]):
            audio = AudioFileClip(narrations[i])
            clip = clip.with_audio(audio)

        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac")
    return output_path


# 페이지별 내레이션 텍스트 (PDF 내용 기반)
NARRATIONS = [
    "AI LLM 기반 non-GPS 자율군집드론 만들기. Q250-V3 Opti 플랫폼으로 GPS 없이 실내외 자율비행을 구현합니다.",
    "자율비행 드론은 딱 5가지 계층으로 이해하세요. 1단계 눈과 귀: RealSense D435i 카메라와 IMU, LiDAR. 2단계 내 위치 파악: PX4 EKF2가 절대 위치를 계산. 3단계 판단: LLM은 3번 판단 계층에만 개입, 모터 직접 제어는 위험합니다. 4단계 비행 명령: PX4 OFFBOARD 모드로 1미터 가라는 식의 명령. 5단계 물리 동작: ESC와 BLDC 모터가 자세 제어와 모터 출력을 담당.",
    "하드웨어 역할 분리: 픽스호크 6C 미니는 실시간 자세 제어, 센서 융합 EKF2, 모터 출력, 안전 제어를 담당. 젯슨 오린은 비전 처리, VIO SLAM, 경로 계획을 담당. 젯슨이 아무리 빨라도 드론이 자동으로 안정적으로 나는 건 아닙니다. 자세 제어는 픽스호크 몫입니다. 고장 나면 페일세이프로 제자리 호버링이나 비상 착륙.",
    "VIO 원리: 카메라 특징점과 IMU 관성 데이터를 합쳐 6자유도 포즈 추정. RealSense D435i로 특징점 추출, IMU로 관성 데이터, PX4 EKF2에서 데이터 융합. 주의: 카메라 가림, 저조도 100룩스 미만, 무늬 없는 바닥에서는 드리프트와 로스 발생.",
    "회피 알고리즘 비교. 비AI 방식: 뎁스 카메라와 라이다로 거리값만 판단, 코스트맵 생성, 연산 빠르고 가벼움. AI 방식: YOLO 텐서RT로 사람이나 차량 특정 타겟 식별, 회피 규칙 차등 적용. 충돌 방지만 필요하면 비AI로 충분.",
    "가짜 GPS 원리: 실내에서 미션과 RTL, 지오펜스 쓰려면 전역 좌표 필요. VIO 로컬 포즈를 임의 원점 적용해 위도 경도로 강제 변환, MAVLink GPS_INPUT으로 전송. 주의: GPS 신호가 아님, 원점과 방향이 나갈 수 있으니 주의.",
    "실버스 메시 네트워크: 자가 치유로 누가 끊어져도 다른 드론으로 통신 유지, 홉 제한 없음. ROS 2 Fast-DDS로 드론끼리 실시간 위치 브로드캐스트해 군집 충돌 방지. 일반 와이파이 대비 수십 배 출력, 단일 홉 100Mbps, 최대 20-50km 통신.",
    "LLM과 AI 필요 여부: 기본 장애물 회피는 AI 불필요, 특정 타겟 식별은 YOLO 필요, 자연어 임무 명령은 LLM 번역 필요, 비행 로그 분석은 LLM 도움. 핵심: 이 시스템이 이해할 좌표와 경로로 번역, LLM은 고수준 보조만.",
    "멀티모달 비행 데이터 DB: ULog, 비디오, ROS2 토픽 수집. 핵심은 시간 정렬 - 이기종 데이터 타임스탬프 하나로 맞춤. 검색과 질의, 분석과 복기, 파라미터 튜닝 제안 자동화.",
    "SITL 시뮬레이션 필수: 한 번의 코드 오류로 수십만 원 손실 방지. 가상 환경 Gazebo에서 100% 동일한 제어 코드 실행. 이착륙, 장애물 회피, 통신 두절 시 비상 복귀 검증. 시뮬에서 100% 검증 안 된 코드는 실드론에 넣지 마세요.",
    "페일세이프 4대 시나리오: 통신 두절시 즉시 수동 모드 전환, 배터리 부족시 자동 RTL, 자율비행 폭주시 킬 스위치 작동, 지오펜스 이탈시 자동 RTL. 프로펠러 제거 후 벤치 테스트 필수.",
    "통합 테스트 체크리스트: 1단계 하드웨어 점검, 2단계 SITL 검증, 3단계 실내 비행 VIO 튜닝, 4단계 군집 테스트. 프로펠러 제거 후 벤치 테스트, VIO 튜닝과 회피 파라미터 100% 검증 후 실전.",
]


def main():
    print("📄 PDF → 이미지 변환 중...")
    images = pdf_to_images(PDF_PATH, dpi=192)
    print(f"✅ {len(images)}페이지 이미지 생성 완료")

    print("🎤 TTS 내레이션 생성 중...")
    narrations = []
    for i, text in enumerate(NARRATIONS):
        audio_path = f"{OUTPUT_DIR}/narration_{i+1:02d}.mp3"
        tts = gTTS(text=text, lang="ko", slow=False)
        tts.save(audio_path)
        narrations.append(audio_path)
    print(f"✅ {len(narrations)}개 내레이션 생성 완료")

    print("🎬 비디오 생성 중...")
    output_path = f"{OUTPUT_DIR}/drone_tutorial_final.mp4"

    clips = []
    for i, img_path in enumerate(images):
        duration = 5.0

        if i < len(NARRATIONS):
            audio_path = f"{OUTPUT_DIR}/narration_{i+1:02d}.mp3"
            if os.path.exists(audio_path):
                audio = AudioFileClip(audio_path)
                duration = max(duration, audio.duration)

        clip = ImageClip(img_path).with_duration(duration).with_fps(24)

        if os.path.exists(f"{OUTPUT_DIR}/narration_{i+1:02d}.mp3"):
            audio = AudioFileClip(f"{OUTPUT_DIR}/narration_{i+1:02d}.mp3")
            clip = clip.with_audio(audio)

        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        f"{OUTPUT_DIR}/drone_tutorial_final.mp4",
        fps=24,
        codec="libx264",
        audio_codec="aac",
    )
    print(f"✅ 비디오 생성 완료: {OUTPUT_DIR}/drone_tutorial_final.mp4")

    size_mb = os.path.getsize(f"{OUTPUT_DIR}/drone_tutorial_final.mp4") / (1024 * 1024)
    print(f"📊 파일 크기: {size_mb:.1f} MB")


if __name__ == "__main__":
    print("📄 PDF → 이미지 변환 중...")
    images = pdf_to_images("/tmp/drone_doc.pdf", dpi=192)
    print(f"✅ {len(images)}페이지 이미지 생성 완료")

    print("🎤 TTS 내레이션 생성 중...")
    for i, text in enumerate(NARRATIONS):
        audio_path = f"{OUTPUT_DIR}/narration_{i+1:02d}.mp3"
        tts = gTTS(text=NARRATIONS[i], lang="ko", slow=False)
        tts.save(audio_path)
    print(f"✅ {len(NARRATIONS)}개 내레이션 생성 완료")

    print("🎬 비디오 생성 중...")
    clips = []
    for i, img_path in enumerate(images):
        duration = 5.0

        audio_path = f"{OUTPUT_DIR}/narration_{i+1:02d}.mp3"
        if os.path.exists(audio_path):
            audio = AudioFileClip(audio_path)
            duration = max(duration, audio.duration)

        clip = ImageClip(img_path).with_duration(duration).with_fps(24)

        if os.path.exists(audio_path):
            audio = AudioFileClip(audio_path)
            clip = clip.with_audio(audio)

        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    output_path = f"{OUTPUT_DIR}/drone_tutorial_final.mp4"
    final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    print(f"✅ 비디오 생성 완료: {output_path}")

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"📊 파일 크기: {size_mb:.1f} MB")
