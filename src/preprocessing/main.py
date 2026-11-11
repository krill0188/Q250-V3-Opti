#!/usr/bin/env python3
"""
메인 전처리 파이프라인 실행 스크립트
"""

import argparse
import sys
from pathlib import Path
import logging

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.preprocessing import (
    create_pipeline,
    run_all_pipelines,
    DATASET_CONFIGS,
    create_pipeline,
)
from src.preprocessing.config import DatasetConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Drone Data Preprocessing Pipeline")
    parser.add_argument(
        "--dataset",
        "-d",
        choices=list(DATASET_CONFIGS.keys()) + ["all"],
        default="all",
        help="실행할 데이터셋 (기본: all)",
    )
    parser.add_argument("--config", "-c", type=str, help="설정 파일 경로 (YAML)")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="~/data/drone_datasets/processed",
        help="출력 디렉토리",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=["train", "val", "test"],
        default=["train", "val", "test"],
        help="생성할 분할",
    )
    parser.add_argument("--seq-len", type=int, default=100, help="시퀀스 길이")
    parser.add_argument("--stride", type=int, default=1, help="스트라이드")
    parser.add_argument("--target-len", type=int, default=1, help="타겟 길이")
    parser.add_argument("--batch-size", type=int, default=32, help="배치 크기")
    parser.add_argument("--num-workers", type=int, default=4, help="데이터로더 워커 수")
    parser.add_argument(
        "--dry-run", action="store_true", help="실제 실행 없이 설정만 확인"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")

    return parser.parse_args()


def load_custom_config(config_path: str) -> dict:
    """사용자 설정 파일 로드"""
    import yaml

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("Drone Data Preprocessing Pipeline")
    logger.info("=" * 60)

    # 설정 로드
    if args.config:
        custom_config = load_custom_config(args.config)
        logger.info(f"Loaded custom config: {args.config}")
    else:
        custom_config = {}

    # 데이터셋 선택
    if args.dataset == "all":
        datasets_to_run = list(DATASET_CONFIGS.keys())
    else:
        datasets_to_run = [args.dataset]

    logger.info(f"Datasets to process: {datasets_to_run}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Splits: {args.splits}")
    logger.info(f"Sequence length: {args.seq_len}")

    if args.dry_run:
        logger.info("DRY RUN - No actual processing")
        return 0

    # 파이프라인 실행
    try:
        # 설정 구성
        configs = {}
        for name in datasets_to_run:
            base_config = DATASET_CONFIGS[name]
            # 커스텀 설정 병합
            if name in custom_config:
                # 설정 병합 로직 필요
                pass
            configs[name] = base_config

        logger.info("Starting pipeline execution...")
        results = run_all_pipelines(configs)

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)

        for name, result in results.items():
            logger.info(f"  {name}: {result}")

        return 0

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
