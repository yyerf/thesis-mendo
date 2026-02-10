"""Interactive CLI: compare ML vs Mendo core on any sentence.

Usage:
  python training/compare_models_cli.py --model training/symptom_classifier.joblib
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import sys

import joblib

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import SYMPTOM_LABELS
from mendo_core.step3_hybrid import extract_symptoms_hybrid


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _normalize_hybrid(labels: List[str]) -> List[str]:
    normalized: List[str] = []
    for lbl in labels:
        key = (lbl or "").strip().lower()
        if key in {"cough_productive", "cough_dry", "cough_general"}:
            key = "cough"
        if key in SYMPTOM_LABELS:
            normalized.append(key)
    return sorted(set(normalized))


def _predict_ml(text: str, model: dict) -> List[str]:
    vectorizer = model["vectorizer"]
    clf = model["classifier"]
    mlb = model["label_binarizer"]
    threshold = model.get("threshold", 0.5)

    X_vec = vectorizer.transform([text])
    if hasattr(clf, "predict_proba"):
        scores = clf.predict_proba(X_vec)[0]
        labels = [mlb.classes_[i] for i, s in enumerate(scores) if s >= threshold]
    else:
        pred = clf.predict(X_vec)[0]
        labels = [mlb.classes_[i] for i, v in enumerate(pred) if v == 1]

    return sorted(set([lbl for lbl in labels if lbl in SYMPTOM_LABELS]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare ML vs Mendo core")
    parser.add_argument(
        "--model",
        type=str,
        default="training/symptom_classifier.joblib",
        help="Trained model path",
    )
    args = parser.parse_args()

    model_path = _resolve(args.model)
    model = joblib.load(model_path)

    print("Type a sentence (or 'exit' to quit).")

    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not text or text.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        ml_labels = _predict_ml(text, model)
        core_labels = _normalize_hybrid(list(extract_symptoms_hybrid(text)))

        print(f"ML:   {ml_labels}")
        print(f"Core: {core_labels}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
