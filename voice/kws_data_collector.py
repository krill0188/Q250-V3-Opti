"""
KWS Data Collector - 음성 명령 학습 데이터 수집
각 키워드별 자연어 문장을 실제 음성으로 녹음하여 학습 데이터셋 구성
"""

import pyaudio
import wave
import json
import uuid
import time
import os
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime

from voice.keyword_specs import KEYWORD_SPECS, get_phrases_for_keyword


@dataclass
class CollectionConfig:
    """수집 설정"""

    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    record_seconds: float = 2.0  # 녹음 길이 (여유분 포함)
    format: int = pyaudio.paInt16
    samples_per_phrase: int = 3  # 문장당 녹음 횟수


@dataclass
class SampleMetadata:
    """샘플 메타데이터"""

    file: str
    keyword: str
    phrase: str
    speaker_id: str
    session_id: str
    timestamp: str
    duration: float
    sample_rate: int
    channels: int
    environment: str = "indoor"  # indoor, outdoor, windy, noisy
    noise_level: str = "low"  # low, medium, high
    distance: str = "near"  # near, medium, far
    notes: str = ""


class KWSDataCollector:
    """KWS 학습 데이터 수집기"""

    def __init__(
        self,
        output_dir: str = "~/data/kws_training",
        config: Optional[CollectionConfig] = None,
        speaker_id: str = "speaker_001",
        environment: str = "indoor",
        noise_level: str = "low",
        distance: str = "near",
    ):
        self.output_dir = Path(output_dir).expanduser()
        self.config = config or CollectionConfig()
        self.speaker_id = speaker_id
        self.environment = environment
        self.noise_level = noise_level
        self.distance = distance

        # 디렉토리 구조
        self.audio_dir = self.output_dir / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.output_dir / "metadata.jsonl"
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # PyAudio
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None

        # 통계
        self.stats = {
            "total_collected": 0,
            "by_keyword": {},
            "by_phrase": {},
            "start_time": datetime.now().isoformat(),
        }

    def _open_stream(self):
        """오디오 스트림 열기"""
        self.stream = self.p.open(
            format=self.config.format,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            frames_per_buffer=self.config.chunk_size,
        )

    def _close_stream(self):
        """오디오 스트림 닫기"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def record_phrase(
        self, keyword: str, phrase: str, count: Optional[int] = None
    ) -> List[SampleMetadata]:
        """특정 문장 녹음 (여러 번 반복)"""
        if count is None:
            count = self.config.samples_per_phrase

        print(f"\n{'='*60}")
        print(f"키워드: {keyword}")
        print(f'문장: "{phrase}"')
        print(f"반복: {count}회")
        print(f"{'='*60}")

        if not self.stream:
            self._open_stream()

        metadata_list = []

        for i in range(count):
            input(f'\n[{i+1}/{count}] 준비되면 Enter ("{phrase}")...')

            print("녹음 시작... 🔴")
            frames = []

            # 프리롤: 0.5초 대기 (첫 음절 놓치지 않게)
            preroll_frames = int(self.config.sample_rate / self.config.chunk_size * 0.5)
            for _ in range(preroll_frames):
                data = self.stream.read(
                    self.config.chunk_size, exception_on_overflow=False
                )
                frames.append(data)

            # 실제 녹음
            record_frames = int(
                self.config.sample_rate
                / self.config.chunk_size
                * self.config.record_seconds
            )
            for _ in range(record_frames):
                data = self.stream.read(
                    self.config.chunk_size, exception_on_overflow=False
                )
                frames.append(data)

            print("녹음 완료 ✓")

            # 저장
            sample_id = str(uuid.uuid4())[:8]
            filename = f"{keyword}_{self.speaker_id}_{sample_id}.wav"
            filepath = self.audio_dir / filename

            with wave.open(str(filepath), "wb") as wf:
                wf.setnchannels(self.config.channels)
                wf.setsampwidth(self.p.get_sample_size(self.config.format))
                wf.setframerate(self.config.sample_rate)
                wf.writeframes(b"".join(frames))

            # 메타데이터
            metadata = SampleMetadata(
                file=str(filepath.relative_to(self.output_dir)),
                keyword=keyword,
                phrase=phrase,
                speaker_id=self.speaker_id,
                session_id=self.session_id,
                timestamp=datetime.now().isoformat(),
                duration=self.config.record_seconds + 0.5,
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                environment=self.environment,
                noise_level=self.noise_level,
                distance=self.distance,
            )

            metadata_list.append(metadata)
            self._save_metadata(metadata)
            self._update_stats(keyword, phrase)

            print(f"저장: {filename}")

        return metadata_list

    def _save_metadata(self, metadata: SampleMetadata):
        """메타데이터 저장 (JSONL)"""
        with open(self.metadata_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(metadata), ensure_ascii=False) + "\n")

    def _update_stats(self, keyword: str, phrase: str):
        self.stats["total_collected"] += 1
        self.stats["by_keyword"][keyword] = self.stats["by_keyword"].get(keyword, 0) + 1
        self.stats["by_phrase"][phrase] = self.stats["by_phrase"].get(phrase, 0) + 1

    def collect_keyword(
        self,
        keyword: str,
        phrases: Optional[List[str]] = None,
        samples_per_phrase: Optional[int] = None,
    ) -> List[SampleMetadata]:
        """키워드의 모든 문장 수집"""
        if phrases is None:
            phrases = get_phrases_for_keyword(keyword)

        if not phrases:
            print(f"키워드 '{keyword}'에 대한 문장이 없습니다.")
            return []

        all_metadata = []
        for phrase in phrases:
            metadata = self.record_phrase(keyword, phrase, samples_per_phrase)
            all_metadata.extend(metadata)

        return all_metadata

    def collect_all_keywords(
        self,
        keywords: Optional[List[str]] = None,
        samples_per_phrase: int = 3,
        skip_existing: bool = True,
    ):
        """모든 키워드 순차 수집"""
        if keywords is None:
            keywords = [s.keyword for s in KEYWORD_SPECS]

        print(f"\n{'#'*60}")
        print(f"KWS 학습 데이터 수집 시작")
        print(f"대상 키워드: {len(keywords)}개")
        print(f"화자: {self.speaker_id}")
        print(f"환경: {self.environment}/{self.noise_level}/{self.distance}")
        print(f"{'#'*60}")

        self._open_stream()

        try:
            for kw_idx, keyword in enumerate(keywords):
                print(f"\n\n[{kw_idx+1}/{len(keywords)}] 키워드: {keyword}")

                # 기존 데이터 확인
                if skip_existing:
                    existing = self._count_existing(keyword)
                    needed = samples_per_phrase * len(get_phrases_for_keyword(keyword))
                    if existing >= needed:
                        print(f"  이미 충분한 데이터 있음 ({existing}개), 건너뜀")
                        continue

                self.collect_keyword(keyword, samples_per_phrase=samples_per_phrase)

                # 중간 저장
                self._print_progress()

        except KeyboardInterrupt:
            print("\n\n수집 중단됨 (Ctrl+C)")
        finally:
            self._close_stream()
            self.p.terminate()
            self._save_session_summary()

        print(f"\n\n수집 완료! 총 {self.stats['total_collected']}개 샘플")

    def _count_existing(self, keyword: str) -> int:
        return self.stats["by_keyword"].get(keyword, 0)

    def _print_progress(self):
        print(f"\n--- 진행 상황 ---")
        print(f"총 수집: {self.stats['total_collected']}개")
        for kw, cnt in sorted(self.stats["by_keyword"].items()):
            print(f"  {kw}: {cnt}개")

    def _save_session_summary(self):
        """세션 요약 저장"""
        summary = {
            "session_id": self.session_id,
            "speaker_id": self.speaker_id,
            "environment": self.environment,
            "noise_level": self.noise_level,
            "distance": self.distance,
            "config": asdict(self.config),
            "stats": self.stats,
            "end_time": datetime.now().isoformat(),
        }

        summary_file = self.output_dir / f"session_{self.session_id}_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"세션 요약 저장: {summary_file}")


class MultiSpeakerCollector:
    """다중 화자 수집 관리"""

    def __init__(self, base_dir: str = "~/data/kws_training"):
        self.base_dir = Path(base_dir).expanduser()

    def collect_for_speaker(
        self,
        speaker_id: str,
        keywords: Optional[List[str]] = None,
        samples_per_phrase: int = 3,
        environment: str = "indoor",
        noise_level: str = "low",
        distance: str = "near",
    ):
        """특정 화자 데이터 수집"""
        speaker_dir = self.base_dir / f"speaker_{speaker_id}"

        collector = KWSDataCollector(
            output_dir=str(speaker_dir),
            speaker_id=speaker_id,
            environment=environment,
            noise_level=noise_level,
            distance=distance,
        )

        collector.collect_all_keywords(
            keywords=keywords, samples_per_phrase=samples_per_phrase
        )

    def merge_all_speakers(self, output_dir: Optional[str] = None):
        """모든 화자 데이터 병합"""
        if output_dir is None:
            output_dir = self.base_dir / "merged"
        elif isinstance(output_dir, str):
            output_dir = Path(output_dir).expanduser()

        output_dir.mkdir(parents=True, exist_ok=True)
        merged_audio = output_dir / "audio"
        merged_audio.mkdir(exist_ok=True)

        all_metadata = []

        for speaker_dir in self.base_dir.glob("speaker_*"):
            if not speaker_dir.is_dir():
                continue

            metadata_file = speaker_dir / "metadata.jsonl"
            if not metadata_file.exists():
                continue

            with open(metadata_file, "r", encoding="utf-8") as f:
                for line in f:
                    meta = json.loads(line)
                    # 오디오 파일 복사
                    src = speaker_dir / meta["file"]
                    dst = merged_audio / meta["file"]
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if src.exists():
                        shutil.copy2(src, dst)
                    all_metadata.append(meta)

        # 병합된 메타데이터 저장
        with open(output_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
            for meta in all_metadata:
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")

        print(f"병합 완료: {len(all_metadata)}개 샘플 → {output_dir}")


def quick_collect(
    keywords: Optional[List[str]] = None,
    speaker_id: str = "test",
    samples: int = 5,
    output: str = "~/data/kws_quick",
):
    """빠른 테스트용 수집"""
    collector = KWSDataCollector(
        output_dir=output,
        speaker_id=speaker_id,
        config=CollectionConfig(samples_per_phrase=samples, record_seconds=1.5),
    )

    if keywords is None:
        keywords = [
            "emergency_stop",
            "land_now",
            "takeoff",
            "land",
            "hover",
            "move_forward",
            "move_backward",
            "move_left",
            "move_right",
            "dive_attack",
            "deceive_start",
            "mode_cruise",
            "mode_agile",
        ]

    collector.collect_all_keywords(keywords=keywords, samples_per_phrase=samples)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KWS 학습 데이터 수집")
    parser.add_argument("--speaker", default="speaker_001", help="화자 ID")
    parser.add_argument("--keywords", nargs="+", help="수집할 키워드 (기본: 전체)")
    parser.add_argument("--samples", type=int, default=3, help="문장당 샘플 수")
    parser.add_argument("--output", default="~/data/kws_training", help="출력 디렉토리")
    parser.add_argument("--env", default="indoor", help="환경 (indoor/outdoor)")
    parser.add_argument("--noise", default="low", help="소음 (low/medium/high)")
    parser.add_argument("--dist", default="near", help="거리 (near/medium/far)")
    parser.add_argument("--quick", action="store_true", help="빠른 테스트 모드")

    args = parser.parse_args()

    if args.quick:
        quick_collect(speaker_id=args.speaker, samples=args.samples, output=args.output)
    else:
        collector = KWSDataCollector(
            output_dir=args.output,
            speaker_id=args.speaker,
            environment=args.env,
            noise_level=args.noise,
            distance=args.dist,
        )

        keywords = args.keywords
        if not keywords:
            keywords = [s.keyword for s in KEYWORD_SPECS]

        collector.collect_all_keywords(
            keywords=keywords, samples_per_phrase=args.samples
        )
