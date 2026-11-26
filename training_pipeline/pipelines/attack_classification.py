"""
FAN-GHETS24 Attack Classification Pipeline
"""

import sys

sys.path.append("/Users/amaster/data/additional_datasets/training_pipeline")

import json
from pathlib import Path

from data.sequence_dataset import load_fanghets_data

from training.sequence_trainer import run_fanghets_training


def main():
    config_path = (
        "/Users/amaster/data/additional_datasets/training_pipeline/config/fanghets.yaml"
    )

    print("=" * 60)
    print("FAN-GHETS24 ATTACK CLASSIFICATION PIPELINE")
    print("=" * 60)

    # 1. 데이터 로드 및 전처리
    print("\n[1/4] Loading and preprocessing data...")
    data = load_fanghets_data(config_path)

    # 2. 모델 훈련
    print("\n[2/4] Training model...")
    trainer = run_fanghets_training(config_path, data)

    # 3. 결과 저장
    print("\n[3/4] Saving results...")
    results = {
        "best_val_f1": (
            max(trainer.history["val_f1"]) if trainer.history["val_f1"] else 0
        ),
        "history": trainer.history,
        "class_names": (
            trainer.class_names.tolist()
            if hasattr(trainer.class_names, "tolist")
            else list(trainer.class_names)
        ),
        "model_type": trainer.model_cfg["type"],
        "input_dim": data["input_dim"],
        "num_classes": data["num_classes"],
    }

    output_dir = Path(
        "/Users/amaster/data/additional_datasets/training_pipeline/outputs/fanghets"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # 4. ONNX Export (선택적)
    print("\n[4/4] Exporting to ONNX...")
    try:
        export_onnx(trainer, data, output_dir)
    except Exception as e:
        print(f"ONNX export skipped: {e}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"Results saved to: {output_dir}")

    return trainer, data


def export_onnx(trainer, data, output_dir):
    """ONNX 변환"""
    import torch

    try:
        model_path = trainer.export_cfg.get(
            "model_path", "models/fanghets_attack_classification.pth"
        )
        onnx_path = trainer.export_cfg.get(
            "onnx_path", "models/fanghets_attack_classification.onnx"
        )

        # 더미 입력 생성
        batch_size = 1
        seq_len = data["dataset"].max_seq_len
        input_dim = data["input_dim"]

        dummy_seq = torch.randn(batch_size, seq_len, input_dim)
        dummy_lengths = torch.tensor([seq_len])

        trainer.model.eval()
        torch.onnx.export(
            trainer.model,
            (dummy_seq, dummy_lengths),
            onnx_path,
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            input_names=["sequence", "lengths"],
            output_names=["logits"],
            dynamic_axes={
                "sequence": {0: "batch", 1: "seq_len"},
                "lengths": {0: "batch"},
                "logits": {0: "batch"},
            },
        )
        print(f"ONNX model saved to {onnx_path}")

    except Exception as e:
        print(f"ONNX export failed: {e}")


if __name__ == "__main__":
    trainer, data = main()
