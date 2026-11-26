"""
Tabular Model Training for FALCON, SkyMimic
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import warnings

from catboost import CatBoostClassifier
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
import xgboost as xgb
import yaml

warnings.filterwarnings("ignore")


class TabularTrainer:
    """표형 모델 훈련 클래스"""

    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.model_cfg = self.config["model"]
        self.train_cfg = self.config["training"]
        self.eval_cfg = self.config["evaluation"]
        self.export_cfg = self.config["export"]

        self.models = []
        self.best_model = None
        self.cv_scores = []
        self.feature_importances = None
        self.class_names = None

    def _get_model(self, fold: int = 0):
        """모델 인스턴스 생성"""
        model_type = self.model_cfg["type"]
        params = self.model_cfg["params"].copy()
        params["random_state"] = self.config["seed"] + fold

        if model_type == "lightgbm":
            return lgb.LGBMClassifier(**params)
        elif model_type == "xgboost":
            return xgb.XGBClassifier(**params, eval_metric="mlogloss")
        elif model_type == "catboost":
            params["verbose"] = False
            return CatBoostClassifier(**params)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def train_cv(self, X: np.ndarray, y: np.ndarray, class_names: List[str] = None) -> Dict:
        """Cross-validation 훈련"""
        self.class_names = class_names
        cv_folds = self.train_cfg.get("cv_folds", 5)
        cv_strategy = self.train_cfg.get("cv_strategy", "stratified_kfold")

        if cv_strategy == "stratified_kfold":
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=self.config["seed"])
        else:
            from sklearn.model_selection import KFold

            cv = KFold(n_splits=cv_folds, shuffle=True, random_state=self.config["seed"])

        fold_scores = {"f1_macro": [], "f1_weighted": [], "accuracy": [], "roc_auc": []}
        n_classes = len(class_names) if class_names is not None else len(np.unique(y))
        oof_preds = np.zeros((len(y), n_classes))
        oof_labels = np.zeros(len(y), dtype=int)

        for fold, (trn_idx, val_idx) in enumerate(cv.split(X, y)):
            print(f"\n{'='*50}")
            print(f"Fold {fold+1}/{cv_folds}")
            print(f"{'='*50}")

            X_trn, X_val = X[trn_idx], X[val_idx]
            y_trn, y_val = y[trn_idx], y[val_idx]

            model = self._get_model(fold)

            # Early stopping을 위한 eval set
            eval_set = [(X_val, y_val)]

            if self.model_cfg["type"] == "lightgbm":
                model.fit(
                    X_trn,
                    y_trn,
                    eval_set=eval_set,
                    eval_metric=self.model_cfg.get("eval_metric", "multi_logloss"),
                    callbacks=[
                        lgb.early_stopping(self.model_cfg.get("early_stopping_rounds", 50)),
                        lgb.log_evaluation(100),
                    ],
                )
            elif self.model_cfg["type"] == "xgboost":
                model.fit(
                    X_trn,
                    y_trn,
                    eval_set=eval_set,
                    early_stopping_rounds=self.model_cfg.get("early_stopping_rounds", 50),
                    verbose=100,
                )
            elif self.model_cfg["type"] == "catboost":
                model.fit(
                    X_trn,
                    y_trn,
                    eval_set=eval_set,
                    early_stopping_rounds=self.model_cfg.get("early_stopping_rounds", 50),
                    verbose=100,
                )

            self.models.append(model)

            # 검증
            val_pred = model.predict(X_val)
            val_proba = model.predict_proba(X_val)

            # 메트릭 계산
            f1_macro = f1_score(y_val, val_pred, average="macro")
            f1_weighted = f1_score(y_val, val_pred, average="weighted")
            acc = accuracy_score(y_val, val_pred)
            try:
                roc_auc = roc_auc_score(y_val, val_proba, multi_class="ovr")
            except:
                roc_auc = 0.0

            fold_scores["f1_macro"].append(f1_macro)
            fold_scores["f1_weighted"].append(f1_weighted)
            fold_scores["accuracy"].append(acc)
            fold_scores["roc_auc"].append(roc_auc)

            oof_preds[val_idx] = val_proba
            oof_labels[val_idx] = val_pred

            print(
                f"Fold {fold+1} - Macro F1: {f1_macro:.4f}, Weighted F1: {f1_weighted:.4f}, Acc: {acc:.4f}, AUC: {roc_auc:.4f}"
            )

        self.cv_scores = fold_scores

        # CV 결과 요약
        print(f"\n{'='*50}")
        print("CV RESULTS SUMMARY")
        print(f"{'='*50}")
        for metric, scores in fold_scores.items():
            print(f"{metric}: {np.mean(scores):.4f} ± {np.std(scores):.4f}")

        # Best model 선택 (가장 좋은 fold)
        best_fold = np.argmax(fold_scores["f1_macro"])
        self.best_model = self.models[best_fold]
        print(f"\nBest fold: {best_fold+1} (Macro F1: {fold_scores['f1_macro'][best_fold]:.4f})")

        # Feature importance
        self._extract_feature_importance()

        # Threshold optimization (선택적)
        if self.train_cfg.get("optimize_threshold", False):
            self._optimize_thresholds(oof_preds, oof_labels)

        return {
            "cv_scores": fold_scores,
            "oof_predictions": oof_preds,
            "oof_labels": oof_labels,
            "best_fold": best_fold,
        }

    def train_full(self, X: np.ndarray, y: np.ndarray) -> None:
        """전체 데이터로 재훈련"""
        print("\nTraining on full dataset...")
        self.best_model = self._get_model(0)

        if self.model_cfg["type"] == "lightgbm":
            self.best_model.fit(X, y)
        elif self.model_cfg["type"] == "xgboost":
            self.best_model.fit(X, y)
        elif self.model_cfg["type"] == "catboost":
            self.best_model.fit(X, y, verbose=False)

        self._extract_feature_importance()

    def _extract_feature_importance(self) -> None:
        """피처 중요도 추출"""
        if self.best_model is None:
            return

        model_type = self.model_cfg["type"]
        if model_type == "lightgbm":
            self.feature_importances = self.best_model.feature_importances_
        elif model_type == "xgboost":
            self.feature_importances = self.best_model.feature_importances_
        elif model_type == "catboost":
            self.feature_importances = self.best_model.get_feature_importance()

    def _optimize_thresholds(self, oof_proba: np.ndarray, oof_labels: np.ndarray) -> None:
        """클래스별 임계값 최적화"""
        from scipy.optimize import minimize_scalar

        n_classes = oof_proba.shape[1]
        self.optimal_thresholds = np.ones(n_classes) * 0.5

        for c in range(n_classes):

            def f1_thresh(thresh):
                pred = (oof_proba[:, c] >= thresh).astype(int)
                true = (oof_labels == c).astype(int)
                return -f1_score(true, pred, zero_division=0)

            res = minimize_scalar(f1_thresh, bounds=(0.01, 0.99), method="bounded")
            self.optimal_thresholds[c] = res.x

        print(f"Optimized thresholds: {self.optimal_thresholds}")

    def predict(self, X: np.ndarray, use_threshold: bool = False) -> np.ndarray:
        """예측"""
        if self.best_model is None:
            raise ValueError("Model not trained yet")

        if use_threshold and hasattr(self, "optimal_thresholds"):
            proba = self.best_model.predict_proba(X)
            n_samples = X.shape[0]
            preds = np.zeros(n_samples, dtype=int)

            for i in range(n_samples):
                # 임계값 적용 후 가장 높은 클래스 선택
                scored = proba[i] * self.optimal_thresholds
                preds[i] = np.argmax(scored)
            return preds
        else:
            return self.best_model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """확률 예측"""
        if self.best_model is None:
            raise ValueError("Model not trained yet")
        return self.best_model.predict_proba(X)

    def evaluate(self, X: np.ndarray, y: np.ndarray, class_names: List[str] = None) -> Dict:
        """상세 평가"""
        if self.best_model is None:
            raise ValueError("Model not trained yet")

        y_pred = self.predict(X)
        y_proba = self.predict_proba(X)

        results = {
            "f1_macro": f1_score(y, y_pred, average="macro"),
            "f1_weighted": f1_score(y, y_pred, average="weighted"),
            "accuracy": accuracy_score(y, y_pred),
            "roc_auc_ovr": roc_auc_score(y, y_proba, multi_class="ovr"),
            "precision_macro": precision_score(y, y_pred, average="macro", zero_division=0),
            "recall_macro": recall_score(y, y_pred, average="macro", zero_division=0),
        }

        # Per-class 리포트
        if self.eval_cfg.get("per_class_report", True):
            report = classification_report(
                y, y_pred, target_names=class_names, output_dict=True, zero_division=0
            )
            results["classification_report"] = report

        # Confusion matrix
        if self.eval_cfg.get("confusion_matrix", True):
            cm = confusion_matrix(y, y_pred)
            results["confusion_matrix"] = cm.tolist()

        return results

    def save_model(self, path: str) -> None:
        """모델 저장"""
        if self.best_model is None:
            raise ValueError("No model to save")

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        model_type = self.model_cfg["type"]
        if model_type == "lightgbm":
            self.best_model.booster_.save_model(path)
        elif model_type in ["xgboost", "catboost"]:
            joblib.dump(self.best_model, path)

        # 메타데이터 저장
        meta = {
            "model_type": model_type,
            "feature_importances": (
                self.feature_importances.tolist() if self.feature_importances is not None else None
            ),
            "class_names": (
                self.class_names.tolist()
                if hasattr(self.class_names, "tolist")
                else list(self.class_names) if self.class_names is not None else None
            ),
            "optimal_thresholds": (
                self.optimal_thresholds.tolist() if hasattr(self, "optimal_thresholds") else None
            ),
            "cv_scores": {k: [float(v) for v in vals] for k, vals in self.cv_scores.items()},
        }
        import json

        meta_path = path.replace(".txt", "_meta.json").replace(".pkl", "_meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        print(f"Model saved to {path}")
        print(f"Meta saved to {meta_path}")

    def load_model(self, path: str) -> None:
        """모델 로드"""
        model_type = self.model_cfg["type"]
        if model_type == "lightgbm":
            self.best_model = lgb.Booster(model_file=path)
        elif model_type in ["xgboost", "catboost"]:
            self.best_model = joblib.load(path)

        # 메타데이터 로드
        import json

        meta_path = path.replace(".txt", "_meta.json").replace(".pkl", "_meta.json")
        if Path(meta_path).exists():
            with open(meta_path, "r") as f:
                meta = json.load(f)
            self.feature_importances = (
                np.array(meta.get("feature_importances"))
                if meta.get("feature_importances")
                else None
            )
            self.class_names = meta.get("class_names")
            self.optimal_thresholds = (
                np.array(meta.get("optimal_thresholds")) if meta.get("optimal_thresholds") else None
            )
            self.cv_scores = meta.get("cv_scores", {})

        print(f"Model loaded from {path}")


def run_falcon_training(
    config_path: str, data_splits: Dict, feature_names: List, class_names: List
) -> TabularTrainer:
    """FALCON 훈련 실행 헬퍼"""
    trainer = TabularTrainer(config_path)

    # Train + Val로 CV
    X_train, y_train = data_splits["train"]
    X_val, y_val = data_splits["val"]
    X_test, y_test = data_splits["test"]

    # CV 훈련
    cv_results = trainer.train_cv(X_train, y_train, class_names)

    # 전체 데이터로 재훈련
    X_full = np.vstack([X_train, X_val, X_test])
    y_full = np.hstack([y_train, y_val, y_test])
    trainer.train_full(X_full, y_full)

    # Test 세트 평가
    print("\n" + "=" * 50)
    print("TEST SET EVALUATION")
    print("=" * 50)
    test_results = trainer.evaluate(X_test, y_test, class_names)

    for metric, value in test_results.items():
        if isinstance(value, (int, float)):
            print(f"{metric}: {value:.4f}")

    # 모델 저장
    export_path = trainer.export_cfg.get("model_path", "models/falcon_intrusion_detection.txt")
    trainer.save_model(export_path)

    return trainer
