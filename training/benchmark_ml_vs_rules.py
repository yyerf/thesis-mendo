"""Benchmark ML vs Mendo core baselines on a JSONL dataset.

Usage:
  python training/benchmark_ml_vs_rules.py \
    --data data/datasets/symptom_eval.from_testing.jsonl \
    --model training/symptom_classifier.joblib
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import sys

import joblib
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.preprocessing import MultiLabelBinarizer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import RuleRegexModel, SYMPTOM_LABELS
from mendo_core.step3_hybrid import extract_symptoms_hybrid


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _load_jsonl(path: Path) -> Tuple[List[str], List[List[str]]]:
    texts: List[str] = []
    labels: List[List[str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            texts.append(obj.get("text", ""))
            labels.append(obj.get("labels") or [])
    return texts, labels


def _binarize(label_list: List[List[str]], mlb: MultiLabelBinarizer) -> np.ndarray:
    allowed = set(mlb.classes_)
    cleaned = [[lbl for lbl in labels if lbl in allowed] for labels in label_list]
    return mlb.transform(cleaned)


def _normalize_hybrid(labels: List[str]) -> List[str]:
    normalized: List[str] = []
    for lbl in labels:
        key = (lbl or "").strip().lower()
        if key in {"cough_productive", "cough_dry", "cough_general"}:
            key = "cough"
        if key in SYMPTOM_LABELS:
            normalized.append(key)
    return normalized


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "micro_f1": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "micro_precision": precision_score(y_true, y_pred, average="micro", zero_division=0),
        "micro_recall": recall_score(y_true, y_pred, average="micro", zero_division=0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ML vs rules")
    parser.add_argument(
        "--data",
        type=str,
        default="data/datasets/symptom_eval.synthetic.jsonl",
        help="JSONL dataset path",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="training/symptom_classifier.joblib",
        help="Trained model file",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="testing/benchmark/results/benchmark_ml_vs_rules.json",
        help="Output metrics JSON",
    )
    args = parser.parse_args()

    data_path = _resolve(args.data)
    model_path = _resolve(args.model)
    out_path = _resolve(args.out)

    texts, labels = _load_jsonl(data_path)

    mlb = MultiLabelBinarizer(classes=SYMPTOM_LABELS)
    mlb.fit([SYMPTOM_LABELS])
    y_true = _binarize(labels, mlb)

    model = joblib.load(model_path)
    vectorizer = model["vectorizer"]
    clf = model["classifier"]
    threshold = model.get("threshold", 0.5)

    X_vec = vectorizer.transform(texts)
    if hasattr(clf, "predict_proba"):
        scores = clf.predict_proba(X_vec)
        y_ml = (scores >= threshold).astype(int)
    else:
        y_ml = clf.predict(X_vec)

    rules = RuleRegexModel()
    y_rules = _binarize([sorted(rules.predict(t)) for t in texts], mlb)

    y_hybrid = _binarize(
        [sorted(_normalize_hybrid(list(extract_symptoms_hybrid(t)))) for t in texts],
        mlb,
    )

    results = {
        "ml": _metrics(y_true, y_ml),
        "baseline_rules": _metrics(y_true, y_rules),
        "baseline_hybrid": _metrics(y_true, y_hybrid),
        "dataset": str(data_path),
        "count": len(texts),
    }

    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("=== Benchmark Complete ===")
    print(json.dumps(results, indent=2))
    print(f"\nSaved to: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
