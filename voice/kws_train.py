"""
KWS Model Training - 키워드 스팟팅 모델 학습 및 TFLite 변환
MFCC + DS-CNN 아키텍처, INT8 양자화로 임베디드 배포용
"""

import os
import json
import time
import numpy as np
import librosa
import tensorflow as tf
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from typing import Tuple, Dict, List, Optional
import warnings

warnings.filterwarnings("ignore")


# === 하이퍼파라미터 ===
SAMPLE_RATE = 16000
N_MFCC = 13
N_FFT = 480
HOP_LENGTH = 160  # 10ms @ 16kHz
TARGET_FRAMES = 200  # 2초 = 200프레임 @ 10ms
N_CLASSES = 27  # KEYWORD_SPECS 개수

# 학습 설정
BATCH_SIZE = 32
EPOCHS = 100
LEARNING_RATE = 1e-3
PATIENCE = 15
VAL_SPLIT = 0.2


def load_metadata(metadata_file: str) -> List[Dict]:
    """메타데이터 JSONL 로드"""
    data = []
    with open(metadata_file, "r", encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data


def extract_mfcc(audio_path: str) -> np.ndarray:
    """오디오 파일에서 MFCC 특징 추출"""
    audio, _ = librosa.load(audio_path, sr=SAMPLE_RATE)

    mfcc = librosa.feature.mfcc(
        y=audio, sr=SAMPLE_RATE, n_mfcc=N_MFCC, n_fft=N_FFT, hop_length=HOP_LENGTH
    ).T  # (time, n_mfcc)

    # 길이 맞추기
    if len(mfcc) > TARGET_FRAMES:
        mfcc = mfcc[:TARGET_FRAMES]
    elif len(mfcc) < TARGET_FRAMES:
        pad_width = TARGET_FRAMES - len(mfcc)
        mfcc = np.pad(mfcc, ((0, pad_width), (0, 0)), mode="constant")

    return mfcc.astype(np.float32)  # (200, 13)


def prepare_dataset(
    metadata_file: str, audio_dir: str, label_to_idx: Dict[str, int]
) -> Tuple[np.ndarray, np.ndarray]:
    """메타데이터 → 특징/레이블 배열"""
    metadata = load_metadata(metadata_file)

    X = []
    y = []

    print(f"데이터 로드 중: {len(metadata)}개 샘플")
    for i, meta in enumerate(metadata):
        keyword = meta["keyword"]
        if keyword not in label_to_idx:
            continue

        audio_path = Path(audio_dir) / meta["file"]
        if not audio_path.exists():
            print(f"파일 없음: {audio_path}")
            continue

        mfcc = extract_mfcc(str(audio_path))
        X.append(mfcc)
        y.append(label_to_idx[keyword])

        if (i + 1) % 100 == 0:
            print(f"  처리됨: {i + 1}/{len(metadata)}")

    X = np.array(X)  # (N, 200, 13)
    y = np.array(y)

    # 채널 차원 추가 (CNN용: N, H, W, C)
    X = X[..., np.newaxis]  # (N, 200, 13, 1)

    return X, y


def build_ds_cnn_model(
    input_shape: Tuple[int, int, int], num_classes: int
) -> tf.keras.Model:
    """
    DS-CNN (Depthwise Separable CNN) 아키텍처
    Google Speech Commands 논문 기반, 초경량 KWS용
    """
    inputs = tf.keras.Input(shape=input_shape)

    # Initial Conv
    x = tf.keras.layers.Conv2D(
        32, (3, 3), strides=(2, 2), padding="same", use_bias=False, name="conv1"
    )(inputs)
    x = tf.keras.layers.BatchNormalization(name="bn1")(x)
    x = tf.keras.layers.ReLU(name="relu1")(x)

    # Depthwise Separable Blocks
    x = _dw_conv_block(x, 64, (3, 3), strides=(1, 1), name="dw1")
    x = _dw_conv_block(x, 64, (3, 3), strides=(2, 2), name="dw2")
    x = _dw_conv_block(x, 128, (3, 3), strides=(1, 1), name="dw3")
    x = _dw_conv_block(x, 128, (3, 3), strides=(2, 2), name="dw4")
    x = _dw_conv_block(x, 256, (3, 3), strides=(1, 1), name="dw5")

    # Global Average Pooling + Classifier
    x = tf.keras.layers.GlobalAveragePooling2D(name="gap")(x)
    x = tf.keras.layers.Dropout(0.3, name="dropout")(x)
    outputs = tf.keras.layers.Dense(num_classes, activation="softmax", name="output")(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="ds_cnn_kws")
    return model


def _dw_conv_block(x, filters: int, kernel_size: tuple, strides: tuple, name: str):
    """Depthwise Separable Convolution Block"""
    # Depthwise Conv
    x = tf.keras.layers.DepthwiseConv2D(
        kernel_size, strides=strides, padding="same", use_bias=False, name=f"{name}_dw"
    )(x)
    x = tf.keras.layers.BatchNormalization(name=f"{name}_bn_dw")(x)
    x = tf.keras.layers.ReLU(name=f"{name}_relu_dw")(x)

    # Pointwise Conv
    x = tf.keras.layers.Conv2D(
        filters, (1, 1), padding="same", use_bias=False, name=f"{name}_pw"
    )(x)
    x = tf.keras.layers.BatchNormalization(name=f"{name}_bn_pw")(x)
    x = tf.keras.layers.ReLU(name=f"{name}_relu_pw")(x)

    return x


def representative_dataset_gen(X_train: np.ndarray, num_samples: int = 100):
    """양자화용 대표 데이터셋 제너레이터"""
    for i in range(min(num_samples, len(X_train))):
        yield [X_train[i : i + 1].astype(np.float32)]


def convert_to_tflite(
    model: tf.keras.Model, X_train: np.ndarray, output_path: str, quantize: bool = True
) -> bytes:
    """TFLite 변환 (INT8 양자화 옵션)"""
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    if quantize:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = lambda: representative_dataset_gen(X_train)
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8

    tflite_model = converter.convert()

    with open(output_path, "wb") as f:
        f.write(tflite_model)

    print(f"TFLite 모델 저장: {output_path} ({len(tflite_model) / 1024:.1f} KB)")
    return tflite_model


def train_kws(
    metadata_file: str = "~/data/kws_training/metadata.jsonl",
    audio_dir: str = "~/data/kws_training/audio",
    output_dir: str = "~/models/kws",
    augment_dir: Optional[str] = None,
):
    """전체 학습 파이프라인"""

    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. 키워드 라벨 로드 (keyword_specs에서)
    from voice.keyword_specs import get_keywords_list

    keywords = get_keywords_list()
    label_to_idx = {kw: i for i, kw in enumerate(keywords)}
    idx_to_label = {i: kw for i, kw in enumerate(keywords)}

    print(f"클래스 수: {len(keywords)}")
    print(f"키워드: {keywords}")

    # 라벨 저장
    with open(output_path / "labels.json", "w", encoding="utf-8") as f:
        json.dump(idx_to_label, f, ensure_ascii=False, indent=2)

    # 2. 메인 데이터 준비
    print("\n=== 메인 데이터 준비 ===")
    X_train, y_train = prepare_dataset(metadata_file, audio_dir, label_to_idx)
    print(f"훈련 데이터: {X_train.shape}, 레이블: {y_train.shape}")

    # 3. 증강 데이터 추가 (있는 경우)
    if augment_dir and Path(augment_dir).expanduser().exists():
        print("\n=== 증강 데이터 추가 ===")
        augment_meta = Path(augment_dir).expanduser() / "metadata.jsonl"
        augment_audio = Path(augment_dir).expanduser() / "audio"
        if augment_meta.exists():
            X_aug, y_aug = prepare_dataset(
                str(augment_meta), str(augment_audio), label_to_idx
            )
            X_train = np.concatenate([X_train, X_aug])
            y_train = np.concatenate([y_train, y_aug])
            print(f"증강 후: {X_train.shape}")

    # 4. Train/Val 분할
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=VAL_SPLIT, stratify=y_train, random_state=42
    )
    print(f"\nTrain: {X_train.shape}, Val: {X_val.shape}")

    # 5. 클래스 가중치 계산 (불균형 보정)
    class_weights = compute_class_weight(
        "balanced", classes=np.unique(y_train), y=y_train
    )
    class_weight_dict = {i: w for i, w in enumerate(class_weights)}

    # 6. 모델 빌드
    model = build_ds_cnn_model(
        input_shape=(TARGET_FRAMES, N_MFCC, 1), num_classes=len(keywords)
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(LEARNING_RATE),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy", "sparse_top_k_categorical_accuracy"],
    )

    model.summary()

    # 7. 콜백
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=PATIENCE,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", patience=8, factor=0.5, min_lr=1e-6, verbose=1
        ),
        tf.keras.callbacks.ModelCheckpoint(
            str(output_path / "best_kws.h5"),
            monitor="val_accuracy",
            save_best_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.TensorBoard(
            log_dir=str(output_path / "logs"), histogram_freq=1
        ),
    ]

    # 8. 학습
    print("\n=== 학습 시작 ===")
    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        class_weight=class_weight_dict,
        callbacks=callbacks,
        verbose=1,
    )

    # 8. 평가
    print("\n=== 평가 ===")
    results = model.evaluate(X_val, y_val, verbose=1)
    print(f"Validation Loss: {results[0]:.4f}")
    print(f"Validation Acc:  {results[1]:.4f}")
    print(f"Top-5 Acc:       {results[2]:.4f}")

    # 9. TFLite 변환 (INT8 양자화)
    print("\n=== TFLite 변환 (INT8) ===")
    convert_to_tflite(
        model, X_train, str(output_path / "kws_model_int8.tflite"), quantize=True
    )

    # FP16 버전도 저장 (참고용)
    convert_to_tflite(
        model, X_train, str(output_path / "kws_model_fp16.tflite"), quantize=False
    )

    # 10. 학습 곡선 저장
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(12, 4))
    plt.subplot(1, 2, 1)
    plt.plot(history.history["accuracy"], label="Train")
    plt.plot(history.history["val_accuracy"], label="Val")
    plt.title("Accuracy")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(history.history["loss"], label="Train")
    plt.plot(history.history["val_loss"], label="Val")
    plt.title("Loss")
    plt.legend()

    plt.tight_layout()
    plt.savefig(output_path / "training_curves.png", dpi=150)
    plt.close()

    print(f"\n완료! 모델 저장: {output_path}")
    print(f"  - best_kws.h5 (Keras)")
    print(f"  - kws_model_int8.tflite (INT8 양자화)")
    print(f"  - kws_model_fp16.tflite (FP16)")
    print(f"  - labels.json")
    print(f"  - training_curves.png")


