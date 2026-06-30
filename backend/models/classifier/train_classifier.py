"""Classifier training + evaluation script.

Trains both MLP and SVM on ADNI-derived fused feature vectors.
Applies SMOTE for class imbalance handling.

Run:
    python -m backend.models.classifier.train_classifier \\
        --features_csv data/clinical/adni_features.csv \\
        --save_dir data/checkpoints
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from torch.utils.data import DataLoader, TensorDataset

from backend.models.classifier.alzheimer_classifier import AlzheimerMLP, STAGES
from backend.utils.logger import get_logger

logger = get_logger(__name__)

STAGE_MAP = {"CN": "Normal", "MCI": "MCI", "AD": "AD",
             "Normal": "Normal", "0": "Normal", "1": "MCI", "2": "AD"}


def load_dataset(features_csv: str) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(features_csv)
    label_col = "stage" if "stage" in df.columns else df.columns[-1]
    X = df.drop(columns=[label_col]).values.astype(np.float32)
    y_raw = df[label_col].astype(str).map(STAGE_MAP).fillna("Normal")
    le = LabelEncoder()
    le.fit(STAGES)
    y = le.transform(y_raw).astype(np.int64)
    return X, y


def apply_smote(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    try:
        from imblearn.over_sampling import SMOTE
        smote = SMOTE(random_state=42)
        X_res, y_res = smote.fit_resample(X, y)
        logger.info(f"SMOTE applied: {len(X)} → {len(X_res)} samples")
        return X_res, y_res
    except ImportError:
        logger.warning("imbalanced-learn not installed — skipping SMOTE")
        return X, y


def train_mlp(X_train: np.ndarray, y_train: np.ndarray,
              X_val: np.ndarray, y_val: np.ndarray,
              save_dir: Path, epochs: int = 100, lr: float = 1e-3) -> None:
    input_dim = X_train.shape[1]
    model = AlzheimerMLP(input_dim=input_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    X_t = torch.tensor(X_train)
    y_t = torch.tensor(y_train)
    loader = DataLoader(TensorDataset(X_t, y_t), batch_size=32, shuffle=True)

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if epoch % 20 == 0:
            model.eval()
            with torch.no_grad():
                val_logits = model(torch.tensor(X_val))
                val_preds = val_logits.argmax(dim=1).numpy()
            acc = (val_preds == y_val).mean()
            logger.info(f"MLP Epoch {epoch}/{epochs} loss={total_loss/len(loader):.4f} val_acc={acc:.4f}")

    torch.save({"model_state": model.state_dict(), "input_dim": input_dim},
               save_dir / "classifier.pth")
    logger.info(f"MLP checkpoint saved to {save_dir}/classifier.pth")

    model.eval()
    with torch.no_grad():
        test_preds = model(torch.tensor(X_val)).argmax(dim=1).numpy()
    print(classification_report(y_val, test_preds, target_names=STAGES))
    print("Confusion matrix:\n", confusion_matrix(y_val, test_preds))


def train_svm(X_train: np.ndarray, y_train: np.ndarray,
              X_val: np.ndarray, y_val: np.ndarray,
              save_dir: Path) -> None:
    svm = SVC(kernel="rbf", C=1.0, probability=True, random_state=42)
    svm.fit(X_train, y_train)

    val_preds = svm.predict(X_val)
    acc = (val_preds == y_val).mean()
    logger.info(f"SVM validation accuracy: {acc:.4f}")
    print(classification_report(y_val, val_preds, target_names=STAGES))

    with open(save_dir / "classifier.pkl", "wb") as f:
        pickle.dump(svm, f)
    logger.info(f"SVM checkpoint saved to {save_dir}/classifier.pkl")


def train(features_csv: str, save_dir: str = "data/checkpoints",
          epochs: int = 100, run_svm: bool = True) -> None:
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    X, y = load_dataset(features_csv)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_test, y_test, test_size=0.5, stratify=y_test, random_state=42)

    X_train, y_train = apply_smote(X_train, y_train)

    logger.info(f"Dataset: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
    train_mlp(X_train, y_train, X_val, y_val, save_path, epochs=epochs)
    if run_svm:
        train_svm(X_train, y_train, X_val, y_val, save_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features_csv", required=True)
    parser.add_argument("--save_dir", default="data/checkpoints")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--no_svm", action="store_true")
    args = parser.parse_args()
    train(args.features_csv, args.save_dir, args.epochs, not args.no_svm)
