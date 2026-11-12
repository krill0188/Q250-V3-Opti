#!/usr/bin/env python3
"""
DroneAudioDataset 오디오 분류 모델 학습
- Binary: unknown vs yes_drone
- Multiclass: unknown, bebop_1, membo_1
- Input: MFCC (40차원, 157 timesteps)
- Architecture: CNN + LSTM
- Class imbalance handling: Class weights + Focal Loss
"""

import os
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.utils.class_weight import compute_class_weight
import argparse
from pathlib import Path


class AudioDataset(Dataset):
    def __init__(self, features_path, labels_path=None):
        """NPZ 파일에서 특징과 라벨 로드"""
        data = np.load(features_path)
        self.features = data["features"]  # (N, 6280) = (N, 157*40) - flattened
        self.labels = data["labels"]      # (N,)

        # Flatten된 (N, 6280) -> (N, 157, 40) -> (N, 1, 157, 40) for CNN
        self.features = self.features.astype(np.float32)
        self.features = self.features.reshape(-1, 157, 40)  # (N, 157, 40)
        self.features = np.expand_dims(self.features, axis=1)  # (N, 1, 157, 40)

        print(f"Loaded {len(self.features)} samples, shape: {self.features.shape}")
        print(f"Label distribution: {np.bincount(self.labels)}")

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return torch.from_numpy(self.features[idx]), torch.tensor(
            self.labels[idx], dtype=torch.long
        )


class AudioCNNLSTM(nn.Module):
    def __init__(self, num_classes, input_channels=1, hidden_dim=128, num_layers=2):
        super().__init__()

        # CNN Feature Extractor
        self.cnn = nn.Sequential(
            # Input: (B, 1, 157, 40)
            nn.Conv2d(input_channels, 32, kernel_size=(3, 3), padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d((2, 2)),  # -> (B, 32, 78, 20)
            nn.Conv2d(32, 64, kernel_size=(3, 3), padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d((2, 2)),  # -> (B, 64, 39, 10)
            nn.Conv2d(64, 128, kernel_size=(3, 3), padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),  # -> (B, 128, 1, 1)
        )

        # LSTM for temporal modeling
        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=0.3 if num_layers > 1 else 0,
        )

        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        # x: (B, 1, 157, 40)
        batch_size = x.size(0)

        # CNN feature extraction
        x = self.cnn(x)  # (B, 128, 1, 1)
        x = x.squeeze(-1).squeeze(-1)  # (B, 128)

        # Add sequence dimension for LSTM
        x = x.unsqueeze(1)  # (B, 1, 128)

        # LSTM
        lstm_out, _ = self.lstm(x)  # (B, 1, hidden_dim*2)
        x = lstm_out.squeeze(1)  # (B, hidden_dim*2)

        # Classification
        x = self.classifier(x)
        return x


class FocalLoss(nn.Module):
    """Focal Loss for addressing class imbalance"""
    def __init__(self, alpha=None, gamma=2.0, reduction='mean'):
        super().__init__()
        self.alpha = alpha  # 클래스별 가중치 (Tensor)
        self.gamma = gamma  # focusing parameter
        self.reduction = reduction

    def forward(self, inputs, targets):
        ce_loss = nn.functional.cross_entropy(inputs, targets, weight=self.alpha, reduction='none')
        pt = torch.exp(-ce_loss)
        focal_loss = (1 - pt) ** self.gamma * ce_loss
        
        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        return focal_loss


def compute_class_weights(labels, num_classes):
    """클래스별 가중치 계산 (inverse frequency)"""
    classes = np.arange(num_classes)
    weights = compute_class_weight('balanced', classes=classes, y=labels)
    return torch.tensor(weights, dtype=torch.float32)


def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0
    all_preds = []
    all_labels = []

    for features, labels in loader:
        features = features.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(features)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        preds = outputs.argmax(dim=1).cpu().numpy()
        all_preds.extend(preds)
        all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(loader)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="weighted")

    return avg_loss, acc, f1