def evaluate_tflite(tflite_path: str, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
    """TFLite 모델 평가"""
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    correct = 0
    total = len(X_test)

    for i in range(total):
        input_data = X_test[i : i + 1].astype(np.float32)

        # INT8 양자화 모델이면 입력 양자화
        if input_details[0]["dtype"] == np.int8:
            quant_params = input_details[0]["quantization"]
            if isinstance(quant_params, tuple) and len(quant_params) == 2:
                scale, zero_point = quant_params
            else:
                scale, zero_point = 1.0, 0
            input_data = (input_data / scale + zero_point).astype(np.int8)

        interpreter.set_tensor(input_details[0]["index"], input_data)
        interpreter.invoke()

        output = interpreter.get_tensor(output_details[0]["index"])

        # INT8 출력 디퀀타이즈
        if output_details[0]["dtype"] == np.int8:
            quant_params = output_details[0]["quantization"]
            if isinstance(quant_params, tuple) and len(quant_params) == 2:
                scale, zero_point = quant_params
            else:
                scale, zero_point = 1.0, 0
            output = (output.astype(np.float32) - zero_point) * scale

        pred = np.argmax(output[0])
        if pred == y_test[i]:
            correct += 1

    accuracy = correct / total
    print(f"TFLite 모델 정확도: {accuracy:.4f} ({correct}/{total})")

    return {"accuracy": accuracy, "correct": correct, "total": total}


def test_tflite_inference_speed(tflite_path: str, num_runs: int = 100) -> Dict:
    """TFLite 추론 속도 테스트"""
    interpreter = tf.lite.Interpreter(model_path=tflite_path)
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    input_shape = input_details[0]["shape"]

    # 더미 입력
    dummy_input = np.random.randn(*input_shape).astype(np.float32)
    if input_details[0]["dtype"] == np.int8:
        quant_params = input_details[0]["quantization"]
        if isinstance(quant_params, tuple) and len(quant_params) == 2:
            scale, zero_point = quant_params
        else:
            scale, zero_point = 1.0, 0
        dummy_input = (dummy_input / scale + zero_point).astype(np.int8)

    # 워밍업
    for _ in range(10):
        interpreter.set_tensor(input_details[0]["index"], dummy_input)
        interpreter.invoke()

    # 측정
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        interpreter.set_tensor(input_details[0]["index"], dummy_input)
        interpreter.invoke()
        times.append((time.perf_counter() - start) * 1000)

    times = np.array(times)
    print(f"TFLite 추론 속도 ({num_runs}회):")
    print(f"  평균: {times.mean():.2f}ms")
    print(f"  표준편차: {times.std():.2f}ms")
    print(f"  최소: {times.min():.2f}ms")
    print(f"  최대: {times.max():.2f}ms")

    return {
        "mean_ms": float(times.mean()),
        "std_ms": float(times.std()),
        "min_ms": float(times.min()),
        "max_ms": float(times.max()),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KWS 모델 학습")
    parser.add_argument("--metadata", default="~/data/kws_training/metadata.jsonl")
    parser.add_argument("--audio", default="~/data/kws_training/audio")
    parser.add_argument("--augment", default="~/data/kws_training_aug")
    parser.add_argument("--output", default="~/models/kws")
    parser.add_argument("--eval-only", action="store_true", help="평가만 수행")
    parser.add_argument("--tflite", help="평가할 TFLite 모델 경로")

    args = parser.parse_args()

    if args.eval_only and args.tflite:
        # 평가 모드
        from voice.keyword_specs import get_keywords_list

        keywords = get_keywords_list()
        label_to_idx = {kw: i for i, kw in enumerate(keywords)}

        X_test, y_test = prepare_dataset(args.metadata, args.audio, label_to_idx)
        _, X_test, _, y_test = train_test_split(
            X_test, y_test, test_size=0.2, random_state=42
        )

        evaluate_tflite(args.tflite, X_test, y_test)
        test_tflite_inference_speed(args.tflite)
    else:
        # 학습 모드
        train_kws(args.metadata, args.audio, args.output, args.augment)
