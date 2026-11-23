"""
Sequence Model Training for FAN-GHETS24, FANET
"""

import json
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau, StepLR
from torch.utils.data import DataLoader

warnings.filterwarnings("ignore")

from models.sequence.attack_classifier import get_model


class SequenceTrainer:
    """시퀀스 모델 훈련 클래스"""

    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.model_cfg = self.config["model"]
        self.train_cfg = self.config["training"]
        self.eval_cfg = self.config["evaluation"]
        self.export_cfg = self.config["export"]

        self.device = self._get_device()
        self.model = None
        self.best_model_state = None
        self.history = {"train_loss": [], "val_loss": [], "val_f1": [], "val_acc": []}
        self.class_names = None

    def _get_device(self) -> torch.device:
        device_cfg = self.config.get("device", "auto")
        if device_cfg == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device_cfg)

    def build_model(
        self, input_dim: int, num_classes: int, class_names: List[str]
    ) -> None:
        """모델 생성"""
        self.class_names = class_names

        model_params = self.model_cfg["params"].copy()
        model_params.update({"input_dim": input_dim, "num_classes": num_classes})

        self.model = get_model(self.model_cfg["type"], **model_params)
        self.model = self.model.to(self.device)

        # 클래스 가중치
        if self.train_cfg.get("class_weights") == "balanced":
            # 나중 dataloader에서 계산
            pass

        print(f"Model: {self.model_cfg['type']}")
        print(f"Parameters: {sum(p.numel() for p in self.model.parameters()):,}")
        print(f"Device: {self.device}")

    def _get_criterion(self, class_weights: Optional[torch.Tensor] = None):
        """Loss 함수"""
        if class_weights is not None:
            class_weights = class_weights.to(self.device)
        return nn.CrossEntropyLoss(weight=class_weights)

    def _get_optimizer(self):
        """옵티마이저"""
        lr = self.train_cfg["learning_rate"]
        wd = self.train_cfg["weight_decay"]
        opt_type = self.train_cfg.get("optimizer", "adamw")

        if opt_type == "adamw":
            return AdamW(self.model.parameters(), lr=lr, weight_decay=wd)
        elif opt_type == "adam":
            return torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=wd)
        elif opt_type == "sgd":
            return torch.optim.SGD(
                self.model.parameters(), lr=lr, weight_decay=wd, momentum=0.9
            )
        else:
            return AdamW(self.model.parameters(), lr=lr, weight_decay=wd)

    def _get_scheduler(self, optimizer):
        """스케줄러"""
        sched_type = self.train_cfg.get("scheduler", "cosine")
        epochs = self.train_cfg["epochs"]
        lr = self.train_cfg["learning_rate"]

        if sched_type == "cosine":
            return CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.01)
        elif sched_type == "plateau":
            return ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=5)
        elif sched_type == "step":
            return StepLR(optimizer, step_size=epochs // 3, gamma=0.1)
        return None

    def _compute_class_weights(self, labels: np.ndarray) -> torch.Tensor:
        """클래스 가중치 계산"""
        from sklearn.utils.class_weight import compute_class_weight

        classes = np.unique(labels)
        weights = compute_class_weight("balanced", classes=classes, y=labels)
        return torch.FloatTensor(weights)

    def train_epoch(
        self,
        dataloader: DataLoader,
        criterion,
        optimizer,
        class_weights: Optional[torch.Tensor] = None,
    ) -> Dict:
        """한 에폭 훈련"""
        self.model.train()
        total_loss = 0
        all_preds = []
        all_labels = []

        grad_clip = self.train_cfg.get("gradient_clip", 1.0)

        for batch in dataloader:
            sequences = batch["sequence"].to(self.device)
            labels = batch["label"].to(self.device)
            lengths = batch["length"].to(self.device)

            optimizer.zero_grad()
            logits = self.model(sequences, lengths)
            loss = criterion(logits, labels)
            loss.backward()

            if grad_clip:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), grad_clip)

            optimizer.step()

            total_loss += loss.item()
            preds = logits.argmax(dim=1).detach().cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().numpy())

        avg_loss = total_loss / len(dataloader)
        f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0)
        acc = accuracy_score(all_labels, all_preds)

        return {"loss": avg_loss, "f1_macro": f1, "accuracy": acc}

    def validate(self, dataloader: DataLoader, criterion) -> Dict:
        """검증"""
        self.model.eval()
        total_loss = 0
        all_preds = []
        all_labels = []
        all_probas = []

        with torch.no_grad():
            for batch in dataloader:
                sequences = batch["sequence"].to(self.device)
                labels = batch["label"].to(self.device)
                lengths = batch["length"].to(self.device)

                logits = self.model(sequences, lengths)
                loss = criterion(logits, labels)

                total_loss += loss.item()
                probas = F.softmax(logits, dim=1).cpu().numpy()
                preds = logits.argmax(dim=1).cpu().numpy()

                all_probas.extend(probas)
                all_preds.extend(preds)
                all_labels.extend(labels.cpu().numpy())

        avg_loss = total_loss / len(dataloader)
        f1_macro = f1_score(all_labels, all_preds, average="macro", zero_division=0)
        f1_weighted = f1_score(
            all_labels, all_preds, average="weighted", zero_division=0
        )
        acc = accuracy_score(all_labels, all_preds)

        try:
            roc_auc = roc_auc_score(all_labels, all_probas, multi_class="ovr")
        except:
            roc_auc = 0.0

        return {
            "loss": avg_loss,
            "f1_macro": f1_macro,
            "f1_weighted": f1_weighted,
            "accuracy": acc,
            "roc_auc": roc_auc,
            "predictions": np.array(all_preds),
            "labels": np.array(all_labels),
            "probabilities": np.array(all_probas),
        }

    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        class_weights: Optional[torch.Tensor] = None,
    ) -> Dict:
        """전체 훈련 루프"""
        criterion = self._get_criterion(class_weights)
        optimizer = self._get_optimizer()
        scheduler = self._get_scheduler(optimizer)

        epochs = self.train_cfg["epochs"]
        patience = self.train_cfg.get("early_stopping_patience", 10)

        best_val_f1 = 0
        patience_counter = 0

        print(f"\nStarting training for {epochs} epochs...")
        print(f"Early stopping patience: {patience}")

        for epoch in range(1, epochs + 1):
            start_time = time.time()

            # Train
            train_metrics = self.train_epoch(
                train_loader, criterion, optimizer, class_weights
            )

            # Validate
            val_metrics = self.validate(val_loader, criterion)

            # Scheduler step
            if scheduler:
                if isinstance(scheduler, ReduceLROnPlateau):
                    scheduler.step(val_metrics["f1_macro"])
                else:
                    scheduler.step()

            # History
            self.history["train_loss"].append(train_metrics["loss"])
            self.history["val_loss"].append(val_metrics["loss"])
            self.history["val_f1"].append(val_metrics["f1_macro"])
            self.history["val_acc"].append(val_metrics["accuracy"])

            # Best model
            if val_metrics["f1_macro"] > best_val_f1:
                best_val_f1 = val_metrics["f1_macro"]
                self.best_model_state = self.model.state_dict().copy()
                patience_counter = 0
                improved = " ★"
            else:
                patience_counter += 1
                improved = ""

            elapsed = time.time() - start_time
            print(
                f"Epoch {epoch:3d}/{epochs} | "
                f"Train Loss: {train_metrics['loss']:.4f} F1: {train_metrics['f1_macro']:.4f} | "
                f"Val Loss: {val_metrics['loss']:.4f} F1: {val_metrics['f1_macro']:.4f} "
                f"Acc: {val_metrics['accuracy']:.4f} AUC: {val_metrics['roc_auc']:.4f} "
                f"({elapsed:.1f}s){improved}"
            )

            if patience_counter >= patience:
                print(f"Early stopping triggered after {epoch} epochs")
                break

        # Load best model
        if self.best_model_state:
            self.model.load_state_dict(self.best_model_state)

        return {
            "best_val_f1": best_val_f1,
            "history": self.history,
            "epochs_trained": epoch,
        }

    def evaluate(self, test_loader: DataLoader) -> Dict:
        """테스트 세트 평가"""
        self.model.eval()
        all_preds = []
        all_labels = []
        all_probas = []

        with torch.no_grad():
            for batch in test_loader:
                sequences = batch["sequence"].to(self.device)
                labels = batch["label"].to(self.device)
                lengths = batch["length"].to(self.device)

                logits = self.model(sequences, lengths)
                probas = F.softmax(logits, dim=1).cpu().numpy()
                preds = logits.argmax(dim=1).cpu().numpy()

                all_probas.extend(probas)
                all_preds.extend(preds)
                all_labels.extend(labels.cpu().numpy())

        y_true = np.array(all_labels)
        y_pred = np.array(all_preds)
        y_proba = np.array(all_probas)

        results = {
            "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
            "f1_weighted": f1_score(
                y_true, y_pred, average="weighted", zero_division=0
            ),
            "accuracy": accuracy_score(y_true, y_pred),
            "roc_auc_ovr": roc_auc_score(y_true, y_proba, multi_class="ovr"),
            "precision_macro": precision_score(
                y_true, y_pred, average="macro", zero_division=0
            ),
            "recall_macro": recall_score(
                y_true, y_pred, average="macro", zero_division=0
            ),
        }

        # Per-class report
        if self.eval_cfg.get("per_class_report", True):
            report = classification_report(
                y_true,
                y_pred,
                target_names=self.class_names,
                output_dict=True,
                zero_division=0,
            )
            results["classification_report"] = report

        # Confusion matrix
        if self.eval_cfg.get("confusion_matrix", True):
            cm = confusion_matrix(y_true, y_pred)
            results["confusion_matrix"] = cm.tolist()

        return results

    def save_model(self, path: str) -> None:
        """모델 저장"""
        if self.model is None:
            raise ValueError("No model to save")

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "model_config": {
                    "type": self.model_cfg["type"],
                    "params": self.model_cfg["params"],
                },
                "class_names": self.class_names,
                "history": self.history,
                "best_val_f1": (
                    max(self.history["val_f1"]) if self.history["val_f1"] else 0
                ),
            },
            path,
        )

        print(f"Model saved to {path}")

    def load_model(self, path: str) -> None:
        """모델 로드"""
        checkpoint = torch.load(path, map_location=self.device)

        # 모델 재구성 필요 (config에서)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.class_names = checkpoint.get("class_names")
        self.history = checkpoint.get("history", {})

        print(f"Model loaded from {path}")


