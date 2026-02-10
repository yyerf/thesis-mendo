"""Interactive CLI: compare V1 vs V2 models + Mendo core on any sentence.

Usage:
  python training/compare_models_cli.py
  python training/compare_models_cli.py --v1 training/symptom_classifier_v1.joblib --v2 training/symptom_classifier_v2.joblib
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

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
    parser = argparse.ArgumentParser(description="Compare V1 vs V2 models + Mendo core")
    parser.add_argument(
        "--v1",
        type=str,
        default="training/symptom_classifier_v1.joblib",
        help="V1 model path (2,170 samples)",
    )
    parser.add_argument(
        "--v2",
        type=str,
        default="training/symptom_classifier_v2.joblib",
        help="V2 model path (3,670 samples)",
    )
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="Run quick test on typo cases and exit",
    )
    args = parser.parse_args()

    v1_path = _resolve(args.v1)
    v2_path = _resolve(args.v2)
    
    v1_model = None
    v2_model = None
    
    if v1_path.exists():
        v1_model = joblib.load(v1_path)
        print(f"✅ Loaded V1: {v1_path.name}")
    else:
        print(f"⚠️  V1 not found: {v1_path}")
    
    if v2_path.exists():
        v2_model = joblib.load(v2_path)
        print(f"✅ Loaded V2: {v2_path.name}")
    else:
        print(f"⚠️  V2 not found: {v2_path}")

    if args.quick_test:
        print("\n" + "="*70)
        print("🧪 QUICK TEST: Typos and Edge Cases")
        print("="*70)
        
        test_cases = [
            ("sepun ako", "runny_nose"),
            ("ubu ako grabe", "cough"),
            ("masaket ulo", "headache"),
            ("lagnt ko", "fever"),
            ("moubo ko", "cough"),
            ("init init katawan", "fever"),
        ]
        
        v1_correct = 0
        v2_correct = 0
        
        for text, expected in test_cases:
            v1_pred = _predict_ml(text, v1_model) if v1_model else []
            v2_pred = _predict_ml(text, v2_model) if v2_model else []
            
            v1_match = expected in v1_pred
            v2_match = expected in v2_pred
            
            if v1_match:
                v1_correct += 1
            if v2_match:
                v2_correct += 1
            
            print(f"\n📝 {text:20s} (expect: {expected})")
            print(f"   V1: {v1_pred} {'✅' if v1_match else '❌'}")
            print(f"   V2: {v2_pred} {'✅' if v2_match else '❌'}")
        
        print("\n" + "="*70)
        print(f"V1: {v1_correct}/{len(test_cases)} correct ({v1_correct/len(test_cases):.1%})")
        print(f"V2: {v2_correct}/{len(test_cases)} correct ({v2_correct/len(test_cases):.1%})")
        print("="*70)
        
        if v2_correct > v1_correct:
            print("\n🎉 V2 IS BETTER on typos/edge cases!")
        elif v2_correct == v1_correct:
            print("\n⚖️  V1 and V2 perform equally")
        else:
            print("\n⚠️  V1 performs better - V2 needs review")
        
        return 0

    print("\n💡 Type a sentence to compare (or 'exit' to quit)")
    print("   Try typos like: 'sepun ako', 'ubu grabe', 'masaket ulo'\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not text or text.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        v1_labels = _predict_ml(text, v1_model) if v1_model else []
        v2_labels = _predict_ml(text, v2_model) if v2_model else []
        core_labels = _normalize_hybrid(list(extract_symptoms_hybrid(text)))

        print(f"V1:   {v1_labels}")
        print(f"V2:   {v2_labels}")
        print(f"Core: {core_labels}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
