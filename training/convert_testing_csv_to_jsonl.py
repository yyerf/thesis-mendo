"""Convert testing/benchmark/testing.csv to JSONL training data.

Outputs canonical labels aligned to mendo_core.symptom_models.SYMPTOM_LABELS.

Usage:
  python training/convert_testing_csv_to_jsonl.py \
    --input testing/benchmark/testing.csv \
    --output data/datasets/symptom_eval.from_testing.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import SYMPTOM_LABELS


LABEL_MAP: Dict[str, List[str]] = {
    "HEADACHE": ["headache"],
    "FEVER": ["fever"],
    "COUGH_DRY": ["cough"],
    "COUGH_PRODUCTIVE": ["cough"],
    "COUGH_GENERAL": ["cough"],
    "COUGH": ["cough"],
    "RUNNY_NOSE": ["runny_nose"],
    "NASAL_CONGESTION": ["stuffy_nose"],
    "STOMACH_ACHE": ["stomach_ache"],
    "DIARRHEA": ["diarrhea"],
    "BODY_ACHES": ["body_aches"],
    "SORE_THROAT": ["sore_throat"],
    "DIZZINESS": ["dizziness"],
    "NAUSEA": ["nausea"],
    "VOMITING": ["vomiting"],
    "FATIGUE": ["fatigue"],
    "SHORTNESS_OF_BREATH": ["shortness_of_breath"],
    "CHEST_PAIN": ["chest_pain"],
    "NONE": [],
}


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _map_labels(raw: str) -> Tuple[List[str], List[str]]:
    raw = (raw or "").strip()
    if not raw:
        return [], []

    labels: List[str] = []
    dropped: List[str] = []

    for part in raw.split(","):
        token = part.strip().upper()
        if not token:
            continue
        if token in LABEL_MAP:
            labels.extend(LABEL_MAP[token])
        else:
            dropped.append(token)

    # ensure canonical + unique
    canonical = [lbl for lbl in labels if lbl in SYMPTOM_LABELS]
    return sorted(set(canonical)), dropped


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert testing.csv to JSONL dataset")
    parser.add_argument(
        "--input",
        type=str,
        default="testing/benchmark/testing.csv",
        help="Path to testing.csv",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/datasets/symptom_eval.from_testing.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args()

    input_path = _resolve(args.input)
    output_path = _resolve(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    kept = 0
    dropped_label_counts: Dict[str, int] = {}
    empty_labels = 0

    with input_path.open("r", encoding="utf-8") as f_in, output_path.open(
        "w", encoding="utf-8"
    ) as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            total += 1
            text = (row.get("input_text") or "").strip()
            raw_labels = (row.get("expected_symptoms") or "").strip()
            labels, dropped = _map_labels(raw_labels)
            if not text:
                continue

            if not labels:
                empty_labels += 1
            else:
                kept += 1

            for d in dropped:
                dropped_label_counts[d] = dropped_label_counts.get(d, 0) + 1

            record = {
                "id": row.get("test_id") or f"test_{total}",
                "text": text,
                "labels": labels,
            }
            f_out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print("=== Conversion Complete ===")
    print(f"Input rows: {total}")
    print(f"Rows with labels kept: {kept}")
    print(f"Rows with empty labels: {empty_labels}")
    if dropped_label_counts:
        top = sorted(dropped_label_counts.items(), key=lambda x: x[1], reverse=True)
        print("\nDropped label counts (top 15):")
        for name, count in top[:15]:
            print(f"  {name}: {count}")

    print(f"\nOutput JSONL: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