def validate(model, loader, criterion, device):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)

            outputs = model(features)
            loss = criterion(outputs, labels)

            total_loss += loss.item()
            preds = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(loader)
    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average="weighted")

    return avg_loss, acc, f1, all_labels, all_preds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=str,
        default="/Users/amaster/data/drone_datasets/processed/drone_audio",
        help="데이터 루트 경로",
    )
    parser.add_argument(
        "--task",
        type=str,
        choices=["binary", "multiclass"],
        default="binary",
        help="학습 태스크",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument(
        "--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu"
    )
    parser.add_argument("--save_dir", type=str, default="./checkpoints")
    parser.add_argument("--loss", type=str, choices=["ce", "focal", "weighted_ce"], default="weighted_ce",
                        help="Loss function: ce (CrossEntropy), focal (FocalLoss), weighted_ce (Class weighted CE)")
    parser.add_argument("--gamma", type=float, default=2.0, help="Focal loss gamma")
    args = parser.parse_args()

    device = torch.device(args.device)
    print(f"Using device: {device}")
    print(f"Loss function: {args.loss}")

    # 데이터 경로 설정
    task_dir = Path(args.data) / args.task
    train_features = task_dir / "train" / "features.npz"
    val_features = task_dir / "val" / "features.npz"
    test_features = task_dir / "test" / "features.npz"

    # 클래스 수 결정
    if args.task == "binary":
        num_classes = 2
    else:
        num_classes = 3

    # 데이터 로더 생성
    train_dataset = AudioDataset(str(train_features))
    val_dataset = AudioDataset(str(val_features))
    test_dataset = AudioDataset(str(test_features))

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0
    )
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0
    )

    # 모델 생성
    model = AudioCNNLSTM(num_classes=num_classes).to(device)
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Class weights 계산 (train set 기준)
    train_labels = train_dataset.labels
    class_weights = compute_class_weights(train_labels, num_classes).to(device)
    print(f"Class weights: {class_weights}")

    # 손실 함수 설정
    if args.loss == "focal":
        criterion = FocalLoss(alpha=class_weights, gamma=args.gamma)
        print(f"Using Focal Loss (gamma={args.gamma}) with class weights")
    elif args.loss == "weighted_ce":
        criterion = nn.CrossEntropyLoss(weight=class_weights)
        print(f"Using CrossEntropyLoss with class weights")
    else:
        criterion = nn.CrossEntropyLoss()
        print(f"Using standard CrossEntropyLoss")

    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # 체크포인트 디렉토리
    save_dir = Path(args.save_dir) / args.task
    save_dir.mkdir(parents=True, exist_ok=True)

    # 학습 루프
    best_val_f1 = 0
    patience = 10
    patience_counter = 0

    for epoch in range(args.epochs):
        train_loss, train_acc, train_f1 = train_epoch(
            model, train_loader, criterion, optimizer, device
        )
        val_loss, val_acc, val_f1, _, _ = validate(model, val_loader, criterion, device)
        scheduler.step()

        print(
            f"Epoch {epoch+1}/{args.epochs}: "
            f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f}, F1: {train_f1:.4f} | "
            f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}, F1: {val_f1:.4f} | "
            f"LR: {optimizer.param_groups[0]['lr']:.6f}"
        )

        # 베스트 모델 저장
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            patience_counter = 0
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_f1": val_f1,
                    "val_acc": val_acc,
                    "num_classes": num_classes,
                    "task": args.task,
                    "loss_type": args.loss,
                },
                save_dir / "best_model.pth",
            )
            print(f"  -> Best model saved (Val F1: {val_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch+1}")
                break

    # 테스트 평가
    print("\n=== Test Evaluation ===")
    checkpoint = torch.load(save_dir / "best_model.pth")
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc, test_f1, test_labels, test_preds = validate(
        model, test_loader, criterion, device
    )

    print(f"Test Loss: {test_loss:.4f}, Acc: {test_acc:.4f}, F1: {test_f1:.4f}")
    print("\nClassification Report:")
    if args.task == "binary":
        target_names = ["unknown", "yes_drone"]
    else:
        target_names = ["unknown", "bebop_1", "membo_1"]
    print(classification_report(test_labels, test_preds, target_names=target_names, zero_division=0))

    # ONNX 내보내기 (배포용)
    dummy_input = torch.randn(1, 1, 157, 40).to(device)
    torch.onnx.export(
        model,
        dummy_input,
        save_dir / "model.onnx",
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        opset_version=11,
    )
    print(f"ONNX model exported to {save_dir / 'model.onnx'}")


if __name__ == "__main__":
    main()