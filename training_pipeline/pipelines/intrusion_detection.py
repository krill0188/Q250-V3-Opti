"""
FALCON Intrusion Detection Pipeline
"""

import sys

sys.path.append("/Users/amaster/data/additional_datasets/training_pipeline")

from pathlib import Path

import yaml
from data.tabular_dataset import load_falcon_data

from training.tabular_trainer import run_falcon_training


def main():
    config_path = (
        "/Users/amaster/data/additional_datasets/training_pipeline/config/falcon.yaml"
    )

    print("=" * 60)
    print("FALCON INTRUSION DETECTION PIPELINE")
    print("=" * 60)

    # 1. 데이터 로드 및 전처리
    print("\n[1/4] Loading and preprocessing data...")
    data = load_falcon_data(config_path)

    print(f"  Input dim: {data['input_dim']}")
    print(f"  Num classes: {data['num_classes']}")
    print(f"  Classes: {data['class_names']}")
    print(f"  Train: {data['splits']['train'][0].shape}")
    print(f"  Val: {data['splits']['val'][0].shape}")
    print(f"  Test: {data['splits']['test'][0].shape}")

    # 2. 모델 훈련
    print("\n[2/4] Training model with cross-validation...")
    trainer = run_falcon_training(
        config_path, data["splits"], data["feature_names"], data["class_names"]
    )

    # 3. 결과 저장
    print("\n[3/4] Saving results...")
    import json

    results = {
        "cv_scores": {
            k: [float(v) for v in vals] for k, vals in trainer.cv_scores.items()
        },
        "feature_importances": (
            trainer.feature_importances.tolist()
            if trainer.feature_importances is not None
            else None
        ),
        "feature_names": data["feature_names"],
        "class_names": (
            data["class_names"].tolist()
            if hasattr(data["class_names"], "tolist")
            else list(data["class_names"])
        ),
        "model_type": trainer.model_cfg["type"],
    }

    output_dir = Path(
        "/Users/amaster/data/additional_datasets/training_pipeline/outputs/falcon"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Feature importance CSV
    if trainer.feature_importances is not None:
        import pandas as pd

        # feature_names는 선택된 피처만 포함 (feature selection 후)
        fi_features = data["feature_names"]
        fi_importance = trainer.feature_importances

        if len(fi_features) == len(fi_importance):
            fi_df = pd.DataFrame(
                {"feature": fi_features, "importance": fi_importance}
            ).sort_values("importance", ascending=False)
            fi_df.to_csv(output_dir / "feature_importance.csv", index=False)
            print(f"\nTop 20 Features:")
            print(fi_df.head(20).to_string(index=False))
        else:
            print(
                f"\nFeature importance length mismatch: features={len(fi_features)}, importance={len(fi_importance)}"
            )
            # 중요도만 저장
            fi_df = pd.DataFrame({"importance": fi_importance}).sort_values(
                "importance", ascending=False
            )
            fi_df.to_csv(output_dir / "feature_importance.csv", index=False)
            print(f"Saved importance only (length: {len(fi_importance)})")
            print(f"Top 20 Importance values:")
            print(fi_df.head(20).to_string(index=False))

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
    import onnx
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    # LightGBM을 sklearn wrapper로 감싸서 변환
    # 또는 onnxmltools 사용
    try:
        import onnxmltools
        from onnxmltools.convert.lightgbm import convert as convert_lgbm

        model_path = trainer.export_cfg.get(
            "model_path", "models/falcon_intrusion_detection.txt"
        )
        onnx_path = trainer.export_cfg.get(
            "onnx_path", "models/falcon_intrusion_detection.onnx"
        )

        # Booster 로드
        import lightgbm as lgb

        booster = lgb.Booster(model_file=model_path)

        # 변환
        onnx_model = convert_lgbm(
            booster,
            initial_types=[("input", FloatTensorType([None, data["input_dim"]]))],
        )

        Path(onnx_path).parent.mkdir(parents=True, exist_ok=True)
        onnxmltools.utils.save_model(onnx_model, onnx_path)
        print(f"ONNX model saved to {onnx_path}")

    except ImportError:
        print("onnxmltools not installed. Install with: pip install onnxmltools")
        # 대안: pickle로 저장된 모델 사용
        pass


if __name__ == "__main__":
    trainer, data = main()