def run_fanghets_training(config_path: str, data: Dict) -> SequenceTrainer:
    """FAN-GHETS24 훈련 실행 헬퍼"""
    from data.sequence_dataset import FANGHETSDataset

    trainer = SequenceTrainer(config_path)
    dataset = data["dataset"]
    splits = data["splits"]
    class_names = data["class_names"]
    input_dim = data["input_dim"]
    num_classes = data["num_classes"]

    # 모델 빌드
    trainer.build_model(input_dim, num_classes, class_names)

    # DataLoaders
    batch_size = trainer.train_cfg["batch_size"]
    train_loader = dataset.create_dataloaders(splits, batch_size=batch_size)["train"]
    val_loader = dataset.create_dataloaders(splits, batch_size=batch_size)["val"]
    test_loader = dataset.create_dataloaders(splits, batch_size=batch_size)["test"]

    # 클래스 가중치
    _, y_train = splits["train"]
    class_weights = trainer._compute_class_weights(y_train)
    print(f"Class weights: {class_weights}")

    # 훈련
    print("\n" + "=" * 60)
    print("TRAINING")
    print("=" * 60)
    train_results = trainer.train(train_loader, val_loader, class_weights)

    # 테스트 평가
    print("\n" + "=" * 60)
    print("TEST EVALUATION")
    print("=" * 60)
    test_results = trainer.evaluate(test_loader)

    for metric, value in test_results.items():
        if isinstance(value, (int, float)):
            print(f"{metric}: {value:.4f}")

    # 모델 저장
    export_path = trainer.export_cfg.get(
        "model_path", "models/fanghets_attack_classification.pth"
    )
    trainer.save_model(export_path)

    return trainer
