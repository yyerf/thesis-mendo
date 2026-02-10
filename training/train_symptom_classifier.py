"""Train a supervised multi-label symptom classifier.

This gives the thesis a true trained ML component.

Usage (example):
  python training/train_symptom_classifier.py \
    --data data/datasets/symptom_eval.sample.jsonl \
    --model-out training/symptom_classifier.joblib
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
import sys

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import RuleRegexModel, SYMPTOM_LABELS
from mendo_core.step3_hybrid import extract_symptoms_hybrid


def load_jsonl(path: Path) -> Tuple[List[str], List[List[str]]]:
    texts: List[str] = []
    labels: List[List[str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            text = (obj.get("text") or "").strip()
            lbls = obj.get("labels") or []
            if not isinstance(lbls, list):
                raise ValueError("labels must be a list")
            if text:
                texts.append(text)
                labels.append([str(x).strip() for x in lbls if str(x).strip()])
    if not texts:
        raise ValueError(f"No valid rows found in {path}")
    return texts, labels


def _resolve_path(path_str: str) -> Path:
    raw = Path(path_str)
    if raw.is_absolute():
        return raw
    base_dir = Path(__file__).resolve().parents[1]
    return (base_dir / raw).resolve()


def _binarize_predictions(
    label_set_list: List[List[str]],
    mlb: MultiLabelBinarizer,
) -> np.ndarray:
    allowed = set(mlb.classes_)
    cleaned = [[lbl for lbl in labels if lbl in allowed] for labels in label_set_list]
    return mlb.transform(cleaned)


def _normalize_hybrid_labels(labels: List[str]) -> List[str]:
    normalized: List[str] = []
    for lbl in labels:
        key = (lbl or "").strip().lower()
        if key in {"cough_productive", "cough_dry", "cough_general"}:
            key = "cough"
        if key in SYMPTOM_LABELS:
            normalized.append(key)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a multi-label symptom classifier")
    parser.add_argument(
        "--data",
        type=str,
        default="data/datasets/symptom_eval.sample.jsonl",
        help="Path to JSONL dataset",
    )
    parser.add_argument(
        "--model-out",
        type=str,
        default="training/symptom_classifier.joblib",
        help="Where to save the trained model",
    )
    parser.add_argument(
        "--metrics-out",
        type=str,
        default="training/symptom_classifier_metrics.json",
        help="Where to save evaluation metrics",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split size")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Probability threshold for multi-label prediction",
    )
    args = parser.parse_args()

    data_path = _resolve_path(args.data)
    model_out = _resolve_path(args.model_out)
    metrics_out = _resolve_path(args.metrics_out)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.parent.mkdir(parents=True, exist_ok=True)

    texts, labels = load_jsonl(data_path)

    label_counts: Dict[str, int] = {k: 0 for k in SYMPTOM_LABELS}
    for row in labels:
        for lbl in row:
            if lbl in label_counts:
                label_counts[lbl] += 1

    print("=== Dataset Summary ===")
    print(f"Rows: {len(texts)}")
    print("Label counts (non-zero):")
    for k in SYMPTOM_LABELS:
        if label_counts[k] > 0:
            print(f"  {k}: {label_counts[k]}")

    X_train, X_test, y_train_raw, y_test_raw = train_test_split(
        texts,
        labels,
        test_size=args.test_size,
        random_state=args.seed,
        shuffle=True,
    )

    mlb = MultiLabelBinarizer(classes=SYMPTOM_LABELS)
    mlb.fit([SYMPTOM_LABELS])
    y_train = mlb.transform(y_train_raw)
    y_test = mlb.transform(y_test_raw)

    train_label_counts: Dict[str, int] = {k: 0 for k in SYMPTOM_LABELS}
    for row in y_train_raw:
        for lbl in row:
            if lbl in train_label_counts:
                train_label_counts[lbl] += 1
    missing_in_train = [k for k, v in train_label_counts.items() if v == 0]
    if missing_in_train:
        print("\n⚠️  Labels missing in training split:")
        print("  " + ", ".join(missing_in_train))
        print("  Consider adding more data or lowering --test-size.")

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_features=30000,
    )

    clf = OneVsRestClassifier(
        LogisticRegression(
            max_iter=1000,
            solver="liblinear",
            class_weight="balanced",
        )
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    clf.fit(X_train_vec, y_train)

    X_test_vec = vectorizer.transform(X_test)

    if hasattr(clf, "predict_proba"):
        y_scores = clf.predict_proba(X_test_vec)
        y_pred = (y_scores >= args.threshold).astype(int)
    else:
        y_pred = clf.predict(X_test_vec)

    micro_f1 = f1_score(y_test, y_pred, average="micro", zero_division=0)
    macro_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
    micro_p = precision_score(y_test, y_pred, average="micro", zero_division=0)
    micro_r = recall_score(y_test, y_pred, average="micro", zero_division=0)

    report = classification_report(
        y_test,
        y_pred,
        labels=list(range(len(mlb.classes_))),
        target_names=list(mlb.classes_),
        zero_division=0,
    )

    # Baseline comparison using Mendo rule-based model
    rule_model = RuleRegexModel()
    rule_preds_raw = [sorted(rule_model.predict(text)) for text in X_test]
    rule_pred = _binarize_predictions(rule_preds_raw, mlb)
    rule_micro_f1 = f1_score(y_test, rule_pred, average="micro", zero_division=0)
    rule_macro_f1 = f1_score(y_test, rule_pred, average="macro", zero_division=0)
    rule_micro_p = precision_score(y_test, rule_pred, average="micro", zero_division=0)
    rule_micro_r = recall_score(y_test, rule_pred, average="micro", zero_division=0)

    # Hybrid baseline using Mendo step3 (dictionary + semantic fallback)
    hybrid_preds_raw = [
        sorted(_normalize_hybrid_labels(list(extract_symptoms_hybrid(text))))
        for text in X_test
    ]
    hybrid_pred = _binarize_predictions(hybrid_preds_raw, mlb)
    hybrid_micro_f1 = f1_score(y_test, hybrid_pred, average="micro", zero_division=0)
    hybrid_macro_f1 = f1_score(y_test, hybrid_pred, average="macro", zero_division=0)
    hybrid_micro_p = precision_score(y_test, hybrid_pred, average="micro", zero_division=0)
    hybrid_micro_r = recall_score(y_test, hybrid_pred, average="micro", zero_division=0)

    metrics = {
        "micro_f1": micro_f1,
        "macro_f1": macro_f1,
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "baseline_rules": {
            "micro_f1": rule_micro_f1,
            "macro_f1": rule_macro_f1,
            "micro_precision": rule_micro_p,
            "micro_recall": rule_micro_r,
        },
        "baseline_hybrid": {
            "micro_f1": hybrid_micro_f1,
            "macro_f1": hybrid_macro_f1,
            "micro_precision": hybrid_micro_p,
            "micro_recall": hybrid_micro_r,
        },
        "classes": list(mlb.classes_),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "threshold": args.threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    model_payload = {
        "vectorizer": vectorizer,
        "classifier": clf,
        "label_binarizer": mlb,
        "threshold": args.threshold,
        "created_at": metrics["timestamp"],
    }
    joblib.dump(model_payload, model_out)

    print("=== Training Complete ===")
    print(f"Model saved: {model_out}")
    print(f"Metrics saved: {metrics_out}")
    print("\n=== Summary Metrics (ML) ===")
    print(f"micro_f1: {micro_f1:.4f}")
    print(f"macro_f1: {macro_f1:.4f}")
    print(f"micro_precision: {micro_p:.4f}")
    print(f"micro_recall: {micro_r:.4f}")
    print("\n=== Summary Metrics (Rule Baseline) ===")
    print(f"micro_f1: {rule_micro_f1:.4f}")
    print(f"macro_f1: {rule_macro_f1:.4f}")
    print(f"micro_precision: {rule_micro_p:.4f}")
    print(f"micro_recall: {rule_micro_r:.4f}")
    print("\n=== Summary Metrics (Hybrid Baseline) ===")
    print(f"micro_f1: {hybrid_micro_f1:.4f}")
    print(f"macro_f1: {hybrid_macro_f1:.4f}")
    print(f"micro_precision: {hybrid_micro_p:.4f}")
    print(f"micro_recall: {hybrid_micro_r:.4f}")
    print("\n=== Classification Report ===")
    print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
