#!/usr/bin/env python3
"""
Ensemble Learning for Audio Classification
K-fold Cross Validation, Seed Ensemble, Model Averaging
"""

import os
import json
import random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset, ConcatDataset
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score, classification_report
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import copy

from train_audio_classifier import (
    AudioDataset,
    AudioCNNLSTM,
    train_epoch,
    validate,
    compute_class_weights,
    FocalLoss,
)
from augmentation import get_augmentation_pipeline, mixup_criterion


class EnsembleTrainer:
    """K-fold cross validation ensemble trainer"""

    def __init__(
        self,
        data_dir: str,
        task: str = "multiclass",
        n_splits: int = 5,
        random_state: int = 42,
        device: str = "cpu",
    ):
        self.data_dir = Path(data_dir) / task
        self.task = task
        self.n_splits = n_splits
        self.random_state = random_state
        self.device = torch.device(device)

        # Load full dataset
        train_features = self.data_dir / "train" / "features.npz"
        val_features = self.data_dir / "val" / "features.npz"

        self.train_dataset = AudioDataset(str(train_features))
        self.val_dataset = AudioDataset(str(val_features))

        # Combine train + val for K-fold
        self.full_dataset = ConcatDataset([self.train_dataset, self.val_dataset])

        # Get labels for stratification
        self.labels = np.concatenate(
            [self.train_dataset.labels, self.val_dataset.labels]
        )

        self.num_classes = 2 if task == "binary" else 3
        self.class_weights = compute_class_weights(self.labels, self.num_classes).to(
            self.device
        )

        print(f"Full dataset: {len(self.full_dataset)} samples")
        print(f"Class distribution: {np.bincount(self.labels)}")

    def train_fold(
        self,
        fold_idx: int,
        train_idx: np.ndarray,
        val_idx: np.ndarray,
        epochs: int = 30,
        batch_size: int = 64,
        lr: float = 1e-3,
        loss_type: str = "weighted_ce",
        use_augmentation: bool = True,
        save_dir: Optional[Path] = None,
    ) -> Dict:
        """Train a single fold"""
        print(f"\n{'='*50}")
        print(f"Fold {fold_idx + 1}/{self.n_splits}")
        print(f"Train: {len(train_idx)}, Val: {len(val_idx)}")

        # Create subsets
        train_subset = Subset(self.full_dataset, train_idx)
        val_subset = Subset(self.full_dataset, val_idx)

        train_loader = DataLoader(
            train_subset, batch_size=batch_size, shuffle=True, num_workers=0
        )
        val_loader = DataLoader(
            val_subset, batch_size=batch_size, shuffle=False, num_workers=0
        )

        # Model
        model = AudioCNNLSTM(num_classes=self.num_classes).to(self.device)

        # Loss function
        if loss_type == "focal":
            criterion = FocalLoss(alpha=self.class_weights, gamma=2.0)
        elif loss_type == "weighted_ce":
            criterion = nn.CrossEntropyLoss(weight=self.class_weights)
        else:
            criterion = nn.CrossEntropyLoss()

        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        # Augmentation
        aug_pipeline = get_augmentation_pipeline("medium") if use_augmentation else None

        best_val_f1 = 0
        best_model_state = None
        patience = 10
        patience_counter = 0

        history = {
            "train_loss": [],
            "train_acc": [],
            "train_f1": [],
            "val_loss": [],
            "val_acc": [],
            "val_f1": [],
        }

        for epoch in range(epochs):
            # Training
            model.train()
            train_loss = 0
            train_preds = []
            train_labels = []

            for features, labels in train_loader:
                features = features.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()

                if use_augmentation and random.random() < 0.5:
                    # Apply batch augmentation
                    features_aug, y_a, y_b, lam = aug_pipeline.apply_batch_augment(
                        features, labels
                    )
                    outputs = model(features_aug)
                    loss = mixup_criterion(criterion, outputs, y_a, y_b, lam)
                else:
                    outputs = model(features)
                    loss = criterion(outputs, labels)

                loss.backward()
                optimizer.step()

                train_loss += loss.item()
                preds = outputs.argmax(dim=1).cpu().numpy()
                train_preds.extend(preds)
                train_labels.extend(labels.cpu().numpy())

            # Validation
            val_loss, val_acc, val_f1, val_labels, val_preds = validate(
                model, val_loader, criterion, self.device
            )

            scheduler.step()

            # Metrics
            train_acc = accuracy_score(train_labels, train_preds)
            train_f1 = f1_score(train_labels, train_preds, average="weighted")

            history["train_loss"].append(train_loss / len(train_loader))
            history["train_acc"].append(train_acc)
            history["train_f1"].append(train_f1)
            history["val_loss"].append(val_loss)
            history["val_acc"].append(val_acc)
            history["val_f1"].append(val_f1)

            print(
                f"Epoch {epoch+1}/{epochs}: "
                f"Train Loss: {history['train_loss'][-1]:.4f}, Acc: {train_acc:.4f}, F1: {train_f1:.4f} | "
                f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}, F1: {val_f1:.4f}"
            )

            # Save best
            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                best_model_state = copy.deepcopy(model.state_dict())
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break

        # Load best model
        model.load_state_dict(best_model_state)

        # Final validation
        _, final_acc, final_f1, final_labels, final_preds = validate(
            model, val_loader, criterion, self.device
        )

        # Save fold model
        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "fold": fold_idx,
                    "model_state_dict": best_model_state,
                    "val_f1": best_val_f1,
                    "val_acc": final_acc,
                    "num_classes": self.num_classes,
                    "task": self.task,
                },
                save_dir / f"fold_{fold_idx}_best.pth",
            )

            # Save history
            with open(save_dir / f"fold_{fold_idx}_history.json", "w") as f:
                json.dump(history, f, indent=2)

        return {
            "fold": fold_idx,
            "val_f1": best_val_f1,
            "val_acc": final_acc,
            "test_f1": final_f1,
            "model": model,
            "history": history,
        }

    def run_kfold(
        self,
        epochs: int = 30,
        batch_size: int = 64,
        lr: float = 1e-3,
        loss_type: str = "weighted_ce",
        use_augmentation: bool = True,
        save_dir: str = "./checkpoints/ensemble",
    ) -> Dict:
        """Run K-fold cross validation"""
        save_dir = Path(save_dir) / self.task
        save_dir.mkdir(parents=True, exist_ok=True)

        # Stratified K-Fold
        skf = StratifiedKFold(
            n_splits=self.n_splits, shuffle=True, random_state=self.random_state
        )

        fold_results = []

        for fold_idx, (train_idx, val_idx) in enumerate(
            skf.split(np.arange(len(self.labels)), self.labels)
        ):
            result = self.train_fold(
                fold_idx,
                train_idx,
                val_idx,
                epochs=epochs,
                batch_size=batch_size,
                lr=lr,
                loss_type=loss_type,
                use_augmentation=use_augmentation,
                save_dir=save_dir,
            )
            fold_results.append(result)

        # Ensemble predictions (average probabilities)
        print(f"\n{'='*50}")
        print("ENSEMBLE RESULTS")
        print(f"{'='*50}")

        val_f1s = [r["val_f1"] for r in fold_results]
        test_f1s = [r["test_f1"] for r in fold_results]

        print(f"Fold Val F1s: {[f'{f:.4f}' for f in val_f1s]}")
        print(f"Mean Val F1: {np.mean(val_f1s):.4f} ± {np.std(val_f1s):.4f}")
        print(f"Fold Test F1s: {[f'{f:.4f}' for f in test_f1s]}")
        print(f"Mean Test F1: {np.mean(test_f1s):.4f} ± {np.std(test_f1s):.4f}")

        # Save ensemble summary
        summary = {
            "n_splits": self.n_splits,
            "fold_results": [
                {
                    "fold": r["fold"],
                    "val_f1": r["val_f1"],
                    "val_acc": r["val_acc"],
                    "test_f1": r["test_f1"],
                }
                for r in fold_results
            ],
            "mean_val_f1": float(np.mean(val_f1s)),
            "std_val_f1": float(np.std(val_f1s)),
            "mean_test_f1": float(np.mean(test_f1s)),
            "std_test_f1": float(np.std(test_f1s)),
        }

        with open(save_dir / "ensemble_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return summary


class SeedEnsemble:
    """Train multiple models with different random seeds and average predictions"""

    def __init__(
        self,
        data_dir: str,
        task: str = "multiclass",
        seeds: Optional[List[int]] = None,
        device: str = "cpu",
    ):
        self.data_dir = Path(data_dir) / task
        self.task = task
        self.seeds = seeds or [42, 123, 456, 789, 999]
        self.device = torch.device(device)

        self.train_dataset = AudioDataset(str(self.data_dir / "train" / "features.npz"))
        self.val_dataset = AudioDataset(str(self.data_dir / "val" / "features.npz"))
        self.test_dataset = AudioDataset(str(self.data_dir / "test" / "features.npz"))

        self.num_classes = 2 if task == "binary" else 3
        self.class_weights = compute_class_weights(
            self.train_dataset.labels, self.num_classes
        ).to(self.device)

    def train_seed(
        self,
        seed: int,
        epochs: int = 30,
        batch_size: int = 64,
        lr: float = 1e-3,
        loss_type: str = "weighted_ce",
        use_augmentation: bool = True,
    ) -> Dict:
        """Train model with specific seed"""
        torch.manual_seed(seed)
        np.random.seed(seed)
        random.seed(seed)

        print(f"\n{'='*50}")
        print(f"Seed {seed}")
        print(f"{'='*50}")

        train_loader = DataLoader(
            self.train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
        )
        val_loader = DataLoader(
            self.val_dataset, batch_size=batch_size, shuffle=False, num_workers=0
        )

        model = AudioCNNLSTM(num_classes=self.num_classes).to(self.device)

        if loss_type == "focal":
            criterion = FocalLoss(alpha=self.class_weights, gamma=2.0)
        elif loss_type == "weighted_ce":
            criterion = nn.CrossEntropyLoss(weight=self.class_weights)
        else:
            criterion = nn.CrossEntropyLoss()

        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        aug_pipeline = get_augmentation_pipeline("medium") if use_augmentation else None

        best_val_f1 = 0
        best_model_state = None
        patience = 10
        patience_counter = 0

        for epoch in range(epochs):
            model.train()
            for features, labels in train_loader:
                features = features.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()

                if use_augmentation and random.random() < 0.5:
                    features_aug, y_a, y_b, lam = aug_pipeline.apply_batch_augment(
                        features, labels
                    )
                    outputs = model(features_aug)
                    loss = mixup_criterion(criterion, outputs, y_a, y_b, lam)
                else:
                    outputs = model(features)
                    loss = criterion(outputs, labels)

                loss.backward()
                optimizer.step()

            val_loss, val_acc, val_f1, _, _ = validate(
                model, val_loader, criterion, self.device
            )
            scheduler.step()

            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                best_model_state = copy.deepcopy(model.state_dict())
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break

        model.load_state_dict(best_model_state)

        # Test evaluation
        test_loader = DataLoader(
            self.test_dataset, batch_size=batch_size, shuffle=False, num_workers=0
        )
        test_loss, test_acc, test_f1, test_labels, test_preds = validate(
            model, test_loader, criterion, self.device
        )

        return {
            "seed": seed,
            "val_f1": best_val_f1,
            "test_f1": test_f1,
            "test_acc": test_acc,
            "model_state": best_model_state,
            "test_labels": test_labels,
            "test_preds": test_preds,
        }

    def run_ensemble(
        self,
        epochs: int = 30,
        batch_size: int = 64,
        lr: float = 1e-3,
        loss_type: str = "weighted_ce",
        use_augmentation: bool = True,
        save_dir: str = "./checkpoints/seed_ensemble",
    ) -> Dict:
        """Train ensemble with different seeds"""
        save_dir = Path(save_dir) / self.task
        save_dir.mkdir(parents=True, exist_ok=True)

        results = []
        all_test_probs = []
        all_test_labels = None

        for seed in self.seeds:
            result = self.train_seed(
                seed, epochs, batch_size, lr, loss_type, use_augmentation
            )
            results.append(result)

            # Save individual model
            torch.save(
                {
                    "seed": seed,
                    "model_state_dict": result["model_state"],
                    "val_f1": result["val_f1"],
                    "test_f1": result["test_f1"],
                },
                save_dir / f"seed_{seed}_best.pth",
            )

        # Ensemble prediction (average probabilities from each model)
        print(f"\n{'='*50}")
        print("SEED ENSEMBLE RESULTS")
        print(f"{'='*50}")

        test_f1s = [r["test_f1"] for r in results]
        print(f"Seed Test F1s: {[f'{f:.4f}' for f in test_f1s]}")
        print(f"Mean Test F1: {np.mean(test_f1s):.4f} ± {np.std(test_f1s):.4f}")

        # Ensemble prediction (average probabilities from each model)
        test_loader = DataLoader(
            self.test_dataset, batch_size=64, shuffle=False, num_workers=0
        )

        all_probs = []
        for seed in self.seeds:
            model = AudioCNNLSTM(num_classes=self.num_classes).to(self.device)
            checkpoint = torch.load(
                save_dir / f"seed_{seed}_best.pth", map_location=self.device
            )
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()

            probs = []
            with torch.no_grad():
                for features, _ in test_loader:
                    features = features.to(self.device)
                    outputs = model(features)
                    probs.append(F.softmax(outputs, dim=1).cpu().numpy())

            all_probs.append(np.vstack(probs))

        # Average probabilities
        ensemble_probs = np.mean(all_probs, axis=0)
        ensemble_preds = ensemble_probs.argmax(axis=1)

        # Get true labels
        test_labels = self.test_dataset.labels
        ensemble_acc = accuracy_score(test_labels, ensemble_preds)
        ensemble_f1 = f1_score(test_labels, ensemble_preds, average="weighted")

        print(f"Ensemble Test Acc: {ensemble_acc:.4f}")
        print(f"Ensemble Test F1: {ensemble_f1:.4f}")

        if self.task == "binary":
            target_names = ["unknown", "yes_drone"]
        else:
            target_names = ["unknown", "bebop_1", "membo_1"]
        print(
            classification_report(
                test_labels, ensemble_preds, target_names=target_names, zero_division=0
            )
        )

        # Save ensemble summary
        summary = {
            "seeds": self.seeds,
            "individual_results": [
                {
                    "seed": r["seed"],
                    "val_f1": r["val_f1"],
                    "test_f1": r["test_f1"],
                    "test_acc": r["test_acc"],
                }
                for r in results
            ],
            "ensemble_test_acc": float(ensemble_acc),
            "ensemble_test_f1": float(ensemble_f1),
        }

        with open(save_dir / "seed_ensemble_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return summary


def train_kfold_ensemble(
    data_dir: str,
    task: str = "multiclass",
    n_splits: int = 5,
    epochs: int = 30,
    **kwargs,
) -> Dict:
    """Convenience function for K-fold ensemble"""
    trainer = EnsembleTrainer(data_dir, task, n_splits=n_splits)
    return trainer.run_kfold(epochs=epochs, **kwargs)


def train_seed_ensemble(
    data_dir: str,
    task: str = "multiclass",
    seeds: Optional[List[int]] = None,
    epochs: int = 30,
    **kwargs,
) -> Dict:
    """Convenience function for seed ensemble"""
    ensemble = SeedEnsemble(data_dir, task, seeds=seeds)
    return ensemble.run_ensemble(epochs=epochs, **kwargs)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=str,
        default="/Users/amaster/data/drone_datasets/processed/drone_audio",
    )
    parser.add_argument(
        "--task", type=str, choices=["binary", "multiclass"], default="multiclass"
    )
    parser.add_argument("--mode", type=str, choices=["kfold", "seed"], default="seed")
    parser.add_argument("--epochs", type=int, default=5)  # Quick test
    parser.add_argument("--n_splits", type=int, default=3)
    args = parser.parse_args()

    if args.mode == "kfold":
        train_kfold_ensemble(
            args.data, args.task, n_splits=args.n_splits, epochs=args.epochs
        )
    else:
        train_seed_ensemble(args.data, args.task, epochs=args.epochs)
