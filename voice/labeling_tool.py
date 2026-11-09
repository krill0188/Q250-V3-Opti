"""
STT 데이터 라벨링 도구 (CLI/Web)
- pending 리뷰 목록 확인
- 오디오 재생 및 정답 텍스트 입력
- 학습 데이터로 승인/거절
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import subprocess
import sys

logger = logging.getLogger(__name__)


class STTLabelingTool:
    """STT 결과 검토 및 라벨링 CLI 도구"""

    def __init__(self, log_dir: str = "~/models/stt_logs"):
        from voice.finetune_pipeline import STTLogCollector
        self.collector = STTLogCollector(log_dir)

    def list_pending(self) -> List[Dict]:
        """검토 대기 목록 출력"""
        pending = self.collector.load_pending_review()
        if not pending:
            print("검토 대기 항목이 없습니다.")
            return []

        print(f"\n=== 검토 대기 목록 ({len(pending)}개) ===")
        for i, item in enumerate(pending):
            print(f"\n[{i}] {item['audio_path']}")
            print(f"    STT: '{item['stt_text']}'")
            print(f"    신뢰도: {item['confidence']:.2f}")
            print(f"    시간: {item['timestamp']}")
            meta = item.get('metadata', {})
            if meta:
                print(f"    메타: {meta}")

        return pending

    def play_audio(self, audio_path: str):
        """오디오 재생 (플랫폼별 기본 플레이어)"""
        path = Path(audio_path).expanduser()
        if not path.exists():
            print(f"파일 없음: {path}")
            return False

        try:
            if sys.platform == "darwin":  # macOS
                subprocess.run(["afplay", str(path)], check=False)
            elif sys.platform == "linux":
                subprocess.run(["aplay", str(path)], check=False)
            elif sys.platform == "win32":
                os.startfile(str(path))
            else:
                print("지원하지 않는 플랫폼")
                return False
            return True
        except Exception as e:
            print(f"재생 실패: {e}")
            return False

    def review_item(self, index: int):
        """개별 항목 검토"""
        pending = self.collector.load_pending_review()
        if not (0 <= index < len(pending)):
            print("잘못된 인덱스")
            return

        item = pending[index]
        print(f"\n--- 검토 [{index}] ---")
        print(f"파일: {item['audio_path']}")
        print(f"STT 결과: '{item['stt_text']}'")
        print(f"신뢰도: {item['confidence']:.2f}")

        # 오디오 재생
        print("\n오디오 재생 중... (Enter로 계속)")
        self.play_audio(item['audio_path'])
        input()

        # 정답 텍스트 입력
        print("정답 텍스트를 입력하세요 (빈칸=거절, 'skip'=건너뛰기):")
        ground_truth = input("> ").strip()

        if ground_truth.lower() == "skip":
            print("건너뛰기")
            return
        elif not ground_truth:
            # 거절 처리
            self._reject_item(index)
            print("거절됨")
            return

        # 승인 및 학습 데이터로 이동
        self.collector.approve_pending(index, ground_truth)
        print(f"승인됨: '{ground_truth}'")

    def _reject_item(self, index: int):
        """항목 거절 (대기 목록에서 제거)"""
        lines = []
        with open(self.collector.pending_file, "r", encoding="utf-8") as f:
            lines = [json.loads(l.strip()) for l in f]

        if 0 <= index < len(lines):
            lines[index]["status"] = "rejected"
            with open(self.collector.pending_file, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(json.dumps(l, ensure_ascii=False) + "\n")

    def review_all(self):
        """전체 검토 모드"""
        pending = self.list_pending()
        if not pending:
            return

        print("\n명령어: [Enter]=재생/검토, 'q'=종료, 's'=건너뛰기")
        for i in range(len(pending)):
            print(f"\n[{i+1}/{len(pending)}]")
            self.play_audio(pending[i]['audio_path'])

            cmd = input("명령 (Enter/검토, s/건너뛰기, q/종료): ").strip().lower()
            if cmd == 'q':
                break
            elif cmd == 's':
                continue
            else:
                self.review_item(i)
                # 목록 새로고침
                pending = self.collector.load_pending_review()

    def export_training_data(self, output_path: str, min_confidence: float = 0.7):
        """학습 데이터 내보내기 (HuggingFace datasets 형식)"""
        from datasets import Dataset
        data = self.collector.load_training_data(min_confidence=min_confidence)

        if not data:
            print("내보낼 데이터가 없습니다.")
            return

        ds = Dataset.from_list(data)
        ds.save_to_disk(output_path)
        print(f"학습 데이터 내보내기 완료: {output_path} ({len(data)}개)")

    def stats(self):
        """통계 출력"""
        data = self.collector.load_training_data(min_confidence=0.0)
        pending = self.collector.load_pending_review()

        print("\n=== STT 데이터 통계 ===")
        print(f"학습 데이터 (검토 완료): {len(data)}개")
        print(f"검토 대기: {len(pending)}개")

        if data:
            confidences = [d.get('confidence', 0) for d in data if 'confidence' in d]
            if confidences:
                print(f"평균 신뢰도: {sum(confidences)/len(confidences):.2f}")
                print(f"최소/최대 신뢰도: {min(confidences):.2f} / {max(confidences):.2f}")

            # 텍스트 길이 통계
            lengths = [len(d.get('ground_truth', '')) for d in data]
            print(f"평균 텍스트 길이: {sum(lengths)/len(lengths):.1f}자")


def main():
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="STT Labeling Tool for Whisper Fine-tuning")
    parser.add_argument("--log-dir", default="~/models/stt_logs", help="Log directory")
    parser.add_argument("--list", action="store_true", help="List pending items")
    parser.add_argument("--review", type=int, help="Review specific index")
    parser.add_argument("--review-all", action="store_true", help="Review all pending")
    parser.add_argument("--export", help="Export training data to path")
    parser.add_argument("--min-conf", type=float, default=0.7, help="Min confidence for export")
    parser.add_argument("--stats", action="store_true", help="Show statistics")

    args = parser.parse_args()

    tool = STTLabelingTool(args.log_dir)

    if args.list:
        tool.list_pending()
    elif args.review is not None:
        tool.review_item(args.review)
    elif args.review_all:
        tool.review_all()
    elif args.export:
        tool.export_training_data(args.export, args.min_conf)
    elif args.stats:
        tool.stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()